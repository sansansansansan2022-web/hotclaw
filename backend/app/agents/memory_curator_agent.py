"""Memory curator agent: distill article into memory, evolve profile, add notes."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_gateway import llm_gateway


_MAX_NOTE_CHARS = 120
_MAX_NOTES = 3
_EXCERPT_CHARS = 300


class MemoryCuratorAgent(BaseAgent):
    """Close the self-operating loop by distilling each published article.

    One LLM call produces:
    - article_memory: title / summary / excerpt / tags / keywords for recall
    - evolved_profile_updates: fields to merge into account.evolved_profile_json
    - style_profile_updates: fields to merge into account.style_profile_json
    - new_notes: ≤3 short, dense agent notes (≤120 chars each) for account_notes

    The agent does NOT write to the DB; task_service._persist_memory_curation does.
    """

    agent_id = "memory_curator_agent"
    name = "记忆整理"
    description = "文章完成后蒸馏记忆、更新 evolved_profile 和 style_profile、记录账号注记。"

    input_schema = {
        "type": "object",
        "properties": {
            "assembled_article": {"type": "object", "description": "最终装配文章（来自 article_assembler 或 content_writer）"},
            "content": {"type": "object", "description": "内容（兼容旧格式）"},
            "profile": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "editorial_review": {"type": "object", "description": "编辑审核结果（可选）"},
        },
        "required": [],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "article_memory": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "content_excerpt": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "metadata_json": {"type": "object"},
                },
            },
            "evolved_profile_updates": {"type": "object"},
            "style_profile_updates": {"type": "object"},
            "new_notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "source": {"type": "string"},
                    },
                },
            },
        },
    }

    default_system_prompt = """\
你是 HotClaw 账号运营记忆管理员，负责在每篇文章完成后蒸馏关键记忆、更新账号画像演化层。

## 任务
基于本次文章内容和账号信息，生成以下四部分 JSON：

### 1. article_memory（文章记忆卡）
帮助未来任务了解历史内容，避免重复，强化风格。

### 2. evolved_profile_updates（画像演化更新）
动态更新账号特征——关注已验证的内容方向、情绪模式、受众反应规律。
仅输出本次有新发现的字段，不要覆盖不相关字段。

### 3. style_profile_updates（风格档案更新）
更新写作风格记录——有效的开头模式、常用钩子、段落节奏、结尾 CTA 模式。
仅输出有新观察的字段。

### 4. new_notes（账号注记）
≤3 条精炼运营经验，每条 ≤120 字，密度高、可执行、避免废话。
关注：这次任务学到了什么？什么效果好？什么需要避免？

## 输出规范
返回严格 JSON，不输出其他内容：
{
  "article_memory": {
    "title": string,
    "summary": string,            // 1-2 句话总结文章核心观点
    "content_excerpt": string,    // 文章前 200 字摘录
    "tags": [string],             // 3-5 个内容标签
    "keywords": [string],         // 3-8 个关键词
    "metadata_json": {
      "selected_topic": string,
      "word_count": int,
      "editorial_passed": bool | null
    }
  },
  "evolved_profile_updates": {
    "recent_content_themes": [string],   // 近期内容主题趋势（累积列表）
    "proven_emotional_triggers": [string], // 已验证有效的情绪触发点
    "content_strengths": [string]        // 本账号内容的差异化优势
  },
  "style_profile_updates": {
    "effective_opening_patterns": [string],  // 有效开头模式示例
    "hook_templates": [string],              // 钩子模板
    "cta_patterns": [string]                // 结尾 CTA 模式
  },
  "new_notes": [
    {"content": string, "source": "memory_curator"}
  ]
}
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            response = await llm_gateway.complete(
                agent_id=self.agent_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format="json",
            )
            return self._success(self._normalize(response.parsed or {}, input_data))
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        # Accept assembled_article (new) or content (legacy)
        article = input_data.get("assembled_article") or input_data.get("content") or {}
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        editorial_review = input_data.get("editorial_review") or {}

        title = (
            article.get("selected_title")
            or article.get("title")
            or account_context.get("account_name", "未知标题")
        )
        topic = article.get("selected_topic") or ""
        content_markdown = str(article.get("content_markdown") or "")[:1500]
        word_count = article.get("word_count") or 0
        tags = article.get("tags") or []
        editorial_passed = editorial_review.get("editorial_passed")
        combined_suggestions = editorial_review.get("combined_rewrite_suggestions") or []

        account_name = account_context.get("account_name") or "未知账号"
        positioning = account_context.get("positioning") or profile.get("positioning_raw") or ""
        tone = account_context.get("tone_style") or profile.get("tone") or ""
        domain = profile.get("domain") or ""
        preferred_lane = (ops_context.get("run_strategy") or {}).get("preferred_content_lane") or ""

        parts = [
            "请基于以下本次任务信息，生成记忆蒸馏和画像更新 JSON。",
            "",
            "## 账号基本信息",
            f"- 账号名: {account_name}",
            f"- 定位: {positioning}" if positioning else "",
            f"- 调性: {tone}" if tone else "",
            f"- 领域: {domain}" if domain else "",
            f"- 内容赛道: {preferred_lane}" if preferred_lane else "",
            "",
            "## 本次文章",
            f"- 标题: {title}",
            f"- 选题: {topic}" if topic else "",
            f"- 字数: {word_count}",
            f"- 标签: {', '.join(str(t) for t in tags)}" if tags else "",
            f"- 编辑审核通过: {editorial_passed}" if editorial_passed is not None else "",
            "",
            "## 文章内容（节选）",
            content_markdown,
        ]

        if combined_suggestions:
            parts += [
                "",
                "## 编辑改写建议（反映了哪些不足）",
                *[f"- {s}" for s in combined_suggestions[:3]],
            ]

        parts.append("")
        parts.append("请输出完整记忆蒸馏 JSON。")
        return "\n".join(p for p in parts if p is not None)

    def _normalize(self, data: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        # article_memory
        raw_mem = data.get("article_memory") or {}
        article = input_data.get("assembled_article") or input_data.get("content") or {}
        title = str(raw_mem.get("title") or article.get("selected_title") or "").strip()
        summary = str(raw_mem.get("summary") or article.get("summary") or "").strip()
        content_markdown = str(article.get("content_markdown") or "")
        content_excerpt = str(raw_mem.get("content_excerpt") or content_markdown[:_EXCERPT_CHARS]).strip()
        tags_raw = raw_mem.get("tags") or article.get("tags") or []
        tags = [str(t).strip() for t in tags_raw if str(t).strip()][:8]
        keywords_raw = raw_mem.get("keywords") or []
        keywords = [str(k).strip() for k in keywords_raw if str(k).strip()][:10]
        meta_raw = raw_mem.get("metadata_json") or {}
        metadata_json = {
            "selected_topic": str(meta_raw.get("selected_topic") or article.get("selected_topic") or ""),
            "word_count": int(meta_raw.get("word_count") or article.get("word_count") or 0),
            "editorial_passed": meta_raw.get("editorial_passed"),
        }

        # evolved_profile_updates — keep only known string-list fields
        raw_ep = data.get("evolved_profile_updates") or {}
        evolved_profile_updates = {}
        for key in ("recent_content_themes", "proven_emotional_triggers", "content_strengths"):
            val = raw_ep.get(key)
            if isinstance(val, list) and val:
                evolved_profile_updates[key] = [str(v).strip() for v in val if str(v).strip()][:6]

        # style_profile_updates
        raw_sp = data.get("style_profile_updates") or {}
        style_profile_updates = {}
        for key in ("effective_opening_patterns", "hook_templates", "cta_patterns"):
            val = raw_sp.get(key)
            if isinstance(val, list) and val:
                style_profile_updates[key] = [str(v).strip() for v in val if str(v).strip()][:4]

        # new_notes
        raw_notes = data.get("new_notes") or []
        new_notes = []
        for item in raw_notes[:_MAX_NOTES]:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()[:_MAX_NOTE_CHARS]
            if content:
                new_notes.append({"content": content, "source": "memory_curator"})

        return {
            "article_memory": {
                "title": title,
                "summary": summary,
                "content_excerpt": content_excerpt,
                "tags": tags,
                "keywords": keywords,
                "metadata_json": metadata_json,
            },
            "evolved_profile_updates": evolved_profile_updates,
            "style_profile_updates": style_profile_updates,
            "new_notes": new_notes,
        }

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """Return a minimal stub so the pipeline doesn't fail — curation is optional."""
        article = input_data.get("assembled_article") or input_data.get("content") or {}
        title = str(article.get("selected_title") or article.get("title") or "").strip()
        content_markdown = str(article.get("content_markdown") or "")
        return self._success(
            {
                "article_memory": {
                    "title": title,
                    "summary": "",
                    "content_excerpt": content_markdown[:_EXCERPT_CHARS],
                    "tags": article.get("tags") or [],
                    "keywords": [],
                    "metadata_json": {
                        "selected_topic": str(article.get("selected_topic") or ""),
                        "word_count": int(article.get("word_count") or 0),
                        "editorial_passed": None,
                    },
                },
                "evolved_profile_updates": {},
                "style_profile_updates": {},
                "new_notes": [],
            }
        )
