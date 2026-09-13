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
from pydantic import field_validator


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
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.0



    @field_validator("database_url")
    @classmethod
    def database_url_must_not_be_empty_in_production(
        cls, v: str, info: object
    ) -> str:
        # Allow empty string in development for scaffolding/test purposes.
        # Production readiness check is done at startup in main.py.
        return v

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
