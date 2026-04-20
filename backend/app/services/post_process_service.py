"""Service-backed post-process orchestration for WeChat-ready draft finishing."""

from __future__ import annotations

from typing import Any

from app.services.article_assembler_service import article_assembler_service


class PostProcessService:
    """Coordinate post-process formatting while keeping the agent as a compatibility shell."""

    def prepare(self, *, formatter: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        gate = input_data.get("draft_quality_gate") if isinstance(input_data.get("draft_quality_gate"), dict) else {}
        if gate.get("passed") is False:
            return {
                "used_post_process": False,
                "post_process_skipped": True,
                "skip_reason": "draft_quality_gate_blocked",
                "layout_template": None,
                "template_options": formatter._template_options(),
                "layout_blocks": [],
                "final_content_markdown": "",
                "final_content_html": "",
                "polishing_summary": "Skipped post-processing because the draft quality gate did not pass.",
                "layout_notes": [],
                "image_slots": [],
                "cover_image_prompt": "",
                "wechat_publish_format": {},
            }

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
        source_candidates = input_data.get("source_candidates") if isinstance(input_data.get("source_candidates"), list) else []

        template = formatter._select_template(
            article=article,
            account_context=account_context,
            outline_plan=outline_plan,
            source_candidates=source_candidates,
        )
        final_markdown = formatter._format_markdown(title, content_markdown)
        layout_blocks = formatter._parse_markdown(final_markdown, title=title)
        final_html = formatter._render_wechat_html(
            title=title,
            summary=str(article.get("summary") or "").strip(),
            blocks=layout_blocks,
            template=template,
            account_context=account_context,
            outline_plan=outline_plan,
        )
        headings = formatter._extract_headings(final_markdown)
        image_slots = formatter._build_image_slots(
            title=title,
            headings=headings,
            source_candidates=source_candidates,
            template=template,
        )
        digest = formatter._digest(article, final_markdown)

        return {
            "used_post_process": True,
            "layout_template": formatter._public_template(template),
            "template_options": formatter._template_options(),
            "layout_blocks": formatter._public_blocks(layout_blocks),
            "final_content_markdown": final_markdown,
            "final_content_html": final_html,
            "polishing_summary": (
                f"Applied the {template['name']} template with mobile-first spacing, "
                "section hierarchy, highlight callouts, image placement hints, and WeChat inline HTML."
            ),
            "layout_notes": formatter._layout_notes(template),
            "image_slots": image_slots,
            "cover_image_prompt": formatter._cover_prompt(title, account_context, template),
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


post_process_service = PostProcessService()
