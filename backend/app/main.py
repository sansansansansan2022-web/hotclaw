"""HotClaw FastAPI application entry point."""

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

# Import agent implementations to register them
from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.agents.registry import agent_registry

logger = get_logger(__name__)


def _register_agents() -> None:
    """Register all mock agents into the registry."""
    agent_registry.register(ProfileAgent())
    agent_registry.register(HotTopicAgent())
    agent_registry.register(TopicPlannerAgent())
    agent_registry.register(TitleGeneratorAgent())
    agent_registry.register(ContentWriterAgent())
    agent_registry.register(AuditAgent())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    setup_logging()
    _register_agents()

    # Auto-create tables in development mode
    from app.db.session import engine
    from app.models.tables import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_ready")

    logger.info("app_started", env=settings.app_env, debug=settings.app_debug)
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title="HotClaw",
    description="Multi-agent content production platform for WeChat Official Accounts",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Trace ID middleware
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = generate_trace_id()
    set_trace_id(trace_id)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


# Global exception handler for HotClawError
@app.exception_handler(HotClawError)
async def hotclaw_error_handler(request: Request, exc: HotClawError) -> JSONResponse:
    status_map = {
        1: 400,  # 1xxx -> 400
        2: 409,  # 2xxx -> 409
        3: 502,  # 3xxx -> 502
        4: 400,  # 4xxx -> 400
        5: 500,  # 5xxx -> 500
    }
    category = exc.code // 1000
    http_status = status_map.get(category, 500)

    # Special cases
    if exc.code in (1002, 1003, 1004, 2002):
        http_status = 404
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
@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": 5000,
            "message": "internal server error",
            "data": None,
            "details": {"error": str(exc)} if settings.app_debug else None,
        },
    )


# Register routers
app.include_router(task_router)
app.include_router(stream_router)
app.include_router(agent_router)
app.include_router(skill_router)
app.include_router(llm_provider_router)


@app.get("/api/v1/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}
