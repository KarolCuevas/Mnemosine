"""Gestión mínima de plataforma para ADMIN (H2): invitaciones y cuentas.

El rol ADMIN habilita estos endpoints; NO otorga ni retira permisos sobre el
contenido (matriz de acceso revisada). Desactivar una cuenta revoca todas sus
sesiones en caliente y queda registrado en PERMISSION_AUDIT.
"""

import hashlib
import secrets

from app.repositories import db, invitations, operations, sessions, users
from app.services.errors import ServiceError


class SelfDeactivationError(ServiceError):
    pass


def create_invitation(*, admin_user_id: int, expires_in_days: int = 7) -> tuple[str, object]:
    raw_code = secrets.token_urlsafe(24)
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    with db.transaction() as cursor:
        invitation_id = invitations.create_invitation(
            cursor, code_hash=code_hash, created_by=admin_user_id, expires_in_days=expires_in_days
        )
        cursor.execute(
            "SELECT expires_at FROM INVITATION WHERE invitation_id = %s",
            (invitation_id,),
        )
        expires_at = cursor.fetchone()["expires_at"]
    return raw_code, expires_at


def set_account_active(*, admin_user_id: int, target_user_id: int, active: bool) -> dict:
    if not active and admin_user_id == target_user_id:
        raise SelfDeactivationError("No puedes desactivar tu propia cuenta")

    with db.transaction() as cursor:
        cursor.execute(
            "SELECT user_id, username, is_active, role FROM USER_ACCOUNT WHERE user_id = %s FOR UPDATE",
            (target_user_id,),
        )
        target = cursor.fetchone()
        if target is None:
            raise ServiceError("Cuenta no encontrada")
        cursor.execute(
            "UPDATE USER_ACCOUNT SET is_active = %s WHERE user_id = %s",
            (int(active), target_user_id),
        )
        if not active:
            sessions.revoke_all_for_user(cursor, target_user_id)
        operations.record_permission_audit(
            cursor,
            action="ACCOUNT_ACTIVATE" if active else "ACCOUNT_DEACTIVATE",
            actor_user_id=admin_user_id,
            target_user_id=target_user_id,
            details=f"cuenta {'activada' if active else 'desactivada'} por administración",
        )
    return users.find_by_id(target_user_id)  # type: ignore[return-value]
