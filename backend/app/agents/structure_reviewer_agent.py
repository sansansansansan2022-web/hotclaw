"""Structure reviewer compatibility shell backed by review skill logic."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.skills.review_rewrite_skills import StructureReviewMixin


class StructureReviewerAgent(BaseAgent, StructureReviewMixin):
    """Compatibility shell that preserves the workflow node while delegating logic to the skill layer."""

    agent_id = "structure_reviewer_agent"
    name = "Structure Reviewer"
    description = "Review outline adherence, pacing, and closing strength."

    input_schema = StructureReviewMixin.input_schema
    output_schema = StructureReviewMixin.output_schema
    supported_skills = ["structure_review_skill"]
    default_system_prompt = StructureReviewMixin.default_system_prompt

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        try:
            data = await self.review_structure(
                input_data=input_data,
                context=context,
                completion_callable=litellm.acompletion,
            )
            return self._attach_runtime_trace(self._success(data), context)
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure("JSON_PARSE_ERROR", f"Failed to parse structure review JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure("LLM_ERROR", str(exc)), context)
