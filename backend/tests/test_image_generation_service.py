"""Image generation runtime configuration tests."""

from app.services.image_generation_service import image_generation_service


def test_image_generation_respects_disabled_flag_even_with_api_key():
    config = {
        "provider": "dashscope",
        "model": "wan2.7-image",
        "api_key": "sk-test",
        "enabled": False,
    }

    runtime = image_generation_service._normalize_config(config)

    assert runtime["enabled"] is False
