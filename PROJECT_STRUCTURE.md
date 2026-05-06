# HotClaw 项目结构详解

> 更新时间: 2026-03-31
> 项目定位: 多智能体公众号内容生产平台

---

## 项目概述

HotClaw 是一个**多智能体协作的公众号内容自动生成平台**。用户输入账号定位描述后，6 个 AI 智能体串联流水线，自动完成从账号画像分析到文章审核的全流程。

**技术栈速查表：**

| 层级 | 技术 | 核心作用 |
|------|------|---------|
| 后端框架 | FastAPI + Uvicorn | 异步 REST API |
| ORM | SQLAlchemy 2.0 (Async) | 数据库操作 |
| 数据库 | SQLite（开发）/ MySQL（生产）| 数据持久化 |
| LLM 调用 | LiteLLM | 统一大模型接口 |
| LLM Providers | DashScope / OpenAI / DeepSeek | 具体大模型服务 |
| 前端框架 | Next.js 16 + React 19 | Web 应用 |
| 状态管理 | Zustand | 前端全局状态 |
| 样式方案 | Tailwind CSS 4 + CSS Variables | 设计系统 |
| 实时通信 | Server-Sent Events (SSE) | 任务状态推送 |
| 构建工具 | Turbopack | Next.js 快速构建 |

---

## 一、整体目录结构

```
hotclaw/
├── backend/                          # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py                  # FastAPI 应用入口 + 生命周期
│   │   ├── core/                    # 核心基础设施
│   │   ├── db/                      # 数据库会话管理
│   │   ├── models/                  # SQLAlchemy ORM 模型
│   │   ├── schemas/                 # Pydantic 请求/响应模型
│   │   ├── api/                     # API 路由层
│   │   ├── services/                # 业务逻辑层
│   │   ├── agents/                  # AI 智能体实现
│   │   ├── skills/                  # 技能系统
│   │   ├── orchestrator/             # 工作流编排引擎
│   │   └── llm/                     # LLM 统一网关
│   ├── alembic/                     # 数据库迁移脚本
│   └── tests/                       # 单元测试
│
├── frontend/                        # Next.js 16 前端
│   ├── app/                        # App Router 页面文件
│   ├── components/                 # React 组件库
│   │   ├── command-center/         # 深空指挥舱界面（最新版）
│   │   ├── control-room/           # 控制室界面（旧版）
│   │   └── office/                 # 像素风办公室场景（旧版）
│   ├── hooks/                     # 自定义 React Hooks
│   ├── lib/                       # 工具库（API 客户端）
│   ├── store/                    # Zustand 状态管理
│   ├── types/                    # TypeScript 类型定义
│   └── public/                  # 静态资源（素材图）
│
├── .env                            # 环境变量
├── ARCHITECTURE.md               # 架构设计文档
└── hotclaw_named_assets_pack/   # 命名规范资源包
```

---

## 二、后端目录详解

### 2.1 `backend/app/` — 应用核心

#### `main.py` — 应用入口

**功能：** FastAPI 应用初始化、全局异常处理、CORS 配置

```python
app = FastAPI(title="HotClaw", version="0.1.0")
```

**面试点：**
- FastAPI 生命周期管理 (`startup` / `shutdown` 事件)
- 全局异常处理器 `@app.exception_handler()`
- 错误码设计：code // 1000 映射 HTTP 状态码 (1→400, 3→500 等)
- CORS 中间件配置
- `app.state` 用于存储应用级状态

#### `core/` — 核心基础设施

##### `config.py` — 配置管理

**使用 Pydantic BaseSettings：**
```python
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./hotclaw.db"
    OPENAI_API_KEY: str | None = None
    DASHSCOPE_API_KEY: str | None = None
    # ...
```

**面试点：**
- Pydantic v2 `BaseSettings` 自动读取环境变量
- 类型注解 + 默认值实现配置校验
- 支持 `.env` 文件覆盖

##### `exceptions.py` — 统一异常体系

**分类错误码设计：**

| 错误码段 | 含义 | HTTP 状态码 |
|---------|------|------------|
| 1xxx | 用户输入错误 | 400 |
| 2xxx | 冲突错误 | 409 |
| 3xxx | 外部/执行错误 | 502 |
| 4xxx | 配置错误 | 500 |
| 5xxx | 系统错误 | 500 |

```python
class AppException(Exception):
    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
```

**面试点：**
- 错误码分类设计思想
- 自定义异常 + 全局统一处理
- 错误信息的面向用户 / 面向开发者分层

##### `logger.py` — 结构化日志

**面试点：**
- `trace_id` 链路追踪
- 日志级别配置
- 结构化日志 (JSON 格式) 便于 ELK 收集

---

### 2.2 `db/` — 数据库层

#### `session.py` — 异步数据库会话

```python
async def get_db():
    async with AsyncSession(engine) as session:
        yield session
```

**面试点：**
- `asyncgenerator` + `yield` 实现依赖注入
- SQLAlchemy AsyncSession 的正确用法
- `async with` 上下文管理器确保连接释放
- `engine` 由 `create_async_engine()` 创建
- `config_async_session` 配置事务自动提交/回滚

---

### 2.3 `models/` — ORM 模型

#### `tables.py` — 所有数据库表定义

**核心模型一览：**

| 模型名 | 用途 | 关键字段 |
|-------|------|---------|
| `TaskModel` | 任务主表 | id, positioning, status, created_at |
| `TaskNodeRunModel` | 节点执行记录 | task_id, node_id, status, started_at, completed_at |
| `AccountProfileModel` | 账号画像 | task_id, domain, target_audience |
| `TopicCandidateModel` | 选题候选 | task_id, topic, direction |
| `ArticleDraftModel` | 文章草稿 | task_id, title, content_md |
| `AuditResultModel` | 审核结果 | task_id, overall_score, risk_level |
| `AgentModel` | 智能体配置 | agent_id, name, enabled |
| `SkillModel` | 技能配置 | skill_id, name |
| `LLMProviderModel` | LLM Provider | provider_id, provider_type, config |
| `SystemConfigModel` | 系统配置 KV | key, value |

**面试点：**
- SQLAlchemy 2.0 `Mapped` 类型注解写法
- `relationship` 配置级联删除 (`cascade="all, delete-orphan"`)
- JSON 字段存储结构化数据 (profile_data, topics, config 等)
- SQLite/MySQL 兼容的数据类型选择

---

### 2.4 `schemas/` — Pydantic 模型

**用于 API 请求/响应序列化 + 数据验证：**

```python
# task.py
class TaskCreateRequest(BaseModel):
    positioning: str = Field(..., min_length=5, max_length=1000)

class TaskCreateResponse(BaseModel):
    task_id: str
    message: str

class TaskDetailResponse(BaseModel):
    task_id: str
    status: str
    positioning: str
    result_data: dict | None
```

**面试点：**
- Pydantic v2 `model_config` 配置
- `Field()` 精细化验证
- API 层的 DTO (Data Transfer Object) 模式
- Request/Response 模型分离的好处

---

### 2.5 `api/` — API 路由层

#### `task_routes.py` — 任务管理 API

```
POST   /api/v1/tasks              # 创建任务
GET    /api/v1/tasks              # 列出任务
GET    /api/v1/tasks/{task_id}   # 任务详情
```

```python
@router.post("/tasks", response_model=TaskCreateResponse)
async def create_task(body: TaskCreateRequest, db: AsyncSession):
    task = await TaskService.create_task(db, body.positioning)
    # 后台启动编排引擎
    asyncio.create_task(run_task_pipeline(task.task_id))
    return TaskCreateResponse(task_id=task.task_id)
```

**面试点：**
- FastAPI `Depends` 依赖注入
- `response_model` 自动序列化
- `asyncio.create_task()` 非阻塞启动后台任务
- RESTful API 设计规范

#### `stream_routes.py` — SSE 实时流 API

```
GET /api/v1/tasks/{task_id}/stream   # SSE 事件流
```

```python
@router.get("/tasks/{task_id}/stream")
async def stream_task_events(task_id: str, db: AsyncSession):
    async def event_generator():
        q = asyncio.Queue()
        # 注册订阅
        SSEBroadcaster.register(task_id, q)
        try:
            while True:
                data = await q.get()  # 阻塞等待广播
                yield f"event: {data['event']}\ndata: {data['json']}\n\n"
        finally:
            SSEBroadcaster.unregister(task_id, q)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**面试点：**
- Server-Sent Events 协议格式: `event: xxx\ndata: {}\n\n`
- `StreamingResponse` 配合 `async generator`
- 订阅者模式 (`register` / `unregister`)
- 长连接的生命周期管理 (在 `finally` 中取消订阅)

#### `agent_routes.py` — 智能体配置 API

```
GET    /api/v1/agents              # 列出智能体
GET    /api/v1/agents/{agent_id}   # 智能体详情
PATCH  /api/v1/agents/{agent_id}   # 更新智能体配置
```

#### `llm_provider_routes.py` — LLM 配置 API

```
GET    /api/v1/llm-providers
POST   /api/v1/llm-providers
PATCH  /api/v1/llm-providers/{provider_id}
DELETE /api/v1/llm-providers/{provider_id}
```

**面试点：**
- CRUD API 最佳实践
- 路径参数 + 查询参数处理
- RESTful 动词语义 (GET/POST/PATCH/DELETE)

---

### 2.6 `services/` — 业务逻辑层

#### `task_service.py`

```python
async def create_task(db: AsyncSession, positioning: str) -> TaskModel:
    task = TaskModel(task_id=generate_task_id(), positioning=positioning)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

async def get_task_detail(db: AsyncSession, task_id: str) -> dict:
    # 聚合查询: task + nodes + profile + topics + content + audit
```

**面试点：**
- Service 层的职责 (事务管理 + 业务逻辑)
- Repository 模式 (数据访问抽象)
- `db.refresh()` 触发 ORM 更新

---

### 2.7 `agents/` — AI 智能体实现 ⭐⭐⭐

#### `base.py` — 智能体基类

```python
class BaseAgent(ABC):
    agent_id: str
    name: str

    @abstractmethod
    async def run(self, workspace: Workspace, profile: dict, deps: dict) -> AgentResult:
        ...

    def extract_for_agent(self, agent_id: str, deps: dict) -> dict:
        """从 deps 中提取本智能体需要的数据"""
```

**面试点：**
- ABC 抽象基类实现模板方法模式
- `abstractmethod` 强制子类实现
- `AgentResult` 统一返回格式
- `extract_for_agent` 权限控制思维

#### `registry.py` — 智能体注册表

```python
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {}

def register(agent_id: str, agent_cls: type[BaseAgent]):
    AGENT_REGISTRY[agent_id] = agent_cls

def get_agent(agent_id: str) -> BaseAgent:
    return AGENT_REGISTRY[agent_id]()
```

**面试点：**
- 注册表模式实现插件化架构
- 新增智能体只需 `register()` 即可自动被发现
- `dict[str, type[BaseAgent]]` 类型注解

#### 6 个具体智能体

| 智能体 | 文件 | 核心功能 | 面试考察点 |
|-------|------|---------|-----------|
| ProfileAgent | `profile_agent.py` | 解析账号定位 → 结构化画像 | 正则提取、多维字段生成 |
| HotTopicAgent | `hot_topic_agent.py` | 多搜索引擎并发抓取热点 | `asyncio.gather` 并发、`re` HTML 解析 |
| TopicPlannerAgent | `topic_planner_agent.py` | 基于画像+热点策划选题 | LLM 结构化 JSON 输出 |
| TitleGeneratorAgent | `title_generator_agent.py` | 为每个选题生成候选标题 | 多标题策略、点击率预测 |
| ContentWriterAgent | `content_writer_agent.py` | 撰写 1500-3000 字 Markdown 文章 | 超长文本生成、超时处理 |
| AuditAgent | `audit_agent.py` | 合规检查 + 质量评分 | 风险等级评估、多维度打分 |

**HotTopicAgent 关键代码：**
```python
SEARCH_ENGINES = [
    {"name": "微信搜索", "url": "https://wx.sogou.com/weixin?type=2&query={keyword}"},
    {"name": "搜狗搜索", "url": "https://sogou.com/web?query={keyword}"},
    {"name": "360搜索", "url": "https://www.so.com/s?q={keyword}"},
]

async def run(self, workspace, profile, deps):
    keyword = f"{profile['domain']} {profile['subdomain']}"
    # 并发抓取多个搜索引擎
    results = await asyncio.gather(
        *[fetch_engine(engine, keyword) for engine in SEARCH_ENGINES],
        return_exceptions=True
    )
```

**面试点：**
- `asyncio.gather(return_exceptions=True)` 收集所有结果
- HTML 字符串正则解析
- LLM JSON 输出解析

---

### 2.8 `orchestrator/` — 工作流编排引擎 ⭐⭐⭐

#### `engine.py` — 编排引擎

**流水线定义：**
```python
PIPELINE = [
    "profile_agent",
    "hot_topic_agent",
    "topic_planner_agent",
    "title_generator_agent",
    "content_writer_agent",
    "audit_agent",
]
```

**执行流程：**
```python
async def run_task_pipeline(task_id: str):
    workspace = Workspace(task_id)
    workspace.set_positioning(positioning)

    for node_id in PIPELINE:
        # 1. 启动节点
        await broadcaster.emit(task_id, "node_start", {
            "node_id": node_id,
            "agent_id": node_id.replace("_agent", ""),
        })

        # 2. 执行智能体 (带超时)
        try:
            result = await asyncio.wait_for(
                agent.run(workspace, workspace.profile, deps),
                timeout=300
            )
            # 3. 完成节点
            await broadcaster.emit(task_id, "node_complete", result)
        except asyncio.TimeoutError:
            await broadcaster.emit(task_id, "node_error", {"error": "timeout"})
            # 4. 降级/中断策略
            if agent.required:
                break
```

**面试点：**
- `asyncio.wait_for()` 实现超时控制
- 前置智能体结果通过 `deps` 传递（Pipeline Pattern）
- 降级策略 (Fallback / Required Flag)
- Workspace 模式隔离不同任务的数据

#### `broadcaster.py` — SSE 广播器

```python
class SSEBroadcaster:
    _subscribers: dict[str, list[asyncio.Queue]] = {}
    _history: dict[str, deque[dict]] = {}  # 历史缓冲

    @classmethod
    def register(cls, task_id: str, queue: asyncio.Queue):
        cls._subscribers.setdefault(task_id, []).append(queue)
        # 重放历史事件给新订阅者
        for event in cls._history.get(task_id, []):
            await queue.put(event)

    @classmethod
    async def emit(cls, task_id: str, event: str, data: dict):
        payload = {"event": event, "data": data}
        cls._history.setdefault(task_id, deque(maxlen=100)).append(payload)
        for q in cls._subscribers.get(task_id, []):
            await q.put(payload)
```

**面试点：**
- `asyncio.Queue` 实现发布-订阅
- **历史缓冲**解决 SSE 竞态问题（任务已开始但连接未建立）
- `deque(maxlen=100)` 自动淘汰旧事件
- 新订阅者自动重放已发送事件
- 60 秒延迟清理防止内存泄漏

#### `workspace.py` — 工作空间

```python
class Workspace:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.positioning = ""
        self.profile: dict = {}
        self.hot_topics: dict = {}
        self.topics: list = []
        self.selected_title: dict = {}
        self.content: dict = {}
        self.audit: dict = {}

    def save_agent_output(self, agent_id: str, data: dict):
        setattr(self, agent_id.replace("_agent", ""), data)
```

**面试点：**
- Workspace 作为数据传递的载体
- 智能体按需读取前置输出
- `setattr()` 动态设置属性

---

### 2.9 `llm/` — LLM 统一网关 ⭐⭐⭐

#### `gateway.py` — 门面模式网关

```python
class LLMGateway:
    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._load_providers()

    async def acomplete(self, prompt: str, **kwargs) -> str:
        provider = self._get_provider(kwargs.get("provider"))
        return await provider.acomplete(prompt, **kwargs)

    async def acomplete_json(self, prompt: str, **kwargs) -> dict:
        """带 Markdown JSON 块解析的 LLM 调用"""
        text = await self.acomplete(prompt, **kwargs)
        return self._parse_json(text)
```

**面试点：**
- **Facade 门面模式**：统一入口，对外隐藏多 Provider 细节
- JSON 块解析（` ```json ... ``` `）
- Provider 按优先级选择（数据库配置 > 环境变量）

#### `providers/` — 各 Provider 实现

| Provider | 文件 | 特点 |
|---------|------|------|
| DashScope | `dashscope.py` | 阿里云通义千问/Qwen |
| OpenAI | `openai.py` | 标准 OpenAI API |
| DeepSeek | `deepseek.py` | DeepSeek 系列 |
| Compatible | `compatible.py` | 兼容 OpenAI 接口的其他模型 |

```python
class DashScopeProvider(LLMProvider):
    async def acomplete(self, prompt: str, **kwargs) -> str:
        response = await dashscope.TextGeneration.call(
            model=kwargs.get("model", "qwen-turbo"),
            prompt=prompt,
            api_key=self.config.get("api_key"),
        )
        return response.output.text
```

---

## 三、前端目录详解

### 3.1 `app/` — Next.js App Router

#### `layout.tsx` — 根布局

```typescript
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
```

**面试点：**
- Next.js 16 App Router 根布局
- Server Component 默认（无 "use client"）
- `lang="zh-CN"` 语义化 HTML

#### `page.tsx` — 首页（入口）

```typescript
"use client"
import CommandCenter from "../components/command-center/CommandCenter"
export default function HomePage() {
  return <CommandCenter />
}
```

**面试点：**
- `"use client"` 指令标记客户端组件
- 页面级组件直接导入子组件
- App Router 中 Server/Client 组件分离

#### `globals.css` — 设计系统 ⭐⭐

**完整的 CSS 设计系统：**

```css
/* 颜色系统 */
:root {
  --cc-void: #020509;           /* 深空黑背景 */
  --cc-cyan: #00e5ff;          /* 青色主光 */
  --cc-purple: #8b5cf6;        /* 紫色辅助 */
  --cc-active: #22c55e;        /* 运行中绿 */
  --cc-error: #ef4444;         /* 错误红 */
}

/* 动画系统 */
@keyframes cc-pulse { 0%, 100% { opacity: 1 } 50% { opacity: 0.35 } }
@keyframes cc-ring-spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
@keyframes cc-slide-up { from { opacity: 0; transform: translateY(12px) } to { opacity: 1 } }
@keyframes cc-light-flow { 0% { stroke-dashoffset: 60 } 100% { stroke-dashoffset: 0 } }
```

**面试点：**
- CSS Variables 实现设计系统 token
- HSL 颜色规范
- `linear-gradient` / `radial-gradient` 光效
- `@keyframes` 自定义动画
- 伪元素 `::before` / `::after` 构建装饰层

#### 路由结构

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | CommandCenter | 指挥舱首页（最新 UI）|
| `/newsroom` | CommandCenter | 新闻编辑室（同首页）|
| `/task/[id]` | 任务详情 | 查看任务完整产出 |
| `/settings/agents` | 智能体配置 | AgentModel CRUD |
| `/settings/llm-providers` | LLM 配置 | LLMProviderModel CRUD |
| `/history` | 历史任务 | 任务列表 |

---

### 3.2 `components/command-center/` — 深空指挥舱 ⭐⭐⭐

这是最新的 UI 设计，采用"深空 + 全息"视觉风格。

#### `CommandCenter.tsx` — 主组件

**环形轨道布局：**
```typescript
// 6 个节点围绕中心控制台圆形分布
const NODE_ORBIT = [
  { x: 0,   y: -30 },  // 0: 顶部
  { x: 26,  y: -15 },  // 1: 右上
  { x: 26,  y:  15 },  // 2: 右下
  { x: 0,   y:  30 },  // 3: 底部
  { x: -26, y:  15 },  // 4: 左下
  { x: -26, y: -15 },  // 5: 左上
]
```

**核心状态：**
```typescript
const { nodes, taskDone, taskError, isConnected, reset } = useTaskSSE(taskId)
```

**面试点：**
- 圆形轨道布局计算 (`calc(50% + x%)`)
- `useTaskSSE` Hook 封装 SSE 逻辑
- React `useState` / `useCallback` 最佳实践
- `useEffect` 副作用管理 (定时器、订阅)

#### `CentralConsole.tsx` — 中央控制台

**关键交互：**
```typescript
// textarea 值变化 → 触发 React 状态更新
onChange={(e) => onChange(e.target.value)}

// 提交 → 创建任务 → 建立 SSE 连接
async function handleCreateTask() {
  const data = await createTask(positioning)
  setTaskId(data.task_id)  // 触发 useTaskSSE 建立 SSE
}
```

**面试点：**
- 受控组件 (Controlled Component)
- 异步事件处理 (`async/await`)
- 按钮禁用状态管理
- 进度条 CSS 动画 (`transition: width`)

#### `AgentNode.tsx` — 智能体节点

**状态驱动的 CSS 类：**
```typescript
<div className={`cc-node-shell ${agent.status}`}>
  {/* pending: 灰边 / active: 绿色脉冲 / done: 青色光晕 / error: 红色闪烁 */}
```

**节点悬浮信息：**
```typescript
{/* 悬浮显示详情 (仅非 pending 状态) */}
{(isActive || isDone || isError) && (
  <div className="cc-node-info">
    <div className="cc-node-info-desc">{agent.description}</div>
    <div className="cc-node-info-console active">数据处理中...</div>
  </div>
)}
```

**面试点：**
- 条件渲染优化
- CSS 组合类名
- 内联样式 + CSS 变量混合

#### `HoloLines.tsx` — 全息连接线

**SVG 贝塞尔曲线：**
```typescript
<path
  d={`M ${from.cx} ${from.cy} Q ${mx} ${my} ${to.cx} ${to.cy}`}
  className="cc-holo-flow"
  strokeDasharray="6 12"
  // 流动动画: stroke-dashoffset 从 60 → 0
  // active 时动画速率快, done 时速率慢
/>
```

**面试点：**
- SVG `<path>` + 贝塞尔曲线 `Q` 命令
- `stroke-dasharray` + `stroke-dashoffset` 实现描边动画
- CSS `animation` 控制流动粒子
- SVG 填充颜色按节点状态变化

#### `MissionStatusBar.tsx` — 顶部状态栏

```typescript
<div style={{ display: "flex", alignItems: "center", gap: 7 }}>
  <div className={`cc-sdot ${isConnected ? "active" : "pending"}`} />
  <span>{isConnected ? "链路传输中" : "待命"}</span>
</div>
```

#### `AgentDetailModal.tsx` — 详情弹窗

**面试点：**
- `useEffect` + `keydown` 监听 ESC 关闭
- Backdrop 遮罩层 + 动画
- 键盘无障碍 (focus trap 可进一步优化)

---

### 3.3 `hooks/useTaskSSE.ts` — SSE 通信 Hook ⭐⭐⭐

```typescript
export function useTaskSSE(taskId: string | null) {
  const [nodes, setNodes] = useState<NodeState[]>(INITIAL_NODES.map(...))

  useEffect(() => {
    if (!taskId) return
    reset()
    const es = new EventSource(getTaskStreamUrl(taskId))

    es.addEventListener("node_start", (e) => {
      const data = JSON.parse(e.data)
      setNodes(prev => prev.map(n =>
        n.node_id === data.node_id ? { ...n, status: "running" } : n
      ))
    })

    es.addEventListener("node_complete", (e) => {
      const data = JSON.parse(e.data)
      setNodes(prev => prev.map(n =>
        n.node_id === data.node_id ? { ...n, status: "completed", ...data } : n
      ))
    })

    es.onerror = () => {
      // ⚠️ 不关闭连接，让浏览器自动重连
      console.warn("[SSE] Connection error, auto-reconnecting...")
    }

    return () => es.close()
  }, [taskId])

  return { nodes, taskDone, taskError, isConnected }
}
```

**关键设计决策：**

1. **`es.onerror` 不调用 `es.close()`** — 允许浏览器 EventSource 自动重连（指数退避）
2. **直连后端绕过代理** — `http://localhost:8002` 避免 Next.js 开发服务器缓冲 SSE
3. **React 状态批量更新** — `setNodes(prev => ...)` 基于前一状态
4. **清理函数** — `return () => es.close()` 组件卸载时断开连接

**面试点：**
- EventSource API (`addEventListener` / `onerror`)
- SSE 相比 WebSocket 的优势（单向推送、更简单、超时友好）
- Next.js 开发服务器对 SSE 的影响（缓冲问题）
- React Hooks 依赖数组设计
- `JSON.parse` 错误处理

---

### 3.4 `lib/api.ts` — API 客户端

```typescript
const BASE = "/api/v1"

export function getTaskStreamUrl(taskId: string): string {
  if (typeof window !== "undefined") {
    // SSE 必须直连后端，绕过 Next.js 代理缓冲
    return `http://${window.location.hostname}:8002${BASE}/tasks/${taskId}/stream`
  }
  return `${BASE}/tasks/${taskId}/stream`
}

export async function createTask(positioning: string) {
  const res = await fetch(`${BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ positioning }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

**面试点：**
- `typeof window !== "undefined"` 判断 SSR/CSR 环境
- `fetch` API + `async/await`
- 错误处理 (`throw new Error`)
- API 路径代理配置 (`next.config.ts` rewrites)

---

### 3.5 `store/taskStore.ts` — Zustand 状态管理

```typescript
import { create } from 'zustand'

interface TaskStore {
  activeTaskId: string | null
  activePositioning: string | null
  setActiveTask: (taskId: string, positioning: string) => void
  clearActiveTask: () => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  activeTaskId: null,
  activePositioning: null,
  setActiveTask: (taskId, positioning) =>
    set({ activeTaskId: taskId, activePositioning: positioning }),
  clearActiveTask: () =>
    set({ activeTaskId: null, activePositioning: null }),
}))
```

**面试点：**
- Zustand 轻量状态管理（vs Redux）
- `create()` 函数式定义 store
- `set()` 状态更新

---

### 3.6 `types/index.ts` — TypeScript 类型

```typescript
export type NodeStatus = "pending" | "running" | "completed" | "failed" | "skipped"

export interface TaskDetail {
  task_id: string
  status: string
  positioning: string
  result_data: {
    profile: AccountProfile | null
    hot_topics: HotTopicResult | null
    topics: TopicResult | null
    content: ContentResult | null
    audit: AuditResult | null
  } | null
}
```

**面试点：**
- TypeScript `type` 别名
- 联合类型 (`"pending" | "running"`)
- 泛型接口
- `Record<string, unknown>` vs `any`

---

## 四、面试核心知识点总结

### 4.1 FastAPI / Python 后端

| 知识点 | 出现位置 | 面试问法 |
|-------|---------|---------|
| 异步框架原理 | `main.py`, `session.py` | "FastAPI 如何实现异步？async/await 在底层如何工作？" |
| 依赖注入 | `task_routes.py` `get_db` | "FastAPI 的 `Depends` 是什么原理？" |
| 中间件机制 | `main.py` CORS | "如何在 FastAPI 中添加自定义中间件？" |
| 请求生命周期 | 全链路 | "描述 FastAPI 请求从接收到响应的完整流程" |
| Pydantic 数据验证 | `schemas/` | "Pydantic 如何实现自动校验？自定义验证器怎么写？" |
| SQLAlchemy Async | `session.py`, `models/` | "Async ORM 和同步 ORM 有什么区别？" |

### 4.2 数据库

| 知识点 | 出现位置 | 面试问法 |
|-------|---------|---------|
| ORM 关系映射 | `tables.py` | "relationship 的 cascade 参数有哪些？区别是什么？" |
| JSON 字段存储 | `tables.py` | "结构化数据是存 JSON 列好还是关联表好？" |
| 事务管理 | `session.py` | "AsyncSession 的 commit/rollback 时机是什么？" |
| SQLAlchemy 2.0 新语法 | `tables.py` | "Mapped[...] 语法相比 `Column()` 有什么优势？" |
| Alembic 迁移 | `alembic/` | "如何用 Alembic 做数据库版本管理？" |

### 4.3 异步编程

| 知识点 | 出现位置 | 面试问法 |
|-------|---------|---------|
| `asyncio.gather` | `hot_topic_agent.py` | "gather 的 `return_exceptions=True` 有什么用？" |
| `asyncio.wait_for` | `engine.py` | "wait_for 和 shield 的区别？" |
| 异步生成器 | `stream_routes.py` | "StreamingResponse 配合 async generator 的原理？" |
| 异步队列 | `broadcaster.py` | "asyncio.Queue 和普通 Queue 的区别？" |
| 事件循环 | `engine.py` | "Python 异步事件循环是如何工作的？" |

### 4.4 LLM 集成

| 知识点 | 出现位置 | 面试问法 |
|-------|---------|---------|
| LiteLLM 统一调用 | `llm/gateway.py` | "如何设计一个支持多 LLM Provider 的架构？" |
| JSON 输出解析 | `llm/gateway.py` | "LLM JSON 输出不稳定怎么办？" |
| Provider 模式 | `llm/providers/` | "门面模式在这个项目中的作用是什么？" |
| 配置优先级 | `llm/config.py` | "数据库配置覆盖环境变量如何实现？" |

### 4.5 前端 React / Next.js

| 知识点 | 出现位置 | 面试问法 |
|-------|---------|---------|
| App Router vs Pages | `app/page.tsx` | "App Router 和 Pages Router 有什么区别？" |
| Server vs Client 组件 | `app/layout.tsx` | "什么场景用 Server Component vs Client Component？" |
| useEffect 依赖 | `CommandCenter.tsx` | "useEffect 依赖数组设计有什么坑？" |
| EventSource SSE | `useTaskSSE.ts` | "SSE 和 WebSocket 的区别？各自适用场景？" |
| CSS Variables | `globals.css` | "CSS Variables 在设计系统中的作用？" |
| Zustand vs Redux | `store/taskStore.ts` | "Zustand 为什么比 Redux 更轻量？" |
| TypeScript 类型 | `types/index.ts` | "type 和 interface 的区别？如何选择？" |

### 4.6 工程架构

| 知识点 | 出现位置 | 面试问法 |
|-------|---------|---------|
| 分层架构 | `api/` → `services/` → `models/` | "为什么 API / Service / Model 要分层？" |
| Pipeline Pattern | `orchestrator/engine.py` | "Pipeline 模式和 Chain 模式的区别？" |
| 发布订阅模式 | `orchestrator/broadcaster.py` | "订阅发布模式如何实现解耦？" |
| SSE 历史缓冲 | `broadcaster.py` | "SSE 重连后如何保证状态一致性？" |
| Facade 门面模式 | `llm/gateway.py` | "门面模式解决什么问题？" |
| Registry 注册表 | `agents/registry.py` | "注册表模式如何实现插件化？" |

---

## 五、项目亮点（面试加分项）

1. **SSE 历史缓冲设计** — 新订阅者自动重放已发送事件，解决竞态问题
2. **多 Provider LLM 网关** — 门面模式统一接口，支持数据库动态配置
3. **Workspace 隔离模式** — 任务间数据完全隔离，智能体按需读取
4. **降级 + 超时双重保护** — `asyncio.wait_for` 超时 + Required Flag 中断
5. **CSS 设计系统** — 完整 token 化设计系统，CSS Variables 驱动多状态
6. **SVG 全息连线动画** — 贝塞尔曲线 + stroke-dashoffset 粒子流
7. **Next.js 直连 SSE 绕过代理** — 解决开发服务器 SSE 缓冲问题
8. **异常分类错误码** — 结构化错误码体系，便于前端处理

---

## 六、快速自检清单

```
□ FastAPI 异步路由 (async def)
□ 依赖注入 (Depends)
□ 全局异常处理 (@app.exception_handler)
□ Pydantic 数据验证 (Field, BaseModel)
□ SQLAlchemy AsyncSession
□ asyncio.gather / wait_for
□ Pipeline Pattern 工作流
□ SSE 协议格式 (event: / data:)
□ EventSource API
□ React Hooks (useState, useEffect, useCallback)
□ Next.js App Router
□ CSS Variables / Animations
□ TypeScript 类型系统
□ Zustand 状态管理
□ fetch API + async/await
□ 设计模式 (Facade, Registry, Pipeline, Observer)
□ 浏览器调试 SSE 连接
□ SQLite / MySQL 数据库操作
□ Alembic 数据库迁移
□ LLM JSON 输出解析
□ 多 Provider 架构
```
