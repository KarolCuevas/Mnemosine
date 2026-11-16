"""Proveedor del adaptador de almacenamiento (una instancia por proceso)."""

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.storage import LocalStorageAdapter


@lru_cache
def get_storage() -> LocalStorageAdapter:
    settings = get_settings()
    root = Path(settings.storage_root) if settings.storage_root else Path(__file__).resolve().parents[3] / "storage"
    return LocalStorageAdapter(root)
