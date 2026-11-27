"""Conexiones por usuario. Bloqueo entre procesos; ninguna transacción durante HTTP."""
import base64
import hashlib
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from app.core.config import get_settings
from app.repositories import db
from app.integrations.google_drive import client, crypto
from app.integrations.google_drive.config import DriveError, SCOPE, configuration


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@contextmanager
def connection_lock(user_id: int):
    suffix = hashlib.sha256(f"{get_settings().db_name}:{user_id}".encode()).hexdigest()[:40]
    name = "mnemosine:google:" + suffix
    connection = db.connect(autocommit=True)
    acquired = False
    try:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (name,))
            acquired = cursor.fetchone()["acquired"] == 1
        if not acquired:
            raise DriveError("Hay otra operación con tu Drive en curso. Reintenta en un momento.", status=429, code="busy")
        yield
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
                cursor.fetchall()
        connection.close()


def assert_session(current):
    # Revalidar tras una llamada externa: el usuario puede cerrar sesión/desactivarse entretanto.
    with db.read_only() as cursor:
        cursor.execute("SELECT s.created_at FROM USER_SESSION s JOIN USER_ACCOUNT u ON u.user_id=s.user_id "
                       "WHERE s.session_id=%s AND s.user_id=%s AND u.is_active=1 "
                       "AND s.revoked_at IS NULL AND s.expires_at>NOW()",
                       (current.session_id, current.user_id))
        row = cursor.fetchone()
    if not row or datetime.now() - row["created_at"] > timedelta(days=get_settings().session_absolute_days):
        raise DriveError("Tu sesión terminó. Vuelve a entrar en Mnemosine.", status=401, code="session_expired")


def own_connection(user_id, connection_id=None):
    with db.read_only() as cursor:
        cursor.execute("SELECT * FROM INTEGRATION_CONNECTION WHERE owner_user_id=%s AND provider='google_drive'",
                       (user_id,))
        row = cursor.fetchone()
    if connection_id is not None and (not row or row["connection_id"] != connection_id):
        raise DriveError("Conexión no encontrada.", status=404, code="not_found")
    return row


def public_connection(row):
    if not row:
        return None
    return {"id": row["connection_id"], "status": row["status"], "email": row["account_email"],
            "name": row["account_name"], "updated_at": row["updated_at"].isoformat() + "Z"}


def status(user_id):
    configured, message, origin = True, None, None
    try:
        config = configuration()
        crypto.keyring()
        origin = config.origin
    except DriveError as error:
        configured, message = False, str(error)
    return {"configured": configured, "message": message, "origin": origin,
            "connection": public_connection(own_connection(user_id))}


def begin(current):
    config = configuration()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    encrypted = crypto.encrypt(verifier, f"oauth:{current.user_id}:{current.session_id}:{state_hash}")
    with connection_lock(current.user_id):
        assert_session(current)
        row = own_connection(current.user_id)
        if row and row["status"] == "REVOCATION_PENDING":
            raise DriveError("Termina de desconectar la cuenta anterior antes de conectar otra.", status=409, code="revocation_pending")
        with db.transaction() as cursor:
            if not row:
                cursor.execute("INSERT INTO INTEGRATION_CONNECTION(owner_user_id,provider) VALUES (%s,'google_drive')", (current.user_id,))
            cursor.execute("DELETE FROM OAUTH_AUTHORIZATION WHERE owner_user_id=%s OR expires_at<=UTC_TIMESTAMP(6)", (current.user_id,))
            cursor.execute("INSERT INTO OAUTH_AUTHORIZATION(state_hash,owner_user_id,session_id,connection_generation,verifier_ciphertext,expires_at) "
                           "VALUES (%s,%s,%s,%s,%s,%s)",
                           (state_hash, current.user_id, current.session_id, row["generation"] if row else 0,
                            encrypted, utcnow() + timedelta(minutes=10)))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": config.client_id, "redirect_uri": config.redirect_uri,
        "response_type": "code", "scope": SCOPE, "state": state,
        "access_type": "offline", "prompt": "consent select_account",
        "include_granted_scopes": "false", "code_challenge": challenge, "code_challenge_method": "S256",
    })}


def checked_tokens(body, previous=None):
    previous = previous or {}
    try:
        scope = body.get("scope", previous.get("scope", ""))
        if set(scope.split()) != {SCOPE}:
            raise DriveError("Google no concedió únicamente el permiso de archivos solicitado.", status=409, code="scope_denied")
        access = body["access_token"]
        refresh = body.get("refresh_token") or previous.get("refresh_token")
        expiry = int(body["expires_in"])
        if (body.get("token_type", "").lower() != "bearer" or not 60 <= expiry <= 86400
                or not all(isinstance(token, str) and 1 <= len(token) <= 16384 for token in (access, refresh))):
            raise ValueError()
        return {"access_token": access, "refresh_token": refresh, "scope": SCOPE}, utcnow() + timedelta(seconds=expiry)
    except (KeyError, ValueError, TypeError, AttributeError):
        raise DriveError("Google no entregó las credenciales necesarias. Vuelve a conectar.", status=409, code="reauth_required") from None


def complete(current, state: str, code: str | None, error: str | None):
    if not state or len(state) > 128:
        raise DriveError("La autorización venció o no corresponde a esta sesión.", status=400, code="invalid_state")
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    with connection_lock(current.user_id):
        assert_session(current)
        with db.transaction() as cursor:
            cursor.execute("SELECT * FROM OAUTH_AUTHORIZATION WHERE state_hash=%s AND owner_user_id=%s "
                           "AND session_id=%s AND expires_at>UTC_TIMESTAMP(6) FOR UPDATE",
                           (state_hash, current.user_id, current.session_id))
            flow = cursor.fetchone()
            if not flow:
                raise DriveError("La autorización venció o no corresponde a esta sesión.", status=400, code="invalid_state")
            cursor.execute("DELETE FROM OAUTH_AUTHORIZATION WHERE state_hash=%s", (state_hash,))
        row = own_connection(current.user_id)
        if not row or row["generation"] != flow["connection_generation"] or row["status"] == "REVOCATION_PENDING":
            raise DriveError("La conexión cambió. Inicia de nuevo la autorización.", status=409, code="invalid_state")
        if error:
            return "cancelled" if error == "access_denied" else "unavailable"
        if not code or len(code) > 4096:
            raise DriveError("Google no devolvió un código válido.", status=400, code="invalid_state")
        verifier = crypto.decrypt(flow["verifier_ciphertext"], f"oauth:{current.user_id}:{current.session_id}:{state_hash}")
        body = client.exchange(code, verifier)
        # Identidad de Drive, disponible con drive.file; no se añade openid/profile/email.
        access = body.get("access_token")
        if not isinstance(access, str) or not 1 <= len(access) <= 16384:
            raise DriveError("Google no devolvió un acceso válido.")
        identity = client.identity(access)
        if row["external_subject"] and identity["subject"] != row["external_subject"]:
            raise DriveError("Reconecta la misma cuenta de Google. Para cambiarla, desconecta primero.", status=409, code="account_mismatch")
        previous = crypto.decrypt(row["credentials_ciphertext"], f"google:{current.user_id}") if row["credentials_ciphertext"] else None
        tokens, expiry = checked_tokens(body, previous)
        ciphertext = crypto.encrypt(tokens, f"google:{current.user_id}")
        assert_session(current)
        with db.transaction() as cursor:
            cursor.execute("UPDATE INTEGRATION_CONNECTION SET external_subject=%s,account_email=%s,account_name=%s,"
                           "status='ACTIVE',granted_scopes=%s,credentials_ciphertext=%s,expires_at=%s,generation=generation+1 "
                           "WHERE connection_id=%s AND owner_user_id=%s AND generation=%s",
                           (identity["subject"], identity["email"], identity["name"], SCOPE, ciphertext, expiry,
                            row["connection_id"], current.user_id, row["generation"]))
            if cursor.rowcount != 1:
                raise DriveError("La conexión cambió. Vuelve a conectarla.", status=409, code="invalid_state")
        return "connected"


def mark_reauth(row):
    with db.transaction() as cursor:
        cursor.execute("UPDATE INTEGRATION_CONNECTION SET status='REAUTH_REQUIRED',credentials_ciphertext=NULL,"
                       "expires_at=NULL,generation=generation+1 WHERE connection_id=%s AND status='ACTIVE'",
                       (row["connection_id"],))


def access_token(row):
    # El llamador mantiene connection_lock durante toda la operación.
    if row["status"] != "ACTIVE" or not row["credentials_ciphertext"]:
        raise DriveError("Vuelve a conectar tu Drive para continuar.", status=409, code="reauth_required")
    tokens = crypto.decrypt(row["credentials_ciphertext"], f"google:{row['owner_user_id']}")
    if row["expires_at"] and row["expires_at"] > utcnow() + timedelta(seconds=60):
        return tokens["access_token"]
    try:
        tokens, expiry = checked_tokens(client.refresh(tokens["refresh_token"]), tokens)
    except DriveError as error:
        if error.code in ("reauth_required", "scope_denied"):
            mark_reauth(row)
        raise
    ciphertext = crypto.encrypt(tokens, f"google:{row['owner_user_id']}")
    with db.transaction() as cursor:
        cursor.execute("UPDATE INTEGRATION_CONNECTION SET credentials_ciphertext=%s,expires_at=%s WHERE connection_id=%s",
                       (ciphertext, expiry, row["connection_id"]))
    return tokens["access_token"]


def picker(current, connection_id):
    config = configuration()
    with connection_lock(current.user_id):
        assert_session(current)
        row = own_connection(current.user_id, connection_id)
        token = access_token(row)
        # Detecta revocación incluso si el token en caché todavía no llegó a su vencimiento.
        try:
            identity = client.identity(token)
        except DriveError as error:
            if error.code == "reauth_required":
                mark_reauth(row)
            raise
        if identity["subject"] != row["external_subject"]:
            mark_reauth(row)
            raise DriveError("Vuelve a conectar tu cuenta de Google.", status=409, code="account_mismatch")
        assert_session(current)
        return {"access_token": token, "developer_key": config.picker_key, "app_id": config.project_number,
                "origin": config.origin}


def select_files(current, connection_id, file_ids):
    configuration()
    with connection_lock(current.user_id):
        assert_session(current)
        row = own_connection(current.user_id, connection_id)
        token = access_token(row)
        try:
            items = [client.file_metadata(token, file_id) for file_id in dict.fromkeys(file_ids)]
        except DriveError as error:
            if error.code == "reauth_required":
                mark_reauth(row)
            raise
        assert_session(current)
        with db.transaction() as cursor:
            cursor.execute("SELECT file_id FROM DRIVE_SELECTION WHERE connection_id=%s", (connection_id,))
            existing = {item["file_id"] for item in cursor.fetchall()}
            if len(existing | {item["file_id"] for item in items}) > 500:
                raise DriveError("Quita alguna selección antes de agregar más archivos.", status=422, code="selection_limit")
            for item in items:
                cursor.execute("INSERT INTO DRIVE_SELECTION(connection_id,owner_user_id,file_id,file_name,mime_type,size_bytes,remote_version) "
                               "VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE file_name=VALUES(file_name),"
                               "mime_type=VALUES(mime_type),size_bytes=VALUES(size_bytes),remote_version=VALUES(remote_version),checked_at=UTC_TIMESTAMP(6)",
                               (connection_id, current.user_id, item["file_id"], item["name"], item["mime_type"], item["size_bytes"], item["version"]))
        return {"items": items}


def selected_files(user_id, connection_id, page=1):
    row = own_connection(user_id, connection_id)
    if row["status"] != "ACTIVE":
        raise DriveError("Conecta tu Drive para consultar la selección.", status=409, code="reauth_required")
    with db.read_only() as cursor:
        cursor.execute("SELECT selection_id AS id,file_id,file_name AS name,mime_type,size_bytes,remote_version AS version,checked_at "
                       "FROM DRIVE_SELECTION WHERE connection_id=%s AND owner_user_id=%s ORDER BY selection_id DESC LIMIT 25 OFFSET %s",
                       (connection_id, user_id, (page-1)*25))
        items = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS total FROM DRIVE_SELECTION WHERE connection_id=%s AND owner_user_id=%s", (connection_id, user_id))
        total = cursor.fetchone()["total"]
    for item in items:
        item["audio_validated"] = False
        item["checked_at"] = item["checked_at"].isoformat() + "Z"
    return {"items": items, "page": page, "total": total, "page_size": 25}


def remove_selection(current, connection_id, selection_id):
    with connection_lock(current.user_id):
        own_connection(current.user_id, connection_id)
        assert_session(current)
        with db.transaction() as cursor:
            cursor.execute("DELETE FROM DRIVE_SELECTION WHERE selection_id=%s AND connection_id=%s AND owner_user_id=%s",
                           (selection_id, connection_id, current.user_id))
            if cursor.rowcount != 1:
                raise DriveError("Selección no encontrada.", status=404, code="not_found")


def disconnect(current, connection_id):
    with connection_lock(current.user_id):
        assert_session(current)
        row = own_connection(current.user_id, connection_id)
        tokens = crypto.decrypt(row["credentials_ciphertext"], f"google:{current.user_id}") if row["credentials_ciphertext"] else {}
        # Bloqueo efectivo en Mnemosine antes de intentar la revocación remota.
        with db.transaction() as cursor:
            cursor.execute("UPDATE INTEGRATION_CONNECTION SET status='REVOCATION_PENDING',generation=generation+1 WHERE connection_id=%s", (connection_id,))
            cursor.execute("DELETE FROM OAUTH_AUTHORIZATION WHERE owner_user_id=%s", (current.user_id,))
            cursor.execute("DELETE FROM DRIVE_SELECTION WHERE connection_id=%s", (connection_id,))
        revoke_token = tokens.get("refresh_token") or tokens.get("access_token")
        revoked = not revoke_token or client.revoke(revoke_token)
        if revoked:
            with db.transaction() as cursor:
                cursor.execute("UPDATE INTEGRATION_CONNECTION SET status='DISCONNECTED',credentials_ciphertext=NULL,expires_at=NULL,"
                               "external_subject=NULL,account_email=NULL,account_name=NULL,granted_scopes=NULL WHERE connection_id=%s", (connection_id,))
        return {"revoked": revoked, "connection": public_connection(own_connection(current.user_id, connection_id))}
