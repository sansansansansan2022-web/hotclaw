"""
Tests for Draft (Article Draft) functionality.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import select

from app.models.tables import AccountModel, TaskModel, ArticleDraftModel
from app.services.draft_service import draft_service
from app.core.exceptions import (
    DraftNotFoundError,
    DraftInvalidStatusError,
    DraftAlreadyPublishedError,
)


class TestDraftService:
    """Test draft service operations."""

    @pytest_asyncio.fixture
    async def account(self, db_session):
        account = AccountModel(
            id="draft-test-acc-001",
            name="Draft Test Account",
            positioning="测试定位",
            operation_mode="semi_auto",
            auto_run_enabled=True,
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def task(self, db_session, account):
        task = TaskModel(
            id="draft-test-task-001",
            account_id=account.id,
            workflow_id="default_pipeline",
            status="completed",
            result_data={
                "content": {
                    "title": "测试标题",
                    "content_markdown": "# 测试文章",
                    "word_count": 100,
                    "tags": ["测试"],
                },
                "titles": {"selected_title": "测试标题"},
                "topics": {"selected_topic": "测试选题"},
            },
        )
        db_session.add(task)
        await db_session.commit()
        return task

    @pytest_asyncio.fixture
    async def manual_account(self, db_session):
        account = AccountModel(
            id="manual-test-acc-001",
            name="Manual Account",
            positioning="手动定位",
            operation_mode="manual",
            is_active=True,
        )
        db_session.add(account)
        await db_session.commit()
        return account

    @pytest_asyncio.fixture
    async def manual_task(self, db_session, manual_account):
        task = TaskModel(
            id="manual-task-001",
            account_id=manual_account.id,
            workflow_id="default_pipeline",
            status="completed",
            result_data={
                "content": {"title": "手动标题", "content_markdown": "# 手动", "word_count": 50, "tags": []},
                "titles": {},
                "topics": {},
            },
        )
        db_session.add(task)
        await db_session.commit()
        return task

    @pytest_asyncio.fixture
    async def pending_draft(self, db_session, account, task):
        draft = ArticleDraftModel(
            task_id=task.id,
            account_id=account.id,
            title="待审核标题",
            content_markdown="# 待审核",
            word_count=200,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()
        return draft

    @pytest.mark.asyncio
    async def test_semi_auto_creates_pending_review(self, db_session, account, task):
        draft = await draft_service.create_draft_from_task(
            task_id=task.id,
            result_data=task.result_data,
            account_id=account.id,
            operation_mode="semi_auto",
            db=db_session
        )
        assert draft.draft_status == "pending_review"
        assert draft.publish_status == "not_published"

    @pytest.mark.asyncio
    async def test_manual_creates_draft(self, db_session, manual_account, manual_task):
        draft = await draft_service.create_draft_from_task(
            task_id=manual_task.id,
            result_data=manual_task.result_data,
            account_id=manual_account.id,
            operation_mode="manual",
            db=db_session
        )
        assert draft.draft_status == "draft"
        assert draft.publish_status == "not_published"

    @pytest.mark.asyncio
    async def test_full_auto_auto_publish(self, db_session, account, task):
        draft = await draft_service.create_draft_from_task(
            task_id=task.id,
            result_data=task.result_data,
            account_id=account.id,
            operation_mode="full_auto",
            db=db_session
        )
        assert draft.draft_status == "approved"
        assert draft.publish_status == "not_published"
        assert draft.confirmed_by == "system"

    @pytest.mark.asyncio
    async def test_confirm_publish_state_machine(self, db_session, pending_draft):
        result = await draft_service.confirm_publish(pending_draft.id, db_session)
        assert result.draft_status == "approved"
        assert result.publish_status == "not_published"

    @pytest.mark.asyncio
    async def test_cannot_confirm_twice(self, db_session, pending_draft):
        await draft_service.confirm_publish(pending_draft.id, db_session)
        await db_session.refresh(pending_draft)
        with pytest.raises(DraftInvalidStatusError):
            await draft_service.confirm_publish(pending_draft.id, db_session)

    @pytest.mark.asyncio
    async def test_discarded_cannot_confirm(self, db_session, pending_draft):
        await draft_service.discard_draft(pending_draft.id, db_session)
        await db_session.refresh(pending_draft)
        with pytest.raises(DraftInvalidStatusError):
            await draft_service.confirm_publish(pending_draft.id, db_session)

    @pytest.mark.asyncio
    async def test_discarded_cannot_rerun(self, db_session, pending_draft):
        await draft_service.discard_draft(pending_draft.id, db_session)
        await db_session.refresh(pending_draft)
        with pytest.raises(DraftInvalidStatusError):
            await draft_service.rerun_from_draft(pending_draft.id, db_session)

    @pytest.mark.asyncio
    async def test_rejected_cannot_confirm(self, db_session, pending_draft):
        await draft_service.reject_draft(pending_draft.id, db_session)
        await db_session.refresh(pending_draft)
        with pytest.raises(DraftInvalidStatusError):
            await draft_service.confirm_publish(pending_draft.id, db_session)

    @pytest.mark.asyncio
    async def test_approved_draft_can_rerun(self, db_session, pending_draft):
        await draft_service.confirm_publish(pending_draft.id, db_session)
        await db_session.refresh(pending_draft)
        original_draft, new_task = await draft_service.rerun_from_draft(pending_draft.id, db_session)
        assert original_draft.id == pending_draft.id
        assert new_task.account_id == pending_draft.account_id

    @pytest.mark.asyncio
    async def test_pending_count(self, db_session, pending_draft):
        count = await draft_service.get_pending_review_count(db_session, pending_draft.account_id)
        assert count >= 1

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, db_session, pending_draft):
        drafts, total = await draft_service.list_drafts(
            db_session, page=1, page_size=10, draft_status="pending_review"
        )
        assert all(d.draft_status == "pending_review" for d in drafts)
