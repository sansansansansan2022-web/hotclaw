"""Service-backed post-process orchestration for WeChat-ready draft finishing."""

from __future__ import annotations

from typing import Any

from app.services.article_assembler_service import article_assembler_service


class PostProcessService:
    """Coordinate post-process formatting while keeping the agent as a compatibility shell."""

    async def prepare(self, *, formatter: Any, input_data: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        gate = input_data.get("draft_quality_gate") if isinstance(input_data.get("draft_quality_gate"), dict) else {}
        gate_blocked = gate.get("passed") is False

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
        if not content_markdown:
            return {
                "used_post_process": False,
                "post_process_skipped": True,
                "skip_reason": "empty_content",
                "layout_template": None,
                "template_options": formatter._template_options(),
                "layout_blocks": [],
                "final_content_markdown": "",
                "final_content_html": "",
                "polishing_summary": "Skipped post-processing because no article content was available.",
                "layout_notes": [],
                "image_slots": [],
                "cover_image_prompt": "",
                "wechat_publish_format": {},
            }
        account_context = input_data.get("account_context") if isinstance(input_data.get("account_context"), dict) else {}
        outline_plan = input_data.get("outline_plan") if isinstance(input_data.get("outline_plan"), dict) else {}
        source_candidates = input_data.get("source_candidates") if isinstance(input_data.get("source_candidates"), list) else []
        reference_digest = input_data.get("reference_digest") if isinstance(input_data.get("reference_digest"), dict) else {}

        template = formatter._select_template(
            article=article,
            account_context=account_context,
            outline_plan=outline_plan,
            source_candidates=source_candidates,
        )
        final_markdown = formatter._format_markdown(title, content_markdown)
        layout_blocks = formatter._parse_markdown(final_markdown, title=title)
        headings = formatter._extract_headings(final_markdown)
        image_slots = formatter._build_image_slots(
            title=title,
            headings=headings,
            source_candidates=source_candidates,
            template=template,
            account_context=account_context,
            reference_digest=reference_digest,
            summary=str(article.get("summary") or "").strip(),
        )
        image_slots = await formatter._resolve_image_slots(
            image_slots,
            image_generation_config=(context or {}).get("image_generation_config"),
        )
        final_html = formatter._render_wechat_html(
            title=title,
            summary=str(article.get("summary") or "").strip(),
            blocks=layout_blocks,
            image_slots=image_slots,
            template=template,
            account_context=account_context,
            outline_plan=outline_plan,
        )
        digest = formatter._digest(article, final_markdown)

        return {
            "used_post_process": True,
            "post_process_skipped": False,
            "quality_gate_warning": gate if gate_blocked else None,
            "layout_template": formatter._public_template(template),
            "template_options": formatter._template_options(),
            "layout_blocks": formatter._public_blocks(layout_blocks),
            "final_content_markdown": final_markdown,
            "final_content_html": final_html,
            "polishing_summary": (
                (
                    "Quality gate did not pass, but preview formatting was still generated for human review. "
                    if gate_blocked
                    else ""
                )
                + f"Applied the {template['name']} template with mobile-first spacing, "
                "section hierarchy, semantic image slots, and WeChat inline HTML."
            ),
            "layout_notes": (
                ["当前草稿存在审核风险，排版仅供预览；正式发布前请先处理审核问题。"]
                if gate_blocked
                else []
            )
            + formatter._layout_notes(template),
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
                    "确认生成图片是否符合品牌风格、主题和版权要求。",
                ],
                "needs_human_image_selection": False,
                "preview_images_embedded": True,
                "ready_for_review": True,
            },
        }


post_process_service = PostProcessService()
