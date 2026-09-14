"""
ContractIQ — Core Security & Secret Masking Utilities (Phase 18D)

Provides:
  - Secret masking and scrubbing for exception strings, error payloads, and logs.
  - Ensures DATABASE_URL, GEMINI_API_KEY, JWT secrets, and connection credentials never leak.
"""

import re
from typing import Optional

from app.core.config import settings


def mask_secrets(text: Optional[str]) -> str:
    """
    Scrubs sensitive credentials, connection strings, and API keys from a text message.
    Safe for use on exception messages before returning to clients or writing to logs.
    """
    if not text:
        return ""

    sanitized = str(text)

    # 1. Mask active Gemini API Key if configured
    if settings.gemini_api_key and len(settings.gemini_api_key.strip()) > 4:
        sanitized = sanitized.replace(settings.gemini_api_key.strip(), "[REDACTED_API_KEY]")

    # 2. Mask active Database URL if configured
    if settings.database_url and len(settings.database_url.strip()) > 8:
        sanitized = sanitized.replace(settings.database_url.strip(), "[REDACTED_DB_URL]")

    # 3. Mask JWT secret key if configured
    if settings.jwt_secret_key and len(settings.jwt_secret_key.strip()) > 5:
        sanitized = sanitized.replace(settings.jwt_secret_key.strip(), "[REDACTED_SECRET]")

    # 4. Regex pattern scrub for database connection strings: postgresql://user:password@host/db
    sanitized = re.sub(
        r"(postgres(?:ql)?(?:\+[a-zA-Z0-9_-]+)?://[^:]+:)([^@]+)(@[^\s\"'\)]+)",
        r"\1[REDACTED]\3",
        sanitized,
        flags=re.IGNORECASE,
    )

    # 5. Regex pattern scrub for standard API key formats (AIza..., Bearer eyJ...)
    sanitized = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_GEMINI_KEY]", sanitized)
    sanitized = re.sub(r"Bearer\s+eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+", "Bearer [REDACTED_JWT]", sanitized)

    return sanitized
