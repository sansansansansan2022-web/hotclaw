import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_xiaohongshu_mcp_server_is_registered(client: AsyncClient):
    response = await client.get("/api/v1/mcp/servers/xiaohongshu")

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == "xiaohongshu"
    assert body["command"] == "python"
    assert body["args"] == ["-m", "xhs_mcp_server"]
    assert body["env"]["phone"] == "${XIAOHONGSHU_PHONE_NUMBER}"
    assert body["package_name"] == "xhs-mcp-server"
    assert body["docs_url"] == "https://cloud.tencent.com/developer/mcp/server/10039"


@pytest.mark.asyncio
async def test_default_configs_include_xiaohongshu_mcp_settings(db_session):
    from app.services.system_config_service import SystemConfigService, init_default_configs

    await init_default_configs(db_session)
    service = SystemConfigService(db_session)

    enabled = await service.get_by_key("enable_xiaohongshu_mcp")
    phone = await service.get_by_key("xiaohongshu_phone_number")
    command = await service.get_by_key("xiaohongshu_mcp_command")

    assert enabled is not None
    assert enabled.category == "mcp"
    assert enabled.value == "false"
    assert enabled.requires_restart is True

    assert phone is not None
    assert phone.is_sensitive is True
    assert phone.category == "mcp"

    assert command is not None
    assert command.value == "python"
