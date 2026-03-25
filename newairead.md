# HotClaw 项目对话续接文档

> 本文件记录了 `d:\project\hotclaw\` 项目的核心架构、技术栈和最新进展，用于开启新对话时快速理解上下文。

---

## 一、项目概述

**HotClaw** 是一个基于**多智能体协作**的微信公众号内容生产平台。用户输入"账号定位"后，系统自动完成从热点抓取、选题策划、标题生成、正文撰写到审核风控的**全链路内容生产**。

### 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Next.js 16.2 + React 19 + TypeScript 5.9 + Turbopack |
| **后端** | FastAPI (Python) + SQLAlchemy 2.0 (异步) + Pydantic v2 |
| **数据库** | SQLite (开发) / PostgreSQL (生产) |
| **实时通信** | Server-Sent Events (SSE) |
| **样式** | Tailwind CSS 4.2 + 自定义像素动画 |
| **日志** | structlog (Python) |
| **ID生成** | nanoid |

### 项目结构

```
d:/project/hotclaw/
├── frontend/                    # Next.js 前端
│   ├── app/                   # App Router 页面
│   │   ├── page.tsx          # 首页 (已替换为 PixelOffice Canvas)
│   │   ├── history/         # 历史任务列表
│   │   ├── task/[id]/       # 任务详情页
│   │   └── settings/agents|skills  # 配置管理页
│   ├── components/office/     # 像素风 UI 组件
│   │   ├── PixelOffice.tsx  # ⭐ 新主场景 (Canvas 引擎)
│   │   ├── OfficeScene.tsx  # 旧主场景 (CSS Grid, 已废弃)
│   │   ├── PixelCharacter.tsx  # 旧精灵组件 (已废弃)
│   │   ├── AgentContextMenu.tsx
│   │   ├── AgentSettingsDrawer.tsx
│   │   └── ...
│   ├── hooks/
│   │   └── useTaskSSE.ts    # SSE 实时事件 Hook
│   ├── lib/
│   │   ├── api.ts           # API 客户端 (任务/Agent/Skill)
│   │   ├── assets.ts        # 素材路径常量
│   │   └── pixel-office/    # ⭐ 新像素引擎
│   │       ├── OfficeState.ts  # 角色状态管理器
│   │       ├── Renderer.ts     # Canvas 2D 渲染器
│   │       ├── GameLoop.ts     # requestAnimationFrame 循环
│   │       ├── sprites/spriteData.ts  # 像素精灵数组
│   │       ├── layout/defaultLayout.ts # 21×17 格子布局
│   │       └── types.ts
│   └── public/assets/        # 像素素材
│       ├── LargePixelOffice.png   # 大场景 (1024×896)
│       ├── PixelOffice.png         # 中场景 (256×224)
│       ├── PixelOfficeAssets.png   # 精灵图集 (256×160, 4格×2行)
│       └── 02~07_hotclaw_*.png    # 旧通用精灵
│
├── backend/
│   ├── app/
│   │   ├── agents/          # 6 个智能体实现
│   │   │   ├── base.py      # BaseAgent 基类 + default_system_prompt
│   │   │   ├── profile_agent.py      # 账号定位解析
│   │   │   ├── hot_topic_agent.py    # 热点分析
│   │   │   ├── topic_planner_agent.py # 选题策划
│   │   │   ├── title_generator_agent.py # 标题生成
│   │   │   ├── content_writer_agent.py # 正文生成
│   │   │   └── audit_agent.py         # 审核评估
│   │   ├── orchestrator/
│   │   │   ├── engine.py    # 编排引擎 (6 节点线性执行)
│   │   │   ├── broadcaster.py # SSE 广播器 (支持历史回放)
│   │   │   └── workspace.py  # 任务上下文容器
│   │   ├── api/             # FastAPI 路由
│   │   │   ├── task_routes.py
│   │   │   ├── stream_routes.py  # SSE 端点
│   │   │   ├── agent_routes.py   # Agent 配置 CRUD
│   │   │   └── skill_routes.py
│   │   ├── models/tables.py  # SQLAlchemy ORM
│   │   ├── schemas/         # Pydantic 模型
│   │   └── core/            # 配置/日志/异常
│   └── alembic/             # 数据库迁移
│
├── OpenClaw-bot-review/     # 参考项目 (像素编辑器, 已学习)
├── hotclaw_named_assets_pack/  # 命名素材包
└── R2108101/               # 像素编辑器素材
```

---

## 二、6 节点工作流

```
账号定位输入
    ↓
profile_agent     (账号定位解析)  → 生成账号画像
    ↓
hot_topic_agent  (热点分析)      → 抓取相关热点
    ↓
topic_planner_agent (选题策划)   → 规划内容选题
    ↓
title_generator_agent (标题生成) → 生成多个标题
    ↓
content_writer_agent (正文生成)  → 撰写完整文章
    ↓
audit_agent      (审核评估)     → 风控和质量审核
```

---

## 三、前端架构（当前状态）

### 3.1 PixelOffice 像素引擎（主场景）

**文件位置**: `frontend/lib/pixel-office/`

**核心架构**（学习自 OpenClaw-bot-review）:

```
GameLoop (requestAnimationFrame 循环)
    ↓
OfficeState (游戏状态管理器)
    ├── 6 个 Character 对象 (FSM: IDLE → WALK → TYPE)
    ├── OfficeLayout (21×17 格子地图 + 6 个 Seat)
    └── SSE 事件处理器 (onNodeStart/Complete/Error)
    ↓
Renderer (Canvas 2D 渲染器)
    ├── renderTileGrid()    — 绘制地面/墙壁
    ├── renderScene()       — Z排序绘制桌椅+角色
    ├── renderCharacterSprite() — 像素精灵 + 颜色映射
    ├── renderBubble()      — 浮动气泡
    └── renderLabel()       — 角色头顶标签
```

**精灵图**: 硬编码 16×24 SpriteData 数组，5 种角色类型（分析/策划/创作/审核/默认）× 4 方向（DOWN/LEFT/RIGHT/UP）× 3 状态（idle/walk/type）

**Agent 颜色调色板**:
- 0: `#6366f1` 蓝紫 (分析型) — profile_agent, hot_topic_agent
- 1: `#f97316` 橙 (策划型) — topic_planner_agent
- 2: `#22c55e` 绿 (创作型) — title_generator_agent, content_writer_agent
- 3: `#a855f7` 紫 (审核型) — audit_agent

### 3.2 旧组件（已废弃，保留备用）

- `OfficeScene.tsx` — 基于 CSS Grid 的旧主场景
- `PixelCharacter.tsx` — 基于 CSS Grid div 的旧精灵组件
- `Workstation.tsx` — 旧工位组件

### 3.3 关键 Hook

**useTaskSSE** (`hooks/useTaskSSE.ts`):
- 接收 `taskId`，建立 SSE 连接
- 管理 6 个 `NodeState`：pending/running/completed/failed/skipped
- 广播事件：node_start, node_complete, node_error, task_complete, task_error

---

## 四、后端架构

### 4.1 Agent 系统

每个 Agent 继承 `BaseAgent`，核心方法：
- `execute(input_data, context)` → `AgentResult`
- `fallback(error, input_data)` → `AgentResult | None` (降级策略)
- `default_system_prompt` 类属性 (中文详细描述)
- `_resolve_system_prompt()` — DB 自定义 > 代码默认

**Prompt 优先级**: 数据库 `prompt_template` > 代码 `default_system_prompt`

### 4.2 Orchestrator 引擎

编排引擎按顺序执行 6 个节点：
1. 创建 `TaskNodeRunModel` 记录
2. 广播 `node_start` SSE 事件
3. 解析有效 system prompt（支持热更新）
4. 执行 Agent（带超时）
5. 成功 → 存入 Workspace
6. 失败 → 尝试降级 fallback
7. 降级失败 + required=True → 抛出异常中断
8. 广播 `node_complete` / `node_error`

### 4.3 SSE 广播器

- `SSEBroadcaster` 管理任务→订阅者队列映射
- 新订阅者自动回放 60 秒历史事件（解决竞态）
- 任务结束时发送哨兵值，清理历史

### 4.4 Workspace

任务级上下文容器，每个任务独立实例：
- `set(key, value)` / `get(key)` / `snapshot()`
- `extract_for_agent(input_mapping)` — 从 context 提取输入

---

## 五、API 路由

```
POST   /api/v1/tasks           创建任务
GET    /api/v1/tasks           任务列表
GET    /api/v1/tasks/{id}      任务详情
GET    /api/v1/tasks/{id}/status   任务进度
GET    /api/v1/tasks/{id}/nodes   节点列表
GET    /api/v1/tasks/{id}/stream  SSE 流
GET    /api/v1/agents           Agent 列表
GET    /api/v1/agents/{id}      Agent 详情 (含 prompt_source)
PUT    /api/v1/agents/{id}/config  更新 Agent 配置 (prompt_template)
GET    /api/v1/skills           Skill 列表
PUT    /api/v1/skills/{id}/config  更新 Skill 配置
```

---

## 六、素材资源

| 文件 | 用途 |
|------|------|
| `LargePixelOffice.png` (1024×896) | PixelOffice 主场景背景 |
| `PixelOffice.png` (256×224) | 中型场景备用 |
| `PixelOfficeAssets.png` (256×160) | 精灵图集（4格×2行，每格64×80） |
| `02~07_hotclaw_*.png` | 通用状态精灵（待机/工作/感叹号/齿轮） |

**精灵图布局** (PixelOfficeAssets.png):
- Row 0 (idle): Col0=分析型 | Col1=策划型 | Col2=创作型 | Col3=审核型
- Row 1 (work): 同上 4 个角色工作状态

---

## 七、最新进展（本对话）

### 完成事项

1. **R2108101 素材整合** — 复制 3 张素材到 `public/assets/`，建立 Agent→精灵映射
2. **PixelOffice 像素引擎从零实现** — 完整 Canvas 2D 游戏架构
3. **主场景替换** — `app/page.tsx` 使用新 PixelOffice 组件
4. **SSE 事件集成** — Agent 状态实时驱动 Canvas 渲染
5. **构建验证** — `next build` 通过，TypeScript 类型检查通过

### 保留的旧实现

- `OfficeScene.tsx`、`PixelCharacter.tsx`、`Workstation.tsx` 保留备用
- `hotclaw_named_assets_pack` 素材保留（未使用）

---

## 八、启动方式

```bash
# 后端
cd d:/project/hotclaw/backend
python -m uvicorn app.main:app --reload --port 8000

# 前端
cd d:/project/hotclaw/frontend
npx next dev

# 或生产构建
cd d:/project/hotclaw/frontend
npx next build
```

---

## 九、继续开发建议

1. **完善精灵图可视化** — 当前精灵为硬编码数组，可替换为 R2108101 PixelOfficeAssets.png 精灵图，用 Canvas `drawImage` 替代 `fillRect`
2. **角色移动动画** — 实现 A* 路径寻路和 WALK→TYPE 过渡动画
3. **Monitor 屏幕内容** — 根据 Agent 状态动态显示代码/文字
4. **Matrix 生成特效** — Agent spawn/despawn 时的数字雨动画
5. **GitHub 热力图挂件** — 右侧墙面的 GitHub 贡献热力图
6. **照片墙互动** — 可点击查看的 Agent 照片墙

---

## 十、关键文件速查

| 功能 | 文件 |
|------|------|
| 主页面入口 | `frontend/app/page.tsx` |
| 新像素引擎 | `frontend/lib/pixel-office/` |
| SSE Hook | `frontend/hooks/useTaskSSE.ts` |
| API 客户端 | `frontend/lib/api.ts` |
| 编排引擎 | `backend/app/orchestrator/engine.py` |
| Agent 基类 | `backend/app/agents/base.py` |
| SSE 广播 | `backend/app/orchestrator/broadcaster.py` |
| Agent 路由 | `backend/app/api/agent_routes.py` |
| 任务路由 | `backend/app/api/task_routes.py` |
| 异常体系 | `backend/app/core/exceptions.py` |
