"""Ejecutor de migraciones SQL para Mnemosine.

Ejecutar desde backend: python -m scripts.migrate [--dry-run]

- Lee database/migrations/*.sql en orden alfabético (0001_…, 0002_…).
- Registra versión, archivo y checksum SHA-256 en la tabla schema_migrations.
- Se niega a aplicar una migración ya registrada cuyo contenido cambió.
- Se detiene ante el primer fallo. MySQL hace commit implícito en DDL:
  no se promete rollback transaccional de CREATE/ALTER TABLE.
- El bloqueo con GET_LOCK evita ejecuciones simultáneas.

Regla de los archivos .sql: comentarios de línea con '--' y una sentencia por
';' al final de línea. Sin ';' dentro de literales de texto. Sin procedimientos.
"""

import hashlib
import sys
from pathlib import Path

import mysql.connector
from pydantic import ValidationError

from app.core.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
LOCK_NAME = "mnemosine_migrate"

CREATE_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version VARCHAR(32) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  checksum CHAR(64) NOT NULL,
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""


def split_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    for raw_line in sql_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("--"):
            continue
        buffer.append(line)
        if line.rstrip().endswith(";"):
            statement = "\n".join(buffer).rstrip()
            if statement.endswith(";"):
                statement = statement[:-1]
            if ";" in statement:
                raise ValueError(f"';' interno inesperado: {statement[:80]!r}")
            statements.append(statement)
            buffer = []
    if buffer:
        raise ValueError(f"Migración sin terminar (falta ';'): {' '.join(buffer)[:120]!r}")
    return statements


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    try:
        settings = get_settings()
    except ValidationError:
        print("Configuración incompleta: revisa backend/.env.", file=sys.stderr)
        return 1

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No hay migraciones en {MIGRATIONS_DIR}.", file=sys.stderr)
        return 1

    try:
        connection = mysql.connector.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connection_timeout=5,
            autocommit=True,
        )
    except mysql.connector.Error as error:
        print(f"No se pudo conectar a MySQL (código {error.errno}).", file=sys.stderr)
        return 1

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 10)", (LOCK_NAME,))
            rows = cursor.fetchall()
            if not rows or rows[0][0] != 1:
                print("Otra ejecución de migraciones está en curso.", file=sys.stderr)
                return 1
            try:
                cursor.execute(CREATE_SCHEMA_MIGRATIONS)
                cursor.execute("SELECT version, checksum FROM schema_migrations")
                applied = dict(cursor.fetchall())

                pending: list[tuple[str, Path, str]] = []
                for path in files:
                    version = path.name.split("_", 1)[0]
                    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
                    if version in applied:
                        if applied[version] != checksum:
                            print(
                                f"ABORT: {path.name} cambió tras aplicarse. "
                                "Escribe una migración nueva en lugar de editarla.",
                                file=sys.stderr,
                            )
                            return 1
                        print(f"  ok (ya aplicada)  {path.name}")
                    else:
                        pending.append((version, path, checksum))

                if dry_run:
                    print(f"\nSimulación: {len(pending)} migración(es) pendiente(s).")
                    for version, path, _ in pending:
                        print(f"  pendiente         {path.name}")
                    return 0

                for version, path, checksum in pending:
                    print(f"  aplicando         {path.name}")
                    try:
                        statements = split_statements(path.read_text(encoding="utf-8"))
                    except ValueError as error:
                        print(f"ABORT: {error}", file=sys.stderr)
                        return 1
                    for statement in statements:
                        cursor.execute(statement)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, filename, checksum) VALUES (%s, %s, %s)",
                        (version, path.name, checksum),
                    )
                print(f"\nHecho: {len(pending)} migración(es) aplicada(s), {len(applied)} ya existía(n).")
                return 0
            finally:
                try:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
                    cursor.fetchall()
                except mysql.connector.Error:
                    pass
    except mysql.connector.Error as error:
        print(f"Error de MySQL (código {error.errno}): {error.msg}", file=sys.stderr)
        print("MySQL puede haber confirmado DDL antes del fallo; revisa el esquema antes de reintentar.", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
