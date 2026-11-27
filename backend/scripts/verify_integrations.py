"""I0/I1/I5: MySQL real en base única y audio temporal. Sin llamadas externas.

Desde backend: python -m scripts.verify_integrations
Requiere Docker Desktop. No altera mnemosine ni bases de otras suites.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
RID = "11111111-1111-4111-8111-111111111111"
RID2 = "22222222-2222-4222-8222-222222222222"
checks = 0


def check(label, condition):
    global checks
    if not condition:
        raise AssertionError(label)
    checks += 1
    print(f"  OK {label}")


def docker_sql(sql):
    subprocess.run(["docker", "compose", "exec", "-T", "db", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'],
                   input=sql.encode(), cwd=ROOT, check=True, capture_output=True)


def main():
    name = "mnemosine_integrations_" + uuid.uuid4().hex[:12]
    os.environ["DB_NAME"] = name
    os.environ["MUSICBRAINZ_ENABLED"] = "true"
    os.environ["MUSICBRAINZ_CONTACT"] = "test@example.test"
    docker_sql(f"CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL ON {name}.* TO 'mnemosine_app'@'%';")
    try:
        with tempfile.TemporaryDirectory(prefix="mnemosine_integrations_") as audio_dir:
            os.environ["STORAGE_ROOT"] = audio_dir
            run_checks()
        print(f"\n{checks} comprobaciones correctas. Base y audio de prueba eliminados.")
        return 0
    finally:
        docker_sql(f"DROP DATABASE {name};")


def run_checks():
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    from app.main import app
    from app.repositories import db
    from app.security.passwords import hash_password
    from app.integrations.catalog.providers.musicbrainz import MusicBrainzAdapter
    from app.integrations.catalog.contract import CatalogError
    from app.integrations.catalog.traffic import provider_slot
    from app.services import copies, storage, storage_sources, uploads
    from app.storage.contract import StorageAdapter, StorageCapabilities, ObjectInfo, ObjectPage, ObjectState, UnsupportedOperationError
    from scripts.migrate import CREATE_SCHEMA_MIGRATIONS, MIGRATIONS_DIR, split_statements

    # Partir del esquema anterior y probar que las extensiones conservan la ruta local.
    with db.connect(autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_SCHEMA_MIGRATIONS)
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name[:4] > "0013":
                    continue
                for statement in split_statements(path.read_text(encoding="utf-8")):
                    cursor.execute(statement)
                cursor.execute("INSERT INTO schema_migrations (version, filename, checksum) VALUES (%s,%s,%s)",
                               (path.name[:4], path.name, hashlib.sha256(path.read_bytes()).hexdigest()))
            cursor.execute("INSERT INTO USER_ACCOUNT (username,email,password_hash) VALUES ('old','old@example.test','unused')")
            old_user = cursor.lastrowid
            cursor.execute("INSERT INTO TRACK (title) VALUES ('Archivo anterior')")
            old_track = cursor.lastrowid
            cursor.execute("INSERT INTO TRACK_LOCATION (track_id,owner_user_id,source_id,relative_path,sha256,size_bytes,mime_type) VALUES (%s,%s,9001,'audio/sub/kept.wav',%s,10,'audio/wav')",
                           (old_track, old_user, "a" * 64))
    for _ in range(2):
        result = subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=BACKEND, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    check("migraciones nuevas e idempotencia", "0 migración(es) aplicada(s)" in result.stdout)
    with db.read_only() as cursor:
        cursor.execute("SELECT relative_path, sha256, owner_user_id, visibility FROM TRACK_LOCATION WHERE track_id = %s", (old_track,))
        row = cursor.fetchone()
        check("ruta/hash/dueño/privacidad anteriores intactos", row == {"relative_path": "audio/sub/kept.wav", "sha256": "a" * 64, "owner_user_id": old_user, "visibility": "PRIVATE"})

    clients, user_ids = {}, {}
    for username, role in [("a", "USER"), ("b", "USER"), ("admin", "ADMIN")]:
        with db.transaction() as cursor:
            cursor.execute("INSERT INTO USER_ACCOUNT (username,email,password_hash,role) VALUES (%s,%s,%s,%s)",
                           (username, f"{username}@example.test", hash_password("test-password-2026!"), role))
            user_ids[username] = cursor.lastrowid
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"identity": username, "password": "test-password-2026!"})
        check(f"sesión {username}", response.status_code == 200)
        client.headers["X-CSRF-Token"] = client.cookies.get("mnemosine_csrf")
        clients[username] = client
    a, b, admin = clients["a"], clients["b"], clients["admin"]
    check("catálogo requiere sesión", TestClient(app).get("/api/catalog/recordings").status_code == 401)

    raw = {"id": RID, "title": 'Nombre & "especial"', "length": 120000, "score": 100,
           "tags": [{"name": "NO_INDEXAR"}], "annotation": "NO_INDEXAR", "isrcs": ["USAAA2600001"],
           "artist-credit": [{"name": "Ártista", "artist": {"id": "33333333-3333-4333-8333-333333333333", "name": "Ártista"}}],
           "releases": [{"id": "44444444-4444-4444-8444-444444444444", "title": "Edición A"},
                        {"id": "55555555-5555-4555-8555-555555555555", "title": "Edición B"}]}
    def fake_request(self, path, params):
        return {"recordings": [raw, {**raw, "id": RID2, "disambiguation": "live"}], "count": 40} if path == "/recording" else {**raw, "id": path.rsplit("/", 1)[1]}
    with patch.object(MusicBrainzAdapter, "_request", autospec=True, side_effect=fake_request) as remote:
        searched = a.get("/api/external/musicbrainz/search", params={"title": raw["title"]})
        check("búsqueda proveedor", searched.status_code == 200)
        check("MBID distintos conservados", len({r["provider_id"] for r in searched.json()["items"]}) == 2)
        check("normalización de ediciones", len(searched.json()["items"][0]["releases"]) == 2)
        second = b.get("/api/external/musicbrainz/search", params={"title": raw["title"]})
        check("caché pública compartida sin llamadas repetidas", remote.call_count == 1 and second.json()["origin"] == "cache")
        bad_page = a.get("/api/external/musicbrainz/search", params={"title": "otro", "cursor": searched.json()["next_cursor"]})
        check("cursor ligado a la consulta", bad_page.status_code == 422)
        local = a.get("/api/catalog/recordings", params={"title": "Nombre", "artist": "ártista"})
        check("índice local por título/artista", local.status_code == 200 and local.json()["total"] == 2)
        check("lista blanca persistida", "NO_INDEXAR" not in json.dumps(local.json()) and "score" not in local.json()["items"][0])
        check("CSRF obligatorio", a.post("/api/external/references", json={"provider": "musicbrainz", "provider_id": RID}, headers={"X-CSRF-Token": "wrong"}).status_code == 403)
        check("no confiar en URL/metadatos del navegador", a.post("/api/external/references", json={"provider": "musicbrainz", "provider_id": RID, "original_url": "http://localhost/private"}).status_code == 422)
        saved = a.post("/api/external/references", json={"provider": "musicbrainz", "provider_id": RID})
        check("referencia privada validada por lookup", saved.status_code == 201 and remote.call_count == 2)
        ref_id = saved.json()["reference_id"]
        again = a.post("/api/external/references", json={"provider": "musicbrainz", "provider_id": RID})
        check("guardar es idempotente y usa lookup cacheado", again.json()["reference_id"] == ref_id and remote.call_count == 2)
        check("colección de A visible solo para A", a.get("/api/external/references").json()["total"] == 1 and b.get("/api/external/references").json()["total"] == 0)
        check("admin tampoco ve colección privada", admin.get("/api/external/references").json()["total"] == 0)
        check("B/admin no pueden quitar referencia ajena", b.delete(f"/api/external/references/{ref_id}").status_code == 404 and admin.delete(f"/api/external/references/{ref_id}").status_code == 404)
        with db.transaction() as cursor:
            cursor.execute("UPDATE CATALOG_RECORD SET lookup_at = UTC_TIMESTAMP() - INTERVAL 40 DAY")
        check("lookup vencido se refresca al usarlo", a.get(f"/api/external/musicbrainz/recordings/{RID}").status_code == 200 and remote.call_count == 3)
        check("refresh manual", a.get(f"/api/external/musicbrainz/recordings/{RID}?refresh=true").status_code == 200 and remote.call_count == 4)
        check("A puede quitar su referencia", a.delete(f"/api/external/references/{ref_id}").status_code == 204)
        check("el índice público persiste tras quitar", b.get("/api/catalog/recordings").json()["total"] == 2)
    with db.read_only() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM TRACK_LOCATION")
        check("referencias no crean archivos de audio", cursor.fetchone()["n"] == 1)
    check("proveedor no registrado", a.get("/api/external/deezer/search?title=test").status_code == 404)
    check("listas no soportadas son explícitas", a.get("/api/external/musicbrainz/playlists").status_code == 422)
    with patch.object(MusicBrainzAdapter, "search", side_effect=CatalogError("Proveedor ocupado", status=429, retry_after=12)):
        error = a.get("/api/external/musicbrainz/search?title=uncached")
        check("429 respeta Retry-After", error.status_code == 429 and error.headers["Retry-After"] == "12")
        check("caída externa no afecta índice", a.get("/api/catalog/recordings").status_code == 200)

    # El bloqueo asesor es global a procesos, no un contador en memoria por usuario.
    with provider_slot("musicbrainz"):
        child = subprocess.run([sys.executable, "-c", "from app.integrations.catalog.traffic import provider_slot; from app.integrations.catalog.contract import CatalogError\ntry:\n with provider_slot('musicbrainz'): print('unexpected')\nexcept CatalogError as e: print(e.status)"], cwd=BACKEND, capture_output=True, text=True)
        check("limitador compartido entre procesos", child.returncode == 0 and child.stdout.strip() == "429")
    try:
        with provider_slot("musicbrainz"):
            raise AssertionError("no respetó intervalo")
    except CatalogError as error:
        check("intervalo entre solicitudes", error.status == 429)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000); wav.writeframes(b"\0\0" * 8000)
    audio = buffer.getvalue()
    active = storage.get_storage().save_stream([b"active"], max_bytes=100)
    invalid = a.post("/api/tracks/upload", data={"title": "invalid", "artist": "X"}, files={"file": ("bad.mp3", b"invalid", "audio/mpeg")})
    check("archivo inválido rechazado", invalid.status_code == 422)
    check("fallo limpia solo su temporal", Path(active.token).is_file() and len(list(storage.get_storage().tmp_dir.iterdir())) == 1)
    storage.get_storage().discard(active)

    settings = get_settings()
    old_quota = settings.max_user_quota_bytes
    settings.max_user_quota_bytes = len(audio)
    barrier = threading.Barrier(2)
    original_validate = uploads._validate_audio
    def validate(*args):
        barrier.wait(timeout=10)
        return original_validate(*args)
    def upload(index):
        try:
            return uploads.upload_track(user_id=user_ids["a"], original_filename="tone.wav", content=(audio[i:i+1024] for i in range(0, len(audio), 1024)),
                                        title=f"Tono {index}", artist="Prueba", album=None, track_number=None, disc_number=None, release_year=None)
        except uploads.QuotaExceededError:
            return None
    try:
        with patch.object(uploads, "_validate_audio", side_effect=validate), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(upload, [1, 2]))
        check("cuota concurrente: una carga, no dos", sum(item is not None for item in results) == 1)
        check("sin temporales cruzados ni huérfanos", not list(storage.get_storage().tmp_dir.iterdir()))
    finally:
        settings.max_user_quota_bytes = old_quota
    uploaded = next(item for item in results if item)
    track_id = uploaded["track_id"]
    check("rango local conserva bytes", a.get(f"/api/tracks/{track_id}/audio", headers={"Range": "bytes=4-9"}).content == audio[4:10])
    check("B no recibe bytes privados", b.get(f"/api/tracks/{track_id}/download").status_code == 404)
    check("inventario central no filtra copias ajenas", b.get("/api/storage/sources/9001/objects").json()["items"] == [])
    with db.transaction() as cursor:
        cursor.execute("UPDATE SOURCE SET status='DISCONNECTED' WHERE source_id=9001")
    check("fuente desconectada bloquea entrega", a.get(f"/api/tracks/{track_id}/audio").status_code == 409)
    with db.transaction() as cursor:
        cursor.execute("SELECT availability FROM TRACK_LOCATION WHERE location_id=%s", (uploaded["location_id"],))
        check("desconexión no se convierte en archivo borrado", cursor.fetchone()["availability"] == "AVAILABLE")
        cursor.execute("UPDATE SOURCE SET status='ACTIVE' WHERE source_id=9001")

    class ReadOnlyAdapter(StorageAdapter):
        capabilities = StorageCapabilities(listing=True)
        def stat(self, object_id): return ObjectInfo(object_id, ObjectState.FOUND, len(audio))
        def read_range(self, object_id, offset=0, length=None):
            yield audio[offset:offset + length if length is not None else None]
        def list_objects(self, *, cursor=None, limit=50): return ObjectPage([self.stat("test-object")])
    storage.registry.register("TEST_READ_ONLY", lambda source: ReadOnlyAdapter())
    with db.transaction() as cursor:
        cursor.execute("INSERT INTO SOURCE (device_id,owner_user_id,name,base_relative_path,adapter_code) VALUES (9001,%s,'Lectura de prueba','test','TEST_READ_ONLY')", (user_ids["a"],))
        sid = cursor.lastrowid
        cursor.execute("INSERT INTO TRACK (title) VALUES ('Readonly')")
        tid = cursor.lastrowid
        cursor.execute("INSERT INTO TRACK_LOCATION (track_id,owner_user_id,source_id,relative_path,sha256,size_bytes,mime_type) VALUES (%s,%s,%s,'test-object',%s,%s,'audio/wav')",
                       (tid, user_ids["a"], sid, hashlib.sha256(audio).hexdigest(), len(audio)))
    check("módulo de solo lectura usa inventario común", len(a.get(f"/api/storage/sources/{sid}/objects").json()["items"]) == 1)
    check("módulo de solo lectura usa reproductor común", a.get(f"/api/tracks/{tid}/audio", headers={"Range": "bytes=4-9"}).content == audio[4:10])
    check("admin no enumera fuente de A", admin.get(f"/api/storage/sources/{sid}/objects").status_code == 404)
    check("B no lee módulo ajeno", b.get(f"/api/tracks/{tid}/audio").status_code == 404)
    consumed = []
    def chunks():
        consumed.append(True)
        yield audio
    try:
        uploads.upload_track(user_id=user_ids["a"], source_id=sid, original_filename="test.wav", content=chunks(), title="x", artist="x", album=None, track_number=None, disc_number=None, release_year=None)
        raise AssertionError("escritura inesperada")
    except UnsupportedOperationError:
        check("solo lectura rechaza antes de consumir bytes", not consumed)


if __name__ == "__main__":
    raise SystemExit(main())
