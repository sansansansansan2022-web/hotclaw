"""Tests for the Phase 6 structured content pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.agents.outline_planner_agent import OutlinePlannerAgent
from app.agents.section_writer_agent import SectionWriterAgent
from app.models.tables import AccountModel, ArticleDraftModel, TaskModel, TaskNodeRunModel
from app.orchestrator.engine import orchestrator_engine
from app.services.article_assembler_service import article_assembler_service
from app.services.draft_service import draft_service
from app.services.task_service import task_service


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
        if node_id == "profile_parsing":
            return AgentResult("success", node_def["agent_id"], data={"domain": "growth", "tone": "warm"})
        if node_id == "hot_topic_analysis":
            return AgentResult("success", node_def["agent_id"], data={"hot_topics": [{"title": "Emotional resilience"}]})
        if node_id == "topic_planning":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={"topics": [{"title": "How to stop self-doubt", "estimated_appeal": 0.92}]},
            )
        if node_id == "title_generation":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "selected_topic": "How to stop self-doubt",
                    "titles": [{"text": "When self-doubt takes over", "score": 9.4}],
                },
            )
        if node_id == "outline_planner":
            return AgentResult(
                "failed",
                node_def["agent_id"],
                error={"code": "OUTLINE_FAIL", "message": "outline generation failed"},
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
        if node_id == "audit":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={"passed": True, "risk_level": "low", "overall_comment": "ok", "issues": []},
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
    assert statuses["outline_planner"] == "failed"
    assert statuses["content_writing_fallback"] == "completed"
    assert statuses["section_writer"] == "skipped"
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
    assert draft.structure is not None
    assert draft.word_count > 0

    detail = await draft_service.get_draft_detail(draft.id, db_session)
    assert detail["outline_plan"]["article_goal"] == "Help the reader regulate self-doubt."
    assert detail["section_drafts"]["section_drafts"][0]["section_id"] == "s1"
