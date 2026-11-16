"""Cuentas de usuario. SQL parametrizado sobre USER_ACCOUNT."""

import mysql.connector

from app.repositories import db


def find_by_identity(identity: str) -> dict | None:
    """Busca por username O email (login). Devuelve la fila o None."""
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT user_id, username, email, password_hash, display_name, role, is_active "
            "FROM USER_ACCOUNT WHERE username = %s OR email = %s LIMIT 1",
            (identity, identity),
        )
        return cursor.fetchone()


def find_by_id(user_id: int) -> dict | None:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT user_id, username, email, display_name, role, is_active, created_at "
            "FROM USER_ACCOUNT WHERE user_id = %s LIMIT 1",
            (user_id,),
        )
        return cursor.fetchone()


def create_user(cursor, *, username: str, email: str, password_hash: str, display_name: str | None, role: str = "USER") -> int:
    """Inserta dentro de una transacción abierta (cursor de db.transaction())."""
    cursor.execute(
        "INSERT INTO USER_ACCOUNT (username, email, password_hash, display_name, role) "
        "VALUES (%s, %s, %s, %s, %s)",
        (username, email, password_hash, display_name, role),
    )
    return cursor.lastrowid


def list_users(limit: int = 100) -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT user_id, username, email, display_name, role, is_active, created_at "
            "FROM USER_ACCOUNT ORDER BY user_id LIMIT %s",
            (limit,),
        )
        return list(cursor.fetchall())


def username_or_email_taken(username: str, email: str) -> str | None:
    """Devuelve 'username' | 'email' si ya existe (para mensajes de conflicto)."""
    with db.read_only() as cursor:
        cursor.execute("SELECT username FROM USER_ACCOUNT WHERE username = %s LIMIT 1", (username,))
        row = cursor.fetchone()
        if row:
            return "username"
        cursor.execute("SELECT user_id FROM USER_ACCOUNT WHERE email = %s LIMIT 1", (email,))
        if cursor.fetchone():
            return "email"
        return None


def is_duplicate_error(error: mysql.connector.Error) -> bool:
    return error.errno in (1062,)
