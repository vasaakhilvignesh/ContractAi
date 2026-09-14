"""
ContractIQ Backend — Core Configuration

Reads all application settings from environment variables.
Real credentials are never hardcoded here.

Usage:
    from app.core.config import settings
    print(settings.database_url)
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Populate a .env file (based on backend/.env.example) for local development.
    """

    # ----------------------------------------------------------------
    # Database
    # ----------------------------------------------------------------
    database_url: str = ""
    """
    Full Neon PostgreSQL connection string.
    Format: postgresql+psycopg2://user:password@host/dbname?sslmode=require
    Must be set in .env or the process environment before starting the server.
    """

    # ----------------------------------------------------------------
    # Application
    # ----------------------------------------------------------------
    app_env: str = "development"
    app_debug: bool = True
    app_name: str = "ContractIQ API"
    app_version: str = "1.0.0"

    # ----------------------------------------------------------------
    # Storage & Uploads (Phase 2B) & Document Processing (Phase 3A)
    # ----------------------------------------------------------------
    storage_dir: Path = Path(__file__).resolve().parents[2] / "storage"
    max_upload_size_bytes: int = 20 * 1024 * 1024  # 20 MB default
    allowed_upload_extensions: list[str] = [".pdf"]
    max_pdf_pages: int = 250  # Defensive maximum page count for extraction

    # ----------------------------------------------------------------
    # Embedding Provider (Phase 4A — Google Gemini)
    # ----------------------------------------------------------------
    gemini_api_key: str = ""
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = 768
    embedding_batch_size: int = 100

    # ----------------------------------------------------------------
    # Structured LLM Provider (Phase 6A — Google Gemini)
    # ----------------------------------------------------------------
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.8-flash"
    llm_temperature: float = 0.0

    # ----------------------------------------------------------------
    # Authentication & Security (Phase 13A)
    # ----------------------------------------------------------------
    jwt_secret_key: str = "contractiq-dev-insecure-secret-key-change-in-production-32bytes"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours default

    # ----------------------------------------------------------------
    # CORS & Production Origin Security (Phase 20C)
    # ----------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8443"

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """
        Enforces strict security invariants when APP_ENV=production:
          1. jwt_secret_key must not be the insecure dev default and must be >= 32 chars.
          2. database_url must be provided and non-empty.
          3. gemini_api_key must be provided and non-empty.
          4. app_debug is automatically forced to False in production.
        """
        if self.is_production:
            insecure_defaults = {
                "contractiq-dev-insecure-secret-key-change-in-production-32bytes",
                "change-this-to-a-secure-random-secret-key-in-production",
                "secret",
                "changeme",
                "password",
            }
            if (
                not self.jwt_secret_key
                or self.jwt_secret_key.strip() in insecure_defaults
                or len(self.jwt_secret_key.strip()) < 32
            ):
                raise ValueError(
                    "Production configuration error: JWT_SECRET_KEY must be set to a strong, "
                    "non-default secret of at least 32 characters when APP_ENV=production."
                )

            if not self.is_database_configured:
                raise ValueError(
                    "Production configuration error: DATABASE_URL must be configured when APP_ENV=production."
                )

            if not self.is_gemini_configured:
                raise ValueError(
                    "Production configuration error: GEMINI_API_KEY must be configured when APP_ENV=production."
                )

            if self.app_debug:
                self.app_debug = False

        return self

    @property
    def is_production(self) -> bool:
        """Returns True if the application is configured for production."""
        return self.app_env.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        """Returns parsed list of allowed CORS origin strings."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_database_configured(self) -> bool:
        """Returns True if DATABASE_URL has been provided and is non-empty."""
        return bool(self.database_url and self.database_url.strip())

    @property
    def is_gemini_configured(self) -> bool:
        """Returns True if GEMINI_API_KEY has been provided and is non-empty."""
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    @property
    def safe_database_url_summary(self) -> str:
        """
        Returns a non-sensitive summary of the database URL for logging.
        Never logs the full connection string (which contains the password).
        Example: 'postgresql+psycopg2://<user>@<host>/<dbname>'
        """
        if not self.is_database_configured:
            return "<not configured>"
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self.database_url)
            return (
                f"{parsed.scheme}://{parsed.username}@"
                f"{parsed.hostname}{parsed.path}"
            )
        except Exception:
            return "<configured — parse error>"

    @property
    def safe_gemini_key_summary(self) -> str:
        """
        Returns a masked summary of the Gemini API key for logging.
        Never logs the full secret.
        Example: 'AIza...1234'
        """
        if not self.is_gemini_configured:
            return "<not configured>"
        key = self.gemini_api_key.strip()
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    model_config = {
        "env_file": [str(Path(__file__).resolve().parents[2] / ".env"), ".env"],
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Singleton settings instance — imported throughout the application.
settings = Settings()
