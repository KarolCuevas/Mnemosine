from datetime import datetime

from pydantic import BaseModel, Field


class VisibilityUpdate(BaseModel):
    publish: bool
    declaration: str | None = Field(default=None, max_length=500)


class PublicDownloadUpdate(BaseModel):
    allow: bool
    declaration: str | None = Field(default=None, max_length=500)


class ShareCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    can_stream: bool = True
    can_download: bool = False
    declaration: str = Field(min_length=1, max_length=500)


class ShareOut(BaseModel):
    recipient_user_id: int
    username: str
    display_name: str | None
    can_stream: bool
    can_download: bool
    declaration: str | None
    granted_at: datetime
    revoked_at: datetime | None


class LocationSummaryOut(BaseModel):
    location_id: int
    track_id: int
    title: str
    artists: str
    album: str | None
    visibility: str
    public_download_allowed: bool
    availability: str
    shares: list[ShareOut]
