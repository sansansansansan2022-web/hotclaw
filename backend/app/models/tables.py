"""ORM model definitions for all core tables."""

from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# =============================================================================
# Account Models
# =============================================================================


class AccountModel(Base):
    """WeChat Official Account managed by the platform."""
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    positioning: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posting_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    posting_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    content_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_accounts: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    auto_run_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Publish tracking fields
    last_publish_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_publish_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Publish protection fields
    publish_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_posts_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[list["TaskModel"]] = relationship(back_populates="account")
    automation_plans: Mapped[list["AutomationPlanModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    reference_sources: Mapped[list["ReferenceSourceModel"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


# =============================================================================
# Task Models
# =============================================================================


class TaskModel(Base):
    """Task table: stores each task's full lifecycle."""
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("accounts.id"), nullable=True, index=True
    )
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    elapsed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    node_runs: Mapped[list["TaskNodeRunModel"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    account_profile: Mapped["AccountProfileModel | None"] = relationship(back_populates="task", uselist=False)
    topic_candidates: Mapped[list["TopicCandidateModel"]] = relationship(back_populates="task")
    article_drafts: Mapped[list["ArticleDraftModel"]] = relationship(
        back_populates="task", foreign_keys="ArticleDraftModel.task_id"
    )
    account: Mapped["AccountModel | None"] = relationship(back_populates="tasks")


class TaskNodeRunModel(Base):
    """Node-level execution record for each agent in a task."""
    __tablename__ = "task_node_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    elapsed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["TaskModel"] = relationship(back_populates="node_runs")


class AccountProfileModel(Base):
    """Parsed account profile from user's positioning input."""
    __tablename__ = "account_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False, unique=True)
    positioning: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subdomain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_audience: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["TaskModel"] = relationship(back_populates="account_profile")


class TopicCandidateModel(Base):
    """Candidate topics generated by the topic planner agent."""
    __tablename__ = "topic_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_emotion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_appeal: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["TaskModel"] = relationship(back_populates="topic_candidates")


class ArticleDraftModel(Base):
    """Generated article drafts."""
    __tablename__ = "article_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("accounts.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Legacy compatibility column kept in local SQLite schemas.
    # Keep it synchronized with draft_status so runtime acceptance does not depend
    # on stale demo/dev table definitions.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Draft status: draft / pending_review / approved / rejected / discarded
    draft_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Publish status: not_published / pending / published / failed
    publish_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_published")
    # Whether manual review is required before publishing
    publish_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Source type: manual_task / semi_auto_task
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual_task")
    # Selected topic info
    selected_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Title candidates
    title_candidates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Summary/hook
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Publish timestamps
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    publish_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    task: Mapped["TaskModel"] = relationship(back_populates="article_drafts", foreign_keys=[task_id])
    account: Mapped["AccountModel | None"] = relationship(foreign_keys=[account_id])
    # Note: audit_result should be fetched via query by draft_id, not via relationship
    # to avoid circular import issues

    @validates("draft_status")
    def _sync_legacy_status(self, key: str, value: str) -> str:
        self.status = value
        return value


class AuditResultModel(Base):
    """Audit results for article drafts."""
    __tablename__ = "audit_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    draft_id: Mapped[int] = mapped_column(Integer, ForeignKey("article_drafts.id"), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    overall_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    # Note: No back_populates relationship to avoid circular imports


class ReferenceSourceModel(Base):
    """Reference material source managed per account."""
    __tablename__ = "reference_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.id"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_value: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["AccountModel"] = relationship(back_populates="reference_sources")


class AutomationPlanModel(Base):
    """Per-account automation plan used by runtime and scheduling logic."""

    __tablename__ = "automation_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.id"), nullable=False, index=True
    )
    is_active_plan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    run_strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="manual_only")
    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    schedule_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    publish_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_posts_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    degrade_policy_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    quality_threshold_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["AccountModel"] = relationship(back_populates="automation_plans")


class AgentModel(Base):
    """Agent configuration persisted from manifests."""
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    module_path: Mapped[str] = mapped_column(String(200), nullable=False)
    model_config_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    required_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    retry_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fallback_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SkillModel(Base):
    """Skill configuration persisted from manifests."""
    __tablename__ = "skills"

    skill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    module_path: Mapped[str] = mapped_column(String(200), nullable=False)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WorkflowTemplateModel(Base):
    """Workflow template definitions."""
    __tablename__ = "workflow_templates"

    workflow_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SystemLogModel(Base):
    """Structured system logs."""
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO")
    module: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class SystemConfigModel(Base):
    """System configuration key-value store (replaces .env for runtime settings)."""
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    """配置键名，如 database_url, redis_url, app_debug 等"""

    value: Mapped[str] = mapped_column(Text, nullable=True)
    """配置值"""

    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")
    """值类型：string, number, boolean, json"""

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    """配置说明"""

    category: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    """分类：database, redis, llm, app, log, timeout"""

    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """是否为敏感配置（如 API Key，GET 时应脱敏）"""

    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """是否为系统级配置（不可删除）"""

    requires_restart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """修改后是否需要重启服务"""

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ArticleMemoryModel(Base):
    """Account-scoped article memory — distilled record of past drafts.

    Inspired by Hermes Agent's MEMORY.md but adapted for HotClaw:
    each entry summarizes a past article (title/summary/tags/excerpt) so
    the orchestrator can retrieve relevant prior work and inject it into
    the next task's prompts (avoiding repetition, reinforcing style).
    """
    __tablename__ = "article_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.id"), nullable=False, index=True
    )
    source_draft_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("article_drafts.id"), nullable=True, index=True
    )
    source_task_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tasks.id"), nullable=True, index=True
    )
    article_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AccountNoteModel(Base):
    """Account-scoped curated note (Hermes MEMORY.md analogue).

    Each entry is a short, dense, agent-curated fact about how to operate
    this account (conventions, do/don't, lessons learned). Strict char
    caps keep the prompt-injected snapshot bounded.
    """
    __tablename__ = "account_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("accounts.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="agent")
    source_task_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("tasks.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LLMProviderModel(Base):
    """LLM Provider configuration (user-defined API keys and settings)."""
    __tablename__ = "llm_providers"

    provider_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    """Provider ID: openai, dashscope, deepseek, zhipu, ollama, custom"""

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    """显示名称，如 "OpenAI", "DeepSeek", "Qwen" """

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    """描述信息"""

    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    """API Key（加密存储更安全，生产环境建议加密）"""

    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    """API Base URL"""

    default_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """默认模型"""

    supported_models: Mapped[list | None] = mapped_column(JSON, nullable=True)
    """支持的模型列表"""

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """是否启用"""

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """是否为默认 Provider"""

    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    """超时时间（秒）"""

    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """额外配置（如 temperature 默认值等）"""

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    """状态：active, inactive"""

    test_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    """测试状态：untested, success, failed"""

    test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    """测试消息或错误信息"""

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
