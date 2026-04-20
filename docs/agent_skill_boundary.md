# HotClaw Agent / Skill / Service 职责边界

更新时间：2026-04-17
适用范围：当前 `backend/app` 目录下的创作链、参考源链、运行时与编排层

## 目的

这份文档不是抽象方法论，而是基于 HotClaw 当前代码实现做的职责重划建议。

要解决的不是“功能还不够多”，而是下面这些已经开始出现的结构性症状：

- 一个能力写三层
- 调用链越来越长
- 改一个功能要同时改 agent、skill、service
- debug 时分不清问题出在决策层、执行层还是运行时层

当前最重要的目标不是继续加功能，而是先把能力分层定死，让后续的模型切换、节点动态化、UI 可解释性都有稳定边界。

## 本次审计覆盖

这次归类结论直接基于以下真实模块的代码实现，不是按命名猜测：

- `backend/app/agents/hot_topic_agent.py`
- `backend/app/agents/profile_agent.py`
- `backend/app/agents/title_generator_agent.py`
- `backend/app/agents/topic_planner_agent.py`
- `backend/app/agents/content_writer_agent.py`
- `backend/app/agents/audit_agent.py`
- `backend/app/agents/account_ops_agent.py`
- `backend/app/agents/post_process_agent.py`
- `backend/app/services/query_planner_service.py`
- `backend/app/services/reference_digest_service.py`
- `backend/app/services/article_assembler_service.py`
- `backend/app/services/draft_quality_gate_service.py`
- `backend/app/skills/hot_topic_fetch_skill.py`
- `backend/app/skills/external/github_project_curator_skill.py`
- `backend/app/skills/external/scholar_paper_search_skill.py`
- `backend/app/skills/services/skill_runtime_service.py`
- `backend/app/skills/services/skill_router_service.py`
- `backend/app/skills/services/evidence_service.py`
- `backend/app/orchestrator/engine.py`

## 分层定义

### Agent

Agent 只负责“决定怎么做”。

- 基于上下文做判断
- 选择策略
- 规划下一步
- 决定是否降级、跳过、重试、收缩成本
- 组合多个能力，但不亲自承包底层执行细节

一句话：

> Agent 是决策层，不是工具层。

### Skill

Skill 只负责“把某件复用能力稳定做完”。

- 输入清晰
- 输出清晰
- 能被多个 agent / workflow 复用
- 可以做检索、过滤、生成候选、格式化、提取
- 不应主导整条工作流

一句话：

> Skill 是能力插件，不是流程大脑。

### Service

Service 是后端执行底座。

- 数据库存取
- 持久化和缓存
- 运行时封装
- 规则计算
- 装配、去重、打分、路由、schema 校验

一句话：

> Service 是执行层，不应该伪装成智能体。

### Orchestrator

Orchestrator 只负责流程推进。

- 节点顺序
- 状态机
- 输入输出挂接
- 错误传播
- 执行广播

一句话：

> Orchestrator 负责流程，不负责业务判断。

## 判断标准

判断每个模块时只问三件事：

1. 它是不是在决定怎么做。是的话偏 Agent。
2. 它是不是在稳定执行某个复用能力。是的话偏 Skill。
3. 它是不是纯后端逻辑、持久化、缓存、运行时支撑。是的话偏 Service。

如果一个模块同时命中 1 和 2，通常意味着它已经发生职责污染，需要拆层。

## 当前模块归类表

### 应保留为 Agent 的模块

| 模块 | 当前职责 | 建议归属 | 判断 |
| --- | --- | --- | --- |
| `account_ops_agent` | 基于账号健康、参考源、历史任务生成运行策略 | Agent | 真实在做“是否运行、怎么运行、是否启用 reviewer / rewrite / post-process”的策略判断 |
| `topic_planner_agent` | 从热点和证据中决定当前账号值得写的主题方向 | Agent | 真实在做账号适配、内容 lane、切入角度、why-now 判断 |
| `audit_agent` | 基于风险、证据真实性、合规性做放行或拦截 | Agent | 这是明确的策略门，不应下沉为普通工具 |
| `hot_topic_agent` | 当前混合了证据收集、技能调用、热点分析 | 保留为 Agent 外壳，但必须瘦身 | 它仍有“哪些热点适合当前账号”的判断价值，但现在执行职责过重 |

### 更适合降级为 Skill 的模块

| 模块 | 当前职责 | 目标归属 | 原因 |
| --- | --- | --- | --- |
| `profile_agent` | 单轮 LLM 将定位文本转成结构化画像 | Skill | 当前实现更像 `profile_parse_skill`，没有多步判断或策略分叉 |
| `title_generator_agent` | 单轮 LLM 从 topics 中选强项并生成标题候选 | Skill | 目前是稳定生成能力，不是开放式决策器 |
| `outline_planner_agent` | 基于 topic/title 生成大纲 | Skill | 当前更像 `outline_generate_skill` |
| `content_writer_agent` | 单轮生成完整正文 | Skill | 现在更像 legacy 单发写作能力，而不是真正多步 writer agent |
| `section_writer_agent` | 基于大纲分段出稿 | Skill | 明确执行型能力，适合做 section drafting skill |
| `style_reviewer_agent` | 单轮风格审查 | Skill | 更像 review capability |
| `structure_reviewer_agent` | 单轮结构审查 | Skill | 更像 review capability |
| `rewrite_agent` | 基于 reviewer 结果进行改写 | Skill | 当前是稳定执行型改写，不是上层调度者 |

### 应保留为 Service 的模块

| 模块 | 当前职责 | 建议归属 | 判断 |
| --- | --- | --- | --- |
| `query_planner_service` | 构造查询计划、lane、关键词等 | Service | 规则计算助手，不应升级成 agent |
| `reference_digest_service` | 整理 source scout package、reference digest | Service | 典型数据整形和摘要装配层 |
| `article_assembler_service` | 装配 title / topic / outline / content 产物 | Service | 典型装配器 |
| `draft_quality_gate_service` | 草稿质量闸门、结构化 gate 结果 | Service | 质量校验层，不应伪装成智能体 |
| `skill_runtime_service` | Skill 调用运行时、统一执行入口 | Service | 名字里有 skill，但本质是 runtime service |
| `skill_router_service` | 根据上下文决定是否启用哪些 skill | Service | 是策略辅助器，不应冒充业务 skill |
| `evidence_service` | 证据持久化、转换、source candidate 映射 | Service | 明确的数据与持久化支持层 |

### 应保留为 Skill 的模块

| 模块 | 当前职责 | 建议归属 | 判断 |
| --- | --- | --- | --- |
| `hot_topic_fetch_skill` | 抓取热点、解析结果、标准化输出 | Skill | 是真实可复用的“抓热点”能力 |
| `github_project_curator_skill` | 收集 GitHub 项目候选及元信息 | Skill | 是稳定外部能力适配器 |
| `scholar_paper_search_skill` | 搜论文并返回结构化结果 | Skill | 是稳定外部能力适配器 |

### 应保留为 Orchestrator 的模块

| 模块 | 当前职责 | 建议归属 | 判断 |
| --- | --- | --- | --- |
| `orchestrator/engine.py` | 节点推进、状态管理、节点输入输出挂接、失败广播 | Orchestrator | 主体仍然是工作流推进层 |
| `orchestrator/workspace.py` | 任务中间态和产物容器 | Orchestrator support | 属于流程上下文承载层 |
| `orchestrator/broadcaster.py` | 状态广播 | Orchestrator support | 属于流程观测层 |

## 当前最明显的职责污染

### 1. `hot_topic_agent` 污染最严重

当前 `hot_topic_agent` 同时在做：

- query planning
- skill routing
- skill runtime 调用
- external evidence 收集
- evidence 持久化
- reference digest 装配
- 最后再做 LLM 级热点分析

这意味着它横跨了四层：

- Agent 的判断
- Skill 的执行
- Service 的数据装配
- Runtime 的调用编排

这类模块最危险，因为它会让后续所有优化都变成“继续往里面塞逻辑”。

建议目标：

- 保留“热点是否适合当前账号”的判断职责
- 把 fetch / router / evidence / digest 下沉到 skill + service
- 最终让它只接收已经准备好的 source package / evidence package / query plan，再做账号适配判断

### 2. `post_process_agent` 实际上不是 Agent

`post_process_agent` 当前没有 LLM 决策行为，主要在做：

- 选择模板
- 渲染 markdown / html
- 组装 layout blocks
- 生成 image slots
- 输出微信发布格式

这本质上是格式化和装配服务，不是 agent。

它现在最大的问题不是功能不对，而是“名字在骗架构”。

建议目标：

- 直接下沉成 `post_process_service`
- 如果后面真的要做“多模板智能选择 + 图文组合决策 + 风格适配”，再在上层补一个轻量 agent 壳

### 3. 一批“单轮 LLM 包装器”被命名成了 Agent

下面这些模块目前更像单轮生成或单轮审查能力：

- `profile_agent`
- `title_generator_agent`
- `outline_planner_agent`
- `content_writer_agent`
- `section_writer_agent`
- `style_reviewer_agent`
- `structure_reviewer_agent`
- `rewrite_agent`

这些模块的问题不是不能存在，而是名字和层级过高，容易让上层误以为它们具备多轮推理和流程主导能力。

建议统一认知：

- 当前实现里，它们大多是 skill 形态的能力
- 只有未来真的引入多轮比较、自反思、局部重规划，才值得升级回 agent

### 4. `engine.py` 已经出现轻微策略泄漏

`engine.py` 目前主体仍然是合格的 orchestrator，但已经出现一些策略味道较重的内容：

- reviewer / rewrite / fallback 的分组集合
- structured path 与 legacy fallback 的条件分支
- 部分节点跳过逻辑带有业务语义

这在当前阶段还能接受，但需要守住边界：

- engine 可以管理“条件分支”
- engine 不应该管理“为什么做出这个业务判断”

业务判断应该来自：

- `account_ops_agent`
- `audit_agent`
- 以及未来瘦身后的少数核心 decision agents

## HotClaw 目标结构

### Agent 层

长期建议只保留少量真正有决策价值的 agent：

- `account_ops_agent`
- `hot_topic_agent`，前提是瘦身后只保留主题适配判断
- `topic_planner_agent`
- `audit_agent`

可选后续演进：

- 真正多步写作型 `content_writer_agent`

前提是它不再只是“单轮写稿器”，而是负责：

- 结构规划
- 分段推进
- 自检
- 局部回改

### Skill 层

收口成明确的能力插件：

- `hot_topic_fetch_skill`
- `profile_parse_skill`
- `reference_collect_skill`
- `title_generate_skill`
- `outline_generate_skill`
- `section_draft_skill`
- `style_review_skill`
- `structure_review_skill`
- `rewrite_skill`

### Service 层

继续下沉一切原子执行和运行时支撑：

- `query_planner_service`
- `reference_digest_service`
- `article_assembler_service`
- `draft_quality_gate_service`
- `evidence_service`
- `skill_runtime_service`
- `skill_router_service`
- 参考源、数据库、缓存、微信发布相关 service

### Orchestrator 层

只保留这些职责：

- 节点顺序
- 条件分支
- workspace 挂接
- 状态推进
- 错误传播
- 广播

不要再往里面塞业务推理。

## 第一批收口对象

### 批次 1：低风险、收益立刻可见

1. `post_process_agent -> post_process_service`
2. `title_generator_agent -> title_generate_skill`
3. `profile_agent -> profile_parse_skill`

理由：

- 改动相对局部
- 几乎不影响主流程策略
- 能马上把“名字很智能、实际很工具”的错位纠正掉

### 批次 2：处理中等复杂度污染点

1. 瘦身 `hot_topic_agent`
2. 把 fetch / evidence / digest / router 从 `hot_topic_agent` 中继续下沉
3. 保留 `hot_topic_agent` 作为“账号适配判断器”

理由：

- 这是当前最典型的职责重叠点
- 不处理它，后续所有参考源增强都会继续堆在一个 agent 里

### 批次 3：统一一组执行型写作能力

统一评估并逐步 skill 化：

- `outline_planner_agent`
- `section_writer_agent`
- `content_writer_agent`
- `style_reviewer_agent`
- `structure_reviewer_agent`
- `rewrite_agent`

注意：

- 这里不是说功能变弱
- 而是先把它们从“伪 agent”纠正成“执行型能力”
- 等未来真的引入多轮规划和局部回退，再升级回 agent

## 不建议现在就做的事

- 不建议一次性重写整个 orchestrator
- 不建议把所有逻辑一把梭都塞进 skill
- 不建议为了“纯粹分层”去把已经稳定的 service 再包一层伪 skill
- 不建议在没有稳定 artifact 契约前就做开放式多 agent 协商

## 设计护栏

后续所有边界调整都要遵守这几条：

1. 决策只留在少数 agent。
2. Skill 不主导工作流。
3. Service 不伪装成智能。
4. Orchestrator 不承接业务推理。
5. 同一能力不能同时在 agent、skill、service 三层各写一版。
6. 一个模块如果既做判断又做底层执行，默认视为污染点。

## 最终结论

HotClaw 当前真正的问题不是“agent 不够多”，而是“很多执行型能力被命名成了 agent”。

当前最值得做的不是继续堆智能体数量，而是把系统收口成下面这个结构：

- 少数决策 agent
- 一组稳定 skill
- 清晰 service 底座
- 不承接业务判断的 orchestrator

就当前代码实现来看，最先该动的不是 `topic_planner_agent`、`account_ops_agent`、`audit_agent` 这些真决策层，而是：

- `post_process_agent`
- `profile_agent`
- `title_generator_agent`
- 以及已经明显跨层的 `hot_topic_agent`

这四块收口后，HotClaw 才会从“会说话的 wrapper 堆叠”进入真正可维护的协作系统阶段。
