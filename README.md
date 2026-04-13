# HotClaw

HotClaw is a FastAPI + Next.js content operations platform for WeChat official accounts.  
The current codebase centers on four product objects:

- `Account`: account profile, positioning, operating mode, WeChat config
- `Task`: a single generation run with node-level execution history
- `Draft`: generated article content plus review and publish actions
- `Skill`: runtime research capabilities that agents can call during execution

## What It Does

HotClaw currently supports:

- Multi-agent generation flow for profile parsing, topic discovery, topic planning, title generation, content writing, and auditing
- Task orchestration with execution logs, reruns, node status, and terminal failure visibility
- Draft review workflow with confirm, reject, discard, rerun, and publish-related state transitions
- WeChat publishing infrastructure with config testing, publish records, retry paths, and status sync
- Research skill integration for:
  - GitHub repository curation via the real GitHub REST API
  - Scholar-style paper search via OpenAlex + Crossref adapters
- Settings management for providers, agents, skills, and WeChat configuration
- Local development startup scripts for Windows and Sealos DevBox

## Tech Stack

### Backend

- Python 3.11+
- FastAPI
- SQLAlchemy Async
- Alembic
- Pydantic v2
- httpx
- litellm
- SQLite by default

### Frontend

- Node.js 18+
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- Zustand

## Repository Layout

```text
hotclaw/
|- backend/
|  |- app/
|  |  |- agents/
|  |  |- api/
|  |  |- core/
|  |  |- models/
|  |  |- orchestrator/
|  |  |- schemas/
|  |  |- services/
|  |  `- skills/
|  |- alembic/
|  `- tests/
|- frontend/
|  |- app/
|  |- components/
|  |- lib/
|  |- public/
|  `- types/
|- docs/
|- scripts/
`- tests/
```

## Quick Start

### 1. Clone

```bash
git clone https://github.com/sansansansansan2022-web/hotclaw.git
cd hotclaw
```

### 2. Configure Environment

Copy the example environment file and fill in the values you actually need:

```bash
cp .env.example backend/.env
```

At minimum for normal local startup:

- `DATABASE_URL`
- `LLM_API_KEY`
- `LLM_API_BASE_URL`
- `LLM_MODEL_NAME`

If you want runtime research skills:

- GitHub skill:
  - `ENABLE_GITHUB_SKILL=true`
  - `GITHUB_TOKEN`
- Scholar skill:
  - `ENABLE_SCHOLAR_SKILL=true`
  - `SCHOLAR_PROVIDER=openalex+crossref`
  - `OPENALEX_API_KEY`
  - recommended: `OPENALEX_MAILTO`, `CROSSREF_MAILTO`

HotClaw does not fall back to fake data when these research skill configs are missing.  
If a skill is enabled but its required config is absent, the call fails explicitly.

## Local Development

### Recommended Windows Startup

The fastest supported local startup path is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

Default local ports:

- Frontend: [http://127.0.0.1:3460](http://127.0.0.1:3460)
- Backend health: [http://127.0.0.1:8140/api/v1/health](http://127.0.0.1:8140/api/v1/health)
- Backend docs: [http://127.0.0.1:8140/docs](http://127.0.0.1:8140/docs)

What this script does:

- stops stale local frontend/backend processes
- runs Alembic migrations
- builds or starts the frontend
- starts the backend
- writes logs to `output/local-runtime/`

Useful options:

```powershell
# Disable scheduler noise for a local debug session
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -DisableScheduler

# Force frontend dev mode
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -FrontendMode Dev
```

Stop local processes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

### Manual Startup

#### Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
```

PowerShell:

```powershell
$env:NEXT_PUBLIC_HOTCLAW_API_ORIGIN="http://127.0.0.1:8000"
npm run dev
```

Bash:

```bash
NEXT_PUBLIC_HOTCLAW_API_ORIGIN=http://127.0.0.1:8000 npm run dev
```

## Sealos DevBox Deployment

HotClaw can run inside Sealos DevBox with only the frontend port exposed publicly.

Startup command:

```bash
bash scripts/start-devbox.sh
```

Recommended DevBox environment:

```bash
HOTCLAW_FRONTEND_MODE=auto
HOTCLAW_BACKEND_PORT=8000
HOTCLAW_FRONTEND_PORT=3000
HOTCLAW_ENABLE_SCHEDULER=0
HOTCLAW_API_ORIGIN=http://127.0.0.1:8000
```

Important notes:

- expose port `3000`
- keep the backend internal on `8000`
- use the generated Sealos public domain or a real custom domain you own
- do not try to bind the app to the Sealos console domain itself

See [docs/sealos-devbox.md](/D:/project/hotclaw/docs/sealos-devbox.md) for the deployment notes currently bundled in the repo.

## Runtime Research Skills

Two runtime skills are wired into the backend:

- `github_project_curator_skill`
- `scholar_paper_search_skill`

They are designed to:

- be registered as first-class skills
- run through the backend skill runtime service
- persist invocation logs
- persist evidence items
- write evidence back into workspace context for downstream agents

Related debug endpoints:

- `POST /api/v1/skills/github/curate`
- `POST /api/v1/skills/scholar/search`
- `GET /api/v1/tasks/{task_id}/evidence`
- `GET /api/v1/tasks/{task_id}/skill-invocations`

## Common Commands

### Backend

```bash
cd backend

# all backend tests
pytest -q

# focused skill runtime tests
pytest tests/test_skill_runtime_contract.py -q
```

### Frontend

```bash
cd frontend

# type check
npm run lint

# production build
npm run build

# local dev
npm run dev
```

### Root E2E

```bash
npm run test:e2e
```

## Notes About Generated Files

These directories are not part of the product source of truth:

- `.qoder/`
- `output/`
- `tmp/`
- `.playwright-cli/`

They may contain local artifacts, generated docs, runtime logs, browser automation traces, or debug output.

## License

MIT. See [LICENSE](LICENSE).
