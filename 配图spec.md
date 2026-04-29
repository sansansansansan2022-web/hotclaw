# HotClaw 公众号文章配图能力 Spec（按当前仓库对齐修订版）

## 0. 本次修订目的

这份文档不是重新发明一套“理想架构”，而是基于当前 `hotclaw` 仓库里的真实代码路径，对原始配图 spec 做三件事：

1. 校验哪些设想在当前系统里已经有落点，哪些还没有。
2. 把接口名、数据位置、链路阶段改成和现状一致。
3. 在**不改代码**的前提下，给后续实现留出最小可行、可迭代的落地方案。

---

## 1. 可行性校验结论

## 1.1 结论摘要

原始 spec 的方向是对的，但实现切入点和当前 HotClaw 现状不一致。

如果本次范围**只看草稿阶段**，那么当前代码里真正相关的链路应该收敛为：

```text
content / rewrite_result / assembled_article
→ post_process_agent
→ post_process_service
→ post_process_result
→ article_assembler_service
→ draft persistence / draft detail / task artifact
```

因此，V1 最可行的做法不是新建一整套：

- `figure_policy_service`
- `cover_image_service`
- `evidence_figure_service`
- `explainer_figure_service`
- `article_layout_renderer`

而是：

**以 `post_process_result` 作为配图规划的主数据出口，以 `article_assembler_service + draft_service + task_artifact_service` 作为草稿阶段的数据承载层，在这条链路上增量扩展。**

## 1.2 当前已具备的能力

仓库里已经存在这些真实能力：

1. `backend/app/agents/post_process_agent.py`
   负责文章后处理，已经输出：
   - `layout_template`
   - `layout_blocks`
   - `final_content_markdown`
   - `final_content_html`
   - `image_slots`
   - `cover_image_prompt`
   - `wechat_publish_format`

2. `backend/app/services/post_process_service.py`
   已经把图片相关规划统一塞进 `post_process_result`。

3. `backend/app/orchestrator/engine.py`
   会对 `post_process_result` 做归一化，保留：
   - `image_slots`
   - `cover_image_prompt`
   - `final_content_html`
   - `wechat_publish_format`

4. `backend/app/services/article_assembler_service.py`
   会优先采用 `post_process_result.final_content_markdown/html` 作为最终文章内容。

5. `backend/app/services/draft_service.py`
   草稿详情读取时，会把 `task_result_data["post_process_result"]` 带回给草稿详情 payload。

6. `backend/app/services/task_artifact_service.py`
   已支持把 `post_process_result` 暴露成任务 artifact，作为草稿阶段更稳定的调试和查看入口。

## 1.3 当前尚不具备的能力

这些是原 spec 里写了、但当前代码里**还没有真正落地**的部分：

1. 自动生成或检索真实图片资源
   现有 `image_slots` 只有 prompt / purpose / source_hint，没有图片 URL、文件路径、资产状态。

2. 自动把选中的图片插入 `final_content_html`
   当前 `final_content_html` 是文章排版 HTML，不会根据 `image_slots` 自动补 `<img>`。

3. 证据图抓取闭环
   当前没有论文 PDF 抽图、caption 匹配、图片资产缓存这条链路。

4. 解释图程序化渲染闭环
   当前没有 Mermaid/SVG/HTML 解释图渲染模块。

5. 前端稳定展示 `post_process_result`
   `draft_service.get_draft_detail()` 虽然把 `post_process_result` 放进了返回 dict，但 `backend/app/schemas/draft.py` 里的 `DraftDetail` 目前**没有显式声明这个字段**。现阶段更稳的对外载体是任务 artifact 或后续补 schema。

## 1.4 对原始 spec 的判断

原始 spec 可分成三类：

### A. 可以保留的部分

- 目标：让文章从纯文本升级为更像真实公众号成品
- 原则：配图失败不能阻塞主链路
- 分类：封面图 / 证据图 / 解释图
- 约束：事实型图片优先真实来源，解释型图片优先程序化生成

### B. 需要改写的部分

- “新增多个独立 service 并串入 orchestrator”的表述
- “放在 `content_writer` 之后、`layout_renderer` 之前”的链路描述
- 独立 `FigurePlan / FigureAsset / RenderedArticleAsset` 作为第一优先存储结构

### C. 现阶段不建议写进 V1 承诺的部分

- scholar 全网搜图
- 论文 PDF 通用抽图
- 复杂解释图渲染引擎
- 自动版权识别
- 完整可视化配图工作台

---

## 2. 修订后的 V1 目标

## 2.1 产品目标

在不重构现有 orchestrator 的前提下，为公众号文章增加一层“可落地的配图规划与草稿内容承载能力”，让 HotClaw 输出的文章具备：

1. 至少一条可用的封面图提示或封面图资产绑定位。
2. 最多 3 个正文配图槽位，用于后续人工选择或自动补图。
3. 可记录图片来源、用途、插入位置和审核前注意事项。
4. 即使没有任何图片资源，文章仍可正常生成、审核并保存为草稿。

## 2.2 工程目标

V1 必须满足：

1. 不新增重型 agent 节点。
2. 不破坏现有 `post_process_result` / `draft` 主链路。
3. 图片相关数据优先挂在现有结果结构里，而不是先拆新表。
4. 后续若要扩展自动选图/生图，只需要扩展 `post_process_result.image_slots` 和草稿 HTML 资产绑定逻辑。

---

## 3. V1 范围定义（修订后）

## 3.1 本期要做

V1 只承诺三类“能力”，不承诺三类能力都自动化完成：

### A. 封面图规划

- 生成 `cover_image_prompt`
- 生成 `image_slots[cover]`
- 支持未来把人工选定的封面图资产绑定到该槽位

### B. 正文图槽位规划

- 为文章生成 0~3 个 `inline` 图片槽位
- 标明插入位置、用途、prompt、可能参考来源

### C. 草稿态内容承载

- 草稿阶段保留 `image_slots`
- 草稿阶段保留 `cover_image_prompt`
- 若后续已绑定图片资产，草稿 HTML 应能承载对应 `<img>` 内容

## 3.2 本期不做

V1 明确不承诺：

- 自动完成论文图抓取
- 自动完成解释图渲染
- 自动完成 AI 生图
- 前端可视化配图面板
- 图片版权审核闭环
- 图片风格评分或 A/B Test

---

## 4. 真实系统中的放置位置

## 4.1 当前真实链路

当前仓库的真实**写路径**应以这条为准：

```text
topics / titles / assembled_article / rewrite_result
→ post_process_agent.execute()
→ post_process_service.prepare()
→ output: post_process_result
→ orchestrator normalize
→ article_assembler_service.extract_article_payload()
→ draft persistence
```

当前仓库的真实**读路径**应单独理解为：

```text
draft persistence / task result
→ draft_service.get_draft_detail()
→ DraftDetail response

task result / node output
→ task_artifact_service
→ post_process_result artifact
```

## 4.2 V1 推荐接入点

### 配图规划接入点

放在：

- `backend/app/services/post_process_service.py`

而不是新增独立 orchestrator 节点。

### 图片资源绑定接入点

如果后续要把真实图片插入草稿 HTML，优先放在：

- `post_process_service` 产出 HTML 前
- 或草稿落库前的 HTML 组装阶段

---

## 5. 当前真实接口与数据位置

## 5.1 `post_process_result` 是当前最核心的数据出口

当前真实输出结构来自：

- `backend/app/agents/post_process_agent.py`
- `backend/app/services/post_process_service.py`
- `backend/app/orchestrator/engine.py`

当前已稳定存在的字段：

```json
{
  "used_post_process": true,
  "layout_template": {},
  "template_options": [],
  "layout_blocks": [],
  "final_content_markdown": "...",
  "final_content_html": "...",
  "polishing_summary": "...",
  "layout_notes": [],
  "image_slots": [],
  "cover_image_prompt": "...",
  "wechat_publish_format": {}
}
```

这意味着：

- **图片规划数据最适合继续挂在 `post_process_result.image_slots` 里**
- **封面提示最适合继续挂在 `post_process_result.cover_image_prompt` 里**
- **最终带图 HTML 最适合继续挂在 `post_process_result.final_content_html` 里**

## 5.2 当前 `image_slots` 的真实含义

当前 `post_process_agent._build_image_slots()` 已经生成：

- `slot_id`
- `placement`
- `template_id`
- `purpose`
- `prompt`
- `source_hint`

当前更准确的理解应是：

**`image_slots` 现在是“图片规划槽位”，不是“已完成的图片资产列表”。**

示例形态：

```json
[
  {
    "slot_id": "cover",
    "placement": "cover",
    "template_id": "insight_column",
    "purpose": "建立文章打开前的第一视觉，风格要和正文模板一致。",
    "prompt": "Editorial WeChat cover image for: ...",
    "source_hint": ["source A", "source B"]
  },
  {
    "slot_id": "inline_1",
    "placement": "after_section_1",
    "template_id": "insight_column",
    "purpose": "在长段落之间制造停顿，同时强化本节核心判断。",
    "prompt": "Illustration for section '...' in article '...'",
    "source_hint": ["source A", "source B"]
  }
]
```

## 5.3 草稿与任务侧的数据落点

当前真实代码里：

1. `draft_service.get_draft_detail()` 会把 `task_result_data["post_process_result"]` 放进返回 payload。
2. `task_artifact_service` 已支持 artifact key:
   - `post_process_result`
3. `article_assembler_service` 会优先把 `post_process_result.final_content_markdown/html` 视为最终稿。

因此，V1 的推荐数据落点优先级应是：

1. `task.result_data.post_process_result`
2. 任务 artifact: `post_process_result`
3. `draft.content_html` / `draft.content_markdown`

## 5.4 草稿阶段的真实约束

如果本期范围只到草稿，那么当前最重要的真实约束只有一条：

**图片槽位规划本身不会自动改变草稿 HTML。**

也就是说，`image_slots` 只是规划结果；只有当后续流程明确把图片资产写入 `final_content_html`，或者同步回写到 `draft.content_html`，草稿详情页和后续流程才会看到真实图片。

---

## 6. 修订后的 V1 架构建议

## 6.1 不再新建独立 `figure_*_service` 作为第一步

原 spec 里的这些模块：

- `figure_policy_service`
- `cover_image_service`
- `evidence_figure_service`
- `explainer_figure_service`
- `article_layout_renderer`

在当前阶段不建议先以“并列 service + 新链路”形式落地。

更稳的做法是：

### 第一阶段

继续以 `post_process_service` 作为总入口。

### 第二阶段

如果逻辑变复杂，再在 `services/` 下拆 helper，但仍由 `post_process_service` 统一编排。

推荐拆法：

```text
backend/app/services/
  post_process_service.py              # 总入口，继续保留
  image_slot_planner.py                # 可选，负责扩展 image_slots
  image_asset_binding_service.py       # 可选，负责把已选图片注入草稿 HTML
  explainer_render_service.py          # 可选，负责程序化解释图
```

注意：

- 这些是**helper service**
- 不是 orchestrator 新节点
- 不要求第一版就全部落地

## 6.2 当前最小可行架构

V1 最小可行架构应是：

```text
post_process_service
  ├─ 选择排版模板
  ├─ 生成 final_content_html
  ├─ 生成 cover_image_prompt
  ├─ 生成 image_slots
  └─ 输出审核辅助信息（兼容保留 wechat_publish_format）

draft / task artifact
  └─ 保存 post_process_result
```

---

## 7. 修订后的数据结构设计

## 7.1 继续复用 `post_process_result`

不建议第一版引入新的顶级 `FigurePlan` / `FigureAsset` / `RenderedArticleAsset` 存储对象。

建议把能力收敛到：

```json
{
  "post_process_result": {
    "final_content_html": "...",
    "image_slots": [],
    "cover_image_prompt": "...",
    "wechat_publish_format": {}
  }
}
```

## 7.2 `image_slots` 修订版建议结构

在兼容当前代码的前提下，后续可扩展为：

```json
[
  {
    "slot_id": "cover",
    "placement": "cover",
    "template_id": "insight_column",
    "purpose": "建立文章打开前的第一视觉，风格要和正文模板一致。",
    "prompt": "Create a WeChat article cover for ...",
    "source_hint": ["Attention Is All You Need"],
    "status": "planned",
    "image_kind": "cover",
    "asset_origin": "manual | generated | extracted | none",
    "selected_asset_url": null,
    "selected_asset_path": null,
    "caption": null,
    "credit": null,
    "copyright_note": null
  }
]
```

这些新增字段的好处：

1. 和现有结构兼容，`engine._normalize_post_process_result()` 不需要变更 schema 就能透传 dict。
2. 可以明确区分：
   - 只是规划出来了
   - 已经选好了图
   - 已经注入 HTML
3. 后续接人工选择和自动补图都更顺。

## 7.3 `wechat_publish_format` 的角色

虽然当前 `post_process_result` 里仍然存在 `wechat_publish_format` 字段，但在本次“只到草稿”的 spec 范围内，它不是核心设计对象。

如果文档仍要保留它的说明，应该把它理解为历史兼容字段，而不是草稿配图 V1 的主承载结构。

建议保持其职责为：

- 是否 ready for review
- 推荐预览图槽位
- 审核前 checklist

不建议把图片资产详情都塞到这里。

---

## 8. 修订后的插图策略

## 8.1 封面图策略

当前阶段，封面图策略应分两层：

### 层 1：规划

由 `cover_image_prompt + image_slots[cover]` 表达。

### 层 2：资产绑定

由后续人工或自动流程把真实图片绑定到 `cover` 槽位，再注入草稿 HTML。

当前 V1 先承诺层 1，层 2 留作增强项。

## 8.2 正文图策略

正文图当前不应宣称“已自动获取”，而应宣称：

**系统可生成正文图槽位，并为后续人工/自动资产绑定提供位置与语义提示。**

推荐规则保持简单：

1. 总正文图槽位最多 3 个。
2. 优先按 H2/H3 提取 section。
3. 每个 section 最多一个槽位。
4. 没有 heading 时，从长段落中提取 1~3 个摘要片段作为槽位语义。

## 8.3 证据图与解释图的现实边界

在当前仓库语境下：

- “证据图”更适合定义成：**来源可追溯的图片资产**
- “解释图”更适合定义成：**程序化生成的结构化插图**

但两者目前都还没有完整落地链路。

因此 V1 文档表述应改成：

1. 可以先规划这两类槽位。
2. 可以记录推荐来源和用途。
3. 真正资产生成/提取属于下一阶段实现。

---

## 9. HTML 注入与草稿策略

## 9.1 当前真实约束

当前草稿链路里，`image_slots` 只是规划，不是渲染动作。

它不会自动：

- 根据 `image_slots` 生成图片
- 根据 `image_slots` 补 `<img>`
- 把已选图片同步写回草稿正文

因此：

**只有先把图片写进 `final_content_html`，并在草稿落库时同步进入 `draft.content_html`，草稿详情页和后续编辑链路才会真正看到图片。**

## 9.2 修订后的 V1 要求

V1 文档里对“带图 HTML”的承诺应收敛为：

### 已绑定图片资产时

- 系统应能输出带 `<img>` 的 HTML
- 草稿详情应能直接看到带图内容

### 未绑定图片资产时

- 系统输出纯文本增强版 HTML
- 同时输出图片槽位规划

这比“所有文章都输出带图 HTML”更符合当前真实能力。

---

## 10. 错误处理策略（按现状修订）

## 10.1 总原则

配图相关失败不能阻塞：

- 文章生成
- 草稿保存
- 审核查看

## 10.2 分阶段失败处理

### 阶段 A：图片规划失败

- `image_slots = []`
- `cover_image_prompt = ""`
- `post_process_result` 仍有效

### 阶段 B：图片资源绑定失败

- 保留槽位
- 不注入 `<img>`
- HTML 继续用无图版本

### 阶段 C：草稿 HTML 同步失败

- 记录草稿组装 warning / error
- 不影响无图草稿落库
- 由草稿详情或任务 artifact 展示当前仍处于“仅规划、未注图”状态

## 10.3 Fallback 矩阵

V1 的 fallback 顺序应保持简单，避免把配图失败扩散成草稿失败：

| 失败点 | 保留数据 | 草稿内容 | 用户可见状态 |
| --- | --- | --- | --- |
| 图片槽位规划失败 | `post_process_result` 仍保留，其余字段正常输出 | 使用无图 `final_content_html` | 草稿可审核，但无配图建议 |
| 图片资产绑定失败 | 保留 `image_slots`，槽位标记为未绑定 | 使用无图 `final_content_html` | 草稿可审核，显示“仅规划、未注图” |
| HTML 注图失败 | 保留已选资产信息和错误原因 | 回退到注图前 HTML | 草稿可审核，等待重新注图 |
| 草稿详情 schema 未暴露 `post_process_result` | 任务 artifact 仍可查看 | 草稿正文不受影响 | 前端可先通过 artifact 查看配图规划 |

fallback 的硬约束是：

- 不因为配图失败阻断草稿生成。
- 不把失败状态静默吞掉，至少在 `post_process_result` 或 task artifact 中留下可诊断信息。
- 不把“只有槽位规划”的状态伪装成“草稿已经带图”。

---

## 11. 存储与接口建议（修订后）

## 11.1 V1 不新增数据库表

当前最合理的存储策略仍是轻量版：

- `task.result_data.post_process_result`
- task artifact: `post_process_result`
- `draft.content_html`

如果后续真要保存已选图片资产，可先放：

```text
post_process_result.image_slots[*]
```

而不是先拆表。

但如果图片已经被用户选定并希望在草稿中真正可见，则还必须满足：

- 选图结果持久化到 `post_process_result.image_slots[*]`
- 同步把对应 `<img>` 注入 `final_content_html`
- 最终回写到 `draft.content_html`

## 11.2 对外接口建议

当前真实接口优先级：

1. 草稿详情：
   - `GET /drafts/{draft_id}`
2. 任务 artifact：
   - `post_process_result`

本次 spec 不讨论任何微信发布接口，也不把真实推送到微信纳入当前 V1 范围。

注意：

`DraftDetail` schema 当前未显式声明 `post_process_result`，如果后续前端要稳定读取配图规划，建议未来补上 schema；但这不属于本次文档修订范围。

---

## 12. 验收标准（按真实系统修订）

## 12.1 当前可验收项

V1 完成后，最低应满足：

1. `post_process_result` 中稳定输出：
   - `image_slots`
   - `cover_image_prompt`
   - `final_content_html`
2. `image_slots` 至少包含：
   - 1 个 `cover`
   - 0~3 个 `inline_*`
3. `final_content_html` 在没有图片资源时也可正常展示。
4. 若已经完成选图并进入“草稿可见”状态，则图片必须同步进入 `draft.content_html`，而不仅仅停留在 `post_process_result.image_slots[*]`。
5. 草稿详情或 task artifact 至少有一处能稳定查看配图规划结果。

## 12.2 不应写成当前验收项的内容

以下不应作为本阶段“必须验收”：

1. 自动论文抽图成功率
2. 自动解释图渲染成功率
3. 自动生图质量评分
4. 微信发布兼容
5. 前端图像选择工作台

---

## 13. 后续演进建议

## 13.1 V1.1

在不改 orchestrator 结构的前提下，可优先做：

1. 扩充 `image_slots` 字段，支持已选资产绑定。
2. 在 `post_process_service` 中支持把已选图片插入 `final_content_html`。
3. 补充 `DraftDetail` / artifact 的前端读取能力。

其中第 2 点不再是“可选增强”，而是草稿阶段想做到“已选图片真实可见”时的必要条件。

## 13.2 V1.5

继续增量：

1. 账号级封面风格模板
2. 手工上传/选择图片并绑定槽位
3. 基础 caption / credit 展示

## 13.3 V2

等 V1 跑顺后，再考虑：

1. 论文 PDF 抽图
2. 解释图程序化渲染
3. 自动选图 / 自动生图
4. 独立图片规划器

---

## 14. 一句话总结（修订版）

**HotClaw 当前的公众号配图 V1，不应定义为“新建一套图片系统”，而应定义为：在现有 `post_process -> draft` 链路上，为文章增加可持久化的图片槽位规划、封面提示，以及草稿阶段可承载图片内容的能力。**

这版定义更符合仓库现状，也更适合作为下一步开发依据。
