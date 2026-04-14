# HotClaw

HotClaw 是一个面向公众号账号运营的内容工作台，不只是“自动写稿工具”。

当前项目的主产品对象是：
- `Account`：账号工作区 / 内容资产容器
- `AutomationPlan`：自动化策略
- `ComposeSelectionSession`：一次“新建任务”的最小会话对象
- `Task`：系统运行实例
- `Draft`：内容产物

当前主路径已经从“账号直接 Run”切到：

`账号 -> 新建任务 -> 选推荐资讯 -> 选参考文章 -> 生成预览 -> 提交生成`

## 技术栈

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy Async
- Alembic
- Pydantic v2

### Frontend
- Node.js 18+
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- Zustand

## 仓库结构

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
|  `- types/
|- docs/
|- scripts/
`- tests/
```

## 当前产品能力

- 账号工作区：账号定位、参考源、自动化策略、历史任务/草稿/发布记录
- 新建任务：selection session、推荐资讯、参考文章入篮、compose preview、显式输入注入
- 任务执行：task runtime、node run、artifact-first 任务详情
- 草稿链路：draft 创建、审核、确认发布、发布状态追踪
- 研究能力：GitHub 仓库整理、学术论文搜索

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/sansansansansan2022-web/hotclaw.git
cd hotclaw
```

### 2. 配置后端环境变量

复制示例环境文件：

```bash
cp .env.example backend/.env
```

最小必需配置取决于你的 LLM provider。研究技能相关的额外配置：

- GitHub skill
  - `ENABLE_GITHUB_SKILL=true`
  - `GITHUB_TOKEN`
- Scholar skill
  - `ENABLE_SCHOLAR_SKILL=true`
  - `SCHOLAR_PROVIDER=openalex+crossref`
  - `OPENALEX_API_KEY`
  - 建议补充：`OPENALEX_MAILTO`、`CROSSREF_MAILTO`

注意：
- 缺少技能必需配置时，调用会明确失败
- 不会降级为 fake/mock 数据

## 本地开发

### 推荐的 Windows 启动方式

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

这条脚本现在的定位是：
- `稳定重启器`：停止旧进程、执行后端迁移、复用现有前端生产构建、重新拉起前后端
- `不是前端重建器`：这台 Windows 环境里，从脚本内部触发 Next.js rebuild 容易命中 `spawn EPERM`

默认端口：
- Frontend: `http://127.0.0.1:3460/accounts`
- Backend health: `http://127.0.0.1:8140/api/v1/health`
- Backend docs: `http://127.0.0.1:8140/docs`

日志目录：
- `output/local-runtime/`

### 前端重建 vs 本地重启

#### 只需要“本地重启”的场景

- 后端代码有改动
- 环境变量有改动
- 数据库迁移有改动
- 只是想把前后端重新拉起来

直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

#### 需要先“前端重建”的场景

- 改了 Next.js 页面、组件、样式
- 改了前端类型或前端数据结构
- 需要刷新 `.next` 里的生产构建产物

先进入 `frontend/` 手动执行：

```powershell
cd frontend
npm run lint
npm run build
```

再回到仓库根目录重启：

```powershell
cd ..
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

如果没有现成生产构建，`start-local.ps1` 会直接报清晰错误，提示你先在 `frontend/` 目录手动执行 `npm run lint` 和 `npm run build`。

### 常用选项

```powershell
# 禁用调度器，减少本地调试噪音
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -DisableScheduler

# 明确使用 Next 开发模式
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -FrontendMode Dev

# 显式表达“我要重建前端”
# 这台机器上脚本不会代你重建，而是提示你去 frontend/ 手动执行 lint + build
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -RebuildFrontend
```

停止本地进程：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

## 手动启动

### Backend

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

### Frontend

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

## Sealos DevBox

HotClaw 可以运行在 Sealos DevBox 中，推荐只暴露前端端口。

启动命令：

```bash
bash scripts/start-devbox.sh
```

推荐环境变量：

```bash
HOTCLAW_FRONTEND_MODE=auto
HOTCLAW_BACKEND_PORT=8000
HOTCLAW_FRONTEND_PORT=3000
HOTCLAW_ENABLE_SCHEDULER=0
HOTCLAW_API_ORIGIN=http://127.0.0.1:8000
```

部署说明见：
- [docs/sealos-devbox.md](D:/project/hotclaw/docs/sealos-devbox.md)

## Runtime Research Skills

已接入的运行时技能：
- `github_project_curator_skill`
- `scholar_paper_search_skill`

调试接口：
- `POST /api/v1/skills/github/curate`
- `POST /api/v1/skills/scholar/search`
- `GET /api/v1/tasks/{task_id}/evidence`
- `GET /api/v1/tasks/{task_id}/skill-invocations`

## 常用命令

### Backend

```bash
cd backend
pytest -q
pytest tests/test_skill_runtime_contract.py -q
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
npm run dev
```

### E2E

```bash
npm run test:e2e
```

## 运行产物说明

以下目录不属于核心源代码：
- `.qoder/`
- `output/`
- `tmp/`
- `.playwright-cli/`

它们可能包含：
- 本地运行日志
- 临时文件
- 浏览器自动化轨迹
- AI/调试工具产物

## 项目方向

HotClaw 的推进顺序已经明确：
1. 先把“新建任务”主路径跑顺
2. 再把任务节点产物 / artifact 可解释化补上
3. 再加显性的人工确认闸门
4. 再接真实账号运营数据
5. 最后补发布前质量层

也就是说，HotClaw 的目标是：

**围绕公众号账号做内容决策、创作协作、审核发布的运营工作台。**

