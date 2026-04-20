"""Title generator compatibility shell backed by title generation skill logic."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.skills.title_generate_skill import TitleGenerateMixin


class TitleGeneratorAgent(BaseAgent, TitleGenerateMixin):
    """Compatibility shell that preserves the workflow node while delegating logic to the skill layer."""

    agent_id = "title_generator_agent"
    name = "Title Generator"
    description = "Generate title candidates grounded in strategy and reference cues."

    input_schema = TitleGenerateMixin.input_schema
    output_schema = TitleGenerateMixin.output_schema
    supported_skills = ["title_generate_skill"]
    default_system_prompt = TitleGenerateMixin.default_system_prompt

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)

        try:
            response = await self.run_litellm_completion(
                context=context,
                completion_callable=litellm.acompletion,
                messages=self.build_messages(input_data, system_prompt),
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content
            return self._attach_runtime_trace(
                self._success(self._normalize_titles(self._parse_json(content), input_data)),
                context,
            )
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure("JSON_PARSE_ERROR", f"Failed to parse title JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure("LLM_ERROR", str(exc)), context)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        selected_topic = self._pick_topic(input_data.get("topics") or {})
        return self._success(
            {
                "selected_topic": selected_topic,
                "titles": [
                    {
                        "text": selected_topic or "Untitled",
                        "style": "direct",
                        "score": 5.0,
                        "reasoning": "Fallback uses the strongest topic title directly.",
                    }
                ],
            }
        )
