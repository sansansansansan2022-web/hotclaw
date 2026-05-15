"""MCP server configuration API routes."""

from fastapi import APIRouter, HTTPException

from app.mcp.server_registry import MCPServerInfo, get_mcp_server, list_mcp_servers

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


@router.get("/servers", response_model=list[MCPServerInfo])
async def list_servers() -> list[MCPServerInfo]:
    """List MCP servers known to HotClaw."""
    return list_mcp_servers()


@router.get("/servers/{server_id}", response_model=MCPServerInfo)
async def get_server(server_id: str) -> MCPServerInfo:
    """Get a single MCP server configuration."""
    server = get_mcp_server(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server
