from __future__ import annotations


def test_html_ppt_layout_service_builds_static_deck_artifact():
    from app.services.html_ppt_layout_service import html_ppt_layout_service

    artifact = html_ppt_layout_service.render(
        article={
            "selected_title": "Why terminal agents matter",
            "summary": "Explain the operator workflow shift.",
            "content_markdown": (
                "# Why terminal agents matter\n\n"
                "Intro.\n\n"
                "## Why now\n\n"
                "- Adoption is real\n"
                "- Workflows are changing"
            ),
        },
        outline_plan={"sections": [{"heading": "Why now"}]},
        section_drafts=[{"heading": "Why now", "summary": "Adoption is real."}],
        account_context={"account_name": "Operator Notes"},
        template={"id": "briefing_digest", "name": "Briefing Digest"},
        image_slots=[],
    )

    assert artifact["artifact_type"] == "html_ppt_deck"
    assert artifact["renderer"] == "html-ppt-skill"
    assert artifact["status"] == "preview_ready"
    assert artifact["entry_html"].startswith("<!doctype html>")
    assert "html-ppt-root" in artifact["entry_html"]
    assert "Why terminal agents matter" in artifact["entry_html"]
    assert "这篇内容的阅读路径</h2>" in artifact["entry_html"]
    assert "可以继续展开成图文或演示稿</h2>" in artifact["entry_html"]
    assert artifact["slide_count"] >= 3
