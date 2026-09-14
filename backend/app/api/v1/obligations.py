"""
ContractIQ — Obligation REST API Router (Phase 12A–12E)

Provides endpoints for:
  - 12A: Obligation API query foundation.
  - 12B: Contract-scoped obligation retrieval with multi-facet filtering.
  - 12C: 6-tier evidence lineage verification (obligation → clause → chunk → page → contract).
  - 12D: Deterministic obligation analysis (summary metrics, party breakdowns, recurrence counts,
         overdue/upcoming counts, cadence classification, confidence tiers).
  - 12E: Scoped REST endpoints:
         - GET  /contracts/{contract_id}/obligations/query
         - POST /contracts/{contract_id}/obligations/query
         - GET  /contracts/{contract_id}/obligations/{obligation_id}
"""

from datetime import date
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_optional, verify_contract_access_by_id
from app.core.security import mask_secrets
from app.db.session import get_db
from app.models.user import User
from app.schemas.obligation_api import (
    ObligationDetailResponse,
    ObligationQueryRequest,
    ObligationQueryResponse,
)
from app.services import obligation_service
from app.services.obligation_service import (
    ContractNotFoundError,
    ObligationNotFoundError,
    ObligationScopingError,
    ObligationServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts/{contract_id}/obligations", tags=["Obligations"])


@router.get(
    "/query",
    response_model=ObligationQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query and filter contract obligations with evidence lineage and analysis",
    description=(
        "Retrieves contract-scoped obligations matching specified query filters. Returns 6-tier "
        "evidence citations (obligation → clause → chunk → page → contract) and deterministic analysis "
        "breakdowns (party, type, status, priority, recurrence, overdue/upcoming metrics)."
    ),
)
def query_obligations_get(
    contract_id: uuid.UUID,
    responsible_party: Optional[str] = Query(
        default=None,
        description="Filter by responsible party substring (e.g. Vendor, Customer).",
    ),
    obligation_type: Optional[str] = Query(
        default=None,
        description="Filter by obligation category/type (e.g. payment, reporting, notice).",
    ),
    obligation_status: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by tracking status: pending | in_progress | completed | overdue | waived.",
    ),
    priority: Optional[str] = Query(
        default=None,
        description="Filter by priority level: high | medium | low.",
    ),
    is_recurring: Optional[bool] = Query(
        default=None,
        description="Filter by recurring (True) or non-recurring (False) obligations.",
    ),
    has_due_date: Optional[bool] = Query(
        default=None,
        description="Filter by whether an explicit due date is defined.",
    ),
    due_date_from: Optional[date] = Query(
        default=None,
        description="Inclusive start date for due_date filtering.",
    ),
    due_date_to: Optional[date] = Query(
        default=None,
        description="Inclusive end date for due_date filtering.",
    ),
    include_lineage: bool = Query(
        default=True,
        description="Whether to resolve and verify full 6-tier evidence lineage.",
    ),
    reference_date: Optional[date] = Query(
        default=None,
        description="Reference calendar date for overdue/upcoming calculations (defaults to today).",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> ObligationQueryResponse:
    """GET endpoint for querying contract obligations."""
    verify_contract_access_by_id(contract_id, current_user, db)

    req = ObligationQueryRequest(
        responsible_party=responsible_party,
        obligation_type=obligation_type,
        status=obligation_status,
        priority=priority,
        is_recurring=is_recurring,
        has_due_date=has_due_date,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        include_lineage=include_lineage,
        reference_date=reference_date,
    )
    try:
        return obligation_service.query_contract_obligations(
            db=db,
            contract_id=contract_id,
            filters=req,
        )
    except ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=mask_secrets(f"Contract with id '{contract_id}' not found"),
        )
    except ObligationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=mask_secrets(str(exc)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error querying obligations for contract %s: %s", contract_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while querying obligations: {mask_secrets(str(exc))}",
        )


@router.post(
    "/query",
    response_model=ObligationQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query and filter contract obligations via POST body",
    description=(
        "POST endpoint for querying contract obligations with complex JSON filter criteria. "
        "Returns full evidence lineage and deterministic analysis metrics."
    ),
)
def query_obligations_post(
    contract_id: uuid.UUID,
    payload: ObligationQueryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> ObligationQueryResponse:
    """POST endpoint for querying contract obligations with structured request body."""
    verify_contract_access_by_id(contract_id, current_user, db)

    try:
        return obligation_service.query_contract_obligations(
            db=db,
            contract_id=contract_id,
            filters=payload,
        )
    except ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=mask_secrets(f"Contract with id '{contract_id}' not found"),
        )
    except ObligationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=mask_secrets(str(exc)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error querying obligations for contract %s: %s", contract_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while querying obligations: {mask_secrets(str(exc))}",
        )


@router.get(
    "/{obligation_id}",
    response_model=ObligationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single obligation detail by ID with evidence lineage and analysis",
    description=(
        "Retrieves a single obligation by UUID. Enforces strict contract scoping: returns 404 if "
        "obligation belongs to another contract. Resolves full 6-tier evidence lineage."
    ),
)
def get_obligation_detail(
    contract_id: uuid.UUID,
    obligation_id: uuid.UUID,
    include_lineage: bool = Query(
        default=True,
        description="Whether to resolve and verify full 6-tier evidence lineage.",
    ),
    reference_date: Optional[date] = Query(
        default=None,
        description="Reference calendar date for overdue calculation.",
    ),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> ObligationDetailResponse:
    """GET endpoint for single obligation detail."""
    verify_contract_access_by_id(contract_id, current_user, db)

    try:
        return obligation_service.get_single_obligation_detail(
            db=db,
            contract_id=contract_id,
            obligation_id=obligation_id,
            include_lineage=include_lineage,
            reference_date=reference_date,
        )
    except ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=mask_secrets(f"Contract with id '{contract_id}' not found"),
        )
    except (ObligationNotFoundError, ObligationScopingError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=mask_secrets(str(exc)),
        )
    except ObligationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=mask_secrets(str(exc)),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error getting obligation %s for contract %s: %s",
            obligation_id,
            contract_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while getting obligation: {mask_secrets(str(exc))}",
        )
