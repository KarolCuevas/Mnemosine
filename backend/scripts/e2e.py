"""E2E con Playwright (D11) contra un entorno temporal completamente aislado.

Crea `mnemosine_e2e`, la migra, siembra una cuenta `e2e_admin`, levanta una
API en :8010 y Vite en :5174 (proxy /api → :8010), ejecuta Playwright y, al
terminar (pase o falle), detiene ambos procesos y borra la base de datos.

Uso desde backend: python -m scripts.e2e
(Requiere Docker Desktop en marcha; la base `mnemosine` NO se toca.)
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
os.environ["DB_NAME"] = "mnemosine_e2e"

E2E_IDENTITY = "e2e_admin"
E2E_PASSWORD = "e2e-demo-password-2026!"


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def wait_http(url: str, timeout: float, expect_ok: bool = True) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if expect_ok and response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def stop_process(proc):
    if proc is None:
        return
    # The Windows venv launcher can spawn a child Python process. Stop only this
    # test's process tree before removing its temporary audio/database.
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    proc.wait(timeout=10)


def run(temporary: Path) -> int:
    os.environ["STORAGE_ROOT"] = str(temporary / "storage")
    from scripts.media_test_fixtures import make_tagged_wav
    fixture = temporary / "nombre-distinto.wav"
    make_tagged_wav(fixture)
    try:
        return run_servers(fixture)
    finally:
        docker(
            "compose", "exec", "-T", "db", "sh", "-c",
            'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" '
            '-e "DROP DATABASE IF EXISTS mnemosine_e2e"'
        )


def run_servers(fixture: Path) -> int:
    print("== Preparando base mnemosine_e2e ==")
    result = docker(
        "compose", "exec", "-T", "db", "sh", "-c",
        'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" '
        '-e "DROP DATABASE IF EXISTS mnemosine_e2e; '
        'CREATE DATABASE mnemosine_e2e CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; '
        "GRANT ALL PRIVILEGES ON mnemosine_e2e.* TO 'mnemosine_app'@'%'; FLUSH PRIVILEGES;\""
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        return 1

    subprocess.run([sys.executable, "-m", "scripts.migrate"],
                   cwd=BACKEND, check=True, env={**os.environ}, capture_output=True)

    from app.repositories import db as repos_db
    from app.security import passwords
    with repos_db.transaction() as cursor:
        cursor.execute("SELECT user_id FROM USER_ACCOUNT WHERE username = %s", (E2E_IDENTITY,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO USER_ACCOUNT (username, email, password_hash, role) "
                "VALUES (%s, %s, %s, 'ADMIN')",
                (E2E_IDENTITY, "e2e-admin@example.test", passwords.hash_password(E2E_PASSWORD)),
            )

    api_env = {**os.environ, "DB_NAME": "mnemosine_e2e"}
    print("== Levantando API en :8010 ==")
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8010"],
        cwd=BACKEND, env=api_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    vite = None
    exit_code = 1
    try:
        vite = subprocess.Popen(
            ["node", str(FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"), "--host", "127.0.0.1", "--port", "5174", "--strictPort"],
            cwd=FRONTEND, env={**os.environ, "VITE_API_TARGET": "http://127.0.0.1:8010"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if not wait_http("http://127.0.0.1:8010/api/health", 30):
            print("La API no arrancó en :8010", file=sys.stderr)
            return 1
        if not wait_http("http://127.0.0.1:5174/", 30):
            print("Vite no arrancó en :5174", file=sys.stderr)
            return 1

        print("== Ejecutando Playwright ==")
        result = subprocess.run(["npx.cmd", "playwright", "test"], cwd=FRONTEND,
                                env={**os.environ, "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:5174",
                                     "E2E_IDENTITY": E2E_IDENTITY, "E2E_PASSWORD": E2E_PASSWORD,
                                     "E2E_MEDIA_FIXTURE": str(fixture)})
        exit_code = result.returncode
    finally:
        print("== Limpiando ==")
        for proc in (vite, api):
            try:
                stop_process(proc)
            except Exception:
                pass
    return exit_code


def main() -> int:
    # Never silently run the suite against a leftover server from another run.
    for port in (8010, 5174):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                print(f"El puerto de pruebas {port} está ocupado; libera ese entorno antes de continuar.", file=sys.stderr)
                return 1
    with tempfile.TemporaryDirectory(prefix="mnemosine_e2e_") as temporary:
        return run(Path(temporary))


if __name__ == "__main__":
    raise SystemExit(main())
