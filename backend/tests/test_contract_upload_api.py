"""
ContractIQ — Tests for Contract Document Upload API (Phase 2B)

Verifies:
  1. Successful PDF upload associates file with contract and returns 201 Created.
  2. Upload to nonexistent contract UUID returns 404 Not Found.
  3. Missing file payload returns 422 Unprocessable Entity.
  4. Non-PDF extension (.txt, .exe) returns 400 Bad Request.
  5. File without %PDF- magic signature returns 400 Bad Request.
  6. Oversized file exceeding max limit returns 413 Payload Too Large.
  7. Path traversal filenames (../../secret.pdf) are safely sanitized and do not escape storage.
  8. Response matches ContractUploadResponse schema.
  9. File is physically written to the configured storage directory.
  10. Invalid uploads do not write or leave orphaned files in storage.
  11. Database failure during association removes the newly saved file (no orphans).
  12. Re-uploading a new file updates the contract and removes the old file.
"""

import io
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings


# Valid minimal PDF byte sequence with valid %PDF- magic bytes
VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n99\n%%EOF"


@pytest.fixture
def temp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect application storage_dir to an isolated temporary directory for test duration."""
    test_storage = tmp_path / "contractiq_test_storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "storage_dir", test_storage)
    return test_storage


@pytest.fixture
def created_contract_id(test_client: TestClient, database_url: str | None) -> str:
    """Helper fixture to create a temporary test contract and guarantee its deletion."""
    if not database_url:
        pytest.skip("DATABASE_URL not configured — skipping live DB test")

    payload = {
        "title": f"Upload Test Contract - {uuid.uuid4().hex[:8]}",
        "vendor": "Test Vendor Corp",
        "contract_type": "NDA",
        "status": "active",
    }
    response = test_client.post("/contracts", json=payload)
    assert response.status_code == 201
    contract_id = response.json()["id"]

    yield contract_id

    # Cleanup contract and any associated DB rows
    test_client.delete(f"/contracts/{contract_id}")


class TestContractUploadAPI:
    """Comprehensive test suite for Phase 2B Contract Upload API."""

    @pytest.mark.db
    def test_upload_pdf_success(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """Valid PDF upload returns 201 and updates contract status and storage key."""
        files = {
            "file": ("enterprise_agreement.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["contract_id"] == created_contract_id
        assert data["file_name"] == "enterprise_agreement.pdf"
        assert data["file_size"] == len(VALID_PDF_BYTES)
        assert data["content_type"] == "application/pdf"
        assert data["processing_status"] == "uploaded"
        assert "storage_key" in data
        assert data["storage_key"].startswith("contracts/")
        assert "uploaded_at" in data

        # Verify physical file existence in storage
        physical_file = temp_storage / data["storage_key"]
        assert physical_file.is_file(), "Uploaded file was not found on physical disk"
        assert physical_file.read_bytes() == VALID_PDF_BYTES

        # Verify GET /contracts/{id} now reflects the updated metadata
        get_res = test_client.get(f"/contracts/{created_contract_id}")
        assert get_res.status_code == 200
        contract_data = get_res.json()
        assert contract_data["file_name"] == "enterprise_agreement.pdf"
        assert contract_data["file_storage_key"] == data["storage_key"]
        assert contract_data["processing_status"] == "uploaded"

    @pytest.mark.db
    def test_upload_api_v1_alias_success(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """POST /api/v1/contracts/{id}/upload behaves identically."""
        files = {
            "file": ("v1_test.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/api/v1/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 201
        assert response.json()["contract_id"] == created_contract_id

    @pytest.mark.db
    def test_upload_nonexistent_contract_returns_404(
        self,
        test_client: TestClient,
        temp_storage: Path,
    ):
        """Uploading to a random non-existent UUID returns 404 and stores nothing."""
        random_id = uuid.uuid4()
        files = {
            "file": ("agreement.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{random_id}/upload",
            files=files,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Verify no files were created in storage
        contracts_dir = temp_storage / "contracts"
        if contracts_dir.exists():
            assert len(list(contracts_dir.iterdir())) == 0

    def test_missing_file_payload_returns_422(
        self,
        test_client: TestClient,
    ):
        """Calling upload without the required multipart file parameter returns 422."""
        response = test_client.post(f"/contracts/{uuid.uuid4()}/upload")
        assert response.status_code == 422

    @pytest.mark.db
    def test_reject_wrong_file_extension(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """Files without .pdf extension are rejected with 400 Bad Request."""
        files = {
            "file": ("document.docx", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 400
        assert "Only PDF documents (.pdf) are accepted" in response.json()["detail"]

        # Ensure no file stored
        contracts_dir = temp_storage / "contracts"
        if contracts_dir.exists():
            assert len(list(contracts_dir.iterdir())) == 0

    @pytest.mark.db
    def test_reject_invalid_pdf_magic_signature(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """A renamed file (e.g. text file renamed to .pdf) fails magic byte validation."""
        fake_pdf_content = b"This is plain text, not a real PDF file."
        files = {
            "file": ("fake.pdf", io.BytesIO(fake_pdf_content), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 400
        assert "standard PDF header '%PDF-'" in response.json()["detail"]

        # Ensure no file stored
        contracts_dir = temp_storage / "contracts"
        if contracts_dir.exists():
            assert len(list(contracts_dir.iterdir())) == 0

    @pytest.mark.db
    def test_reject_empty_file(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """0-byte uploaded file is rejected with 400."""
        files = {
            "file": ("empty.pdf", io.BytesIO(b""), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.db
    def test_reject_oversized_file(
        self,
        test_client: TestClient,
        created_contract_id: str,
        monkeypatch: pytest.MonkeyPatch,
        temp_storage: Path,
    ):
        """File exceeding max_upload_size_bytes is rejected with 413 Payload Too Large."""
        # Set artificial low limit: 100 bytes
        monkeypatch.setattr(settings, "max_upload_size_bytes", 100)

        files = {
            "file": ("large.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 413
        assert "exceeds maximum permitted limit" in response.json()["detail"]

    @pytest.mark.db
    def test_path_traversal_filename_is_sanitized_and_safe(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """Filenames attempting directory traversal are safely handled and never escape storage."""
        traversal_filename = "../../../../etc/passwd.pdf"
        files = {
            "file": (traversal_filename, io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 201
        data = response.json()

        # Filename should be sanitized (no path slashes)
        assert "/" not in data["file_name"]
        assert "\\" not in data["file_name"]
        assert ".." not in data["file_name"]

        # Physical file is safely inside temp_storage/contracts
        saved_file = temp_storage / data["storage_key"]
        assert saved_file.is_file()
        assert saved_file.resolve().is_relative_to(temp_storage.resolve())

    @pytest.mark.db
    def test_database_failure_cleans_up_saved_file(
        self,
        test_client: TestClient,
        created_contract_id: str,
        monkeypatch: pytest.MonkeyPatch,
        temp_storage: Path,
    ):
        """If database association fails, the uploaded file is cleaned up so no orphan exists."""
        from app.services import contract_service

        def mock_failing_associate(*args, **kwargs):
            raise RuntimeError("Simulated database failure during association")

        monkeypatch.setattr(contract_service, "associate_contract_file", mock_failing_associate)

        files = {
            "file": ("contract_fail.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        response = test_client.post(
            f"/contracts/{created_contract_id}/upload",
            files=files,
        )
        assert response.status_code == 500

        # Confirm no orphan file was left in storage
        contracts_dir = temp_storage / "contracts"
        if contracts_dir.exists():
            stored_files = list(contracts_dir.glob("*.pdf"))
            assert len(stored_files) == 0, f"Found orphan files: {stored_files}"

    @pytest.mark.db
    def test_reupload_replaces_previous_file(
        self,
        test_client: TestClient,
        created_contract_id: str,
        temp_storage: Path,
    ):
        """Re-uploading a new PDF replaces the previous file and removes the old file from disk."""
        # 1. First upload
        files_1 = {
            "file": ("version_1.pdf", io.BytesIO(VALID_PDF_BYTES), "application/pdf")
        }
        res_1 = test_client.post(f"/contracts/{created_contract_id}/upload", files=files_1)
        assert res_1.status_code == 201
        key_1 = res_1.json()["storage_key"]
        file_1 = temp_storage / key_1
        assert file_1.is_file()

        # 2. Second upload (re-upload with newer content)
        pdf_v2_bytes = VALID_PDF_BYTES + b"\n% Additional content"
        files_2 = {
            "file": ("version_2.pdf", io.BytesIO(pdf_v2_bytes), "application/pdf")
        }
        res_2 = test_client.post(f"/contracts/{created_contract_id}/upload", files=files_2)
        assert res_2.status_code == 201
        key_2 = res_2.json()["storage_key"]
        file_2 = temp_storage / key_2
        assert file_2.is_file()

        # Old file should have been cleaned up
        assert not file_1.is_file(), "Old file was not removed upon re-upload"
        assert key_1 != key_2
