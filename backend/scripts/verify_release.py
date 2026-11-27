"""Prueba la imagen de publicación con MySQL/volumen desechables y audio sintético.

Desde backend: python -m scripts.verify_release
Requiere haber construido la imagen mnemosine:publicacion. No usa la base local.
"""
import io
import secrets
import subprocess
import tempfile
import time
import uuid
import wave
from pathlib import Path

import httpx


def docker(*args, data=None, required=True):
    result = subprocess.run(["docker", *args], input=data, capture_output=True, text=True)
    if required and result.returncode:
        raise RuntimeError("Falló Docker: " + result.stderr[-1500:])
    return result.stdout.strip()


def wait_ready(url):
    for _ in range(90):
        try:
            if httpx.get(url + "/api/ready", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("La imagen no llegó a estar lista.")


def main():
    name = "mnemosine_release_" + uuid.uuid4().hex[:10]
    database, server, volume = name + "_db", name + "_app", name + "_audio"
    password, admin_password = secrets.token_hex(24), secrets.token_hex(16)
    created = {"network": False, "volume": False, "db": False, "app": False}
    try:
        with tempfile.TemporaryDirectory(prefix=name) as temporary:
            root = Path(temporary)
            (root / "db.env").write_text("\n".join([
                "MYSQL_DATABASE=mnemosine", "MYSQL_USER=mnemosine_app",
                "MYSQL_PASSWORD=" + password, "MYSQL_ROOT_PASSWORD=" + secrets.token_hex(24),
            ]), encoding="utf-8")
            (root / "app.env").write_text("\n".join([
                "DB_HOST=db", "DB_PORT=3306", "DB_NAME=mnemosine", "DB_USER=mnemosine_app",
                "DB_PASSWORD=" + password, "SECRET_KEY=" + secrets.token_hex(32),
                "STORAGE_ROOT=/data", "SESSION_COOKIE_SECURE=true", "GOOGLE_DRIVE_ENABLED=false",
                "RELEASE_TEST_PASSWORD=" + admin_password,
            ]), encoding="utf-8")
            docker("network", "create", name)
            created["network"] = True
            docker("volume", "create", volume)
            created["volume"] = True
            docker("run", "-d", "--name", database, "--network", name, "--network-alias", "db",
                   "--env-file", str(root / "db.env"), "mysql:8.4")
            created["db"] = True
            docker("run", "-d", "--name", server, "--network", name,
                   "--env-file", str(root / "app.env"), "-v", volume + ":/data",
                   "-p", "127.0.0.1::8080", "mnemosine:publicacion")
            created["app"] = True
            port = docker("port", server, "8080/tcp").rsplit(":", 1)[-1]
            url = "http://127.0.0.1:" + port
            wait_ready(url)
            print("OK: MySQL limpio, migraciones y servidor de producción.", flush=True)
            docker("exec", "-i", "--user", "10001:10001", server, "python", "-", data="""
import os
from pathlib import Path
from app.repositories import db
from app.security.passwords import hash_password
assert not Path('.env').exists() and not Path('.secrets').exists()
assert 'Uid:\\t10001' in Path('/proc/1/status').read_text()
with db.transaction() as cursor:
    cursor.execute("INSERT INTO USER_ACCOUNT(username,email,password_hash,role) VALUES (%s,%s,%s,'ADMIN')",
                   ('release_test','release@example.test',hash_password(os.environ['RELEASE_TEST_PASSWORD'])))
"""
            )
            print("OK: proceso sin privilegios y sin secretos locales en la imagen.", flush=True)
            with httpx.Client(base_url=url, timeout=30) as web:
                assert web.get("/conexiones", headers={"Accept": "text/html"}).status_code == 200
                for path in ("/.env", "/.git/config", "/api/inexistente", "/assets/missing.js"):
                    assert web.get(path, headers={"Accept": "text/html"}).status_code == 404
                assert web.get("/api/library").status_code == 401
                response = web.post("/api/auth/login", json={"identity": "release_test", "password": admin_password})
                assert response.status_code == 200
                assert all("secure" in value.lower() for value in response.headers.get_list("set-cookie"))
                # Este transporte local es HTTP. En producción el navegador usa HTTPS;
                # para esta prueba reenviamos explícitamente las cookies Secure.
                web.headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in response.cookies.items())
                web.headers["X-CSRF-Token"] = response.cookies["mnemosine_csrf"]
                audio = io.BytesIO()
                with wave.open(audio, "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(8000)
                    output.writeframes(b"\0\0" * 16000)
                payload = audio.getvalue()
                result = web.post("/api/tracks/upload", files={"file": ("publicacion.wav", payload, "audio/wav")})
                assert result.status_code == 201, "Carga devolvió " + str(result.status_code)
                track = result.json()["track_id"]
                assert web.get(f"/api/tracks/{track}/download").content == payload
                partial = web.get(f"/api/tracks/{track}/audio", headers={"Range": "bytes=10-29"})
                assert partial.status_code == 206 and partial.content == payload[10:30]
                print("OK: acceso, cookies Secure, subida y descarga íntegra con rangos.", flush=True)
                docker("restart", server)
                # Docker Desktop puede reasignar un puerto aleatorio al reiniciar.
                port = docker("port", server, "8080/tcp").rsplit(":", 1)[-1]
                url = "http://127.0.0.1:" + port
                web.base_url = url
                wait_ready(url)
                assert web.get(f"/api/tracks/{track}/download").content == payload
                print("OK: audio y sesión conservados después de reiniciar.", flush=True)
        return 0
    finally:
        if created["app"]:
            docker("rm", "-f", "-v", server, required=False)
        if created["db"]:
            docker("rm", "-f", "-v", database, required=False)
        if created["volume"]:
            docker("volume", "rm", volume, required=False)
        if created["network"]:
            docker("network", "rm", name, required=False)
        print("Recursos temporales de publicación retirados; base y audio locales intactos.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
