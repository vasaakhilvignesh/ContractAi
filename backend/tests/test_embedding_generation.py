"""
ContractIQ — Tests for Embedding Generation Service & API (Phase 4B)

Strict Requirements:
  - 100% Mocked: Zero real Gemini API calls.
  - Zero real API keys required.
  - DocumentChunk records -> 768-dim vectors -> DocumentChunk.embedding.
  - Ordering preserved (sorted by chunk_index ASC).
  - Idempotency: skip existing embeddings unless force_reembed=True.
  - Atomic commit / rollback on error (no partial persistence).
  - API endpoints: POST /contracts/{id}/embed and POST /api/v1/contracts/{id}/embed.
  - Zero raw text or secrets in exceptions or logs.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.schemas.embedding import ContractEmbeddingResponse
from app.services.embedding_generation_service import (
    ContractNotFoundError,
    EmbeddingGenerationError,
    NoChunksFoundError,
    generate_contract_embeddings,
)
from app.services.embedding_provider import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingTaskType,
)


def _make_dummy_vector(dim: int = 768, seed: float = 0.1) -> list[float]:
    """Generates a reproducible float vector of specified dimension."""
    return [seed + (i * 0.001) for i in range(dim)]


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock provider for test execution without network calls."""

    def __init__(self, dimension: int = 768, model_name: str = "gemini-embedding-2", batch_size: int = 3):
        self._dim = dimension
        self._model = model_name
        self._batch_size = batch_size
        self.call_count = 0
        self.recorded_texts: list[str] = []
        self.recorded_task_types: list[str] = []
        self.recorded_titles: list[str | None] = []

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_texts(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType | str = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        title: str | None = None,
    ) -> list[list[float]]:
        self.call_count += 1
        self.recorded_texts.extend(texts)
        self.recorded_task_types.append(str(task_type))
        self.recorded_titles.append(title)

        # Return reproducible vectors with distinct seed per index
        return [_make_dummy_vector(dim=self._dim, seed=0.1 * (idx + 1)) for idx in range(len(texts))]


@pytest.fixture
def db_session():
    """Provides a transactional database session for tests with automatic rollback."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_contract_with_chunks(db_session: Session):
    """Creates a temporary contract and 3 chunks in the database for testing."""
    contract = Contract(
        id=uuid.uuid4(),
        title="Acme Test Services Agreement",
        vendor="Acme Corp",
        contract_type="MSA",
        status="active",
        processing_status="completed",
        page_count=2,
    )
    db_session.add(contract)
    db_session.flush()

    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=contract.id,
            page_number=1,
            chunk_index=0,
            char_start=0,
            char_end=150,
            section_header="1. Definitions",
            text="1. Definitions. 'Agreement' means this Master Services Agreement.",
            embedding=None,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=contract.id,
            page_number=1,
            chunk_index=1,
            char_start=151,
            char_end=320,
            section_header="2. Scope of Services",
            text="2. Scope of Services. Provider shall deliver the deliverables as specified.",
            embedding=None,
        ),
        DocumentChunk(
            id=uuid.uuid4(),
            contract_id=contract.id,
            page_number=2,
            chunk_index=2,
            char_start=0,
            char_end=200,
            section_header="3. Termination",
            text="3. Termination. Either party may terminate with 30 days written notice.",
            embedding=None,
        ),
    ]
    db_session.add_all(chunks)
    db_session.commit()

    yield contract, chunks

    # Cleanup
    db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract.id).delete()
    db_session.query(Contract).filter(Contract.id == contract.id).delete()
    db_session.commit()


# ====================================================================
# 1. Service Layer Tests
# ====================================================================

class TestEmbeddingGenerationService:
    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self, db_session: Session, sample_contract_with_chunks):
        contract, chunks = sample_contract_with_chunks
        provider = MockEmbeddingProvider()

        response = await generate_contract_embeddings(
            db=db_session,
            contract_id=contract.id,
            provider=provider,
            force_reembed=False,
        )

        assert response.contract_id == contract.id
        assert response.total_chunks == 3
        assert response.embedded_chunks == 3
        assert response.skipped_chunks == 0
        assert response.dimension == 768
        assert response.model == "gemini-embedding-2"
        assert provider.call_count == 1
        assert len(provider.recorded_texts) == 3

        # Verify database records were persisted with 768-dim float lists
        db_chunks = list(
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.contract_id == contract.id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )
        assert len(db_chunks) == 3
        for idx, chunk in enumerate(db_chunks):
            assert chunk.embedding is not None
            # In PostgreSQL with pgvector, embedding is returned as list or ndarray
            emb_list = list(chunk.embedding)
            assert len(emb_list) == 768
            # Verify ordering: chunk 0 seed 0.1, chunk 1 seed 0.2, chunk 2 seed 0.3
            expected_first_val = 0.1 * (idx + 1)
            assert emb_list[0] == pytest.approx(expected_first_val, abs=1e-4)

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_idempotency_skips_already_embedded_chunks(self, db_session: Session, sample_contract_with_chunks):
        contract, chunks = sample_contract_with_chunks
        provider = MockEmbeddingProvider()

        # Run 1: Embed all 3 chunks
        first_resp = await generate_contract_embeddings(
            db=db_session,
            contract_id=contract.id,
            provider=provider,
            force_reembed=False,
        )
        assert first_resp.embedded_chunks == 3
        assert first_resp.skipped_chunks == 0
        assert provider.call_count == 1

        # Run 2: Re-run without force_reembed -> must skip all, make ZERO provider calls
        second_resp = await generate_contract_embeddings(
            db=db_session,
            contract_id=contract.id,
            provider=provider,
            force_reembed=False,
        )
        assert second_resp.embedded_chunks == 0
        assert second_resp.skipped_chunks == 3
        assert second_resp.total_chunks == 3
        assert "All 3 chunks already have embeddings" in second_resp.message
        # Zero additional provider calls
        assert provider.call_count == 1

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_force_reembed_regenerates_all(self, db_session: Session, sample_contract_with_chunks):
        contract, chunks = sample_contract_with_chunks
        provider = MockEmbeddingProvider()

        # Initial embedding
        await generate_contract_embeddings(
            db=db_session,
            contract_id=contract.id,
            provider=provider,
            force_reembed=False,
        )
        assert provider.call_count == 1

        # Force re-embed
        force_resp = await generate_contract_embeddings(
            db=db_session,
            contract_id=contract.id,
            provider=provider,
            force_reembed=True,
        )
        assert force_resp.embedded_chunks == 3
        assert force_resp.skipped_chunks == 0
        assert provider.call_count == 2

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_zero_chunks_raises_no_chunks_error(self, db_session: Session):
        # Create a contract with no chunks
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
                await generate_contract_embeddings(
                    db=db_session,
                    contract_id=empty_contract.id,
                    provider=MockEmbeddingProvider(),
                )
            assert "has no chunks to embed" in str(exc_info.value)
        finally:
            db_session.query(Contract).filter(Contract.id == empty_contract.id).delete()
            db_session.commit()

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_nonexistent_contract_raises_not_found(self, db_session: Session):
        missing_id = uuid.uuid4()
        with pytest.raises(ContractNotFoundError) as exc_info:
            await generate_contract_embeddings(
                db=db_session,
                contract_id=missing_id,
                provider=MockEmbeddingProvider(),
            )
        assert f"Contract with id '{missing_id}' not found" in str(exc_info.value)

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_provider_failure_triggers_rollback(self, db_session: Session, sample_contract_with_chunks):
        contract, chunks = sample_contract_with_chunks

        # Provider that fails
        failing_provider = MagicMock(spec=EmbeddingProvider)
        failing_provider.embed_texts = AsyncMock(side_effect=RuntimeError("Google Gemini API unavailable 503"))
        failing_provider.dimension = 768
        failing_provider.model_name = "gemini-embedding-2"

        with pytest.raises(EmbeddingGenerationError) as exc_info:
            await generate_contract_embeddings(
                db=db_session,
                contract_id=contract.id,
                provider=failing_provider,
            )

        assert "Embedding generation failed during provider call" in str(exc_info.value)
        assert "Google Gemini API unavailable 503" in str(exc_info.value)

        # Verify rollback: all chunks remain with embedding IS NULL
        db_chunks = (
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.contract_id == contract.id)
            .all()
        )
        assert all(c.embedding is None for c in db_chunks)

    @pytest.mark.db
    @pytest.mark.asyncio
    async def test_dimension_validation_failure_triggers_rollback(self, db_session: Session, sample_contract_with_chunks):
        contract, chunks = sample_contract_with_chunks

        # Provider returning invalid dimensionality (e.g. 512 instead of 768)
        invalid_dim_provider = MagicMock(spec=EmbeddingProvider)
        invalid_dim_provider.embed_texts = AsyncMock(
            return_value=[_make_dummy_vector(dim=512) for _ in range(3)]
        )
        invalid_dim_provider.dimension = 768
        invalid_dim_provider.model_name = "gemini-embedding-2"

        with pytest.raises(EmbeddingGenerationError) as exc_info:
            await generate_contract_embeddings(
                db=db_session,
                contract_id=contract.id,
                provider=invalid_dim_provider,
            )

        assert "Dimensionality validation failed" in str(exc_info.value)
        assert "expected 768 dimensions, received 512" in str(exc_info.value)

        # Verify rollback
        db_chunks = (
            db_session.query(DocumentChunk)
            .filter(DocumentChunk.contract_id == contract.id)
            .all()
        )
        assert all(c.embedding is None for c in db_chunks)


# ====================================================================
# 2. REST API Endpoint Tests
# ====================================================================

class TestEmbeddingAPIEndpoints:
    @pytest.mark.db
    def test_post_embed_success(
        self, test_client: TestClient, sample_contract_with_chunks
    ):
        contract, chunks = sample_contract_with_chunks

        with patch(
            "app.services.embedding_generation_service.get_embedding_provider",
            return_value=MockEmbeddingProvider(),
        ):
            resp = test_client.post(f"/contracts/{contract.id}/embed")
            assert resp.status_code == 200
            data = resp.json()

            assert data["contract_id"] == str(contract.id)
            assert data["total_chunks"] == 3
            assert data["embedded_chunks"] == 3
            assert data["skipped_chunks"] == 0
            assert data["dimension"] == 768
            assert data["model"] == "gemini-embedding-2"
            assert "Successfully generated and persisted 3 embeddings" in data["message"]

    @pytest.mark.db
    def test_post_embed_api_v1_versioned_alias(
        self, test_client: TestClient, sample_contract_with_chunks
    ):
        contract, chunks = sample_contract_with_chunks

        with patch(
            "app.services.embedding_generation_service.get_embedding_provider",
            return_value=MockEmbeddingProvider(),
        ):
            resp = test_client.post(f"/api/v1/contracts/{contract.id}/embed")
            assert resp.status_code == 200
            data = resp.json()
            assert data["contract_id"] == str(contract.id)
            assert data["embedded_chunks"] == 3

    @pytest.mark.db
    def test_post_embed_idempotency_via_api(
        self, test_client: TestClient, sample_contract_with_chunks
    ):
        contract, chunks = sample_contract_with_chunks

        with patch(
            "app.services.embedding_generation_service.get_embedding_provider",
            return_value=MockEmbeddingProvider(),
        ):
            # First call generates embeddings
            r1 = test_client.post(f"/contracts/{contract.id}/embed")
            assert r1.status_code == 200
            assert r1.json()["embedded_chunks"] == 3

            # Second call skips embeddings
            r2 = test_client.post(f"/contracts/{contract.id}/embed")
            assert r2.status_code == 200
            assert r2.json()["embedded_chunks"] == 0
            assert r2.json()["skipped_chunks"] == 3

            # Third call with force_reembed=True re-embeds
            r3 = test_client.post(
                f"/contracts/{contract.id}/embed",
                json={"force_reembed": True},
            )
            assert r3.status_code == 200
            assert r3.json()["embedded_chunks"] == 3
            assert r3.json()["skipped_chunks"] == 0

    @pytest.mark.db
    def test_post_embed_nonexistent_contract_returns_404(
        self, test_client: TestClient
    ):
        fake_id = uuid.uuid4()
        resp = test_client.post(f"/contracts/{fake_id}/embed")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.db
    def test_post_embed_empty_contract_returns_400(
        self, test_client: TestClient, db_session: Session
    ):
        empty_contract = Contract(
            id=uuid.uuid4(),
            title="Empty Contract For API Test",
            status="active",
            processing_status="pending",
        )
        db_session.add(empty_contract)
        db_session.commit()

        try:
            resp = test_client.post(f"/contracts/{empty_contract.id}/embed")
            assert resp.status_code == 400
            assert "no chunks to embed" in resp.json()["detail"]
        finally:
            db_session.query(Contract).filter(Contract.id == empty_contract.id).delete()
            db_session.commit()

    @pytest.mark.db
    def test_post_embed_provider_failure_returns_502(
        self, test_client: TestClient, sample_contract_with_chunks
    ):
        contract, chunks = sample_contract_with_chunks

        failing_provider = MagicMock(spec=EmbeddingProvider)
        failing_provider.embed_texts = AsyncMock(side_effect=RuntimeError("Google GenAI rate limited 429"))
        failing_provider.dimension = 768
        failing_provider.model_name = "gemini-embedding-2"

        with patch(
            "app.services.embedding_generation_service.get_embedding_provider",
            return_value=failing_provider,
        ):
            resp = test_client.post(f"/contracts/{contract.id}/embed")
            assert resp.status_code == 502
            assert "Embedding generation failed" in resp.json()["detail"]
