"""Registro explícito de módulos incluidos en el despliegue, no plugins de usuarios."""
from collections.abc import Callable

from .contract import CatalogError, MusicCatalogAdapter


class MusicCatalogRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[], MusicCatalogAdapter]] = {}

    def register(self, code: str, factory: Callable[[], MusicCatalogAdapter]) -> None:
        if code in self._factories:
            raise ValueError("proveedor ya registrado")
        self._factories[code] = factory

    def resolve(self, code: str) -> MusicCatalogAdapter:
        if code not in self._factories:
            raise CatalogError("Proveedor no disponible", status=404)
        return self._factories[code]()

    def all(self) -> list[MusicCatalogAdapter]:
        return [factory() for factory in self._factories.values()]
