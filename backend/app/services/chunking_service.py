"""
ContractIQ — Clause-Aware Document Chunking Service (Phase 3B)

Implements deterministic, clause-aware document chunking for contract PDFs.

Pipeline:
  ExtractionResult (Phase 3A)
         ↓
  Text Normalization (text_normalization_service)
         ↓
  Clause/Section Boundary Detection & Propagation
         ↓
  Page-Bounded Chunk Assembly (with sentence split & overlap fallback)
         ↓
  DocumentChunk Persistence (Idempotent, embedding=None)

Key Invariants:
  - Chunks are page-bounded: page_number matches source PDF page (1-indexed).
  - chunk_index is globally sequential across the contract (0, 1, 2, ..., N-1).
  - char_start and char_end refer strictly to offsets within the normalized page text.
  - section_header propagates across chunks and across pages until a new header is found.
  - embedding is left NULL (reserved for Phase 3C).
  - Idempotency: Re-running replaces existing chunks in a single atomic transaction.
"""

import re
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.chunk import (
    ChunkCreate,
    ContractChunkingResponse,
    DocumentChunkSummary,
)
from app.schemas.extraction import ExtractionResult, PageExtraction
from app.services.text_normalization_service import (
    is_noise_text,
    normalize_text,
)


# ====================================================================
# Chunking Configuration Defaults
# ====================================================================

DEFAULT_TARGET_CHUNK_SIZE = 1200
DEFAULT_MAX_CHUNK_SIZE = 2000
DEFAULT_MIN_CHUNK_SIZE = 100
DEFAULT_OVERLAP = 150


# ====================================================================
# Custom Exceptions
# ====================================================================


class ChunkingError(Exception):
    """Base exception for chunking pipeline errors."""


class ScannedDocumentChunkingError(ChunkingError):
    """Raised when attempting to chunk a scanned document that requires OCR."""


class EmptyDocumentChunkingError(ChunkingError):
    """Raised when contract has no extractable text content to chunk."""


# ====================================================================
# Heading & Clause Boundary Detection
# ====================================================================

# Matches common contract section/clause prefixes:
# Examples:
#   - "1. Definitions", "1.1 Confidentiality", "12.2 Term"
#   - "SECTION 1", "SECTION 1 — DEFINITIONS", "Section 4.2"
#   - "ARTICLE 5", "ARTICLE V — TERMINATION"
#   - "(a) Invoicing", "(i) Taxes"
#   - "Exhibit A — Statement of Work", "Schedule 1"
CLAUSE_HEADING_PATTERNS = [
    # Explicit legal prefix: SECTION, ARTICLE, CLAUSE, EXHIBIT, SCHEDULE, APPENDIX
    re.compile(
        r"^(?:SECTION|ARTICLE|CLAUSE|EXHIBIT|SCHEDULE|APPENDIX)\s+[0-9IVXLCDM]+(?:\.[0-9]+)*\.?"
        r"(?:\s*[-—–:]\s*|\s+|$).*",
        re.IGNORECASE,
    ),
    # Numbered decimal sections: "1. Definitions", "1.1 Term", "12.3.1 Limitation"
    re.compile(
        r"^(?:\d{1,2}(?:\.\d{1,2})+|\d{1,2}\.)\s+[A-Z0-9].*"
    ),
    # Sub-clause enumeration: "(a) Scope of Services", "(i) Payment terms"
    re.compile(
        r"^\((?:[a-z]|[0-9]{1,2}|[ivxlcdm]+)\)\s+[A-Z].*"
    ),
]


def is_heading_line(line: str) -> bool:
    """
    Evaluates whether a single line of text represents a legal section or clause heading.

    Criteria:
      - Line must be non-empty and reasonably short (<= 120 characters).
      - Must not end with typical non-heading punctuation (comma, semicolon).
      - Matches known structural prefixes (Section, Article, numbered decimals, sub-clauses)
        OR represents a short all-uppercase title (e.g. "LIMITATION OF LIABILITY").
    """
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 120:
        return False

    # Exclude normal lines ending with comma or semicolon
    if cleaned.endswith((",", ";")):
        return False

    # Check structural heading patterns first
    for pattern in CLAUSE_HEADING_PATTERNS:
        if pattern.match(cleaned):
            return True

    # If line ends with period and did not match a heading pattern, it's a regular sentence
    if cleaned.endswith(".") and not re.match(r"^\d+\.\s*$", cleaned):
        return False

    # Check for short all-uppercase title (e.g., "INDEMNIFICATION", "GOVERNING LAW")
    words = [w for w in re.split(r"\s+", cleaned) if w.isalnum()]
    if len(words) >= 1 and cleaned.isupper() and len(cleaned) <= 80:
        # Exclude common uppercase abbreviations of 4 chars or less
        if len(words) == 1 and len(cleaned) <= 4:
            return False
        return True

    return False


def extract_heading_from_unit(unit: str) -> Optional[str]:
    """
    Inspects the beginning of a text unit (paragraph) to determine if it starts
    with or consists of a section heading.
    """
    first_line = unit.split("\n", 1)[0].strip()
    if is_heading_line(first_line):
        return first_line
    return None


# ====================================================================
# Sentence & Paragraph Splitting
# ====================================================================

SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.?!])\s+(?=[A-Z0-9\(\"'])")


def split_oversized_text(
    text: str,
    target_size: int,
    max_size: int,
    overlap: int,
) -> list[str]:
    """
    Splits text that exceeds max_size into sub-chunks using sentence boundaries,
    falling back to deterministic character slices if sentences are abnormally long.
    Applies overlap between consecutive split slices.
    """
    sentences = [s.strip() for s in SENTENCE_SPLIT_REGEX.split(text) if s.strip()]
    if not sentences:
        sentences = [text.strip()]

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_length = 0

    for sent in sentences:
        sent_len = len(sent)

        # Handle extraordinarily long single sentence (longer than max_size)
        if sent_len > max_size:
            # Flush accumulated sentences first
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_length = 0

            # Deterministic hard split of the massive sentence
            start = 0
            while start < sent_len:
                end = min(start + target_size, sent_len)
                sub_slice = sent[start:end].strip()
                if sub_slice:
                    chunks.append(sub_slice)
                if end >= sent_len:
                    break
                start += max(1, target_size - overlap)
            continue

        if current_length + sent_len + 1 > target_size and current_sentences:
            chunk_text = " ".join(current_sentences)
            chunks.append(chunk_text)

            # Apply overlap: retain tail sentence(s) that fit within overlap limit
            overlap_sentences: list[str] = []
            overlap_len = 0
            for prev_sent in reversed(current_sentences):
                if overlap_len + len(prev_sent) + 1 <= overlap:
                    overlap_sentences.insert(0, prev_sent)
                    overlap_len += len(prev_sent) + 1
                else:
                    break

            current_sentences = overlap_sentences + [sent]
            current_length = sum(len(s) for s in current_sentences) + len(current_sentences) - 1
        else:
            current_sentences.append(sent)
            current_length += sent_len + (1 if current_length > 0 else 0)

    if current_sentences:
        chunks.append(" ".join(current_sentences))

    # Defensive guarantee: Ensure no chunk exceeds max_size
    guaranteed_chunks: list[str] = []
    for chk in chunks:
        if len(chk) <= max_size:
            guaranteed_chunks.append(chk)
        else:
            # Hard boundary fallback
            start = 0
            chk_len = len(chk)
            while start < chk_len:
                end = min(start + target_size, chk_len)
                slice_text = chk[start:end].strip()
                if slice_text:
                    guaranteed_chunks.append(slice_text)
                if end >= chk_len:
                    break
                start += max(1, target_size - overlap)

    return guaranteed_chunks


# ====================================================================
# Page-Level Chunk Builder
# ====================================================================


def chunk_page_text(
    page: PageExtraction,
    current_section_header: Optional[str],
    global_chunk_index_start: int,
    target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    max_size: int = DEFAULT_MAX_CHUNK_SIZE,
    min_size: int = DEFAULT_MIN_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> tuple[list[dict], Optional[str], int]:
    """
    Chunks a single page's text respecting clause boundaries, paragraph breaks,
    and section headers.

    Returns:
        tuple of (chunk_dicts, updated_section_header, next_global_chunk_index)
    """
    if not page.has_text or not page.text.strip():
        return [], current_section_header, global_chunk_index_start

    # 1. Normalize page text
    normalized_page_text = normalize_text(page.text)
    if not normalized_page_text or is_noise_text(normalized_page_text):
        return [], current_section_header, global_chunk_index_start

    # 2. Divide page into paragraph units
    raw_units = [u.strip() for u in normalized_page_text.split("\n\n") if u.strip()]
    if not raw_units:
        return [], current_section_header, global_chunk_index_start

    # 3. Assemble units into clause-aware chunks
    emitted_chunks: list[dict] = []
    current_header = current_section_header
    chunk_index = global_chunk_index_start

    accumulated_units: list[str] = []
    accumulated_length = 0

    def emit_chunk(chunk_text: str, header: Optional[str]) -> None:
        nonlocal chunk_index
        cleaned = chunk_text.strip()
        if not cleaned:
            return

        # Locate offsets within normalized page text
        # Search starting from 0 or last known position
        char_start = normalized_page_text.find(cleaned)
        char_end = char_start + len(cleaned) if char_start != -1 else None
        if char_start == -1:
            char_start = None

        emitted_chunks.append({
            "page_number": page.page_number,
            "chunk_index": chunk_index,
            "char_start": char_start,
            "char_end": char_end,
            "section_header": header,
            "text": cleaned,
        })
        chunk_index += 1

    for unit in raw_units:
        detected_header = extract_heading_from_unit(unit)

        # If this unit is a heading or starts with a major heading:
        if detected_header:
            # If we already have accumulated text under a previous section, flush it
            if accumulated_units:
                accumulated_text = "\n\n".join(accumulated_units)
                emit_chunk(accumulated_text, current_header)
                accumulated_units = []
                accumulated_length = 0

            # Update governing section header
            current_header = detected_header

        unit_len = len(unit)

        # If a single unit exceeds max_size, divide it
        if unit_len > max_size:
            if accumulated_units:
                accumulated_text = "\n\n".join(accumulated_units)
                emit_chunk(accumulated_text, current_header)
                accumulated_units = []
                accumulated_length = 0

            sub_chunks = split_oversized_text(unit, target_size, max_size, overlap)
            for sub in sub_chunks:
                emit_chunk(sub, current_header)
            continue

        # If adding unit exceeds target_size:
        if accumulated_length + unit_len + 2 > target_size and accumulated_units:
            accumulated_text = "\n\n".join(accumulated_units)
            emit_chunk(accumulated_text, current_header)
            accumulated_units = [unit]
            accumulated_length = unit_len
        else:
            accumulated_units.append(unit)
            accumulated_length += unit_len + (2 if accumulated_length > 0 else 0)

    # Flush remaining accumulated units on this page
    if accumulated_units:
        accumulated_text = "\n\n".join(accumulated_units)
        # Small chunk handling:
        # If the accumulated text is below min_size:
        if len(accumulated_text) < min_size:
            # Check if it's pure noise (e.g. stray page number)
            if is_noise_text(accumulated_text):
                pass
            elif (
                emitted_chunks
                and emitted_chunks[-1]["section_header"] == current_header
            ):
                # Merge into preceding chunk on same page ONLY if they share the same section header
                last_chunk = emitted_chunks[-1]
                combined = f"{last_chunk['text']}\n\n{accumulated_text}"
                if len(combined) <= max_size:
                    last_chunk["text"] = combined
                    # Recompute char offsets
                    new_start = normalized_page_text.find(combined)
                    if new_start != -1:
                        last_chunk["char_start"] = new_start
                        last_chunk["char_end"] = new_start + len(combined)
                else:
                    # Keep meaningful short legal clause as standalone chunk
                    emit_chunk(accumulated_text, current_header)
            else:
                # Different section header or no previous chunk: emit standalone chunk
                emit_chunk(accumulated_text, current_header)
        else:
            emit_chunk(accumulated_text, current_header)

    return emitted_chunks, current_header, chunk_index


# ====================================================================
# Full Document Chunking Orchestrator
# ====================================================================


def chunk_extraction_result(
    extraction_result: ExtractionResult,
    target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    max_size: int = DEFAULT_MAX_CHUNK_SIZE,
    min_size: int = DEFAULT_MIN_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[ChunkCreate]:
    """
    Transforms an in-memory Phase 3A ExtractionResult into an ordered list
    of clause-aware ChunkCreate records.

    Raises:
        ScannedDocumentChunkingError: If document is scanned / requires OCR.
        EmptyDocumentChunkingError: If document has 0 total pages or 0 extractable text.
    """
    if extraction_result.is_scanned or extraction_result.extraction_status == "scanned_requires_ocr":
        raise ScannedDocumentChunkingError(
            "Cannot chunk scanned contract document: native text extraction yielded no text layer (OCR required)."
        )

    if extraction_result.total_pages == 0:
        raise EmptyDocumentChunkingError("Cannot chunk contract: document contains 0 pages.")

    all_chunks: list[ChunkCreate] = []
    current_section_header: Optional[str] = None
    global_chunk_index = 0

    # Ensure pages are processed in strict ascending order (1-indexed)
    sorted_pages = sorted(extraction_result.pages, key=lambda p: p.page_number)

    for page in sorted_pages:
        page_chunks, current_section_header, global_chunk_index = chunk_page_text(
            page=page,
            current_section_header=current_section_header,
            global_chunk_index_start=global_chunk_index,
            target_size=target_size,
            max_size=max_size,
            min_size=min_size,
            overlap=overlap,
        )

        for chk_dict in page_chunks:
            all_chunks.append(
                ChunkCreate(
                    contract_id=extraction_result.contract_id,
                    page_number=chk_dict["page_number"],
                    chunk_index=chk_dict["chunk_index"],
                    char_start=chk_dict["char_start"],
                    char_end=chk_dict["char_end"],
                    section_header=chk_dict["section_header"],
                    text=chk_dict["text"],
                )
            )

    return all_chunks


# ====================================================================
# Persistence & Idempotency
# ====================================================================


def persist_contract_chunks(
    db: Session,
    contract_id: uuid.UUID,
    chunks: list[ChunkCreate],
) -> list[DocumentChunk]:
    """
    Persists a complete set of DocumentChunk records for a contract in an atomic transaction.

    Idempotency:
      Deletes all existing DocumentChunk rows for this contract_id before inserting new rows,
      ensuring no duplicate chunks or orphaned records exist upon rerun.
    """
    # 1. Remove existing chunks for this contract
    db.query(DocumentChunk).filter(DocumentChunk.contract_id == contract_id).delete()

    # 2. Bulk instantiate new rows
    db_chunks: list[DocumentChunk] = []
    for chk in chunks:
        db_chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=chk.contract_id,
            page_number=chk.page_number,
            chunk_index=chk.chunk_index,
            char_start=chk.char_start,
            char_end=chk.char_end,
            section_header=chk.section_header,
            text=chk.text,
            embedding=None,  # Intentionally None: populated in Phase 3C / Phase 4
        )
        db_chunks.append(db_chunk)

    db.add_all(db_chunks)
    db.commit()

    # Refresh items to ensure server defaults and IDs are synchronized
    for item in db_chunks:
        db.refresh(item)

    return db_chunks


def list_contract_chunks(
    db: Session,
    contract_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[DocumentChunk], int]:
    """
    Retrieves paginated DocumentChunk records for a given contract.
    Sorted deterministically by chunk_index asc.
    """
    base_query = select(DocumentChunk).where(DocumentChunk.contract_id == contract_id)
    total = db.query(DocumentChunk).filter(DocumentChunk.contract_id == contract_id).count()

    paginated_query = base_query.order_by(DocumentChunk.chunk_index.asc()).offset(offset).limit(limit)
    items = list(db.scalars(paginated_query).all())

    return items, total
