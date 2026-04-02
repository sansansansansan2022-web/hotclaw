"""
Database connection and session management.

【数据库会话管理】
使用 SQLAlchemy 2.0 异步 ORM，支持 SQLite（开发）和 MySQL（生产）。
提供两种使用方式：FastAPI 依赖注入 和 独立上下文管理器。

面试点：
- AsyncSession 异步数据库会话
- async generator 作为 FastAPI Depends
- 事务的 commit / rollback 时机
- SQLite 和 MySQL 的兼容处理
"""

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 判断是否为 SQLite（SQLite 不支持 pool_pre_ping）
_is_sqlite = settings.database_url.startswith("sqlite")

# =============================================================================
# 数据库引擎 (Engine)
# =============================================================================
# create_async_engine: 创建异步引擎，用于 SQLAlchemy 2.0 异步操作
# echo=True: 在 DEBUG 模式下打印所有 SQL 语句（用于开发调试）
# pool_pre_ping: 每次从连接池取连接前先 ping，确保连接有效（MySQL 专用）
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    # pool_pre_ping not supported on SQLite
    **({} if _is_sqlite else {"pool_pre_ping": True}),
)

# =============================================================================
# 会话工厂 (Session Factory)
# =============================================================================
# async_sessionmaker: 创建 AsyncSession 实例的工厂
# expire_on_commit=False: 提交后不"过期"对象，允许在事务外访问加载的属性
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,    # 指定使用异步会话类
    expire_on_commit=False,  # 提交后对象仍可访问（避免 lazy load 报错）
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """
    FastAPI dependency that yields a database session.

    【FastAPI 依赖注入函数】
    配合 @router.get("/xxx", dependencies=[Depends(get_db)]) 使用，
    每个请求自动获得独立的数据库会话，请求结束后自动归还。

    【重要】此函数不自动提交！
    调用者负责在需要时显式调用 await session.commit()。

    异常处理：
    - 任何异常发生 → await session.rollback() 回滚事务
    - 最终 → await session.close() 归还连接到池

    使用示例：
        @router.get("/tasks/{task_id}")
        async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(TaskModel).where(...))
            return result.scalar_one_or_none()
    """
    async with async_session_factory() as session:
        try:
            # 【关键】yield 让出控制权，FastAPI 在请求处理完成后自动回收
            yield session
        except Exception:
            # 发生任何异常时回滚未提交的事务
            # 防止脏数据写入数据库
            await session.rollback()
            raise  # 重新抛出异常，让 FastAPI 异常处理器处理
        finally:
            # 无论成功还是失败，都关闭会话归还连接
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncSession:
    """
    Context manager version of get_db for use outside FastAPI routes.

    【独立上下文管理器版本】
    用于非 FastAPI 路由场景，如：
    - 后台任务（asyncio.create_task）
    - 命令行脚本
    - 测试代码

    【关键区别】此函数自动 commit！
    退出 with 块时，如果无异常则自动提交，有异常则自动回滚。

    使用示例：
        async def background_task():
            async with get_db_context() as db:
                task = TaskModel(...)
                db.add(task)
                # 退出 with 时自动 commit
    """
    async with async_session_factory() as session:
        try:
            yield session
            # 【关键】无异常时自动提交
            await session.commit()
        except Exception:
            # 有异常时回滚
            await session.rollback()
            raise
        finally:
            await session.close()
