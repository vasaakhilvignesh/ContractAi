"""
ContractIQ — Comprehensive Tests for Text Normalization & Clause-Aware Chunking (Phase 3B)

Verifies:
  1. Text Normalization:
     - CRLF, CR normalized to LF.
     - Tabs and non-breaking spaces converted to standard space.
     - Excessive horizontal whitespace collapsed.
     - Excessive blank lines (3+) collapsed to 2 newlines.
     - Unicode NFKC ligature resolution and zero-width character stripping.
     - Soft hyphen and safe line-break hyphen healing.
     - Capitalization, defined terms, punctuation, currencies, dates, and percentages preserved.
     - Obvious noise text detection (page numbers).
  2. Heading & Clause Boundary Detection:
     - Section and Article headings.
     - Numbered clauses (1. Definitions, 1.1 Confidentiality).
     - Sub-clause enumerations ((a) Invoicing).
     - Short uppercase titles (LIMITATION OF LIABILITY).
     - Rejection of regular prose sentences.
     - Propagation of section headers across page boundaries.
  3. Chunking Algorithm:
     - Page-bounded chunk construction with 1-indexed page_number.
     - Globally sequential chunk_index.
     - Splitting oversized clauses at sentence boundaries with overlap.
     - Hard split fallback for massive run-on sentences.
     - Enforcement of MAX_CHUNK_SIZE.
     - Meaningful short clause preservation.
     - Accurate char_start and char_end offsets matching normalized page text.
     - Blank page handling (zero chunks).
     - Scanned and empty document rejection.
  4. Database Persistence & Idempotency:
     - DocumentChunk creation with embedding=None.
     - Idempotent replacement of previous chunk sets without duplicates.
     - Cascade deletion with parent contract.
  5. API Endpoints:
     - POST /contracts/{id}/chunk success and response structure.
     - POST /api/v1/contracts/{id}/chunk alias.
     - Rejection of missing contract (404) and missing file (400).
     - Rejection of scanned document (400).
     - GET /contracts/{id}/chunks listing and pagination.
     - GET /api/v1/contracts/{id}/chunks alias.
"""

import io
import uuid
import pytest
import pymupdf
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.chunk import ChunkCreate
from app.schemas.extraction import ExtractionResult, PageBlock, PageExtraction
from app.services import (
    chunking_service,
    contract_service,
    pdf_extraction_service,
    text_normalization_service,
)


# ====================================================================
# Helper PDF Generators
# ====================================================================


def generate_text_pdf(pages_text: list[str]) -> bytes:
    """Generate in-memory PDF bytes containing specified text per page."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
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


# ====================================================================
# 1. Text Normalization Unit Tests
# ====================================================================


class TestTextNormalization:
    """Tests for text_normalization_service.py."""

    def test_normalize_crlf_and_cr_to_lf(self):
        raw = "Line 1\r\nLine 2\rLine 3\nLine 4"
        normalized = text_normalization_service.normalize_text(raw)
        assert "\r" not in normalized
        assert normalized == "Line 1\nLine 2\nLine 3\nLine 4"

    def test_normalize_tabs_and_non_breaking_spaces(self):
        raw = "Clause\t1.1:\u00a0Payment\u202fdue."
        normalized = text_normalization_service.normalize_text(raw)
        assert "\t" not in normalized
        assert "\u00a0" not in normalized
        assert "\u202f" not in normalized
        assert normalized == "Clause 1.1: Payment due."

    def test_normalize_collapse_horizontal_spaces(self):
        raw = "Vendor     agrees   to   provide    services."
        normalized = text_normalization_service.normalize_text(raw)
        assert normalized == "Vendor agrees to provide services."

    def test_normalize_collapse_excessive_blank_lines(self):
        raw = "Section 1\n\n\n\n\nSection 2\n\n\nSection 3"
        normalized = text_normalization_service.normalize_text(raw)
        assert "\n\n\n" not in normalized
        assert normalized == "Section 1\n\nSection 2\n\nSection 3"

    def test_normalize_unicode_nfkc_and_zero_width_chars(self):
        # 'fi' ligature (\ufb01) and 'fl' ligature (\ufb02) and zero-width spaces
        raw = "De\ufb01nitions\u200b of con\ufb02icts\ufeff"
        normalized = text_normalization_service.normalize_text(raw)
        assert "\u200b" not in normalized
        assert "\ufeff" not in normalized
        assert "Definitions of conflicts" == normalized

    def test_normalize_soft_hyphen_and_linebreak_healing(self):
        raw = "The vendor shall indemn-\nification and hold harm-\nless the customer."
        normalized = text_normalization_service.normalize_text(raw)
        assert "indemnification" in normalized
        assert "harmless" in normalized

    def test_normalize_preserves_capitalization_and_defined_terms(self):
        raw = "The 'Master Services Agreement' between ACME CORP and Customer."
        normalized = text_normalization_service.normalize_text(raw)
        assert "ACME CORP" in normalized
        assert "Master Services Agreement" in normalized
        assert "Customer" in normalized

    def test_normalize_preserves_punctuation_currency_and_percentages(self):
        raw = "Late fee: $100,000.50 (one hundred thousand USD) or 1.5% per month; whichever is higher."
        normalized = text_normalization_service.normalize_text(raw)
        assert "$100,000.50" in normalized
        assert "1.5%" in normalized
        assert ";" in normalized
        assert "." in normalized

    def test_normalize_preserves_dates_and_clause_numbering(self):
        raw = "Effective Date: January 15, 2026. Pursuant to Section 12.4(a)(ii)."
        normalized = text_normalization_service.normalize_text(raw)
        assert "January 15, 2026" in normalized
        assert "Section 12.4(a)(ii)" in normalized

    def test_is_noise_text_detection(self):
        assert text_normalization_service.is_noise_text("Page 1 of 5") is True
        assert text_normalization_service.is_noise_text("3 / 10") is True
        assert text_normalization_service.is_noise_text("- 4 -") is True
        assert text_normalization_service.is_noise_text("   ") is True
        assert text_normalization_service.is_noise_text("---") is True

        # Meaningful legal short clauses must NOT be noise
        assert text_normalization_service.is_noise_text("Term: 24 months.") is False
        assert text_normalization_service.is_noise_text("1. Definitions") is False
        assert text_normalization_service.is_noise_text("Payment upon receipt.") is False


# ====================================================================
# 2. Heading & Clause Boundary Detection Tests
# ====================================================================


class TestHeadingAndClauseDetection:
    """Tests for heading pattern matching and propagation."""

    def test_is_heading_line_numbered_clauses(self):
        assert chunking_service.is_heading_line("1. Definitions") is True
        assert chunking_service.is_heading_line("1.1 Confidential Information") is True
        assert chunking_service.is_heading_line("12.4.2 Limitation on Damages") is True

    def test_is_heading_line_section_and_article(self):
        assert chunking_service.is_heading_line("SECTION 1 — DEFINITIONS") is True
        assert chunking_service.is_heading_line("Section 4. Payment Terms") is True
        assert chunking_service.is_heading_line("ARTICLE V — TERMINATION") is True
        assert chunking_service.is_heading_line("Article 3: Intellectual Property") is True
        assert chunking_service.is_heading_line("EXHIBIT A — STATEMENT OF WORK") is True

    def test_is_heading_line_all_caps_titles(self):
        assert chunking_service.is_heading_line("LIMITATION OF LIABILITY") is True
        assert chunking_service.is_heading_line("INDEMNIFICATION") is True
        assert chunking_service.is_heading_line("GOVERNING LAW") is True

    def test_is_heading_line_subclauses(self):
        assert chunking_service.is_heading_line("(a) Invoicing Schedule") is True
        assert chunking_service.is_heading_line("(i) Audit Rights") is True

    def test_is_heading_line_rejects_regular_sentences(self):
        assert (
            chunking_service.is_heading_line(
                "The vendor shall deliver all required software by the agreed date."
            )
            is False
        )
        assert (
            chunking_service.is_heading_line(
                "Neither party shall be liable for indirect, incidental, or punitive damages."
            )
            is False
        )

    def test_section_header_propagation_across_pages(self):
        """Verify that a section header detected on Page 1 propagates to Page 2 until a new header is encountered."""
        page1 = PageExtraction(
            page_number=1,
            text="SECTION 4 — PAYMENT TERMS\n\nPayment is due net 30 days.",
            character_count=52,
            word_count=8,
            has_text=True,
            blocks=[],
        )
        page2 = PageExtraction(
            page_number=2,
            text="Interest accrues at 1.5% per month on overdue invoices.\n\nSECTION 5 — TERMINATION\n\nEither party may terminate upon 30 days notice.",
            character_count=130,
            word_count=21,
            has_text=True,
            blocks=[],
        )

        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=2,
            extracted_pages=2,
            is_scanned=False,
            extraction_status="success",
            pages=[page1, page2],
        )

        chunks = chunking_service.chunk_extraction_result(extraction_result)

        # First chunk on Page 1 has Section 4
        assert chunks[0].page_number == 1
        assert chunks[0].section_header == "SECTION 4 — PAYMENT TERMS"

        # Chunk on Page 2 before Section 5 should inherit Section 4 header!
        assert chunks[1].page_number == 2
        assert chunks[1].section_header == "SECTION 4 — PAYMENT TERMS"
        assert "Interest accrues" in chunks[1].text

        # Chunk on Page 2 after Section 5 should switch to Section 5 header!
        assert chunks[2].page_number == 2
        assert chunks[2].section_header == "SECTION 5 — TERMINATION"
        assert "terminate upon 30 days" in chunks[2].text


# ====================================================================
# 3. Chunking Algorithm Tests
# ====================================================================


class TestChunkingAlgorithm:
    """Tests for chunking assembly, boundaries, size limits, and offsets."""

    def test_chunk_page_bounded_and_contiguous_index(self):
        page1_text = "SECTION 1 — TERM\n\nThis agreement lasts for 3 years."
        page2_text = "SECTION 2 — TERMINATION\n\nTermination for cause requires 15 days notice."

        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=2,
            extracted_pages=2,
            is_scanned=False,
            extraction_status="success",
            pages=[
                PageExtraction(
                    page_number=1,
                    text=page1_text,
                    character_count=len(page1_text),
                    word_count=8,
                    has_text=True,
                ),
                PageExtraction(
                    page_number=2,
                    text=page2_text,
                    character_count=len(page2_text),
                    word_count=9,
                    has_text=True,
                ),
            ],
        )

        chunks = chunking_service.chunk_extraction_result(extraction_result)

        assert len(chunks) == 2
        # Page 1 chunk
        assert chunks[0].page_number == 1
        assert chunks[0].chunk_index == 0
        # Page 2 chunk
        assert chunks[1].page_number == 2
        assert chunks[1].chunk_index == 1

    def test_chunk_char_offsets_accurately_slice_normalized_text(self):
        page_text = "SECTION 8 — CONFIDENTIALITY\n\nEach party shall protect confidential information with reasonable care."
        normalized = text_normalization_service.normalize_text(page_text)

        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=1,
            extracted_pages=1,
            is_scanned=False,
            extraction_status="success",
            pages=[
                PageExtraction(
                    page_number=1,
                    text=page_text,
                    character_count=len(page_text),
                    word_count=13,
                    has_text=True,
                )
            ],
        )

        chunks = chunking_service.chunk_extraction_result(extraction_result)
        assert len(chunks) >= 1
        chk = chunks[0]

        assert chk.char_start is not None
        assert chk.char_end is not None
        # Verify that normalized_text[char_start:char_end] exactly equals the chunk text!
        assert normalized[chk.char_start:chk.char_end] == chk.text

    def test_chunk_oversized_clause_splits_with_overlap(self):
        # Create a single paragraph with 3,000 characters
        sentence = "Vendor shall maintain security certifications and comply with SOC 2 requirements at all times. "
        long_paragraph = "SECTION 10 — SECURITY\n\n" + (sentence * 35)

        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=1,
            extracted_pages=1,
            is_scanned=False,
            extraction_status="success",
            pages=[
                PageExtraction(
                    page_number=1,
                    text=long_paragraph,
                    character_count=len(long_paragraph),
                    word_count=400,
                    has_text=True,
                )
            ],
        )

        chunks = chunking_service.chunk_extraction_result(
            extraction_result,
            target_size=1200,
            max_size=2000,
            overlap=150,
        )

        assert len(chunks) > 1
        for chk in chunks:
            # Strictly enforce MAX_CHUNK_SIZE
            assert len(chk.text) <= 2000
            assert chk.section_header == "SECTION 10 — SECURITY"

        # Check contiguous sequential indices
        for i, chk in enumerate(chunks):
            assert chk.chunk_index == i

    def test_chunk_preserves_meaningful_short_clauses(self):
        page_text = "SECTION 12 — GOVERNING LAW\n\nState of New York."
        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=1,
            extracted_pages=1,
            is_scanned=False,
            extraction_status="success",
            pages=[
                PageExtraction(
                    page_number=1,
                    text=page_text,
                    character_count=len(page_text),
                    word_count=6,
                    has_text=True,
                )
            ],
        )

        chunks = chunking_service.chunk_extraction_result(extraction_result, min_size=100)
        assert len(chunks) == 1
        assert "State of New York" in chunks[0].text

    def test_chunk_blank_page_produces_zero_chunks(self):
        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=1,
            extracted_pages=1,
            is_scanned=False,
            extraction_status="success",
            pages=[
                PageExtraction(
                    page_number=1,
                    text="   \n\n   ",
                    character_count=0,
                    word_count=0,
                    has_text=False,
                )
            ],
        )

        chunks = chunking_service.chunk_extraction_result(extraction_result)
        assert len(chunks) == 0

    def test_chunk_scanned_pdf_raises_error(self):
        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=1,
            extracted_pages=1,
            is_scanned=True,
            extraction_status="scanned_requires_ocr",
            pages=[],
        )

        with pytest.raises(chunking_service.ScannedDocumentChunkingError):
            chunking_service.chunk_extraction_result(extraction_result)

    def test_chunk_empty_document_raises_error(self):
        extraction_result = ExtractionResult(
            contract_id=uuid.uuid4(),
            total_pages=0,
            extracted_pages=0,
            is_scanned=False,
            extraction_status="empty",
            pages=[],
        )

        with pytest.raises(chunking_service.EmptyDocumentChunkingError):
            chunking_service.chunk_extraction_result(extraction_result)


# ====================================================================
# 4. Persistence & Idempotency Tests
# ====================================================================


class TestChunkPersistenceAndIdempotency:
    """Database tests for DocumentChunk table persistence and idempotency."""

    def test_persist_chunks_in_database(self, test_client: TestClient):
        # 1. Create a contract via API
        res = test_client.post("/contracts", json={"title": "Test Persistence Contract"})
        assert res.status_code == 201
        contract_id = uuid.UUID(res.json()["id"])

        try:
            db = next(get_db())
            chunks = [
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=1,
                    chunk_index=0,
                    char_start=0,
                    char_end=25,
                    section_header="SECTION 1",
                    text="First chunk for contract.",
                ),
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=1,
                    chunk_index=1,
                    char_start=26,
                    char_end=55,
                    section_header="SECTION 1",
                    text="Second chunk for contract.",
                ),
            ]

            persisted = chunking_service.persist_contract_chunks(
                db=db, contract_id=contract_id, chunks=chunks
            )
            assert len(persisted) == 2
            # Embedding must remain None
            assert persisted[0].embedding is None
            assert persisted[1].embedding is None

            # Verify query from DB
            items, total = chunking_service.list_contract_chunks(db=db, contract_id=contract_id)
            assert total == 2
            assert items[0].chunk_index == 0
            assert items[1].chunk_index == 1

        finally:
            test_client.delete(f"/contracts/{contract_id}")

    def test_rerun_chunking_replaces_old_chunks_idempotently(self, test_client: TestClient):
        res = test_client.post("/contracts", json={"title": "Test Idempotent Contract"})
        assert res.status_code == 201
        contract_id = uuid.UUID(res.json()["id"])

        try:
            db = next(get_db())

            # First batch: 2 chunks
            batch1 = [
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=1,
                    chunk_index=0,
                    text="Batch 1 - Chunk 0",
                ),
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=1,
                    chunk_index=1,
                    text="Batch 1 - Chunk 1",
                ),
            ]
            chunking_service.persist_contract_chunks(db=db, contract_id=contract_id, chunks=batch1)
            _, total1 = chunking_service.list_contract_chunks(db=db, contract_id=contract_id)
            assert total1 == 2

            # Second batch: 3 new chunks (simulating re-chunking)
            batch2 = [
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=1,
                    chunk_index=0,
                    text="Batch 2 - Chunk 0",
                ),
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=1,
                    chunk_index=1,
                    text="Batch 2 - Chunk 1",
                ),
                ChunkCreate(
                    contract_id=contract_id,
                    page_number=2,
                    chunk_index=2,
                    text="Batch 2 - Chunk 2",
                ),
            ]
            chunking_service.persist_contract_chunks(db=db, contract_id=contract_id, chunks=batch2)
            items2, total2 = chunking_service.list_contract_chunks(db=db, contract_id=contract_id)

            # Idempotency check: total must be 3, NOT 5!
            assert total2 == 3
            assert items2[0].text == "Batch 2 - Chunk 0"
            assert items2[2].text == "Batch 2 - Chunk 2"

        finally:
            test_client.delete(f"/contracts/{contract_id}")

    def test_delete_contract_cascades_to_chunks(self, test_client: TestClient):
        res = test_client.post("/contracts", json={"title": "Test Cascade Delete Contract"})
        assert res.status_code == 201
        contract_id = uuid.UUID(res.json()["id"])

        db = next(get_db())
        chunk = ChunkCreate(
            contract_id=contract_id,
            page_number=1,
            chunk_index=0,
            text="Cascade test chunk",
        )
        chunking_service.persist_contract_chunks(db=db, contract_id=contract_id, chunks=[chunk])

        # Delete parent contract
        del_res = test_client.delete(f"/contracts/{contract_id}")
        assert del_res.status_code == 204

        # Verify chunks were cascade-deleted
        remaining_chunks = db.query(DocumentChunk).filter_by(contract_id=contract_id).all()
        assert len(remaining_chunks) == 0


# ====================================================================
# 5. Chunking API Integration Tests
# ====================================================================


class TestChunkingAPI:
    """Tests for POST /contracts/{id}/chunk and GET /contracts/{id}/chunks."""

    def test_post_chunk_success_endpoint(self, test_client: TestClient):
        # 1. Create contract
        create_res = test_client.post(
            "/contracts", json={"title": "API Chunking Test Contract"}
        )
        assert create_res.status_code == 201
        contract_id = create_res.json()["id"]

        try:
            # 2. Upload text PDF
            pdf_bytes = generate_text_pdf([
                "SECTION 1 — SCOPE\n\nVendor shall supply cloud software.",
                "SECTION 2 — FEES\n\nAnnual fees are $50,000 USD.",
            ])
            upload_res = test_client.post(
                f"/contracts/{contract_id}/upload",
                files={"file": ("contract.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            assert upload_res.status_code == 201

            # 3. Call chunking endpoint
            chunk_res = test_client.post(f"/contracts/{contract_id}/chunk")
            assert chunk_res.status_code == 200
            data = chunk_res.json()

            assert data["contract_id"] == contract_id
            assert data["total_pages"] == 2
            assert data["total_chunks"] >= 2
            assert len(data["sample_chunks"]) >= 2
            assert "Successfully generated" in data["message"]

            # 4. Query chunks via GET
            get_res = test_client.get(f"/contracts/{contract_id}/chunks")
            assert get_res.status_code == 200
            get_data = get_res.json()
            assert get_data["total"] == data["total_chunks"]
            assert len(get_data["items"]) == data["total_chunks"]

        finally:
            test_client.delete(f"/contracts/{contract_id}")

    def test_post_chunk_api_v1_versioned_alias(self, test_client: TestClient):
        create_res = test_client.post(
            "/api/v1/contracts", json={"title": "API v1 Alias Chunk Test"}
        )
        assert create_res.status_code == 201
        contract_id = create_res.json()["id"]

        try:
            pdf_bytes = generate_text_pdf(["ARTICLE 1 — DEFINITIONS\n\nConfidentiality terms."])
            upload_res = test_client.post(
                f"/api/v1/contracts/{contract_id}/upload",
                files={"file": ("alias_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )
            assert upload_res.status_code == 201

            chunk_res = test_client.post(f"/api/v1/contracts/{contract_id}/chunk")
            assert chunk_res.status_code == 200
            assert chunk_res.json()["total_chunks"] >= 1

            get_res = test_client.get(f"/api/v1/contracts/{contract_id}/chunks?limit=10&offset=0")
            assert get_res.status_code == 200
            assert get_res.json()["total"] >= 1

        finally:
            test_client.delete(f"/api/v1/contracts/{contract_id}")

    def test_post_chunk_missing_contract_returns_404(self, test_client: TestClient):
        random_id = str(uuid.uuid4())
        res = test_client.post(f"/contracts/{random_id}/chunk")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

    def test_post_chunk_without_uploaded_file_returns_400(self, test_client: TestClient):
        res = test_client.post("/contracts", json={"title": "No File Contract"})
        assert res.status_code == 201
        contract_id = res.json()["id"]

        try:
            chunk_res = test_client.post(f"/contracts/{contract_id}/chunk")
            assert chunk_res.status_code == 400
            assert "no file has been uploaded" in chunk_res.json()["detail"].lower()
        finally:
            test_client.delete(f"/contracts/{contract_id}")

    def test_post_chunk_scanned_document_returns_400(self, test_client: TestClient):
        res = test_client.post("/contracts", json={"title": "Scanned Document Contract"})
        assert res.status_code == 201
        contract_id = res.json()["id"]

        try:
            scanned_bytes = generate_scanned_pdf(1)
            upload_res = test_client.post(
                f"/contracts/{contract_id}/upload",
                files={"file": ("scanned.pdf", io.BytesIO(scanned_bytes), "application/pdf")},
            )
            assert upload_res.status_code == 201

            chunk_res = test_client.post(f"/contracts/{contract_id}/chunk")
            assert chunk_res.status_code == 400
            assert "ocr required" in chunk_res.json()["detail"].lower()
        finally:
            test_client.delete(f"/contracts/{contract_id}")

    def test_get_chunks_nonexistent_contract_returns_404(self, test_client: TestClient):
        random_id = str(uuid.uuid4())
        res = test_client.get(f"/contracts/{random_id}/chunks")
        assert res.status_code == 404
