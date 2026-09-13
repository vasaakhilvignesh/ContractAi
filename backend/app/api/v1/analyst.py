"""
ContractIQ — AI Analyst REST API Router (Phase 10A–10E)

Provides endpoints for:
  - 10B: POST /analyst/query/single (or /contracts/{contract_id}/analyst) — single-contract question answering.
  - 10C: POST /analyst/query/cross — cross-contract multi-document comparative questions.
  - 10D: Evidence-backed responses with 6-tier lineage and deterministic citation verification.
  - 10E: Retrieval & debug metadata without exposing embeddings or credentials.
"""

import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analyst import (
    AnalystQueryResponse,
    CrossContractAnalystRequest,
    SingleContractAnalystRequest,
)
from app.services import (
    analyst_service,
    rag_service,
)
from app.services.analyst_service import (
    AnalystServiceError,
    ContractScopingError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyst", tags=["Analyst"])


@router.post(
    "/query",
    response_model=AnalystQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask AI Analyst a single-contract or cross-contract question",
    description=(
        "Universal Analyst API query endpoint. If contract_ids contains 1 contract, evaluates "
        "as a single-contract query; if multiple (2-10), evaluates as a scoped cross-contract comparison. "
        "Returns grounded answer claims with deterministically verified citations and optional debug metadata."
    ),
)
async def query_analyst_universal(
    payload: CrossContractAnalystRequest,
    db: Session = Depends(get_db),
) -> AnalystQueryResponse:
    """Universal Analyst query route accepting single or multiple contract IDs."""
    try:
        if len(payload.contract_ids) == 1:
            single_req = SingleContractAnalystRequest(
                query=payload.query,
                top_k=payload.top_k_per_contract,
                min_score_threshold=payload.min_score_threshold,
                include_debug=payload.include_debug,
            )
            return await analyst_service.ask_contract_analyst_single(
                db=db,
                contract_id=payload.contract_ids[0],
                request=single_req,
            )
        else:
            return await analyst_service.ask_contract_analyst_cross(
                db=db,
                request=payload,
            )
    except ContractScopingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except rag_service.ContractNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except AnalystServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error in query_analyst_universal: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during analyst query: {exc}",
        )


@router.post(
    "/contracts/{contract_id}/query",
    response_model=AnalystQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask AI Analyst a question about a specific contract",
    description=(
        "Executes a grounded single-contract inquiry. Retrieves hybrid matches, constructs context, "
        "generates structured answer with claims and citations, verifies citations against the database, "
        "and returns complete evidence lineage."
    ),
)
async def query_analyst_single(
    contract_id: uuid.UUID,
    payload: SingleContractAnalystRequest,
    db: Session = Depends(get_db),
) -> AnalystQueryResponse:
    """Single contract analyst inquiry."""
    try:
        return await analyst_service.ask_contract_analyst_single(
            db=db,
            contract_id=contract_id,
            request=payload,
        )
    except rag_service.ContractNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with id '{contract_id}' not found",
        )
    except AnalystServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error in query_analyst_single for %s: %s", contract_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during single contract analyst query: {exc}",
        )


@router.post(
    "/query/cross",
    response_model=AnalystQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask AI Analyst a comparative question across multiple contracts",
    description=(
        "Executes a scoped multi-contract inquiry across 2 to 10 contracts. Strictly separates "
        "retrieval and context boundaries between contracts, prevents cross-contract evidence bleeding, "
        "and validates citations against the respective contract records."
    ),
)
async def query_analyst_cross(
    payload: CrossContractAnalystRequest,
    db: Session = Depends(get_db),
) -> AnalystQueryResponse:
    """Cross-contract multi-document comparative inquiry."""
    try:
        return await analyst_service.ask_contract_analyst_cross(
            db=db,
            request=payload,
        )
    except ContractScopingError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except AnalystServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error in query_analyst_cross: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during cross-contract analyst query: {exc}",
        )
