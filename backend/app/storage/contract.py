"""Contrato de almacenamiento de audio (RF-14 / RNF-08).

RF-14: el catálogo y el acceso no dependen de una ruta local concreta.
Toda entrega de audio debe pasar por un adaptador que implemente esta
interfaz. Nunca se expone una ruta física a clientes web ni a respuestas API.

Diseño:
- Las rutas son RELATIVAS y se normalizan siempre (ver normalize_relative_path);
  las absolutas, las de otra unidad y los '..' se rechazan.
- Una carga se escribe primero en un temporal ('StagedUpload'), calcula su
  SHA-256 y solo entonces se publica con commit() de forma atómica.
- commit() nunca sobrescribe un destino existente.
- discard() y recover_stale_temps() cubren fallos a mitad de carga.
- La autorización se comprueba en la capa de servicios ANTES de llamar aquí;
  conocer la ruta relativa no concede acceso.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
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
    """Contrato mínimo de almacenamiento de audio del MVP."""

    @abstractmethod
    def save_stream(self, chunks: Iterable[bytes], *, max_bytes: int) -> StagedUpload:
        """Escribe el flujo en un temporal y calcula su SHA-256 y tamaño.

        Ante cualquier error (o si se supera max_bytes) el temporal se elimina
        y se propaga FileTooLargeError/StorageError. El objeto NO queda
        disponible hasta commit()."""

    @abstractmethod
    def commit(self, staged: StagedUpload, relative_path: str) -> str:
        """Publica el temporal en su destino de forma atómica.

        Devuelve la ruta relativa normalizada. Lanza DestinationExistsError si
        ya hay un objeto en el destino."""

    @abstractmethod
    def discard(self, staged: StagedUpload) -> None:
        """Elimina el temporal (p. ej. tras un fallo de transacción SQL)."""

    @abstractmethod
    def exists(self, relative_path: str) -> bool: ...

    @abstractmethod
    def size(self, relative_path: str) -> int:
        """Bytes del objeto; NotFoundError si no existe."""

    @abstractmethod
    def stream_range(self, relative_path: str, offset: int = 0, length: int | None = None) -> Iterator[bytes]:
        """Itera bytes desde 'offset', como mucho 'length' (None = hasta EOF)."""

    @abstractmethod
    def delete(self, relative_path: str) -> bool:
        """Borrado físico EXPLÍCITO. Devuelve True si borró algo.

        Ninguna cascada SQL debe disparar este método (plan §2, punto 9)."""

    @abstractmethod
    def recover_stale_temps(self, older_than: datetime) -> int:
        """Borra temporales interrumpidos anteriores a 'older_than'. Devuelve cuántos."""
