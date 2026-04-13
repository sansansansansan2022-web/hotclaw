"""add pre-generation decision tables

Revision ID: 20260413_0004
Revises: 20260413_0003
Create Date: 2026-04-13 20:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260413_0004"
down_revision: str | None = "20260413_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_analysis_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("positioning_summary", sa.Text(), nullable=False),
        sa.Column("audience_summary", sa.Text(), nullable=True),
        sa.Column("tone_summary", sa.Text(), nullable=True),
        sa.Column("content_lanes_json", sa.JSON(), nullable=True),
        sa.Column("style_keywords_json", sa.JSON(), nullable=True),
        sa.Column("banned_angles_json", sa.JSON(), nullable=True),
        sa.Column("recent_topics_json", sa.JSON(), nullable=True),
        sa.Column("reference_overview_json", sa.JSON(), nullable=True),
        sa.Column("latest_ops_summary_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ready"),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_analysis_snapshots_account_id",
        "account_analysis_snapshots",
        ["account_id"],
        unique=False,
    )

    op.create_table(
        "recommended_content_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("authority_score", sa.Float(), nullable=True),
        sa.Column("freshness_score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("topic_tags_json", sa.JSON(), nullable=True),
        sa.Column("source_payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommended_content_items_account_id",
        "recommended_content_items",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommended_content_items_source_type",
        "recommended_content_items",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_recommended_content_items_status",
        "recommended_content_items",
        ["status"],
        unique=False,
    )

    op.create_table(
        "compose_selection_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("selected_recommendation_ids_json", sa.JSON(), nullable=True),
        sa.Column("selected_reference_source_ids_json", sa.JSON(), nullable=True),
        sa.Column("creation_note", sa.Text(), nullable=True),
        sa.Column("preferred_lane", sa.String(length=100), nullable=True),
        sa.Column("title_direction", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compose_selection_sessions_account_id",
        "compose_selection_sessions",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_compose_selection_sessions_account_id", table_name="compose_selection_sessions")
    op.drop_table("compose_selection_sessions")

    op.drop_index("ix_recommended_content_items_status", table_name="recommended_content_items")
    op.drop_index("ix_recommended_content_items_source_type", table_name="recommended_content_items")
    op.drop_index("ix_recommended_content_items_account_id", table_name="recommended_content_items")
    op.drop_table("recommended_content_items")

    op.drop_index("ix_account_analysis_snapshots_account_id", table_name="account_analysis_snapshots")
    op.drop_table("account_analysis_snapshots")
