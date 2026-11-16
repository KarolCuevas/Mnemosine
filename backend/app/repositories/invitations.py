"""Invitaciones de un solo uso (INVITATION). El alta es por invitación (D2)."""

from app.repositories import db


def create_invitation(cursor, *, code_hash: str, created_by: int, expires_in_days: int) -> int:
    cursor.execute(
        "INSERT INTO INVITATION (code_hash, created_by, expires_at) "
        "VALUES (%s, %s, NOW() + INTERVAL %s DAY)",
        (code_hash, created_by, expires_in_days),
    )
    return cursor.lastrowid


def find_valid_by_code_hash(code_hash: str) -> dict | None:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT invitation_id, created_by, expires_at FROM INVITATION "
            "WHERE code_hash = %s AND used_at IS NULL AND expires_at > NOW() LIMIT 1",
            (code_hash,),
        )
        return cursor.fetchone()


def mark_used(cursor, *, invitation_id: int, used_by: int) -> int:
    """Un solo uso, atómico dentro de la transacción del registro."""
    cursor.execute(
        "UPDATE INVITATION SET used_at = NOW(), used_by = %s "
        "WHERE invitation_id = %s AND used_at IS NULL AND expires_at > NOW()",
        (used_by, invitation_id),
    )
    return cursor.rowcount


def count_active(cursor, created_by: int) -> int:
    cursor.execute(
        "SELECT COUNT(*) AS n FROM INVITATION "
        "WHERE created_by = %s AND used_at IS NULL AND expires_at > NOW()",
        (created_by,),
    )
    return cursor.fetchone()["n"]
