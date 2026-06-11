"""Tests for publish decision service (protection layer).

【发布保护层测试】
验证 publish_decision_service 的各种决策场景：
1. global_emergency_stop = true 时 BLOCK
2. publish_paused = true 时 BLOCK
3. high risk audit_result 时 BLOCK
4. medium risk audit_result 时 SAVE_AS_DRAFT
5. 超过 max_posts_per_day 时 SKIP (full_auto)
6. 小于 min_interval_minutes 时 SKIP (full_auto)
7. 重复标题时 SKIP
8. confirm publish 也经过 decision service
9. full_auto 发布入口不能绕过 decision service
10. 决策结果会写入 publish_record 或 draft
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from app.models.tables import (
    AccountModel,
    ArticleDraftModel,
    AuditResultModel,
    SystemConfigModel,
    TaskModel,
)
from app.models.wechat_config import WeChatConfigModel
from app.services.draft_service import draft_service
from app.services.publish_decision_service import (
    publish_decision_service,
    PublishDecision,
    PublishReasonCode,
    PublishDecisionError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def full_auto_account(db_session):
    """Create a full_auto account ready for publishing."""
    account = AccountModel(
        id="test-publish-full-auto",
        name="Publish Test Full-Auto",
        positioning="测试定位：科技资讯",
        operation_mode="full_auto",
        auto_run_enabled=True,
        auto_publish_enabled=True,
        is_active=True,
        posting_frequency="daily",
        publish_paused=False,
        max_posts_per_day=3,
        min_interval_minutes=60,
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest_asyncio.fixture
async def semi_auto_account(db_session):
    """Create a semi_auto account."""
    account = AccountModel(
        id="test-publish-semi-auto",
        name="Publish Test Semi-Auto",
        positioning="测试定位：职场成长",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        auto_publish_enabled=False,
        is_active=True,
        posting_frequency="weekly",
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest_asyncio.fixture
async def pending_draft(db_session, full_auto_account):
    """Create a pending_review draft."""
    draft = ArticleDraftModel(
        task_id="test-task-001",
        account_id=full_auto_account.id,
        title="测试文章：人工智能的未来",
        content_markdown="# 人工智能的未来\n\n这是一篇测试文章。",
        word_count=100,
        draft_status="pending_review",
        publish_status="not_published",
        source_type="semi_auto_task",
    )
    db_session.add(draft)
    await db_session.commit()
    return draft


@pytest_asyncio.fixture
async def wechat_config(db_session, full_auto_account):
    """Create WeChat config for account."""
    config = WeChatConfigModel(
        account_id=full_auto_account.id,
        app_id="wx_test_app_id",
        app_secret="wx_test_app_secret",
        is_enabled=True,
        default_author="Test Author",
    )
    db_session.add(config)
    await db_session.commit()
    return config


@pytest_asyncio.fixture
async def system_config(db_session):
    """Ensure system configs are initialized."""
    configs = [
        SystemConfigModel(key="global_publish_enabled", value="true", value_type="boolean", category="publish"),
        SystemConfigModel(key="global_emergency_stop", value="false", value_type="boolean", category="publish"),
    ]
    for cfg in configs:
        existing = await db_session.get(SystemConfigModel, cfg.key)
        if not existing:
            db_session.add(cfg)
    await db_session.commit()


# =============================================================================
# Test 1: global_emergency_stop = true 时 BLOCK
# =============================================================================

class TestSystemLevelBlocking:
    """Test system-level publish blocking."""

    @pytest.mark.asyncio
    async def test_emergency_stop_blocks_all(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that global emergency stop blocks all publishing."""
        # Set emergency stop
        config = await db_session.get(SystemConfigModel, "global_emergency_stop")
        config.value = "true"
        await db_session.commit()

        # Decision should be BLOCK
        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.GLOBAL_EMERGENCY_STOP
        assert "紧急停止" in result.reason_message

    @pytest.mark.asyncio
    async def test_global_publish_disabled_blocks(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that global publish disabled blocks all publishing."""
        # Set global publish disabled
        config = await db_session.get(SystemConfigModel, "global_publish_enabled")
        config.value = "false"
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.GLOBAL_PUBLISH_DISABLED


# =============================================================================
# Test 2: publish_paused = true 时 BLOCK
# =============================================================================

class TestAccountPublishPaused:
    """Test account-level publish pause."""

    @pytest.mark.asyncio
    async def test_publish_paused_blocks(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that paused account cannot publish."""
        # Pause publishing
        account = await db_session.get(AccountModel, pending_draft.account_id)
        account.publish_paused = True
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.ACCOUNT_PUBLISH_PAUSED


# =============================================================================
# Test 3: audit_result 高风险 BLOCK
# =============================================================================

class TestAuditResultGating:
    """Test audit result-based gating."""

    @pytest.mark.asyncio
    async def test_generated_high_risk_audit_blocks_created_draft(
        self, db_session, full_auto_account, wechat_config, system_config
    ):
        """Draft creation should persist task audit output for publish gating."""
        task = TaskModel(
            id="test-task-generated-high-risk",
            account_id=full_auto_account.id,
            workflow_id="default_pipeline",
            status="completed",
            result_data={
                "content": {
                    "summary": "测试摘要",
                    "content_markdown": "# 高风险内容\n\n正文内容",
                    "content_html": "<h1>高风险内容</h1><p>正文内容</p>",
                },
                "titles": {"selected_title": "高风险内容", "candidates": ["高风险内容"]},
                "topics": {"selected_topic": "测试选题"},
                "audit_result": {
                    "passed": False,
                    "risk_level": "high",
                    "overall_comment": "生成审核发现高风险内容",
                    "issues": [{"type": "sensitive", "severity": "high"}],
                },
            },
        )
        db_session.add(task)
        await db_session.commit()

        draft = await draft_service.create_draft_from_task(
            task_id=task.id,
            result_data=task.result_data,
            account_id=full_auto_account.id,
            operation_mode="full_auto",
            db=db_session,
        )
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.AUDIT_HIGH_RISK

    @pytest.mark.asyncio
    async def test_high_risk_blocks(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that high risk audit result blocks publishing."""
        # Add high risk audit
        audit = AuditResultModel(
            draft_id=pending_draft.id,
            task_id=pending_draft.task_id,
            passed=False,
            risk_level="high",
            overall_comment="包含敏感内容",
            issues=[{"type": "sensitive", "description": "涉及政治敏感话题"}],
        )
        db_session.add(audit)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.AUDIT_HIGH_RISK

    @pytest.mark.asyncio
    async def test_medium_risk_save_as_draft(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that medium risk saves as draft for auto modes."""
        # Add medium risk audit
        audit = AuditResultModel(
            draft_id=pending_draft.id,
            task_id=pending_draft.task_id,
            passed=True,
            risk_level="medium",
            overall_comment="需要人工确认",
            issues=[{"type": "review", "description": "涉及医疗健康内容"}],
        )
        db_session.add(audit)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.SAVE_AS_DRAFT
        assert result.reason_code == PublishReasonCode.AUDIT_MEDIUM_RISK

    @pytest.mark.asyncio
    async def test_low_risk_allows_publish(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that low risk allows publishing."""
        # Add low risk audit
        audit = AuditResultModel(
            draft_id=pending_draft.id,
            task_id=pending_draft.task_id,
            passed=True,
            risk_level="low",
            overall_comment="内容安全",
            issues=[],
        )
        db_session.add(audit)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.ALLOW_PUBLISH


# =============================================================================
# Test 5-6: 频率限制
# =============================================================================

class TestFrequencyLimits:
    """Test publish frequency limits."""

    @pytest.mark.asyncio
    async def test_daily_limit_exceeded_skips(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that exceeding daily limit causes SKIP for full_auto."""
        # Create already published drafts to exceed limit
        account = await db_session.get(AccountModel, pending_draft.account_id)
        for i in range(3):  # max_posts_per_day = 3
            draft = ArticleDraftModel(
                task_id=f"test-task-pub-{i}",
                account_id=account.id,
                title=f"已发布文章 {i}",
                content_markdown=f"# 文章 {i}",
                word_count=100,
                draft_status="published",
                publish_status="published",
                published_at=datetime.now(timezone.utc),
                source_type="semi_auto_task",
            )
            db_session.add(draft)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.SKIP
        assert result.reason_code == PublishReasonCode.DAILY_LIMIT_EXCEEDED

    @pytest.mark.asyncio
    async def test_interval_not_met_skips(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that insufficient interval causes SKIP for full_auto."""
        # Create recent published draft
        account = await db_session.get(AccountModel, pending_draft.account_id)
        draft = ArticleDraftModel(
            task_id="test-task-recent",
            account_id=account.id,
            title="最近发布的文章",
            content_markdown="# 最近发布",
            word_count=100,
            draft_status="published",
            publish_status="published",
            published_at=datetime.now(timezone.utc) - timedelta(minutes=30),  # Only 30 min ago
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.SKIP
        assert result.reason_code == PublishReasonCode.MIN_INTERVAL_NOT_MET


# =============================================================================
# Test 6: 重复内容检查
# =============================================================================

class TestDuplicateContent:
    """Test duplicate content detection."""

    @pytest.mark.asyncio
    async def test_exact_title_duplicate_skips(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that exact title match causes SKIP."""
        # Create published draft with same title
        account = await db_session.get(AccountModel, pending_draft.account_id)
        draft = ArticleDraftModel(
            task_id="test-task-dup",
            account_id=account.id,
            title="测试文章：人工智能的未来",  # Exact same title
            content_markdown="# 相同标题文章",
            word_count=100,
            draft_status="published",
            publish_status="published",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.SKIP
        assert result.reason_code == PublishReasonCode.DUPLICATE_TITLE_EXACT

    @pytest.mark.asyncio
    async def test_similar_title_save_as_draft(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that similar title causes SAVE_AS_DRAFT."""
        # Create published draft with similar title
        account = await db_session.get(AccountModel, pending_draft.account_id)
        draft = ArticleDraftModel(
            task_id="test-task-sim",
            account_id=account.id,
            title="测试文章：人工智能的革命",  # Very similar title
            content_markdown="# 相似标题文章",
            word_count=100,
            draft_status="published",
            publish_status="published",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            source_type="semi_auto_task",
        )
        db_session.add(draft)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        # Should be similar (not exact), so SAVE_AS_DRAFT
        assert result.decision == PublishDecision.SAVE_AS_DRAFT


# =============================================================================
# Test 8: confirm publish 也经过 decision service
# =============================================================================

class TestConfirmPublishGating:
    """Test that confirm publish also goes through decision service."""

    @pytest.mark.asyncio
    async def test_manual_confirm_respects_high_risk(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that manual_confirm still blocks high risk content."""
        # Add high risk audit
        audit = AuditResultModel(
            draft_id=pending_draft.id,
            task_id=pending_draft.task_id,
            passed=False,
            risk_level="high",
            overall_comment="敏感内容",
            issues=[],
        )
        db_session.add(audit)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="manual_confirm"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.AUDIT_HIGH_RISK

    @pytest.mark.asyncio
    async def test_manual_confirm_allows_medium_risk(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that manual_confirm allows medium risk (human makes final call)."""
        # Add medium risk audit
        audit = AuditResultModel(
            draft_id=pending_draft.id,
            task_id=pending_draft.task_id,
            passed=True,
            risk_level="medium",
            overall_comment="需要确认",
            issues=[],
        )
        db_session.add(audit)
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="manual_confirm"
        )

        # Manual confirm should allow medium risk (human decides)
        assert result.decision == PublishDecision.ALLOW_PUBLISH


# =============================================================================
# Test 9: full_auto 不能绕过 decision service
# =============================================================================

class TestNoBypass:
    """Test that no publish path can bypass decision service."""

    @pytest.mark.asyncio
    async def test_full_auto_requires_decision(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that full_auto publish always goes through decision."""
        # Without any blocks, full_auto should pass
        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.ALLOW_PUBLISH
        assert result.reason_code == PublishReasonCode.ALL_CHECKS_PASSED

    @pytest.mark.asyncio
    async def test_wechat_config_missing_blocks(
        self, db_session, pending_draft, system_config
    ):
        """Test that missing WeChat config blocks publishing."""
        # Don't create wechat_config fixture

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.WECHAT_CONFIG_MISSING

    @pytest.mark.asyncio
    async def test_draft_already_published_blocks(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that already published draft cannot be republished."""
        # Mark draft as published
        pending_draft.publish_status = "published"
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="manual_confirm"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.DRAFT_ALREADY_PUBLISHED

    @pytest.mark.asyncio
    async def test_draft_terminal_state_blocks(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that discarded/rejected drafts cannot be published."""
        # Mark draft as discarded
        pending_draft.draft_status = "discarded"
        await db_session.commit()

        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="manual_confirm"
        )

        assert result.decision == PublishDecision.BLOCK
        assert result.reason_code == PublishReasonCode.DRAFT_TERMINAL_STATE


# =============================================================================
# Test 10: 决策结果记录
# =============================================================================

class TestDecisionLogging:
    """Test that decision results are properly logged."""

    @pytest.mark.asyncio
    async def test_decision_result_contains_checks(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that decision result includes detailed checks."""
        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        # Should have detailed check information
        assert result.checks is not None
        assert "global_publish_enabled" in result.checks
        assert "global_emergency_stop" in result.checks
        assert "account_id" in result.checks
        assert "draft_status" in result.checks

    @pytest.mark.asyncio
    async def test_decision_result_to_dict(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that decision result can be serialized."""
        result = await publish_decision_service.decide_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        # Should be serializable
        result_dict = result.to_dict()
        assert "decision" in result_dict
        assert "reason_code" in result_dict
        assert "reason_message" in result_dict
        assert "checks" in result_dict


# =============================================================================
# Test: Backward compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with legacy validate_for_publish."""

    @pytest.mark.asyncio
    async def test_validate_for_publish_raises_on_block(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that legacy method raises PublishDecisionError on block."""
        # Set emergency stop
        config = await db_session.get(SystemConfigModel, "global_emergency_stop")
        config.value = "true"
        await db_session.commit()

        with pytest.raises(PublishDecisionError) as exc_info:
            await publish_decision_service.validate_for_publish(
                pending_draft.id, db_session, source="full_auto"
            )

        assert exc_info.value.decision == PublishDecision.BLOCK.value
        assert "紧急停止" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validate_for_publish_returns_context_on_allow(
        self, db_session, pending_draft, wechat_config, system_config
    ):
        """Test that legacy method returns context on allow."""
        context = await publish_decision_service.validate_for_publish(
            pending_draft.id, db_session, source="full_auto"
        )

        assert context is not None
        assert "account_id" in context
        assert "draft_status" in context
