"""Respaldo de Mnemosine: base de datos + audio (RNF-09, sección 10 del SRS).

Uso desde backend:  python -m scripts.backup [directorio_destino]

Crea <dest>/<YYYYMMDD-HHMMSS>/ con:
- mnemosine-db.sql   (mysqldump --single-transaction --hex-blob)
- storage/           (copia de <repo>/storage sin .tmp_uncommitted)
- manifest.json      (fecha, conteos por tabla, archivos y bytes de audio, sha256 del .sql)

Nota: el manifiesto permite verificar después la restauración (--verify).
El respaldo incluye el audio: un respaldo solo de metadatos no supera la prueba.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def docker_compose(*args: str) -> str:
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    from app.core.config import get_settings

    settings = get_settings()
    db_name = settings.db_name
    container = docker_compose("ps", "-q", "db")
    if not container:
        print("No se encontró el contenedor de MySQL (docker compose ps -q db).", file=sys.stderr)
        return 1

    if len(sys.argv) > 1:
        dest_root = Path(sys.argv[1]).expanduser().resolve()
    else:
        dest_root = ROOT / "backups"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = dest_root / stamp
    dest.mkdir(parents=True, exist_ok=False)

    sql_path = dest / "mnemosine-db.sql"
    print(f"Exportando {db_name} desde {container}…")
    with sql_path.open("wb") as handle:
        result = subprocess.run(
            ["docker", "exec", container, "sh", "-c",
             f'mysqldump --single-transaction --hex-blob --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" "{db_name}"'],
            stdout=handle,
            stderr=subprocess.PIPE,
        )
    if result.returncode != 0:
        print(f"mysqldump falló: {result.stderr.decode('utf-8', 'ignore')}", file=sys.stderr)
        return 1

    tables_out = subprocess.run(
        ["docker", "exec", container, "sh", "-c",
         f'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT table_name FROM information_schema.tables WHERE table_schema = \'{db_name}\'"'],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    table_counts = {}
    for table in tables_out:
        out = subprocess.run(
            ["docker", "exec", container, "sh", "-c",
             f'mysql -N -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT COUNT(*) FROM {db_name}.{table}"'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        table_counts[table] = int(out)

    storage_src = ROOT / "storage"
    storage_dest = dest / "storage"
    copied_files = 0
    copied_bytes = 0
    if storage_src.is_dir():
        def ignore_func(directory, names):
            return {name for name in names if name == ".tmp_uncommitted"}
        shutil.copytree(storage_src, storage_dest, ignore=ignore_func)
        for path in storage_dest.rglob("*"):
            if path.is_file():
                copied_files += 1
                copied_bytes += path.stat().st_size
        print(f"Audio copiado: {copied_files} archivo(s), {copied_bytes} bytes")
    else:
        print("Aviso: no hay directorio storage/; el respaldo contiene solo metadatos.")

    sql_bytes = sql_path.stat().st_size
    sql_sha = hashlib.sha256(sql_path.read_bytes()).hexdigest()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": db_name,
        "sql_file": sql_path.name,
        "sql_bytes": sql_bytes,
        "sql_sha256": sql_sha,
        "tables": table_counts,
        "storage": {"files": copied_files, "bytes": copied_bytes},
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nRespaldo creado en {dest}")
    print(f"Tablas: {len(table_counts)} · sql: {sql_bytes} bytes · sha256: {sql_sha[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
