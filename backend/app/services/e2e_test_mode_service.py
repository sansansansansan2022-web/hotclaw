"""Minimal E2E-only fake modes for generation and publish flows."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config_service import SystemConfigService


class E2ETestModeService:
    """Runtime-controlled fake modes used only when E2E mode is enabled."""

    GENERATION_MODE_KEY = "e2e_generation_mode"
    GENERATION_FAILURE_MESSAGE_KEY = "e2e_generation_failure_message"
    PUBLISH_MODE_KEY = "e2e_publish_mode"
    PUBLISH_FAILURE_MESSAGE_KEY = "e2e_publish_failure_message"

    MODE_REAL = "real"
    MODE_FAKE_SUCCESS = "fake_success"
    MODE_FAKE_FAILURE = "fake_failure"

    _ENABLED_VALUES = {"1", "true", "yes", "on"}
    _SUPPORTED_MODES = {MODE_REAL, MODE_FAKE_SUCCESS, MODE_FAKE_FAILURE}

    def is_enabled(self) -> bool:
        value = os.getenv("HOTCLAW_E2E_TEST_MODE", "").strip().lower()
        return value in self._ENABLED_VALUES

    async def get_generation_mode(self, db: AsyncSession) -> str:
        return await self._get_mode(db, self.GENERATION_MODE_KEY)

    async def get_generation_failure_message(self, db: AsyncSession) -> str:
        return await self._get_message(
            db,
            self.GENERATION_FAILURE_MESSAGE_KEY,
            "E2E fake generation failure",
        )

    async def get_publish_mode(self, db: AsyncSession) -> str:
        return await self._get_mode(db, self.PUBLISH_MODE_KEY)

    async def get_publish_failure_message(self, db: AsyncSession) -> str:
        return await self._get_message(
            db,
            self.PUBLISH_FAILURE_MESSAGE_KEY,
            "E2E fake publish failure",
        )

    async def _get_mode(self, db: AsyncSession, key: str) -> str:
        if not self.is_enabled():
            return self.MODE_REAL

        service = SystemConfigService(db)
        value = await service.get_value(key, self.MODE_REAL)
        normalized = (value or self.MODE_REAL).strip().lower()
        return normalized if normalized in self._SUPPORTED_MODES else self.MODE_REAL

    async def _get_message(self, db: AsyncSession, key: str, default: str) -> str:
        if not self.is_enabled():
            return default

        service = SystemConfigService(db)
        value = await service.get_value(key, default)
        return (value or default).strip() or default

    def build_generation_result(
        self,
        *,
        task_id: str,
        account_id: str | None,
        positioning: str | None,
    ) -> dict[str, Any]:
        selected_topic = "HotClaw E2E Golden Path Topic"
        selected_title = "HotClaw E2E Golden Draft"
        content_markdown = "\n".join(
            [
                f"# {selected_title}",
                "",
                "This is a deterministic draft used by the HotClaw E2E golden path.",
                "",
                "## Why it exists",
                "It keeps the generation pipeline stable while the UI and status writeback are verified.",
                "",
                "## What it proves",
                "Task creation, draft creation, confirmation, publishing, and publish record writeback stay observable.",
            ]
        )

        content_html = (
            f"<h1>{selected_title}</h1>"
            "<p>This is a deterministic draft used by the HotClaw E2E golden path.</p>"
            "<h2>Why it exists</h2>"
            "<p>It keeps the generation pipeline stable while the UI and status writeback are verified.</p>"
            "<h2>What it proves</h2>"
            "<p>Task creation, draft creation, confirmation, publishing, and publish record writeback stay observable.</p>"
        )

        return {
            "input": {"positioning": positioning or ""},
            "profile": {
                "domain": "e2e",
                "tone": "clear",
                "positioning_raw": positioning or "",
            },
            "topics": {
                "selected_topic": selected_topic,
                "topics": [
                    {
                        "title": selected_topic,
                        "angle": "golden-path",
                        "reasoning": "Deterministic E2E topic",
                    }
                ],
            },
            "titles": {
                "selected_topic": selected_topic,
                "selected_title": selected_title,
                "titles": [
                    {
                        "text": selected_title,
                        "style": "e2e",
                        "reasoning": "Deterministic E2E title",
                    }
                ],
            },
            "content": {
                "selected_topic": selected_topic,
                "selected_title": selected_title,
                "title_candidates": [selected_title],
                "summary": "Deterministic draft generated in E2E fake mode.",
                "content_markdown": content_markdown,
                "content_html": content_html,
                "word_count": 56,
                "tags": ["e2e", "golden-path"],
                "structure": {
                    "sections": [
                        {"heading": "Why it exists", "summary": "Stable fake generation"},
                        {"heading": "What it proves", "summary": "End-to-end observability"},
                    ]
                },
            },
            "outline_plan": {
                "article_goal": "Verify the single golden path",
                "sections": [
                    {"id": "why", "title": "Why it exists", "summary": "Stable fake generation"},
                    {"id": "prove", "title": "What it proves", "summary": "End-to-end observability"},
                ],
            },
            "section_drafts": [
                {
                    "id": "why",
                    "heading": "Why it exists",
                    "summary": "Stable fake generation",
                    "content_markdown": "It keeps the generation pipeline stable.",
                },
                {
                    "id": "prove",
                    "heading": "What it proves",
                    "summary": "End-to-end observability",
                    "content_markdown": "It proves status writeback is visible.",
                },
            ],
            "audit_result": {
                "passed": True,
                "risk_level": "low",
                "issues": [],
                "overall_comment": "E2E fake draft is ready for flow verification.",
            },
            "review_results": [
                {
                    "reviewer": "e2e_fake_reviewer",
                    "passed": True,
                    "score": 1.0,
                    "summary": "Deterministic E2E content passed review.",
                    "issues": [],
                    "rewrite_suggestions": [],
                }
            ],
            "evaluation": {
                "final_score": 1.0,
                "summary": "Deterministic E2E content.",
            },
            "content_pipeline": {
                "version": "e2e-fake-v1",
                "used_structured_pipeline": True,
                "fallback_to_content_writer": False,
                "degraded": False,
            },
            "e2e_test_mode": {
                "enabled": True,
                "task_id": task_id,
                "account_id": account_id,
                "generation_mode": self.MODE_FAKE_SUCCESS,
            },
        }


e2e_test_mode_service = E2ETestModeService()
