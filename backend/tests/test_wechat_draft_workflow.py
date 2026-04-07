"""Workflow tests for manual / semi_auto / full_auto WeChat integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import DraftPublishError
from app.models.tables import AccountModel, ArticleDraftModel, TaskModel
from app.services.draft_service import draft_service
from app.services.task_service import task_service


def _build_result_data(title: str) -> dict:
    return {
        "content": {
            "summary": "测试摘要",
            "content_markdown": f"# {title}\n\n正文内容",
            "content_html": f"<h1>{title}</h1><p>正文内容</p>",
        },
        "titles": {"selected_title": title, "candidates": [title]},
        "topics": {"selected_topic": "测试选题"},
    }


@pytest.mark.asyncio
async def test_manual_mode_does_not_auto_publish(db_session, monkeypatch):
    account = AccountModel(
        id="workflow-manual",
        name="Manual Workflow",
        positioning="测试定位",
        operation_mode="manual",
        auto_run_enabled=False,
        is_active=True,
    )
    task = TaskModel(
        id="manual-task",
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        result_data=_build_result_data("手动模式"),
    )
    db_session.add_all([account, task])
    await db_session.commit()

    publish_mock = AsyncMock()
    monkeypatch.setattr(draft_service, "publish_to_wechat", publish_mock)

    await task_service._create_draft_from_task_result(task, task.result_data, db_session)

    drafts, _ = await draft_service.list_drafts(db_session)
    created = drafts[0]
    assert created.draft_status == "draft"
    assert created.publish_status == "not_published"
    publish_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_semi_auto_mode_creates_pending_review_without_auto_publish(db_session, monkeypatch):
    account = AccountModel(
        id="workflow-semi",
        name="Semi Workflow",
        positioning="测试定位",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        is_active=True,
    )
    task = TaskModel(
        id="semi-task",
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        result_data=_build_result_data("半自动模式"),
    )
    db_session.add_all([account, task])
    await db_session.commit()

    publish_mock = AsyncMock()
    monkeypatch.setattr(draft_service, "publish_to_wechat", publish_mock)

    await task_service._create_draft_from_task_result(task, task.result_data, db_session)

    drafts, _ = await draft_service.list_drafts(db_session)
    created = drafts[0]
    assert created.draft_status == "pending_review"
    assert created.publish_status == "not_published"
    publish_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_full_auto_mode_triggers_publish(db_session, monkeypatch):
    account = AccountModel(
        id="workflow-full",
        name="Full Workflow",
        positioning="测试定位",
        operation_mode="full_auto",
        auto_run_enabled=True,
        auto_publish_enabled=True,
        is_active=True,
    )
    task = TaskModel(
        id="full-task",
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        result_data=_build_result_data("全自动模式"),
    )
    db_session.add_all([account, task])
    await db_session.commit()

    async def publish_side_effect(draft_id: int, db, **kwargs):
        created = await draft_service.get_draft(draft_id, db)
        created.publish_status = "pending"
        db.add(created)
        await db.flush()
        return created, {"publish_status": "pending"}

    publish_mock = AsyncMock(side_effect=publish_side_effect)
    monkeypatch.setattr(draft_service, "publish_to_wechat", publish_mock)

    await task_service._create_draft_from_task_result(task, task.result_data, db_session)

    drafts, _ = await draft_service.list_drafts(db_session)
    created = drafts[0]
    assert created.draft_status == "approved"
    assert publish_mock.await_count == 1
    assert created.confirmed_by == "system"


@pytest.mark.asyncio
async def test_full_auto_publish_failure_keeps_draft_consistent(db_session, monkeypatch):
    account = AccountModel(
        id="workflow-full-fail",
        name="Full Workflow Fail",
        positioning="测试定位",
        operation_mode="full_auto",
        auto_run_enabled=True,
        auto_publish_enabled=True,
        is_active=True,
    )
    task = TaskModel(
        id="full-fail-task",
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        result_data=_build_result_data("全自动失败"),
    )
    db_session.add_all([account, task])
    await db_session.commit()

    monkeypatch.setattr(
        draft_service,
        "publish_to_wechat",
        AsyncMock(side_effect=DraftPublishError(1, "wechat publish failed")),
    )

    await task_service._create_draft_from_task_result(task, task.result_data, db_session)

    drafts, _ = await draft_service.list_drafts(db_session)
    created = drafts[0]
    assert created.draft_status == "approved"
    assert created.publish_status == "not_published"
    assert created.published_at is None
