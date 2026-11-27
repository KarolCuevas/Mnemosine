"""Contrato de almacenamiento de audio (RF-14 / RNF-08).

RF-14: el catálogo y el acceso no dependen de una ruta local concreta.
Toda entrega de audio debe pasar por un adaptador que implemente esta
interfaz. Nunca se expone una ruta física a clientes web ni a respuestas API.

Diseño:
- Las rutas son RELATIVAS y se normalizan siempre (ver normalize_relative_path);
  las absolutas, las de otra unidad y los '..' se rechazan.
- LOCAL escribe primero en un temporal ('StagedUpload'), calcula su
  SHA-256 y solo entonces se publica con commit() de forma atómica.
- commit() nunca sobrescribe un destino existente.
- discard() limpia el temporal propio. recover_stale_temps() solo se usa offline.
- La autorización se comprueba en la capa de servicios ANTES de llamar aquí;
  conocer la ruta relativa no concede acceso.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Iterable, Iterator

MAX_RELATIVE_PATH_LENGTH = 512
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class StorageError(Exception):
    """Error base del almacenamiento."""


class InvalidPathError(StorageError):
    """Ruta absoluta, con '..', caracteres de control o demasiado larga."""


class FileTooLargeError(StorageError):
    """El flujo superó el máximo permitido para la carga."""


class DestinationExistsError(StorageError):
    """El destino de commit() ya existe; nunca se sobrescribe."""


class NotFoundError(StorageError):
    """El objeto no existe (o no es un archivo regular)."""


class UnsupportedOperationError(StorageError):
    """El adaptador no implementa la capacidad solicitada."""


class SourceUnavailableError(StorageError):
    """Fuente desconectada, propietario inactivo o adaptador no configurado."""


class ObjectState(StrEnum):
    FOUND = "FOUND"
    NOT_ACCESSIBLE = "NOT_ACCESSIBLE"
    NOT_FOUND = "NOT_FOUND"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    TEMPORARY_ERROR = "TEMPORARY_ERROR"


@dataclass(frozen=True)
class StorageCapabilities:
    read: bool = True
    write: bool = False
    ranges: bool = True
    listing: bool = False
    resumable_upload: bool = False
    changes: bool = False
    delete: bool = False


@dataclass(frozen=True)
class ObjectInfo:
    object_id: str
    state: ObjectState
    size_bytes: int | None = None
    version: str | None = None


@dataclass(frozen=True)
class ObjectPage:
    items: list[ObjectInfo]
    next_cursor: str | None = None


def normalize_relative_path(relative_path: str) -> str:
    if not isinstance(relative_path, str):
        raise InvalidPathError("la ruta debe ser texto")
    candidate = relative_path.replace("\\", "/")
    if not candidate.strip():
        raise InvalidPathError("ruta vacía")
    if candidate.startswith("/") or _DRIVE_PREFIX.match(candidate):
        raise InvalidPathError("la ruta debe ser relativa a la raíz de almacenamiento")
    segments: list[str] = []
    for segment in candidate.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            raise InvalidPathError("la ruta sale de la raíz de almacenamiento")
        segments.append(segment)
    if not segments:
        raise InvalidPathError("ruta vacía")
    normalized = "/".join(segments)
    if len(normalized) > MAX_RELATIVE_PATH_LENGTH:
        raise InvalidPathError(f"la ruta supera {MAX_RELATIVE_PATH_LENGTH} caracteres")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise InvalidPathError("la ruta contiene caracteres de control")
    return normalized


@dataclass(frozen=True)
class StagedUpload:
    """Carga temporal ya validada a nivel de bytes. 'token' es opaco: solo el
    adaptador que lo creó entiende su significado. No exponer a clientes."""

    token: str
    sha256: str
    size_bytes: int


class StorageAdapter(ABC):
    """Objetos y capacidades. La preparación local es opcional, nunca obligatoria para lectores."""

    capabilities = StorageCapabilities()

    def require(self, capability: str) -> None:
        if not getattr(self.capabilities, capability, False):
            raise UnsupportedOperationError("operación no soportada por esta fuente")

    @abstractmethod
    def stat(self, object_id: str) -> ObjectInfo: ...

    @abstractmethod
    def read_range(self, object_id: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]: ...

    def list_objects(self, *, cursor: str | None = None, limit: int = 50) -> ObjectPage:
        raise UnsupportedOperationError("esta fuente no permite inventario")

    def save_stream(self, chunks: Iterable[bytes], *, max_bytes: int) -> StagedUpload:
        """Escribe el flujo en un temporal y calcula su SHA-256 y tamaño.

        Ante cualquier error (o si se supera max_bytes) el temporal se elimina
        y se propaga FileTooLargeError/StorageError. El objeto NO queda
        disponible hasta commit()."""
        raise UnsupportedOperationError("esta fuente no prepara temporales locales")

    def commit(self, staged: StagedUpload, relative_path: str) -> str:
        """Publica el temporal en su destino de forma atómica.

        Devuelve la ruta relativa normalizada. Lanza DestinationExistsError si
        ya hay un objeto en el destino."""
        raise UnsupportedOperationError("esta fuente no admite publicación local")

    def discard(self, staged: StagedUpload) -> None:
        """Elimina el temporal (p. ej. tras un fallo de transacción SQL)."""
        raise UnsupportedOperationError("esta fuente no prepara temporales locales")

    def exists(self, relative_path: str) -> bool:
        return self.stat(relative_path).state == ObjectState.FOUND

    def size(self, relative_path: str) -> int:
        """Bytes del objeto; NotFoundError si no existe."""
        info = self.stat(relative_path)
        if info.state != ObjectState.FOUND or info.size_bytes is None:
            raise NotFoundError("objeto no disponible")
        return info.size_bytes

    def stream_range(self, relative_path: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]:
        """Itera bytes desde 'offset', como mucho 'length' (None = hasta EOF)."""
        return self.read_range(relative_path, offset, length)

    def delete(self, relative_path: str) -> bool:
        """Borrado físico EXPLÍCITO. Devuelve True si borró algo.

        Ninguna cascada SQL debe disparar este método (plan §2, punto 9)."""
        raise UnsupportedOperationError("esta fuente no admite borrado")

    def recover_stale_temps(self, older_than: datetime) -> int:
        """Borra temporales interrumpidos anteriores a 'older_than'. Devuelve cuántos."""
        raise UnsupportedOperationError("esta fuente no prepara temporales locales")
