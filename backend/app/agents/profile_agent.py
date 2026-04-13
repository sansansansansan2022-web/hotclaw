"""Profile agent: parses account positioning into a structured profile."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings


class ProfileAgent(BaseAgent):
    """Turn free-form account positioning into a structured profile."""

    agent_id = "profile_agent"
    name = "Profile Agent"
    description = "Parse account positioning into a structured content profile."

    input_schema = {
        "type": "object",
        "properties": {
            "positioning": {"type": "string", "description": "Natural language account positioning"},
            "account_context": {"type": "object", "description": "Optional account context"},
        },
        "required": ["positioning"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "subdomain": {"type": "string"},
            "target_audience": {
                "type": "object",
                "properties": {
                    "age_range": {"type": "string"},
                    "occupation": {"type": "string"},
                    "interests": {"type": "array", "items": {"type": "string"}},
                },
            },
            "tone": {"type": "string"},
            "content_style": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "source_preferences": {"type": "array", "items": {"type": "string"}},
            "research_mode": {"type": "string"},
            "open_source_mode": {"type": "string"},
            "positioning_raw": {"type": "string"},
        },
    }

    supported_skills = []

    default_system_prompt = """You are a profile analyst for a content operations system.

Read the account positioning and return strict JSON only.

Required fields:
- domain
- subdomain
- target_audience { age_range, occupation, interests }
- tone
- content_style
- keywords
- source_preferences: choose from scholar, github, wechat, web_search
- research_mode: choose disabled, enabled, research_first
- open_source_mode: choose disabled, enabled, open_source_first

Rules:
- Infer only what is reasonably supported by the positioning text.
- If the account clearly focuses on research, papers, methods, or academic interpretation, include scholar and set research_mode accordingly.
- If the account clearly focuses on developers, tools, GitHub, open source, or engineering trends, include github and set open_source_mode accordingly.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        positioning = input_data.get("positioning", "")
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = f"Parse this account positioning into the required JSON contract:\n{positioning}"

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
            data["positioning_raw"] = positioning
            data["source_preferences"] = self._normalize_source_preferences(data.get("source_preferences"))
            data["research_mode"] = self._normalize_research_mode(data.get("research_mode"), data["source_preferences"])
            data["open_source_mode"] = self._normalize_open_source_mode(
                data.get("open_source_mode"),
                data["source_preferences"],
            )
            return self._success(data)

        except json.JSONDecodeError as exc:
            return self._failure(code="JSON_PARSE_ERROR", message=f"Failed to parse profile JSON: {exc}")
        except Exception as exc:
            return self._failure(code="LLM_ERROR", message=str(exc))

    def _parse_json(self, content: str) -> dict:
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)

    def _normalize_source_preferences(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            clean = str(item).strip().lower()
            if clean not in {"scholar", "github", "wechat", "web_search"}:
                continue
            if clean in seen:
                continue
            seen.add(clean)
            normalized.append(clean)
        return normalized

    def _normalize_research_mode(self, value: object, source_preferences: list[str]) -> str:
        clean = str(value or "").strip().lower()
        if clean in {"disabled", "enabled", "research_first"}:
            return clean
        return "enabled" if "scholar" in source_preferences else "disabled"

    def _normalize_open_source_mode(self, value: object, source_preferences: list[str]) -> str:
        clean = str(value or "").strip().lower()
        if clean in {"disabled", "enabled", "open_source_first"}:
            return clean
        return "enabled" if "github" in source_preferences else "disabled"

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
                "domain": "general",
                "subdomain": "general",
                "target_audience": {"age_range": "18-45", "occupation": "general", "interests": []},
                "tone": "neutral",
                "content_style": "analysis",
                "keywords": [],
                "source_preferences": source_preferences,
                "research_mode": "enabled" if "scholar" in source_preferences else "disabled",
                "open_source_mode": "enabled" if "github" in source_preferences else "disabled",
                "positioning_raw": positioning,
            }
        )
