"""Tests for the Phase 5 account ops harness and conservative runtime policy."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.tables import AccountModel, ArticleDraftModel, TaskModel
from app.services.account_harness_service import account_harness_service
from app.services.task_service import task_service


async def _create_account(client, payload: dict) -> str:
    response = await client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["account_id"]


@pytest.mark.asyncio
async def test_account_run_records_ops_context_and_downgrades_full_auto(client, monkeypatch):
    async def _noop_background(*args, **kwargs):
        return None

    monkeypatch.setattr("app.api.account_routes._run_account_task_in_background", _noop_background)

    account_id = await _create_account(
        client,
        {
            "name": "Ops Harness Account",
            "positioning": "An account used to verify account-level ops judgment before runtime.",
            "operation_mode": "full_auto",
            "automation_plan": {
                "plan_type": "full_auto",
                "is_enabled": False,
                "run_strategy": "hybrid",
                "schedule_type": "daily",
                "schedule_config": {"time": "08:30"},
                "auto_publish_enabled": True,
                "publish_review_required": False,
            },
        },
    )

    run_response = await client.post(f"/api/v1/accounts/{account_id}/run")
    assert run_response.status_code == 200, run_response.text
    run_data = run_response.json()
    assert run_data["effective_mode"] == "semi_auto"

    task_id = run_data["task_id"]
    detail_response = await client.get(f"/api/v1/tasks/{task_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["ops_context"]["run_strategy"]["effective_mode"] == "semi_auto"
    assert detail["ops_context"]["run_strategy"]["allow_auto_publish"] is False
    assert detail["ops_context"]["run_strategy"]["degraded_from"] == "full_auto"

    account_response = await client.get(f"/api/v1/accounts/{account_id}")
    assert account_response.status_code == 200
    account_detail = account_response.json()
    assert account_detail["latest_effective_mode"] == "semi_auto"
    assert account_detail["latest_ops_degraded"] is True
    assert account_detail["latest_ops_context"]["run_strategy"]["effective_mode"] == "semi_auto"


@pytest.mark.asyncio
async def test_run_task_uses_effective_mode_for_draft_creation(db_session, monkeypatch):
    account = AccountModel(
        id="acc-ops-effective-mode",
        name="Effective Mode Account",
        positioning="Use task ops context to drive draft status.",
        operation_mode="full_auto",
        auto_publish_enabled=True,
        is_active=True,
        last_run_status="running",
    )
    task = TaskModel(
        id="task-ops-effective-mode",
        workflow_id="default_pipeline",
        status="pending",
        account_id=account.id,
        input_data={
            "positioning": account.positioning,
            "ops_context": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "account_health": {"status": "attention", "issues": []},
                "operation_stage": "style_learning",
                "run_strategy": {
                    "allow_run": True,
                    "requested_mode": "full_auto",
                    "effective_mode": "semi_auto",
                    "allow_auto_publish": False,
                    "preferred_reference_source_ids": [],
                    "avoid_recent_topics": [],
                    "preferred_content_lane": "Topic lane",
                    "degraded_from": "full_auto",
                    "degrade_reason": "reference_sources_insufficient",
                },
                "ops_notes": ["Downgraded for safety."],
                "signals": {
                    "enabled_reference_source_count": 0,
                    "pending_review_count": 0,
                    "recent_failed_publish_count": 0,
                    "recent_success_publish_count": 0,
                    "recent_failed_task_count": 0,
                },
                "fallback_used": False,
            },
        },
    )
    db_session.add_all([account, task])
    await db_session.commit()

    async def _fake_run(task_obj, db):
        now = datetime.now(timezone.utc)
        task_obj.status = "completed"
        task_obj.started_at = now
        task_obj.completed_at = now
        task_obj.result_data = {
            "content": {"content_markdown": "Body", "content_html": "<p>Body</p>"},
            "titles": {"selected_title": "Title", "candidates": ["Title"]},
            "topics": {"selected_topic": "Topic lane"},
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
    assert draft.draft_status == "pending_review"
    assert draft.source_type == "semi_auto_task"

    task_result = await db_session.execute(select(TaskModel).where(TaskModel.id == task.id))
    saved_task = task_result.scalar_one()
    assert saved_task.result_data["ops_context"]["run_strategy"]["effective_mode"] == "semi_auto"


def test_scheduler_backlog_block_survives_ops_agent_fallback():
    context = account_harness_service._normalize_ops_context(
        {
            "account": {
                "account_id": "acc-scheduler-block",
                "name": "Scheduler Block Account",
            },
            "automation_plan": {"plan_type": "semi_auto"},
            "reference_sources": [],
            "recent_tasks": [],
            "recent_drafts": [],
            "recent_publishes": [],
            "signals": {
                "enabled_reference_source_count": 0,
                "pending_review_count": account_harness_service.PENDING_REVIEW_BLOCK_THRESHOLD,
                "recent_failed_publish_count": 0,
                "recent_success_publish_count": 0,
                "recent_failed_task_count": 0,
                "preferred_content_lane": None,
            },
            "trigger": {"source": "scheduler", "requested_plan_type": "semi_auto"},
        },
        {
            "account_health": {"status": "attention", "issues": ["Ops agent fallback was required."]},
            "operation_stage": "style_learning",
            "run_strategy": {
                "allow_run": True,
                "effective_mode": "semi_auto",
                "allow_auto_publish": False,
                "preferred_reference_source_ids": [],
                "avoid_recent_topics": [],
                "preferred_content_lane": None,
            },
            "ops_notes": ["Fallback policy."],
        },
        fallback_used=True,
    )

    assert context["run_strategy"]["allow_run"] is False
    assert "Scheduler run blocked because review backlog is too large." in context["account_health"]["issues"]
