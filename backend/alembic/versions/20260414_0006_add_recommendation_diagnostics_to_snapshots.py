"""add recommendation diagnostics to account analysis snapshots

Revision ID: 20260414_0006
Revises: 20260414_0005
Create Date: 2026-04-14 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260414_0006"
down_revision: str | None = "20260414_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("account_analysis_snapshots")}

    if "recommendation_diagnostics_json" not in column_names:
        op.add_column(
            "account_analysis_snapshots",
            sa.Column("recommendation_diagnostics_json", sa.JSON(), nullable=True),
        )
    if "recommendation_refreshed_at" not in column_names:
        op.add_column(
            "account_analysis_snapshots",
            sa.Column("recommendation_refreshed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    column_names = {column["name"] for column in inspector.get_columns("account_analysis_snapshots")}

    if "recommendation_refreshed_at" in column_names:
        op.drop_column("account_analysis_snapshots", "recommendation_refreshed_at")
    if "recommendation_diagnostics_json" in column_names:
        op.drop_column("account_analysis_snapshots", "recommendation_diagnostics_json")
