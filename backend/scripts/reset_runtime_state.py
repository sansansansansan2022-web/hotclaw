"""Reset local runtime/demo data while preserving system configuration tables."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import delete, select, func as sa_func

from app.db.session import async_session_factory
from app.models.tables import (
    AccountModel,
    AccountProfileModel,
    AutomationPlanModel,
    ArticleDraftModel,
    AuditResultModel,
    ReferenceSourceModel,
    TaskModel,
    TaskNodeRunModel,
    TopicCandidateModel,
)
from app.models.wechat_config import WeChatConfigModel, WeChatPublishRecordModel


@dataclass(frozen=True)
class ResetTarget:
    label: str
    model: type


RESET_TARGETS: tuple[ResetTarget, ...] = (
    ResetTarget("audit_results", AuditResultModel),
    ResetTarget("wechat_publish_records", WeChatPublishRecordModel),
    ResetTarget("article_drafts", ArticleDraftModel),
    ResetTarget("task_node_runs", TaskNodeRunModel),
    ResetTarget("topic_candidates", TopicCandidateModel),
    ResetTarget("account_profiles", AccountProfileModel),
    ResetTarget("reference_sources", ReferenceSourceModel),
    ResetTarget("automation_plans", AutomationPlanModel),
    ResetTarget("tasks", TaskModel),
    ResetTarget("wechat_configs", WeChatConfigModel),
    ResetTarget("accounts", AccountModel),
)

PRESERVED_TABLES: tuple[str, ...] = (
    "system_configs",
    "llm_providers",
    "agents",
    "skills",
    "workflow_templates",
)


async def collect_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    async with async_session_factory() as session:
        for target in RESET_TARGETS:
            result = await session.execute(select(sa_func.count()).select_from(target.model))
            counts[target.label] = result.scalar() or 0
    return counts


async def apply_reset() -> dict[str, int]:
    deleted: dict[str, int] = {}
    async with async_session_factory() as session:
        for target in RESET_TARGETS:
            result = await session.execute(delete(target.model))
            deleted[target.label] = result.rowcount or 0
        await session.commit()
    return deleted


async def main(apply: bool) -> int:
    counts = await collect_counts()
    print("Runtime tables scheduled for cleanup:")
    for name, count in counts.items():
        print(f"  - {name}: {count}")

    print("Preserved configuration tables:")
    for table in PRESERVED_TABLES:
        print(f"  - {table}")

    if not apply:
        print("\nDry run only. Re-run with --apply to delete the runtime/demo data above.")
        return 0

    deleted = await apply_reset()
    print("\nDeleted rows:")
    for name, count in deleted.items():
        print(f"  - {name}: {count}")

    remaining = await collect_counts()
    print("\nRemaining runtime rows:")
    for name, count in remaining.items():
        print(f"  - {name}: {count}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear local runtime/demo data while preserving system configs.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete runtime/demo rows. Without this flag the script only reports counts.",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
