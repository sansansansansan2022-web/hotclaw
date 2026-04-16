"""Schema version logging and critical migration guards."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.core.logger import get_logger
from app.db.session import engine
import app.models.wechat_config  # noqa: F401

logger = get_logger(__name__)

CRITICAL_SCHEMA: dict[str, tuple[str, ...]] = {
    "accounts": ("id", "name", "is_active"),
    "tasks": ("id", "account_id", "status", "input_data"),
    "article_drafts": ("id", "task_id", "draft_status", "publish_status"),
    "reference_sources": ("id", "account_id", "metadata_json", "article_count", "latest_error_message"),
    "recommended_content_items": ("id", "account_id", "source_payload_json", "topic_tags_json"),
    "compose_selection_sessions": (
        "id",
        "account_id",
        "selected_recommendation_ids_json",
        "selected_reference_source_ids_json",
        "task_reference_sources_json",
        "source_confirmed",
        "outline_confirmed",
        "preview_version",
        "approved_outline_seed_json",
    ),
    "account_analysis_snapshots": (
        "id",
        "account_id",
        "recommendation_diagnostics_json",
        "recommendation_refreshed_at",
    ),
    "automation_plans": (
        "id",
        "account_id",
        "schedule_config",
        "degrade_policy_json",
        "quality_threshold_json",
    ),
    "system_configs": ("key", "value", "value_type"),
    "wechat_configs": ("id", "account_id", "app_id", "is_enabled"),
    "wechat_publish_records": ("id", "draft_id", "account_id", "publish_status", "trigger_type"),
}


@dataclass(slots=True)
class SchemaGuardReport:
    current_revisions: tuple[str, ...]
    head_revisions: tuple[str, ...]
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: dict[str, list[str]] = field(default_factory=dict)

    @property
    def revision_display(self) -> str:
        return ", ".join(self.current_revisions) if self.current_revisions else "unversioned"

    @property
    def head_display(self) -> str:
        return ", ".join(self.head_revisions) if self.head_revisions else "unknown"

    @property
    def revision_aligned(self) -> bool:
        return set(self.current_revisions) == set(self.head_revisions) and bool(self.head_revisions)

    @property
    def is_ready(self) -> bool:
        return self.revision_aligned and not self.missing_tables and not self.missing_columns

    def failure_message(self) -> str:
        parts: list[str] = []
        if not self.revision_aligned:
            parts.append(
                f"alembic revision mismatch (current={self.revision_display}, head={self.head_display})"
            )
        if self.missing_tables:
            parts.append(f"missing tables: {', '.join(self.missing_tables)}")
        if self.missing_columns:
            column_parts = [
                f"{table}[{', '.join(columns)}]"
                for table, columns in sorted(self.missing_columns.items())
            ]
            parts.append(f"missing columns: {'; '.join(column_parts)}")
        return "; ".join(parts) if parts else "schema is ready"


class SchemaGuardService:
    async def inspect_runtime_schema(self) -> SchemaGuardReport:
        head_revisions = self._load_head_revisions()
        async with engine.connect() as conn:
            report = await conn.run_sync(
                self._inspect_schema_sync,
                head_revisions,
            )
        return report

    async def assert_runtime_schema(self) -> SchemaGuardReport:
        report = await self.inspect_runtime_schema()
        logger.info(
            "schema_version_checked",
            current_revision=report.revision_display,
            head_revision=report.head_display,
            missing_tables=report.missing_tables,
            missing_columns=report.missing_columns,
        )
        if not report.is_ready:
            raise RuntimeError(
                "Database schema check failed: "
                f"{report.failure_message()}. Run `python -m alembic upgrade head` in `backend/` before starting the backend."
            )
        return report

    def inspect_connection_schema(
        self,
        sync_conn,
        *,
        head_revisions: tuple[str, ...] | None = None,
        critical_schema: Mapping[str, tuple[str, ...]] | None = None,
    ) -> SchemaGuardReport:
        return self._inspect_schema_sync(
            sync_conn,
            head_revisions or self._load_head_revisions(),
            critical_schema or CRITICAL_SCHEMA,
        )

    def _inspect_schema_sync(
        self,
        sync_conn,
        head_revisions: tuple[str, ...],
        critical_schema: Mapping[str, tuple[str, ...]] = CRITICAL_SCHEMA,
    ) -> SchemaGuardReport:
        inspector = inspect(sync_conn)
        actual_tables = set(inspector.get_table_names())
        missing_tables = sorted(table for table in critical_schema if table not in actual_tables)
        missing_columns: dict[str, list[str]] = {}

        for table_name, required_columns in critical_schema.items():
            if table_name not in actual_tables:
                continue
            actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
            absent = sorted(column for column in required_columns if column not in actual_columns)
            if absent:
                missing_columns[table_name] = absent

        current_revisions: tuple[str, ...]
        if "alembic_version" in actual_tables:
            rows = sync_conn.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            current_revisions = tuple(str(row[0]) for row in rows if row and row[0])
        else:
            current_revisions = ()

        return SchemaGuardReport(
            current_revisions=current_revisions,
            head_revisions=head_revisions,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def _load_head_revisions() -> tuple[str, ...]:
        backend_dir = Path(__file__).resolve().parents[2]
        config = Config(str(backend_dir / "alembic.ini"))
        config.set_main_option("script_location", str((backend_dir / "alembic").resolve()))
        script = ScriptDirectory.from_config(config)
        return tuple(script.get_heads())


schema_guard_service = SchemaGuardService()
