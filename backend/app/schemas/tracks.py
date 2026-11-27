"""Recorrido principal: carga, biblioteca, detalle, audio y descarga."""

from datetime import datetime

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    track_id: int
    location_id: int
    title: str
    artist: str
    album: str | None
    duration_seconds: int
    size_bytes: int
    sha256: str
    mime_type: str
    visibility: str
    album_artist: str | None = None
    genre: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    release_year: int | None = None
    cover_url: str | None = None
    warnings: list[str] = Field(default_factory=list)


class LibraryItem(BaseModel):
    cover_url: str | None = None
    location_id: int
    track_id: int
    title: str
    artists: str
    album: str | None
    duration_seconds: int
    track_number: int | None
    size_bytes: int
    availability: str
    available: bool
    visibility: str
    added_at: datetime


class LibraryPage(BaseModel):
    items: list[LibraryItem]
    total: int
    page: int
    page_size: int


class CopyOut(BaseModel):
    location_id: int
    size_bytes: int
    mime_type: str
    visibility: str
    availability: str
    sha256: str
    created_at: datetime


class AccessOut(BaseModel):
    can_stream: bool
    can_download: bool
    available: bool


class TrackDetail(BaseModel):
    cover_url: str | None = None
    album_artist: str | None = None
    genre: str | None = None
    track_id: int
    title: str
    artists: str
    album: str | None
    release_year: int | None
    duration_seconds: int
    track_number: int | None
    disc_number: int | None
    copies: list[CopyOut]
    access: AccessOut


class UploadForm(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    artist: str | None = Field(default=None, max_length=255)
    album: str | None = Field(default=None, max_length=512)
    track_number: int | None = Field(default=None, ge=1, le=1000)
    disc_number: int | None = Field(default=None, ge=1, le=100)
    release_year: int | None = Field(default=None, ge=1000, le=9999)
    album_artist: str | None = Field(default=None, max_length=255)
    genre: str | None = Field(default=None, max_length=255)
