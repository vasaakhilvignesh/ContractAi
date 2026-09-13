"""add_obligation_type_and_deadline_info

Revision ID: c82e75f1b94a
Revises: fd983c1fd05f
Create Date: 2026-09-13 16:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c82e75f1b94a'
down_revision: Union[str, None] = 'fd983c1fd05f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add obligation_type column with index
    op.add_column(
        'obligations',
        sa.Column(
            'obligation_type',
            sa.String(length=100),
            nullable=True,
            comment=(
                "Type/category of obligation: "
                "payment | delivery | reporting | notice | confidentiality | "
                "compliance | audit | insurance | renewal | termination | other"
            ),
        ),
    )
    op.create_index(
        op.f('ix_obligations_obligation_type'),
        'obligations',
        ['obligation_type'],
        unique=False,
    )

    # 2. Add deadline_info column for textual due date description
    op.add_column(
        'obligations',
        sa.Column(
            'deadline_info',
            sa.String(length=500),
            nullable=True,
            comment="Extracted due/deadline description or trigger condition when present",
        ),
    )

    # 3. Add extraction_confidence column
    op.add_column(
        'obligations',
        sa.Column(
            'extraction_confidence',
            sa.Float(),
            nullable=True,
            comment="LLM extraction confidence score (0.0 to 1.0)",
        ),
    )


def downgrade() -> None:
    # 1. Drop extraction_confidence column
    op.drop_column('obligations', 'extraction_confidence')

    # 2. Drop deadline_info column
    op.drop_column('obligations', 'deadline_info')

    # 3. Drop index and obligation_type column
    op.drop_index(op.f('ix_obligations_obligation_type'), table_name='obligations')
    op.drop_column('obligations', 'obligation_type')
