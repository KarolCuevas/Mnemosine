"""Rutas de autenticación: registro por invitación, login, logout y perfil.

Reglas: los errores de credenciales/invitación son genéricos (no revelan si la
cuenta existe); el login aplica rate limiting por IP+identidad; las mutaciones
exigen CSRF (doble envío); la sesión es revocable y expira en caliente.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut, user_to_out
from app.security import tokens
from app.security.deps import CurrentUser, get_current_user, require_csrf
from app.security.rate_limit import login_limiter
from app.services import auth_service
from app.services.errors import AuthError, ConflictError, InvitationError

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _set_auth_cookies(response: Response, raw_token: str) -> None:
    response.set_cookie(tokens.SESSION_COOKIE, raw_token, **tokens.session_cookie_kwargs())
    response.set_cookie(tokens.CSRF_COOKIE, tokens.csrf_from_session(raw_token), **tokens.csrf_cookie_kwargs())


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(tokens.SESSION_COOKIE, path="/")
    response.delete_cookie(tokens.CSRF_COOKIE, path="/")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response) -> UserOut:
    try:
        user, raw_token = auth_service.register_with_invitation(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            invitation_code=payload.invitation_code,
        )
    except InvitationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invitación no válida o caducada")
    except ConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="El usuario o el correo ya están en uso")
    _set_auth_cookies(response, raw_token)
    return user_to_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response) -> UserOut:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{client_ip}:{payload.identity.lower()}"
    if not login_limiter.check_and_hit(
        rate_key,
        limit=settings.login_rate_limit_attempts,
        window_minutes=settings.login_rate_limit_window_minutes,
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Demasiados intentos. Espera unos minutos.")
    try:
        user, raw_token = auth_service.login(identity=payload.identity, password=payload.password)
    except AuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Credenciales no válidas")
    login_limiter.reset(rate_key)
    _set_auth_cookies(response, raw_token)
    return user_to_out(user)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(response: Response, _csrf: None = Depends(require_csrf),
           current: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    auth_service.logout(session_id=current.session_id)
    _clear_auth_cookies(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current.user_id,
        username=current.username,
        email=current.email,
        display_name=current.display_name,
        role=current.role,
    )
