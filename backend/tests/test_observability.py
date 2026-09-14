"""
ContractIQ — Performance & Observability Test Suite (Phase 19)

Covers:
  - 19A: Request ID generation, propagation, and correlation
  - 19A: Structured logging and SafeLoggingFilter secret scrubbing
  - 19B: Provider metrics, latency instrumentation, and whitelist filtering
  - 19C: Performance composite indexes verification
  - 19D: Safe error handling and non-leakage of credentials
  - 19E: Health, readiness, and liveness probe behavior
"""

import json
import logging
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import JSONLineFormatter, SafeLoggingFilter, _scrub
from app.core.observability import SAFE_LOG_KEYS, log_operation_result, timed_operation
from app.main import app
from app.services.gemini_structured_output_provider import GeminiStructuredOutputProvider
from app.services.structured_output_validator import StructuredOutputProviderError


class DummySchema(BaseModel):
    name: str
    score: float


# ====================================================================
# 19A: Request ID & Correlation Tests
# ====================================================================

class TestRequestIDPropagation:
    def test_request_generates_x_request_id_header(self):
        client = TestClient(app)
        response = client.get("/health/liveness")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        req_id = response.headers["x-request-id"]
        assert len(req_id) > 10
        # Valid UUID string check
        parsed = uuid.UUID(req_id)
        assert str(parsed) == req_id

    def test_client_supplied_request_id_is_preserved(self):
        client = TestClient(app)
        custom_id = "trace-contractiq-client-12345"
        response = client.get("/health/liveness", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("x-request-id") == custom_id

    def test_malformed_oversized_request_id_is_sanitized(self):
        client = TestClient(app)
        dangerous_id = "bad-id-with-special-chars-&&&-" + ("a" * 100)
        response = client.get("/health/liveness", headers={"X-Request-ID": dangerous_id})
        assert response.status_code == 200
        echoed_id = response.headers.get("x-request-id")
        assert echoed_id != dangerous_id
        # Replaced with a valid UUID4
        uuid.UUID(echoed_id)


# ====================================================================
# 19A: Structured Logging & Safe Secret Filter Tests
# ====================================================================

class TestStructuredLoggingAndSecretFiltering:
    def test_scrub_removes_database_url_credentials(self):
        fake_db = "postgresql+psycopg2://admin:super_secret_pw123@prod-db.example.com:5432/contracts_db"
        result = _scrub(f"Connecting to {fake_db}")
        assert "super_secret_pw123" not in result
        assert "[REDACTED]" in result

    def test_scrub_removes_bearer_jwt_tokens(self):
        token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature"
        msg = f"Incoming authorization: {token}"
        result = _scrub(msg)
        assert "doNotLeakThisSignature" not in result
        assert "Bearer [REDACTED_JWT]" in result

    def test_scrub_removes_google_aiza_keys(self):
        fake_key = "AIzaSyD-" + ("X" * 31)
        msg = f"Calling Gemini API with key {fake_key}"
        result = _scrub(msg)
        assert fake_key not in result
        assert "[REDACTED_GEMINI_KEY]" in result

    def test_safe_logging_filter_scrubs_log_record(self):
        log_filter = SafeLoggingFilter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Connection string: postgresql://user:my_secret_pass@db.internal:5432/testdb",
            args=(),
            exc_info=None,
        )
        log_filter.filter(record)
        assert "my_secret_pass" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_json_line_formatter_emits_valid_json_with_extras(self):
        formatter = JSONLineFormatter()
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Operation completed successfully",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-abc-123"
        record.operation = "test_op"
        record.duration_ms = 42.5
        record.status = "ok"

        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "app.test"
        assert parsed["message"] == "Operation completed successfully"
        assert parsed["request_id"] == "req-abc-123"
        assert parsed["operation"] == "test_op"
        assert parsed["duration_ms"] == 42.5
        assert parsed["status"] == "ok"


# ====================================================================
# 19B: Latency & Provider Observability Instrumentation Tests
# ====================================================================

class TestObservabilityInstrumentation:
    @pytest.mark.asyncio
    async def test_timed_operation_records_duration_and_emits_log(self, caplog):
        caplog.set_level(logging.INFO)
        async with timed_operation("test_work", {"top_k": 5}) as ctx:
            time.sleep(0.02)
            ctx["matches_returned"] = 3

        # Check emitted logs
        records = [r for r in caplog.records if getattr(r, "operation", "") == "test_work"]
        assert len(records) == 1
        rec = records[0]
        assert rec.status == "ok"
        assert rec.duration_ms >= 15.0
        assert rec.top_k == 5
        assert rec.matches_returned == 3

    @pytest.mark.asyncio
    async def test_timed_operation_captures_error_and_reraises(self, caplog):
        caplog.set_level(logging.ERROR)
        with pytest.raises(ValueError, match="Expected failure"):
            async with timed_operation("failing_work", {"phase": "test"}):
                raise ValueError("Expected failure")

        records = [r for r in caplog.records if getattr(r, "operation", "") == "failing_work"]
        assert len(records) == 1
        rec = records[0]
        assert rec.status == "error"
        assert rec.error_type == "ValueError"

    def test_log_operation_result_filters_non_whitelisted_metadata(self, caplog):
        caplog.set_level(logging.INFO)
        log_operation_result(
            operation="vector_search",
            duration_ms=12.3,
            status="ok",
            metadata={
                "top_k": 10,
                "unauthorized_key": "should_not_appear_in_extra",
                "secret_param": "super_secret_data",
            },
        )
        rec = [r for r in caplog.records if getattr(r, "operation", "") == "vector_search"][0]
        assert getattr(rec, "top_k", None) == 10
        assert not hasattr(rec, "unauthorized_key")
        assert not hasattr(rec, "secret_param")

    @pytest.mark.asyncio
    async def test_gemini_structured_output_provider_observability_on_failure(self, caplog):
        caplog.set_level(logging.ERROR)
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Simulated Gemini upstream failure")
        )

        provider = GeminiStructuredOutputProvider(
            api_key="mock-key",
            model_name="gemini-3.8-flash",
            client=mock_client,
        )

        with pytest.raises(StructuredOutputProviderError):
            await provider.generate_structured(
                prompt="Extract data",
                schema=DummySchema,
            )

        err_records = [
            r for r in caplog.records
            if getattr(r, "operation", "") == "gemini_structured_llm_call"
        ]
        assert len(err_records) == 1
        assert err_records[0].status == "error"
        assert err_records[0].model == "gemini-3.8-flash"
        assert err_records[0].schema == "DummySchema"


# ====================================================================
# 19C: Database Composite Indexes Verification
# ====================================================================

class TestPerformanceIndexes:
    def test_composite_indexes_exist_in_migration_graph(self):
        """Verify that migration f31920b7c102 is present and defines required indexes."""
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config("backend/alembic.ini")
        cfg.set_main_option("script_location", "backend/alembic")
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        assert head == "f31920b7c102"

        rev = script.get_revision("f31920b7c102")
        assert rev is not None
        assert "composite_indexes" in rev.doc.lower()


# ====================================================================
# 19E: Health, Readiness & Liveness Probes
# ====================================================================

class TestHealthReadinessLivenessProbes:
    def test_liveness_returns_200_alive(self):
        client = TestClient(app)
        response = client.get("/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "version" in data

    def test_readiness_returns_200_when_db_connected(self):
        client = TestClient(app)
        with patch("app.main.check_database_connection", return_value={"connected": True}):
            response = client.get("/health/readiness")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["database_connected"] is True
            assert data["ready"] is True

    def test_readiness_returns_503_when_db_disconnected(self):
        client = TestClient(app)
        with patch("app.main.check_database_connection", return_value={"connected": False, "error": "Connection refused"}):
            response = client.get("/health/readiness")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["database_connected"] is False
            assert data["ready"] is False

    def test_health_response_contains_non_sensitive_diagnostics(self):
        client = TestClient(app)
        with patch("app.main.check_database_connection", return_value={"connected": True, "pg_version": "PostgreSQL 16.1"}):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "environment" in data
            assert "llm_configured" in data
            assert "llm_model" in data
            assert data["llm_model"] == "gemini-3.8-flash"
            assert "embedding_model" in data
            # Never expose secrets in response
            content_str = json.dumps(data)
            if settings.gemini_api_key:
                assert settings.gemini_api_key not in content_str
            if settings.database_url:
                assert settings.database_url not in content_str
