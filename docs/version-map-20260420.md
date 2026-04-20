# HotClaw Version Map - 2026-04-20

This document is the current source of truth for HotClaw version identity, deployment lines, and cleanup rules.

## Active Version Lines

| Line | Current Anchor | Purpose | Status |
| --- | --- | --- | --- |
| Product development | `improve` | Main product and architecture work. Agent, skill, service, schema, API, and UI contract changes start here. | Active |
| Architecture anchor | `architecture-rollup-20260418` | Rollback point for the agent/skill/service governance rollout. This is not a production runtime tag. | Active tag |
| ECS rollback | `stable-20260416` | Known stable Alibaba Cloud ECS runtime rollback point. | Active tag |
| ModelScope demo | `sansan2026/hotclaw1` | Demo/runtime packaging line for ModelScope Space. Platform-specific Docker/app startup fixes live here. | Active demo line |
| GitHub master | `origin/master` | Older merged product history. Do not use as the main development branch right now. | Historical |

## Deprecated Or Side Lines

| Line | Status | Notes |
| --- | --- | --- |
| `sansan2026/hotclaw` ModelScope Space | Deprecated | Replaced by `sansan2026/hotclaw1`. Do not deploy new work here. |
| Local `master` | Historical | Behind `origin/master` and not aligned with current `improve` work. |
| `wechat-token-hotfix` | Side hotfix | Contains WeChat token request hardening. Review before merging into `improve`; do not treat it as the main line. |
| `.modelscope-*` local folders | Deployment work copies | Keep ignored from the main repository status. They are not product source directories. |
| `.stable-build` | Local build workspace | Keep ignored from the main repository status. |

## Current Timeline

| Date | Anchor | Meaning |
| --- | --- | --- |
| 2026-03-25 | `15d54da` | Initial HotClaw pixel-art newsroom implementation. |
| 2026-03-26 | `312ce5f`, `79cd166` | Unified LLM gateway and real agent calls. |
| 2026-04-02 to 2026-04-03 | `b720c44` to `3c817b6` | WeChat publishing, draft workflow, publish protection, account module. |
| 2026-04-07 to 2026-04-10 | `8794a39`, `480735a`, `68381b4` | Operations console rebuild, localization fixes, writing pipeline quality improvements. |
| 2026-04-13 to 2026-04-14 | `bfceebd`, `f6f8706` | Account detail flow, recommendations, compose basket/session work. |
| 2026-04-15 to 2026-04-16 | `04996be`, `stable-20260416` | Docker/ECS runtime stabilization and rollback anchor. |
| 2026-04-16 to 2026-04-18 | `d3fd66e` to `de6d961` | Runtime governance, artifact contracts, batch1-3 agent/skill boundary rollup. |
| 2026-04-20 | ModelScope `hotclaw1@cc529c7` | Demo line expanded account-matched news sources. |

## Tag Naming Rules

Use names that explain intent without reading commit history.

| Pattern | Meaning | Example |
| --- | --- | --- |
| `stable-YYYYMMDD` | Known rollback point for a deployed runtime. | `stable-20260416` |
| `architecture-rollup-YYYYMMDD` | Architecture governance anchor, not necessarily deploy-stable. | `architecture-rollup-20260418` |
| `demo-modelscope-YYYYMMDD-N` | Known working ModelScope demo point. | `demo-modelscope-20260420-1` |
| `hotfix-topic-YYYYMMDD` | Narrow emergency fix point. | `hotfix-wechat-token-20260416` |

Avoid ambiguous names such as `final`, `fix2`, `latest`, or `stable2` for recovery-critical versions.

## Environment Responsibilities

| Environment | Responsibility | Rule |
| --- | --- | --- |
| `improve` | Product truth | Business behavior, schemas, contracts, agent/skill/service work, and frontend product flows start here. |
| ModelScope `hotclaw1` | Demo shell | Dockerfile, `app.py`, ModelScope port/env/startup adaptation, and demo-only packaging can stay here. |
| Alibaba Cloud ECS | Stable runtime | Keep rollback commands and image tags documented. Do not treat manual ECS patching as source of truth. |

## One-Way Sync Policy

Default flow:

1. Change product behavior on `improve`.
2. Run local verification appropriate to the change.
3. Commit on `improve`.
4. Copy or cherry-pick only the demo-required subset into ModelScope `hotclaw1`.
5. Verify ModelScope build/runtime.
6. Record notable deployment points in this document or a dated deployment note.

Allowed exceptions:

- ModelScope-only Dockerfile, `app.py`, port, process, and environment adaptations may be made directly in `hotclaw1`.
- Demo-only labels or empty-state copy may be made in `hotclaw1` if they do not change product contracts.

Not allowed:

- Do not create new business behavior first in ModelScope.
- Do not back-merge ModelScope platform hacks into `improve` without review.
- Do not treat ECS manual commands as product code changes.

## Rollback Notes

### ECS rollback

Use `stable-20260416` as the rollback identity. Its annotated tag records the stable runtime details:

- Backend image: `hotclaw/backend:20260415`
- Frontend image: `hotclaw/frontend:20260415-fix2`
- Redis image: `hotclaw/redis:7-alpine`
- Runtime guards: disable scheduler, disable system config init, clear proxy envs, and set `NO_PROXY` for WeChat API and internal services.

### Architecture rollback

Use `architecture-rollup-20260418` to return to the architecture-governance starting point before further agent/skill/service refactors.

## Guardrails

- Do not continue feature work from local `master`.
- Do not commit `.modelscope-*` or `.stable-build` into the main repository.
- Do not use `latest` as a critical rollback image tag.
- Do not mix database migration fixes, deployment platform fixes, and agent architecture refactors in one commit.
- Do not weaken contract tests just to pass a refactor; split the contract alignment into its own commit if needed.
- Keep legacy fallback paths until structured artifacts have proven stable across real task runs.

## Current Cleanup State

As of 2026-04-20, the main repository intentionally ignores these local deployment/build work copies:

- `.modelscope-hotclaw-space/`
- `.modelscope-hotclaw1-space/`
- `.stable-build/`
