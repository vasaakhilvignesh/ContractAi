"""
ContractIQ — Storage Service Layer

Handles safe file storage and validation for uploaded contract documents:
  - File extension and MIME validation
  - PDF magic signature verification (%PDF-)
  - Size limitation enforcement
  - Path traversal prevention via UUID-based safe storage keys
  - Atomic cleanup on failure
"""

import os
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

# PDF standard file signature
PDF_MAGIC_BYTES = b"%PDF-"
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",  # Permitted as some clients send this for PDF
}


def sanitize_filename(filename: str | None) -> str:
    """
    Extract the clean basename of an uploaded file without directory traversal characters.
    """
    if not filename:
        return "unnamed.pdf"
    # Take only the final component of any path
    base = Path(filename).name
    # Strip dangerous characters
    cleaned = "".join(c for c in base if c.isalnum() or c in ("-", "_", ".", " ")).strip()
    return cleaned or "document.pdf"


async def validate_pdf_upload(
    file: UploadFile,
    max_size_bytes: int | None = None,
) -> Tuple[bytes, int]:
    """
    Validate the uploaded file:
      1. Check filename presence and .pdf extension.
      2. Check declared content-type.
      3. Read file contents and check size limit.
      4. Verify %PDF- magic byte signature.

    Returns:
        tuple of (file_bytes, file_size_in_bytes)

    Raises:
        HTTPException on any validation failure.
    """
    max_size = max_size_bytes or settings.max_upload_size_bytes

    if not file.filename or not file.filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload.",
        )

    # Check file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_upload_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{ext}'. Only PDF documents (.pdf) are accepted.",
        )

    # Check Content-Type header if present
    if file.content_type and file.content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type '{file.content_type}'. Must be 'application/pdf'.",
        )

    # Read content and enforce size limit
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size} bytes) exceeds maximum permitted limit ({max_size} bytes).",
        )

    # Validate PDF signature (magic bytes: %PDF-)
    if not content.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file signature: file does not start with standard PDF header '%PDF-'.",
        )

    return content, file_size


def save_contract_file(
    contract_id: uuid.UUID,
    content: bytes,
    storage_base_dir: Path | None = None,
) -> Tuple[Path, str]:
    """
    Safely store contract PDF bytes onto the filesystem.

    Uses a generated UUID filename to prevent any client-controlled path traversal:
      Relative storage key: contracts/{contract_id}_{token}.pdf

    Returns:
        tuple of (absolute_file_path, relative_storage_key)
    """
    base_dir = (storage_base_dir or settings.storage_dir).resolve()
    target_dir = (base_dir / "contracts").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    # Generate a collision-free safe filename
    safe_filename = f"{contract_id}_{uuid.uuid4().hex}.pdf"
    file_path = (target_dir / safe_filename).resolve()

    # Path traversal assertion: target must reside within base_dir
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage path security violation: attempted path traversal.",
        )

    # Write file to disk
    with open(file_path, "wb") as f:
        f.write(content)

    relative_storage_key = f"contracts/{safe_filename}"
    return file_path, relative_storage_key


def remove_stored_file(
    storage_key_or_path: str | Path | None,
    storage_base_dir: Path | None = None,
) -> bool:
    """
    Safely delete a stored file if it exists.
    Used for rollback cleanup on failure or replacing files on re-upload.
    """
    if not storage_key_or_path:
        return False

    base_dir = (storage_base_dir or settings.storage_dir).resolve()

    if isinstance(storage_key_or_path, Path):
        target_path = storage_key_or_path.resolve()
    else:
        target_path = (base_dir / storage_key_or_path).resolve()

    # Security check: ensure path is within storage directory before unlinking
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        return False

    try:
        if target_path.is_file():
            target_path.unlink()
            return True
    except OSError:
        pass
    return False
