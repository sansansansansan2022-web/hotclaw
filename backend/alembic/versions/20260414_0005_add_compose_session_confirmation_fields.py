"""add compose session confirmation fields

Revision ID: 20260414_0005
Revises: 20260413_0004
Create Date: 2026-04-14 10:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260414_0005"
down_revision: str | None = "20260413_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "compose_selection_sessions",
        sa.Column("source_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "compose_selection_sessions",
        sa.Column("outline_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "compose_selection_sessions",
        sa.Column("preview_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "compose_selection_sessions",
        sa.Column("approved_outline_seed_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("compose_selection_sessions", "approved_outline_seed_json")
    op.drop_column("compose_selection_sessions", "preview_version")
    op.drop_column("compose_selection_sessions", "outline_confirmed")
    op.drop_column("compose_selection_sessions", "source_confirmed")
