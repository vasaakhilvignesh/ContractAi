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

from app.services.text_normalization_service import (
    normalize_text,
    is_noise_text,
)

from app.services.chunking_service import (
    ChunkingError,
    ScannedDocumentChunkingError,
    EmptyDocumentChunkingError,
    is_heading_line,
    chunk_page_text,
    chunk_extraction_result,
    persist_contract_chunks,
    list_contract_chunks,
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
    "normalize_text",
    "is_noise_text",
    "ChunkingError",
    "ScannedDocumentChunkingError",
    "EmptyDocumentChunkingError",
    "is_heading_line",
    "chunk_page_text",
    "chunk_extraction_result",
    "persist_contract_chunks",
    "list_contract_chunks",
]



