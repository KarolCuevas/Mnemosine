"""Fuentes y trabajos de escaneo (Fase 5 / H5 / B12).

Una fuente describe un árbol de directorios autorizado para importar. Las
rutas son RELATIVAS a `scan_root` (Setting SCAN_ROOT, por defecto <repo>/storage);
las absolutas, las de otra unidad y las que escapen de la raíz se rechazan.

Reescanear nunca duplica rutas ni cambia dueños/permisos (UNIQUE
(source_id, relative_path)); el propietario de la importación se asigna
EXPLÍCITAMENTE al crear el trabajo (D7), nunca se infiere.
"""

import hashlib
from datetime import datetime
from pathlib import Path, PurePosixPath

from app.core.config import get_settings
from app.repositories import db, operations
from app.services import audio as audio_probe
from app.services import catalog


class SourcePathError(Exception):
    pass


def _scan_root() -> Path:
    settings = get_settings()
    root = Path(settings.scan_root) if settings.scan_root else Path(__file__).resolve().parents[3] / "storage"
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_source_path(base_relative_path: str) -> str:
    """Ruta de la fuente relativa a scan_root; rechaza escapes y unidades."""
    candidate = (base_relative_path or "").strip().replace("\\", "/")
    if not candidate:
        raise SourcePathError("la ruta no puede estar vacía")
    if candidate.startswith("/") or (len(candidate) > 1 and candidate[1] == ":"):
        raise SourcePathError("la ruta debe ser relativa a la raíz de escaneo")
    segments: list[str] = []
    for segment in candidate.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise SourcePathError("la ruta sale de la raíz de escaneo")
        segments.append(segment)
    if not segments:
        raise SourcePathError("la ruta no puede estar vacía")
    normalized = "/".join(segments)
    if len(normalized) > 512:
        raise SourcePathError("la ruta supera 512 caracteres")
    return normalized


def source_absolute_path(base_relative_path: str) -> Path:
    root = _scan_root()
    normalized = normalize_source_path(base_relative_path)
    candidate = (root / normalized).resolve()
    if candidate != root and root not in candidate.parents:
        raise SourcePathError("la ruta sale de la raíz de escaneo")
    return candidate


def create_source(*, name: str, base_relative_path: str, owner_user_id: int | None = None) -> dict:
    name = name.strip()
    if not name:
        raise SourcePathError("el nombre no puede estar vacío")
    if len(name) > 255:
        raise SourcePathError("el nombre es demasiado largo")
    source_absolute_path(base_relative_path)  # valida ahora, no en el primer escaneo
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO SOURCE (device_id, owner_user_id, name, base_relative_path, status) "
            "VALUES (9002, %s, %s, %s, 'ACTIVE')",
            (owner_user_id, name, normalize_source_path(base_relative_path)),
        )
        source_id = cursor.lastrowid
        cursor.execute(
            "SELECT source_id, device_id, owner_user_id, name, base_relative_path, status, "
            "       last_scanned_at, created_at FROM SOURCE WHERE source_id = %s",
            (source_id,),
        )
        return cursor.fetchone()


def list_sources() -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT s.source_id, s.owner_user_id, s.name, s.base_relative_path, s.status, "
            "       s.last_scanned_at, s.created_at, "
            "       (SELECT COUNT(*) FROM TRACK_LOCATION l WHERE l.source_id = s.source_id) AS copies, "
            "       (SELECT COUNT(*) FROM SCAN_JOB j WHERE j.source_id = s.source_id) AS scan_jobs "
            "FROM SOURCE s ORDER BY s.source_id"
        )
        return list(cursor.fetchall())


def set_source_status(*, source_id: int, status: str) -> dict:
    if status not in ("ACTIVE", "DISCONNECTED"):
        raise SourcePathError("estado no válido")
    with db.transaction() as cursor:
        cursor.execute("SELECT source_id FROM SOURCE WHERE source_id = %s", (source_id,))
        if cursor.fetchone() is None:
            raise SourcePathError("la fuente no existe")
        cursor.execute("UPDATE SOURCE SET status = %s WHERE source_id = %s", (status, source_id))
    return {"source_id": source_id, "status": status}


def create_scan_job(*, source_id: int, owner_user_id: int) -> dict:
    """Crea el trabajo de escaneo. El propietario es OBLIGATORIO (D7)."""
    owner_user_id = int(owner_user_id or 0)
    if owner_user_id <= 0:
        raise SourcePathError("la importación requiere un propietario explícito")
    with db.transaction() as cursor:
        cursor.execute("SELECT user_id FROM USER_ACCOUNT WHERE user_id = %s AND is_active = 1 LIMIT 1", (owner_user_id,))
        if cursor.fetchone() is None:
            raise SourcePathError("el propietario indicado no existe o está desactivado")
        cursor.execute(
            "SELECT source_id, status FROM SOURCE WHERE source_id = %s LIMIT 1",
            (source_id,),
        )
        source = cursor.fetchone()
        if source is None:
            raise SourcePathError("la fuente no existe")
        if source["status"] != "ACTIVE":
            raise SourcePathError("la fuente está desconectada")
        cursor.execute(
            "INSERT INTO SCAN_JOB (source_id, owner_user_id, status) VALUES (%s, %s, 'PENDING')",
            (source_id, owner_user_id),
        )
        job_id = cursor.lastrowid
        operations.record_file_operation(
            cursor, type_="SCAN", result="SUCCESS", actor_user_id=owner_user_id,
            detail=f"escaneo de fuente {source_id} solicitado",
        )
        cursor.execute(
            "SELECT scan_job_id, source_id, owner_user_id, status, files_found, files_added, "
            "       files_skipped, error_message, created_at, started_at, finished_at FROM SCAN_JOB WHERE scan_job_id = %s",
            (job_id,),
        )
        return cursor.fetchone()


def get_scan_job(*, scan_job_id: int) -> dict | None:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT scan_job_id, source_id, owner_user_id, status, files_found, files_added, "
            "       files_skipped, error_message, created_at, started_at, finished_at "
            "FROM SCAN_JOB WHERE scan_job_id = %s",
            (scan_job_id,),
        )
        return cursor.fetchone()


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_scan(*, scan_job_id: int) -> None:
    """Ejecuta el escaneo. Cada archivo aisla sus fallos; el trabajo termina
    COMPLETED o FAILED con contadores. La disponibilidad se reconcilia al final."""
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE SCAN_JOB SET status = 'RUNNING', started_at = NOW() WHERE scan_job_id = %s",
            (scan_job_id,),
        )
        cursor.execute(
            "SELECT j.scan_job_id, j.source_id, j.owner_user_id, s.base_relative_path, s.status "
            "FROM SCAN_JOB j JOIN SOURCE s ON s.source_id = j.source_id WHERE j.scan_job_id = %s",
            (scan_job_id,),
        )
        job = cursor.fetchone()
        if job is None:
            return

    try:
        root = source_absolute_path(job["base_relative_path"])
        if not root.is_dir():
            _finish_job(scan_job_id, "FAILED", 0, 0, 0,
                        f"la carpeta de la fuente no existe o no es accesible: {root}", result="FAILURE")
            return
        candidates = [
            path for path in root.rglob("*")
            if path.is_file() and audio_probe.allowed_extension(path.name)
        ]
        found_paths = {path.relative_to(root).as_posix() for path in candidates}
    except SourcePathError as error:
        _finish_job(scan_job_id, "FAILED", 0, 0, 0, str(error), result="FAILURE")
        return

    added = skipped = failed = 0
    for path in candidates:
        try:
            inserted = _import_one(scan_job_id=scan_job_id, source_id=job["source_id"],
                                   owner_user_id=job["owner_user_id"], root=root, path=path)
            if inserted:
                added += 1
            else:
                skipped += 1
        except Exception:  # un archivo corrupto no aborta el lote
            failed += 1

    # Reconciliar disponibilidad contra lo encontrado en disco.
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT relative_path FROM TRACK_LOCATION WHERE source_id = %s",
            (job["source_id"],),
        )
        known = {row["relative_path"] for row in cursor.fetchall()}
        missing = sorted(known - found_paths)
        restored = sorted(known & found_paths)
        for rel in missing:
            cursor.execute(
                "UPDATE TRACK_LOCATION SET availability = 'MISSING' WHERE source_id = %s AND relative_path = %s",
                (job["source_id"], rel),
            )
        for rel in restored:
            cursor.execute(
                "UPDATE TRACK_LOCATION SET availability = 'AVAILABLE' WHERE source_id = %s AND relative_path = %s AND availability <> 'AVAILABLE'",
                (job["source_id"], rel),
            )
        cursor.execute(
            "UPDATE SOURCE SET last_scanned_at = NOW() WHERE source_id = %s",
            (job["source_id"],),
        )

    _finish_job(
        scan_job_id,
        "COMPLETED",
        len(candidates),
        added,
        skipped,
        (f"{failed} archivo(s) con error" if failed else None),
        result=("FAILURE" if failed else "SUCCESS"),
    )


def _finish_job(scan_job_id: int, status: str, found: int, added: int, skipped: int,
                error: str | None, result: str = "SUCCESS") -> None:
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE SCAN_JOB SET status = %s, files_found = %s, files_added = %s, files_skipped = %s, "
            "error_message = %s, finished_at = NOW() WHERE scan_job_id = %s",
            (status, found, added, skipped, error, scan_job_id),
        )
        cursor.execute(
            "INSERT INTO FILE_OPERATION (type, actor_user_id, result, detail) "
            "SELECT 'SCAN', owner_user_id, %s, %s FROM SCAN_JOB WHERE scan_job_id = %s",
            (result, f"escaneo {status}: encontrados {found}, añadidos {added}, omitidos {skipped}", scan_job_id),
        )


def _import_one(*, scan_job_id: int, source_id: int, owner_user_id: int, root: Path, path: Path) -> bool:
    """Importa UN archivo; False si ya existía (source_id, relative_path)."""
    relative_path = path.relative_to(root).as_posix()
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT location_id FROM TRACK_LOCATION WHERE source_id = %s AND relative_path = %s LIMIT 1",
            (source_id, relative_path),
        )
        if cursor.fetchone() is not None:
            return False

    # Fuera de la transacción: sonda + hash (puede tardar); después se confirma.
    ext, duration, mime = audio_probe.probe_audio_file(path)
    sha256 = _sha256_of(path)
    size_bytes = path.stat().st_size
    tags = audio_probe.read_easy_tags(path)
    stem = path.stem

    def pick(key: str, default: str) -> str:
        value = tags.get(key, "").strip()
        return value or default

    title = pick("title", stem)[:512]
    artist_name = pick("artist", "Desconocido")[:255]
    album_title = tags.get("album", "").strip()[:512] or None

    track_number = None
    raw_track = tags.get("tracknumber", "").split("/")[0].strip()
    if raw_track.isdigit():
        track_number = min(int(raw_track), 1000)
    disc_number = None
    raw_disc = tags.get("discnumber", "").split("/")[0].strip()
    if raw_disc.isdigit():
        disc_number = max(1, min(int(raw_disc), 100))

    year = None
    raw_date = tags.get("date", "").strip()[:4]
    if raw_date.isdigit():
        year = int(raw_date)

    with db.transaction() as cursor:
        # Volver a comprobar dentro de la transacción final.
        cursor.execute(
            "SELECT location_id FROM TRACK_LOCATION WHERE source_id = %s AND relative_path = %s LIMIT 1",
            (source_id, relative_path),
        )
        if cursor.fetchone() is not None:
            return False
        artist_id = catalog.find_or_create_artist(cursor, artist_name)
        album_id = catalog.find_or_create_album(cursor, album_title, year)
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
        catalog.ensure_album_artist(cursor, album_id, artist_id)
        cursor.execute(
            "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, "
            "sha256, size_bytes, mime_type, visibility, availability) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'PRIVATE', 'AVAILABLE')",
            (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime),
        )
        location_id = cursor.lastrowid
        operations.record_file_operation(
            cursor, type_="SCAN", result="SUCCESS", actor_user_id=owner_user_id,
            location_id=location_id, bytes_transferred=size_bytes,
            detail="escaneo: copia importada",
        )
    return True
