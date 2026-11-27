"""Prueba real de carga/etiquetas/portadas en una BD y almacenamiento temporales.

Desde backend: python -m scripts.verify_media
Requiere FFmpeg en PATH o MEDIA_TEST_FFMPEG (solo herramienta de pruebas).
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
DATABASE = "mnemosine_media_test"
RESULTS = []


def check(label, condition):
    RESULTS.append(bool(condition))
    print(f"  {'ok' if condition else 'FALLO'} {label}")
    if not condition:
        raise AssertionError(label)


def docker_sql(sql):
    subprocess.run(["docker", "compose", "exec", "-T", "db", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'],
                   input=sql.encode(), check=True, cwd=ROOT, capture_output=True)


def main():
    ffmpeg = os.environ.get("MEDIA_TEST_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg or not Path(ffmpeg).is_file():
        print("Configura MEDIA_TEST_FFMPEG o instala FFmpeg para generar los cinco formatos.", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="mnemosine_media_") as temporary:
        root = Path(temporary).resolve()
        assert root.parent == Path(tempfile.gettempdir()).resolve()
        storage = root / "storage"
        fixture_dir = root / "fixtures"
        fixture_dir.mkdir()
        os.environ["DB_NAME"] = DATABASE
        os.environ["STORAGE_ROOT"] = str(storage)
        from scripts.media_test_fixtures import ALBUM, ARTISTS, TITLE, add_tags, make_all_formats
        from PIL import Image
        fixtures = make_all_formats(fixture_dir, ffmpeg)
        print("== Preparando base aislada y cinco formatos sintéticos ==")
        docker_sql(f"DROP DATABASE IF EXISTS {DATABASE}; CREATE DATABASE {DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; "
                   f"GRANT ALL PRIVILEGES ON {DATABASE}.* TO 'mnemosine_app'@'%'; FLUSH PRIVILEGES;")
        try:
            subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=ROOT / "backend", check=True, capture_output=True)
            from fastapi.testclient import TestClient
            from app.main import app
            from app.repositories import db
            from app.security.passwords import hash_password
            from app.services import uploads

            secret = "synthetic-media-password-2026"
            password_hash = hash_password(secret)
            ids = {}
            with db.transaction() as cursor:
                for name, role in [("media_a", "USER"), ("media_b", "USER"), ("media_admin", "ADMIN")]:
                    cursor.execute("INSERT INTO USER_ACCOUNT (username,email,password_hash,role) VALUES (%s,%s,%s,%s)", (name, f"{name}@example.test", password_hash, role))
                    ids[name] = cursor.lastrowid

            def client(name):
                session = TestClient(app)
                response = session.post("/api/auth/login", json={"identity": name, "password": secret})
                check(f"sesión {name}", response.status_code == 200)
                return session, {"X-CSRF-Token": session.cookies.get("mnemosine_csrf")}

            a, headers = client("media_a")
            b, _ = client("media_b")
            admin, admin_headers = client("media_admin")
            anonymous = TestClient(app)
            created = []
            for extension, path in fixtures.items():
                original = path.read_bytes()
                response = a.post("/api/tracks/upload", files={"file": (path.name, original)}, headers=headers)
                check(f"{extension}: subir sin completar formulario → 201", response.status_code == 201)
                item = response.json()
                created.append(item)
                check(f"{extension}: etiquetas completas", item["title"] == TITLE and item["artist"] == ", ".join(ARTISTS)
                      and item["album"] == ALBUM and item["album_artist"] == "Ensamble de prueba" and item["genre"] == "Ambient"
                      and (item["track_number"], item["disc_number"], item["release_year"]) == (3, 2, 2021))
                cover_url = item["cover_url"]
                cover = a.get(cover_url)
                check(f"{extension}: portada JPEG privada", cover.status_code == 200 and cover.headers["content-type"] == "image/jpeg"
                      and cover.headers["cache-control"] == "private, no-store" and len(cover.content) <= 512 * 1024)
                with Image.open(io.BytesIO(cover.content)) as image:
                    check(f"{extension}: portada legible", image.format == "JPEG" and max(image.size) <= 800)
                detail = a.get(f"/api/tracks/{item['track_id']}").json()
                check(f"{extension}: detalle conserva etiquetas y portada", detail["genre"] == "Ambient" and detail["cover_url"] == cover_url
                      and detail["release_year"] == 2021 and detail["artists"] == ", ".join(ARTISTS))
                check(f"{extension}: audio original intacto", a.get(f"/api/tracks/{item['track_id']}/download").content == original
                      and item["sha256"] == hashlib.sha256(original).hexdigest())
                check(f"{extension}: portada aislada de B, admin y anónimo", b.get(cover_url).status_code == 404
                      and admin.get(cover_url).status_code == 404 and anonymous.get(cover_url).status_code == 401)

            first = created[0]
            check("biblioteca incluye URLs, no bytes de imágenes", all(item["cover_url"] for item in a.get("/api/library").json()["items"]))
            payload = {"username": "media_b", "can_stream": False, "can_download": True, "declaration": "Audio sintético autorizado para la prueba"}
            share = a.post(f"/api/locations/{first['location_id']}/shares", json=payload, headers=headers)
            check("share de descarga permite ver portada", share.status_code in (200, 201) and b.get(first["cover_url"]).status_code == 200)
            check("compartidas conserva portada", b.get("/api/library/shared").json()["items"][0]["cover_url"] == first["cover_url"])
            a.delete(f"/api/locations/{first['location_id']}/shares/{ids['media_b']}", headers=headers)
            check("revocar share revoca portada inmediatamente", b.get(first["cover_url"]).status_code == 404)
            a.post(f"/api/locations/{first['location_id']}/visibility", json={"publish": True, "declaration": "Audio sintético autorizado"}, headers=headers)
            check("portada pública solo para autenticados", b.get(first["cover_url"]).status_code == 200 and anonymous.get(first["cover_url"]).status_code == 401)
            check("catálogo público incluye portada", b.get("/api/discovery/media_a").json()["items"][0]["cover_url"] == first["cover_url"])
            a.post(f"/api/locations/{first['location_id']}/visibility", json={"publish": False}, headers=headers)
            check("volver a privada oculta portada", b.get(first["cover_url"]).status_code == 404)

            playlist = a.post("/api/playlists", json={"name": "Con portadas"}, headers=headers).json()
            a.post(f"/api/playlists/{playlist['playlist_id']}/tracks", json={"track_id": first["track_id"]}, headers=headers)
            check("lista conserva portada para el reproductor", a.get(f"/api/playlists/{playlist['playlist_id']}").json()["tracks"][0]["cover_url"] == first["cover_url"])

            manual = {"title": "Título corregido", "artist": "Mi artista", "album": "Mi álbum", "genre": "Jazz", "album_artist": "Mi ensamble", "track_number": "300", "disc_number": "3", "release_year": "2025"}
            edited = a.post("/api/tracks/upload", files={"file": ("editado.flac", fixtures["flac"].read_bytes())}, data=manual, headers=headers)
            check("correcciones manuales prevalecen, pista >255 y portada conservada", edited.status_code == 201
                  and all(str(edited.json()[key]) == value for key, value in manual.items()) and bool(edited.json()["cover_url"]))

            no_tags = fixture_dir / "sin-etiquetas.wav"
            unknown = a.post("/api/tracks/upload", files={"file": (no_tags.name, no_tags.read_bytes())}, headers=headers)
            check("sin etiquetas: nombre de archivo y artista desconocido", unknown.status_code == 201
                  and unknown.json()["title"] == "sin-etiquetas" and unknown.json()["artist"] == "Artista desconocido" and unknown.json()["cover_url"] is None)

            damaged_cover = fixture_dir / "portada-danada.flac"
            damaged_cover.write_bytes(fixtures["flac"].read_bytes())
            add_tags(damaged_cover, cover=b"not an image")
            invalid = a.post("/api/tracks/upload", files={"file": (damaged_cover.name, damaged_cover.read_bytes())}, headers=headers)
            check("portada dañada no pierde audio ni etiquetas", invalid.status_code == 201 and invalid.json()["title"] == TITLE
                  and invalid.json()["cover_url"] is None and len(invalid.json()["warnings"]) == 1)
            check("audio falso sigue rechazado", a.post("/api/tracks/upload", files={"file": ("fake.flac", b"fake audio")}, headers=headers).status_code == 422)
            check("subida sin CSRF rechazada", a.post("/api/tracks/upload", files={"file": (no_tags.name, no_tags.read_bytes())}).status_code == 403)
            check("pista fuera de rango rechazada", a.post("/api/tracks/upload", files={"file": (no_tags.name, no_tags.read_bytes())}, data={"track_number": "1001"}, headers=headers).status_code == 422)

            before = a.get("/api/library").json()["total"]
            before_files = {path.relative_to(storage) for path in storage.rglob("*") if path.is_file()}
            with patch("app.services.uploads.save_metadata", side_effect=RuntimeError("synthetic failure")):
                try:
                    uploads.upload_track(user_id=ids["media_a"], original_filename="fallo.flac", content=fixtures["flac"].read_bytes())
                    raise AssertionError("No se produjo el fallo simulado")
                except RuntimeError:
                    pass
            check("fallo de metadatos revierte catálogo y temporales", a.get("/api/library").json()["total"] == before
                  and {path.relative_to(storage) for path in storage.rglob("*") if path.is_file()} == before_files)
            admin.post(f"/api/admin/users/{ids['media_a']}/deactivate", headers=admin_headers)
            check("desactivar propietario corta la portada", a.get(first["cover_url"]).status_code == 401 and b.get(first["cover_url"]).status_code == 404)
            print(f"\n{sum(RESULTS)}/{len(RESULTS)} verificaciones correctas")
            return 0
        finally:
            docker_sql(f"DROP DATABASE IF EXISTS {DATABASE};")
            print("Base y archivos temporales de la prueba eliminados.")


if __name__ == "__main__":
    raise SystemExit(main())
