"""Regression tests for orchestration execution metadata and routing decisions."""

from app.orchestrator.engine import OrchestratorEngine
from app.orchestrator.workspace import Workspace


def test_inject_execution_meta_appends_stage_envelopes():
    engine = OrchestratorEngine()
    result_data = {"content": {"title": "x"}, "execution_meta": {"legacy_flag": True}}
    envelopes = [
        {"stage": "profile_parsing", "status": "ok"},
        {"stage": "audit", "status": "degraded"},
    ]

    payload = engine._inject_execution_meta(
        result_data=result_data,
        stage_envelopes=envelopes,
        degraded=True,
        review_only=True,
        task_id="task-meta-1",
    )

    execution_meta = payload["execution_meta"]
    assert execution_meta["legacy_flag"] is True
    assert execution_meta["stages"][:-1] == envelopes
    terminal_stage = execution_meta["stages"][-1]
    assert terminal_stage["stage"] == "terminal_publishability"
    assert terminal_stage["task_id"] == "task-meta-1"
    assert terminal_stage["status"] == "degraded"
    assert execution_meta["single_gate_mode"] is True
    assert execution_meta["degraded"] is True
    assert execution_meta["publishability"] == "review_only"


def test_audit_blocker_skips_rewrite():
    engine = OrchestratorEngine()
    blocker_audit = {"publish_decision": "blocker", "risk_level": "high", "rewrite_required": True}
    medium_audit = {"publish_decision": "rewrite", "risk_level": "medium", "rewrite_required": False}
    blocker_workspace = Workspace(task_id="task-1", input_data={})
    medium_workspace = Workspace(task_id="task-2", input_data={})
    blocker_workspace.set("audit_result", blocker_audit)
    medium_workspace.set("audit_result", medium_audit)

    assert engine._is_audit_blocker(blocker_audit) is True
    assert engine._should_run_rewrite(blocker_workspace) is False
    assert engine._should_run_rewrite(medium_workspace) is True
