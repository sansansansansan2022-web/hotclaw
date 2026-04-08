from app.schemas.account_onboarding import ExistingAccountAnalysisResponse
from app.services.account_onboarding_service import account_onboarding_service


async def test_analyze_existing_account_returns_structured_payload(client, monkeypatch):
    async def _fake_analyze(_payload):
        return ExistingAccountAnalysisResponse(
            account_name="Legacy Account",
            inferred_positioning="Focus on practical operator lessons for a mature public account.",
            inferred_audience="Operators and growth leads.",
            inferred_tone_style="Practical, steady, and explanatory.",
            inferred_content_strategy="Keep recurring columns and review the strongest historical topics first.",
            inferred_reference_accounts_summary="Observed from legacy materials.",
            recommended_operation_mode="semi_auto",
            onboarding_notes=["Looks stable enough for semi-auto review."],
            extracted_topics=["growth", "content ops", "wechat"],
            style_summary="Long-form and explain-first.",
            analysis_confidence="medium",
            source_summary="Pasted article bodies: 2 | URL inputs: 1",
            used_article_count=2,
        )

    monkeypatch.setattr(account_onboarding_service, "analyze_existing_account", _fake_analyze)

    response = await client.post(
        "/api/v1/account-onboarding/analyze-existing",
        json={
            "account_name": "Legacy Account",
            "article_urls": ["https://example.com/a"],
            "article_texts": ["Article one", "Article two"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_name"] == "Legacy Account"
    assert body["recommended_operation_mode"] == "semi_auto"
    assert body["used_article_count"] == 2
    assert body["extracted_topics"] == ["growth", "content ops", "wechat"]


async def test_analyze_existing_account_requires_materials(client):
    response = await client.post(
        "/api/v1/account-onboarding/analyze-existing",
        json={"account_name": "Legacy Account", "article_urls": [], "article_texts": []},
    )

    assert response.status_code == 400
    assert "Provide at least one article URL or pasted article text." in response.json()["detail"]
