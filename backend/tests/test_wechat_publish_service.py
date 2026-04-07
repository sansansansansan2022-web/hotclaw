"""Tests for WeChat publish orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from app.core.exceptions import DraftPublishError
from app.models.tables import AccountModel, ArticleDraftModel, SystemConfigModel
from app.models.wechat_config import WeChatConfigModel
from app.services.publish_decision_service import PublishDecisionError
from app.services.publish_record_service import publish_record_service
from app.services.wechat_draft_service import wechat_draft_service
from app.services.wechat_media_service import wechat_media_service
from app.services.wechat_publish_service import wechat_publish_service
from app.services.wechat_token_service import WeChatTokenError


async def _ensure_publish_switches(db_session):
    configs = [
        SystemConfigModel(key="global_publish_enabled", value="true", value_type="boolean", category="publish"),
        SystemConfigModel(key="global_emergency_stop", value="false", value_type="boolean", category="publish"),
    ]
    for config in configs:
        existing = await db_session.get(SystemConfigModel, config.key)
        if not existing:
            db_session.add(config)
    await db_session.commit()


@pytest_asyncio.fixture
async def account(db_session):
    account = AccountModel(
        id="wechat-publish-account",
        name="WeChat Publish Account",
        positioning="测试定位",
        operation_mode="semi_auto",
        auto_publish_enabled=False,
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    await _ensure_publish_switches(db_session)
    return account


@pytest_asyncio.fixture
async def draft(db_session, account):
    draft = ArticleDraftModel(
        task_id="wechat-task-1",
        account_id=account.id,
        title="HotClaw 发布测试",
        summary="一篇用于测试微信公众号发布链路的草稿。",
        content_markdown="# 标题\n\n正文内容",
        content_html="<p>正文内容</p>",
        word_count=100,
        draft_status="approved",
        publish_status="not_published",
        source_type="semi_auto_task",
        confirmed_by="user",
    )
    db_session.add(draft)
    await db_session.commit()
    return draft


@pytest_asyncio.fixture
async def wechat_config(db_session, account):
    config = WeChatConfigModel(
        account_id=account.id,
        app_id="wx-publish-app-id",
        app_secret="wx-publish-secret",
        is_enabled=True,
        default_author="HotClaw",
        need_open_comment=True,
        only_fans_can_comment=False,
    )
    db_session.add(config)
    await db_session.commit()
    return config


@pytest.mark.asyncio
async def test_publish_requires_wechat_config(db_session, draft):
    with pytest.raises(PublishDecisionError) as exc_info:
        await wechat_publish_service.publish_draft_to_wechat(draft.id, operator="tester", db=db_session)

    assert exc_info.value.reason_code == "WECHAT_CONFIG_MISSING"


@pytest.mark.asyncio
async def test_publish_fails_when_token_refresh_fails(db_session, draft, wechat_config, monkeypatch):
    monkeypatch.setattr(
        wechat_draft_service,
        "create_wechat_draft",
        AsyncMock(side_effect=WeChatTokenError("token refresh failed")),
    )
    monkeypatch.setattr(
        wechat_media_service,
        "rewrite_article_html_images",
        AsyncMock(return_value=("<p>正文内容</p>", None)),
    )

    with pytest.raises(DraftPublishError) as exc_info:
        await wechat_publish_service.publish_draft_to_wechat(draft.id, operator="tester", db=db_session)

    assert "token refresh failed" in exc_info.value.message
    latest_record = await publish_record_service.get_latest_for_draft(draft.id, db_session)
    assert latest_record is not None
    assert latest_record.publish_status == publish_record_service.STATUS_FAILED


@pytest.mark.asyncio
async def test_terminal_draft_cannot_be_published(db_session, account, wechat_config):
    terminal_draft = ArticleDraftModel(
        task_id="wechat-task-terminal",
        account_id=account.id,
        title="终态草稿",
        content_markdown="# 内容",
        word_count=20,
        draft_status="discarded",
        publish_status="not_published",
        source_type="manual_task",
    )
    db_session.add(terminal_draft)
    await db_session.commit()

    with pytest.raises(PublishDecisionError) as exc_info:
        await wechat_publish_service.publish_draft_to_wechat(terminal_draft.id, operator="tester", db=db_session)

    assert exc_info.value.reason_code == "DRAFT_TERMINAL_STATE"


@pytest.mark.asyncio
async def test_publish_successful_flow_updates_record_and_draft(db_session, draft, wechat_config, monkeypatch):
    monkeypatch.setattr(
        wechat_media_service,
        "rewrite_article_html_images",
        AsyncMock(return_value=("<p>微信正文</p>", "thumb-media-1")),
    )
    monkeypatch.setattr(
        wechat_draft_service,
        "create_wechat_draft",
        AsyncMock(return_value={"media_id": "wechat-draft-media-1"}),
    )
    monkeypatch.setattr(
        wechat_publish_service,
        "free_publish",
        AsyncMock(return_value={"publish_id": "publish-job-1", "msg_data_id": "msg-data-1"}),
    )
    monkeypatch.setattr(
        wechat_publish_service,
        "get_publish_status",
        AsyncMock(
            return_value={
                "status": publish_record_service.STATUS_PUBLISHED,
                "message": "published",
                "article_id": "article-1",
                "msg_data_id": "msg-data-1",
                "article_url": "https://mp.weixin.qq.com/s/example",
                "publish_status_code": 2,
            }
        ),
    )

    result = await wechat_publish_service.publish_draft_to_wechat(draft.id, operator="tester", db=db_session)

    assert result.success is True
    assert result.publish_record_id is not None
    assert result.publish_status == publish_record_service.STATUS_PUBLISHED

    refreshed_draft = await db_session.get(ArticleDraftModel, draft.id)
    assert refreshed_draft.publish_status == "published"
    assert refreshed_draft.draft_status == "published"
    assert refreshed_draft.published_at is not None

    record = await publish_record_service.get_latest_for_draft(draft.id, db_session)
    assert record is not None
    assert record.publish_status == publish_record_service.STATUS_PUBLISHED
    assert record.publish_id == "publish-job-1"
    assert record.url == "https://mp.weixin.qq.com/s/example"


@pytest.mark.asyncio
async def test_publish_idempotency_blocks_active_record(db_session, draft, wechat_config):
    await publish_record_service.create_record(
        draft_id=draft.id,
        account_id=draft.account_id,
        task_id=draft.task_id,
        db=db_session,
        source_mode="semi_auto",
        trigger_type=publish_record_service.TRIGGER_SEMI_AUTO_CONFIRM,
    )

    with pytest.raises(PublishDecisionError) as exc_info:
        await wechat_publish_service.publish_draft_to_wechat(draft.id, operator="tester", db=db_session)

    assert exc_info.value.reason_code == "ACTIVE_PUBLISH_EXISTS"
