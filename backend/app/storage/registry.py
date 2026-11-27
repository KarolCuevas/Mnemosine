from collections.abc import Callable

from .contract import SourceUnavailableError, StorageAdapter


class StorageRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[dict], StorageAdapter]] = {}

    def register(self, code: str, factory: Callable[[dict], StorageAdapter]) -> None:
        if code in self._factories:
            raise ValueError("adaptador ya registrado")
        self._factories[code] = factory

    def resolve(self, source: dict) -> StorageAdapter:
        factory = self._factories.get(source["adapter_code"])
        if factory is None:
            raise SourceUnavailableError("adaptador no configurado")
        return factory(source)
