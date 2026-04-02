"""E2E tests for draft workflow scenarios.

【E2E 草稿工作流测试】
验证从账号创建 → 任务执行 → 草稿生成 → 确认发布的完整链路。
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from app.models.tables import AccountModel, TaskModel, ArticleDraftModel
from app.services.draft_service import draft_service
from app.services.account_service import account_service
from app.core.exceptions import (
    DraftAlreadyPublishedError,
    DraftInvalidStatusError,
)


class TestDraftCreation:
    """Test draft creation from task results."""

    @pytest.mark.asyncio
    async def test_semi_auto_creates_pending_review_draft(self, db_session):
        """Test that semi_auto mode creates pending_review draft."""
        account = AccountModel(
            id="test-semi-auto",
            name="Semi-Auto Test",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
        )
        db_session.add(account)

        task = TaskModel(
            id="test-task-1",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="completed",
            result_data={
                "content": {
                    "title": "测试标题",
                    "content_markdown": "# 测试文章\n\n这是测试内容。",
                    "word_count": 50,
                    "tags": ["测试"],
                },
                "titles": {"selected_title": "测试标题"},
                "topics": {"selected_topic": "测试选题"},
            },
        )
        db_session.add(task)
        await db_session.commit()

        draft = await draft_service.create_draft_from_task(
            task_id=task.id,
            result_data=task.result_data,
            account_id=account.id,
            operation_mode="semi_auto",
            db=db_session
        )
        await db_session.commit()

        assert draft.draft_status == "pending_review"
        assert draft.publish_status == "not_published"
        assert draft.source_type == "semi_auto_task"
        assert draft.title == "测试标题"

    @pytest.mark.asyncio
    async def test_full_auto_creates_approved_draft(self, db_session):
        """Test that full_auto mode creates approved draft (auto publish)."""
        account = AccountModel(
            id="test-full-auto",
            name="Full-Auto Test",
            positioning="测试定位",
            operation_mode="full_auto",
            auto_run_enabled=True,
            is_active=True,
        )
        db_session.add(account)

        task = TaskModel(
            id="test-task-2",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="completed",
            result_data={
                "content": {
                    "title": "自动发布标题",
                    "content_markdown": "# 自动发布\n\n内容",
                },
                "titles": {"selected_title": "自动发布标题"},
                "topics": {"selected_topic": "选题"},
            },
        )
        db_session.add(task)
        await db_session.commit()

        draft = await draft_service.create_draft_from_task(
            task_id=task.id,
            result_data=task.result_data,
            account_id=account.id,
            operation_mode="full_auto",
            db=db_session
        )
        await db_session.commit()

        assert draft.draft_status == "approved"
        assert draft.publish_status == "published"
        assert draft.confirmed_by == "system"
        assert draft.published_at is not None

    @pytest.mark.asyncio
    async def test_manual_creates_draft_status(self, db_session):
        """Test that manual mode creates draft status (not pending_review)."""
        account = AccountModel(
            id="test-manual",
            name="Manual Test",
            positioning="测试定位",
            operation_mode="manual",
            auto_run_enabled=False,
            is_active=True,
        )
        db_session.add(account)

        task = TaskModel(
            id="test-task-3",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="completed",
            result_data={
                "content": {"title": "手动标题", "content_markdown": "# 内容"},
                "titles": {"selected_title": "手动标题"},
                "topics": {"selected_topic": "选题"},
            },
        )
        db_session.add(task)
        await db_session.commit()

        draft = await draft_service.create_draft_from_task(
            task_id=task.id,
            result_data=task.result_data,
            account_id=account.id,
            operation_mode="manual",
            db=db_session
        )
        await db_session.commit()

        assert draft.draft_status == "draft"
        assert draft.publish_status == "not_published"


class TestDraftConfirmation:
    """Test draft confirmation workflow."""

    @pytest.mark.asyncio
    async def test_confirm_publish_updates_status(self, db_session):
        """Test that confirming publish updates draft status correctly."""
        account = AccountModel(
            id="test-confirm",
            name="Confirm Test",
            positioning="测试",
            operation_mode="semi_auto",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        draft = ArticleDraftModel(
            task_id="test-task",
            account_id=account.id,
            title="待审核",
            content_markdown="# 内容",
            word_count=100,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        result = await draft_service.confirm_publish(draft.id, db_session)

        assert result.draft_status == "approved"
        assert result.publish_status == "published"
        assert result.confirmed_at is not None
        assert result.confirmed_by == "user"

    @pytest.mark.asyncio
    async def test_api_confirm_publish(self, client, db_session):
        """Test API endpoint for confirming publish."""
        account = AccountModel(
            id="test-api-confirm",
            name="API Confirm Test",
            positioning="测试",
            operation_mode="semi_auto",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        draft = ArticleDraftModel(
            task_id="test-api-task",
            account_id=account.id,
            title="API测试",
            content_markdown="# 内容",
            word_count=50,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()
        draft_id = draft.id

        response = await client.post(f"/api/v1/drafts/{draft_id}/confirm-publish")

        assert response.status_code == 200
        data = response.json()
        assert data["draft_status"] == "approved"
        assert data["publish_status"] == "published"


class TestTerminalStateProtection:
    """Test that terminal state drafts cannot be modified."""

    @pytest.mark.asyncio
    async def test_published_cannot_confirm_again(self, db_session):
        """Test that published draft cannot be confirmed again."""
        draft = ArticleDraftModel(
            task_id="test",
            title="已发布",
            content_markdown="# 内容",
            word_count=50,
            draft_status="published",
            publish_status="published",
            source_type="semi_auto_task",
            published_at=datetime.now(timezone.utc),
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by="user",
        )
        db_session.add(draft)
        await db_session.commit()

        with pytest.raises(DraftAlreadyPublishedError):
            await draft_service.confirm_publish(draft.id, db_session)

    @pytest.mark.asyncio
    async def test_published_cannot_discard(self, db_session):
        """Test that published draft cannot be discarded."""
        draft = ArticleDraftModel(
            task_id="test",
            title="已发布",
            content_markdown="# 内容",
            word_count=50,
            draft_status="published",
            publish_status="published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        with pytest.raises(DraftInvalidStatusError):
            await draft_service.discard_draft(draft.id, db_session)

    @pytest.mark.asyncio
    async def test_published_cannot_rerun(self, db_session):
        """Test that published draft cannot be rerun."""
        draft = ArticleDraftModel(
            task_id="test",
            title="已发布",
            content_markdown="# 内容",
            word_count=50,
            draft_status="published",
            publish_status="published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        with pytest.raises(DraftAlreadyPublishedError):
            await draft_service.rerun_from_draft(draft.id, db_session)

    @pytest.mark.asyncio
    async def test_discarded_cannot_confirm(self, db_session):
        """Test that discarded draft cannot be confirmed."""
        draft = ArticleDraftModel(
            task_id="test",
            title="已废弃",
            content_markdown="# 内容",
            word_count=50,
            draft_status="discarded",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        with pytest.raises(DraftInvalidStatusError):
            await draft_service.confirm_publish(draft.id, db_session)

    @pytest.mark.asyncio
    async def test_discarded_cannot_rerun(self, db_session):
        """Test that discarded draft cannot be rerun."""
        draft = ArticleDraftModel(
            task_id="test",
            title="已废弃",
            content_markdown="# 内容",
            word_count=50,
            draft_status="discarded",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        with pytest.raises(DraftInvalidStatusError):
            await draft_service.rerun_from_draft(draft.id, db_session)

    @pytest.mark.asyncio
    async def test_api_terminal_state_rejection(self, client, db_session):
        """Test that API rejects operations on terminal drafts."""
        draft = ArticleDraftModel(
            task_id="test",
            title="已发布",
            content_markdown="# 内容",
            word_count=50,
            draft_status="published",
            publish_status="published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()
        draft_id = draft.id

        response = await client.post(f"/api/v1/drafts/{draft_id}/confirm-publish")
        assert response.status_code in [400, 409]

        response = await client.post(f"/api/v1/drafts/{draft_id}/discard")
        assert response.status_code == 400


class TestManualAccountIsolation:
    """Test that manual accounts are isolated from auto-scheduling."""

    @pytest.mark.asyncio
    async def test_manual_account_run_manually(self, db_session):
        """Test that manual account can be run manually."""
        account = AccountModel(
            id="test-manual-run",
            name="Manual Account",
            positioning="测试定位",
            operation_mode="manual",
            auto_run_enabled=False,
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        # Manual run (user triggered) should work with allow_auto=True
        result_account, task = await account_service.run_account(
            account.id, db_session, allow_auto=True
        )

        assert task is not None
        assert task.account_id == account.id
        assert task.status == "pending"


class TestDraftListAndCount:
    """Test draft listing and counting."""

    @pytest.mark.asyncio
    async def test_list_drafts_by_status(self, db_session):
        """Test filtering drafts by status."""
        account = AccountModel(
            id="test-list",
            name="List Test",
            positioning="测试",
            operation_mode="semi_auto",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        for i, status in enumerate(["pending_review", "pending_review", "draft"]):
            draft = ArticleDraftModel(
                task_id=f"task-{i}",
                account_id=account.id,
                title=f"草稿{i}",
                content_markdown="# 内容",
                word_count=50,
                draft_status=status,
                publish_status="not_published",
                source_type="semi_auto_task",
            )
            db_session.add(draft)
        await db_session.commit()

        drafts, total = await draft_service.list_drafts(
            db_session,
            account_id=account.id,
            draft_status="pending_review"
        )
        assert total == 2
        assert all(d.draft_status == "pending_review" for d in drafts)

    @pytest.mark.asyncio
    async def test_pending_count(self, db_session):
        """Test pending draft count."""
        account = AccountModel(
            id="test-count",
            name="Count Test",
            positioning="测试",
            operation_mode="semi_auto",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        draft = ArticleDraftModel(
            task_id="count-task",
            account_id=account.id,
            title="待审核",
            content_markdown="# 内容",
            word_count=50,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        count = await draft_service.get_pending_review_count(db_session, account.id)
        assert count >= 1


class TestDraftRerun:
    """Test draft rerun workflow."""

    @pytest.mark.asyncio
    async def test_rerun_creates_new_task(self, db_session):
        """Test that rerunning a draft creates a new task."""
        account = AccountModel(
            id="test-rerun",
            name="Rerun Test",
            positioning="测试定位",
            operation_mode="semi_auto",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        draft = ArticleDraftModel(
            task_id="original-task",
            account_id=account.id,
            title="原草稿",
            content_markdown="# 内容",
            word_count=50,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        original, new_task = await draft_service.rerun_from_draft(draft.id, db_session)

        assert new_task is not None
        assert new_task.account_id == account.id
        assert new_task.status == "pending"
        assert new_task.id != draft.task_id

    @pytest.mark.asyncio
    async def test_rerun_preserves_original(self, db_session):
        """Test that rerunning preserves the original draft."""
        account = AccountModel(
            id="test-rerun-preserve",
            name="Rerun Preserve Test",
            positioning="测试",
            operation_mode="semi_auto",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()

        draft = ArticleDraftModel(
            task_id="orig-task",
            account_id=account.id,
            title="原草稿",
            content_markdown="# 内容",
            word_count=50,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        original, new_task = await draft_service.rerun_from_draft(draft.id, db_session)
        await db_session.refresh(original)

        assert original.draft_status == "pending_review"
