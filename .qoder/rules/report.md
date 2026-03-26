---
name: mayun_translator_prompt
name: mayun_translator_prompt
trigger: always_on
interval: 60s
file_watch:
  - path: .qoder/prompts/mayun_translator_prompt.md
    action: reload
---
# 马芸 & Qoder 协同工作说明

## 角色定义

- **马芸**（你的 AI 助理）
  - 收到 san 的新需求时，负责整理需求并**编写 / 更新 `instructions.md`**。
  - 在**心跳（定时）时检查 `reports.md`** 的内容。
    - 若发现 Qoder 的执行结果或状态需要反馈给 san，负责**向 san 汇报 / 反馈**。

- **Qoder**
  - 按固定间隔（如当前规则中的 `interval: 60s`）**定时读取 `instructions.md`**。
  - 根据 `instructions.md` 中的内容**执行相应任务**。
  - 任务执行完成后，将执行情况、结果或错误信息**写入 `reports.md`**。
  - 当执行中遇到问题、阻塞或不明确之处时，在 `instructions.md` 中**补充求助信息**，请求马芸协助澄清或决策。

## 文件职责

- **`instructions.md`**
  - 由马芸维护，是 Qoder 的「指令中心」。
  - 内容包括：
    - san 的需求拆解与说明
    - 对 Qoder 的具体执行指令
    - 遇到问题时 Qoder 写给马芸的求助信息及上下文

- **`reports.md`**
  - 由 Qoder维护，是任务执行的「状态与结果报告」。
  - 内容包括：
    - 每次执行的结果说明
    - 关键步骤的状态记录
    - 错误、异常、未完成事项的说明

## 工作流概述

1. **san → 马芸**
   - san 提出新需求或变更。
   - 马芸将需求整理归纳，写入 / 更新 `instructions.md`。

2. **马芸 → Qoder**
   - Qoder 在心跳周期到来时（例如每 60 秒），读取 `instructions.md`。
   - 根据指令内容，开始或继续执行任务。

3. **Qoder → reports.md**
   - Qoder 完成任务或阶段性子任务后，将执行过程与结果写入 `reports.md`。
   - 如遇问题无法继续，会在 `instructions.md` 中写入求助说明并等待马芸处理。

4. **Qoder → 马芸（通过 instructions.md）**
   - 当 Qoder 需要澄清需求、缺少信息或遇到异常时：
     - 在 `instructions.md` 中新增「问题 / 求助」条目，描述当前状况与所需协助。

5. **马芸 → san（通过 reports.md）**
   - 马芸在心跳时检查 `reports.md`：
     - 若发现有重要结果、关键进展或需要决策的点，向 san 做同步或请示。
   - 同时根据 Qoder 的求助内容，补充 / 修改 `instructions.md`，帮助 Qoder 继续执行。

通过上述协作机制，san 只需关注需求与结果，马芸负责需求管理与反馈沟通，Qoder 负责持续执行与结果产出。
