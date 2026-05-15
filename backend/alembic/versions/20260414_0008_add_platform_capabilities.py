"""add platform capabilities

Revision ID: 20260414_0008
Revises: 20260414_0007
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260414_0008"
down_revision = "20260414_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_capabilities",
        sa.Column("capability_id", sa.String(length=128), primary_key=True),
        sa.Column("content_platform", sa.String(length=32), nullable=False),
        sa.Column("capability_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("prompt_overrides_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_platform_capabilities_content_platform", "platform_capabilities", ["content_platform"])
    op.create_index("ix_platform_capabilities_capability_type", "platform_capabilities", ["capability_type"])


def downgrade() -> None:
    op.drop_index("ix_platform_capabilities_capability_type", table_name="platform_capabilities")
    op.drop_index("ix_platform_capabilities_content_platform", table_name="platform_capabilities")
    op.drop_table("platform_capabilities")
