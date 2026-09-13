"""
ContractIQ — Cross-Contract Comparison REST API Router (Phase 11A–11E)

Provides endpoints for:
  - 11A: POST /contracts/compare (and /api/v1/contracts/compare) — multi-contract structured comparison.
  - 11B: Field comparison matrix over ContractFact, Obligation, and Contract metadata.
  - 11C: Evidence-backed comparison with 6-tier lineage.
  - 11D: Deterministic difference analysis and variance reporting.
  - 11E: Scoping validation (2-10 contracts, non-empty, deduplicated).
"""

import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.comparison import (
    ContractComparisonRequest,
    ContractComparisonResponse,
)
from app.services import comparison_service
from app.services.comparison_service import (
    ComparisonScopingError,
    ComparisonServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts/compare", tags=["Contract Comparison"])


@router.post(
    "",
    response_model=ContractComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare 2 to 10 contracts side-by-side",
    description=(
        "Executes structured, evidence-backed cross-contract comparison. Compares extracted "
        "ContractFacts (effective date, value, payment terms, notice periods, liability caps, "
        "governing law, etc.), obligations, and metadata. Produces deterministic variance analysis "
        "with full 6-tier evidence lineage back to source chunk and page."
    ),
)
def compare_contracts(
    payload: ContractComparisonRequest,
    db: Session = Depends(get_db),
) -> ContractComparisonResponse:
    """Compare multiple contracts with deterministic variance analysis."""
    try:
        return comparison_service.compare_contracts_structured(
            db=db,
            request=payload,
        )
    except ComparisonScopingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ComparisonServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error in compare_contracts: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during contract comparison: {exc}",
        )


@router.get(
    "",
    response_model=ContractComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare contracts via query parameters",
    description="Convenience GET endpoint allowing contract IDs to be passed as repeated query parameters.",
)
def compare_contracts_get(
    contract_id: Optional[list[str]] = Query(
        default=None,
        description="List of 2 to 10 contract UUIDs to compare.",
    ),
    include_obligations: bool = Query(
        default=True,
        description="Whether to include obligations in the comparison.",
    ),
    db: Session = Depends(get_db),
) -> ContractComparisonResponse:
    """GET convenience handler for contract comparison."""
    if not contract_id or len(contract_id) < 2 or len(contract_id) > 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Must provide between 2 and 10 contract IDs.",
        )

    parsed_ids: list[uuid.UUID] = []
    for cid_str in contract_id:
        try:
            parsed_ids.append(uuid.UUID(cid_str.strip()))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid UUID '{cid_str}'.",
            )

    # Check uniqueness
    if len(parsed_ids) != len(set(parsed_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate contract IDs are not allowed in comparison request.",
        )

    req = ContractComparisonRequest(
        contract_ids=parsed_ids,
        include_obligations=include_obligations,
    )
    return compare_contracts(payload=req, db=db)
