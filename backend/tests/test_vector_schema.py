"""
ContractIQ — Tests for Vector(768) Schema & HNSW Index (Phase 4C)

Verifies:
  1. SQLAlchemy model declares Vector(768).
  2. Live database column format_type is vector(768).
  3. Column is nullable (supporting un-embedded chunks).
  4. HNSW index idx_document_chunks_embedding_hnsw exists with vector_cosine_ops.
  5. Chunks with embedding=None are accepted and persisted.
  6. Chunks with 768-dimensional float vectors are accepted and persisted.
  7. Chunks with incorrect dimensionality (e.g. 512) are rejected by PostgreSQL.
  8. Alembic version is at 18338ecd31a9.
"""

import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.contract import Contract
from app.models.document_chunk import EMBEDDING_DIMENSION, DocumentChunk


def _make_dummy_vector(dim: int = 768, seed: float = 0.05) -> list[float]:
    """Generates a reproducible float vector of specified dimension."""
    return [seed + (i * 0.001) for i in range(dim)]


@pytest.fixture
def db_session():
    """Provides a transactional database session with cleanup."""
    if not settings.is_database_configured:
        pytest.skip("DATABASE_URL is not configured.")
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def temporary_contract(db_session: Session):
    """Creates a temporary contract for testing chunk insertions."""
    contract = Contract(
        id=uuid.uuid4(),
        title="Vector Schema Test Contract",
        status="active",
        processing_status="chunking",
    )
    db_session.add(contract)
    db_session.commit()

    yield contract

    # Cleanup any chunks and the contract
    db_session.query(DocumentChunk).filter(DocumentChunk.contract_id == contract.id).delete()
    db_session.query(Contract).filter(Contract.id == contract.id).delete()
    db_session.commit()


# ====================================================================
# Model & Schema Unit Tests
# ====================================================================

class TestVectorModelDeclaration:
    def test_model_declares_vector_768(self):
        """Verify SQLAlchemy model defines DocumentChunk.embedding as Vector(768)."""
        assert EMBEDDING_DIMENSION == 768
        assert settings.embedding_dimension == 768

        embedding_col = DocumentChunk.__table__.c.embedding
        assert embedding_col.type.dim == 768
        assert embedding_col.nullable is True


# ====================================================================
# Database Catalog & Schema Tests
# ====================================================================

class TestVectorDatabaseCatalog:
    @pytest.mark.db
    def test_database_column_type_is_vector_768(self, db_session: Session):
        """Verify PostgreSQL catalog reports format_type as vector(768) and nullable."""
        result = db_session.execute(text("""
            SELECT 
                a.attname, 
                pg_catalog.format_type(a.atttypid, a.atttypmod) as format_type,
                NOT a.attnotnull as is_nullable
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relname = 'document_chunks' AND a.attname = 'embedding';
        """)).mappings().first()

        assert result is not None
        assert result["attname"] == "embedding"
        assert result["format_type"] == "vector(768)"
        assert result["is_nullable"] is True

    @pytest.mark.db
    def test_hnsw_index_exists_with_vector_cosine_ops(self, db_session: Session):
        """Verify HNSW index exists on document_chunks using vector_cosine_ops."""
        result = db_session.execute(text("""
            SELECT 
                i.relname as index_name,
                am.amname as index_type,
                opc.opcname as opclass_name,
                ix.indisunique,
                pg_get_indexdef(i.oid) as index_def
            FROM pg_index ix
            JOIN pg_class c ON ix.indrelid = c.oid
            JOIN pg_class i ON ix.indexrelid = i.oid
            JOIN pg_am am ON i.relam = am.oid
            JOIN pg_opclass opc ON opc.oid = ANY(ix.indclass)
            WHERE c.relname = 'document_chunks' AND i.relname = 'idx_document_chunks_embedding_hnsw';
        """)).mappings().first()

        assert result is not None
        assert result["index_name"] == "idx_document_chunks_embedding_hnsw"
        assert result["index_type"] == "hnsw"
        assert result["opclass_name"] == "vector_cosine_ops"
        assert result["indisunique"] is False
        assert "USING hnsw (embedding vector_cosine_ops)" in result["index_def"]

    @pytest.mark.db
    def test_alembic_current_revision(self, db_session: Session):
        """Verify Alembic migration revision is at current schema head."""
        rev = db_session.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        assert rev == "f31920b7c102"


# ====================================================================
# Data Integrity & Constraint Tests
# ====================================================================

class TestVectorDataIntegrity:
    @pytest.mark.db
    def test_null_embedding_is_valid(self, db_session: Session, temporary_contract: Contract):
        """Verify chunks with embedding=None persist without constraint violation."""
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=temporary_contract.id,
            page_number=1,
            chunk_index=0,
            text="Clause text without embedding.",
            embedding=None,
        )
        db_session.add(chunk)
        db_session.commit()

        # Query back
        stored = db_session.query(DocumentChunk).filter(DocumentChunk.id == chunk.id).first()
        assert stored is not None
        assert stored.embedding is None

    @pytest.mark.db
    def test_768_dimensional_vector_persists(self, db_session: Session, temporary_contract: Contract):
        """Verify 768-dimensional float vectors persist and retrieve accurately."""
        test_vec = _make_dummy_vector(dim=768, seed=0.42)
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=temporary_contract.id,
            page_number=1,
            chunk_index=1,
            text="Clause text with 768-dim vector embedding.",
            embedding=test_vec,
        )
        db_session.add(chunk)
        db_session.commit()

        # Query back
        stored = db_session.query(DocumentChunk).filter(DocumentChunk.id == chunk.id).first()
        assert stored is not None
        assert stored.embedding is not None

        retrieved_list = list(stored.embedding)
        assert len(retrieved_list) == 768
        assert pytest.approx(retrieved_list[0], abs=1e-4) == pytest.approx(test_vec[0], abs=1e-4)

    @pytest.mark.db
    def test_invalid_dimension_rejected_by_model(self, db_session: Session, temporary_contract: Contract):
        """Verify pgvector/SQLAlchemy rejects vectors with dimensionality != 768 on insert."""
        wrong_dim_vec = _make_dummy_vector(dim=512)
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            contract_id=temporary_contract.id,
            page_number=1,
            chunk_index=2,
            text="Clause with 512-dim vector (should fail).",
            embedding=wrong_dim_vec,
        )
        db_session.add(chunk)

        try:
            with pytest.raises((SQLAlchemyError, ValueError)) as exc_info:
                db_session.commit()
            error_msg = str(exc_info.value).lower()
            assert "768" in error_msg and ("512" in error_msg or "dimensions" in error_msg)
        finally:
            db_session.rollback()

    @pytest.mark.db
    def test_invalid_dimension_rejected_by_postgresql_engine(self, db_session: Session, temporary_contract: Contract):
        """Verify PostgreSQL database engine rejects raw SQL with invalid vector dimensions."""
        chunk_id = uuid.uuid4()
        raw_insert = text("""
            INSERT INTO document_chunks (
                id, contract_id, page_number, chunk_index, text, embedding
            ) VALUES (
                :id, :contract_id, 1, 3, 'Raw invalid dim test', '[1.0, 2.0, 3.0]'::vector
            )
        """)
        try:
            with pytest.raises(DBAPIError) as exc_info:
                db_session.execute(raw_insert, {"id": chunk_id, "contract_id": temporary_contract.id})
                db_session.commit()
            error_msg = str(exc_info.value).lower()
            assert "768" in error_msg and "expected" in error_msg
        finally:
            db_session.rollback()
