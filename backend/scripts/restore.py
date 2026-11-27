"""Restauración de un respaldo de Mnemosine.

Uso desde backend:  python -m scripts.restore <directorio_respaldo> [--db-name NOMBRE] [--storage-dir DIR]

Por defecto restaura en una base NUEVA (`mnemosine_restore`) y en un directorio
temporal, SIN tocar la base `mnemosine` ni storage/ reales. Sirve para validar
respaldos (prueba del SRS §10). Para restaurar de verdad sobre `mnemosine`:

    python -m scripts.restore <respaldo> --db-name mnemosine --storage-dir <repo>/storage --yes

Comprueba el sha256 del dump y los conteos de filas de cada tabla contra el
manifiesto; imprime «RESTAURACIÓN VERIFICADA» o avisa de discrepancias.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def quarantine_sql(database: str, tables) -> str:
    """No reactivar grants ni trabajos a partir de un respaldo. No llama a Google."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("Nombre de base inválido")
    statements = []
    if "INTEGRATION_CONNECTION" in tables:
        statements.append(f"UPDATE {database}.INTEGRATION_CONNECTION SET credentials_ciphertext=NULL,expires_at=NULL,"
                          "status=CASE WHEN status='DISCONNECTED' THEN 'DISCONNECTED' ELSE 'REAUTH_REQUIRED' END,"
                          "generation=generation+1")
    if "OAUTH_AUTHORIZATION" in tables:
        statements.append(f"DELETE FROM {database}.OAUTH_AUTHORIZATION")
    if "TRANSFER_JOB" in tables:
        statements.append(f"UPDATE {database}.TRANSFER_JOB SET status='CANCELLED',reserved_bytes=0,lease_token=NULL,lease_expires_at=NULL "
                          "WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED')")
    return "; ".join(statements)


def docker_compose(*args: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def container_exec(container: str, sql_command: str) -> str:
    result = subprocess.run(
        ["docker", "exec", container, "sh", "-c",
         f'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "{sql_command}"'],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("--db-name", default="mnemosine_restore")
    parser.add_argument("--storage-dir", type=Path, default=None)
    parser.add_argument("--yes", action="store_true",
                        help="Requerido para sobrescribir --db-name=mnemosine")
    args = parser.parse_args()

    backup = args.backup_dir.resolve()
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        print(f"No existe el manifiesto: {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sql_path = backup / manifest["sql_file"]
    sql_sha = hashlib.sha256(sql_path.read_bytes()).hexdigest()
    if sql_sha != manifest.get("sql_sha256"):
        print("FALLO: el sha256 del dump no coincide con el manifiesto (respaldo corrupto).", file=sys.stderr)
        return 1
    print(f"Dump verificado: sha256 {sql_sha[:16]}…")

    target_db = args.db_name
    if not re.fullmatch(r"[A-Za-z0-9_]+", target_db) or any(not re.fullmatch(r"[A-Za-z0-9_]+", table) for table in manifest["tables"]):
        print("Nombre de base o tabla inválido.", file=sys.stderr)
        return 1
    if target_db == "mnemosine" and not args.yes:
        print("Restaurar sobre 'mnemosine' destruirá la base actual. Repite con --yes.", file=sys.stderr)
        return 1

    container = docker_compose("ps", "-q", "db")
    if not container:
        print("No se encontró el contenedor de MySQL.", file=sys.stderr)
        return 1

    print(f"Restaurando base {target_db}…")
    with sql_path.open("rb") as handle:
        subprocess.run(
            ["docker", "exec", "-i", container, "sh", "-c",
             f'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS {target_db}; CREATE DATABASE {target_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"'],
            check=True,
        )
        subprocess.run(
            ["docker", "exec", "-i", container, "sh", "-c",
             f'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" {target_db}'],
            stdin=handle,
            check=True,
        )

    mismatches = []
    for table, expected in manifest["tables"].items():
        out = container_exec(container, f"SELECT COUNT(*) FROM {target_db}.{table}")
        try:
            actual = int(out)
        except ValueError:
            actual = -1
        status = "ok" if actual == expected else "DIFIERE"
        if actual != expected:
            mismatches.append(table)
        print(f"  {status}  {table}: {actual} (manifiesto {expected})")

    # Comparar el respaldo antes de invalidar intencionalmente estados transitorios.
    quarantine = quarantine_sql(target_db, manifest["tables"])
    if quarantine:
        container_exec(container, quarantine)
        print("  Conexiones requieren autorización nueva; trabajos pendientes cancelados.")

    storage_target = args.storage_dir
    if storage_target is None:
        temp_root = Path(tempfile.mkdtemp(prefix="mnemosine_restore_"))
        storage_target = temp_root / "storage"
    if (backup / "storage").is_dir():
        if storage_target.exists():
            shutil.rmtree(storage_target)
        shutil.copytree(backup / "storage", storage_target)
        restored = sum(1 for p in storage_target.rglob("*") if p.is_file())
        expected_files = manifest["storage"]["files"]
        status = "ok" if restored == expected_files else "DIFIERE"
        print(f"  {status}  audio: {restored} archivo(s) (manifiesto {expected_files}) en {storage_target}")
        if restored != expected_files:
            mismatches.append("storage")
    else:
        print("  (respaldo sin carpeta storage/; solo metadatos)")

    print()
    if mismatches:
        print(f"RESTAURACIÓN CON DIFERENCIAS en: {', '.join(mismatches)}", file=sys.stderr)
        return 1
    print("RESTAURACIÓN VERIFICADA: conteos y audio coinciden con el manifiesto.")
    if target_db == "mnemosine_restore":
        print("(Base de verificación creada; puedes borrarla con: docker exec … mysql -e 'DROP DATABASE mnemosine_restore')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
