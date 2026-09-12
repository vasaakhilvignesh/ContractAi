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
from app.schemas.contract import ContractCreate, ContractUpdate


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

