"""Verificación del recorrido de compartición y listas (Fase 4 / H4).

Crea `mnemosine_test`, migra, crea admin e invita a A y B, sube un WAV sintético
como A y comprueba: publicación con/sin declaración, descubrimiento, descarga
pública autorizada, share individual, revocación en caliente, unpublish,
listas (crear, añadir, reordenar, borrar, aislamiento) y reglas del ADMIN
como usuario sin privilegios de contenido.

Uso desde backend: python -m scripts.verify_sharing
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
        for index in range(8000):
            sample = int(0.3 * 32767 * math.sin(2 * math.pi * 330 * index / 8000))
            frames += struct.pack("<h", sample)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def main() -> int:
    wav_bytes = make_wav_bytes()

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
        admin_user = TestClient(app)
        admin_user.post("/api/auth/login", json={"identity": "admin", "password": admin_password})
        a.post("/api/auth/register", json={"username": "usuario.a", "email": "a@example.test",
                                           "password": "cuenta-demo-123456", "invitation_code": invitation_a})
        b.post("/api/auth/register", json={"username": "usuario.b", "email": "b@example.test",
                                           "password": "cuenta-demo-123456", "invitation_code": invitation_b})
        csrf_a = a.cookies.get("mnemosine_csrf")
        headers_a = {"X-CSRF-Token": csrf_a}
        headers_b = {"X-CSRF-Token": b.cookies.get("mnemosine_csrf")}
        headers_admin_user = {"X-CSRF-Token": admin_user.cookies.get("mnemosine_csrf")}

        print("== A sube una canción (privada) ==")
        created = a.post(
            "/api/tracks/upload",
            files={"file": ("compartida.wav", wav_bytes, "audio/x-wav")},
            data={"title": "Anonadamiento", "artist": "Kältmare", "album": "Sol"},
            headers=headers_a,
        )
        check("subida → 201", created.status_code == 201)
        track_id = created.json()["track_id"]
        location_id = created.json()["location_id"]

        print("== Publicación exige declaración ==")
        no_decl = a.post(f"/api/locations/{location_id}/visibility", json={"publish": True}, headers=headers_a)
        check("publicar sin declaración → 422", no_decl.status_code == 422)
        decl = "Declaro que tengo autorización para hacerla pública"
        published = a.post(f"/api/locations/{location_id}/visibility",
                           json={"publish": True, "declaration": decl}, headers=headers_a)
        check("publicar con declaración → 200 PUBLIC",
              published.status_code == 200 and published.json()["visibility"] == "PUBLIC")
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM AUTHORIZATION_DECLARATION WHERE location_id = %s AND kind = 'PUBLICATION'",
                (location_id,),
            )
            check("declaration PUBLICATION asociada a la copia", cursor.fetchone()["n"] == 1)
            cursor.execute(
                "SELECT COUNT(*) AS n FROM PERMISSION_AUDIT WHERE location_id = %s AND action = 'PUBLISH'",
                (location_id,),
            )
            check("PERMISSION_AUDIT registra PUBLISH con declaración", cursor.fetchone()["n"] == 1)

        print("== Descubrimiento con usuarios autenticados ==")
        discovery = b.get("/api/discovery").json()
        check("B ve a A en Descubrir", any(acc["username"] == "usuario.a" for acc in discovery.get("accounts", [])))
        catalog = b.get("/api/discovery/usuario.a").json()
        check("B ve el catálogo público de A", any(item["track_id"] == track_id for item in catalog.get("items", [])))
        check("la descarga pública está denegada hasta autorizarla",
              all(item["public_download_allowed"] == 0 for item in catalog.get("items", [])))
        check("B reproduce la copia pública → 200", b.get(f"/api/tracks/{track_id}/audio").status_code == 200)
        check("B no puede descargarla → 404", b.get(f"/api/tracks/{track_id}/download").status_code == 404)
        check("anónimo no puede usar Descubrir → 401", TestClient(app).get("/api/discovery").status_code == 401)

        print("== Descarga pública autorizada ==")
        no_decl_dl = a.post(f"/api/locations/{location_id}/public-download",
                            json={"allow": True}, headers=headers_a)
        check("autorizar descarga pública sin declaración → 422", no_decl_dl.status_code == 422)
        allowed = a.post(f"/api/locations/{location_id}/public-download",
                         json={"allow": True, "declaration": "Declaración de descarga pública"}, headers=headers_a)
        check("autorizar descarga pública → 200", allowed.status_code == 200 and allowed.json()["public_download_allowed"] is True)
        check("B descarga ahora la copia pública → 200", b.get(f"/api/tracks/{track_id}/download").status_code == 200)

        print("== Despublicar vuelve a privado ==")
        unpublished = a.post(f"/api/locations/{location_id}/visibility", json={"publish": False}, headers=headers_a)
        check("despublicar → 200 PRIVATE",
              unpublished.status_code == 200 and unpublished.json()["visibility"] == "PRIVATE")
        check("B ya no reproduce la copia → 404", b.get(f"/api/tracks/{track_id}/audio").status_code == 404)

        print("== Share individual y revocación en caliente ==")
        no_decl_share = a.post(f"/api/locations/{location_id}/shares",
                               json={"username": "usuario.b", "can_stream": True, "can_download": False},
                               headers=headers_a)
        check("share sin declaración → 422", no_decl_share.status_code == 422)
        shared = a.post(f"/api/locations/{location_id}/shares",
                        json={"username": "usuario.b", "can_stream": True, "can_download": False,
                              "declaration": "Le comparto mi música"},
                        headers=headers_a)
        check("share con declaración → 201", shared.status_code == 201)
        check("B reproduce vía share → 200", b.get(f"/api/tracks/{track_id}/audio").status_code == 200)
        check("B no puede descargarla (share sin can_download) → 404",
              b.get(f"/api/tracks/{track_id}/download").status_code == 404)
        check("B aparece en Compartidas conmigo",
              any(item["track_id"] == track_id for item in b.get("/api/library/shared").json().get("items", [])))
        check("A puede ver los shares de su copia",
              any(s["username"] == "usuario.b" for s in a.get(f"/api/locations/{location_id}").json()["shares"]))
        revoke = a.delete(f"/api/locations/{location_id}/shares/{b.get('/api/auth/me').json()['id']}", headers=headers_a)
        check("A revoca el share → 200", revoke.status_code == 200)
        check("tras revocar, B ya no reproduce → 404 (nuevas solicitudes)",
              b.get(f"/api/tracks/{track_id}/audio").status_code == 404)
        check("B no puede compartir la copia de A → 403/404",
              b.post(f"/api/locations/{location_id}/shares",
                     json={"username": "usuario.a", "can_stream": True, "declaration": "x"},
                     headers=headers_b).status_code in (403, 404))

        print("== ADMIN como usuario sin privilegios ==")
        check("admin (autenticado) no puede despublicar la copia de A → 403/404",
              admin_user.post(f"/api/locations/{location_id}/visibility", json={"publish": True, "declaration": "x"},
                              headers=headers_admin_user).status_code in (403, 404))

        print("== Listas privadas ordenadas ==")
        playlist = a.post("/api/playlists", json={"name": "Mi mix", "description": "para el camino"}, headers=headers_a)
        check("A crea la lista → 201", playlist.status_code == 201)
        playlist_id = playlist.json()["playlist_id"]
        check("A lista sus listas", any(p["playlist_id"] == playlist_id for p in a.get("/api/playlists").json()))
        add1 = a.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id}, headers=headers_a)
        check("A añade la canción a la lista → 201", add1.status_code == 201)
        add2 = a.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id}, headers=headers_a)
        check("la misma canción dos veces → 400", add2.status_code == 400)
        check("B no puede añadir a la lista de A → 404",
              b.post(f"/api/playlists/{playlist_id}/tracks", json={"track_id": track_id}, headers=headers_b).status_code == 404)
        check("B no puede ver la lista de A → 404", b.get(f"/api/playlists/{playlist_id}").status_code == 404)
        detail = a.get(f"/api/playlists/{playlist_id}").json()
        check("detalle de la lista con posición 1", any(t["track_id"] == track_id and t["position"] == 1 for t in detail["tracks"]))
        reorder = a.put(f"/api/playlists/{playlist_id}/order", json={"track_ids": [track_id]}, headers=headers_a)
        check("reordenar → 200", reorder.status_code == 200)
        delete_item = a.delete(f"/api/playlists/{playlist_id}/tracks/{track_id}", headers=headers_a)
        check("quitar de la lista → 200", delete_item.status_code == 200)
        delete_list = a.delete(f"/api/playlists/{playlist_id}", headers=headers_a)
        check("eliminar la lista → 204", delete_list.status_code == 204)
        check("la canción sigue existiendo tras borrar la lista (no borrado físico)",
              a.get(f"/api/tracks/{track_id}").status_code == 200)
    finally:
        docker_sql("DROP DATABASE IF EXISTS mnemosine_test;")
        shutil.rmtree(STORAGE_TMP, ignore_errors=True)

    failures = sum(1 for _, ok in RESULTS if not ok)
    print()
    if failures:
        print(f"Verificación H4: {failures} fallo(s) de {len(RESULTS)} comprobaciones.", file=sys.stderr)
        return 1
    print(f"Verificación H4: {len(RESULTS)} comprobaciones correctas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
