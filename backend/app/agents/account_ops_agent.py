"""Account-level operations agent for run-time strategy decisions."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BaseAgent, AgentResult
from app.llm.base import LLMCallOptions
from app.llm.gateway import LLMGateway


class AccountOpsAgent(BaseAgent):
    """Generate structured ops guidance before an account run starts."""

    agent_id = "account_ops_agent"
    name = "Account Ops Agent"
    description = "Judges whether an account run should proceed and how conservative the runtime strategy should be."

    input_schema = {
        "type": "object",
        "properties": {
            "account": {"type": "object"},
            "automation_plan": {"type": "object"},
            "reference_sources": {"type": "array", "items": {"type": "object"}},
            "recent_tasks": {"type": "array", "items": {"type": "object"}},
            "recent_drafts": {"type": "array", "items": {"type": "object"}},
            "recent_publishes": {"type": "array", "items": {"type": "object"}},
            "signals": {"type": "object"},
            "trigger": {"type": "object"},
        },
        "required": ["account", "automation_plan", "signals", "trigger"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "account_health": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "issues": {"type": "array", "items": {"type": "string"}},
                },
            },
            "operation_stage": {"type": "string"},
            "run_strategy": {
                "type": "object",
                "properties": {
                    "allow_run": {"type": "boolean"},
                    "effective_mode": {"type": "string"},
                    "allow_auto_publish": {"type": "boolean"},
                    "allow_reviewers": {"type": "boolean"},
                    "reviewer_mode": {"type": "string"},
                    "allow_rewrite": {"type": "boolean"},
                    "allow_post_process": {"type": "boolean"},
                    "high_cost_model_nodes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "preferred_reference_source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "avoid_recent_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "preferred_content_lane": {"type": ["string", "null"]},
                },
            },
            "ops_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "account_health",
            "operation_stage",
            "run_strategy",
            "ops_notes",
        ],
    }

    default_system_prompt = """\
You are the HotClaw account operations controller.

Your job is not to write article content. Your job is to decide whether the
next account run should proceed, how conservative it should be, and whether
automatic publishing should be allowed for this single run.

Return strict JSON only with this shape:
{
  "account_health": {
    "status": "ready | attention | risk_recovery",
    "issues": ["..."]
  },
  "operation_stage": "style_learning | steady_state | risk_recovery",
  "run_strategy": {
    "allow_run": true,
    "effective_mode": "manual | semi_auto | full_auto",
    "allow_auto_publish": false,
    "allow_reviewers": true,
    "reviewer_mode": "single | dual",
    "allow_rewrite": true,
    "allow_post_process": true,
    "high_cost_model_nodes": ["outline_planner"],
    "preferred_reference_source_ids": ["1", "2"],
    "avoid_recent_topics": ["..."],
    "preferred_content_lane": "..."
  },
  "ops_notes": ["..."]
}

Rules:
- Be conservative.
- If there are too few references, pending-review backlog, or recent failures,
  do not recommend aggressive automation.
- Never output markdown. JSON only.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        gateway = LLMGateway()
        prompt = self._build_prompt(input_data)

        try:
            response = await gateway.complete(
                agent_id=self.agent_id,
                prompt=prompt,
                options=LLMCallOptions(
                    system_prompt=self.get_system_prompt(context),
                    temperature=0.2,
                    max_tokens=900,
                ),
                trace_id=str(context.get("trace_id") or ""),
            )
            data = self._parse_json(response.content)
            return self._success(self._normalize_output(data))
        except Exception as exc:
            return self._failure("OPS_AGENT_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._success(self._heuristic_output(input_data))

    def _build_prompt(self, input_data: dict[str, Any]) -> str:
        return (
            "Review the following account runtime snapshot and return a conservative "
            "single-run operations decision as strict JSON.\n\n"
            f"{json.dumps(input_data, ensure_ascii=False, indent=2)}"
        )

    def _parse_json(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
        return json.loads(cleaned.strip())

    def _normalize_output(self, data: dict[str, Any]) -> dict[str, Any]:
        run_strategy = data.get("run_strategy") if isinstance(data.get("run_strategy"), dict) else {}
        account_health = data.get("account_health") if isinstance(data.get("account_health"), dict) else {}

        return {
            "account_health": {
                "status": str(account_health.get("status") or "attention"),
                "issues": [str(item).strip() for item in account_health.get("issues", []) if str(item).strip()],
            },
            "operation_stage": str(data.get("operation_stage") or "style_learning"),
            "run_strategy": {
                "allow_run": bool(run_strategy.get("allow_run", True)),
                "effective_mode": str(run_strategy.get("effective_mode") or "semi_auto"),
                "allow_auto_publish": bool(run_strategy.get("allow_auto_publish", False)),
                "allow_reviewers": bool(run_strategy.get("allow_reviewers", True)),
                "reviewer_mode": str(run_strategy.get("reviewer_mode") or "dual"),
                "allow_rewrite": bool(run_strategy.get("allow_rewrite", True)),
                "allow_post_process": bool(run_strategy.get("allow_post_process", True)),
                "high_cost_model_nodes": [
                    str(item).strip()
                    for item in run_strategy.get("high_cost_model_nodes", [])
                    if str(item).strip()
                ],
                "preferred_reference_source_ids": [
                    str(item).strip()
                    for item in run_strategy.get("preferred_reference_source_ids", [])
                    if str(item).strip()
                ],
                "avoid_recent_topics": [
                    str(item).strip()
                    for item in run_strategy.get("avoid_recent_topics", [])
                    if str(item).strip()
                ],
                "preferred_content_lane": (
                    str(run_strategy.get("preferred_content_lane")).strip()
                    if run_strategy.get("preferred_content_lane")
                    else None
                ),
            },
            "ops_notes": [str(item).strip() for item in data.get("ops_notes", []) if str(item).strip()],
        }

    def _heuristic_output(self, input_data: dict[str, Any]) -> dict[str, Any]:
        plan = input_data.get("automation_plan") if isinstance(input_data.get("automation_plan"), dict) else {}
        signals = input_data.get("signals") if isinstance(input_data.get("signals"), dict) else {}
        reference_sources = input_data.get("reference_sources") if isinstance(input_data.get("reference_sources"), list) else []
        recent_drafts = input_data.get("recent_drafts") if isinstance(input_data.get("recent_drafts"), list) else []

        enabled_reference_source_count = int(signals.get("enabled_reference_source_count") or 0)
        pending_review_count = int(signals.get("pending_review_count") or 0)
        recent_failed_publish_count = int(signals.get("recent_failed_publish_count") or 0)
        recent_failed_task_count = int(signals.get("recent_failed_task_count") or 0)
        recent_success_publish_count = int(signals.get("recent_success_publish_count") or 0)

        issues: list[str] = []
        notes: list[str] = []
        plan_type = str(plan.get("plan_type") or "manual")
        operation_stage = "steady_state"
        effective_mode = plan_type
        allow_auto_publish = bool(plan.get("auto_publish_enabled", False))
        allow_run = True
        allow_reviewers = True
        reviewer_mode = "dual"
        allow_rewrite = True
        allow_post_process = True
        high_cost_model_nodes: list[str] = []

        if enabled_reference_source_count < 2:
            issues.append("Reference sources are still sparse.")
            notes.append("Reference sources are still sparse, so this run should stay conservative.")
            operation_stage = "style_learning"

        if pending_review_count >= 3:
            issues.append("Pending review backlog is building up.")
            notes.append("There is already a pending-review backlog for this account.")

        if recent_failed_publish_count >= 2 or recent_failed_task_count >= 2:
            issues.append("Recent failures suggest the account is in recovery.")
            notes.append("Recent task or publish failures suggest a recovery phase.")
            operation_stage = "risk_recovery"

        if recent_success_publish_count == 0 and operation_stage == "steady_state":
            operation_stage = "style_learning"

        if plan_type == "full_auto" and (
            enabled_reference_source_count < 2
            or pending_review_count >= 3
            or recent_failed_publish_count >= 2
            or operation_stage in {"style_learning", "risk_recovery"}
        ):
            effective_mode = "semi_auto"
            allow_auto_publish = False
            notes.append("Full-auto is downgraded for this run to reduce risk.")

        if pending_review_count >= 6 and str(input_data.get("trigger", {}).get("source")) == "scheduler":
            allow_run = False
            notes.append("Scheduler-triggered run is paused until review backlog drops.")

        if operation_stage == "risk_recovery":
            reviewer_mode = "single"
            allow_post_process = False
            high_cost_model_nodes = []
        elif effective_mode in {"semi_auto", "full_auto"} and operation_stage == "steady_state":
            high_cost_model_nodes = ["outline_planner", "rewrite_agent"]

        if not allow_reviewers:
            reviewer_mode = "single"
            allow_rewrite = False
        if reviewer_mode == "single":
            notes.append("Use a single reviewer to keep the run conservative.")

        preferred_reference_source_ids = [
            str(item.get("id"))
            for item in reference_sources[:3]
            if isinstance(item, dict) and item.get("id") is not None
        ]
        avoid_recent_topics: list[str] = []
        for item in recent_drafts:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("selected_topic") or item.get("title") or "").strip()
            if topic and topic not in avoid_recent_topics:
                avoid_recent_topics.append(topic)
            if len(avoid_recent_topics) >= 4:
                break

        return {
            "account_health": {
                "status": "risk_recovery" if operation_stage == "risk_recovery" else ("ready" if not issues else "attention"),
                "issues": issues,
            },
            "operation_stage": operation_stage,
            "run_strategy": {
                "allow_run": allow_run,
                "effective_mode": effective_mode,
                "allow_auto_publish": allow_auto_publish and effective_mode == "full_auto",
                "allow_reviewers": allow_reviewers,
                "reviewer_mode": reviewer_mode,
                "allow_rewrite": allow_rewrite,
                "allow_post_process": allow_post_process,
                "high_cost_model_nodes": high_cost_model_nodes,
                "preferred_reference_source_ids": preferred_reference_source_ids,
                "avoid_recent_topics": avoid_recent_topics,
                "preferred_content_lane": str(signals.get("preferred_content_lane") or "").strip() or None,
            },
            "ops_notes": notes or ["Conservative heuristic fallback was used for this run."],
        }
