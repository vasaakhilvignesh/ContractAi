"""
ContractIQ — Hybrid Retrieval Service with Reciprocal Rank Fusion (Phase 5C)

Combines semantic vector retrieval (pgvector cosine similarity search) and
keyword retrieval (PostgreSQL native Full-Text Search with ts_rank_cd) using
Reciprocal Rank Fusion (RRF).

RRF Formula:
    RRF_score(d) = sum_{m in M} 1 / (k + r_m(d))

Where:
    - k = 60 (standard RRF smoothing constant)
    - r_m(d) is the 1-indexed rank of chunk d in retrieval method m (1 = best)
    - If chunk d does not appear in method m, its rank contribution from m is 0

Guarantees:
    - Multi-modal retrieval: combines dense vector similarity and sparse keyword search.
    - Preserves existing paths: delegates to retrieval_service and keyword_retrieval_service.
    - Deduplication: chunks appearing in both retrieval lists appear once in the output.
    - Transparent scoring: exposes hybrid_score/rrf_score alongside individual ranks and scores.
    - Contract-scoped: strictly restricted to chunks of the target contract.
    - Zero embedding exposure: returned schemas never leak embedding vector floats.
    - Resilient: if one retrieval path returns zero matches or has un-embedded chunks,
      results from the other path are still returned cleanly without failure.
"""

import logging
import time
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import log_operation_result
from app.models.contract import Contract
from app.schemas.query import (
    ChunkMatch,
    ContractHybridQueryResponse,
    HybridChunkMatch,
    KeywordChunkMatch,
)
from app.services.embedding_provider import EmbeddingProvider
from app.services.keyword_retrieval_service import (
    ContractNotFoundError as KeywordContractNotFoundError,
    query_contract_keywords,
)
from app.services.retrieval_service import (
    ContractNotFoundError as VectorContractNotFoundError,
    NoChunksFoundError,
    NoEmbeddedChunksError,
    query_contract_chunks,
)

logger = logging.getLogger(__name__)

# Standard RRF smoothing constant (Cormack, Clarke, and Buettcher 2009)
DEFAULT_RRF_K: int = 60


class HybridRetrievalError(Exception):
    """Base exception for hybrid retrieval errors."""
    pass


class ContractNotFoundError(HybridRetrievalError):
    """Raised when the requested contract does not exist."""
    pass


def compute_rrf_score(ranks: list[Optional[int]], k: int = DEFAULT_RRF_K) -> float:
    """
    Calculates the Reciprocal Rank Fusion score from a list of 1-indexed ranks.

    Formula:
        score = sum(1.0 / (k + rank)) for each valid 1-indexed rank

    Args:
        ranks: List of 1-indexed ranks (None or <= 0 ignored).
        k: RRF smoothing constant (default 60).

    Returns:
        float: Computed RRF score rounded to 6 decimal places.
    """
    score = 0.0
    for r in ranks:
        if r is not None and r > 0:
            score += 1.0 / (k + r)
    return round(score, 6)


def reciprocal_rank_fusion(
    semantic_matches: list[ChunkMatch],
    keyword_matches: list[KeywordChunkMatch],
    top_k: int = 5,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[HybridChunkMatch]:
    """
    Fuses ranked semantic matches and keyword matches using Reciprocal Rank Fusion.

    Deduplicates chunks that appear in both result sets, merges their metadata,
    computes the unified RRF score, sorts by score descending (with chunk_index
    as deterministic tie-breaker), and returns the top_k HybridChunkMatch items.

    Args:
        semantic_matches: Ranked ChunkMatch list from semantic vector retrieval.
        keyword_matches: Ranked KeywordChunkMatch list from keyword retrieval.
        top_k: Maximum number of fused matches to return.
        rrf_k: RRF smoothing constant (default 60).

    Returns:
        list[HybridChunkMatch]: Fused, ranked, and bounded matches.
    """
    candidates: dict[uuid.UUID, dict] = {}

    # 1. Ingest semantic candidates (1-indexed rank)
    for rank_idx, sm in enumerate(semantic_matches, start=1):
        candidates[sm.id] = {
            "id": sm.id,
            "contract_id": sm.contract_id,
            "page_number": sm.page_number,
            "chunk_index": sm.chunk_index,
            "section_header": sm.section_header,
            "text": sm.text,
            "char_start": sm.char_start,
            "char_end": sm.char_end,
            "semantic_rank": rank_idx,
            "semantic_similarity": sm.similarity_score,
            "keyword_rank": None,
            "keyword_score": None,
        }

    # 2. Ingest keyword candidates (1-indexed rank), deduplicating existing chunks
    for rank_idx, km in enumerate(keyword_matches, start=1):
        if km.id in candidates:
            candidates[km.id]["keyword_rank"] = rank_idx
            candidates[km.id]["keyword_score"] = km.keyword_rank
        else:
            candidates[km.id] = {
                "id": km.id,
                "contract_id": km.contract_id,
                "page_number": km.page_number,
                "chunk_index": km.chunk_index,
                "section_header": km.section_header,
                "text": km.text,
                "char_start": km.char_start,
                "char_end": km.char_end,
                "semantic_rank": None,
                "semantic_similarity": None,
                "keyword_rank": rank_idx,
                "keyword_score": km.keyword_rank,
            }

    # 3. Compute unified RRF score for all candidates
    for cand in candidates.values():
        score = compute_rrf_score(
            ranks=[cand["semantic_rank"], cand["keyword_rank"]],
            k=rrf_k,
        )
        cand["hybrid_score"] = score
        cand["rrf_score"] = score

    # 4. Sort candidates: primary by hybrid_score descending, secondary by chunk_index ascending
    sorted_candidates = sorted(
        candidates.values(),
        key=lambda c: (-c["hybrid_score"], c["chunk_index"]),
    )

    # 5. Apply top_k limit and construct HybridChunkMatch instances
    return [HybridChunkMatch(**c) for c in sorted_candidates[:top_k]]


async def query_contract_hybrid(
    db: Session,
    contract_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    rrf_k: int = DEFAULT_RRF_K,
    provider: Optional[EmbeddingProvider] = None,
) -> ContractHybridQueryResponse:
    """
    Executes hybrid retrieval (semantic vector + PostgreSQL keyword FTS) for a contract,
    fusing results via Reciprocal Rank Fusion (RRF).

    Args:
        db: Active SQLAlchemy database session.
        contract_id: UUID of the target contract.
        query: Validated natural language search query.
        top_k: Maximum number of fused chunks to return (default 5, range 1-20).
        rrf_k: RRF smoothing constant (default 60).
        provider: Optional custom EmbeddingProvider instance.

    Returns:
        ContractHybridQueryResponse: Complete fused response with metadata and provenance.

    Raises:
        ContractNotFoundError: If the requested contract does not exist.
        HybridRetrievalError: If database or retrieval operations fail unexpectedly.
    """
    # 1. Validate contract existence
    contract = db.scalars(
        select(Contract).where(Contract.id == contract_id)
    ).first()
    if not contract:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")

    # 2. Execute semantic vector retrieval (Phase 5A) — with timing
    semantic_matches: list[ChunkMatch] = []
    _sem_start = time.perf_counter()
    _sem_status = "ok"
    try:
        semantic_resp = await query_contract_chunks(
            db=db,
            contract_id=contract_id,
            query=query,
            top_k=top_k,
            provider=provider,
        )
        semantic_matches = semantic_resp.matches
    except VectorContractNotFoundError:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")
    except (NoChunksFoundError, NoEmbeddedChunksError):
        # Gracefully handle contracts without chunks or embeddings
        semantic_matches = []
        _sem_status = "skipped"
    except Exception as exc:
        logger.warning(
            "Semantic retrieval error for contract %s: %s. Falling back to keyword-only.",
            contract_id,
            exc,
        )
        semantic_matches = []
        _sem_status = "error"
    finally:
        _sem_ms = round((time.perf_counter() - _sem_start) * 1000, 2)
        log_operation_result(
            operation="semantic_retrieval",
            duration_ms=_sem_ms,
            status=_sem_status,
            metadata={
                "contract_id": str(contract_id),
                "top_k": top_k,
                "matches_returned": len(semantic_matches),
            },
        )

    # 3. Execute keyword full-text retrieval (Phase 5B) — with timing
    keyword_matches: list[KeywordChunkMatch] = []
    _kw_start = time.perf_counter()
    _kw_status = "ok"
    try:
        keyword_resp = await query_contract_keywords(
            db=db,
            contract_id=contract_id,
            query=query,
            top_k=top_k,
        )
        keyword_matches = keyword_resp.matches
    except KeywordContractNotFoundError:
        raise ContractNotFoundError(f"Contract with id '{contract_id}' not found.")
    except Exception as exc:
        logger.warning(
            "Keyword retrieval error for contract %s: %s. Falling back to semantic-only.",
            contract_id,
            exc,
        )
        keyword_matches = []
        _kw_status = "error"
    finally:
        _kw_ms = round((time.perf_counter() - _kw_start) * 1000, 2)
        log_operation_result(
            operation="keyword_retrieval",
            duration_ms=_kw_ms,
            status=_kw_status,
            metadata={
                "contract_id": str(contract_id),
                "top_k": top_k,
                "matches_returned": len(keyword_matches),
            },
        )

    # 4. Fuse candidate sets using Reciprocal Rank Fusion — with timing
    _rrf_start = time.perf_counter()
    fused_matches = reciprocal_rank_fusion(
        semantic_matches=semantic_matches,
        keyword_matches=keyword_matches,
        top_k=top_k,
        rrf_k=rrf_k,
    )
    _rrf_ms = round((time.perf_counter() - _rrf_start) * 1000, 2)
    log_operation_result(
        operation="hybrid_rrf_fusion",
        duration_ms=_rrf_ms,
        status="ok",
        metadata={
            "contract_id": str(contract_id),
            "semantic_matches": len(semantic_matches),
            "keyword_matches": len(keyword_matches),
            "matches_returned": len(fused_matches),
            "rrf_k": rrf_k,
            "top_k": top_k,
        },
    )

    # 5. Return unified response
    return ContractHybridQueryResponse(
        contract_id=contract.id,
        query=query,
        total_matches=len(fused_matches),
        top_k=top_k,
        rrf_k=rrf_k,
        semantic_matches_count=len(semantic_matches),
        keyword_matches_count=len(keyword_matches),
        matches=fused_matches,
    )
