"""Registro por invitación, login y sesiones (Fase 2 / H2).

Flujos en UNA transacción cuando tocan varias tablas (registro: cuenta +
invitación + sesión). La contraseña se hashea ANTES de abrir la transacción
(coste argon2, sin retener bloqueos).
"""

import hashlib

from app.repositories import db, invitations, sessions, users
from app.security import passwords, tokens
from app.services.errors import AuthError, ConflictError, InvitationError

_DUMMY_HASH: str | None = None


def _dummy_verify(password: str) -> None:
    """Verificación ficticia para no filtrar por tiempo qué cuentas existen."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = passwords.hash_password("mnemosine-dummy-password")
    passwords.verify_password(_DUMMY_HASH, password)


def _code_hash(raw_code: str) -> str:
    return hashlib.sha256(raw_code.strip().encode("utf-8")).hexdigest()


def register_with_invitation(*, username: str, email: str, password: str,
                             display_name: str | None, invitation_code: str) -> tuple[dict, str]:
    """Crea la cuenta, consume la invitación y abre sesión. Devuelve (usuario, token_crudo)."""
    password_hash = passwords.hash_password(password)
    code_hash = _code_hash(invitation_code)
    raw_token = tokens.new_session_token()

    with db.transaction() as cursor:
        cursor.execute(
            "SELECT invitation_id, used_at, expires_at FROM INVITATION "
            "WHERE code_hash = %s FOR UPDATE",
            (code_hash,),
        )
        invitation = cursor.fetchone()
        if invitation is None or invitation["used_at"] is not None:
            raise InvitationError("Invitación no válida")
        cursor.execute(
            "SELECT expires_at > NOW() AS vigente FROM INVITATION WHERE invitation_id = %s",
            (invitation["invitation_id"],),
        )
        if not cursor.fetchone()["vigente"]:
            raise InvitationError("Invitación caducada")

        taken = users.username_or_email_taken(username, email)
        if taken:
            raise ConflictError(taken)

        user_id = users.create_user(
            cursor, username=username, email=email,
            password_hash=password_hash, display_name=display_name, role="USER",
        )
        updated = invitations.mark_used(cursor, invitation_id=invitation["invitation_id"], used_by=user_id)
        if updated != 1:
            raise InvitationError("Invitación no válida")
        sessions.create_session(cursor, user_id=user_id, token_hash=tokens.hash_token(raw_token))

    user = users.find_by_id(user_id)
    assert user is not None
    return user, raw_token


def login(*, identity: str, password: str) -> tuple[dict, str]:
    """Verifica credenciales y abre sesión. AuthError genérico si falla."""
    account = users.find_by_identity(identity)
    if account is None or not account["is_active"]:
        _dummy_verify(password)
        raise AuthError("Credenciales no válidas")
    if not passwords.verify_password(account["password_hash"], password):
        raise AuthError("Credenciales no válidas")

    raw_token = tokens.new_session_token()
    with db.transaction() as cursor:
        sessions.create_session(cursor, user_id=account["user_id"], token_hash=tokens.hash_token(raw_token))

    user = users.find_by_id(account["user_id"])
    assert user is not None
    return user, raw_token


def logout(*, session_id: int) -> None:
    with db.transaction() as cursor:
        sessions.revoke_session(cursor, session_id)
