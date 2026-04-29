"""Post-process agent for WeChat-ready draft finishing."""

from __future__ import annotations

import base64
import re
from html import escape
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.services.image_generation_service import image_generation_service
from app.services.post_process_service import post_process_service


class PostProcessAgent(BaseAgent):
    """Polish, format, and suggest preview images after the draft quality gate passes."""

    agent_id = "post_process_agent"
    name = "Post-process Agent"
    description = "Prepare a passed draft for human review with WeChat formatting and preview image placeholders."

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
            "reference_digest": {"type": "object"},
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
        return self._success(await post_process_service.prepare(formatter=self, input_data=input_data, context=context))

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
        word_count = int(article.get("word_count") or self._count_words(str(article.get("content_markdown") or "")))

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
        text = re.sub(r"(?<!\n)\n(?!\n|#|[-*] |\d+\. |> |\s*$)", "\n\n", text)
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
                list_items.append((unordered_match or ordered_match).group(1).strip())
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
        image_slots: list[dict[str, Any]],
        template: dict[str, Any],
        account_context: dict[str, Any],
        outline_plan: dict[str, Any],
    ) -> str:
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        body_background = template["body_background"]
        account_name = str(account_context.get("account_name") or account_context.get("name") or "HotClaw").strip()
        lead_text = self._lead_text(summary, blocks)
        read_minutes = self._read_minutes(blocks)
        ending_cta = str(outline_plan.get("ending_cta") or "").strip()
        rendered_blocks = self._render_blocks(blocks, image_slots=image_slots, template=template)
        cover_slot = next((slot for slot in image_slots if slot.get("slot_id") == "cover"), None)

        html_parts = [
            (
                f'<section class="rich_media" data-hotclaw-template="{escape(str(template["id"]), quote=True)}" '
                f'style="max-width:677px;margin:0 auto;background:{body_background};color:#3f3f3f;'
                'word-wrap:break-word;">'
                '<section class="rich_media_area_primary" '
                'style="position:relative;margin:0 auto;padding:22px 16px 28px;background:#fff;">'
                f'<h1 class="rich_media_title" style="margin:0 0 14px 0;color:#0f172a;'
                f'font-size:25px;line-height:1.4;font-weight:700;">{self._inline(title)}</h1>'
                '<p class="rich_media_meta_list" style="margin:0 0 18px 0;color:#8c8c8c;'
                'font-size:14px;line-height:1.6;">'
                f'<span class="rich_media_meta rich_media_meta_text" style="margin-right:8px;">{escape(account_name)}</span>'
                f'<span class="rich_media_meta rich_media_meta_text" style="margin-right:8px;">{escape(str(template["name"]))}</span>'
                f'<span class="rich_media_meta rich_media_meta_text">预计阅读 {read_minutes} 分钟</span>'
                '</p>'
            ),
        ]

        if cover_slot:
            html_parts.append(self._render_image_figure(cover_slot, template=template, caption=title, variant="cover"))

        if lead_text:
            html_parts.append(
                f'<section style="margin:0 0 22px 0;padding:14px 16px;border-left:4px solid {accent};'
                f'background:{accent_soft};border-radius:0 12px 12px 0;">'
                f'<p style="margin:0 0 8px 0;color:{accent};font-size:13px;font-weight:700;">先给结论</p>'
                f'<p style="margin:0;color:#334155;font-size:16px;line-height:1.85;">{self._inline(lead_text)}</p>'
                '</section>'
            )

        html_parts.append(
            '<section class="rich_media_content" '
            'style="overflow:hidden;color:#3e3e3e;font-size:16px;line-height:1.8;">'
            f'{rendered_blocks}'
            '</section>'
        )

        if ending_cta:
            html_parts.append(
                f'<section style="margin:24px 0 0 0;padding:16px 16px;border-radius:12px;'
                f'background:{accent_soft};border-left:4px solid {accent};">'
                f'<p style="margin:0 0 8px 0;color:{accent};font-size:13px;font-weight:800;">收束一下</p>'
                f'<p style="margin:0;color:#334155;font-size:15px;line-height:1.85;">{self._inline(ending_cta)}</p>'
                '</section>'
            )

        html_parts.append(
            '<section style="margin:24px 0 0 0;text-align:center;color:#94a3b8;font-size:12px;line-height:1.7;">'
            '排版和配图由 HotClaw 智能体生成；正式发布前请确认图片版权、事实和品牌风格。'
            '</section>'
        )
        html_parts.append("</section></section>")
        return "".join(html_parts)

    def _render_blocks(self, blocks: list[dict[str, Any]], *, image_slots: list[dict[str, Any]], template: dict[str, Any]) -> str:
        rendered: list[str] = []
        heading_index = 0
        paragraphs_in_section = 0
        inserted_slots: set[str] = set()
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        inline_slots = {
            str(slot.get("placement")): slot
            for slot in image_slots
            if slot.get("image_kind") == "inline"
        }

        for block in blocks:
            block_type = block.get("type")
            if block_type == "heading":
                heading_index += 1
                paragraphs_in_section = 0
                heading_text = str(block.get("text") or "")
                rendered.append(self._render_heading(heading_text, heading_index, template))
            elif block_type == "paragraph":
                paragraphs_in_section += 1
                rendered.append(
                    '<p style="clear:both;min-height:1em;margin:0 0 1.15em 0;color:#3f3f3f;'
                    f'font-size:16px;line-height:1.9;letter-spacing:.02em;white-space:pre-wrap;">'
                    f'{self._inline(str(block.get("text") or ""))}</p>'
                )
                slot_key = f"after_section_{heading_index}"
                slot = inline_slots.get(slot_key)
                if slot and slot_key not in inserted_slots and paragraphs_in_section == 2:
                    caption = str(slot.get("caption") or block.get("text") or "")
                    rendered.append(self._render_image_figure(slot, template=template, caption=caption, variant="inline"))
                    inserted_slots.add(slot_key)
            elif block_type == "quote":
                rendered.append(
                    f'<blockquote style="margin:8px 0 1.2em 0;padding:10px 0 10px 12px;'
                    f'border-left:3px solid {accent};background:transparent;color:#64748b;'
                    f'font-size:15px;line-height:1.85;">{self._inline(str(block.get("text") or ""))}</blockquote>'
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
                    f'<{tag} style="margin:0 0 1.2em 0;padding-left:24px;color:#3f3f3f;font-size:16px;line-height:1.8;">'
                    f'{rendered_items}</{tag}>'
                )
            elif block_type == "divider":
                rendered.append('<p style="margin:24px auto;width:52px;border-top:2px solid #e2e8f0;height:1px;"></p>')

        return "".join(rendered)

    def _render_heading(self, text: str, index: int, template: dict[str, Any]) -> str:
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        style = template.get("heading_style")
        safe_text = self._inline(text)

        if style == "numbered_bar":
            return (
                '<section style="margin:2em 0 1em 0;">'
                f'<p style="margin:0 0 6px 0;color:{accent};font-size:12px;font-weight:700;letter-spacing:1.5px;">'
                f'PART {index:02d}</p>'
                f'<h2 style="margin:0;padding:0 0 0 10px;border-left:4px solid {accent};'
                f'color:#0f172a;font-size:21px;line-height:1.45;font-weight:700;">{safe_text}</h2>'
                '</section>'
            )
        if style == "tag_bar":
            return (
                '<section style="margin:2em 0 1em 0;">'
                f'<p style="display:inline-block;margin:0 0 10px 0;padding:4px 10px;border-radius:999px;'
                f'background:{accent_soft};color:{accent};font-size:12px;font-weight:700;">要点 {index}</p>'
                f'<h2 style="margin:0;color:#0f172a;font-size:21px;line-height:1.45;font-weight:700;">{safe_text}</h2>'
                '</section>'
            )
        if style == "playbook_step":
            return (
                '<section style="margin:2em 0 1em 0;display:block;">'
                f'<p style="margin:0 0 8px 0;color:{accent};font-size:12px;font-weight:700;letter-spacing:1px;">STEP {index}</p>'
                f'<h2 style="margin:0;padding:10px 12px;border-radius:10px;background:{accent_soft};'
                f'color:#111827;font-size:20px;line-height:1.45;font-weight:700;">{safe_text}</h2>'
                '</section>'
            )
        return (
            '<section style="margin:2em 0 1em 0;text-align:left;">'
            f'<p style="margin:0 0 8px 0;color:{accent};font-size:18px;line-height:1;">✦</p>'
            f'<h2 style="margin:0;color:#0f172a;font-size:21px;line-height:1.45;font-weight:700;">{safe_text}</h2>'
            '</section>'
        )

    def _render_image_figure(self, slot: dict[str, Any], *, template: dict[str, Any], caption: str, variant: str) -> str:
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        image_url = str(slot.get("selected_asset_url") or "").strip()
        if not image_url:
            return ""

        wrapper_margin = "0 0 22px 0" if variant == "cover" else "4px 0 1.4em 0"
        border_radius = "10px" if variant == "cover" else "8px"
        origin = str(slot.get("asset_origin") or "")
        note = "AI 生成封面" if variant == "cover" and origin == "generated" else (
            "AI 生成配图" if origin == "generated" else ("语义配图预览" if variant == "cover" else "段间配图预览")
        )
        caption_text = str(slot.get("caption") or caption or "").strip()
        credit = str(slot.get("credit") or "").strip()
        suffix = f" · {credit}" if credit else ""
        return (
            f'<figure data-hotclaw-image-slot="{escape(str(slot.get("slot_id") or "image"), quote=True)}" '
            f'style="margin:{wrapper_margin};padding:0;border-radius:{border_radius};background:#fff;'
            f'border:1px solid {accent_soft};overflow:hidden;">'
            f'<img src="{escape(image_url, quote=True)}" alt="{escape(caption, quote=True)}" '
            f'style="display:block;width:100%;max-width:100%;height:auto!important;object-fit:cover;background:{accent_soft};" />'
            f'<figcaption style="margin:0;padding:8px 12px;color:{accent};font-size:12px;line-height:1.7;background:#fff;">'
            f'{note}{suffix} · {self._inline(self._clip(caption_text, 48))}</figcaption>'
            '</figure>'
        )

    def _lead_text(self, summary: str, blocks: list[dict[str, Any]]) -> str:
        if summary:
            return self._clip(summary, 120)
        for block in blocks:
            if block.get("type") == "paragraph":
                return self._clip(str(block.get("text") or ""), 120)
        return ""

    def _read_minutes(self, blocks: list[dict[str, Any]]) -> int:
        text = " ".join(
            str(block.get("text") or " ".join(str(item) for item in block.get("items", [])))
            for block in blocks
        )
        return max(1, round(self._count_words(text) / 420))

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
        account_context: dict[str, Any] | None = None,
        reference_digest: dict[str, Any] | None = None,
        summary: str = "",
    ) -> list[dict[str, Any]]:
        source_names: list[str] = []
        for item in source_candidates[:3]:
            if isinstance(item, dict):
                name = str(item.get("source_name") or item.get("source_title") or "").strip()
                if name:
                    source_names.append(name)

        source_label = " · ".join(source_names[:2]) or template["name"]
        visual_sections = self._select_visual_sections(headings)
        slots: list[dict[str, Any]] = [
            {
                "slot_id": "cover",
                "placement": "cover",
                "template_id": template["id"],
                "status": "planned",
                "image_kind": "cover",
                "asset_origin": "planned_generation",
                "binding_status": "bound",
                "draft_visibility": "visible",
                "fallback_behavior": "generate_semantic_preview_if_model_unavailable",
                "purpose": "建立文章第一视觉，用一个抽象但贴题的画面概括全文判断。",
                "prompt": self._image_prompt(
                    title=title,
                    summary=summary,
                    section_heading="",
                    template=template,
                    account_context=account_context or {},
                    image_kind="cover",
                ),
                "source_hint": source_names[:2],
                "selected_asset_url": "",
                "selected_asset_path": None,
                "caption": title,
                "credit": None,
                "copyright_note": "AI 生成预览图；正式发布前请确认商用授权与品牌合规。",
                "placement_reason": "封面位承担第一印象，应概括全文主题而不是复用来源配图。",
            }
        ]

        for index, heading in visual_sections:
            slots.append(
                {
                    "slot_id": f"inline_{index}",
                    "placement": f"after_section_{index}",
                    "template_id": template["id"],
                    "status": "planned",
                    "image_kind": "inline",
                    "asset_origin": "planned_generation",
                    "binding_status": "bound",
                    "draft_visibility": "visible",
                    "fallback_behavior": "generate_semantic_preview_if_model_unavailable",
                    "purpose": "插在本节首段之后，作为读者理解框架或关键矛盾的视觉停顿。",
                    "prompt": self._image_prompt(
                        title=title,
                        summary=summary,
                        section_heading=heading,
                        template=template,
                        account_context=account_context or {},
                        image_kind="inline",
                    ),
                    "source_hint": source_names[:2],
                    "selected_asset_url": "",
                    "selected_asset_path": None,
                    "caption": heading,
                    "credit": None,
                    "copyright_note": "AI 生成段间配图；正式发布前请确认商用授权与品牌合规。",
                    "placement_reason": "本节进入具体论证后插图，避免图片抢在观点之前出现。",
                }
            )
        return slots

    async def _resolve_image_slots(
        self,
        image_slots: list[dict[str, Any]],
        *,
        image_generation_config: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for slot in image_slots:
            next_slot = dict(slot)
            prompt = str(next_slot.get("prompt") or "").strip()
            image_kind = str(next_slot.get("image_kind") or "inline")
            size = "1200x628" if image_kind == "cover" else "1024x768"
            result = await image_generation_service.generate(
                config=image_generation_config,
                prompt=prompt,
                size=size,
            )
            if result.success and result.asset_url:
                next_slot.update(
                    {
                        "status": "generated",
                        "asset_origin": "generated",
                        "selected_asset_url": result.asset_url,
                        "provider": result.provider,
                        "model": result.model,
                        "generation_error": None,
                    }
                )
            else:
                fallback_label = self._slot_fallback_label(next_slot)
                next_slot.update(
                    {
                        "status": "preview_ready",
                        "asset_origin": "generated_preview",
                        "selected_asset_url": self._build_preview_image_url(
                            primary_text=fallback_label["primary"],
                            secondary_text=fallback_label["secondary"],
                            template=self._template_by_id(str(next_slot.get("template_id") or "")),
                            image_kind=image_kind,
                        ),
                        "provider": result.provider,
                        "model": result.model,
                        "generation_error": result.error_message,
                    }
                )
            resolved.append(next_slot)
        return resolved

    def _select_visual_sections(self, headings: list[str]) -> list[tuple[int, str]]:
        if not headings:
            return []
        priority_keywords = (
            "框架",
            "决策",
            "结构",
            "路径",
            "方法",
            "流程",
            "架构",
            "问题",
            "趋势",
            "pattern",
            "framework",
            "architecture",
            "workflow",
        )
        ranked: list[tuple[int, int, str]] = []
        for index, heading in enumerate(headings[:4], start=1):
            text = heading.lower()
            score = 2 if any(keyword in text for keyword in priority_keywords) else 0
            if index in {1, 2}:
                score += 1
            ranked.append((score, index, heading))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [(index, heading) for _, index, heading in ranked[:1]]

    def _image_prompt(
        self,
        *,
        title: str,
        summary: str,
        section_heading: str,
        template: dict[str, Any],
        account_context: dict[str, Any],
        image_kind: str,
    ) -> str:
        tone = str(account_context.get("tone_style") or "professional, editorial, analytical").strip()
        audience = str(account_context.get("target_audience") or account_context.get("audience") or "").strip()
        focus = section_heading or title
        role = "cover image" if image_kind == "cover" else "inline section illustration"
        composition = (
            "wide editorial cover, one clear focal metaphor, cinematic lighting"
            if image_kind == "cover"
            else "clean conceptual illustration placed between paragraphs, clear visual hierarchy"
        )
        return (
            f"Create a WeChat public account {role} for an article titled: {title}. "
            f"Article summary: {summary or title}. Visual focus: {focus}. "
            f"Audience: {audience or 'AI engineers, product builders, and technical decision makers'}. "
            f"Tone: {tone}. Template mood: {template['name']} with accent color {template['accent_color']}. "
            f"Style: modern editorial illustration, {composition}, high quality, coherent with the full article. "
            "Avoid screenshots, UI mockups, logos, brand marks, random text, watermarks, and dense diagrams. "
            "No embedded words or readable text in the image."
        )

    def _slot_fallback_label(self, slot: dict[str, Any]) -> dict[str, str]:
        primary = str(slot.get("caption") or "文章配图").strip()
        if slot.get("image_kind") == "cover":
            secondary = "全文主题视觉"
        else:
            secondary = "段落核心观点"
        return {"primary": primary, "secondary": secondary}

    def _template_by_id(self, template_id: str) -> dict[str, Any]:
        return next((template for template in self.LAYOUT_TEMPLATES if template["id"] == template_id), self.LAYOUT_TEMPLATES[0])

    def _collect_source_image_assets(
        self,
        *,
        source_candidates: list[Any],
        account_context: dict[str, Any],
        reference_digest: dict[str, Any],
    ) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: Any, *, caption: str = "", credit: str = "", source_hint: list[str] | None = None) -> None:
            text = str(url or "").strip()
            if not self._is_usable_image_url(text) or text in seen:
                return
            seen.add(text)
            assets.append(
                {
                    "url": text,
                    "caption": caption or None,
                    "credit": credit or None,
                    "source_hint": source_hint or ([credit] if credit else []),
                    "copyright_note": "从已同步参考源/原文摘要中提取；发布前请确认授权与版权。",
                }
            )

        def scan_text(text: Any, *, caption: str = "", credit: str = "", source_hint: list[str] | None = None) -> None:
            if not isinstance(text, str) or "http" not in text:
                return
            for match in re.finditer(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text):
                add(match.group(1), caption=caption, credit=credit, source_hint=source_hint)
            for match in re.finditer(r"<img[^>]+src=[\"'](https?://[^\"']+)[\"']", text, flags=re.I):
                add(match.group(1), caption=caption, credit=credit, source_hint=source_hint)
            for match in re.finditer(r"(https?://[^\s\"')<>]+?\.(?:png|jpe?g|webp|gif)(?:\?[^\s\"')<>]*)?)", text, flags=re.I):
                add(match.group(1), caption=caption, credit=credit, source_hint=source_hint)

        def scan_record(record: Any, *, fallback_caption: str = "", fallback_credit: str = "") -> None:
            if not isinstance(record, dict):
                return
            caption = str(
                record.get("title")
                or record.get("source_title")
                or record.get("resolved_title")
                or fallback_caption
                or ""
            ).strip()
            credit = str(record.get("source_name") or record.get("name") or fallback_credit or "").strip()
            hint = [item for item in (credit, caption) if item]
            for key in (
                "image_url",
                "cover_image_url",
                "thumbnail_url",
                "thumb_url",
                "og_image",
                "image",
                "cover",
            ):
                add(record.get(key), caption=caption, credit=credit, source_hint=hint)
            for key in ("content_markdown", "content_markdown_excerpt", "html", "preview", "snippet", "summary"):
                scan_text(record.get(key), caption=caption, credit=credit, source_hint=hint)
            for nested_key in ("entry", "source", "metadata_json", "source_payload_json"):
                scan_record(record.get(nested_key), fallback_caption=caption, fallback_credit=credit)
            samples = record.get("article_samples")
            if isinstance(samples, list):
                for sample in samples:
                    scan_record(sample, fallback_caption=caption, fallback_credit=credit)

        for digest in reference_digest.get("source_digests") or []:
            scan_record(digest)
        for snippet in reference_digest.get("source_snippets") or []:
            scan_record(snippet)
        selected_source_ids = [
            str(source_id)
            for source_id in (reference_digest.get("selected_source_ids") or [])
            if source_id is not None
        ]
        reference_sources = list(account_context.get("reference_sources") or [])
        if selected_source_ids:
            order = {source_id: index for index, source_id in enumerate(selected_source_ids)}
            reference_sources.sort(key=lambda item: order.get(str((item or {}).get("id")), 999))
        for source in reference_sources:
            scan_record(source)
        for item in source_candidates:
            scan_record(item)

        return assets[:4]

    def _is_usable_image_url(self, value: str) -> bool:
        if not value.startswith(("http://", "https://")):
            return False
        lowered = value.lower()
        if any(token in lowered for token in ("avatar", "profile_photo", "emoji")):
            return False
        return any(token in lowered for token in (".png", ".jpg", ".jpeg", ".webp", ".gif", "mmbiz.qpic.cn"))

    def _build_preview_image_url(
        self,
        *,
        primary_text: str,
        secondary_text: str,
        template: dict[str, Any],
        image_kind: str,
    ) -> str:
        width, height = (1200, 628) if image_kind == "cover" else (1200, 720)
        primary = escape(self._clip(primary_text, 34))
        secondary = escape(self._clip(secondary_text, 42))
        accent = template["accent_color"]
        accent_soft = template["accent_soft"]
        surface = template["surface"]
        svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent}" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="card" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{surface}" stop-opacity="0.98" />
      <stop offset="100%" stop-color="{accent_soft}" stop-opacity="0.96" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="36" fill="url(#bg)" />
  <circle cx="{width - 140}" cy="120" r="90" fill="white" fill-opacity="0.12" />
  <circle cx="120" cy="{height - 120}" r="72" fill="white" fill-opacity="0.08" />
  <rect x="72" y="78" width="{width - 144}" height="{height - 156}" rx="32" fill="url(#card)" />
  <rect x="104" y="118" width="164" height="42" rx="21" fill="{accent_soft}" />
  <text x="186" y="145" text-anchor="middle" font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" font-size="20" font-weight="700" fill="{accent}">{escape(template['name'])}</text>
  <text x="104" y="246" font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" font-size="52" font-weight="800" fill="#0f172a">{primary}</text>
  <text x="104" y="308" font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" font-size="28" font-weight="500" fill="#334155">{secondary}</text>
  <rect x="104" y="{height - 134}" width="260" height="16" rx="8" fill="{accent}" fill-opacity="0.22" />
  <rect x="104" y="{height - 102}" width="188" height="16" rx="8" fill="{accent}" fill-opacity="0.14" />
</svg>
""".strip()
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    def _cover_prompt(self, title: str, account_context: dict[str, Any], template: dict[str, Any]) -> str:
        tone = str(account_context.get("tone_style") or "clear, professional").strip()
        return (
            f"Create a WeChat article cover for '{title}' using the {template['name']} style. "
            f"Tone: {tone}. Strong focal image, clean negative space, no embedded text."
        )

    def _layout_notes(self, template: dict[str, Any]) -> list[str]:
        return [
            f"已选择「{template['name']}」模板：{template['scenario']}",
            "正文使用公众号兼容的内联 HTML 样式，预览无需依赖外部 CSS。",
            "配图先根据标题、摘要和分节语义生成图片计划，再调用已配置的图像模型生成。",
            "图像模型不可用时才使用语义预览占位图，确保演示预览不会空白。",
            "正式发布前仍需要人工确认图片版权、清晰度和品牌风格。",
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

    def _count_words(self, text: str) -> int:
        if not text:
            return 0
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        english = len(re.findall(r"[A-Za-z0-9_]+", text))
        return chinese + english
