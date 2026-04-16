# 2026-04-16 Most Stable Runtime

This document records the most stable ECS runtime state confirmed on 2026-04-16 (Beijing time), plus the rollback path.

## Naming

- Stable runtime name: `stable-20260416`
- Today's large-change branch: `improve`
- Stable runtime code baseline: `04996be` (`codex/sealos-devbox-deploy`)

## Confirmed Stable ECS Runtime

- Frontend image: `crpi-o9gekzkp7uuce95d.cn-hangzhou.personal.cr.aliyuncs.com/hotclaw/frontend:20260415-fix2`
- Backend image: `crpi-o9gekzkp7uuce95d.cn-hangzhou.personal.cr.aliyuncs.com/hotclaw/backend:20260415`
- Redis image: `crpi-o9gekzkp7uuce95d.cn-hangzhou.personal.cr.aliyuncs.com/hotclaw/redis:7-alpine`
- Data mount: `/opt/hotclaw/data:/app/data`

## Required Backend Runtime Flags

The backend is considered stable only when started with these runtime guards:

- `HOTCLAW_ENABLE_SYSTEM_CONFIG_INIT=0`
- `HOTCLAW_ENABLE_SCHEDULER=0`
- Clear inherited proxy variables inside the container:
  - `HTTP_PROXY=`
  - `HTTPS_PROXY=`
  - `ALL_PROXY=`
  - `http_proxy=`
  - `https_proxy=`
  - `all_proxy=`
- Add `NO_PROXY` and `no_proxy` for internal services and WeChat:
  - `localhost,127.0.0.1,backend,hotclaw-backend,hotclaw-redis,redis,api.weixin.qq.com`

## Stable Backend Run Command

```bash
docker rm -f hotclaw-backend

docker run -d \
  --name hotclaw-backend \
  --network hotclaw-net \
  --network-alias backend \
  --restart unless-stopped \
  -p 8140:8140 \
  --env-file /opt/hotclaw/backend.env \
  -e APP_ENV=production \
  -e APP_DEBUG=false \
  -e APP_HOST=0.0.0.0 \
  -e APP_PORT=8140 \
  -e DATABASE_URL=sqlite+aiosqlite:////app/data/hotclaw.db \
  -e REDIS_URL=redis://hotclaw-redis:6379/0 \
  -e HOTCLAW_ENABLE_SCHEDULER=0 \
  -e HOTCLAW_ENABLE_SYSTEM_CONFIG_INIT=0 \
  -e HOTCLAW_AUTO_CREATE_TABLES=0 \
  -e HTTP_PROXY= \
  -e HTTPS_PROXY= \
  -e ALL_PROXY= \
  -e http_proxy= \
  -e https_proxy= \
  -e all_proxy= \
  -e NO_PROXY=localhost,127.0.0.1,backend,hotclaw-backend,hotclaw-redis,redis,api.weixin.qq.com \
  -e no_proxy=localhost,127.0.0.1,backend,hotclaw-backend,hotclaw-redis,redis,api.weixin.qq.com \
  -v /opt/hotclaw/data:/app/data \
  crpi-o9gekzkp7uuce95d.cn-hangzhou.personal.cr.aliyuncs.com/hotclaw/backend:20260415
```

## Health Check

```bash
docker logs --tail 100 hotclaw-backend
curl http://127.0.0.1:8140/api/v1/health
curl http://127.0.0.1:8140/api/v1/accounts
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected signal:

- `Application startup complete`
- `Uvicorn running on http://0.0.0.0:8140`
- `/api/v1/health` returns `200`
- `/api/v1/accounts` returns JSON

## WeChat Notes

- If WeChat test returns `All connection attempts failed`, first inspect container proxy variables:

```bash
docker exec hotclaw-backend sh -c 'env | grep -i proxy || true'
```

- If WeChat returns `40164 invalid ip`, add the ECS public IP to the WeChat IP whitelist.
- Confirmed whitelist IP on 2026-04-16: `114.55.168.65`

## Rollback Strategy

If a new backend image or startup change causes accounts to disappear, health checks to fail, or WeChat connectivity to regress:

1. Remove the current backend container.
2. Re-run the stable backend command above exactly as-is.
3. Re-check `/api/v1/health` and `/api/v1/accounts`.
4. Only after that, retry feature-specific debugging.

## Non-Stable Hotfix Note

The WeChat hotfix branch `wechat-token-hotfix` contains the `trust_env=False` retry hardening, but its first image attempt was not safe to deploy directly because it was built on a baseline that did not match the ECS database migration head (`20260414_0007`).

Before deploying that fix again, rebuild it on top of a baseline that includes the current migration head.
