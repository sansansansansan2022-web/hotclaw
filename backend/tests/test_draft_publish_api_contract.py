from __future__ import annotations

import pytest

from app.models.tables import AccountModel, ArticleDraftModel, SystemConfigModel
from app.models.wechat_config import WeChatConfigModel
from app.services.publish_record_service import publish_record_service


async def _ensure_publish_switches(db_session) -> None:
    configs = [
        SystemConfigModel(key="global_publish_enabled", value="true", value_type="boolean", category="publish"),
        SystemConfigModel(key="global_emergency_stop", value="false", value_type="boolean", category="publish"),
    ]
    for config in configs:
        existing = await db_session.get(SystemConfigModel, config.key)
        if not existing:
            db_session.add(config)
    await db_session.commit()


@pytest.mark.asyncio
async def test_wechat_status_reads_latest_publish_attempt(client, db_session):
    account = AccountModel(
        id="draft-contract-account",
        name="Draft Contract Account",
        positioning="contract positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    draft = ArticleDraftModel(
        task_id="draft-contract-task",
        account_id=account.id,
        title="Contract Draft",
        content_markdown="# Contract Draft",
        word_count=20,
        draft_status="approved",
        publish_status="failed",
        source_type="semi_auto_task",
    )
    db_session.add_all([account, draft])
    await db_session.commit()

    first = await publish_record_service.create_record(
        draft_id=draft.id,
        account_id=account.id,
        task_id=draft.task_id,
        db=db_session,
        source_mode="semi_auto",
        trigger_type=publish_record_service.TRIGGER_SEMI_AUTO_CONFIRM,
    )
    await publish_record_service.update_failed(
        first.id,
        db_session,
        error_code="FAIL",
        error_message="first failure",
    )
    latest = await publish_record_service.increment_retry(first.id, db_session)
    await db_session.commit()

    response = await client.get(f"/api/v1/drafts/{draft.id}/wechat-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["record_id"] == latest.id
    assert payload["data"]["publish_status"] == publish_record_service.STATUS_PENDING


@pytest.mark.asyncio
async def test_publish_to_wechat_returns_conflict_when_config_missing(client, db_session):
    await _ensure_publish_switches(db_session)

    account = AccountModel(
        id="draft-publish-missing-config",
        name="Missing Config Account",
        positioning="contract positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    draft = ArticleDraftModel(
        task_id="draft-publish-missing-config-task",
        account_id=account.id,
        title="Missing Config Draft",
        content_markdown="# Missing Config Draft",
        word_count=20,
        draft_status="approved",
        publish_status="not_published",
        source_type="semi_auto_task",
    )
    db_session.add_all([account, draft])
    await db_session.commit()

    response = await client.post(f"/api/v1/drafts/{draft.id}/publish-to-wechat")

    assert response.status_code == 409
    payload = response.json()
    assert payload["code"] == 9004
    assert "WeChat config" in payload["message"]


@pytest.mark.asyncio
async def test_publish_to_wechat_fake_failure_returns_bad_gateway(client, db_session, monkeypatch):
    monkeypatch.setenv("HOTCLAW_E2E_TEST_MODE", "1")
    await _ensure_publish_switches(db_session)

    db_session.add_all(
        [
            SystemConfigModel(
                key="e2e_publish_mode",
                value="fake_failure",
                value_type="string",
                category="audit",
            ),
            SystemConfigModel(
                key="e2e_publish_failure_message",
                value="Contract fake publish failure",
                value_type="string",
                category="audit",
            ),
        ]
    )

    account = AccountModel(
        id="draft-publish-fake-failure",
        name="Fake Failure Account",
        positioning="contract positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    draft = ArticleDraftModel(
        task_id="draft-publish-fake-failure-task",
        account_id=account.id,
        title="Fake Failure Draft",
        content_markdown="# Fake Failure Draft",
        word_count=20,
        draft_status="approved",
        publish_status="not_published",
        source_type="semi_auto_task",
    )
    config = WeChatConfigModel(
        account_id=account.id,
        app_id="wx-fake-failure",
        app_secret="wx-fake-failure-secret",
        is_enabled=True,
        default_author="HotClaw",
    )
    db_session.add_all([account, draft, config])
    await db_session.commit()

    response = await client.post(f"/api/v1/drafts/{draft.id}/publish-to-wechat")

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == 9004
    assert "Contract fake publish failure" in payload["message"]
