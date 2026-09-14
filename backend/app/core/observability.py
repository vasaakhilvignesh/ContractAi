"""
ContractIQ — Observability Utilities (Phase 19B)

Provides:
  - OperationTimer: async context manager for timing named operations with
    structured logging. Never logs secrets, contract content, or JWTs.
  - log_operation_result: helper to emit a single structured log line for
    a completed operation with duration_ms, status, and safe metadata.
  - SAFE_LOG_KEYS: whitelist of metadata keys permitted in log output.

Design principles:
  - Timing is always wall-clock (time.perf_counter) — monotonic, no drift.
  - Metadata values are filtered against a whitelist before logging.
  - No contract text, API keys, passwords, or JWTs are ever emitted.
  - All timing is best-effort: failure in observability never breaks the
    instrumented operation.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# Whitelist of metadata keys permitted in structured log output.
# Values associated with any other key are silently dropped.
SAFE_LOG_KEYS: frozenset[str] = frozenset({
    "operation",
    "duration_ms",
    "status",
    "contract_id",
    "query_length",
    "top_k",
    "matches_returned",
    "semantic_matches",
    "keyword_matches",
    "rrf_k",
    "total_chunks",
    "total_citations",
    "valid_citations",
    "invalid_citations",
    "model",
    "temperature",
    "batch_size",
    "texts_count",
    "schema",
    "has_sufficient_evidence",
    "rag_status",
    "provider",
    "request_id",
    "method",
    "route",
    "response_status",
    "error_type",
    "phase",
    "embedding_dimension",
})


def _safe_meta(metadata: dict[str, Any]) -> dict[str, Any]:
    """Returns only whitelist-approved keys from a metadata dict."""
    return {k: v for k, v in metadata.items() if k in SAFE_LOG_KEYS}


def log_operation_result(
    operation: str,
    duration_ms: float,
    status: str = "ok",
    metadata: Optional[dict[str, Any]] = None,
    level: int = logging.INFO,
) -> None:
    """
    Emits a single structured log line for a completed operation.

    Args:
        operation: Short name for the operation (e.g., "semantic_retrieval").
        duration_ms: Wall-clock duration in milliseconds.
        status: "ok" | "error" | "skipped".
        metadata: Optional dict of safe contextual information.
        level: Log level (default INFO).
    """
    safe = _safe_meta(metadata or {})
    extra = {
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "status": status,
        **safe,
    }
    msg_parts = [f"op={operation}", f"status={status}", f"duration_ms={extra['duration_ms']}"]
    for k, v in safe.items():
        if k not in ("operation", "status", "duration_ms"):
            msg_parts.append(f"{k}={v}")
    logger.log(level, " ".join(msg_parts), extra=extra)


@asynccontextmanager
async def timed_operation(
    operation: str,
    metadata: Optional[dict[str, Any]] = None,
    log_on_success: bool = True,
    log_on_error: bool = True,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Async context manager that times an operation and emits a structured
    log line on completion.

    Usage:
        async with timed_operation("semantic_retrieval", {"contract_id": cid}) as ctx:
            result = await do_work()
            ctx["matches"] = len(result)  # optionally add safe result metadata

    On success: logs at INFO with status="ok" and duration_ms.
    On exception: logs at ERROR with status="error" and error_type (class name only).
    Re-raises exceptions unchanged.

    Never logs: API keys, JWTs, DB URLs, contract text content, or passwords.
    """
    ctx: dict[str, Any] = {}
    start = time.perf_counter()
    try:
        yield ctx
        elapsed_ms = (time.perf_counter() - start) * 1000
        if log_on_success:
            merged = dict(metadata or {})
            merged.update(ctx)
            log_operation_result(
                operation=operation,
                duration_ms=elapsed_ms,
                status="ok",
                metadata=merged,
            )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if log_on_error:
            merged = dict(metadata or {})
            merged.update(ctx)
            merged["error_type"] = type(exc).__name__
            log_operation_result(
                operation=operation,
                duration_ms=elapsed_ms,
                status="error",
                metadata=merged,
                level=logging.ERROR,
            )
        raise
