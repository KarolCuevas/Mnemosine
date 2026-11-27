"""Proveedor del adaptador de almacenamiento (una instancia por proceso)."""

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.storage import LocalStorageAdapter
from app.repositories import db
from app.storage.contract import SourceUnavailableError
from app.storage.registry import StorageRegistry

registry = StorageRegistry()


def _local(source: dict) -> LocalStorageAdapter:
    if source["config_version"] != 1 or source.get("adapter_config") not in (None, "{}", {}):
        raise SourceUnavailableError("configuración de fuente no soportada")
    # No agregar el prefijo al ID: las rutas desde 0012 ya son relativas a la raíz global.
    return LocalStorageAdapter(get_storage().root, source_prefix=source["base_relative_path"])


registry.register("LOCAL", _local)


def get_source(source_id: int) -> dict:
    with db.read_only() as cursor:
        cursor.execute("SELECT s.*, u.is_active AS owner_active FROM SOURCE s "
                       "LEFT JOIN USER_ACCOUNT u ON u.user_id = s.owner_user_id WHERE s.source_id = %s", (source_id,))
        source = cursor.fetchone()
    if not source or source["status"] != "ACTIVE" or (source["owner_user_id"] is not None and not source["owner_active"]):
        raise SourceUnavailableError("fuente no disponible")
    return source


def get_storage_for_source(source_id: int):
    """Uso interno después de autorizar la copia o inventario. Sin caché de credenciales."""
    return registry.resolve(get_source(source_id))


@lru_cache
def get_storage() -> LocalStorageAdapter:
    """Preparación temporal local; entrega y destinos usan get_storage_for_source."""
    settings = get_settings()
    root = Path(settings.storage_root) if settings.storage_root else Path(__file__).resolve().parents[3] / "storage"
    return LocalStorageAdapter(root)
