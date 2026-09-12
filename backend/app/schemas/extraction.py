"""
ContractIQ — PDF Text Extraction Schemas (Phase 3A)

Defines strongly typed Pydantic v2 schemas for:
  - PageBlock: structural text block coordinates and heading hints
  - PageExtraction: 1-indexed page text and token/character metrics
  - ExtractionResult: pipeline-level in-memory representation
  - ContractExtractionResponse: API response schema (without exposing full text)
"""

import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PageBlock(BaseModel):
    """
    Structural block within a page (used for header and layout detection).
    Preserves spatial coordinates (bbox) and text flow.
    """

    block_index: int = Field(..., ge=0, description="0-indexed order of the block on the page")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="Bounding box coordinates (x0, y0, x1, y1) in points"
    )
    text: str = Field(..., description="Verbatim text content of this block")
    is_heading_candidate: bool = Field(
        default=False, description="Heuristic flag indicating this block may be a section header"
    )


class PageExtraction(BaseModel):
    """
    Page-level extracted text and metadata.
    Enforces strict 1-indexed page numbering for lineage tracing in Phase 3B.
    """

    page_number: int = Field(
        ..., ge=1, description="1-indexed page number matching source PDF page"
    )
    text: str = Field(..., description="Verbatim extracted text for this page")
    character_count: int = Field(
        ..., ge=0, description="Total characters extracted from this page"
    )
    word_count: int = Field(..., ge=0, description="Total words extracted from this page")
    has_text: bool = Field(
        ..., description="True if meaningful text is present; False if page is blank or image-only"
    )
    blocks: list[PageBlock] = Field(
        default_factory=list, description="Extracted structural blocks for layout preservation"
    )


class ExtractionResult(BaseModel):
    """
    Complete document extraction payload passed to downstream chunking (Phase 3B).
    Held in-memory as an intermediate pipeline representation.
    """

    contract_id: uuid.UUID = Field(..., description="UUID of the parent contract")
    total_pages: int = Field(..., ge=0, description="Total pages in the source PDF")
    extracted_pages: int = Field(
        ..., ge=0, description="Number of pages successfully processed"
    )
    is_scanned: bool = Field(
        ..., description="True if no extractable text was found across the document"
    )
    extraction_status: str = Field(
        ...,
        description="Outcome: 'success' | 'empty' | 'scanned_requires_ocr' | 'partial'",
    )
    pages: list[PageExtraction] = Field(
        default_factory=list, description="Ordered list of page extraction objects"
    )


class ContractExtractionResponse(BaseModel):
    """
    API response schema returned by POST /contracts/{contract_id}/extract.
    Summarizes extraction results without dumping raw PDF text over HTTP.
    """

    contract_id: uuid.UUID = Field(..., description="UUID of the contract")
    total_pages: int = Field(..., ge=0, description="Total pages in the source PDF")
    extracted_pages: int = Field(
        ..., ge=0, description="Number of pages successfully processed"
    )
    is_scanned: bool = Field(
        ..., description="True if the document appears to be scanned/image-only"
    )
    extraction_status: str = Field(
        ..., description="Status of extraction: success | empty | scanned_requires_ocr"
    )
    processing_status: str = Field(
        ..., description="Current processing lifecycle status of the contract"
    )
    page_count: Optional[int] = Field(
        default=None, description="Persisted page_count on the contract record"
    )
    message: Optional[str] = Field(
        default=None, description="Human-readable summary of extraction result"
    )

    model_config = ConfigDict(from_attributes=True)
