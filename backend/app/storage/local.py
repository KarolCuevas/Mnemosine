"""Adaptador de almacenamiento local para el MVP.

Raíz configurada en el constructor (en desarrollo, <repo>/storage). Todo el
audio vive bajo esa raíz; los temporales bajo <raíz>/.tmp_uncommitted para
garantizar publicación exclusiva mediante hard link en el mismo volumen.
recover_stale_temps() se reserva a mantenimiento con escritores detenidos.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from .contract import (
    DestinationExistsError,
    FileTooLargeError,
    InvalidPathError,
    NotFoundError,
    StagedUpload,
    ObjectInfo,
    ObjectPage,
    ObjectState,
    StorageCapabilities,
    StorageAdapter,
    normalize_relative_path,
)

TEMP_DIR_NAME = ".tmp_uncommitted"
CHUNK_SIZE = 64 * 1024


class LocalStorageAdapter(StorageAdapter):
    capabilities = StorageCapabilities(write=True, listing=True, delete=True)

    def __init__(self, root: str | Path, *, source_prefix: str = "") -> None:
        self.root = Path(root).expanduser().resolve()
        self.source_prefix = normalize_relative_path(source_prefix) if source_prefix else ""
        self.root.mkdir(parents=True, exist_ok=True)
        self.tmp_dir = self.root / TEMP_DIR_NAME
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        normalized = normalize_relative_path(relative_path)
        if self.source_prefix and normalized != self.source_prefix and not normalized.startswith(self.source_prefix + "/"):
            raise InvalidPathError("el objeto no pertenece a esta fuente")
        candidate = (self.root / normalized).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise InvalidPathError("la ruta sale de la raíz de almacenamiento")
        return candidate

    def save_stream(self, chunks: Iterable[bytes], *, max_bytes: int) -> StagedUpload:
        if max_bytes <= 0:
            raise ValueError("max_bytes debe ser positivo")
        temp_path = self.tmp_dir / f"{uuid.uuid4().hex}.part"
        digest = hashlib.sha256()
        total = 0
        try:
            with temp_path.open("wb") as handle:
                for chunk in chunks:
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise FileTooLargeError(
                            f"el archivo supera el máximo de {max_bytes} bytes"
                        )
                    digest.update(chunk)
                    handle.write(chunk)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        return StagedUpload(token=str(temp_path), sha256=digest.hexdigest(), size_bytes=total)

    def commit(self, staged: StagedUpload, relative_path: str) -> str:
        destination = self._resolve(relative_path)
        if destination.exists() or destination.is_symlink():
            raise DestinationExistsError(f"el destino ya existe: {normalize_relative_path(relative_path)}")
        source = Path(staged.token)
        if not source.is_file():
            raise NotFoundError("el temporal de la carga ya no existe")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Creación exclusiva también si dos procesos compiten. Mismo volumen que el temporal.
            os.link(source, destination)
        except FileExistsError:
            raise DestinationExistsError("el destino ya existe") from None
        try:
            source.unlink()
        except OSError:
            # El destino ya existe: retirar solo el temporal es mantenimiento posterior.
            pass
        return normalize_relative_path(relative_path)

    def discard(self, staged: StagedUpload) -> None:
        try:
            Path(staged.token).unlink(missing_ok=True)
        except OSError:
            pass

    def exists(self, relative_path: str) -> bool:
        try:
            return self._resolve(relative_path).is_file()
        except InvalidPathError:
            return False

    def size(self, relative_path: str) -> int:
        target = self._resolve(relative_path)
        if not target.is_file():
            raise NotFoundError("el objeto no existe")
        return target.stat().st_size

    def read_range(self, relative_path: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]:
        if offset < 0 or (length is not None and length < 0):
            raise ValueError("offset y length no pueden ser negativos")
        target = self._resolve(relative_path)
        if not target.is_file():
            raise NotFoundError("el objeto no existe")
        remaining = length
        with target.open("rb") as handle:
            if offset:
                handle.seek(offset)
            while remaining is None or remaining > 0:
                to_read = CHUNK_SIZE if remaining is None else min(CHUNK_SIZE, remaining)
                chunk = handle.read(to_read)
                if not chunk:
                    break
                yield chunk
                if remaining is not None:
                    remaining -= len(chunk)

    def stat(self, object_id: str) -> ObjectInfo:
        try:
            target = self._resolve(object_id)
            if not target.is_file():
                return ObjectInfo(object_id, ObjectState.NOT_FOUND)
            info = target.stat()
            return ObjectInfo(object_id, ObjectState.FOUND, info.st_size, f"{info.st_mtime_ns}:{info.st_size}")
        except (PermissionError, InvalidPathError):
            return ObjectInfo(object_id, ObjectState.NOT_ACCESSIBLE)
        except OSError:
            return ObjectInfo(object_id, ObjectState.TEMPORARY_ERROR)

    def list_objects(self, *, cursor: str | None = None, limit: int = 50) -> ObjectPage:
        if not 1 <= limit <= 100:
            raise ValueError("límite no válido")
        root = self._resolve(self.source_prefix) if self.source_prefix else self.root
        import heapq
        # Selección acotada en memoria. El escaneo administrativo completo sigue separado.
        names = (path.relative_to(self.root).as_posix() for path in root.rglob("*")
                 if path.is_file() and not path.is_symlink() and self.tmp_dir not in path.parents)
        page = heapq.nsmallest(limit + 1, (name for name in names if cursor is None or name > cursor))
        return ObjectPage([self.stat(name) for name in page[:limit]], page[limit - 1] if len(page) > limit else None)

    def delete(self, relative_path: str) -> bool:
        target = self._resolve(relative_path)
        if target.is_file():
            target.unlink()
            return True
        return False

    def recover_stale_temps(self, older_than: datetime) -> int:
        if not older_than:
            raise ValueError("older_than es obligatorio")
        cutoff = older_than.timestamp()
        removed = 0
        for temp_file in self.tmp_dir.glob("*.part"):
            try:
                if temp_file.stat().st_mtime < cutoff:
                    temp_file.unlink()
                    removed += 1
            except OSError:
                continue
        return removed
