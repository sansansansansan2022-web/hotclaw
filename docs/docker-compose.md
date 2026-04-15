# HotClaw Docker Compose

## Files

- `backend/Dockerfile`: backend runtime image
- `frontend/Dockerfile`: frontend runtime image
- `docker-compose.yml`: one-command local/prod-style startup

## Default ports

- Frontend: `3460`
- Backend: `8140`
- Redis: internal only

## Before first start

1. Make sure `backend/.env` exists.
2. Put your LLM and optional skill credentials in `backend/.env`.
3. If you want SQLite, the compose file will store it in the named volume at `/app/data/hotclaw.db`.
4. If you want PostgreSQL instead, override `HOTCLAW_DOCKER_DATABASE_URL` before startup.

## Start

```bash
docker compose up -d --build
```

## Check status

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

## Stop

```bash
docker compose down
```

## Stop and remove persisted data

```bash
docker compose down -v
```

## Notes

- Backend container runs `python -m alembic upgrade head` before starting `uvicorn`.
- Frontend container uses Next.js production mode and proxies `/api/*` to the backend container through `HOTCLAW_API_ORIGIN`.
- The frontend image intentionally does not expose `NEXT_PUBLIC_HOTCLAW_API_ORIGIN`, so browser requests stay same-origin and go through the Next.js rewrite layer.
- Docker-only overrides use `HOTCLAW_DOCKER_*` names to avoid accidentally inheriting your local dev `DATABASE_URL` or `REDIS_URL`.
