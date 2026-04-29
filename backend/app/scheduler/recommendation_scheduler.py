"""Background scheduler for account recommendation refreshes."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.logger import get_logger
from app.core.tracer import generate_trace_id, set_trace_id
from app.models.tables import AccountAnalysisSnapshotModel, AccountModel

logger = get_logger(__name__)

RECOMMENDATION_REFRESH_INTERVAL_SECONDS = 6 * 60 * 60
MAX_CONCURRENT_RECOMMENDATION_REFRESHES = 1


class RecommendationScheduler:
    """Refresh cached recommendation candidates on a slow background cadence."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_RECOMMENDATION_REFRESHES)

    async def start(self) -> None:
        if self._running:
            logger.warning("recommendation_scheduler_already_running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("recommendation_scheduler_started", interval=RECOMMENDATION_REFRESH_INTERVAL_SECONDS)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("recommendation_scheduler_stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.refresh_due_accounts()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "recommendation_scheduler_tick_error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            await asyncio.sleep(RECOMMENDATION_REFRESH_INTERVAL_SECONDS)

    async def refresh_due_accounts(self) -> int:
        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            result = await db.execute(select(AccountModel).where(AccountModel.is_active == True))
            accounts = list(result.scalars().all())
            due_account_ids: list[str] = []
            for account in accounts:
                snapshot = await self._latest_snapshot(account.id, db)
                if self._is_due(snapshot):
                    due_account_ids.append(account.id)

        if not due_account_ids:
            logger.info("recommendation_scheduler_no_due_accounts")
            return 0

        logger.info("recommendation_scheduler_due_accounts", due_account_count=len(due_account_ids))
        await asyncio.gather(*(self._refresh_account_limited(account_id) for account_id in due_account_ids))
        return len(due_account_ids)

    async def _refresh_account_limited(self, account_id: str) -> None:
        async with self._semaphore:
            await self._refresh_account(account_id)

    async def _refresh_account(self, account_id: str) -> None:
        from app.db.session import async_session_factory
        from app.services.recommendation_service import recommendation_service

        trace_id = generate_trace_id()
        set_trace_id(trace_id)
        logger.info("recommendation_scheduler_refresh_started", account_id=account_id, trace_id=trace_id)
        async with async_session_factory() as db:
            try:
                await recommendation_service.refresh_recommendations(account_id, db)
                await db.commit()
                logger.info("recommendation_scheduler_refresh_completed", account_id=account_id)
            except Exception as exc:
                await db.rollback()
                logger.error(
                    "recommendation_scheduler_refresh_failed",
                    account_id=account_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

    async def _latest_snapshot(self, account_id: str, db) -> AccountAnalysisSnapshotModel | None:
        result = await db.execute(
            select(AccountAnalysisSnapshotModel)
            .where(AccountAnalysisSnapshotModel.account_id == account_id)
            .order_by(AccountAnalysisSnapshotModel.generated_at.desc(), AccountAnalysisSnapshotModel.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _is_due(self, snapshot: AccountAnalysisSnapshotModel | None) -> bool:
        if snapshot is None or snapshot.recommendation_refreshed_at is None:
            return True
        refreshed_at = snapshot.recommendation_refreshed_at
        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - refreshed_at >= timedelta(
            seconds=RECOMMENDATION_REFRESH_INTERVAL_SECONDS
        )


recommendation_scheduler = RecommendationScheduler()
