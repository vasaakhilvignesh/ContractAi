"""
ContractIQ — Contract REST API Router

Provides CRUD endpoints for the Contract resource:
  - POST   /contracts              (create contract)
  - GET    /contracts              (list contracts with pagination & filtering)
  - GET    /contracts/{contract_id} (get contract by ID)
  - PATCH  /contracts/{contract_id} (update contract fields)
  - DELETE /contracts/{contract_id} (delete contract)
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.contract import (
    ContractCreate,
    ContractListResponse,
    ContractResponse,
    ContractUpdate,
    ContractUploadResponse,
    ContractProcessingStatusResponse,
    ContractProcessingStatusUpdate,
    ProcessingStatus,
)
from app.schemas.chunk import (
    ContractChunkingResponse,
    ContractChunkListResponse,
    DocumentChunkSummary,
)
from app.schemas.extraction import ContractExtractionResponse
from app.schemas.embedding import (
    ContractEmbedRequest,
    ContractEmbeddingResponse,
)
from app.schemas.query import (
    ContractQueryRequest,
    ContractQueryResponse,
    ContractKeywordQueryRequest,
    ContractKeywordQueryResponse,
    ContractHybridQueryRequest,
    ContractHybridQueryResponse,
)
from app.schemas.clause import (
    ContractClauseExtractionRequest,
    ContractClauseExtractionResponse,
    ContractClauseListResponse,
)
from app.schemas.obligation import (
    ContractObligationExtractionRequest,
    ContractObligationExtractionResponse,
    ContractObligationListResponse,
)
from app.schemas.contract_fact import (
    ContractFactExtractionRequest,
    ContractFactExtractionResponse,
    ContractFactListResponse,
)
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceResponse,
    EvidenceListResponse,
    EvidenceLineage,
    EvidenceLineageListResponse,
    EvidenceValidationSummary,
)
from app.services import (
    contract_service,
    storage_service,
    pdf_extraction_service,
    chunking_service,
    embedding_generation_service,
    retrieval_service,
    keyword_retrieval_service,
    hybrid_retrieval_service,
    clause_extraction_service,
    obligation_extraction_service,
    contract_fact_service,
    evidence_service,
)
from app.services.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
)
from app.services.structured_output_validator import (
    StructuredOutputError,
    StructuredOutputConfigurationError,
)



router = APIRouter(prefix="/contracts", tags=["Contracts"])



@router.post(
    "",
    response_model=ContractResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contract",
    description="Creates and persists a new contract record with initial metadata.",
)
def create_contract(
    contract_in: ContractCreate,
    db: Session = Depends(get_db),
) -> ContractResponse:
    """Create a new contract."""
    return contract_service.create_contract(db=db, contract_in=contract_in)


@router.get(
    "",
    response_model=ContractListResponse,
    status_code=status.HTTP_200_OK,
    summary="List contracts",
    description="Returns a paginated list of contracts with optional attribute filtering.",
)
def list_contracts(
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    vendor: Optional[str] = Query(None, description="Filter by vendor name substring"),
    contract_type: Optional[str] = Query(None, description="Filter by contract type"),
    risk_level: Optional[str] = Query(None, description="Filter by aggregate risk level"),
    db: Session = Depends(get_db),
) -> ContractListResponse:
    """List contracts with pagination and basic filtering."""
    items, total = contract_service.list_contracts(
        db=db,
        offset=offset,
        limit=limit,
        status=status,
        vendor=vendor,
        contract_type=contract_type,
        risk_level=risk_level,
    )
    return ContractListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{contract_id}",
    response_model=ContractResponse,
    status_code=status.HTTP_200_OK,
    summary="Get contract by ID",
    description="Retrieves a single contract record by its UUID.",
)
def get_contract(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ContractResponse:
    """Get a contract by UUID."""
    contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    return contract


@router.patch(
    "/{contract_id}",
    response_model=ContractResponse,
    status_code=status.HTTP_200_OK,
    summary="Update contract",
    description="Updates one or more fields on an existing contract record.",
)
def update_contract(
    contract_id: uuid.UUID,
    contract_in: ContractUpdate,
    db: Session = Depends(get_db),
) -> ContractResponse:
    """Partially update an existing contract."""
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    return contract_service.update_contract(
        db=db,
        db_contract=db_contract,
        contract_in=contract_in,
    )


@router.delete(
    "/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete contract",
    description="Permanently deletes a contract and cascades to dependent entities.",
)
def delete_contract(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a contract."""
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    contract_service.delete_contract(db=db, db_contract=db_contract)


@router.post(
    "/{contract_id}/upload",
    response_model=ContractUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload contract PDF document",
    description=(
        "Uploads a PDF document and associates it with an existing contract. "
        "Validates file type, size, and PDF signature (%PDF-). "
        "Stores the file securely using path-traversal resistant identifiers."
    ),
)
async def upload_contract_pdf(
    contract_id: uuid.UUID,
    file: UploadFile = File(..., description="PDF file to upload"),
    db: Session = Depends(get_db),
) -> ContractUploadResponse:
    """Upload and associate a contract PDF."""
    # 1. Confirm the contract exists
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )

    # 2. Validate the file format, extension, size, and %PDF- signature
    content, file_size = await storage_service.validate_pdf_upload(file)

    # 3. Save the file to safe storage
    saved_path, storage_key = storage_service.save_contract_file(
        contract_id=contract_id,
        content=content,
    )

    clean_file_name = storage_service.sanitize_filename(file.filename)
    old_storage_key = db_contract.file_storage_key

    # 4. Associate file with contract in database
    try:
        updated_contract = contract_service.associate_contract_file(
            db=db,
            db_contract=db_contract,
            file_name=clean_file_name,
            storage_key=storage_key,
            processing_status="uploaded",
        )
    except Exception:
        # Rollback and clean up saved file to avoid orphaned files on disk
        storage_service.remove_stored_file(saved_path)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record uploaded contract file in database.",
        )

    # 5. Clean up old file if this was a re-upload and old file exists
    if old_storage_key and old_storage_key != storage_key:
        storage_service.remove_stored_file(old_storage_key)

    return ContractUploadResponse(
        contract_id=updated_contract.id,
        file_name=updated_contract.file_name or clean_file_name,
        file_size=file_size,
        content_type=file.content_type or "application/pdf",
        storage_key=updated_contract.file_storage_key or storage_key,
        processing_status=updated_contract.processing_status,
        uploaded_at=updated_contract.updated_at,
    )


@router.get(
    "/{contract_id}/processing-status",
    response_model=ContractProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get contract processing status",
    description="Retrieves the current document processing status and error state for a contract.",
)
def get_contract_processing_status(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ContractProcessingStatusResponse:
    """Get contract processing status."""
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    return ContractProcessingStatusResponse(
        contract_id=db_contract.id,
        processing_status=db_contract.processing_status,
        processing_error=db_contract.processing_error,
        file_name=db_contract.file_name,
        updated_at=db_contract.updated_at,
    )


@router.patch(
    "/{contract_id}/processing-status",
    response_model=ContractProcessingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Update contract processing status",
    description="Transitions contract document processing status along the defined state lifecycle.",
)
def update_contract_processing_status(
    contract_id: uuid.UUID,
    status_in: ContractProcessingStatusUpdate,
    db: Session = Depends(get_db),
) -> ContractProcessingStatusResponse:
    """Transition contract processing status."""
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )

    try:
        updated_contract = contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=status_in.status,
            error_message=status_in.error_message,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ContractProcessingStatusResponse(
        contract_id=updated_contract.id,
        processing_status=updated_contract.processing_status,
        processing_error=updated_contract.processing_error,
        file_name=updated_contract.file_name,
        updated_at=updated_contract.updated_at,
    )


@router.post(
    "/{contract_id}/extract",
    response_model=ContractExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text and structure from uploaded contract PDF",
    description=(
        "Safely loads the uploaded PDF document, parses text and layout blocks "
        "preserving 1-indexed page boundaries, detects scanned documents, and updates "
        "contract page_count and processing status."
    ),
)
def extract_contract_text(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ContractExtractionResponse:
    """Extract text from uploaded contract PDF."""
    # 1. Verify contract exists
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )

    # 2. Verify file has been uploaded
    if not db_contract.file_storage_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot extract text: no document file has been uploaded for this contract.",
        )

    # 3. Transition contract lifecycle into processing state
    current_status = db_contract.processing_status
    if current_status == ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract document has already completed processing. Re-upload a document to re-process.",
        )

    # Transition to QUEUED then PROCESSING if currently UPLOADED or FAILED
    try:
        if current_status in (ProcessingStatus.UPLOADED.value, ProcessingStatus.FAILED.value):
            db_contract = contract_service.update_contract_processing_status(
                db=db, db_contract=db_contract, new_status=ProcessingStatus.QUEUED
            )
            db_contract = contract_service.update_contract_processing_status(
                db=db, db_contract=db_contract, new_status=ProcessingStatus.PROCESSING
            )
        elif current_status == ProcessingStatus.QUEUED.value:
            db_contract = contract_service.update_contract_processing_status(
                db=db, db_contract=db_contract, new_status=ProcessingStatus.PROCESSING
            )
        # If already in PROCESSING state, proceed directly
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to advance processing state: {exc}",
        )

    # 4. Perform extraction with PyMuPDF
    try:
        extraction_result = pdf_extraction_service.extract_contract_document(
            storage_key=db_contract.file_storage_key,
            contract_id=db_contract.id,
        )
    except pdf_extraction_service.PDFNotFoundError:
        contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.FAILED,
            error_message="Physical PDF file missing from storage.",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical contract PDF file not found on disk.",
        )
    except pdf_extraction_service.PDFPathTraversalError:
        contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.FAILED,
            error_message="Security violation: invalid storage path.",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path security violation: storage key attempts directory traversal.",
        )
    except pdf_extraction_service.PDFEncryptedError as exc:
        contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.FAILED,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password-protected and encrypted PDFs are not supported.",
        )
    except (
        pdf_extraction_service.PDFCorruptedError,
        pdf_extraction_service.PDFPageLimitExceededError,
    ) as exc:
        contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.FAILED,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.FAILED,
            error_message="An unexpected error occurred during PDF text extraction.",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during PDF text extraction.",
        )

    # 5. Update Contract.page_count
    db_contract.page_count = extraction_result.total_pages
    db.commit()
    db.refresh(db_contract)

    # 6. Lifecycle transition based on extraction outcome
    if (
        extraction_result.is_scanned
        or extraction_result.extraction_status == "scanned_requires_ocr"
    ):
        db_contract = contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.FAILED,
            error_message="Scanned document detected: native text extraction yielded no characters (requires OCR).",
        )
        message = (
            "Document appears to be scanned or image-only. No text layer found (requires OCR)."
        )
    else:
        db_contract = contract_service.update_contract_processing_status(
            db=db,
            db_contract=db_contract,
            new_status=ProcessingStatus.COMPLETED,
        )
        message = f"Successfully extracted text from {extraction_result.extracted_pages} pages."

    return ContractExtractionResponse(
        contract_id=db_contract.id,
        total_pages=extraction_result.total_pages,
        extracted_pages=extraction_result.extracted_pages,
        is_scanned=extraction_result.is_scanned,
        extraction_status=extraction_result.extraction_status,
        processing_status=db_contract.processing_status,
        page_count=db_contract.page_count,
        message=message,
    )


@router.post(
    "/{contract_id}/chunk",
    response_model=ContractChunkingResponse,
    status_code=status.HTTP_200_OK,
    summary="Normalize text and generate clause-aware chunks from contract",
    description=(
        "Extracts text, performs conservative normalization, segments text into clause-aware "
        "chunks preserving page lineage and section headers, and idempotently persists "
        "DocumentChunk records in an atomic transaction."
    ),
)
def chunk_contract(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ContractChunkingResponse:
    """Normalize text and generate clause-aware chunks from uploaded contract."""
    # 1. Verify contract exists
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )

    # 2. Verify file has been uploaded
    if not db_contract.file_storage_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot chunk document: no file has been uploaded for this contract.",
        )

    # 3. Perform text extraction using Phase 3A service
    try:
        extraction_result = pdf_extraction_service.extract_contract_document(
            storage_key=db_contract.file_storage_key,
            contract_id=db_contract.id,
        )
    except pdf_extraction_service.PDFNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical contract PDF file not found on disk.",
        )
    except pdf_extraction_service.PDFPathTraversalError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path security violation: storage key attempts directory traversal.",
        )
    except pdf_extraction_service.PDFEncryptedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except (
        pdf_extraction_service.PDFCorruptedError,
        pdf_extraction_service.PDFPageLimitExceededError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during PDF text extraction.",
        )

    # 4. Scanned and empty document rejection
    if (
        extraction_result.is_scanned
        or extraction_result.extraction_status == "scanned_requires_ocr"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot chunk scanned contract document: native text extraction yielded no text layer (OCR required).",
        )

    if extraction_result.total_pages == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot chunk contract document: file contains 0 pages.",
        )

    # 5. Execute clause-aware chunking pipeline
    try:
        chunks_to_create = chunking_service.chunk_extraction_result(extraction_result)
    except chunking_service.ScannedDocumentChunkingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except chunking_service.EmptyDocumentChunkingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate chunks from contract text: {exc}",
        )

    # 6. Idempotently persist chunks inside atomic transaction
    try:
        db_chunks = chunking_service.persist_contract_chunks(
            db=db,
            contract_id=db_contract.id,
            chunks=chunks_to_create,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist document chunks in database.",
        )

    # 7. Update contract page_count if not already populated
    if not db_contract.page_count or db_contract.page_count != extraction_result.total_pages:
        db_contract.page_count = extraction_result.total_pages
        db.commit()
        db.refresh(db_contract)

    # 8. Construct sample chunk summaries
    samples = [
        DocumentChunkSummary(
            id=chk.id,
            page_number=chk.page_number,
            chunk_index=chk.chunk_index,
            section_header=chk.section_header,
            text_snippet=chk.text[:120] + "..." if len(chk.text) > 120 else chk.text,
            char_count=len(chk.text),
        )
        for chk in db_chunks[:5]
    ]

    return ContractChunkingResponse(
        contract_id=db_contract.id,
        total_chunks=len(db_chunks),
        total_pages=extraction_result.total_pages,
        processing_status=db_contract.processing_status,
        sample_chunks=samples,
        message=(
            f"Successfully generated and persisted {len(db_chunks)} clause-aware "
            f"chunks across {extraction_result.total_pages} pages."
        ),
    )


@router.get(
    "/{contract_id}/chunks",
    response_model=ContractChunkListResponse,
    status_code=status.HTTP_200_OK,
    summary="List document chunks for contract",
    description="Retrieves a paginated list of persisted DocumentChunk records for a contract.",
)
def list_contract_chunks(
    contract_id: uuid.UUID,
    offset: int = Query(0, ge=0, description="Number of chunks to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of chunks to return"),
    db: Session = Depends(get_db),
) -> ContractChunkListResponse:
    """List document chunks with pagination."""
    db_contract = contract_service.get_contract(db=db, contract_id=contract_id)
    if not db_contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )

    items, total = chunking_service.list_contract_chunks(
        db=db,
        contract_id=contract_id,
        offset=offset,
        limit=limit,
    )
    return ContractChunkListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{contract_id}/embed",
    response_model=ContractEmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and persist dense vector embeddings for contract chunks",
    description=(
        "Retrieves persisted DocumentChunk records for a contract, generates 768-dimensional "
        "dense vector embeddings using Gemini (gemini-embedding-2) via the embedding provider, "
        "and atomically persists them to PostgreSQL. Supports idempotent execution."
    ),
)
async def embed_contract(
    contract_id: uuid.UUID,
    payload: Optional[ContractEmbedRequest] = None,
    db: Session = Depends(get_db),
) -> ContractEmbeddingResponse:
    """Generate and persist vector embeddings for contract chunks."""
    force_reembed = payload.force_reembed if payload else False
    try:
        return await embedding_generation_service.generate_contract_embeddings(
            db=db,
            contract_id=contract_id,
            force_reembed=force_reembed,
        )
    except embedding_generation_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except embedding_generation_service.NoChunksFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding provider configuration error: {exc}",
        )
    except (EmbeddingProviderError, embedding_generation_service.EmbeddingGenerationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding generation failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during embedding generation: {exc}",
        )


@router.post(
    "/{contract_id}/query",
    response_model=ContractQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic vector retrieval for contract chunks",
    description=(
        "Embeds the search query using Gemini (gemini-embedding-2) with RETRIEVAL_QUERY "
        "and executes a pgvector cosine similarity search (<=>) against the contract's 768-dimensional "
        "chunk embeddings, returning ranked ChunkMatch results ordered by similarity descending."
    ),
)
async def query_contract(
    contract_id: uuid.UUID,
    payload: ContractQueryRequest,
    db: Session = Depends(get_db),
) -> ContractQueryResponse:
    """Execute semantic vector retrieval for contract chunks."""
    try:
        return await retrieval_service.query_contract_chunks(
            db=db,
            contract_id=contract_id,
            query=payload.query,
            top_k=payload.top_k,
            min_similarity=payload.min_similarity,
        )
    except retrieval_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except (retrieval_service.NoChunksFoundError, retrieval_service.NoEmbeddedChunksError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except EmbeddingConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding provider configuration error: {exc}",
        )
    except (EmbeddingProviderError, retrieval_service.RetrievalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Semantic retrieval failed during provider call: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during semantic retrieval: {exc}",
        )


@router.post(
    "/{contract_id}/keyword-query",
    response_model=ContractKeywordQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Keyword full-text retrieval for contract chunks",
    description=(
        "Executes a PostgreSQL Full-Text Search query (websearch_to_tsquery) against the contract's "
        "document chunks using cover density ranking (ts_rank_cd), returning ranked KeywordChunkMatch "
        "results ordered by relevance descending. Strictly contract-scoped, no embeddings returned."
    ),
)
async def query_contract_keywords(
    contract_id: uuid.UUID,
    payload: ContractKeywordQueryRequest,
    db: Session = Depends(get_db),
) -> ContractKeywordQueryResponse:
    """Execute keyword full-text retrieval for contract chunks."""
    try:
        return await keyword_retrieval_service.query_contract_keywords(
            db=db,
            contract_id=contract_id,
            query=payload.query,
            top_k=payload.top_k,
        )
    except keyword_retrieval_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except keyword_retrieval_service.KeywordRetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword retrieval failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during keyword retrieval: {exc}",
        )


@router.post(
    "/{contract_id}/hybrid-query",
    response_model=ContractHybridQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid retrieval with Reciprocal Rank Fusion (RRF)",
    description=(
        "Combines semantic vector retrieval (pgvector cosine similarity) and keyword retrieval "
        "(PostgreSQL Full-Text Search) using Reciprocal Rank Fusion (RRF: score = sum(1 / (k + rank))). "
        "Deduplicates chunks, preserves chunk metadata, and returns transparent rank and score provenance. "
        "Strictly contract-scoped, no embeddings returned."
    ),
)
async def query_contract_hybrid(
    contract_id: uuid.UUID,
    payload: ContractHybridQueryRequest,
    db: Session = Depends(get_db),
) -> ContractHybridQueryResponse:
    """Execute hybrid retrieval combining semantic and keyword search via RRF."""
    try:
        return await hybrid_retrieval_service.query_contract_hybrid(
            db=db,
            contract_id=contract_id,
            query=payload.query,
            top_k=payload.top_k,
            rrf_k=payload.rrf_k,
        )
    except hybrid_retrieval_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except hybrid_retrieval_service.HybridRetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid retrieval failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during hybrid retrieval: {exc}",
        )


@router.post(
    "/{contract_id}/extract-clauses",
    response_model=ContractClauseExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract structured clauses from contract chunks",
    description=(
        "Extracts structured legal clauses (clause type, verbatim text, section/label, page number) "
        "from contract document chunks using the StructuredLLMProvider. Preserves strict source "
        "traceability (clause -> chunk -> page -> contract). Operation is idempotent unless force_reextract=True."
    ),
)
async def extract_clauses(
    contract_id: uuid.UUID,
    payload: Optional[ContractClauseExtractionRequest] = None,
    db: Session = Depends(get_db),
) -> ContractClauseExtractionResponse:
    """Extract and persist structured clauses for a contract."""
    force = payload.force_reextract if payload else False
    try:
        return await clause_extraction_service.extract_contract_clauses(
            db=db,
            contract_id=contract_id,
            force_reextract=force,
        )
    except clause_extraction_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except clause_extraction_service.NoChunksFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except StructuredOutputConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Structured output provider is not configured: {exc}",
        )
    except clause_extraction_service.ClauseExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Clause extraction failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during clause extraction: {exc}",
        )


@router.get(
    "/{contract_id}/clauses",
    response_model=ContractClauseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List extracted clauses for a contract",
    description="Retrieves all extracted clauses for a contract, with optional filtering by clause_type.",
)
def get_clauses(
    contract_id: uuid.UUID,
    clause_type: Optional[str] = Query(
        default=None,
        description="Filter by legal clause type (e.g. termination, liability, auto_renewal)",
    ),
    db: Session = Depends(get_db),
) -> ContractClauseListResponse:
    """List persisted clauses for a contract."""
    try:
        return clause_extraction_service.list_contract_clauses(
            db=db,
            contract_id=contract_id,
            clause_type=clause_type,
        )
    except clause_extraction_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while listing clauses: {exc}",
        )


@router.post(
    "/{contract_id}/extract-obligations",
    response_model=ContractObligationExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract structured obligations from contract clauses",
    description=(
        "Extracts structured contractual obligations (title, description, responsible party, "
        "obligation type, due date / deadline info, frequency, recurring status, verbatim text) "
        "from contract clauses using the StructuredLLMProvider. Preserves strict source traceability "
        "(obligation -> clause -> chunk -> page -> contract). Idempotent unless force_reextract=True."
    ),
)
async def extract_obligations(
    contract_id: uuid.UUID,
    payload: Optional[ContractObligationExtractionRequest] = None,
    db: Session = Depends(get_db),
) -> ContractObligationExtractionResponse:
    """Extract and persist structured obligations for a contract."""
    force = payload.force_reextract if payload else False
    try:
        return await obligation_extraction_service.extract_contract_obligations(
            db=db,
            contract_id=contract_id,
            force_reextract=force,
        )
    except obligation_extraction_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except obligation_extraction_service.NoClausesFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except StructuredOutputConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Structured output provider is not configured: {exc}",
        )
    except obligation_extraction_service.ObligationExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Obligation extraction failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during obligation extraction: {exc}",
        )


@router.get(
    "/{contract_id}/obligations",
    response_model=ContractObligationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List extracted obligations for a contract",
    description="Retrieves all extracted obligations for a contract, with optional filtering by party, obligation_type, and status.",
)
def get_obligations(
    contract_id: uuid.UUID,
    responsible_party: Optional[str] = Query(
        default=None,
        description="Filter by responsible party (e.g. Vendor, Customer)",
    ),
    obligation_type: Optional[str] = Query(
        default=None,
        description="Filter by obligation category/type (e.g. payment, reporting, notice)",
    ),
    obligation_status: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by tracking status (e.g. pending, in_progress, completed)",
    ),
    db: Session = Depends(get_db),
) -> ContractObligationListResponse:
    """List persisted obligations for a contract."""
    try:
        return obligation_extraction_service.list_contract_obligations(
            db=db,
            contract_id=contract_id,
            responsible_party=responsible_party,
            obligation_type=obligation_type,
            status=obligation_status,
        )
    except obligation_extraction_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while listing obligations: {exc}",
        )


@router.post(
    "/{contract_id}/extract-facts",
    response_model=ContractFactExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract structured contract facts from contract clauses",
    description=(
        "Extracts structured contract-level facts (effective date, expiration date, value, payment terms, "
        "currency, parties, governing law, notice period, renewal term, termination notice period, liability cap, etc.) "
        "from contract clauses using the StructuredLLMProvider. Preserves strict source traceability "
        "(fact -> source clause -> chunk -> page -> contract). Idempotent unless force_reextract=True."
    ),
)
async def extract_facts(
    contract_id: uuid.UUID,
    payload: Optional[ContractFactExtractionRequest] = None,
    db: Session = Depends(get_db),
) -> ContractFactExtractionResponse:
    """Extract and persist structured contract-level facts for a contract."""
    force = payload.force_reextract if payload else False
    try:
        return await contract_fact_service.extract_contract_facts(
            db=db,
            contract_id=contract_id,
            force_reextract=force,
        )
    except contract_fact_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except contract_fact_service.NoClausesFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except StructuredOutputConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Structured output provider is not configured: {exc}",
        )
    except contract_fact_service.ContractFactExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contract fact extraction failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during contract fact extraction: {exc}",
        )


@router.get(
    "/{contract_id}/facts",
    response_model=ContractFactListResponse,
    status_code=status.HTTP_200_OK,
    summary="List extracted contract facts for a contract",
    description="Retrieves all extracted facts for a contract, with optional filtering by fact_key.",
)
def get_facts(
    contract_id: uuid.UUID,
    fact_key: Optional[str] = Query(
        default=None,
        description="Filter by fact key (e.g. effective_date, governing_law, notice_period)",
    ),
    db: Session = Depends(get_db),
) -> ContractFactListResponse:
    """List persisted contract facts for a contract."""
    try:
        return contract_fact_service.list_contract_facts(
            db=db,
            contract_id=contract_id,
            fact_key=fact_key,
        )
    except contract_fact_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while listing contract facts: {exc}",
        )


# ====================================================================
# Phase 7B: Evidence Endpoints
# ====================================================================

@router.post(
    "/{contract_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create persistent evidence record for a contract",
    description=(
        "Persists a source-oriented evidence record anchoring an extracted domain entity "
        "(clause, obligation, fact) to contract text, page number, and chunk."
    ),
)
def create_evidence_record(
    contract_id: uuid.UUID,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    """Create a persistent evidence record."""
    try:
        return evidence_service.create_evidence(
            db=db,
            contract_id=contract_id,
            payload=payload,
        )
    except evidence_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except evidence_service.EvidenceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while creating evidence: {exc}",
        )


@router.get(
    "/{contract_id}/evidence",
    response_model=EvidenceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List evidence records for a contract",
    description="Lists evidence records for a contract with optional filtering by source_item_type, source_item_id, and page_number.",
)
def list_contract_evidence(
    contract_id: uuid.UUID,
    source_item_type: Optional[str] = Query(
        default=None,
        description="Filter by source item type ('clause' | 'obligation' | 'contract_fact')",
    ),
    source_item_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Filter by UUID of specific source item",
    ),
    page_number: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by source page number (1-indexed)",
    ),
    db: Session = Depends(get_db),
) -> EvidenceListResponse:
    """List evidence records for a contract."""
    try:
        return evidence_service.list_contract_evidence(
            db=db,
            contract_id=contract_id,
            source_item_type=source_item_type,
            source_item_id=source_item_id,
            page_number=page_number,
        )
    except evidence_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while listing evidence: {exc}",
        )


@router.get(
    "/{contract_id}/evidence/lineage",
    response_model=EvidenceLineageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List evidence with complete 6-tier lineage traces",
    description="Returns all evidence records with resolved 6-tier provenance: evidence → source item → clause → chunk → page → contract.",
)
def list_contract_evidence_lineage(
    contract_id: uuid.UUID,
    source_item_type: Optional[str] = Query(
        default=None,
        description="Filter by source item type ('clause' | 'obligation' | 'contract_fact')",
    ),
    source_item_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Filter by UUID of specific source item",
    ),
    page_number: Optional[int] = Query(
        default=None,
        ge=1,
        description="Filter by source page number (1-indexed)",
    ),
    db: Session = Depends(get_db),
) -> EvidenceLineageListResponse:
    """List complete evidence lineages for a contract."""
    try:
        return evidence_service.list_evidence_lineage(
            db=db,
            contract_id=contract_id,
            source_item_type=source_item_type,
            source_item_id=source_item_id,
            page_number=page_number,
        )
    except evidence_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving evidence lineage: {exc}",
        )


@router.get(
    "/{contract_id}/evidence/{evidence_id}",
    response_model=EvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single evidence record by ID",
    description="Retrieves a specific evidence record belonging to the contract.",
)
def get_evidence(
    contract_id: uuid.UUID,
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    """Get single evidence record."""
    try:
        return evidence_service.get_evidence_by_id(
            db=db,
            contract_id=contract_id,
            evidence_id=evidence_id,
        )
    except evidence_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except evidence_service.EvidenceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with id '{evidence_id}' not found for contract '{contract_id}'",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while getting evidence: {exc}",
        )


@router.get(
    "/{contract_id}/evidence/{evidence_id}/lineage",
    response_model=EvidenceLineage,
    status_code=status.HTTP_200_OK,
    summary="Get complete lineage trace for an evidence record",
    description="Retrieves the full 6-tier provenance: evidence → source item → clause → chunk → page → contract.",
)
def get_evidence_lineage(
    contract_id: uuid.UUID,
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EvidenceLineage:
    """Get lineage trace for an evidence record."""
    try:
        return evidence_service.get_evidence_lineage(
            db=db,
            contract_id=contract_id,
            evidence_id=evidence_id,
        )
    except evidence_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except evidence_service.EvidenceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with id '{evidence_id}' not found for contract '{contract_id}'",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while getting evidence lineage: {exc}",
        )


# ====================================================================
# Phase 7C: Deterministic Evidence Validation Endpoints
# ====================================================================

@router.post(
    "/{contract_id}/evidence/validate",
    response_model=EvidenceValidationSummary,
    status_code=status.HTTP_200_OK,
    summary="Validate contract evidence integrity and lineage",
    description=(
        "Deterministically validates all evidence records for a contract against source chunks, "
        "clauses, page numbers, text excerpts, and ownership relationships. Detects broken, "
        "missing, or stale evidence."
    ),
)
def validate_contract_evidence(
    contract_id: uuid.UUID,
    evidence_id: Optional[uuid.UUID] = Query(
        default=None,
        description="Optionally validate only a specific evidence record",
    ),
    db: Session = Depends(get_db),
) -> EvidenceValidationSummary:
    """Validate contract evidence integrity."""
    try:
        return evidence_service.validate_contract_evidence(
            db=db,
            contract_id=contract_id,
            evidence_id=evidence_id,
        )
    except evidence_service.ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while validating evidence: {exc}",
        )
