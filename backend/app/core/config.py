from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "127.0.0.1"
    db_port: int = 3307
    db_name: str = "mnemosine"
    db_user: str = "mnemosine_app"
    db_password: str

    # Seguridad (Fase 2). Genera SECRET_KEY aleatorio: python -c "import secrets;print(secrets.token_hex(32))"
    secret_key: str
    session_sliding_days: int = 7      # expiración deslizante por inactividad
    session_absolute_days: int = 30    # límite absoluto desde la creación
    session_cookie_secure: bool = False  # True obligatorio tras HTTPS
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_minutes: int = 5

    # Cargas (Fase 3). D3: 50 MB por archivo, 5 GB por cuenta.
    max_upload_bytes: int = 50 * 1024 * 1024
    max_user_quota_bytes: int = 5 * 1024 * 1024 * 1024
    storage_root: str | None = None    # por defecto <repo>/storage
    musicbrainz_enabled: bool = False
    musicbrainz_contact: str = ""
    catalog_cache_seconds: int = Field(default=3600, ge=60, le=86400)
    catalog_record_ttl_days: int = Field(default=30, ge=1, le=365)
    google_drive_enabled: bool = False
    google_oauth_client_file: str = ""
    google_token_keys_file: str = ""
    google_picker_key_file: str = ""
    google_project_id: str = ""
    google_project_number: str = ""
    google_app_origin: str = "http://127.0.0.1:5173"

    @field_validator("musicbrainz_contact")
    @classmethod
    def validate_contact(cls, value: str) -> str:
        value = value.strip()
        if value and (len(value) > 250 or not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value)
                      or not ("@" in value or value.startswith("https://"))):
            raise ValueError("usa un correo o URL HTTPS de contacto sin saltos de línea")
        return value
    # Nota (Fase 5): no existe un SCAN_ROOT separado. Las fuentes registradas
    # deben vivir DENTRO de storage_root; así toda copia tiene una única
    # raíz servible y las entregas no dependen de la fuente.


@lru_cache
def get_settings() -> Settings:
    return Settings()
