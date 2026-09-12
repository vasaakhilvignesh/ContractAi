"""
ContractIQ — Tests for Contract Processing State Lifecycle (Phase 2C)

Verifies:
  1. Newly uploaded contract starts in "uploaded" state.
  2. GET /contracts/{id}/processing-status returns current state and metadata.
  3. uploaded -> queued succeeds.
  4. queued -> processing succeeds.
  5. processing -> completed succeeds.
  6. processing -> failed succeeds and records error_message.
  7. failed -> queued retry succeeds and clears error_message.
  8. Invalid state value is rejected with 422 Unprocessable Entity.
  9. Invalid state transition (e.g. uploaded -> completed) is rejected with 400 Bad Request.
  10. Attempting to transition a contract with no uploaded file (pending) is rejected with 400.
  11. Nonexistent contract UUID returns 404 Not Found on GET and PATCH.
  12. Re-uploading a new PDF resets processing_status back to "uploaded" and clears errors.
  13. /api/v1/ route aliases for processing-status work identically.
"""

import io
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n99\n%%EOF"


@pytest.fixture
def temp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate storage to temporary folder for the duration of tests."""
    test_storage = tmp_path / "processing_test_storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "storage_dir", test_storage)
    return test_storage


@pytest.fixture
def uploaded_contract(
    test_client: TestClient, database_url: str | None, temp_storage: Path
) -> str:
    """Creates a test contract and uploads a valid PDF so it starts in 'uploaded' state."""
    if not database_url:
        pytest.skip("DATABASE_URL not configured — skipping live DB test")

    # 1. Create contract
    create_res = test_client.post(
        "/contracts",
        json={"title": f"Processing Test - {uuid.uuid4().hex[:8]}", "vendor": "Acme Inc"},
    )
    assert create_res.status_code == 201
    contract_id = create_res.json()["id"]

    # 2. Upload PDF
    files = {"file": ("test_doc.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")}
    upload_res = test_client.post(f"/contracts/{contract_id}/upload", files=files)
    assert upload_res.status_code == 201
    assert upload_res.json()["processing_status"] == "uploaded"

    yield contract_id

    # Cleanup
    test_client.delete(f"/contracts/{contract_id}")


class TestContractProcessingState:
    """Comprehensive test suite for Phase 2C Processing State Lifecycle."""

    @pytest.mark.db
    def test_newly_uploaded_contract_is_in_uploaded_state(
        self, test_client: TestClient, uploaded_contract: str
    ):
        """A newly uploaded contract must report processing_status='uploaded'."""
        res = test_client.get(f"/contracts/{uploaded_contract}/processing-status")
        assert res.status_code == 200
        data = res.json()
        assert data["contract_id"] == uploaded_contract
        assert data["processing_status"] == "uploaded"
        assert data["processing_error"] is None
        assert data["file_name"] == "test_doc.pdf"
        assert "updated_at" in data

    @pytest.mark.db
    def test_api_v1_processing_status_alias(
        self, test_client: TestClient, uploaded_contract: str
    ):
        """GET /api/v1/contracts/{id}/processing-status behaves identically."""
        res = test_client.get(f"/api/v1/contracts/{uploaded_contract}/processing-status")
        assert res.status_code == 200
        assert res.json()["contract_id"] == uploaded_contract
        assert res.json()["processing_status"] == "uploaded"

    @pytest.mark.db
    def test_full_successful_lifecycle_progression(
        self, test_client: TestClient, uploaded_contract: str
    ):
        """Valid transition sequence: uploaded -> queued -> processing -> completed."""
        # 1. uploaded -> queued
        res_queue = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "queued"},
        )
        assert res_queue.status_code == 200
        assert res_queue.json()["processing_status"] == "queued"

        # 2. queued -> processing
        res_proc = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "processing"},
        )
        assert res_proc.status_code == 200
        assert res_proc.json()["processing_status"] == "processing"

        # 3. processing -> completed
        res_comp = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "completed"},
        )
        assert res_comp.status_code == 200
        assert res_comp.json()["processing_status"] == "completed"
        assert res_comp.json()["processing_error"] is None

    @pytest.mark.db
    def test_failure_and_retry_lifecycle(
        self, test_client: TestClient, uploaded_contract: str
    ):
        """Failure lifecycle: uploaded -> queued -> processing -> failed -> queued (retry)."""
        # uploaded -> queued -> processing
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "queued"})
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "processing"})

        # processing -> failed with error message
        error_detail = "Simulated OCR failure on page 3"
        res_fail = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "failed", "error_message": error_detail},
        )
        assert res_fail.status_code == 200
        data_fail = res_fail.json()
        assert data_fail["processing_status"] == "failed"
        assert data_fail["processing_error"] == error_detail

        # failed -> queued (retry)
        res_retry = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "queued"},
        )
        assert res_retry.status_code == 200
        data_retry = res_retry.json()
        assert data_retry["processing_status"] == "queued"
        # Error message should be cleared upon retry
        assert data_retry["processing_error"] is None

    @pytest.mark.db
    def test_reject_invalid_state_transition(
        self, test_client: TestClient, uploaded_contract: str
    ):
        """Invalid transition (e.g. uploaded -> completed directly) must return 400 Bad Request."""
        res = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "completed"},
        )
        assert res.status_code == 400
        assert "Invalid processing status transition" in res.json()["detail"]

    @pytest.mark.db
    def test_reject_completed_transition(
        self, test_client: TestClient, uploaded_contract: str
    ):
        """Once completed, status cannot transition to processing or queued (terminal)."""
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "queued"})
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "processing"})
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "completed"})

        # Attempt completed -> processing
        res = test_client.patch(
            f"/contracts/{uploaded_contract}/processing-status",
            json={"status": "processing"},
        )
        assert res.status_code == 400
        assert "terminal state" in res.json()["detail"]

    def test_reject_unrecognized_status_enum_value(
        self, test_client: TestClient
    ):
        """An arbitrary/unrecognized string value must be rejected by Pydantic with 422."""
        res = test_client.patch(
            f"/contracts/{uuid.uuid4()}/processing-status",
            json={"status": "arbitrary_unknown_status"},
        )
        assert res.status_code == 422

    @pytest.mark.db
    def test_cannot_transition_contract_without_uploaded_file(
        self, test_client: TestClient, database_url: str | None
    ):
        """A contract in 'pending' state without an uploaded document cannot transition."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured")

        # Create contract without upload
        create_res = test_client.post(
            "/contracts",
            json={"title": "Pending Only Contract", "vendor": "Vendor X"},
        )
        assert create_res.status_code == 201
        contract_id = create_res.json()["id"]

        try:
            # Check initial state
            status_res = test_client.get(f"/contracts/{contract_id}/processing-status")
            assert status_res.status_code == 200
            assert status_res.json()["processing_status"] == "pending"

            # Attempt to queue without uploading
            patch_res = test_client.patch(
                f"/contracts/{contract_id}/processing-status",
                json={"status": "queued"},
            )
            assert patch_res.status_code == 400
            assert "no document has been uploaded" in patch_res.json()["detail"].lower()
        finally:
            test_client.delete(f"/contracts/{contract_id}")

    @pytest.mark.db
    def test_nonexistent_contract_returns_404(
        self, test_client: TestClient, database_url: str | None
    ):
        """Nonexistent contract UUID returns 404 for both GET and PATCH."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured")

        random_id = uuid.uuid4()
        get_res = test_client.get(f"/contracts/{random_id}/processing-status")
        assert get_res.status_code == 404

        patch_res = test_client.patch(
            f"/contracts/{random_id}/processing-status",
            json={"status": "queued"},
        )
        assert patch_res.status_code == 404

    @pytest.mark.db
    def test_reupload_resets_processing_state(
        self, test_client: TestClient, uploaded_contract: str, temp_storage: Path
    ):
        """Re-uploading a new PDF after failure or completion resets status to 'uploaded'."""
        # Progress to completed
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "queued"})
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "processing"})
        test_client.patch(f"/contracts/{uploaded_contract}/processing-status", json={"status": "completed"})

        # Re-upload new document
        new_pdf_bytes = VALID_PDF_BYTES + b"\n% new version"
        files = {"file": ("updated_doc.pdf", io.BytesIO(new_pdf_bytes), "application/pdf")}
        upload_res = test_client.post(f"/contracts/{uploaded_contract}/upload", files=files)
        assert upload_res.status_code == 201
        assert upload_res.json()["processing_status"] == "uploaded"

        # Check status endpoint confirms reset to uploaded
        status_res = test_client.get(f"/contracts/{uploaded_contract}/processing-status")
        assert status_res.status_code == 200
        assert status_res.json()["processing_status"] == "uploaded"
        assert status_res.json()["file_name"] == "updated_doc.pdf"
        assert status_res.json()["processing_error"] is None
