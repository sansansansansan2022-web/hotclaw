"""
HotClaw FastAPI application entry point.

銆怓astAPI 搴旂敤鍏ュ彛銆?
璐熻矗锛?
1. 搴旂敤鍒濆鍖栵紙閰嶇疆銆佹棩蹇椼€佹櫤鑳戒綋娉ㄥ唽銆佹暟鎹簱锛?
2. 鐢熷懡鍛ㄦ湡绠＄悊锛坰tartup/shutdown锛?
3. 鍏ㄥ眬涓棿浠讹紙CORS銆乀race ID锛?
4. 鍏ㄥ眬寮傚父澶勭悊
5. 璺敱娉ㄥ唽

闈㈣瘯鐐癸細
- FastAPI lifespan 鐢熷懡鍛ㄦ湡绠＄悊
- 鍏ㄥ眬涓棿浠?
- 鍏ㄥ眬寮傚父澶勭悊鍣?
- 鍚姩鏃跺垵濮嬪寲锛堟櫤鑳戒綋娉ㄥ唽銆佹暟鎹簱琛ㄥ垱寤猴級
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
import app.skills  # noqa: F401

# Import routes
from app.api.task_routes import router as task_router
from app.api.stream_routes import router as stream_router
from app.api.agent_routes import router as agent_router
from app.api.skill_routes import router as skill_router
from app.api.llm_provider_routes import router as llm_provider_router
from app.api.system_config_routes import router as system_config_router
from app.api.account_routes import router as account_router
from app.api.account_onboarding_routes import router as account_onboarding_router
from app.api.automation_plan_routes import router as automation_plan_router
from app.api.reference_source_routes import router as reference_source_router
from app.api.draft_routes import router as draft_router
from app.api.wechat_routes import router as wechat_router

# Import agent implementations to register them
# 銆愬叧閿€戝鍏ユ墍鏈夋櫤鑳戒綋绫伙紝瑙﹀彂娉ㄥ唽
from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.agents.outline_planner_agent import OutlinePlannerAgent
from app.agents.section_writer_agent import SectionWriterAgent
from app.agents.style_reviewer_agent import StyleReviewerAgent
from app.agents.structure_reviewer_agent import StructureReviewerAgent
from app.agents.rewrite_agent import RewriteAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.agents.account_ops_agent import AccountOpsAgent
from app.agents.registry import agent_registry

logger = get_logger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _register_agents() -> None:
    """
    Register all agents into the registry.

    銆愭櫤鑳戒綋娉ㄥ唽銆?
    搴旂敤鍚姩鏃讹紝灏嗘墍鏈夋櫤鑳戒綋娉ㄥ唽鍒板叏灞€娉ㄥ唽琛ㄣ€?
    鍚庣画缂栨帓寮曟搸閫氳繃 agent_registry.get(agent_id) 鑾峰彇瀹炰緥銆?
    """
    agent_registry.register(ProfileAgent())
    agent_registry.register(HotTopicAgent())
    agent_registry.register(TopicPlannerAgent())
    agent_registry.register(TitleGeneratorAgent())
    agent_registry.register(OutlinePlannerAgent())
    agent_registry.register(SectionWriterAgent())
    agent_registry.register(StyleReviewerAgent())
    agent_registry.register(StructureReviewerAgent())
    agent_registry.register(RewriteAgent())
    agent_registry.register(ContentWriterAgent())
    agent_registry.register(AuditAgent())
    agent_registry.register(AccountOpsAgent())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: startup and shutdown.

    銆愮敓鍛藉懆鏈熺鐞嗐€?
    FastAPI lifespan 鏇夸唬鑰佺殑 startup/shutdown 浜嬩欢銆?
    - enter: 搴旂敤鍚姩鏃舵墽琛?
    - exit: 搴旂敤鍏抽棴鏃舵墽琛?
    """
    # ===== STARTUP =====
    setup_logging()  # 鍒濆鍖栫粨鏋勫寲鏃ュ織
    _register_agents()  # 娉ㄥ唽鎵€鏈夋櫤鑳戒綋
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

    # Initialize default system configs
    from app.db.session import async_session_factory
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

    scheduler_enabled = _env_flag("HOTCLAW_ENABLE_SCHEDULER", True)
    account_scheduler = None
    if scheduler_enabled:
        from app.scheduler.account_scheduler import account_scheduler as scheduler

        account_scheduler = scheduler
        await account_scheduler.start()
        logger.info("account_scheduler_enabled")
    else:
        logger.info("account_scheduler_disabled")

    logger.info("app_started", env=settings.app_env, debug=settings.app_debug)
    yield
    # ===== SHUTDOWN =====
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
# 銆怌ORS 閰嶇疆銆?
# allow_origins=["*"] 鍏佽鎵€鏈夋潵婧愶紙寮€鍙戠幆澧冿級
# 鐢熶骇鐜搴旈檺鍒朵负鍏蜂綋鐨勫煙鍚?
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 鐢熶骇鐜搴旈檺鍒?
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Trace ID middleware
# 銆愰摼璺拷韪腑闂翠欢銆?
# 涓烘瘡涓姹傜敓鎴愬敮涓€鐨?trace_id锛屾敞鍏ュ埌鏃ュ織鍜屽搷搴斿ご涓?
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    response = await call_next(request)
    # 灏?trace_id 杩斿洖缁欏墠绔紝渚夸簬闂鎺掓煡
    response.headers["X-Trace-Id"] = trace_id
    return response


# Global exception handler for HotClawError
# 銆愯嚜瀹氫箟寮傚父澶勭悊銆?
@app.exception_handler(HotClawError)
async def hotclaw_error_handler(request: Request, exc: HotClawError) -> JSONResponse:
    """
    澶勭悊鎵€鏈?HotClawError 瀛愮被寮傚父銆?

    銆愰敊璇爜鍒?HTTP 鐘舵€佺爜鐨勬槧灏勩€?
    code // 1000 = HTTP 鐘舵€佺爜
    """
    # 閿欒鐮佸垎娈垫槧灏?
    status_map = {
        1: 400,  # 1xxx -> 400 鐢ㄦ埛杈撳叆閿欒
        2: 409,  # 2xxx -> 409 鍐茬獊閿欒
        3: 502,  # 3xxx -> 502 澶栭儴鏈嶅姟閿欒
        4: 400,  # 4xxx -> 400 閰嶇疆閿欒
        5: 500,  # 5xxx -> 500 绯荤粺閿欒
        6: 400,  # 6xxx -> 400 璐﹀彿閿欒
        7: 500,  # 7xxx -> 500 璋冨害鍣ㄩ敊璇?
        8: 409,  # 8xxx -> 409 浠诲姟鍐茬獊閿欒
        9: 400,  # 9xxx -> 400 鑽夌閿欒
    }
    category = exc.code // 1000
    http_status = status_map.get(category, 500)

    # 鐗规畩澶勭悊锛氳祫婧愪笉瀛樺湪
    if exc.code in (1002, 1003, 1004, 2002):
        http_status = 404
    # 瓒呮椂閿欒
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
# 銆愬厹搴曞紓甯稿鐞嗐€?
# 鎹曡幏鎵€鏈夋湭琚鐞嗙殑寮傚父锛屼綔涓烘渶鍚庨槻绾?
@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": 5000,
            "message": "internal server error",
            "data": None,
            # 銆愬畨鍏ㄣ€戠敓浜х幆澧冧笉娉勯湶璇︾粏閿欒淇℃伅
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
app.include_router(account_onboarding_router)
app.include_router(automation_plan_router)
app.include_router(reference_source_router)
app.include_router(draft_router)
app.include_router(wechat_router)


@app.get("/api/v1/health")
async def health_check() -> dict:
    """Health check endpoint used by local smoke tests."""
    return {"status": "ok", "version": "0.1.0"}



