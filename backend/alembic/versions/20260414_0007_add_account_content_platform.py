"""add account content platform

Revision ID: 20260414_0007
Revises: 20260414_0006
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_0007"
down_revision = "20260414_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("content_platform", sa.String(length=32), nullable=False, server_default="wechat"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "content_platform")
