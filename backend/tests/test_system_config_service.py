import pytest

from app.services.system_config_service import SystemConfigService, init_default_configs


@pytest.mark.asyncio
async def test_default_configs_include_image_generation_settings(db_session):
    await init_default_configs(db_session)

    service = SystemConfigService(db_session)

    provider = await service.get_by_key("image_generation_provider")
    model = await service.get_by_key("image_generation_model")
    api_key = await service.get_by_key("image_generation_api_key")
    base_url = await service.get_by_key("image_generation_base_url")
    presets = await service.get_typed_value("image_generation_provider_presets")

    assert provider is not None
    assert provider.value == "dashscope"
    assert provider.category == "image_assets"
    assert provider.is_system is True
    assert provider.requires_restart is False

    assert model is not None
    assert model.value == "wan2.7-image"
    assert model.category == "image_assets"
    assert model.description
    assert api_key is not None
    assert api_key.value == ""
    assert api_key.category == "image_assets"
    assert api_key.is_sensitive is True
    assert base_url is not None
    assert base_url.value == "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
    assert base_url.category == "image_assets"
    assert {item["provider_id"] for item in presets} >= {
        "dashscope",
        "openai",
        "google_vertex",
        "stability",
        "volcengine",
        "custom",
    }


@pytest.mark.asyncio
async def test_get_image_generation_config_returns_defaults(db_session):
    await init_default_configs(db_session)

    service = SystemConfigService(db_session)

    config = await service.get_image_generation_config()

    assert config["provider"] == "dashscope"
    assert config["model"] == "wan2.7-image"
    assert config["enabled"] is False
    assert config["api_key"] == ""
    assert config["base_url"] == "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
    assert {item["provider_id"] for item in config["provider_presets"]} >= {
        "dashscope",
        "openai",
        "google_vertex",
        "stability",
        "volcengine",
        "custom",
    }
