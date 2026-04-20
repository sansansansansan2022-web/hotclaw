# HotClaw 职责收口操作指南

更新时间：2026-04-17
依赖文档：`docs/agent_skill_boundary.md`

## 目标

这份指南不是新的架构宣言，而是把上一份职责重划文档变成可以逐批执行的收口手册。

目标只有三个：

1. 把决策层、能力层、执行层切开。
2. 用尽量小的批次完成收口，避免一口气大改导致链路失稳。
3. 在每一批改造前，提前知道改完会得到什么，可能失去什么，以及如何回退。

## 适用原则

### 收口不是重写

本轮不重写 orchestrator，不替换 runtime，不推翻现有任务详情页和 artifacts 机制。
所有改造都围绕现有 `engine + workspace + artifacts + runtime` 体系增量演进。

### 收口优先级

优先顺序固定为：

1. 先改“名字明显不对、职责最错位”的模块
2. 再改“跨层最严重、会持续放大复杂度”的模块
3. 最后再改“可以工作但层级过高”的执行型 agent

### 单批次护栏

每一批都要满足：

- 只动一小组紧邻模块
- 不同时改流程拓扑和业务 prompt
- 不同时引入新的 fallback 机制
- 改完后可以单独 smoke test
- 可以一键回退到上一批状态

## 收口总路线

### 批次 1：去掉最明显的“伪 Agent”

目标模块：

- `post_process_agent -> post_process_service`
- `title_generator_agent -> title_generate_skill`
- `profile_agent -> profile_parse_skill`

后处理代理 -> 后处理服务` - `标题生成代理 -> 标题生成技能` - `资料解析代理 -> 资料解析技能`


这是当前收益最高、风险最低的一批。

### 批次 2：拆解 `hot_topic_agent`

目标模块：

- `hot_topic_agent`
- `hot_topic_fetch_skill`
- `skill_router_service`
- `skill_runtime_service`
- `evidence_service`
- `reference_digest_service`
- `query_planner_service`

这一批不追求功能增强，只追求把“热点适配判断”和“证据收集执行”拆开。

### 批次 3：统一执行型写作能力

目标模块：

- `outline_planner_agent -> outline_generate_skill`
- `section_writer_agent -> section_draft_skill`
- `content_writer_agent -> legacy_writer_skill` 或保留过渡壳
- `style_reviewer_agent -> style_review_skill`
- `structure_reviewer_agent -> structure_review_skill`
- `rewrite_agent -> rewrite_skill`

这一批的重点是把“单轮 LLM 包装器”统一还原成执行型能力。

## 操作前准备

在开始任何批次前，先做四件事。

### 1. 建立模块台账

至少补齐这张表：

| 模块 | 当前层级 | 目标层级 | 上游调用者 | 下游依赖 | 当前产物键 | 是否有 fallback |
| --- | --- | --- | --- | --- | --- | --- |

作用：

- 避免改完名字后，不知道 workspace / artifact / UI 哪些地方还在引用旧字段
- 避免“代码改完了，节点显示还挂着旧 agent_id”

### 2. 锁定每个模块的输入输出契约

每个收口对象都要在改造前确认：

- 当前输入从哪里来
- 当前输出写到哪里
- 哪些字段被前端直接消费
- 哪些字段被下游节点依赖

如果不先锁契约，最容易出现的问题是：

- 逻辑没坏，但页面空了
- 节点没挂，但下游读不到数据
- artifact 名字变了，task detail 直接降级

### 3. 明确过渡策略

每个模块改造前，先选一种过渡方式：

- 保留旧 agent_id，内部改成调用 skill / service
- 新增 skill，同时保留旧 agent 外壳过渡一个阶段
- 直接删除旧 agent，由 orchestrator 改调新 skill

默认建议：

- 第一批以“保留旧壳、内部降级”为主
- 第二批开始才逐步移除壳

### 4. 为每一批准备最小 smoke test

每个批次至少要有一条最短链路验证。

建议如下：

- 批次 1：
  - profile parse 输出结构完整
  - title generation 仍能给 preview 提供候选标题
  - post-process 仍能产出 HTML / image slots / publish format
- 批次 2：
  - hot topic 仍能产出 `query_plan + selected_evidence + reference_digest + hot_topics`
  - 参考源篮子和创作链路不断
- 批次 3：
  - topic -> title -> outline -> section -> review -> rewrite 仍能完整串联

## 批次 1 操作指南

### 目标

先纠正最明显的命名错位，让系统里的“Agent”数量下降，但功能不下降。

### 1. `post_process_agent -> post_process_service`

#### 改法

- 新建 `post_process_service`
- 把模板选择、markdown/html 格式化、image slot 生成、wechat publish format 输出全部下沉
- 过渡期保留 `post_process_agent`，但它只做 service 调用和结果透传

#### 为什么先改它

- 当前它没有真实的 agent 判断行为
- 不依赖复杂的上下文决策
- 改完后最能立刻净化架构语义

#### 验收

- 任务详情页里 post-process 产物不变
- 前端仍能看到排版结果、模板、image slots
- 节点轨迹可继续展示成功/跳过原因

### 2. `title_generator_agent -> title_generate_skill`

#### 改法

- 新建 skill 契约，输入为 `topics/profile/account_context/reference_digest`
- 输出保持 `selected_topic + titles`
- 过渡期保留旧 agent 壳，只负责：
  - 构造 skill 输入
  - 调用 runtime
  - 兼容旧 artifact 结构

#### 为什么先改它

- 当前实现是典型单轮生成能力
- 最适合示范“Agent 外壳 -> Skill 内核”的迁移路径

#### 验收

- preview 页仍能展示标题候选
- 最终成稿仍能读取 `selected_topic`
- task detail 中标题产物不消失

### 3. `profile_agent -> profile_parse_skill`

#### 改法

- 把自然语言定位 -> 结构化画像的逻辑迁到 skill
- 保留旧输出 contract
- 如果 onboarding 流程或账号详情页直接依赖旧字段，不改字段名

#### 为什么先改它

- 纯结构化解析，几乎没有多步判断
- 改动清晰，收益稳定

#### 验收

- 账号画像仍能被后续 hot topic / topic planner 读取
- 账号详情页画像区不退化
- 旧任务读取旧 profile artifact 不报错

### 批次 1 预评估

#### 预期收益

- “名义上的 agent 数量”会下降，但真实能力不会减少
- 新增功能时更容易直接判断该写 skill 还是写 service
- 维护者更容易看懂：哪些模块在思考，哪些模块只是在执行

#### 风险

- orchestrator、workspace、前端如果直接写死 agent 名称或 artifact key，容易出现显示降级
- 旧节点 ID 如果直接改掉，task detail 可能会丢失映射

#### 总体判断

这是高收益、低风险批次，建议优先落地。

## 批次 2 操作指南

### 目标

解决当前最大的职责污染点：`hot_topic_agent`

### 原则

这一步不是“删除 hot topic 能力”，而是：

- 保留热点适配判断
- 拆掉它身上不该背的执行负担

### 1. 先把 `hot_topic_agent` 的职责切成三段

#### A. 规划输入

保留在 service：

- `query_planner_service`

#### B. 外部证据和候选源收集

放在 skill + runtime：

- `hot_topic_fetch_skill`
- `github_project_curator_skill`
- `scholar_paper_search_skill`
- `skill_router_service`
- `skill_runtime_service`
- `evidence_service`

#### C. 账号适配判断

保留在 `hot_topic_agent`：

- 哪些热点适合当前账号
- 哪些热点不值得写
- 为什么是现在写
- 最后给 `topic_planner_agent` 的热度与适配判断

### 2. 过渡实现建议

不要第一步就让 orchestrator 直接调多个 skill 节点。
先把 `hot_topic_agent` 改成只做两件事：

- 接收已准备好的 evidence package
- 负责热点适配分析

然后把 evidence package 的准备过程逐步迁到一个独立的 skill collection step。

### 3. 产物契约要先锁

这一步必须提前锁定这些产物：

- `query_plan`
- `source_candidates`
- `selected_evidence`
- `evidence_summaries`
- `reference_digest`
- `hot_topics`

否则一拆就会出现：

- 账号详情页推荐资讯区空白
- 创作篮子拿不到来源
- topic planner 没证据可用

### 批次 2 预评估

#### 预期收益

- 热点链路的可维护性会明显提升
- 以后加新的参考源 skill 不需要继续把逻辑堆进 `hot_topic_agent`
- debug 时能更快区分“抓取失败”还是“判断失败”

#### 风险

- 这是第一次真正碰跨层污染点，影响面比批次 1 大
- 如果 evidence 契约没先锁，会把账号详情页和创作前链一起打穿

#### 总体判断

这是中风险、高价值批次，必须在批次 1 稳住后再做。

## 批次 3 操作指南

### 目标

把执行型写作链统一成能力层，而不是一组名为 agent 的单轮包装器。

### 建议改法

#### 1. 统一抽象为写作技能组

建议分成：

- `outline_generate_skill`
- `section_draft_skill`
- `style_review_skill`
- `structure_review_skill`
- `rewrite_skill`

#### 2. `content_writer_agent` 特殊处理

它当前是 legacy fallback 写稿器，建议先不要强拆。

过渡做法：

- 如果仍承担 fallback 兜底，先保留壳
- 内部把单轮写稿逻辑明确标为 legacy writer capability
- 等结构化链稳定后，再决定彻底 skill 化还是保留成“单步 fallback writer”

#### 3. reviewer 并行化前先 skill 化

如果未来要做 reviewer 并行：

- 先把 style / structure review 都变成 skill
- 再由上层 agent 或 orchestrator 条件分支决定单 reviewer / 双 reviewer

不要让 reviewer agent 自己管理彼此调用关系。

### 批次 3 预评估

#### 预期收益

- 写作链结构更清晰
- 模型切换粒度更细
- reviewer、rewrite 的复用性更强
- 后续“每个 agent 选模型”会自然过渡到“每个能力节点选模型”

#### 风险

- 这批最容易牵动 preview、task detail、artifact 展示
- 如果没有稳定的中间产物契约，UI 会先崩可解释性

#### 总体判断

这是中高风险批次，必须建立在前两批和 artifact 契约稳定之后。

## 推荐执行顺序

建议不要并行大改，按下面顺序推进：

1. 文档和契约补齐
2. 批次 1
3. 批次 1 smoke test + UI 核验
4. 批次 2
5. 批次 2 参考源链路联调
6. 批次 3
7. 批次 3 写作链路联调

## 每批都要回答的 5 个问题

每次收口前，都先回答这 5 个问题：

1. 这个模块到底是在思考，还是在执行。
2. 这个模块的输入输出有没有被 UI 直接消费。
3. 改名后旧任务详情还能不能读。
4. 过渡期是保留旧壳，还是直接改 orchestrator。
5. 出问题时，能不能一键回退到上一批。

如果这 5 个问题回答不清，说明这一批还没准备好开始动。

## 修改后的总体效果预评估

### 架构可读性

预期提升明显。

改完后三层语义会更统一：

- Agent 真正只剩决策者
- Skill 真正只剩能力插件
- Service 真正只剩执行底座

这会直接降低团队内的命名歧义和新增代码的随意性。

### 研发效率

中期提升明显，短期会有一点迁移成本。

短期成本来自：

- 契约补齐
- orchestrator 映射调整
- artifact 兼容处理

中期收益来自：

- 加一个新参考源时不用改三层
- 模型切换粒度更细
- debug 能更快定位到“决策错误”还是“执行失败”

### 稳定性

如果按批次推进，整体稳定性会上升。
如果多批并行推进，稳定性会先下降。

原因很简单：

- 收口本身不是在加复杂度
- 但如果同时改层级、改节点、改契约、改 UI，风险会叠加

### 可观测性

预期会明显提升。

改完后任务详情页更容易回答这些问题：

- 这一步是判断节点还是执行节点
- 失败是 skill 执行失败，还是 agent 策略失败
- 哪些产物是中间能力输出，哪些是最终决策结果

### 后续动态编排能力

这是这轮收口的长期收益点。

只有先切清 agent 和 skill，后面 `account_ops_agent` 才可能真正变成“协作总控”。
否则它永远只能控制一堆职责混乱的节点，很难做稳定的条件分支和模型策略。

## 最终建议

就 HotClaw 当前状态，建议按下面原则推进：

- 先改错位最明显的模块，不先碰最复杂链路
- 先保留旧壳兼容，不急着一步到位删光
- 先锁产物契约，再拆跨层热点链
- 先让架构语义变干净，再谈更聪明的动态协作

如果按这个指南推进，预期结果不是“功能突然变多”，而是：

- 系统边界更清楚
- 改动成本下降
- 调试成本下降
- 后续三阶段演进更稳

这才是当前 HotClaw 最值钱的增益。
