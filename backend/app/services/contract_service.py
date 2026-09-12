"""
ContractIQ — Contract Service Layer

Encapsulates all database interactions for the Contract entity.
Keeps SQL and database transaction logic separate from FastAPI route handlers.
"""

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractUpdate, ProcessingStatus



def get_contract(db: Session, contract_id: uuid.UUID) -> Optional[Contract]:
    """Retrieve a single contract by its UUID primary key."""
    stmt = select(Contract).where(Contract.id == contract_id)
    return db.scalars(stmt).first()


def list_contracts(
    db: Session,
    *,
    offset: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    contract_type: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> tuple[list[Contract], int]:
    """
    List contracts with stable pagination and basic attribute filtering.

    Returns:
        tuple of (contracts_list, total_count)
    """
    query = select(Contract)

    if status:
        query = query.where(Contract.status == status)
    if vendor:
        query = query.where(Contract.vendor.ilike(f"%{vendor}%"))
    if contract_type:
        query = query.where(Contract.contract_type == contract_type)
    if risk_level:
        query = query.where(Contract.risk_level == risk_level)

    # Compute total matching count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    # Apply stable ordering and pagination
    paginated_query = (
        query.order_by(Contract.created_at.desc(), Contract.id.asc())
        .offset(offset)
        .limit(limit)
    )
    items = list(db.scalars(paginated_query).all())

    return items, total


def create_contract(db: Session, contract_in: ContractCreate) -> Contract:
    """Create and persist a new contract record."""
    contract_data = contract_in.model_dump()
    db_contract = Contract(**contract_data)
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)
    return db_contract


def update_contract(
    db: Session,
    db_contract: Contract,
    contract_in: ContractUpdate,
) -> Contract:
    """Update fields on an existing contract record."""
    update_data = contract_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_contract, field, value)
    db.commit()
    db.refresh(db_contract)
    return db_contract


def delete_contract(db: Session, db_contract: Contract) -> None:
    """Delete a contract record and cascade delete associated children."""
    db.delete(db_contract)
    db.commit()


def associate_contract_file(
    db: Session,
    db_contract: Contract,
    *,
    file_name: str,
    storage_key: str,
    processing_status: str = "uploaded",
) -> Contract:
    """
    Associate an uploaded document with an existing contract record.
    Updates file_name, file_storage_key, and sets processing_status.
    """
    db_contract.file_name = file_name
    db_contract.file_storage_key = storage_key
    db_contract.processing_status = processing_status
    db_contract.processing_error = None
    db.commit()
    db.refresh(db_contract)
    return db_contract


VALID_PROCESSING_TRANSITIONS: dict[str, set[str]] = {
    ProcessingStatus.PENDING.value: set(),  # Document must be uploaded first
    ProcessingStatus.UPLOADED.value: {ProcessingStatus.QUEUED.value},
    ProcessingStatus.QUEUED.value: {ProcessingStatus.PROCESSING.value},
    ProcessingStatus.PROCESSING.value: {
        ProcessingStatus.COMPLETED.value,
        ProcessingStatus.FAILED.value,
    },
    ProcessingStatus.COMPLETED.value: set(),  # Terminal state (re-upload resets to uploaded)
    ProcessingStatus.FAILED.value: {ProcessingStatus.QUEUED.value},  # Retry
}


def update_contract_processing_status(
    db: Session,
    db_contract: Contract,
    new_status: ProcessingStatus | str,
    error_message: str | None = None,
) -> Contract:
    """
    Transition contract processing state according to the valid lifecycle.

    Lifecycle:
      uploaded -> queued -> processing -> completed
                                       -> failed -> queued (retry)

    Raises:
        ValueError if the transition is disallowed or invalid.
    """
    current_status = db_contract.processing_status
    target_status = (
        new_status.value if isinstance(new_status, ProcessingStatus) else str(new_status)
    )

    if current_status == ProcessingStatus.PENDING.value:
        raise ValueError(
            "Cannot transition processing status: no document has been uploaded for this contract."
        )

    allowed = VALID_PROCESSING_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        allowed_list = sorted(list(allowed))
        if not allowed_list:
            allowed_msg = "none (terminal state — re-upload a new file to reset)"
        else:
            allowed_msg = ", ".join(f"'{s}'" for s in allowed_list)
        raise ValueError(
            f"Invalid processing status transition from '{current_status}' to '{target_status}'. "
            f"Allowed transitions from '{current_status}': [{allowed_msg}]."
        )

    # If transitioning to failed, record error message
    if target_status == ProcessingStatus.FAILED.value:
        db_contract.processing_error = (
            error_message or "Processing failed without specific error description."
        )
    else:
        # Clear previous error on retry / progression
        db_contract.processing_error = None

    db_contract.processing_status = target_status
    db.commit()
    db.refresh(db_contract)
    return db_contract


