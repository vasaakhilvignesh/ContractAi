"""typed_vector_and_hnsw_index

Revision ID: 18338ecd31a9
Revises: df2c477aaabb
Create Date: 2026-09-12 19:28:31.587652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '18338ecd31a9'
down_revision: Union[str, None] = 'df2c477aaabb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Alter document_chunks.embedding column from untyped vector to vector(768)
    op.alter_column(
        'document_chunks',
        'embedding',
        existing_type=pgvector.sqlalchemy.Vector(),
        type_=pgvector.sqlalchemy.Vector(768),
        existing_nullable=True,
        nullable=True,
    )

    # 2. Create HNSW index for cosine distance approximate nearest-neighbor search
    op.create_index(
        'idx_document_chunks_embedding_hnsw',
        'document_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    # 1. Drop HNSW index
    op.drop_index(
        'idx_document_chunks_embedding_hnsw',
        table_name='document_chunks',
        postgresql_using='hnsw',
    )

    # 2. Revert column from vector(768) to untyped vector
    op.alter_column(
        'document_chunks',
        'embedding',
        existing_type=pgvector.sqlalchemy.Vector(768),
        type_=pgvector.sqlalchemy.Vector(),
        existing_nullable=True,
        nullable=True,
    )
