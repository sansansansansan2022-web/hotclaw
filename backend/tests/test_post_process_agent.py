from __future__ import annotations

import pytest

from app.agents.post_process_agent import PostProcessAgent
from app.services.image_generation_service import ImageGenerationResult


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
    for slot in result.data["image_slots"]:
        assert slot["status"] == "preview_ready"
        assert slot["asset_origin"] == "generated_preview"
        assert slot["binding_status"] == "bound"
        assert slot["draft_visibility"] == "visible"
        assert slot["fallback_behavior"] == "generate_semantic_preview_if_model_unavailable"
        assert slot["selected_asset_url"].startswith("data:image/svg+xml;base64,")
        assert slot["selected_asset_path"] is None
        assert slot["caption"]
        assert slot["credit"] is None
        assert slot["copyright_note"]
    assert result.data["image_slots"][0]["image_kind"] == "cover"
    assert len(result.data["image_slots"]) >= 1


@pytest.mark.asyncio
async def test_post_process_agent_plans_semantic_images_instead_of_source_capture():
    agent = PostProcessAgent()

    result = await agent.execute(
        {
            "draft_quality_gate": {"passed": True, "status": "passed", "risk_level": "low", "issues": []},
            "assembled_article": {
                "selected_title": "Trace2Skill 工程复盘",
                "summary": "这篇文章拆解 Trace2Skill 的工程化难点。",
                "content_markdown": (
                    "# Trace2Skill 工程复盘\n\n"
                    "先给一个判断：真实系统里的技能蒸馏难点不在论文图表。\n\n"
                    "## 先看数据\n\n"
                    "执行轨迹的噪声会直接污染技能文档。\n\n"
                    "## 再看迁移\n\n"
                    "同一份技能文档在不同模型上的表现并不一致。\n"
                ),
            },
            "account_context": {
                "account_name": "AI 阅微轩",
                "reference_sources": [
                    {
                        "name": "AI 阅微轩",
                        "metadata_json": {
                            "article_samples": [
                                {
                                    "title": "论文精读｜Trace2Skill",
                                    "source_name": "AI 阅微轩",
                                    "content_markdown_excerpt": (
                                        "正文\n\n"
                                        "![](https://mmbiz.qpic.cn/mmbiz_png/demo-one/640?wx_fmt=png&from=appmsg)\n\n"
                                        "Figure 1\n\n"
                                        "![](https://mmbiz.qpic.cn/mmbiz_png/demo-two/640?wx_fmt=png&from=appmsg)\n"
                                    ),
                                }
                            ]
                        },
                    }
                ],
            },
        },
        {},
    )

    assert result.is_success
    slots = result.data["image_slots"]
    assert len(slots) == 2
    assert slots[0]["asset_origin"] == "generated_preview"
    assert slots[0]["status"] == "preview_ready"
    assert slots[1]["image_kind"] == "inline"
    assert slots[1]["fallback_behavior"] == "generate_semantic_preview_if_model_unavailable"
    assert "Trace2Skill 工程复盘" in slots[0]["prompt"]
    assert "先看数据" in slots[1]["prompt"]


@pytest.mark.asyncio
async def test_post_process_agent_uses_configured_image_generation(monkeypatch):
    async def fake_generate(*, config, prompt, size):
        return ImageGenerationResult(
            success=True,
            asset_url="https://cdn.example.com/generated.png",
            provider=config["provider"],
            model=config["model"],
        )

    monkeypatch.setattr("app.agents.post_process_agent.image_generation_service.generate", fake_generate)
    agent = PostProcessAgent()

    result = await agent.execute(
        {
            "draft_quality_gate": {"passed": True, "status": "passed", "risk_level": "low", "issues": []},
            "assembled_article": {
                "selected_title": "Tesla 算力基建判断",
                "summary": "这篇文章解释 Tesla 资本支出背后的算力基建逻辑。",
                "content_markdown": (
                    "# Tesla 算力基建判断\n\n"
                    "先给结论：这不是一次普通扩产，而是自动驾驶算力基建。\n\n"
                    "## 决策框架\n\n"
                    "团队应该从资本效率、推理网络和训练闭环三个维度看这件事。\n"
                ),
            },
        },
        {"image_generation_config": {"provider": "openai", "model": "gpt-image-1", "api_key": "sk-test"}},
    )

    assert result.is_success
    assert result.data["image_slots"][0]["asset_origin"] == "generated"
    assert result.data["image_slots"][0]["status"] == "generated"
    assert result.data["image_slots"][0]["selected_asset_url"] == "https://cdn.example.com/generated.png"
    assert "AI 生成封面" in result.data["final_content_html"]


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
    assert result.data["skip_reason"] == "empty_content"
    assert result.data["template_options"]
