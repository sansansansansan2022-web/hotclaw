"""Topic planner agent for account-aware content strategy."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service


class TopicPlannerAgent(BaseAgent):
    """Generate topic candidates from hot topics plus account strategy context."""

    agent_id = "topic_planner_agent"
    name = "Topic Planner"
    description = "Turn source-backed hot topics into account-fit topic candidates."

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile", "hot_topics"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "angle": {"type": "string"},
                        "hook": {"type": "string"},
                        "target_emotion": {"type": "string"},
                        "estimated_appeal": {"type": "number"},
                        "reasoning": {"type": "string"},
                        "why_now": {"type": "string"},
                        "reference_basis": {"type": "string"},
                        "target_reader": {"type": "string"},
                        "content_lane": {"type": "string"},
                        "topic_kind": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }

    default_system_prompt = """You are a senior WeChat content strategist.

Turn source-backed hot topics into 3-5 topic candidates that this account can actually own.
Return strict JSON only.

Rules:
- Topic candidates must be account-fit, source-backed, and audience-aware.
- Do not just restate a hot topic. Choose a sharper angle the account can credibly write.
- Explain why each topic is worth writing now, which reference basis supports it, and who it is really for.
- Avoid generic lane drift, shallow summaries, and topics that duplicate the recent-avoid list.
- topic_kind must be one of: paper_digest, research_trend, github_project_review, tools_roundup, benchmark_analysis, industry_method_explainer, general_analysis.
- When external evidence exists, evidence_refs must name the real paper or repo titles that support the topic.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            model = settings.llm_model_name
            if not model.startswith("dashscope/"):
                model = f"dashscope/{model}"

            response = await litellm.acompletion(
                model=model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base_url,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.llm_timeout,
                custom_llm_provider="dashscope",
            )
            content = response.choices[0].message.content
            return self._success(self._normalize_topics(self._parse_json(content)))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse topic JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        hot_topics = input_data.get("hot_topics") or {}
        query_plan = self._resolve_query_plan(input_data)
        lane_label = ((query_plan.get("lane") or {}).get("label")) or "通用洞察"
        digest = input_data.get("reference_digest") or {}
        preferred_sources = digest.get("preferred_source_names") if isinstance(digest, dict) else []
        selected_evidence = input_data.get("selected_evidence") or []
        target_reader = (
            (input_data.get("account_context") or {}).get("audience")
            or (input_data.get("profile") or {}).get("target_audience")
            or "this account's core readers"
        )

        topics: list[dict[str, Any]] = []
        for item in hot_topics.get("hot_topics", []) if isinstance(hot_topics.get("hot_topics"), list) else []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            evidence_refs = [
                str(item.get("title") or "").strip()
                for item in selected_evidence[:2]
                if isinstance(item, dict) and str(item.get("title") or "").strip()
            ]
            topic_kind = "general_analysis"
            if any(
                isinstance(item, dict) and str(item.get("source_type") or "").startswith("github")
                for item in selected_evidence
            ):
                topic_kind = "github_project_review"
            elif any(
                isinstance(item, dict) and str(item.get("source_type") or "").startswith("scholar")
                for item in selected_evidence
            ):
                topic_kind = "paper_digest"
            topics.append(
                {
                    "title": title,
                    "angle": f"Use the {lane_label} lane to turn this hot topic into an account-owned judgment.",
                    "hook": "scene + contradiction",
                    "target_emotion": "recognition",
                    "estimated_appeal": float(item.get("relevance_score") or 0.65),
                    "reasoning": f"This topic already shows relevance and can be localized for {target_reader}.",
                    "why_now": "Source scouting shows the topic is active enough to justify a timely piece.",
                    "reference_basis": ", ".join(preferred_sources[:2]) if preferred_sources else "reference digest",
                    "target_reader": str(target_reader),
                    "content_lane": lane_label,
                    "topic_kind": topic_kind,
                    "evidence_refs": evidence_refs,
                }
            )
            if len(topics) >= 3:
                break

        return self._success({"topics": topics})

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        profile = input_data.get("profile") or {}
        hot_topics = input_data.get("hot_topics") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = input_data.get("reference_digest") or {}
        source_candidates = input_data.get("source_candidates") or []
        selected_evidence = input_data.get("selected_evidence") or []
        evidence_summaries = input_data.get("evidence_summaries") or {}

        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
            "preferred_content_lane": (ops_context.get("run_strategy") or {}).get("preferred_content_lane") or "",
        }

        hot_snapshot = hot_topics.get("hot_topics") if isinstance(hot_topics.get("hot_topics"), list) else []
        return "\n".join(
            [
                "Create topic candidates for the next article.",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
                "",
                "QUERY PLAN",
                article_assembler_service.to_pretty_json(query_plan),
                "",
                "REFERENCE DIGEST",
                article_assembler_service.to_pretty_json(reference_digest),
                "",
                "EVIDENCE SUMMARIES",
                article_assembler_service.to_pretty_json(evidence_summaries),
                "",
                "SELECTED EVIDENCE",
                article_assembler_service.to_pretty_json(selected_evidence[:8] if isinstance(selected_evidence, list) else []),
                "",
                "SOURCE CANDIDATES",
                article_assembler_service.to_pretty_json(source_candidates[:6] if isinstance(source_candidates, list) else []),
                "",
                "HOT TOPICS",
                article_assembler_service.to_pretty_json(hot_snapshot[:8]),
                "",
                "RETURN CONTRACT",
                "- Return JSON with topics.",
                "- Provide 3-5 topics.",
                "- Each topic must include title, angle, hook, target_emotion, estimated_appeal, reasoning, why_now, reference_basis, target_reader, content_lane, topic_kind, evidence_refs.",
                "- angle should explain the account-owned perspective, not just paraphrase the hot topic title.",
                "- If the topic is grounded in a paper or repo, topic_kind and evidence_refs must reflect that evidence explicitly.",
            ]
        )

    def _resolve_query_plan(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query_plan = input_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan
        return query_planner_service.build_plan(
            profile=input_data.get("profile") or {},
            account_context=input_data.get("account_context") or {},
            ops_context=input_data.get("ops_context") or {},
            hot_topics=input_data.get("hot_topics") or {},
        )

    def _normalize_topics(self, data: dict[str, Any]) -> dict[str, Any]:
        raw_topics = data.get("topics") if isinstance(data, dict) else None
        normalized: list[dict[str, Any]] = []
        if isinstance(raw_topics, list):
            for item in raw_topics:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                normalized.append(
                    {
                        "title": title,
                        "angle": str(item.get("angle") or "").strip(),
                        "hook": str(item.get("hook") or "").strip(),
                        "target_emotion": str(item.get("target_emotion") or "").strip(),
                        "estimated_appeal": float(item.get("estimated_appeal") or 0.0),
                        "reasoning": str(item.get("reasoning") or "").strip(),
                        "why_now": str(item.get("why_now") or "").strip(),
                        "reference_basis": str(item.get("reference_basis") or "").strip(),
                        "target_reader": str(item.get("target_reader") or "").strip(),
                        "content_lane": str(item.get("content_lane") or "").strip(),
                        "topic_kind": str(item.get("topic_kind") or "general_analysis").strip() or "general_analysis",
                        "evidence_refs": [
                            str(ref).strip()
                            for ref in item.get("evidence_refs", [])
                            if str(ref).strip()
                        ] if isinstance(item.get("evidence_refs"), list) else [],
                    }
                )
        return {"topics": normalized}

    def _parse_json(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)
