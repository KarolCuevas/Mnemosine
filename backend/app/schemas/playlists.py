from datetime import datetime

from pydantic import BaseModel, Field


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class PlaylistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class PlaylistAddTrack(BaseModel):
    track_id: int


class PlaylistReorder(BaseModel):
    track_ids: list[int] = Field(min_length=1)


class PlaylistSummary(BaseModel):
    playlist_id: int
    name: str
    description: str | None
    item_count: int
    created_at: datetime
    updated_at: datetime


class PlaylistTrack(BaseModel):
    cover_url: str | None = None
    position: int
    track_id: int
    title: str
    artists: str
    album: str | None
    duration_seconds: int
    track_number: int | None


class PlaylistDetail(BaseModel):
    playlist_id: int
    name: str
    description: str | None
    tracks: list[PlaylistTrack]
