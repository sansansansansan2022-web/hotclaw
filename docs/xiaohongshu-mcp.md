# 小红书 MCP 接入说明

HotClaw 已登记 `xiaohongshu` MCP server，后续小红书专属工作流可以通过 `/api/v1/mcp/servers/xiaohongshu` 读取启动配置。

来源：[腾讯云 MCP 广场 - 小红书MCP发布器](https://cloud.tencent.com/developer/mcp/server/10039)

## 环境变量

```bash
ENABLE_XIAOHONGSHU_MCP=true
XIAOHONGSHU_PHONE_NUMBER=你的手机号
XIAOHONGSHU_MCP_COMMAND=python
XIAOHONGSHU_MCP_TIMEOUT_SECONDS=120
XIAOHONGSHU_CHROMEDRIVER_PATH=
```

## 本地安装

```bash
cd backend
pip install -e ".[xiaohongshu]"
npx @puppeteer/browsers install chromedriver@你的 Chrome 版本
```

如 chromedriver 不在 PATH 中，把路径写入 `XIAOHONGSHU_CHROMEDRIVER_PATH`。

## 首次登录

```bash
env phone=你的手机号 python -m xhs_mcp_server.__login__
```

终端出现验证码提示后输入短信验证码。再次运行同一命令，如果显示 cookies 登录成功，就表示本地登录态可用。

## 调试 MCP server

```bash
npx @modelcontextprotocol/inspector -e phone=你的手机号 python -m xhs_mcp_server
```

插件文档说明：使用本地图片发布时，检查器里可能出现请求超时，但帖子仍可能已经发送。后续工作流要把“提交动作”和“发布状态确认”分开处理。
