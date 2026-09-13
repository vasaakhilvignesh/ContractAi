"""add_evidence_table

Revision ID: a71f49b1a03e
Revises: e41a982f63cb
Create Date: 2026-09-13 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a71f49b1a03e'
down_revision: Union[str, None] = 'e41a982f63cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'evidence',
        sa.Column('id', sa.UUID(), nullable=False, comment='Unique identifier for this evidence record'),
        sa.Column('contract_id', sa.UUID(), nullable=False, comment='Parent contract this evidence belongs to'),
        sa.Column('source_clause_id', sa.UUID(), nullable=True, comment='Direct FK to clause in the lineage chain (evidence -> source item -> clause)'),
        sa.Column('source_chunk_id', sa.UUID(), nullable=True, comment='Direct FK to document chunk containing the source text'),
        sa.Column('source_item_type', sa.String(length=50), nullable=False, comment='Type of source item supported by this evidence: clause | obligation | contract_fact'),
        sa.Column('source_item_id', sa.UUID(), nullable=False, comment='UUID of the specific source item (clause, obligation, or contract fact)'),
        sa.Column('source_item_reference', sa.String(length=255), nullable=True, comment='Canonical reference identifier for the source item (e.g., clause:<uuid>)'),
        sa.Column('page_number', sa.Integer(), nullable=True, comment='1-indexed source PDF page number where this evidence text appears'),
        sa.Column('source_text', sa.Text(), nullable=False, comment='Verbatim text quote from the contract document serving as evidence'),
        sa.Column('char_start', sa.Integer(), nullable=True, comment='Character start offset of the evidence span within normalized text'),
        sa.Column('char_end', sa.Integer(), nullable=True, comment='Character end offset of the evidence span within normalized text'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Evidence creation timestamp — immutable after insert'),
        sa.CheckConstraint('page_number IS NULL OR page_number >= 1', name='ck_evidence_page_number_positive'),
        sa.CheckConstraint('char_start IS NULL OR char_start >= 0', name='ck_evidence_char_start_non_negative'),
        sa.CheckConstraint('char_end IS NULL OR (char_start IS NOT NULL AND char_end >= char_start)', name='ck_evidence_char_end_gte_start'),
        sa.CheckConstraint("source_item_type IN ('clause', 'obligation', 'contract_fact')", name='ck_evidence_source_item_type_valid'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_clause_id'], ['clauses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_chunk_id'], ['document_chunks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_evidence_contract_id'), 'evidence', ['contract_id'], unique=False)
    op.create_index(op.f('ix_evidence_source_clause_id'), 'evidence', ['source_clause_id'], unique=False)
    op.create_index(op.f('ix_evidence_source_chunk_id'), 'evidence', ['source_chunk_id'], unique=False)
    op.create_index(op.f('ix_evidence_source_item_type'), 'evidence', ['source_item_type'], unique=False)
    op.create_index(op.f('ix_evidence_source_item_id'), 'evidence', ['source_item_id'], unique=False)
    op.create_index(op.f('ix_evidence_source_item_reference'), 'evidence', ['source_item_reference'], unique=False)
    op.create_index(op.f('ix_evidence_page_number'), 'evidence', ['page_number'], unique=False)
    op.create_index(op.f('ix_evidence_created_at'), 'evidence', ['created_at'], unique=False)
    op.create_index('ix_evidence_source_item', 'evidence', ['source_item_type', 'source_item_id'], unique=False)
    op.create_index('ix_evidence_contract_page', 'evidence', ['contract_id', 'page_number'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_evidence_contract_page', table_name='evidence')
    op.drop_index('ix_evidence_source_item', table_name='evidence')
    op.drop_index(op.f('ix_evidence_created_at'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_page_number'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_source_item_reference'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_source_item_id'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_source_item_type'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_source_chunk_id'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_source_clause_id'), table_name='evidence')
    op.drop_index(op.f('ix_evidence_contract_id'), table_name='evidence')
    op.drop_table('evidence')
