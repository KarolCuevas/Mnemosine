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

import filetype
import mutagen

from app.core.config import get_settings
from app.repositories import db, operations
from app.services.storage import get_storage

CENTRAL_SOURCE_ID = 9001  # migración 0009_fuente_central.sql

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg", ".wav"}

# Tipo real devuelto por filetype → extensiones compatibles. El audio nunca se
# acepta solo por la extensión declarada.
_MIME_BY_EXT = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a", "audio/aac"},
    ".flac": {"audio/flac", "audio/x-flac"},
    ".ogg": {"audio/ogg", "audio/x-ogg", "application/ogg"},
    ".wav": {"audio/x-wav", "audio/wav", "audio/wave", "audio/vnd.wave"},
}


class UploadValidationError(Exception):
    """El archivo no supera la validación real (formato/contenido/tamaño)."""


class QuotaExceededError(Exception):
    """La cuenta supera su cuota de almacenamiento."""


def _validate_audio(temp_path: Path, original_filename: str) -> tuple[str, int, str]:
    ext = Path(original_filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"formato no admitido: {ext or '(sin extensión)'}. Admitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    kind = filetype.guess(str(temp_path))
    guessed_mime = kind.mime if kind else None
    allowed_mimes = _MIME_BY_EXT[ext]
    if guessed_mime and guessed_mime not in allowed_mimes:
        raise UploadValidationError(f"el contenido no coincide con la extensión {ext} (detectado: {guessed_mime})")

    audio = mutagen.File(str(temp_path))
    if audio is None or not getattr(audio, "info", None) or not getattr(audio.info, "length", 0):
        raise UploadValidationError("no se reconoce como un audio válido (contenedor/códec no legible)")
    duration = int(audio.info.length)
    if duration <= 0:
        raise UploadValidationError("la duración del audio no es válida")

    mime = guessed_mime or next(iter(allowed_mimes))
    return ext, duration, mime


def _find_or_create_artist(cursor, name: str) -> int:
    artist = name.strip()
    cursor.execute("SELECT artist_id FROM ARTIST WHERE LOWER(name) = LOWER(%s) LIMIT 1", (artist,))
    row = cursor.fetchone()
    if row:
        return row["artist_id"]
    cursor.execute("INSERT INTO ARTIST (name, sort_name) VALUES (%s, %s)", (artist, artist))
    return cursor.lastrowid


def _find_or_create_album(cursor, title: str | None, release_year: int | None) -> int | None:
    album = (title or "").strip()
    if not album:
        return None
    cursor.execute("SELECT album_id FROM ALBUM WHERE LOWER(title) = LOWER(%s) LIMIT 1", (album,))
    row = cursor.fetchone()
    if row:
        return row["album_id"]
    cursor.execute(
        "INSERT INTO ALBUM (title, sort_title, release_year) VALUES (%s, %s, %s)",
        (album, album, release_year),
    )
    return cursor.lastrowid


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

        artist_id = _find_or_create_artist(cursor, artist)
        album_id = _find_or_create_album(cursor, album, release_year)

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
            cursor.execute(
                "INSERT INTO ALBUM_ARTIST (album_id, artist_id) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE artist_id = artist_id",
                (album_id, artist_id),
            )
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
