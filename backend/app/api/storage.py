from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.security.deps import CurrentUser, get_current_user
from app.services import storage_sources
from app.storage.contract import SourceUnavailableError, StorageError, UnsupportedOperationError

router = APIRouter(tags=["Fuentes de almacenamiento"])


@router.get("/storage/sources")
def sources(response: Response, current: CurrentUser = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    return {"items": storage_sources.list_sources(current.user_id)}


@router.get("/storage/sources/{source_id}/objects")
def objects(source_id: int, response: Response, cursor: str | None = Query(None, max_length=512),
            limit: int = Query(50, ge=1, le=100), current: CurrentUser = Depends(get_current_user)):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return storage_sources.list_objects(current.user_id, source_id, cursor=cursor, limit=limit)
    except SourceUnavailableError:
        raise HTTPException(404, "Fuente no disponible") from None
    except UnsupportedOperationError:
        raise HTTPException(422, "Esta fuente no permite listar objetos") from None
    except StorageError:
        raise HTTPException(503, "No se pudo consultar la fuente") from None
