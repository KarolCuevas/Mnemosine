"""Permisos de una copia (Fase 4). Solo el dueño puede modificarlos/consultarlos.

Toda mutación exige sesión + CSRF y queda auditada en PERMISSION_AUDIT. El rol
ADMIN no interviene (matriz revisada).
"""

import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import db
from app.schemas.locations import (
    LocationSummaryOut,
    PublicDownloadUpdate,
    ShareCreate,
    ShareOut,
    VisibilityUpdate,
)
from app.security.deps import CurrentUser, get_current_user, require_csrf
from app.services import sharing
from app.services.errors import ServiceError
from app.services.sharing import CopyNotFoundError, DeclarationRequiredError

router = APIRouter(prefix="/locations/{location_id}", tags=["Permisos de copia"])


def _get_summary(*, location_id: int, user_id: int) -> LocationSummaryOut:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT l.location_id, l.track_id, t.title, a.title AS album, "
            "       l.visibility, l.public_download_allowed, l.availability, "
            "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
            "FROM TRACK_LOCATION l "
            "JOIN TRACK t ON t.track_id = l.track_id "
            "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id "
            "JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            "WHERE l.location_id = %s AND l.owner_user_id = %s "
            "GROUP BY l.location_id, l.track_id, t.title, a.title, l.visibility, "
            "         l.public_download_allowed, l.availability",
            (location_id, user_id),
        )
        location = cursor.fetchone()
        if location is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    shares = sharing.list_shares(owner_id=user_id, location_id=location_id)
    return LocationSummaryOut(**location, shares=[ShareOut(**share) for share in shares])


@router.get("", response_model=LocationSummaryOut)
def get_location(location_id: int, current: CurrentUser = Depends(get_current_user)) -> LocationSummaryOut:
    try:
        return _get_summary(location_id=location_id, user_id=current.user_id)
    except CopyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")


@router.post("/visibility", response_model=LocationSummaryOut)
def set_visibility(location_id: int, payload: VisibilityUpdate,
                   _csrf: None = Depends(require_csrf),
                   current: CurrentUser = Depends(get_current_user)) -> LocationSummaryOut:
    try:
        sharing.set_visibility(user_id=current.user_id, location_id=location_id,
                               publish=payload.publish, declaration=payload.declaration)
    except DeclarationRequiredError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except CopyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    return _get_summary(location_id=location_id, user_id=current.user_id)


@router.post("/public-download", response_model=LocationSummaryOut)
def set_public_download(location_id: int, payload: PublicDownloadUpdate,
                        _csrf: None = Depends(require_csrf),
                        current: CurrentUser = Depends(get_current_user)) -> LocationSummaryOut:
    try:
        sharing.set_public_download(user_id=current.user_id, location_id=location_id,
                                    allow=payload.allow, declaration=payload.declaration)
    except DeclarationRequiredError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except CopyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    return _get_summary(location_id=location_id, user_id=current.user_id)


@router.post("/shares", response_model=LocationSummaryOut, status_code=status.HTTP_201_CREATED)
def create_share(location_id: int, payload: ShareCreate,
                 _csrf: None = Depends(require_csrf),
                 current: CurrentUser = Depends(get_current_user)) -> LocationSummaryOut:
    try:
        sharing.share_with_user(
            owner_id=current.user_id,
            location_id=location_id,
            recipient_username=payload.username,
            can_stream=payload.can_stream,
            can_download=payload.can_download,
            declaration=payload.declaration,
        )
    except DeclarationRequiredError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    except CopyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except mysql.connector.Error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="no se pudo compartir")
    return _get_summary(location_id=location_id, user_id=current.user_id)


@router.delete("/shares/{recipient_user_id}", response_model=LocationSummaryOut)
def delete_share(location_id: int, recipient_user_id: int,
                 _csrf: None = Depends(require_csrf),
                 current: CurrentUser = Depends(get_current_user)) -> LocationSummaryOut:
    try:
        sharing.revoke_share(owner_id=current.user_id, location_id=location_id,
                             recipient_user_id=recipient_user_id)
    except CopyNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    return _get_summary(location_id=location_id, user_id=current.user_id)
