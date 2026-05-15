import pytest
from httpx import AsyncClient


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {row["capability_id"]: row for row in rows}


@pytest.mark.asyncio
async def test_list_platform_capabilities_returns_builtin_defaults(client: AsyncClient):
    response = await client.get("/api/v1/platform-capabilities", params={"content_platform": "xhs"})

    assert response.status_code == 200
    body = response.json()
    rows = _by_id(body["capabilities"])

    assert body["total"] == 3
    assert body["enabled_count"] == 3
    assert body["builtin_count"] == 3
    assert set(rows) == {
        "xiaohongshu.analysis.image_text_account",
        "xiaohongshu.layout.cover_cards",
        "xiaohongshu.recommendation.note_scout",
    }
    assert rows["xiaohongshu.recommendation.note_scout"]["source"] == "builtin"
    assert rows["xiaohongshu.recommendation.note_scout"]["content_platform"] == "xiaohongshu"
    assert rows["xiaohongshu.recommendation.note_scout"]["status"] == "active"


@pytest.mark.asyncio
async def test_create_custom_platform_capability(client: AsyncClient):
    response = await client.post(
        "/api/v1/platform-capabilities",
        json={
            "capability_id": "xiaohongshu.publish.mock_bridge",
            "content_platform": "rednote",
            "capability_type": "publish",
            "name": "Mock publish bridge",
            "description": "Test-only publisher adapter.",
            "config_json": {"adapter": "mock", "supports_draft": True},
            "prompt_overrides_json": {"post_process": "Prepare a publish-ready note."},
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["capability_id"] == "xiaohongshu.publish.mock_bridge"
    assert created["content_platform"] == "xiaohongshu"
    assert created["capability_type"] == "publish"
    assert created["is_builtin"] is False
    assert created["source"] == "custom"
    assert created["config_json"] == {"adapter": "mock", "supports_draft": True}

    list_response = await client.get("/api/v1/platform-capabilities", params={"content_platform": "xiaohongshu"})
    rows = _by_id(list_response.json()["capabilities"])
    assert rows["xiaohongshu.publish.mock_bridge"]["source"] == "custom"

    generated_response = await client.post(
        "/api/v1/platform-capabilities",
        json={
            "content_platform": "小红书",
            "capability_type": "recommendation",
            "name": "中文能力名",
        },
    )
    assert generated_response.status_code == 201
    generated = generated_response.json()
    assert generated["capability_id"].startswith("xiaohongshu.recommendation.")
    assert generated["content_platform"] == "xiaohongshu"


@pytest.mark.asyncio
async def test_override_builtin_platform_capability_merges_defaults(client: AsyncClient):
    response = await client.put(
        "/api/v1/platform-capabilities/xiaohongshu.recommendation.note_scout",
        json={
            "name": "Overridden note scout",
            "config_json": {"output_shape": "custom_note_package", "extra_flag": True},
            "prompt_overrides_json": {"recommendation": "Use the custom note scout contract."},
        },
    )

    assert response.status_code == 200
    overridden = response.json()
    assert overridden["is_builtin"] is True
    assert overridden["source"] == "overridden"
    assert overridden["name"] == "Overridden note scout"
    assert overridden["config_json"]["source_types"] == [
        "xiaohongshu_note_scout",
        "reference_source",
        "public_search",
    ]
    assert overridden["config_json"]["output_shape"] == "custom_note_package"
    assert overridden["config_json"]["extra_flag"] is True
    assert overridden["prompt_overrides_json"]["recommendation"] == "Use the custom note scout contract."

    list_response = await client.get("/api/v1/platform-capabilities", params={"content_platform": "xhs"})
    rows = _by_id(list_response.json()["capabilities"])
    assert rows["xiaohongshu.recommendation.note_scout"]["source"] == "overridden"


@pytest.mark.asyncio
async def test_delete_and_restore_builtin_platform_capability(client: AsyncClient):
    capability_id = "xiaohongshu.layout.cover_cards"

    delete_response = await client.delete(f"/api/v1/platform-capabilities/{capability_id}")
    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["status"] == "deleted"
    assert deleted["is_enabled"] is False

    hidden_response = await client.get("/api/v1/platform-capabilities", params={"content_platform": "xiaohongshu"})
    assert capability_id not in _by_id(hidden_response.json()["capabilities"])

    deleted_response = await client.get(
        "/api/v1/platform-capabilities",
        params={"content_platform": "xiaohongshu", "include_deleted": True},
    )
    assert _by_id(deleted_response.json()["capabilities"])[capability_id]["status"] == "deleted"

    restore_response = await client.post(f"/api/v1/platform-capabilities/{capability_id}/restore")
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["status"] == "active"
    assert restored["is_enabled"] is True

    effective_response = await client.get("/api/v1/platform-capabilities/effective/xiaohongshu")
    effective_rows = _by_id(effective_response.json()["capabilities"])
    assert effective_rows[capability_id]["status"] == "active"


@pytest.mark.asyncio
async def test_effective_platform_capabilities_groups_by_type_and_prompt_hints(client: AsyncClient):
    create_response = await client.post(
        "/api/v1/platform-capabilities",
        json={
            "capability_id": "xiaohongshu.recommendation.custom_prompt",
            "content_platform": "xiaohongshu",
            "capability_type": "recommendation",
            "name": "Custom prompt recommendation",
            "prompt_overrides_json": {
                "recommendation": "Custom recommendation prompt hint.",
                "post_process": "Custom post process prompt hint.",
            },
        },
    )
    assert create_response.status_code == 201

    response = await client.get("/api/v1/platform-capabilities/effective/red")

    assert response.status_code == 200
    body = response.json()
    assert body["content_platform"] == "xiaohongshu"

    recommendation_ids = {
        row["capability_id"]
        for row in body["by_type"]["recommendation"]
    }
    assert "xiaohongshu.recommendation.note_scout" in recommendation_ids
    assert "xiaohongshu.recommendation.custom_prompt" in recommendation_ids
    assert "Custom recommendation prompt hint." in body["prompt_hints"]["recommendation"]
    assert "Custom post process prompt hint." in body["prompt_hints"]["post_process"]
    assert any("小红书图文笔记" in hint for hint in body["prompt_hints"]["recommendation"])
