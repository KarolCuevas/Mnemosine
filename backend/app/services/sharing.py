"""Publicación, descarga pública y compartición individual (Fase 4 / H4).

Reglas (plan + DECISIONES D8/matriz):
- Publicar exige declaración (AUTHORIZATION_DECLARATION, tipo PUBLICATION).
- Publicar no concede descarga: la descarga pública necesita además
  public_download_allowed = 1 y declaración DOWNLOAD.
- Compartir exige declaración (se guarda en TRACK_SHARE.declaration y en
  PERMISSION_AUDIT.declaration).
- Re-conceder tras revocar reactiva la fila existente (UNIQUE copia+destinatario).
- Toda mutación exige sesión + CSRF (rutas) y queda en PERMISSION_AUDIT.
- El rol ADMIN no interviene en estos permisos.
"""

from app.repositories import db, operations
from app.services.errors import ServiceError


class DeclarationRequiredError(ServiceError):
    pass


class CopyNotFoundError(ServiceError):
    pass


def _get_owned_location(cursor, *, location_id: int, owner_id: int) -> dict | None:
    cursor.execute(
        "SELECT location_id, track_id, relative_path, visibility, public_download_allowed, availability "
        "FROM TRACK_LOCATION WHERE location_id = %s AND owner_user_id = %s LIMIT 1",
        (location_id, owner_id),
    )
    return cursor.fetchone()


def set_visibility(*, user_id: int, location_id: int, publish: bool, declaration: str | None) -> dict:
    declaration = (declaration or "").strip() or None
    if publish and not declaration:
        raise DeclarationRequiredError("publicar exige una declaración de autorización (quién, alcance)")

    with db.transaction() as cursor:
        location = _get_owned_location(cursor, location_id=location_id, owner_id=user_id)
        if location is None:
            raise CopyNotFoundError("copia no encontrada")
        if publish:
            cursor.execute(
                "UPDATE TRACK_LOCATION SET visibility = 'PUBLIC' WHERE location_id = %s",
                (location_id,),
            )
            cursor.execute(
                "INSERT INTO AUTHORIZATION_DECLARATION (location_id, kind, declaration, declared_by) "
                "VALUES (%s, 'PUBLICATION', %s, %s)",
                (location_id, declaration, user_id),
            )
            operations.record_permission_audit(
                cursor, action="PUBLISH", actor_user_id=user_id,
                location_id=location_id, declaration=declaration,
                details="la copia pasa a ser visible para las cuentas autenticadas",
            )
        else:
            cursor.execute(
                "UPDATE TRACK_LOCATION SET visibility = 'PRIVATE' WHERE location_id = %s",
                (location_id,),
            )
            operations.record_permission_audit(
                cursor, action="UNPUBLISH", actor_user_id=user_id,
                location_id=location_id,
                details="la copia vuelve a ser privada",
            )
    return {"location_id": location_id, "visibility": "PUBLIC" if publish else "PRIVATE"}


def set_public_download(*, user_id: int, location_id: int, allow: bool, declaration: str | None) -> dict:
    declaration = (declaration or "").strip() or None
    if allow and not declaration:
        raise DeclarationRequiredError("autorizar la descarga pública exige una declaración (quién, alcance)")

    with db.transaction() as cursor:
        location = _get_owned_location(cursor, location_id=location_id, owner_id=user_id)
        if location is None:
            raise CopyNotFoundError("copia no encontrada")
        cursor.execute(
            "UPDATE TRACK_LOCATION SET public_download_allowed = %s WHERE location_id = %s",
            (int(allow), location_id),
        )
        if allow:
            cursor.execute(
                "INSERT INTO AUTHORIZATION_DECLARATION (location_id, kind, declaration, declared_by) "
                "VALUES (%s, 'DOWNLOAD', %s, %s)",
                (location_id, declaration, user_id),
            )
        operations.record_permission_audit(
            cursor,
            action="DOWNLOAD_GRANT" if allow else "DOWNLOAD_REVOKE",
            actor_user_id=user_id,
            location_id=location_id,
            declaration=declaration if allow else None,
            details=("public_download_allowed=1" if allow else "public_download_allowed=0"),
        )
    return {"location_id": location_id, "public_download_allowed": allow}


def share_with_user(*, owner_id: int, location_id: int, recipient_username: str,
                    can_stream: bool, can_download: bool, declaration: str) -> dict:
    declaration = (declaration or "").strip()
    if not declaration:
        raise DeclarationRequiredError("compartir exige una declaración de autorización (quién, alcance)")
    if not can_stream and not can_download:
        raise ServiceError("elige al menos un permiso para compartir")

    with db.transaction() as cursor:
        location = _get_owned_location(cursor, location_id=location_id, owner_id=owner_id)
        if location is None:
            raise CopyNotFoundError("copia no encontrada")
        cursor.execute(
            "SELECT user_id FROM USER_ACCOUNT WHERE username = %s AND is_active = 1 LIMIT 1",
            (recipient_username.strip().lower(),),
        )
        recipient = cursor.fetchone()
        if recipient is None:
            raise ServiceError("la cuenta destinataria no existe o está desactivada")
        recipient_id = recipient["user_id"]
        if recipient_id == owner_id:
            raise ServiceError("no puedes compartir una copia contigo mismo")
        cursor.execute(
            "INSERT INTO TRACK_SHARE (location_id, recipient_user_id, can_stream, can_download, "
            "granted_by, declaration, granted_at, revoked_at, revoked_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW(), NULL, NULL) "
            "ON DUPLICATE KEY UPDATE can_stream = VALUES(can_stream), can_download = VALUES(can_download), "
            "granted_by = VALUES(granted_by), declaration = VALUES(declaration), granted_at = NOW(), "
            "revoked_at = NULL, revoked_by = NULL",
            (location_id, recipient_id, int(can_stream), int(can_download), owner_id, declaration),
        )
        operations.record_permission_audit(
            cursor, action="SHARE_GRANT", actor_user_id=owner_id,
            location_id=location_id, target_user_id=recipient_id,
            declaration=declaration,
            details=f"stream={int(can_stream)}, descarga={int(can_download)}",
        )
    return {"location_id": location_id, "recipient_user_id": recipient_id,
            "can_stream": can_stream, "can_download": can_download}


def revoke_share(*, owner_id: int, location_id: int, recipient_user_id: int) -> dict:
    with db.transaction() as cursor:
        location = _get_owned_location(cursor, location_id=location_id, owner_id=owner_id)
        if location is None:
            raise CopyNotFoundError("copia no encontrada")
        cursor.execute(
            "UPDATE TRACK_SHARE SET revoked_at = NOW(), revoked_by = %s "
            "WHERE location_id = %s AND recipient_user_id = %s AND revoked_at IS NULL",
            (owner_id, location_id, recipient_user_id),
        )
        if cursor.rowcount != 1:
            raise ServiceError("no había un compartir activo para esa cuenta")
        operations.record_permission_audit(
            cursor, action="SHARE_REVOKE", actor_user_id=owner_id,
            location_id=location_id, target_user_id=recipient_user_id,
            details="share revocado; las nuevas solicitudes serán denegadas",
        )
    return {"location_id": location_id, "recipient_user_id": recipient_user_id, "revoked": True}


def list_shares(*, owner_id: int, location_id: int) -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT location_id FROM TRACK_LOCATION WHERE location_id = %s AND owner_user_id = %s LIMIT 1",
            (location_id, owner_id),
        )
        if cursor.fetchone() is None:
            raise CopyNotFoundError("copia no encontrada")
        cursor.execute(
            "SELECT s.recipient_user_id, u.username, u.display_name, s.can_stream, s.can_download, "
            "       s.declaration, s.granted_at, s.revoked_at "
            "FROM TRACK_SHARE s JOIN USER_ACCOUNT u ON u.user_id = s.recipient_user_id "
            "WHERE s.location_id = %s ORDER BY s.revoked_at IS NOT NULL, u.username",
            (location_id,),
        )
        return list(cursor.fetchall())
