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


def set_account_role(*, admin_user_id: int, target_user_id: int, role: str) -> dict:
    """Promueve/degrada una cuenta. No puedes cambiar tu propio rol (evita quedarse sin admin)."""
    if role not in ("USER", "ADMIN"):
        raise ServiceError("rol no válido")
    if admin_user_id == target_user_id:
        raise SelfDeactivationError("no puedes cambiar tu propio rol")

    with db.transaction() as cursor:
        cursor.execute(
            "SELECT user_id, username, role, is_active FROM USER_ACCOUNT WHERE user_id = %s FOR UPDATE",
            (target_user_id,),
        )
        target = cursor.fetchone()
        if target is None:
            raise ServiceError("Cuenta no encontrada")
        if target["role"] == role:
            return users.find_by_id(target_user_id)  # type: ignore[return-value]
        cursor.execute(
            "UPDATE USER_ACCOUNT SET role = %s WHERE user_id = %s",
            (role, target_user_id),
        )
        operations.record_permission_audit(
            cursor,
            action="ROLE_CHANGE",
            actor_user_id=admin_user_id,
            target_user_id=target_user_id,
            details=f"rol {target['role']} -> {role}",
        )
    return users.find_by_id(target_user_id)  # type: ignore[return-value]


def list_file_operations(*, type_: str | None, page: int, page_size: int) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    offset = (page - 1) * page_size
    with db.read_only() as cursor:
        where = "type = %s" if type_ else "1=1"
        params = ((type_,) if type_ else ())
        cursor.execute(f"SELECT COUNT(*) AS total FROM FILE_OPERATION WHERE {where}", params)
        total = cursor.fetchone()["total"]
        cursor.execute(
            f"SELECT operation_id, type, actor_user_id, location_id, result, bytes_transferred, detail, created_at "
            f"FROM FILE_OPERATION WHERE {where} ORDER BY operation_id DESC LIMIT %s OFFSET %s",
            (*params, page_size, offset),
        )
        items = list(cursor.fetchall())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_permission_audits(*, page: int, page_size: int) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    offset = (page - 1) * page_size
    with db.read_only() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM PERMISSION_AUDIT")
        total = cursor.fetchone()["total"]
        cursor.execute(
            "SELECT audit_id, action, actor_user_id, location_id, target_user_id, declaration, details, created_at "
            "FROM PERMISSION_AUDIT ORDER BY audit_id DESC LIMIT %s OFFSET %s",
            (page_size, offset),
        )
        items = list(cursor.fetchall())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def moderate_unpublish(*, admin_user_id: int, location_id: int) -> dict:
    """Moderación: despublica cualquier copia PUBLIC. No concede ni retira acceso a bytes;
    solo deja la copia como PRIVATE. Queda auditada."""
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT location_id, visibility FROM TRACK_LOCATION WHERE location_id = %s LIMIT 1",
            (location_id,),
        )
        location = cursor.fetchone()
        if location is None:
            raise ServiceError("copia no encontrada")
        cursor.execute(
            "UPDATE TRACK_LOCATION SET visibility = 'PRIVATE' WHERE location_id = %s",
            (location_id,),
        )
        operations.record_permission_audit(
            cursor,
            action="UNPUBLISH",
            actor_user_id=admin_user_id,
            location_id=location_id,
            details="despublicada por moderación",
        )
    return {"location_id": location_id, "visibility": "PRIVATE"}


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
