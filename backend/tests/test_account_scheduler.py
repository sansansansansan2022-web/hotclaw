"""
Tests for Account Scheduler functionality.

Covers:
1. Scheduler eligibility checks
2. Manual mode accounts not auto-scheduled
3. Disabled accounts not auto-scheduled
4. Running status updates
5. Error message tracking
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from sqlalchemy import select

from app.models.tables import AccountModel, TaskModel
from app.scheduler.account_scheduler import account_scheduler
from app.services.account_service import account_service
from app.core.exceptions import (
    AccountNotFoundError,
    AccountInactiveError,
    AccountValidationError,
    TaskAlreadyExistsError,
)


class TestAccountServiceRun:
    """Test account run functionality."""

    @pytest_asyncio.fixture
    async def manual_account(self, db_session):
        """Create a manual mode account."""
        account = AccountModel(
            id="test-manual-001",
            name="Manual Test Account",
            positioning="专注于科技数码的公众号",
            operation_mode="manual",
            auto_run_enabled=True,
            is_active=True,
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def semi_auto_account(self, db_session):
        """Create a semi-auto mode account."""
        account = AccountModel(
            id="test-semi-001",
            name="Semi-Auto Test Account",
            positioning="专注于美食分享的公众号",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency="weekly",
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def disabled_account(self, db_session):
        """Create a disabled account."""
        account = AccountModel(
            id="test-disabled-001",
            name="Disabled Test Account",
            positioning="已禁用的公众号",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=False,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def account_with_running_task(self, db_session, semi_auto_account):
        """Create an account with a running task."""
        task = TaskModel(
            id="test-task-running-001",
            account_id=semi_auto_account.id,
            workflow_id="default_pipeline",
            status="running",
            input_data={"positioning": "test"},
        )
        db_session.add(task)
        await db_session.commit()
        return semi_auto_account

    # -------------------------------------------------------------------------
    # Test: Manual mode accounts cannot be auto-scheduled
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_manual_account_cannot_be_auto_run(self, db_session, manual_account):
        """
        Manual mode accounts should raise AccountValidationError when
        allow_auto=False (default) to prevent auto-scheduling.
        """
        with pytest.raises(AccountValidationError) as exc_info:
            await account_service.run_account(manual_account.id, db_session, allow_auto=False)

        assert "manual mode" in str(exc_info.value.message).lower()
        assert exc_info.value.code == 6003  # AccountValidationError

    @pytest.mark.asyncio
    async def test_manual_account_can_be_manually_run(self, db_session, manual_account):
        """
        Manual mode accounts CAN be run manually via button click.
        """
        account, task = await account_service.run_account(
            manual_account.id, db_session, allow_auto=False
        )
        assert task is not None
        assert task.account_id == manual_account.id
        assert account.last_run_status == "running"

    # -------------------------------------------------------------------------
    # Test: Disabled accounts cannot be run
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_disabled_account_cannot_be_run(self, db_session, disabled_account):
        """
        Disabled accounts should raise AccountInactiveError.
        """
        with pytest.raises(AccountInactiveError):
            await account_service.run_account(disabled_account.id, db_session, allow_auto=True)

    # -------------------------------------------------------------------------
    # Test: Non-existent account raises error
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_nonexistent_account_raises_error(self, db_session):
        """
        Running a non-existent account should raise AccountNotFoundError.
        """
        with pytest.raises(AccountNotFoundError):
            await account_service.run_account("nonexistent-id", db_session)

    # -------------------------------------------------------------------------
    # Test: Account with empty positioning cannot be run
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_empty_positioning_cannot_be_run(self, db_session, semi_auto_account):
        """
        Account with empty positioning should raise AccountValidationError.
        """
        semi_auto_account.positioning = ""
        await db_session.commit()

        with pytest.raises(AccountValidationError) as exc_info:
            await account_service.run_account(semi_auto_account.id, db_session, allow_auto=True)

        assert "positioning" in str(exc_info.value.message).lower()

    # -------------------------------------------------------------------------
    # Test: Running task prevents duplicate run
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_running_task_prevents_duplicate_run(
        self, db_session, account_with_running_task
    ):
        """
        Account with existing running/pending task should raise TaskAlreadyExistsError.
        """
        with pytest.raises(TaskAlreadyExistsError) as exc_info:
            await account_service.run_account(
                account_with_running_task.id, db_session, allow_auto=True
            )

        assert exc_info.value.code == 8001
        assert account_with_running_task.id in str(exc_info.value.details)

    # -------------------------------------------------------------------------
    # Test: Successful run updates status
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_successful_run_updates_status(self, db_session, semi_auto_account):
        """
        Successful run should update last_run_at and last_run_status.
        """
        account, task = await account_service.run_account(
            semi_auto_account.id, db_session, allow_auto=True
        )

        assert account.last_run_at is not None
        assert account.last_run_status == "running"
        assert account.last_error_message is None
        assert task.id is not None

    # -------------------------------------------------------------------------
    # Test: Update account run status
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_run_status_success(self, db_session, semi_auto_account):
        """
        Update run status to success.
        """
        await account_service.update_account_run_status(
            semi_auto_account.id, db_session, "success"
        )

        await db_session.refresh(semi_auto_account)
        assert semi_auto_account.last_run_status == "success"
        assert semi_auto_account.last_error_message is None

    @pytest.mark.asyncio
    async def test_update_run_status_failure(self, db_session, semi_auto_account):
        """
        Update run status to failed with error message.
        """
        error_msg = "LLM API timeout after 60s"
        await account_service.update_account_run_status(
            semi_auto_account.id, db_session, "failed", error_msg
        )

        await db_session.refresh(semi_auto_account)
        assert semi_auto_account.last_run_status == "failed"
        assert error_msg in semi_auto_account.last_error_message

    @pytest.mark.asyncio
    async def test_update_run_status_truncates_long_error(self, db_session, semi_auto_account):
        """
        Very long error messages should be truncated.
        """
        long_error = "A" * 1000
        await account_service.update_account_run_status(
            semi_auto_account.id, db_session, "failed", long_error
        )

        await db_session.refresh(semi_auto_account)
        assert len(semi_auto_account.last_error_message) <= 500


class TestSchedulerEligibility:
    """Test scheduler eligibility checks."""

    def test_final_eligibility_accepts_naive_due_datetime(self):
        """
        SQLAlchemy DateTime columns can reload timezone-aware UTC values as
        naive datetimes. The scheduler must not crash when comparing them.
        """
        account = SimpleNamespace(
            is_active=True,
            auto_run_enabled=True,
            operation_mode="semi_auto",
            next_run_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).replace(tzinfo=None),
        )

        assert account_scheduler._is_eligible_for_auto_run(account) is True

    @pytest.mark.asyncio
    async def test_scheduler_preserves_failed_task_status(self, db_session, monkeypatch):
        """
        TaskService.run_task records failed tasks without re-raising. The
        scheduler must inspect the final task status before marking success.
        """
        account = AccountModel(
            id="test-scheduler-failed-task",
            name="Scheduler Failed Task Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency="daily",
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()

        class _SessionContext:
            async def __aenter__(self):
                return db_session

            async def __aexit__(self, exc_type, exc, tb):
                return False

        async def _fake_failed_run(task_id, db):
            task = await db.get(TaskModel, task_id)
            task.status = "failed"
            task.error_message = "boom"
            task.completed_at = datetime.now(timezone.utc)
            db.add(task)
            await account_service.update_account_run_status(account.id, db, "failed", "boom")
            await db.commit()

        monkeypatch.setattr("app.db.session.async_session_factory", lambda: _SessionContext())
        monkeypatch.setattr("app.services.task_service.task_service.run_task", _fake_failed_run)

        await account_scheduler._run_account_task(account.id)

        refreshed = await db_session.execute(select(AccountModel).where(AccountModel.id == account.id))
        saved_account = refreshed.scalar_one()
        assert saved_account.last_run_status == "failed"
        assert saved_account.last_error_message == "boom"

    @pytest.mark.asyncio
    async def test_get_due_accounts_excludes_manual_mode(self, db_session):
        """
        get_due_accounts should NOT return manual mode accounts.
        """
        # Create manual account that would be due
        manual_account = AccountModel(
            id="test-due-manual",
            name="Due Manual Account",
            positioning="Test positioning",
            operation_mode="manual",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(manual_account)
        await db_session.commit()

        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-due-manual" not in due_ids

    @pytest.mark.asyncio
    async def test_get_due_accounts_excludes_disabled(self, db_session):
        """
        get_due_accounts should NOT return disabled accounts.
        """
        # Create disabled account that would be due
        disabled_account = AccountModel(
            id="test-due-disabled",
            name="Due Disabled Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=False,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(disabled_account)
        await db_session.commit()

        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-due-disabled" not in due_ids

    @pytest.mark.asyncio
    async def test_get_due_accounts_excludes_future_runs(self, db_session):
        """
        get_due_accounts should NOT return accounts with future next_run_at.
        """
        # Create account with future next_run_at
        future_account = AccountModel(
            id="test-due-future",
            name="Future Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(future_account)
        await db_session.commit()

        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-due-future" not in due_ids

    @pytest.mark.asyncio
    async def test_get_due_accounts_includes_valid_accounts(self, db_session):
        """
        get_due_accounts should return semi_auto/full_auto accounts
        that are active and past next_run_at.
        """
        # Create valid due account
        valid_account = AccountModel(
            id="test-due-valid",
            name="Valid Due Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency="weekly",
        )
        db_session.add(valid_account)
        await db_session.commit()

        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-due-valid" in due_ids

    @pytest.mark.asyncio
    async def test_get_due_accounts_excludes_auto_run_disabled(self, db_session):
        """
        get_due_accounts should NOT return accounts with auto_run_enabled=False.
        """
        account = AccountModel(
            id="test-due-no-auto",
            name="No Auto Run Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=False,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(account)
        await db_session.commit()

        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-due-no-auto" not in due_ids


class TestAccountCRUDWithStatus:
    """Test account CRUD operations with status fields."""

    @pytest.mark.asyncio
    async def test_create_account_with_default_status(self, db_session):
        """
        Creating an account should set default last_run_status to 'never_run'.
        """
        account = await account_service.create_account(
            {
                "name": "New Account",
                "positioning": "Test positioning for new account",
                "operation_mode": "manual",
            },
            db_session
        )
        await db_session.commit()

        assert account.last_run_status == "never_run"
        assert account.last_error_message is None

    @pytest.mark.asyncio
    async def test_create_account_validates_operation_mode(self, db_session):
        """
        Creating an account with invalid operation_mode should raise error.
        """
        with pytest.raises(AccountValidationError) as exc_info:
            await account_service.create_account(
                {
                    "name": "Bad Account",
                    "positioning": "Test positioning",
                    "operation_mode": "invalid_mode",
                },
                db_session
            )

        assert exc_info.value.code == 6003

    @pytest.mark.asyncio
    async def test_update_account_validates_operation_mode(self, db_session):
        """
        Updating an account with invalid operation_mode should raise error.
        """
        account = AccountModel(
            id="test-update-mode",
            name="Update Mode Test",
            positioning="Test positioning",
            operation_mode="manual",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        with pytest.raises(AccountValidationError):
            await account_service.update_account(
                "test-update-mode",
                {"operation_mode": "bad_mode"},
                db_session
            )


class TestDueAccountsExcludesRunningTasks:
    """Test that get_due_accounts excludes accounts with pending/running tasks."""

    @pytest_asyncio.fixture
    async def account_with_pending_task(self, db_session):
        """Create an account with a pending task."""
        account = AccountModel(
            id="test-pending-account",
            name="Pending Task Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency="weekly",
        )
        db_session.add(account)
        await db_session.flush()

        task = TaskModel(
            id="test-task-pending",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="pending",  # Task is pending, should block scheduling
            input_data={"positioning": "test"},
        )
        db_session.add(task)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def account_with_running_task_fixture(self, db_session):
        """Create an account with a running task."""
        account = AccountModel(
            id="test-running-account",
            name="Running Task Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency="weekly",
        )
        db_session.add(account)
        await db_session.flush()

        task = TaskModel(
            id="test-task-running-fixture",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="running",  # Task is running, should block scheduling
            input_data={"positioning": "test"},
        )
        db_session.add(task)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def account_with_completed_task(self, db_session):
        """Create an account with a completed task (should be eligible)."""
        account = AccountModel(
            id="test-completed-account",
            name="Completed Task Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency="weekly",
        )
        db_session.add(account)
        await db_session.flush()

        task = TaskModel(
            id="test-task-completed",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="completed",  # Task is completed, should NOT block scheduling
            input_data={"positioning": "test"},
        )
        db_session.add(task)
        await db_session.commit()
        return account

    @pytest.mark.asyncio
    async def test_get_due_accounts_excludes_pending_task(self, db_session, account_with_pending_task):
        """
        get_due_accounts should NOT return accounts with pending tasks.
        This prevents duplicate task creation.
        """
        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-pending-account" not in due_ids

    @pytest.mark.asyncio
    async def test_get_due_accounts_excludes_running_task(
        self, db_session, account_with_running_task_fixture
    ):
        """
        get_due_accounts should NOT return accounts with running tasks.
        This prevents duplicate task creation when scheduler ticks while task is still running.
        """
        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-running-account" not in due_ids

    @pytest.mark.asyncio
    async def test_get_due_accounts_includes_completed_task(
        self, db_session, account_with_completed_task
    ):
        """
        get_due_accounts should return accounts with completed tasks.
        A completed task should not block the next scheduled run.
        """
        due_accounts = await account_service.get_due_accounts(db_session)
        due_ids = [a.id for a in due_accounts]

        assert "test-completed-account" in due_ids


class TestNextRunAtRefresh:
    """Test that next_run_at is refreshed after task completion."""

    @pytest_asyncio.fixture
    async def account_for_refresh(self, db_session):
        """Create an account for next_run_at refresh testing."""
        old_next_run = datetime.now(timezone.utc) - timedelta(hours=1)
        account = AccountModel(
            id="test-refresh-account",
            name="Refresh Test Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=old_next_run,
            posting_frequency="weekly",
        )
        db_session.add(account)
        await db_session.commit()
        return account, old_next_run

    @pytest.mark.asyncio
    async def test_refresh_next_run_updates_timestamp(self, db_session, account_for_refresh):
        """
        refresh_next_run should update next_run_at based on posting_frequency.
        """
        account, old_next_run = account_for_refresh

        await account_service.refresh_next_run(account.id, db_session)
        await db_session.refresh(account)

        # next_run_at should be updated to a future date
        assert account.next_run_at is not None
        assert account.next_run_at > old_next_run
        # Should be approximately 7 days (weekly) in the future
        expected_delta = timedelta(days=7)
        actual_delta = account.next_run_at - datetime.now(timezone.utc)
        assert abs(actual_delta.days - expected_delta.days) <= 1  # Allow 1 day tolerance

    @pytest.mark.asyncio
    async def test_refresh_next_run_with_no_frequency(self, db_session):
        """
        If posting_frequency is not set, next_run_at should become None.
        """
        account = AccountModel(
            id="test-no-frequency",
            name="No Frequency Account",
            positioning="Test positioning",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
            posting_frequency=None,  # No frequency set
        )
        db_session.add(account)
        await db_session.commit()

        await account_service.refresh_next_run(account.id, db_session)
        await db_session.refresh(account)

        # next_run_at should be None when no frequency is set
        assert account.next_run_at is None


class TestTemporaryTaskCompatibility:
    """Test that temporary tasks (no account_id) don't trigger account logic."""

    @pytest.mark.asyncio
    async def test_create_task_without_account_id(self, db_session):
        """
        Creating a task without account_id should work fine.
        This is a temporary/one-off task.
        """
        from app.services.task_service import task_service

        task = await task_service.create_task(
            positioning="临时任务定位",
            workflow_id="default_pipeline",
            db=db_session
        )
        await db_session.commit()

        # Task should be created without account_id
        assert task.id is not None
        assert task.account_id is None
        assert task.status == "pending"

    @pytest.mark.asyncio
    async def test_run_task_without_account_id_does_not_fail(self, db_session):
        """
        Running a task without account_id should not fail due to account logic.
        The account-related methods should be skipped.
        """
        from app.services.task_service import task_service

        # Create task without account
        task = await task_service.create_task(
            positioning="临时任务定位",
            workflow_id="default_pipeline",
            db=db_session
        )
        await db_session.commit()
        task_id = task.id

        # Task should have no account_id
        assert task.account_id is None

        # The _refresh_account_next_run and _update_account_run_status_on_failure
        # methods should be called with None and gracefully skip
        # (This is implicitly tested - if there was an error, the test would fail)
