"""Gestión mínima de plataforma para ADMIN (H2).

El rol ADMIN habilita estos endpoints; NO concede acceso al contenido (matriz
de acceso revisada). Toda mutación exige CSRF y queda auditada.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import users as users_repo
from app.schemas.auth import InvitationOut, InvitationRequest, UserOut, user_to_out
from app.security.deps import CurrentUser, get_admin_user, require_csrf
from app.services import admin_service
from app.services.errors import ServiceError
from app.services.admin_service import SelfDeactivationError

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
