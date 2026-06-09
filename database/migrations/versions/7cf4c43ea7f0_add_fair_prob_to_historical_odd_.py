"""add fair_prob to historical odd snapshots

Revision ID: 7cf4c43ea7f0
Revises: 931852330f15
Create Date: 2026-06-09 11:59:02.515729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cf4c43ea7f0'
down_revision: Union[str, Sequence[str], None] = '931852330f15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "historical_odd_snapshots",
        sa.Column("fair_prob", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("historical_odd_snapshots", "fair_prob")
