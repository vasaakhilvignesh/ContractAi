"""add_hashed_password_to_users

Revision ID: e911249325b6
Revises: a71f49b1a03e
Create Date: 2026-09-14 12:39:42.675239

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e911249325b6'
down_revision: Union[str, None] = 'a71f49b1a03e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('hashed_password', sa.String(length=255), nullable=True, comment='Cryptographically salted and hashed password'),
    )


def downgrade() -> None:
    op.drop_column('users', 'hashed_password')
