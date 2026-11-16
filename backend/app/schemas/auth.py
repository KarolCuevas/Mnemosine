import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 12
PASSWORD_MAX = 256


def _validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN:
        raise ValueError(f"la contraseña debe tener al menos {PASSWORD_MIN} caracteres")
    if len(value) > PASSWORD_MAX:
        raise ValueError("la contraseña es demasiado larga")
    if value.strip() != value or " " in value:
        raise ValueError("la contraseña no debe contener espacios")
    return value


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=255)
    password: str
    display_name: str | None = Field(default=None, max_length=255)
    invitation_code: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("el usuario solo puede usar letras, números, '.', '_' y '-'")
        return value.lower()

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("correo no válido")
        return value

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        return _validate_password(value)


class LoginRequest(BaseModel):
    identity: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None = None
    display_name: str | None = None
    role: str


class MessageOut(BaseModel):
    detail: str


class InvitationOut(BaseModel):
    code: str
    expires_at: datetime


class InvitationRequest(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)


def user_to_out(user: dict) -> UserOut:
    return UserOut(
        id=user["user_id"],
        username=user["username"],
        email=user.get("email"),
        display_name=user.get("display_name"),
        role=user["role"],
    )
