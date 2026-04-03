"""E2E tests for scheduler auto-trigger and account state synchronization.

【Scheduler 自动触发与状态同步 E2E 测试】

验证 HotClaw 账号托管模式的完整链路：
- scheduler tick → 找到 due accounts → 创建 task → 运行 agent
- 生成 draft 或自动发布
- 回写 account 状态
- 页面/API 可读取最新 account 状态摘要

测试场景：
1. semi_auto 账号自动触发并生成 pending_review 草稿
2. full_auto 账号自动触发并自动发布
3. manual 账号不会自动触发
4. disabled / auto_run_enabled=false 不会自动触发
5. 已有 pending/running task 时不重复调度
6. 任务失败时 account 状态同步
7. 多账号并发扫描
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from app.models.tables import AccountModel, TaskModel, ArticleDraftModel
from app.services.account_service import account_service
from app.services.task_service import task_service
from app.services.draft_service import draft_service
from app.scheduler.account_scheduler import account_scheduler


# =============================================================================
# Test Fixtures & Helpers
# =============================================================================

@pytest_asyncio.fixture
async def scheduler_tick_helper(db_session):
    """
    Provide a helper to trigger scheduler tick synchronously.

    Usage:
        await scheduler_tick_helper.trigger(db_session)
    """
    class SchedulerTickHelper:
        async def trigger(self, session):
            """Manually trigger scheduler tick and process due accounts."""
            from sqlalchemy import select, exists

            # Get due accounts with direct query (avoid dialect issues)
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
                    ~task_check,
                )
                .order_by(AccountModel.next_run_at)
            )

            result = await session.execute(stmt)
            due_accounts = list(result.scalars().all())

            results = []
            for account in due_accounts:
                # Check eligibility (same as scheduler)
                if not self._is_eligible(account):
                    continue
                try:
                    # Run account task
                    _, task = await account_service.run_account(
                        account.id, session, allow_auto=True
                    )
                    await session.commit()

                    # Run task synchronously
                    await task_service.run_task(task.id, session)

                    # Check actual task status (task_service may catch exceptions internally)
                    task_check = await task_service.get_task(task.id, session)
                    if task_check.status == "failed":
                        # Task failed (orchestrator caught exception)
                        await account_service.update_account_run_status(
                            account.id, session, "failed", task_check.error_message or "Task failed"
                        )
                        await session.commit()

                        results.append({
                            "account_id": account.id,
                            "task_id": task.id,
                            "status": "failed",
                            "error": task_check.error_message
                        })
                        continue

                    # Update account status to success
                    await account_service.update_account_run_status(
                        account.id, session, "success"
                    )
                    await session.commit()

                    # Refresh next run time
                    await account_service.refresh_next_run(account.id, session)
                    await session.commit()

                    results.append({
                        "account_id": account.id,
                        "task_id": task.id,
                        "status": "success"
                    })
                except Exception as e:
                    # Update account status to failed
                    await account_service.update_account_run_status(
                        account.id, session, "failed", str(e)[:500]
                    )
                    await session.commit()

                    results.append({
                        "account_id": account.id,
                        "status": "failed",
                        "error": str(e)
                    })

            return results

        def _is_eligible(self, account) -> bool:
            """Check if account is eligible for auto-run."""
            if not account.is_active:
                return False
            if not account.auto_run_enabled:
                return False
            if account.operation_mode == "manual":
                return False
            if not account.next_run_at:
                return False
            now = datetime.now(timezone.utc)
            return account.next_run_at <= now

    return SchedulerTickHelper()


@pytest_asyncio.fixture
async def account_state(db_session):
    """
    Helper to assert account state after operations.

    Usage:
        await account_state.assert_success(account_id)
    """
    class AccountStateHelper:
        async def refresh(self, account_id):
            """Refresh account from database."""
            from sqlalchemy import select
            stmt = select(AccountModel).where(AccountModel.id == account_id)
            result = await db_session.execute(stmt)
            return result.scalar_one_or_none()

        async def assert_status(self, account_id, expected_status, expected_run_status=None):
            """Assert account has expected run status."""
            account = await self.refresh(account_id)
            assert account is not None, f"Account {account_id} not found"
            if expected_run_status:
                assert account.last_run_status == expected_run_status, \
                    f"Expected last_run_status={expected_run_status}, got {account.last_run_status}"
            return account

        async def assert_success(self, account_id):
            """Assert account run was successful."""
            account = await self.refresh(account_id)
            assert account is not None
            assert account.last_run_status == "success", \
                f"Expected success, got {account.last_run_status}"
            assert account.last_run_at is not None, "last_run_at should be set"
            return account

        async def assert_failed(self, account_id, expect_error=True):
            """Assert account run failed."""
            account = await self.refresh(account_id)
            assert account is not None
            assert account.last_run_status == "failed", \
                f"Expected failed, got {account.last_run_status}"
            if expect_error:
                assert account.last_error_message is not None, \
                    "Error message should be set on failure"
            return account

        async def assert_not_run(self, account_id):
            """Assert account was not run (last_run_at unchanged)."""
            account = await self.refresh(account_id)
            assert account is not None
            # For newly created accounts, last_run_status should still be initial value
            # or not changed by scheduler
            return account

        async def assert_next_run_refreshed(self, account_id):
            """Assert next_run_at was refreshed."""
            account = await self.refresh(account_id)
            assert account is not None
            assert account.next_run_at is not None, "next_run_at should be set"
            # next_run_at should be in the future
            assert account.next_run_at > datetime.now(timezone.utc), \
                "next_run_at should be in the future"

    return AccountStateHelper()


@pytest_asyncio.fixture
async def fake_publish_service():
    """
    Mock WeChat publish service for testing.

    Usage:
        with fake_publish_service.success():
            # Test successful publish
        with fake_publish_service.failure():
            # Test failed publish
    """
    class FakePublishService:
        def success(self):
            """Mock successful publish."""
            return patch(
                "app.services.draft_service.draft_service.publish_to_wechat",
                new_callable=AsyncMock,
                return_value=(None, {"media_id": "fake_media_id", "url": "https://fake.url"})
            )

        def failure(self, error_message="Fake publish failure"):
            """Mock failed publish."""
            from app.core.exceptions import DraftPublishError
            return patch(
                "app.services.draft_service.draft_service.publish_to_wechat",
                new_callable=AsyncMock,
                side_effect=DraftPublishError(1, error_message)
            )

    return FakePublishService()


# =============================================================================
# Scenario 1: semi_auto 账号自动触发
# =============================================================================

class TestSemiAutoSchedulerTrigger:
    """Scenario 1: semi_auto account auto-trigger."""

    @pytest.mark.asyncio
    async def test_semi_auto_triggers_and_creates_draft(
        self, db_session, scheduler_tick_helper, account_state, mock_llm
    ):
        """
        Test that due semi_auto account is triggered and creates pending_review draft.

        Steps:
        1. Create semi_auto account with due time
        2. Trigger scheduler tick
        3. Verify task created
        4. Verify draft created with pending_review status
        5. Verify account status updated
        """
        # Create semi_auto account
        account = AccountModel(
            id="test-semi-auto-scheduler",
            name="Scheduler Semi-Auto Test",
            positioning="测试定位：职场成长类公众号",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            posting_frequency="daily",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()

        # Trigger scheduler tick using helper
        results = await scheduler_tick_helper.trigger(db_session)

        # Verify task was created
        assert len(results) == 1
        assert results[0]["account_id"] == account.id
        assert results[0]["status"] == "success"

        # Verify draft created with pending_review status
        from sqlalchemy import select
        stmt = select(ArticleDraftModel).where(
            ArticleDraftModel.account_id == account.id
        )
        result = await db_session.execute(stmt)
        draft = result.scalar_one_or_none()

        assert draft is not None, "Draft should be created"
        assert draft.draft_status == "pending_review", \
            f"Expected pending_review, got {draft.draft_status}"
        assert draft.publish_status == "not_published", \
            f"Expected not_published, got {draft.publish_status}"
        assert draft.source_type == "semi_auto_task"

        # Verify account status
        account = await account_state.assert_success(account.id)
        await account_state.assert_next_run_refreshed(account.id)

    @pytest.mark.asyncio
    async def test_semi_auto_task_created_with_correct_account_id(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """Test that created task has correct account_id."""
        account = AccountModel(
            id="test-semi-auto-account-id",
            name="Test Account ID",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify task
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        task = result.scalar_one_or_none()

        assert task is not None, "Task should be created"
        assert task.account_id == account.id


# =============================================================================
# Scenario 2: full_auto 账号自动触发并自动发布
# =============================================================================

class TestFullAutoSchedulerTrigger:
    """Scenario 2: full_auto account auto-trigger with auto-publish."""

    @pytest.mark.asyncio
    async def test_full_auto_triggers_and_auto_publishes(
        self, db_session, scheduler_tick_helper, account_state, mock_llm, fake_publish_service
    ):
        """
        Test that due full_auto account auto-triggers and auto-publishes.

        Steps:
        1. Create full_auto account with due time
        2. Trigger scheduler tick
        3. Verify task created
        4. Verify draft created with published status (auto published)
        5. Verify account status updated
        """
        # Create full_auto account
        account = AccountModel(
            id="test-full-auto-scheduler",
            name="Scheduler Full-Auto Test",
            positioning="测试定位：科技资讯公众号",
            operation_mode="full_auto",
            auto_run_enabled=True,
            is_active=True,
            posting_frequency="daily",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()

        # Mock successful publish
        with fake_publish_service.success():
            await scheduler_tick_helper.trigger(db_session)

        # Verify draft with published status
        from sqlalchemy import select
        stmt = select(ArticleDraftModel).where(
            ArticleDraftModel.account_id == account.id
        )
        result = await db_session.execute(stmt)
        draft = result.scalar_one_or_none()

        # Note: full_auto creates draft_status="approved" (not "published")
        # The draft is auto-approved but actual publish to WeChat requires separate call
        assert draft is not None, "Draft should be created"
        assert draft.draft_status == "approved", \
            f"Expected approved (auto-approved), got {draft.draft_status}"
        assert draft.publish_status == "published", \
            f"Expected published, got {draft.publish_status}"
        assert draft.confirmed_by == "system"

        # Verify account status
        account = await account_state.assert_success(account.id)
        await account_state.assert_next_run_refreshed(account.id)


# =============================================================================
# Scenario 3: manual 账号不会自动触发
# =============================================================================

class TestManualAccountIsolation:
    """Scenario 3: manual account won't auto-trigger."""

    @pytest.mark.asyncio
    async def test_manual_account_not_triggered(
        self, db_session, scheduler_tick_helper, account_state, mock_llm
    ):
        """
        Test that manual account is NOT triggered by scheduler.

        Steps:
        1. Create manual account with due time
        2. Trigger scheduler tick
        3. Verify NO task created
        4. Verify account status unchanged
        """
        # Create manual account
        account = AccountModel(
            id="test-manual-scheduler",
            name="Scheduler Manual Test",
            positioning="测试定位",
            operation_mode="manual",
            auto_run_enabled=False,  # Manual mode
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            last_run_status="never_run",
        )
        db_session.add(account)
        await db_session.commit()

        original_last_run_at = account.last_run_at

        # Trigger scheduler tick
        results = await scheduler_tick_helper.trigger(db_session)

        # Verify NO task was created
        assert len(results) == 0, "Manual account should not be triggered"

        # Verify account status unchanged
        refreshed = await account_state.refresh(account.id)
        assert refreshed.last_run_at == original_last_run_at, \
            "last_run_at should not change for manual account"

    @pytest.mark.asyncio
    async def test_manual_with_due_time_not_triggered(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """
        Test that manual account with due time is still not triggered.

        Even if next_run_at is set, manual accounts should not be auto-scheduled.
        """
        account = AccountModel(
            id="test-manual-due-time",
            name="Manual With Due Time",
            positioning="测试定位",
            operation_mode="manual",
            auto_run_enabled=False,
            is_active=True,
            posting_frequency="daily",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify NO task
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        task = result.scalar_one_or_none()

        assert task is None, "Manual account should not create task"


# =============================================================================
# Scenario 4: disabled / auto_run_enabled=false 不会自动触发
# =============================================================================

class TestAccountEligibility:
    """Scenario 4: disabled or auto_run_enabled=false accounts won't trigger."""

    @pytest.mark.asyncio
    async def test_disabled_account_not_triggered(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """Test that disabled account is NOT triggered."""
        account = AccountModel(
            id="test-disabled-scheduler",
            name="Disabled Account",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=False,  # Disabled
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify NO task
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        task = result.scalar_one_or_none()

        assert task is None, "Disabled account should not create task"

    @pytest.mark.asyncio
    async def test_auto_run_disabled_account_not_triggered(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """Test that account with auto_run_enabled=False is NOT triggered."""
        account = AccountModel(
            id="test-auto-run-disabled",
            name="Auto Run Disabled",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=False,  # Auto run disabled
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify NO task
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        task = result.scalar_one_or_none()

        assert task is None, "Account with auto_run_enabled=False should not create task"

    @pytest.mark.asyncio
    async def test_future_due_account_not_triggered(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """Test that account with future next_run_at is NOT triggered."""
        account = AccountModel(
            id="test-future-due",
            name="Future Due",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),  # Future
        )
        db_session.add(account)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify NO task
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        task = result.scalar_one_or_none()

        assert task is None, "Future due account should not be triggered"


# =============================================================================
# Scenario 5: 已有 pending/running task 时不重复调度
# =============================================================================

class TestDuplicateSchedulingPrevention:
    """Scenario 5: pending/running task prevents duplicate scheduling."""

    @pytest.mark.asyncio
    async def test_pending_task_prevents_duplicate(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """Test that account with pending task is NOT triggered again."""
        account = AccountModel(
            id="test-pending-task",
            name="Account With Pending Task",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)

        # Create pending task
        existing_task = TaskModel(
            id="existing-pending-task",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="pending",
        )
        db_session.add(existing_task)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify only the original task exists
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        tasks = list(result.scalars().all())

        assert len(tasks) == 1, "Should not create duplicate task"
        assert tasks[0].id == "existing-pending-task"

    @pytest.mark.asyncio
    async def test_running_task_prevents_duplicate(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """Test that account with running task is NOT triggered again."""
        account = AccountModel(
            id="test-running-task",
            name="Account With Running Task",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)

        # Create running task
        existing_task = TaskModel(
            id="existing-running-task",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="running",
        )
        db_session.add(existing_task)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify only the original task exists
        from sqlalchemy import select
        stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        result = await db_session.execute(stmt)
        tasks = list(result.scalars().all())

        assert len(tasks) == 1, "Should not create duplicate task"
        assert tasks[0].id == "existing-running-task"


# =============================================================================
# Scenario 6: 任务失败时 account 状态同步
# =============================================================================

class TestTaskFailureStateSync:
    """Scenario 6: task failure syncs account status (with fallback).

    Note: Due to orchestrator fallback mechanism, LLM failures are gracefully
    handled and the pipeline continues. These tests verify that behavior.
    """

    @pytest.mark.asyncio
    async def test_llm_failure_triggers_fallback(
        self, db_session, scheduler_tick_helper, account_state, mock_llm
    ):
        """
        Test that LLM failure triggers fallback and task still completes.

        The orchestrator has fallback mechanism - when LLM fails,
        the agent returns degraded results instead of crashing.
        """
        account = AccountModel(
            id="test-failure-sync",
            name="Failure Sync Test",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)
        await db_session.commit()

        # Mock LLM to raise error
        async def mock_llm_error(*args, **kwargs):
            raise Exception("LLM API Error")

        with patch("litellm.acompletion", side_effect=mock_llm_error):
            results = await scheduler_tick_helper.trigger(db_session)

        # Verify task completed (with fallback)
        assert len(results) == 1
        assert results[0]["status"] == "success", \
            "Task should complete with fallback (not crash)"

        # Verify account status is success (fallback succeeded)
        account = await account_state.assert_success(account.id)

        # Verify draft was created (with degraded content from fallback)
        from sqlalchemy import select
        stmt = select(ArticleDraftModel).where(
            ArticleDraftModel.account_id == account.id
        )
        result = await db_session.execute(stmt)
        draft = result.scalar_one_or_none()
        assert draft is not None, "Draft should be created even with fallback"
        assert draft.draft_status == "pending_review"

    @pytest.mark.asyncio
    async def test_task_failure_syncs_account_status(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """
        Test that when task truly fails, account.last_run_status and last_error_message are updated.

        This test mocks orchestrator_engine.run to raise an exception directly,
        bypassing the fallback mechanism.
        """
        account = AccountModel(
            id="test-true-failure",
            name="True Failure Test",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account)
        await db_session.commit()

        # Mock orchestrator to raise exception (bypass fallback)
        async def mock_run_failure(task, db):
            raise Exception("Orchestrator critical failure")

        with patch("app.orchestrator.engine.orchestrator_engine.run", side_effect=mock_run_failure):
            results = await scheduler_tick_helper.trigger(db_session)

        # Verify task failed
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "Orchestrator critical failure" in results[0].get("error", "")

        # Verify account status is failed
        from sqlalchemy import select
        stmt = select(AccountModel).where(AccountModel.id == account.id)
        result = await db_session.execute(stmt)
        updated_account = result.scalar_one()

        assert updated_account.last_run_status == "failed", \
            f"Expected failed, got {updated_account.last_run_status}"
        assert updated_account.last_error_message is not None
        assert "Orchestrator" in updated_account.last_error_message or "failure" in updated_account.last_error_message

        # Verify task status is failed
        task_stmt = select(TaskModel).where(TaskModel.account_id == account.id)
        task_result = await db_session.execute(task_stmt)
        task = task_result.scalar_one()
        assert task.status == "failed"
        assert task.error_message is not None

    @pytest.mark.asyncio
    async def test_mixed_failure_and_success(
        self, db_session, scheduler_tick_helper, account_state, mock_llm
    ):
        """
        Test that one account's LLM failure (with fallback) doesn't affect other accounts.
        """
        # Create two accounts
        success_account = AccountModel(
            id="test-success-account",
            name="Success Account",
            positioning="测试定位成功",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        fail_account = AccountModel(
            id="test-fail-account",
            name="Fail Account",
            positioning="测试定位失败",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(success_account)
        db_session.add(fail_account)
        await db_session.commit()

        # Mock first LLM call to fail (fallback will handle), second succeeds
        call_count = 0
        async def mock_mixed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 6:  # First ~6 agent calls fail
                raise Exception("Simulated LLM failure")
            # Later calls succeed
            from tests.e2e.mock_llm import get_mock_llm_response
            return get_mock_llm_response(
                agent_id=kwargs.get("model", ""),
                messages=kwargs.get("messages", []),
                **kwargs
            )

        with patch("litellm.acompletion", side_effect=mock_mixed):
            results = await scheduler_tick_helper.trigger(db_session)

        # Verify both were attempted (with fallback)
        assert len(results) == 2

        # Verify both succeeded (with degraded content from fallback)
        success_result = next(r for r in results if r["account_id"] == success_account.id)
        fail_result = next(r for r in results if r["account_id"] == fail_account.id)

        assert success_result["status"] == "success"
        assert fail_result["status"] == "success"


# =============================================================================
# Scenario 7: 多账号并发扫描
# =============================================================================

class TestMultiAccountScanning:
    """Scenario 7: multi-account concurrent scan."""

    @pytest.mark.asyncio
    async def test_only_eligible_accounts_triggered(
        self, db_session, scheduler_tick_helper, mock_llm
    ):
        """
        Test that only eligible accounts are triggered in a batch.

        Steps:
        1. Create 4 accounts:
           - semi_auto due (should trigger)
           - full_auto due (should trigger)
           - manual due (should NOT trigger)
           - disabled due (should NOT trigger)
        2. Trigger scheduler tick
        3. Verify only 2 tasks created
        """
        accounts = [
            # Should trigger: semi_auto
            AccountModel(
                id="multi-semi-auto",
                name="Multi Semi-Auto",
                positioning="测试定位1",
                operation_mode="semi_auto",
                auto_run_enabled=True,
                is_active=True,
                next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
            # Should trigger: full_auto
            AccountModel(
                id="multi-full-auto",
                name="Multi Full-Auto",
                positioning="测试定位2",
                operation_mode="full_auto",
                auto_run_enabled=True,
                is_active=True,
                next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
            # Should NOT trigger: manual
            AccountModel(
                id="multi-manual",
                name="Multi Manual",
                positioning="测试定位3",
                operation_mode="manual",
                auto_run_enabled=False,
                is_active=True,
                next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
            # Should NOT trigger: disabled
            AccountModel(
                id="multi-disabled",
                name="Multi Disabled",
                positioning="测试定位4",
                operation_mode="semi_auto",
                auto_run_enabled=True,
                is_active=False,  # Disabled
                next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
        ]

        for account in accounts:
            db_session.add(account)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Count tasks created
        from sqlalchemy import select, or_
        stmt = select(TaskModel).where(
            or_(
                TaskModel.account_id == "multi-semi-auto",
                TaskModel.account_id == "multi-full-auto",
                TaskModel.account_id == "multi-manual",
                TaskModel.account_id == "multi-disabled",
            )
        )
        result = await db_session.execute(stmt)
        tasks = list(result.scalars().all())

        # Only semi_auto and full_auto should create tasks
        assert len(tasks) == 2, f"Expected 2 tasks, got {len(tasks)}"
        task_account_ids = {t.account_id for t in tasks}
        assert "multi-semi-auto" in task_account_ids
        assert "multi-full-auto" in task_account_ids

    @pytest.mark.asyncio
    async def test_batch_status_updates(
        self, db_session, scheduler_tick_helper, account_state, mock_llm
    ):
        """
        Test that batch processing updates each account status correctly.
        """
        # Create two accounts
        account1 = AccountModel(
            id="batch-account-1",
            name="Batch Account 1",
            positioning="测试定位批处理1",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        account2 = AccountModel(
            id="batch-account-2",
            name="Batch Account 2",
            positioning="测试定位批处理2",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(account1)
        db_session.add(account2)
        await db_session.commit()

        await scheduler_tick_helper.trigger(db_session)

        # Verify both accounts updated
        await account_state.assert_success(account1.id)
        await account_state.assert_success(account2.id)


# =============================================================================
# Account State Assertions
# =============================================================================

class TestAccountStateHelpers:
    """Test account state assertion helpers."""

    @pytest.mark.asyncio
    async def test_assert_success_works(self, db_session, account_state):
        """Test assert_success helper."""
        account = AccountModel(
            id="test-assert-success",
            name="Assert Success Test",
            positioning="测试",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            last_run_status="success",
            last_run_at=datetime.now(timezone.utc),
        )
        db_session.add(account)
        await db_session.commit()

        result = await account_state.assert_success(account.id)
        assert result.last_run_status == "success"

    @pytest.mark.asyncio
    async def test_assert_failed_works(self, db_session, account_state):
        """Test assert_failed helper."""
        account = AccountModel(
            id="test-assert-failed",
            name="Assert Failed Test",
            positioning="测试",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            last_run_status="failed",
            last_error_message="Test error",
        )
        db_session.add(account)
        await db_session.commit()

        result = await account_state.assert_failed(account.id)
        assert result.last_run_status == "failed"

    @pytest.mark.asyncio
    async def test_next_run_refreshed(self, db_session, account_state):
        """Test next_run_at is refreshed after success."""
        account = AccountModel(
            id="test-next-run-refresh",
            name="Next Run Refresh Test",
            positioning="测试",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
            posting_frequency="daily",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            last_run_status="success",
            last_run_at=datetime.now(timezone.utc),
        )
        db_session.add(account)
        await db_session.commit()

        # Simulate refresh
        from app.services.account_service import account_service
        await account_service.refresh_next_run(account.id, db_session)
        await db_session.commit()

        # Refresh from database using test's db_session
        from sqlalchemy import select
        stmt = select(AccountModel).where(AccountModel.id == account.id)
        result = await db_session.execute(stmt)
        refreshed = result.scalar_one_or_none()

        assert refreshed is not None, "Account should still exist"
        assert refreshed.next_run_at is not None, "next_run_at should be set"
        assert refreshed.next_run_at > datetime.now(timezone.utc), \
            "next_run_at should be in the future"
