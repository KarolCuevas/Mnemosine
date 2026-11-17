"""Recorrido funcional completo (H3) contra una base de datos de prueba.

Crea `mnemosine_test`, migra, crea admin, invita a A y B, sube un WAV sintetizado
en memoria, y comprueba aislamiento, reproducción por rango, búsqueda y descarga.
Al terminar elimina la base de prueba y el árbol temporal de audio.

Uso desde backend: python -m scripts.verify_journey
"""

import io
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
STORAGE_TMP = tempfile.mkdtemp(prefix="mnemosine_test_storage_")

os.environ["DB_NAME"] = "mnemosine_test"
os.environ["STORAGE_ROOT"] = STORAGE_TMP

RESULTS: list[tuple[str, bool]] = []


def check(label: str, condition: bool) -> None:
    RESULTS.append((label, bool(condition)))
    print(f"  {'ok   ' if condition else 'FALLO'} {label}")


def docker_sql(sql: str) -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'],
        input=sql.encode("utf-8"),
        check=True,
        cwd=ROOT,
        capture_output=True,
    )


def make_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        frames = bytearray()
        for index in range(8000):  # 1 segundo de un tono de 440 Hz
            sample = int(0.3 * 32767 * math.sin(2 * math.pi * 440 * index / 8000))
            frames += struct.pack("<h", sample)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def main() -> int:
    wav_bytes = make_wav_bytes()
    print(f"WAV de prueba: {len(wav_bytes)} bytes")

    print("== Preparando base de datos de prueba ==")
    docker_sql(
        "DROP DATABASE IF EXISTS mnemosine_test; "
        "CREATE DATABASE mnemosine_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; "
        "GRANT ALL PRIVILEGES ON mnemosine_test.* TO 'mnemosine_app'@'%'; FLUSH PRIVILEGES;"
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.migrate"],
            cwd=BACKEND,
            check=True,
            env={**os.environ},
            capture_output=True,
        )

        from fastapi.testclient import TestClient

        from app.main import app
        from app.repositories import db as repos_db
        from app.security import passwords

        admin_password = "admin-demo-password-1"
        with repos_db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO USER_ACCOUNT (username, email, password_hash, role) "
                "VALUES (%s, %s, %s, 'ADMIN')",
                ("admin", "admin@example.test", passwords.hash_password(admin_password)),
            )

        admin = TestClient(app)
        admin.post("/api/auth/login", json={"identity": "admin", "password": admin_password})
        csrf_admin = admin.cookies.get("mnemosine_csrf")
        headers_admin = {"X-CSRF-Token": csrf_admin}
        invitation_a = admin.post("/api/admin/invitations", json={"expires_in_days": 7}, headers=headers_admin).json()["code"]
        invitation_b = admin.post("/api/admin/invitations", json={"expires_in_days": 7}, headers=headers_admin).json()["code"]

        a = TestClient(app)
        b = TestClient(app)
        a.post("/api/auth/register", json={"username": "usuario.a", "email": "a@example.test",
                                           "password": "cuenta-demo-123456", "invitation_code": invitation_a})
        b.post("/api/auth/register", json={"username": "usuario.b", "email": "b@example.test",
                                           "password": "cuenta-demo-123456", "invitation_code": invitation_b})
        csrf_a = a.cookies.get("mnemosine_csrf")
        headers_a = {"X-CSRF-Token": csrf_a}

        print("== Carga (datos reales + validación) ==")
        files = {"file": ("aurora.wav", wav_bytes, "audio/x-wav")}
        data = {"title": "Aurora", "artist": "Kältmare", "album": "Sol", "track_number": "1"}
        created = a.post("/api/tracks/upload", files=files, data=data, headers=headers_a)
        check("A sube un WAV válido → 201", created.status_code == 201)
        track_id = created.json().get("track_id") if created.status_code == 201 else -1
        check("visibilidad inicial PRIVATE", created.json().get("visibility") == "PRIVATE")
        check("duración detectada por mutagen (>= 1 s)", created.json().get("duration_seconds", 0) >= 1)

        fake = a.post(
            "/api/tracks/upload",
            files={"file": ("falso.mp3", b"esto no es un mp3", "audio/mpeg")},
            data={"title": "Falso", "artist": "X"},
            headers=headers_a,
        )
        check("un .mp3 que no es audio → 422", fake.status_code == 422)
        no_csrf = a.post(
            "/api/tracks/upload",
            files={"file": ("otro.wav", wav_bytes, "audio/x-wav")},
            data={"title": "Sin CSRF", "artist": "X"},
        )
        check("carga sin CSRF → 403", no_csrf.status_code == 403)

        print("== Biblioteca y búsqueda ==")
        lib_a = a.get("/api/library").json()
        check("A ve su copia en la biblioteca", lib_a["total"] == 1 and lib_a["items"][0]["title"] == "Aurora")
        check("B no ve ninguna copia de A", b.get("/api/library").json()["total"] == 0)
        check("búsqueda por título", a.get("/api/library", params={"q": "aurora"}).json()["total"] == 1)
        check("búsqueda por artista", a.get("/api/library", params={"q": "kältmare"}).json()["total"] == 1)
        check("búsqueda por álbum", a.get("/api/library", params={"q": "sol"}).json()["total"] == 1)
        check("búsqueda sin coincidencias", a.get("/api/library", params={"q": "zzz"}).json()["total"] == 0)

        print("== Detalle ==")
        detail = a.get(f"/api/tracks/{track_id}")
        check("A ve el detalle con su copia", detail.status_code == 200 and len(detail.json().get("copies", [])) == 1)
        check("B no puede ver el detalle de A → 404", b.get(f"/api/tracks/{track_id}").status_code == 404)

        print("== Reproducción y rangos ==")
        audio = a.get(f"/api/tracks/{track_id}/audio")
        check("A reproduce: 200 y bytes íntegros", audio.status_code == 200 and audio.content == wav_bytes)
        check("Accept-Ranges: bytes", audio.headers.get("accept-ranges") == "bytes")
        full_size = len(wav_bytes)
        part = a.get(f"/api/tracks/{track_id}/audio", headers={"Range": "bytes=0-99"})
        check("Range 0-99 → 206 y 100 bytes correctos",
              part.status_code == 206 and part.content == wav_bytes[:100]
              and part.headers.get("content-range") == f"bytes 0-99/{full_size}")
        tail = a.get(f"/api/tracks/{track_id}/audio", headers={"Range": "bytes=-50"})
        check("Range sufijo -50 → 206 con los últimos 50 bytes",
              tail.status_code == 206 and tail.content == wav_bytes[-50:])
        broken = a.get(f"/api/tracks/{track_id}/audio", headers={"Range": f"bytes={full_size + 10}-"})
        check("Range fuera de rango → 416", broken.status_code == 416 and broken.headers.get("content-range") == f"bytes */{full_size}")
        check("B no puede reproducir la copia de A → 404", b.get(f"/api/tracks/{track_id}/audio").status_code == 404)

        print("== Descarga ==")
        download = a.get(f"/api/tracks/{track_id}/download")
        disposition = download.headers.get("content-disposition", "")
        check("A descarga: bytes íntegros y adjunto",
              download.status_code == 200 and download.content == wav_bytes and "attachment" in disposition)
        check("B no puede descargar la copia de A → 404", b.get(f"/api/tracks/{track_id}/download").status_code == 404)

        print("== Dos usuarios, mismos bytes ==")
        same_bytes = b.post(
            "/api/tracks/upload",
            files={"file": ("mismos-bytes.wav", wav_bytes, "audio/x-wav")},
            data={"title": "Copia de B", "artist": "Kältmare", "album": "Sol"},
            headers={"X-CSRF-Token": b.cookies.get("mnemosine_csrf")},
        )
        check("B sube los mismos bytes → 201", same_bytes.status_code == 201)
        b_track = same_bytes.json().get("track_id") if same_bytes.status_code == 201 else -1
        check("B ve su copia en su biblioteca", b.get("/api/library").json()["total"] == 1)
        check("A ve solo la suya (no la copia de B)", a.get("/api/library").json()["total"] == 1)
        check("A no puede ver la copia de B → 404", a.get(f"/api/tracks/{b_track}").status_code == 404)
        check("B puede reproducir su copia → 200", b.get(f"/api/tracks/{b_track}/audio").status_code == 200)
        check("B puede descargar su copia → 200", b.get(f"/api/tracks/{b_track}/download").status_code == 200)
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT DISTINCT sha256 FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
                "WHERE t.track_id IN (%s, %s)",
                (track_id, b_track),
            )
            hashes = [row["sha256"] for row in cursor.fetchall()]
        check("ambos usuarios poseen copias con el mismo SHA-256", len(hashes) == 1 and hashes[0] == hashlib.sha256(wav_bytes).hexdigest())

        print("== Registro de operaciones ==")
        with repos_db.read_only() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM FILE_OPERATION WHERE type = 'UPLOAD' AND result = 'SUCCESS'")
            uploads_n = cursor.fetchone()["n"]
            cursor.execute("SELECT COUNT(*) AS n FROM FILE_OPERATION WHERE type = 'DOWNLOAD' AND result = 'SUCCESS'")
            downloads_n = cursor.fetchone()["n"]
        check("la subida quedó registrada en FILE_OPERATION", uploads_n >= 1)
        check("la descarga quedó registrada en FILE_OPERATION", downloads_n >= 1)
    finally:
        docker_sql("DROP DATABASE IF EXISTS mnemosine_test;")
        shutil.rmtree(STORAGE_TMP, ignore_errors=True)

    failures = sum(1 for _, ok in RESULTS if not ok)
    print()
    if failures:
        print(f"Recorrido H3: {failures} fallo(s) de {len(RESULTS)} comprobaciones.", file=sys.stderr)
        return 1
    print(f"Recorrido H3: {len(RESULTS)} comprobaciones correctas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
