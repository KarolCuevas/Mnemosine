"""Cifrado autenticado con claves versionadas y contexto que impide intercambiar dueños."""
import json
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from .config import DriveError, read_private_file


def keyring():
    try:
        data = json.loads(read_private_file(get_settings().google_token_keys_file))
        current = data["current"]
        keys = {key: Fernet(value.encode("ascii")) for key, value in data["keys"].items()}
        if not isinstance(current, str) or ":" in current or current not in keys:
            raise ValueError()
        return current, keys
    except (ValueError, TypeError, KeyError, AttributeError):
        raise DriveError("No está disponible la clave de protección de Google.", code="configuration") from None


def encrypt(value, purpose: str) -> str:
    current, keys = keyring()
    content = json.dumps({"purpose": purpose, "value": value}, separators=(",", ":")).encode()
    return current + ":" + keys[current].encrypt(content).decode("ascii")


def decrypt(value: str, purpose: str):
    try:
        _, keys = keyring()
        version, ciphertext = value.split(":", 1)
        content = json.loads(keys[version].decrypt(ciphertext.encode("ascii")))
        if content["purpose"] != purpose:
            raise ValueError()
        return content["value"]
    except (InvalidToken, ValueError, KeyError, TypeError, AttributeError):
        raise DriveError("No se pudieron abrir las credenciales de esta conexión.", code="credentials") from None
