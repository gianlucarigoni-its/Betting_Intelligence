"""upgrade team metadata model

Revision ID: 996644213396
Revises: 3e0e62788fde
Create Date: 2026-06-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "996644213396"
down_revision = "3e0e62788fde"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema for richer team metadata."""
    op.add_column(
        "teams",
        sa.Column("canonical_name", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("iso_code_2", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("fifa_code", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column(
            "is_fifa_member",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "teams",
        sa.Column("source_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("source_team_name", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column("last_synced_at", sa.String(length=30), nullable=True),
    )

    op.execute("UPDATE teams SET canonical_name = name WHERE canonical_name IS NULL")
    op.execute("UPDATE teams SET iso_code_2 = country_code WHERE iso_code_2 IS NULL")

    with op.batch_alter_table("teams") as batch_op:
        batch_op.alter_column("canonical_name", existing_type=sa.String(length=150), nullable=False)
        batch_op.create_index("ix_teams_canonical_name", ["canonical_name"], unique=False)
        batch_op.create_index("ix_teams_iso_code_2", ["iso_code_2"], unique=False)
        batch_op.create_index("ix_teams_fifa_code", ["fifa_code"], unique=True)

    with op.batch_alter_table("teams") as batch_op:
        batch_op.alter_column("is_fifa_member", server_default=None)
        batch_op.alter_column("is_active", server_default=None)


def downgrade() -> None:
    """Downgrade database schema by removing richer team metadata."""
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_index("ix_teams_fifa_code")
        batch_op.drop_index("ix_teams_iso_code_2")
        batch_op.drop_index("ix_teams_canonical_name")

    op.drop_column("teams", "last_synced_at")
    op.drop_column("teams", "source_team_name")
    op.drop_column("teams", "source_name")
    op.drop_column("teams", "is_active")
    op.drop_column("teams", "is_fifa_member")
    op.drop_column("teams", "fifa_code")
    op.drop_column("teams", "iso_code_2")
    op.drop_column("teams", "canonical_name")