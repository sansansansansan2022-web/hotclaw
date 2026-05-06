# HTML PPT Renderer Artifact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an HTML PPT-style browser preview artifact to HotClaw post-processing without changing the WeChat publish HTML path.

**Architecture:** Introduce a focused backend renderer service that converts the existing article payload, outline, sections, account context, and selected post-process template into a static deck artifact. `PostProcessService` attaches the artifact under `post_process_result.layout_artifacts`, while `TaskArtifactService` exposes a dedicated `layout_artifacts` task artifact for the UI/API.

**Tech Stack:** Python 3.11, FastAPI service layer, existing post-process pipeline, pytest.

---

### Task 1: Renderer Service Contract

**Files:**
- Create: `backend/app/services/html_ppt_layout_service.py`
- Test: `backend/tests/test_html_ppt_layout_service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_html_ppt_layout_service_builds_static_deck_artifact():
    from app.services.html_ppt_layout_service import html_ppt_layout_service

    artifact = html_ppt_layout_service.render(
        article={
            "selected_title": "Why terminal agents matter",
            "summary": "Explain the operator workflow shift.",
            "content_markdown": "# Why terminal agents matter\n\nIntro.\n\n## Why now\n\n- Adoption is real\n- Workflows are changing",
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
    assert artifact["slide_count"] >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_html_ppt_layout_service.py -q`

Expected: fail because `app.services.html_ppt_layout_service` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `HtmlPptLayoutService.render(...)` that returns a self-contained static HTML deck artifact using inline CSS and escaped content.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_html_ppt_layout_service.py -q`

Expected: pass.

### Task 2: Post-Process Attachment

**Files:**
- Modify: `backend/app/services/post_process_service.py`
- Test: `backend/tests/test_post_process_agent.py`

- [ ] **Step 1: Write the failing test**

Extend `test_post_process_agent_generates_wechat_layout_template` to assert:

```python
layout_artifacts = result.data["layout_artifacts"]
assert layout_artifacts["primary"]["artifact_type"] == "html_ppt_deck"
assert layout_artifacts["primary"]["status"] == "preview_ready"
assert layout_artifacts["primary"]["entry_html"].startswith("<!doctype html>")
assert result.data["wechat_publish_format"]["content_format"] == "wechat_inline_html"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_post_process_agent.py::test_post_process_agent_generates_wechat_layout_template -q`

Expected: fail because `layout_artifacts` is missing.

- [ ] **Step 3: Attach renderer output**

Import `html_ppt_layout_service` in `PostProcessService.prepare()` and add:

```python
layout_artifacts = {
    "primary": html_ppt_layout_service.render(
        article=article,
        outline_plan=outline_plan,
        section_drafts=input_data.get("section_drafts"),
        account_context=account_context,
        template=template,
        image_slots=image_slots,
    )
}
```

Return it alongside existing post-process fields.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_post_process_agent.py::test_post_process_agent_generates_wechat_layout_template -q`

Expected: pass.

### Task 3: Task Artifact Exposure

**Files:**
- Modify: `backend/app/services/task_artifact_service.py`
- Test: `backend/tests/test_task_artifact_api.py`

- [ ] **Step 1: Write the failing test**

Add a `post_process_result.layout_artifacts.primary` fixture and assert the API contains `layout_artifacts` with `display_payload.layout_artifacts.primary.artifact_type == "html_ppt_deck"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_task_artifact_api.py::test_task_artifacts_and_effective_input_contract -q`

Expected: fail because the artifact spec is missing.

- [ ] **Step 3: Add artifact spec and display branch**

Add an `ARTIFACT_SPECS` entry:

```python
{
    "artifact_key": "layout_artifacts",
    "stage": "post_process",
    "title": "Layout Artifacts",
    "source_node_ids": ("post_process_agent",),
}
```

Return `{"layout_artifacts": layout_artifacts}` from `_display_payload_for`.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
pytest backend/tests/test_html_ppt_layout_service.py backend/tests/test_post_process_agent.py::test_post_process_agent_generates_wechat_layout_template backend/tests/test_task_artifact_api.py::test_task_artifacts_and_effective_input_contract -q
```

Expected: all pass.
