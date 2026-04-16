"""Post-process agent for WeChat-ready draft finishing."""

from __future__ import annotations

import re
from html import escape
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.services.article_assembler_service import article_assembler_service


class PostProcessAgent(BaseAgent):
    """Polish, format, and suggest images after the draft quality gate passes."""

    agent_id = "post_process_agent"
    name = "Post-process Agent"
    description = "Prepare a passed draft for human review with WeChat formatting and image placement suggestions."

    input_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "object"},
            "assembled_article": {"type": "object"},
            "rewrite_result": {"type": "object"},
            "draft_quality_gate": {"type": "object"},
            "outline_plan": {"type": "object"},
            "section_drafts": {"type": "object"},
            "titles": {"type": "object"},
            "topics": {"type": "object"},
            "account_context": {"type": "object"},
            "source_candidates": {"type": "array"},
        },
        "required": ["draft_quality_gate"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "used_post_process": {"type": "boolean"},
            "layout_template": {"type": "object"},
            "template_options": {"type": "array", "items": {"type": "object"}},
            "layout_blocks": {"type": "array", "items": {"type": "object"}},
            "final_content_markdown": {"type": "string"},
            "final_content_html": {"type": "string"},
            "polishing_summary": {"type": "string"},
            "layout_notes": {"type": "array", "items": {"type": "string"}},
            "image_slots": {"type": "array", "items": {"type": "object"}},
            "cover_image_prompt": {"type": "string"},
            "wechat_publish_format": {"type": "object"},
        },
    }

    supported_skills: list[str] = []

    LAYOUT_TEMPLATES: tuple[dict[str, Any], ...] = (
        {
            "id": "insight_column",
            "name": "深度观点专栏",
            "scenario": "适合判断、复盘、行业观察和偏观点型内容。",
            "summary": "用强标题、导读卡片、分节编号和结尾行动框，把文章从新闻稿变成有判断的公众号专栏。",
            "accent_color": "#0f766e",
            "accent_soft": "#ccfbf1",
            "hero_background": "linear-gradient(135deg,#0f766e 0%,#0b1220 100%)",
            "body_background": "#fffaf3",
            "surface": "#ffffff",
            "heading_style": "numbered_bar",
            "recommended_for": ["观点", "复盘", "运营观察", "行业判断"],
            "style_keywords": ["克制", "有判断", "移动端长读"],
        },
        {
            "id": "briefing_digest",
            "name": "资讯快报解读",
            "scenario": "适合最新资讯、多个新闻源、技术动态和快读型内容。",
            "summary": "先给要点，再展开影响，视觉上像一份可收藏的今日简报，而不是传统新闻稿。",
            "accent_color": "#2563eb",
            "accent_soft": "#dbeafe",
            "hero_background": "linear-gradient(135deg,#1d4ed8 0%,#38bdf8 100%)",
            "body_background": "#f8fbff",
            "surface": "#ffffff",
            "heading_style": "tag_bar",
            "recommended_for": ["快讯", "最新资讯", "技术动态", "多来源摘要"],
            "style_keywords": ["信息密度", "清晰层级", "快速扫读"],
        },
        {
            "id": "warm_story",
            "name": "故事化陪伴稿",
            "scenario": "适合个人成长、情绪洞察、经验分享和轻口语内容。",
            "summary": "用柔和开场、留白、重点金句和温暖结尾，让文章更像公众号陪伴型长文。",
            "accent_color": "#c2410c",
            "accent_soft": "#ffedd5",
            "hero_background": "linear-gradient(135deg,#9a3412 0%,#fdba74 100%)",
            "body_background": "#fff7ed",
            "surface": "#fffdf8",
            "heading_style": "soft_marker",
            "recommended_for": ["成长", "情绪", "经验分享", "陪伴型内容"],
            "style_keywords": ["温暖", "松弛", "故事感"],
        },
        {
            "id": "operator_playbook",
            "name": "方法论手册",
            "scenario": "适合步骤、清单、策略、工具方法和行动指南。",
            "summary": "把正文整理成操作手册式版面，突出步骤、提示框和行动清单，方便读者保存复用。",
            "accent_color": "#4338ca",
            "accent_soft": "#e0e7ff",
            "hero_background": "linear-gradient(135deg,#312e81 0%,#6366f1 100%)",
            "body_background": "#f8f7ff",
            "surface": "#ffffff",
            "heading_style": "playbook_step",
            "recommended_for": ["方法论", "教程", "清单", "工作流"],
            "style_keywords": ["可执行", "结构清楚", "保存价值"],
        },
    )

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        gate = input_data.get("draft_quality_gate") if isinstance(input_data.get("draft_quality_gate"), dict) else {}
        if gate.get("passed") is False:
            return self._success(
                {
                    "used_post_process": False,
                    "post_process_skipped": True,
                    "skip_reason": "draft_quality_gate_blocked",
                    "layout_template": None,
                    "template_options": self._template_options(),
                    "layout_blocks": [],
                    "final_content_markdown": "",
                    "final_content_html": "",
                    "polishing_summary": "Skipped post-processing because the draft quality gate did not pass.",
                    "layout_notes": [],
                    "image_slots": [],
                    "cover_image_prompt": "",
                    "wechat_publish_format": {},
                }
            )

        article = article_assembler_service.extract_article_payload(
            {
                "content": input_data.get("content"),
                "assembled_article": input_data.get("assembled_article"),
                "rewrite_result": input_data.get("rewrite_result"),
                "titles": input_data.get("titles"),
                "topics": input_data.get("topics"),
                "outline_plan": input_data.get("outline_plan"),
                "section_drafts": input_data.get("section_drafts"),
            }
        )
        title = str(article.get("selected_title") or "Untitled").strip()
        content_markdown = str(article.get("content_markdown") or "").strip()
        account_context = input_data.get("account_context") if isinstance(input_data.get("account_context"), dict) else {}
        outline_plan = input_data.get("outline_plan") if isinstance(input_data.get("outline_plan"), dict) else {}
        template = self._select_template(
            article=article,
            account_context=account_context,
            outline_plan=outline_plan,
            source_candidates=input_data.get("source_candidates") if isinstance(input_data.get("source_candidates"), list) else [],
        )
        final_markdown = self._format_markdown(title, content_markdown)
        layout_blocks = self._parse_markdown(final_markdown, title=title)
        final_html = self._render_wechat_html(
            title=title,
            summary=str(article.get("summary") or "").strip(),
            blocks=layout_blocks,
            template=template,
            account_context=account_context,
            outline_plan=outline_plan,
        )
        headings = self._extract_headings(final_markdown)
        image_slots = self._build_image_slots(
            title=title,
            headings=headings,
            source_candidates=input_data.get("source_candidates") if isinstance(input_data.get("source_candidates"), list) else [],
            template=template,
        )
        digest = self._digest(article, final_markdown)

        return self._success(
            {
                "used_post_process": True,
                "layout_template": self._public_template(template),
                "template_options": self._template_options(),
                "layout_blocks": self._public_blocks(layout_blocks),
                "final_content_markdown": final_markdown,
                "final_content_html": final_html,
                "polishing_summary": (
                    f"Applied the {template['name']} template with mobile-first spacing, "
                    "section hierarchy, highlight callouts, image placement hints, and WeChat inline HTML."
                ),
                "layout_notes": self._layout_notes(template),
                "image_slots": image_slots,
                "cover_image_prompt": self._cover_prompt(title, account_context, template),
                "wechat_publish_format": {
                    "title": title[:64],
                    "digest": digest,
                    "template_id": template["id"],
                    "template_name": template["name"],
                    "content_format": "wechat_inline_html",
                    "recommended_preview_image_slot": image_slots[0]["slot_id"] if image_slots else None,
                    "review_checklist": [
                        "确认标题、摘要与正文判断一致。",
                        "确认事实、来源和引用都可追溯。",
                        "确认图片版权、清晰度和公众号封面裁切效果。",
                    ],
                    "needs_human_image_selection": True,
                    "ready_for_review": True,
                },
            }
        )

    def _template_options(self) -> list[dict[str, Any]]:
        return [self._public_template(template) for template in self.LAYOUT_TEMPLATES]

    def _public_template(self, template: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": template["id"],
            "name": template["name"],
            "scenario": template["scenario"],
            "summary": template["summary"],
            "accent_color": template["accent_color"],
            "recommended_for": list(template.get("recommended_for", [])),
            "style_keywords": list(template.get("style_keywords", [])),
        }

    def _select_template(
        self,
        *,
        article: dict[str, Any],
        account_context: dict[str, Any],
        outline_plan: dict[str, Any],
        source_candidates: list[Any],
    ) -> dict[str, Any]:
        text = " ".join(
            str(value or "")
            for value in (
                article.get("selected_topic"),
                article.get("selected_title"),
                article.get("summary"),
                outline_plan.get("content_lane"),
                outline_plan.get("article_goal"),
                account_context.get("positioning"),
                account_context.get("content_strategy"),
            )
        ).lower()
        source_count = len(source_candidates)
        word_count = int(article.get("word_count") or article_assembler_service.count_words(str(article.get("content_markdown") or "")))

        scores = {template["id"]: 0 for template in self.LAYOUT_TEMPLATES}
        if source_count >= 2 or any(keyword in text for keyword in ("资讯", "新闻", "快讯", "动态", "latest", "news", "brief")):
            scores["briefing_digest"] += 4
        if any(keyword in text for keyword in ("方法", "步骤", "清单", "工具", "教程", "workflow", "playbook", "how to")):
            scores["operator_playbook"] += 4
        if any(keyword in text for keyword in ("成长", "情绪", "故事", "陪伴", "经验", "个人", "self", "confidence")):
            scores["warm_story"] += 4
        if any(keyword in text for keyword in ("判断", "复盘", "洞察", "观点", "行业", "策略", "analysis", "operator")):
            scores["insight_column"] += 4
        if word_count >= 900:
            scores["insight_column"] += 1
            scores["operator_playbook"] += 1
        if word_count <= 650:
            scores["briefing_digest"] += 1

        selected_id = max(scores, key=lambda key: (scores[key], -self._template_index(key)))
        return next(template for template in self.LAYOUT_TEMPLATES if template["id"] == selected_id)

    def _template_index(self, template_id: str) -> int:
        for index, template in enumerate(self.LAYOUT_TEMPLATES):
            if template["id"] == template_id:
                return index
        return 999

    def _format_markdown(self, title: str, content_markdown: str) -> str:
        text = (content_markdown or "").replace("\r\n", "\n").strip()
        if title and not re.match(r"^#\s+", text):
            text = f"# {title}\n\n{text}" if text else f"# {title}"
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"(?<!\n)\n(?!\n|#|[-*] |\d+\. |>|\s*$)", "\n\n", text)
        return text.strip()

    def _parse_markdown(self, markdown: str, *, title: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        paragraph_lines: list[str] = []
        list_items: list[str] = []
        list_type: str | None = None

        def flush_paragraph() -> None:
            if not paragraph_lines:
                return
            paragraph = " ".join(line.strip() for line in paragraph_lines if line.strip()).strip()
            paragraph_lines.clear()
            for chunk in self._split_long_paragraph(paragraph):
                blocks.append({"type": "paragraph", "text": chunk})

        def flush_list() -> None:
            nonlocal list_type
            if not list_items:
                return
            blocks.append({"type": "list", "ordered": list_type == "ordered", "items": list_items.copy()})
            list_items.clear()
            list_type = None

        for raw_line in markdown.split("\n"):
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
                text = heading_match.group(2).strip()
                if level == 1 and self._same_title(text, title):
                    continue
                blocks.append({"type": "heading", "level": level, "text": text})
                continue

            if re.match(r"^---+$", line):
                flush_paragraph()
                flush_list()
                blocks.append({"type": "divider"})
                continue

            quote_match = re.match(r"^>\s*(.+)$", line)
            if quote_match:
                flush_paragraph()
                flush_list()
                blocks.append({"type": "quote", "text": quote_match.group(1).strip()})
                continue

            unordered_match = re.match(r"^[-*]\s+(.+)$", line)
            ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
            if unordered_match or ordered_match:
                flush_paragraph()
                next_type = "unordered" if unordered_match else "ordered"
                if list_type and list_type != next_type:
                    flush_list()
                list_type = next_type
                list_items.append((unordered_match or ordered_match).group(1).strip())  # type: ignore[union-attr]
                continue

            flush_list()
            paragraph_lines.append(line)

        flush_paragraph()
        flush_list()
        return blocks

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        if len(paragraph) <= 180:
            return [paragraph]
        parts = [part.strip() for part in re.split(r"(?<=[。！？.!?])", paragraph) if part.strip()]
        chunks: list[str] = []
        current = ""
        for part in parts or [paragraph]:
            if len(current) + len(part) <= 180:
                current = f"{current}{part}".strip()
                continue
            if current:
                chunks.append(current)
            current = part
        if current:
            chunks.append(current)
        return chunks or [paragraph]

    def _render_wechat_html(
        self,
        *,
        title: str,
        summary: str,
        blocks: list[dict[str, Any]],
        template: dict[str, Any],
        account_context: dict[str, Any],
        outline_plan: dict[str, Any],
    ) -> str:
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        surface = template["surface"]
        body_background = template["body_background"]
        account_name = str(account_context.get("account_name") or account_context.get("name") or "HotClaw").strip()
        lead_text = self._lead_text(summary, blocks)
        read_minutes = self._read_minutes(blocks)
        ending_cta = str(outline_plan.get("ending_cta") or "").strip()
        rendered_blocks = self._render_blocks(blocks, template=template)

        html_parts = [
            (
                f'<section data-hotclaw-template="{escape(str(template["id"]), quote=True)}" '
                f'style="max-width:677px;margin:0 auto;background:{body_background};'
                'padding:0 0 28px 0;color:#1f2937;font-family:-apple-system,BlinkMacSystemFont,'
                '\'PingFang SC\',\'Microsoft YaHei\',\'Helvetica Neue\',Arial,sans-serif;">'
            ),
            (
                f'<section style="margin:0 0 22px 0;padding:34px 28px 30px;border-radius:0 0 28px 28px;'
                f'background:{template["hero_background"]};color:#fff;">'
                f'<p style="margin:0 0 14px 0;font-size:13px;letter-spacing:2px;opacity:.82;">'
                f'{escape(account_name)} · {escape(str(template["name"]))}</p>'
                f'<h1 style="margin:0;font-size:28px;line-height:1.28;font-weight:800;letter-spacing:-.4px;">'
                f'{self._inline(title)}</h1>'
                f'<p style="margin:18px 0 0 0;font-size:13px;line-height:1.8;opacity:.82;">'
                f'预计阅读 {read_minutes} 分钟 · 已套用公众号排版模板</p>'
                '</section>'
            ),
        ]

        if lead_text:
            html_parts.append(
                f'<section style="margin:0 18px 22px;padding:18px 18px;border-radius:20px;'
                f'background:{surface};border:1px solid {accent_soft};box-shadow:0 8px 24px rgba(15,23,42,.06);">'
                f'<p style="margin:0 0 8px 0;color:{accent};font-size:13px;font-weight:700;">先给结论</p>'
                f'<p style="margin:0;color:#334155;font-size:16px;line-height:1.85;">{self._inline(lead_text)}</p>'
                '</section>'
            )

        html_parts.append(
            f'<section style="margin:0 18px;padding:20px 18px 24px;border-radius:24px;'
            f'background:{surface};box-shadow:0 12px 34px rgba(15,23,42,.07);">'
            f'{rendered_blocks}'
            '</section>'
        )

        if ending_cta:
            html_parts.append(
                f'<section style="margin:22px 18px 0;padding:18px 18px;border-radius:22px;'
                f'background:{accent_soft};border-left:5px solid {accent};">'
                f'<p style="margin:0 0 8px 0;color:{accent};font-size:13px;font-weight:800;">收束一下</p>'
                f'<p style="margin:0;color:#334155;font-size:15px;line-height:1.85;">{self._inline(ending_cta)}</p>'
                '</section>'
            )

        html_parts.append(
            '<section style="margin:20px 18px 0;text-align:center;color:#94a3b8;font-size:12px;line-height:1.7;">'
            '排版由 HotClaw 智能体生成，发布前请确认事实、图片版权与封面裁切。'
            '</section>'
        )
        html_parts.append("</section>")
        return "".join(html_parts)

    def _render_blocks(self, blocks: list[dict[str, Any]], *, template: dict[str, Any]) -> str:
        rendered: list[str] = []
        heading_index = 0
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]

        for block in blocks:
            block_type = block.get("type")
            if block_type == "heading":
                heading_index += 1
                rendered.append(self._render_heading(str(block.get("text") or ""), heading_index, template))
            elif block_type == "paragraph":
                rendered.append(
                    '<p style="margin:0 0 18px 0;color:#334155;font-size:16px;line-height:1.95;'
                    f'letter-spacing:.1px;">{self._inline(str(block.get("text") or ""))}</p>'
                )
            elif block_type == "quote":
                rendered.append(
                    f'<blockquote style="margin:6px 0 20px 0;padding:14px 16px;border-left:4px solid {accent};'
                    f'background:{accent_soft};border-radius:0 16px 16px 0;color:#334155;font-size:15px;'
                    f'line-height:1.85;">{self._inline(str(block.get("text") or ""))}</blockquote>'
                )
            elif block_type == "list":
                ordered = bool(block.get("ordered"))
                items = block.get("items") if isinstance(block.get("items"), list) else []
                tag = "ol" if ordered else "ul"
                rendered_items = "".join(
                    f'<li style="margin:0 0 10px 0;padding-left:2px;line-height:1.8;">{self._inline(str(item))}</li>'
                    for item in items
                )
                rendered.append(
                    f'<{tag} style="margin:2px 0 20px 0;padding-left:22px;color:#334155;font-size:15px;">'
                    f'{rendered_items}</{tag}>'
                )
            elif block_type == "divider":
                rendered.append(
                    '<p style="margin:24px auto;width:52px;border-top:2px solid #e2e8f0;height:1px;"></p>'
                )

        return "".join(rendered)

    def _render_heading(self, text: str, index: int, template: dict[str, Any]) -> str:
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        style = template.get("heading_style")
        safe_text = self._inline(text)

        if style == "numbered_bar":
            return (
                '<section style="margin:28px 0 16px 0;">'
                f'<p style="margin:0 0 8px 0;color:{accent};font-size:12px;font-weight:800;letter-spacing:1.5px;">'
                f'PART {index:02d}</p>'
                f'<h2 style="margin:0;padding:0 0 0 12px;border-left:5px solid {accent};'
                f'color:#0f172a;font-size:21px;line-height:1.45;font-weight:800;">{safe_text}</h2>'
                '</section>'
            )
        if style == "tag_bar":
            return (
                '<section style="margin:28px 0 16px 0;">'
                f'<p style="display:inline-block;margin:0 0 10px 0;padding:4px 10px;border-radius:999px;'
                f'background:{accent_soft};color:{accent};font-size:12px;font-weight:800;">要点 {index}</p>'
                f'<h2 style="margin:0;color:#0f172a;font-size:21px;line-height:1.45;font-weight:800;">{safe_text}</h2>'
                '</section>'
            )
        if style == "playbook_step":
            return (
                '<section style="margin:28px 0 16px 0;display:block;">'
                f'<p style="margin:0 0 10px 0;color:{accent};font-size:12px;font-weight:800;letter-spacing:1px;">STEP {index}</p>'
                f'<h2 style="margin:0;padding:12px 14px;border-radius:16px;background:{accent_soft};'
                f'color:#111827;font-size:20px;line-height:1.45;font-weight:800;">{safe_text}</h2>'
                '</section>'
            )
        return (
            '<section style="margin:28px 0 16px 0;text-align:left;">'
            f'<p style="margin:0 0 8px 0;color:{accent};font-size:18px;line-height:1;">✦</p>'
            f'<h2 style="margin:0;color:#0f172a;font-size:21px;line-height:1.45;font-weight:800;">{safe_text}</h2>'
            '</section>'
        )

    def _lead_text(self, summary: str, blocks: list[dict[str, Any]]) -> str:
        if summary:
            return self._clip(summary, 120)
        for block in blocks:
            if block.get("type") == "paragraph":
                return self._clip(str(block.get("text") or ""), 120)
        return ""

    def _read_minutes(self, blocks: list[dict[str, Any]]) -> int:
        text = " ".join(str(block.get("text") or " ".join(str(item) for item in block.get("items", []))) for block in blocks)
        words = article_assembler_service.count_words(text)
        return max(1, round(words / 420))

    def _extract_headings(self, markdown: str) -> list[str]:
        headings = [
            match.group(1).strip()
            for match in re.finditer(r"^#{2,3}\s+(.+)$", markdown, flags=re.MULTILINE)
            if match.group(1).strip()
        ]
        if headings:
            return headings[:4]
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", markdown) if len(part.strip()) > 20]
        return [self._clip(paragraph, 28) for paragraph in paragraphs[1:4]]

    def _build_image_slots(
        self,
        *,
        title: str,
        headings: list[str],
        source_candidates: list[Any],
        template: dict[str, Any],
    ) -> list[dict[str, Any]]:
        source_names = []
        for item in source_candidates[:3]:
            if isinstance(item, dict):
                name = str(item.get("source_name") or item.get("source_title") or "").strip()
                if name:
                    source_names.append(name)
        slots = [
            {
                "slot_id": "cover",
                "placement": "cover",
                "template_id": template["id"],
                "purpose": "建立文章打开前的第一视觉，风格要和正文模板一致。",
                "prompt": (
                    f"Editorial WeChat cover image for: {title}. "
                    f"Match the {template['name']} layout, clean composition, high contrast, no embedded text."
                ),
                "source_hint": source_names[:2],
            }
        ]
        for index, heading in enumerate(headings[:3], start=1):
            slots.append(
                {
                    "slot_id": f"inline_{index}",
                    "placement": f"after_section_{index}",
                    "template_id": template["id"],
                    "purpose": "在长段落之间制造停顿，同时强化本节核心判断。",
                    "prompt": (
                        f"Illustration for section '{heading}' in article '{title}', "
                        f"{template['name']} WeChat editorial style, no text."
                    ),
                    "source_hint": source_names[:2],
                }
            )
        return slots

    def _cover_prompt(self, title: str, account_context: dict[str, Any], template: dict[str, Any]) -> str:
        tone = str(account_context.get("tone_style") or "clear, professional").strip()
        return (
            f"Create a WeChat article cover for '{title}' using the {template['name']} style. "
            f"Tone: {tone}. Strong focal image, clean negative space, no embedded text."
        )

    def _layout_notes(self, template: dict[str, Any]) -> list[str]:
        return [
            f"已选择「{template['name']}」模板：{template['scenario']}",
            "正文使用公众号兼容的内联 HTML 样式，发布到微信草稿时不会依赖外部 CSS。",
            "长段落会被拆短，H2 会被转换成视觉分节，降低移动端阅读疲劳。",
            "发布前图片仍需要人工确认版权、清晰度和封面裁切。",
        ]

    def _digest(self, article: dict[str, Any], markdown: str) -> str:
        summary = str(article.get("summary") or "").strip()
        if summary:
            return self._clip(re.sub(r"\s+", " ", summary), 120)
        text = re.sub(r"^#+\s*", "", markdown, flags=re.MULTILINE)
        text = re.sub(r"[*_`>#-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return self._clip(text, 120)

    def _public_blocks(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        public: list[dict[str, Any]] = []
        for index, block in enumerate(blocks):
            public.append(
                {
                    "id": f"block_{index + 1}",
                    "type": block.get("type"),
                    "level": block.get("level"),
                    "text": self._clip(str(block.get("text") or ""), 120) if block.get("text") else None,
                    "item_count": len(block.get("items") or []) if isinstance(block.get("items"), list) else None,
                }
            )
        return public

    def _inline(self, value: str) -> str:
        rendered = escape(str(value or ""), quote=False)
        rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
        rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
        rendered = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", rendered)
        return rendered

    def _same_title(self, value: str, title: str) -> bool:
        normalize = lambda text: re.sub(r"\s+", "", text or "").lower()
        return normalize(value) == normalize(title)

    def _clip(self, value: str, limit: int) -> str:
        value = str(value or "").strip()
        return value[:limit] + ("..." if len(value) > limit else "")
