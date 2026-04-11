"""Hot topic agent for account-aware source scouting."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.core.logger import get_logger
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service
from app.skills.registry import skill_registry

logger = get_logger(__name__)


class HotTopicAgent(BaseAgent):
    """Discover relevant hot topics while separating source scouting from writing."""

    agent_id = "hot_topic_agent"
    name = "Hot Topic Agent"
    description = "Scout candidate sources, then analyze hot topics that fit the account."

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "history_summary": {"type": "string"},
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
        },
    }

    supported_skills = ["hot_topic_fetch_skill"]

    default_system_prompt = """You are a source-aware hot topic analyst for Chinese public-account writing.

Your job is to:
1. read the account profile and strategy hints,
2. review the scoped source-scout results,
3. return only the hot topics that are genuinely relevant to this account.

Return strict JSON only.

Rules:
- Keep the account positioning and lane front and center.
- Prefer topics that are both timely and writable for this audience.
- Do not write the article. Only rank and summarize source-backed topic opportunities.
- Ignore source candidates that are noisy, generic, or off-positioning.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        system_prompt = self.get_system_prompt(context)

        try:
            query_plan = query_planner_service.build_plan(
                profile=profile,
                account_context=account_context,
                ops_context=ops_context,
            )
            logger.info("hot_topic_query_plan_ready", lane=query_plan.get("lane"))

            skill_result = await self._fetch_with_skill(query_plan)
            if skill_result.get("status") != "success":
                error = skill_result.get("error", {})
                raise RuntimeError(f"Skill failed: {error.get('message') or error.get('code') or 'unknown'}")

            search_results = skill_result.get("data", {}).get("results", [])
            scout_package = reference_digest_service.build_source_scout_package(
                search_results=search_results,
                query_plan=query_plan,
                account_context=account_context,
                ops_context=ops_context,
                limit=8,
            )
            logger.info("hot_topic_source_scout_complete", result_count=len(search_results))

            if not search_results:
                return self._success(
                    {
                        "hot_topics": [],
                        "query_plan": query_plan,
                        "source_candidates": scout_package.get("source_candidates", []),
                        "source_snippets": scout_package.get("source_snippets", []),
                        "reference_digest": scout_package.get("reference_digest", {}),
                    }
                )

            structured_topics = await self._analyze_with_llm(
                search_results=search_results,
                profile=profile,
                account_context=account_context,
                system_prompt=system_prompt,
                query_plan=query_plan,
                reference_digest=scout_package.get("reference_digest", {}),
            )

            return self._success(
                {
                    "hot_topics": structured_topics,
                    "query_plan": query_plan,
                    "source_candidates": scout_package.get("source_candidates", []),
                    "source_snippets": scout_package.get("source_snippets", []),
                    "reference_digest": scout_package.get("reference_digest", {}),
                }
            )
        except Exception as exc:
            logger.error("hot_topic_agent_error", error=str(exc))
            return self._failure(code="HOT_TOPIC_ERROR", message=str(exc))

    async def _fetch_with_skill(self, query_plan: dict[str, Any]) -> dict[str, Any]:
        try:
            skill = skill_registry.get("hot_topic_fetch_skill")
            queries = query_plan.get("primary_queries") or query_plan.get("secondary_queries") or []
            return await skill.execute(
                {
                    "queries": queries,
                    "keywords": query_plan.get("search_terms") or [],
                    "engines": ["weixin", "sogou", "360"],
                    "max_results_per_engine": 8,
                }
            )
        except Exception as exc:
            logger.warning("hot_topic_skill_fetch_failed", error=str(exc))
            return {
                "status": "failed",
                "skill_id": "hot_topic_fetch_skill",
                "data": None,
                "error": {"code": "SKILL_ERROR", "message": str(exc)},
            }

    async def _analyze_with_llm(
        self,
        *,
        search_results: list[dict[str, Any]],
        profile: dict[str, Any],
        account_context: dict[str, Any],
        system_prompt: str,
        query_plan: dict[str, Any],
        reference_digest: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not search_results:
            return []

        user_prompt = self._build_analysis_prompt(
            search_results=search_results,
            profile=profile,
            account_context=account_context,
            query_plan=query_plan,
            reference_digest=reference_digest,
        )

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
            data = self._parse_json(content)
            topics = data.get("hot_topics")
            return topics if isinstance(topics, list) else self._fallback_topics(search_results)
        except json.JSONDecodeError:
            logger.warning("hot_topic_llm_json_parse_error")
            return self._fallback_topics(search_results)
        except Exception as exc:
            logger.warning("hot_topic_llm_analysis_error", error=str(exc))
            return self._fallback_topics(search_results)

    def _build_analysis_prompt(
        self,
        *,
        search_results: list[dict[str, Any]],
        profile: dict[str, Any],
        account_context: dict[str, Any],
        query_plan: dict[str, Any],
        reference_digest: dict[str, Any],
    ) -> str:
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
        }
        search_snapshot = [
            {
                "title": item.get("title"),
                "source": item.get("source"),
                "source_type": item.get("source_type"),
                "snippet": item.get("snippet"),
            }
            for item in search_results[:16]
            if isinstance(item, dict)
        ]

        return "\n".join(
            [
                "Review the source-scout results and pick the hot topics worth carrying into planning.",
                "",
                "ACCOUNT SNAPSHOT",
                json.dumps(account_snapshot, ensure_ascii=False, indent=2),
                "",
                "QUERY PLAN",
                json.dumps(query_plan, ensure_ascii=False, indent=2),
                "",
                "REFERENCE DIGEST",
                json.dumps(reference_digest, ensure_ascii=False, indent=2),
                "",
                "SOURCE SCOUT RESULTS",
                json.dumps(search_snapshot, ensure_ascii=False, indent=2),
                "",
                "RETURN CONTRACT",
                "- Return JSON with hot_topics only.",
                "- Include 5-8 items when possible.",
                "- Each hot topic must include title, source, heat_score, summary, relevance_score.",
                "- relevance_score must reflect the account, not just general popularity.",
                "- Skip topics below 0.5 relevance.",
            ]
        )

    def _fallback_topics(self, search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fallback: list[dict[str, Any]] = []
        for item in search_results[:8]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            fallback.append(
                {
                    "title": title,
                    "source": str(item.get("source") or item.get("source_type") or "source").strip(),
                    "heat_score": 70,
                    "summary": str(item.get("snippet") or title)[:80],
                    "relevance_score": 0.62,
                }
            )
        return fallback

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

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        query_plan = query_planner_service.build_plan(
            profile=profile,
            account_context=account_context,
            ops_context=ops_context,
        )
        reference_digest = reference_digest_service.build_reference_digest(
            account_context=account_context,
            ops_context=ops_context,
            query_plan=query_plan,
            limit=3,
        )
        return self._success(
            {
                "hot_topics": [],
                "query_plan": query_plan,
                "source_candidates": [],
                "source_snippets": [],
                "reference_digest": reference_digest,
            }
        )
