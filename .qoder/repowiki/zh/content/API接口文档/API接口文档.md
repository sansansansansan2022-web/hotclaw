# API接口文档

<cite>
**本文引用的文件**
- [backend/app/main.py](file://backend/app/main.py)
- [backend/app/api/task_routes.py](file://backend/app/api/task_routes.py)
- [backend/app/api/stream_routes.py](file://backend/app/api/stream_routes.py)
- [backend/app/api/agent_routes.py](file://backend/app/api/agent_routes.py)
- [backend/app/api/skill_routes.py](file://backend/app/api/skill_routes.py)
- [backend/app/api/draft_routes.py](file://backend/app/api/draft_routes.py)
- [backend/app/api/account_routes.py](file://backend/app/api/account_routes.py)
- [backend/app/services/draft_service.py](file://backend/app/services/draft_service.py)
- [backend/app/services/account_service.py](file://backend/app/services/account_service.py)
- [backend/app/scheduler/account_scheduler.py](file://backend/app/scheduler/account_scheduler.py)
- [backend/app/schemas/draft.py](file://backend/app/schemas/draft.py)
- [backend/app/schemas/account.py](file://backend/app/schemas/account.py)
- [backend/app/models/tables.py](file://backend/app/models/tables.py)
- [backend/app/schemas/common.py](file://backend/app/schemas/common.py)
- [backend/app/schemas/task.py](file://backend/app/schemas/task.py)
- [backend/app/schemas/agent.py](file://backend/app/schemas/agent.py)
- [backend/app/schemas/skill.py](file://backend/app/schemas/skill.py)
- [backend/app/core/exceptions.py](file://backend/app/core/exceptions.py)
- [backend/app/orchestrator/broadcaster.py](file://backend/app/orchestrator/broadcaster.py)
- [frontend/lib/api.ts](file://frontend/lib/api.ts)
- [frontend/hooks/useTaskSSE.ts](file://frontend/hooks/useTaskSSE.ts)
- [frontend/types/index.ts](file://frontend/types/index.ts)
- [ARCHITECTURE.md](file://ARCHITECTURE.md)
- [Notice.md](file://Notice.md)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [依赖分析](#依赖分析)
7. [性能考量](#性能考量)
8. [故障排查指南](#故障排查指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
本文件为 HotClaw 平台的完整 API 接口参考，覆盖任务管理、实时事件流、Agent 配置、技能管理、草稿管理和账户调度六大类 API。文档提供每个端点的 HTTP 方法、URL 模式、请求参数、响应格式、错误码说明，以及认证授权、请求/响应头、SSE 事件流的连接与消息格式、实时交互模式、版本管理、速率限制与性能优化建议。本文档同时面向 API 使用者与集成开发者。

## 项目结构
后端采用 FastAPI，API 路由位于独立模块，统一通过网关入口暴露；前端通过 HTTP + SSE 与后端交互。整体遵循"路由层只处理请求/响应、业务逻辑在服务层"的分层约束。新增的草稿管理和账户调度功能通过专门的服务层实现业务逻辑，定时调度器负责自动执行账户任务。

```mermaid
graph TB
subgraph "前端"
FE_API["前端API客户端<br/>/frontend/lib/api.ts"]
FE_SSE["前端SSE钩子<br/>/frontend/hooks/useTaskSSE.ts"]
end
subgraph "后端"
GW["网关/FastAPI<br/>/backend/app/main.py"]
TASK["任务路由<br/>/backend/app/api/task_routes.py"]
STREAM["SSE路由<br/>/backend/app/api/stream_routes.py"]
AGENT["Agent路由<br/>/backend/app/api/agent_routes.py"]
SKILL["Skill路由<br/>/backend/app/api/skill_routes.py"]
DRAFT["草稿路由<br/>/backend/app/api/draft_routes.py"]
ACCOUNT["账户路由<br/>/backend/app/api/account_routes.py"]
DRAFT_SRV["草稿服务<br/>/backend/app/services/draft_service.py"]
ACCOUNT_SRV["账户服务<br/>/backend/app/services/account_service.py"]
SCHED["账户调度器<br/>/backend/app/scheduler/account_scheduler.py"]
BROAD["SSE广播器<br/>/backend/app/orchestrator/broadcaster.py"]
end
FE_API --> GW
FE_SSE --> GW
GW --> TASK
GW --> STREAM
GW --> AGENT
GW --> SKILL
GW --> DRAFT
GW --> ACCOUNT
STREAM --> BROAD
DRAFT --> DRAFT_SRV
ACCOUNT --> ACCOUNT_SRV
ACCOUNT --> SCHED
```

**图表来源**
- [backend/app/main.py:60-142](file://backend/app/main.py#L60-L142)
- [backend/app/api/task_routes.py:16-163](file://backend/app/api/task_routes.py#L16-L163)
- [backend/app/api/stream_routes.py:11-43](file://backend/app/api/stream_routes.py#L11-L43)
- [backend/app/api/agent_routes.py:14-115](file://backend/app/api/agent_routes.py#L14-L115)
- [backend/app/api/skill_routes.py:14-61](file://backend/app/api/skill_routes.py#L14-L61)
- [backend/app/api/draft_routes.py:28-236](file://backend/app/api/draft_routes.py#L28-L236)
- [backend/app/api/account_routes.py:27-263](file://backend/app/api/account_routes.py#L27-L263)
- [backend/app/services/draft_service.py:33-425](file://backend/app/services/draft_service.py#L33-L425)
- [backend/app/services/account_service.py:35-420](file://backend/app/services/account_service.py#L35-L420)
- [backend/app/scheduler/account_scheduler.py:25-259](file://backend/app/scheduler/account_scheduler.py#L25-L259)
- [backend/app/orchestrator/broadcaster.py:11-94](file://backend/app/orchestrator/broadcaster.py#L11-L94)

**章节来源**
- [backend/app/main.py:60-142](file://backend/app/main.py#L60-L142)
- [ARCHITECTURE.md:414-448](file://ARCHITECTURE.md#L414-L448)

## 核心组件
- 统一响应模型：所有 API 响应遵循统一包装结构，包含 code、message、data，便于前端一致处理。
- 异常体系：后端定义了统一的异常基类与分类，全局异常处理器将业务异常映射为合适的 HTTP 状态码。新增账户、草稿相关异常类型。
- SSE 广播器：负责按任务维度维护订阅队列、事件缓冲与历史回放，确保晚到订阅也能收到历史事件。
- 前端 API 客户端：封装基础请求、统一错误处理与端点路径，提供任务、Agent、Skill、草稿、账户的常用调用方法。
- 前端 SSE 钩子：封装 EventSource 订阅、事件监听与状态管理，映射后端事件到前端节点状态。
- 草稿服务：管理文章草稿的生命周期，包括状态转换、审核、发布等操作。
- 账户服务：管理微信公众号账号的全生命周期，包括创建、更新、运行、调度等。
- 账户调度器：后台定时任务，自动检查到期的账户并触发任务执行。

**章节来源**
- [backend/app/schemas/common.py:7-27](file://backend/app/schemas/common.py#L7-L27)
- [backend/app/core/exceptions.py:225-366](file://backend/app/core/exceptions.py#L225-L366)
- [backend/app/orchestrator/broadcaster.py:11-94](file://backend/app/orchestrator/broadcaster.py#L11-L94)
- [frontend/lib/api.ts:14-110](file://frontend/lib/api.ts#L14-L110)
- [frontend/hooks/useTaskSSE.ts:28-124](file://frontend/hooks/useTaskSSE.ts#L28-L124)
- [backend/app/services/draft_service.py:33-425](file://backend/app/services/draft_service.py#L33-L425)
- [backend/app/services/account_service.py:35-420](file://backend/app/services/account_service.py#L35-L420)
- [backend/app/scheduler/account_scheduler.py:25-259](file://backend/app/scheduler/account_scheduler.py#L25-L259)

## 架构总览
HotClaw 的 API 架构遵循 Notice.md 的分层约束：路由层只做请求/响应处理，业务逻辑在服务层；SSE 事件由编排器广播至广播器，再由路由层以 EventSourceResponse 推送给前端。新增的草稿管理和账户调度通过专门的服务层实现，调度器在后台独立运行。

```mermaid
sequenceDiagram
participant C as "客户端"
participant G as "网关(FastAPI)"
participant S as "SSE广播器"
participant E as "编排器(事件产生)"
participant DS as "草稿服务"
participant AS as "账户服务"
participant SCH as "账户调度器"
C->>G : "GET /api/v1/tasks/{task_id}/stream"
G->>S : "subscribe(task_id)"
S-->>G : "返回队列(含历史回放)"
G-->>C : "EventSourceResponse(事件流)"
E->>S : "broadcast(task_id, event, data)"
S-->>G : "推送消息到订阅队列"
G-->>C : "事件推送(node_start/node_complete/node_error/task_complete)"
C->>G : "POST /api/v1/drafts/{draft_id}/confirm-publish"
G->>DS : "confirm_publish(draft_id)"
DS-->>G : "更新草稿状态"
G-->>C : "确认发布结果"
C->>G : "POST /api/v1/accounts/{account_id}/run"
G->>AS : "run_account(account_id)"
AS->>SCH : "触发后台任务"
SCH-->>AS : "执行任务"
AS-->>G : "返回任务信息"
G-->>C : "运行结果"
```

**图表来源**
- [backend/app/api/stream_routes.py:14-43](file://backend/app/api/stream_routes.py#L14-L43)
- [backend/app/orchestrator/broadcaster.py:30-85](file://backend/app/orchestrator/broadcaster.py#L30-L85)
- [frontend/hooks/useTaskSSE.ts:62-120](file://frontend/hooks/useTaskSSE.ts#L62-L120)
- [backend/app/api/draft_routes.py:101-131](file://backend/app/api/draft_routes.py#L101-L131)
- [backend/app/api/account_routes.py:156-181](file://backend/app/api/account_routes.py#L156-L181)
- [backend/app/services/draft_service.py:243-285](file://backend/app/services/draft_service.py#L243-L285)
- [backend/app/services/account_service.py:197-276](file://backend/app/services/account_service.py#L197-L276)
- [backend/app/scheduler/account_scheduler.py:144-204](file://backend/app/scheduler/account_scheduler.py#L144-L204)

## 详细组件分析

### 任务管理 API
- 基础路径：/api/v1/tasks
- 版本：v1
- 认证：未强制要求（跨域允许通配）
- 速率限制：未内置

1) 创建任务
- 方法：POST
- 路径：/api/v1/tasks
- 请求体：
  - positioning: string（必填，长度 5-500）
  - workflow_id: string（可选，默认 default_pipeline）
- 成功响应：data 包含 task_id、status、created_at、workflow_id
- 典型错误：1001（参数校验失败）

2) 查询任务状态
- 方法：GET
- 路径：/api/v1/tasks/{task_id}/status
- 成功响应：data 包含 task_id、status、current_node、progress（total_nodes、completed_nodes、current_node_index）、started_at、elapsed_seconds
- 典型错误：1002（任务不存在）

3) 查询任务详情
- 方法：GET
- 路径：/api/v1/tasks/{task_id}
- 成功响应：data 包含 task_id、status、input_data、workflow_id、result_data、error_message、created_at、started_at、completed_at、elapsed_seconds、total_tokens

4) 查询任务节点执行记录
- 方法：GET
- 路径：/api/v1/tasks/{task_id}/nodes
- 成功响应：data 包含 nodes 数组，每项包含 node_id、agent_id、status、input_data、output_data、started_at、completed_at、elapsed_seconds、prompt_tokens、completion_tokens、model_used、degraded、error_message

5) 分页查询任务列表
- 方法：GET
- 路径：/api/v1/tasks
- 查询参数：
  - page: int（>=1，默认1）
  - page_size: int（1-100，默认20）
  - status: string（可选）
- 成功响应：data 包含 tasks 数组（含 task_id、positioning_summary、status、created_at、elapsed_seconds）与 pagination（page、page_size、total）

请求示例（创建任务）
- 方法：POST
- URL：/api/v1/tasks
- 请求头：Content-Type: application/json
- 请求体：
  - positioning: "我是一个关注职场成长的公众号..."
  - workflow_id: "default_pipeline"

响应示例（创建任务）
- 响应体：
  - code: 0
  - message: "ok"
  - data: { task_id: "...", status: "pending", created_at: "...", workflow_id: "default_pipeline" }

错误码说明（任务相关）
- 1001：参数校验失败
- 1002：任务不存在
- 2001：任务已在运行
- 2002：工作流不存在
- 3001：LLM 调用失败
- 3003：Agent 执行超时
- 3004：Agent 执行失败
- 3005：Skill 执行失败
- 5000：内部服务器错误

**章节来源**
- [backend/app/api/task_routes.py:19-163](file://backend/app/api/task_routes.py#L19-L163)
- [backend/app/schemas/task.py:10-83](file://backend/app/schemas/task.py#L10-L83)
- [backend/app/schemas/common.py:7-27](file://backend/app/schemas/common.py#L7-L27)
- [backend/app/core/exceptions.py:17-125](file://backend/app/core/exceptions.py#L17-L125)

### 实时事件流 API（SSE）
- 基础路径：/api/v1/tasks
- 事件类型：
  - node_start：节点开始执行
  - node_complete：节点完成（含输出摘要、耗时、降级标记）
  - node_error：节点错误（含错误信息）
  - task_complete：任务完成
  - task_error：任务级错误
- 连接处理：
  - 前端通过 EventSource 订阅 /api/v1/tasks/{task_id}/stream
  - 后端使用 sse-starlette 的 EventSourceResponse
  - 广播器维护订阅队列与历史缓冲，支持晚到订阅的历史回放
  - 连接空闲超过一定时间会发送 keepalive 注释，避免代理中断
  - 断开或结束时发送结束哨兵，触发清理

SSE 事件格式
- 事件名：event
- 数据：data（JSON 字符串）
- 示例：
  - event: node_start
  - data: { node_id, agent_id, name, index, total, started_at }

前端事件映射
- node_start → 节点状态 running
- node_complete → 节点状态 completed，填充耗时、输出摘要、降级标记
- node_error → 节点状态 failed，填充错误信息
- task_complete → 任务完成，关闭连接
- task_error → 任务错误，关闭连接

```mermaid
sequenceDiagram
participant FE as "前端"
participant GW as "后端路由"
participant BR as "广播器"
participant OR as "编排器"
FE->>GW : "GET /api/v1/tasks/{task_id}/stream"
GW->>BR : "subscribe(task_id)"
BR-->>GW : "队列(含历史)"
GW-->>FE : "EventSourceResponse"
OR->>BR : "broadcast(task_id, 'node_start', {...})"
BR-->>GW : "推送消息"
GW-->>FE : "event=node_start"
OR->>BR : "broadcast(task_id, 'node_complete', {...})"
BR-->>GW : "推送消息"
GW-->>FE : "event=node_complete"
OR->>BR : "broadcast(task_id, 'task_complete', {...})"
BR-->>GW : "推送消息"
GW-->>FE : "event=task_complete"
```

**图表来源**
- [backend/app/api/stream_routes.py:14-43](file://backend/app/api/stream_routes.py#L14-L43)
- [backend/app/orchestrator/broadcaster.py:30-85](file://backend/app/orchestrator/broadcaster.py#L30-L85)
- [frontend/hooks/useTaskSSE.ts:65-111](file://frontend/hooks/useTaskSSE.ts#L65-L111)

**章节来源**
- [backend/app/api/stream_routes.py:14-43](file://backend/app/api/stream_routes.py#L14-L43)
- [backend/app/orchestrator/broadcaster.py:11-94](file://backend/app/orchestrator/broadcaster.py#L11-L94)
- [frontend/hooks/useTaskSSE.ts:28-124](file://frontend/hooks/useTaskSSE.ts#L28-L124)

### Agent 配置 API
- 基础路径：/api/v1/agents
- 版本：v1
- 认证：未强制要求（跨域允许通配）
- 速率限制：未内置

1) 列出所有 Agent
- 方法：GET
- 路径：/api/v1/agents
- 成功响应：data 包含 agents 数组，每项包含 agent_id、name、description、version、required_skills、status、has_custom_prompt

2) 获取单个 Agent 详情
- 方法：GET
- 路径：/api/v1/agents/{agent_id}
- 成功响应：data 包含 agent_id、name、description、version、model_config_data、prompt_template、prompt_source、default_system_prompt、retry_config、status
- 典型错误：1003（Agent 不存在）

3) 更新 Agent 配置
- 方法：PUT
- 路径：/api/v1/agents/{agent_id}/config
- 请求体：
  - model_config_data: object（可选）
  - prompt_template: string（可选；空字符串表示重置为默认）
  - retry_config: object（可选）
- 成功响应：data 包含 agent_id 与 updated_fields（实际更新的字段列表）

请求示例（更新 Agent 配置）
- 方法：PUT
- URL：/api/v1/agents/{agent_id}/config
- 请求头：Content-Type: application/json
- 请求体：
  - model_config_data: { ... }
  - prompt_template: "自定义提示词..."
  - retry_config: { ... }

响应示例（更新 Agent 配置）
- 响应体：
  - code: 0
  - message: "ok"
  - data: { agent_id: "...", updated_fields: ["model_config_data","prompt_template"] }

错误码说明（Agent 相关）
- 1003：Agent 不存在
- 4001：配置校验失败
- 5000：内部服务器错误

**章节来源**
- [backend/app/api/agent_routes.py:17-115](file://backend/app/api/agent_routes.py#L17-L115)
- [backend/app/schemas/agent.py:6-29](file://backend/app/schemas/agent.py#L6-L29)
- [backend/app/core/exceptions.py:31-43](file://backend/app/core/exceptions.py#L31-L43)

### 技能管理 API
- 基础路径：/api/v1/skills
- 版本：v1
- 认证：未强制要求（跨域允许通配）
- 速率限制：未内置

1) 列出所有技能
- 方法：GET
- 路径：/api/v1/skills
- 成功响应：data 包含 skills 数组，每项包含 skill_id、name、description、version、config_data、status

2) 更新技能配置
- 方法：PUT
- 路径：/api/v1/skills/{skill_id}/config
- 请求体：
  - config_data: object（可选）
- 成功响应：data 包含 skill_id 与 updated: true

请求示例（更新技能配置）
- 方法：PUT
- URL：/api/v1/skills/{skill_id}/config
- 请求头：Content-Type: application/json
- 请求体：
  - config_data: { "sources": [...], "max_items": 20 }

响应示例（更新技能配置）
- 响应体：
  - code: 0
  - message: "ok"
  - data: { skill_id: "...", updated: true }

错误码说明（技能相关）
- 1004：技能不存在
- 4001：配置校验失败
- 5000：内部服务器错误

**章节来源**
- [backend/app/api/skill_routes.py:17-61](file://backend/app/api/skill_routes.py#L17-L61)
- [backend/app/schemas/skill.py:6-22](file://backend/app/schemas/skill.py#L6-L22)
- [backend/app/core/exceptions.py:38-42](file://backend/app/core/exceptions.py#L38-L42)

### 草稿管理 API
- 基础路径：/api/v1/drafts
- 版本：v1
- 认证：未强制要求（跨域允许通配）
- 速率限制：未内置

1) 草稿列表
- 方法：GET
- 路径：/api/v1/drafts
- 查询参数：
  - page: int（>=1，默认1）
  - page_size: int（1-100，默认20）
  - account_id: string（可选）
  - draft_status: string（可选）
  - publish_status: string（可选）
- 成功响应：data 包含 drafts 数组（包含草稿基本信息）与 pagination（page、page_size、total、total_pages）

2) 获取草稿详情
- 方法：GET
- 路径：/api/v1/drafts/{draft_id}
- 成功响应：data 包含草稿完整信息，包括标题、内容、字数统计、状态、审核结果等
- 典型错误：9001（草稿不存在）

3) 确认发布草稿
- 方法：POST
- 路径：/api/v1/drafts/{draft_id}/confirm-publish
- 描述：将草稿状态从待审核或草稿转为已批准并发布
- 成功响应：data 包含 draft_id、draft_status、publish_status、confirmed_at
- 典型错误：9002（状态不允许）、9004（发布失败）

4) 废弃草稿
- 方法：POST
- 路径：/api/v1/drafts/{draft_id}/discard
- 描述：废弃草稿，使其进入废弃状态
- 成功响应：data 包含 draft_id 和更新后的 draft_status
- 典型错误：9002（状态不允许）

5) 拒绝草稿
- 方法：POST
- 路径：/api/v1/drafts/{draft_id}/reject
- 描述：拒绝草稿，使其进入拒绝状态
- 成功响应：data 包含 draft_id 和更新后的 draft_status
- 典型错误：9002（状态不允许）

6) 从草稿重跑
- 方法：POST
- 路径：/api/v1/drafts/{draft_id}/rerun
- 描述：基于草稿的账号和定位重新创建任务
- 成功响应：data 包含 draft_id、original_task_id、new_task_id、status
- 典型错误：9001（草稿不存在）、9005（创建失败）

7) 获取待审核草稿数量
- 方法：GET
- 路径：/api/v1/drafts/pending-count
- 查询参数：
  - account_id: string（可选）
- 成功响应：data 包含 count 和 account_id

草稿状态流转图
```mermaid
stateDiagram-v2
[*] --> 草稿
[*] --> 待审核
[*] --> 已批准
[*] --> 已拒绝
[*] --> 已废弃
[*] --> 已发布
草稿 --> 已批准 : 确认发布
草稿 --> 已废弃 : 废弃
待审核 --> 已批准 : 确认发布
待审核 --> 已拒绝 : 拒绝
待审核 --> 已废弃 : 废弃
已批准 --> 已发布 : 发布
```

**图表来源**
- [backend/app/services/draft_service.py:22-30](file://backend/app/services/draft_service.py#L22-L30)
- [backend/app/api/draft_routes.py:101-235](file://backend/app/api/draft_routes.py#L101-L235)

请求示例（获取草稿详情）
- 方法：GET
- URL：/api/v1/drafts/{draft_id}
- 成功响应示例：
  - code: 0
  - message: "ok"
  - data: {
    "id": 1,
    "task_id": "task_123",
    "account_id": "acc_456",
    "title": "示例文章",
    "content_markdown": "# 标题\n\n内容...",
    "word_count": 1500,
    "draft_status": "pending_review",
    "publish_status": "not_published",
    "publish_review_required": true,
    "source_type": "semi_auto_task",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }

错误码说明（草稿相关）
- 9001：草稿不存在
- 9002：草稿状态不允许该操作
- 9003：草稿已发布
- 9004：草稿发布失败
- 9005：从草稿创建任务失败

**章节来源**
- [backend/app/api/draft_routes.py:31-235](file://backend/app/api/draft_routes.py#L31-L235)
- [backend/app/services/draft_service.py:204-421](file://backend/app/services/draft_service.py#L204-L421)
- [backend/app/schemas/draft.py:36-128](file://backend/app/schemas/draft.py#L36-L128)
- [backend/app/core/exceptions.py:313-366](file://backend/app/core/exceptions.py#L313-L366)

### 账户调度 API
- 基础路径：/api/v1/accounts
- 版本：v1
- 认证：未强制要求（跨域允许通配）
- 速率限制：未内置

1) 创建账户
- 方法：POST
- 路径：/api/v1/accounts
- 请求体：
  - name: string（1-100字符）
  - category: string（可选，50字符）
  - positioning: string（5-500字符，必填）
  - audience: string（可选，200字符）
  - tone_style: string（可选，100字符）
  - posting_frequency: enum（daily/weekly/biweekly/monthly，可选）
  - posting_time: string（格式 HH:MM，可选）
  - content_strategy: string（可选）
  - reference_accounts: string（可选）
  - operation_mode: enum（manual/semi_auto/full_auto，默认manual）
  - auto_run_enabled: boolean（默认false）
  - auto_publish_enabled: boolean（默认false）
  - is_active: boolean（默认true）
- 成功响应：data 包含 account_id、name、is_active、operation_mode
- 典型错误：6003（账户验证失败）

2) 账户列表
- 方法：GET
- 路径：/api/v1/accounts
- 查询参数：
  - page: int（>=1，默认1）
  - page_size: int（1-100，默认20）
- 成功响应：data 包含 accounts 数组与 pagination 信息

3) 获取账户详情
- 方法：GET
- 路径：/api/v1/accounts/{account_id}
- 成功响应：data 包含账户完整信息及最近的任务记录
- 典型错误：6001（账户不存在）

4) 更新账户
- 方法：PATCH
- 路径：/api/v1/accounts/{account_id}
- 请求体：可选字段（同创建请求体）
- 成功响应：data 包含更新后的账户摘要信息
- 典型错误：6001/6003（账户不存在或验证失败）

5) 手动触发账户运行
- 方法：POST
- 路径：/api/v1/accounts/{account_id}/run
- 描述：手动触发一次任务执行
- 成功响应：data 包含 account_id、task_id、status、operation_mode
- 典型错误：6001/6002/6003/8001/8002（账户状态或任务相关错误）

6) 启用账户
- 方法：POST
- 路径：/api/v1/accounts/{account_id}/enable
- 成功响应：data 包含更新后的账户摘要信息

7) 禁用账户
- 方法：POST
- 路径：/api/v1/accounts/{account_id}/disable
- 成功响应：data 包含更新后的账户摘要信息

账户运行模式说明
- manual：手动模式，仅支持手动触发
- semi_auto：半自动模式，生成草稿后需要人工审核
- full_auto：全自动模式，自动生成并发布文章

调度器配置
- 调度间隔：60秒
- 最大并发运行数：3个
- 自动运行条件：账户启用、允许自动运行、半自动或全自动模式、到达下次运行时间、无进行中的任务

**章节来源**
- [backend/app/api/account_routes.py:30-263](file://backend/app/api/account_routes.py#L30-L263)
- [backend/app/services/account_service.py:41-420](file://backend/app/services/account_service.py#L41-L420)
- [backend/app/schemas/account.py:29-146](file://backend/app/schemas/account.py#L29-L146)
- [backend/app/core/exceptions.py:225-283](file://backend/app/core/exceptions.py#L225-L283)
- [backend/app/scheduler/account_scheduler.py:25-259](file://backend/app/scheduler/account_scheduler.py#L25-L259)

### 认证与授权、请求/响应头
- 认证：未强制要求（跨域允许通配）
- 请求头：
  - Content-Type: application/json
- 响应头：
  - X-Trace-Id：后端中间件注入的追踪 ID，便于问题定位
- 健康检查：
  - GET /api/v1/health：返回 { status: "ok", version: "0.1.0" }

**章节来源**
- [backend/app/main.py:67-84](file://backend/app/main.py#L67-L84)
- [backend/app/main.py:139-142](file://backend/app/main.py#L139-L142)

### 错误处理与错误码
- 统一响应模型：ApiResponse(code, message, data)，错误时返回 ApiErrorResponse
- 全局异常映射：
  - 1xxx：客户端参数错误（映射 400）
  - 2xxx：冲突/资源不存在（映射 409/404）
  - 3xxx：外部/执行错误（映射 502/504）
  - 4xxx：配置错误（映射 400）
  - 5xxx：系统错误（映射 500）
  - 6xxx：账户相关错误（映射 400/404）
  - 7xxx：调度器相关错误（映射 500）
  - 8xxx：任务相关错误（映射 400/409）
  - 9xxx：草稿相关错误（映射 400/404/409）
- 特殊映射：
  - 1002/1003/1004/2002 → 404
  - 3003 → 504

**章节来源**
- [backend/app/schemas/common.py:7-27](file://backend/app/schemas/common.py#L7-L27)
- [backend/app/main.py:87-130](file://backend/app/main.py#L87-L130)
- [backend/app/core/exceptions.py:17-366](file://backend/app/core/exceptions.py#L17-L366)

## 依赖分析
- 路由层依赖：
  - 任务路由依赖 task_service 与统一响应模型
  - SSE 路由依赖广播器
  - Agent/Skill 路由依赖注册中心与数据库模型
  - 草稿路由依赖 draft_service 与草稿模型
  - 账户路由依赖 account_service 与账户模型
- 服务层依赖：
  - 草稿服务依赖 SQLAlchemy ORM 模型和异常定义
  - 账户服务依赖任务模型、账户模型和调度辅助方法
  - 调度器依赖账户服务和任务服务
- 前端依赖：
  - API 客户端封装统一请求与错误处理
  - SSE 钩子封装事件监听与状态更新

```mermaid
graph LR
TASK_RT["任务路由"] --> TASK_SCHEMA["任务Schema"]
TASK_RT --> COMMON["统一响应模型"]
STREAM_RT["SSE路由"] --> BROADCASTER["SSE广播器"]
AGENT_RT["Agent路由"] --> AGENT_SCHEMA["Agent Schema"]
SKILL_RT["Skill路由"] --> SKILL_SCHEMA["Skill Schema"]
DRAFT_RT["草稿路由"] --> DRAFT_SCHEMA["草稿Schema"]
DRAFT_RT --> DRAFT_SERVICE["草稿服务"]
ACCOUNT_RT["账户路由"] --> ACCOUNT_SCHEMA["账户Schema"]
ACCOUNT_RT --> ACCOUNT_SERVICE["账户服务"]
ACCOUNT_RT --> SCHEDULER["账户调度器"]
FE_API["前端API客户端"] --> COMMON
FE_SSE["前端SSE钩子"] --> FE_TYPES["前端类型定义"]
```

**图表来源**
- [backend/app/api/task_routes.py:10-14](file://backend/app/api/task_routes.py#L10-L14)
- [backend/app/api/stream_routes.py:9](file://backend/app/api/stream_routes.py#L9)
- [backend/app/api/agent_routes.py:8-12](file://backend/app/api/agent_routes.py#L8-L12)
- [backend/app/api/skill_routes.py:7-12](file://backend/app/api/skill_routes.py#L7-L12)
- [backend/app/api/draft_routes.py:15-25](file://backend/app/api/draft_routes.py#L15-L25)
- [backend/app/api/account_routes.py:23-24](file://backend/app/api/account_routes.py#L23-L24)
- [frontend/lib/api.ts:14-39](file://frontend/lib/api.ts#L14-L39)
- [frontend/hooks/useTaskSSE.ts:4-6](file://frontend/hooks/useTaskSSE.ts#L4-L6)
- [frontend/types/index.ts:10-15](file://frontend/types/index.ts#L10-L15)

**章节来源**
- [backend/app/api/task_routes.py:10-14](file://backend/app/api/task_routes.py#L10-L14)
- [backend/app/api/stream_routes.py:9](file://backend/app/api/stream_routes.py#L9)
- [backend/app/api/agent_routes.py:8-12](file://backend/app/api/agent_routes.py#L8-L12)
- [backend/app/api/skill_routes.py:7-12](file://backend/app/api/skill_routes.py#L7-L12)
- [backend/app/api/draft_routes.py:15-25](file://backend/app/api/draft_routes.py#L15-L25)
- [backend/app/api/account_routes.py:23-24](file://backend/app/api/account_routes.py#L23-L24)
- [frontend/lib/api.ts:14-39](file://frontend/lib/api.ts#L14-L39)
- [frontend/hooks/useTaskSSE.ts:4-6](file://frontend/hooks/useTaskSSE.ts#L4-L6)
- [frontend/types/index.ts:10-15](file://frontend/types/index.ts#L10-L15)

## 性能考量
- SSE 连接空闲保活：后端在超时等待期间发送 keepalive 注释，避免代理层中断连接。
- 历史回放：广播器维护历史事件缓冲，晚到订阅可立即获得历史事件，减少重复轮询。
- 异步与后台任务：任务创建后立即返回，编排在后台异步执行，降低请求延迟。
- 前端状态管理：SSE 钩子集中管理节点状态与错误，避免重复渲染与无效请求。
- 草稿批量处理：草稿列表支持分页和过滤，避免一次性加载大量数据。
- 账户调度并发控制：调度器使用信号量限制最大并发运行数，防止系统过载。
- 建议：
  - 前端对 EventSource 连接增加重连与退避策略
  - 合理设置 page_size，避免一次性拉取过多历史任务
  - 对频繁查询的端点增加本地缓存与去抖
  - 调整调度器并发数以适应硬件资源

**章节来源**
- [backend/app/api/stream_routes.py:24-38](file://backend/app/api/stream_routes.py#L24-L38)
- [backend/app/orchestrator/broadcaster.py:22-85](file://backend/app/orchestrator/broadcaster.py#L22-L85)
- [backend/app/api/task_routes.py:36-44](file://backend/app/api/task_routes.py#L36-L44)
- [frontend/hooks/useTaskSSE.ts:113-120](file://frontend/hooks/useTaskSSE.ts#L113-L120)
- [backend/app/scheduler/account_scheduler.py:21-22](file://backend/app/scheduler/account_scheduler.py#L21-L22)

## 故障排查指南
- 常见错误与处理
  - 1001（参数校验失败）：检查请求体字段是否符合 Schema 与长度限制
  - 1002（任务不存在）：确认 task_id 是否正确，或先创建任务
  - 1003/1004（Agent/Skill 不存在）：确认注册中心是否存在对应标识
  - 3003（Agent 执行超时）：检查外部 LLM/服务超时设置与网络状况
  - 5000（内部错误）：查看后端日志，定位具体异常位置
  - 6001（账户不存在）：确认账户ID是否正确
  - 6002（账户未激活）：先启用账户再尝试运行
  - 6003（账户验证失败）：检查输入字段格式和范围
  - 8001（任务已存在）：等待现有任务完成后重试
  - 9001（草稿不存在）：确认草稿ID是否正确
  - 9002（草稿状态不允许）：检查草稿当前状态是否支持该操作
- 追踪与诊断
  - 使用 X-Trace-Id 响应头关联请求链路
  - 健康检查 /api/v1/health 确认服务可用性
  - 查看调度器日志确认自动运行状态
- 前端调试
  - 使用浏览器 Network 面板观察 SSE 连接与事件
  - 检查前端类型定义与后端响应一致性
  - 监控草稿状态变化和账户运行进度

**章节来源**
- [backend/app/main.py:87-130](file://backend/app/main.py#L87-L130)
- [backend/app/core/exceptions.py:17-366](file://backend/app/core/exceptions.py#L17-L366)
- [frontend/lib/api.ts:14-24](file://frontend/lib/api.ts#L14-L24)

## 结论
本文档提供了 HotClaw 平台的完整 API 参考，涵盖任务管理、实时事件流、Agent 配置、技能管理、草稿管理和账户调度的端点、参数、响应与错误码，并结合前端实现说明了 SSE 事件流的交互模式。新增的草稿管理和账户调度功能完善了平台的内容创作和自动化运营能力。建议在生产环境中补充认证授权、速率限制与更完善的可观测性措施，以提升安全性与稳定性。

## 附录

### API 版本管理
- 当前版本：v1
- 健康检查：/api/v1/health 返回版本号

**章节来源**
- [backend/app/main.py:60-65](file://backend/app/main.py#L60-L65)
- [backend/app/main.py:139-142](file://backend/app/main.py#L139-L142)

### 速率限制与安全建议
- 当前未内置速率限制与认证授权
- 建议：
  - 引入速率限制中间件或网关限流
  - 添加 API Key 或 JWT 认证
  - 生产环境收紧 CORS 策略
  - 监控调度器运行状态和系统负载

**章节来源**
- [backend/app/main.py:67-74](file://backend/app/main.py#L67-L74)
- [backend/app/scheduler/account_scheduler.py:46-65](file://backend/app/scheduler/account_scheduler.py#L46-L65)