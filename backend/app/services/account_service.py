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
from app.models.tables import AccountModel, TaskModel

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
        )
        db.add(account)
        await db.flush()
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

        # Fetch recent tasks
        stmt = (
            select(TaskModel)
            .where(TaskModel.account_id == account_id)
            .order_by(desc(TaskModel.created_at))
            .limit(recent_limit)
        )
        result = await db.execute(stmt)
        recent_tasks = list(result.scalars().all())

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
            "last_run_at": account.last_run_at.isoformat() if account.last_run_at else None,
            "next_run_at": account.next_run_at.isoformat() if account.next_run_at else None,
            "last_run_status": account.last_run_status,
            "last_error_message": account.last_error_message,
            "created_at": account.created_at.isoformat() if account.created_at else None,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            "recent_tasks": [
                {
                    "task_id": t.id,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "elapsed_seconds": t.elapsed_seconds,
                }
                for t in recent_tasks
            ],
        }

    async def update_account(
        self, account_id: str, data: dict, db: AsyncSession
    ) -> AccountModel:
        """Update account fields (only provided fields are applied)."""
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
            allow_auto: If False, raises error for manual mode accounts (for scheduler use)

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

        # Check operation mode for auto scheduler
        if not allow_auto and account.operation_mode == "manual":
            raise AccountValidationError(
                message="manual mode account cannot be auto-scheduled",
                details={"account_id": account_id, "operation_mode": account.operation_mode}
            )

        # Check for existing running/pending tasks
        existing_task = await self._get_running_task(account_id, db)
        if existing_task:
            raise TaskAlreadyExistsError(account_id, existing_task.id)

        # Create task with account positioning
        try:
            task = TaskModel(
                id=generate_task_id(),
                account_id=account_id,
                workflow_id="default_pipeline",
                status="pending",
                input_data={"positioning": account.positioning},
            )
            db.add(task)
            await db.flush()
        except Exception as e:
            logger.error("task_create_failed", account_id=account_id, error=str(e))
            raise TaskCreateError(account_id, str(e))

        # Update timestamps and status
        now = datetime.now(timezone.utc)
        account.last_run_at = now
        account.next_run_at = self._compute_next_run(account)
        account.last_run_status = "running"
        account.last_error_message = None  # Clear previous error
        db.add(account)

        await db.flush()
        logger.info(
            "account_run_triggered",
            account_id=account_id,
            task_id=task.id,
            operation_mode=account.operation_mode
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
        from sqlalchemy import not_, exists
        from sqlalchemy.dialects.sqlite import select as sqlite_select

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
                AccountModel.auto_run_enabled == True,
                AccountModel.operation_mode.in_(["semi_auto", "full_auto"]),
                AccountModel.next_run_at != None,
                AccountModel.next_run_at <= now,
                ~task_check,  # No pending/running task exists
            )
            .order_by(AccountModel.next_run_at)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def refresh_next_run(self, account_id: str, db: AsyncSession) -> None:
        """Recalculate and persist next_run_at after a task completes."""
        account = await self.get_account(account_id, db)
        account.next_run_at = self._compute_next_run(account)
        db.add(account)
        await db.flush()
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
        return {
            "account_id": account.id,
            "account_name": account.name,
            "positioning": account.positioning,
            "audience": account.audience,
            "tone_style": account.tone_style,
            "content_strategy": account.content_strategy,
            "reference_accounts": account.reference_accounts,
            "operation_mode": account.operation_mode,
        }


account_service = AccountService()
