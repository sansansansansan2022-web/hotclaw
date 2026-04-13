import pytest

from app.core.exceptions import ConfigError
from app.core.config import settings
from app.models.tables import EvidenceItemModel, SkillInvocationLogModel, TaskModel
from app.skills.adapters.github_search_adapter import github_search_adapter
from app.skills.adapters.openalex_adapter import openalex_adapter
from app.skills.rankers.paper_ranker import paper_ranker
from app.skills.rankers.repo_ranker import repo_ranker
from app.skills.services.evidence_service import evidence_service
from app.skills.services.skill_router_service import skill_router_service


def test_skill_router_selects_relevant_external_skills():
    plans = skill_router_service.plan_invocations(
        profile={
            "positioning_raw": "面向 AI 工程师做论文解读和开源项目精选",
            "source_preferences": ["scholar", "github"],
            "research_mode": "enabled",
            "open_source_mode": "enabled",
        },
        task_goal="AI agent benchmark",
        current_node="hot_topic_analysis",
        workspace_context={},
        account_context={"content_strategy": "研究解读 + 开源精选"},
    )

    skill_names = {plan["skill_name"] for plan in plans}
    assert "scholar_paper_search_skill" in skill_names
    assert "github_project_curator_skill" in skill_names


def test_paper_ranker_deduplicates_by_doi_and_title():
    papers = [
        {
            "title": "Agent Systems for Reliable Tool Use",
            "doi": "10.1000/test-1",
            "year": 2025,
            "venue": "NeurIPS",
            "abstract_or_summary": "A paper about agent tool use.",
            "citation_count": 50,
            "paper_type": "journal-article",
            "url": "https://doi.org/10.1000/test-1",
        },
        {
            "title": "Agent Systems for Reliable Tool Use",
            "doi": "10.1000/test-1",
            "year": 2025,
            "venue": "NeurIPS",
            "abstract_or_summary": "Duplicate record.",
            "citation_count": 55,
            "paper_type": "journal-article",
            "url": "https://doi.org/10.1000/test-1",
        },
        {
            "title": "Benchmarking Production Agents",
            "doi": None,
            "year": 2024,
            "venue": "ICLR",
            "abstract_or_summary": "Benchmark analysis.",
            "citation_count": 15,
            "paper_type": "preprint",
            "url": "https://example.com/paper",
        },
    ]

    ranked = paper_ranker.rank(topic="agent benchmark", papers=papers, max_results=10)

    assert len(ranked) == 2
    assert ranked[0]["score_breakdown"]["overall"] >= ranked[1]["score_breakdown"]["overall"]


def test_repo_ranker_penalizes_curated_lists():
    repos = [
        {
            "full_name": "example/awesome-agent-tools",
            "name": "awesome-agent-tools",
            "description": "Awesome curated list for agent tools",
            "topics": ["awesome", "agents"],
            "stargazers_count": 4000,
            "forks_count": 300,
            "pushed_at": "2026-04-01T00:00:00Z",
            "updated_at": "2026-04-01T00:00:00Z",
            "html_url": "https://github.com/example/awesome-agent-tools",
            "license": {"spdx_id": "MIT"},
            "has_issues": True,
            "homepage": "",
            "_readme_text": "install usage curated list",
        },
        {
            "full_name": "example/agent-runtime",
            "name": "agent-runtime",
            "description": "Runtime framework for agent orchestration",
            "topics": ["agent", "runtime", "framework"],
            "stargazers_count": 3200,
            "forks_count": 280,
            "pushed_at": "2026-04-10T00:00:00Z",
            "updated_at": "2026-04-10T00:00:00Z",
            "html_url": "https://github.com/example/agent-runtime",
            "license": {"spdx_id": "Apache-2.0"},
            "has_issues": True,
            "homepage": "https://example.com",
            "_readme_text": "install usage quickstart test ci getting started",
        },
    ]

    ranked, buckets = repo_ranker.rank(topic="agent runtime", repos=repos, max_results=10)

    assert ranked[0]["full_name"] == "example/agent-runtime"
    assert "curated_list_lower_priority" in ranked[1]["risk_flags"]
    assert "framework" in buckets


def test_evidence_service_builds_workspace_payload():
    rows = [
        EvidenceItemModel(
            id=1,
            workspace_id="task_1",
            task_id="task_1",
            account_id="acct_1",
            skill_name="github_project_curator_skill",
            source_type="github_repo",
            source_id="example/agent-runtime",
            title="example/agent-runtime",
            url="https://github.com/example/agent-runtime",
            summary="Runtime framework for agent orchestration",
            relevance_score=0.9,
            authority_score=0.8,
            freshness_score=0.7,
            practical_score=0.85,
            selected_reason="Strong engineering signal",
            risk_flags=[],
        ),
        EvidenceItemModel(
            id=2,
            workspace_id="task_1",
            task_id="task_1",
            account_id="acct_1",
            skill_name="scholar_paper_search_skill",
            source_type="scholar_paper",
            source_id="10.1000/test-1",
            title="Reliable Agent Tool Use",
            url="https://doi.org/10.1000/test-1",
            summary="Paper on reliable tool use",
            relevance_score=0.88,
            authority_score=0.92,
            freshness_score=0.66,
            practical_score=0.74,
            selected_reason="Grounds the methods section",
            risk_flags=["missing_doi"],
        ),
    ]

    payload = evidence_service.build_workspace_context(rows)

    assert len(payload["fetched_evidence"]) == 2
    assert len(payload["selected_evidence"]) == 2
    assert payload["citation_guardrails"]["must_ground_titles_in_evidence"] is True
    assert "github_project_curator_skill" in payload["evidence_summaries"]
    assert "scholar_paper_search_skill" in payload["evidence_summaries"]


def test_github_adapter_requires_real_token(monkeypatch):
    monkeypatch.setattr(settings, "enable_github_skill", True)
    monkeypatch.setattr(settings, "github_token", "")

    with pytest.raises(ConfigError):
        github_search_adapter.validate_config()


def test_openalex_adapter_requires_real_key(monkeypatch):
    monkeypatch.setattr(settings, "enable_scholar_skill", True)
    monkeypatch.setattr(settings, "scholar_provider", "openalex+crossref")
    monkeypatch.setattr(settings, "openalex_api_key", "")

    with pytest.raises(ConfigError):
        openalex_adapter.validate_config()


@pytest.mark.asyncio
async def test_skill_debug_endpoints_fail_without_required_config(client, db_session, monkeypatch):
    task = TaskModel(
        id="task_skill_debug",
        account_id="acct_skill_debug",
        workflow_id="standard",
        status="pending",
        input_data={"positioning": "AI engineer account"},
    )
    db_session.add(task)
    await db_session.commit()

    monkeypatch.setattr(settings, "enable_github_skill", True)
    monkeypatch.setattr(settings, "github_token", "")
    github_response = await client.post(
        "/api/v1/skills/github/curate",
        json={
            "task_id": task.id,
            "workspace_id": task.id,
            "topic": "agent runtime",
            "max_results": 3,
        },
    )
    assert github_response.status_code == 400
    assert "GITHUB_TOKEN" in github_response.json()["message"]

    monkeypatch.setattr(settings, "enable_scholar_skill", True)
    monkeypatch.setattr(settings, "scholar_provider", "openalex+crossref")
    monkeypatch.setattr(settings, "openalex_api_key", "")
    scholar_response = await client.post(
        "/api/v1/skills/scholar/search",
        json={
            "task_id": task.id,
            "workspace_id": task.id,
            "topic": "agent benchmark",
            "max_results": 3,
        },
    )
    assert scholar_response.status_code == 400
    assert "OPENALEX_API_KEY" in scholar_response.json()["message"]

    invocation_rows = await db_session.execute(
        SkillInvocationLogModel.__table__.select().where(SkillInvocationLogModel.task_id == task.id)
    )
    assert len(invocation_rows.all()) == 2


@pytest.mark.asyncio
async def test_task_evidence_and_invocation_routes(client, db_session):
    task = TaskModel(
        id="task_skill_evidence",
        account_id="acct_skill_evidence",
        workflow_id="standard",
        status="completed",
        input_data={"positioning": "AI engineer account"},
    )
    db_session.add(task)
    db_session.add(
        EvidenceItemModel(
            workspace_id=task.id,
            task_id=task.id,
            account_id=task.account_id,
            skill_name="github_project_curator_skill",
            source_type="github_repo",
            source_id="example/agent-runtime",
            title="example/agent-runtime",
            url="https://github.com/example/agent-runtime",
            summary="Runtime framework",
            relevance_score=0.9,
            authority_score=0.8,
            freshness_score=0.7,
            practical_score=0.8,
            selected_reason="Useful runtime reference",
            risk_flags=[],
        )
    )
    db_session.add(
        SkillInvocationLogModel(
            task_id=task.id,
            workspace_id=task.id,
            account_id=task.account_id,
            skill_name="github_project_curator_skill",
            request_fingerprint="fp1",
            input_json={"topic": "agent runtime"},
            output_json={"results": []},
            status="success",
            latency_ms=123,
        )
    )
    await db_session.commit()

    evidence_response = await client.get(f"/api/v1/tasks/{task.id}/evidence")
    assert evidence_response.status_code == 200
    assert evidence_response.json()["data"]["count"] == 1
    assert evidence_response.json()["data"]["evidence"][0]["skill_name"] == "github_project_curator_skill"

    invocation_response = await client.get(f"/api/v1/tasks/{task.id}/skill-invocations")
    assert invocation_response.status_code == 200
    assert invocation_response.json()["data"]["count"] == 1
    assert invocation_response.json()["data"]["invocations"][0]["skill_name"] == "github_project_curator_skill"
