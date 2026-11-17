"""Fuentes y trabajos de escaneo (Fase 5 / H5 / B12).

Una fuente describe un árbol de directorios autorizado para importar. Las
rutas son RELATIVAS a la raíz de audio (storage_root, por defecto
<repo>/storage); las absolutas, las de otra unidad y las que escapen de la
raíz se rechazan. Las copias importadas referencian rutas relativas a ESA
raíz (con el prefijo de la fuente), de modo que la entrega no depende de la
fuente.

Reescanear nunca duplica rutas ni cambia dueños/permisos (UNIQUE
(source_id, relative_path)); el propietario de la importación se asigna
EXPLÍCITAMENTE al crear el trabajo (D7), nunca se infiere.
"""

import hashlib
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.repositories import db, operations
from app.services import audio as audio_probe
from app.services import catalog


class SourcePathError(Exception):
    pass


def _audio_root() -> Path:
    """Raíz única servible: <repo>/storage por defecto (STORAGE_ROOT)."""
    settings = get_settings()
    root = Path(settings.storage_root) if settings.storage_root else Path(__file__).resolve().parents[3] / "storage"
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_source_path(base_relative_path: str) -> str:
    """Ruta de la fuente relativa a la raíz de audio; rechaza escapes y unidades."""
    candidate = (base_relative_path or "").strip().replace("\\", "/")
    if not candidate:
        raise SourcePathError("la ruta no puede estar vacía")
    if candidate.startswith("/") or (len(candidate) > 1 and candidate[1] == ":"):
        raise SourcePathError("la ruta debe ser relativa a la raíz de audio")
    segments: list[str] = []
    for segment in candidate.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise SourcePathError("la ruta sale de la raíz de audio")
        segments.append(segment)
    if not segments:
        raise SourcePathError("la ruta no puede estar vacía")
    normalized = "/".join(segments)
    if len(normalized) > 512:
        raise SourcePathError("la ruta supera 512 caracteres")
    return normalized


def source_absolute_path(base_relative_path: str) -> Path:
    root = _audio_root()
    normalized = normalize_source_path(base_relative_path)
    candidate = (root / normalized).resolve()
    if candidate != root and root not in candidate.parents:
        raise SourcePathError("la ruta sale de la raíz de audio")
    return candidate


def stored_relative_path(base_relative_path: str, relative_to_source: str) -> str:
    """Ruta tal como se almacena en TRACK_LOCATION (relativa a la raíz de audio)."""
    prefix = normalize_source_path(base_relative_path)
    return f"{prefix}/{relative_to_source}" if relative_to_source else prefix


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
            "       (SELECT COUNT(*) FROM SCAN_JOB j WHERE j.source_id = s.source_id) AS scan_jobs, "
            "       (SELECT MAX(j.scan_job_id) FROM SCAN_JOB j WHERE j.source_id = s.source_id) AS last_scan_job_id "
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


def _record_file_report(scan_job_id: int, row: dict) -> None:
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO SCAN_JOB_FILE (scan_job_id, relative_path, outcome, track_id, title, artist, album, "
            "duration_seconds, detail) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                scan_job_id,
                (row.get("relative_path") or "")[:512],
                row.get("outcome"),
                row.get("track_id"),
                (row.get("title") or "")[:512] or None,
                (row.get("artist") or "")[:255] or None,
                (row.get("album") or "")[:512] or None,
                row.get("duration_seconds"),
                (row.get("detail") or "")[:255] or None,
            ),
        )


def get_scan_job_files(*, scan_job_id: int) -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT scan_job_file_id, relative_path, outcome, track_id, title, artist, album, "
            "       duration_seconds, detail, created_at "
            "FROM SCAN_JOB_FILE WHERE scan_job_id = %s ORDER BY scan_job_file_id",
            (scan_job_id,),
        )
        return list(cursor.fetchall())


def list_scan_jobs(*, source_id: int | None = None, limit: int = 20) -> list[dict]:
    with db.read_only() as cursor:
        if source_id is not None:
            cursor.execute(
                "SELECT scan_job_id, source_id, owner_user_id, status, files_found, files_added, "
                "       files_skipped, error_message, created_at, started_at, finished_at "
                "FROM SCAN_JOB WHERE source_id = %s ORDER BY scan_job_id DESC LIMIT %s",
                (source_id, limit),
            )
        else:
            cursor.execute(
                "SELECT scan_job_id, source_id, owner_user_id, status, files_found, files_added, "
                "       files_skipped, error_message, created_at, started_at, finished_at "
                "FROM SCAN_JOB ORDER BY scan_job_id DESC LIMIT %s",
                (limit,),
            )
        return list(cursor.fetchall())


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
        found_paths = {
            stored_relative_path(job["base_relative_path"], path.relative_to(root).as_posix())
            for path in candidates
        }
    except SourcePathError as error:
        _finish_job(scan_job_id, "FAILED", 0, 0, 0, str(error), result="FAILURE")
        return

    added = skipped = failed = 0
    for path in candidates:
        try:
            inserted, file_row = _import_one(scan_job_id=scan_job_id, source_id=job["source_id"],
                                             owner_user_id=job["owner_user_id"], root=root, path=path,
                                             base_relative_path=job["base_relative_path"])
            _record_file_report(scan_job_id, file_row)
            if inserted:
                added += 1
            else:
                skipped += 1
        except Exception:  # un archivo corrupto no aborta el lote
            failed += 1
            _record_file_report(scan_job_id, {
                "relative_path": stored_relative_path(job["base_relative_path"], path.relative_to(root).as_posix()),
                "outcome": "FAILED",
                "track_id": None,
                "title": None,
                "artist": None,
                "album": None,
                "duration_seconds": None,
                "detail": "no se pudo importar (formato, contenido o longitud de ruta)",
            })

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
        missing_rows = []
        if missing:
            placeholders = ",".join(["%s"] * len(missing))
            cursor.execute(
                f"SELECT l.relative_path, l.track_id, t.title, t.duration_seconds, a.title AS album, "
                f"       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
                f"FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
                f"LEFT JOIN ALBUM a ON a.album_id = t.album_id "
                f"JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
                f"WHERE l.source_id = %s AND l.relative_path IN ({placeholders}) "
                f"GROUP BY l.relative_path, l.track_id, t.title, t.duration_seconds, a.title",
                (job["source_id"], *missing),
            )
            missing_rows = list(cursor.fetchall())
        for row in missing_rows:
            _record_file_report(scan_job_id, {
                "relative_path": row["relative_path"],
                "outcome": "MISSING",
                "track_id": row["track_id"],
                "title": row["title"],
                "artist": row["artists"],
                "album": row["album"],
                "duration_seconds": row["duration_seconds"],
                "detail": "no encontrada en disco; la copia se conserva como MISSING",
            })
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


def _import_one(*, scan_job_id: int, source_id: int, owner_user_id: int, root: Path, path: Path,
                base_relative_path: str) -> tuple[bool, dict]:
    """Importa UN archivo; devuelve (True=importado/ False=omitido, fila de informe)."""
    subpath = path.relative_to(root).as_posix()
    relative_path = stored_relative_path(base_relative_path, subpath)
    if len(relative_path) > 512:
        raise ValueError("la ruta supera 512 caracteres")
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT location_id FROM TRACK_LOCATION WHERE source_id = %s AND relative_path = %s LIMIT 1",
            (source_id, relative_path),
        )
        if cursor.fetchone() is not None:
            cursor.execute(
                "SELECT l.track_id, l.relative_path, t.title, t.duration_seconds, a.title AS album, "
                "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
                "FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
                "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
                "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
                "WHERE l.source_id = %s AND l.relative_path = %s "
                "GROUP BY l.track_id, l.relative_path, t.title, t.duration_seconds, a.title",
                (source_id, relative_path),
            )
            row = cursor.fetchone()
            return False, {
                "relative_path": relative_path,
                "outcome": "SKIPPED",
                "track_id": row["track_id"] if row else None,
                "title": row["title"] if row else None,
                "artist": row["artists"] if row else None,
                "album": row["album"] if row else None,
                "duration_seconds": row["duration_seconds"] if row else None,
                "detail": "ya importada anteriormente; no se cambia su dueño ni sus permisos",
            }

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
            return False, {
                "relative_path": relative_path,
                "outcome": "SKIPPED",
                "track_id": None,
                "title": title,
                "artist": artist_name,
                "album": album_title,
                "duration_seconds": duration,
                "detail": "ya importada anteriormente (carrera); se omite",
            }
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
    return True, {
        "relative_path": relative_path,
        "outcome": "ADDED",
        "track_id": track_id,
        "title": title,
        "artist": artist_name,
        "album": album_title,
        "duration_seconds": duration,
        "detail": None,
    }
