"""Static registry for external MCP servers known to HotClaw."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import settings


class MCPServerInfo(BaseModel):
    """Runtime-safe description of an MCP stdio server."""

    server_id: str
    name: str
    description: str
    transport: str = "stdio"
    enabled: bool = False
    command: str
    args: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    required_env: list[str] = Field(default_factory=list)
    package_name: str | None = None
    docs_url: str | None = None
    login_command: list[str] = Field(default_factory=list)
    inspector_command: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _env_value(value: str, placeholder: str) -> str:
    return value.strip() if value and value.strip() else placeholder


def _xiaohongshu_server() -> MCPServerInfo:
    phone_placeholder = "${XIAOHONGSHU_PHONE_NUMBER}"
    command = settings.xiaohongshu_mcp_command or "python"
    phone_value = _env_value(settings.xiaohongshu_phone_number, phone_placeholder)
    env = {"phone": phone_value}
    if settings.xiaohongshu_chromedriver_path:
        env["CHROMEDRIVER_PATH"] = settings.xiaohongshu_chromedriver_path

    return MCPServerInfo(
        server_id="xiaohongshu",
        name="小红书 MCP 发布器",
        description="XGenerationLab 的小红书内容发布 MCP server，用于后续小红书专属工作流。",
        enabled=bool(settings.enable_xiaohongshu_mcp),
        command=command,
        args=["-m", "xhs_mcp_server"],
        env=env,
        required_env=["XIAOHONGSHU_PHONE_NUMBER"],
        package_name="xhs-mcp-server",
        docs_url="https://cloud.tencent.com/developer/mcp/server/10039",
        login_command=["env", "phone=${XIAOHONGSHU_PHONE_NUMBER}", command, "-m", "xhs_mcp_server.__login__"],
        inspector_command=[
            "npx",
            "@modelcontextprotocol/inspector",
            "-e",
            "phone=${XIAOHONGSHU_PHONE_NUMBER}",
            command,
            "-m",
            "xhs_mcp_server",
        ],
        capabilities=["publish_note"],
        notes=[
            "首次使用前需要运行登录命令并输入短信验证码生成 cookies。",
            "本 server 依赖 Chrome/chromedriver；chromedriver 版本需要与本机 Chrome 主版本匹配。",
            "插件文档提示发布本地图片时可能出现请求超时，但帖子仍可能已经发送，工作流需要做二次状态校验。",
        ],
    )


def list_mcp_servers() -> list[MCPServerInfo]:
    """Return all MCP servers configured for HotClaw."""
    return [_xiaohongshu_server()]


def get_mcp_server(server_id: str) -> MCPServerInfo | None:
    """Return a single MCP server by ID."""
    normalized = server_id.strip().lower()
    return next((server for server in list_mcp_servers() if server.server_id == normalized), None)
