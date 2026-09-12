"""
ContractIQ — Services Package
"""

from app.services.contract_service import (
    create_contract,
    get_contract,
    list_contracts,
    update_contract,
    delete_contract,
    associate_contract_file,
    update_contract_processing_status,
    VALID_PROCESSING_TRANSITIONS,
)

from app.services.storage_service import (
    validate_pdf_upload,
    save_contract_file,
    remove_stored_file,
    sanitize_filename,
)

from app.services.pdf_extraction_service import (
    PDFExtractionError,
    PDFNotFoundError,
    PDFPathTraversalError,
    PDFEncryptedError,
    PDFCorruptedError,
    PDFPageLimitExceededError,
    resolve_pdf_path,
    extract_text_from_pdf,
    extract_contract_document,
)

__all__ = [
    "create_contract",
    "get_contract",
    "list_contracts",
    "update_contract",
    "delete_contract",
    "associate_contract_file",
    "update_contract_processing_status",
    "VALID_PROCESSING_TRANSITIONS",
    "validate_pdf_upload",
    "save_contract_file",
    "remove_stored_file",
    "sanitize_filename",
    "PDFExtractionError",
    "PDFNotFoundError",
    "PDFPathTraversalError",
    "PDFEncryptedError",
    "PDFCorruptedError",
    "PDFPageLimitExceededError",
    "resolve_pdf_path",
    "extract_text_from_pdf",
    "extract_contract_document",
]



