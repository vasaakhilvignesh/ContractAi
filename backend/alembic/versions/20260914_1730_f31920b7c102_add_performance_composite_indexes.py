"""add_performance_composite_indexes

Revision ID: f31920b7c102
Revises: e911249325b6
Create Date: 2026-09-14 17:30:00.000000

Phase 19C: Add justified composite indexes to accelerate common access paths:
  1. document_chunks(contract_id, chunk_index) - accelerates sequential chunk loading and context assembly
  2. contract_facts(contract_id, fact_key) - accelerates fact lookup by key in comparison and analyst queries
  3. clauses(contract_id, clause_type) - accelerates clause filtering by category in risk analysis and comparison
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f31920b7c102'
down_revision: Union[str, None] = 'e911249325b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite index for document chunks by contract and chunk index
    op.create_index(
        'ix_document_chunks_contract_chunk_idx',
        'document_chunks',
        ['contract_id', 'chunk_index'],
        unique=False,
    )

    # 2. Composite index for contract facts by contract and fact key
    op.create_index(
        'ix_contract_facts_contract_fact_key',
        'contract_facts',
        ['contract_id', 'fact_key'],
        unique=False,
    )

    # 3. Composite index for clauses by contract and clause type
    op.create_index(
        'ix_clauses_contract_clause_type',
        'clauses',
        ['contract_id', 'clause_type'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_clauses_contract_clause_type', table_name='clauses')
    op.drop_index('ix_contract_facts_contract_fact_key', table_name='contract_facts')
    op.drop_index('ix_document_chunks_contract_chunk_idx', table_name='document_chunks')
