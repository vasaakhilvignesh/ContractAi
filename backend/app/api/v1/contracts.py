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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.contract import (
    ContractCreate,
    ContractListResponse,
    ContractResponse,
    ContractUpdate,
)
from app.services import contract_service

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
