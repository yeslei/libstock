from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
    )

    jwt_secret_key: str = Field(
        default="development-only-secret-change-before-production",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "libstock-api"
    jwt_audience: str = "libstock-web"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)

    cors_origins: list[str] = ["http://localhost:4200"]

    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def empty_cookie_domain_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver_for_postgres(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("cookie_samesite")
    @classmethod
    def secure_cookie_required_for_samesite_none(cls, value: str, info):
        if value == "none" and not info.data.get("cookie_secure", False):
            raise ValueError("COOKIE_SECURE must be true when COOKIE_SAMESITE is none")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
