"""add skill runtime tables

Revision ID: 20260413_0003
Revises: 20260408_0002
Create Date: 2026-04-13 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260413_0003"
down_revision: Union[str, None] = "20260408_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("skill_invocation_logs"):
        op.create_table(
            "skill_invocation_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=True),
            sa.Column("workspace_id", sa.String(length=64), nullable=True),
            sa.Column("account_id", sa.String(length=64), nullable=True),
            sa.Column("skill_name", sa.String(length=100), nullable=False),
            sa.Column("request_fingerprint", sa.String(length=128), nullable=True),
            sa.Column("input_json", sa.JSON(), nullable=True),
            sa.Column("output_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="started"),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_task_id"), ["task_id"])
    _create_index_if_missing(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_workspace_id"), ["workspace_id"])
    _create_index_if_missing(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_account_id"), ["account_id"])
    _create_index_if_missing(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_skill_name"), ["skill_name"])
    _create_index_if_missing(
        inspector,
        "skill_invocation_logs",
        op.f("ix_skill_invocation_logs_request_fingerprint"),
        ["request_fingerprint"],
    )

    inspector = sa.inspect(bind)
    if not inspector.has_table("evidence_items"):
        op.create_table(
            "evidence_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.String(length=64), nullable=True),
            sa.Column("task_id", sa.String(length=64), nullable=True),
            sa.Column("account_id", sa.String(length=64), nullable=True),
            sa.Column("skill_name", sa.String(length=100), nullable=True),
            sa.Column("source_type", sa.String(length=64), nullable=False),
            sa.Column("source_id", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("url", sa.String(length=1000), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("raw_payload_json", sa.JSON(), nullable=True),
            sa.Column("normalized_payload_json", sa.JSON(), nullable=True),
            sa.Column("relevance_score", sa.Float(), nullable=True),
            sa.Column("authority_score", sa.Float(), nullable=True),
            sa.Column("freshness_score", sa.Float(), nullable=True),
            sa.Column("practical_score", sa.Float(), nullable=True),
            sa.Column("selected_reason", sa.Text(), nullable=True),
            sa.Column("risk_flags", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "evidence_items", op.f("ix_evidence_items_workspace_id"), ["workspace_id"])
    _create_index_if_missing(inspector, "evidence_items", op.f("ix_evidence_items_task_id"), ["task_id"])
    _create_index_if_missing(inspector, "evidence_items", op.f("ix_evidence_items_account_id"), ["account_id"])
    _create_index_if_missing(inspector, "evidence_items", op.f("ix_evidence_items_skill_name"), ["skill_name"])
    _create_index_if_missing(inspector, "evidence_items", op.f("ix_evidence_items_source_type"), ["source_type"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("skill_cache"):
        op.create_table(
            "skill_cache",
            sa.Column("cache_key", sa.String(length=128), nullable=False),
            sa.Column("skill_name", sa.String(length=100), nullable=False),
            sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
            sa.Column("response_json", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("cache_key"),
        )
        inspector = sa.inspect(bind)
    _create_index_if_missing(inspector, "skill_cache", op.f("ix_skill_cache_skill_name"), ["skill_name"])
    _create_index_if_missing(inspector, "skill_cache", op.f("ix_skill_cache_request_fingerprint"), ["request_fingerprint"])
    _create_index_if_missing(inspector, "skill_cache", op.f("ix_skill_cache_expires_at"), ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("skill_cache"):
        _drop_index_if_exists(inspector, "skill_cache", op.f("ix_skill_cache_expires_at"))
        _drop_index_if_exists(inspector, "skill_cache", op.f("ix_skill_cache_request_fingerprint"))
        _drop_index_if_exists(inspector, "skill_cache", op.f("ix_skill_cache_skill_name"))
        op.drop_table("skill_cache")

    inspector = sa.inspect(bind)
    if inspector.has_table("evidence_items"):
        _drop_index_if_exists(inspector, "evidence_items", op.f("ix_evidence_items_source_type"))
        _drop_index_if_exists(inspector, "evidence_items", op.f("ix_evidence_items_skill_name"))
        _drop_index_if_exists(inspector, "evidence_items", op.f("ix_evidence_items_account_id"))
        _drop_index_if_exists(inspector, "evidence_items", op.f("ix_evidence_items_task_id"))
        _drop_index_if_exists(inspector, "evidence_items", op.f("ix_evidence_items_workspace_id"))
        op.drop_table("evidence_items")

    inspector = sa.inspect(bind)
    if inspector.has_table("skill_invocation_logs"):
        _drop_index_if_exists(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_request_fingerprint"))
        _drop_index_if_exists(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_skill_name"))
        _drop_index_if_exists(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_account_id"))
        _drop_index_if_exists(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_workspace_id"))
        _drop_index_if_exists(inspector, "skill_invocation_logs", op.f("ix_skill_invocation_logs_task_id"))
        op.drop_table("skill_invocation_logs")


def _create_index_if_missing(inspector: sa.Inspector, table: str, index_name: str, columns: list[str]) -> None:
    existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table, columns, unique=False)


def _drop_index_if_exists(inspector: sa.Inspector, table: str, index_name: str) -> None:
    existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
    if index_name in existing_indexes:
        op.drop_index(index_name, table_name=table)
