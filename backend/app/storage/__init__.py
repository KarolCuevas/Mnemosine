"""Almacenamiento de audio. Sustituir LocalStorageAdapter por otro antes de
cambiar a fuentes remotas; el resto del código depende solo del contrato."""

from .contract import (
    DestinationExistsError,
    FileTooLargeError,
    InvalidPathError,
    NotFoundError,
    StagedUpload,
    StorageAdapter,
    StorageError,
    normalize_relative_path,
)
from .local import LocalStorageAdapter

__all__ = [
    "LocalStorageAdapter",
    "StagedUpload",
    "StorageAdapter",
    "StorageError",
    "InvalidPathError",
    "FileTooLargeError",
    "DestinationExistsError",
    "NotFoundError",
    "normalize_relative_path",
]
