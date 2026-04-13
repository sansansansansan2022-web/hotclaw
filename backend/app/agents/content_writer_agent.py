"""Content writer agent: generates full article content."""

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings


class ContentWriterAgent(BaseAgent):
    """Generate long-form content using grounded topics, titles, and evidence."""

    agent_id = "content_writer_agent"
    name = "Content Writer Agent"
    description = "Generate a complete article from topics, titles, and grounded evidence."

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "topics": {"type": "object"},
            "titles": {"type": "object"},
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile", "topics", "titles", "hot_topics"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "content_markdown": {"type": "string"},
            "word_count": {"type": "integer"},
            "structure": {
                "type": "object",
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                    }
                },
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }

    supported_skills = []

    default_system_prompt = """You are a professional Chinese long-form public-account writer.

Generate a complete article as strict JSON.

Required output fields:
- content_markdown
- word_count
- structure { sections: [{ heading, summary }] }
- tags

Rules:
- Match the account tone and audience.
- Use only grounded paper titles and repository names that exist in the provided evidence.
- Do not invent studies, benchmarks, repos, or citation claims.
- Keep paragraphs readable on mobile.
- Total length should usually stay between 1500 and 3000 Chinese characters.
- If the selected topic is paper_digest or research_trend, the article must include:
  background, problem, core method, why it matters, limitations.
- If the selected topic is github_project_review or tools_roundup, the article must include:
  project定位, who it is for, modules worth studying, risks and limits.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile", {})
        topics = input_data.get("topics", {})
        titles_data = input_data.get("titles", {})
        hot_topics = input_data.get("hot_topics", {})
        selected_evidence = input_data.get("selected_evidence") or []
        evidence_summaries = input_data.get("evidence_summaries") or {}
        citation_guardrails = input_data.get("citation_guardrails") or {}
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(
            profile=profile,
            topics=topics,
            titles_data=titles_data,
            hot_topics=hot_topics,
            selected_evidence=selected_evidence,
            evidence_summaries=evidence_summaries,
            citation_guardrails=citation_guardrails,
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
            return self._success(data)

        except json.JSONDecodeError as exc:
            return self._failure(code="JSON_PARSE_ERROR", message=f"Failed to parse content JSON: {exc}")
        except Exception as exc:
            return self._failure(code="LLM_ERROR", message=str(exc))

    def _build_user_prompt(
        self,
        *,
        profile: dict,
        topics: dict,
        titles_data: dict,
        hot_topics: dict,
        selected_evidence: list[dict],
        evidence_summaries: dict[str, str],
        citation_guardrails: dict[str, bool],
    ) -> str:
        tone = profile.get("tone", "neutral")
        domain = profile.get("domain", "unknown")
        keywords = profile.get("keywords", [])

        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        hot_list = hot_topics.get("hot_topics", []) if isinstance(hot_topics, dict) else []
        sorted_topics = sorted(topic_list, key=lambda item: item.get("estimated_appeal", 0), reverse=True)
        top_topic = sorted_topics[0] if sorted_topics else {}

        prompt_parts = [
            "Please write a complete article grounded in the following planning package.",
            "",
            "ACCOUNT",
            json.dumps(
                {
                    "domain": domain,
                    "tone": tone,
                    "keywords": keywords,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "SELECTED TOPIC",
            json.dumps(top_topic, ensure_ascii=False, indent=2),
            "",
            "TITLE CANDIDATES",
            json.dumps(title_list[:4], ensure_ascii=False, indent=2),
            "",
            "HOT TOPICS",
            json.dumps(hot_list[:6], ensure_ascii=False, indent=2),
            "",
            "EVIDENCE SUMMARIES",
            json.dumps(evidence_summaries, ensure_ascii=False, indent=2),
            "",
            "SELECTED EVIDENCE",
            json.dumps(selected_evidence[:10], ensure_ascii=False, indent=2),
            "",
            "CITATION GUARDRAILS",
            json.dumps(citation_guardrails, ensure_ascii=False, indent=2),
            "",
            "REQUIREMENTS",
            "- Output strict JSON only.",
            "- Use the highest-scoring title unless a lower one better matches the topic_kind and evidence.",
            "- Ground concrete repo names and paper names in SELECTED EVIDENCE only.",
            "- Keep the structure readable and evidence-aware.",
        ]
        return "\n".join(prompt_parts)

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

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._success(
            {
                "content_markdown": "# Article generation failed\n\nThe content writer failed and no grounded article could be produced.",
                "word_count": 0,
                "structure": {"sections": []},
                "tags": [],
            }
        )
