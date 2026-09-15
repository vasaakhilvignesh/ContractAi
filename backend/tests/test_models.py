"""
ContractIQ — Tests for SQLAlchemy Models

Tests:
  1. All 7 model classes are importable.
  2. Table names are correctly defined.
  3. Base.metadata contains all expected tables.
  4. Key columns exist on each model (spot-check for schema integrity).
  5. Relationships are defined (spot-check).

These tests do NOT require a database connection.
"""

import pytest
from sqlalchemy import inspect as sa_inspect

from app.db.base import Base
import app.models  # ensures all models are loaded into Base.metadata

from app.models.user import User
from app.models.contract import Contract
from app.models.document_chunk import DocumentChunk
from app.models.clause import Clause
from app.models.obligation import Obligation
from app.models.risk_signal import RiskSignal
from app.models.audit_event import AuditEvent
from app.models.contract_fact import ContractFact
from app.models.evidence import Evidence


EXPECTED_TABLES = {
    "users",
    "contracts",
    "document_chunks",
    "clauses",
    "obligations",
    "risk_signals",
    "audit_events",
    "contract_facts",
    "evidence",
}


class TestModelImports:
    """All 7 model classes must be importable without error."""

    def test_user_importable(self):
        assert User is not None

    def test_contract_importable(self):
        assert Contract is not None

    def test_document_chunk_importable(self):
        assert DocumentChunk is not None

    def test_clause_importable(self):
        assert Clause is not None

    def test_obligation_importable(self):
        assert Obligation is not None

    def test_risk_signal_importable(self):
        assert RiskSignal is not None

    def test_audit_event_importable(self):
        assert AuditEvent is not None

    def test_contract_fact_importable(self):
        assert ContractFact is not None

    def test_evidence_importable(self):
        assert Evidence is not None


class TestTableNames:
    """Each model must declare the correct table name."""

    def test_users_table_name(self):
        assert User.__tablename__ == "users"

    def test_contracts_table_name(self):
        assert Contract.__tablename__ == "contracts"

    def test_document_chunks_table_name(self):
        assert DocumentChunk.__tablename__ == "document_chunks"

    def test_clauses_table_name(self):
        assert Clause.__tablename__ == "clauses"

    def test_obligations_table_name(self):
        assert Obligation.__tablename__ == "obligations"

    def test_risk_signals_table_name(self):
        assert RiskSignal.__tablename__ == "risk_signals"

    def test_audit_events_table_name(self):
        assert AuditEvent.__tablename__ == "audit_events"

    def test_contract_facts_table_name(self):
        assert ContractFact.__tablename__ == "contract_facts"

    def test_evidence_table_name(self):
        assert Evidence.__tablename__ == "evidence"


class TestBaseMetadata:
    """Base.metadata must contain all 7 expected tables."""

    def test_all_tables_registered_in_metadata(self):
        registered = set(Base.metadata.tables.keys())
        missing = EXPECTED_TABLES - registered
        assert not missing, (
            f"The following tables are missing from Base.metadata: {missing}. "
            "Ensure all model modules are imported in app/models/__init__.py."
        )

    def test_no_unexpected_tables(self):
        registered = set(Base.metadata.tables.keys())
        unexpected = registered - EXPECTED_TABLES
        assert not unexpected, (
            f"Unexpected tables found in Base.metadata: {unexpected}. "
            "If these are intentional, update EXPECTED_TABLES in this test."
        )


class TestEvidenceLineageColumns:
    """
    Verify that critical evidence lineage columns exist on each model.
    These columns are what make the evidence chain traceable.
    """

    def _get_column_names(self, model) -> set:
        mapper = sa_inspect(model)
        return {col.key for col in mapper.columns}

    def test_document_chunk_has_contract_id(self):
        cols = self._get_column_names(DocumentChunk)
        assert "contract_id" in cols

    def test_document_chunk_has_page_number(self):
        cols = self._get_column_names(DocumentChunk)
        assert "page_number" in cols

    def test_document_chunk_has_chunk_index(self):
        cols = self._get_column_names(DocumentChunk)
        assert "chunk_index" in cols

    def test_document_chunk_has_embedding_column(self):
        cols = self._get_column_names(DocumentChunk)
        assert "embedding" in cols, (
            "embedding column must exist on document_chunks for pgvector support"
        )

    def test_clause_has_contract_id(self):
        cols = self._get_column_names(Clause)
        assert "contract_id" in cols

    def test_clause_has_source_chunk_id(self):
        cols = self._get_column_names(Clause)
        assert "source_chunk_id" in cols

    def test_clause_has_page_number(self):
        cols = self._get_column_names(Clause)
        assert "page_number" in cols

    def test_clause_has_verbatim_text(self):
        cols = self._get_column_names(Clause)
        assert "verbatim_text" in cols

    def test_obligation_has_source_clause_id(self):
        cols = self._get_column_names(Obligation)
        assert "source_clause_id" in cols

    def test_obligation_has_source_chunk_id(self):
        cols = self._get_column_names(Obligation)
        assert "source_chunk_id" in cols

    def test_obligation_has_page_number(self):
        cols = self._get_column_names(Obligation)
        assert "page_number" in cols

    def test_risk_signal_has_source_clause_id(self):
        cols = self._get_column_names(RiskSignal)
        assert "source_clause_id" in cols

    def test_risk_signal_has_rule_id(self):
        cols = self._get_column_names(RiskSignal)
        assert "rule_id" in cols, (
            "rule_id is required for deterministic rules engine traceability"
        )

    def test_risk_signal_has_verbatim_evidence(self):
        cols = self._get_column_names(RiskSignal)
        assert "verbatim_evidence" in cols

    def test_risk_signal_has_page_number(self):
        cols = self._get_column_names(RiskSignal)
        assert "page_number" in cols


class TestRelationships:
    """Verify that key relationships are declared on models."""

    def _get_relationship_names(self, model) -> set:
        mapper = sa_inspect(model)
        return {rel.key for rel in mapper.relationships}

    def test_user_has_contracts_relationship(self):
        rels = self._get_relationship_names(User)
        assert "contracts" in rels

    def test_contract_has_document_chunks_relationship(self):
        rels = self._get_relationship_names(Contract)
        assert "document_chunks" in rels

    def test_contract_has_clauses_relationship(self):
        rels = self._get_relationship_names(Contract)
        assert "clauses" in rels

    def test_contract_has_obligations_relationship(self):
        rels = self._get_relationship_names(Contract)
        assert "obligations" in rels

    def test_contract_has_risk_signals_relationship(self):
        rels = self._get_relationship_names(Contract)
        assert "risk_signals" in rels

    def test_clause_has_obligations_relationship(self):
        rels = self._get_relationship_names(Clause)
        assert "obligations" in rels

    def test_clause_has_risk_signals_relationship(self):
        rels = self._get_relationship_names(Clause)
        assert "risk_signals" in rels

    def test_document_chunk_has_clauses_relationship(self):
        rels = self._get_relationship_names(DocumentChunk)
        assert "clauses" in rels
