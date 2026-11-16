"""Ejecutar desde backend: python -m scripts.check_db."""
import sys

import mysql.connector
from pydantic import ValidationError

from app.core.config import get_settings

EXPECTED_TABLES = [
    "schema_migrations",
    "USER_ACCOUNT",
    "USER_SESSION",
    "INVITATION",
    "DEVICE",
    "SOURCE",
    "SCAN_JOB",
    "ARTIST",
    "ALBUM",
    "TRACK",
    "TRACK_ARTIST",
    "ALBUM_ARTIST",
    "TRACK_LOCATION",
    "TRACK_SHARE",
    "PERMISSION_AUDIT",
    "PLAYLIST",
    "PLAYLIST_TRACK",
    "FILE_OPERATION",
]


def main() -> int:
    try:
        settings = get_settings()
    except ValidationError:
        print("Configuración incompleta: revisa backend/.env.", file=sys.stderr)
        return 1

    try:
        with mysql.connector.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connection_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                    (settings.db_name,),
                )
                existing = {row[0] for row in cursor.fetchall()}
    except mysql.connector.Error as error:
        print(f"No se pudo comprobar MySQL (código {error.errno}). Revisa servicio y configuración.", file=sys.stderr)
        return 1

    missing = [table for table in EXPECTED_TABLES if table not in existing]
    if missing:
        print("Conexión correcta, pero faltan tablas:", ", ".join(missing), file=sys.stderr)
        print("Aplica las migraciones con: python -m scripts.migrate", file=sys.stderr)
        return 1

    print(f"Conexión a MySQL correcta; {len(EXPECTED_TABLES)} tablas presentes y cuentas, sesiones y permisos listos para H2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
