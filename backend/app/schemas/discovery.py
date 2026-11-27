from datetime import datetime

from pydantic import BaseModel


class DiscoveryAccount(BaseModel):
    username: str
    display_name: str | None
    public_copies: int


class DiscoveryItem(BaseModel):
    cover_url: str | None = None
    location_id: int
    track_id: int
    title: str
    artists: str
    album: str | None
    duration_seconds: int
    track_number: int | None
    size_bytes: int
    mime_type: str
    public_download_allowed: bool
    added_at: datetime


class DiscoveryCatalog(BaseModel):
    username: str
    display_name: str | None
    items: list[DiscoveryItem]


class SharedItem(BaseModel):
    cover_url: str | None = None
    location_id: int
    track_id: int
    title: str
    artists: str
    album: str | None
    duration_seconds: int
    track_number: int | None
    size_bytes: int
    mime_type: str
    availability: str
    can_stream: bool
    can_download: bool
    owner_username: str
