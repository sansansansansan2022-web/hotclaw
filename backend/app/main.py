"""
HotClaw FastAPI application entry point.

【FastAPI 应用入口】
负责：
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

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import setup_logging, get_logger
from app.core.tracer import generate_trace_id, set_trace_id
from app.core.exceptions import HotClawError
from app.schemas.common import ApiErrorResponse

# Import routes
from app.api.task_routes import router as task_router
from app.api.stream_routes import router as stream_router
from app.api.agent_routes import router as agent_router
from app.api.skill_routes import router as skill_router
from app.api.llm_provider_routes import router as llm_provider_router
from app.api.system_config_routes import router as system_config_router
from app.api.account_routes import router as account_router
from app.api.draft_routes import router as draft_router

# Import agent implementations to register them
# 【关键】导入所有智能体类，触发注册
from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.agents.registry import agent_registry

logger = get_logger(__name__)


def _register_agents() -> None:
    """
    Register all agents into the registry.

    【智能体注册】
    应用启动时，将所有智能体注册到全局注册表。
    后续编排引擎通过 agent_registry.get(agent_id) 获取实例。
    """
    agent_registry.register(ProfileAgent())
    agent_registry.register(HotTopicAgent())
    agent_registry.register(TopicPlannerAgent())
    agent_registry.register(TitleGeneratorAgent())
    agent_registry.register(ContentWriterAgent())
    agent_registry.register(AuditAgent())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: startup and shutdown.

    【生命周期管理】
    FastAPI lifespan 替代老的 startup/shutdown 事件。
    - enter: 应用启动时执行
    - exit: 应用关闭时执行
    """
    # ===== STARTUP =====
    setup_logging()  # 初始化结构化日志
    _register_agents()  # 注册所有智能体

    # Auto-create tables in development mode
    # 【开发友好】自动创建数据库表，无需手动运行 migration
    from app.db.session import engine
    from app.models.tables import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_ready")

    # Initialize default system configs
    from app.db.session import async_session_factory
    from app.services.system_config_service import init_default_configs
    async with async_session_factory() as db:
        await init_default_configs(db)
    logger.info("system_configs_initialized")

    # Start Account Scheduler
    from app.scheduler.account_scheduler import account_scheduler
    await account_scheduler.start()

    logger.info("app_started", env=settings.app_env, debug=settings.app_debug)
    yield
    # ===== SHUTDOWN =====
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
# 生产环境应限制为具体的域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
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
    # 错误码分段映射
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
            # 【安全】生产环境不泄露详细错误信息
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
app.include_router(account_router)
app.include_router(draft_router)


@app.get("/api/v1/health")
async def health_check() -> dict:
    """健康检查端点，用于负载均衡探活。"""
    return {"status": "ok", "version": "0.1.0"}
