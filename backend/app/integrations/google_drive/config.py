"""Configuración del servidor: nunca se publican el JSON OAuth ni la clave de cifrado."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import get_settings

SCOPE = "https://www.googleapis.com/auth/drive.file"
CALLBACK_PATH = "/api/integrations/google_drive/callback"


class DriveError(Exception):
    def __init__(self, message: str, *, status: int = 503, code: str = "unavailable"):
        super().__init__(message)
        self.status, self.code = status, code


def read_private_file(filename: str) -> str:
    try:
        path = Path(filename)
        if not filename or not path.is_absolute() or path.stat().st_size > 65536:
            raise ValueError()
        return path.read_text(encoding="utf-8-sig").strip()
    except (OSError, ValueError):
        raise DriveError("La conexión con Google aún no está configurada.", code="configuration") from None


@dataclass(frozen=True)
class GoogleConfig:
    client_id: str
    client_secret: str = field(repr=False)
    origin: str
    project_number: str
    picker_key: str = field(repr=False)

    @property
    def redirect_uri(self):
        return self.origin + CALLBACK_PATH


def configuration() -> GoogleConfig:
    settings = get_settings()
    if not settings.google_drive_enabled:
        raise DriveError("La conexión con Google Drive está deshabilitada.", code="disabled")
    try:
        origin = settings.google_app_origin
        parsed = urlsplit(origin)
        if (parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path
                or not parsed.hostname or parsed.scheme not in ("https", "http")
                or (parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost"))):
            raise ValueError()
        client = json.loads(read_private_file(settings.google_oauth_client_file))["web"]
        picker_key = read_private_file(settings.google_picker_key_file)
        if (client["project_id"] != settings.google_project_id
                or not settings.google_project_number.isdigit()
                or not client["client_id"].endswith(".apps.googleusercontent.com")
                or not client["client_secret"] or not picker_key.startswith("AIza")
                or origin not in client.get("javascript_origins", [])
                or origin + CALLBACK_PATH not in client.get("redirect_uris", [])):
            raise ValueError()
        return GoogleConfig(client["client_id"], client["client_secret"], origin,
                            settings.google_project_number, picker_key)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise DriveError("Revisa la configuración de Google Drive en el servidor.", code="configuration") from None
