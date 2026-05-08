"""Tests for the Phase 6 structured content pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.agents.outline_planner_agent import OutlinePlannerAgent
from app.agents.section_writer_agent import SectionWriterAgent
from app.llm.base import LLMResponse
from app.models.tables import AccountModel, ArticleDraftModel, TaskModel, TaskNodeRunModel
from app.orchestrator.engine import orchestrator_engine
from app.services.article_assembler_service import article_assembler_service
from app.services.draft_service import draft_service
from app.services.task_service import task_service


def _fake_llm_response(payload: dict) -> LLMResponse:
    text = json.dumps(payload, ensure_ascii=False)
    return LLMResponse(content=text, model="mock", provider="mock", parsed=payload)


@pytest.mark.asyncio
async def test_outline_planner_fallback_returns_structured_outline():
    agent = OutlinePlannerAgent()
    result = await agent.fallback(
        Exception("boom"),
        {
            "titles": {"titles": [{"text": "A safer title"}]},
            "topics": {"topics": [{"title": "Reader anxiety"}]},
            "ops_context": {"run_strategy": {"preferred_content_lane": "warm analysis"}},
        },
    )

    assert result is not None
    assert result.is_success
    assert result.data["article_goal"]
    assert len(result.data["sections"]) >= 3
    assert result.data["sections"][0]["section_id"] == "s1"
    assert result.data["emotional_arc"] == "recognition -> diagnosis -> turn -> landing"
    assert result.data["sections"][0]["section_transition_hint"]


@pytest.mark.asyncio
async def test_section_writer_fallback_returns_section_drafts():
    agent = SectionWriterAgent()
    result = await agent.fallback(
        Exception("boom"),
        {
            "titles": {"titles": [{"text": "A safer title"}]},
            "topics": {"topics": [{"title": "Reader anxiety"}]},
            "outline_plan": {
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "Open strongly",
                        "summary": "Introduce the tension.",
                        "key_points": ["Lead with a relatable scene"],
                    }
                ]
            },
        },
    )

    assert result is not None
    assert result.is_success
    drafts = result.data["section_drafts"]
    assert len(drafts) == 1
    assert drafts[0]["section_id"] == "s1"
    assert drafts[0]["content_markdown"]


@pytest.mark.asyncio
async def test_outline_execute_falls_back_when_generated_outline_drifts(monkeypatch):
    async def _fake_completion(**kwargs):
        return _fake_llm_response(
            {
                "article_goal": "Write about vague workplace fatigue.",
                "opening_hook": "为什么你总觉得职场让人很累？",
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "先聊聊职场疲惫",
                        "purpose": "讨论一般性的职场状态",
                        "key_points": ["和当前题目没有关系"],
                    }
                ],
                "ending_cta": "祝你工作顺利。",
            }
        )

    monkeypatch.setattr("app.agents.outline_planner_agent.llm_gateway.complete", _fake_completion)

    agent = OutlinePlannerAgent()
    result = await agent.execute(
        {
            "profile": {"positioning_raw": "写给内容团队负责人的运营判断"},
            "topics": {"selected_topic": "为什么很多内容复盘越写越空"},
            "titles": {"selected_title": "很多复盘写到最后，只剩一句正确的废话"},
            "ops_context": {"run_strategy": {"preferred_content_lane": "运营洞察"}},
        },
        {},
    )

    assert result.is_success
    assert result.data["emotional_arc"] == "recognition -> diagnosis -> turn -> landing"
    assert "复盘" in result.data["opening_hook"] or "很多复盘写到最后" in result.data["summary"]


@pytest.mark.asyncio
async def test_section_writer_execute_falls_back_when_generated_sections_drift(monkeypatch):
    async def _fake_completion(**kwargs):
        return _fake_llm_response(
            {
                "section_drafts": [
                    {
                        "section_id": "s1",
                        "heading": "泛泛聊职场",
                        "summary": "和选题无关",
                        "content_markdown": "很多人都会在工作里感到压力，这是一种常见现象。",
                    }
                ]
            }
        )

    monkeypatch.setattr("app.agents.section_writer_agent.llm_gateway.complete", _fake_completion)

    agent = SectionWriterAgent()
    result = await agent.execute(
        {
            "titles": {"selected_title": "很多复盘写到最后，只剩一句正确的废话"},
            "topics": {"selected_topic": "为什么很多内容复盘越写越空"},
            "outline_plan": {
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "先把问题说透",
                        "summary": "说明复盘为什么会越写越空。",
                        "purpose": "围绕复盘跑题问题展开",
                        "key_points": ["把复盘写空的常见机制说清楚"],
                    }
                ]
            },
        },
        {},
    )

    assert result.is_success
    assert "复盘" in result.data["section_drafts"][0]["content_markdown"] or "复盘" in result.data["section_drafts"][0]["summary"]


def test_reference_source_context_prioritizes_preferred_sources():
    reference_context = article_assembler_service.build_reference_source_context(
        {
            "reference_sources": [
                {
                    "id": "1",
                    "name": "Warm Column",
                    "source_type": "pasted_article",
                    "notes": "Short, grounded openings and a calm closing.",
                    "preview": "Start with a lived moment, then turn the argument inward.",
                },
                {
                    "id": "2",
                    "name": "Sharp Newsletter",
                    "source_type": "article_url",
                    "notes": "Often opens with contradiction and closes with a concrete move.",
                    "preview": "A good draft does not explain the background for five paragraphs.",
                },
            ]
        },
        {"run_strategy": {"preferred_reference_source_ids": ["2"]}},
    )

    assert reference_context["selected_source_ids"][0] == "2"
    assert reference_context["preferred_source_names"][0] == "Sharp Newsletter"
    assert any("Warm Column" in item or "Sharp Newsletter" in item for item in reference_context["style_takeaways"])


def test_outline_and_section_prompts_include_reference_and_structure_guards():
    outline_agent = OutlinePlannerAgent()
    section_agent = SectionWriterAgent()
    input_data = {
        "profile": {"positioning_raw": "Write practical operator essays.", "tone": "warm, sharp"},
        "topics": {"selected_topic": "AI 内容团队怎么避免模板化"},
        "titles": {"selected_title": "AI 内容团队，最怕的不是写不出来"},
        "account_context": {
            "account_name": "Operator Notes",
            "positioning": "写给内容团队负责人的运营复盘",
            "audience": "内容负责人",
            "tone_style": "冷静但不端着",
            "content_strategy": "用真实运营观察拆解内容问题",
            "reference_sources": [
                {
                    "id": "ref-1",
                    "name": "Reference One",
                    "source_type": "pasted_article",
                    "notes": "喜欢从一个矛盾瞬间切入，再把判断拉出来。",
                    "preview": "真正的问题，不是工具太多，而是大家写出来的东西越来越像。",
                }
            ],
        },
        "ops_context": {
            "run_strategy": {
                "preferred_content_lane": "运营洞察",
                "preferred_reference_source_ids": ["ref-1"],
                "avoid_recent_topics": ["旧话题"],
            }
        },
        "outline_plan": {
            "article_goal": "Explain why templated content weakens a team.",
            "opening_hook": "你可能已经发现，团队写作越高效，文章反而越不像人写的。",
            "ending_cta": "把这篇转给还在追求产能却忽略表达的人。",
            "sections": [
                {
                    "section_id": "s1",
                    "heading": "先把问题说准",
                    "purpose": "让读者认出自己团队的问题",
                    "summary": "从真实协作场景切入。",
                    "key_points": ["别一上来解释背景", "先让人看到问题已经发生"],
                    "section_transition_hint": "认出问题后，再追原因。",
                }
            ],
        },
    }

    outline_prompt = outline_agent._build_user_prompt(input_data)
    section_prompt = section_agent._build_user_prompt(input_data)

    assert "REFERENCE STYLE BRIEF" in outline_prompt
    assert "section_transition_hint" in outline_prompt
    assert "opening_hook" in section_prompt
    assert "preferred_reference_source_ids" in section_prompt
    assert "Avoid these anti-patterns" in section_prompt


def test_text_matches_topic_accepts_shorter_meaningful_chinese_anchor_pairs():
    assert article_assembler_service.text_matches_topic(
        "这篇复盘最后还是写成了正确的废话，问题不在态度，在于没有把复盘写实。",
        selected_topic="为什么很多内容复盘越写越空",
        selected_title="很多复盘写到最后，只剩一句正确的废话",
    )


def test_article_assembler_builds_final_content():
    assembled = article_assembler_service.assemble_article(
        outline_plan={
            "article_goal": "Help the reader understand how to calm self-doubt.",
            "target_reader_takeaway": "Leave with one practical reflection.",
            "opening_hook": "You know that moment when your confidence drops for no obvious reason?",
            "ending_cta": "Invite the reader to save the article for the next low moment.",
            "sections": [
                {
                    "section_id": "s1",
                    "heading": "Name the feeling",
                    "summary": "Describe the common emotional pattern.",
                },
                {
                    "section_id": "s2",
                    "heading": "Reset the inner script",
                    "summary": "Offer a practical reframing move.",
                },
            ],
        },
        section_drafts={
            "section_drafts": [
                {
                    "section_id": "s1",
                    "heading": "Name the feeling",
                    "summary": "Describe the common emotional pattern.",
                    "content_markdown": "Self-doubt often arrives quietly before it turns loud.",
                },
                {
                    "section_id": "s2",
                    "heading": "Reset the inner script",
                    "summary": "Offer a practical reframing move.",
                    "content_markdown": "Replace vague blame with one concrete observation and one next step.",
                },
            ]
        },
        titles={"titles": [{"text": "When self-doubt takes over"}]},
        topics={"topics": [{"title": "self-doubt"}]},
    )

    assert assembled["selected_title"] == "When self-doubt takes over"
    assert assembled["selected_topic"] == "self-doubt"
    assert "## Name the feeling" in assembled["content_markdown"]
    assert "## Closing" not in assembled["content_markdown"]
    assert assembled["content_html"]
    assert "<h1>When self-doubt takes over</h1>" in assembled["content_html"]
    assert assembled["structure"]["sections"][0]["heading"] == "Name the feeling"
    assert assembled["word_count"] > 0


def test_article_assembler_normalizes_legacy_content_shape():
    result = article_assembler_service.normalize_result_data(
        {
            "topics": {"selected_topic": "reader confidence"},
            "titles": {
                "selected_topic": "reader confidence",
                "titles": [{"text": "A stronger title", "score": 9.1}],
            },
            "content": {
                "content_markdown": "# A stronger title\n\nBody copy.",
                "tags": ["confidence"],
            },
        }
    )

    assert result["content"]["selected_title"] == "A stronger title"
    assert result["content"]["selected_topic"] == "reader confidence"
    assert result["content"]["title_candidates"] == ["A stronger title"]
    assert result["content"]["summary"]
    assert result["content"]["content_html"]


@pytest.mark.asyncio
async def test_structured_pipeline_falls_back_to_legacy_writer(db_session, monkeypatch):
    task = TaskModel(
        id="task-structured-fallback",
        workflow_id="default_pipeline",
        status="pending",
        input_data={"positioning": "Test structured content fallback."},
    )
    db_session.add(task)
    await db_session.commit()

    async def _noop(*args, **kwargs):
        return None

    async def _fake_execute_node(node_def, input_data, context, trace_id, db):
        node_id = node_def["node_id"]
        if node_id == "context_building":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "effective_profile": {"domain": "growth", "tone": "warm"},
                    "account_context": None,
                    "ops_context": {},
                    "retrieved_memories": [],
                    "positioning": input_data.get("positioning", ""),
                },
            )
        if node_id == "hot_topic_analysis":
            return AgentResult("success", node_def["agent_id"], data={"hot_topics": [{"title": "Emotional resilience"}]})
        if node_id == "topic_selection":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "topics": [{"title": "How to stop self-doubt", "estimated_appeal": 0.92}],
                    "selected_topic": "How to stop self-doubt",
                    "titles": [{"text": "When self-doubt takes over", "score": 9.4}],
                },
            )
        if node_id == "content_drafting":
            return AgentResult(
                "failed",
                node_def["agent_id"],
                error={"code": "DRAFTING_FAIL", "message": "content drafting failed"},
            )
        if node_id == "content_writing_fallback":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "summary": "Fallback summary",
                    "content_markdown": "# When self-doubt takes over\n\nFallback body.",
                    "structure": {"sections": [{"heading": "Fallback", "summary": "Fallback"}]},
                    "tags": ["growth"],
                },
            )
        if node_id == "editorial_review":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={"editorial_passed": True, "style": {}, "structure": {}, "audit": {}, "combined_rewrite_suggestions": []},
            )
        raise AssertionError(f"Unexpected node: {node_id}")

    monkeypatch.setattr("app.orchestrator.engine.broadcaster.broadcast", _noop)
    monkeypatch.setattr("app.orchestrator.engine.broadcaster.close_task", _noop)
    monkeypatch.setattr(orchestrator_engine, "_execute_node", _fake_execute_node)

    saved_task = await db_session.get(TaskModel, task.id)
    result = await orchestrator_engine.run(saved_task, db_session)

    assert result["content_pipeline"]["fallback_to_content_writer"] is True
    assert result["content"]["selected_title"] == "When self-doubt takes over"
    assert result["content"]["summary"] == "Fallback summary"

    rows = await db_session.execute(
        select(TaskNodeRunModel).where(TaskNodeRunModel.task_id == task.id).order_by(TaskNodeRunModel.id)
    )
    statuses = {row.node_id: row.status for row in rows.scalars().all()}
    assert statuses["content_drafting"] == "failed"
    assert statuses["content_writing_fallback"] == "completed"
    assert statuses["article_assembler"] == "skipped"


@pytest.mark.asyncio
async def test_run_task_structured_result_still_creates_draft(db_session, monkeypatch):
    account = AccountModel(
        id="acc-structured-draft",
        name="Structured Draft Account",
        positioning="Use the structured pipeline to create drafts.",
        operation_mode="manual",
        auto_publish_enabled=False,
        is_active=True,
        last_run_status="running",
    )
    task = TaskModel(
        id="task-structured-draft",
        workflow_id="default_pipeline",
        status="pending",
        account_id=account.id,
        input_data={"positioning": account.positioning},
    )
    db_session.add_all([account, task])
    await db_session.commit()

    async def _fake_run(task_obj, db):
        now = datetime.now(timezone.utc)
        task_obj.status = "completed"
        task_obj.started_at = now
        task_obj.completed_at = now
        task_obj.result_data = {
            "profile": {"domain": "growth", "tone": "warm"},
            "topics": {"topics": [{"title": "self-doubt"}]},
            "titles": {
                "selected_topic": "self-doubt",
                "titles": [{"text": "When self-doubt takes over", "score": 9.4}],
            },
            "outline_plan": {
                "article_goal": "Help the reader regulate self-doubt.",
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "Name the moment",
                        "summary": "Show the reader the exact emotional moment.",
                    }
                ],
            },
            "section_drafts": {
                "section_drafts": [
                    {
                        "section_id": "s1",
                        "heading": "Name the moment",
                        "summary": "Show the reader the exact emotional moment.",
                        "content_markdown": "The spiral usually starts from one small moment of hesitation.",
                    }
                ]
            },
            "assembled_article": {
                "selected_topic": "self-doubt",
                "selected_title": "When self-doubt takes over",
                "title_candidates": ["When self-doubt takes over"],
                "summary": "A calm article about dealing with self-doubt.",
                "content_markdown": "# When self-doubt takes over\n\n## Name the moment\n\nThe spiral usually starts from one small moment of hesitation.",
                "structure": {"sections": [{"section_id": "s1", "heading": "Name the moment", "summary": "Show the reader the exact emotional moment."}]},
                "tags": ["growth", "confidence"],
                "word_count": 128,
            },
            "content_pipeline": {
                "version": "phase6-structured-v1",
                "used_structured_pipeline": True,
                "fallback_to_content_writer": False,
                "degraded": False,
            },
        }
        db.add(task_obj)
        await db.flush()
        return task_obj.result_data

    monkeypatch.setattr("app.services.task_service.orchestrator_engine.run", _fake_run)

    await task_service.run_task(task.id, db_session)

    draft_result = await db_session.execute(
        select(ArticleDraftModel).where(ArticleDraftModel.task_id == task.id)
    )
    draft = draft_result.scalar_one()
    assert draft.title == "When self-doubt takes over"
    assert draft.summary == "A calm article about dealing with self-doubt."
    assert draft.content_html
    assert draft.structure is not None
    assert draft.word_count > 0

    detail = await draft_service.get_draft_detail(draft.id, db_session)
    assert detail["content_html"]
    assert detail["outline_plan"]["article_goal"] == "Help the reader regulate self-doubt."
    assert detail["section_drafts"]["section_drafts"][0]["section_id"] == "s1"
