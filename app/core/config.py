from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    APP_NAME: str = "Personal Notes"
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Security & Authentication
    SECRET_KEY: str = Field(
        default="personal-notes-dev-secret-key-32chars-min-security-hash",
        description="Cryptographic secret key for signing JWTs and session cookies"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    COOKIE_NAME: str = "personal_notes_session"
    COOKIE_SECURE: bool = False  # False for local HTTP, True for production HTTPS
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./personal_notes.db",
        description="Async database connection string (PostgreSQL or SQLite fallback)"
    )

    # Password Reset
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def sync_database_url(self) -> str:
        """Helper for Alembic or sync tooling if needed."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://")
        elif url.startswith("sqlite+aiosqlite:///"):
            return url.replace("sqlite+aiosqlite:///", "sqlite:///")
        return url


settings = Settings()
