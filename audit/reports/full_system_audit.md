# HotClaw Full System Audit

生成时间: 2026-04-11 18:00 (Asia/Shanghai)

## 1. 本次审计范围

本次审计覆盖了以下范围，并坚持以“实际运行结果”为准，不以 README 或静态直觉替代验证：

- 后端 API
- 前端控制台页面
- 任务编排与节点链路
- draft 状态机
- 发布链路
- scheduler 异步扫描链路
- 现有 pytest
- 现有 Playwright E2E
- fake / mock / stub / fallback / test mode 盘点
- 数据库 schema / 运行环境 / 路径风险

本次审计没有做大规模重构，只做了少量会阻塞审计的最小修复与审计辅助脚本。

## 2. 实际运行环境

| 项目 | 实际值 | 证据 |
| --- | --- | --- |
| 工作目录 | `D:\project\hotclaw` | 本次执行环境 |
| Python | `3.12.7` | 已实际执行 `python --version` |
| Node.js | `v22.18.0` | 已实际执行 `node --version` |
| npm | `10.9.3` | 已实际执行 `npm --version` |
| 默认后端 DB 配置 | `sqlite+aiosqlite:///./hotclaw.db` | `backend/.env`, `backend/app/core/config.py` |
| API 审计实际 DB | `D:\project\hotclaw\backend\hotclaw.db` | `audit/artifacts/api/backend-api-audit-summary.json` |
| Playwright E2E DB | `sqlite+aiosqlite:///./hotclaw.e2e.db` | `playwright.config.ts` |
| Playwright 前端端口 | `3107` | `playwright.config.ts`, `audit/logs/page-smoke.log` |
| Playwright 后端端口 | `8107` | `playwright.config.ts`, `audit/logs/page-smoke.log` |
| API 审计临时端口 | `8145` / `8146` / `8147` | API artifact URL 与对应后端日志 |

### 运行环境观察

- `alembic upgrade head` 实际执行成功，schema 初始化可跑通。
- 前端 `next build` 实际执行成功，但日志提示仓库根目录与 `frontend/` 下存在双 `package-lock.json`，根目录推断可能影响 Turbopack root 判定。
- 默认数据库使用相对路径，前后端 / Playwright / API audit 的工作目录不同时，存在连接到不同 SQLite 文件的现实风险。

## 3. 代码扫描后的功能地图

### 后端主要路由

| 模块 | 主要入口 |
| --- | --- |
| 健康检查 | `/api/v1/health` |
| Accounts | `/api/v1/accounts`，含创建、列表、详情、PATCH、`/{id}/run`、enable、disable |
| Tasks | `/api/v1/tasks`，含创建、列表、详情、状态、节点、rerun、SSE stream |
| Drafts | `/api/v1/drafts`，含列表、详情、pending-count、confirm、discard、reject、rerun、publish-to-wechat、wechat-status、publish-records、retry-publish |
| WeChat Config / Publish Record | `/api/v1/accounts/{account_id}/wechat-config`、`/api/v1/wechat/config`、`/api/v1/publish-records/{id}`、`/api/v1/wechat/publish-records/{id}/refresh-status` |
| Automation Plan | `/api/v1/accounts/{account_id}/automation-plan` |
| Reference Sources | `/api/v1/accounts/{account_id}/reference-sources` |
| Agents / Skills / Providers | `/api/v1/agents`、`/api/v1/skills`、`/api/v1/llm-providers` |
| System Config | `/system-configs` |
| Account Onboarding | `/api/v1/account-onboarding/analyze-existing` |

### 前端主要页面

| 页面 | 路由 |
| --- | --- |
| Dashboard | `/dashboard` |
| Accounts 列表 | `/accounts` |
| Account 详情 | `/accounts/[id]` |
| Account Workspace | `/accounts/[id]/workspace` |
| Account Automation | `/accounts/[id]/automation` |
| Account Memory | `/accounts/[id]/memory` |
| Account Reference Sources | `/accounts/[id]/reference-sources` |
| Account Style Profile | `/accounts/[id]/style-profile` |
| Task Detail | `/task/[id]` |
| Task History | `/tasks/history` |
| Drafts 列表 | `/drafts` |
| Draft Detail | `/drafts/[id]` |
| Publish Logs | `/publish-logs` |
| Legacy Publish Records Redirect | `/publish-records` |
| Settings | `/settings` |
| WeChat Settings | `/settings/wechat`、`/settings/wechat/[id]` |
| LLM Providers / Agents / Skills | `/settings/llm-providers`、`/settings/agents`、`/settings/skills` |

### 核心服务 / 链路

| 领域 | 主要实现 |
| --- | --- |
| 任务执行 | `backend/app/services/task_service.py` |
| draft 生命周期 | `backend/app/services/draft_service.py` |
| WeChat 发布 | `backend/app/services/wechat_publish_service.py` |
| 发布记录 | `backend/app/services/publish_record_service.py` |
| 调度器 | `backend/app/scheduler/account_scheduler.py` |
| 编排引擎 | `backend/app/orchestrator/engine.py` |
| E2E fake mode | `backend/app/services/e2e_test_mode_service.py` |
| Account run 策略 / 降级 | `backend/app/services/account_harness_service.py` |

### 已存在测试类型

| 类型 | 位置 | 说明 |
| --- | --- | --- |
| pytest 单测 / API / 集成 | `backend/tests` | 主体测试集 |
| pytest E2E | `backend/tests/e2e` | 调度、draft、链路类测试，广泛使用 mock fixture |
| Playwright E2E | `tests/e2e` | 前端金线与失败路径 |
| 审计脚本 | `audit/scripts/run_backend_api_audit.py` | 本次新增，做 API 级运行审计 |
| 审计 Playwright 冒烟 | `tests/e2e/page-smoke.audit.spec.ts` | 本次新增，做页面级打开性与选择器审计 |

## 4. 实际执行的命令清单

以下命令已实际执行。未列出的结论不视为已验证。

```powershell
python --version
node --version
npm --version

# backend / schema / collect
backend\.venv\Scripts\python.exe -c "import app.main"
backend\.venv\Scripts\python.exe -m pytest --collect-only
backend\.venv\Scripts\python.exe -m alembic upgrade head

# frontend static / build
cd frontend
npm run lint
npx playwright test --list
npm run build

# full test runs
cd backend
backend\.venv\Scripts\python.exe -m pytest

cd D:\project\hotclaw
backend\.venv\Scripts\python.exe audit\scripts\run_backend_api_audit.py
npm run test:e2e -- --reporter=list
npm run test:e2e -- tests/e2e/draft.spec.ts --reporter=list
npm run test:e2e -- tests/e2e/page-smoke.audit.spec.ts --reporter=list
```

## 5. 实际跑过的测试清单

| 测试 / 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| Backend import / startup import check | 通过 | `audit/logs/backend-import-check.log` |
| Pytest collect | 通过，收集到 `268` 个测试 | `audit/logs/pytest-collect.log` |
| Frontend type check (`npm run lint`) | 通过 | `audit/logs/frontend-lint.log` |
| Playwright test discovery | 通过，发现 `5` 个原有 E2E | `audit/logs/playwright-list.log` |
| Alembic upgrade | 通过 | `audit/logs/alembic-upgrade.log` |
| Frontend build | 通过，伴随 lockfile warning | `audit/logs/frontend-build-escalated.log` |
| 全量 pytest | `255 passed / 13 failed / 6 warnings` | `audit/logs/pytest-all.log` |
| 后端 API 审计 fake-flow | 完成 | `audit/artifacts/api/fake-flow/summary.json` |
| 后端 API 审计 real-flow | 失败，任务轮询超时 | `audit/artifacts/api/real-flow/summary.json`, `audit/logs/real-flow-backend.err.log` |
| 后端 API 审计 scheduler-fake | 完成 | `audit/artifacts/api/scheduler-fake/summary.json` |
| 原有 Playwright E2E 全量 | `4 passed / 1 failed` | `audit/logs/playwright-e2e-escalated.log` |
| Playwright draft 失败用例单独复跑 | 仍失败 | `audit/logs/playwright-draft-only.log` |
| 审计专用页面冒烟 | `1 passed` | `audit/logs/page-smoke.log`, `audit/artifacts/page-smoke-summary.json` |

## 6. 功能测试总表

分类规则:

- `真实验证通过`: 真实运行了后端 / 前端 / DB / 网络链路，且该结论不依赖 fake/mock 返回业务结果。
- `仅模拟验证通过`: 运行是真跑的，但核心业务结果依赖 fake/mock/test mode。
- `未验证 / 失败 / 阻塞`: 没跑通，或只看到了代码存在。

| 功能域 | 入口 | 验证方式 | 当前结论 | 真实 / 模拟 | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| health | `/api/v1/health` | API 审计 | 通过 | 真实验证通过 | `audit/artifacts/api/fake-flow/01-health.json` | 基础健康检查可用 |
| 账号 CRUD | `/api/v1/accounts` | API 审计 + 页面冒烟 | 通过 | 真实验证通过 | `audit/artifacts/api/fake-flow/02-list-accounts.json`, `08-fake-flow-create-account.json`, `09-account-detail.json`, `audit/artifacts/page-smoke-summary.json` | 创建、列表、详情均实跑通过 |
| account workspace | `/accounts/[id]/workspace` | Playwright 页面冒烟 | 通过 | 仅模拟验证通过 | `audit/artifacts/page-smoke-summary.json`, `audit/screenshots/page-smoke-account-workspace.png` | 页面打开、Run 按钮、task/draft 行可见；内容来自 fake generation |
| run task | `/api/v1/accounts/{id}/run` | API 审计 fake-flow / real-flow | fake 通过；real 卡死 | fake 通过，real 阻塞 | `audit/artifacts/api/fake-flow/10-run-account.json`, `audit/artifacts/api/real-flow/03-run-account.json`, `243-real-flow-task-detail-task_rMO46EdTZh19.json` | 真实 LLM 链路未完成 |
| task detail / polling | `/api/v1/tasks/{id}`、`/task/[id]` | API 审计 + Playwright 页面冒烟 | fake 通过；real 失败 | fake 通过，real 阻塞 | `audit/artifacts/api/fake-flow/12-fake-flow-task-detail-task_SoBGPl0UTOKY.json`, `audit/artifacts/page-smoke-summary.json`, `audit/artifacts/api/real-flow/243-real-flow-task-detail-task_rMO46EdTZh19.json` | real-flow 最终仍 `pending` |
| draft list / draft detail | `/api/v1/drafts`、`/drafts/[id]` | API 审计 + Playwright 页面冒烟 | 通过 | 仅模拟验证通过 | `audit/artifacts/api/fake-flow/15-draft-list.json`, `16-draft-detail.json`, `audit/artifacts/page-smoke-summary.json` | draft 内容来自 fake generation |
| confirm publish API | `/api/v1/drafts/{id}/confirm-publish` | API 审计 | 通过 | 仅模拟验证通过 | `audit/artifacts/api/fake-flow/18-confirm-publish.json` | 首次确认通过 |
| confirm publish 重复提交防护 | 同上 | API 审计 | 通过 | 真实验证通过 | `audit/artifacts/api/fake-flow/19-confirm-publish-duplicate.json` | 返回 `400` / `code=9002`，错误可见 |
| confirm publish UI 行为 | `/drafts/[id]` | 原有 Playwright draft.spec | 失败 | 未验证 / 失败 / 阻塞 | `audit/logs/playwright-draft-only.log`, `test-results/draft-draft-confirm-succes-99914-d-prevents-duplicate-submit-chromium/trace.zip` | UI 金线未跑通 |
| publish to wechat fake success | `/api/v1/drafts/{id}/publish-to-wechat` | 页面冒烟 + 原有 Playwright publish.spec | 通过 | 仅模拟验证通过 | `audit/artifacts/page-smoke-summary.json`, `audit/logs/playwright-e2e-escalated.log` | 返回 fake media/publish id，published writeback 成功 |
| publish to wechat fake failure | 同上 | API 审计 + 原有 Playwright failure.spec | 通过 | 仅模拟验证通过 | `audit/artifacts/api/fake-flow/24-publish-fake-failure.json`, `audit/logs/playwright-e2e-escalated.log` | 失败状态与错误信息可见 |
| WeChat config test | `/api/v1/accounts/{id}/wechat-config/test` | API 审计 | 失败但有真实外部回包 | 真实验证通过（失败路径） | `audit/artifacts/api/fake-flow/23-wechat-config-test.json`, `audit/logs/fake-flow-backend.err.log` | 实际打到了 WeChat，返回 `invalid appid` |
| publish record 写回 | `/api/v1/drafts/{id}/publish-records`、`/publish-logs` | fake-flow + 页面冒烟 | 通过 | 仅模拟验证通过 | `audit/artifacts/api/fake-flow/25-publish-records-after-failure.json`, `audit/artifacts/page-smoke-summary.json` | fake success / fake failure 均有记录写回 |
| sync publish status | `/api/v1/wechat/publish-records/{id}/refresh-status` | 仅代码存在 + 原有页面可打开 | 未完成实证 | 未验证 / 失败 / 阻塞 | `audit/logs/playwright-e2e-escalated.log` | 本次未拿到真实可轮询的微信 publish_id |
| retry publish | `/api/v1/drafts/{id}/retry-publish` | API 审计 | 失败 | 未验证 / 失败 / 阻塞 | `audit/artifacts/api/fake-flow/27-retry-publish-fake-success.json`, `audit/logs/fake-flow-backend.err.log` | fake_success 下仍因 `MultipleResultsFound` 失败 |
| scheduler 启动 | runtime startup | API 审计 + page-smoke webserver logs | 通过 | 真实验证通过 | `audit/logs/scheduler-fake-backend.err.log`, `audit/logs/page-smoke.log` | scheduler loop 确实启动 |
| scheduler 扫描 due account | 调度器 runtime | scheduler-fake API 审计 | 通过 | 真实 runtime + 模拟内容 | `audit/artifacts/api/scheduler-fake/summary.json` | 扫描、建 task、生成 draft 均发生；内容为 fake generation |
| e2e test mode | env + system-configs | API 审计 + Playwright | 通过 | 仅模拟验证通过 | `playwright.config.ts`, `audit/artifacts/api/fake-flow/04-07*.json`, `audit/logs/page-smoke.log` | 运行时可控 fake generation/publish 已实证 |
| 数据库初始化 / schema | Alembic + runtime startup | 实际执行 | 通过，但有路径风险 | 真实验证通过 | `audit/logs/alembic-upgrade.log`, `audit/artifacts/api/backend-api-audit-summary.json` | schema 初始化可跑通，DB 路径仍有漂移风险 |
| 前端构建 | `npm run build` | 实际执行 | 通过 | 真实验证通过 | `audit/logs/frontend-build-escalated.log` | build 通过 |
| 前端基础页面可打开性 | dashboard/accounts/task/drafts/publish/settings | 审计页面冒烟 | 通过 | 真实页面打开 + 部分 fake 数据 | `audit/artifacts/page-smoke-summary.json`, `audit/screenshots/*.png` | 11 个核心页面/路由实开通过 |

## 7. 自动化测试结果总表

### pytest

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| collected | `268` | `audit/logs/pytest-collect.log` |
| passed | `255` | `audit/logs/pytest-all.log` |
| failed | `13` | `audit/logs/pytest-all.log` |
| warnings | `6` | `audit/logs/pytest-all.log` |

### Playwright 原有 E2E

| 用例 | 结果 | 证据 |
| --- | --- | --- |
| `tests/e2e/generation.spec.ts` | 通过 | `audit/logs/playwright-e2e-escalated.log` |
| `tests/e2e/publish.spec.ts` | 通过 | `audit/logs/playwright-e2e-escalated.log` |
| `tests/e2e/failure.spec.ts` | 通过 | `audit/logs/playwright-e2e-escalated.log` |
| `tests/e2e/draft.spec.ts` | 失败 | `audit/logs/playwright-e2e-escalated.log`, `audit/logs/playwright-draft-only.log` |

### 审计新增自动化

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| API full audit script | 完成 3 个场景，其中 2 完成、1 失败 | `audit/artifacts/api/backend-api-audit-summary.json` |
| 页面冒烟 Playwright | `1 passed` | `audit/logs/page-smoke.log`, `audit/artifacts/page-smoke-summary.json` |

## 8. 失败项明细

### 8.1 运行时真实链路失败 / 阻塞

| 严重级别 | 失败项 | 失败现象 | 复现 / 证据 | 初步归因 |
| --- | --- | --- | --- | --- |
| P0 | real-flow 真实生成链路阻塞 | task 轮询超时，最终 artifact 里 `status=pending`，没有 draft、没有 result_data | `audit/artifacts/api/real-flow/summary.json`, `audit/artifacts/api/real-flow/243-real-flow-task-detail-task_rMO46EdTZh19.json`, `audit/logs/real-flow-backend.err.log` | 真实 LLM 链路能进入 orchestrator，但多次停在 `LiteLLM completion() model= deepseek-chat; provider = dashscope`，未完成、未失败、未超时落库 |
| P0 | retry publish 在 fake_success 下仍失败 | `/retry-publish` 返回 `code=9004`，消息含 `Multiple rows were found when one or none was required` | `audit/artifacts/api/fake-flow/27-retry-publish-fake-success.json`, `audit/logs/fake-flow-backend.err.log` | publish record / draft 状态查询对多条记录处理不正确，导致 retry 路径不可用 |
| P1 | confirm publish UI 金线失败 | Playwright draft 用例单独复跑仍失败，附件 trace / screenshot 已落盘 | `audit/logs/playwright-draft-only.log`, `test-results/draft-draft-confirm-succes-99914-d-prevents-duplicate-submit-chromium/test-failed-1.png`, `.../trace.zip` | API 层 confirm 可跑通，但 UI 金线对“确认后状态是否立即变成 approved”不稳定，存在前后端一致性或竞态问题 |
| P1 | WeChat 真链路仅验证到配置测试失败 | `wechat-config/test` 真实打到 WeChat 并返回 `40013 invalid appid` | `audit/artifacts/api/fake-flow/23-wechat-config-test.json`, `audit/logs/fake-flow-backend.err.log` | 证明真实外部网络可达，但当前配置不具备真实发布前提 |

### 8.2 pytest 失败项逐项归因

| 严重级别 | 失败测试 | 失败现象 | 初步归因 | 证据 |
| --- | --- | --- | --- | --- |
| P1 | `tests/e2e/test_draft_workflow.py::TestManualAccountIsolation::test_manual_account_run_manually` | manual account 手动运行测试失败 | manual / semi_auto / full_auto 语义与测试预期存在漂移 | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestSemiAutoSchedulerTrigger::test_semi_auto_task_created_with_correct_account_id` | semi_auto 调度任务测试失败 | 调度后的 account/task 状态与预期不一致，且日志里出现 `account_run_status_updated ... status=failed` | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestFullAutoSchedulerTrigger::test_full_auto_triggers_and_auto_publishes` | 期望 `approved`，实际 `pending_review` | full_auto 自动审批/自动发布语义与代码行为不一致 | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestTaskFailureStateSync::test_llm_failure_triggers_fallback` | fallback 状态同步测试失败 | 调度失败/降级后的状态同步合同不稳定 | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestTaskFailureStateSync::test_task_failure_syncs_account_status` | task failure 状态同步失败 | 同上 | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestTaskFailureStateSync::test_mixed_failure_and_success` | mixed 成功/失败场景失败 | 同上 | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestMultiAccountScanning::test_only_eligible_accounts_triggered` | eligible account 扫描结果不符合预期 | scheduler eligibility / mode contract 漂移 | `audit/logs/pytest-all.log` |
| P1 | `tests/e2e/test_scheduler_e2e.py::TestMultiAccountScanning::test_batch_status_updates` | batch status update 失败 | scheduler 状态更新合同不稳定 | `audit/logs/pytest-all.log` |
| P1 | `tests/test_account_scheduler.py::TestAccountServiceRun::test_manual_account_cannot_be_auto_run` | manual account 本应拒绝 auto-run，但测试未得到预期异常 | `account_service.run_account` 当前允许 manual 账户在某些调用上下文触发 | `audit/logs/pytest-all.log` |
| P1 | `tests/test_account_scheduler.py::TestNextRunAtRefresh::test_refresh_next_run_updates_timestamp` | `TypeError: can't compare offset-naive and offset-aware datetimes` | `next_run_at` 时区处理不一致 | `audit/logs/pytest-all.log` |
| P2 | `tests/test_agent_api.py::test_list_agents_success` | 期望 6 个 agent，实际返回 12 个 | agent 注册数量已扩展，但测试未更新 | `audit/logs/pytest-all.log` |
| P2 | `tests/test_agent_contract.py::TestHotTopicAgentSkillIntegration::test_agent_input_schema_includes_profile` | `profile.description` 缺失 | schema 合同未补齐描述字段 | `audit/logs/pytest-all.log` |
| P2 | `tests/test_llm_provider.py::TestLLMGateway::test_is_provider_available` | provider availability 断言失败 | provider 初始化逻辑或测试预期已变化 | `audit/logs/pytest-all.log` |

## 9. 模拟链路总表

本表专门回答“哪些通过，其实不是在真实业务链路里通过的”。

| 名称 | 所在文件 | 触发方式 | 模拟对象 | 默认开启 | 影响哪些测试 / 审计 | 是否影响生产路径 |
| --- | --- | --- | --- | --- | --- | --- |
| E2E fake generation | `backend/app/services/e2e_test_mode_service.py`, `backend/app/services/task_service.py` | `HOTCLAW_E2E_TEST_MODE=1` + system config `e2e_generation_mode=fake_success/fake_failure` | 绕过真实 orchestrator 结果，直接返回固定 draft 或固定失败 | 否 | Playwright generation/publish/failure/draft/page-smoke，API fake-flow，scheduler-fake | 仅在 E2E mode 开启时生效 |
| E2E fake publish | `backend/app/services/e2e_test_mode_service.py`, `backend/app/services/wechat_publish_service.py` | `HOTCLAW_E2E_TEST_MODE=1` + system config `e2e_publish_mode=fake_success/fake_failure` | 伪造 media_id / publish_id / article_url，或固定 publish 失败 | 否 | Playwright publish/failure/page-smoke，API fake-flow | 仅在 E2E mode 开启时生效 |
| pytest mock LLM fixture | `backend/tests/e2e/conftest.py`, `backend/tests/e2e/mock_llm.py` | `patch("litellm.acompletion", ...)` | 所有 agent 的 LLM 返回 | 否 | 多数 pytest e2e 调度 / draft 流程 | 仅测试 |
| fake publish fixture | `backend/tests/e2e/test_scheduler_e2e.py` | test fixture / context manager | 发布成功 / 失败结果 | 否 | scheduler e2e pytest | 仅测试 |
| unit monkeypatch / AsyncMock | `backend/tests/*.py` 多处 | patch / monkeypatch / AsyncMock | provider、orchestrator、publish、HTTP 等 | 否 | 单测 / 合同测试 | 仅测试 |
| agent fallback | `backend/app/agents/*.py`, `backend/app/orchestrator/engine.py` | agent 报错或超时 | 以降级内容代替真实 agent 输出 | 否 | 真实 runtime 与 pytest 都会触发 | 是，属于生产降级路径 |
| legacy structured-content fallback | `backend/app/orchestrator/engine.py` | structured pipeline 任一关键节点失败 / 超时 | 回退到 `content_writer_agent` 生成 legacy content | 否 | 结构化内容相关运行与测试 | 是，属于生产降级路径 |
| account ops fallback | `backend/app/services/account_harness_service.py` | ops agent 失败 | 回退为保守的 run strategy / ops context | 否 | 实际 real-flow artifact 中已出现 `fallback_used=true` | 是，属于生产降级路径 |
| legacy automation-plan fallback | `backend/app/services/automation_plan_service.py`, 前端 `legacy_fallback` 展示 | 没有专门 automation_plan 记录时 | 从 account 字段合成 legacy 计划摘要 | 是，只要 plan 缺失就会出现 | account automation 页面与数据展示 | 是 |
| frontend pending-count fallback | `frontend/lib/api/index.ts` | `/drafts/pending-count` 返回 422 | 改用 `listDrafts(...pending_review)` 计算数量 | 否，发生 422 时触发 | dashboard 页面 | 是，属于前端容错路径 |
| simulated publish placeholder | `backend/app/services/publish_service.py` | 若直接调用该旧服务 | 永远返回 `success=True` 且 `simulated=true` | 不是当前主链路默认 | 本次审计主链未使用到 | 是，保留在代码中有误导风险 |

### 模拟链路总结

- 本次所有“生成成功、draft 产出、发布成功、发布记录写回”的前端 E2E 通过，核心上都依赖了 E2E fake generation 或 E2E fake publish。
- pytest 中多数 scheduler / draft / workflow 测试依赖 mock LLM、fake publish fixture 或 monkeypatch，不是完整真实链路。
- 真实 runtime 中确实存在 fallback 路径，不属于测试专用 fake，但这意味着“任务成功”不一定等于“真实 agent 全链路成功”。

## 10. 风险清单

| 风险 | 当前状态 | 证据 |
| --- | --- | --- |
| 真实 LLM 链路不可依赖 | 高风险 | `audit/artifacts/api/real-flow/summary.json`, `audit/logs/real-flow-backend.err.log` |
| retry publish 不可用 | 高风险 | `audit/artifacts/api/fake-flow/27-retry-publish-fake-success.json` |
| real WeChat 发布未完整验证 | 高风险 | 仅验证到 config test 真实失败，未有真实 publish 成功证据 |
| scheduler 行为与测试合同漂移 | 高风险 | `audit/logs/pytest-all.log` 中 8 个 scheduler / mode 相关失败 |
| `next_run_at` 时区处理不一致 | 中风险 | `audit/logs/pytest-all.log` |
| 相对路径数据库错连风险 | 中风险 | `backend/.env`, `backend/app/core/config.py`, `playwright.config.ts`, `audit/artifacts/api/backend-api-audit-summary.json` |
| lockfile / workspace root 推断不稳定 | 中风险 | `audit/logs/frontend-build-escalated.log` |
| 仓库中存在真实 provider / app 凭据文件 | 中风险 | `backend/.env` 实际存在，应做密钥治理；本报告不展示具体值 |
| `publish_service.py` 旧模拟服务仍存在 | 中风险 | `backend/app/services/publish_service.py` |

## 11. 修复优先级建议

### P0

1. 修 real generation 卡死问题。
   目标: 真实 task 不能长期停在 `pending/running` 而无结果、无失败、无超时落库。
   先做法: 给 LiteLLM 调用与 orchestrator node 增加硬超时、错误写回、trace_id 级日志。

2. 修 retry publish / wechat status 的多记录查询错误。
   目标: `retry-publish`、`wechat-status` 在存在多条 publish record 时仍能 deterministically 取最新记录。

### P1

1. 对齐 manual / semi_auto / full_auto 的运行合同。
   目标: 让 `account_service.run_account`、scheduler、draft 初始状态、auto publish 行为一致，并恢复相关 pytest。

2. 修 draft confirm 的前后端一致性问题。
   目标: UI 点击确认后，API 查询与页面 badge 都稳定变为 `approved`，消除当前 Playwright 金线失败。

3. 统一 `next_run_at` 时区。
   目标: 所有写入与比较都使用 offset-aware datetime。

4. 补 publish sync 的真实链路验证。
   目标: 拿一个有效微信测试账号，至少打通一次真实 submit + refresh-status。

### P2

1. 更新 agent API / contract / provider availability 测试预期。
   目标: 修复已经落后的测试合同。

2. 处理 DB 相对路径漂移。
   目标: 统一 dev / e2e / audit 的数据库路径策略，避免根目录与 backend 目录各自产生 SQLite 文件。

3. 清理遗留模拟入口与脚本脆弱点。
   目标: 明确废弃 `publish_service.py` 或避免误用，同时修稳 `start-local.ps1`。

## 12. 审计过程中做过的最小修复

| 文件 | 修改内容 | 目的 |
| --- | --- | --- |
| `backend/app/core/config.py` | 规范化 `.env` 预加载值，去除已有环境变量尾部空白 | 修复 `APP_DEBUG=true ` 这类值导致的运行解析问题，保证后端能稳定起服务 |
| `scripts/start-local.ps1` | 调整命令输出捕获方式 | 改善启动脚本出错时的观测性，但该脚本仍不算稳定 |
| `audit/scripts/run_backend_api_audit.py` | 新增 | API 级全链路审计与证据归档 |
| `tests/e2e/page-smoke.audit.spec.ts` | 新增 | 页面级打开性 / data-testid / 核心区域冒烟 |

## 13. 结论

### 真实可用且已被实证的部分

- 后端基础 API 可启动，health 可用。
- 账号创建、列表、详情这些基础 CRUD 可跑通。
- schema 初始化与前端生产构建可跑通。
- 核心前端页面路由可打开，不会直接 500，且关键按钮 / `data-testid` 在页面冒烟中可见。
- scheduler 确实会启动，也确实会扫描 due account 并创建任务。
- WeChat config test 真实打到了外部接口，失败信息可见。

### 只在模拟模式下跑通的部分

- 账号 -> 生成 -> draft -> confirm -> publish -> publish record writeback 这条金线，在 fake generation / fake publish 下可以跑通。
- 现有前端 Playwright 大部分通过，核心依赖 `HOTCLAW_E2E_TEST_MODE=1`。
- 页面级 publish logs 展示成功记录，也是基于 fake publish 数据。

### 当前未被证明可靠，或已明确失败的部分

- 真实 LLM 生成链路没有被证明能完成；本次实跑结果是卡住。
- retry publish 明确失败。
- draft confirm 的 UI 金线明确失败。
- scheduler / account mode 相关行为与现有 pytest 合同明显漂移。
- 真实 WeChat 发布与真实 publish status refresh 仍未完成实证。

### 对项目当前状态的判断

项目当前**适合继续开发**，但前提是团队明确接受下面这个现实：

- HotClaw 现在有一条“比较可靠的 fake 集成开发通道”。
- HotClaw 还没有一条“被本次审计证明稳定的真实生成 + 真实发布通道”。

如果目标是继续做产品开发、前端联调、可观测性完善、补测试，这个状态可以继续推进。
如果目标是宣称“真实业务链路已可用”或直接进入发布 / 试运营，本次审计结论是不支持的。

