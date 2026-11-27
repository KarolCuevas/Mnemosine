from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.integrations.catalog.contract import CatalogError
from app.repositories import external_catalog as repository
from app.security.deps import CurrentUser, get_current_user, require_csrf
from app.services import external_catalog as service

router = APIRouter(tags=["Referencias musicales"])
User = Annotated[CurrentUser, Depends(get_current_user)]


def _call(function: Callable, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except CatalogError as error:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
        raise HTTPException(error.status, str(error), headers=headers) from None


@router.get("/integrations/providers")
def providers(current: User):
    return {"items": service.providers()}


@router.get("/catalog/recordings")
def local_recordings(current: User, title: str = Query("", max_length=200), artist: str = Query("", max_length=200),
                     page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=50)):
    return repository.local_search(title=title, artist=artist, page=page, page_size=page_size)


@router.get("/external/references")
def references(current: User, response: Response, page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=50)):
    response.headers["Cache-Control"] = "private, no-store"
    return repository.list_references(current.user_id, page=page, page_size=page_size)


class ReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(max_length=64)
    provider_id: str = Field(max_length=128)


@router.post("/external/references", status_code=201, dependencies=[Depends(require_csrf)])
def save_reference(payload: ReferenceInput, current: User, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return _call(service.save, current.user_id, payload.provider, payload.provider_id)


@router.delete("/external/references/{reference_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_reference(reference_id: int, current: User):
    if not repository.delete_reference(current.user_id, reference_id):
        raise HTTPException(404, "No encontrado")
    return Response(status_code=204)


@router.get("/external/{provider}/search")
def external_search(provider: str, current: User, response: Response, title: str = Query(..., min_length=1, max_length=200),
                    artist: str = Query("", max_length=200), cursor: str | None = Query(None, max_length=512),
                    limit: int = Query(20, ge=1, le=25)):
    response.headers["Cache-Control"] = "private, no-store"
    return _call(service.search, provider, title=title, artist=artist, cursor=cursor, limit=limit)


@router.get("/external/{provider}/recordings/{identifier}")
def recording(provider: str, identifier: str, current: User, refresh: bool = False):
    return _call(service.lookup, provider, identifier, refresh=refresh)


@router.get("/external/{provider}/playlists")
def playlists(provider: str, current: User):
    return _call(lambda: service.registry.resolve(provider).list_playlists())
