"""Style reviewer compatibility shell backed by review skill logic."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.skills.review_rewrite_skills import StyleReviewMixin


class StyleReviewerAgent(BaseAgent, StyleReviewMixin):
    """Compatibility shell that preserves the workflow node while delegating logic to the skill layer."""

    agent_id = "style_reviewer_agent"
    name = "Style Reviewer"
    description = "Review style drift, AI tone, and voice consistency."

    input_schema = StyleReviewMixin.input_schema
    output_schema = StyleReviewMixin.output_schema
    supported_skills = ["style_review_skill"]
    default_system_prompt = StyleReviewMixin.default_system_prompt

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        try:
            data = await self.review_style(
                input_data=input_data,
                context=context,
                completion_callable=litellm.acompletion,
            )
            return self._attach_runtime_trace(self._success(data), context)
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure("JSON_PARSE_ERROR", f"Failed to parse style review JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure("LLM_ERROR", str(exc)), context)
