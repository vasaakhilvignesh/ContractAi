"""add_contract_facts_table

Revision ID: e41a982f63cb
Revises: c82e75f1b94a
Create Date: 2026-09-13 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e41a982f63cb'
down_revision: Union[str, None] = 'c82e75f1b94a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create contract_facts table
    op.create_table(
        'contract_facts',
        sa.Column('id', sa.UUID(), nullable=False, comment='Unique identifier for this extracted contract fact'),
        sa.Column('contract_id', sa.UUID(), nullable=False, comment='Parent contract this fact belongs to'),
        sa.Column('source_clause_id', sa.UUID(), nullable=True, comment='Source clause from which this fact was extracted'),
        sa.Column('source_chunk_id', sa.UUID(), nullable=True, comment='Source document chunk for direct evidence reference'),
        sa.Column('fact_key', sa.String(length=100), nullable=False, comment='Standard fact identifier (e.g., effective_date, governing_law, liability_cap)'),
        sa.Column('fact_value', sa.Text(), nullable=True, comment='Extracted textual or normalized value of the fact'),
        sa.Column('fact_value_json', sa.Text(), nullable=True, comment='Optional JSON-serialized representation for multi-valued or complex facts'),
        sa.Column('verbatim_evidence', sa.Text(), nullable=True, comment='Exact quoted text from the contract/clause supporting this fact'),
        sa.Column('page_number', sa.Integer(), nullable=True, comment='Page number in the source PDF where the fact evidence appears (1-indexed)'),
        sa.Column('confidence', sa.Float(), nullable=True, comment='LLM extraction confidence score (0.0 to 1.0)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record last-updated timestamp'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_clause_id'], ['clauses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_chunk_id'], ['document_chunks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_contract_facts_contract_id'), 'contract_facts', ['contract_id'], unique=False)
    op.create_index(op.f('ix_contract_facts_source_clause_id'), 'contract_facts', ['source_clause_id'], unique=False)
    op.create_index(op.f('ix_contract_facts_source_chunk_id'), 'contract_facts', ['source_chunk_id'], unique=False)
    op.create_index(op.f('ix_contract_facts_fact_key'), 'contract_facts', ['fact_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contract_facts_fact_key'), table_name='contract_facts')
    op.drop_index(op.f('ix_contract_facts_source_chunk_id'), table_name='contract_facts')
    op.drop_index(op.f('ix_contract_facts_source_clause_id'), table_name='contract_facts')
    op.drop_index(op.f('ix_contract_facts_contract_id'), table_name='contract_facts')
    op.drop_table('contract_facts')
