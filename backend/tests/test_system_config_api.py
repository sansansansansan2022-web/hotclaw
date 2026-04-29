import pytest
from httpx import AsyncClient

from app.services.system_config_service import init_default_configs


@pytest.mark.asyncio
async def test_image_generation_test_requires_api_key(client: AsyncClient, db_session):
    await init_default_configs(db_session)

    response = await client.post(
        "/system-configs/image-generation/test",
        json={
            "provider": "dashscope",
            "model": "wan2.7-image",
            "base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
            "api_key": "",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error_message"] == "API Key is required"


@pytest.mark.asyncio
async def test_image_generation_test_rejects_unwired_provider(client: AsyncClient, db_session):
    await init_default_configs(db_session)

    response = await client.post(
        "/system-configs/image-generation/test",
        json={
            "provider": "stability",
            "model": "stable-image-core",
            "base_url": "https://api.stability.ai/v2beta/stable-image/generate/core",
            "api_key": "sk-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "not wired yet" in body["error_message"]
