"""Conexiones MySQL para repositorios. Sin ORM: SQL explícito y parametrizado.

Las funciones reciben una conexión abierta o la crean por sí mismas según el
caso; las transacciones de varias sentencias usan una conexión común con
autocommit desactivado y commit/rollback explícitos.
"""

from contextlib import contextmanager
from typing import Iterator

import mysql.connector
from mysql.connector.connection import MySQLConnection

from app.core.config import get_settings


def connect(*, autocommit: bool = False) -> MySQLConnection:
    settings = get_settings()
    return mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connection_timeout=5,
        autocommit=autocommit,
        raw=False,
    )


@contextmanager
def transaction() -> Iterator[mysql.connector.cursor.MySQLCursor]:
    """Transacción DML; rollback ante cualquier excepción."""
    connection = connect(autocommit=False)
    try:
        with connection.cursor(dictionary=True) as cursor:
            try:
                yield cursor
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connection.close()


@contextmanager
def read_only() -> Iterator[mysql.connector.cursor.MySQLCursor]:
    connection = connect(autocommit=True)
    try:
        with connection.cursor(dictionary=True) as cursor:
            yield cursor
    finally:
        connection.close()
