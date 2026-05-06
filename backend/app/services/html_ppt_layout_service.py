"""Static HTML deck artifact renderer inspired by html-ppt-skill templates."""

from __future__ import annotations

import re
from html import escape
from typing import Any


class HtmlPptLayoutService:
    """Render browser-preview layout artifacts without changing WeChat HTML."""

    renderer_name = "html-ppt-skill"
    renderer_version = "v0-static-artifact"

    def render(
        self,
        *,
        article: dict[str, Any],
        outline_plan: dict[str, Any] | None,
        section_drafts: dict[str, Any] | list[dict[str, Any]] | None,
        account_context: dict[str, Any] | None,
        template: dict[str, Any] | None,
        image_slots: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        title = self._clean_text(article.get("selected_title") or article.get("title") or "Untitled")
        summary = self._clean_text(article.get("summary"))
        account_name = self._clean_text(
            (account_context or {}).get("account_name")
            or (account_context or {}).get("name")
            or "HotClaw"
        )
        template_id = self._clean_text((template or {}).get("id")) or "html_ppt_default"
        template_name = self._clean_text((template or {}).get("name")) or "HTML PPT Preview"
        sections = self._sections_from(section_drafts, outline_plan, article)
        cover_image = self._first_image_url(image_slots or [])

        slides = [
            self._cover_slide(title=title, summary=summary, account_name=account_name, cover_image=cover_image),
            self._agenda_slide(sections=sections),
        ]
        slides.extend(self._content_slide(item, index=index + 1) for index, item in enumerate(sections[:8]))
        slides.append(self._closing_slide(title=title, summary=summary))
        entry_html = self._document(
            title=title,
            template_id=template_id,
            template_name=template_name,
            slides=slides,
        )

        return {
            "artifact_type": "html_ppt_deck",
            "renderer": self.renderer_name,
            "renderer_version": self.renderer_version,
            "status": "preview_ready",
            "template_id": template_id,
            "template_name": template_name,
            "entry_html": entry_html,
            "slide_count": len(slides),
            "assets": [],
            "export_targets": ["browser_preview"],
            "warnings": [],
        }

    def _document(self, *, title: str, template_id: str, template_name: str, slides: list[str]) -> str:
        slide_count = len(slides)
        return (
            "<!doctype html>\n"
            '<html lang="zh-CN">\n'
            "<head>\n"
            '  <meta charset="utf-8" />\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
            f"  <title>{escape(title)}</title>\n"
            "  <style>\n"
            "    :root { color-scheme: light; --bg: #f8fafc; --ink: #0f172a; --muted: #64748b; --line: #cbd5e1; --accent: #2563eb; --accent-soft: #dbeafe; }\n"
            "    * { box-sizing: border-box; }\n"
            "    body { margin: 0; background: var(--bg); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }\n"
            "    .html-ppt-root { min-height: 100vh; padding: 24px; }\n"
            "    .deck-meta { max-width: 1120px; margin: 0 auto 16px; display: flex; justify-content: space-between; gap: 16px; color: var(--muted); font-size: 13px; }\n"
            "    .slide { width: min(1120px, 100%); min-height: 630px; margin: 0 auto 24px; padding: 56px; border: 1px solid var(--line); border-radius: 18px; background: #fff; box-shadow: 0 24px 70px rgba(15, 23, 42, .10); display: flex; flex-direction: column; justify-content: center; page-break-after: always; }\n"
            "    .slide.cover { background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 55%, #38bdf8 100%); color: #fff; }\n"
            "    .eyebrow { margin: 0 0 18px; color: var(--accent); font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }\n"
            "    .cover .eyebrow, .cover .muted { color: rgba(255,255,255,.78); }\n"
            "    h1 { margin: 0; font-size: 68px; line-height: 1.04; letter-spacing: 0; }\n"
            "    h2 { margin: 0 0 24px; font-size: 44px; line-height: 1.12; letter-spacing: 0; }\n"
            "    p { margin: 0; font-size: 22px; line-height: 1.65; }\n"
            "    .muted { color: var(--muted); }\n"
            "    .summary { margin-top: 28px; max-width: 780px; }\n"
            "    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 26px; }\n"
            "    .card { border: 1px solid var(--line); border-radius: 14px; padding: 20px; background: #f8fafc; }\n"
            "    .card strong { display: block; font-size: 20px; margin-bottom: 8px; }\n"
            "    ul { margin: 22px 0 0; padding-left: 26px; font-size: 23px; line-height: 1.7; }\n"
            "    li + li { margin-top: 8px; }\n"
            "    .cover-image { margin-top: 30px; max-height: 220px; max-width: 100%; border-radius: 16px; object-fit: cover; border: 1px solid rgba(255,255,255,.32); }\n"
            "    .slide-number { margin-top: auto; padding-top: 28px; color: var(--muted); font-size: 13px; }\n"
            "    .cover .slide-number { color: rgba(255,255,255,.70); }\n"
            "    @media (max-width: 760px) { .html-ppt-root { padding: 12px; } .slide { min-height: 540px; padding: 28px; border-radius: 12px; } h1 { font-size: 42px; } h2 { font-size: 30px; } p, ul { font-size: 18px; } .grid { grid-template-columns: 1fr; } }\n"
            "  </style>\n"
            "</head>\n"
            f'<body data-hotclaw-layout="{escape(template_id, quote=True)}">\n'
            '  <main class="html-ppt-root">\n'
            f'    <div class="deck-meta"><span>{escape(template_name)}</span><span>{slide_count} slides</span></div>\n'
            f"{''.join(slides)}\n"
            "  </main>\n"
            "</body>\n"
            "</html>"
        )

    def _cover_slide(self, *, title: str, summary: str, account_name: str, cover_image: str | None) -> str:
        image_html = (
            f'<img class="cover-image" src="{escape(cover_image, quote=True)}" alt="" />'
            if cover_image
            else ""
        )
        return (
            '<section class="slide cover">\n'
            f'  <p class="eyebrow">{escape(account_name)} · HTML PPT</p>\n'
            f"  <h1>{escape(title)}</h1>\n"
            f'  <p class="summary muted">{escape(summary)}</p>\n'
            f"  {image_html}\n"
            '  <div class="slide-number">01 / cover</div>\n'
            "</section>\n"
        )

    def _agenda_slide(self, *, sections: list[dict[str, Any]]) -> str:
        cards = "".join(
            (
                '<div class="card">'
                f"<strong>{index + 1:02d}. {escape(self._clean_text(item.get('heading')) or f'Section {index + 1}')}</strong>"
                f"<span>{escape(self._clean_text(item.get('summary')))}</span>"
                "</div>"
            )
            for index, item in enumerate(sections[:6])
        )
        return (
            '<section class="slide">\n'
            '  <p class="eyebrow">Structure</p>\n'
            "  <h2>这篇内容的阅读路径</h2>\n"
            f'  <div class="grid">{cards}</div>\n'
            '  <div class="slide-number">02 / agenda</div>\n'
            "</section>\n"
        )

    def _content_slide(self, item: dict[str, Any], *, index: int) -> str:
        heading = self._clean_text(item.get("heading")) or f"Section {index}"
        summary = self._clean_text(item.get("summary"))
        bullets = self._bullets_for(item)
        bullet_html = "".join(f"<li>{escape(text)}</li>" for text in bullets[:5])
        return (
            '<section class="slide">\n'
            f'  <p class="eyebrow">Part {index:02d}</p>\n'
            f"  <h2>{escape(heading)}</h2>\n"
            f'  <p class="muted">{escape(summary)}</p>\n'
            f"  <ul>{bullet_html}</ul>\n"
            f'  <div class="slide-number">{index + 2:02d} / section</div>\n'
            "</section>\n"
        )

    def _closing_slide(self, *, title: str, summary: str) -> str:
        return (
            '<section class="slide">\n'
            '  <p class="eyebrow">Landing</p>\n'
            "  <h2>可以继续展开成图文或演示稿</h2>\n"
            f'  <p class="muted">{escape(summary or title)}</p>\n'
            '  <div class="slide-number">end</div>\n'
            "</section>\n"
        )

    def _sections_from(
        self,
        section_drafts: dict[str, Any] | list[dict[str, Any]] | None,
        outline_plan: dict[str, Any] | None,
        article: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raw_sections: Any = section_drafts
        if isinstance(raw_sections, dict):
            raw_sections = raw_sections.get("section_drafts") or raw_sections.get("sections") or []
        sections = [item for item in raw_sections if isinstance(item, dict)] if isinstance(raw_sections, list) else []
        if sections:
            return sections

        outline_sections = (outline_plan or {}).get("sections") if isinstance(outline_plan, dict) else None
        if isinstance(outline_sections, list):
            sections = [item for item in outline_sections if isinstance(item, dict)]
        if sections:
            return sections

        markdown_sections = self._sections_from_markdown(self._clean_text(article.get("content_markdown")))
        return markdown_sections or [{"heading": self._clean_text(article.get("selected_title")) or "Article", "summary": self._clean_text(article.get("summary"))}]

    def _sections_from_markdown(self, markdown: str) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line in markdown.splitlines():
            heading_match = re.match(r"^#{2,3}\s+(.+)$", line.strip())
            if heading_match:
                current = {"heading": heading_match.group(1).strip(), "summary": "", "key_points": []}
                sections.append(current)
                continue
            bullet_match = re.match(r"^[-*]\s+(.+)$", line.strip())
            if bullet_match and current is not None:
                current.setdefault("key_points", []).append(bullet_match.group(1).strip())
                continue
            if current is not None and line.strip() and not current.get("summary"):
                current["summary"] = line.strip()
        return sections

    def _bullets_for(self, item: dict[str, Any]) -> list[str]:
        candidates = item.get("key_points")
        if isinstance(candidates, list):
            bullets = [self._clean_text(value) for value in candidates if self._clean_text(value)]
            if bullets:
                return bullets
        content = self._clean_text(item.get("content_markdown") or item.get("content"))
        lines = [
            match.group(1).strip()
            for match in re.finditer(r"^[-*]\s+(.+)$", content, flags=re.MULTILINE)
        ]
        if lines:
            return lines
        summary = self._clean_text(item.get("summary"))
        return [summary] if summary else ["保留这一节的核心判断，适合继续拆成图文卡片。"]

    def _first_image_url(self, image_slots: list[dict[str, Any]]) -> str | None:
        for slot in image_slots:
            url = self._clean_text(slot.get("selected_asset_url") or slot.get("asset_url"))
            if url:
                return url
        return None

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()


html_ppt_layout_service = HtmlPptLayoutService()
