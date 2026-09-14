"""
ContractIQ — Structured Logging Configuration (Phase 19A)

Provides:
  - Safe structured (JSON-line) logging for production use.
  - A SafeLoggingFilter that strips Authorization headers, raw JWTs,
    API keys, and DATABASE_URL values before any log record is emitted.
  - configure_logging() — call once at application startup.

Design:
  - All log records are emitted as plain text in development (app_debug=True)
    or as compact JSON lines in production (app_debug=False).
  - The filter works at the logging layer so it catches all log records.
  - Never leaks: GEMINI_API_KEY, DATABASE_URL credentials, JWT tokens,
    Authorization headers, or raw contract document text.
"""

import json
import logging
import re
import sys
from typing import Any

from app.core.config import settings

# Secret-pattern matchers used by the log filter
_REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"(postgres(?:ql)?(?:\+[a-zA-Z0-9_-]+)?://[^:]+:)([^@]+)(@\S+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\3",
    ),
    (
        re.compile(r"Bearer\s+eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
        "Bearer [REDACTED_JWT]",
    ),
    (
        re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
        "[REDACTED_GEMINI_KEY]",
    ),
    (
        re.compile(r"(authorization:\s*)(?!Bearer\s+\[REDACTED_JWT\])(\S+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
]


def _scrub(text: str) -> str:
    if not text:
        return text
    if settings.gemini_api_key and len(settings.gemini_api_key.strip()) > 4:
        text = text.replace(settings.gemini_api_key.strip(), "[REDACTED_API_KEY]")
    if settings.database_url and len(settings.database_url.strip()) > 8:
        text = text.replace(settings.database_url.strip(), "[REDACTED_DB_URL]")
    if settings.jwt_secret_key and len(settings.jwt_secret_key.strip()) > 5:
        text = text.replace(settings.jwt_secret_key.strip(), "[REDACTED_SECRET]")
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SafeLoggingFilter(logging.Filter):
    """
    Logging filter that scrubs sensitive values from log messages and
    string-form exception text before the record is emitted.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _scrub(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    _scrub(a) if isinstance(a, str) else a for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (_scrub(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        if record.exc_text and isinstance(record.exc_text, str):
            record.exc_text = _scrub(record.exc_text)
        return True


class JSONLineFormatter(logging.Formatter):
    """
    Emits each log record as a single compact JSON line, compatible with
    Cloud Logging / Loki / Datadog structured log ingestion.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "operation", "duration_ms", "status", "route", "method"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """
    Configures the root logger for ContractIQ.

    - Development (app_debug=True): Human-readable format with INFO level.
    - Production (app_debug=False): JSON-line format with INFO level.
    - SafeLoggingFilter applied unconditionally to strip secrets.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    safe_filter = SafeLoggingFilter()
    handler.addFilter(safe_filter)

    if settings.app_debug:
        fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    else:
        handler.setFormatter(JSONLineFormatter())

    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.app_debug else logging.WARNING
    )
    logging.getLogger("google.genai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
