# HotClaw - 多智能体公众号爆文编辑部平台 架构设计文档

> 版本：v0.1-MVP | 状态：架构设计阶段

---

## 第一部分：项目总体架构

### 1.1 一句话定义

HotClaw 是一个**基于多智能体协作的公众号内容生产平台**，用户仅需输入"账号定位"，系统自动完成从热点抓取、选题策划、标题生成、正文撰写到审核风控的全链路内容生产，并输出可编辑的文章草稿。

### 1.2 系统边界

**第一版做什么（MVP Scope）：**
- 账号定位解析（用户输入 → 结构化画像）
- 热点抓取与分析
- 选题策划（生成 3~5 个候选选题）
- 标题生成（每个选题 3~5 个候选标题）
- 正文生成（单篇完整文章）
- 基础审核风控（敏感词、合规性检查）
- 草稿输出（结构化 JSON + 可预览 HTML）
- 任务全链路可视化（每个节点状态实时追踪）
- 智能体/Skill 声明式注册与配置管理
- 历史任务查询与回放

**第一版不做什么：**
- 不接公众号 API（不自动发布）
- 不做多账号批量管理
- 不做用户登录/权限体系（单用户模式）
- 不做图片/视频等多媒体内容生成
- 不做 A/B 测试与数据回流
- 不做支付/计费
- 不做 Agent 自主学习/微调
- 不做分布式部署（单机单进程即可）

### 1.3 文字版架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React SPA)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ 任务创建 │ │ 运行监控 │ │ 结果预览 │ │ Agent配置│ │ 历史任务 │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       └────────────┴────────────┴─────────────┴────────────┘       │
│                              │ HTTP + SSE                           │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                      API Gateway (FastAPI)                           │
│                    统一入口 / 参数校验 / 路由                        │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                    Orchestrator (工作流引擎)                         │
│              加载 workflow manifest → 按 DAG 调度 agent              │
│              管理 workspace 上下文 → 推进节点执行                    │
│              状态广播(SSE) → 异常处理 → 结果收集                     │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │          │
┌──────▼──┐ ┌────▼────┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│ 账号解析 │ │热点分析 │ │选题策划│ │内容生成│ │ 审核  │   ← Agent Layer
│ Agent   │ │ Agent   │ │ Agent │ │ Agent │ │ Agent │
└──┬──────┘ └──┬──────┘ └──┬────┘ └──┬────┘ └──┬────┘
   │           │           │         │         │
   │     ┌─────▼─────┐    │    ┌────▼────┐  ┌─▼──────────┐
   │     │新闻抓取Skill│   │    │摘要Skill│  │风险检测Skill│  ← Skill Layer
   │     │标题评分Skill│   │    └─────────┘  └────────────┘
   │     └────────────┘    │
   │                       │
┌──▼───────────────────────▼──────────────────────────────────────────┐
│                       Infrastructure Layer                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ SQLite   │ │  Redis   │ │ LLM API  │ │ Log/Trace│ │ Config   │ │
│  │ (持久化) │ │ (缓存)   │ │ (模型层) │ │ (日志)   │ │ (配置)   │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.4 为什么前后端分离

| 原因 | 说明 |
|------|------|
| **职责清晰** | 后端专注 Agent 调度与业务逻辑，前端专注可视化与交互体验 |
| **实时性需求** | 任务运行时需要 SSE 推送节点状态，前端独立消费事件流 |
| **可替换性** | 未来可接 Electron 桌面端、小程序端、CLI 等多种前端 |
| **开发效率** | 前后端可并行开发，只需约定 API 协议 |
| **可视化复杂度** | 工作流可视化、实时状态、结果预览等前端逻辑较重，需独立架构 |

---

## 第二部分：核心设计理念

### 2.1 设计原则（12 条）

| # | 原则 | 说明 |
|---|------|------|
| 1 | **Workspace-First** | 每个任务创建独立 workspace，所有 agent 在同一 workspace 内共享上下文，workspace 是隔离与协作的基本单位 |
| 2 | **Manifest-First** | 新增 agent/skill/workflow 通过 YAML/JSON manifest 声明式注册，而非硬编码；系统启动时扫描加载 |
| 3 | **控制平面与执行平面分离** | Orchestrator 只负责调度（何时调谁），Agent 只负责执行（做什么事）；两者通过标准协议通信 |
| 4 | **Gateway 唯一入口** | 所有外部请求经 API Gateway 进入，统一鉴权、限流、参数校验；内部服务不暴露 |
| 5 | **结构化输入输出** | 所有 agent 的输入输出必须是 JSON Schema 定义的结构体，拒绝自由文本传递 |
| 6 | **可审计可回放** | 每个节点的输入、输出、耗时、token 消耗、错误信息全部持久化，支持任务级回放 |
| 7 | **渐进式自动化** | MVP 阶段允许用户在关键节点介入（选择选题、修改标题），不追求全自动黑盒 |
| 8 | **Skills 是原子能力** | Skill 是无状态的、可复用的原子工具（如：抓新闻、算评分）；Agent 是有上下文的决策者，Agent 调用 Skill |
| 9 | **失败不阻塞** | 单个 agent 失败时提供降级策略（返回默认值/跳过/重试），不让整条链路崩溃 |
| 10 | **配置优先于代码** | 能通过配置改变的行为，不写死在代码里；包括 prompt 模板、模型选择、重试策略等 |
| 11 | **最小权限原则** | 每个 agent 只能访问自己声明的 skills 和 workspace 中被显式授权的字段 |
| 12 | **可视化是一等公民** | 运行链路可视化不是附加功能，而是核心能力；架构设计时即考虑状态广播 |

### 2.2 对 OpenClaw 理念的吸收与改造

| OpenClaw 理念 | HotClaw 改造 |
|---------------|-------------|
| 控制平面/执行平面分离 | 保留。Orchestrator = 控制平面，Agent = 执行平面。但 HotClaw 的 Orchestrator 是一个内置模块而非独立服务（MVP 阶段不需要微服务） |
| Gateway 统一入口 | 保留。但 HotClaw 的 Gateway 就是 FastAPI 的路由层，不单独部署 |
| Workspace 上下文隔离 | 保留并强化。HotClaw 的 workspace 绑定到具体"任务"，每个任务有独立的上下文字典，agent 间通过 workspace 共享数据 |
| Tool/Plugin 注册机制 | 改造为 Skill 层。HotClaw 的 Skill 比 OpenClaw 的 Tool 更重——Skill 可以有自己的配置、rate limit、缓存策略 |
| Manifest 声明式注册 | 保留。HotClaw 用 YAML manifest 注册 agent/skill/workflow，启动时校验并加载 |
| Canvas 可视化 | 简化。MVP 不做拖拽式 Canvas，只做线性流程的节点状态卡片可视化；但架构预留 DAG 可视化扩展点 |
| 严格配置校验 | 保留。使用 JSON Schema 校验所有 manifest 和运行时输入输出 |
| 可回放可审计 | 保留。HotClaw 记录每个节点的完整输入输出快照，支持任务级回放 |

### 2.3 核心概念定义

| 概念 | 定义 | 类比 |
|------|------|------|
| **Agent（智能体）** | 有角色、有上下文、有决策能力的执行单元。每个 agent 有明确的输入输出 schema，内部调用 LLM 和/或 Skills 来完成任务。Agent 是有状态的（在 workspace 内） | 编辑部里的"人"——选题编辑、标题编辑、审核编辑 |
| **Skill（技能）** | 无状态的原子能力。可以是 API 调用、数据处理函数、外部服务封装。Skill 不做决策，只做执行 | 编辑部里的"工具"——搜索引擎、评分卡、敏感词库 |
| **Plugin（插件）** | MVP 阶段不实现。未来用于接入外部系统（如公众号 API、数据分析平台）。Plugin 是 Skill 的超集，有自己的生命周期和鉴权 | 编辑部对接的"外部系统"——微信后台、数据平台 |
| **Workflow（工作流）** | 定义 agent 的执行顺序和依赖关系的有向无环图（DAG）。MVP 阶段为线性链，但数据结构预留 DAG | 编辑部的"工作流程 SOP" |
| **Workspace（工作空间）** | 一次任务执行的上下文容器。包含：任务参数、各 agent 的输出、中间状态、元数据。workspace 在任务创建时初始化，任务结束后归档 | 编辑部的"选题卡" |
| **Gateway（网关）** | 系统对外的唯一入口。负责路由、参数校验、错误格式化。在 MVP 中就是 FastAPI 的路由层 | 编辑部的"前台" |
| **Orchestrator（编排器）** | 工作流执行引擎。读取 workflow 定义，按顺序/依赖调度 agent，管理 workspace 生命周期，广播执行状态 | 编辑部的"主编" |

---

## 第三部分：MVP 最小闭环

### 3.1 用户最小输入

```
"我是一个关注职场成长的公众号，目标读者是 25-35 岁的互联网从业者"
```

一句话，描述账号定位。系统接受后自动运行。

### 3.2 系统最小处理链

```
用户输入 → 账号解析 Agent → 热点分析 Agent → 选题策划 Agent → 标题生成 Agent → 正文生成 Agent → 审核 Agent → 草稿输出
```

6 个 Agent，线性链，单次运行，约 2~5 分钟完成。

### 3.3 用户最小可感知输出

- 实时看到每个节点的运行状态（进行中/完成/失败）
- 看到 3~5 个候选选题（含热度评分）
- 看到每个选题对应的 3~5 个候选标题（含评分）
- 看到一篇完整的正文文章（Markdown 格式，可预览 HTML）
- 看到审核结果（通过/有风险，附风险详情）
- 可下载/复制草稿

### 3.4 第一版必须实现的 7 个核心能力

| # | 能力 | 说明 |
|---|------|------|
| 1 | 一键启动 | 输入账号定位，一键启动全链路 |
| 2 | 链路可视化 | 实时看到每个 agent 节点的状态、耗时、输出摘要 |
| 3 | 结果输出 | 输出完整的候选选题 + 标题 + 正文 + 审核结果 |
| 4 | Agent 配置 | 可查看/修改每个 agent 的 prompt 模板、模型、参数 |
| 5 | Skill 管理 | 可查看/修改 skill 的配置（如新闻源、敏感词表） |
| 6 | 历史回溯 | 可查看历史任务的完整运行记录 |
| 7 | 错误降级 | 单个节点失败不阻断全流程，有默认降级策略 |

### 3.5 明确延后的功能

| 功能 | 延后原因 |
|------|---------|
| 公众号 API 对接 | 需要公众号授权，MVP 不涉及 |
| 多账号管理 | 先做好单账号全链路 |
| 用户体系/权限 | 单用户模式足够 |
| 图片生成/排版 | 内容生成本身就够复杂 |
| DAG 工作流编辑器 | 线性链足够验证 MVP |
| Agent 自主学习 | 先用配置化 prompt |
| 分布式/高可用 | 单机单进程够用 |

---

## 第四部分：前端框架设计

### 4.1 技术栈

| 类别 | 选择 | 理由 |
|------|------|------|
| 框架 | **React 18 + TypeScript** | 生态成熟、组件化好、SSE 处理方便 |
| 构建 | **Vite** | 快速启动，HMR 好 |
| 路由 | **React Router v6** | 标准选择 |
| 状态管理 | **Zustand** | 轻量、无 boilerplate、适合中小型项目 |
| UI 库 | **Ant Design 5** | 中文生态好、表格/表单/卡片组件完善 |
| HTTP | **Axios** | 拦截器好用 |
| 实时通信 | **EventSource (SSE)** | 单向推送足够，比 WebSocket 简单 |
| 代码高亮 | **react-markdown + rehype** | 用于文章预览 |

### 4.2 页面设计

#### 页面列表与路由

| 页面 | 路由 | 说明 |
|------|------|------|
| 首页/新建任务 | `/` | 输入账号定位，一键启动 |
| 任务运行页 | `/task/:taskId/run` | 实时查看各节点运行状态 |
| 任务结果页 | `/task/:taskId/result` | 查看完整输出，预览文章 |
| 智能体配置页 | `/settings/agents` | 查看/编辑所有 agent 配置 |
| 智能体详情页 | `/settings/agents/:agentId` | 单个 agent 的 prompt、模型、参数 |
| Skill 管理页 | `/settings/skills` | 查看/编辑所有 skill 配置 |
| 历史任务页 | `/history` | 任务列表，支持查看详情与回放 |

#### 页面跳转关系

```
首页 (/)
  │
  ├── [创建任务] ──→ 任务运行页 (/task/:id/run)
  │                      │
  │                      └── [运行完成] ──→ 任务结果页 (/task/:id/result)
  │
  ├── [历史任务] ──→ 历史任务页 (/history)
  │                      │
  │                      └── [查看详情] ──→ 任务结果页 (/task/:id/result)
  │
  ├── [智能体配置] ──→ 智能体配置页 (/settings/agents)
  │                      │
  │                      └── [编辑] ──→ 智能体详情页 (/settings/agents/:id)
  │
  └── [Skill管理] ──→ Skill管理页 (/settings/skills)
```

### 4.3 组件树

```
<App>
├── <AppLayout>                          # 全局布局（侧边导航 + 主内容区）
│   ├── <Sidebar>                        # 侧边导航
│   │   ├── <NavItem to="/" />           # 新建任务
│   │   ├── <NavItem to="/history" />    # 历史任务
│   │   ├── <NavItem to="/settings/agents" /> # 智能体
│   │   └── <NavItem to="/settings/skills" /> # Skills
│   │
│   └── <MainContent>                    # 路由出口
│       ├── <HomePage>                   # 首页
│       │   ├── <AccountInput />         # 账号定位输入框
│       │   ├── <QuickTemplates />       # 快速模板（可选）
│       │   └── <RecentTasks />          # 最近任务列表
│       │
│       ├── <TaskRunPage>                # 任务运行页
│       │   ├── <TaskHeader />           # 任务基本信息
│       │   ├── <PipelineView>           # 流水线可视化
│       │   │   └── <NodeCard />         # 单个节点卡片（×N）
│       │   │       ├── <NodeStatus />   # 状态指示器
│       │   │       ├── <NodeTimer />    # 耗时
│       │   │       └── <NodePreview />  # 输出预览
│       │   └── <RunLog />              # 实时日志面板
│       │
│       ├── <TaskResultPage>             # 结果页
│       │   ├── <AccountProfile />       # 账号画像卡片
│       │   ├── <TopicList />            # 候选选题列表
│       │   ├── <TitleList />            # 候选标题列表
│       │   ├── <ArticlePreview />       # 文章预览（Markdown → HTML）
│       │   ├── <AuditResult />          # 审核结果
│       │   └── <ExportActions />        # 导出/复制操作
│       │
│       ├── <AgentConfigPage>            # 智能体配置列表
│       │   └── <AgentCard />            # 单个 agent 卡片（×N）
│       │
│       ├── <AgentDetailPage>            # 智能体详情
│       │   ├── <PromptEditor />         # Prompt 模板编辑器
│       │   ├── <ModelSelector />        # 模型选择
│       │   ├── <ParamForm />            # 参数配置表单
│       │   └── <IOSchemaView />         # 输入输出 Schema 展示
│       │
│       ├── <SkillConfigPage>            # Skill 列表
│       │   └── <SkillCard />            # 单个 skill 卡片
│       │
│       └── <HistoryPage>               # 历史任务
│           ├── <TaskFilter />           # 筛选/搜索
│           └── <TaskTable />            # 任务列表表格
```

### 4.4 状态管理设计

使用 Zustand，分为以下 store：

```typescript
// stores/taskStore.ts — 当前任务状态
interface TaskStore {
  currentTaskId: string | null;
  taskStatus: 'idle' | 'running' | 'completed' | 'failed';
  nodes: NodeState[];           // 各节点运行状态
  workspace: Record<string, any>; // workspace 数据快照
  createTask: (input: string) => Promise<string>;
  subscribeToTask: (taskId: string) => void;  // SSE 订阅
  unsubscribe: () => void;
}

// stores/configStore.ts — 配置数据
interface ConfigStore {
  agents: AgentConfig[];
  skills: SkillConfig[];
  fetchAgents: () => Promise<void>;
  updateAgent: (id: string, config: Partial<AgentConfig>) => Promise<void>;
  fetchSkills: () => Promise<void>;
  updateSkill: (id: string, config: Partial<SkillConfig>) => Promise<void>;
}

// stores/historyStore.ts — 历史任务
interface HistoryStore {
  tasks: TaskSummary[];
  total: number;
  fetchTasks: (page: number, filters?: TaskFilter) => Promise<void>;
}
```

### 4.5 实时状态更新方式

**采用 SSE（Server-Sent Events）：**

```
前端                                    后端
  │                                       │
  ├── POST /api/tasks (创建任务) ────────→│
  │←── { taskId: "xxx" } ────────────────│
  │                                       │
  ├── GET /api/tasks/xxx/stream ─────────→│  (SSE 连接)
  │←── event: node_start                 │
  │    data: { nodeId, agentName, ... }  │
  │←── event: node_progress              │
  │    data: { nodeId, progress, ... }   │
  │←── event: node_complete              │
  │    data: { nodeId, output, ... }     │
  │←── event: node_start                 │
  │    data: { nodeId, agentName, ... }  │
  │     ...                              │
  │←── event: task_complete              │
  │    data: { resultUrl, ... }          │
  │                                       │
```

SSE 事件类型：

| 事件 | 说明 |
|------|------|
| `node_start` | 节点开始执行 |
| `node_progress` | 节点执行中（含进度信息） |
| `node_complete` | 节点执行完成（含输出摘要） |
| `node_error` | 节点执行失败（含错误信息） |
| `task_complete` | 任务全部完成 |
| `task_error` | 任务级错误 |

### 4.6 可视化运行设计

MVP 采用**垂直流水线卡片**布局，不做 Canvas 拖拽：

```
┌─────────────────────────────────────┐
│  ✅ 账号定位解析        耗时 3.2s    │
│  ─────────────────────────────────  │
│  输出: 领域=职场成长 | 调性=专业温暖 │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  🔄 热点分析            耗时 --      │
│  ─────────────────────────────────  │
│  正在抓取热点新闻...                  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  ⏳ 选题策划             等待中      │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  ⏳ 标题生成             等待中      │
└─────────────────────────────────────┘
         │
         ▼
  ...
```

每个卡片状态对应样式：
- `pending` → 灰色，虚线边框
- `running` → 蓝色，呼吸动画
- `completed` → 绿色，显示输出摘要
- `failed` → 红色，显示错误信息

---

## 第五部分：后端框架设计

### 5.1 技术栈

| 类别 | 选择 | 理由 |
|------|------|------|
| 语言 | **Python 3.11+** | AI 生态最好、LLM SDK 最全 |
| Web 框架 | **FastAPI** | 异步支持好、自动 OpenAPI 文档、SSE 支持 |
| ORM | **SQLAlchemy 2.0 + alembic** | 成熟稳定，async 支持 |
| 任务调度 | **内置 asyncio** | MVP 不需要 Celery，单进程足够 |
| 配置校验 | **Pydantic v2** | 和 FastAPI 无缝集成 |
| LLM 调用 | **litellm 或直接 openai SDK** | 统一多模型调用接口 |

### 5.2 模块设计与职责

```
backend/
├── gateway/           # API 网关层
├── orchestrator/      # 工作流编排器
├── agents/            # 智能体执行层
├── skills/            # 技能层
├── services/          # 业务服务层
├── models/            # 数据模型
├── schemas/           # Pydantic Schema
├── config/            # 配置加载
└── core/              # 核心工具（日志、异常、追踪）
```

#### 模块职责清单

| 模块 | 职责 | 依赖 |
|------|------|------|
| **gateway/** | 路由定义、参数校验、统一错误响应、SSE 端点 | schemas/ |
| **orchestrator/** | 加载 workflow 定义 → 创建 workspace → 按顺序调度 agent → 收集结果 → 广播状态 | agents/, workspace |
| **agents/** | Agent 基类、各具体 agent 实现、agent 注册中心 | skills/, LLM |
| **skills/** | Skill 基类、各具体 skill 实现、skill 注册中心 | 外部 API |
| **services/task_service** | 任务 CRUD、状态管理 | models/ |
| **services/config_service** | agent/skill/workflow 配置的读写 | manifest files |
| **services/draft_service** | 草稿生成与存储 | models/ |
| **services/audit_service** | 审核结果管理 | models/ |
| **models/** | SQLAlchemy 数据模型 | DB |
| **schemas/** | Pydantic 输入输出模型 | - |
| **config/** | manifest 加载、配置校验、环境变量 | manifest files |
| **core/logger** | 结构化日志 | - |
| **core/tracer** | trace_id 生成与传播 | - |
| **core/exceptions** | 统一异常定义与处理 | - |
| **core/workspace** | Workspace 上下文管理 | - |

### 5.3 核心调用链

```
[HTTP Request]
     │
     ▼
 gateway/routes.py          # 1. 接收请求，参数校验
     │
     ▼
 services/task_service.py   # 2. 创建任务记录，初始化 workspace
     │
     ▼
 orchestrator/engine.py     # 3. 加载 workflow，启动 asyncio 任务
     │
     ├──→ agents/profile_agent.py    # 4a. 账号解析
     │         │
     │         └──→ LLM API
     │
     ├──→ agents/hot_topic_agent.py  # 4b. 热点分析
     │         │
     │         ├──→ skills/news_fetcher.py  → 外部 API
     │         └──→ LLM API
     │
     ├──→ agents/topic_agent.py      # 4c. 选题策划
     │         └──→ LLM API
     │
     ├──→ agents/title_agent.py      # 4d. 标题生成
     │         │
     │         ├──→ LLM API
     │         └──→ skills/title_scorer.py
     │
     ├──→ agents/content_agent.py    # 4e. 正文生成
     │         │
     │         ├──→ LLM API
     │         └──→ skills/summary_skill.py
     │
     └──→ agents/audit_agent.py      # 4f. 审核
               │
               └──→ skills/risk_detector.py
     │
     ▼
 services/draft_service.py  # 5. 生成草稿，持久化
     │
     ▼
 [SSE: task_complete]       # 6. 通知前端
```

### 5.4 Orchestrator 引擎设计

```python
# 伪代码示意
class OrchestratorEngine:
    async def run_workflow(self, task_id: str, workflow: WorkflowDef, workspace: Workspace):
        for node in workflow.nodes:
            agent = self.agent_registry.get(node.agent_id)
            
            # 从 workspace 提取该 agent 需要的输入
            agent_input = workspace.extract(node.input_mapping)
            
            # 广播节点开始
            await self.broadcast(task_id, "node_start", node)
            
            try:
                # 执行 agent
                output = await agent.execute(agent_input, workspace)
                
                # 校验输出 schema
                validated = node.output_schema.validate(output)
                
                # 写入 workspace
                workspace.set(node.output_key, validated)
                
                # 持久化节点运行记录
                await self.save_node_run(task_id, node, agent_input, output)
                
                # 广播节点完成
                await self.broadcast(task_id, "node_complete", node, output)
                
            except Exception as e:
                # 降级处理
                fallback = await agent.fallback(e, agent_input)
                if fallback:
                    workspace.set(node.output_key, fallback)
                    await self.broadcast(task_id, "node_complete", node, fallback, degraded=True)
                else:
                    await self.broadcast(task_id, "node_error", node, str(e))
                    if node.required:
                        raise WorkflowAbortError(node, e)
```

---

## 第六部分：智能体体系设计

### 6.1 Agent 基类

```python
class BaseAgent(ABC):
    agent_id: str
    name: str
    description: str
    input_schema: Type[BaseModel]    # Pydantic model
    output_schema: Type[BaseModel]   # Pydantic model
    required_skills: list[str]       # 依赖的 skill id 列表
    model: str                       # 默认使用的 LLM 模型
    prompt_template: str             # prompt 模板（支持变量替换）
    
    @abstractmethod
    async def execute(self, input: BaseModel, workspace: Workspace) -> BaseModel:
        ...
    
    async def fallback(self, error: Exception, input: BaseModel) -> Optional[BaseModel]:
        """降级策略，默认返回 None（不降级）"""
        return None
```

### 6.2 第一版智能体列表

#### 1. 账号定位解析智能体 (ProfileAgent)

| 属性 | 值 |
|------|------|
| **agent_id** | `profile_agent` |
| **输入** | `{ positioning: string }` — 用户输入的账号定位描述 |
| **输出** | `{ domain: string, subdomain: string, target_audience: { age_range, occupation, interests }, tone: string, content_style: string, keywords: string[] }` |
| **依赖 Skill** | 无 |
| **结构化输出** | 是，JSON Schema 强制 |
| **降级策略** | 使用通用默认画像（"泛资讯、18-45岁、中性调性"）|

#### 2. 热点分析智能体 (HotTopicAgent)

| 属性 | 值 |
|------|------|
| **agent_id** | `hot_topic_agent` |
| **输入** | `{ profile: AccountProfile }` — 来自 workspace 的账号画像 |
| **输出** | `{ hot_topics: [{ title, source, heat_score, summary, url, relevance_score }] }` — 5~10 条热点 |
| **依赖 Skill** | `news_fetcher_skill`（新闻抓取）|
| **结构化输出** | 是 |
| **降级策略** | Skill 失败时使用缓存的近期热点；LLM 失败时返回 Skill 原始结果不做分析 |

#### 3. 选题策划智能体 (TopicPlannerAgent)

| 属性 | 值 |
|------|------|
| **agent_id** | `topic_planner_agent` |
| **输入** | `{ profile: AccountProfile, hot_topics: HotTopic[] }` |
| **输出** | `{ topics: [{ title, angle, hook, target_emotion, estimated_appeal, reasoning }] }` — 3~5 个候选选题 |
| **依赖 Skill** | 无 |
| **结构化输出** | 是 |
| **降级策略** | 直接使用热点标题作为选题，不做深度策划 |

#### 4. 标题生成智能体 (TitleGeneratorAgent)

| 属性 | 值 |
|------|------|
| **agent_id** | `title_generator_agent` |
| **输入** | `{ profile: AccountProfile, topic: TopicCandidate }` — 选择的选题 |
| **输出** | `{ titles: [{ text, style, score, reasoning }] }` — 3~5 个候选标题 |
| **依赖 Skill** | `title_scorer_skill`（标题评分）|
| **结构化输出** | 是 |
| **降级策略** | 评分 Skill 失败时跳过评分，仅输出标题文本 |

#### 5. 正文生成智能体 (ContentWriterAgent)

| 属性 | 值 |
|------|------|
| **agent_id** | `content_writer_agent` |
| **输入** | `{ profile: AccountProfile, topic: TopicCandidate, title: string, hot_topics: HotTopic[] }` |
| **输出** | `{ content_markdown: string, word_count: int, structure: { sections: [{ heading, summary }] }, tags: string[] }` |
| **依赖 Skill** | `summary_skill`（摘要，用于素材压缩）|
| **结构化输出** | 是（元数据结构化，正文为 Markdown string） |
| **降级策略** | 摘要 Skill 失败时直接使用原始素材；LLM 失败时返回空文章并标记失败 |

#### 6. 审核智能体 (AuditAgent)

| 属性 | 值 |
|------|------|
| **agent_id** | `audit_agent` |
| **输入** | `{ title: string, content_markdown: string, profile: AccountProfile }` |
| **输出** | `{ passed: bool, risk_level: "low"|"medium"|"high", issues: [{ type, description, location, suggestion }], overall_comment: string }` |
| **依赖 Skill** | `risk_detector_skill`（敏感词/合规检测）|
| **结构化输出** | 是 |
| **降级策略** | Skill 失败时仅做 LLM 审核；LLM 也失败时标记为"未审核"，不阻断输出 |

---

## 第七部分：Skill 机制设计

### 7.1 Skill 定义

**Skill 是无状态的、可复用的原子能力单元。** Skill 封装了一个具体的技术操作（API 调用、数据处理、规则匹配等），对外提供标准化的输入输出接口。Skill 不做业务决策，只做能力执行。

### 7.2 Skill 与 Agent 的区别

| 维度 | Agent | Skill |
|------|-------|-------|
| 状态 | 有状态（在 workspace 内） | 无状态 |
| 决策 | 做决策（基于 LLM） | 不做决策（纯执行） |
| 依赖 | 可依赖多个 Skill | 不依赖其他 Skill |
| 注册 | manifest + 代码实现 | manifest + 代码实现 |
| 可独立运行 | 是（但通常由 Orchestrator 调度） | 是（被 Agent 调用） |
| 类比 | 编辑部的"人" | 编辑部的"工具" |

### 7.3 Skill 基类

```python
class BaseSkill(ABC):
    skill_id: str
    name: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    config_schema: Type[BaseModel]   # 该 skill 的配置项 schema
    
    @abstractmethod
    async def execute(self, input: BaseModel, config: BaseModel) -> BaseModel:
        ...
```

### 7.4 Skill 注册方式

通过 YAML manifest 声明式注册：

```yaml
# manifests/skills/news_fetcher.yaml
skill_id: news_fetcher_skill
name: 新闻抓取
description: 从多个新闻源抓取最新热点新闻
version: "1.0.0"
module: skills.news_fetcher.NewsFetcherSkill   # Python 模块路径
input_schema: skills.news_fetcher.NewsFetcherInput
output_schema: skills.news_fetcher.NewsFetcherOutput
config:
  sources:
    - name: "百度热搜"
      url: "https://top.baidu.com"
      enabled: true
    - name: "微博热搜"
      url: "https://weibo.com/hot"
      enabled: true
  max_items: 20
  cache_ttl_seconds: 300
```

系统启动时：
1. 扫描 `manifests/skills/` 目录
2. 校验 manifest 格式（JSON Schema 校验）
3. 动态加载对应的 Python 模块
4. 注册到 SkillRegistry

### 7.5 Skill 调用协议

```python
# Agent 内部调用 Skill
class HotTopicAgent(BaseAgent):
    async def execute(self, input, workspace):
        # 通过 skill registry 获取 skill 实例
        news_skill = self.skill_registry.get("news_fetcher_skill")
        
        # 构造 skill 输入
        skill_input = NewsFetcherInput(
            keywords=input.profile.keywords,
            domain=input.profile.domain
        )
        
        # 调用 skill
        news_result = await news_skill.execute(skill_input)
        
        # 使用 skill 输出 + LLM 做分析
        ...
```

### 7.6 第一版内置 Skills

#### 1. 新闻抓取 Skill (news_fetcher_skill)

| 属性 | 值 |
|------|------|
| **输入** | `{ keywords: string[], domain: string, max_items: int }` |
| **输出** | `{ articles: [{ title, source, url, published_at, summary }] }` |
| **配置** | 新闻源列表、缓存时间、请求超时 |
| **实现** | HTTP 抓取 + 简单解析（MVP 可用 RSS 或热搜 API）|

#### 2. 摘要 Skill (summary_skill)

| 属性 | 值 |
|------|------|
| **输入** | `{ text: string, max_length: int }` |
| **输出** | `{ summary: string }` |
| **配置** | 使用的 LLM 模型、温度 |
| **实现** | 调用 LLM 做文本摘要 |

#### 3. 风险检测 Skill (risk_detector_skill)

| 属性 | 值 |
|------|------|
| **输入** | `{ text: string }` |
| **输出** | `{ risks: [{ type, keyword, position, severity }], has_risk: bool }` |
| **配置** | 敏感词表路径、检测规则 |
| **实现** | 关键词匹配 + 规则引擎（MVP 不需要调 LLM）|

#### 4. 标题评分 Skill (title_scorer_skill)

| 属性 | 值 |
|------|------|
| **输入** | `{ title: string, domain: string, target_audience: string }` |
| **输出** | `{ score: float, dimensions: { clickability, relevance, emotion, clarity }, suggestions: string[] }` |
| **配置** | 评分模型、评分维度权重 |
| **实现** | 调用 LLM 做多维度评分 |

---

## 第八部分：工作流与配置设计

### 8.1 工作流定义结构

```yaml
# manifests/workflows/default_pipeline.yaml
workflow_id: default_pipeline
name: 默认内容生产流水线
description: 从账号定位到文章草稿的全链路
version: "1.0.0"

# 输入 schema
input_schema:
  type: object
  required: [positioning]
  properties:
    positioning:
      type: string
      description: 用户输入的账号定位描述
      minLength: 5
      maxLength: 500

# 节点定义（有序）
nodes:
  - node_id: profile_parsing
    agent_id: profile_agent
    name: 账号定位解析
    input_mapping:
      positioning: "$.input.positioning"
    output_key: profile
    required: true
    timeout_seconds: 30

  - node_id: hot_topic_analysis
    agent_id: hot_topic_agent
    name: 热点分析
    input_mapping:
      profile: "$.workspace.profile"
    output_key: hot_topics
    required: true
    timeout_seconds: 60

  - node_id: topic_planning
    agent_id: topic_planner_agent
    name: 选题策划
    input_mapping:
      profile: "$.workspace.profile"
      hot_topics: "$.workspace.hot_topics.hot_topics"
    output_key: topics
    required: true
    timeout_seconds: 45

  - node_id: title_generation
    agent_id: title_generator_agent
    name: 标题生成
    input_mapping:
      profile: "$.workspace.profile"
      topic: "$.workspace.topics.topics[0]"  # 默认取第一个选题
    output_key: titles
    required: true
    timeout_seconds: 45

  - node_id: content_writing
    agent_id: content_writer_agent
    name: 正文生成
    input_mapping:
      profile: "$.workspace.profile"
      topic: "$.workspace.topics.topics[0]"
      title: "$.workspace.titles.titles[0].text"
      hot_topics: "$.workspace.hot_topics.hot_topics"
    output_key: content
    required: true
    timeout_seconds: 120

  - node_id: audit
    agent_id: audit_agent
    name: 内容审核
    input_mapping:
      title: "$.workspace.titles.titles[0].text"
      content_markdown: "$.workspace.content.content_markdown"
      profile: "$.workspace.profile"
    output_key: audit_result
    required: false   # 审核失败不阻断输出
    timeout_seconds: 30

# 输出 schema
output_mapping:
  profile: "$.workspace.profile"
  topics: "$.workspace.topics"
  titles: "$.workspace.titles"
  content: "$.workspace.content"
  audit_result: "$.workspace.audit_result"
```

### 8.2 Agent 配置结构

```yaml
# manifests/agents/profile_agent.yaml
agent_id: profile_agent
name: 账号定位解析智能体
description: 将用户的账号定位描述解析为结构化画像
version: "1.0.0"
module: agents.profile_agent.ProfileAgent

model:
  provider: openai       # 或 zhipu, moonshot, deepseek 等
  name: gpt-4o-mini
  temperature: 0.3
  max_tokens: 1000

prompt_template: |
  你是一位专业的公众号运营专家。请根据以下账号定位描述，解析出结构化的账号画像。

  ## 账号定位描述
  {positioning}

  ## 输出要求
  请以 JSON 格式输出以下字段：
  - domain: 主领域
  - subdomain: 细分领域
  - target_audience: 目标受众（含 age_range, occupation, interests）
  - tone: 内容调性
  - content_style: 内容风格
  - keywords: 核心关键词列表

input_schema:
  type: object
  required: [positioning]
  properties:
    positioning:
      type: string

output_schema:
  type: object
  required: [domain, target_audience, tone, keywords]
  properties:
    domain:
      type: string
    subdomain:
      type: string
    target_audience:
      type: object
      properties:
        age_range: { type: string }
        occupation: { type: string }
        interests: { type: array, items: { type: string } }
    tone:
      type: string
    content_style:
      type: string
    keywords:
      type: array
      items: { type: string }

required_skills: []

retry:
  max_attempts: 2
  backoff_seconds: 5

fallback:
  strategy: default_value
  default:
    domain: "泛资讯"
    subdomain: "综合"
    target_audience: { age_range: "18-45", occupation: "通用", interests: [] }
    tone: "中性"
    content_style: "信息型"
    keywords: []
```

### 8.3 Skill 配置结构

```yaml
# manifests/skills/news_fetcher.yaml
skill_id: news_fetcher_skill
name: 新闻抓取
description: 从多个新闻源抓取热点新闻
version: "1.0.0"
module: skills.news_fetcher.NewsFetcherSkill

input_schema:
  type: object
  required: [keywords]
  properties:
    keywords:
      type: array
      items: { type: string }
    domain:
      type: string
    max_items:
      type: integer
      default: 10

output_schema:
  type: object
  required: [articles]
  properties:
    articles:
      type: array
      items:
        type: object
        properties:
          title: { type: string }
          source: { type: string }
          url: { type: string }
          published_at: { type: string }
          summary: { type: string }

config:
  sources:
    - id: baidu_hot
      name: 百度热搜
      type: api
      enabled: true
    - id: weibo_hot
      name: 微博热搜
      type: api
      enabled: true
  cache_ttl_seconds: 300
  request_timeout_seconds: 10
  max_concurrent_requests: 3
```

### 8.4 输入输出 Schema 规范

所有 agent/skill 的输入输出使用 JSON Schema (draft-07) 定义，并在运行时用 Pydantic 校验：

- 输入校验时机：Agent/Skill `execute()` 被调用前
- 输出校验时机：Agent/Skill `execute()` 返回后
- 校验失败处理：抛出 `SchemaValidationError`，由 Orchestrator 按降级策略处理

### 8.5 配置校验规则

| 校验项 | 规则 | 时机 |
|--------|------|------|
| manifest 格式 | 必须符合对应的 meta-schema | 系统启动时 |
| module 路径 | 必须可导入 | 系统启动时 |
| agent_id/skill_id | 全局唯一 | 系统启动时 |
| workflow 引用的 agent | 必须已注册 | 系统启动时 |
| agent 引用的 skill | 必须已注册 | 系统启动时 |
| input_mapping 路径 | JSONPath 语法合法 | workflow 加载时 |
| 运行时输入 | 符合 input_schema | 每次执行前 |
| 运行时输出 | 符合 output_schema | 每次执行后 |

---

## 第九部分：MVP 接口设计

### 9.1 RESTful API 列表

**基础路径：** `/api/v1`

---

#### 1. 创建任务

```
POST /api/v1/tasks

请求体:
{
  "positioning": "我是一个关注职场成长的公众号，目标读者是25-35岁的互联网从业者",
  "workflow_id": "default_pipeline"     // 可选，默认使用 default_pipeline
}

返回体:
{
  "code": 0,
  "data": {
    "task_id": "task_20260323_abc123",
    "status": "pending",
    "created_at": "2026-03-23T12:00:00Z",
    "workflow_id": "default_pipeline"
  }
}
```

#### 2. 查询任务状态

```
GET /api/v1/tasks/{task_id}/status

返回体:
{
  "code": 0,
  "data": {
    "task_id": "task_20260323_abc123",
    "status": "running",           // pending | running | completed | failed
    "current_node": "hot_topic_analysis",
    "progress": {
      "total_nodes": 6,
      "completed_nodes": 1,
      "current_node_index": 2
    },
    "started_at": "2026-03-23T12:00:01Z",
    "elapsed_seconds": 35
  }
}
```

#### 3. 任务事件流（SSE）

```
GET /api/v1/tasks/{task_id}/stream

响应: text/event-stream

event: node_start
data: {"node_id":"hot_topic_analysis","agent_id":"hot_topic_agent","name":"热点分析","started_at":"..."}

event: node_complete
data: {"node_id":"hot_topic_analysis","agent_id":"hot_topic_agent","output_summary":"获取到8条热点","elapsed_seconds":12.3}

event: task_complete
data: {"task_id":"task_20260323_abc123","elapsed_seconds":180}
```

#### 4. 查询任务详情（结果）

```
GET /api/v1/tasks/{task_id}

返回体:
{
  "code": 0,
  "data": {
    "task_id": "task_20260323_abc123",
    "status": "completed",
    "input": { "positioning": "..." },
    "workflow_id": "default_pipeline",
    "result": {
      "profile": { ... },
      "topics": { ... },
      "titles": { ... },
      "content": { "content_markdown": "...", "word_count": 1500, ... },
      "audit_result": { "passed": true, ... }
    },
    "created_at": "...",
    "completed_at": "...",
    "elapsed_seconds": 180
  }
}
```

#### 5. 查询节点运行日志

```
GET /api/v1/tasks/{task_id}/nodes

返回体:
{
  "code": 0,
  "data": {
    "nodes": [
      {
        "node_id": "profile_parsing",
        "agent_id": "profile_agent",
        "name": "账号定位解析",
        "status": "completed",
        "input": { ... },
        "output": { ... },
        "started_at": "...",
        "completed_at": "...",
        "elapsed_seconds": 3.2,
        "token_usage": { "prompt_tokens": 200, "completion_tokens": 150 },
        "degraded": false,
        "error": null
      },
      ...
    ]
  }
}
```

#### 6. 获取 Agent 列表

```
GET /api/v1/agents

返回体:
{
  "code": 0,
  "data": {
    "agents": [
      {
        "agent_id": "profile_agent",
        "name": "账号定位解析智能体",
        "description": "...",
        "version": "1.0.0",
        "model": { "provider": "openai", "name": "gpt-4o-mini" },
        "required_skills": [],
        "status": "active"
      },
      ...
    ]
  }
}
```

#### 7. 更新 Agent 配置

```
PUT /api/v1/agents/{agent_id}/config

请求体:
{
  "model": {
    "provider": "deepseek",
    "name": "deepseek-chat",
    "temperature": 0.5
  },
  "prompt_template": "新的 prompt 模板...",
  "retry": {
    "max_attempts": 3
  }
}

返回体:
{
  "code": 0,
  "data": {
    "agent_id": "profile_agent",
    "updated_fields": ["model", "prompt_template", "retry"],
    "updated_at": "..."
  }
}
```

#### 8. 获取 Skill 列表

```
GET /api/v1/skills

返回体:
{
  "code": 0,
  "data": {
    "skills": [
      {
        "skill_id": "news_fetcher_skill",
        "name": "新闻抓取",
        "description": "...",
        "version": "1.0.0",
        "config": { ... },
        "status": "active"
      },
      ...
    ]
  }
}
```

#### 9. 更新 Skill 配置

```
PUT /api/v1/skills/{skill_id}/config

请求体:
{
  "config": {
    "sources": [ ... ],
    "cache_ttl_seconds": 600
  }
}

返回体:
{
  "code": 0,
  "data": {
    "skill_id": "news_fetcher_skill",
    "updated_at": "..."
  }
}
```

#### 10. 查询历史任务

```
GET /api/v1/tasks?page=1&page_size=20&status=completed

返回体:
{
  "code": 0,
  "data": {
    "tasks": [
      {
        "task_id": "...",
        "positioning_summary": "职场成长公众号...",
        "status": "completed",
        "created_at": "...",
        "elapsed_seconds": 180,
        "topic_count": 5,
        "article_word_count": 1500
      },
      ...
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 42
    }
  }
}
```

### 9.2 统一错误码

| 错误码 | 含义 | HTTP Status |
|--------|------|-------------|
| 0 | 成功 | 200 |
| 1001 | 参数校验失败 | 400 |
| 1002 | 任务不存在 | 404 |
| 1003 | Agent 不存在 | 404 |
| 1004 | Skill 不存在 | 404 |
| 2001 | 任务已在运行中 | 409 |
| 2002 | 工作流定义不存在 | 404 |
| 3001 | LLM 调用失败 | 502 |
| 3002 | 外部 API 调用失败 | 502 |
| 3003 | Agent 执行超时 | 504 |
| 4001 | 配置校验失败 | 400 |
| 4002 | 配置文件格式错误 | 400 |
| 5000 | 内部服务器错误 | 500 |

### 9.3 统一响应格式

```json
{
  "code": 0,          // 0=成功，非0=失败
  "message": "ok",    // 人类可读的消息
  "data": { ... },    // 成功时的数据
  "error": {          // 失败时的错误详情（仅失败时存在）
    "code": 1001,
    "message": "positioning 字段不能为空",
    "details": { ... }
  },
  "trace_id": "tr_abc123"  // 链路追踪 ID
}
```

---

## 第十部分：MVP 数据库设计

### 10.1 数据库选择

**MVP 使用 SQLite**，理由：
- 零部署成本，单文件
- Python 原生支持
- SQLAlchemy 兼容，后续可无缝切换到 PostgreSQL
- 单用户场景完全够用

### 10.2 表设计

#### 1. tasks（任务表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) PK | 任务 ID（如 task_20260323_abc123）|
| workflow_id | VARCHAR(64) | 使用的工作流 ID |
| status | VARCHAR(20) | pending / running / completed / failed |
| input_data | JSON | 用户输入（positioning 等）|
| result_data | JSON | 最终结果（全部 workspace 输出）|
| error_message | TEXT | 失败时的错误信息 |
| created_at | DATETIME | 创建时间 |
| started_at | DATETIME | 开始执行时间 |
| completed_at | DATETIME | 完成时间 |
| elapsed_seconds | FLOAT | 总耗时 |
| total_tokens | INTEGER | 总 token 消耗 |

**用途：** 存储每次任务的完整生命周期信息

#### 2. task_node_runs（任务节点运行记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | VARCHAR(64) FK → tasks.id | 关联任务 |
| node_id | VARCHAR(64) | 节点 ID |
| agent_id | VARCHAR(64) | 执行的 agent ID |
| status | VARCHAR(20) | pending / running / completed / failed / skipped |
| input_data | JSON | 该节点的输入 |
| output_data | JSON | 该节点的输出 |
| error_message | TEXT | 错误信息 |
| degraded | BOOLEAN | 是否降级执行 |
| started_at | DATETIME | 开始时间 |
| completed_at | DATETIME | 完成时间 |
| elapsed_seconds | FLOAT | 耗时 |
| prompt_tokens | INTEGER | prompt token 数 |
| completion_tokens | INTEGER | completion token 数 |
| model_used | VARCHAR(64) | 实际使用的模型 |
| retry_count | INTEGER | 重试次数 |

**用途：** 每个 agent 节点的完整运行记录，支持回放和审计

#### 3. account_profiles（账号画像表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | VARCHAR(64) FK → tasks.id | 关联任务 |
| positioning | TEXT | 原始定位描述 |
| domain | VARCHAR(100) | 主领域 |
| subdomain | VARCHAR(100) | 细分领域 |
| target_audience | JSON | 目标受众 |
| tone | VARCHAR(50) | 调性 |
| content_style | VARCHAR(50) | 风格 |
| keywords | JSON | 关键词列表 |
| created_at | DATETIME | 创建时间 |

**用途：** 存储解析后的账号画像，可用于后续复用

#### 4. topic_candidates（候选选题表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | VARCHAR(64) FK → tasks.id | 关联任务 |
| title | VARCHAR(200) | 选题标题 |
| angle | TEXT | 切入角度 |
| hook | TEXT | 钩子 |
| target_emotion | VARCHAR(50) | 目标情绪 |
| estimated_appeal | FLOAT | 预估吸引力 |
| reasoning | TEXT | 选题理由 |
| rank | INTEGER | 排序 |
| selected | BOOLEAN | 是否被选中 |
| created_at | DATETIME | 创建时间 |

**用途：** 存储选题策划的候选结果

#### 5. article_drafts（文章草稿表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | VARCHAR(64) FK → tasks.id | 关联任务 |
| title | VARCHAR(200) | 文章标题 |
| content_markdown | TEXT | Markdown 正文 |
| content_html | TEXT | HTML 正文（预渲染）|
| word_count | INTEGER | 字数 |
| structure | JSON | 文章结构 |
| tags | JSON | 标签 |
| status | VARCHAR(20) | draft / audited / approved / rejected |
| created_at | DATETIME | 创建时间 |

**用途：** 存储生成的文章草稿

#### 6. audit_results（审核结果表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| task_id | VARCHAR(64) FK → tasks.id | 关联任务 |
| draft_id | INTEGER FK → article_drafts.id | 关联草稿 |
| passed | BOOLEAN | 是否通过 |
| risk_level | VARCHAR(20) | low / medium / high |
| issues | JSON | 问题列表 |
| overall_comment | TEXT | 总体评价 |
| created_at | DATETIME | 创建时间 |

**用途：** 存储审核结果

#### 7. agents（智能体配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| agent_id | VARCHAR(64) PK | 智能体 ID |
| name | VARCHAR(100) | 名称 |
| description | TEXT | 描述 |
| version | VARCHAR(20) | 版本 |
| module_path | VARCHAR(200) | Python 模块路径 |
| model_config | JSON | 模型配置 |
| prompt_template | TEXT | prompt 模板 |
| input_schema | JSON | 输入 schema |
| output_schema | JSON | 输出 schema |
| required_skills | JSON | 依赖的 skill 列表 |
| retry_config | JSON | 重试配置 |
| fallback_config | JSON | 降级配置 |
| status | VARCHAR(20) | active / disabled |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**用途：** 持久化 agent 配置（manifest 加载后写入 DB，运行时配置修改也写回 DB）

#### 8. skills（技能配置表）

| 字段 | 类型 | 说明 |
|------|------|------|
| skill_id | VARCHAR(64) PK | 技能 ID |
| name | VARCHAR(100) | 名称 |
| description | TEXT | 描述 |
| version | VARCHAR(20) | 版本 |
| module_path | VARCHAR(200) | Python 模块路径 |
| input_schema | JSON | 输入 schema |
| output_schema | JSON | 输出 schema |
| config | JSON | 运行时配置 |
| status | VARCHAR(20) | active / disabled |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**用途：** 持久化 skill 配置

#### 9. workflow_templates（工作流模板表）

| 字段 | 类型 | 说明 |
|------|------|------|
| workflow_id | VARCHAR(64) PK | 工作流 ID |
| name | VARCHAR(100) | 名称 |
| description | TEXT | 描述 |
| version | VARCHAR(20) | 版本 |
| definition | JSON | 完整的工作流定义（nodes, mappings 等）|
| input_schema | JSON | 输入 schema |
| output_mapping | JSON | 输出映射 |
| status | VARCHAR(20) | active / disabled |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**用途：** 存储工作流模板定义

#### 10. system_logs（系统日志表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 自增 ID |
| trace_id | VARCHAR(64) | 链路追踪 ID |
| task_id | VARCHAR(64) | 关联任务（可为空）|
| node_id | VARCHAR(64) | 关联节点（可为空）|
| level | VARCHAR(10) | DEBUG / INFO / WARN / ERROR |
| module | VARCHAR(100) | 来源模块 |
| message | TEXT | 日志消息 |
| context | JSON | 上下文数据 |
| created_at | DATETIME | 时间戳 |

**用途：** 结构化系统日志，支持按 trace_id/task_id 检索

### 10.3 表关系图

```
tasks (1) ──→ (N) task_node_runs
tasks (1) ──→ (1) account_profiles
tasks (1) ──→ (N) topic_candidates
tasks (1) ──→ (N) article_drafts
article_drafts (1) ──→ (1) audit_results
tasks (N) ──→ (1) workflow_templates     (通过 workflow_id)
task_node_runs (N) ──→ (1) agents       (通过 agent_id)
system_logs (N) ──→ (1) tasks           (通过 task_id，可选)
```

---

## 第十一部分：异常、日志、可观测性设计

### 11.1 异常分层

| 层级 | 异常类型 | 示例 | 处理方式 |
|------|---------|------|---------|
| **用户输入异常** | `ValidationError` | positioning 为空、超长 | Gateway 层拦截，返回 400 + 明确提示 |
| **节点执行异常** | `AgentExecutionError` | LLM 返回格式错误、schema 校验失败 | 按 agent 降级策略处理（重试/默认值/跳过）|
| **第三方接口异常** | `ExternalAPIError` | 新闻 API 超时、LLM API 429 | Skill 层重试 + 限流；上报给 agent 做降级 |
| **配置异常** | `ConfigError` | manifest 格式错误、模块加载失败 | 系统启动时校验，阻止启动并输出明确错误 |
| **系统异常** | `InternalError` | 数据库连接失败、OOM | 记录完整堆栈，返回 500，触发告警 |

### 11.2 异常类层次

```python
class HotClawError(Exception):
    """基类"""
    code: int
    message: str

class ValidationError(HotClawError):     # 1001
class NotFoundError(HotClawError):        # 1002-1004
class ConflictError(HotClawError):        # 2001

class AgentExecutionError(HotClawError):  # 3xxx
class SkillExecutionError(HotClawError):
class ExternalAPIError(HotClawError):     # 3001-3003
class AgentTimeoutError(HotClawError):    # 3003

class ConfigError(HotClawError):          # 4xxx
class SchemaValidationError(HotClawError):

class InternalError(HotClawError):        # 5000
```

### 11.3 结构化日志设计

每条日志包含以下字段：

```json
{
  "timestamp": "2026-03-23T12:00:05.123Z",
  "level": "INFO",
  "trace_id": "tr_abc123",
  "task_id": "task_20260323_abc123",
  "node_id": "hot_topic_analysis",
  "agent_id": "hot_topic_agent",
  "module": "agents.hot_topic_agent",
  "event": "agent_execute_start",
  "message": "开始执行热点分析",
  "context": {
    "input_keys": ["profile"],
    "model": "gpt-4o-mini"
  },
  "duration_ms": null,
  "error": null
}
```

### 11.4 Trace ID / Task ID 机制

```
trace_id: 每个 HTTP 请求生成一个，贯穿整个请求生命周期
          格式: tr_{nanoid(12)}
          
task_id:  每个任务生成一个，贯穿任务所有节点
          格式: task_{date}_{nanoid(8)}
          
关系:     一个 trace_id 对应一个 API 请求
          一个 task_id 对应一个完整任务
          创建任务的请求: trace_id → task_id (1:1)
          SSE 流: 每次 SSE 连接有自己的 trace_id，但 task_id 不变
```

### 11.5 节点级运行日志

每个 agent 节点执行时自动记录：

| 时间点 | 记录内容 |
|--------|---------|
| 节点开始 | agent_id, input_data（脱敏）, model_config |
| LLM 调用 | prompt（脱敏）, model, temperature |
| LLM 返回 | raw_output, token_usage |
| Skill 调用 | skill_id, skill_input, skill_output |
| schema 校验 | 校验结果, 错误详情（如有）|
| 降级触发 | 原始错误, 降级策略, 降级结果 |
| 节点完成 | output_data（脱敏）, elapsed_ms |

### 11.6 错误回放能力

基于 `task_node_runs` 表的完整输入输出记录，支持：
- 按 task_id 回放完整执行链路
- 按 node_id 查看单个节点的详细输入输出
- 对比不同任务的同一节点执行差异
- 用历史输入重新执行某个 agent（调试用）

### 11.7 任务审计能力

每个任务的完整审计链：
```
任务创建 → [节点1: 输入→输出→耗时→token] → [节点2: ...] → ... → 任务完成
```
全部数据持久化在 DB 中，不存在"黑盒"环节。

---

## 第十二部分：项目目录结构

```
hotclaw/
├── frontend/                       # 前端项目
│   ├── public/
│   ├── src/
│   │   ├── api/                    # API 调用封装
│   │   │   ├── client.ts           # Axios 实例
│   │   │   ├── tasks.ts            # 任务相关 API
│   │   │   ├── agents.ts           # Agent 相关 API
│   │   │   └── skills.ts           # Skill 相关 API
│   │   ├── components/             # 通用组件
│   │   │   ├── Layout/
│   │   │   ├── NodeCard/
│   │   │   ├── PipelineView/
│   │   │   └── MarkdownPreview/
│   │   ├── pages/                  # 页面组件
│   │   │   ├── Home/
│   │   │   ├── TaskRun/
│   │   │   ├── TaskResult/
│   │   │   ├── AgentConfig/
│   │   │   ├── SkillConfig/
│   │   │   └── History/
│   │   ├── stores/                 # Zustand stores
│   │   │   ├── taskStore.ts
│   │   │   ├── configStore.ts
│   │   │   └── historyStore.ts
│   │   ├── hooks/                  # 自定义 hooks
│   │   │   └── useSSE.ts
│   │   ├── types/                  # TypeScript 类型
│   │   │   └── index.ts
│   │   ├── utils/                  # 工具函数
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                        # 后端项目
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── gateway/                # API 网关层
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── task_routes.py
│   │   │   │   ├── agent_routes.py
│   │   │   │   ├── skill_routes.py
│   │   │   │   └── stream_routes.py
│   │   │   └── middleware.py       # 中间件（trace_id 注入等）
│   │   ├── orchestrator/           # 工作流引擎
│   │   │   ├── __init__.py
│   │   │   ├── engine.py           # 核心引擎
│   │   │   ├── workspace.py        # Workspace 管理
│   │   │   └── broadcaster.py      # SSE 广播
│   │   ├── agents/                 # 智能体
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Agent 基类
│   │   │   ├── registry.py         # Agent 注册中心
│   │   │   ├── profile_agent.py
│   │   │   ├── hot_topic_agent.py
│   │   │   ├── topic_planner_agent.py
│   │   │   ├── title_generator_agent.py
│   │   │   ├── content_writer_agent.py
│   │   │   └── audit_agent.py
│   │   ├── skills/                 # 技能
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Skill 基类
│   │   │   ├── registry.py         # Skill 注册中心
│   │   │   ├── news_fetcher.py
│   │   │   ├── summary_skill.py
│   │   │   ├── risk_detector.py
│   │   │   └── title_scorer.py
│   │   ├── services/               # 业务服务
│   │   │   ├── __init__.py
│   │   │   ├── task_service.py
│   │   │   ├── config_service.py
│   │   │   └── draft_service.py
│   │   ├── models/                 # 数据模型
│   │   │   ├── __init__.py
│   │   │   └── tables.py
│   │   ├── schemas/                # Pydantic Schema
│   │   │   ├── __init__.py
│   │   │   ├── task.py
│   │   │   ├── agent.py
│   │   │   ├── skill.py
│   │   │   └── common.py
│   │   ├── core/                   # 核心工具
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # 应用配置
│   │   │   ├── database.py         # 数据库连接
│   │   │   ├── exceptions.py       # 统一异常
│   │   │   ├── logger.py           # 结构化日志
│   │   │   └── tracer.py           # 追踪
│   │   └── config/                 # 配置加载
│   │       ├── __init__.py
│   │       └── loader.py           # manifest 加载器
│   ├── alembic/                    # 数据库迁移
│   ├── tests/                      # 测试
│   ├── pyproject.toml
│   └── alembic.ini
│
├── manifests/                      # 声明式配置（核心）
│   ├── agents/                     # Agent manifests
│   │   ├── profile_agent.yaml
│   │   ├── hot_topic_agent.yaml
│   │   ├── topic_planner_agent.yaml
│   │   ├── title_generator_agent.yaml
│   │   ├── content_writer_agent.yaml
│   │   └── audit_agent.yaml
│   ├── skills/                     # Skill manifests
│   │   ├── news_fetcher.yaml
│   │   ├── summary_skill.yaml
│   │   ├── risk_detector.yaml
│   │   └── title_scorer.yaml
│   ├── workflows/                  # Workflow manifests
│   │   └── default_pipeline.yaml
│   └── schemas/                    # Meta-schemas（用于校验 manifest 格式）
│       ├── agent_manifest.schema.json
│       ├── skill_manifest.schema.json
│       └── workflow_manifest.schema.json
│
├── data/                           # 数据文件
│   ├── sensitive_words.txt         # 敏感词表
│   └── hotclaw.db                  # SQLite 数据库文件
│
├── scripts/                        # 脚本
│   ├── init_db.py                  # 初始化数据库
│   ├── validate_manifests.py       # 校验所有 manifest
│   └── dev.sh                      # 开发启动脚本
│
├── docs/                           # 文档（按需）
│
├── .env.example                    # 环境变量示例
├── .gitignore
└── README.md
```

**目录用途说明：**

| 目录 | 用途 |
|------|------|
| `frontend/` | React SPA 前端，独立构建部署 |
| `backend/` | FastAPI 后端，Python 项目 |
| `manifests/` | 所有声明式配置文件，agent/skill/workflow 的"注册表" |
| `data/` | 运行时数据文件（数据库、敏感词表等）|
| `scripts/` | 开发/运维脚本 |
| `docs/` | 项目文档（按需创建，不预先生成）|

---

## 第十三部分：开发顺序

### Phase 1：基础骨架（核心目标：跑通最小链路）

**核心交付物：**
- 后端 FastAPI 项目骨架（main.py, 路由, 数据库）
- Agent/Skill 基类与注册机制
- Manifest 加载器与配置校验
- Orchestrator 引擎（线性链执行）
- Workspace 上下文管理
- 1 个最简 agent（profile_agent）端到端跑通
- SSE 状态广播
- SQLite 数据库初始化

**验收标准：**
- `POST /api/v1/tasks` → 创建任务 → Orchestrator 调度 profile_agent → SSE 推送状态 → 数据入库
- manifest 校验通过后 agent 正确加载
- 非法 manifest 启动时报错

### Phase 2：全链路 Agent（核心目标：6 个 agent 全部跑通）

**核心交付物：**
- 6 个 agent 实现（profile → hot_topic → topic → title → content → audit）
- 4 个 skill 实现（news_fetcher → summary → title_scorer → risk_detector）
- 完整的 default_pipeline workflow
- 降级策略实现
- 节点运行记录持久化

**验收标准：**
- 输入一句话 → 系统自动跑完全链路 → 输出完整文章草稿
- 任一 agent 失败时降级不崩
- 所有节点运行记录可查

### Phase 3：前端 MVP（核心目标：可视化运行）

**核心交付物：**
- React 项目骨架
- 首页（任务创建）
- 任务运行页（SSE 实时状态卡片）
- 结果页（选题、标题、文章预览）
- 历史任务页

**验收标准：**
- 前端输入 → 后端运行 → 前端实时看到节点状态 → 看到最终文章
- 可查看历史任务

### Phase 4：配置管理（核心目标：Agent/Skill 可配置）

**核心交付物：**
- Agent 配置页（查看/修改 prompt、模型、参数）
- Skill 配置页（查看/修改配置）
- 配置修改 API
- 配置变更持久化

**验收标准：**
- 前端修改 agent prompt → 下次任务使用新 prompt
- 前端修改 skill 配置 → 立即生效

### Phase 5：打磨与健壮性（核心目标：可靠运行）

**核心交付物：**
- 完善错误处理与提示
- 日志查询界面
- 任务回放能力
- 环境配置与部署脚本
- 基础测试覆盖

**验收标准：**
- 连续运行 20 个任务无崩溃
- 错误场景有清晰的用户提示
- 可按 task_id 回溯完整执行链

---

## 第十四部分：技术选型建议

### 前端技术栈

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **React 18 + TypeScript** | 生态最大，组件库选择多，SSE 处理成熟 | Vue 3（也可以，如果你更熟悉） |
| **Vite** | 构建速度快，配置简单 | Next.js（SSR 不需要，过重） |
| **Zustand** | 轻量状态管理，无 boilerplate | Redux Toolkit（也行，但 MVP 过重）/ Jotai |
| **Ant Design 5** | 中文生态好，企业级组件全 | Shadcn/ui（更灵活但需要更多定制） |
| **Axios** | 拦截器好、请求取消方便 | fetch（够用但不方便） |

### 后端技术栈

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **Python 3.11+** | AI/LLM 生态最好 | Node.js（LLM SDK 不如 Python 全） |
| **FastAPI** | 异步、自动文档、Pydantic 集成、SSE 支持 | Flask（不够现代）/ Django（过重） |
| **SQLAlchemy 2.0** | 成熟 ORM，async 支持，后续可切数据库 | Tortoise-ORM（较小众） |
| **Pydantic v2** | 和 FastAPI 无缝，性能好，JSON Schema 导出 | dataclasses（校验能力不足） |
| **litellm** | 统一多模型调用，切模型只需改配置 | 直接用 openai SDK（只支持 OpenAI 兼容接口） |

### 数据库

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **SQLite**（MVP） | 零部署，单文件，Python 原生 | PostgreSQL（MVP 不需要，后续升级） |

### 队列/缓存

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **内存缓存 (dict/lru_cache)**（MVP） | 零依赖，MVP 足够 | Redis（后续加，MVP 不需要外部依赖） |
| **asyncio 原生**（任务队列） | MVP 单进程，不需要 Celery | Celery + Redis（后续扩展时加） |

### 可视化方案

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **Ant Design Card + 自定义 CSS** | MVP 用卡片流水线足够，实现简单 | ReactFlow（DAG 可视化，Phase 2+ 扩展时引入） |

### 日志追踪方案

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **structlog**（Python 结构化日志） | 零外部依赖，JSON 日志 | loguru（也不错，但 structlog 更适合结构化） |
| **SQLite system_logs 表** | 入库可查询，MVP 足够 | ELK / Loki（后续规模化时引入） |

### 配置校验方案

| 选择 | 理由 | 替代方案 |
|------|------|---------|
| **Pydantic v2** | 运行时校验，和 FastAPI 同栈 | jsonschema 库（也可以，但 Pydantic 更 Pythonic） |
| **YAML manifests** | 人类可读，git 友好 | TOML（也行）/ JSON（不够可读） |

---

## 第十五部分：最终输出

### 1. 系统总体描述（适合写进项目开题书）

> HotClaw（热爪）是一个面向公众号内容创作场景的多智能体协作平台。用户仅需输入账号定位描述，系统即自动编排"账号画像解析→热点抓取分析→选题策划→标题生成→正文撰写→审核风控"六大智能体，以流水线方式完成从零到一的爆文内容生产。系统采用前后端分离架构，后端以 Python FastAPI 为核心，通过 Orchestrator 引擎调度声明式注册的 Agent 和 Skill，全链路运行状态通过 SSE 实时推送至 React 前端进行可视化展示。所有 Agent 的输入输出均遵循 JSON Schema 规范，执行过程全量持久化，支持任务回放与审计。系统以 Manifest-First 理念设计，新增 Agent 或 Skill 只需编写代码实现并添加 YAML 配置文件，无需修改框架代码，具备良好的可扩展性和可维护性。

### 2. 亮点描述（适合简历/项目介绍）

> 独立设计并实现了一个多智能体公众号内容生产平台，核心亮点包括：(1) 控制平面与执行平面分离的 Orchestrator 架构，支持声明式工作流编排；(2) Manifest-First 的 Agent/Skill 注册机制，新增能力零框架代码修改；(3) Workspace 上下文隔离机制，保障多任务并发安全；(4) 全链路结构化输入输出 + 节点级运行记录持久化，支持任务回放与审计；(5) SSE 实时状态推送 + 流水线可视化前端；(6) Agent 级降级策略，单节点故障不阻断全链路。技术栈：React + TypeScript + Zustand / Python + FastAPI + SQLAlchemy + Pydantic + litellm。

### 3. 第一版目录树

```
hotclaw/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── tasks.ts
│   │   │   ├── agents.ts
│   │   │   └── skills.ts
│   │   ├── components/
│   │   │   ├── Layout/
│   │   │   │   ├── AppLayout.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   ├── NodeCard/
│   │   │   │   └── NodeCard.tsx
│   │   │   ├── PipelineView/
│   │   │   │   └── PipelineView.tsx
│   │   │   └── MarkdownPreview/
│   │   │       └── MarkdownPreview.tsx
│   │   ├── pages/
│   │   │   ├── Home/
│   │   │   │   └── HomePage.tsx
│   │   │   ├── TaskRun/
│   │   │   │   └── TaskRunPage.tsx
│   │   │   ├── TaskResult/
│   │   │   │   └── TaskResultPage.tsx
│   │   │   ├── AgentConfig/
│   │   │   │   ├── AgentConfigPage.tsx
│   │   │   │   └── AgentDetailPage.tsx
│   │   │   ├── SkillConfig/
│   │   │   │   └── SkillConfigPage.tsx
│   │   │   └── History/
│   │   │       └── HistoryPage.tsx
│   │   ├── stores/
│   │   │   ├── taskStore.ts
│   │   │   ├── configStore.ts
│   │   │   └── historyStore.ts
│   │   ├── hooks/
│   │   │   └── useSSE.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── gateway/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── task_routes.py
│   │   │   │   ├── agent_routes.py
│   │   │   │   ├── skill_routes.py
│   │   │   │   └── stream_routes.py
│   │   │   └── middleware.py
│   │   ├── orchestrator/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── workspace.py
│   │   │   └── broadcaster.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── profile_agent.py
│   │   │   ├── hot_topic_agent.py
│   │   │   ├── topic_planner_agent.py
│   │   │   ├── title_generator_agent.py
│   │   │   ├── content_writer_agent.py
│   │   │   └── audit_agent.py
│   │   ├── skills/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── news_fetcher.py
│   │   │   ├── summary_skill.py
│   │   │   ├── risk_detector.py
│   │   │   └── title_scorer.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── task_service.py
│   │   │   ├── config_service.py
│   │   │   └── draft_service.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── tables.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── task.py
│   │   │   ├── agent.py
│   │   │   ├── skill.py
│   │   │   └── common.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── exceptions.py
│   │   │   ├── logger.py
│   │   │   └── tracer.py
│   │   └── config/
│   │       ├── __init__.py
│   │       └── loader.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic.ini
│
├── manifests/
│   ├── agents/
│   │   ├── profile_agent.yaml
│   │   ├── hot_topic_agent.yaml
│   │   ├── topic_planner_agent.yaml
│   │   ├── title_generator_agent.yaml
│   │   ├── content_writer_agent.yaml
│   │   └── audit_agent.yaml
│   ├── skills/
│   │   ├── news_fetcher.yaml
│   │   ├── summary_skill.yaml
│   │   ├── risk_detector.yaml
│   │   └── title_scorer.yaml
│   ├── workflows/
│   │   └── default_pipeline.yaml
│   └── schemas/
│       ├── agent_manifest.schema.json
│       ├── skill_manifest.schema.json
│       └── workflow_manifest.schema.json
│
├── data/
│   └── sensitive_words.txt
│
├── scripts/
│   ├── init_db.py
│   └── validate_manifests.py
│
├── .env.example
└── .gitignore
```

### 4. 下一步最应该先写的文件清单

按优先级排序，Phase 1 必须先完成的文件：

| 优先级 | 文件 | 说明 |
|--------|------|------|
| **P0** | `backend/app/main.py` | FastAPI 入口，应用初始化，挂载路由 |
| **P0** | `backend/app/core/config.py` | 应用配置（环境变量、路径、模型 API key）|
| **P0** | `backend/app/core/database.py` | SQLite 连接与 session 管理 |
| **P0** | `backend/app/models/tables.py` | 全部数据表定义 |
| **P0** | `backend/app/core/exceptions.py` | 统一异常类 |
| **P0** | `backend/app/core/logger.py` | 结构化日志 |
| **P0** | `backend/app/core/tracer.py` | trace_id 生成与传播 |
| **P1** | `backend/app/schemas/common.py` | 统一响应格式 |
| **P1** | `backend/app/schemas/task.py` | 任务相关 schema |
| **P1** | `backend/app/agents/base.py` | Agent 基类 |
| **P1** | `backend/app/skills/base.py` | Skill 基类 |
| **P1** | `backend/app/agents/registry.py` | Agent 注册中心 |
| **P1** | `backend/app/skills/registry.py` | Skill 注册中心 |
| **P1** | `backend/app/config/loader.py` | Manifest YAML 加载器 |
| **P1** | `backend/app/orchestrator/workspace.py` | Workspace 上下文管理 |
| **P1** | `backend/app/orchestrator/engine.py` | Orchestrator 引擎 |
| **P1** | `backend/app/orchestrator/broadcaster.py` | SSE 广播 |
| **P2** | `backend/app/gateway/routes/task_routes.py` | 任务 API 路由 |
| **P2** | `backend/app/gateway/routes/stream_routes.py` | SSE 流路由 |
| **P2** | `backend/app/gateway/middleware.py` | trace_id 注入中间件 |
| **P2** | `backend/app/services/task_service.py` | 任务服务 |
| **P2** | `backend/app/agents/profile_agent.py` | 第一个 agent 实现 |
| **P3** | `manifests/agents/profile_agent.yaml` | 第一个 agent manifest |
| **P3** | `manifests/workflows/default_pipeline.yaml` | 工作流定义 |
| **P3** | `manifests/schemas/*.json` | Meta-schema 定义 |
| **P3** | `backend/pyproject.toml` | Python 项目配置 |
| **P3** | `.env.example` | 环境变量示例 |
| **P3** | `.gitignore` | Git 忽略规则 |

---

> **建议的启动顺序：** 先写 P0（基础设施）→ P1（框架骨架）→ P2（第一条 API 链路）→ P3（配置文件），争取尽快跑通"创建任务 → 调度 1 个 agent → SSE 推送状态 → 结果入库"的最小闭环。
