from app.services.reference_source_service import reference_source_service


async def _create_account(client, name: str) -> str:
    response = await client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "positioning": f"{name} focuses on practical operator content for a scoped audience.",
            "operation_mode": "manual",
        },
    )
    assert response.status_code == 201
    return response.json()["account_id"]


async def test_reference_sources_are_account_scoped_and_account_detail_has_summary(client):
    account_a = await _create_account(client, "Reference Account A")
    account_b = await _create_account(client, "Reference Account B")

    create_a = await client.post(
        f"/api/v1/accounts/{account_a}/reference-sources",
        json={
            "source_type": "article_url",
            "name": "A URL Source",
            "source_value": "https://example.com/a",
        },
    )
    assert create_a.status_code == 201

    create_b = await client.post(
        f"/api/v1/accounts/{account_b}/reference-sources",
        json={
            "source_type": "wechat_account",
            "name": "B WeChat Source",
            "source_value": "legacy-growth-lab",
        },
    )
    assert create_b.status_code == 201

    list_a = await client.get(f"/api/v1/accounts/{account_a}/reference-sources")
    assert list_a.status_code == 200
    body_a = list_a.json()
    assert body_a["total"] == 1
    assert body_a["sources"][0]["name"] == "A URL Source"

    detail_a = await client.get(f"/api/v1/accounts/{account_a}")
    assert detail_a.status_code == 200
    assert detail_a.json()["reference_source_count"] == 1
    assert detail_a.json()["reference_source_enabled_count"] == 1
    assert detail_a.json()["reference_source_last_sync_status"] == "pending"


async def test_reference_source_can_be_disabled_and_manual_source_syncs_as_manual_only(client):
    account_id = await _create_account(client, "Manual Reference Account")

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/reference-sources",
        json={
            "source_type": "pasted_article",
            "source_value": "This is a long pasted article body used as a manual reference source for onboarding and later reviews.",
            "notes": "Seeded from onboarding.",
        },
    )
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]
    assert create_response.json()["sync_status"] == "manual_only"

    patch_response = await client.patch(
        f"/api/v1/accounts/{account_id}/reference-sources/{source_id}",
        json={"is_enabled": False},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["is_enabled"] is False

    sync_response = await client.post(
        f"/api/v1/accounts/{account_id}/reference-sources/{source_id}/sync"
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["source"]["sync_status"] == "manual_only"
    assert sync_response.json()["source"]["article_count"] == 1
    assert "manual-only" in sync_response.json()["message"].lower()


async def test_article_url_reference_source_sync_updates_status(client, monkeypatch):
    account_id = await _create_account(client, "URL Sync Account")

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/reference-sources",
        json={
            "source_type": "article_url",
            "source_value": "https://example.com/sync-me",
        },
    )
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    async def _fake_fetch_success(_source_value: str):
        return (
            {
                "resolved_title": "Example Article",
                "content_length": 1200,
                "preview": "A synced article preview",
            },
            None,
        )

    monkeypatch.setattr(reference_source_service, "_fetch_article_url_source", _fake_fetch_success)

    sync_response = await client.post(
        f"/api/v1/accounts/{account_id}/reference-sources/{source_id}/sync"
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["source"]["sync_status"] == "synced"
    assert sync_response.json()["source"]["article_count"] == 1
    assert sync_response.json()["source"]["metadata_json"]["resolved_title"] == "Example Article"


async def test_article_url_reference_source_sync_failure_is_visible(client, monkeypatch):
    account_id = await _create_account(client, "URL Failure Account")

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/reference-sources",
        json={
            "source_type": "article_url",
            "source_value": "https://example.com/fail-me",
        },
    )
    assert create_response.status_code == 201
    source_id = create_response.json()["id"]

    async def _fake_fetch_failure(_source_value: str):
        return ({}, "Unable to fetch article source.")

    monkeypatch.setattr(reference_source_service, "_fetch_article_url_source", _fake_fetch_failure)

    sync_response = await client.post(
        f"/api/v1/accounts/{account_id}/reference-sources/{source_id}/sync"
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["source"]["sync_status"] == "failed"
    assert sync_response.json()["source"]["latest_error_message"] == "Unable to fetch article source."
