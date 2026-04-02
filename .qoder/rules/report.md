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

---

# 执行报告

## 2026-04-02 — HotClaw MVP P0 功能补齐（第一轮：页面）

### 任务说明
基于现有仓库做增量开发，补齐"仅输入账号定位"前提下的 P0 功能：结果页、历史任务页、设置页。

### 完成情况

| 模块 | 文件 | 状态 |
|------|------|------|
| 后端 rerun 接口 | `backend/app/api/task_routes.py` | ✅ 新增 POST /api/v1/tasks/{id}/rerun |
| 后端 rerun service | `backend/app/services/task_service.py` | ✅ 新增 rerun_task() 方法 |
| 列表响应增强 | `backend/app/schemas/task.py` | ✅ TaskSummary 增加 error_message + audit_result |
| 列表响应填充 | `backend/app/api/task_routes.py` | ✅ 填充新增字段 |
| 前端类型定义 | `frontend/types/index.ts` | ✅ 新增 TaskResultData, AuditResult, AuditIssue, AccountProfile 等 |
| 前端 API | `frontend/lib/api.ts` | ✅ 新增 rerunTask(), listTasks 支持 status 筛选 |
| 结果页 | `frontend/app/task/[id]/page.tsx` | ✅ 重写，新增结果总览 Tab、重跑按钮、审核结果展示 |
| 历史任务页 | `frontend/app/history/page.tsx` | ✅ 重写，新增状态筛选、审核标签、错误预览、重跑按钮 |
| 设置页入口 | `frontend/app/settings/page.tsx` | ✅ 新建，设置中心主页 |
| LLM 设置页 | `frontend/app/settings/llm-providers/page.tsx` | ✅ 更新 header，统一视觉风格 |
| 智能体设置页 | `frontend/app/settings/agents/page.tsx` | ✅ 更新 header，统一视觉风格 |
| 技能设置页 | `frontend/app/settings/skills/page.tsx` | ✅ 重写，统一视觉风格 |

### 验证结果
- 前端 TypeScript 检查：`tsc --noEmit` ✅ 通过
- 后端 Python 导入检查：`from app.api.task_routes import router` ✅ OK

### 下一轮待办
- 第二轮：实现首个可用 Skill（hot_topic_fetch_skill 或 content_postprocess_skill）
- 第三轮：补齐统一错误处理、前端错误展示和最小降级

---

## 2026-04-02 — Account 托管模式稳定性增强（第三轮）

### 任务说明
给"账号托管模式"补稳定性，实现：
1. 统一错误处理
2. Account 运行状态增强
3. Scheduler 防重复触发
4. 最小降级策略
5. 前端状态展示
6. 后端测试用例

### 完成情况

| 模块 | 文件 | 状态 |
|------|------|------|
| ORM 模型增强 | `backend/app/models/tables.py` | ✅ 新增 `last_run_status`, `last_error_message` 字段 |
| 错误码扩展 | `backend/app/core/exceptions.py` | ✅ 新增 Scheduler/Task 相关错误码 (7xxx, 8xxx) |
| Schema 增强 | `backend/app/schemas/account.py` | ✅ AccountSummary/AccountDetail 增加运行状态字段 |
| Service 增强 | `backend/app/services/account_service.py` | ✅ 完善错误处理、防重复逻辑、状态更新 |
| Scheduler 增强 | `backend/app/scheduler/account_scheduler.py` | ✅ 防重复触发、验收能力、日志完善 |
| API 增强 | `backend/app/api/account_routes.py` | ✅ 完善错误返回、409 冲突处理 |
| 前端类型 | `frontend/types/index.ts` | ✅ AccountSummary/AccountDetail 增加字段 |
| 账号列表页 | `frontend/app/accounts/page.tsx` | ✅ 增强状态展示、错误预览 |
| 账号详情页 | `frontend/app/accounts/[id]/page.tsx` | ✅ 增强运行状态、错误展示 |
| 后端测试 | `backend/tests/test_account_scheduler.py` | ✅ 新增 14 个测试用例 |

### 核心改进点

#### 1. 统一错误处理
- 新增错误码：
  - `7001`: SchedulerError
  - `7002`: SchedulerAccountSkipError
  - `7003`: SchedulerTaskCreateError
  - `8001`: TaskAlreadyExistsError
  - `8002`: TaskCreateError
- 所有 API 返回统一结构，错误有清晰 message

#### 2. Account 运行状态
- 新增字段：`last_run_status`, `last_error_message`
- 状态值：`never_run`, `running`, `success`, `failed`
- 成功/失败后更新状态
- 错误消息自动截断（最大 500 字符）

#### 3. Scheduler 验收能力
- `get_due_accounts` 过滤：is_active + auto_run_enabled + operation_mode + next_run_at
- 最终 eligibility 检查：`is_eligible_for_auto_run()`
- 跳过 manual/disabled 账号
- 跳过已有 running/pending task 的账号

#### 4. 防重复触发
- 创建任务前检查：`await _get_running_task()`
- 抛出 `TaskAlreadyExistsError`（409 Conflict）
- Semaphore 限制并发数（MAX_CONCURRENT_RUNS=3）

#### 5. 最小降级策略
- Scheduler tick 异常不崩溃服务
- 单个账号失败不影响其他账号
- 失败时更新 `last_run_status` 和 `last_error_message`
- `update_account_run_status()` 方法支持 success/failed/cancelled

### 验证结果
- 前端 TypeScript 检查：`tsc --noEmit` ✅ 通过
- 后端 Python 导入检查：全部 ✅ OK
- 测试文件语法检查：✅ OK

### 下一轮待办
- 人工重点验证：
  1. 创建 semi_auto 账号后，scheduler 扫描时能创建任务
  2. manual 账号不会被 scheduler 自动创建任务
  3. disabled 账号不会被 scheduler 自动创建任务
  4. 同一账号已有 running/pending task 时，scheduler 不重复创建任务
- 数据库 Migration 需要执行（添加新字段）
- 运行完整测试套件

---

## 2026-04-02 — 草稿箱功能（第四轮）

### 任务说明
实现"草稿箱"功能，支持 semi_auto 模式下的内容审核发布流程：
1. 自动生成内容进入 pending_review 状态
2. 草稿列表页和详情页
3. 手动确认发布
4. 废弃/拒绝/重跑功能
5. 发布状态记录
6. 账号详情页增加草稿入口

### 完成情况

| 模块 | 文件 | 状态 |
|------|------|------|
| ORM 模型扩展 | `backend/app/models/tables.py` | ✅ ArticleDraftModel 新增 draft_status, publish_status, source_type 等字段 |
| 错误码扩展 | `backend/app/core/exceptions.py` | ✅ 新增 Draft 相关错误码 (9xxx) |
| Draft Schema | `backend/app/schemas/draft.py` | ✅ 新建 DraftSummary, DraftDetail, DraftListResponse 等 |
| Draft Service | `backend/app/services/draft_service.py` | ✅ 新建 create_draft_from_task, confirm_publish, discard_draft, rerun_from_draft 等 |
| Draft API | `backend/app/api/draft_routes.py` | ✅ 新建 CRUD + 操作 API |
| Task Service 集成 | `backend/app/services/task_service.py` | ✅ 任务完成后自动创建草稿 |
| Publish Service | `backend/app/services/publish_service.py` | ✅ 新建发布服务（占位） |
| 前端类型 | `frontend/types/index.ts` | ✅ 新增 DraftStatus, DraftSummary, DraftDetail 等 |
| 前端 API | `frontend/lib/api.ts` | ✅ 新增 listDrafts, getDraft, confirmPublishDraft 等 |
| 草稿箱列表页 | `frontend/app/drafts/page.tsx` | ✅ 新建，支持筛选、分页、操作按钮 |
| 草稿详情页 | `frontend/app/drafts/[id]/page.tsx` | ✅ 新建，展示全文、审核结果、操作按钮 |
| 账号详情页增强 | `frontend/app/accounts/[id]/page.tsx` | ✅ 增加草稿箱入口 |
| 后端测试 | `backend/tests/test_draft.py` | ✅ 新建草稿功能测试用例 |

### 核心改进点

#### 1. 草稿状态机
- `draft` → `pending_review` → `approved` / `rejected` / `discarded` → `published`
- 状态转换严格校验，防止非法操作

#### 2. 自动草稿创建
- `semi_auto` 模式任务完成后自动创建 `pending_review` 状态草稿
- `manual` 模式任务完成后创建 `draft` 状态草稿
- 自动提取标题候选、选题摘要、正文内容

#### 3. 发布确认流程
- 待审核草稿可确认发布 → `approved` → `published`
- 支持废弃（discarded）和拒绝（rejected）
- 支持基于草稿重跑生成新内容

#### 4. 账号详情页草稿入口
- 显示当前账号运营模式说明
- 快捷入口：待确认草稿、查看全部草稿
- 支持 URL 参数筛选：`/drafts?account_id=xxx&draft_status=pending_review`

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/drafts | 草稿列表（支持分页、状态/账号筛选） |
| GET | /api/v1/drafts/{id} | 草稿详情 |
| POST | /api/v1/drafts/{id}/confirm-publish | 确认发布 |
| POST | /api/v1/drafts/{id}/discard | 废弃草稿 |
| POST | /api/v1/drafts/{id}/reject | 拒绝草稿 |
| POST | /api/v1/drafts/{id}/rerun | 从草稿重跑 |

### 验证结果
- 前端 TypeScript 检查：`tsc --noEmit` ✅ 通过
- 后端 Python 导入检查：全部 ✅ OK
- 测试文件语法检查：✅ OK

### 下一轮待办
- 数据库 Migration 需要执行（添加 article_drafts 新字段）
- 人工验证完整流程：创建 semi_auto 账号 → 定时触发 → 生成草稿 → 审核发布
- 完善 Publish Service（当前为占位实现）
- 端到端测试

---

## 2026-04-02 — Account 模块全栈实现（第二轮）

### 任务说明
实现公众号账号管理模块，包括后端 ORM/Service/API、前端类型/API/页面、编排层集成、定时调度器。

### 完成情况

| 模块 | 文件 | 状态 |
|------|------|------|
| ORM 模型 | `backend/app/models/tables.py` | ✅ AccountModel 已存在 |
| Schema | `backend/app/schemas/account.py` | ✅ 已存在（AccountCreateRequest, AccountSummary, AccountDetail 等） |
| Service | `backend/app/services/account_service.py` | ✅ 已存在（CRUD + run_account + get_due_accounts） |
| API 路由 | `backend/app/api/account_routes.py` | ✅ 新增（CRUD + run + enable/disable） |
| API 注册 | `backend/app/main.py` | ✅ 已添加 account_router |
| Orchestrator 集成 | `backend/app/orchestrator/engine.py` | ✅ 新增 account_context 注入逻辑 |
| Scheduler | `backend/app/scheduler/account_scheduler.py` | ✅ 新增定时调度器 |
| Scheduler 启动 | `backend/app/main.py` | ✅ lifespan 中启动/停止 scheduler |
| 前端类型 | `frontend/types/index.ts` | ✅ 新增 AccountSummary, AccountDetail, AccountCreateRequest 等 |
| 前端 API | `frontend/lib/api.ts` | ✅ 新增 createAccount, listAccounts, getAccount 等 |
| 账号列表页 | `frontend/app/accounts/page.tsx` | ✅ 新建（分页、状态标签、运行按钮） |
| 新建账号页 | `frontend/app/accounts/new/page.tsx` | ✅ 新建（完整表单） |
| 账号详情页 | `frontend/app/accounts/[id]/page.tsx` | ✅ 新建（信息展示 + 快速操作） |
| 编辑账号页 | `frontend/app/accounts/[id]/edit/page.tsx` | ✅ 新建（编辑表单） |

### 验证结果
- 前端 TypeScript 检查：`tsc --noEmit` ✅ 通过
- 后端 Python 导入检查：`from app.api.account_routes import router` ✅ OK

### 下一轮待办
- 测试 Account CRUD API
- 测试 Scheduler 定时执行
- 完善 Account Memory Service（如需历史记录分析）

---

## 2026-03-26

| 任务 | 状态 | 说明 |
|------|------|------|
| D盘创建 aaa.txt | ✅ 完成 | 测试文件已创建 |

## 完成情况

- LLM API 配置功能 ✅
- MySQL 数据库配置 ✅
- 前端设置页面 ✅
- D盘测试文件 ✅
- GitHub 推送 ⏳ 待网络恢复
