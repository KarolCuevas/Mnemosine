from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_relative_path: str = Field(min_length=1, max_length=512)
    owner_user_id: int | None = Field(default=None)


class SourceOut(BaseModel):
    source_id: int
    owner_user_id: int | None
    name: str
    base_relative_path: str
    status: str
    last_scanned_at: datetime | None
    created_at: datetime
    copies: int
    scan_jobs: int


class ScanRequest(BaseModel):
    owner_user_id: int = Field(gt=0)


class ScanJobOut(BaseModel):
    scan_job_id: int
    source_id: int
    owner_user_id: int
    status: str
    files_found: int
    files_added: int
    files_skipped: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SourceStatusUpdate(BaseModel):
    status: Literal["ACTIVE", "DISCONNECTED"]


class RoleUpdate(BaseModel):
    role: Literal["USER", "ADMIN"]


class FileOperationOut(BaseModel):
    operation_id: int
    type: str
    actor_user_id: int | None
    location_id: int | None
    result: str
    bytes_transferred: int | None
    detail: str | None
    created_at: datetime


class FileOperationPage(BaseModel):
    items: list[FileOperationOut]
    total: int
    page: int
    page_size: int


class PermissionAuditOut(BaseModel):
    audit_id: int
    action: str
    actor_user_id: int | None
    location_id: int | None
    target_user_id: int | None
    declaration: str | None
    details: str | None
    created_at: datetime


class PermissionAuditPage(BaseModel):
    items: list[PermissionAuditOut]
    total: int
    page: int
    page_size: int


class ModerateUnpublishOut(BaseModel):
    location_id: int
    visibility: str
