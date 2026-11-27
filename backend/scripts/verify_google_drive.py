"""Pruebas OAuth/Picker con MySQL temporal, HTTP de Google simulado y tres usuarios.

No usa credenciales reales ni llama a Google. python -m scripts.verify_google_drive
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from cryptography.fernet import Fernet

from scripts.verify_integrations import docker_sql, BACKEND

checks = 0


def check(label, condition):
    global checks
    if not condition:
        raise AssertionError(label)
    checks += 1
    print("  OK " + label)


def main():
    name = "mnemosine_google_" + uuid.uuid4().hex[:12]
    os.environ["DB_NAME"] = name
    docker_sql(f"CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL ON {name}.* TO 'mnemosine_app'@'%';")
    try:
        with tempfile.TemporaryDirectory(prefix="mnemosine_google_") as directory:
            private = Path(directory)
            origin = "http://127.0.0.1:5173"
            (private / "client.json").write_text(json.dumps({"web": {"project_id": "test-project", "client_id": "test.apps.googleusercontent.com",
                "client_secret": "TEST_CLIENT_SECRET", "javascript_origins": [origin], "redirect_uris": [origin + "/api/integrations/google_drive/callback"]}}))
            (private / "keys.json").write_text(json.dumps({"current": "v1", "keys": {"v1": Fernet.generate_key().decode()}}))
            (private / "picker.txt").write_text("AIzaTEST_ONLY")
            os.environ.update({"GOOGLE_DRIVE_ENABLED": "true", "GOOGLE_PROJECT_ID": "test-project", "GOOGLE_PROJECT_NUMBER": "123",
                "GOOGLE_APP_ORIGIN": origin, "GOOGLE_OAUTH_CLIENT_FILE": str(private / "client.json"),
                "GOOGLE_TOKEN_KEYS_FILE": str(private / "keys.json"), "GOOGLE_PICKER_KEY_FILE": str(private / "picker.txt"), "STORAGE_ROOT": str(private / "audio")})
            result = subprocess.run([sys.executable, "-m", "scripts.migrate"], cwd=BACKEND, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            run_checks()
        print(f"\n{checks} comprobaciones Google correctas. Base temporal eliminada; sin llamadas externas.")
    finally:
        docker_sql(f"DROP DATABASE {name};")


def run_checks():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.repositories import db
    from app.security.passwords import hash_password
    from app.integrations.google_drive import client, crypto
    from app.integrations.google_drive.config import DriveError, SCOPE
    from app.services import google_drive as service

    clients, users = {}, {}
    for who, role in (("a", "USER"), ("b", "USER"), ("admin", "ADMIN")):
        with db.transaction() as cursor:
            cursor.execute("INSERT INTO USER_ACCOUNT(username,email,password_hash,role) VALUES (%s,%s,%s,%s)",
                           (who, who + "@example.test", hash_password("test-google-only-2026!"), role))
            users[who] = cursor.lastrowid
        clients[who] = TestClient(app)
        check("sesión " + who, clients[who].post("/api/auth/login", json={"identity": who, "password": "test-google-only-2026!"}).status_code == 200)
        clients[who].headers["X-CSRF-Token"] = clients[who].cookies.get("mnemosine_csrf")
    a, b, admin = clients["a"], clients["b"], clients["admin"]
    root = "/api/integrations/google_drive"
    flags = {"refresh_failure": False, "revocation_failure": False, "subject": None, "bad_scope": False}
    calls = []

    def fake(method, url, *, token=None, data=None, params=None):
        calls.append((method, url, token, data, params))
        if url == client.TOKEN_URL:
            if flags.get("close_session"):
                with db.transaction() as cursor:
                    cursor.execute("UPDATE USER_SESSION SET revoked_at=NOW() WHERE user_id=%s", (flags["close_session"],))
            if flags["refresh_failure"] and data["grant_type"] == "refresh_token":
                raise DriveError("Reconecta", status=409, code="reauth_required")
            who = (data.get("code") or data.get("refresh_token")).split("-")[-1]
            return {"access_token": "access-" + who, "refresh_token": "refresh-" + who, "expires_in": 3600,
                    "token_type": "Bearer", "scope": "https://www.googleapis.com/auth/drive" if flags["bad_scope"] else SCOPE}
        if url == client.REVOKE_URL:
            if flags["revocation_failure"]:
                raise DriveError("Sin red")
            return {}
        if url.endswith("/about"):
            who = flags["subject"] or token.split("-")[-1]
            return {"user": {"permissionId": "subject-" + who, "emailAddress": who + "@example.test", "displayName": who}}
        file_id = url.rsplit("/", 1)[-1]
        if file_id != "file_" + token.split("-")[-1]:
            raise DriveError("Sin acceso", status=404, code="not_accessible")
        return {"id": file_id, "name": 'Audio <privado>.wav', "mimeType": "audio/wav", "size": "120", "version": "7",
                "ownedByMe": True, "isAppAuthorized": True, "capabilities": {"canDownload": True}}

    def begin(web):
        result = web.post(root + "/authorize")
        check("inicio OAuth", result.status_code == 200)
        return parse_qs(urlsplit(result.json()["authorization_url"]).query)

    def finish(web, query, who="a", **extra):
        return web.get(root + "/callback", params={"state": query["state"][0], "code": "code-" + who, **extra}, follow_redirects=False)

    with patch.object(client, "request", side_effect=fake):
        check("Google requiere sesión", TestClient(app).get(root + "/status").status_code == 401)
        check("authorize exige CSRF", a.post(root + "/authorize", headers={"X-CSRF-Token": "wrong"}).status_code == 403)
        check("rechaza otro origen", a.post(root + "/authorize", headers={"Origin": "https://bad.example"}).status_code == 403)
        initial = a.get(root + "/status")
        check("sin conexión y sin tokens públicos", initial.json()["connection"] is None and "SECRET" not in initial.text and "AIza" not in initial.text)
        query = begin(a)
        check("solo drive.file, PKCE, offline y retorno fijo", query["scope"] == [SCOPE] and query["code_challenge_method"] == ["S256"]
              and query["access_type"] == ["offline"] and query["redirect_uri"] == ["http://127.0.0.1:5173" + root + "/callback"])
        with db.read_only() as cursor:
            cursor.execute("SELECT * FROM OAUTH_AUTHORIZATION WHERE owner_user_id=%s", (users["a"],))
            flow = cursor.fetchone()
        check("state no persiste en claro", flow["state_hash"] != query["state"][0])
        verifier = crypto.decrypt(flow["verifier_ciphertext"], f"oauth:{users['a']}:{flow['session_id']}:{flow['state_hash']}")
        check("PKCE corresponde al verificador cifrado", base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode() == query["code_challenge"][0])
        n = len(calls)
        check("B no usa state de A", finish(b, query).headers["location"].endswith("invalid_state") and len(calls) == n)
        result = finish(a, query)
        check("callback correcto sin código en retorno", result.status_code == 303 and result.headers["location"] == "/conexiones?google=connected")
        check("callback sin caché y sin referente", "no-store" in result.headers["cache-control"] and result.headers["referrer-policy"] == "no-referrer")
        check("state no reutilizable", finish(a, query).headers["location"].endswith("invalid_state"))
        row = service.own_connection(users["a"])
        cid = row["connection_id"]
        prefix = root + f"/connections/{cid}"
        check("credenciales cifradas", "refresh-a" not in row["credentials_ciphertext"] and "access-a" not in row["credentials_ciphertext"])
        visible = a.get(root + "/status")
        check("status no expone tokens ni secreto", all(value not in visible.text for value in ("refresh-a", "access-a", "TEST_CLIENT_SECRET", "ciphertext")))
        n = len(calls)
        for intruder in (b, admin):
            check("otra cuenta no obtiene Picker", intruder.post(prefix + "/picker").status_code == 404)
            check("otra cuenta no guarda selección", intruder.post(prefix + "/files", json={"file_ids": ["file_a"]}).status_code == 404)
            check("otra cuenta no ve selección", intruder.get(prefix + "/files").status_code == 404)
            check("otra cuenta no desconecta", intruder.post(prefix + "/disconnect").status_code == 404)
        check("rechazos antes de llamar a Google", len(calls) == n)
        picker = a.post(prefix + "/picker")
        check("Picker recibe solo token corto propio", picker.json()["access_token"] == "access-a" and "refresh" not in picker.text and "no-store" in picker.headers["cache-control"])
        check("Picker exige CSRF", a.post(prefix + "/picker", headers={"X-CSRF-Token": "wrong"}).status_code == 403)
        check("metadatos del navegador no son confiables", a.post(prefix + "/files", json={"file_ids": ["file_a"], "owner_user_id": users["b"]}).status_code == 422)
        check("ID ajeno se revalida con Google", a.post(prefix + "/files", json={"file_ids": ["file_b"]}).status_code == 404)
        check("selección propia comprobada", a.post(prefix + "/files", json={"file_ids": ["file_a"]}).status_code == 200)
        a.post(prefix + "/files", json={"file_ids": ["file_a"]})
        listing = a.get(prefix + "/files").json()
        check("selección idempotente y sin audio ficticio", listing["total"] == 1 and listing["items"][0]["audio_validated"] is False)
        sid = listing["items"][0]["id"]
        check("ADMIN no quita selección de A", admin.delete(prefix + f"/files/{sid}").status_code == 404)
        with db.transaction() as cursor:
            cursor.executemany("INSERT INTO DRIVE_SELECTION(connection_id,owner_user_id,file_id,file_name,mime_type,size_bytes,remote_version) "
                               "VALUES (%s,%s,%s,'Fixture.wav','audio/wav',120,'1')",
                               [(cid, users["a"], f"limit_{i}") for i in range(499)])
        check("revalidar al límite no crea duplicados", a.post(prefix + "/files", json={"file_ids": ["file_a"]}).status_code == 200
              and a.get(prefix + "/files").json()["total"] == 500)
        with db.transaction() as cursor:
            cursor.execute("DELETE FROM DRIVE_SELECTION WHERE connection_id=%s AND file_id LIKE 'limit_%%'", (cid,))
        q_b = begin(b)
        finish(b, q_b, "b")
        cb = service.own_connection(users["b"])["connection_id"]
        check("selecciones separadas", b.get(root + f"/connections/{cb}/files").json()["total"] == 0)
        check("token separado por cuenta", b.post(root + f"/connections/{cb}/picker").json()["access_token"] == "access-b")
        # Rechazar cambio de identidad sin desconexión explícita.
        mismatch = finish(a, begin(a), "b")
        check("reconexión verifica identidad estable", mismatch.headers["location"].endswith("account_mismatch") and service.own_connection(users["a"])["external_subject"] == "subject-a")
        denied = finish(a, begin(a), error="access_denied")
        check("cancelación conserva conexión anterior", denied.headers["location"].endswith("cancelled") and service.own_connection(users["a"])["status"] == "ACTIVE")
        flags["bad_scope"] = True
        check("rechaza alcance completo de Drive", finish(a, begin(a)).headers["location"].endswith("scope_denied"))
        flags["bad_scope"] = False
        expired = begin(a)
        with db.transaction() as cursor:
            cursor.execute("UPDATE OAUTH_AUTHORIZATION SET expires_at=UTC_TIMESTAMP()-INTERVAL 1 SECOND WHERE owner_user_id=%s", (users["a"],))
        check("state vencido rechazado", finish(a, expired).headers["location"].endswith("invalid_state"))
        # Una segunda sesión de la misma persona tampoco puede consumir el state.
        old = begin(a)
        other_session = TestClient(app)
        other_session.post("/api/auth/login", json={"identity": "a", "password": "test-google-only-2026!"})
        check("state ligado a sesión concreta", finish(other_session, old).headers["location"].endswith("invalid_state"))
        check("sesión original conserva state", finish(a, old).headers["location"].endswith("connected"))
        with db.transaction() as cursor:
            cursor.execute("UPDATE INTEGRATION_CONNECTION SET expires_at=UTC_TIMESTAMP()-INTERVAL 1 SECOND WHERE connection_id=%s", (cid,))
        n = len([c for c in calls if c[1] == client.TOKEN_URL])
        check("renovación de token vencido", a.post(prefix + "/picker").status_code == 200)
        check("renovación invocada una vez", len([c for c in calls if c[1] == client.TOKEN_URL]) == n+1)
        a.post(prefix + "/picker")
        check("token renovado reutilizado", len([c for c in calls if c[1] == client.TOKEN_URL]) == n+1)
        with service.connection_lock(users["a"]):
            check("bloqueo por conexión entre clientes", a.post(prefix + "/picker").status_code == 429)
            check("otra cuenta no queda bloqueada", b.post(root + f"/connections/{cb}/picker").status_code == 200)
        with db.transaction() as cursor:
            cursor.execute("UPDATE INTEGRATION_CONNECTION SET expires_at=UTC_TIMESTAMP()-INTERVAL 1 SECOND WHERE connection_id=%s", (cid,))
        flags["refresh_failure"] = True
        check("revocación requiere reconectar", a.post(prefix + "/picker").status_code == 409 and service.own_connection(users["a"])["status"] == "REAUTH_REQUIRED")
        flags["refresh_failure"] = False
        check("reconexión recupera acceso", finish(a, begin(a)).headers["location"].endswith("connected"))
        check("selección conservada al reconectar", a.get(prefix + "/files").json()["total"] == 1)
        stale_flow = begin(a)
        flags["revocation_failure"] = True
        result = a.post(prefix + "/disconnect")
        check("desconexión bloquea aunque Google falle", not result.json()["revoked"] and a.post(prefix + "/picker").status_code == 409)
        check("callback anterior no reactiva conexión", finish(a, stale_flow).headers["location"].endswith("invalid_state"))
        check("no reconectar durante revocación pendiente", a.post(root + "/authorize").status_code == 409)
        flags["revocation_failure"] = False
        result = a.post(prefix + "/disconnect")
        check("reintento completa revocación", result.json()["revoked"] and service.own_connection(users["a"])["credentials_ciphertext"] is None)
        check("desconexión idempotente", a.post(prefix + "/disconnect").json()["revoked"])
        check("otra cuenta permanece conectada", b.post(root + f"/connections/{cb}/picker").status_code == 200)
        with db.read_only() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM DRIVE_SELECTION WHERE connection_id=%s", (cid,))
            check("desconexión limpia solo selección propia", cursor.fetchone()["total"] == 0)
            cursor.execute("SELECT COUNT(*) AS total FROM TRACK_LOCATION")
            check("no crea audio ni copias inexistentes", cursor.fetchone()["total"] == 0)
        check("nunca solicita borrar originales", not any(method == "DELETE" for method, *_ in calls))
        closing = begin(admin)
        flags["close_session"] = users["admin"]
        result = finish(admin, closing, "admin")
        flags["close_session"] = None
        check("cerrar sesión durante OAuth impide guardar permisos", result.headers["location"].endswith("session_expired")
              and service.own_connection(users["admin"])["credentials_ciphertext"] is None)
        from scripts.restore import quarantine_sql
        docker_sql(quarantine_sql(os.environ["DB_NAME"], ["INTEGRATION_CONNECTION", "OAUTH_AUTHORIZATION", "TRANSFER_JOB"]) + ";")
        restored = service.own_connection(users["b"])
        check("restaurar no reactiva credenciales", restored["status"] == "REAUTH_REQUIRED" and restored["credentials_ciphertext"] is None)
        check("conexión restaurada exige consentimiento nuevo", b.post(root + f"/connections/{cb}/picker").status_code == 409)


if __name__ == "__main__":
    main()
