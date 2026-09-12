"""
ContractIQ — Test Configuration (conftest.py)

Shared pytest fixtures for the backend test suite.

Design decisions:
  - Tests do NOT require a real database connection.
    Any test that needs database connectivity is marked with @pytest.mark.db
    and is skipped if DATABASE_URL is not configured.
  - The FastAPI test client uses httpx.AsyncClient via httpx's ASGI transport.
  - No test secrets are committed to the repository.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    """
    Returns an httpx TestClient for the FastAPI app.
    Tests using this fixture do NOT require a database connection.
    """
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="session")
def database_url() -> str | None:
    """
    Returns the DATABASE_URL from the environment/settings, or None if not configured.
    Used to skip database-dependent tests gracefully.
    """
    if settings.is_database_configured:
        return settings.database_url
    return os.environ.get("DATABASE_URL") or None


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "db: marks tests that require a live database connection "
        "(skipped if DATABASE_URL is not set)",
    )
