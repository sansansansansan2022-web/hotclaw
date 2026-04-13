"""Decide when runtime skills should be auto-invoked."""

from __future__ import annotations

from typing import Any


class SkillRouterService:
    """Rule-based router for evidence skills."""

    SCHOLAR_HINTS = {
        "ai",
        "research",
        "paper",
        "academic",
        "benchmark",
        "method",
        "model",
        "arxiv",
        "论文",
        "学术",
        "方法",
        "研究",
    }
    GITHUB_HINTS = {
        "github",
        "open source",
        "repo",
        "repository",
        "project",
        "tool",
        "tools",
        "framework",
        "agent",
        "developer",
        "开发者",
        "开源",
        "项目",
        "工具",
    }

    def plan_invocations(
        self,
        *,
        profile: dict[str, Any],
        task_goal: str,
        current_node: str,
        workspace_context: dict[str, Any],
        account_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if current_node != "hot_topic_analysis":
            return []

        joined = " ".join(
            [
                str(profile.get("positioning_raw") or ""),
                str(profile.get("domain") or ""),
                str(profile.get("subdomain") or ""),
                str(task_goal or ""),
                str((account_context or {}).get("content_strategy") or ""),
            ]
        ).lower()
        source_preferences = [str(item).lower() for item in profile.get("source_preferences") or []]
        research_mode = str(profile.get("research_mode") or "").lower()
        open_source_mode = str(profile.get("open_source_mode") or "").lower()
        fetched_evidence = workspace_context.get("fetched_evidence")
        evidence_items = fetched_evidence if isinstance(fetched_evidence, list) else []

        topic = (
            str(profile.get("subdomain") or "").strip()
            or str(profile.get("domain") or "").strip()
            or str(task_goal or "").strip()
            or "AI"
        )

        plans: list[dict[str, Any]] = []
        scholar_plan = {
            "skill_name": "scholar_paper_search_skill",
            "reason": "Account positioning leans toward research, methods, or paper interpretation.",
            "input_data": {
                "topic": topic,
                "max_results": 8,
                "mode": "high_level",
            },
        }
        if research_mode in {"enabled", "research_first"} or "scholar" in source_preferences or any(
            hint in joined for hint in self.SCHOLAR_HINTS
        ):
            if not self._already_fetched(scholar_plan["skill_name"], scholar_plan["input_data"], evidence_items):
                plans.append(scholar_plan)

        github_plan = {
            "skill_name": "github_project_curator_skill",
            "reason": "Account positioning leans toward developers, open-source tooling, or project analysis.",
            "input_data": {
                "topic": topic,
                "max_results": 8,
                "prefer_active": True,
                "mode": "curated",
            },
        }
        if open_source_mode in {"enabled", "open_source_first"} or "github" in source_preferences or any(
            hint in joined for hint in self.GITHUB_HINTS
        ):
            if not self._already_fetched(github_plan["skill_name"], github_plan["input_data"], evidence_items):
                plans.append(github_plan)
        return plans

    def _already_fetched(
        self,
        skill_name: str,
        input_data: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> bool:
        topic = str(input_data.get("topic") or "").strip().lower()
        if not topic:
            return False
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("skill_name") or "").strip() != skill_name:
                continue
            haystack = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("source_id") or ""),
                ]
            ).lower()
            if topic in haystack:
                return True
        return False


skill_router_service = SkillRouterService()
