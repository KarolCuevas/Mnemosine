"""Rutas del recorrido principal (Fase 3): carga, biblioteca, audio, descarga.

Cada solicitud de audio/descarga revalida sesión y permiso sobre la copia
resuelta; nada se sirve desde un directorio estático público. Rutas y rutas
físicas nunca aparecen en las respuestas.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.schemas.tracks import LibraryPage, TrackDetail, UploadResponse, AccessOut
from app.security.deps import CurrentUser, get_current_user, require_csrf
from app.services import copies, delivery, library, uploads
from app.services.delivery import RangeNotSatisfiable
from app.services.storage import get_storage_for_source
from app.storage.contract import SourceUnavailableError, UnsupportedOperationError
from app.services.uploads import QuotaExceededError, UploadValidationError
from app.repositories import db, operations
from app.storage import FileTooLargeError, StorageError

router = APIRouter(tags=["Biblioteca y audio"])


@router.post("/tracks/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_track(
    file: UploadFile = File(...),
    title: str | None = Form(None, max_length=512),
    artist: str | None = Form(None, max_length=255),
    album: str | None = Form(None, max_length=512),
    track_number: int | None = Form(None, ge=1, le=1000),
    disc_number: int | None = Form(None, ge=1, le=100),
    release_year: int | None = Form(None, ge=1000, le=9999),
    album_artist: str | None = Form(None, max_length=255),
    genre: str | None = Form(None, max_length=255),
    source_id: int = Form(uploads.CENTRAL_SOURCE_ID, gt=0),
    _csrf: None = Depends(require_csrf),
    current: CurrentUser = Depends(get_current_user),
) -> UploadResponse:
    settings = get_settings()
    if file.size is not None and file.size > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="el archivo supera el máximo de 50 MB")
    try:
        result = uploads.upload_track(
            user_id=current.user_id,
            original_filename=file.filename or "sin-nombre",
            content=iter(lambda: file.file.read(64 * 1024), b""),
            source_id=source_id,
            title=title,
            artist=artist,
            album=album,
            track_number=track_number,
            disc_number=disc_number,
            release_year=release_year,
            album_artist=album_artist,
            genre=genre,
        )
    except FileTooLargeError:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="el archivo supera el máximo de 50 MB")
    except QuotaExceededError as error:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=str(error))
    except UploadValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(error))
    except SourceUnavailableError:
        raise HTTPException(status_code=404, detail="Destino no disponible")
    except UnsupportedOperationError:
        raise HTTPException(status_code=422, detail="Este destino no admite cargas en esta versión")
    except (StorageError, OSError):
        raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                            detail="no se pudo guardar el archivo; inténtalo de nuevo")
    return UploadResponse(**result)


@router.get("/library", response_model=LibraryPage)
def list_library(
    q: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
) -> LibraryPage:
    data = library.list_library(owner_id=current.user_id, q=q, page=page, page_size=page_size)
    return LibraryPage(**data)


@router.get("/tracks/{track_id}", response_model=TrackDetail)
def track_detail(track_id: int, current: CurrentUser = Depends(get_current_user)) -> TrackDetail:
    detail = library.get_track_detail(track_id=track_id, user_id=current.user_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    return TrackDetail(**detail)


@router.get("/tracks/{track_id}/cover")
def track_cover(track_id: int, current: CurrentUser = Depends(get_current_user)) -> Response:
    # Same view policy for owners, shares and PUBLIC. ADMIN has no bypass.
    if not copies.can_view_track(track_id=track_id, user_id=current.user_id):
        raise HTTPException(status_code=404, detail="No encontrado")
    with db.read_only() as cursor:
        cursor.execute("SELECT cover_jpeg FROM TRACK_METADATA WHERE track_id = %s", (track_id,))
        row = cursor.fetchone()
    if not row or not row["cover_jpeg"]:
        raise HTTPException(status_code=404, detail="No encontrado")
    return Response(content=bytes(row["cover_jpeg"]), media_type="image/jpeg", headers={
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Cross-Origin-Resource-Policy": "same-origin",
    })


def _resolve_delivery(track_id: int, user_id: int, action: str):
    """Resuelve la copia autorizada (propia, compartida o PUBLIC) y verifica disco."""
    copy, state = copies.resolve_for_action(track_id=track_id, user_id=user_id, action=action)
    if state == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado")
    if state == "unavailable":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="La copia no está disponible en este momento")
    try:
        storage = get_storage_for_source(copy["source_id"])
        fresh_size = storage.size(copy["relative_path"])
    except StorageError:
        raise HTTPException(status_code=409, detail="La copia no está disponible en este momento") from None
    return storage, copy, fresh_size


def _audio_headers(size: int) -> dict[str, str]:
    return {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }


@router.get("/tracks/{track_id}/audio")
def stream_audio(track_id: int, request: Request, current: CurrentUser = Depends(get_current_user)) -> Response:
    storage, copy, size = _resolve_delivery(track_id, current.user_id, "stream")
    base_headers = _audio_headers(size)
    mime = copy["mime_type"]

    range_header = request.headers.get("range")
    if range_header is None:
        return StreamingResponse(
            storage.stream_range(copy["relative_path"]),
            status_code=status.HTTP_200_OK,
            media_type=mime,
            headers={**base_headers, "Content-Length": str(size)},
        )

    try:
        byte_range = delivery.parse_range(range_header, size)
    except RangeNotSatisfiable:
        return Response(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                        headers={**base_headers, "Content-Range": f"bytes */{size}"})

    length = byte_range.end - byte_range.start + 1
    return StreamingResponse(
        storage.stream_range(copy["relative_path"], byte_range.start, length),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=mime,
        headers={
            **base_headers,
            "Content-Range": delivery.content_range(byte_range.start, byte_range.end, size),
            "Content-Length": str(length),
        },
    )


@router.get("/tracks/{track_id}/download")
def download_track(track_id: int, current: CurrentUser = Depends(get_current_user)) -> Response:
    storage, copy, size = _resolve_delivery(track_id, current.user_id, "download")
    detail = library.get_track_detail(track_id=track_id, user_id=current.user_id) or {}
    filename, disposition = delivery.attachment_filename(
        detail.get("title") or "cancion", copy["relative_path"]
    )
    with db.transaction() as cursor:
        operations.record_file_operation(
            cursor, type_="DOWNLOAD", result="SUCCESS", actor_user_id=current.user_id,
            location_id=copy["location_id"], bytes_transferred=size,
            detail="descarga solicitada; recepción por el cliente no verificable",
        )
    return StreamingResponse(
        storage.stream_range(copy["relative_path"]),
        status_code=status.HTTP_200_OK,
        media_type="application/octet-stream",
        headers={
            **_audio_headers(size),
            "Content-Length": str(size),
            "Content-Disposition": disposition,
        },
    )
