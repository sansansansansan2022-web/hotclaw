"""Section writer compatibility shell backed by structured writing skill logic."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.skills.structured_writing_skills import OutlineGenerateMixin, SectionDraftMixin


class SectionWriterAgent(BaseAgent, SectionDraftMixin, OutlineGenerateMixin):
    """Compatibility shell that preserves the workflow node while delegating logic to the skill layer."""

    agent_id = "section_writer_agent"
    name = "Section Writer"
    description = "Draft article sections from the structured outline."

    input_schema = SectionDraftMixin.input_schema
    output_schema = SectionDraftMixin.output_schema
    supported_skills = ["section_draft_skill"]
    default_system_prompt = SectionDraftMixin.default_system_prompt

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        selected_title = self._resolve_selected_title(input_data)
        selected_topic = self._resolve_selected_topic(input_data)
        try:
            normalized = await self.generate_section_drafts(
                input_data=input_data,
                context=context,
                completion_callable=litellm.acompletion,
            )
            if not self._section_drafts_match_topic(normalized, selected_topic, selected_title):
                fallback_result = await self.fallback(RuntimeError("section topic drift detected"), input_data)
                if fallback_result and fallback_result.is_success:
                    return self._attach_runtime_trace(fallback_result, context, fallback_used=True)
            return self._attach_runtime_trace(self._success(normalized), context)
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure("JSON_PARSE_ERROR", f"Failed to parse section JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure("LLM_ERROR", str(exc)), context)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._success(self._section_fallback_payload(error, input_data))

    def _resolve_selected_title(self, input_data: dict) -> str:
        titles = input_data.get("titles") or {}
        if isinstance(titles, dict):
            if isinstance(titles.get("selected_title"), str):
                return str(titles["selected_title"]).strip()
            title_list = titles.get("titles")
            if isinstance(title_list, list) and title_list:
                first = title_list[0]
                if isinstance(first, dict):
                    return str(first.get("text") or first.get("title") or "").strip()
                return str(first).strip()
        return "Untitled"

    def _resolve_selected_topic(self, input_data: dict) -> str:
        topics = input_data.get("topics") or {}
        if isinstance(topics, dict):
            if isinstance(topics.get("selected_topic"), str):
                return str(topics["selected_topic"]).strip()
            topic_list = topics.get("topics")
            if isinstance(topic_list, list) and topic_list:
                first = topic_list[0]
                if isinstance(first, dict):
                    return str(first.get("title") or first.get("topic") or "").strip()
                return str(first).strip()
        return self._resolve_selected_title(input_data)
