"""add_search_vector_and_gin_index

Revision ID: fd983c1fd05f
Revises: 18338ecd31a9
Create Date: 2026-09-12 21:57:59.167070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fd983c1fd05f'
down_revision: Union[str, None] = '18338ecd31a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add search_vector as a stored generated TSVECTOR column derived from text
    op.add_column(
        'document_chunks',
        sa.Column(
            'search_vector',
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
            comment="PostgreSQL tsvector generated automatically from chunk text for full-text search",
        ),
    )

    # 2. Create GIN index for full-text search queries
    op.create_index(
        'idx_document_chunks_search_vector_gin',
        'document_chunks',
        ['search_vector'],
        unique=False,
        postgresql_using='gin',
    )


def downgrade() -> None:
    # 1. Drop GIN index
    op.drop_index(
        'idx_document_chunks_search_vector_gin',
        table_name='document_chunks',
        postgresql_using='gin',
    )

    # 2. Drop search_vector column
    op.drop_column('document_chunks', 'search_vector')
