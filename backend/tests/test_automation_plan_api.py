async def _create_account(client, payload: dict) -> str:
    response = await client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["account_id"]


async def test_new_account_creates_default_automation_plan(client):
    account_id = await _create_account(
        client,
        {
            "name": "Automation Default Account",
            "positioning": "Automation default account for testing account creation.",
            "operation_mode": "manual",
        },
    )

    plan_response = await client.get(f"/api/v1/accounts/{account_id}/automation-plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["config_source"] == "plan"
    assert plan["plan_type"] == "manual"
    assert plan["is_enabled"] is False
    assert plan["run_strategy"] == "manual_only"
    assert plan["schedule_type"] == "none"

    detail_response = await client.get(f"/api/v1/accounts/{account_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["automation_plan_summary"]["plan_type"] == "manual"


async def test_account_create_can_seed_recommended_automation_plan(client):
    account_id = await _create_account(
        client,
        {
            "name": "Automation Existing Account",
            "positioning": "An existing-like account with a recommended automation plan.",
            "operation_mode": "semi_auto",
            "automation_plan": {
                "plan_type": "semi_auto",
                "is_enabled": False,
                "run_strategy": "hybrid",
                "schedule_type": "weekly",
                "schedule_config": {"weekday": "wed", "time": "09:30"},
                "auto_publish_enabled": False,
                "publish_review_required": True,
            },
        },
    )

    plan_response = await client.get(f"/api/v1/accounts/{account_id}/automation-plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["plan_type"] == "semi_auto"
    assert plan["schedule_type"] == "weekly"
    assert plan["schedule_config"]["weekday"] == "wed"
    assert plan["schedule_config"]["time"] == "09:30"

    detail_response = await client.get(f"/api/v1/accounts/{account_id}")
    detail = detail_response.json()
    assert detail["operation_mode"] == "semi_auto"
    assert detail["posting_frequency"] == "weekly"
    assert detail["posting_time"] == "09:30"
    assert detail["auto_run_enabled"] is False


async def test_patch_automation_plan_updates_legacy_account_fields(client):
    account_id = await _create_account(
        client,
        {
            "name": "Automation Patch Account",
            "positioning": "Patch automation plan and mirror the effective values back to account detail.",
        },
    )

    patch_response = await client.patch(
        f"/api/v1/accounts/{account_id}/automation-plan",
        json={
            "plan_type": "full_auto",
            "is_enabled": True,
            "run_strategy": "scheduled",
            "schedule_type": "daily",
            "schedule_config": {"time": "08:15"},
            "auto_publish_enabled": True,
            "publish_review_required": False,
            "max_posts_per_day": 2,
            "min_interval_minutes": 180,
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    plan = patch_response.json()
    assert plan["plan_type"] == "full_auto"
    assert plan["is_enabled"] is True
    assert plan["auto_publish_enabled"] is True
    assert plan["schedule_type"] == "daily"

    detail_response = await client.get(f"/api/v1/accounts/{account_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["operation_mode"] == "full_auto"
    assert detail["auto_run_enabled"] is True
    assert detail["auto_publish_enabled"] is True
    assert detail["posting_frequency"] == "daily"
    assert detail["posting_time"] == "08:15"
    assert detail["max_posts_per_day"] == 2
    assert detail["min_interval_minutes"] == 180
    assert detail["automation_plan_summary"]["plan_type"] == "full_auto"


async def test_account_profile_patch_preserves_plan_only_publish_safeguards(client):
    account_id = await _create_account(
        client,
        {
            "name": "Automation Legacy Patch Account",
            "positioning": "Patch profile fields without clobbering plan-only safeguards.",
            "operation_mode": "semi_auto",
            "automation_plan": {
                "plan_type": "semi_auto",
                "is_enabled": True,
                "run_strategy": "hybrid",
                "schedule_type": "weekly",
                "schedule_config": {"weekday": "wed", "time": "09:30"},
                "auto_publish_enabled": True,
                "publish_review_required": False,
            },
        },
    )

    patch_response = await client.patch(
        f"/api/v1/accounts/{account_id}",
        json={
            "name": "Automation Legacy Patch Account Updated",
            "positioning": "Patch profile fields without clobbering plan-only safeguards.",
            "category": "",
            "audience": "",
            "tone_style": "",
            "posting_frequency": "weekly",
            "posting_time": "09:30",
            "content_strategy": "",
            "reference_accounts": "",
            "operation_mode": "semi_auto",
            "auto_run_enabled": True,
            "auto_publish_enabled": True,
            "is_active": True,
            "publish_paused": False,
            "max_posts_per_day": None,
            "min_interval_minutes": None,
        },
    )
    assert patch_response.status_code == 200, patch_response.text

    plan_response = await client.get(f"/api/v1/accounts/{account_id}/automation-plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["publish_review_required"] is False
    assert plan["schedule_config"]["weekday"] == "wed"


async def test_disable_account_persists_across_transaction_boundary(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Disable Persist Account",
            "positioning": "Disable account persistence test account.",
            "operation_mode": "manual",
        },
    )

    response = await client.post(f"/api/v1/accounts/{account_id}/disable")
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    await db_session.rollback()
    detail_response = await client.get(f"/api/v1/accounts/{account_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["is_active"] is False
