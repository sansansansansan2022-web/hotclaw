from sqlalchemy import select

from app.models.tables import ComposeSelectionSessionModel, RecommendedContentItemModel, ReferenceSourceModel, TaskModel
from app.services.account_run_dispatch_service import account_run_dispatch_service


async def _create_account(client, payload: dict) -> str:
    response = await client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["account_id"]


async def _create_recommendation(db_session, account_id: str, recommendation_id: str = "rec_demo_1") -> str:
    row = RecommendedContentItemModel(
        id=recommendation_id,
        account_id=account_id,
        title="OpenCLI: AI agent in terminal workflows",
        summary="A recent GitHub project that fits developer-tooling analysis.",
        source_type="github_repo",
        source_name="GitHub",
        source_url="https://github.com/example/opencli",
        relevance_score=0.92,
        authority_score=0.75,
        freshness_score=0.81,
        reason="High fit for an AI developer tools account.",
        topic_tags_json=["AI Agent", "Developer Tools"],
        source_payload_json={"full_name": "example/opencli"},
        status="new",
    )
    db_session.add(row)
    await db_session.commit()
    return row.id


async def _create_reference_source(db_session, account_id: str) -> int:
    row = ReferenceSourceModel(
        account_id=account_id,
        source_type="article_url",
        name="OpenAI Blog",
        source_value="https://openai.com/blog",
        notes="Primary reference source",
        is_enabled=True,
        sync_status="synced",
        article_count=3,
        metadata_json={"preview": "Official product and research updates."},
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row.id


async def _confirm_preview_and_outline(
    client,
    *,
    account_id: str,
    session_id: str,
    creation_note: str,
    preferred_lane: str,
    title_direction: str,
) -> dict:
    confirm_sources_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions/{session_id}/confirm-sources",
        json={"confirmed": True},
    )
    assert confirm_sources_response.status_code == 200, confirm_sources_response.text

    preview_response = await client.post(
        f"/api/v1/accounts/{account_id}/compose-preview",
        json={
            "selection_session_id": session_id,
            "creation_note": creation_note,
            "preferred_lane": preferred_lane,
            "title_direction": title_direction,
        },
    )
    assert preview_response.status_code == 200, preview_response.text
    preview_payload = preview_response.json()

    confirm_outline_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions/{session_id}/confirm-outline",
        json={
            "preview_version": preview_payload["selection_session"]["preview_version"],
            "approved_outline_seed": preview_payload["outline_preview"],
        },
    )
    assert confirm_outline_response.status_code == 200, confirm_outline_response.text
    return preview_payload


async def test_create_and_get_selection_session(client):
    account_id = await _create_account(
        client,
        {
            "name": "Compose Session Account",
            "positioning": "A technology account focused on AI product analysis and tooling.",
        },
    )

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions",
        json={
            "creation_note": "Focus on why the tool matters now.",
            "preferred_lane": "AI tools",
            "title_direction": "judgment-led",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["selection_session"]["account_id"] == account_id
    assert created["selection_session"]["creation_note"] == "Focus on why the tool matters now."
    assert created["selection_session"]["preferred_lane"] == "AI tools"
    assert created["selected_recommendations"] == []
    assert created["selected_reference_sources"] == []

    session_id = created["selection_session"]["id"]
    get_response = await client.get(
        f"/api/v1/accounts/{account_id}/selection-sessions/{session_id}"
    )
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["selection_session"]["id"] == session_id
    assert fetched["selection_session"]["status"] == "draft"


async def test_select_reference_sources_for_selection_session(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Compose References Account",
            "positioning": "A technology account that writes with curated sources.",
        },
    )
    reference_source_id = await _create_reference_source(db_session, account_id)

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions",
        json={},
    )
    assert create_response.status_code == 201, create_response.text
    session_id = create_response.json()["selection_session"]["id"]

    select_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions/{session_id}/reference-sources/select",
        json={"reference_source_ids": [reference_source_id]},
    )
    assert select_response.status_code == 200, select_response.text
    bundle = select_response.json()
    assert bundle["selection_session"]["selected_reference_source_ids"] == [str(reference_source_id)]
    assert len(bundle["selected_reference_sources"]) == 1
    assert bundle["selected_reference_sources"][0]["id"] == reference_source_id


async def test_submit_selection_session_creates_task_with_explicit_input(client, db_session, monkeypatch):
    account_id = await _create_account(
        client,
        {
            "name": "Compose Submit Account",
            "positioning": "A technology account focused on AI engineering tools and product judgment.",
        },
    )
    recommendation_id = await _create_recommendation(db_session, account_id)
    reference_source_id = await _create_reference_source(db_session, account_id)

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions",
        json={"reference_source_ids": [reference_source_id]},
    )
    assert create_response.status_code == 201, create_response.text
    session_id = create_response.json()["selection_session"]["id"]

    select_response = await client.post(
        f"/api/v1/accounts/{account_id}/recommendations/select",
        json={
            "recommendation_ids": [recommendation_id],
            "action": "use_for_creation",
            "selection_session_id": session_id,
        },
    )
    assert select_response.status_code == 200, select_response.text

    creation_note = "Focus on practical workflow value and adoption boundary."
    preferred_lane = "AI tools"
    title_direction = "judgment-led"
    await _confirm_preview_and_outline(
        client,
        account_id=account_id,
        session_id=session_id,
        creation_note=creation_note,
        preferred_lane=preferred_lane,
        title_direction=title_direction,
    )

    monkeypatch.setattr(account_run_dispatch_service, "schedule", lambda **kwargs: None)

    submit_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions/{session_id}/submit",
        json={
            "creation_note": creation_note,
            "preferred_lane": preferred_lane,
            "title_direction": title_direction,
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    payload = submit_response.json()
    assert payload["account_id"] == account_id
    assert payload["selection_session_id"] == session_id
    assert payload["status"] == "pending"

    task_result = await db_session.execute(
        select(TaskModel).where(TaskModel.id == payload["task_id"])
    )
    task = task_result.scalar_one()
    assert task.input_data["selection_session_id"] == session_id
    assert len(task.input_data["selected_recommendations"]) == 1
    assert len(task.input_data["selected_reference_sources"]) == 1
    assert "compose_preview" in task.input_data
    assert "query_plan" in task.input_data
    assert "outline_seed" in task.input_data

    session_result = await db_session.execute(
        select(ComposeSelectionSessionModel).where(ComposeSelectionSessionModel.id == session_id)
    )
    session = session_result.scalar_one()
    assert session.status == "submitted"
    assert session.source_confirmed is True
    assert session.outline_confirmed is True


async def test_preview_requires_confirmed_sources(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Compose Preview Guard",
            "positioning": "A technology account focused on research-backed product analysis.",
        },
    )
    recommendation_id = await _create_recommendation(db_session, account_id, recommendation_id="rec_preview_guard")
    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions",
        json={},
    )
    assert create_response.status_code == 201, create_response.text
    session_id = create_response.json()["selection_session"]["id"]

    select_response = await client.post(
        f"/api/v1/accounts/{account_id}/recommendations/select",
        json={
            "recommendation_ids": [recommendation_id],
            "action": "use_for_creation",
            "selection_session_id": session_id,
        },
    )
    assert select_response.status_code == 200, select_response.text

    preview_response = await client.post(
        f"/api/v1/accounts/{account_id}/compose-preview",
        json={
            "selection_session_id": session_id,
            "creation_note": "Test preview guard",
        },
    )
    assert preview_response.status_code == 400, preview_response.text
    assert "confirmed" in preview_response.json()["detail"]


async def test_changing_sources_resets_confirmations(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Compose Confirmation Reset",
            "positioning": "A technology account focused on AI tooling analysis.",
        },
    )
    recommendation_id = await _create_recommendation(db_session, account_id, recommendation_id="rec_confirmation_reset")
    reference_source_id = await _create_reference_source(db_session, account_id)

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions",
        json={"reference_source_ids": [reference_source_id]},
    )
    assert create_response.status_code == 201, create_response.text
    session_id = create_response.json()["selection_session"]["id"]

    select_response = await client.post(
        f"/api/v1/accounts/{account_id}/recommendations/select",
        json={
            "recommendation_ids": [recommendation_id],
            "action": "use_for_creation",
            "selection_session_id": session_id,
        },
    )
    assert select_response.status_code == 200, select_response.text

    await _confirm_preview_and_outline(
        client,
        account_id=account_id,
        session_id=session_id,
        creation_note="Confirm once",
        preferred_lane="AI tools",
        title_direction="judgment-led",
    )

    remove_response = await client.post(
        f"/api/v1/accounts/{account_id}/recommendations/select",
        json={
            "recommendation_ids": [recommendation_id],
            "action": "remove_from_creation",
            "selection_session_id": session_id,
        },
    )
    assert remove_response.status_code == 200, remove_response.text
    removed_payload = remove_response.json()
    assert removed_payload["selection_session"]["source_confirmed"] is False
    assert removed_payload["selection_session"]["outline_confirmed"] is False


async def test_remove_recommendation_from_creation_session(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Compose Remove Recommendation",
            "positioning": "A technology account focused on AI tooling analysis.",
        },
    )
    recommendation_id = await _create_recommendation(db_session, account_id, recommendation_id="rec_remove_demo")

    create_response = await client.post(
        f"/api/v1/accounts/{account_id}/selection-sessions",
        json={},
    )
    assert create_response.status_code == 201, create_response.text
    session_id = create_response.json()["selection_session"]["id"]

    select_response = await client.post(
        f"/api/v1/accounts/{account_id}/recommendations/select",
        json={
            "recommendation_ids": [recommendation_id],
            "action": "use_for_creation",
            "selection_session_id": session_id,
        },
    )
    assert select_response.status_code == 200, select_response.text
    assert select_response.json()["selection_session"]["selected_recommendation_ids"] == [recommendation_id]

    remove_response = await client.post(
        f"/api/v1/accounts/{account_id}/recommendations/select",
        json={
            "recommendation_ids": [recommendation_id],
            "action": "remove_from_creation",
            "selection_session_id": session_id,
        },
    )
    assert remove_response.status_code == 200, remove_response.text
    removed = remove_response.json()
    assert removed["selection_session"]["selected_recommendation_ids"] == []
    assert removed["selected_recommendations"] == []

    session_result = await db_session.execute(
        select(ComposeSelectionSessionModel).where(ComposeSelectionSessionModel.id == session_id)
    )
    session = session_result.scalar_one()
    assert session.selected_recommendation_ids_json == []
