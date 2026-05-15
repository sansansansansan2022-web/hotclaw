"""
HotClaw FastAPI application entry point.

【FastAPI 应用入口】
职责：
1. 应用初始化（配置、日志、智能体注册、数据库）
2. 生命周期管理（startup/shutdown）
3. 全局中间件（CORS、Trace ID）
4. 全局异常处理
5. 路由注册

面试点：
- FastAPI lifespan 生命周期管理
- 全局中间件
- 全局异常处理器
- 启动时初始化（智能体注册、数据库表创建）
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.logger import setup_logging, get_logger
from app.core.tracer import generate_trace_id, set_trace_id
from app.core.exceptions import HotClawError
from app.schemas.common import ApiErrorResponse
from app.services.schema_guard_service import schema_guard_service
import app.skills  # noqa: F401

# Import routes
from app.api.task_routes import router as task_router
from app.api.stream_routes import router as stream_router
from app.api.agent_routes import router as agent_router
from app.api.skill_routes import router as skill_router
from app.api.llm_provider_routes import router as llm_provider_router
from app.api.system_config_routes import router as system_config_router
from app.api.settings_routes import router as settings_router
from app.api.account_routes import router as account_router
from app.api.account_insight_routes import router as account_insight_router
from app.api.account_onboarding_routes import router as account_onboarding_router
from app.api.automation_plan_routes import router as automation_plan_router
from app.api.compose_preview_routes import router as compose_preview_router
from app.api.compose_session_routes import router as compose_session_router
from app.api.reference_source_routes import router as reference_source_router
from app.api.recommendation_routes import router as recommendation_router
from app.api.draft_routes import router as draft_router
from app.api.wechat_routes import router as wechat_router
from app.api.config_routes import router as config_router
from app.api.mcp_routes import router as mcp_router
from app.api.platform_capability_routes import router as platform_capability_router

# Import agent implementations to register them
# 【导入所有智能体】触发注册
from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.rewrite_agent import RewriteAgent
from app.agents.post_process_agent import PostProcessAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.agents.account_ops_agent import AccountOpsAgent
from app.agents.registry import agent_registry

logger = get_logger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    """从环境变量读取布尔值标志。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _startup_default_enabled() -> bool:
    """生产环境默认启用某些功能。"""
    return str(settings.app_env or "").strip().lower() == "production"


def _single_worker_startup_default_enabled() -> bool:
    """Enable startup helpers that are only safe in local single-process runs."""
    return str(settings.app_env or "").strip().lower() in {"development", "dev", "local"}


def _register_agents() -> None:
    """
    Register all agents into the registry.

    【智能体注册】
    应用启动时，将所有智能体注册到全局注册表。
    后续编排通过 agent_registry.get(agent_id) 获取实例。
    """
    agent_registry.register(ProfileAgent())
    agent_registry.register(HotTopicAgent())
    agent_registry.register(TopicPlannerAgent())
    agent_registry.register(ContentWriterAgent())
    agent_registry.register(RewriteAgent())
    agent_registry.register(PostProcessAgent())
    agent_registry.register(AuditAgent())
    agent_registry.register(AccountOpsAgent())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: startup and shutdown.

    【生命周期管理】
    FastAPI lifespan 替代旧的 startup/shutdown 事件。
    - enter: 应用启动时执行
    - exit: 应用关闭时执行
    """
    # ===== STARTUP =====
    setup_logging()  # 初始化结构化日志
    _register_agents()  # 注册所有智能体
    auto_create_tables = os.getenv("HOTCLAW_AUTO_CREATE_TABLES", "0").strip().lower() in {"1", "true", "yes"}
    if auto_create_tables:
        from app.db.session import engine
        from app.models.tables import Base
        from app.models.wechat_config import WeChatConfigModel, WeChatPublishRecordModel

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.warning("database_tables_auto_created")
    else:
        logger.info("database_table_auto_create_skipped")

    await schema_guard_service.assert_runtime_schema(allow_revision_mismatch=auto_create_tables)

    from app.db.session import async_session_factory

    recovery_enabled = _env_flag(
        "HOTCLAW_RECOVER_INTERRUPTED_TASKS_ON_STARTUP",
        _single_worker_startup_default_enabled(),
    )
    if recovery_enabled:
        from app.services.task_service import task_service

        try:
            async with async_session_factory() as db:
                recovered_count = await task_service.recover_interrupted_active_tasks(db)
            if recovered_count:
                logger.warning("startup_interrupted_tasks_recovered", count=recovered_count)
        except OperationalError as exc:
            logger.error("startup_interrupted_task_recovery_failed", error=str(exc))
            raise
    else:
        logger.info("startup_interrupted_task_recovery_disabled")

    system_config_init_enabled = _env_flag("HOTCLAW_ENABLE_SYSTEM_CONFIG_INIT", _startup_default_enabled())
    if system_config_init_enabled:
        from app.services.system_config_service import init_default_configs

        try:
            async with async_session_factory() as db:
                await init_default_configs(db)
        except OperationalError as exc:
            if "system_configs" in str(exc):
                logger.error(
                    "startup_schema_missing",
                    missing_table="system_configs",
                    hint="Run `python -m alembic upgrade head` before starting the backend.",
                )
                raise RuntimeError(
                    "Database schema is not initialized. Run `python -m alembic upgrade head` in "
                    "`backend/` before starting the backend."
                ) from exc
            raise
        logger.info("system_configs_initialized")
    else:
        logger.info("system_configs_init_skipped")

    scheduler_enabled = _env_flag("HOTCLAW_ENABLE_SCHEDULER", _startup_default_enabled())
    account_scheduler = None
    if scheduler_enabled:
        from app.scheduler.account_scheduler import account_scheduler as scheduler

        account_scheduler = scheduler
        await account_scheduler.start()
        logger.info("account_scheduler_enabled")
    else:
        logger.info("account_scheduler_disabled")

    recommendation_scheduler_enabled = _env_flag(
        "HOTCLAW_ENABLE_RECOMMENDATION_SCHEDULER",
        _single_worker_startup_default_enabled(),
    )
    recommendation_scheduler = None
    if recommendation_scheduler_enabled:
        from app.scheduler.recommendation_scheduler import recommendation_scheduler as rec_scheduler

        recommendation_scheduler = rec_scheduler
        await recommendation_scheduler.start()
        logger.info("recommendation_scheduler_enabled")
    else:
        logger.info("recommendation_scheduler_disabled")

    logger.info("app_started", env=settings.app_env, debug=settings.app_debug)
    yield
    # ===== SHUTDOWN =====
    if recommendation_scheduler is not None:
        await recommendation_scheduler.stop()
    if account_scheduler is not None:
        await account_scheduler.stop()
    logger.info("app_shutdown")


app = FastAPI(
    title="HotClaw",
    description="Multi-agent content production platform for WeChat Official Accounts",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
# 【CORS 配置】
# allow_origins=["*"] 允许所有来源（开发环境）
# 生产环境建议限制为具体的域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Trace ID middleware
# 【链路追踪中间件】
# 为每个请求生成唯一的 trace_id，注入到日志和响应头中
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    response = await call_next(request)
    # 将 trace_id 返回给前端，便于问题排查
    response.headers["X-Trace-Id"] = trace_id
    return response


# Global exception handler for HotClawError
# 【自定义异常处理】
@app.exception_handler(HotClawError)
async def hotclaw_error_handler(request: Request, exc: HotClawError) -> JSONResponse:
    """
    处理所有 HotClawError 子类异常。

    【错误码到 HTTP 状态码的映射】
    code // 1000 = HTTP 状态码
    """
    # 错误码分类映射
    status_map = {
        1: 400,  # 1xxx -> 400 用户输入错误
        2: 409,  # 2xxx -> 409 冲突错误
        3: 502,  # 3xxx -> 502 外部服务错误
        4: 400,  # 4xxx -> 400 配置错误
        5: 500,  # 5xxx -> 500 系统错误
        6: 400,  # 6xxx -> 400 账号错误
        7: 500,  # 7xxx -> 500 调度器错误
        8: 409,  # 8xxx -> 409 任务冲突错误
        9: 400,  # 9xxx -> 400 草稿错误
    }
    category = exc.code // 1000
    http_status = status_map.get(category, 500)

    # 特殊处理：资源不存在
    if exc.code in (1002, 1003, 1004, 2002):
        http_status = 404
    # 超时错误
    if exc.code == 3003:
        http_status = 504

    return JSONResponse(
        status_code=http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
            "details": exc.details if exc.details else None,
        },
    )


# Global unhandled exception handler
# 【兜底异常处理】
# 捕获所有未被处理的异常，作为最后防线
@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": 5000,
            "message": "internal server error",
            "data": None,
            # 【安全】生产环境不暴露详细错误信息
            "details": {"error": str(exc)} if settings.app_debug else None,
        },
    )


# Register routers
app.include_router(task_router)
app.include_router(stream_router)
app.include_router(agent_router)
app.include_router(skill_router)
app.include_router(llm_provider_router)
app.include_router(system_config_router)
app.include_router(settings_router)
app.include_router(account_router)
app.include_router(account_insight_router)
app.include_router(account_onboarding_router)
app.include_router(automation_plan_router)
app.include_router(recommendation_router)
app.include_router(compose_session_router)
app.include_router(compose_preview_router)
app.include_router(reference_source_router)
app.include_router(draft_router)
app.include_router(wechat_router)
app.include_router(config_router)
app.include_router(mcp_router)
app.include_router(platform_capability_router)


@app.get("/api/v1/health")
async def health_check() -> dict:
    """Health check endpoint used by local smoke tests."""
    return {"status": "ok", "version": "0.1.0"}
