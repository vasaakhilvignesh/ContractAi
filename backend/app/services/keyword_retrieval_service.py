"""
ContractIQ — Keyword Retrieval Service (Phase 5B)

Orchestrates contract-scoped keyword retrieval over DocumentChunk.text using
PostgreSQL native Full-Text Search (tsvector, tsquery, ts_rank_cd).

Guarantees:
  - Contract-scoped: only chunks belonging to the target contract are searched.
  - PostgreSQL native FTS: uses websearch_to_tsquery for safe query parsing and ts_rank_cd
    (cover density) for relevance ranking.
  - Independent: operates independently from Phase 5A semantic vector retrieval.
  - Never exposes embeddings: returned KeywordChunkMatch items strictly omit embedding vectors.
  - Safe bounds: respects top_k limits (1-20, default 5).
  - Clean empty responses: queries with zero matches return an empty list rather than errors.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.query import (
    ContractKeywordQueryResponse,
    KeywordChunkMatch,
)

logger = logging.getLogger(__name__)


class KeywordRetrievalError(Exception):
    """Base exception for keyword retrieval errors."""
    pass


class ContractNotFoundError(KeywordRetrievalError):
    """Raised when the requested contract does not exist."""
    pass


async def query_contract_keywords(
    db: Session,
    contract_id: uuid.UUID,
    query: str,
    top_k: int = 5,
) -> ContractKeywordQueryResponse:
    """
    Executes contract-scoped keyword full-text retrieval against document chunks.

    Args:
        db: Active SQLAlchemy database session.
        contract_id: UUID of the target contract.
        query: Validated natural language query string.
        top_k: Maximum number of ranked chunks to return (default 5, range 1-20).

    Returns:
        ContractKeywordQueryResponse containing ranked KeywordChunkMatch items.

    Raises:
        ContractNotFoundError: If the specified contract does not exist.
        KeywordRetrievalError: If database query execution fails.
    """
    # 1. Validate that the target contract exists
    contract = db.scalars(
        select(Contract).where(Contract.id == contract_id)
    ).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # 2. Build PostgreSQL Full-Text Search tsquery using websearch_to_tsquery
    # websearch_to_tsquery safely handles natural phrases, AND/OR logic, and punctuation
    # without throwing syntax errors on arbitrary input.
    ts_query = func.websearch_to_tsquery("english", query)

    # 3. Calculate relevance using Cover Density ranking (ts_rank_cd)
    rank_expr = func.ts_rank_cd(DocumentChunk.search_vector, ts_query).label("keyword_rank")

    # 4. Build contract-scoped search query
    stmt = (
        select(DocumentChunk, rank_expr)
        .where(
            DocumentChunk.contract_id == contract_id,
            DocumentChunk.search_vector.op("@@")(ts_query),
        )
        .order_by(rank_expr.desc(), DocumentChunk.chunk_index.asc())
        .limit(top_k)
    )

    try:
        results = db.execute(stmt).all()
    except Exception as exc:
        logger.error(
            "Keyword retrieval query failed for contract %s: %s",
            contract_id,
            type(exc).__name__,
        )
        raise KeywordRetrievalError(
            f"Database keyword full-text query failed: {exc}"
        ) from exc

    # 5. Transform results into KeywordChunkMatch models
    matches: list[KeywordChunkMatch] = []
    for chunk, raw_rank in results:
        matches.append(
            KeywordChunkMatch(
                id=chunk.id,
                contract_id=chunk.contract_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                section_header=chunk.section_header,
                text=chunk.text,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                keyword_rank=round(float(raw_rank), 6),
            )
        )

    return ContractKeywordQueryResponse(
        contract_id=contract.id,
        query=query,
        total_matches=len(matches),
        top_k=top_k,
        matches=matches,
    )
