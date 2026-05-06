"""Structured article assembly and content result normalization."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from html import escape
from typing import Any

from app.services.reference_digest_service import reference_digest_service


class ArticleAssemblerService:
    """Assemble section drafts into article content and normalize legacy outputs."""

    def to_pretty_json(self, value: Any) -> str:
        """Serialize prompt context as readable JSON for LLM calls."""
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            return json.dumps(str(value), ensure_ascii=False, indent=2)

    def summarize_outline_plan(self, outline_plan: dict[str, Any] | None) -> dict[str, Any]:
        """Build a compact outline summary for downstream prompts."""
        outline_plan = outline_plan if isinstance(outline_plan, dict) else {}
        sections: list[dict[str, Any]] = []
        raw_sections = outline_plan.get("sections")
        if isinstance(raw_sections, list):
            for index, item in enumerate(raw_sections):
                if not isinstance(item, dict):
                    continue
                sections.append(
                    {
                        "section_id": str(item.get("section_id") or item.get("id") or f"s{index + 1}"),
                        "heading": self._clean_text(item.get("heading") or item.get("title"))
                        or f"Section {index + 1}",
                        "purpose": self._clean_text(item.get("purpose") or item.get("goal")),
                        "summary": self._clean_text(item.get("summary")),
                        "key_points": self._normalize_string_list(item.get("key_points")),
                        "tone_hint": self._clean_text(item.get("tone_hint")),
                        "section_transition_hint": self._clean_text(
                            item.get("section_transition_hint") or item.get("transition_hint")
                        ),
                        "evidence_refs": self._normalize_string_list(item.get("evidence_refs")),
                    }
                )

        return {
            "article_goal": self._clean_text(outline_plan.get("article_goal")),
            "why_this_topic": self._clean_text(outline_plan.get("why_this_topic")),
            "strategic_angle": self._clean_text(outline_plan.get("strategic_angle")),
            "reference_basis": self._clean_text(outline_plan.get("reference_basis")),
            "target_reader": self._clean_text(outline_plan.get("target_reader")),
            "content_lane": self._clean_text(outline_plan.get("content_lane")),
            "target_reader_takeaway": self._clean_text(outline_plan.get("target_reader_takeaway")),
            "opening_hook": self._clean_text(outline_plan.get("opening_hook")),
            "emotional_arc": self._clean_text(outline_plan.get("emotional_arc")),
            "ending_cta": self._clean_text(outline_plan.get("ending_cta")),
            "estimated_word_count": int(outline_plan.get("estimated_word_count") or 0),
            "summary": self._clean_text(outline_plan.get("summary")),
            "sections": sections,
        }

    def summarize_section_drafts(
        self,
        section_drafts: dict[str, Any] | list[dict[str, Any]] | None,
        *,
        content_preview_chars: int = 220,
    ) -> list[dict[str, Any]]:
        """Build a compact section summary for review and rewrite prompts."""
        normalized_sections = self._normalize_section_drafts(section_drafts)
        return [
            {
                "section_id": item.get("section_id"),
                "heading": item.get("heading"),
                "summary": item.get("summary"),
                "word_count": int(item.get("word_count") or self.count_words(item.get("content_markdown") or "")),
                "evidence_refs": self._normalize_string_list(item.get("evidence_refs")),
                "content_preview": self._clip_text(item.get("content_markdown"), content_preview_chars),
            }
            for item in normalized_sections
        ]

    def summarize_review_result(
        self,
        review_result: dict[str, Any] | None,
        *,
        issue_limit: int = 8,
    ) -> dict[str, Any]:
        """Compact reviewer output for rewrite prompts and diagnostics."""
        review_result = review_result if isinstance(review_result, dict) else {}
        issues = review_result.get("issues") if isinstance(review_result.get("issues"), list) else []
        normalized_issues: list[dict[str, Any]] = []
        for item in issues[:issue_limit]:
            if not isinstance(item, dict):
                continue
            normalized_issues.append(
                {
                    "code": self._clean_text(item.get("code")) or "issue",
                    "severity": self._clean_text(item.get("severity")) or "medium",
                    "section_id": self._clean_text(item.get("section_id") or item.get("location")),
                    "message": self._clean_text(item.get("message") or item.get("description")),
                    "suggestion": self._clean_text(item.get("suggestion")),
                    "evidence_excerpt": self._clean_text(item.get("evidence_excerpt")),
                }
            )
        return {
            "reviewer": self._clean_text(review_result.get("reviewer")),
            "passed": review_result.get("passed"),
            "summary": self._clean_text(review_result.get("summary")),
            "rewrite_suggestions": self._normalize_string_list(review_result.get("rewrite_suggestions")),
            "issues": normalized_issues,
        }

    def build_topic_anchors(self, *values: Any) -> list[str]:
        """Extract lightweight anchor phrases from topic/title text for drift checks."""
        anchors: list[str] = []
        seen: set[str] = set()
        weak_short_anchors = {
            "为什",
            "为什么",
            "什么",
            "怎么",
            "如何",
            "很多",
            "一些",
            "一个",
            "这种",
            "那种",
            "这个",
            "那个",
            "不是",
            "没有",
            "我们",
            "你们",
            "他们",
            "因为",
            "所以",
            "然后",
            "最后",
            "就是",
        }
        for value in values:
            raw_text = self._clean_text(value)
            parts = [
                re.sub(r"[^\w\u4e00-\u9fff]+", "", part)
                for part in re.split(r"[\s,，。！？、:：;；()（）【】《》“”\"'/-]+", raw_text)
            ]
            normalized_parts = [part for part in parts if len(part) >= 2] or [
                re.sub(r"[^\w\u4e00-\u9fff]+", "", raw_text)
            ]

            for text in normalized_parts:
                if len(text) < 2:
                    continue

                candidates = [text] if len(text) <= 8 else []
                for width in (4, 3, 2, 5, 6):
                    if len(text) < width:
                        continue
                    for index in range(len(text) - width + 1):
                        candidates.append(text[index:index + width])

                added_for_text = 0
                for candidate in candidates:
                    cleaned = candidate.strip()
                    if len(cleaned) < 2:
                        continue
                    if cleaned in seen:
                        continue
                    if cleaned.isdigit():
                        continue
                    if len(cleaned) <= 3 and cleaned in weak_short_anchors:
                        continue
                    seen.add(cleaned)
                    anchors.append(cleaned)
                    added_for_text += 1
                    if added_for_text >= 24:
                        break
        return anchors[:48]

    def text_matches_topic(
        self,
        text: Any,
        *,
        selected_topic: Any,
        selected_title: Any,
    ) -> bool:
        """Heuristic guard against large topic drift in generated content."""
        haystack = re.sub(r"\s+", "", self._clean_text(text)).lower()
        if not haystack:
            return False

        anchors = self.build_topic_anchors(selected_topic, selected_title)
        if not anchors:
            return True

        strong_matches = [
            anchor for anchor in anchors if len(anchor) >= 4 and anchor.lower() in haystack
        ]
        if strong_matches:
            return True

        medium_matches = {
            anchor for anchor in anchors if len(anchor) in {2, 3} and anchor.lower() in haystack
        }
        return len(medium_matches) >= 2

    def build_reference_source_context(
        self,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        *,
        limit: int = 3,
    ) -> dict[str, Any]:
        """Build a stable, lightweight reference style summary for content agents."""
        digest = reference_digest_service.build_reference_digest(
            account_context=account_context,
            ops_context=ops_context,
            limit=limit,
        )
        return {
            "source_count": digest.get("source_count", 0),
            "selected_source_ids": digest.get("selected_source_ids", []),
            "preferred_source_names": digest.get("preferred_source_names", []),
            "style_takeaways": digest.get("style_takeaways", []),
            "structure_takeaways": digest.get("structure_takeaways", []),
            "usage_rules": digest.get("usage_rules", []),
            "sources": digest.get("source_digests", []),
        }

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
            last_body_part = body_parts[-1] if body_parts else ""
            if ending_cta not in last_body_part:
                body_parts.append(ending_cta)

        content_markdown = "\n\n".join(part for part in body_parts if part).strip()
        content_html = self.ensure_content_html(existing_content.get("content_html"), content_markdown)
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
            "content_html": content_html,
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
        content_html = self.ensure_content_html(content.get("content_html"), content_markdown)
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
            "content_html": content_html,
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
        revised_html = self.ensure_content_html(
            (result_data.get("rewrite_result") or {}).get("revised_content_html")
            or (result_data.get("rewrite_result") or {}).get("content_html"),
            rewrite_content,
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

    def ensure_content_html(self, content_html: Any, content_markdown: Any) -> str | None:
        html = self._clean_text(content_html)
        if html:
            return html

        markdown = self._clean_text(content_markdown)
        if not markdown:
            return None

        return self._markdown_to_html(markdown)

    def _markdown_to_html(self, markdown: str) -> str:
        normalized = markdown.replace("\r\n", "\n").strip()
        if not normalized:
            return ""

        blocks: list[str] = []
        paragraph_lines: list[str] = []
        list_items: list[str] = []
        list_tag: str | None = None

        def flush_paragraph() -> None:
            if not paragraph_lines:
                return
            blocks.append(
                f"<p>{'<br/>'.join(self._render_inline_markdown(line) for line in paragraph_lines)}</p>"
            )
            paragraph_lines.clear()

        def flush_list() -> None:
            nonlocal list_tag
            if not list_items or not list_tag:
                return
            blocks.append(
                f"<{list_tag}>"
                + "".join(f"<li>{item}</li>" for item in list_items)
                + f"</{list_tag}>"
            )
            list_items.clear()
            list_tag = None

        for raw_line in normalized.split("\n"):
            line = raw_line.strip()
            if not line:
                flush_paragraph()
                flush_list()
                continue

            heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
            if heading_match:
                flush_paragraph()
                flush_list()
                level = len(heading_match.group(1))
                blocks.append(
                    f"<h{level}>{self._render_inline_markdown(heading_match.group(2))}</h{level}>"
                )
                continue

            unordered_match = re.match(r"^[-*]\s+(.+)$", line)
            ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
            if unordered_match or ordered_match:
                flush_paragraph()
                next_tag = "ul" if unordered_match else "ol"
                if list_tag and list_tag != next_tag:
                    flush_list()
                list_tag = next_tag
                list_items.append(
                    self._render_inline_markdown(
                        (unordered_match or ordered_match).group(1)  # type: ignore[union-attr]
                    )
                )
                continue

            flush_list()
            paragraph_lines.append(line)

        flush_paragraph()
        flush_list()
        return "".join(blocks)

    def _render_inline_markdown(self, text: str) -> str:
        rendered = escape(text, quote=False)
        rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
        rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
        rendered = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", rendered)
        return rendered

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

    def _normalize_reference_sources(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata_json") if isinstance(item.get("metadata_json"), dict) else {}
            preview = self._clean_text(item.get("preview") or metadata.get("preview"))
            source_value = self._clean_text(item.get("source_value"))
            if not preview and source_value:
                preview = source_value

            notes = self._clip_text(item.get("notes"), 220)
            normalized.append(
                {
                    "id": self._clean_text(item.get("id")),
                    "name": self._clean_text(item.get("name")) or "Unnamed reference",
                    "source_type": self._clean_text(item.get("source_type")) or "reference",
                    "sync_status": self._clean_text(item.get("sync_status")) or "unknown",
                    "article_count": int(item.get("article_count") or 0),
                    "resolved_title": self._clip_text(item.get("resolved_title") or metadata.get("resolved_title"), 120),
                    "notes": notes,
                    "preview": self._clip_text(preview, 260),
                    "style_clues": self._clip_text(item.get("style_clues") or notes, 180),
                }
            )
        return normalized

    def _prioritize_reference_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not sources:
            return []

        preferred_index = {source_id: index for index, source_id in enumerate(preferred_ids)}

        def _sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
            item_id = self._clean_text(item.get("id"))
            is_preferred = 0 if item_id in preferred_index else 1
            preferred_order = preferred_index.get(item_id, 999)
            return (is_preferred, preferred_order, self._clean_text(item.get("name")))

        sorted_sources = sorted(sources, key=_sort_key)
        return sorted_sources[:limit]

    def _clip_text(self, value: Any, limit: int) -> str:
        text = self._clean_text(value)
        if len(text) <= limit:
            return text
        clipped = text[: max(limit - 3, 0)].rstrip()
        return f"{clipped}..."

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text


article_assembler_service = ArticleAssemblerService()
