"""E2E test configuration and fixtures.

【E2E 测试配置】
提供端到端测试所需的 fixtures，覆盖：
- 测试数据库
- Mock LLM Provider
- HTTP 客户端
- Scheduler tick 触发
"""

import asyncio
import os
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.tables import Base
from app.db.session import get_db
from app.main import app, _register_agents


# =============================================================================
# Test Database Configuration
# =============================================================================

# Use SQLite with URI for cross-session sharing
# file::memory:?cache=shared allows multiple connections to see same data
TEST_DATABASE_URL = "sqlite+aiosqlite:///file:test_e2e?mode=memory&cache=shared&uri=true"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def db_session():
    """Create test database tables and yield a session."""
    # Register agents before running tests
    _register_agents()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    """HTTP test client with overridden DB dependency."""
    _register_agents()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
def mock_llm():
    """
    Mock litellm.acompletion for deterministic LLM responses.

    Usage:
        async def test_something(mock_llm):
            # litellm.acompletion is now mocked
            ...
    """
    from tests.e2e.mock_llm import get_mock_llm_response

    async def mock_completion(*args, **kwargs):
        # Extract messages from args if positional, or kwargs
        messages = kwargs.get("messages", [])
        if args and isinstance(args[0], list):
            messages = args[0]
        return get_mock_llm_response(
            agent_id=kwargs.get("model", ""),
            messages=messages,
        )

    with patch("litellm.acompletion", side_effect=mock_completion) as mock:
        yield mock


@pytest_asyncio.fixture
def mock_llm_with_response():
    """
    Create a mock that returns custom data.

    Usage:
        async def test_custom(mock_llm_with_response):
            # Set custom response
            mock_llm_with_response.set_response("custom data")
            ...
    """
    from tests.e2e.mock_llm import MockLLMResponse, MockChoice, MockMessage

    response_store = {"response": None}

    async def mock_completion(*args, **kwargs):
        if response_store["response"]:
            return MockLLMResponse(json.dumps(response_store["response"], ensure_ascii=False))
        from tests.e2e.mock_llm import get_mock_llm_response
        return get_mock_llm_response(
            agent_id=kwargs.get("model", ""),
            messages=kwargs.get("messages", []),
            **kwargs
        )

    class MockController:
        def set_response(self, data: dict):
            response_store["response"] = data

        def get_mock(self):
            return mock_completion

    controller = MockController()

    with patch("litellm.acompletion", side_effect=mock_completion):
        yield controller


@pytest_asyncio.fixture
async def scheduler_tick():
    """
    Provide a function to trigger scheduler tick synchronously.

    Usage:
        async def test_scheduler(scheduler_tick, db_session):
            # Create account with due time
            ...

            # Trigger scheduler tick
            await scheduler_tick.trigger(db_session)

            # Verify results
            ...
    """
    class SchedulerTickController:
        async def trigger(self, db_session=None):
            """Manually trigger a scheduler tick for due accounts."""
            from app.scheduler.account_scheduler import account_scheduler
            from app.models.tables import AccountModel, TaskModel
            from sqlalchemy import select

            # Use provided session or create new one
            session = db_session if db_session else test_session_factory()

            try:
                # Get due accounts using direct query (avoid dialect import issue)
                now = datetime.now(timezone.utc)

                # Subquery: check if account has pending/running task
                from sqlalchemy import exists
                task_check = (
                    select(TaskModel.id)
                    .where(
                        TaskModel.account_id == AccountModel.id,
                        TaskModel.status.in_(["pending", "running"])
                    )
                    .limit(1)
                    .exists()
                )

                stmt = (
                    select(AccountModel)
                    .where(
                        AccountModel.is_active == True,
                        AccountModel.auto_run_enabled == True,
                        AccountModel.operation_mode.in_(["semi_auto", "full_auto"]),
                        AccountModel.next_run_at != None,
                        AccountModel.next_run_at <= now,
                        ~task_check,
                    )
                    .order_by(AccountModel.next_run_at)
                )

                result = await session.execute(stmt)
                due_accounts = list(result.scalars().all())

                # Process each due account
                for account in due_accounts:
                    await account_scheduler._run_account_task(account.id)
            finally:
                if db_session is None:
                    await session.close()

    return SchedulerTickController()


@pytest_asyncio.fixture
async def cleanup_test_data(db_session):
    """
    Fixture to clean up test data after each test.
    Automatically cleans up at the end of the test.
    """
    yield

    # Cleanup is handled by db_session fixture dropping tables
    pass


# =============================================================================
# Test Account Factories
# =============================================================================

@pytest_asyncio.fixture
async def semi_auto_account(db_session):
    """Create a semi_auto account ready for scheduling."""
    from app.models.tables import AccountModel
    from app.core.tracer import generate_account_id

    account = AccountModel(
        id=generate_account_id(),
        name="E2E Test Semi-Auto Account",
        positioning="专注于职场成长的公众号，目标读者25-35岁互联网从业者",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        is_active=True,
        posting_frequency="daily",
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # Due immediately
        last_run_status="never_run",
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest_asyncio.fixture
async def manual_account(db_session):
    """Create a manual mode account."""
    from app.models.tables import AccountModel
    from app.core.tracer import generate_account_id

    account = AccountModel(
        id=generate_account_id(),
        name="E2E Test Manual Account",
        positioning="美食探店类公众号",
        operation_mode="manual",
        auto_run_enabled=False,
        is_active=True,
        last_run_status="never_run",
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest_asyncio.fixture
async def full_auto_account(db_session):
    """Create a full_auto account ready for scheduling."""
    from app.models.tables import AccountModel
    from app.core.tracer import generate_account_id

    account = AccountModel(
        id=generate_account_id(),
        name="E2E Test Full-Auto Account",
        positioning="科技前沿资讯公众号",
        operation_mode="full_auto",
        auto_run_enabled=True,
        is_active=True,
        posting_frequency="daily",
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # Due immediately
        last_run_status="never_run",
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest_asyncio.fixture
async def published_draft(db_session, semi_auto_account):
    """Create a published draft for terminal state tests."""
    from app.models.tables import ArticleDraftModel
    from app.core.tracer import generate_task_id

    draft = ArticleDraftModel(
        task_id=generate_task_id(),
        account_id=semi_auto_account.id,
        title="已发布的文章",
        content_markdown="# 已发布\n\n这是一篇已发布的文章。",
        word_count=50,
        draft_status="published",
        publish_status="published",
        source_type="semi_auto_task",
        published_at=datetime.now(timezone.utc),
        confirmed_at=datetime.now(timezone.utc),
        confirmed_by="user",
    )
    db_session.add(draft)
    await db_session.commit()
    return draft


@pytest_asyncio.fixture
async def pending_draft(db_session, semi_auto_account):
    """Create a pending_review draft for confirmation tests."""
    from app.models.tables import ArticleDraftModel
    from app.core.tracer import generate_task_id

    draft = ArticleDraftModel(
        task_id=generate_task_id(),
        account_id=semi_auto_account.id,
        title="待审核文章",
        content_markdown="# 待审核\n\n这是一篇待审核的文章。",
        word_count=100,
        draft_status="pending_review",
        publish_status="not_published",
        source_type="semi_auto_task",
    )
    db_session.add(draft)
    await db_session.commit()
    return draft


# =============================================================================
# Helper Functions
# =============================================================================

async def wait_for_condition(condition_func, timeout=10, interval=0.5):
    """
    Wait for a condition to become true.

    Args:
        condition_func: Async function that returns True when condition is met
        timeout: Maximum seconds to wait
        interval: Check interval in seconds

    Returns:
        True if condition met, False if timeout
    """
    elapsed = 0
    while elapsed < timeout:
        if await condition_func():
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False
