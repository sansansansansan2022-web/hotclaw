"""Tests for workspace and orchestrator core logic."""

import pytest
from app.orchestrator.workspace import Workspace


def test_workspace_basic_operations():
    """Normal case: workspace get/set/snapshot."""
    ws = Workspace(task_id="test_001", input_data={"positioning": "test input"})

    assert ws.get_input() == {"positioning": "test input"}
    assert ws.get("nonexistent") is None

    ws.set("profile", {"domain": "test"})
    assert ws.get("profile") == {"domain": "test"}

    snap = ws.snapshot()
    assert "input" in snap
    assert "profile" in snap


def test_workspace_extract_for_agent():
    """Normal case: extract agent input from workspace."""
    ws = Workspace(task_id="test_002", input_data={"positioning": "tech blog"})
    ws.set("profile", {"domain": "tech", "tone": "professional"})

    # Extract with input mapping
    result = ws.extract_for_agent({
        "positioning": "input.positioning",
        "profile": "profile",
    })
    assert result["positioning"] == "tech blog"
    assert result["profile"]["domain"] == "tech"


def test_workspace_extract_missing_key():
    """Error case: extract a key that doesn't exist in workspace."""
    ws = Workspace(task_id="test_003", input_data={})
    result = ws.extract_for_agent({"missing": "nonexistent_key"})
    assert result["missing"] is None
