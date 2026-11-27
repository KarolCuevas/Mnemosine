"""Carga local por bloques. Validación privada, cuota serializada y compensación."""
import uuid
from collections.abc import Iterable
from pathlib import Path

from app.core.config import get_settings
from app.repositories import db, operations
from app.services import audio as audio_probe, catalog, quota
from app.services.metadata import clean_text, read_embedded_metadata, save_metadata
from app.services.storage import get_storage, get_storage_for_source, get_source
from app.services.quota import QuotaExceededError
from app.storage.contract import SourceUnavailableError, UnsupportedOperationError

CENTRAL_SOURCE_ID = 9001


class UploadValidationError(Exception):
    pass


def _validate_audio(temp_path: Path, original_filename: str) -> tuple[str, int, str]:
    try:
        return audio_probe.probe_audio_file(temp_path, original_filename)
    except audio_probe.AudioProbeError as error:
        raise UploadValidationError(str(error)) from error


def upload_track(*, user_id: int, original_filename: str, content: bytes | Iterable[bytes],
                 title: str | None = None, artist: str | None = None, album: str | None = None,
                 track_number: int | None = None, disc_number: int | None = None,
                 release_year: int | None = None, album_artist: str | None = None,
                 genre: str | None = None, source_id: int = CENTRAL_SOURCE_ID) -> dict:
    settings = get_settings()
    source = get_source(source_id)
    if source_id != CENTRAL_SOURCE_ID and source["owner_user_id"] != user_id:
        raise SourceUnavailableError("destino no disponible")
    storage = get_storage_for_source(source_id)
    storage.require("write")
    if source["adapter_code"] != "LOCAL":
        raise UnsupportedOperationError("el destino requiere un trabajador de transferencias aún no habilitado")
    staging = get_storage()
    for value, limit in ((title, 512), (artist, 255), (album, 512), (album_artist, 255), (genre, 255)):
        if value is not None and len(value.strip()) > limit:
            raise UploadValidationError("los metadatos superan el límite de longitud")
    for value, minimum, maximum in ((track_number, 1, 1000), (disc_number, 1, 100), (release_year, 1000, 9999)):
        if value is not None and not minimum <= value <= maximum:
            raise UploadValidationError("pista, disco o año fuera del intervalo admitido")

    staged = staging.save_stream([content] if isinstance(content, bytes) else content, max_bytes=settings.max_upload_bytes)
    published = None
    try:
        ext, duration, mime = _validate_audio(Path(staged.token), original_filename)
        metadata = read_embedded_metadata(Path(staged.token))
        fallback_title = Path(original_filename.replace("\\", "/")).stem
        title = clean_text(title, 512) or metadata.title or clean_text(fallback_title, 512) or "Sin título"
        artists = [clean_text(artist, 255)] if clean_text(artist, 255) else metadata.artists or ["Artista desconocido"]
        album = clean_text(album, 512) or metadata.album
        track_number = track_number if track_number is not None else metadata.track_number
        disc_number = disc_number if disc_number is not None else metadata.disc_number
        release_year = release_year if release_year is not None else metadata.release_year
        metadata.release_year = release_year
        metadata.album_artist = clean_text(album_artist, 255) or metadata.album_artist
        metadata.genre = clean_text(genre, 255) or metadata.genre
        with db.transaction() as cursor:
            # Bloquear antes de la primera lectura consistente para ver la carga anterior.
            quota.lock_account(cursor, user_id)
            quota.check_capacity(cursor, user_id, staged.size_bytes)
            cursor.execute("SELECT status FROM SOURCE WHERE source_id = %s FOR SHARE", (source_id,))
            if cursor.fetchone()["status"] != "ACTIVE":
                raise SourceUnavailableError("destino desconectado")
            album_id = catalog.find_or_create_album(cursor, album, release_year)
            cursor.execute("INSERT INTO TRACK (title, duration_seconds, disc_number, track_number, album_id) VALUES (%s,%s,%s,%s,%s)",
                           (title, duration, disc_number, track_number, album_id))
            track_id = cursor.lastrowid
            artist_ids = set()
            for name in artists:
                artist_id = catalog.find_or_create_artist(cursor, name)
                if artist_id in artist_ids:
                    continue
                artist_ids.add(artist_id)
                position = len(artist_ids)
                cursor.execute("INSERT INTO TRACK_ARTIST (track_id, artist_id, position, role) VALUES (%s,%s,%s,'MAIN')", (track_id, artist_id, position))
                if not metadata.album_artist:
                    catalog.ensure_album_artist(cursor, album_id, artist_id)
            if album_id is not None and metadata.album_artist:
                catalog.ensure_album_artist(cursor, album_id, catalog.find_or_create_artist(cursor, metadata.album_artist))
            save_metadata(cursor, track_id, metadata)
            relative_path = f"{source['base_relative_path']}/{user_id}/{uuid.uuid4().hex}{ext}"
            storage.commit(staged, relative_path)
            published = relative_path
            cursor.execute(
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime_type, visibility, availability) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'PRIVATE','AVAILABLE')",
                (track_id, user_id, source_id, relative_path, staged.sha256, staged.size_bytes, mime),
            )
            location_id = cursor.lastrowid
            operations.record_file_operation(cursor, type_="UPLOAD", result="SUCCESS", actor_user_id=user_id,
                                             location_id=location_id, bytes_transferred=staged.size_bytes, detail="carga privada")
    except BaseException:
        if published is not None:
            # Un fallo de red al confirmar SQL puede dejar un resultado incierto.
            # Nunca borrar bytes que quizás ya referencie un commit confirmado.
            try:
                with db.read_only() as cursor:
                    cursor.execute("SELECT location_id FROM TRACK_LOCATION WHERE source_id = %s AND relative_path = %s", (source_id, published))
                    registered = cursor.fetchone() is not None
                if not registered:
                    storage.delete(published)
            except Exception:
                # Con BD inaccesible, conservar para reconciliación manual.
                pass
        raise
    finally:
        staging.discard(staged)  # Solo el temporal propio, incluso si falla la sonda.

    return {"track_id": track_id, "location_id": location_id, "title": title, "artist": ", ".join(artists),
            "album": album or None, "duration_seconds": duration, "size_bytes": staged.size_bytes,
            "sha256": staged.sha256, "mime_type": mime, "visibility": "PRIVATE",
            "album_artist": metadata.album_artist, "genre": metadata.genre,
            "track_number": track_number, "disc_number": disc_number, "release_year": release_year,
            "cover_url": f"/api/tracks/{track_id}/cover" if metadata.cover else None,
            "warnings": metadata.warnings}
