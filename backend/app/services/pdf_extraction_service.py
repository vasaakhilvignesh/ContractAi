"""
ContractIQ — PDF Text Extraction Service (Phase 3A)

Provides pure, testable extraction functions using PyMuPDF (fitz):
  - Safe storage path resolution and traversal prevention
  - PDF document opening and encrypted PDF rejection
  - Sequential 1-indexed page extraction
  - Block-level layout preservation and simple heading heuristics
  - Character, word, and page counts
  - Blank page preservation
  - Scanned / image-only PDF detection (without OCR)
  - Clean application-level exception hierarchy
"""

import re
import uuid
from pathlib import Path
from typing import Optional

import pymupdf

from app.core.config import settings
from app.schemas.extraction import ExtractionResult, PageBlock, PageExtraction


# ====================================================================
# Custom Exceptions for Extraction
# ====================================================================


class PDFExtractionError(Exception):
    """Base exception for all PDF extraction failures."""


class PDFNotFoundError(PDFExtractionError):
    """Raised when the contract file does not exist or has not been uploaded."""


class PDFPathTraversalError(PDFExtractionError):
    """Raised when a storage key violates directory boundary safety."""


class PDFEncryptedError(PDFExtractionError):
    """Raised when a PDF is password-protected or encrypted."""


class PDFCorruptedError(PDFExtractionError):
    """Raised when a PDF file structure is corrupted or unreadable."""


class PDFPageLimitExceededError(PDFExtractionError):
    """Raised when a PDF document exceeds the defensive page limit."""


# ====================================================================
# Safe File Resolution
# ====================================================================


def resolve_pdf_path(
    storage_key: Optional[str],
    storage_base_dir: Optional[Path] = None,
) -> Path:
    """
    Safely resolves a relative storage key to an absolute Path.

    Guarantees:
      1. storage_key is provided and non-empty.
      2. Resolved path strictly resides inside storage_base_dir (preventing path traversal).
      3. Physical file exists on disk and is a regular file.

    Raises:
      PDFNotFoundError: If storage_key is empty or file does not exist on disk.
      PDFPathTraversalError: If the key attempts to escape the storage directory.
    """
    if not storage_key or not str(storage_key).strip():
        raise PDFNotFoundError(
            "Cannot extract document: no file has been uploaded for this contract."
        )

    base_dir = (storage_base_dir or settings.storage_dir).resolve()
    resolved_path = (base_dir / storage_key).resolve()

    # Path traversal assertion: target must reside within base_dir
    try:
        resolved_path.relative_to(base_dir)
    except ValueError:
        raise PDFPathTraversalError(
            "Storage path security violation: storage key attempts directory traversal."
        )

    if not resolved_path.is_file():
        raise PDFNotFoundError("Physical contract PDF file was not found on disk.")

    return resolved_path


# ====================================================================
# Layout & Heading Candidate Heuristics
# ====================================================================

# Matches typical contract clause heading prefixes (e.g., "1.", "Section 4", "Article II", "Exhibit A")
HEADING_PREFIX_REGEX = re.compile(
    r"^(?:(?:\d{1,2}(?:\.\d{1,2})*|\b[IVXLCDM]+\b|[A-Z])[\.\:\)]\s*|(?:Section|Article|Clause|Schedule|Exhibit|Appendix)\s+\w+)",
    re.IGNORECASE,
)


def is_heading_candidate_heuristic(
    text: str, bbox: tuple[float, float, float, float]
) -> bool:
    """
    Conservative heuristic to flag potential section/clause headers.

    Rules:
      - Must be short (< 120 chars, <= 2 lines).
      - Must not end with typical sentence terminators (., ,, ;).
      - Triggers on:
          1. Known contract section prefixes (e.g. '7. Termination', 'Article 3', 'Section 1.2').
          2. ALL-CAPS short titles (e.g. 'CONFIDENTIALITY', 'LIMITATION OF LIABILITY').
      - Defaults to False when uncertain to avoid structural hallucinations.
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if len(lines) > 2 or len(cleaned) > 120:
        return False

    first_line = lines[0]

    # Exclude normal sentences ending with sentence punctuation
    if cleaned.endswith((".", ",", ";")) and not re.match(r"^\d+\.\s*$", cleaned):
        return False

    # Check for prefix match (e.g. '1. Definitions', 'Section 2. Term')
    if HEADING_PREFIX_REGEX.match(first_line):
        return True

    # Check for short all-uppercase title
    words = [w for w in re.split(r"\s+", cleaned) if w.isalnum()]
    if len(words) >= 1 and cleaned.isupper() and len(cleaned) <= 80:
        return True

    return False


# ====================================================================
# Pure PDF Text Extraction
# ====================================================================


def extract_text_from_pdf(
    file_path: Path,
    contract_id: uuid.UUID,
    max_pages: Optional[int] = None,
) -> ExtractionResult:
    """
    Extracts text and block layout from a verified PDF file using PyMuPDF.

    Preserves 1-indexed page numbering, calculates character/word counts,
    preserves blank pages, and detects scanned/image-only documents.

    Args:
        file_path: Absolute Path to the validated PDF file.
        contract_id: UUID of the parent contract.
        max_pages: Maximum permitted pages before raising an error (default: settings.max_pdf_pages).

    Returns:
        ExtractionResult holding ordered PageExtraction objects.

    Raises:
        PDFEncryptedError: If PDF is encrypted/password-protected.
        PDFCorruptedError: If PyMuPDF cannot parse the document.
        PDFPageLimitExceededError: If page count exceeds max_pages limit.
    """
    limit = max_pages or settings.max_pdf_pages

    try:
        doc = pymupdf.open(file_path)
    except pymupdf.FileDataError as exc:
        raise PDFCorruptedError(f"Corrupted or invalid PDF structure: {exc}")
    except Exception as exc:
        raise PDFCorruptedError(f"Unable to open PDF document: {exc}")

    try:
        # 1. Detect password-protected or encrypted PDF
        if doc.is_encrypted or getattr(doc, "needs_pass", 0):
            raise PDFEncryptedError(
                "Password-protected and encrypted PDFs are not supported."
            )

        total_pages = len(doc)

        # 2. Defensive page count verification
        if limit and total_pages > limit:
            raise PDFPageLimitExceededError(
                f"PDF page count ({total_pages}) exceeds maximum permitted limit ({limit} pages)."
            )

        pages: list[PageExtraction] = []
        has_any_images = False

        # 3. Sequential 1-indexed page extraction
        for idx in range(total_pages):
            page_num = idx + 1
            page = doc[idx]

            # Check if page has raster images (used for scanned PDF heuristic)
            if not has_any_images and len(page.get_images()) > 0:
                has_any_images = True

            # Extract raw Unicode text
            page_text = page.get_text("text") or ""
            char_count = len(page_text)
            word_count = len(page_text.split())
            has_text = bool(page_text.strip())

            # Extract blocks for layout preservation
            page_blocks: list[PageBlock] = []
            raw_blocks = page.get_text("blocks") or []

            for b_idx, block in enumerate(raw_blocks):
                # block tuple: (x0, y0, x1, y1, text, block_no, block_type)
                # block_type == 0 is text; 1 is image
                if len(block) >= 7 and block[6] != 0:
                    continue

                b_text = block[4] if len(block) > 4 else ""
                if not b_text or not b_text.strip():
                    continue

                bbox = (
                    round(float(block[0]), 2),
                    round(float(block[1]), 2),
                    round(float(block[2]), 2),
                    round(float(block[3]), 2),
                )
                is_heading = is_heading_candidate_heuristic(b_text, bbox)

                page_blocks.append(
                    PageBlock(
                        block_index=b_idx,
                        bbox=bbox,
                        text=b_text,
                        is_heading_candidate=is_heading,
                    )
                )

            # Preserve page entry even if blank (has_text=False)
            pages.append(
                PageExtraction(
                    page_number=page_num,
                    text=page_text,
                    character_count=char_count,
                    word_count=word_count,
                    has_text=has_text,
                    blocks=page_blocks,
                )
            )

        # 4. Scanned / image-only / empty detection
        total_extracted_chars = sum(p.character_count for p in pages)

        if total_pages == 0:
            is_scanned = False
            extraction_status = "empty"
        elif total_extracted_chars == 0 and has_any_images:
            is_scanned = True
            extraction_status = "scanned_requires_ocr"
        elif total_extracted_chars < 50 and has_any_images and total_pages >= 1:
            is_scanned = True
            extraction_status = "scanned_requires_ocr"
        elif total_extracted_chars == 0 and not has_any_images:
            is_scanned = False
            extraction_status = "empty"
        else:
            is_scanned = False
            extraction_status = "success"

        return ExtractionResult(
            contract_id=contract_id,
            total_pages=total_pages,
            extracted_pages=len(pages),
            is_scanned=is_scanned,
            extraction_status=extraction_status,
            pages=pages,
        )

    finally:
        doc.close()


# ====================================================================
# Orchestrated Service Invocation
# ====================================================================


def extract_contract_document(
    storage_key: Optional[str],
    contract_id: uuid.UUID,
    storage_base_dir: Optional[Path] = None,
    max_pages: Optional[int] = None,
) -> ExtractionResult:
    """
    Convenience orchestrator: resolves storage key safely and executes extraction.

    Args:
        storage_key: Relative storage key from Contract.file_storage_key.
        contract_id: UUID of the contract.
        storage_base_dir: Optional override for base storage directory.
        max_pages: Optional page limit override.

    Returns:
        ExtractionResult
    """
    file_path = resolve_pdf_path(storage_key, storage_base_dir=storage_base_dir)
    return extract_text_from_pdf(file_path, contract_id, max_pages=max_pages)
