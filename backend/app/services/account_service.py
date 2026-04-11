"""Account service: business logic for account lifecycle management."""

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    AccountNotFoundError,
    AccountInactiveError,
    AccountValidationError,
    TaskAlreadyExistsError,
    TaskCreateError,
)
from app.core.logger import get_logger
from app.core.tracer import generate_task_id, generate_account_id
from app.models.tables import AccountModel, ReferenceSourceModel, TaskModel
from app.services.automation_plan_service import automation_plan_service
from app.services.account_harness_service import account_harness_service
from app.services.article_assembler_service import article_assembler_service
from app.services.reference_digest_service import reference_digest_service

logger = get_logger(__name__)

# Frequency → approximate interval in days
FREQUENCY_INTERVALS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
}

# Valid operation modes
VALID_OPERATION_MODES = {"manual", "semi_auto", "full_auto"}


class AccountService:

    # -------------------------------------------------------------------------
    # CRUD
    # -------------------------------------------------------------------------

    async def create_account(self, data: dict, db: AsyncSession) -> AccountModel:
        """Create a new account."""
        from app.core.tracer import generate_account_id

        automation_plan_payload = data.pop("automation_plan", None)

        # Validate operation_mode
        operation_mode = data.get("operation_mode", "manual")
        if operation_mode not in VALID_OPERATION_MODES:
            raise AccountValidationError(
                message=f"invalid operation_mode: {operation_mode}",
                details={"valid_modes": list(VALID_OPERATION_MODES)}
            )

        account_id = generate_account_id()
        account = AccountModel(
            id=account_id,
            name=data["name"],
            positioning=data["positioning"],
            category=data.get("category"),
            audience=data.get("audience"),
            tone_style=data.get("tone_style"),
            posting_frequency=data.get("posting_frequency"),
            posting_time=data.get("posting_time"),
            content_strategy=data.get("content_strategy"),
            reference_accounts=data.get("reference_accounts"),
            operation_mode=operation_mode,
            auto_run_enabled=data.get("auto_run_enabled", False),
            auto_publish_enabled=data.get("auto_publish_enabled", False),
            is_active=data.get("is_active", True),
            last_run_status="never_run",
            # Publish protection fields
            publish_paused=data.get("publish_paused", False),
            max_posts_per_day=data.get("max_posts_per_day"),
            min_interval_minutes=data.get("min_interval_minutes"),
        )
        db.add(account)
        await db.flush()
        await automation_plan_service.create_initial_plan(account, db, automation_plan_payload)
        logger.info("account_created", account_id=account_id, name=data["name"])
        return account

    async def get_account(self, account_id: str, db: AsyncSession) -> AccountModel:
        """Get account by ID."""
        stmt = select(AccountModel).where(AccountModel.id == account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    async def get_account_detail(
        self, account_id: str, db: AsyncSession, recent_limit: int = 5
    ) -> dict[str, Any]:
        """
        Get full account detail with recent tasks.
        Returns serializable dict (not ORM) for response.
        """
        account = await self.get_account(account_id, db)
        await db.refresh(account)
        automation_plan_summary = await automation_plan_service.get_effective_summary(account, db)

        # Fetch recent tasks
        stmt = (
            select(
                TaskModel.id,
                TaskModel.status,
                TaskModel.created_at,
                TaskModel.elapsed_seconds,
                TaskModel.input_data,
                TaskModel.result_data,
            )
            .where(TaskModel.account_id == account_id)
            .order_by(desc(TaskModel.created_at), desc(TaskModel.id))
            .limit(recent_limit)
        )
        result = await db.execute(stmt)
        recent_task_rows = list(result.all())
        latest_task = recent_task_rows[0] if recent_task_rows else None
        latest_ops_context = account_harness_service.extract_ops_context(
            latest_task.input_data if latest_task else None,
            latest_task.result_data if latest_task else None,
        )
        latest_run_strategy = latest_ops_context.get("run_strategy") if isinstance(latest_ops_context, dict) else {}
        latest_effective_mode = latest_run_strategy.get("effective_mode") if isinstance(latest_run_strategy, dict) else None
        latest_allow_auto_publish = (
            bool(latest_run_strategy.get("allow_auto_publish"))
            if isinstance(latest_run_strategy, dict) and "allow_auto_publish" in latest_run_strategy
            else None
        )
        latest_ops_degraded = bool(
            latest_effective_mode
            and automation_plan_summary.get("plan_type")
            and latest_effective_mode != automation_plan_summary.get("plan_type")
        )

        source_count_result = await db.execute(
            select(sa_func.count())
            .select_from(ReferenceSourceModel)
            .where(ReferenceSourceModel.account_id == account_id)
        )
        reference_source_count = int(source_count_result.scalar() or 0)

        enabled_count_result = await db.execute(
            select(sa_func.count())
            .select_from(ReferenceSourceModel)
            .where(
                ReferenceSourceModel.account_id == account_id,
                ReferenceSourceModel.is_enabled.is_(True),
            )
        )
        reference_source_enabled_count = int(enabled_count_result.scalar() or 0)

        latest_source_result = await db.execute(
            select(ReferenceSourceModel.sync_status)
            .where(ReferenceSourceModel.account_id == account_id)
            .order_by(desc(ReferenceSourceModel.updated_at), desc(ReferenceSourceModel.id))
            .limit(1)
        )
        reference_source_last_sync_status = latest_source_result.scalar_one_or_none()

        logger.info(
            "account_detail_loaded",
            account_id=account_id,
            recent_limit=recent_limit,
            recent_task_count=len(recent_task_rows),
            reference_source_count=reference_source_count,
        )

        return {
            "account_id": account.id,
            "name": account.name,
            "category": account.category,
            "positioning": account.positioning,
            "audience": account.audience,
            "tone_style": account.tone_style,
            "posting_frequency": account.posting_frequency,
            "posting_time": account.posting_time,
            "content_strategy": account.content_strategy,
            "reference_accounts": account.reference_accounts,
            "operation_mode": account.operation_mode,
            "auto_run_enabled": account.auto_run_enabled,
            "auto_publish_enabled": account.auto_publish_enabled,
            "is_active": account.is_active,
            "publish_paused": getattr(account, "publish_paused", False),
            "max_posts_per_day": getattr(account, "max_posts_per_day", None),
            "min_interval_minutes": getattr(account, "min_interval_minutes", None),
            "last_run_at": account.last_run_at.isoformat() if account.last_run_at else None,
            "next_run_at": account.next_run_at.isoformat() if account.next_run_at else None,
            "last_run_status": account.last_run_status,
            "last_error_message": account.last_error_message,
            "last_publish_status": getattr(account, "last_publish_status", None),
            "last_publish_error_message": getattr(account, "last_publish_error_message", None),
            "last_published_at": account.last_published_at.isoformat() if account.last_published_at else None,
            "reference_source_count": reference_source_count,
            "reference_source_enabled_count": reference_source_enabled_count,
            "reference_source_last_sync_status": reference_source_last_sync_status,
            "automation_plan_summary": automation_plan_summary,
            "latest_ops_context": latest_ops_context,
            "latest_effective_mode": latest_effective_mode,
            "latest_allow_auto_publish": latest_allow_auto_publish,
            "latest_ops_degraded": latest_ops_degraded,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            "recent_tasks": [
                {
                    "task_id": t.id,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "elapsed_seconds": t.elapsed_seconds,
                }
                for t in recent_task_rows
            ],
        }

    async def update_account(
        self, account_id: str, data: dict, db: AsyncSession
    ) -> AccountModel:
        """Update account fields (only provided fields are applied)."""
        automation_plan_payload = data.pop("automation_plan", None)
        legacy_plan_fields = {
            "operation_mode",
            "auto_run_enabled",
            "auto_publish_enabled",
            "posting_frequency",
            "posting_time",
            "max_posts_per_day",
            "min_interval_minutes",
        }
        has_legacy_plan_updates = any(field in data for field in legacy_plan_fields)

        # Validate operation_mode if provided
        if "operation_mode" in data and data["operation_mode"] is not None:
            if data["operation_mode"] not in VALID_OPERATION_MODES:
                raise AccountValidationError(
                    message=f"invalid operation_mode: {data['operation_mode']}",
                    details={"valid_modes": list(VALID_OPERATION_MODES)}
                )

        account = await self.get_account(account_id, db)
        for key, value in data.items():
            if value is not None and hasattr(account, key):
                setattr(account, key, value)

        if automation_plan_payload:
            await automation_plan_service.upsert_plan(account, automation_plan_payload, db)
        elif has_legacy_plan_updates:
            await automation_plan_service.sync_plan_from_account_legacy(account, db)

        db.add(account)
        await db.flush()
        logger.info("account_updated", account_id=account_id, fields=list(data.keys()))
        return account

    async def enable_account(self, account_id: str, db: AsyncSession) -> AccountModel:
        """Enable an account."""
        account = await self.get_account(account_id, db)
        account.is_active = True
        db.add(account)
        await db.flush()
        logger.info("account_enabled", account_id=account_id)
        return account

    async def disable_account(self, account_id: str, db: AsyncSession) -> AccountModel:
        """Disable an account."""
        account = await self.get_account(account_id, db)
        account.is_active = False
        db.add(account)
        await db.flush()
        logger.info("account_disabled", account_id=account_id)
        return account

    async def list_accounts(
        self, db: AsyncSession, page: int = 1, page_size: int = 20
    ) -> tuple[list[AccountModel], int]:
        """List accounts with pagination."""
        stmt = select(AccountModel).order_by(desc(AccountModel.created_at))
        count_stmt = select(AccountModel)

        count_result = await db.execute(
            select(sa_func.count()).select_from(count_stmt.subquery())
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())
        return accounts, total

    # -------------------------------------------------------------------------
    # Run
    # -------------------------------------------------------------------------

    async def run_account(
        self, account_id: str, db: AsyncSession, allow_auto: bool = False
    ) -> tuple[AccountModel, TaskModel]:
        """
        Manually trigger a task for the account.
        Creates a task from account positioning and starts execution.
        Updates last_run_at / next_run_at / last_run_status.

        Args:
            account_id: The account to run
            db: Database session
            allow_auto: True when the scheduler is auto-triggering the account

        Raises:
            AccountNotFoundError: Account does not exist
            AccountInactiveError: Account is disabled
            AccountValidationError: Positioning is empty or mode not allowed
            TaskAlreadyExistsError: Account already has running/pending task
        """
        account = await self.get_account(account_id, db)

        # Check account exists
        if account is None:
            raise AccountNotFoundError(account_id)

        # Check account is active
        if not account.is_active:
            raise AccountInactiveError(account_id)

        # Check positioning
        if not account.positioning or not account.positioning.strip():
            raise AccountValidationError(
                message="positioning is required to run account",
                details={"account_id": account_id}
            )

        plan_summary = await automation_plan_service.get_effective_summary(account, db)

        # Manual-mode accounts can still be run from the account workspace.
        # Only the scheduler path should reject them.
        if allow_auto and not automation_plan_service.should_auto_run(plan_summary):
            raise AccountValidationError(
                message="account automation plan is not eligible for auto scheduling",
                details={
                    "account_id": account_id,
                    "plan_type": plan_summary.get("plan_type"),
                    "run_strategy": plan_summary.get("run_strategy"),
                    "is_enabled": plan_summary.get("is_enabled"),
                },
            )

        # Check for existing running/pending tasks
        existing_task = await self._get_running_task(account_id, db)
        if existing_task:
            raise TaskAlreadyExistsError(account_id, existing_task.id)

        ops_context = await account_harness_service.evaluate_account_run(
            account,
            db,
            allow_auto=allow_auto,
        )
        run_strategy = ops_context.get("run_strategy", {})
        if not run_strategy.get("allow_run", True):
            raise AccountValidationError(
                message="account operations harness blocked this run",
                details={
                    "account_id": account_id,
                    "trigger_source": "scheduler" if allow_auto else "manual",
                    "effective_mode": run_strategy.get("effective_mode"),
                    "ops_notes": ops_context.get("ops_notes", []),
                },
            )

        # Create task with account positioning
        try:
            task = TaskModel(
                id=generate_task_id(),
                account_id=account_id,
                workflow_id="default_pipeline",
                status="pending",
                input_data={
                    "positioning": account.positioning,
                    "ops_context": ops_context,
                },
            )
            db.add(task)
            await db.flush()
        except Exception as e:
            logger.error("task_create_failed", account_id=account_id, error=str(e))
            raise TaskCreateError(account_id, str(e))

        await automation_plan_service.mark_run_started(account, db)
        logger.info(
            "account_run_triggered",
            account_id=account_id,
            task_id=task.id,
            operation_mode=plan_summary.get("plan_type", account.operation_mode),
            allow_run=run_strategy.get("allow_run", True),
            effective_mode=run_strategy.get("effective_mode"),
            allow_auto_publish=run_strategy.get("allow_auto_publish"),
        )

        return account, task

    async def update_account_run_status(
        self,
        account_id: str,
        db: AsyncSession,
        status: str,
        error_message: str | None = None
    ) -> None:
        """
        Update account run status after task completion.

        Args:
            account_id: The account to update
            db: Database session
            status: "success", "failed", or "cancelled"
            error_message: Error message if failed
        """
        account = await self.get_account(account_id, db)
        account.last_run_status = status
        if error_message:
            # Truncate long error messages
            account.last_error_message = error_message[:500] if len(error_message) > 500 else error_message
        await automation_plan_service.mark_run_status(account, status, db)
        db.add(account)
        await db.flush()
        logger.info(
            "account_run_status_updated",
            account_id=account_id,
            status=status,
            has_error=bool(error_message)
        )

    async def _get_running_task(self, account_id: str, db: AsyncSession) -> TaskModel | None:
        """Check if account has any running or pending task."""
        stmt = select(TaskModel).where(
            TaskModel.account_id == account_id,
            TaskModel.status.in_(["pending", "running"])
        ).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Scheduler helpers
    # -------------------------------------------------------------------------

    async def get_due_accounts(self, db: AsyncSession) -> list[AccountModel]:
        """
        Find all accounts eligible for automatic scheduling.
        Criteria:
        - is_active == True
        - auto_run_enabled == True
        - operation_mode in ("semi_auto", "full_auto")
        - next_run_at is not None and <= now
        - NO existing pending/running task for this account

        Returns accounts ordered by next_run_at.
        """
        from sqlalchemy import select

        now = datetime.now(timezone.utc)

        # Subquery: check if account has pending/running task
        task_check = (
            select(TaskModel.id)
            .where(
                TaskModel.account_id == AccountModel.id,
                TaskModel.status.in_(["pending", "running"])
            )
            .limit(1)
            .exists()
        )

        stmt = (
            select(AccountModel)
            .where(
                AccountModel.is_active == True,
                ~task_check,  # No pending/running task exists
            )
            .order_by(AccountModel.next_run_at)
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())
        due_accounts: list[tuple[datetime, AccountModel]] = []

        for account in candidates:
            summary = await automation_plan_service.get_effective_summary(account, db)
            if automation_plan_service.should_auto_run(summary, now=now):
                next_run_at = summary.get("next_run_at") or now
                if isinstance(next_run_at, str):
                    next_run_at = datetime.fromisoformat(next_run_at)
                if next_run_at.tzinfo is None:
                    next_run_at = next_run_at.replace(tzinfo=timezone.utc)
                due_accounts.append((next_run_at, account))

        due_accounts.sort(key=lambda item: item[0])
        return [account for _, account in due_accounts]

    async def refresh_next_run(self, account_id: str, db: AsyncSession) -> None:
        """Recalculate and persist next_run_at after a task completes."""
        account = await self.get_account(account_id, db)
        await automation_plan_service.refresh_next_run(account, db)
        logger.info("account_next_run_refreshed", account_id=account_id, next_run=account.next_run_at)

    def _compute_next_run(self, account: AccountModel) -> datetime | None:
        """
        Compute next_run_at based on posting_frequency and posting_time.
        Returns None if no frequency is set.
        """
        if not account.posting_frequency:
            return None

        interval_days = FREQUENCY_INTERVALS.get(account.posting_frequency, 7)
        now = datetime.now(timezone.utc)
        next_date = now + timedelta(days=interval_days)

        # If posting_time is set (e.g. "08:00"), align to that time of day
        if account.posting_time:
            try:
                hour, minute = map(int, account.posting_time.split(":"))
                next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except (ValueError, AttributeError):
                pass

        return next_date

    # -------------------------------------------------------------------------
    # Account context (for agent injection)
    # -------------------------------------------------------------------------

    async def get_account_context(self, account_id: str | None, db: AsyncSession) -> dict | None:
        """
        Build a lightweight context dict from an account.
        Returns None for temporary tasks (account_id is None).
        """
        if not account_id:
            return None

        account = await self.get_account(account_id, db)
        summary = await automation_plan_service.get_effective_summary(account, db)
        source_rows = await db.execute(
            select(
                ReferenceSourceModel.id,
                ReferenceSourceModel.name,
                ReferenceSourceModel.source_type,
                ReferenceSourceModel.sync_status,
                ReferenceSourceModel.article_count,
                ReferenceSourceModel.notes,
                ReferenceSourceModel.source_value,
                ReferenceSourceModel.metadata_json,
            )
            .where(
                ReferenceSourceModel.account_id == account_id,
                ReferenceSourceModel.is_enabled.is_(True),
            )
            .order_by(desc(ReferenceSourceModel.updated_at), desc(ReferenceSourceModel.id))
            .limit(5)
        )
        serializable_summary = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in summary.items()
        }
        reference_sources = []
        for row in source_rows.all():
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            preview = (
                metadata.get("preview")
                or (row.source_value if row.source_type == "pasted_article" else None)
            )
            reference_sources.append(
                {
                    "id": str(row.id),
                    "name": row.name,
                    "source_type": row.source_type,
                    "sync_status": row.sync_status,
                    "article_count": int(row.article_count or 0),
                    "notes": row.notes,
                    "resolved_title": metadata.get("resolved_title"),
                    "preview": article_assembler_service._clip_text(preview, 280),
                    "metadata_json": metadata,
                }
            )

        reference_digest = reference_digest_service.build_account_reference_digest(
            reference_sources,
            limit=3,
        )
        return {
            "account_id": account.id,
            "account_name": account.name,
            "positioning": account.positioning,
            "audience": account.audience,
            "tone_style": account.tone_style,
            "content_strategy": account.content_strategy,
            "reference_accounts": account.reference_accounts,
            "reference_sources": reference_sources,
            "reference_source_briefs": reference_digest.get("source_digests", []),
            "reference_digest": reference_digest,
            "reference_style_guide": {
                "preferred_source_names": reference_digest.get("preferred_source_names", []),
                "style_takeaways": reference_digest.get("style_takeaways", []),
                "structure_takeaways": reference_digest.get("structure_takeaways", []),
                "usage_rules": reference_digest.get("usage_rules", []),
            },
            "operation_mode": summary.get("plan_type", account.operation_mode),
            "automation_plan_summary": serializable_summary,
        }


account_service = AccountService()
