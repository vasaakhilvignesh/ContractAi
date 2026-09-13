"""
ContractIQ Backend — FastAPI Application Entry Point

Phase 1 scope:
  - Application factory with lifespan
  - GET /health — verifies API process + real database connectivity

Out of scope for Phase 1:
  - Authentication middleware
  - Contract upload/ingestion endpoints
  - RAG/retrieval endpoints
  - AI analysis endpoints
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import check_database_connection
from app.schemas.health import DatabaseHealthSchema, HealthResponseSchema
from app.api.v1.contracts import router as contracts_router
from app.api.v1.analyst import router as analyst_router


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
    print(f"[ContractIQ] Starting up. DB target: {db_summary}")

    if not settings.is_database_configured:
        print(
            "[ContractIQ] WARNING: DATABASE_URL is not configured. "
            "Database-dependent endpoints will return 503."
        )
    else:
        # Perform a startup connectivity check (non-fatal — server starts regardless)
        result = check_database_connection()
        if result["connected"]:
            print(
                f"[ContractIQ] Database connected. "
                f"pgvector: {result.get('pgvector_version', 'not found')}"
            )
        else:
            print(
                f"[ContractIQ] WARNING: Database connectivity check failed: "
                f"{result.get('error', 'unknown error')}"
            )

    yield

    # --- Shutdown ---
    print("[ContractIQ] Shutting down.")


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
    # CORS — Development configuration.
    # In production (Phase 5+), restrict allow_origins to the deployed
    # frontend domain.
    # ----------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ----------------------------------------------------------------
    # Routes
    # ----------------------------------------------------------------
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all application routes."""

    # Register domain routers
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
        )

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
