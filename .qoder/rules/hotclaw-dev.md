# HotClaw 开发指导规则

你是 HotClaw 项目的开发助手。请严格遵循以下规则。

## 项目定位

HotClaw 是一个**面向公众号内容生产的多智能体平台**，当前处于 MVP 第一版。

核心工作流：
```
账号定位解析 → 热点分析 → 选题策划 → 标题生成 → 正文生成 → 审核评估
```

## 必须遵守的约束

### 技术栈（不可更改）
- 后端：Python + FastAPI + SQLAlchemy + Pydantic v2
- 前端：Next.js + TypeScript + Tailwind CSS
- 数据库：SQLite (MVP) → PostgreSQL (生产)

### 目录结构（不可更改）
```
backend/app/
├── api/          # 路由层，不写业务逻辑
├── agents/       # Agent 实现
├── skills/       # Skill 工具层
├── orchestrator/ # 工作流引擎
├── services/     # 业务服务
├── models/       # ORM 模型
├── schemas/      # Pydantic Schema
└── core/         # 配置/日志/异常

frontend/app/
├── page.tsx      # 首页
├── task/[id]/    # 任务详情
├── history/      # 历史任务
└── settings/     # 配置页
```

### API 返回格式（统一）
```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### Agent 返回格式（统一）
```json
{
  "status": "success",
  "agent_name": "xxx",
  "data": {},
  "error": null,
  "trace_id": "xxx"
}
```

### 命名规则
- Python：snake_case
- TypeScript：PascalCase
- API path：小写、短横线

## 禁止事项

- ❌ 擅自改技术栈
- ❌ 擅自改目录结构
- ❌ 硬编码密钥/URL
- ❌ 把业务逻辑写进路由层
- ❌ 使用伪代码代替实现
- ❌ 提前实现未来功能
- ❌ 静默吞错

## 当前开发任务

### Phase 2：真实 LLM 调用（最高优先级）

目标：将 Mock Agent 替换为真实 LLM 调用。

#### 任务 1：创建 LLM 调用层

在 `backend/app/core/` 下创建 `llm.py`：

```python
# 功能要求：
# 1. 使用 litellm 或 openai SDK
# 2. 支持配置化的 model 和 api_base
# 3. 支持超时和重试
# 4. 返回结构化 JSON
# 5. 记录 token 消耗
```

#### 任务 2：更新 Agent 基类

修改 `backend/app/agents/base.py`：
- 添加 `call_llm()` 方法
- 支持 system_prompt + user_prompt
- 支持 JSON 模式输出
- 记录 token 到 AgentResult

#### 任务 3：替换 Mock Agent

按顺序替换以下 Agent（每次只改一个）：
1. `profile_agent.py` - 账号定位解析
2. `hot_topic_agent.py` - 热点分析
3. `topic_planner_agent.py` - 选题策划
4. `title_generator_agent.py` - 标题生成
5. `content_writer_agent.py` - 正文生成
6. `audit_agent.py` - 审核评估

每个 Agent 需要：
- 调用真实 LLM
- 解析 JSON 输出
- 保留 fallback 逻辑
- 更新单元测试

#### 任务 4：配置 LLM

在 `backend/app/core/config.py` 添加：
```python
llm_model: str = "gpt-4o"
llm_api_base: str = ""  # 留空使用默认
llm_api_key: str = ""   # 从环境变量读取
llm_timeout: int = 60
```

## 开发流程

每次开发时：
1. 只做当前明确要求的任务
2. 先读 NOTICE.md 确认约束
3. 写代码前先写测试
4. 完成后运行测试确认通过
5. 不要擅自扩展需求

## 环境变量

在 `.env` 中配置：
```
LLM_API_KEY=your-key
LLM_API_BASE=https://api.example.com/v1
LLM_MODEL=gpt-4o
```