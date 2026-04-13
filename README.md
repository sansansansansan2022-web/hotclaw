# HotClaw - 热爪智能内容运营平台

<!--
  HotClaw README 中文说明
  ======================
  本文件是 HotClaw 项目的中文说明文档。

  HotClaw 是一个基于 FastAPI + Next.js 的微信公众号内容运营平台。
  当前代码库围绕四个核心产品对象展开：

  1. Account（账号）：账号画像、定位、运营模式、微信配置
  2. Task（任务）：单次内容生成运行，包含节点级执行历史
  3. Draft（草稿）：生成的稿件内容，以及审核、发布相关操作
  4. Skill（技能）：运行时研究能力，Agent 在执行过程中可调用

  主要功能：
  - 多 Agent 生成流程：画像解析 → 话题发现 → 话题规划 → 标题生成 → 内容写作 → 审核
  - 任务编排：执行日志、重跑、节点状态、终端失败可见性
  - 草稿审核工作流：确认发布、拒绝、废弃、重跑、发布状态转换
  - 微信发布基础设施：配置测试、发布记录、重试路径、状态同步
  - 研究技能集成：GitHub 仓库整理、学术论文搜索
  - 设置管理：提供商、Agent、技能、微信配置
  - 本地开发和 Sealos DevBox 部署脚本
-->

<!-- 项目简介（英文保留以便国际开发者阅读） -->
HotClaw is a FastAPI + Next.js content operations platform for WeChat official accounts.
The current codebase centers on four product objects:

- `Account`: account profile, positioning, operating mode, WeChat config
- `Task`: a single generation run with node-level execution history
- `Draft`: generated article content plus review and publish actions
- `Skill`: runtime research capabilities that agents can call during execution

<!-- 功能说明 -->
## What It Does / 功能说明

HotClaw 当前支持以下功能：

- **多 Agent 生成流程**：画像解析、话题发现、话题规划、标题生成、内容写作、审核
- **任务编排**：执行日志、重跑、节点状态、终端失败可见性
- **草稿审核工作流**：确认发布、拒绝、废弃、重跑、发布状态转换
- **微信发布基础设施**：配置测试、发布记录、重试路径、状态同步
- **研究技能集成**：
  - GitHub 仓库整理（通过真实 GitHub REST API）
  - 学术论文搜索（通过 OpenAlex + Crossref 适配器）
- **设置管理**：提供商、Agent、技能、微信配置
- **本地开发和 Sealos DevBox 部署脚本**

<!-- 技术栈 -->
## Tech Stack / 技术栈

### Backend / 后端

- Python 3.11+
- FastAPI（高性能 Web 框架）
- SQLAlchemy Async（异步 ORM）
- Alembic（数据库迁移工具）
- Pydantic v2（数据验证）
- httpx（异步 HTTP 客户端）
- litellm（LLM 统一接口）
- SQLite by default（默认使用 SQLite）

### Frontend / 前端

- Node.js 18+
- Next.js 16
- React 19
- TypeScript（类型安全）
- Tailwind CSS（样式框架）
- Zustand（状态管理）

<!-- 仓库结构 -->
## Repository Layout / 仓库结构

```text
hotclaw/
|- backend/                    # 后端目录
|  |- app/
|  |  |- agents/               # Agent 智能体模块
|  |  |- api/                  # API 路由
|  |  |- core/                 # 核心配置、异常
|  |  |- models/               # 数据库模型
|  |  |- orchestrator/         # 任务编排引擎
|  |  |- schemas/              # Pydantic 数据模型
|  |  |- services/             # 业务服务层
|  |  `- skills/               # 技能模块（外部技能、适配器、排序器）
|  |- alembic/                 # 数据库迁移
|  `- tests/                   # 后端测试
|- frontend/                   # 前端目录
|  |- app/                    # Next.js App Router 页面
|  |- components/             # React 组件
|  |- lib/                    # 工具库、API 调用
|  |- public/                 # 静态资源
|  `- types/                  # TypeScript 类型定义
|- docs/                      # 文档目录
|- scripts/                   # 启动脚本
`- tests/                     # 端到端测试
```

<!-- 快速开始 -->
## Quick Start / 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/sansansansansan2022-web/hotclaw.git
cd hotclaw
```

### 2. 配置环境变量

复制示例环境文件并填写实际需要的值：

```bash
cp .env.example backend/.env
```

本地启动的最小配置：

- `DATABASE_URL` - 数据库连接字符串
- `LLM_API_KEY` - LLM API 密钥
- `LLM_API_BASE_URL` - LLM API 地址
- `LLM_MODEL_NAME` - LLM 模型名称

如需运行时研究技能，还需配置：

- **GitHub 技能**：
  - `ENABLE_GITHUB_SKILL=true`
  - `GITHUB_TOKEN`
- **学术技能**：
  - `ENABLE_SCHOLAR_SKILL=true`
  - `SCHOLAR_PROVIDER=openalex+crossref`
  - `OPENALEX_API_KEY`
  - 推荐添加：`OPENALEX_MAILTO`、`CROSSREF_MAILTO`

> 注意：如果技能已启用但缺少必需配置，调用会明确失败，不会使用假数据降级。

<!-- 本地开发 -->
## Local Development / 本地开发

### 推荐 Windows 启动方式

最快的本地启动方式：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

默认本地端口：

- 前端：http://127.0.0.1:3460
- 后端健康检查：http://127.0.0.1:8140/api/v1/health
- 后端 API 文档：http://127.0.0.1:8140/docs

启动脚本功能：

- 停止旧的前端/后端进程
- 运行 Alembic 数据库迁移
- 构建或启动前端
- 启动后端
- 日志输出到 `output/local-runtime/`

常用选项：

```powershell
# 禁用调度器，减少本地调试噪音
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -DisableScheduler

# 强制使用前端开发模式
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -FrontendMode Dev
```

停止本地进程：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

### 手动启动

#### 后端启动

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

#### 前端启动

```bash
cd frontend
npm install
```

PowerShell：

```powershell
$env:NEXT_PUBLIC_HOTCLAW_API_ORIGIN="http://127.0.0.1:8000"
npm run dev
```

Bash：

```bash
NEXT_PUBLIC_HOTCLAW_API_ORIGIN=http://127.0.0.1:8000 npm run dev
```

<!-- Sealos DevBox 部署 -->
## Sealos DevBox Deployment / Sealos DevBox 部署

HotClaw 可以在 Sealos DevBox 中运行，只需将前端端口公开。

启动命令：

```bash
bash scripts/start-devbox.sh
```

推荐环境变量配置：

```bash
HOTCLAW_FRONTEND_MODE=auto      # 自动构建前端
HOTCLAW_BACKEND_PORT=8000       # 后端端口
HOTCLAW_FRONTEND_PORT=3000       # 前端端口
HOTCLAW_ENABLE_SCHEDULER=0       # 禁用调度器（演示用）
HOTCLAW_API_ORIGIN=http://127.0.0.1:8000
```

部署注意事项：

- 暴露端口 `3000`
- 后端保持在内部端口 `8000`
- 使用 Sealos 生成的公共域名或绑定自己的域名
- 不要尝试将应用绑定到 Sealos 控制台域名本身

详细部署说明请参阅 [docs/sealos-devbox.md](/D:/project/hotclaw/docs/sealos-devbox.md)。

<!-- 运行时研究技能 -->
## Runtime Research Skills / 运行时研究技能

两个运行时技能已接入后端：

- `github_project_curator_skill` - GitHub 仓库整理技能
- `scholar_paper_search_skill` - 学术论文搜索技能

它们的设计目标：

- 注册为一等公民技能
- 通过后端技能运行时服务执行
- 持久化调用日志
- 持久化证据项
- 将证据写回工作区上下文，供下游 Agent 使用

相关调试端点：

- `POST /api/v1/skills/github/curate`
- `POST /api/v1/skills/scholar/search`
- `GET /api/v1/tasks/{task_id}/evidence`
- `GET /api/v1/tasks/{task_id}/skill-invocations`

<!-- 常用命令 -->
## Common Commands / 常用命令

### 后端命令

```bash
cd backend

# 运行所有后端测试
pytest -q

# 运行技能运行时测试
pytest tests/test_skill_runtime_contract.py -q
```

### 前端命令

```bash
cd frontend

# 类型检查
npm run lint

# 生产构建
npm run build

# 本地开发
npm run dev
```

### 端到端测试

```bash
npm run test:e2e
```

<!-- 生成文件说明 -->
## Notes About Generated Files / 生成文件说明

以下目录不属于产品源代码：

- `.qoder/` - Qoder AI 助手工作目录
- `output/` - 输出日志目录
- `tmp/` - 临时文件目录
- `.playwright-cli/` - 浏览器自动化轨迹

它们可能包含本地工件、生成的文档、运行时日志、浏览器自动化跟踪或调试输出。

<!-- 许可证 -->
## License / 许可证

MIT. 详见 [LICENSE](LICENSE)。
