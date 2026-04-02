# Agent智能体系统

<cite>
**本文档引用的文件**
- [backend/app/agents/base.py](file://backend/app/agents/base.py)
- [backend/app/agents/profile_agent.py](file://backend/app/agents/profile_agent.py)
- [backend/app/agents/audit_agent.py](file://backend/app/agents/audit_agent.py)
- [backend/app/agents/registry.py](file://backend/app/agents/registry.py)
- [backend/app/orchestrator/engine.py](file://backend/app/orchestrator/engine.py)
- [backend/app/orchestrator/workspace.py](file://backend/app/orchestrator/workspace.py)
- [backend/app/skills/base.py](file://backend/app/skills/base.py)
- [backend/app/skills/registry.py](file://backend/app/skills/registry.py)
- [backend/app/models/tables.py](file://backend/app/models/tables.py)
- [backend/app/core/config.py](file://backend/app/core/config.py)
- [backend/app/api/agent_routes.py](file://backend/app/api/agent_routes.py)
- [backend/app/main.py](file://backend/app/main.py)
</cite>

## 目录
1. [简介](#简介)
2. [项目结构](#项目结构)
3. [核心组件](#核心组件)
4. [架构总览](#架构总览)
5. [详细组件分析](#详细组件分析)
6. [依赖关系分析](#依赖关系分析)
7. [性能考虑](#性能考虑)
8. [故障排查指南](#故障排查指南)
9. [结论](#结论)
10. [附录](#附录)

## 简介
本文件面向Agent智能体系统，系统采用“多智能体编排”架构，围绕BaseAgent基类设计统一的抽象接口与生命周期管理，通过工作空间（Workspace）实现节点间数据共享，由编排引擎（OrchestratorEngine）按固定流程顺序调度六大核心Agent完成从账号定位到内容审核的完整内容生产链路。系统同时提供技能（Skill）能力模块、注册表（Registry）、配置中心与数据库持久化，支持运行时配置更新与可观测性追踪。

## 项目结构
后端采用FastAPI应用入口，核心模块分布如下：
- agents：智能体基类与具体实现（账号解析、热点分析、选题策划、标题生成、内容写作、审核评估）
- orchestrator：编排引擎与工作空间
- skills：技能基类与注册表
- models：SQLAlchemy ORM模型（任务、节点执行记录、账号画像、话题候选、文章草稿、审核结果、系统配置等）
- core：配置、日志、追踪工具
- api：REST API路由（任务、流式事件、智能体配置、技能、LLM提供商、系统配置）
- main：应用入口、中间件、异常处理、启动/关闭生命周期

```mermaid
graph TB
subgraph "应用入口"
MAIN["main.py<br/>应用启动/中间件/异常处理"]
end
subgraph "编排层"
ORCH["orchestrator/engine.py<br/>编排引擎"]
WS["orchestrator/workspace.py<br/>工作空间"]
end
subgraph "智能体层"
BASE["agents/base.py<br/>BaseAgent/AgentResult"]
REG["agents/registry.py<br/>AgentRegistry"]
PRA["agents/profile_agent.py<br/>账号解析"]
AUD["agents/audit_agent.py<br/>审核评估"]
end
subgraph "技能层"
SKBASE["skills/base.py<br/>BaseSkill"]
SKREG["skills/registry.py<br/>SkillRegistry"]
end
subgraph "数据与配置"
MODELS["models/tables.py<br/>ORM模型"]
CFG["core/config.py<br/>配置中心"]
end
subgraph "API层"
AGENTAPI["api/agent_routes.py<br/>智能体配置API"]
end
MAIN --> ORCH
ORCH --> WS
ORCH --> REG
REG --> PRA
REG --> AUD
ORCH --> MODELS
ORCH --> CFG
MAIN --> AGENTAPI
MAIN --> MODELS
```

图表来源
- [backend/app/main.py:1-153](file://backend/app/main.py#L1-L153)
- [backend/app/orchestrator/engine.py:1-285](file://backend/app/orchestrator/engine.py#L1-L285)
- [backend/app/orchestrator/workspace.py:1-53](file://backend/app/orchestrator/workspace.py#L1-L53)
- [backend/app/agents/base.py:1-99](file://backend/app/agents/base.py#L1-L99)
- [backend/app/agents/registry.py:1-40](file://backend/app/agents/registry.py#L1-L40)
- [backend/app/agents/profile_agent.py:1-102](file://backend/app/agents/profile_agent.py#L1-L102)
- [backend/app/agents/audit_agent.py:1-141](file://backend/app/agents/audit_agent.py#L1-L141)
- [backend/app/skills/base.py:1-37](file://backend/app/skills/base.py#L1-L37)
- [backend/app/skills/registry.py:1-37](file://backend/app/skills/registry.py#L1-L37)
- [backend/app/models/tables.py:1-319](file://backend/app/models/tables.py#L1-L319)
- [backend/app/core/config.py:1-99](file://backend/app/core/config.py#L1-L99)
- [backend/app/api/agent_routes.py:1-115](file://backend/app/api/agent_routes.py#L1-L115)

章节来源
- [backend/app/main.py:1-153](file://backend/app/main.py#L1-L153)
- [backend/app/orchestrator/engine.py:1-285](file://backend/app/orchestrator/engine.py#L1-L285)
- [backend/app/models/tables.py:1-319](file://backend/app/models/tables.py#L1-L319)

## 核心组件
- BaseAgent与AgentResult：定义统一的异步执行接口、标准化返回结构、成功/失败封装与回退策略钩子，确保所有Agent遵循一致的契约。
- AgentRegistry：集中注册与检索Agent实例，支持查询、遍历与存在性检查。
- OrchestratorEngine：线性编排六大Agent节点，管理任务生命周期、节点执行记录、超时控制、错误传播与降级回退。
- Workspace：任务级上下文容器，提供键值存取、快照与按映射提取输入的能力。
- Skills：工具型能力封装，与Agent解耦，通过注册表统一管理。
- 数据模型：以ORM形式承载任务、节点执行、账号画像、话题候选、文章草稿、审核结果与系统配置等。
- 配置中心：从环境变量与运行时配置加载LLM参数、超时与应用参数。
- API路由：提供智能体配置查询与更新接口，支持运行时调整系统提示词与重试策略。

章节来源
- [backend/app/agents/base.py:18-99](file://backend/app/agents/base.py#L18-L99)
- [backend/app/agents/registry.py:10-40](file://backend/app/agents/registry.py#L10-L40)
- [backend/app/orchestrator/engine.py:89-285](file://backend/app/orchestrator/engine.py#L89-L285)
- [backend/app/orchestrator/workspace.py:12-53](file://backend/app/orchestrator/workspace.py#L12-L53)
- [backend/app/skills/base.py:16-37](file://backend/app/skills/base.py#L16-L37)
- [backend/app/skills/registry.py:10-37](file://backend/app/skills/registry.py#L10-L37)
- [backend/app/models/tables.py:23-319](file://backend/app/models/tables.py#L23-L319)
- [backend/app/core/config.py:52-99](file://backend/app/core/config.py#L52-L99)
- [backend/app/api/agent_routes.py:17-115](file://backend/app/api/agent_routes.py#L17-L115)

## 架构总览
系统采用“编排驱动”的流水线式架构：应用启动时注册所有Agent；编排引擎按预设节点顺序依次调度；每个节点从工作空间提取输入，调用Agent执行，将输出写回工作空间；节点执行记录持久化，支持SSE事件广播；最终任务结果作为工作空间快照返回。

```mermaid
sequenceDiagram
participant Client as "客户端"
participant API as "API路由"
participant Engine as "编排引擎"
participant Reg as "Agent注册表"
participant Agent as "具体Agent"
participant WS as "工作空间"
participant DB as "数据库"
Client->>API : "提交任务请求"
API->>Engine : "run(task, db)"
Engine->>WS : "初始化工作空间"
loop 按节点顺序
Engine->>Reg : "获取Agent实例"
Engine->>WS : "extract_for_agent(映射)"
Engine->>Agent : "execute(input_data, context)"
Agent-->>Engine : "AgentResult"
alt 成功
Engine->>WS : "set(output_key, data)"
Engine->>DB : "记录节点执行"
else 失败
Engine->>Agent : "fallback(error, input_data)"
Agent-->>Engine : "回退结果(可选)"
opt 回退成功
Engine->>WS : "set(output_key, fallback_data)"
Engine->>DB : "记录降级节点"
end
end
end
Engine->>DB : "记录任务完成"
Engine-->>API : "返回结果数据"
API-->>Client : "返回任务结果"
```

图表来源
- [backend/app/orchestrator/engine.py:92-234](file://backend/app/orchestrator/engine.py#L92-L234)
- [backend/app/orchestrator/workspace.py:36-53](file://backend/app/orchestrator/workspace.py#L36-L53)
- [backend/app/agents/registry.py:23-28](file://backend/app/agents/registry.py#L23-L28)
- [backend/app/models/tables.py:23-74](file://backend/app/models/tables.py#L23-L74)

## 详细组件分析

### BaseAgent基类与生命周期
- 抽象方法：execute(input_data, context) → AgentResult，强制实现统一的异步执行接口。
- 生命周期管理：
  - 执行前：编排引擎注入系统提示词（优先DB自定义，否则使用Agent默认），合并工作空间快照作为上下文。
  - 执行中：带超时控制，超时或异常被捕获并转换为节点失败。
  - 执行后：成功写入工作空间；失败触发回退；必要时抛出错误中断流程。
- 通用功能：
  - 标准化返回：AgentResult封装状态、代理标识、数据、错误与追踪ID。
  - 成功/失败便捷构造器：_success/_failure统一错误码与消息格式。
  - 回退钩子：fallback(error, input_data)可选实现，用于降级恢复。

```mermaid
classDiagram
class BaseAgent {
+agent_id : str
+name : str
+description : str
+default_system_prompt : str
+execute(input_data, context) AgentResult*
+fallback(error, input_data) AgentResult?
+get_system_prompt(context) str
-_success(data, trace_id) AgentResult
-_failure(code, message, trace_id) AgentResult
}
class AgentResult {
+status : str
+agent_name : str
+data : dict
+error : dict
+trace_id : str
+to_dict() dict
+is_success bool
}
BaseAgent --> AgentResult : "返回"
```

图表来源
- [backend/app/agents/base.py:49-99](file://backend/app/agents/base.py#L49-L99)

章节来源
- [backend/app/agents/base.py:49-99](file://backend/app/agents/base.py#L49-L99)

### 六大核心Agent职责与实现要点
- 账号解析（ProfileAgent）
  - 职责：将用户输入的账号定位描述解析为结构化画像（领域、子域、受众、调性、风格、关键词等）。
  - 实现：构造系统提示词与用户提示词，调用LLM生成JSON，解析并校验，失败时回退到默认结构。
  - 关键点：针对特定供应商（如dashscope）拼接模型前缀，处理LLM返回的markdown代码块包裹的JSON。

- 审核评估（AuditAgent）
  - 职责：对标题与正文进行合规性审核与质量评估，输出通过与否、风险等级与问题清单。
  - 实现：组合账号画像与内容摘要构建用户提示词，限制内容长度避免token溢出，解析JSON并回退兜底。
  - 关键点：严格遵循输出schema约束，高风险问题直接导致不通过。

```mermaid
flowchart TD
Start(["开始"]) --> ParseInput["解析输入: profile/titles/content"]
ParseInput --> BuildPrompt["构建审核提示词"]
BuildPrompt --> CallLLM["调用LLM生成JSON"]
CallLLM --> ParseJSON{"JSON解析成功?"}
ParseJSON --> |是| Validate["校验输出schema"]
ParseJSON --> |否| Fallback["回退兜底"]
Validate --> Done(["结束"])
Fallback --> Done
```

图表来源
- [backend/app/agents/audit_agent.py:53-141](file://backend/app/agents/audit_agent.py#L53-L141)

章节来源
- [backend/app/agents/profile_agent.py:12-102](file://backend/app/agents/profile_agent.py#L12-L102)
- [backend/app/agents/audit_agent.py:12-141](file://backend/app/agents/audit_agent.py#L12-L141)

### 编排引擎与工作空间
- 编排策略：
  - 固定线性节点序列：账号解析 → 热点分析 → 选题策划 → 标题生成 → 正文生成 → 审核评估。
  - 输入映射：每个节点定义input_mapping，将工作空间键映射到Agent输入字段。
  - 输出写回：节点成功后将data写入工作空间指定key。
  - 超时与错误：统一超时控制，失败时尝试回退；必填节点失败直接中断并记录错误。
- 工作空间：
  - 提供get/set/snapshot/extract_for_agent等方法，支持从原始输入与历史输出中抽取Agent所需数据。
  - 支持简单顶层键映射，便于MVP阶段快速迭代。

```mermaid
sequenceDiagram
participant E as "编排引擎"
participant W as "工作空间"
participant A as "Agent"
participant D as "数据库"
E->>W : "snapshot() 作为上下文"
E->>W : "extract_for_agent(mapping)"
E->>A : "execute(input, context)"
A-->>E : "AgentResult"
alt 成功
E->>W : "set(output_key, data)"
E->>D : "持久化节点记录"
else 失败
E->>A : "fallback(error, input)"
A-->>E : "回退结果(可选)"
opt 回退成功
E->>W : "set(output_key, fallback_data)"
E->>D : "标记降级节点"
end
end
```

图表来源
- [backend/app/orchestrator/engine.py:107-234](file://backend/app/orchestrator/engine.py#L107-L234)
- [backend/app/orchestrator/workspace.py:19-53](file://backend/app/orchestrator/workspace.py#L19-L53)

章节来源
- [backend/app/orchestrator/engine.py:31-86](file://backend/app/orchestrator/engine.py#L31-L86)
- [backend/app/orchestrator/engine.py:92-234](file://backend/app/orchestrator/engine.py#L92-L234)
- [backend/app/orchestrator/workspace.py:12-53](file://backend/app/orchestrator/workspace.py#L12-L53)

### 注册机制与动态加载
- Agent注册：
  - 应用启动时导入各Agent实现并在main中集中注册到AgentRegistry。
  - Registry提供register/get/list_all/has等操作，支持重复注册告警与缺失异常。
- 动态加载：
  - 当前通过显式导入实现静态注册；后续可扩展为从配置或插件目录动态发现与实例化。
- 依赖注入与配置：
  - 编排引擎通过Registry按agent_id获取实例；系统提示词优先从数据库自定义模板加载，否则使用Agent默认模板。

```mermaid
classDiagram
class AgentRegistry {
-_agents : dict[str, BaseAgent]
+register(agent) void
+get(agent_id) BaseAgent
+list_all() list
+has(agent_id) bool
}
class BaseAgent {
+agent_id : str
+execute(input_data, context) AgentResult*
}
AgentRegistry --> BaseAgent : "管理实例"
```

图表来源
- [backend/app/agents/registry.py:10-40](file://backend/app/agents/registry.py#L10-L40)
- [backend/app/agents/base.py:49-75](file://backend/app/agents/base.py#L49-L75)

章节来源
- [backend/app/agents/registry.py:10-40](file://backend/app/agents/registry.py#L10-L40)
- [backend/app/main.py:34-42](file://backend/app/main.py#L34-L42)

### 数据模型与持久化
- 任务与节点执行：
  - TaskModel：任务生命周期、输入输出、耗时与总token统计。
  - TaskNodeRunModel：节点级执行记录，含输入/输出、错误、耗时、token、模型与重试次数。
- 结果实体：
  - AccountProfileModel：账号画像持久化。
  - TopicCandidateModel：候选话题持久化。
  - ArticleDraftModel：文章草稿持久化。
  - AuditResultModel：审核结果持久化。
- 系统配置：
  - AgentModel/SkillModel：智能体/技能元数据与运行时配置。
  - SystemConfigModel：系统配置键值表。
  - LLMProviderModel：LLM提供商配置（密钥、URL、模型、超时等）。

```mermaid
erDiagram
TASK {
string id PK
string workflow_id
string status
json input_data
json result_data
string error_message
float elapsed_seconds
int total_tokens
}
TASK_NODE_RUN {
int id PK
string task_id FK
string node_id
string agent_id
string status
json input_data
json output_data
string error_message
boolean degraded
float elapsed_seconds
int prompt_tokens
int completion_tokens
string model_used
int retry_count
}
ACCOUNT_PROFILE {
int id PK
string task_id FK
text positioning
string domain
string subdomain
json target_audience
string tone
string content_style
json keywords
}
TOPIC_CANDIDATE {
int id PK
string task_id FK
string title
text angle
text hook
string target_emotion
float estimated_appeal
text reasoning
int rank
boolean selected
}
ARTICLE_DRAFT {
int id PK
string task_id FK
string title
text content_markdown
text content_html
int word_count
json structure
json tags
string status
}
AUDIT_RESULT {
int id PK
string task_id FK
int draft_id FK
boolean passed
string risk_level
json issues
text overall_comment
}
TASK ||--o{ TASK_NODE_RUN : "包含"
TASK ||--|| ACCOUNT_PROFILE : "包含"
TASK ||--o{ TOPIC_CANDIDATE : "包含"
TASK ||--o{ ARTICLE_DRAFT : "包含"
ARTICLE_DRAFT ||--|| AUDIT_RESULT : "包含"
```

图表来源
- [backend/app/models/tables.py:23-158](file://backend/app/models/tables.py#L23-L158)

章节来源
- [backend/app/models/tables.py:23-319](file://backend/app/models/tables.py#L23-L319)

### API与配置管理
- 智能体配置API：
  - 列出已注册Agent并查询其DB自定义提示词是否存在。
  - 获取单个Agent详情，返回有效提示词（优先DB自定义）。
  - 更新Agent配置（模型参数、提示词模板、重试策略），空字符串表示重置为默认。
- 配置中心：
  - 从环境变量加载LLM提供商配置，自动填充API Key、Base URL与默认模型。
  - 统一超时参数（Agent、Skill、LLM）。

章节来源
- [backend/app/api/agent_routes.py:17-115](file://backend/app/api/agent_routes.py#L17-L115)
- [backend/app/core/config.py:21-99](file://backend/app/core/config.py#L21-L99)

## 依赖关系分析
- 组件耦合：
  - 编排引擎强依赖AgentRegistry与Workspace；弱依赖数据库模型用于持久化与提示词解析。
  - Agent实现仅依赖BaseAgent与配置中心，保持与编排层解耦。
  - 技能层与智能体层相互独立，通过注册表管理。
- 外部依赖：
  - LLM调用通过统一SDK封装，当前示例对接特定供应商。
  - 数据库使用SQLAlchemy ORM，支持异步会话。
- 循环依赖：
  - 未见循环导入；注册在应用启动阶段集中完成。

```mermaid
graph LR
Engine["编排引擎"] --> Reg["Agent注册表"]
Engine --> WS["工作空间"]
Engine --> DB["数据库模型"]
Engine --> Cfg["配置中心"]
Agent["具体Agent"] --> Base["BaseAgent"]
Agent --> Cfg
Skill["技能实现"] --> SBase["BaseSkill"]
Skill --> SReg["Skill注册表"]
```

图表来源
- [backend/app/orchestrator/engine.py:18-26](file://backend/app/orchestrator/engine.py#L18-L26)
- [backend/app/agents/base.py:11-15](file://backend/app/agents/base.py#L11-L15)
- [backend/app/skills/base.py:10-13](file://backend/app/skills/base.py#L10-L13)

章节来源
- [backend/app/orchestrator/engine.py:18-26](file://backend/app/orchestrator/engine.py#L18-L26)
- [backend/app/agents/base.py:11-15](file://backend/app/agents/base.py#L11-L15)
- [backend/app/skills/base.py:10-13](file://backend/app/skills/base.py#L10-L13)

## 性能考虑
- 超时控制：编排引擎对Agent执行设置统一超时，避免阻塞；LLM调用同样设置超时，防止长尾请求。
- Token统计：节点执行记录累计prompt与completion token，便于成本与性能分析。
- 内容截断：审核Agent对正文内容进行长度限制，避免超出token上限。
- 并发与资源：当前为线性编排；若扩展为并行，需引入队列与资源配额控制。
- 日志与追踪：全局Trace ID中间件贯穿请求生命周期，结合数据库日志模型实现端到端追踪。

## 故障排查指南
- 常见错误类型：
  - Agent执行错误：编排引擎捕获异常并记录节点失败；必填节点失败会中断任务。
  - LLM解析失败：JSON解析异常会被捕获并转为失败结果；建议检查提示词与输出格式。
  - 超时：Agent执行超时会记录错误并中断；可适当提高超时阈值或优化Agent内部逻辑。
  - 回退策略：部分Agent提供回退实现，可在服务异常时返回兜底结构，降低整体失败率。
- 排查步骤：
  - 查看任务与节点执行记录，确认失败节点与错误信息。
  - 检查系统提示词来源（默认模板 vs DB自定义）。
  - 核对LLM提供商配置与API Key有效性。
  - 启用调试模式查看详细堆栈信息。

章节来源
- [backend/app/orchestrator/engine.py:176-196](file://backend/app/orchestrator/engine.py#L176-L196)
- [backend/app/agents/profile_agent.py:74-77](file://backend/app/agents/profile_agent.py#L74-L77)
- [backend/app/agents/audit_agent.py:82-85](file://backend/app/agents/audit_agent.py#L82-L85)

## 结论
本系统以BaseAgent为核心，通过编排引擎实现稳定的线性工作流，配合工作空间实现节点间数据共享与上下文传递。注册表与配置中心提供了良好的扩展性与运行时可调性。建议后续增强：
- 引入动态加载与插件化机制；
- 支持并行编排与任务图；
- 完善技能体系与跨Agent协作协议；
- 加强可观测性与告警机制。

## 附录
- Agent间通信协议：
  - 输入/输出均为结构化JSON，遵循各Agent定义的schema。
  - 上下文通过工作空间快照传递，包含历史节点输出。
- 错误处理策略：
  - 统一的AgentResult封装错误码与消息；
  - 必填节点失败直接中断，非必填节点尝试回退；
  - 超时与异常均记录节点执行记录并广播事件。
- 扩展开发指南：
  - 新增Agent：继承BaseAgent，实现execute与可选fallback，注册到AgentRegistry。
  - 新增技能：继承BaseSkill，实现execute，注册到SkillRegistry。
  - 配置管理：通过Agent配置API更新提示词与重试策略，或在DB中维护AgentModel条目。