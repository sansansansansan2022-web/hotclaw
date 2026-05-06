"""Tests for Phase 6C review and rewrite integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.agents.base import AgentResult
from app.agents.rewrite_agent import RewriteAgent
from app.agents.structure_reviewer_agent import StructureReviewerAgent
from app.agents.style_reviewer_agent import StyleReviewerAgent
from app.llm.base import LLMResponse
from app.models.tables import AccountModel, ArticleDraftModel, TaskModel, TaskNodeRunModel
from app.orchestrator.engine import orchestrator_engine
from app.services.article_assembler_service import article_assembler_service
from app.services.task_service import task_service


def _fake_llm_response(payload: dict) -> LLMResponse:
    text = json.dumps(payload)
    return LLMResponse(content=text, model="mock", provider="mock", parsed=payload)


@pytest.mark.asyncio
async def test_style_reviewer_execute_normalizes_output(monkeypatch):
    async def _fake_completion(**kwargs):
        return _fake_llm_response(
            {
                "passed": False,
                "score": 0.61,
                "summary": "Tone drifts into generic guidance in the middle section.",
                "issues": [
                    {
                        "code": "style_drift",
                        "severity": "medium",
                        "message": "The article sounds more generic than the account voice.",
                        "section_id": "s2",
                        "suggestion": "Restore the warmer first-person voice.",
                        "evidence_excerpt": "At this moment, it is important to note",
                    }
                ],
                "rewrite_suggestions": ["Tighten abstract phrasing in the middle section."],
            }
        )

    monkeypatch.setattr("app.agents.style_reviewer_agent.llm_gateway.complete", _fake_completion)

    agent = StyleReviewerAgent()
    result = await agent.execute(
        {
            "assembled_article": {
                "selected_title": "Test title",
                "content_markdown": "# Test title\n\nBody copy.",
            },
            "account_context": {"tone_style": "warm, grounded"},
        },
        {},
    )

    assert result.is_success
    assert result.data["reviewer"] == "style_reviewer"
    assert result.data["score"] == pytest.approx(0.61)
    assert result.data["issues"][0]["code"] == "style_drift"
    assert result.data["issues"][0]["section_id"] == "s2"
    assert result.data["issues"][0]["evidence_excerpt"] == "At this moment, it is important to note"


@pytest.mark.asyncio
async def test_structure_reviewer_execute_normalizes_output(monkeypatch):
    async def _fake_completion(**kwargs):
        return _fake_llm_response(
            {
                "passed": False,
                "score": 0.55,
                "summary": "The close is too abrupt and the second section is thin.",
                "issues": [
                    {
                        "code": "weak_closing",
                        "severity": "medium",
                        "message": "The ending does not cash out the article promise.",
                        "section_id": "s3",
                        "evidence_excerpt": "希望这篇文章对你有所启发",
                    }
                ],
                "rewrite_suggestions": ["Strengthen the closing with a clearer takeaway."],
            }
        )

    monkeypatch.setattr("app.agents.structure_reviewer_agent.llm_gateway.complete", _fake_completion)

    agent = StructureReviewerAgent()
    result = await agent.execute(
        {
            "outline_plan": {"sections": [{"section_id": "s1", "heading": "Opening"}]},
            "assembled_article": {
                "selected_title": "Test title",
                "content_markdown": "# Test title\n\nBody copy.",
            },
        },
        {},
    )

    assert result.is_success
    assert result.data["reviewer"] == "structure_reviewer"
    assert result.data["issues"][0]["code"] == "weak_closing"
    assert result.data["issues"][0]["evidence_excerpt"] == "希望这篇文章对你有所启发"


@pytest.mark.asyncio
async def test_rewrite_agent_execute_normalizes_output(monkeypatch):
    async def _fake_completion(**kwargs):
        return _fake_llm_response(
            {
                "used_rewrite": True,
                "revised_content_markdown": "# Revised title\n\nImproved body copy.",
                "revision_summary": "Tightened the tone and strengthened the ending.",
                "fixed_issues": ["style_drift", "weak_closing"],
                "changed_sections": ["s2", "s3"],
            }
        )

    monkeypatch.setattr("app.agents.rewrite_agent.llm_gateway.complete", _fake_completion)

    agent = RewriteAgent()
    result = await agent.execute(
        {
            "assembled_article": {
                "selected_title": "Original title",
                "content_markdown": "# Original title\n\nOriginal body copy.",
            },
            "style_review": {"issues": [{"code": "style_drift"}]},
            "structure_review": {"issues": [{"code": "weak_closing"}]},
        },
        {},
    )

    assert result.is_success
    assert result.data["used_rewrite"] is True
    assert "Improved body copy." in result.data["revised_content_markdown"]
    assert result.data["fixed_issues"] == ["style_drift", "weak_closing"]


def test_reviewer_and_rewrite_prompts_include_reference_context_and_issue_focus():
    style_agent = StyleReviewerAgent()
    structure_agent = StructureReviewerAgent()
    rewrite_agent = RewriteAgent()
    input_data = {
        "assembled_article": {
            "selected_title": "别把 AI 写作变成流水线",
            "selected_topic": "AI 写作团队的模板化问题",
            "summary": "一篇关于内容团队写作变形的文章",
            "content_markdown": "# 别把 AI 写作变成流水线\n\n## 开头\n\n问题已经发生。\n\n## 中段\n\n真正的问题不是不会写，而是越写越像。\n\n## 结尾\n\n希望对你有帮助。",
        },
        "outline_plan": {
            "opening_hook": "你可能已经发现，团队越追求稳定产出，文章越像一个模子里出来的。",
            "ending_cta": "把这篇发给那个还在只盯产能表的人。",
            "sections": [{"section_id": "s1", "heading": "开头", "purpose": "让问题先发生"}],
        },
        "section_drafts": {
            "section_drafts": [
                {
                    "section_id": "s1",
                    "heading": "开头",
                    "summary": "让问题先发生",
                    "content_markdown": "问题已经发生。",
                }
            ]
        },
        "account_context": {
            "account_name": "Content Ops Weekly",
            "positioning": "写给内容团队负责人的运营观察",
            "tone_style": "判断明确，但不端着",
            "reference_sources": [
                {
                    "id": "ref-1",
                    "name": "Reference One",
                    "source_type": "pasted_article",
                    "notes": "喜欢从矛盾瞬间切入，不爱长背景。",
                    "preview": "真正的差距，常常不是方法，而是你到底有没有看到问题已经发生。",
                }
            ],
        },
        "ops_context": {
            "run_strategy": {
                "preferred_content_lane": "运营洞察",
                "preferred_reference_source_ids": ["ref-1"],
            }
        },
        "style_review": {
            "reviewer": "style_reviewer",
            "issues": [{"code": "style_drift", "severity": "medium", "section_id": "s1", "message": "太泛"}],
        },
        "structure_review": {
            "reviewer": "structure_reviewer",
            "issues": [{"code": "weak_closing", "severity": "medium", "section_id": "s3", "message": "收尾太软"}],
        },
    }

    style_prompt = style_agent._build_user_prompt(input_data)
    structure_prompt = structure_agent._build_user_prompt(input_data)
    rewrite_prompt = rewrite_agent._build_user_prompt(input_data)

    assert "REFERENCE STYLE BRIEF" in style_prompt
    assert "allowed_issue_codes" in style_prompt
    assert "SECTION SUMMARY" in structure_prompt
    assert "reference_structure_missed" in structure_prompt
    assert "REVIEW FOCUS" in rewrite_prompt
    assert "style_drift" in rewrite_prompt
    assert "priority_issues" in rewrite_prompt


def test_article_assembler_prefers_rewrite_but_keeps_assembled_baseline():
    normalized = article_assembler_service.normalize_result_data(
        {
            "assembled_article": {
                "selected_title": "Original title",
                "selected_topic": "self-doubt",
                "title_candidates": ["Original title"],
                "summary": "Original summary",
                "content_markdown": "# Original title\n\nOriginal body copy.",
                "structure": {"sections": [{"section_id": "s1", "heading": "Opening", "summary": "Intro"}]},
                "tags": ["growth"],
                "word_count": 12,
            },
            "rewrite_result": {
                "used_rewrite": True,
                "revised_content_markdown": "# Original title\n\nRevised body copy.",
                "revision_summary": "Tightened the article.",
            },
        }
    )

    assert normalized["assembled_article"]["content_markdown"] == "# Original title\n\nOriginal body copy."
    assert normalized["content"]["content_markdown"] == "# Original title\n\nRevised body copy."


@pytest.mark.asyncio
async def test_reviewer_failure_does_not_block_pipeline(db_session, monkeypatch):
    task = TaskModel(
        id="task-reviewer-best-effort",
        workflow_id="default_pipeline",
        status="pending",
        input_data={"positioning": "Test reviewer best effort."},
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
            return AgentResult("success", node_def["agent_id"], data={"hot_topics": [{"title": "Confidence"}]})
        if node_id == "topic_planning":
            return AgentResult("success", node_def["agent_id"], data={"topics": [{"title": "Confidence reset"}]})
        if node_id == "title_generation":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={"selected_topic": "Confidence reset", "titles": [{"text": "How to reset confidence"}]},
            )
        if node_id == "outline_planner":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "article_goal": "Help readers rebuild confidence.",
                    "sections": [{"section_id": "s1", "heading": "Opening", "summary": "Open the article."}],
                },
            )
        if node_id == "section_writer":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "section_drafts": [
                        {
                            "section_id": "s1",
                            "heading": "Opening",
                            "summary": "Open the article.",
                            "content_markdown": "Body copy.",
                        }
                    ]
                },
            )
        if node_id == "article_assembler":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "selected_title": "How to reset confidence",
                    "selected_topic": "Confidence reset",
                    "title_candidates": ["How to reset confidence"],
                    "summary": "Original summary",
                    "content_markdown": "# How to reset confidence\n\nBody copy.",
                    "structure": {"sections": [{"section_id": "s1", "heading": "Opening", "summary": "Open the article."}]},
                    "tags": ["growth"],
                    "word_count": 18,
                },
            )
        if node_id == "style_reviewer":
            return AgentResult(
                "failed",
                node_def["agent_id"],
                error={"code": "STYLE_REVIEW_FAILED", "message": "style review unavailable"},
            )
        if node_id == "structure_reviewer":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "reviewer": "structure_reviewer",
                    "passed": True,
                    "score": 0.9,
                    "summary": "Structure is sound.",
                    "issues": [],
                    "rewrite_suggestions": [],
                },
            )
        if node_id == "rewrite_agent":
            return AgentResult(
                "success",
                node_def["agent_id"],
                data={
                    "used_rewrite": True,
                    "revised_content_markdown": "# How to reset confidence\n\nRevised body copy.",
                    "revision_summary": "Smoothed the pacing.",
                    "fixed_issues": ["style_drift"],
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

    assert result["style_review"]["failed"] is True
    assert result["structure_review"]["passed"] is True
    assert result["rewrite_result"]["used_rewrite"] is True
    assert "Revised body copy." in result["content"]["content_markdown"]
    assert "Body copy." in result["assembled_article"]["content_markdown"]

    rows = await db_session.execute(
        select(TaskNodeRunModel).where(TaskNodeRunModel.task_id == task.id).order_by(TaskNodeRunModel.id)
    )
    statuses = {row.node_id: row.status for row in rows.scalars().all()}
    assert statuses["style_reviewer"] == "failed"
    assert statuses["rewrite_agent"] == "completed"
    assert statuses["audit"] == "completed"


@pytest.mark.asyncio
async def test_rewrite_failure_still_creates_draft(db_session, monkeypatch):
    account = AccountModel(
        id="acc-rewrite-failed",
        name="Rewrite Failed Account",
        positioning="Create safe drafts even when rewrite fails.",
        operation_mode="manual",
        auto_publish_enabled=False,
        is_active=True,
        last_run_status="running",
    )
    task = TaskModel(
        id="task-rewrite-failed",
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
            "assembled_article": {
                "selected_topic": "confidence",
                "selected_title": "Original draft",
                "title_candidates": ["Original draft"],
                "summary": "Original summary",
                "content_markdown": "# Original draft\n\nOriginal body copy.",
                "structure": {"sections": [{"section_id": "s1", "heading": "Opening", "summary": "Intro"}]},
                "tags": ["growth"],
                "word_count": 12,
            },
            "style_review": {"reviewer": "style_reviewer", "passed": False, "summary": "Needs polish", "issues": []},
            "structure_review": {"reviewer": "structure_reviewer", "passed": True, "summary": "Good structure", "issues": []},
            "review_results": [
                {"reviewer": "style_reviewer", "passed": False, "summary": "Needs polish", "issues": []},
                {"reviewer": "structure_reviewer", "passed": True, "summary": "Good structure", "issues": []},
            ],
            "rewrite_result": {
                "used_rewrite": False,
                "rewrite_failed": True,
                "revision_summary": "Rewrite failed. Keeping the assembled draft.",
                "failure_reason": "rewrite timeout",
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
    assert draft.content_markdown == "# Original draft\n\nOriginal body copy."


@pytest.mark.asyncio
async def test_rewrite_success_updates_draft_content(db_session, monkeypatch):
    account = AccountModel(
        id="acc-rewrite-success",
        name="Rewrite Success Account",
        positioning="Use rewritten content when available.",
        operation_mode="manual",
        auto_publish_enabled=False,
        is_active=True,
        last_run_status="running",
    )
    task = TaskModel(
        id="task-rewrite-success",
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
            "assembled_article": {
                "selected_topic": "confidence",
                "selected_title": "Original draft",
                "title_candidates": ["Original draft"],
                "summary": "Original summary",
                "content_markdown": "# Original draft\n\nOriginal body copy.",
                "structure": {"sections": [{"section_id": "s1", "heading": "Opening", "summary": "Intro"}]},
                "tags": ["growth"],
                "word_count": 12,
            },
            "style_review": {"reviewer": "style_reviewer", "passed": False, "summary": "Needs polish", "issues": []},
            "structure_review": {"reviewer": "structure_reviewer", "passed": False, "summary": "Close stronger", "issues": []},
            "review_results": [
                {"reviewer": "style_reviewer", "passed": False, "summary": "Needs polish", "issues": []},
                {"reviewer": "structure_reviewer", "passed": False, "summary": "Close stronger", "issues": []},
            ],
            "rewrite_result": {
                "used_rewrite": True,
                "revised_content_markdown": "# Original draft\n\nRevised body copy.",
                "revision_summary": "Softened the tone and improved the ending.",
                "fixed_issues": ["style_drift", "weak_closing"],
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
    assert draft.content_markdown == "# Original draft\n\nRevised body copy."
