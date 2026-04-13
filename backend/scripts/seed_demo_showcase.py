"""Seed a polished technology demo account with showcase tasks and drafts."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from sqlalchemy import delete, or_, select

from app.db.session import async_session_factory
from app.models.tables import (
    AccountModel,
    AccountProfileModel,
    ArticleDraftModel,
    AuditResultModel,
    ReferenceSourceModel,
    TaskModel,
    TaskNodeRunModel,
    TopicCandidateModel,
)
from app.models.wechat_config import WeChatConfigModel, WeChatPublishRecordModel
from app.services.article_assembler_service import article_assembler_service
from app.services.automation_plan_service import automation_plan_service
from app.services.e2e_test_mode_service import E2ETestModeService
from app.services.system_config_service import SystemConfigService

DEMO_ACCOUNT_ID = "acct_demo_tech_signal_lab"
DEMO_ACCOUNT_NAME = "Tech Signal Lab"
DEMO_TASK_PREFIX = "task_demo_tech_"
DEMO_FAILED_TASK_ID = f"{DEMO_TASK_PREFIX}signal_window_failed"
DEMO_AUTHOR = "Tech Signal Lab"
DEMO_REFERENCE_ACCOUNT = "a16z, SemiAnalysis, Stratechery"
NODE_ORDER: tuple[tuple[str, str], ...] = (
    ("profile_parsing", "profile_agent"),
    ("hot_topic_analysis", "hot_topic_agent"),
    ("topic_planning", "topic_planner_agent"),
    ("title_generation", "title_generator_agent"),
    ("outline_planner", "outline_planner_agent"),
    ("section_writer", "section_writer_agent"),
    ("article_assembler", "article_assembler_service"),
    ("style_reviewer", "style_reviewer_agent"),
    ("structure_reviewer", "structure_reviewer_agent"),
    ("rewrite_agent", "rewrite_agent"),
    ("audit", "audit_agent"),
)


@dataclass(frozen=True)
class DemoSection:
    heading: str
    summary: str
    body: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class DemoDraftSpec:
    slug: str
    hours_ago: float
    duration_seconds: int
    topic: str
    title: str
    summary: str
    intro: str
    closing: str
    angle: str
    hook: str
    title_candidates: tuple[str, ...]
    tags: tuple[str, ...]
    sections: tuple[DemoSection, ...]
    draft_status: str
    publish_status: str
    publish_record_state: str | None
    publish_error_message: str | None
    final_score: float
    used_rewrite: bool
    query_lane: str

    @property
    def task_id(self) -> str:
        return f"{DEMO_TASK_PREFIX}{self.slug}"


DEMO_DRAFT_SPECS: tuple[DemoDraftSpec, ...] = (
    DemoDraftSpec(
        slug="agent_moat",
        hours_ago=11.0,
        duration_seconds=74,
        topic="2026 年 AI Agent 的竞争点正在从模型能力转向业务接入速度",
        title="AI Agent 进入下半场：谁先接进真实流程，谁先拿到效率红利",
        summary="一篇写给科技团队的判断稿：行业差距正在从 Demo 能力转向真实流程接入后的留存、反馈和复用效率。",
        intro="过去一年大家都在比模型、比提示词、比谁能更快做出会说话的 Agent。进入 2026 年后，真正拉开差距的事情开始变成谁能把 Agent 接进真实业务流程，并把结果稳定写回系统。",
        closing="对科技团队来说，下一阶段最有价值的不是再追一个更炫的 Demo，而是把 Agent 的上下文、权限、反馈闭环和业务 KPI 放进同一条系统链路里。",
        angle="business-integration",
        hook="当所有人都能做出一个会说话的 Agent，真正值钱的是它能不能接管一段真实工作流。",
        title_candidates=(
            "AI Agent 进入下半场：谁先接进真实流程，谁先拿到效率红利",
            "2026 年最强的 Agent 公司，不一定是模型能力最强的那家",
            "Agent 不再是展示品，真正战场是流程接入率",
        ),
        tags=("AI Agent", "工作流", "效率工具"),
        sections=(
            DemoSection(
                heading="为什么现在才进入下半场",
                summary="模型逐渐普及后，差异化开始从能力演示转向业务接入。",
                body="底层模型能力被快速复制后，产品层已经很难只靠“能不能生成”形成壁垒。真正决定用户是否愿意长期付费的，是 Agent 能不能进入 CRM、客服工单、研发协作和运营流程，并保持正确率与可追踪性。",
                evidence_refs=("semi-analysis", "ops-memo"),
            ),
            DemoSection(
                heading="真正的胜负手是什么",
                summary="上下文体系、权限体系和反馈闭环，决定 Agent 能否长期跑下去。",
                body="团队真正该看的不是模型首轮输出，而是接入真实流程后有没有权限管理、上下文记忆、人工兜底，以及能不能把结果回写到业务系统。少一个环节，Agent 都会停留在“会说但不会做”的阶段。",
                evidence_refs=("semi-analysis", "gtc-notes"),
            ),
            DemoSection(
                heading="科技团队现在应该怎么做",
                summary="优先从高频、可回写、容错强的流程切入。",
                body="最适合率先落地的不是最复杂的流程，而是高频、结构明确、可审计的链路，比如客服分流、销售跟进、内容初稿和内部知识问答。先做能稳定积累反馈的数据闭环，再扩展到更复杂的任务。",
                evidence_refs=("ops-memo",),
            ),
        ),
        draft_status="pending_review",
        publish_status="not_published",
        publish_record_state=None,
        publish_error_message=None,
        final_score=0.94,
        used_rewrite=True,
        query_lane="Workflow Integration",
    ),
    DemoDraftSpec(
        slug="device_models",
        hours_ago=8.6,
        duration_seconds=68,
        topic="端侧模型和云推理开始重新分工，智能硬件会重写 AI 入口",
        title="端侧模型回来了：为什么 2026 年的智能硬件会重写 AI 入口",
        summary="解释端侧模型复兴背后的产业逻辑，并给产品团队一套“哪些能力该端侧、哪些该上云”的判断框架。",
        intro="过去两年，很多团队默认 AI 最终都会回到云上统一完成。但 2026 年硬件侧的变化告诉我们，端侧模型不是补充，而是在重新定义 AI 入口。",
        closing="对硬件和 AI 产品团队来说，下一步最关键的不是把所有能力都做在设备里，而是重新划分“本地即时判断”和“云端深度推理”的边界。",
        angle="device-ai",
        hook="端侧模型真正的价值，不是便宜，而是让“响应速度”和“隐私可控”重新变成产品卖点。",
        title_candidates=(
            "端侧模型回来了：为什么 2026 年的智能硬件会重写 AI 入口",
            "云不再是唯一答案，端侧模型正在重做 AI 设备体验",
            "智能硬件的新机会，藏在端侧模型的重新分工里",
        ),
        tags=("端侧模型", "智能硬件", "AI 入口"),
        sections=(
            DemoSection(
                heading="端侧模型为什么重新重要",
                summary="响应速度、功耗和隐私，让端侧模型回到核心位置。",
                body="端侧模型并不是为了替代云，而是为了让即时判断、连续交互和隐私敏感场景重新拥有可交付的体验。尤其在手机、耳机、车机和边缘设备上，低延迟和离线可用开始成为真正的差异化卖点。",
                evidence_refs=("gtc-notes", "ops-memo"),
            ),
            DemoSection(
                heading="云和端会怎样重新分工",
                summary="本地完成即时决策，云端负责复杂推理和跨任务整合。",
                body="更合理的架构，是把高频、低延迟、可本地缓存的判断留在端侧，把需要长上下文、复杂推理和外部检索的任务交给云端。这样既能兼顾成本，也能兼顾体验和安全边界。",
                evidence_refs=("gtc-notes",),
            ),
            DemoSection(
                heading="产品团队该如何落地",
                summary="先做端云混合能力，再做纯端侧承诺。",
                body="成熟做法不是直接宣称“全部端侧”，而是先建立端云混合能力：设备先做即时理解和状态保持，复杂决策再交给云。这样能避免端侧算力受限带来的体验断层。",
                evidence_refs=("semi-analysis",),
            ),
        ),
        draft_status="approved",
        publish_status="failed",
        publish_record_state="failed",
        publish_error_message="示范用失败发布：保留一条可重试的 publish 记录，方便演示 retry 和 wechat-status。",
        final_score=0.91,
        used_rewrite=True,
        query_lane="Device AI",
    ),
    DemoDraftSpec(
        slug="saas_pricing",
        hours_ago=6.2,
        duration_seconds=72,
        topic="推理成本持续下降后，SaaS 定价逻辑正在被重新改写",
        title="推理成本断崖式下降后，SaaS 创业公司的新定价窗口出现了",
        summary="解释推理成本下行为什么会影响 SaaS 客单价、毛利结构和产品打包方式。",
        intro="很多人把推理成本下降理解成“模型更便宜了”。但对 SaaS 创业公司来说，这其实意味着新的定价窗口出现了。",
        closing="真正聪明的团队，不会把成本下降直接变成价格战，而是会把它转译成更高频的使用场景、更强的交付承诺和更清晰的订阅分层。",
        angle="pricing-window",
        hook="成本下降不是利润自动变高，而是你终于有空间把“以前不敢卖的能力”重新打包了。",
        title_candidates=(
            "推理成本断崖式下降后，SaaS 创业公司的新定价窗口出现了",
            "AI 成本下行，为什么 SaaS 公司反而更该重做套餐",
            "模型更便宜以后，真正改变的是 SaaS 的定价权",
        ),
        tags=("SaaS", "推理成本", "定价"),
        sections=(
            DemoSection(
                heading="为什么这不是简单的成本下降",
                summary="成本变化会传导到能力颗粒度和交付方式。",
                body="当模型调用成本持续下降，企业就不再需要把 AI 能力当作昂贵的附加项谨慎售卖。更细颗粒度、更高频次、更强交付承诺的能力，开始具备成为标准套餐的可能。",
                evidence_refs=("semi-analysis", "ops-memo"),
            ),
            DemoSection(
                heading="定价窗口会出现在哪里",
                summary="自动化程度高、原来因成本受压制的能力会先被重新打包。",
                body="最先受益的通常是那些原来“需求强，但调用太贵”的能力，比如批量总结、自动跟进、实时助手、智能质检和多轮分析。现在这些能力可以从高级附加包下沉到主套餐里，直接提升留存与使用频次。",
                evidence_refs=("semi-analysis",),
            ),
            DemoSection(
                heading="创业团队应该先改哪三件事",
                summary="先改套餐，再改指标，最后改交付承诺。",
                body="第一，重新拆解套餐，把 AI 能力按频次和结果价值打包；第二，重定义核心指标，不只看调用量，也看自动完成率和二次使用率；第三，把交付承诺从“能生成”升级为“能稳定完成一段任务”。",
                evidence_refs=("ops-memo", "gtc-notes"),
            ),
        ),
        draft_status="published",
        publish_status="published",
        publish_record_state="published",
        publish_error_message=None,
        final_score=0.95,
        used_rewrite=False,
        query_lane="AI Economics",
    ),
    DemoDraftSpec(
        slug="engineering_copilot",
        hours_ago=3.9,
        duration_seconds=66,
        topic="AI Coding 工具正在从代码补全升级为工程协作层",
        title="Copilot 之后，真正值得关注的是 AI 如何接管工程协作",
        summary="从工程团队视角解释 AI coding 的下一阶段：不只是写代码，而是进入 review、排障、变更理解和团队协作。",
        intro="今天再聊 AI Coding，如果还只盯着代码补全，已经有点晚了。真正值得关注的变化，是 AI 正在从“个人写代码助手”变成“团队工程协作层”。",
        closing="下一阶段真正有价值的，不是让 AI 多写几行代码，而是让它减少团队在沟通、理解和交接上的系统性损耗。",
        angle="engineering-collaboration",
        hook="代码补全只是入口，真正大的机会在于 AI 能否接住团队协作里最耗时间的那部分。",
        title_candidates=(
            "Copilot 之后，真正值得关注的是 AI 如何接管工程协作",
            "AI Coding 的下一阶段，不是写更多代码，而是减少团队协作损耗",
            "从补全到协作层，AI Coding 正在进入真正的组织级价值区间",
        ),
        tags=("AI Coding", "研发协作", "开发者工具"),
        sections=(
            DemoSection(
                heading="为什么补全已经不是核心变量",
                summary="补全能力趋同后，价值转向上下文理解和跨人协作。",
                body="当主流 Coding Assistant 都能完成中高质量补全后，下一阶段决定体验的，是它是否能理解整个仓库、最近变更、团队规范和评审上下文。竞争焦点已经从写一段代码，转向理解一个工程系统。",
                evidence_refs=("ops-memo", "gtc-notes"),
            ),
            DemoSection(
                heading="最值得接管的协作环节",
                summary="Review 准备、改动解释、故障归因和交接摘要，最容易先出价值。",
                body="工程协作里最耗时间的并不是敲代码，而是理解上下文、解释改动、串联依赖、复盘故障和做跨团队交接。AI 进入这些场景后，带来的节省往往比写代码本身更稳定、更容易量化。",
                evidence_refs=("ops-memo", "semi-analysis"),
            ),
            DemoSection(
                heading="团队该如何评估新一代 AI Coding",
                summary="看它是否能减少沟通成本，而不只是看生成准确率。",
                body="评估 AI Coding 工具时，建议把指标从“补全接受率”扩展到“PR 解释时间”“review 往返轮次”“排障定位时长”和“新成员熟悉代码库速度”。这些才更接近组织级价值。",
                evidence_refs=("gtc-notes",),
            ),
        ),
        draft_status="approved",
        publish_status="not_published",
        publish_record_state=None,
        publish_error_message=None,
        final_score=0.93,
        used_rewrite=True,
        query_lane="Developer Tools",
    ),
)

REFERENCE_SOURCE_DEFS: tuple[dict[str, Any], ...] = (
    {
        "source_type": "wechat_account",
        "name": "a16z AI Briefing",
        "source_value": "a16z",
        "notes": "用于模拟高密度科技判断、行业节奏感和投资视角。",
        "article_count": 18,
        "style_takeaway": "观点先行，判断清楚，句子短。",
        "structure_takeaway": "先给结论，再拆行业变量，最后给团队建议。",
    },
    {
        "source_type": "pasted_article",
        "name": "SemiAnalysis Device Memo",
        "source_value": "端侧模型不是替代云，而是让响应速度、隐私和离线体验重新进入产品定义层。",
        "notes": "用于模拟硬件与模型分工相关的深度分析素材。",
        "article_count": 7,
        "style_takeaway": "用产业视角解释技术变化。",
        "structure_takeaway": "先解释变化，再判断赢家，最后落到产品策略。",
    },
    {
        "source_type": "pasted_article",
        "name": "GTC Product Signal Notes",
        "source_value": "企业真正采购的不是单次模型输出，而是可接入系统、可追踪、可回写的稳定能力。",
        "notes": "用于模拟会议信号、产品机会和团队执行建议。",
        "article_count": 5,
        "style_takeaway": "保持克制，不夸张，用商业语气收尾。",
        "structure_takeaway": "每段都要落回产品或组织动作。",
    },
)


def resolve_wechat_credentials(args: argparse.Namespace) -> tuple[str, str]:
    app_id = (
        args.wechat_app_id
        or os.getenv("HOTCLAW_DEMO_WECHAT_APP_ID")
        or "demo-app-id-placeholder"
    )
    app_secret = (
        args.wechat_app_secret
        or os.getenv("HOTCLAW_DEMO_WECHAT_APP_SECRET")
        or "demo-app-secret-placeholder"
    )
    return app_id, app_secret


def hours_ago(base_time: datetime, value: float) -> datetime:
    return base_time - timedelta(hours=value)


def build_markdown(spec: DemoDraftSpec) -> str:
    blocks: list[str] = [f"# {spec.title}", "", spec.intro]
    for section in spec.sections:
        blocks.extend(["", f"## {section.heading}", "", section.body])
    blocks.extend(["", "## 结尾判断", "", spec.closing])
    return "\n".join(blocks).strip()


def build_structure(spec: DemoDraftSpec, markdown: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for index, section in enumerate(spec.sections, start=1):
        sections.append(
            {
                "section_id": f"s{index}",
                "heading": section.heading,
                "summary": section.summary,
                "word_count": article_assembler_service.count_words(section.body),
                "evidence_refs": list(section.evidence_refs),
            }
        )
    sections.append(
        {
            "section_id": f"s{len(spec.sections) + 1}",
            "heading": "结尾判断",
            "summary": "把观点压回团队可执行动作。",
            "word_count": article_assembler_service.count_words(spec.closing),
            "evidence_refs": ["ops-memo"],
        }
    )
    return {
        "sections": sections,
        "estimated_word_count": article_assembler_service.count_words(markdown),
    }


def build_outline_plan(spec: DemoDraftSpec) -> dict[str, Any]:
    return {
        "article_goal": spec.summary,
        "target_reader": "AI 产品经理、科技媒体编辑、创业公司负责人",
        "target_reader_takeaway": "读完后能判断这个变化该不该进入团队路线图。",
        "strategic_angle": spec.angle,
        "content_lane": spec.query_lane,
        "opening_hook": spec.hook,
        "ending_cta": "把行业判断变成一个具体的产品动作。",
        "estimated_word_count": 1500,
        "summary": spec.summary,
        "sections": [
            {
                "section_id": f"s{index}",
                "heading": section.heading,
                "summary": section.summary,
                "purpose": section.summary,
                "key_points": [section.summary, "给出团队动作建议"],
                "evidence_refs": list(section.evidence_refs),
                "tone_hint": "理性、克制、有判断",
            }
            for index, section in enumerate(spec.sections, start=1)
        ],
    }


def build_section_drafts(spec: DemoDraftSpec) -> list[dict[str, Any]]:
    return [
        {
            "section_id": f"s{index}",
            "heading": section.heading,
            "summary": section.summary,
            "content_markdown": section.body,
            "word_count": article_assembler_service.count_words(section.body),
            "evidence_refs": list(section.evidence_refs),
        }
        for index, section in enumerate(spec.sections, start=1)
    ]


def build_reference_digest(reference_sources: list[ReferenceSourceModel]) -> dict[str, Any]:
    return {
        "summary": "选择了 3 条风格和观点最适合科技评论写作的参考源。",
        "source_count": len(reference_sources),
        "selected_source_ids": [str(item.id) for item in reference_sources],
        "preferred_source_names": [item.name for item in reference_sources],
        "style_takeaways": [item.metadata_json.get("style_takeaway") for item in reference_sources if item.metadata_json],
        "structure_takeaways": [item.metadata_json.get("structure_takeaway") for item in reference_sources if item.metadata_json],
        "usage_rules": [
            "结论先行，不要铺垫过长。",
            "每个段落都要回到产品或业务动作。",
            "避免假大空，要给出团队判断。",
        ],
        "source_digests": [
            {
                "source_id": str(item.id),
                "source_type": item.source_type,
                "source_name": item.name,
                "source_title": item.name,
                "style_brief": item.metadata_json.get("style_takeaway") if item.metadata_json else None,
                "structure_brief": item.metadata_json.get("structure_takeaway") if item.metadata_json else None,
                "snippet": item.source_value[:180],
                "origin": "demo_seed",
                "fit_score": 0.9,
            }
            for item in reference_sources
        ],
    }


def build_query_plan(spec: DemoDraftSpec) -> dict[str, Any]:
    return {
        "lane": {
            "id": spec.query_lane.lower().replace(" ", "-"),
            "label": spec.query_lane,
            "reason": "根据账号定位和最近任务，优先选择最适合科技评论的内容赛道。",
        },
        "selected_topic": spec.topic,
        "selected_title": spec.title,
        "primary_queries": [
            f"{spec.topic} 2026",
            f"{spec.query_lane} product strategy",
        ],
        "secondary_queries": [
            "enterprise adoption signals",
            "product implication for content teams",
        ],
        "source_preferences": ["wechat_account", "pasted_article"],
        "banned_angles": ["空泛趋势复读", "没有落地动作的宏观判断"],
        "account_keywords": ["AI", "科技", "产品策略", "组织效率"],
    }


def build_source_candidates(spec: DemoDraftSpec, reference_sources: list[ReferenceSourceModel]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in reference_sources:
        candidates.append(
            {
                "source_id": str(item.id),
                "source_type": item.source_type,
                "source_name": item.name,
                "source_title": f"{item.name}: {spec.topic}",
                "snippet": item.source_value[:140],
                "fit_score": 0.88,
                "origin": "demo_seed",
                "why_selected": item.notes,
            }
        )
    return candidates


def build_ops_context(spec: DemoDraftSpec, reference_sources: list[ReferenceSourceModel], generated_at: datetime) -> dict[str, Any]:
    return {
        "generated_at": generated_at.isoformat(),
        "trigger": {
            "source": "manual",
            "requested_plan_type": "semi_auto",
        },
        "account_health": {
            "status": "ready",
            "issues": [],
        },
        "operation_stage": "growth",
        "run_strategy": {
            "allow_run": True,
            "requested_mode": "semi_auto",
            "effective_mode": "semi_auto",
            "degraded_from": None,
            "allow_auto_publish": False,
            "preferred_reference_source_ids": [str(item.id) for item in reference_sources],
            "avoid_recent_topics": ["重复复读模型性能榜单"],
            "preferred_content_lane": spec.query_lane,
        },
        "ops_notes": [
            "这是一个手工触发的科技演示账号，优先保留人工确认环节。",
            "优先选择可转化为团队动作的科技评论题材。",
        ],
        "fallback_used": False,
    }


def build_content_payload(spec: DemoDraftSpec) -> dict[str, Any]:
    markdown = build_markdown(spec)
    return {
        "selected_topic": spec.topic,
        "selected_title": spec.title,
        "title_candidates": list(spec.title_candidates),
        "summary": spec.summary,
        "content_markdown": markdown,
        "content_html": article_assembler_service.ensure_content_html(None, markdown),
        "word_count": article_assembler_service.count_words(markdown),
        "tags": list(spec.tags),
        "structure": build_structure(spec, markdown),
    }


def build_result_data(spec: DemoDraftSpec, reference_sources: list[ReferenceSourceModel], generated_at: datetime) -> dict[str, Any]:
    content = build_content_payload(spec)
    ops_context = build_ops_context(spec, reference_sources, generated_at)
    return {
        "input": {"positioning": "服务 AI 产品、工程和科技商业团队的深度分析账号"},
        "profile": {
            "domain": "technology",
            "subdomain": "ai-product-strategy",
            "target_audience": {
                "occupation": "AI 产品经理 / 创业者 / 工程负责人",
                "interests": ["产业变化", "产品策略", "工程效率"],
            },
            "tone": "理性、克制、带判断",
            "content_style": "结论先行、商业导向、可执行",
            "keywords": ["AI", "科技评论", "产品策略", "组织效率"],
            "positioning_raw": "服务 AI 产品、工程和科技商业团队的深度分析账号",
        },
        "query_plan": build_query_plan(spec),
        "reference_digest": build_reference_digest(reference_sources),
        "source_candidates": build_source_candidates(spec, reference_sources),
        "style_profile": {
            "tone": "理性克制",
            "sentence_pattern": "短句 + 中等长度解释",
            "rhetoric": ["结论先行", "给出判断", "最后落动作"],
        },
        "retrieved_memories": [
            {
                "id": f"memo-{spec.slug}",
                "title": f"{spec.query_lane} memory",
                "summary": f"最近 30 天账号最受欢迎的内容赛道是 {spec.query_lane}。",
                "tags": list(spec.tags),
                "metadata": {"origin": "demo_seed"},
            }
        ],
        "outline_plan": build_outline_plan(spec),
        "section_drafts": build_section_drafts(spec),
        "style_review": {
            "reviewer": "style_reviewer",
            "passed": True,
            "summary": "语气稳定，科技评论感足够。",
            "issues": [],
        },
        "structure_review": {
            "reviewer": "structure_reviewer",
            "passed": True,
            "summary": "结构清晰，层次完整。",
            "issues": [],
        },
        "review_results": [
            {
                "reviewer": "style_reviewer",
                "passed": True,
                "score": round(spec.final_score, 2),
                "summary": "风格和结构都达到了 demo 展示标准。",
                "issues": [],
                "rewrite_suggestions": [] if not spec.used_rewrite else ["收紧开头句，压缩冗余过渡。"],
            }
        ],
        "rewrite_result": {
            "applied": spec.used_rewrite,
            "summary": "已根据 review 结果做一次收紧和提纯。",
        } if spec.used_rewrite else None,
        "evaluation": {
            "final_score": spec.final_score,
            "summary": "这是一篇适合科技账号 demo 展示的完整稿件。",
        },
        "content_pipeline": {
            "version": "demo-showcase-v1",
            "used_structured_pipeline": True,
            "fallback_to_content_writer": False,
            "degraded": False,
        },
        "topics": {
            "selected_topic": spec.topic,
            "topics": [
                {
                    "title": spec.topic,
                    "angle": spec.angle,
                    "reasoning": "最符合当前账号定位和最近表现。",
                    "estimated_appeal": 0.92,
                },
                {
                    "title": f"{spec.topic}：产品团队版",
                    "angle": "team-actions",
                    "reasoning": "更偏执行建议。",
                    "estimated_appeal": 0.79,
                },
            ],
        },
        "titles": {
            "selected_topic": spec.topic,
            "selected_title": spec.title,
            "titles": [
                {"text": title, "style": "tech-analysis", "reasoning": "兼顾行业判断和传播性"}
                for title in spec.title_candidates
            ],
        },
        "content": content,
        "audit_result": {
            "passed": True,
            "risk_level": "low",
            "issues": [],
            "overall_comment": "内容可发布，适合演示确认和发布流程。",
        },
        "ops_context": ops_context,
        "execution_meta": {
            "runtime_mode": "demo",
            "provider": "fake",
            "simulated": True,
            "trace_id": f"demo-trace-{spec.slug}",
        },
    }


def build_failed_result_data(reference_sources: list[ReferenceSourceModel], generated_at: datetime) -> dict[str, Any]:
    return {
        "input": {"positioning": "服务 AI 产品、工程和科技商业团队的深度分析账号"},
        "profile": {
            "domain": "technology",
            "tone": "理性、克制、带判断",
        },
        "query_plan": {
            "lane": {"id": "signal-window", "label": "Signal Window"},
            "selected_topic": "技术信号窗口期",
        },
        "reference_digest": build_reference_digest(reference_sources),
        "source_candidates": build_source_candidates(DEMO_DRAFT_SPECS[0], reference_sources),
        "outline_plan": {
            "article_goal": "解释窗口期为何短暂且重要。",
            "sections": [],
        },
        "ops_context": {
            "generated_at": generated_at.isoformat(),
            "trigger": {"source": "manual", "requested_plan_type": "semi_auto"},
            "account_health": {"status": "attention", "issues": ["一次超时已被记录，建议重试。"]},
            "operation_stage": "growth",
            "run_strategy": {
                "allow_run": True,
                "requested_mode": "semi_auto",
                "effective_mode": "semi_auto",
                "allow_auto_publish": False,
                "preferred_reference_source_ids": [str(item.id) for item in reference_sources],
                "avoid_recent_topics": [],
                "preferred_content_lane": "Signal Window",
            },
            "ops_notes": ["故意保留一条失败任务，方便演示 rerun 和错误态。"],
            "fallback_used": False,
        },
        "execution_meta": {
            "runtime_mode": "demo",
            "provider": "fake",
            "simulated": True,
            "timed_out": True,
            "trace_id": "demo-trace-signal-window-failed",
        },
    }


async def cleanup_existing_demo(db) -> None:
    await cleanup_accounts(db, [DEMO_ACCOUNT_ID])


async def cleanup_accounts(db, account_ids: list[str]) -> None:
    if not account_ids:
        return

    draft_condition = ArticleDraftModel.account_id.in_(account_ids)
    task_condition = TaskModel.account_id.in_(account_ids)
    if DEMO_ACCOUNT_ID in account_ids:
        draft_condition = or_(draft_condition, ArticleDraftModel.task_id.like(f"{DEMO_TASK_PREFIX}%"))
        task_condition = or_(task_condition, TaskModel.id.like(f"{DEMO_TASK_PREFIX}%"))

    draft_ids_result = await db.execute(select(ArticleDraftModel.id).where(draft_condition))
    draft_ids = [row[0] for row in draft_ids_result.all()]

    task_ids_result = await db.execute(select(TaskModel.id).where(task_condition))
    task_ids = [row[0] for row in task_ids_result.all()]

    if draft_ids:
        await db.execute(delete(AuditResultModel).where(AuditResultModel.draft_id.in_(draft_ids)))
        await db.execute(delete(WeChatPublishRecordModel).where(WeChatPublishRecordModel.draft_id.in_(draft_ids)))
        await db.execute(delete(ArticleDraftModel).where(ArticleDraftModel.id.in_(draft_ids)))

    if task_ids:
        await db.execute(delete(TaskNodeRunModel).where(TaskNodeRunModel.task_id.in_(task_ids)))
        await db.execute(delete(AccountProfileModel).where(AccountProfileModel.task_id.in_(task_ids)))
        await db.execute(delete(TopicCandidateModel).where(TopicCandidateModel.task_id.in_(task_ids)))
        await db.execute(delete(TaskModel).where(TaskModel.id.in_(task_ids)))

    await db.execute(delete(ArticleDraftModel).where(ArticleDraftModel.account_id.in_(account_ids)))
    await db.execute(delete(ReferenceSourceModel).where(ReferenceSourceModel.account_id.in_(account_ids)))
    await db.execute(delete(WeChatConfigModel).where(WeChatConfigModel.account_id.in_(account_ids)))
    await db.execute(delete(WeChatPublishRecordModel).where(WeChatPublishRecordModel.account_id.in_(account_ids)))
    await db.execute(delete(TaskModel).where(TaskModel.account_id.in_(account_ids)))
    from app.models.tables import AutomationPlanModel
    await db.execute(delete(AutomationPlanModel).where(AutomationPlanModel.account_id.in_(account_ids)))
    await db.execute(delete(AccountModel).where(AccountModel.id.in_(account_ids)))

    await db.flush()


async def purge_demo_noise(db) -> list[str]:
    result = await db.execute(select(AccountModel.id, AccountModel.name, AccountModel.positioning))
    account_ids: list[str] = []
    for account_id, name, positioning in result.all():
        if account_id == DEMO_ACCOUNT_ID:
            continue
        normalized_name = str(name or "")
        normalized_positioning = str(positioning or "")
        if (
            normalized_name.startswith("Audit ")
            or normalized_name.startswith("E2E Account ")
            or normalized_positioning.startswith("HotClaw audit positioning")
            or normalized_positioning.startswith("HotClaw E2E positioning")
        ):
            account_ids.append(account_id)

    await cleanup_accounts(db, account_ids)
    return account_ids


async def set_demo_modes(db) -> None:
    config_service = SystemConfigService(db)
    await config_service.set_value(
        E2ETestModeService.GENERATION_MODE_KEY,
        E2ETestModeService.MODE_FAKE_SUCCESS,
    )
    await config_service.set_value(
        E2ETestModeService.PUBLISH_MODE_KEY,
        E2ETestModeService.MODE_FAKE_SUCCESS,
    )
    await config_service.set_value(
        E2ETestModeService.GENERATION_FAILURE_MESSAGE_KEY,
        "Demo generation failure placeholder",
    )
    await config_service.set_value(
        E2ETestModeService.PUBLISH_FAILURE_MESSAGE_KEY,
        "Demo publish failure placeholder",
    )
    await db.flush()


async def create_demo_account(db, seeded_at: datetime) -> AccountModel:
    account = AccountModel(
        id=DEMO_ACCOUNT_ID,
        name=DEMO_ACCOUNT_NAME,
        category="科技",
        positioning="面向 AI 产品经理、工程负责人和科技创业团队，提供产业变化、产品策略和组织效率的深度分析。",
        audience="AI 产品经理、工程负责人、创业公司操盘手、科技媒体编辑",
        tone_style="理性、克制、带商业判断",
        posting_frequency="daily",
        posting_time="08:30",
        content_strategy="结论先行，产业信号和产品动作并重，每篇都落到团队执行建议。",
        reference_accounts=DEMO_REFERENCE_ACCOUNT,
        operation_mode="semi_auto",
        auto_run_enabled=True,
        auto_publish_enabled=False,
        is_active=True,
        last_run_at=seeded_at - timedelta(hours=2),
        next_run_at=seeded_at + timedelta(hours=10),
        last_run_status="success",
        last_error_message=None,
        last_publish_status="published",
        last_publish_error_message=None,
        last_published_at=seeded_at - timedelta(hours=5),
        publish_paused=False,
        max_posts_per_day=2,
        min_interval_minutes=180,
        created_at=seeded_at - timedelta(hours=12),
        updated_at=seeded_at,
    )
    db.add(account)
    await db.flush()

    await automation_plan_service.create_initial_plan(
        account,
        db,
        {
            "plan_type": "semi_auto",
            "is_enabled": True,
            "run_strategy": "hybrid",
            "schedule_type": "daily",
            "schedule_config": {"time": "08:30"},
            "auto_publish_enabled": False,
            "publish_review_required": True,
            "max_posts_per_day": 2,
            "min_interval_minutes": 180,
            "timezone": "Asia/Shanghai",
            "notes": "Demo showcase automation plan",
        },
    )
    plan = await automation_plan_service.get_active_plan(DEMO_ACCOUNT_ID, db)
    if plan is not None:
        plan.last_run_at = account.last_run_at
        plan.next_run_at = account.next_run_at
        plan.latest_status = "success"
        db.add(plan)

    await db.flush()
    return account


async def create_reference_sources(db, seeded_at: datetime) -> list[ReferenceSourceModel]:
    sources: list[ReferenceSourceModel] = []
    for index, definition in enumerate(REFERENCE_SOURCE_DEFS):
        source = ReferenceSourceModel(
            account_id=DEMO_ACCOUNT_ID,
            source_type=definition["source_type"],
            name=definition["name"],
            source_value=definition["source_value"],
            notes=definition["notes"],
            is_enabled=True,
            sync_status="manual_only",
            last_synced_at=seeded_at - timedelta(hours=12 - index),
            article_count=definition["article_count"],
            latest_error_message=None,
            metadata_json={
                "origin": "demo_seed",
                "style_takeaway": definition["style_takeaway"],
                "structure_takeaway": definition["structure_takeaway"],
            },
            created_at=seeded_at - timedelta(hours=12 - index),
            updated_at=seeded_at - timedelta(hours=2 - index * 0.1),
        )
        db.add(source)
        sources.append(source)
    await db.flush()
    return sources


async def create_wechat_config(db, seeded_at: datetime, app_id: str, app_secret: str) -> WeChatConfigModel:
    config = WeChatConfigModel(
        account_id=DEMO_ACCOUNT_ID,
        app_id=app_id,
        app_secret=app_secret,
        default_author=DEMO_AUTHOR,
        default_thumb_media_id=None,
        need_open_comment=True,
        only_fans_can_comment=False,
        is_enabled=True,
        test_status="untested",
        test_message="Demo credentials seeded. Run the real connection test from the console.",
        last_sync_at=seeded_at,
        created_at=seeded_at,
        updated_at=seeded_at,
    )
    db.add(config)
    await db.flush()
    return config


async def create_success_task_stack(
    db,
    spec: DemoDraftSpec,
    reference_sources: list[ReferenceSourceModel],
    account: AccountModel,
    seeded_at: datetime,
) -> tuple[TaskModel, ArticleDraftModel]:
    created_at = hours_ago(seeded_at, spec.hours_ago)
    started_at = created_at + timedelta(seconds=4)
    completed_at = started_at + timedelta(seconds=spec.duration_seconds)
    result_data = build_result_data(spec, reference_sources, completed_at)
    content = result_data["content"]

    task = TaskModel(
        id=spec.task_id,
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        input_data={
            "positioning": account.positioning,
            "ops_context": result_data["ops_context"],
        },
        result_data=result_data,
        error_message=None,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=float(spec.duration_seconds),
        total_tokens=1760 + int(spec.final_score * 100),
        created_at=created_at,
        updated_at=completed_at,
    )
    db.add(task)
    await db.flush()

    db.add(
        AccountProfileModel(
            task_id=task.id,
            positioning=account.positioning,
            domain="technology",
            subdomain="ai-product-strategy",
            target_audience=result_data["profile"]["target_audience"],
            tone="理性、克制、带判断",
            content_style="结论先行、可执行",
            keywords=result_data["profile"]["keywords"],
            created_at=created_at,
            updated_at=completed_at,
        )
    )

    for rank, title in enumerate(spec.title_candidates, start=1):
        db.add(
            TopicCandidateModel(
                task_id=task.id,
                title=title,
                angle=spec.angle,
                hook=spec.hook,
                target_emotion="clarity",
                estimated_appeal=max(0.7, 0.96 - rank * 0.05),
                reasoning="与账号定位高度一致，兼顾传播和判断。",
                rank=rank,
                selected=rank == 1,
                created_at=created_at,
                updated_at=completed_at,
            )
        )

    output_key_by_node = {
        "profile_parsing": "profile",
        "hot_topic_analysis": "source_candidates",
        "topic_planning": "topics",
        "title_generation": "titles",
        "outline_planner": "outline_plan",
        "section_writer": "section_drafts",
        "article_assembler": "content",
        "style_reviewer": "style_review",
        "structure_reviewer": "structure_review",
        "rewrite_agent": "rewrite_result",
        "audit": "audit_result",
    }
    slice_seconds = max(spec.duration_seconds / len(NODE_ORDER), 2)
    for index, (node_id, agent_id) in enumerate(NODE_ORDER):
        node_started = started_at + timedelta(seconds=index * slice_seconds)
        node_completed = min(completed_at, node_started + timedelta(seconds=slice_seconds - 0.5))
        output_data = result_data.get(output_key_by_node[node_id])
        db.add(
            TaskNodeRunModel(
                task_id=task.id,
                node_id=node_id,
                agent_id=agent_id,
                status="completed",
                input_data={"topic": spec.topic, "lane": spec.query_lane},
                output_data=output_data if isinstance(output_data, (dict, list)) else {"value": output_data},
                error_message=None,
                degraded=False,
                started_at=node_started,
                completed_at=node_completed,
                elapsed_seconds=max((node_completed - node_started).total_seconds(), 0.5),
                prompt_tokens=120 + index * 11,
                completion_tokens=180 + index * 13,
                model_used="demo-showcase-v1",
                retry_count=0,
                created_at=node_started,
                updated_at=node_completed,
            )
        )

    draft = ArticleDraftModel(
        task_id=task.id,
        account_id=account.id,
        title=spec.title,
        content_markdown=content["content_markdown"],
        content_html=content["content_html"],
        word_count=content["word_count"],
        structure=content["structure"],
        tags=content["tags"],
        status=spec.draft_status,
        draft_status=spec.draft_status,
        publish_status=spec.publish_status,
        publish_review_required=True,
        source_type="semi_auto_task",
        selected_topic=spec.topic,
        title_candidates=list(spec.title_candidates),
        summary=spec.summary,
        confirmed_at=completed_at if spec.publish_record_state in {"failed", "published"} else None,
        confirmed_by="demo.operator" if spec.publish_record_state in {"failed", "published"} else None,
        published_at=completed_at + timedelta(minutes=8) if spec.publish_record_state == "published" else None,
        publish_error_message=spec.publish_error_message,
        created_at=completed_at + timedelta(minutes=5),
        updated_at=completed_at + timedelta(minutes=10),
    )
    db.add(draft)
    await db.flush()

    db.add(
        AuditResultModel(
            task_id=task.id,
            draft_id=draft.id,
            passed=True,
            risk_level="low",
            issues=[],
            overall_comment="适合作为科技 demo 稿件展示，结构完整、观点清楚。",
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )
    )

    if spec.publish_record_state:
        publish_started = completed_at + timedelta(minutes=2)
        publish_finished = completed_at + timedelta(minutes=8)
        db.add(
            WeChatPublishRecordModel(
                draft_id=draft.id,
                task_id=task.id,
                account_id=account.id,
                wechat_draft_id=f"e2e-media-{draft.id}",
                media_id=f"e2e-media-{draft.id}",
                publish_id=f"e2e-publish-{draft.id}" if spec.publish_record_state == "published" else None,
                article_id=f"e2e-article-{draft.id}" if spec.publish_record_state == "published" else None,
                url=f"https://example.test/hotclaw/publish/{draft.id}" if spec.publish_record_state == "published" else None,
                publish_status=spec.publish_record_state,
                source_mode="manual",
                trigger_type="manual_confirm",
                publish_attempt=1,
                retry_count=0,
                parent_record_id=None,
                error_code="E2E_FAKE_PUBLISH" if spec.publish_record_state == "failed" else None,
                error_message=spec.publish_error_message,
                request_snapshot=f"simulated=true;source=e2e_fake;draft={draft.id}",
                response_snapshot=(
                    "simulated=true;source=e2e_fake;provider=fake;event=publish_success"
                    if spec.publish_record_state == "published"
                    else "simulated=true;source=e2e_fake;provider=fake;event=publish_failed"
                ),
                started_at=publish_started,
                finished_at=publish_finished,
                published_at=publish_finished if spec.publish_record_state == "published" else None,
                last_checked_at=publish_finished,
                created_at=publish_started,
                updated_at=publish_finished,
            )
        )

    await db.flush()
    return task, draft


async def create_failed_task(db, reference_sources: list[ReferenceSourceModel], account: AccountModel, seeded_at: datetime) -> TaskModel:
    created_at = hours_ago(seeded_at, 12.2)
    started_at = created_at + timedelta(seconds=5)
    completed_at = started_at + timedelta(seconds=92)
    result_data = build_failed_result_data(reference_sources, completed_at)

    task = TaskModel(
        id=DEMO_FAILED_TASK_ID,
        account_id=account.id,
        workflow_id="default_pipeline",
        status="failed",
        input_data={
            "positioning": account.positioning,
            "ops_context": result_data["ops_context"],
        },
        result_data=result_data,
        error_message="outline_planner timed out after 92 seconds in demo seed",
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=92.0,
        total_tokens=1120,
        created_at=created_at,
        updated_at=completed_at,
    )
    db.add(task)
    await db.flush()

    failure_index = 4
    slice_seconds = 92 / max(len(NODE_ORDER), 1)
    for index, (node_id, agent_id) in enumerate(NODE_ORDER):
        node_started = started_at + timedelta(seconds=index * slice_seconds)
        if index < failure_index:
            node_completed = node_started + timedelta(seconds=slice_seconds - 0.5)
            db.add(
                TaskNodeRunModel(
                    task_id=task.id,
                    node_id=node_id,
                    agent_id=agent_id,
                    status="completed",
                    input_data={"topic": "技术信号窗口期"},
                    output_data={"demo": True, "node": node_id},
                    error_message=None,
                    degraded=False,
                    started_at=node_started,
                    completed_at=node_completed,
                    elapsed_seconds=max((node_completed - node_started).total_seconds(), 0.5),
                    prompt_tokens=100 + index * 9,
                    completion_tokens=140 + index * 8,
                    model_used="demo-showcase-v1",
                    retry_count=0,
                    created_at=node_started,
                    updated_at=node_completed,
                )
            )
        elif index == failure_index:
            node_completed = node_started + timedelta(seconds=slice_seconds - 0.5)
            db.add(
                TaskNodeRunModel(
                    task_id=task.id,
                    node_id=node_id,
                    agent_id=agent_id,
                    status="failed",
                    input_data={"topic": "技术信号窗口期"},
                    output_data=None,
                    error_message="demo timeout in outline_planner",
                    degraded=False,
                    started_at=node_started,
                    completed_at=node_completed,
                    elapsed_seconds=max((node_completed - node_started).total_seconds(), 0.5),
                    prompt_tokens=188,
                    completion_tokens=0,
                    model_used="demo-showcase-v1",
                    retry_count=0,
                    created_at=node_started,
                    updated_at=node_completed,
                )
            )
            break

    await db.flush()
    return task


async def seed_demo(app_id: str, app_secret: str, *, purge_noise: bool) -> None:
    seeded_at = datetime.now(timezone.utc).replace(microsecond=0)
    async with async_session_factory() as db:
        purged_noise = await purge_demo_noise(db) if purge_noise else []
        await cleanup_existing_demo(db)
        await set_demo_modes(db)
        account = await create_demo_account(db, seeded_at)
        reference_sources = await create_reference_sources(db, seeded_at)
        await create_wechat_config(db, seeded_at, app_id, app_secret)

        drafts_created: list[ArticleDraftModel] = []
        for spec in DEMO_DRAFT_SPECS:
            _, draft = await create_success_task_stack(db, spec, reference_sources, account, seeded_at)
            drafts_created.append(draft)

        await create_failed_task(db, reference_sources, account, seeded_at)
        await db.commit()

    print("Demo showcase seeded successfully.")
    print(f"account_id={DEMO_ACCOUNT_ID}")
    print(f"draft_count={len(drafts_created)}")
    print("task_count=5")
    print("reference_sources=3")
    print("wechat_config=stored")
    print("modes=generation:fake_success,publish:fake_success")
    print(f"purged_noise_accounts={len(purged_noise) if purge_noise else 0}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually write the demo seed data.")
    parser.add_argument("--purge-noise", action="store_true", help="Delete old audit/e2e accounts so only the demo view remains.")
    parser.add_argument("--wechat-app-id", dest="wechat_app_id")
    parser.add_argument("--wechat-app-secret", dest="wechat_app_secret")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if not args.apply:
        raise SystemExit("Refusing to run without --apply.")

    app_id, app_secret = resolve_wechat_credentials(args)
    await seed_demo(app_id, app_secret, purge_noise=args.purge_noise)


if __name__ == "__main__":
    asyncio.run(main())
