"""Ejecutar desde backend: python -m scripts.check_db."""
import sys

import mysql.connector
from pydantic import ValidationError

from app.core.config import get_settings


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
    except mysql.connector.Error as error:
        print(f"No se pudo comprobar MySQL (código {error.errno}). Revisa servicio y configuración.", file=sys.stderr)
        return 1
    print("Conexión a MySQL correcta. Las tablas del proyecto siguen pendientes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
