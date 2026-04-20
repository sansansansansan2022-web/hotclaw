"""Rewrite compatibility shell backed by review/rewrite skill logic."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.skills.review_rewrite_skills import RewriteMixin


class RewriteAgent(BaseAgent, RewriteMixin):
    """Compatibility shell that preserves the workflow node while delegating logic to the skill layer."""

    agent_id = "rewrite_agent"
    name = "Rewrite Agent"
    description = "Apply one revision pass using reviewer findings."

    input_schema = RewriteMixin.input_schema
    output_schema = RewriteMixin.output_schema
    supported_skills = ["rewrite_skill"]
    default_system_prompt = RewriteMixin.default_system_prompt

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        try:
            data = await self.rewrite_article(
                input_data=input_data,
                context=context,
                completion_callable=litellm.acompletion,
            )
            return self._attach_runtime_trace(self._success(data), context)
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure("JSON_PARSE_ERROR", f"Failed to parse rewrite JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure("LLM_ERROR", str(exc)), context)
