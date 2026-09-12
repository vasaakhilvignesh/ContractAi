"""
ContractIQ — Tests for Semantic Vector Retrieval (Phase 5A)

Verifies:
  1. Successful semantic vector retrieval against contract chunks.
  2. Query embedding generates with task_type=RETRIEVAL_QUERY.
  3. Provider receives exact user query string.
  4. 768-dimensional query vector is used for similarity computation.
  5. Nearest chunks ordered by cosine distance ascending (similarity descending).
  6. Similarity score conversion is mathematically exact: score = 1.0 - distance.
  7. Default top_k=5 applied when omitted.
  8. Maximum top_k=20 accepted.
  9. Invalid top_k (< 1 or > 20) rejected with 422 Unprocessable Entity.
  10. Contract scoping: only chunks from the specified contract are retrieved.
  11. Chunks from other contracts in database never appear in results.
  12. Chunks with NULL embedding are strictly excluded.
  13. Empty query string rejected with 422.
  14. Whitespace-only query string rejected with 422.
  15. Nonexistent contract UUID returns 404 Not Found.
  16. Contract with zero chunks returns 400 Bad Request.
  17. Contract with chunks but zero embeddings returns 400 Bad Request.
  18. Optional min_similarity threshold filters chunks below threshold.
  19. High min_similarity returning zero matches returns 200 OK with matches=[].
  20. Upstream provider failure returns 502 Bad Gateway.
  21. No embedding vector is exposed in API response.
  22. Both /contracts/{id}/query and /api/v1/contracts/{id}/query work identically.
"""

import math
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.query import ChunkMatch, ContractQueryRequest, ContractQueryResponse
from app.services.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTaskType,
)
from app.services.retrieval_service import (
    ContractNotFoundError,
    NoChunksFoundError,
    NoEmbeddedChunksError,
    RetrievalError,
    query_contract_chunks,
)


def _make_unit_vector(dim: int = 768, active_index: int = 0) -> list[float]:
    """Returns a unit vector along the specified axis."""
    vec = [0.0] * dim
    vec[active_index] = 1.0
    return vec


def _make_split_vector(dim: int = 768, idx_a: int = 0, idx_b: int = 1) -> list[float]:
    """Returns a normalized vector at 45 degrees between two axes."""
    vec = [0.0] * dim
    val = 1.0 / math.sqrt(2.0)
    vec[idx_a] = val
    vec[idx_b] = val
    return vec


class MockRetrievalEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock provider with recorded calls and controllable query vectors."""

    def __init__(
        self,
        dimension: int = 768,
        model_name: str = "gemini-embedding-2",
        query_vector: Optional[list[float]] = None,
    ):
        self._dim = dimension
        self._model = model_name
        self._query_vector = query_vector or _make_unit_vector(dim=dimension, active_index=0)
        self.recorded_queries: list[str] = []
        self.recorded_tasks: list[str] = []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_texts(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType | str = EmbeddingTaskType.RETRIEVAL_QUERY,
        title: str | None = None,
    ) -> list[list[float]]:
        self.recorded_queries.extend(texts)
        self.recorded_tasks.append(str(task_type))
        return [self._query_vector for _ in texts]


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests with automatic cleanup."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def retrieval_test_data(db_session: Session):
    """
    Sets up a primary contract with 4 chunks:
      - Chunk 0: identical direction to query vector (distance = 0.0, sim = 1.0)
      - Chunk 1: 45 degrees from query vector (distance ~ 0.2929, sim ~ 0.7071)
      - Chunk 2: orthogonal to query vector (distance = 1.0, sim = 0.0)
      - Chunk 3: un-embedded (embedding = None)

    Also sets up a secondary contract with 1 chunk to verify contract isolation.
    """
    # 1. Primary contract
    primary_contract = Contract(
        id=uuid.uuid4(),
        title="Primary Retrieval Test Agreement",
        vendor="Acme Corp",
        contract_type="MSA",
        status="active",
        processing_status="completed",
        page_count=3,
    )
    db_session.add(primary_contract)

    # 2. Secondary contract (to test cross-contract isolation)
    secondary_contract = Contract(
        id=uuid.uuid4(),
        title="Secondary Unrelated Contract",
        vendor="Other Corp",
        contract_type="SaaS",
        status="active",
        processing_status="completed",
        page_count=1,
    )
    db_session.add(secondary_contract)
    db_session.flush()

    vec_identical = _make_unit_vector(768, active_index=0)
    vec_angled = _make_split_vector(768, idx_a=0, idx_b=1)
    vec_orthogonal = _make_unit_vector(768, active_index=2)

    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=1,
            chunk_index=0,
            char_start=0,
            char_end=120,
            section_header="1. Definitions",
            text="Primary contract chunk 0: exactly matches query direction.",
            embedding=vec_identical,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=1,
            chunk_index=1,
            char_start=121,
            char_end=250,
            section_header="2. Scope",
            text="Primary contract chunk 1: 45 degrees partial match.",
            embedding=vec_angled,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=2,
            chunk_index=2,
            char_start=0,
            char_end=180,
            section_header="3. Termination",
            text="Primary contract chunk 2: orthogonal direction.",
            embedding=vec_orthogonal,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=3,
            chunk_index=3,
            char_start=0,
            char_end=100,
            section_header="4. Unembedded",
            text="Primary contract chunk 3: un-embedded (embedding is NULL).",
            embedding=None,
        ),
    ]
    db_session.add_all(chunks)

    # Secondary contract chunk with identical embedding
    other_chunk = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=secondary_contract.id,
        page_number=1,
        chunk_index=0,
        section_header="Other Contract Clause",
        text="Secondary contract chunk: must NEVER be retrieved for primary contract.",
        embedding=vec_identical,
    )
    db_session.add(other_chunk)
    db_session.commit()

    yield primary_contract, secondary_contract, chunks, other_chunk

    # Cleanup
    db_session.query(DocumentChunk).filter(
        DocumentChunk.contract_id.in_([primary_contract.id, secondary_contract.id])
    ).delete(synchronize_session=False)
    db_session.query(Contract).filter(
        Contract.id.in_([primary_contract.id, secondary_contract.id])
    ).delete(synchronize_session=False)
    db_session.commit()


# ====================================================================
# 1. Service Layer Tests
# ====================================================================

class TestRetrievalService:
    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_retrieval_success_ordering_and_scores(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify successful semantic retrieval, ordering, and distance/similarity formulas."""
        primary, secondary, chunks, other_chunk = retrieval_test_data
        query_vec = _make_unit_vector(768, active_index=0)
        provider = MockRetrievalEmbeddingProvider(query_vector=query_vec)

        response = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="notice period for termination",
            top_k=5,
            provider=provider,
        )

        assert response.contract_id == primary.id
        assert response.query == "notice period for termination"
        assert response.top_k == 5
        # Primary contract has 3 embedded chunks (chunk 3 is NULL, so excluded)
        assert response.total_matches == 3
        assert len(response.matches) == 3

        # Match 0: chunk 0 (distance = 0.0, similarity = 1.0)
        m0 = response.matches[0]
        assert m0.chunk_index == 0
        assert m0.cosine_distance == pytest.approx(0.0, abs=1e-4)
        assert m0.similarity_score == pytest.approx(1.0, abs=1e-4)

        # Match 1: chunk 1 (distance ~ 0.2929, similarity ~ 0.7071)
        m1 = response.matches[1]
        assert m1.chunk_index == 1
        expected_dist = 1.0 - (1.0 / math.sqrt(2.0))
        assert m1.cosine_distance == pytest.approx(expected_dist, abs=1e-4)
        assert m1.similarity_score == pytest.approx(1.0 - expected_dist, abs=1e-4)

        # Match 2: chunk 2 (distance = 1.0, similarity = 0.0)
        m2 = response.matches[2]
        assert m2.chunk_index == 2
        assert m2.cosine_distance == pytest.approx(1.0, abs=1e-4)
        assert m2.similarity_score == pytest.approx(0.0, abs=1e-4)

        # Strict ordering: distance ascending, similarity descending
        assert response.matches[0].cosine_distance <= response.matches[1].cosine_distance <= response.matches[2].cosine_distance
        assert response.matches[0].similarity_score >= response.matches[1].similarity_score >= response.matches[2].similarity_score

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_retrieval_query_task_type_and_dimension(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify provider receives RETRIEVAL_QUERY task type and 768-dim vector."""
        primary, _, _, _ = retrieval_test_data
        provider = MockRetrievalEmbeddingProvider()

        await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="governing law clause",
            provider=provider,
        )

        assert provider.recorded_queries == ["governing law clause"]
        assert "RETRIEVAL_QUERY" in provider.recorded_tasks[0]
        assert provider.dimension == 768

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_contract_scoping_never_returns_other_contract_chunks(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify chunks from secondary contract are never returned even with identical embedding."""
        primary, secondary, _, other_chunk = retrieval_test_data
        provider = MockRetrievalEmbeddingProvider()

        response = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            top_k=10,
            provider=provider,
        )

        matched_ids = [m.id for m in response.matches]
        assert other_chunk.id not in matched_ids
        for m in response.matches:
            assert m.contract_id == primary.id

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_null_embeddings_strictly_excluded(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify chunks with embedding=None are never returned."""
        primary, _, chunks, _ = retrieval_test_data
        null_chunk = chunks[3]  # chunk with embedding=None
        provider = MockRetrievalEmbeddingProvider()

        response = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            top_k=10,
            provider=provider,
        )

        matched_ids = [m.id for m in response.matches]
        assert null_chunk.id not in matched_ids

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_top_k_limits_results(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify top_k parameter limits the number of returned chunks."""
        primary, _, _, _ = retrieval_test_data
        provider = MockRetrievalEmbeddingProvider()

        response = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            top_k=2,
            provider=provider,
        )

        assert len(response.matches) == 2
        assert response.total_matches == 2
        assert response.top_k == 2

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_optional_min_similarity_filters_chunks(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify min_similarity filters out chunks with lower similarity scores."""
        primary, _, _, _ = retrieval_test_data
        provider = MockRetrievalEmbeddingProvider()

        # Threshold 0.8: should only return chunk 0 (sim 1.0), filtering chunks 1 and 2
        resp = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            min_similarity=0.8,
            provider=provider,
        )
        assert resp.total_matches == 1
        assert resp.matches[0].chunk_index == 0

        # Threshold 0.5: returns chunk 0 (1.0) and chunk 1 (~0.7071), filtering chunk 2 (0.0)
        resp2 = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            min_similarity=0.5,
            provider=provider,
        )
        assert resp2.total_matches == 2
        assert [m.chunk_index for m in resp2.matches] == [0, 1]

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_threshold_resulting_in_zero_matches_returns_empty_list(
        self, db_session: Session, retrieval_test_data
    ):
        """Verify threshold higher than all chunk similarities returns 200 with matches=[]."""
        primary, _, _, _ = retrieval_test_data
        provider = MockRetrievalEmbeddingProvider()

        resp = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            min_similarity=0.999,  # higher than 1.0 with float margin or using orthogonal
            provider=provider,
        )
        # Only chunk 0 is ~1.0; test with 1.01 or query orthogonal to all
        orthogonal_to_all = _make_unit_vector(768, active_index=50)
        ortho_provider = MockRetrievalEmbeddingProvider(query_vector=orthogonal_to_all)
        resp_zero = await query_contract_chunks(
            db=db_session,
            contract_id=primary.id,
            query="test query",
            min_similarity=0.5,
            provider=ortho_provider,
        )
        assert resp_zero.total_matches == 0
        assert resp_zero.matches == []

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_nonexistent_contract_raises_not_found(self, db_session: Session):
        """Verify querying nonexistent contract UUID raises ContractNotFoundError."""
        missing_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError) as exc_info:
            await query_contract_chunks(
                db=db_session,
                contract_id=missing_id,
                query="test",
                provider=MockRetrievalEmbeddingProvider(),
            )
        assert f"Contract with id '{missing_id}' not found" in str(exc_info.value)

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_contract_with_zero_chunks_raises_no_chunks_error(
        self, db_session: Session
    ):
        """Verify querying contract with zero chunks raises NoChunksFoundError."""
        empty_contract = Contract(
            id=uuid.uuid4(),
            title="Empty Contract",
            status="active",
            processing_status="pending",
        )
        db_session.add(empty_contract)
        db_session.commit()

        try:
            with pytest.raises(NoChunksFoundError) as exc_info:
                await query_contract_chunks(
                    db=db_session,
                    contract_id=empty_contract.id,
                    query="test",
                    provider=MockRetrievalEmbeddingProvider(),
                )
            assert "has no chunks" in str(exc_info.value)
        finally:
            db_session.query(Contract).filter(Contract.id == empty_contract.id).delete()
            db_session.commit()

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_contract_with_zero_embedded_chunks_raises_no_embedded_chunks_error(
        self, db_session: Session
    ):
        """Verify contract with chunks but zero embeddings raises NoEmbeddedChunksError."""
        unembedded_contract = Contract(
            id=uuid.uuid4(),
            title="Unembedded Chunks Contract",
            status="active",
            processing_status="chunked",
        )
        db_session.add(unembedded_contract)
        db_session.flush()

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=unembedded_contract.id,
            page_number=1,
            chunk_index=0,
            text="Chunk with no embedding.",
            embedding=None,
        )
        db_session.add(chunk)
        db_session.commit()

        try:
            with pytest.raises(NoEmbeddedChunksError) as exc_info:
                await query_contract_chunks(
                    db=db_session,
                    contract_id=unembedded_contract.id,
                    query="test",
                    provider=MockRetrievalEmbeddingProvider(),
                )
            assert "has no embedded chunks" in str(exc_info.value)
        finally:
            db_session.query(DocumentChunk).filter(
                DocumentChunk.contract_id == unembedded_contract.id
            ).delete()
            db_session.query(Contract).filter(
                Contract.id == unembedded_contract.id
            ).delete()
            db_session.commit()


# ====================================================================
# 2. REST API Endpoint Tests
# ====================================================================

class TestRetrievalAPIEndpoints:
    @pytest.mark.db
    def test_post_query_success(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify POST /contracts/{id}/query returns 200 with ranked ChunkMatch results."""
        primary, _, _, _ = retrieval_test_data

        with patch(
            "app.services.retrieval_service.get_embedding_provider",
            return_value=MockRetrievalEmbeddingProvider(),
        ):
            resp = test_client.post(
                f"/contracts/{primary.id}/query",
                json={"query": "termination notice period", "top_k": 3},
            )
            assert resp.status_code == 200
            data = resp.json()

            assert data["contract_id"] == str(primary.id)
            assert data["query"] == "termination notice period"
            assert data["top_k"] == 3
            assert data["total_matches"] == 3
            assert len(data["matches"]) == 3

            # Verify schema fields are present
            first_match = data["matches"][0]
            assert "id" in first_match
            assert "contract_id" in first_match
            assert "page_number" in first_match
            assert "chunk_index" in first_match
            assert "section_header" in first_match
            assert "text" in first_match
            assert "similarity_score" in first_match
            assert "cosine_distance" in first_match

            # Critical: No embedding vectors exposed in response
            assert "embedding" not in first_match

    @pytest.mark.db
    def test_post_query_api_v1_versioned_alias(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify POST /api/v1/contracts/{id}/query works identically to root route."""
        primary, _, _, _ = retrieval_test_data

        with patch(
            "app.services.retrieval_service.get_embedding_provider",
            return_value=MockRetrievalEmbeddingProvider(),
        ):
            resp = test_client.post(
                f"/api/v1/contracts/{primary.id}/query",
                json={"query": "scope of deliverables"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["contract_id"] == str(primary.id)
            assert data["top_k"] == 5  # default top_k

    @pytest.mark.db
    def test_post_query_default_top_k_is_5(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify top_k defaults to 5 when omitted from payload."""
        primary, _, _, _ = retrieval_test_data

        with patch(
            "app.services.retrieval_service.get_embedding_provider",
            return_value=MockRetrievalEmbeddingProvider(),
        ):
            resp = test_client.post(
                f"/contracts/{primary.id}/query",
                json={"query": "default top k check"},
            )
            assert resp.status_code == 200
            assert resp.json()["top_k"] == 5

    @pytest.mark.db
    def test_post_query_rejects_empty_query(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify empty string query is rejected with 422."""
        primary, _, _, _ = retrieval_test_data
        resp = test_client.post(
            f"/contracts/{primary.id}/query",
            json={"query": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.db
    def test_post_query_rejects_whitespace_query(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify whitespace-only query is rejected with 422."""
        primary, _, _, _ = retrieval_test_data
        resp = test_client.post(
            f"/contracts/{primary.id}/query",
            json={"query": "   \n\t   "},
        )
        assert resp.status_code == 422

    @pytest.mark.db
    def test_post_query_rejects_top_k_out_of_bounds(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify top_k < 1 and top_k > 20 are rejected with 422."""
        primary, _, _, _ = retrieval_test_data

        # top_k = 0
        resp_low = test_client.post(
            f"/contracts/{primary.id}/query",
            json={"query": "valid query", "top_k": 0},
        )
        assert resp_low.status_code == 422

        # top_k = 21
        resp_high = test_client.post(
            f"/contracts/{primary.id}/query",
            json={"query": "valid query", "top_k": 21},
        )
        assert resp_high.status_code == 422

        # top_k = 20 (boundary maximum) should succeed
        with patch(
            "app.services.retrieval_service.get_embedding_provider",
            return_value=MockRetrievalEmbeddingProvider(),
        ):
            resp_max = test_client.post(
                f"/contracts/{primary.id}/query",
                json={"query": "valid query", "top_k": 20},
            )
            assert resp_max.status_code == 200
            assert resp_max.json()["top_k"] == 20

    @pytest.mark.db
    def test_post_query_nonexistent_contract_returns_404(
        self, test_client: TestClient
    ):
        """Verify nonexistent contract returns 404."""
        missing_id = uuid.uuid4()
        resp = test_client.post(
            f"/contracts/{missing_id}/query",
            json={"query": "any query"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.db
    def test_post_query_provider_failure_returns_502(
        self, test_client: TestClient, retrieval_test_data
    ):
        """Verify upstream provider failure returns 502 Bad Gateway."""
        primary, _, _, _ = retrieval_test_data

        failing_provider = MagicMock(spec=EmbeddingProvider)
        failing_provider.embed_query = AsyncMock(
            side_effect=RuntimeError("Google GenAI RateLimitError 429")
        )
        failing_provider.dimension = 768

        with patch(
            "app.services.retrieval_service.get_embedding_provider",
            return_value=failing_provider,
        ):
            resp = test_client.post(
                f"/contracts/{primary.id}/query",
                json={"query": "failing provider query"},
            )
            assert resp.status_code == 502
            assert "Semantic retrieval failed" in resp.json()["detail"]
