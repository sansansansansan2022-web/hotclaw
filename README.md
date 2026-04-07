<div align="center">
  <img src="./frontend/public/images/hotclaw-hero.png" alt="HotClaw" width="100%" />

  # HotClaw

  **Multi-Agent Content Production Platform for WeChat Official Accounts**

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
  [![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
</div>

---

## 项目简介

HotClaw 是一个面向微信公众号内容生产与运营的全栈平台。系统围绕“账号托管 -> 任务编排 -> 草稿审核 -> 微信发布”构建，既支持人工介入，也支持半自动和全自动运营模式。

当前仓库包含：

- `backend/`: FastAPI + SQLAlchemy + Pydantic 的业务后端
- `frontend/`: Next.js 16 + React 19 + TailwindCSS + Zustand 的控制台前端

---

## 当前能力

### 1. 多 Agent 内容工作流

- 6 个核心 Agent 链路：`Profile -> HotTopic -> Topic -> Title -> Content -> Audit`
- 基于 Task 的编排与节点追踪
- 支持任务历史、节点执行明细、失败重跑

### 2. 三种运营模式

| 模式 | 行为 |
| --- | --- |
| `manual` | 手动触发任务，只生成内部草稿 |
| `semi_auto` | 自动生成草稿，进入 `pending_review`，人工确认后再发布 |
| `full_auto` | 任务完成后在满足规则时自动触发微信发布 |

### 3. 草稿工作流

- Draft 状态：`draft` / `pending_review` / `approved` / `rejected` / `discarded` / `published`
- 支持确认发布、拒绝、丢弃、从草稿重跑任务
- 草稿详情页可查看审核结果、发布记录和允许的后续动作

### 4. 微信公众号发布基础设施

- 每个账号绑定独立微信公众号配置
- 测试公众号连接
- Access Token 获取与数据库缓存
- 正文图片上传与 HTML 图片替换
- 封面素材上传
- 创建微信草稿并提交发布
- 发布记录落库、状态追踪、重试入口

### 5. 控制台前端

- 统一 Shell：侧边栏、顶部栏、内容区、全局 Toast
- 关键页面：
  - `/login`
  - `/dashboard`
  - `/workspace`
  - `/accounts`
  - `/accounts/new`
  - `/accounts/[id]`
  - `/accounts/[id]/edit`
  - `/drafts`
  - `/drafts/[id]`
  - `/publish-logs`
  - `/tasks/history`
  - `/settings`
  - `/settings/wechat`
- 已支持全局语言切换：`English` / `中文`
- 全局 Toast 默认展示 5 秒后自动消失，同时支持手动关闭

---

## 最近更新

### 2026-04

- 重建前端控制台结构，统一到 `frontend/components/console/*`
- 接入微信公众号发布服务、配置服务、发布记录与相关测试
- 新增全局语言设置，使用后端 `system-configs` 持久化 `ui_language`
- 关键控制台页面支持中英文切换
- 全局 Toast 调整为 5 秒后自动消失

---

## 技术栈

### 后端

- FastAPI
- SQLAlchemy Async
- Pydantic v2
- Alembic
- APScheduler
- httpx
- SQLite 默认开发库
- 支持通过 `database_url` 切换到其他 SQLAlchemy 异步数据库配置

### 前端

- Next.js 16
- React 19
- TypeScript
- TailwindCSS
- Zustand

---

## 目录结构

```text
hotclaw/
├─ backend/
│  ├─ app/
│  │  ├─ agents/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ db/
│  │  ├─ models/
│  │  ├─ orchestrator/
│  │  ├─ scheduler/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  └─ main.py
│  ├─ alembic/
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/
│  ├─ app/
│  ├─ components/
│  │  ├─ command-center/
│  │  ├─ console/
│  │  └─ providers/
│  ├─ lib/
│  ├─ public/
│  ├─ store/
│  └─ types/
└─ README.md
```

---

## 快速启动

### 环境要求

- Python 3.11+
- Node.js 18+

### 1. 克隆项目

```bash
git clone https://github.com/sansansansansan2022-web/hotclaw.git
cd hotclaw
```

### 2. 启动后端

```bash
cd backend

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8000
```

说明：

- 后端会在启动时自动初始化数据库表和默认系统配置
- 默认数据库是 `backend/hotclaw.db`
- 配置文件读取路径是 `backend/.env`

### 3. 启动前端

```bash
cd frontend
npm install

# PowerShell
$env:NEXT_PUBLIC_HOTCLAW_API_ORIGIN="http://127.0.0.1:8000"
npm run dev
```

### 4. 访问地址

- Frontend: [http://127.0.0.1:3000](http://127.0.0.1:3000)
- Backend API: [http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1)
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 常用命令

### 后端

```bash
cd backend

# 运行全部测试
pytest -q

# 运行微信相关测试
pytest tests/test_wechat_config_api.py tests/test_wechat_publish_service.py tests/test_wechat_draft_workflow.py -q

# 运行 e2e 测试
pytest tests/e2e -q
```

### 前端

```bash
cd frontend

# 类型检查（项目里 lint 脚本即 tsc）
npm run lint

# 生产构建
npm run build

# 本地开发
npm run dev
```

---

## 微信发布链路说明

当前工程里，微信公众号发布能力已经是系统基础设施的一部分，而不是独立 demo。

核心路径：

1. 账号绑定微信公众号配置
2. 测试连接并缓存 access token
3. 草稿进入允许发布的状态
4. 走 `publish_decision_service` 做前置检查
5. 上传正文图片 / 封面素材
6. 创建微信草稿
7. 提交微信发布
8. 写入 `publish_records`
9. 在草稿详情和发布日志中追踪状态

---

## 前端全局语言设置

控制台现在支持 `English` 和 `中文` 切换。

实现方式：

- 前端通过 Zustand 保存当前语言
- 后端通过 `system-configs` 保存全局值 `ui_language`
- 根布局启动时自动同步后端设置
- 顶部栏和 Settings 页面都可以切换语言

---

## 当前文档约定

下面这些目录当前不作为发布源码的一部分：

- `.qoder/`
- `output/`
- `tmp/`

它们可能包含本地生成文档、截图或调试输出，不应默认纳入提交。

---

## 许可证

MIT License。详见 [LICENSE](LICENSE)。

