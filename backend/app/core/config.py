from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
