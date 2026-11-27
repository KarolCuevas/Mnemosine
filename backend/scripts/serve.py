"""Arranque del contenedor: volumen, conexión SQL, migraciones y servidor único."""
import os
import sys
import tempfile
import time
from pathlib import Path

import mysql.connector
import uvicorn

from app.core.config import get_settings
from app.repositories import db
from scripts.migrate import main as migrate


def main():
    settings = get_settings()
    if len(settings.secret_key) < 32 or settings.secret_key.startswith("CAMBIAR"):
        raise RuntimeError("Configura una clave de sesión nueva en el servicio.")
    if not settings.db_password or settings.db_password.startswith("CAMBIAR"):
        raise RuntimeError("Configura el acceso a MySQL en el servicio.")
    if not settings.storage_root or not Path(settings.storage_root).is_absolute():
        raise RuntimeError("Configura una ruta absoluta de almacenamiento persistente.")
    storage = Path(settings.storage_root).resolve()
    if os.environ.get("RAILWAY_PROJECT_ID"):
        mounted = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
        if not mounted or storage != Path(mounted).resolve():
            raise RuntimeError("Conecta un volumen persistente a la ruta de STORAGE_ROOT antes de publicar.")
    os.umask(0o077)
    storage.mkdir(parents=True, exist_ok=True)
    # Railway monta los volúmenes como root. El proceso web pierde privilegios
    # después de preparar exclusivamente la raíz del volumen configurado.
    if os.environ.get("MNEMOSINE_DROP_PRIVILEGES") == "1" and hasattr(os, "geteuid") and os.geteuid() == 0:
        os.chown(storage, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    with tempfile.TemporaryFile(dir=storage):
        pass
    for attempt in range(20):
        try:
            connection = db.connect(autocommit=True)
            connection.close()
            break
        except mysql.connector.Error:
            if attempt == 19:
                raise RuntimeError("MySQL no está disponible; revisa la conexión privada del servicio.") from None
            print("Esperando a MySQL…", flush=True)
            time.sleep(3)
    if migrate() != 0:
        return 1
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise RuntimeError("Puerto del servicio no válido.")
    uvicorn.run("app.web:create_application", factory=True, host="0.0.0.0", port=port,
                proxy_headers=False, limit_concurrency=64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
