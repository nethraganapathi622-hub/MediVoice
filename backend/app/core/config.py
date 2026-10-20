from functools import lru_cache
import os
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "MediVoice API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS configuration
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Discrete PostgreSQL connection fields
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_DB: Optional[str] = None

    # Full database connection strings
    DATABASE_URL: Optional[str] = None
    DATABASE_CONNECT_TIMEOUT: int = 5
    TEST_DATABASE_URL: Optional[str] = None

    # Security & Staff Authentication
    SECRET_KEY: str = "medivoice-insecure-dev-secret-key-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours

    # AI Voice Assistant & Emergency Configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EMERGENCY_CONTACT_PHONE: str = "+91 (44) 2829 0200"
    EMERGENCY_AMBULANCE_NUMBER: str = "108"
    ASSISTANT_SESSION_TTL_MINUTES: int = 60
    NOTIFICATION_WEBHOOK_URL: Optional[str] = None

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        """Assemble DATABASE_URL from discrete fields if provided, safely encoding special characters."""
        if self.POSTGRES_USER and self.POSTGRES_DB:
            # Construct URL using SQLAlchemy URL.create which safely percent-encodes passwords
            # containing special characters (@, #, %, !, &, ?, etc.)
            db_url = URL.create(
                drivername="postgresql+psycopg2",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD or "",
                host=self.POSTGRES_HOST or "localhost",
                port=self.POSTGRES_PORT or 5432,
                database=self.POSTGRES_DB,
            ).render_as_string(hide_password=False)
            self.DATABASE_URL = db_url
        elif not self.DATABASE_URL:
            self.DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/medivoice_db"

        if self.DATABASE_URL:
            # Clean accidental repeated variable prefix or whitespace/quotes
            clean_url = self.DATABASE_URL.strip()
            while clean_url.startswith("DATABASE_URL="):
                clean_url = clean_url[len("DATABASE_URL="):].strip()
            if (clean_url.startswith('"') and clean_url.endswith('"')) or (
                clean_url.startswith("'") and clean_url.endswith("'")
            ):
                clean_url = clean_url[1:-1].strip()
            self.DATABASE_URL = clean_url

        # Validate that the assembled DATABASE_URL is parseable
        try:
            make_url(self.DATABASE_URL)
        except Exception as e:
            raise ValueError(f"Invalid DATABASE_URL configuration: {type(e).__name__}")

        # Enforce strong SECRET_KEY in production mode
        if self.ENVIRONMENT == "production":
            if (
                not self.SECRET_KEY
                or self.SECRET_KEY.startswith("medivoice-insecure-dev")
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError(
                    "Production security error: SECRET_KEY must be set to a strong, random secret of at least 32 characters in production."
                )

        return self

    @property
    def safe_database_url(self) -> str:
        """Return database URL with password masked for safe diagnostic logging."""
        try:
            return make_url(self.DATABASE_URL).render_as_string(hide_password=True)
        except Exception:
            return "postgresql://***:***@localhost:5432/medivoice_db"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
