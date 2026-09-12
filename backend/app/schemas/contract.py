"""
ContractIQ — Contract API Schemas

Pydantic schemas for validating requests and structuring responses
for the Contract entity.

Follows strict Pydantic v2 conventions and ensures no database
internals or credentials are exposed in API payloads.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field



class ContractBase(BaseModel):
    """Shared fields for contract creation and representation."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Contract title or document name",
        examples=["Master Services Agreement - Acme Corp"],
    )
    vendor: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Counterparty or vendor name",
        examples=["Acme Corporation"],
    )
    contract_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Contract classification (e.g. MSA, NDA, SaaS, PSA)",
        examples=["MSA"],
    )
    status: str = Field(
        default="active",
        max_length=50,
        description="Contract lifecycle status (active, expired, pending_review, terminated)",
        examples=["active"],
    )
    effective_date: Optional[date] = Field(
        default=None,
        description="Date the contract becomes effective",
        examples=["2026-01-01"],
    )
    expiry_date: Optional[date] = Field(
        default=None,
        description="Date the contract expires or renews",
        examples=["2027-01-01"],
    )
    contract_value: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Total monetary value of the contract",
        examples=[150000.00],
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=10,
        description="Currency code (ISO 4217)",
        examples=["USD"],
    )
    risk_level: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Aggregate risk level (critical, high, medium, low, none)",
        examples=["low"],
    )
    has_auto_renewal: Optional[bool] = Field(
        default=None,
        description="Whether the contract contains an auto-renewal provision",
        examples=[True],
    )


class ContractCreate(ContractBase):
    """Schema for creating a new contract record via API."""

    uploaded_by: Optional[uuid.UUID] = Field(
        default=None,
        description="User UUID who uploaded the contract (optional in Phase 2A)",
    )
    file_name: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Original uploaded file name (optional metadata)",
        examples=["acme_msa_2026.pdf"],
    )
    page_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Total page count of the contract (optional metadata)",
        examples=[18],
    )


class ContractUpdate(BaseModel):
    """Schema for updating an existing contract. All fields are optional."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    vendor: Optional[str] = Field(default=None, max_length=255)
    contract_type: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=50)
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    contract_value: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=10)
    file_name: Optional[str] = Field(default=None, max_length=500)
    page_count: Optional[int] = Field(default=None, ge=1)
    processing_status: Optional[str] = Field(default=None, max_length=50)
    processing_error: Optional[str] = None
    risk_level: Optional[str] = Field(default=None, max_length=20)
    has_auto_renewal: Optional[bool] = None


class ContractResponse(ContractBase):
    """Full contract response schema returned to the client."""

    id: uuid.UUID
    uploaded_by: Optional[uuid.UUID] = None
    file_name: Optional[str] = None
    file_storage_key: Optional[str] = None
    page_count: Optional[int] = None
    processing_status: str
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractListResponse(BaseModel):
    """Paginated list response for contracts."""

    items: list[ContractResponse]
    total: int = Field(..., ge=0, description="Total number of contracts matching filters")
    limit: int = Field(..., ge=1, description="Page limit")
    offset: int = Field(..., ge=0, description="Page offset")


class ContractUploadResponse(BaseModel):
    """Response returned after a contract PDF is successfully uploaded."""

    contract_id: uuid.UUID = Field(..., description="UUID of the contract")
    file_name: str = Field(..., description="Original uploaded file name")
    file_size: int = Field(..., ge=0, description="Size of the uploaded file in bytes")
    content_type: str = Field(..., description="MIME content type of the uploaded file")
    storage_key: str = Field(..., description="Relative storage key for the stored document")
    processing_status: str = Field(..., description="Current document processing status")
    uploaded_at: datetime = Field(..., description="Timestamp when the file was uploaded and recorded")

    model_config = ConfigDict(from_attributes=True)


class ProcessingStatus(str, Enum):
    """Controlled lifecycle states for contract document processing."""

    PENDING = "pending"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ContractProcessingStatusUpdate(BaseModel):
    """Payload for updating contract processing status."""

    status: ProcessingStatus = Field(
        ...,
        description="Target processing status: queued | processing | completed | failed",
        examples=["queued"],
    )
    error_message: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional error detail if transitioning to 'failed'",
        examples=["Extraction timeout on page 14"],
    )


class ContractProcessingStatusResponse(BaseModel):
    """Response representing contract processing status and progress."""

    contract_id: uuid.UUID = Field(..., description="UUID of the contract")
    processing_status: str = Field(..., description="Current processing lifecycle status")
    processing_error: Optional[str] = Field(
        default=None, description="Error detail if processing failed"
    )
    file_name: Optional[str] = Field(
        default=None, description="Original uploaded filename if file exists"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when processing status was last updated"
    )

    model_config = ConfigDict(from_attributes=True)


