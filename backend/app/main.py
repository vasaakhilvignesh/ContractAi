"""
ContractIQ Backend — FastAPI Application Entry Point

Phase 1 scope:
  - Application factory with lifespan
  - GET /health — verifies API process + real database connectivity

Phase 19 additions:
  - Structured logging via configure_logging() (19A)
  - Request ID / latency middleware via RequestIDMiddleware (19A)
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.security import mask_secrets
from app.db.session import check_database_connection
from app.middleware.request_id import RequestIDMiddleware
from app.schemas.health import DatabaseHealthSchema, HealthResponseSchema, ReadinessResponseSchema
from app.api.v1.contracts import router as contracts_router
from app.api.v1.analyst import router as analyst_router
from app.api.v1.comparison import router as comparison_router
from app.api.v1.obligations import router as obligations_router
from app.api.v1.auth import router as auth_router

# Configure structured logging before any logger is used.
configure_logging()
_startup_logger = logging.getLogger(__name__)


# ====================================================================
# Lifespan (startup / shutdown)
# ====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Runs startup logic before yield, shutdown logic after.
    """
    # --- Startup ---
    db_summary = settings.safe_database_url_summary
    _startup_logger.info("[ContractIQ] Starting up. DB target: %s", db_summary)

    if not settings.is_database_configured:
        _startup_logger.warning(
            "[ContractIQ] DATABASE_URL is not configured. "
            "Database-dependent endpoints will return 503."
        )
    else:
        result = check_database_connection()
        if result["connected"]:
            _startup_logger.info(
                "[ContractIQ] Database connected. pgvector: %s",
                result.get("pgvector_version", "not found"),
            )
        else:
            _startup_logger.warning(
                "[ContractIQ] Database connectivity check failed: %s",
                result.get("error", "unknown error"),
            )

    yield

    # --- Shutdown ---
    _startup_logger.info("[ContractIQ] Shutting down.")


# ====================================================================
# Application Factory
# ====================================================================

def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "ContractIQ — Evidence-First Contract Intelligence and Risk Analysis Platform. "
            "Phase 1: Backend Foundation + Database Layer."
        ),
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # ----------------------------------------------------------------
    # CORS — Production & Development origin handling (Phase 20C)
    # Never uses unrestricted wildcard allow_origins with credentials.
    # In production, uses explicitly configured origins (CORS_ORIGINS).
    # In development, permits local dev origins by default.
    # ----------------------------------------------------------------
    cors_allowed_origins = (
        settings.cors_origins_list
        if settings.is_production
        else (settings.cors_origins_list or ["http://localhost:5173", "http://localhost:3000", "http://localhost:8443"])
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ----------------------------------------------------------------
    # Request ID & Latency Middleware (Phase 19A)
    # Attaches a correlation ID to every request and emits a single
    # structured access-log line per response.  Must be added AFTER
    # CORS middleware so it wraps the full request lifecycle.
    # ----------------------------------------------------------------
    app.add_middleware(RequestIDMiddleware)

    # ----------------------------------------------------------------
    # Security & Error Reliability (Phase 18D)
    # Global exception handlers ensure credentials, database URLs,
    # and internal secrets are scrubbed before returning to the client.
    # ----------------------------------------------------------------
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = mask_secrets(str(exc.detail)) if isinstance(exc.detail, str) else exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        masked_error = mask_secrets(str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal server error: {masked_error}"},
        )

    # ----------------------------------------------------------------
    # Routes
    # ----------------------------------------------------------------
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all application routes."""

    # Register domain routers
    # Note: comparison_router and obligations_router must precede contracts_router generic routes
    app.include_router(auth_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(comparison_router)
    app.include_router(comparison_router, prefix="/api/v1")
    app.include_router(obligations_router)
    app.include_router(obligations_router, prefix="/api/v1")
    app.include_router(contracts_router)
    app.include_router(contracts_router, prefix="/api/v1")
    app.include_router(analyst_router)
    app.include_router(analyst_router, prefix="/api/v1")

    @app.get(
        "/health",
        response_model=HealthResponseSchema,
        tags=["System"],
        summary="API and database health check",
        description=(
            "Returns the health status of the API process and database connection. "
            "Performs a real database round-trip to verify connectivity. "
            "Never exposes database credentials in the response."
        ),
    )
    def health_check() -> HealthResponseSchema:
        """
        GET /health

        Returns:
          - status: 'ok' if both API and DB are healthy; 'degraded' otherwise.
          - version: Application version.
          - database: Database connectivity details (no credentials).
          - environment: Current app environment.
          - llm_configured: Boolean flag indicating if Gemini is configured.
          - llm_model: Configured LLM model name.
          - embedding_configured: Boolean flag indicating if embedding provider is configured.
          - embedding_model: Configured embedding model name.
        """
        db_result = check_database_connection()

        db_health = DatabaseHealthSchema(
            connected=db_result["connected"],
            pg_version=db_result.get("pg_version"),
            pgvector_version=db_result.get("pgvector_version"),
            error=db_result.get("error"),
        )

        overall_status = "ok" if db_result["connected"] else "degraded"

        return HealthResponseSchema(
            status=overall_status,
            version=settings.app_version,
            database=db_health,
            environment=settings.app_env,
            llm_configured=settings.is_gemini_configured,
            llm_model=settings.llm_model,
            embedding_configured=settings.is_gemini_configured,
            embedding_model=settings.embedding_model,
        )

    @app.get(
        "/health/liveness",
        tags=["System"],
        summary="Process liveness probe",
        description="Returns 200 OK if the API server process is running and able to handle requests.",
    )
    def liveness_check() -> dict:
        return {"status": "alive", "version": settings.app_version}

    @app.get(
        "/health/readiness",
        response_model=ReadinessResponseSchema,
        tags=["System"],
        summary="Dependency readiness probe",
        description="Returns 200 OK if the application and required database dependency are ready to accept traffic; 503 otherwise.",
    )
    def readiness_check() -> JSONResponse:
        db_result = check_database_connection()
        is_ready = bool(db_result.get("connected"))
        status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
        payload = {
            "status": "ready" if is_ready else "not_ready",
            "database_connected": is_ready,
            "ready": is_ready,
        }
        return JSONResponse(status_code=status_code, content=payload)

    @app.get(
        "/",
        tags=["System"],
        include_in_schema=False,
    )
    def root() -> dict:
        return {
            "project": "ContractIQ",
            "phase": "Phase 2A — Contract API Foundation",
            "docs": "/docs",
            "health": "/health",
            "contracts": "/contracts",
        }


# ====================================================================
# Application Instance
# ====================================================================

app = create_app()
