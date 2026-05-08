"""Tests for MemoryCuratorAgent and memory curation persistence."""

from __future__ import annotations

import pytest

from app.agents.memory_curator_agent import MemoryCuratorAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_response(data: dict):
    class _Resp:
        parsed = data
        content = str(data)
        tokens = 0
    return _Resp()


SAMPLE_ARTICLE = {
    "selected_title": "复盘写到最后，只剩一句正确的废话",
    "selected_topic": "为什么很多内容复盘越写越空",
    "content_markdown": "## 先把问题说透\n\n复盘是运营团队最常见的动作，却也是最常被写烂的。\n\n## 模式识别\n\n绝大多数复盘，问题归因到最后都是执行力不足。",
    "word_count": 85,
    "summary": "分析内容复盘为什么会越写越空，根源在于缺乏真实观察。",
    "tags": ["内容运营", "复盘", "方法论"],
}

SAMPLE_INPUT = {
    "assembled_article": SAMPLE_ARTICLE,
    "profile": {"domain": "内容运营", "tone": "冷静"},
    "account_context": {
        "account_name": "运营研究院",
        "positioning": "写给内容团队负责人",
        "tone_style": "冷静但不端着",
    },
    "ops_context": {
        "run_strategy": {"preferred_content_lane": "运营洞察"}
    },
    "editorial_review": {
        "editorial_passed": True,
        "combined_rewrite_suggestions": ["开头可以再具体一些"],
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_curator_normalize_output(monkeypatch):
    llm_output = {
        "article_memory": {
            "title": "复盘写到最后，只剩一句正确的废话",
            "summary": "分析内容复盘越写越空的根源。",
            "content_excerpt": "复盘是运营团队最常见的动作",
            "tags": ["内容运营", "复盘"],
            "keywords": ["复盘", "内容运营", "方法论"],
            "metadata_json": {
                "selected_topic": "为什么很多内容复盘越写越空",
                "word_count": 85,
                "editorial_passed": True,
            },
        },
        "evolved_profile_updates": {
            "recent_content_themes": ["内容复盘方法论"],
            "proven_emotional_triggers": ["焦虑感"],
            "content_strengths": ["真实运营观察"],
        },
        "style_profile_updates": {
            "effective_opening_patterns": ["从一个失败场景切入"],
            "hook_templates": ["你是否也遇到过这样的情况"],
        },
        "new_notes": [
            {"content": "本账号读者最关注的是可复用的运营方法，而非理论。", "source": "memory_curator"},
            {"content": "开头需要具体场景，不要用抽象问句。", "source": "memory_curator"},
        ],
    }

    async def _fake_complete(**kwargs):
        return _make_llm_response(llm_output)

    monkeypatch.setattr("app.agents.memory_curator_agent.llm_gateway.complete", _fake_complete)

    agent = MemoryCuratorAgent()
    result = await agent.execute(SAMPLE_INPUT, {})

    assert result.is_success
    data = result.data

    assert data["article_memory"]["title"] == "复盘写到最后，只剩一句正确的废话"
    assert data["article_memory"]["summary"]
    assert isinstance(data["article_memory"]["tags"], list)
    assert isinstance(data["article_memory"]["keywords"], list)
    assert data["article_memory"]["metadata_json"]["editorial_passed"] is True

    assert "recent_content_themes" in data["evolved_profile_updates"]
    assert "effective_opening_patterns" in data["style_profile_updates"]

    assert len(data["new_notes"]) == 2
    for note in data["new_notes"]:
        assert len(note["content"]) <= 120
        assert note["source"] == "memory_curator"


@pytest.mark.asyncio
async def test_memory_curator_fallback_when_llm_fails(monkeypatch):
    async def _fail(**kwargs):
        raise RuntimeError("LLM timeout")

    monkeypatch.setattr("app.agents.memory_curator_agent.llm_gateway.complete", _fail)

    agent = MemoryCuratorAgent()
    # execute returns failure; fallback is called by the engine, test directly here
    fallback_result = await agent.fallback(RuntimeError("LLM timeout"), SAMPLE_INPUT)

    assert fallback_result is not None
    assert fallback_result.is_success
    data = fallback_result.data
    assert data["article_memory"]["title"] == SAMPLE_ARTICLE["selected_title"]
    assert data["evolved_profile_updates"] == {}
    assert data["new_notes"] == []


@pytest.mark.asyncio
async def test_memory_curator_note_length_capped(monkeypatch):
    long_note = "x" * 200
    llm_output = {
        "article_memory": {
            "title": "Test",
            "summary": "Summary",
            "content_excerpt": "",
            "tags": [],
            "keywords": [],
            "metadata_json": {},
        },
        "evolved_profile_updates": {},
        "style_profile_updates": {},
        "new_notes": [{"content": long_note, "source": "memory_curator"}],
    }

    async def _fake_complete(**kwargs):
        return _make_llm_response(llm_output)

    monkeypatch.setattr("app.agents.memory_curator_agent.llm_gateway.complete", _fake_complete)

    agent = MemoryCuratorAgent()
    result = await agent.execute({"assembled_article": {"selected_title": "Test"}}, {})

    assert result.is_success
    notes = result.data["new_notes"]
    assert len(notes) == 1
    assert len(notes[0]["content"]) == 120


@pytest.mark.asyncio
async def test_persist_memory_curation_creates_article_memory(db_session):
    """Integration test: _persist_memory_curation writes ArticleMemoryModel."""
    from app.models.tables import ArticleMemoryModel, AccountModel
    from app.services.task_service import TaskService

    account = AccountModel(
        id="acc-mem-test",
        name="Memory Test Account",
        positioning="Test positioning",
        operation_mode="manual",
        is_active=True,
        last_run_status="running",
    )
    db_session.add(account)
    await db_session.flush()

    service = TaskService()
    curation = {
        "article_memory": {
            "title": "记忆整理测试文章",
            "summary": "这是一篇测试文章的摘要。",
            "content_excerpt": "文章开头...",
            "tags": ["测试"],
            "keywords": ["memory"],
            "metadata_json": {"selected_topic": "测试", "word_count": 100, "editorial_passed": True},
        },
        "evolved_profile_updates": {
            "recent_content_themes": ["测试主题"],
        },
        "style_profile_updates": {
            "hook_templates": ["以问题开头"],
        },
        "new_notes": [
            {"content": "这个账号读者喜欢简洁直接的内容。", "source": "memory_curator"}
        ],
    }

    await service._persist_memory_curation("acc-mem-test", "task-test-001", curation, db_session)
    await db_session.flush()

    from sqlalchemy import select
    rows = await db_session.execute(
        select(ArticleMemoryModel).where(ArticleMemoryModel.account_id == "acc-mem-test")
    )
    memories = rows.scalars().all()
    assert len(memories) == 1
    assert memories[0].title == "记忆整理测试文章"
    assert memories[0].source_task_id == "task-test-001"

    # Check account profile evolution
    await db_session.refresh(account)
    assert account.evolved_profile_json is not None
    assert "recent_content_themes" in account.evolved_profile_json
    assert account.style_profile_json is not None
    assert "hook_templates" in account.style_profile_json
    assert account.last_evolved_at is not None

    # Check notes
    from app.models.tables import AccountNoteModel
    note_rows = await db_session.execute(
        select(AccountNoteModel).where(AccountNoteModel.account_id == "acc-mem-test")
    )
    notes = note_rows.scalars().all()
    assert len(notes) == 1
    assert notes[0].source == "memory_curator"
    assert notes[0].source_task_id == "task-test-001"
