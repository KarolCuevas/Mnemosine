"""HTTP acotado a Google; errores sanitizados, tokens solo en cabecera/cuerpo POST."""
import json
import re
import httpx

from app.core.config import get_settings
from .config import DriveError, SCOPE, configuration

API = "https://www.googleapis.com/drive/v3/"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
FILE_FIELDS = "id,name,mimeType,size,version,trashed,driveId,ownedByMe,isAppAuthorized,capabilities(canDownload)"


def request(method, url, *, token=None, data=None, params=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False) as client:
            with client.stream(method, url, headers=headers, data=data, params=params) as response:
                raw = bytearray()
                for chunk in response.iter_bytes(65536):
                    raw.extend(chunk)
                    if len(raw) > 1024 * 1024:
                        raise DriveError("Google devolvió una respuesta demasiado grande.")
                try:
                    body = json.loads(raw) if raw else {}
                except ValueError:
                    raise DriveError("Google devolvió una respuesta no válida.") from None
                if not isinstance(body, dict):
                    raise DriveError("Google devolvió una respuesta no válida.")
                if response.status_code >= 400:
                    if url == REVOKE_URL and response.status_code == 400 and body.get("error") == "invalid_token":
                        return {}  # Ya revocado; desconectar sigue siendo idempotente.
                    if body.get("error") == "invalid_grant" or response.status_code == 401:
                        raise DriveError("Vuelve a conectar tu cuenta de Google.", status=409, code="reauth_required")
                    if response.status_code == 429:
                        raise DriveError("Google está ocupado. Reintenta en un momento.", status=429, code="rate_limited")
                    if response.status_code in (403, 404):
                        raise DriveError("No se puede acceder a ese archivo con tu conexión.", status=404, code="not_accessible")
                    raise DriveError("No se pudo completar la solicitud a Google.")
                if response.status_code < 200 or response.status_code >= 300:
                    raise DriveError("Google devolvió una respuesta inesperada.")
                return body
    except httpx.HTTPError:
        raise DriveError("No se pudo contactar con Google. Reintenta en un momento.") from None


def exchange(code: str, verifier: str):
    config = configuration()
    return request("POST", TOKEN_URL, data={"code": code, "code_verifier": verifier,
                   "client_id": config.client_id, "client_secret": config.client_secret,
                   "redirect_uri": config.redirect_uri, "grant_type": "authorization_code"})


def refresh(refresh_token: str):
    config = configuration()
    return request("POST", TOKEN_URL, data={"refresh_token": refresh_token,
                   "client_id": config.client_id, "client_secret": config.client_secret,
                   "grant_type": "refresh_token"})


def revoke(token: str) -> bool:
    try:
        request("POST", REVOKE_URL, data={"token": token})
        return True
    except DriveError as error:
        # invalid_grant / 401 means the grant is already unusable.
        if error.code == "reauth_required":
            return True
        return False


def identity(token: str):
    body = request("GET", API + "about", token=token,
                   params={"fields": "user(permissionId,emailAddress,displayName)"})
    user = body.get("user", {})
    if not isinstance(user, dict):
        raise DriveError("Google no devolvió la identidad de esta cuenta.")
    subject = user.get("permissionId")
    if not isinstance(subject, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", subject):
        raise DriveError("Google no devolvió la identidad de esta cuenta.")
    return {"subject": subject, "email": str(user.get("emailAddress") or "")[:255],
            "name": str(user.get("displayName") or "")[:255]}


def file_metadata(token: str, file_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", file_id):
        raise DriveError("Identificador de archivo no válido.", status=422, code="invalid_file")
    body = request("GET", API + "files/" + file_id, token=token, params={"fields": FILE_FIELDS})
    capabilities = body.get("capabilities")
    if (body.get("id") != file_id or body.get("trashed") or body.get("driveId")
            or body.get("ownedByMe") is not True or body.get("isAppAuthorized") is not True
            or not isinstance(capabilities, dict) or capabilities.get("canDownload") is not True):
        raise DriveError("Elige un archivo propio de Mi unidad con descarga permitida.", status=422, code="unsupported_file")
    mime = body.get("mimeType", "")
    # Solo candidatos a audio. Los bytes se validarán al incorporar la copia en I3.
    if not isinstance(mime, str) or not (mime.startswith("audio/") or mime in ("application/ogg", "application/octet-stream")):
        raise DriveError("Elige un archivo de audio; carpetas, accesos directos y documentos no se admiten.", status=422, code="unsupported_file")
    try:
        size = int(body["size"])
        version = str(body["version"])
        name = body["name"]
        if size < 1 or size > get_settings().max_upload_bytes or len(version) > 128:
            raise ValueError()
        if not isinstance(name, str) or not 1 <= len(name) <= 512 or len(mime) > 255:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise DriveError("El archivo está vacío, es demasiado grande o tiene datos incompletos.", status=422, code="invalid_file") from None
    return {"file_id": file_id, "name": name, "mime_type": mime, "size_bytes": size,
            "version": version, "audio_validated": False}
