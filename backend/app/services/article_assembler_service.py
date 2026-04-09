"""Structured article assembly and content result normalization."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


class ArticleAssemblerService:
    """Assemble section drafts into article content and normalize legacy outputs."""

    def assemble_article(
        self,
        *,
        outline_plan: dict[str, Any] | None,
        section_drafts: dict[str, Any] | list[dict[str, Any]] | None,
        titles: dict[str, Any] | None = None,
        topics: dict[str, Any] | None = None,
        existing_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        outline_plan = outline_plan if isinstance(outline_plan, dict) else {}
        existing_content = existing_content if isinstance(existing_content, dict) else {}
        normalized_sections = self._normalize_section_drafts(section_drafts)

        selected_title = self.extract_selected_title(titles, existing_content)
        selected_topic = self.extract_selected_topic(topics, titles, existing_content)
        title_candidates = self.extract_title_candidates(titles, existing_content)

        body_parts: list[str] = []
        if selected_title:
            body_parts.append(f"# {selected_title}")

        opening_hook = self._clean_text(
            outline_plan.get("opening_hook") or outline_plan.get("article_goal")
        )
        if opening_hook:
            body_parts.append(opening_hook)

        structure_sections: list[dict[str, Any]] = []
        for section in normalized_sections:
            heading = self._clean_text(section.get("heading")) or "Untitled Section"
            section_body = self._clean_text(section.get("content_markdown"))
            section_summary = self._clean_text(section.get("summary"))

            if heading:
                body_parts.append(f"## {heading}")
            if section_body:
                body_parts.append(section_body)
            elif section_summary:
                body_parts.append(section_summary)

            structure_sections.append(
                {
                    "section_id": section.get("section_id") or section.get("id"),
                    "heading": heading,
                    "summary": section_summary,
                    "word_count": self.count_words(section_body or section_summary or ""),
                    "evidence_refs": self._normalize_string_list(section.get("evidence_refs")),
                }
            )

        ending_cta = self._clean_text(outline_plan.get("ending_cta"))
        if ending_cta:
            body_parts.append(f"## Closing\n{ending_cta}")

        content_markdown = "\n\n".join(part for part in body_parts if part).strip()
        summary = (
            self._clean_text(existing_content.get("summary"))
            or self._build_summary_from_outline(outline_plan)
            or self._build_summary_from_sections(normalized_sections)
            or self._summarize_markdown(content_markdown)
        )
        tags = self._normalize_tags(existing_content.get("tags"), selected_topic, outline_plan)

        return {
            "selected_topic": selected_topic,
            "title_candidates": title_candidates,
            "selected_title": selected_title,
            "summary": summary,
            "content_markdown": content_markdown,
            "content_html": existing_content.get("content_html"),
            "structure": {"sections": structure_sections},
            "tags": tags,
            "word_count": self.count_words(content_markdown),
            "article_goal": self._clean_text(outline_plan.get("article_goal")),
            "target_reader_takeaway": self._clean_text(outline_plan.get("target_reader_takeaway")),
            "opening_hook": opening_hook,
            "ending_cta": ending_cta,
        }

    def normalize_result_data(self, result_data: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(result_data, dict):
            return {}

        normalized = deepcopy(result_data)
        normalized["assembled_article"] = self.extract_assembled_article_payload(normalized)
        normalized["content"] = self.extract_article_payload(normalized)

        pipeline = normalized.get("content_pipeline")
        if not isinstance(pipeline, dict):
            pipeline = {}
        pipeline.setdefault("version", "phase6-structured-v1")
        pipeline.setdefault(
            "used_structured_pipeline",
            bool(normalized.get("outline_plan") or normalized.get("section_drafts")),
        )
        pipeline.setdefault("fallback_to_content_writer", False)
        pipeline.setdefault("rewrite_attempted", bool(normalized.get("rewrite_result")))
        pipeline.setdefault("rewrite_used", bool(self._extract_rewrite_content(normalized.get("rewrite_result"))))
        pipeline.setdefault(
            "rewrite_failed",
            bool(
                isinstance(normalized.get("rewrite_result"), dict)
                and normalized.get("rewrite_result", {}).get("rewrite_failed")
            ),
        )
        pipeline.setdefault("degraded", bool(pipeline.get("fallback_to_content_writer")))
        normalized["content_pipeline"] = pipeline
        return normalized

    def extract_assembled_article_payload(self, result_data: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(result_data, dict):
            return self._empty_payload()

        existing_content = result_data.get("content")
        if not isinstance(existing_content, dict):
            existing_content = {}

        assembled_article = result_data.get("assembled_article")
        if isinstance(assembled_article, dict):
            content = {**existing_content, **assembled_article}
        elif result_data.get("outline_plan") or result_data.get("section_drafts"):
            content = self.assemble_article(
                outline_plan=result_data.get("outline_plan"),
                section_drafts=result_data.get("section_drafts"),
                titles=result_data.get("titles"),
                topics=result_data.get("topics"),
                existing_content=existing_content,
            )
        else:
            content = dict(existing_content)

        selected_title = self.extract_selected_title(result_data.get("titles"), content)
        selected_topic = self.extract_selected_topic(
            result_data.get("topics"), result_data.get("titles"), content
        )
        title_candidates = self.extract_title_candidates(result_data.get("titles"), content)
        content_markdown = self._clean_text(
            content.get("content_markdown") or content.get("content")
        )
        summary = (
            self._clean_text(content.get("summary"))
            or self._summarize_markdown(content_markdown)
        )
        structure = self._normalize_structure(
            content.get("structure"),
            result_data.get("outline_plan"),
            result_data.get("section_drafts"),
        )
        tags = self._normalize_tags(content.get("tags"), selected_topic, result_data.get("outline_plan"))

        return {
            "selected_topic": selected_topic,
            "title_candidates": title_candidates,
            "selected_title": selected_title,
            "summary": summary,
            "content_markdown": content_markdown,
            "content_html": content.get("content_html"),
            "structure": structure,
            "tags": tags,
            "word_count": content.get("word_count") or self.count_words(content_markdown),
        }

    def extract_article_payload(self, result_data: dict[str, Any] | None) -> dict[str, Any]:
        assembled = self.extract_assembled_article_payload(result_data)
        if not isinstance(result_data, dict):
            return assembled

        rewrite_content = self._extract_rewrite_content(result_data.get("rewrite_result"))
        if not rewrite_content:
            return assembled

        revised = dict(assembled)
        revised["content_markdown"] = rewrite_content
        revised_html = self._clean_text(
            (result_data.get("rewrite_result") or {}).get("revised_content_html")
            or (result_data.get("rewrite_result") or {}).get("content_html")
        )
        if revised_html:
            revised["content_html"] = revised_html
        revised["word_count"] = self.count_words(rewrite_content)
        return revised

    def extract_selected_title(
        self, titles_data: dict[str, Any] | None, content: dict[str, Any] | None = None
    ) -> str:
        content = content if isinstance(content, dict) else {}
        titles_data = titles_data if isinstance(titles_data, dict) else {}
        title = (
            self._clean_text(content.get("selected_title"))
            or self._clean_text(content.get("title"))
            or self._clean_text(titles_data.get("selected_title"))
        )
        if title:
            return title

        candidates = self.extract_title_candidates(titles_data, content)
        return candidates[0] if candidates else "Untitled"

    def extract_selected_topic(
        self,
        topics_data: dict[str, Any] | None,
        titles_data: dict[str, Any] | None = None,
        content: dict[str, Any] | None = None,
    ) -> str:
        topics_data = topics_data if isinstance(topics_data, dict) else {}
        titles_data = titles_data if isinstance(titles_data, dict) else {}
        content = content if isinstance(content, dict) else {}

        topic = (
            self._clean_text(content.get("selected_topic"))
            or self._clean_text(topics_data.get("selected_topic"))
            or self._clean_text(titles_data.get("selected_topic"))
        )
        if topic:
            return topic

        topic_items = topics_data.get("topics")
        if isinstance(topic_items, list):
            for item in topic_items:
                if isinstance(item, dict):
                    candidate = self._clean_text(item.get("title"))
                    if candidate:
                        return candidate
        return ""

    def extract_title_candidates(
        self, titles_data: dict[str, Any] | None, content: dict[str, Any] | None = None
    ) -> list[str]:
        content = content if isinstance(content, dict) else {}
        titles_data = titles_data if isinstance(titles_data, dict) else {}

        content_candidates = content.get("title_candidates")
        if isinstance(content_candidates, list):
            normalized = [self._title_candidate_to_text(item) for item in content_candidates]
            return [item for item in normalized if item]

        candidates = titles_data.get("candidates")
        if isinstance(candidates, list):
            normalized = [self._title_candidate_to_text(item) for item in candidates]
            normalized = [item for item in normalized if item]
            if normalized:
                return normalized

        title_items = titles_data.get("titles")
        if isinstance(title_items, list):
            normalized = [self._title_candidate_to_text(item) for item in title_items]
            return [item for item in normalized if item]

        selected_title = self._clean_text(content.get("selected_title")) or self._clean_text(
            titles_data.get("selected_title")
        )
        return [selected_title] if selected_title else []

    def count_words(self, text: str) -> int:
        if not text:
            return 0
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        english = len(re.findall(r"[A-Za-z0-9_]+", text))
        return chinese + english

    def _empty_payload(self) -> dict[str, Any]:
        return {
            "selected_topic": "",
            "title_candidates": [],
            "selected_title": "Untitled",
            "summary": "",
            "content_markdown": "",
            "content_html": None,
            "structure": {"sections": []},
            "tags": [],
            "word_count": 0,
        }

    def _normalize_section_drafts(
        self, section_drafts: dict[str, Any] | list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        source = section_drafts
        if isinstance(section_drafts, dict):
            source = section_drafts.get("section_drafts") or section_drafts.get("sections") or []
        if not isinstance(source, list):
            return []

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(source):
            if not isinstance(item, dict):
                continue
            section_id = item.get("section_id") or item.get("id") or f"s{index + 1}"
            heading = self._clean_text(item.get("heading") or item.get("title")) or f"Section {index + 1}"
            normalized.append(
                {
                    "section_id": section_id,
                    "id": section_id,
                    "heading": heading,
                    "summary": self._clean_text(item.get("summary")),
                    "content_markdown": self._clean_text(
                        item.get("content_markdown") or item.get("content")
                    ),
                    "word_count": item.get("word_count"),
                    "evidence_refs": self._normalize_string_list(item.get("evidence_refs")),
                }
            )
        return normalized

    def _normalize_structure(
        self,
        structure: Any,
        outline_plan: Any,
        section_drafts: Any,
    ) -> dict[str, Any]:
        if isinstance(structure, dict) and isinstance(structure.get("sections"), list):
            return structure

        normalized_sections = self._normalize_section_drafts(section_drafts)
        if normalized_sections:
            return {
                "sections": [
                    {
                        "section_id": item.get("section_id"),
                        "heading": item.get("heading"),
                        "summary": item.get("summary"),
                    }
                    for item in normalized_sections
                ]
            }

        if isinstance(outline_plan, dict) and isinstance(outline_plan.get("sections"), list):
            sections: list[dict[str, Any]] = []
            for index, item in enumerate(outline_plan.get("sections", [])):
                if not isinstance(item, dict):
                    continue
                sections.append(
                    {
                        "section_id": item.get("section_id") or item.get("id") or f"s{index + 1}",
                        "heading": self._clean_text(item.get("heading") or item.get("title"))
                        or f"Section {index + 1}",
                        "summary": self._clean_text(
                            item.get("purpose") or item.get("summary") or item.get("goal")
                        ),
                    }
                )
            return {"sections": sections}

        return {"sections": []}

    def _build_summary_from_outline(self, outline_plan: dict[str, Any]) -> str:
        parts = [
            self._clean_text(outline_plan.get("article_goal")),
            self._clean_text(outline_plan.get("target_reader_takeaway")),
        ]
        summary = " ".join(part for part in parts if part).strip()
        return summary[:240]

    def _build_summary_from_sections(self, section_drafts: list[dict[str, Any]]) -> str:
        fragments: list[str] = []
        for item in section_drafts[:3]:
            summary = self._clean_text(item.get("summary"))
            if summary:
                fragments.append(summary)
        return " ".join(fragments)[:240]

    def _summarize_markdown(self, content_markdown: str) -> str:
        text = self._clean_text(re.sub(r"^#+\s*", "", content_markdown, flags=re.MULTILINE))
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text[:220].strip()

    def _normalize_tags(self, raw_tags: Any, selected_topic: str, outline_plan: Any) -> list[str]:
        tags = self._normalize_string_list(raw_tags)
        if tags:
            return tags[:6]
        fallback: list[str] = []
        if selected_topic:
            fallback.append(selected_topic[:24])
        if isinstance(outline_plan, dict):
            for value in outline_plan.get("content_lanes", []) if isinstance(outline_plan.get("content_lanes"), list) else []:
                if isinstance(value, str):
                    fallback.append(value[:24])
        unique: list[str] = []
        for item in fallback:
            if item and item not in unique:
                unique.append(item)
        return unique[:6]

    def _extract_rewrite_content(self, rewrite_result: Any) -> str:
        if not isinstance(rewrite_result, dict):
            return ""
        if rewrite_result.get("used_rewrite") is False:
            return ""
        return self._clean_text(
            rewrite_result.get("revised_content_markdown")
            or rewrite_result.get("content_markdown")
            or rewrite_result.get("content")
        )

    def _title_candidate_to_text(self, value: Any) -> str | None:
        if isinstance(value, str):
            return self._clean_text(value)
        if isinstance(value, dict):
            return self._clean_text(value.get("text") or value.get("title"))
        return None

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = self._clean_text(item)
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text


article_assembler_service = ArticleAssemblerService()
