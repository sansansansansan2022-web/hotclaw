"""Hot topic agent compatibility shell."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.services.hot_topic_analysis_service import hot_topic_analysis_service


class HotTopicAgent(BaseAgent):
    """Keep account-fit judgment in the agent while orchestration lives in services."""

    agent_id = "hot_topic_agent"
    name = "Hot Topic Agent"
    description = "Scout candidate sources, then analyze hot topics that fit the account."

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {
                "type": "object",
                "description": "Structured account profile used to assess topic fit.",
            },
            "account_context": {
                "type": "object",
                "description": "Persisted account metadata and strategy context.",
            },
            "ops_context": {
                "type": "object",
                "description": "Run-time strategy and scoring hints from account ops.",
            },
            "history_summary": {"type": "string"},
            "query_plan": {"type": "object"},
            "source_candidates": {"type": "array"},
            "reference_digest": {"type": "object"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "hot_topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "source": {"type": "string"},
                        "heat_score": {"type": "integer"},
                        "summary": {"type": "string"},
                        "relevance_score": {"type": "number"},
                    },
                },
            },
            "query_plan": {"type": "object"},
            "source_candidates": {"type": "array"},
            "source_snippets": {"type": "array"},
            "reference_digest": {"type": "object"},
            "external_evidence": {"type": "object"},
            "fetched_evidence": {"type": "array"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
    }

    supported_skills = ["hot_topic_fetch_skill"]

    default_system_prompt = """You are a source-aware hot topic analyst for Chinese public-account writing.

Your job is to:
1. read the account profile and strategy hints,
2. review both scoped source-scout results and grounded external evidence,
3. return only the hot topics that are genuinely relevant to this account.

Return strict JSON only.

Rules:
- Keep the account positioning and lane front and center.
- Prefer topics that are both timely and writable for this audience.
- Do not write the article. Only rank and summarize source-backed topic opportunities.
- Ignore source candidates that are noisy, generic, or off-positioning.
- If external evidence is present, treat it as the citation source of truth.
"""

    async def execute(self, input_data: dict[str, Any], context: dict[str, Any]) -> AgentResult:
        return await hot_topic_analysis_service.execute(
            agent=self,
            input_data=input_data,
            context=context,
        )

    async def fallback(self, error: Exception, input_data: dict[str, Any]) -> AgentResult | None:
        return await hot_topic_analysis_service.fallback(
            agent=self,
            error=error,
            input_data=input_data,
        )
