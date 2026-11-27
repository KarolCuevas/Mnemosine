"""Catálogos de metadatos: deliberadamente sin operaciones de audio."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogError(Exception):
    def __init__(self, message: str, *, status: int = 503, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class CatalogCapabilities:
    search: bool = False
    lookup: bool = False
    playlists: bool = False
    requires_user_connection: bool = False


class CoreArtist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str | None = None
    name: str = Field(max_length=512)
    credit: str = Field(max_length=512)
    join_phrase: str = Field(default="", max_length=128)


class CoreRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str
    title: str = Field(max_length=512)
    date: str | None = Field(default=None, max_length=10)


class Recording(BaseModel):
    """Lista blanca: solo núcleo CC0; no tags, portadas, ratings ni puntuación."""
    model_config = ConfigDict(extra="forbid")
    provider: str
    entity_type: str = "recording"
    provider_id: str
    title: str = Field(max_length=512)
    artists: list[CoreArtist] = Field(default_factory=list)
    duration_ms: int | None = Field(default=None, ge=0)
    isrcs: list[str] = Field(default_factory=list)
    releases: list[CoreRelease] = Field(default_factory=list)
    disambiguation: str | None = Field(default=None, max_length=2000)
    original_url: str
    fetched_at: datetime


@dataclass
class CatalogPage:
    items: list[Recording]
    total: int


class MusicCatalogAdapter(ABC):
    code: str
    capabilities = CatalogCapabilities()

    @property
    def enabled(self) -> bool:
        return True

    def normalize_id(self, value: str) -> str:
        if not value or len(value) > 128:
            raise CatalogError("Identificador no válido", status=422)
        return value

    @abstractmethod
    def search(self, title: str, artist: str, *, offset: int, limit: int) -> CatalogPage: ...

    @abstractmethod
    def get_reference(self, provider_id: str) -> Recording: ...

    def list_playlists(self):
        raise CatalogError("Este catálogo no ofrece listas en Mnemosine", status=422)
