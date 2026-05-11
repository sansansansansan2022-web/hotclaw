# Design Doc: Multi-Agent Orchestration Refactor (13 -> 8)

## 1. Context

This design implements the PRD in `docs/prd-multi-agent-13-to-9-refactor.md` with confirmed product decisions:

- Single quality gate: `audit` is the only gate.
- Flow order: **audit -> rewrite (conditional)**.
- Blocker policy: **degraded preview only** (no publish).
- Rewrite trigger: **`rewrite_required=true` OR `risk_level=medium`**.
- Observability scope: **StageEnvelope at both node and task level**.
- Compatibility: **read-compat only** (no long-term dual-write aliases).

---

## 2. Goals

- Reduce orchestration complexity from 13 agents to 8.
- Move recovery/degrade strategy to orchestration layer.
- Standardize stage output contracts and runtime traces.
- Preserve operational safety with strict publish decisions.

---

## 3. Final Orchestration Flow

## 3.1 Runtime flow (confirmed)

`profile -> hot_topic -> topic_planner(+title) -> content_writer(+outline+section) -> audit -> rewrite?(conditional) -> post_process -> account_ops_finalize`

### Stage responsibilities

- `topic_planner`: topic candidates + title candidates + selected title.
- `content_writer`: complete draft bundle (outline/sections/content).
- `audit`: style+structure+compliance merged output; emits decision.
- `rewrite`: only if trigger conditions match.
- `post_process`: preview-ready formatting and image handling.
- `account_ops_finalize`: terminal orchestration summary for downstream ops.

---

## 4. Decision Policies

## 4.1 Audit decision model

`audit` must output:

- `risk_level`: `low | medium | high`
- `rewrite_required`: boolean
- `publish_decision`: `pass | rewrite | blocker`

Derivation:

- `high` -> `publish_decision=blocker`
- `medium` -> `publish_decision=rewrite`
- `low` and no critical issues -> `publish_decision=pass`

## 4.2 Rewrite trigger

Rewrite executes when either condition is true:

1. `audit_result.rewrite_required == true`
2. `audit_result.risk_level == "medium"`

Otherwise rewrite is skipped as `strategy skip`.

## 4.3 Blocker handling

For `publish_decision=blocker`:

- Do not proceed to publish path.
- Allow degraded preview artifact generation for human review.
- Mark task as non-publishable in execution meta.

---

## 5. State Machine Design

## 5.1 Core states

- `PRECHECK`
- `RUNNING(stage)`
- `RETRYING(stage)`
- `DEGRADED(stage)`
- `BLOCKED_REVIEW_ONLY`
- `COMPLETED`
- `FAILED`

## 5.2 Transition rules

- Transient failures (`timeout`, `429`, connection) -> retry with backoff.
- Retry exhausted with fallback available -> degraded.
- Hard schema/runtime contract failures -> fail-fast.
- Audit blocker -> `BLOCKED_REVIEW_ONLY` terminal branch.

---

## 6. Structured Output Contract

## 6.1 StageEnvelope schema

```json
{
  "trace_id": "string",
  "task_id": "string",
  "stage": "string",
  "status": "ok|retryable_error|degraded|hard_fail|skipped",
  "severity": "none|minor|major|blocker",
  "attempt": 1,
  "max_attempts": 3,
  "latency_ms": 1234,
  "model_route": {
    "provider": "string|null",
    "model": "string|null",
    "fallback_used": false
  },
  "error": {
    "code": "string|null",
    "message": "string|null",
    "retry_after_ms": 0
  },
  "next_action": "continue|retry|degrade|rewrite|stop"
}
```

## 6.2 Storage scope (confirmed B)

StageEnvelope is stored in two places:

1. **Node-level**
   - `task_node_runs.output_data.stage_envelope`
2. **Task-level aggregate**
   - `task.result_data.execution_meta.stages[]`

Aggregation rules:

- Append per node completion.
- Preserve execution order.
- Include final synthetic stage for terminal decision (`publishable` vs `review_only`).

---

## 7. Data Model and Payload Design

## 7.1 Stage payload minimums

- `topic_planner.output`
  - `topics[]`, `selected_topic`, `titles[]`, `selected_title`
- `content_writer.output`
  - `outline[]`, `sections[]`, `content_markdown`
- `audit.output`
  - `issues[]`, `risk_level`, `rewrite_required`, `publish_decision`, `reason_codes[]`
- `account_ops_finalize.output`
  - `final_status`, `publishability`, `ops_notes`

## 7.2 Task-level meta additions

`task.result_data.execution_meta` adds:

- `stages[]` (aggregated StageEnvelope list)
- `single_gate_mode: true`
- `publishability: publishable | review_only | blocked`
- `degraded: boolean`

---

## 8. Failure Recovery and Degrade Strategy

## 8.1 Pre-stage checks

- Provider/model health
- Timeout budget
- Circuit-breaker cooldown
- Required input contract completeness

## 8.2 Error classes

- `retryable_error`: timeout/429/network
- `degraded`: retry exhausted but fallback path exists
- `hard_fail`: schema mismatch, contract break, unsafe state

## 8.3 Degrade priority

1. Provider/model fallback
2. Prompt simplification
3. Output granularity downgrade
4. Review-only terminal state

---

## 9. Compatibility Strategy (confirmed)

Read-compat only:

- Old task records remain readable.
- New runs write only new canonical structures.
- No long-term dual-write aliases beyond minimal transitional glue in assembler/normalizer.

---

## 10. Implementation Plan

## Phase 1: Pipeline and registry consolidation

- Remove old 5 agents from active registry.
- Update workflow node definitions to 8-stage chain.
- Merge title generation into topic planner output.

## Phase 2: Audit/rewrite decision engine

- Standardize `audit_result` with `publish_decision`.
- Implement rewrite trigger policy (`flag OR medium`).
- Implement blocker -> review-only branch.

## Phase 3: Envelope observability

- Node-level StageEnvelope generation.
- Task-level `execution_meta.stages[]` aggregation.
- Structured log alignment (`trace_id`, stage, decision).

## Phase 4: Validation

- E2E happy path
- Retry/degrade path
- Blocker review-only path
- Backward read compatibility checks

---

## 11. Test Strategy

- Unit tests:
  - audit decision derivation
  - rewrite trigger predicate
  - envelope builder and severity mapping
- Integration tests:
  - full 8-stage run
  - transient failure with retry/degrade
  - blocker path to review-only terminal state
- Contract tests:
  - node envelope schema
  - aggregated task `execution_meta.stages`

---

## 12. Risks and Guardrails

- Risk: prompt inflation after role merge.
  - Guardrail: strict output schema + max token caps + fallback defaults.
- Risk: inconsistent node/task envelope views.
  - Guardrail: write-through helper function for both sinks.
- Risk: blocker path accidentally publishing.
  - Guardrail: centralized publishability check in orchestration finalizer.

---

## 13. Open Follow-up (non-blocking)

- Optional feature flag for staged rollout by environment.
- Future router integration with policy-compiled model pools.
- Frontend timeline visualization for `execution_meta.stages`.
