# Sealos DevBox Quick Deploy

This project can be shared from Sealos DevBox by exposing only the frontend port.

## Why only one public port

- Frontend runs on port `3000`
- Backend runs on port `8000`
- The frontend proxies `/api/*` to `http://127.0.0.1:8000`
- Because both processes run inside the same DevBox, the backend does not need a public domain

## Recommended DevBox settings

- Runtime: Python 3.11+ and Node.js 20+
- Startup command:

```bash
bash scripts/start-devbox.sh
```

- Public service port: `3000`
- Domain: bind your Sealos public domain, for example `hzh.sealos.run`

## Optional environment variables

```bash
HOTCLAW_FRONTEND_MODE=auto
HOTCLAW_BACKEND_PORT=8000
HOTCLAW_FRONTEND_PORT=3000
HOTCLAW_ENABLE_SCHEDULER=0
HOTCLAW_API_ORIGIN=http://127.0.0.1:8000
```

## Notes

- `HOTCLAW_FRONTEND_MODE=auto` tries a production build first, then falls back to dev mode if needed.
- `HOTCLAW_ENABLE_SCHEDULER=0` is recommended for public demo or review environments.
- If you need real external integrations, add the required environment variables in the DevBox project settings instead of committing them into the repo.
