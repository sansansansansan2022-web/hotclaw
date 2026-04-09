"""add automation_plans table

Revision ID: 20260408_0002
Revises: 20260408_0001
Create Date: 2026-04-08 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408_0002"
down_revision: Union[str, None] = "20260408_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("automation_plans"):
        op.create_table(
            "automation_plans",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("account_id", sa.String(length=64), nullable=False),
            sa.Column("is_active_plan", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("plan_type", sa.String(length=20), nullable=False, server_default="manual"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("run_strategy", sa.String(length=20), nullable=False, server_default="manual_only"),
            sa.Column("schedule_type", sa.String(length=20), nullable=False, server_default="none"),
            sa.Column("schedule_config", sa.JSON(), nullable=True),
            sa.Column("auto_publish_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("publish_review_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("max_posts_per_day", sa.Integer(), nullable=True),
            sa.Column("min_interval_minutes", sa.Integer(), nullable=True),
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"),
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("latest_status", sa.String(length=32), nullable=True),
            sa.Column("degrade_policy_json", sa.JSON(), nullable=True),
            sa.Column("quality_threshold_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    index_name = op.f("ix_automation_plans_account_id")
    existing_indexes = {index["name"] for index in inspector.get_indexes("automation_plans")}
    if index_name not in existing_indexes:
        op.create_index(index_name, "automation_plans", ["account_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("automation_plans"):
        index_name = op.f("ix_automation_plans_account_id")
        existing_indexes = {index["name"] for index in inspector.get_indexes("automation_plans")}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="automation_plans")
        op.drop_table("automation_plans")
