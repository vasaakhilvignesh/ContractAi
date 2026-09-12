"""
ContractIQ — Tests for Hybrid Retrieval & Reciprocal Rank Fusion (Phase 5C)

Verifies:
  1. Reciprocal Rank Fusion (RRF) formula: score = sum(1 / (k + rank)) with k=60.
  2. Semantic-only match: returns valid hybrid score from semantic rank, keyword fields None.
  3. Keyword-only match: returns valid hybrid score from keyword rank, semantic fields None.
  4. Chunk appearing in both results: fused into single item with combined RRF score.
  5. Correct RRF ranking: items ordered strictly by hybrid_score descending.
  6. Deduplication: chunks in both retrieval paths appear exactly once.
  7. Top K: top_k parameter correctly bounds the returned list.
  8. Contract scoping: only chunks from the target contract are returned; other contracts excluded.
  9. Empty semantic results: returns keyword matches cleanly without failure.
  10. Empty keyword results: returns semantic matches cleanly without failure.
  11. Both empty: returns total_matches=0, matches=[] without failure.
  12. Missing contract: nonexistent contract UUID returns 404 Not Found.
  13. No embedding leakage: embeddings are never present in responses.
  14. Phase 5A semantic retrieval and Phase 5B keyword retrieval remain unaffected and functional.
  15. API endpoints: both /contracts/{id}/hybrid-query and /api/v1/contracts/{id}/hybrid-query work.
"""

import math
import uuid
from typing import Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import create_app
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.query import (
    ChunkMatch,
    ContractHybridQueryRequest,
    ContractHybridQueryResponse,
    ContractKeywordQueryResponse,
    ContractQueryResponse,
    HybridChunkMatch,
    KeywordChunkMatch,
)
from app.services.embedding_provider import (
    EmbeddingProvider,
    EmbeddingTaskType,
)
from app.services.hybrid_retrieval_service import (
    DEFAULT_RRF_K,
    ContractNotFoundError,
    HybridRetrievalError,
    compute_rrf_score,
    query_contract_hybrid,
    reciprocal_rank_fusion,
)


def _make_unit_vector(dim: int = 768, active_index: int = 0) -> list[float]:
    """Returns a unit vector along the specified axis."""
    vec = [0.0] * dim
    vec[active_index] = 1.0
    return vec


class MockHybridEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock embedding provider for hybrid retrieval tests."""

    def __init__(self, query_vector: Optional[list[float]] = None):
        self._query_vector = query_vector or _make_unit_vector(768, active_index=0)

    @property
    def model_name(self) -> str:
        return "mock-embedding-hybrid"

    @property
    def dimension(self) -> int:
        return 768

    async def embed_texts(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> list[list[float]]:
        return [_make_unit_vector(768, active_index=0) for _ in texts]

    async def embed_query(
        self,
        query: str,
    ) -> list[float]:
        return list(self._query_vector)


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests with automatic cleanup."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def hybrid_test_data(db_session: Session):
    """
    Sets up a primary contract with 4 chunks:
      - chunk_0: vector along axis 0, text has "indemnification liabilities"
      - chunk_1: vector along axis 1, text has "confidentiality obligations"
      - chunk_2: vector along axis 2, text has "governing law jurisdiction"
      - chunk_3: vector along axis 3, text has "termination notice period"
    and a secondary contract with matching keywords/vectors to test contract scoping.
    """
    primary_contract = Contract(
        id=uuid.uuid4(),
        title="Master Services Agreement - Hybrid Test",
        vendor="Apex Technologies",
        contract_type="MSA",
        status="active",
        processing_status="completed",
        page_count=2,
    )
    secondary_contract = Contract(
        id=uuid.uuid4(),
        title="Secondary Unrelated Contract",
        vendor="Other Corp",
        contract_type="NDA",
        status="active",
        processing_status="completed",
        page_count=1,
    )
    db_session.add(primary_contract)
    db_session.add(secondary_contract)
    db_session.commit()

    # Primary chunks
    c0 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=primary_contract.id,
        chunk_index=0,
        page_number=1,
        section_header="Section 1. Indemnification",
        text="The vendor indemnifies customer against liabilities damages and claims.",
        char_start=0,
        char_end=72,
        embedding=_make_unit_vector(768, 0),
    )
    c1 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=primary_contract.id,
        chunk_index=1,
        page_number=1,
        section_header="Section 2. Confidentiality",
        text="Each party must protect confidentiality obligations and proprietary secrets.",
        char_start=73,
        char_end=150,
        embedding=_make_unit_vector(768, 1),
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=primary_contract.id,
        chunk_index=2,
        page_number=2,
        section_header="Section 3. Governing Law",
        text="Governing law and jurisdiction shall be the courts of New York State.",
        char_start=0,
        char_end=70,
        embedding=_make_unit_vector(768, 2),
    )
    c3 = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=primary_contract.id,
        chunk_index=3,
        page_number=2,
        section_header="Section 4. Termination",
        text="Either party may request termination with thirty days written notice period.",
        char_start=71,
        char_end=147,
        embedding=_make_unit_vector(768, 3),
    )

    # Secondary contract chunk (matching terms and vector to verify isolation)
    c_sec = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=secondary_contract.id,
        chunk_index=0,
        page_number=1,
        section_header="Unrelated Section",
        text="The vendor indemnifies against liabilities in competitor contract.",
        char_start=0,
        char_end=68,
        embedding=_make_unit_vector(768, 0),
    )

    db_session.add_all([c0, c1, c2, c3, c_sec])
    db_session.commit()

    yield {
        "primary_contract": primary_contract,
        "secondary_contract": secondary_contract,
        "chunks": [c0, c1, c2, c3],
        "secondary_chunk": c_sec,
    }

    # Teardown
    db_session.query(DocumentChunk).filter(
        DocumentChunk.contract_id.in_([primary_contract.id, secondary_contract.id])
    ).delete(synchronize_session=False)
    db_session.query(Contract).filter(
        Contract.id.in_([primary_contract.id, secondary_contract.id])
    ).delete(synchronize_session=False)
    db_session.commit()


# ====================================================================
# Unit Tests: Reciprocal Rank Fusion Algorithm
# ====================================================================

class TestReciprocalRankFusionAlgorithm:
    """Pure algorithmic unit tests for RRF computation and deduplication."""

    def test_compute_rrf_score_formula(self):
        """Verifies mathematical correctness of 1 / (k + rank) with k=60."""
        # Rank 1 with k=60 -> 1/61 = ~0.016393
        score_r1 = compute_rrf_score([1], k=60)
        assert score_r1 == round(1.0 / 61, 6)

        # Rank 2 with k=60 -> 1/62 = ~0.016129
        score_r2 = compute_rrf_score([2], k=60)
        assert score_r2 == round(1.0 / 62, 6)

        # In both results at rank 1 and rank 2 -> 1/61 + 1/62
        score_both = compute_rrf_score([1, 2], k=60)
        assert score_both == round(1.0 / 61 + 1.0 / 62, 6)

    def test_semantic_only_match(self):
        """Chunk matched only by semantic retrieval has semantic rank and None for keyword."""
        cid = uuid.uuid4()
        chunk_id = uuid.uuid4()
        sem = [
            ChunkMatch(
                id=chunk_id,
                contract_id=cid,
                page_number=1,
                chunk_index=0,
                text="Some semantic text",
                similarity_score=0.88,
                cosine_distance=0.12,
            )
        ]
        fused = reciprocal_rank_fusion(semantic_matches=sem, keyword_matches=[], top_k=5, rrf_k=60)
        assert len(fused) == 1
        assert fused[0].id == chunk_id
        assert fused[0].semantic_rank == 1
        assert fused[0].semantic_similarity == 0.88
        assert fused[0].keyword_rank is None
        assert fused[0].keyword_score is None
        assert fused[0].hybrid_score == round(1.0 / 61, 6)
        assert fused[0].rrf_score == fused[0].hybrid_score

    def test_keyword_only_match(self):
        """Chunk matched only by keyword retrieval has keyword rank and None for semantic."""
        cid = uuid.uuid4()
        chunk_id = uuid.uuid4()
        kw = [
            KeywordChunkMatch(
                id=chunk_id,
                contract_id=cid,
                page_number=1,
                chunk_index=1,
                text="Some keyword text",
                keyword_rank=0.25,
            )
        ]
        fused = reciprocal_rank_fusion(semantic_matches=[], keyword_matches=kw, top_k=5, rrf_k=60)
        assert len(fused) == 1
        assert fused[0].id == chunk_id
        assert fused[0].semantic_rank is None
        assert fused[0].semantic_similarity is None
        assert fused[0].keyword_rank == 1
        assert fused[0].keyword_score == 0.25
        assert fused[0].hybrid_score == round(1.0 / 61, 6)

    def test_chunk_appearing_in_both_results_and_deduplication(self):
        """A chunk appearing in both result sets is deduplicated and combines both scores."""
        cid = uuid.uuid4()
        chunk_both_id = uuid.uuid4()
        chunk_sem_id = uuid.uuid4()

        sem = [
            ChunkMatch(
                id=chunk_both_id,
                contract_id=cid,
                page_number=1,
                chunk_index=0,
                text="Both text",
                similarity_score=0.90,
                cosine_distance=0.10,
            ),
            ChunkMatch(
                id=chunk_sem_id,
                contract_id=cid,
                page_number=1,
                chunk_index=1,
                text="Sem only",
                similarity_score=0.75,
                cosine_distance=0.25,
            ),
        ]
        kw = [
            KeywordChunkMatch(
                id=chunk_both_id,
                contract_id=cid,
                page_number=1,
                chunk_index=0,
                text="Both text",
                keyword_rank=0.50,
            ),
        ]

        fused = reciprocal_rank_fusion(semantic_matches=sem, keyword_matches=kw, top_k=5, rrf_k=60)

        # Deduplication: 2 total items, not 3
        assert len(fused) == 2
        # chunk_both_id ranks first due to combined score: 1/61 + 1/61
        assert fused[0].id == chunk_both_id
        assert fused[0].semantic_rank == 1
        assert fused[0].keyword_rank == 1
        assert fused[0].semantic_similarity == 0.90
        assert fused[0].keyword_score == 0.50
        assert fused[0].hybrid_score == round(1.0 / 61 + 1.0 / 61, 6)

        # chunk_sem_id ranks second: 1/62
        assert fused[1].id == chunk_sem_id
        assert fused[1].semantic_rank == 2
        assert fused[1].keyword_rank is None
        assert fused[1].hybrid_score == round(1.0 / 62, 6)

    def test_correct_rrf_ranking(self):
        """Verifies that RRF order strictly favors chunks ranked high in both methods."""
        cid = uuid.uuid4()
        c_a = uuid.uuid4()  # Rank 1 sem (1/61)
        c_b = uuid.uuid4()  # Rank 2 sem (1/62) + Rank 1 kw (1/61) -> 1/62 + 1/61
        c_c = uuid.uuid4()  # Rank 2 kw (1/62)

        sem = [
            ChunkMatch(id=c_a, contract_id=cid, page_number=1, chunk_index=0, text="A", similarity_score=0.9, cosine_distance=0.1),
            ChunkMatch(id=c_b, contract_id=cid, page_number=1, chunk_index=1, text="B", similarity_score=0.8, cosine_distance=0.2),
        ]
        kw = [
            KeywordChunkMatch(id=c_b, contract_id=cid, page_number=1, chunk_index=1, text="B", keyword_rank=0.4),
            KeywordChunkMatch(id=c_c, contract_id=cid, page_number=1, chunk_index=2, text="C", keyword_rank=0.3),
        ]

        fused = reciprocal_rank_fusion(semantic_matches=sem, keyword_matches=kw, top_k=5, rrf_k=60)
        # B should rank #1 because 1/62 + 1/61 > 1/61
        assert [m.id for m in fused] == [c_b, c_a, c_c]
        assert fused[0].hybrid_score > fused[1].hybrid_score > fused[2].hybrid_score

    def test_top_k_limits_results(self):
        """Verifies top_k bounds the returned matches list."""
        cid = uuid.uuid4()
        sem = [
            ChunkMatch(id=uuid.uuid4(), contract_id=cid, page_number=1, chunk_index=i, text=f"text {i}", similarity_score=0.8 - i * 0.1, cosine_distance=0.2 + i * 0.1)
            for i in range(5)
        ]
        fused = reciprocal_rank_fusion(semantic_matches=sem, keyword_matches=[], top_k=2, rrf_k=60)
        assert len(fused) == 2


# ====================================================================
# Integration Tests: Hybrid Retrieval Service
# ====================================================================

class TestHybridRetrievalService:
    """Integration tests running against Neon PostgreSQL and Mock Embedding Provider."""

    @pytest.mark.asyncio
    async def test_hybrid_query_chunk_appearing_in_both_results(self, db_session: Session, hybrid_test_data: dict):
        """A chunk matching both vector and keyword search is returned with both scores and fused RRF rank."""
        contract = hybrid_test_data["primary_contract"]
        # Chunk 0 has vector along axis 0, and text containing "indemnifies customer against liabilities"
        provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        resp = await query_contract_hybrid(
            db=db_session,
            contract_id=contract.id,
            query="indemnifies liabilities",
            top_k=5,
            provider=provider,
        )

        assert resp.contract_id == contract.id
        assert resp.total_matches >= 1
        top_match = resp.matches[0]
        # Chunk 0 should be top match
        assert top_match.chunk_index == 0
        assert top_match.semantic_rank is not None
        assert top_match.keyword_rank is not None
        assert top_match.semantic_similarity is not None
        assert top_match.keyword_score is not None
        assert top_match.hybrid_score > 0.03  # in both, so 1/61 + 1/61 ~ 0.03278

    @pytest.mark.asyncio
    async def test_hybrid_query_semantic_only_match(self, db_session: Session, hybrid_test_data: dict):
        """Query matching semantically but without keyword match returns semantic rank and None for keyword."""
        contract = hybrid_test_data["primary_contract"]
        # Provider vector matches chunk 2 (governing law, axis 2), but query has nonsense words with no keyword matches
        provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=2))

        resp = await query_contract_hybrid(
            db=db_session,
            contract_id=contract.id,
            query="xyznonexistentkeyword",
            top_k=5,
            provider=provider,
        )

        assert resp.total_matches >= 1
        # Top match should be chunk 2 with semantic match and None keyword
        top_match = resp.matches[0]
        assert top_match.chunk_index == 2
        assert top_match.semantic_rank == 1
        assert top_match.keyword_rank is None
        assert top_match.keyword_score is None

    @pytest.mark.asyncio
    async def test_hybrid_query_keyword_only_match(self, db_session: Session, hybrid_test_data: dict):
        """Query matching keywords but whose vector is orthogonal/dissimilar returns keyword rank."""
        contract = hybrid_test_data["primary_contract"]
        # Provider vector along axis 10 (orthogonal to all contract chunks 0-3)
        provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=10))

        resp = await query_contract_hybrid(
            db=db_session,
            contract_id=contract.id,
            query="confidentiality proprietary secrets",
            top_k=5,
            provider=provider,
        )

        assert resp.total_matches >= 1
        # Chunk 1 contains "confidentiality proprietary secrets"
        chunk1_match = next((m for m in resp.matches if m.chunk_index == 1), None)
        assert chunk1_match is not None
        assert chunk1_match.keyword_rank == 1
        assert chunk1_match.keyword_score is not None

    @pytest.mark.asyncio
    async def test_hybrid_query_contract_scoping(self, db_session: Session, hybrid_test_data: dict):
        """Chunks from other contracts are strictly never returned even with identical keywords & vectors."""
        primary = hybrid_test_data["primary_contract"]
        secondary = hybrid_test_data["secondary_contract"]
        provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        resp = await query_contract_hybrid(
            db=db_session,
            contract_id=primary.id,
            query="indemnifies liabilities",
            top_k=10,
            provider=provider,
        )

        returned_contract_ids = {m.contract_id for m in resp.matches}
        assert secondary.id not in returned_contract_ids
        for m in resp.matches:
            assert m.contract_id == primary.id

    @pytest.mark.asyncio
    async def test_hybrid_query_top_k_limits(self, db_session: Session, hybrid_test_data: dict):
        """Verifies top_k limits the number of matches returned."""
        contract = hybrid_test_data["primary_contract"]
        provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        resp = await query_contract_hybrid(
            db=db_session,
            contract_id=contract.id,
            query="party contract",
            top_k=2,
            provider=provider,
        )

        assert len(resp.matches) <= 2
        assert resp.top_k == 2

    @pytest.mark.asyncio
    async def test_hybrid_query_empty_results_when_neither_matches(self, db_session: Session, hybrid_test_data: dict):
        """When query matches neither vector (orthogonal) nor keyword (punctuation), returns clean empty list."""
        contract = hybrid_test_data["primary_contract"]
        # Empty mock results
        with patch("app.services.hybrid_retrieval_service.query_contract_chunks") as mock_vec, \
             patch("app.services.hybrid_retrieval_service.query_contract_keywords") as mock_kw:
            mock_vec.return_value = ContractQueryResponse(
                contract_id=contract.id,
                query="???",
                total_matches=0,
                top_k=5,
                matches=[],
            )
            mock_kw.return_value = ContractKeywordQueryResponse(
                contract_id=contract.id,
                query="???",
                total_matches=0,
                top_k=5,
                matches=[],
            )

            resp = await query_contract_hybrid(
                db=db_session,
                contract_id=contract.id,
                query="???",
                top_k=5,
            )

            assert resp.total_matches == 0
            assert resp.matches == []

    @pytest.mark.asyncio
    async def test_hybrid_query_missing_contract_raises_not_found(self, db_session: Session):
        """Querying a nonexistent contract UUID raises ContractNotFoundError."""
        random_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError) as exc_info:
            await query_contract_hybrid(
                db=db_session,
                contract_id=random_id,
                query="indemnification",
            )
        assert str(random_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_hybrid_query_no_embedding_leakage(self, db_session: Session, hybrid_test_data: dict):
        """Responses never expose raw embedding vector floats in any schema field."""
        contract = hybrid_test_data["primary_contract"]
        provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        resp = await query_contract_hybrid(
            db=db_session,
            contract_id=contract.id,
            query="indemnification",
            top_k=5,
            provider=provider,
        )

        assert not hasattr(resp, "embedding")
        for match in resp.matches:
            assert not hasattr(match, "embedding")
            match_dict = match.model_dump()
            assert "embedding" not in match_dict
            assert "vector" not in match_dict


# ====================================================================
# API Endpoint Integration Tests
# ====================================================================

class TestHybridRetrievalAPIEndpoints:
    """End-to-end FastAPI endpoint tests using TestClient."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_post_hybrid_query_success(self, hybrid_test_data: dict):
        """POST /contracts/{id}/hybrid-query returns 200 OK with expected hybrid response payload."""
        contract = hybrid_test_data["primary_contract"]
        mock_provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        with patch("app.services.retrieval_service.get_embedding_provider", return_value=mock_provider):
            response = self.client.post(
                f"/contracts/{contract.id}/hybrid-query",
                json={"query": "indemnification liabilities", "top_k": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["contract_id"] == str(contract.id)
        assert data["query"] == "indemnification liabilities"
        assert data["top_k"] == 3
        assert data["rrf_k"] == 60
        assert "matches" in data
        assert len(data["matches"]) <= 3

        if len(data["matches"]) > 0:
            m = data["matches"][0]
            assert "hybrid_score" in m
            assert "rrf_score" in m
            assert "semantic_rank" in m
            assert "keyword_rank" in m
            assert "text" in m
            assert "page_number" in m
            assert "chunk_index" in m
            assert "embedding" not in m

    def test_post_hybrid_query_versioned_alias(self, hybrid_test_data: dict):
        """POST /api/v1/contracts/{id}/hybrid-query works identically to root endpoint."""
        contract = hybrid_test_data["primary_contract"]
        mock_provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        with patch("app.services.retrieval_service.get_embedding_provider", return_value=mock_provider):
            response = self.client.post(
                f"/api/v1/contracts/{contract.id}/hybrid-query",
                json={"query": "termination notice period", "top_k": 2},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["contract_id"] == str(contract.id)
        assert data["top_k"] == 2

    def test_post_hybrid_query_default_top_k_is_5(self, hybrid_test_data: dict):
        """Omitting top_k applies the default value of 5."""
        contract = hybrid_test_data["primary_contract"]
        mock_provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        with patch("app.services.retrieval_service.get_embedding_provider", return_value=mock_provider):
            response = self.client.post(
                f"/contracts/{contract.id}/hybrid-query",
                json={"query": "governing law jurisdiction"},
            )

        assert response.status_code == 200
        assert response.json()["top_k"] == 5

    def test_post_hybrid_query_rejects_empty_query(self, hybrid_test_data: dict):
        """Empty query string returns 422 Unprocessable Entity."""
        contract = hybrid_test_data["primary_contract"]
        response = self.client.post(
            f"/contracts/{contract.id}/hybrid-query",
            json={"query": ""},
        )
        assert response.status_code == 422

    def test_post_hybrid_query_rejects_whitespace_query(self, hybrid_test_data: dict):
        """Whitespace-only query string returns 422 Unprocessable Entity."""
        contract = hybrid_test_data["primary_contract"]
        response = self.client.post(
            f"/contracts/{contract.id}/hybrid-query",
            json={"query": "   \n\t   "},
        )
        assert response.status_code == 422

    def test_post_hybrid_query_rejects_top_k_out_of_bounds(self, hybrid_test_data: dict):
        """top_k < 1 or > 20 is rejected with 422 Unprocessable Entity."""
        contract = hybrid_test_data["primary_contract"]

        # Below lower bound
        r_low = self.client.post(
            f"/contracts/{contract.id}/hybrid-query",
            json={"query": "valid query", "top_k": 0},
        )
        assert r_low.status_code == 422

        # Above upper bound
        r_high = self.client.post(
            f"/contracts/{contract.id}/hybrid-query",
            json={"query": "valid query", "top_k": 25},
        )
        assert r_high.status_code == 422

    def test_post_hybrid_query_nonexistent_contract_returns_404(self):
        """Querying a nonexistent contract returns 404 Not Found."""
        random_id = uuid.uuid4()
        response = self.client.post(
            f"/contracts/{random_id}/hybrid-query",
            json={"query": "indemnification"},
        )
        assert response.status_code == 404
        assert f"Contract with id '{random_id}' not found" in response.json()["detail"]

    def test_phase_5a_and_5b_endpoints_remain_unaffected(self, hybrid_test_data: dict):
        """Verifies Phase 5A vector retrieval and Phase 5B keyword retrieval endpoints remain functional."""
        contract = hybrid_test_data["primary_contract"]
        mock_provider = MockHybridEmbeddingProvider(query_vector=_make_unit_vector(768, active_index=0))

        # Test Phase 5A
        with patch("app.services.retrieval_service.get_embedding_provider", return_value=mock_provider):
            r_5a = self.client.post(
                f"/contracts/{contract.id}/query",
                json={"query": "indemnification", "top_k": 2},
            )
        assert r_5a.status_code == 200
        assert "matches" in r_5a.json()

        # Test Phase 5B
        r_5b = self.client.post(
            f"/contracts/{contract.id}/keyword-query",
            json={"query": "indemnification liabilities", "top_k": 2},
        )
        assert r_5b.status_code == 200
        assert "matches" in r_5b.json()
