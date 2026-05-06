"""Tests for WeChat config API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from app.models.tables import AccountModel
from app.services.wechat_token_service import wechat_token_service


@pytest_asyncio.fixture
async def account(db_session):
    account = AccountModel(
        id="wechat-config-account",
        name="WeChat Config Account",
        positioning="测试定位",
        operation_mode="semi_auto",
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest.mark.asyncio
async def test_create_get_and_update_wechat_config(client, account):
    create_payload = {
        "app_id": "wx1234567890abcd",
        "app_secret": "very-secret-token",
        "default_author": "HotClaw",
        "need_open_comment": True,
        "only_fans_can_comment": False,
        "is_enabled": True,
    }

    create_response = await client.post(f"/api/v1/accounts/{account.id}/wechat-config", json=create_payload)
    assert create_response.status_code == 200
    create_data = create_response.json()["data"]
    assert create_data["account_id"] == account.id
    assert create_data["has_app_secret"] is True
    assert create_data["app_id_masked"].startswith("wx12")
    assert create_data["app_secret_masked"] != create_payload["app_secret"]

    get_response = await client.get(f"/api/v1/accounts/{account.id}/wechat-config")
    assert get_response.status_code == 200
    get_data = get_response.json()["data"]
    assert get_data["default_author"] == "HotClaw"
    assert get_data["is_enabled"] is True

    update_response = await client.put(
        f"/api/v1/accounts/{account.id}/wechat-config",
        json={"default_author": "Updated Author", "is_enabled": False},
    )
    assert update_response.status_code == 200
    update_data = update_response.json()["data"]
    assert update_data["default_author"] == "Updated Author"
    assert update_data["is_enabled"] is False


@pytest.mark.asyncio
async def test_test_connection_endpoint_updates_status(client, db_session, account, monkeypatch):
    create_payload = {
        "app_id": "wx-test-connection",
        "app_secret": "another-secret",
        "default_author": "Tester",
        "is_enabled": True,
    }
    create_response = await client.post(f"/api/v1/accounts/{account.id}/wechat-config", json=create_payload)
    assert create_response.status_code == 200

    tested_at = datetime.now(timezone.utc)
    monkeypatch.setattr(
        wechat_token_service,
        "test_connection",
        AsyncMock(
            return_value={
                "success": True,
                "message": "Connection successful",
                "tested_at": tested_at,
                "token_expires_at": tested_at,
            }
        ),
    )

    response = await client.post(f"/api/v1/accounts/{account.id}/wechat-config/test")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["success"] is True
    assert payload["message"] == "Connection successful"

    get_response = await client.get(f"/api/v1/accounts/{account.id}/wechat-config")
    assert get_response.status_code == 200
    config_data = get_response.json()["data"]
    assert config_data["last_test_status"] == "success"
    assert config_data["verified_at"] is not None
