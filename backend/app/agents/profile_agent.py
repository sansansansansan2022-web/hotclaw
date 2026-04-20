"""Profile agent compatibility shell backed by profile parsing skill logic."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.skills.profile_parse_skill import ProfileParseMixin


class ProfileAgent(BaseAgent, ProfileParseMixin):
    """Compatibility shell that preserves the workflow node while delegating logic to the skill layer."""

    agent_id = "profile_agent"
    name = "账号定位解析智能体"
    description = "Parse account positioning into a structured content profile."

    input_schema = ProfileParseMixin.input_schema
    output_schema = ProfileParseMixin.output_schema
    supported_skills = ["profile_parse_skill"]
    default_system_prompt = ProfileParseMixin.default_system_prompt

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        positioning = str(input_data.get("positioning") or "")
        system_prompt = context.get("system_prompt") or self.default_system_prompt

        try:
            response = await self.run_litellm_completion(
                context=context,
                completion_callable=litellm.acompletion,
                messages=self.build_messages(positioning, system_prompt),
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content
            data = self.normalize_profile(self._parse_json(content), positioning)
            return self._attach_runtime_trace(self._success(data), context)
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure(code="JSON_PARSE_ERROR", message=f"Failed to parse profile JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure(code="LLM_ERROR", message=str(exc)), context)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        positioning = str(input_data.get("positioning") or "")
        lower = positioning.lower()
        source_preferences: list[str] = []

        if any(token in lower for token in ("论文", "学术", "research", "paper", "arxiv", "benchmark")):
            source_preferences.append("scholar")
        if any(token in lower for token in ("github", "开源", "developer", "repo", "项目", "工具")):
            source_preferences.append("github")

        return self._success(
            {
                "domain": "泛资讯",
                "subdomain": "通用",
                "target_audience": {"age_range": "18-45", "occupation": "general", "interests": []},
                "tone": "中性",
                "content_style": "分析型",
                "keywords": [],
                "source_preferences": source_preferences,
                "research_mode": "enabled" if "scholar" in source_preferences else "disabled",
                "open_source_mode": "enabled" if "github" in source_preferences else "disabled",
                "positioning_raw": positioning,
            }
        )
