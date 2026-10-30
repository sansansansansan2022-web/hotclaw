"""Approved drafts become account-scoped context for later runs."""

import pytest
from sqlalchemy import select

from app.models.tables import AccountModel, ArticleDraftModel, TaskModel
from app.services.account_service import account_service
from app.services.draft_service import draft_service
from app.agents.content_writer_agent import ContentWriterAgent


@pytest.mark.asyncio
async def test_article_memories_only_include_approved_drafts_for_account(client, db_session):
    db_session.add_all([
        AccountModel(id="memory-a", name="A", positioning="AI"),
        AccountModel(id="memory-b", name="B", positioning="AI"),
        TaskModel(id="memory-task-a", account_id="memory-a", workflow_id="default_pipeline"),
        TaskModel(id="memory-task-b", account_id="memory-b", workflow_id="default_pipeline"),
    ])
    await db_session.flush()
    db_session.add_all([
        ArticleDraftModel(task_id="memory-task-a", account_id="memory-a", title="Approved A", summary="Useful pattern", content_markdown="A" * 500, word_count=500, tags=["AI"], draft_status="draft"),
        ArticleDraftModel(task_id="memory-task-a", account_id="memory-a", title="Unreviewed A", content_markdown="Ignore", word_count=1, draft_status="draft"),
        ArticleDraftModel(task_id="memory-task-b", account_id="memory-b", title="Approved B", content_markdown="Ignore", word_count=1, draft_status="approved"),
    ])
    await db_session.commit()
    memories_before, _ = await account_service.list_article_memories("memory-a", db_session)
    assert memories_before == []
    draft = (await db_session.execute(select(ArticleDraftModel).where(ArticleDraftModel.title == "Approved A"))).scalar_one()
    await draft_service.confirm_publish(draft.id, db_session)
    await db_session.commit()

    response = await client.get("/api/v1/accounts/memory-a/article-memories")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["title"] for item in body["memories"]] == ["Approved A"]

    context = await account_service.get_account_context("memory-a", db_session)
    assert [item["title"] for item in context["recent_article_memories"]] == ["Approved A"]
    assert len(context["recent_article_memories"][0]["content_excerpt"]) <= 280
    prompt = ContentWriterAgent()._build_user_prompt(
        profile={}, topics={}, titles_data={}, hot_topics={}, account_context=context,
        selected_evidence=[], evidence_summaries={}, citation_guardrails={},
    )
    assert "Approved A" in prompt
    assert "Unreviewed A" not in prompt
    assert "Approved B" not in prompt

    search = await client.get("/api/v1/accounts/memory-a/article-memories", params={"query": "not found"})
    assert search.status_code == 200
    assert search.json()["total"] == 0
