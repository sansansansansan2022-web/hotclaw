"""
Database connection and session management.
"""

from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
_sqlite_engine_kwargs: dict = {}
if _is_sqlite:
    # Local SQLite is used concurrently by the task runner, scheduler, and task
    # detail APIs. WAL mode plus a busy timeout gives readers a much better
    # chance of succeeding while a write transaction is active.
    _sqlite_engine_kwargs = {
        "connect_args": {"timeout": 30},
        "poolclass": NullPool,
    }

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    **({} if _is_sqlite else {"pool_pre_ping": True}),
    **_sqlite_engine_kwargs,
)

if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncSession:
    """Context manager version of get_db for use outside FastAPI routes."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
