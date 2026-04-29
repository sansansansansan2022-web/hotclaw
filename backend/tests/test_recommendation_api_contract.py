from sqlalchemy import select
from types import SimpleNamespace
from datetime import datetime, timezone

from app.models.tables import RecommendedContentItemModel
from app.services.account_service import account_service
from app.services.news_source_service import news_source_service
from app.services.recommendation_service import recommendation_service
from app.skills.services.skill_router_service import skill_router_service
from app.services.account_analysis_service import account_analysis_service


async def _create_account(client, payload: dict) -> str:
    response = await client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["account_id"]


async def _seed_recommendation(
    db_session,
    *,
    account_id: str,
    recommendation_id: str,
    title: str,
    source_type: str = "github_repo",
    relevance_score: float,
    authority_score: float,
    freshness_score: float,
    source_payload_json: dict | None = None,
    status: str = "new",
    published_at=None,
):
    row = RecommendedContentItemModel(
        id=recommendation_id,
        account_id=account_id,
        title=title,
        summary=f"Summary for {title}",
        source_type=source_type,
        source_name="GitHub" if source_type == "github_repo" else "Public Search",
        source_url=f"https://example.com/{recommendation_id}",
        relevance_score=relevance_score,
        authority_score=authority_score,
        freshness_score=freshness_score,
        reason="Account-fit recommendation",
        topic_tags_json=["AI", "Developer Tools"],
        source_payload_json=source_payload_json or {},
        status=status,
        published_at=published_at,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def test_list_recommendations_bucket_high_and_extended(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Contract Account",
            "positioning": "A developer-facing AI tooling account.",
        },
    )

    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_high_1",
        title="High 1",
        relevance_score=0.88,
        authority_score=0.72,
        freshness_score=0.66,
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_high_2",
        title="High 2",
        relevance_score=0.82,
        authority_score=0.71,
        freshness_score=0.62,
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_high_3",
        title="High 3",
        relevance_score=0.79,
        authority_score=0.68,
        freshness_score=0.64,
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_ext_1",
        title="Extended 1",
        relevance_score=0.58,
        authority_score=0.54,
        freshness_score=0.49,
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_ext_2",
        title="Extended 2",
        relevance_score=0.52,
        authority_score=0.50,
        freshness_score=0.48,
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_low_1",
        title="Low 1",
        relevance_score=0.22,
        authority_score=0.18,
        freshness_score=0.31,
    )

    response = await client.get(f"/api/v1/accounts/{account_id}/recommendations?min_count=5")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["min_count"] == 5
    assert payload["coverage"]["high_relevance_count"] == 5
    assert payload["coverage"]["extended_count"] == 0
    assert payload["coverage"]["returned_count"] == 5
    assert payload["coverage"]["meets_requested_min_count"] is True
    assert payload["coverage"]["relaxed_count"] == 2
    assert payload["shortage_notice"]["status"] == "ok"
    assert payload["shortage_notice"]["reason_code"] is None
    assert [item["id"] for item in payload["high_relevance_items"]] == [
        "rec_high_1",
        "rec_high_2",
        "rec_high_3",
        "rec_ext_1",
        "rec_ext_2",
    ]
    assert payload["extended_items"] == []
    returned_ids = {
        item["id"]
        for item in [*payload["high_relevance_items"], *payload["extended_items"]]
    }
    assert "rec_low_1" not in returned_ids


async def test_list_recommendations_rejects_invalid_min_count(client):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Invalid Min Count",
            "positioning": "A developer-facing AI tooling account.",
        },
    )
    response = await client.get(f"/api/v1/accounts/{account_id}/recommendations?min_count=6")
    assert response.status_code == 400, response.text
    assert "min_count" in response.json()["detail"]


async def test_list_recommendations_keeps_stale_selected_items_below_fresh_candidates(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Freshness Account",
            "positioning": "A developer-facing AI tooling account.",
        },
    )

    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_selected_old",
        title="Old selected item",
        relevance_score=0.51,
        authority_score=0.50,
        freshness_score=0.35,
        status="selected",
        published_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_new_fresh",
        title="Fresh candidate",
        relevance_score=0.45,
        authority_score=0.60,
        freshness_score=1.00,
        published_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
    )

    response = await client.get(f"/api/v1/accounts/{account_id}/recommendations?min_count=5")

    assert response.status_code == 200, response.text
    payload = response.json()
    returned_items = [*payload["high_relevance_items"], *payload["extended_items"]]
    assert returned_items[0]["title"] == "Fresh candidate"


async def test_list_recommendations_promotes_decent_news_matches_into_high_relevance(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Adaptive High Relevance",
            "positioning": "An AI product strategy account for technical operators.",
        },
    )

    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_news_highish_1",
        title="Agent workflow signals from enterprise platform releases",
        source_type="news_article",
        relevance_score=0.66,
        authority_score=0.58,
        freshness_score=0.74,
        source_payload_json={"account_fit": {"score": 0.72}},
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_news_highish_2",
        title="AI coding tools move from assistants to workflow layers",
        source_type="news_article",
        relevance_score=0.63,
        authority_score=0.55,
        freshness_score=0.70,
        source_payload_json={"account_fit": {"score": 0.69}},
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_news_extended_1",
        title="General AI product news roundup",
        source_type="news_article",
        relevance_score=0.49,
        authority_score=0.46,
        freshness_score=0.60,
        source_payload_json={"account_fit": {"score": 0.42}},
    )

    response = await client.get(f"/api/v1/accounts/{account_id}/recommendations?min_count=5")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["coverage"]["high_relevance_count"] >= 1
    assert payload["high_relevance_items"][0]["id"] in {"rec_news_highish_1", "rec_news_highish_2"}


async def test_refresh_recommendations_returns_bucketed_shape(client, db_session, monkeypatch):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Refresh Account",
            "positioning": "A developer-facing AI tooling account.",
        },
    )
    high = await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_refresh_high",
        title="Refresh High",
        relevance_score=0.84,
        authority_score=0.72,
        freshness_score=0.69,
        source_payload_json={"collector": {"source_key": "news_article_feed"}},
    )
    extended = await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_refresh_extended",
        title="Refresh Extended",
        relevance_score=0.56,
        authority_score=0.51,
        freshness_score=0.47,
        source_payload_json={"collector": {"source_key": "news_article_feed"}},
    )

    async def _fake_refresh(target_account_id: str, db):
        assert target_account_id == account_id
        result = await db.execute(
            select(RecommendedContentItemModel).where(RecommendedContentItemModel.account_id == account_id)
        )
        rows = list(result.scalars().all())
        return {
            "rows": rows,
            "diagnostics": {
                "source_diagnostics": [
                    {
                        "source_key": "news_article_feed",
                        "label": "News Feed",
                        "source_type": "news_article",
                        "status": "success",
                        "query": "ai tooling",
                        "candidate_count": len(rows),
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": None,
                        "error_message": None,
                        "detail": None,
                    }
                ],
                "filter_diagnostics": {
                    "raw_candidate_count": len(rows),
                    "high_relevance_count": 1,
                    "extended_count": 1,
                    "filtered_out_count": 0,
                    "filtered_low_relevance_count": 0,
                    "filtered_low_authority_count": 0,
                    "sources_with_candidates": 1,
                    "sources_failed_or_disabled": 0,
                },
            },
            "refreshed_at": None,
        }

    monkeypatch.setattr(recommendation_service, "refresh_recommendations", _fake_refresh)

    response = await client.post(f"/api/v1/accounts/{account_id}/recommendations/refresh?min_count=5")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["min_count"] == 5
    assert payload["coverage"]["high_relevance_count"] == 2
    assert payload["coverage"]["extended_count"] == 0
    assert payload["coverage"]["returned_count"] == 2
    assert payload["coverage"]["shortage_count"] == 3
    assert payload["coverage"]["relaxed_count"] == 1
    assert payload["shortage_notice"]["status"] == "insufficient_total"
    assert payload["shortage_notice"]["reason_code"] == "insufficient_total"
    assert payload["source_diagnostics"][0]["label"] == "News Feed"
    assert payload["filter_diagnostics"]["high_relevance_count"] == payload["coverage"]["high_relevance_count"]
    returned_ids = [
        item["id"] for item in [*payload["high_relevance_items"], *payload["extended_items"]]
    ]
    assert high.id in returned_ids
    assert extended.id in returned_ids


async def test_refresh_recommendations_real_service_serializes_new_rows_without_greenlet(client, monkeypatch):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Refresh Real Service",
            "positioning": "An AI product and tooling account for builders.",
            "audience": "AI product managers and engineering leads",
            "tone_style": "Analytical and practical",
        },
    )

    snapshot = SimpleNamespace(
        id="ins_refresh_real",
        account_id=account_id,
        positioning_summary="AI product and tooling account for builders.",
        audience_summary="AI product managers and engineering leads",
        tone_summary="Analytical and practical",
        content_lanes_json=[{"id": "ai_tools", "label": "AI Tools"}],
        latest_ops_summary_json={"preferred_content_lane": "AI Tools"},
        recommendation_diagnostics_json=None,
        recommendation_refreshed_at=None,
    )

    async def _fake_snapshot(account_id_arg, db):
        assert account_id_arg == account_id
        return snapshot

    async def _fake_account_context(account_id_arg, db):
        assert account_id_arg == account_id
        return {
            "account_name": "Recommendation Refresh Real Service",
            "positioning": "AI product and tooling account for builders.",
            "audience": "AI product managers and engineering leads",
            "tone_style": "Analytical and practical",
            "reference_sources": [],
        }

    async def _fake_hot_topics(query_plan):
        return [], []

    async def _fake_news_candidates(*, snapshot, query_plan):
        return (
            [
                {
                    "title": "Practical AI agent workflows for product teams",
                    "summary": "A timely product-side look at agent orchestration.",
                    "source_type": "news_article",
                    "source_name": "OpenAI News",
                    "source_url": "https://example.com/openai-agent-workflows",
                    "published_at": None,
                    "relevance_score": 0.82,
                    "authority_score": 0.71,
                    "freshness_score": 0.66,
                    "reason": "Strong fit for AI product and tooling coverage.",
                    "topic_tags_json": ["AI Tools", "Product Strategy"],
                    "source_payload_json": {
                        "collector": {
                            "source_key": "openai_news",
                            "label": "OpenAI News",
                            "kind": "news_feed",
                        }
                    },
                }
            ],
            [
                {
                    "source_key": "openai_news",
                    "label": "OpenAI News",
                    "source_type": "news_article",
                    "status": "success",
                    "query": None,
                    "candidate_count": 1,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": None,
                    "error_message": None,
                    "detail": None,
                }
            ],
        )

    async def _fake_skill_candidates(*, account_id, snapshot, account_context, query_plan, db):
        return [], []

    monkeypatch.setattr(account_analysis_service, "get_or_refresh_snapshot", _fake_snapshot)
    monkeypatch.setattr(account_service, "get_account_context", _fake_account_context)
    monkeypatch.setattr(recommendation_service, "_collect_hot_topic_recommendations", _fake_hot_topics)
    monkeypatch.setattr(news_source_service, "collect_candidates", _fake_news_candidates)
    monkeypatch.setattr(recommendation_service, "_collect_skill_recommendations", _fake_skill_candidates)
    monkeypatch.setattr(skill_router_service, "plan_invocations", lambda **kwargs: [])

    response = await client.post(f"/api/v1/accounts/{account_id}/recommendations/refresh?min_count=5")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["coverage"]["returned_count"] == 1
    assert payload["high_relevance_items"][0]["title"] == "Practical AI agent workflows for product teams"


async def test_list_recommendations_exposes_filtered_out_diagnostics(client, db_session):
    account_id = await _create_account(
        client,
        {
            "name": "Recommendation Diagnostics Account",
            "positioning": "An AI research account focused on developer tooling.",
        },
    )

    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_filtered_1",
        title="Filtered Candidate 1",
        source_type="news_article",
        relevance_score=0.31,
        authority_score=0.52,
        freshness_score=0.58,
    )
    await _seed_recommendation(
        db_session,
        account_id=account_id,
        recommendation_id="rec_filtered_2",
        title="Filtered Candidate 2",
        source_type="news_article",
        relevance_score=0.28,
        authority_score=0.22,
        freshness_score=0.51,
    )

    response = await client.get(f"/api/v1/accounts/{account_id}/recommendations?min_count=5")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["coverage"]["returned_count"] == 0
    assert payload["shortage_notice"]["status"] == "insufficient_total"
    assert payload["shortage_notice"]["reason_code"] == "filtered_out_by_quality_bar"
    assert payload["filter_diagnostics"]["raw_candidate_count"] == 2
    assert payload["filter_diagnostics"]["filtered_out_count"] == 2
