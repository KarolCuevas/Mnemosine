"""Dependencias FastAPI: autenticación por cookie, CSRF y rol ADMIN."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.repositories import db as repos_db
from app.repositories import sessions as sessions_repo
from app.security import tokens


@dataclass
class CurrentUser:
    user_id: int
    username: str
    email: str
    display_name: str | None
    role: str
    session_id: int
    raw_token: str


def _unauthorized(detail: str = "No autenticado") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_user(request: Request) -> CurrentUser:
    settings = get_settings()
    raw_token = request.cookies.get(tokens.SESSION_COOKIE)
    if not raw_token:
        raise _unauthorized()

    row = sessions_repo.get_active_session_with_user(tokens.hash_token(raw_token))
    if row is None:
        raise _unauthorized()
    if not row["is_active"]:
        # Cuenta desactivada con sesiones aún vivas: rechazo y revocación.
        with repos_db.transaction() as cursor:
            sessions_repo.revoke_session(cursor, row["session_id"])
        raise _unauthorized()

    created_at: datetime = row["created_at"]
    if datetime.now() - created_at > timedelta(days=settings.session_absolute_days):
        with repos_db.transaction() as cursor:
            sessions_repo.revoke_session(cursor, row["session_id"])
        raise _unauthorized("Sesión caducada; vuelve a iniciar sesión")

    sessions_repo.touch_and_extend(row["session_id"])  # expiración deslizante

    return CurrentUser(
        user_id=row["user_id"],
        username=row["username"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"],
        session_id=row["session_id"],
        raw_token=raw_token,
    )


def require_csrf(request: Request) -> None:
    raw_token = request.cookies.get(tokens.SESSION_COOKIE)
    presented = request.headers.get(tokens.CSRF_HEADER)
    if not tokens.csrf_valid(raw_token or "", presented):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF no válido")


def get_admin_user(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol de administrador")
    return current
