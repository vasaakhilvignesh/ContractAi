"""
ContractIQ — Tests for /health endpoint

Tests:
  1. Health endpoint is reachable (no database required).
  2. Response structure is correct.
  3. Status field is "ok" or "degraded" (never absent).
  4. Database health sub-object is always present.
  5. Credentials are never leaked in the response.
  6. When DATABASE_URL is not configured, status is "degraded".
  7. When DATABASE_URL is configured, database connectivity is verified (db marker).
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_endpoint_is_reachable(self, test_client: TestClient):
        """Health endpoint must return 200 regardless of DB state."""
        response = test_client.get("/health")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text}"
        )

    def test_health_response_is_valid_json(self, test_client: TestClient):
        """Response must be valid JSON."""
        response = test_client.get("/health")
        data = response.json()
        assert isinstance(data, dict), "Response body must be a JSON object"

    def test_health_response_has_required_fields(self, test_client: TestClient):
        """Response must contain status, version, and database fields."""
        response = test_client.get("/health")
        data = response.json()
        assert "status" in data, "Response must contain 'status'"
        assert "version" in data, "Response must contain 'version'"
        assert "database" in data, "Response must contain 'database'"

    def test_health_status_is_ok_or_degraded(self, test_client: TestClient):
        """status field must be 'ok' or 'degraded'."""
        response = test_client.get("/health")
        data = response.json()
        assert data["status"] in ("ok", "degraded"), (
            f"status must be 'ok' or 'degraded', got {data['status']!r}"
        )

    def test_health_database_sub_object_structure(self, test_client: TestClient):
        """database sub-object must have 'connected' boolean field."""
        response = test_client.get("/health")
        data = response.json()
        db = data["database"]
        assert isinstance(db, dict), "database field must be an object"
        assert "connected" in db, "database must have 'connected' field"
        assert isinstance(db["connected"], bool), "connected must be a boolean"

    def test_health_no_credentials_in_response(self, test_client: TestClient):
        """Database credentials must never appear in /health response."""
        response = test_client.get("/health")
        text = response.text.lower()

        # Passwords should never appear — we check for common patterns
        # but cannot check for the actual credential since we don't have it.
        # What we CAN ensure: DATABASE_URL as a raw value is not echoed.
        import os
        db_url = os.environ.get("DATABASE_URL", "")
        if "@" in db_url:
            # Extract password fragment (between ':' and '@' after the user segment)
            try:
                # postgresql://user:PASSWORD@host/db
                creds_part = db_url.split("://")[1].split("@")[0]
                if ":" in creds_part:
                    password = creds_part.split(":", 1)[1]
                    if password:
                        assert password not in response.text, (
                            "DATABASE password must not appear in /health response"
                        )
            except (IndexError, AttributeError):
                pass  # If parsing fails, we cannot check — not a test failure

    def test_health_version_is_string(self, test_client: TestClient):
        """version must be a non-empty string."""
        response = test_client.get("/health")
        data = response.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_without_db_is_degraded(self, test_client: TestClient, database_url, monkeypatch):
        """When database connection fails or is disconnected, status should be 'degraded'."""
        if database_url:
            import app.main
            monkeypatch.setattr(
                app.main,
                "check_database_connection",
                lambda: {
                    "connected": False,
                    "pg_version": None,
                    "pgvector_version": None,
                    "error": "Simulated connection error",
                },
            )
        response = test_client.get("/health")
        data = response.json()
        assert data["status"] == "degraded", (
            "Without DATABASE_URL or on connection failure, status should be 'degraded'"
        )
        assert data["database"]["connected"] is False

    @pytest.mark.db
    def test_health_with_real_db_is_ok(self, test_client: TestClient, database_url):
        """When DATABASE_URL is configured and DB is reachable, status should be 'ok'."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")
        response = test_client.get("/health")
        data = response.json()
        assert data["status"] == "ok", (
            f"With DATABASE_URL configured, expected 'ok', got: {data}"
        )
        assert data["database"]["connected"] is True
        assert data["database"]["pg_version"] is not None
        assert data["database"]["pgvector_version"] is not None, (
            "pgvector must be installed and verified in Neon database"
        )
