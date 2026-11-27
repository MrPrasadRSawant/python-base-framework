import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


def _split_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Base API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = []

    # --- Database ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app_db"

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "text"  # console format; log files are always JSON
    LOG_TO_FILE: bool = True
    LOG_DIR: Path = Path("logs")
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_FILE_BACKUP_COUNT: int = 5
    LOG_SQL: bool = False
    LOG_REQUEST_BODY_ON_ERROR: bool = True
    LOG_MAX_BODY_BYTES: int = 4096

    # --- Log tables (in addition to the log files) ---
    EXCEPTION_LOG_DB_ENABLED: bool = True
    EXCEPTION_LOG_DB_MIN_STATUS: int = 400  # 500 -> store server errors only
    REQUEST_LOG_DB_ENABLED: bool = True
    REQUEST_LOG_EXCLUDE_PATHS: Annotated[list[str], NoDecode] = ["/api/v1/health"]
    SERVICE_CALL_LOG_DB_ENABLED: bool = True  # rows from @track_service
    # Background writer shared by all log tables
    DB_LOG_QUEUE_SIZE: int = 10_000
    DB_LOG_BATCH_SIZE: int = 50
    DB_LOG_FLUSH_INTERVAL: float = 1.0  # seconds

    # Read-only APIs over the log tables. Put them behind auth before enabling in production.
    EXCEPTION_LOG_API_ENABLED: bool = False
    REQUEST_LOG_API_ENABLED: bool = False
    SERVICE_CALL_LOG_API_ENABLED: bool = False

    # --- Pagination / search ---
    PAGINATION_DEFAULT_LIMIT: int = 20
    PAGINATION_MAX_LIMIT: int = 100
    SEARCH_MAX_FILTERS: int = 20
    SEARCH_MAX_IN_VALUES: int = 100

    # --- Request tracing ---
    REQUEST_ID_HEADER: str = "X-Request-ID"

    # --- Redaction ---
    REDACT_EXTRA_KEYS: Annotated[list[str], NoDecode] = []
    REDACT_EMAILS: bool = True

    # --- Authentication ---
    # Required, at least 32 characters. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_ISSUER: str = "base-api"
    ACCESS_TOKEN_TTL_MINUTES: int = Field(15, ge=1)
    LOGIN_MAX_FAILED: int = Field(5, ge=1)  # failed logins in a row before the lock
    LOGIN_LOCK_MINUTES: int = Field(15, ge=1)
    # POST /auth/register open to anyone. Keep false unless the app allows sign-up.
    AUTH_SELF_REGISTRATION_ENABLED: bool = False
    # Local development only: create the two documented demo accounts on startup.
    DEV_SEED_ACCOUNTS: bool = False
    # Refresh token: opaque, stored hashed, sent as an HttpOnly cookie scoped to /auth.
    REFRESH_TOKEN_TTL_DAYS: int = Field(7, ge=1)
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = True  # HTTPS only (browsers allow it on http://localhost)
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    # Access tokens issued to API clients (client credentials grant). No refresh token.
    SERVICE_TOKEN_TTL_MINUTES: int = Field(15, ge=1)

    # --- Rate limiting (per client IP, in memory per worker; "<n>/<second|minute|hour>") ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "10/minute"  # /auth/login and /auth/token password grant
    RATE_LIMIT_REGISTER: str = "5/minute"
    RATE_LIMIT_REFRESH: str = "30/minute"
    RATE_LIMIT_TOKEN: str = "60/minute"  # /auth/token client_credentials, per IP
    RATE_LIMIT_TOKEN_PER_CLIENT: str = "30/minute"  # ... and per client_id

    @field_validator(
        "RATE_LIMIT_LOGIN",
        "RATE_LIMIT_REGISTER",
        "RATE_LIMIT_REFRESH",
        "RATE_LIMIT_TOKEN",
        "RATE_LIMIT_TOKEN_PER_CLIENT",
    )
    @classmethod
    def check_rate_rule(cls, value: str) -> str:
        if not re.fullmatch(r"\s*\d+\s*/\s*(second|minute|hour)\s*", value):
            raise ValueError("use '<count>/<second|minute|hour>', e.g. '10/minute'")
        return value

    @field_validator(
        "CORS_ORIGINS", "REDACT_EXTRA_KEYS", "REQUEST_LOG_EXCLUDE_PATHS", mode="before"
    )
    @classmethod
    def split_csv(cls, value: str | list[str]) -> list[str]:
        return _split_csv(value)

    @field_validator("LOG_DIR", mode="after")
    @classmethod
    def resolve_log_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else BASE_DIR / value

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
