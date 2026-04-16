from __future__ import annotations

import pytest

from app.agents.post_process_agent import PostProcessAgent


@pytest.mark.asyncio
async def test_post_process_agent_generates_wechat_layout_template():
    agent = PostProcessAgent()

    result = await agent.execute(
        {
            "draft_quality_gate": {
                "passed": True,
                "status": "passed",
                "risk_level": "low",
                "issues": [],
            },
            "assembled_article": {
                "selected_title": "AI 工具热潮之后，团队真正要补的是判断力",
                "selected_topic": "AI 工具运营判断",
                "summary": "这篇文章讨论 AI 工具普及之后，内容团队为什么更需要判断力而不是更多模板。",
                "content_markdown": (
                    "# AI 工具热潮之后，团队真正要补的是判断力\n\n"
                    "过去一年，很多团队把 AI 当成效率工具，但真正拉开差距的不是谁写得更快。\n\n"
                    "## 先看问题\n\n"
                    "当大家都能快速生成文本，普通稿件会越来越像同一份新闻通稿。\n\n"
                    "## 再看方法\n\n"
                    "- 先确定读者今天最关心的判断\n"
                    "- 再决定哪些事实值得进入正文\n"
                    "- 最后用账号自己的语气说清楚取舍\n"
                ),
                "tags": ["AI 工具", "内容运营"],
            },
            "account_context": {
                "account_name": "内容运营观察",
                "positioning": "写给内容团队负责人的运营观察。",
                "tone_style": "克制、有判断、少套话",
                "content_strategy": "用复盘和观点帮助团队做判断。",
            },
            "source_candidates": [
                {"source_name": "TechCrunch AI", "source_title": "AI tool adoption report"},
                {"source_name": "OpenAI News", "source_title": "Agent workflow update"},
            ],
        },
        {},
    )

    assert result.is_success
    assert result.data["used_post_process"] is True
    assert result.data["layout_template"]["id"] in {
        "insight_column",
        "briefing_digest",
        "warm_story",
        "operator_playbook",
    }
    assert len(result.data["template_options"]) >= 4
    assert result.data["layout_blocks"]
    assert "data-hotclaw-template" in result.data["final_content_html"]
    assert "style=" in result.data["final_content_html"]
    assert "发布前检查" not in result.data["final_content_markdown"]
    assert result.data["wechat_publish_format"]["content_format"] == "wechat_inline_html"
    assert result.data["wechat_publish_format"]["template_id"] == result.data["layout_template"]["id"]
    assert result.data["image_slots"][0]["slot_id"] == "cover"


@pytest.mark.asyncio
async def test_post_process_agent_skips_when_quality_gate_blocks():
    agent = PostProcessAgent()

    result = await agent.execute(
        {
            "draft_quality_gate": {
                "passed": False,
                "status": "blocked",
                "failure_reasons": ["unsupported_claim"],
            }
        },
        {},
    )

    assert result.is_success
    assert result.data["used_post_process"] is False
    assert result.data["post_process_skipped"] is True
    assert result.data["skip_reason"] == "draft_quality_gate_blocked"
    assert result.data["template_options"]
