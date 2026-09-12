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
from app.schemas.extraction import ContractExtractionResponse
from app.services import contract_service, storage_service, pdf_extraction_service



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



