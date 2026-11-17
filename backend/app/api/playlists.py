"""Listas privadas ordenadas (Fase 4). Solo el dueño lee y modifica su lista."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.schemas.playlists import (
    PlaylistAddTrack,
    PlaylistCreate,
    PlaylistDetail,
    PlaylistReorder,
    PlaylistSummary,
    PlaylistTrack,
    PlaylistUpdate,
)
from app.security.deps import CurrentUser, get_current_user, require_csrf
from app.services import playlists
from app.services.errors import ServiceError
from app.services.playlists import PlaylistNotFoundError

router = APIRouter(prefix="/playlists", tags=["Listas"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")


@router.get("", response_model=list[PlaylistSummary])
def list_playlists(current: CurrentUser = Depends(get_current_user)) -> list[PlaylistSummary]:
    return [PlaylistSummary(**row) for row in playlists.list_playlists(owner_id=current.user_id)]


@router.post("", response_model=PlaylistSummary, status_code=status.HTTP_201_CREATED)
def create_playlist(payload: PlaylistCreate,
                    _csrf: None = Depends(require_csrf),
                    current: CurrentUser = Depends(get_current_user)) -> PlaylistSummary:
    try:
        created = playlists.create_playlist(owner_id=current.user_id, name=payload.name, description=payload.description)
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    return PlaylistSummary(**created, item_count=0)


@router.get("/{playlist_id}", response_model=PlaylistDetail)
def get_playlist(playlist_id: int, current: CurrentUser = Depends(get_current_user)) -> PlaylistDetail:
    try:
        detail = playlists.get_playlist_detail(owner_id=current.user_id, playlist_id=playlist_id)
    except PlaylistNotFoundError:
        raise _not_found()
    return PlaylistDetail(
        playlist_id=detail["playlist_id"],
        name=detail["name"],
        description=detail["description"],
        tracks=[PlaylistTrack(**track) for track in detail["tracks"]],
    )


@router.patch("/{playlist_id}", response_model=PlaylistDetail)
def rename_playlist(playlist_id: int, payload: PlaylistUpdate,
                    _csrf: None = Depends(require_csrf),
                    current: CurrentUser = Depends(get_current_user)) -> PlaylistDetail:
    try:
        playlists.update_playlist(owner_id=current.user_id, playlist_id=playlist_id,
                                  name=payload.name, description=payload.description)
    except PlaylistNotFoundError:
        raise _not_found()
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    detail = playlists.get_playlist_detail(owner_id=current.user_id, playlist_id=playlist_id)
    return PlaylistDetail(
        playlist_id=detail["playlist_id"], name=detail["name"], description=detail["description"],
        tracks=[PlaylistTrack(**track) for track in detail["tracks"]],
    )


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(playlist_id: int,
                    _csrf: None = Depends(require_csrf),
                    current: CurrentUser = Depends(get_current_user)) -> Response:
    try:
        playlists.delete_playlist(owner_id=current.user_id, playlist_id=playlist_id)
    except PlaylistNotFoundError:
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{playlist_id}/tracks", status_code=status.HTTP_201_CREATED)
def add_track(playlist_id: int, payload: PlaylistAddTrack,
              _csrf: None = Depends(require_csrf),
              current: CurrentUser = Depends(get_current_user)) -> dict:
    try:
        return playlists.add_track(owner_id=current.user_id, playlist_id=playlist_id, track_id=payload.track_id)
    except PlaylistNotFoundError:
        raise _not_found()
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.delete("/{playlist_id}/tracks/{track_id}")
def remove_track(playlist_id: int, track_id: int,
                 _csrf: None = Depends(require_csrf),
                 current: CurrentUser = Depends(get_current_user)) -> dict:
    try:
        return playlists.remove_track(owner_id=current.user_id, playlist_id=playlist_id, track_id=track_id)
    except PlaylistNotFoundError:
        raise _not_found()


@router.put("/{playlist_id}/order")
def reorder_tracks(playlist_id: int, payload: PlaylistReorder,
                   _csrf: None = Depends(require_csrf),
                   current: CurrentUser = Depends(get_current_user)) -> dict:
    try:
        return playlists.reorder_tracks(owner_id=current.user_id, playlist_id=playlist_id,
                                        ordered_track_ids=payload.track_ids)
    except PlaylistNotFoundError:
        raise _not_found()
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
