"""Profile parsing skill and shared normalization helpers."""

from __future__ import annotations

import json

import litellm

from app.core.config import settings
from app.platforms import normalize_content_platform
from app.skills.base import BaseSkill, SkillResult


class ProfileParseMixin:
    """Shared profile parsing behavior used by both the agent shell and the skill."""

    input_schema = {
        "type": "object",
        "properties": {
            "positioning": {"type": "string", "description": "Natural language account positioning"},
            "account_context": {"type": "object", "description": "Optional account context"},
            "content_platform": {"type": "string", "description": "wechat or xiaohongshu"},
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
            "content_platform": {"type": "string"},
            "visual_style": {"type": "object"},
        },
    }

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
- content_platform: choose wechat or xiaohongshu
- visual_style: for Xiaohongshu accounts, infer cover/card direction, image-text rhythm, title hooks, and note-taking/comment bait cues; otherwise return an empty object.

Rules:
- Infer only what is reasonably supported by the positioning text.
- If the account clearly focuses on research, papers, methods, or academic interpretation, include scholar and set research_mode accordingly.
- If the account clearly focuses on developers, tools, GitHub, open source, or engineering trends, include github and set open_source_mode accordingly.
- If the positioning mentions 小红书, XHS, RedNote, 种草, 笔记, 封面, 图文, or lifestyle-style image-text operation, set content_platform to xiaohongshu and make content_style image-text-note oriented.
"""

    def build_messages(self, positioning: str, system_prompt: str, content_platform: str | None = None) -> list[dict[str, str]]:
        platform = normalize_content_platform(content_platform)
        user_prompt = "\n".join(
            [
                "Parse this account positioning into the required JSON contract:",
                positioning,
                "",
                f"Requested content platform: {platform}",
            ]
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def normalize_profile(self, data: dict, positioning: str) -> dict:
        normalized = dict(data)
        normalized["positioning_raw"] = positioning
        normalized["content_platform"] = normalize_content_platform(normalized.get("content_platform"))
        if not isinstance(normalized.get("visual_style"), dict):
            normalized["visual_style"] = {}
        normalized["source_preferences"] = self._normalize_source_preferences(normalized.get("source_preferences"))
        normalized["research_mode"] = self._normalize_research_mode(
            normalized.get("research_mode"),
            normalized["source_preferences"],
        )
        normalized["open_source_mode"] = self._normalize_open_source_mode(
            normalized.get("open_source_mode"),
            normalized["source_preferences"],
        )
        return normalized

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


class ProfileParseSkill(BaseSkill, ProfileParseMixin):
    """Reusable capability for turning positioning text into a structured profile."""

    skill_id = "profile_parse_skill"
    name = "Profile Parse Skill"
    description = "Parse natural-language account positioning into a structured content profile."

    input_schema = ProfileParseMixin.input_schema
    output_schema = ProfileParseMixin.output_schema

    async def execute(self, input_data: dict) -> dict:
        positioning = str(input_data.get("positioning") or "").strip()
        if not positioning:
            return SkillResult.failure(self.skill_id, "invalid_input", "positioning is required").to_dict()

        system_prompt = str(input_data.get("system_prompt") or self.default_system_prompt)

        try:
            response = await litellm.acompletion(
                messages=self.build_messages(positioning, system_prompt, input_data.get("content_platform")),
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content
            data = self.normalize_profile(self._parse_json(content), positioning)
            return SkillResult.success(self.skill_id, data).to_dict()
        except json.JSONDecodeError as exc:
            return SkillResult.failure(
                self.skill_id,
                "JSON_PARSE_ERROR",
                f"Failed to parse profile JSON: {exc}",
            ).to_dict()
        except Exception as exc:
            return SkillResult.failure(self.skill_id, "LLM_ERROR", str(exc)).to_dict()


profile_parse_skill = ProfileParseSkill()
