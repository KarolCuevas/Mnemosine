"""Carga privada de audio de extremo a extremo (Fase 3).

Flujo (regla 8 del plan: el FS no se revierte por SQL, así que hay temporales,
compensación y recuperación):
1. streaming del cuerpo a un temporal y cálculo de SHA-256/tamaño;
2. validación real del contenido (extensión + tipo por magic bytes + mutagen);
3. cuota por cuenta y límite por archivo (D3);
4. commit atómico del temporal (nunca sobrescribe);
5. transacción SQL: ARTIST/ALBUM/TRACK/TRACK_LOCATION(PRIVATE)/FILE_OPERATION;
   si falla, se borra el archivo ya publicado (compensación documentada).

La visibilidad siempre nace PRIVATE; publicar es una acción explícita (H4).
"""

import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.repositories import db, operations
from app.services import audio as audio_probe
from app.services import catalog
from app.services.storage import get_storage

CENTRAL_SOURCE_ID = 9001  # migración 0009_fuente_central.sql

class UploadValidationError(Exception):
    """El archivo no supera la validación real (formato/contenido/tamaño)."""


class QuotaExceededError(Exception):
    """La cuenta supera su cuota de almacenamiento."""


def _validate_audio(temp_path: Path, original_filename: str) -> tuple[str, int, str]:
    try:
        return audio_probe.probe_audio_file(temp_path, original_filename)
    except audio_probe.AudioProbeError as error:
        raise UploadValidationError(str(error)) from error


def upload_track(*, user_id: int, original_filename: str, content: bytes,
                 title: str, artist: str, album: str | None,
                 track_number: int | None, disc_number: int | None,
                 release_year: int | None) -> dict:
    settings = get_settings()
    storage = get_storage()

    title, artist = (title or "").strip(), (artist or "").strip()
    if not title or not artist:
        raise UploadValidationError("título y artista son obligatorios")
    if len(title) > 512 or len(artist) > 255:
        raise UploadValidationError("título o artista demasiado largos")

    storage.recover_stale_temps(datetime.now())  # limpia temporales interrumpidos
    staged = storage.save_stream([content], max_bytes=settings.max_upload_bytes)

    ext, duration, mime = _validate_audio(Path(staged.token), original_filename)
    total_bytes = staged.size_bytes

    with db.transaction() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) AS used FROM TRACK_LOCATION WHERE owner_user_id = %s",
            (user_id,),
        )
        if cursor.fetchone()["used"] + total_bytes > settings.max_user_quota_bytes:
            storage.discard(staged)
            raise QuotaExceededError("esta cuenta supera su cuota de almacenamiento (5 GB)")

        artist_id = catalog.find_or_create_artist(cursor, artist)
        album_id = catalog.find_or_create_album(cursor, album, release_year)

        cursor.execute(
            "INSERT INTO TRACK (title, duration_seconds, disc_number, track_number, album_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (title, duration, disc_number, track_number, album_id),
        )
        track_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO TRACK_ARTIST (track_id, artist_id, position, role) VALUES (%s, %s, 1, 'MAIN')",
            (track_id, artist_id),
        )
        if album_id is not None:
            catalog.ensure_album_artist(cursor, album_id, artist_id)
        relative_path = f"audio/{user_id}/{uuid.uuid4().hex}{ext}"
        try:
            storage.commit(staged, relative_path)
        except Exception:
            storage.discard(staged)
            raise
        try:
            cursor.execute(
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, "
                "sha256, size_bytes, mime_type, visibility, availability) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'PRIVATE', 'AVAILABLE')",
                (track_id, user_id, CENTRAL_SOURCE_ID, relative_path, staged.sha256, total_bytes, mime),
            )
            location_id = cursor.lastrowid
            operations.record_file_operation(
                cursor, type_="UPLOAD", result="SUCCESS", actor_user_id=user_id,
                location_id=location_id, bytes_transferred=total_bytes,
                detail="carga privada",
            )
        except Exception:
            # Compensación: el archivo ya se publicó; borrarlo si la BD falla.
            storage.delete(relative_path)
            raise

    return {
        "track_id": track_id,
        "location_id": location_id,
        "title": title,
        "artist": artist,
        "album": album or None,
        "duration_seconds": duration,
        "size_bytes": total_bytes,
        "sha256": staged.sha256,
        "mime_type": mime,
        "visibility": "PRIVATE",
    }
