from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import computed_field, field_validator
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
    # Background writer used by both tables
    DB_LOG_QUEUE_SIZE: int = 10_000
    DB_LOG_BATCH_SIZE: int = 50
    DB_LOG_FLUSH_INTERVAL: float = 1.0  # seconds

    # Read-only API over exception_log. Put it behind auth before enabling in production.
    EXCEPTION_LOG_API_ENABLED: bool = False

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
