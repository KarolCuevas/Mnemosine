from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from app.security.deps import CurrentUser, get_current_user, require_csrf
from app.services import google_drive as service
from app.integrations.google_drive.config import DriveError

router = APIRouter(prefix="/integrations/google_drive", tags=["Google Drive personal"])


def call(function, *args):
    try:
        return function(*args)
    except DriveError as error:
        raise HTTPException(status_code=error.status, detail=str(error),
                            headers={"Retry-After": "3"} if error.status == 429 else None) from None


@router.get("/status")
def status(current: CurrentUser = Depends(get_current_user)):
    return call(service.status, current.user_id)


@router.post("/authorize", dependencies=[Depends(require_csrf)])
def authorize(current: CurrentUser = Depends(get_current_user)):
    return call(service.begin, current)


@router.get("/callback", include_in_schema=False)
def callback(request: Request):
    outcome = "unavailable"
    try:
        current = get_current_user(request)
        params = request.scope.get("google_oauth_query", {})
        outcome = service.complete(current, params.get("state", ""), params.get("code"), params.get("error"))
    except HTTPException:
        outcome = "session_expired"
    except DriveError as error:
        outcome = error.code if error.code in {"invalid_state", "account_mismatch", "scope_denied", "reauth_required", "session_expired"} else "unavailable"
    # Destino fijo; nunca refleja códigos, errores o destinos aportados por el navegador.
    return RedirectResponse("/conexiones?google=" + outcome, status_code=303)


@router.post("/connections/{connection_id}/picker", dependencies=[Depends(require_csrf)])
def picker(connection_id: int, current: CurrentUser = Depends(get_current_user)):
    return call(service.picker, current, connection_id)


class SelectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_ids: list[str] = Field(min_length=1, max_length=5)


@router.post("/connections/{connection_id}/files", dependencies=[Depends(require_csrf)])
def select(connection_id: int, payload: SelectionIn, current: CurrentUser = Depends(get_current_user)):
    return call(service.select_files, current, connection_id, payload.file_ids)


@router.get("/connections/{connection_id}/files")
def files(connection_id: int, page: int = Query(1, ge=1, le=100), current: CurrentUser = Depends(get_current_user)):
    return call(service.selected_files, current.user_id, connection_id, page)


@router.delete("/connections/{connection_id}/files/{selection_id}", dependencies=[Depends(require_csrf)], status_code=204)
def remove(connection_id: int, selection_id: int, current: CurrentUser = Depends(get_current_user)):
    call(service.remove_selection, current, connection_id, selection_id)
    return Response(status_code=204)


@router.post("/connections/{connection_id}/disconnect", dependencies=[Depends(require_csrf)])
def disconnect(connection_id: int, current: CurrentUser = Depends(get_current_user)):
    return call(service.disconnect, current, connection_id)
