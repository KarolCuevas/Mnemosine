"""Sesiones revocables (USER_SESSION). SQL parametrizado.

created_at ancla el límite absoluto; expires_at el deslizante. Desactivar la
cuenta revoca todas sus sesiones con revoke_all_for_user().
"""

import mysql.connector

from app.core.config import get_settings
from app.repositories import db


def create_session(cursor, *, user_id: int, token_hash: str) -> int:
    settings = get_settings()
    cursor.execute(
        "INSERT INTO USER_SESSION (user_id, token_hash, expires_at) "
        "VALUES (%s, %s, NOW() + INTERVAL %s DAY)",
        (user_id, token_hash, settings.session_sliding_days),
    )
    return cursor.lastrowid


def get_active_session_with_user(token_hash: str) -> dict | None:
    """Sesión viva (no revocada, no expirada) unida a su usuario, o None."""
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT s.session_id, s.user_id, s.created_at, s.expires_at, s.last_used_at, "
            "       u.username, u.email, u.display_name, u.role, u.is_active "
            "FROM USER_SESSION s JOIN USER_ACCOUNT u ON u.user_id = s.user_id "
            "WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > NOW() "
            "LIMIT 1",
            (token_hash,),
        )
        return cursor.fetchone()


def touch_and_extend(session_id: int) -> None:
    """Deslizante: actualiza last_used_at y extiende expires_at."""
    settings = get_settings()
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE USER_SESSION SET last_used_at = NOW(), expires_at = NOW() + INTERVAL %s DAY "
            "WHERE session_id = %s AND revoked_at IS NULL",
            (settings.session_sliding_days, session_id),
        )


def revoke_session(cursor, session_id: int) -> None:
    cursor.execute(
        "UPDATE USER_SESSION SET revoked_at = NOW() WHERE session_id = %s AND revoked_at IS NULL",
        (session_id,),
    )


def revoke_all_for_user(cursor, user_id: int) -> int:
    cursor.execute(
        "UPDATE USER_SESSION SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )
    return cursor.rowcount


def is_duplicate_error(error: mysql.connector.Error) -> bool:
    return error.errno in (1062,)
