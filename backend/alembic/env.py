"""
ContractIQ — Alembic Migration Environment

This file configures Alembic to:
  1. Read DATABASE_URL from the environment (never from alembic.ini).
  2. Import all SQLAlchemy models so that autogenerate detects them.
  3. Run migrations in online mode against the configured database.

Offline mode (--sql flag) is supported but not the primary workflow.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ====================================================================
# Ensure `backend/` is on sys.path so `app.*` imports resolve correctly
# when Alembic is run from the `backend/` directory.
# ====================================================================
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ====================================================================
# Load application configuration and all models
# ====================================================================
from app.core.config import settings  # noqa: E402
from app.db.base import Base           # noqa: E402

# CRITICAL: Import all model modules so that Alembic's autogenerate
# can detect all mapped tables in Base.metadata.
import app.models  # noqa: E402, F401  — side-effect import to populate Base.metadata

# ====================================================================
# Alembic Config object (access to alembic.ini values)
# ====================================================================
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ====================================================================
# Inject DATABASE_URL from environment (overrides blank alembic.ini value)
# ====================================================================
_database_url = settings.database_url

if not _database_url:
    raise RuntimeError(
        "\n\n"
        "  DATABASE_URL is not set.\n"
        "  Alembic requires a database connection to generate or apply migrations.\n"
        "  Set DATABASE_URL in backend/.env (copy backend/.env.example) "
        "or in the process environment.\n"
    )

config.set_main_option("sqlalchemy.url", _database_url)

# Target metadata for autogenerate
target_metadata = Base.metadata


# ====================================================================
# Offline migration mode
# ====================================================================

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL without a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ====================================================================
# Online migration mode (default)
# ====================================================================

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Connects to the live database and applies migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,       # Detect column type changes
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ====================================================================
# Entry point
# ====================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
