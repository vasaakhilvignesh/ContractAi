"""
ContractIQ — Request ID & Latency Middleware (Phase 19A)

Attaches a correlation/request ID to every incoming HTTP request and
emits a single structured access log line per request containing:
  - request_id: UUID4 string (sourced from X-Request-ID header if provided,
    otherwise generated fresh).
  - method: HTTP method.
  - route: Templated route path (e.g. /contracts/{contract_id}) — never
    the raw URL which may contain query parameters with sensitive values.
  - response_status: HTTP response status code.
  - duration_ms: Total round-trip duration in milliseconds.

Security guarantees:
  - Never logs query string parameters (may contain tokens or PII).
  - Never logs request/response bodies.
  - Never logs Authorization headers.
  - Propagates the request_id to the response via X-Request-ID header so
    clients can correlate requests with server logs.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that:
      1. Reads X-Request-ID from the request, or generates a new UUID4.
      2. Attaches the request_id to request.state for downstream use.
      3. Emits a structured access-log line on every response.
      4. Propagates the request_id back in the X-Request-ID response header.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Resolve or generate request ID
        incoming_id = request.headers.get(REQUEST_ID_HEADER, "").strip()
        # Accept incoming ID only if it looks like a safe alphanumeric token
        if incoming_id and len(incoming_id) <= 64 and incoming_id.replace("-", "").isalnum():
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        # 2. Attach to request state (available in route handlers and services)
        request.state.request_id = request_id

        # 3. Process the request and measure total latency
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "method=%s route=%s status=500 duration_ms=%s request_id=%s error_type=%s",
                request.method,
                _safe_route(request),
                elapsed_ms,
                request_id,
                type(exc).__name__,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": _safe_route(request),
                    "response_status": 500,
                    "duration_ms": elapsed_ms,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        # 4. Emit structured access log line
        logger.info(
            "method=%s route=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            _safe_route(request),
            response.status_code,
            elapsed_ms,
            request_id,
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": _safe_route(request),
                "response_status": response.status_code,
                "duration_ms": elapsed_ms,
            },
        )

        # 5. Propagate request_id back to caller
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _safe_route(request: Request) -> str:
    """
    Returns the route template (e.g. /contracts/{contract_id}) rather than
    the raw URL path (which may embed IDs) or query string (which may embed
    tokens or filters).
    Falls back to the raw path if no route match is available.
    """
    try:
        route = request.scope.get("route")
        if route is not None and hasattr(route, "path"):
            return route.path
    except Exception:
        pass
    # Safe fallback: path only, no query string
    return request.url.path
