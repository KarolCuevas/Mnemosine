"""Gestión de plataforma para ADMIN (H2/H5).

El rol ADMIN habilita estos endpoints; NO concede acceso al contenido (matriz
de acceso revisada). Toda mutación exige CSRF y queda auditada.
"""

import threading

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.repositories import users as users_repo
from app.schemas.admin import (
    FileOperationPage,
    ModerateUnpublishOut,
    PermissionAuditPage,
    RoleUpdate,
    ScanJobOut,
    ScanRequest,
    SourceCreate,
    SourceOut,
    SourceStatusUpdate,
)
from app.schemas.auth import InvitationOut, InvitationRequest, UserOut, user_to_out
from app.security.deps import CurrentUser, get_admin_user, require_csrf
from app.services import admin_service, scans
from app.services.errors import ServiceError
from app.services.admin_service import SelfDeactivationError
from app.services.scans import SourcePathError

router = APIRouter(prefix="/admin", tags=["Administración"])


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
def create_invitation(payload: InvitationRequest, _csrf: None = Depends(require_csrf),
                      admin: CurrentUser = Depends(get_admin_user)) -> InvitationOut:
    code, expires_at = admin_service.create_invitation(
        admin_user_id=admin.user_id, expires_in_days=payload.expires_in_days
    )
    return InvitationOut(code=code, expires_at=expires_at)


@router.get("/users", response_model=list[UserOut])
def list_users(admin: CurrentUser = Depends(get_admin_user)) -> list[UserOut]:
    return [user_to_out(u) for u in users_repo.list_users(limit=100)]


@router.get("/operations", response_model=FileOperationPage)
def list_operations(type_: str | None = Query(None, alias="type"),
                    page: int = Query(1, ge=1),
                    page_size: int = Query(50, ge=1, le=200),
                    admin: CurrentUser = Depends(get_admin_user)) -> FileOperationPage:
    normalized = (type_ or "").strip().upper() or None
    if normalized and normalized not in ("UPLOAD", "DOWNLOAD", "SCAN"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="type debe ser UPLOAD, DOWNLOAD o SCAN")
    return FileOperationPage(**admin_service.list_file_operations(type_=normalized, page=page, page_size=page_size))


@router.get("/permission-audit", response_model=PermissionAuditPage)
def list_permission_audit(page: int = Query(1, ge=1),
                          page_size: int = Query(50, ge=1, le=200),
                          admin: CurrentUser = Depends(get_admin_user)) -> PermissionAuditPage:
    return PermissionAuditPage(**admin_service.list_permission_audits(page=page, page_size=page_size))


@router.get("/sources", response_model=list[SourceOut])
def list_sources(admin: CurrentUser = Depends(get_admin_user)) -> list[SourceOut]:
    return [SourceOut(**row) for row in scans.list_sources()]


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate,
                  _csrf: None = Depends(require_csrf),
                  admin: CurrentUser = Depends(get_admin_user)) -> SourceOut:
    try:
        row = scans.create_source(name=payload.name, base_relative_path=payload.base_relative_path,
                                  owner_user_id=payload.owner_user_id)
    except SourcePathError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    return SourceOut(**row, copies=0, scan_jobs=0)


@router.post("/sources/{source_id}/scan", response_model=ScanJobOut, status_code=status.HTTP_202_ACCEPTED)
def scan_source(source_id: int, payload: ScanRequest,
                _csrf: None = Depends(require_csrf),
                admin: CurrentUser = Depends(get_admin_user)) -> ScanJobOut:
    try:
        job = scans.create_scan_job(source_id=source_id, owner_user_id=payload.owner_user_id)
    except SourcePathError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    threading.Thread(
        target=scans.run_scan,
        kwargs={"scan_job_id": job["scan_job_id"]},
        daemon=True,
        name=f"scan-{job['scan_job_id']}",
    ).start()
    return ScanJobOut(**job)


@router.get("/scan-jobs/{scan_job_id}", response_model=ScanJobOut)
def get_scan_job(scan_job_id: int, admin: CurrentUser = Depends(get_admin_user)) -> ScanJobOut:
    row = scans.get_scan_job(scan_job_id=scan_job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado")
    return ScanJobOut(**row)


@router.post("/sources/{source_id}/status")
def set_source_status(source_id: int, payload: SourceStatusUpdate,
                      _csrf: None = Depends(require_csrf),
                      admin: CurrentUser = Depends(get_admin_user)) -> dict:
    try:
        return scans.set_source_status(source_id=source_id, status=payload.status)
    except SourcePathError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


@router.post("/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, payload: RoleUpdate,
             _csrf: None = Depends(require_csrf),
             admin: CurrentUser = Depends(get_admin_user)) -> UserOut:
    try:
        updated = admin_service.set_account_role(
            admin_user_id=admin.user_id, target_user_id=user_id, role=payload.role
        )
    except SelfDeactivationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except ServiceError as error:
        detail = str(error)
        if detail == "Cuenta no encontrada":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    return user_to_out(updated)


@router.post("/locations/{location_id}/unpublish", response_model=ModerateUnpublishOut)
def moderate_unpublish(location_id: int,
                       _csrf: None = Depends(require_csrf),
                       admin: CurrentUser = Depends(get_admin_user)) -> ModerateUnpublishOut:
    try:
        return ModerateUnpublishOut(**admin_service.moderate_unpublish(
            admin_user_id=admin.user_id, location_id=location_id
        ))
    except ServiceError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, _csrf: None = Depends(require_csrf),
                    admin: CurrentUser = Depends(get_admin_user)) -> UserOut:
    try:
        updated = admin_service.set_account_active(
            admin_user_id=admin.user_id, target_user_id=user_id, active=False
        )
    except SelfDeactivationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No puedes desactivar tu propia cuenta")
    except ServiceError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada")
    return user_to_out(updated)


@router.post("/users/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, _csrf: None = Depends(require_csrf),
                  admin: CurrentUser = Depends(get_admin_user)) -> UserOut:
    try:
        updated = admin_service.set_account_active(
            admin_user_id=admin.user_id, target_user_id=user_id, active=True
        )
    except ServiceError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cuenta no encontrada")
    return user_to_out(updated)
