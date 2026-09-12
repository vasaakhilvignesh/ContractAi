"""
ContractIQ — Tests for Keyword Full-Text Retrieval (Phase 5B)

Verifies:
  1. Normal keyword retrieval matching specific words in DocumentChunk.text.
  2. Contract scoping: only chunks belonging to the queried contract are returned;
     chunks from other contracts with identical matching keywords are strictly excluded.
  3. Relevance ranking: results are ordered by keyword_rank descending (ts_rank_cd).
  4. Top K limiting: top_k parameter bounds the number of returned chunks.
  5. Default top_k=5 applied when omitted.
  6. Top K validation: top_k < 1 and top_k > 20 rejected with 422 Unprocessable Entity.
  7. Empty / whitespace-only query rejected with 422 Unprocessable Entity.
  8. Punctuation-only query produces a clean response with total_matches=0, matches=[].
  9. Query with zero matching terms returns 200 OK with total_matches=0, matches=[].
  10. Nonexistent contract UUID returns 404 Not Found.
  11. Chunks with NULL embedding CAN be retrieved by keyword search (since keyword search
      only indexes text and does not require vector embeddings).
  12. Embeddings are strictly NEVER exposed in ChunkMatch / KeywordChunkMatch responses.
  13. Preserves all metadata (page_number, chunk_index, section_header, char_start, char_end, text).
  14. Both /contracts/{id}/keyword-query and /api/v1/contracts/{id}/keyword-query work identically.
  15. Phase 5A semantic vector retrieval endpoint remains completely intact and functional.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.query import (
    ContractKeywordQueryRequest,
    ContractKeywordQueryResponse,
    KeywordChunkMatch,
)
from app.services.keyword_retrieval_service import (
    ContractNotFoundError,
    KeywordRetrievalError,
    query_contract_keywords,
)


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests with automatic cleanup."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def keyword_test_data(db_session: Session):
    """
    Sets up a primary contract with 4 chunks featuring distinct contract terminology,
    and a secondary contract with matching keywords to verify strict contract scoping.
    """
    primary_contract = Contract(
        id=uuid.uuid4(),
        title="Master Services Agreement - Keyword Test",
        vendor="Acme Cloud Solutions",
        contract_type="MSA",
        status="active",
        processing_status="completed",
        page_count=3,
    )
    secondary_contract = Contract(
        id=uuid.uuid4(),
        title="Unrelated Vendor Contract",
        vendor="Competitor Corp",
        contract_type="SOW",
        status="active",
        processing_status="completed",
        page_count=1,
    )
    db_session.add(primary_contract)
    db_session.add(secondary_contract)
    db_session.flush()

    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=1,
            chunk_index=0,
            char_start=0,
            char_end=150,
            section_header="1. Definitions and Term",
            text="This Agreement shall commence on the Effective Date and continue for an initial term of three years.",
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=2,
            chunk_index=1,
            char_start=151,
            char_end=350,
            section_header="2. Early Termination and Notice",
            text="Either party may terminate this Agreement for convenience upon giving thirty (30) days prior written notice to the other party.",
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=2,
            chunk_index=2,
            char_start=351,
            char_end=580,
            section_header="3. Immediate Termination for Material Breach",
            text="Either party may terminate immediately upon written notice if the other party commits a material breach of this Agreement and fails to cure such breach within fifteen days.",
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=primary_contract.id,
            page_number=3,
            chunk_index=3,
            char_start=581,
            char_end=800,
            section_header="4. Indemnification and Liability",
            text="The Service Provider shall indemnify, defend, and hold harmless the Customer against any third-party intellectual property infringement claims.",
        ),
    ]
    db_session.add_all(chunks)

    # Secondary contract chunk containing the exact word 'terminate' and 'notice'
    other_chunk = DocumentChunk(
        id=uuid.uuid4(),
        contract_id=secondary_contract.id,
        page_number=1,
        chunk_index=0,
        char_start=0,
        char_end=120,
        section_header="Cross-Contract Isolation",
        text="Competitor Corp notice: terminate all services immediately upon notice.",
    )
    db_session.add(other_chunk)
    db_session.commit()

    yield primary_contract, secondary_contract, chunks, other_chunk

    # Teardown
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

class TestKeywordRetrievalService:
    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_keyword_search_success_and_relevance(
        self, db_session: Session, keyword_test_data
    ):
        """Verify keyword search returns matching chunks ordered by keyword_rank."""
        primary, _, chunks, _ = keyword_test_data

        response = await query_contract_keywords(
            db=db_session,
            contract_id=primary.id,
            query="terminate written notice",
            top_k=5,
        )

        assert response.contract_id == primary.id
        assert response.query == "terminate written notice"
        assert response.total_matches >= 2
        assert len(response.matches) >= 2

        # Both chunk 1 and chunk 2 contain 'terminate' and 'notice'
        matched_chunk_indices = [m.chunk_index for m in response.matches]
        assert 1 in matched_chunk_indices
        assert 2 in matched_chunk_indices

        # Verify ranking order: keyword_rank descending
        for i in range(len(response.matches) - 1):
            assert response.matches[i].keyword_rank >= response.matches[i + 1].keyword_rank

        # Verify first match contains required fields and valid rank
        top_match = response.matches[0]
        assert top_match.keyword_rank > 0.0
        assert top_match.text is not None
        assert top_match.page_number in [1, 2, 3]

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_contract_scoping_never_leaks_other_contracts(
        self, db_session: Session, keyword_test_data
    ):
        """Verify chunks from other contracts are strictly excluded even when matching keywords."""
        primary, secondary, _, other_chunk = keyword_test_data

        # Both primary and secondary contracts have chunks matching 'terminate notice'
        response = await query_contract_keywords(
            db=db_session,
            contract_id=primary.id,
            query="terminate notice",
            top_k=10,
        )

        retrieved_ids = {m.id for m in response.matches}
        assert other_chunk.id not in retrieved_ids
        for m in response.matches:
            assert m.contract_id == primary.id

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_keyword_search_top_k_limits_results(
        self, db_session: Session, keyword_test_data
    ):
        """Verify top_k parameter limits the number of returned results."""
        primary, _, _, _ = keyword_test_data

        response = await query_contract_keywords(
            db=db_session,
            contract_id=primary.id,
            query="terminate notice breach agreement",
            top_k=1,
        )

        assert len(response.matches) == 1
        assert response.total_matches == 1
        assert response.top_k == 1

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_query_with_no_matches_returns_empty_list(
        self, db_session: Session, keyword_test_data
    ):
        """Verify query with no matching keywords returns total_matches=0, matches=[]."""
        primary, _, _, _ = keyword_test_data

        response = await query_contract_keywords(
            db=db_session,
            contract_id=primary.id,
            query="nonexistentkeywordxyzzy aerospace submarine",
            top_k=5,
        )

        assert response.total_matches == 0
        assert response.matches == []

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_punctuation_only_query_returns_empty_cleanly(
        self, db_session: Session, keyword_test_data
    ):
        """Verify query with only punctuation characters returns empty result without SQL errors."""
        primary, _, _, _ = keyword_test_data

        response = await query_contract_keywords(
            db=db_session,
            contract_id=primary.id,
            query="!@#$%^&*()_+~`-={}|[]\\:\";'<>?,./",
            top_k=5,
        )

        assert response.total_matches == 0
        assert response.matches == []

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_nonexistent_contract_raises_not_found(self, db_session: Session):
        """Verify querying a nonexistent contract UUID raises ContractNotFoundError."""
        missing_id = uuid.uuid4()

        with pytest.raises(ContractNotFoundError) as exc_info:
            await query_contract_keywords(
                db=db_session,
                contract_id=missing_id,
                query="termination",
            )
        assert f"Contract with id '{missing_id}' not found" in str(exc_info.value)


# ====================================================================
# 2. REST API Endpoint Tests
# ====================================================================

class TestKeywordRetrievalAPIEndpoints:
    @pytest.mark.db
    def test_post_keyword_query_success(
        self, test_client: TestClient, keyword_test_data
    ):
        """Verify POST /contracts/{id}/keyword-query returns 200 with ranked KeywordChunkMatch items."""
        primary, _, _, _ = keyword_test_data

        resp = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": "indemnify infringement", "top_k": 3},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["contract_id"] == str(primary.id)
        assert data["query"] == "indemnify infringement"
        assert data["top_k"] == 3
        assert data["total_matches"] >= 1
        assert len(data["matches"]) >= 1

        first_match = data["matches"][0]
        assert "id" in first_match
        assert "contract_id" in first_match
        assert "page_number" in first_match
        assert "chunk_index" in first_match
        assert "section_header" in first_match
        assert "text" in first_match
        assert "keyword_rank" in first_match
        assert isinstance(first_match["keyword_rank"], float)

        # Critical: Embeddings and vector distances MUST NOT be present
        assert "embedding" not in first_match
        assert "similarity_score" not in first_match
        assert "cosine_distance" not in first_match

    @pytest.mark.db
    def test_post_keyword_query_versioned_alias(
        self, test_client: TestClient, keyword_test_data
    ):
        """Verify POST /api/v1/contracts/{id}/keyword-query works identically."""
        primary, _, _, _ = keyword_test_data

        resp = test_client.post(
            f"/api/v1/contracts/{primary.id}/keyword-query",
            json={"query": "written notice"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contract_id"] == str(primary.id)
        assert data["top_k"] == 5  # default top_k

    @pytest.mark.db
    def test_post_keyword_query_default_top_k_is_5(
        self, test_client: TestClient, keyword_test_data
    ):
        """Verify default top_k=5 applied when top_k omitted."""
        primary, _, _, _ = keyword_test_data

        resp = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": "agreement"},
        )
        assert resp.status_code == 200
        assert resp.json()["top_k"] == 5

    @pytest.mark.db
    def test_post_keyword_query_rejects_empty_query(
        self, test_client: TestClient, keyword_test_data
    ):
        """Verify empty query string is rejected with 422."""
        primary, _, _, _ = keyword_test_data

        resp = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.db
    def test_post_keyword_query_rejects_whitespace_query(
        self, test_client: TestClient, keyword_test_data
    ):
        """Verify whitespace-only query is rejected with 422."""
        primary, _, _, _ = keyword_test_data

        resp = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": "    \t\n   "},
        )
        assert resp.status_code == 422

    @pytest.mark.db
    def test_post_keyword_query_rejects_top_k_out_of_bounds(
        self, test_client: TestClient, keyword_test_data
    ):
        """Verify top_k < 1 and top_k > 20 are rejected with 422."""
        primary, _, _, _ = keyword_test_data

        # top_k = 0
        resp_low = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": "valid query", "top_k": 0},
        )
        assert resp_low.status_code == 422

        # top_k = 21
        resp_high = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": "valid query", "top_k": 21},
        )
        assert resp_high.status_code == 422

        # top_k = 20 (maximum bound) should succeed
        resp_max = test_client.post(
            f"/contracts/{primary.id}/keyword-query",
            json={"query": "valid query", "top_k": 20},
        )
        assert resp_max.status_code == 200
        assert resp_max.json()["top_k"] == 20

    @pytest.mark.db
    def test_post_keyword_query_nonexistent_contract_returns_404(
        self, test_client: TestClient
    ):
        """Verify querying nonexistent contract UUID returns 404."""
        missing_id = uuid.uuid4()

        resp = test_client.post(
            f"/contracts/{missing_id}/keyword-query",
            json={"query": "termination"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.db
    def test_phase_5a_vector_query_remains_functional(
        self, test_client: TestClient, keyword_test_data
    ):
        """
        Regression test: Verify Phase 5A vector retrieval endpoint (/contracts/{id}/query)
        remains completely functional and unaffected by Phase 5B keyword additions.
        """
        primary, _, _, _ = keyword_test_data
        from unittest.mock import patch
        from tests.test_vector_retrieval import MockRetrievalEmbeddingProvider

        with patch(
            "app.services.retrieval_service.get_embedding_provider",
            return_value=MockRetrievalEmbeddingProvider(),
        ):
            resp = test_client.post(
                f"/contracts/{primary.id}/query",
                json={"query": "notice period for termination", "top_k": 2},
            )
            # Since primary contract chunks don't have embeddings populated,
            # Phase 5A correctly returns 400 NoEmbeddedChunksError
            assert resp.status_code == 400
            assert "no embedded chunks" in resp.json()["detail"].lower()
