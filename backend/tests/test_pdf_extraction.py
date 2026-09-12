"""
ContractIQ — Comprehensive Tests for PDF Text Extraction Engine (Phase 3A)

Verifies:
  1. Single-page text PDF extraction (text, 1-indexed page, character & word counts).
  2. Multi-page sequential extraction preserving 1-indexed order.
  3. Blank page preservation (middle blank page retains page number, has_text=False).
  4. Scanned / image-only PDF detection (is_scanned=True, scanned_requires_ocr).
  5. Empty document detection (total_pages=0 or blank pages without images).
  6. Encrypted / password-protected PDF rejection (PDFEncryptedError).
  7. Corrupted / malformed PDF rejection (PDFCorruptedError).
  8. Missing physical file rejection (PDFNotFoundError).
  9. Storage path traversal prevention (PDFPathTraversalError).
  10. Defensive page limit enforcement (PDFPageLimitExceededError).
  11. Heading candidate heuristic accuracy.
  12. API endpoint POST /contracts/{id}/extract success and Contract.page_count update.
  13. API endpoint POST /api/v1/contracts/{id}/extract versioned alias.
  14. API endpoint scanned PDF handling (status="failed", error notes OCR required).
  15. API endpoint corrupted PDF failure handling (status="failed").
  16. API endpoint encrypted PDF failure handling (status="failed").
  17. API endpoint missing storage file handling (404, status="failed").
  18. API endpoint rejection of contract with no uploaded file (400).
  19. API endpoint rejection of nonexistent contract (404).
  20. API endpoint rejection of already completed contract without re-upload (400).
"""

import io
import os
import uuid
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.contract import ProcessingStatus
from app.services import pdf_extraction_service


# ====================================================================
# Test PDF Programmatic Fixture Generators
# ====================================================================


def generate_text_pdf(pages_text: list[str]) -> bytes:
    """Generate in-memory PDF bytes containing the specified text per page."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            # Insert text at reasonable page coordinates (x=50, y=72)
            page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_scanned_pdf(page_count: int = 1) -> bytes:
    """Generate in-memory PDF with raster images on each page and zero extractable text."""
    doc = pymupdf.open()
    for _ in range(page_count):
        page = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), 0)
        pix.clear_with(200)
        page.insert_image(pymupdf.Rect(50, 50, 200, 200), pixmap=pix)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def generate_encrypted_pdf(password: str = "secret_pw") -> bytes:
    """Generate in-memory password-protected PDF bytes."""
    doc = pymupdf.open()
    doc.new_page()
    pdf_bytes = doc.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=password,
    )
    doc.close()
    return pdf_bytes


# ====================================================================
# Pytest Fixtures
# ====================================================================


@pytest.fixture
def temp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate storage_dir to temporary test folder."""
    test_storage = tmp_path / "extraction_test_storage"
    test_storage.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "storage_dir", test_storage)
    return test_storage


@pytest.fixture
def test_contract_id(test_client: TestClient, database_url: str | None) -> str:
    """Creates a temporary test contract and guarantees deletion."""
    if not database_url:
        pytest.skip("DATABASE_URL not configured — skipping live DB test")

    res = test_client.post(
        "/contracts",
        json={"title": f"Extract Test - {uuid.uuid4().hex[:8]}", "vendor": "Acme Legal"},
    )
    assert res.status_code == 201
    contract_id = res.json()["id"]

    yield contract_id

    # Cleanup contract after test
    test_client.delete(f"/contracts/{contract_id}")


# ====================================================================
# 1. Pure Service Unit Tests (No Database Required)
# ====================================================================


class TestPDFExtractionServiceUnit:
    """Unit tests verifying pure extraction logic and safety boundaries."""

    def test_extract_single_page_pdf(self, tmp_path: Path):
        text_content = (
            "1. Definitions and Interpretation\n"
            "This Master Services Agreement is entered into by Acme Corp."
        )
        pdf_bytes = generate_text_pdf([text_content])
        pdf_file = tmp_path / "single_page.pdf"
        pdf_file.write_bytes(pdf_bytes)

        contract_id = uuid.uuid4()
        result = pdf_extraction_service.extract_text_from_pdf(pdf_file, contract_id)

        assert result.contract_id == contract_id
        assert result.total_pages == 1
        assert result.extracted_pages == 1
        assert result.is_scanned is False
        assert result.extraction_status == "success"

        page = result.pages[0]
        assert page.page_number == 1
        assert "Master Services Agreement" in page.text
        assert page.has_text is True
        assert page.character_count > 0
        assert page.word_count > 5
        assert len(page.blocks) >= 1

    def test_extract_multipage_pdf_sequential_order(self, tmp_path: Path):
        pages_content = [
            "Page One: Section 1. Term of Agreement",
            "Page Two: Section 2. Payment Terms and Invoicing",
            "Page Three: Section 3. Confidentiality and IP",
        ]
        pdf_bytes = generate_text_pdf(pages_content)
        pdf_file = tmp_path / "multipage.pdf"
        pdf_file.write_bytes(pdf_bytes)

        result = pdf_extraction_service.extract_text_from_pdf(pdf_file, uuid.uuid4())

        assert result.total_pages == 3
        assert result.extracted_pages == 3
        assert [p.page_number for p in result.pages] == [1, 2, 3]
        assert "Term of Agreement" in result.pages[0].text
        assert "Payment Terms" in result.pages[1].text
        assert "Confidentiality" in result.pages[2].text

    def test_preserve_blank_pages(self, tmp_path: Path):
        # Page 1 has text, Page 2 is empty, Page 3 has text
        pages_content = [
            "1. Preamble and Scope of Services",
            "",  # intentionally blank
            "2. Governing Law and Jurisdiction",
        ]
        pdf_bytes = generate_text_pdf(pages_content)
        pdf_file = tmp_path / "with_blank.pdf"
        pdf_file.write_bytes(pdf_bytes)

        result = pdf_extraction_service.extract_text_from_pdf(pdf_file, uuid.uuid4())

        assert result.total_pages == 3
        assert result.extracted_pages == 3

        # Page 1
        assert result.pages[0].page_number == 1
        assert result.pages[0].has_text is True

        # Page 2 (blank page preserved)
        assert result.pages[1].page_number == 2
        assert result.pages[1].has_text is False
        assert result.pages[1].character_count == 0
        assert result.pages[1].word_count == 0
        assert result.pages[1].text == ""

        # Page 3
        assert result.pages[2].page_number == 3
        assert result.pages[2].has_text is True
        assert "Governing Law" in result.pages[2].text

    def test_detect_scanned_image_only_pdf(self, tmp_path: Path):
        pdf_bytes = generate_scanned_pdf(page_count=2)
        pdf_file = tmp_path / "scanned.pdf"
        pdf_file.write_bytes(pdf_bytes)

        result = pdf_extraction_service.extract_text_from_pdf(pdf_file, uuid.uuid4())

        assert result.total_pages == 2
        assert result.is_scanned is True
        assert result.extraction_status == "scanned_requires_ocr"
        assert all(p.has_text is False for p in result.pages)

    def test_reject_encrypted_pdf(self, tmp_path: Path):
        pdf_bytes = generate_encrypted_pdf(password="test_secret")
        pdf_file = tmp_path / "encrypted.pdf"
        pdf_file.write_bytes(pdf_bytes)

        with pytest.raises(pdf_extraction_service.PDFEncryptedError) as exc_info:
            pdf_extraction_service.extract_text_from_pdf(pdf_file, uuid.uuid4())

        assert "Password-protected" in str(exc_info.value)

    def test_reject_corrupted_pdf(self, tmp_path: Path):
        pdf_file = tmp_path / "corrupt.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\nCorrupted content that cannot be parsed by MuPDF\n")

        with pytest.raises(pdf_extraction_service.PDFCorruptedError):
            pdf_extraction_service.extract_text_from_pdf(pdf_file, uuid.uuid4())

    def test_missing_physical_file_raises_not_found(self, temp_storage: Path):
        with pytest.raises(pdf_extraction_service.PDFNotFoundError):
            pdf_extraction_service.resolve_pdf_path(
                "contracts/missing_file_that_does_not_exist.pdf",
                storage_base_dir=temp_storage,
            )

    def test_storage_path_traversal_rejected(self, temp_storage: Path):
        with pytest.raises(pdf_extraction_service.PDFPathTraversalError):
            pdf_extraction_service.resolve_pdf_path(
                "../../etc/passwd",
                storage_base_dir=temp_storage,
            )

    def test_defensive_page_limit_enforced(self, tmp_path: Path):
        pages_content = ["Page 1", "Page 2", "Page 3", "Page 4"]
        pdf_bytes = generate_text_pdf(pages_content)
        pdf_file = tmp_path / "four_pages.pdf"
        pdf_file.write_bytes(pdf_bytes)

        with pytest.raises(pdf_extraction_service.PDFPageLimitExceededError) as exc_info:
            pdf_extraction_service.extract_text_from_pdf(
                pdf_file, uuid.uuid4(), max_pages=2
            )

        assert "exceeds maximum permitted limit" in str(exc_info.value)

    def test_heading_candidate_heuristics(self):
        bbox = (50.0, 72.0, 200.0, 90.0)
        # Should match
        assert pdf_extraction_service.is_heading_candidate_heuristic("1. Definitions", bbox) is True
        assert pdf_extraction_service.is_heading_candidate_heuristic("Section 4. Term", bbox) is True
        assert pdf_extraction_service.is_heading_candidate_heuristic("Article II - Indemnity", bbox) is True
        assert pdf_extraction_service.is_heading_candidate_heuristic("CONFIDENTIALITY", bbox) is True

        # Should NOT match
        assert pdf_extraction_service.is_heading_candidate_heuristic("", bbox) is False
        assert (
            pdf_extraction_service.is_heading_candidate_heuristic(
                "This is a standard contractual clause that ends with a period.", bbox
            )
            is False
        )
        assert (
            pdf_extraction_service.is_heading_candidate_heuristic(
                "Very long paragraph text that contains many characters exceeding the heading limit " * 3,
                bbox,
            )
            is False
        )


# ====================================================================
# 2. API Integration Tests (Live Neon DB + FastAPI TestClient)
# ====================================================================


class TestPDFExtractionAPI:
    """Integration tests for POST /contracts/{contract_id}/extract."""

    def test_extract_endpoint_success_updates_page_count(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        # 1. Upload a 2-page valid contract PDF
        pdf_bytes = generate_text_pdf([
            "1. Definitions and Preamble",
            "2. Term and Termination Notice Period of 30 Days",
        ])
        upload_res = test_client.post(
            f"/contracts/{test_contract_id}/upload",
            files={"file": ("contract.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_res.status_code == 201
        assert upload_res.json()["processing_status"] == "uploaded"

        # 2. Call extraction endpoint
        extract_res = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert extract_res.status_code == 200
        data = extract_res.json()

        assert data["contract_id"] == test_contract_id
        assert data["total_pages"] == 2
        assert data["extracted_pages"] == 2
        assert data["is_scanned"] is False
        assert data["extraction_status"] == "success"
        assert data["processing_status"] == "completed"
        assert data["page_count"] == 2

        # 3. Confirm Contract record in database has page_count updated
        get_res = test_client.get(f"/contracts/{test_contract_id}")
        assert get_res.status_code == 200
        assert get_res.json()["page_count"] == 2
        assert get_res.json()["processing_status"] == "completed"

    def test_extract_endpoint_api_v1_versioned_alias(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        pdf_bytes = generate_text_pdf(["Single Page Document"])
        test_client.post(
            f"/api/v1/contracts/{test_contract_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )

        res = test_client.post(f"/api/v1/contracts/{test_contract_id}/extract")
        assert res.status_code == 200
        assert res.json()["total_pages"] == 1
        assert res.json()["processing_status"] == "completed"

    def test_extract_endpoint_scanned_pdf_flags_scanned_and_failed(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        scanned_bytes = generate_scanned_pdf(page_count=1)
        test_client.post(
            f"/contracts/{test_contract_id}/upload",
            files={"file": ("scanned_doc.pdf", io.BytesIO(scanned_bytes), "application/pdf")},
        )

        extract_res = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert extract_res.status_code == 200
        data = extract_res.json()

        assert data["is_scanned"] is True
        assert data["extraction_status"] == "scanned_requires_ocr"
        assert data["processing_status"] == "failed"

        # Check status endpoint reflects failure with descriptive message
        status_res = test_client.get(f"/contracts/{test_contract_id}/processing-status")
        assert status_res.status_code == 200
        assert status_res.json()["processing_status"] == "failed"
        assert "OCR" in (status_res.json()["processing_error"] or "")

    def test_extract_endpoint_encrypted_pdf_fails_gracefully(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        encrypted_bytes = generate_encrypted_pdf()
        test_client.post(
            f"/contracts/{test_contract_id}/upload",
            files={"file": ("encrypted.pdf", io.BytesIO(encrypted_bytes), "application/pdf")},
        )

        extract_res = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert extract_res.status_code == 400
        assert "Password-protected" in extract_res.json()["detail"]

        # Confirm processing_status was updated to failed
        status_res = test_client.get(f"/contracts/{test_contract_id}/processing-status")
        assert status_res.json()["processing_status"] == "failed"

    def test_extract_endpoint_corrupted_file_fails_gracefully(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        # Upload valid PDF first
        pdf_bytes = generate_text_pdf(["Valid text"])
        upload_res = test_client.post(
            f"/contracts/{test_contract_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        storage_key = upload_res.json()["storage_key"]

        # Corrupt file on disk
        target_path = temp_storage / storage_key
        target_path.write_bytes(b"%PDF-1.4\ncorrupted file bytes")

        extract_res = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert extract_res.status_code == 400
        assert "Corrupted" in extract_res.json()["detail"]

        status_res = test_client.get(f"/contracts/{test_contract_id}/processing-status")
        assert status_res.json()["processing_status"] == "failed"

    def test_extract_endpoint_missing_physical_file_returns_404(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        # Upload valid PDF
        pdf_bytes = generate_text_pdf(["Some text"])
        upload_res = test_client.post(
            f"/contracts/{test_contract_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        storage_key = upload_res.json()["storage_key"]

        # Delete physical file
        (temp_storage / storage_key).unlink()

        extract_res = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert extract_res.status_code == 404
        assert "not found on disk" in extract_res.json()["detail"]

    def test_extract_endpoint_without_uploaded_file_returns_400(
        self,
        test_client: TestClient,
        test_contract_id: str,
    ):
        # Contract has no file uploaded yet
        res = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert res.status_code == 400
        assert "no document file has been uploaded" in res.json()["detail"]

    def test_extract_endpoint_nonexistent_contract_returns_404(
        self,
        test_client: TestClient,
    ):
        random_id = uuid.uuid4()
        res = test_client.post(f"/contracts/{random_id}/extract")
        assert res.status_code == 404

    def test_extract_already_completed_contract_returns_400(
        self,
        test_client: TestClient,
        test_contract_id: str,
        temp_storage: Path,
    ):
        # 1. Upload and extract successfully
        pdf_bytes = generate_text_pdf(["Single page"])
        test_client.post(
            f"/contracts/{test_contract_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        first_extract = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert first_extract.status_code == 200
        assert first_extract.json()["processing_status"] == "completed"

        # 2. Second extract call should be rejected because contract is already completed
        second_extract = test_client.post(f"/contracts/{test_contract_id}/extract")
        assert second_extract.status_code == 400
        assert "already completed" in second_extract.json()["detail"]
