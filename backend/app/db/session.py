"""
ContractIQ Backend — Database Session Configuration

Creates the SQLAlchemy engine and session factory from DATABASE_URL.
Neon PostgreSQL requires SSL; the connection string must include
?sslmode=require (or equivalent).

Usage:
    from app.db.session import get_db

    # In a FastAPI route dependency:
    @app.get("/example")
    def example(db: Session = Depends(get_db)):
        ...
"""

from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings


def _build_engine():
    """
    Build the SQLAlchemy engine only if DATABASE_URL is configured.
    Returns None if DATABASE_URL is not set (prevents startup crash during
    scaffolding or test runs that don't need a real DB).
    """
    if not settings.is_database_configured:
        return None

    return create_engine(
        settings.database_url,
        # Neon PostgreSQL serverless connections can be recycled frequently.
        pool_pre_ping=True,        # Verifies connection health before use
        pool_size=5,               # Small pool — suitable for serverless Neon
        max_overflow=10,
        pool_recycle=300,          # Recycle connections every 5 minutes
        echo=settings.app_debug,   # Log SQL in development; set False in production
        connect_args={
            # Neon enforces SSL; redundant if already in connection string
            # but safe to declare explicitly.
            "connect_timeout": 10,
        },
    )


# Engine — None if DATABASE_URL is not configured.
engine = _build_engine()

# Session factory — bound to engine if available.
SessionLocal: sessionmaker | None = (
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
    if engine is not None
    else None
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.

    Raises RuntimeError if DATABASE_URL is not configured so that
    routes that require a database fail early with a clear error
    rather than a cryptic AttributeError.
    """
    if SessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set DATABASE_URL in backend/.env before starting the server."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> dict:
    """
    Performs a lightweight health check against the database.

    Returns a dict with:
      - connected: bool
      - pg_version: str | None
      - pgvector_version: str | None
      - error: str | None (non-sensitive message only)

    Never exposes the DATABASE_URL or credentials in the return value.
    """
    if engine is None:
        return {
            "connected": False,
            "pg_version": None,
            "pgvector_version": None,
            "error": "DATABASE_URL is not configured.",
        }

    try:
        with engine.connect() as conn:
            pg_version_row = conn.execute(text("SELECT version()")).scalar()
            # pgvector availability — check if the extension is installed
            pgvector_row = conn.execute(
                text(
                    "SELECT extversion FROM pg_extension "
                    "WHERE extname = 'vector'"
                )
            ).scalar()

        return {
            "connected": True,
            "pg_version": str(pg_version_row) if pg_version_row else None,
            "pgvector_version": str(pgvector_row) if pgvector_row else None,
            "error": None,
        }
    except Exception as exc:
        # Return a safe, non-credential-exposing error message.
        return {
            "connected": False,
            "pg_version": None,
            "pgvector_version": None,
            "error": f"Database connection failed: {type(exc).__name__}",
        }
