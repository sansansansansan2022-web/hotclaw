"""add reference_sources table

Revision ID: 20260408_0001
Revises:
Create Date: 2026-04-08 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("reference_sources"):
        op.create_table(
            "reference_sources",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("account_id", sa.String(length=64), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("source_value", sa.Text(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sync_status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("article_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latest_error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    index_name = op.f("ix_reference_sources_account_id")
    existing_indexes = {index["name"] for index in inspector.get_indexes("reference_sources")}
    if index_name not in existing_indexes:
        op.create_index(index_name, "reference_sources", ["account_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("reference_sources"):
        index_name = op.f("ix_reference_sources_account_id")
        existing_indexes = {index["name"] for index in inspector.get_indexes("reference_sources")}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="reference_sources")
        op.drop_table("reference_sources")
