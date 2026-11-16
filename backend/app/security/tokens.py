"""Tokens de sesión opacos y CSRF por doble envío con HMAC (D4).

- El token de sesión es aleatorio; en la base solo se guarda su SHA-256
  (USER_SESSION.token_hash), nunca el valor que viaja en la cookie.
- El token CSRF es HMAC_SHA256(secret_key, token_crudo): cualquier cliente que
  lea la cookie mnemosine_csrf (no HttpOnly) puede enviarlo en X-CSRF-Token;
  un sitio externo no puede calcularlo sin secret_key ni leer la cookie.
- Comparaciones con compare_digest (tiempo constante).
"""

import hashlib
import hmac
import secrets
from typing import Literal

from app.core.config import get_settings

SESSION_COOKIE = "mnemosine_session"
CSRF_COOKIE = "mnemosine_csrf"
CSRF_HEADER = "x-csrf-token"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_from_session(raw_token: str) -> str:
    settings = get_settings()
    return hmac.new(settings.secret_key.encode("utf-8"), raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def csrf_valid(raw_token: str, presented: str | None) -> bool:
    if not presented:
        return False
    expected = csrf_from_session(raw_token)
    return hmac.compare_digest(expected, presented)


def session_cookie_kwargs() -> dict:
    settings = get_settings()
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.session_cookie_secure,
        "path": "/",
        "max_age": settings.session_absolute_days * 24 * 3600,
    }


def csrf_cookie_kwargs() -> dict:
    settings = get_settings()
    return {
        "httponly": False,  # legible por JS: patrón doble envío
        "samesite": "lax",
        "secure": settings.session_cookie_secure,
        "path": "/",
        "max_age": settings.session_absolute_days * 24 * 3600,
    }


CookieName = Literal["mnemosine_session", "mnemosine_csrf"]
