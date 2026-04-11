"""Deterministic query planning for source discovery and content strategy."""

from __future__ import annotations

import re
from typing import Any


class QueryPlannerService:
    """Plan account-aware source queries without introducing a second orchestrator."""

    _LANE_LIBRARY: dict[str, dict[str, Any]] = {
        "ai_tools": {
            "label": "AI 工具",
            "keywords": ["ai工具", "agent", "工作流", "提效", "产品", "应用", "软件", "自动化"],
            "query_suffixes": ["最新 动向", "使用 体验", "案例 拆解", "工作流 实战"],
            "source_preferences": [
                "产品发布公告",
                "一线使用案例",
                "公众号深度拆解",
                "工具对比评测",
            ],
            "banned_angles": [
                "脱离使用场景的功能罗列",
                "纯融资八卦",
                "泛泛而谈的AI大趋势",
            ],
        },
        "ai_research": {
            "label": "AI 论文",
            "keywords": ["论文", "paper", "research", "模型", "benchmark", "arxiv", "研究"],
            "query_suffixes": ["新论文 解读", "研究 进展", "方法 对比", "实验 结果"],
            "source_preferences": [
                "原始论文或摘要",
                "研究团队博客",
                "专业解读文章",
                "方法对比综述",
            ],
            "banned_angles": [
                "没有论文依据的二手传闻",
                "只讲概念不讲贡献",
                "把研究误写成产品宣传",
            ],
        },
        "emotional_growth": {
            "label": "情绪成长",
            "keywords": ["情绪", "成长", "焦虑", "内耗", "关系", "自我", "职场成长", "心理"],
            "query_suffixes": ["真实 场景", "问题 拆解", "经验 反思", "关系 修复"],
            "source_preferences": [
                "第一人称经验稿",
                "公众号观点文",
                "贴近生活的案例复盘",
                "心理与成长向长文",
            ],
            "banned_angles": [
                "空泛鸡汤",
                "没有场景的劝慰",
                "过度医疗化或说教化表达",
            ],
        },
        "industry_observation": {
            "label": "行业观察",
            "keywords": ["行业", "趋势", "观察", "商业", "市场", "公司", "组织", "创业"],
            "query_suffixes": ["趋势 判断", "案例 观察", "组织 变化", "市场 信号"],
            "source_preferences": [
                "行业媒体分析",
                "公司动态与公开访谈",
                "案例拆解文章",
                "观点型公众号长文",
            ],
            "banned_angles": [
                "空洞趋势判断",
                "与账号定位无关的猎奇新闻",
                "没有案例支撑的宏大叙事",
            ],
        },
        "general_insight": {
            "label": "通用洞察",
            "keywords": ["观察", "案例", "趋势", "方法", "复盘", "实践"],
            "query_suffixes": ["案例 拆解", "趋势 观察", "实践 复盘", "一线 经验"],
            "source_preferences": [
                "案例型文章",
                "公众号深度长文",
                "一线经验总结",
            ],
            "banned_angles": [
                "和账号定位无关的泛热点",
                "模板化方法论",
                "纯背景知识堆砌",
            ],
        },
    }

    _LANE_ALIASES = {
        "ai工具": "ai_tools",
        "agent": "ai_tools",
        "工作流": "ai_tools",
        "提效": "ai_tools",
        "ai论文": "ai_research",
        "论文": "ai_research",
        "research": "ai_research",
        "arxiv": "ai_research",
        "情绪成长": "emotional_growth",
        "成长": "emotional_growth",
        "心理": "emotional_growth",
        "关系": "emotional_growth",
        "行业观察": "industry_observation",
        "行业": "industry_observation",
        "趋势": "industry_observation",
        "商业": "industry_observation",
    }

    def build_plan(
        self,
        *,
        profile: dict[str, Any] | None = None,
        account_context: dict[str, Any] | None = None,
        ops_context: dict[str, Any] | None = None,
        selected_topic: str | None = None,
        selected_title: str | None = None,
        hot_topics: dict[str, Any] | None = None,
        max_queries: int = 4,
    ) -> dict[str, Any]:
        """Build a reusable query plan for source scouting and writing strategy."""

        profile = profile if isinstance(profile, dict) else {}
        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        hot_topics = hot_topics if isinstance(hot_topics, dict) else {}

        lane_hint = (
            (ops_context.get("run_strategy") or {}).get("preferred_content_lane")
            or account_context.get("content_strategy")
            or account_context.get("positioning")
            or profile.get("subdomain")
            or profile.get("domain")
            or ""
        )
        topic_hint = self._clean_text(selected_topic) or self._pick_hot_topic(hot_topics)
        title_hint = self._clean_text(selected_title)

        lane_id, lane_reason = self._infer_lane(
            lane_hint=lane_hint,
            topic_hint=topic_hint,
            title_hint=title_hint,
            profile=profile,
            account_context=account_context,
        )
        lane_config = self._LANE_LIBRARY[lane_id]

        keyword_pool = self._collect_keyword_pool(
            profile=profile,
            account_context=account_context,
            lane_config=lane_config,
            lane_hint=lane_hint,
            topic_hint=topic_hint,
            title_hint=title_hint,
        )
        primary_queries = self._build_primary_queries(
            topic_hint=topic_hint,
            title_hint=title_hint,
            keywords=keyword_pool,
            lane_config=lane_config,
            max_queries=max_queries,
        )
        secondary_queries = self._build_secondary_queries(
            topic_hint=topic_hint,
            keywords=keyword_pool,
            lane_config=lane_config,
            max_queries=max_queries,
        )
        source_preferences = self._build_source_preferences(
            account_context=account_context,
            lane_config=lane_config,
        )
        banned_angles = self._build_banned_angles(
            account_context=account_context,
            ops_context=ops_context,
            lane_config=lane_config,
        )

        return {
            "lane": {
                "id": lane_id,
                "label": lane_config["label"],
                "input_hint": self._clean_text(lane_hint) or None,
                "reason": lane_reason,
            },
            "selected_topic": topic_hint or None,
            "selected_title": title_hint or None,
            "primary_queries": primary_queries,
            "secondary_queries": secondary_queries,
            "source_preferences": source_preferences,
            "banned_angles": banned_angles,
            "account_keywords": keyword_pool[:8],
            "search_terms": keyword_pool[:4] or [lane_config["label"]],
        }

    def _infer_lane(
        self,
        *,
        lane_hint: str,
        topic_hint: str,
        title_hint: str,
        profile: dict[str, Any],
        account_context: dict[str, Any],
    ) -> tuple[str, str]:
        haystack = " ".join(
            filter(
                None,
                [
                    self._clean_text(lane_hint),
                    self._clean_text(topic_hint),
                    self._clean_text(title_hint),
                    self._clean_text(profile.get("domain")),
                    self._clean_text(profile.get("subdomain")),
                    self._clean_text(account_context.get("positioning")),
                ],
            )
        ).lower()

        for alias, lane_id in self._LANE_ALIASES.items():
            if alias in haystack:
                return lane_id, f"Matched lane hint '{alias}' from account context."

        best_lane = "general_insight"
        best_score = -1
        for lane_id, lane_config in self._LANE_LIBRARY.items():
            score = sum(1 for keyword in lane_config["keywords"] if keyword in haystack)
            if score > best_score:
                best_lane = lane_id
                best_score = score

        if best_score > 0:
            return best_lane, "Inferred lane from account wording and topic signals."
        return "general_insight", "No strong lane signal found, defaulted to general insight."

    def _collect_keyword_pool(
        self,
        *,
        profile: dict[str, Any],
        account_context: dict[str, Any],
        lane_config: dict[str, Any],
        lane_hint: str,
        topic_hint: str,
        title_hint: str,
    ) -> list[str]:
        raw_keywords: list[str] = []
        raw_keywords.extend(self._normalize_string_list(profile.get("keywords")))
        raw_keywords.extend(
            [
                self._clean_text(topic_hint),
                self._clean_text(title_hint),
                self._clean_text(profile.get("domain")),
                self._clean_text(profile.get("subdomain")),
                self._clean_text(account_context.get("positioning")),
                self._clean_text(account_context.get("audience")),
                self._clean_text(account_context.get("content_strategy")),
                self._clean_text(lane_hint),
            ]
        )
        raw_keywords.extend(lane_config["keywords"])

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_keywords:
            text = self._clean_text(item)
            if not text:
                continue
            compact = re.sub(r"\s+", " ", text)
            key = compact.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(compact)
            if len(normalized) >= 12:
                break
        return normalized

    def _build_primary_queries(
        self,
        *,
        topic_hint: str,
        title_hint: str,
        keywords: list[str],
        lane_config: dict[str, Any],
        max_queries: int,
    ) -> list[str]:
        queries: list[str] = []
        focus = topic_hint or title_hint or (keywords[0] if keywords else lane_config["label"])
        for suffix in lane_config["query_suffixes"]:
            candidate = self._clean_text(f"{focus} {suffix}")
            if candidate and candidate not in queries:
                queries.append(candidate)
            if len(queries) >= max_queries:
                return queries

        for keyword in keywords:
            candidate = self._clean_text(f"{keyword} {lane_config['query_suffixes'][0]}")
            if candidate and candidate not in queries:
                queries.append(candidate)
            if len(queries) >= max_queries:
                break
        return queries

    def _build_secondary_queries(
        self,
        *,
        topic_hint: str,
        keywords: list[str],
        lane_config: dict[str, Any],
        max_queries: int,
    ) -> list[str]:
        queries: list[str] = []
        topic_tokens = self._tokenize(topic_hint)
        broad_focus = " ".join(topic_tokens[:2]) if topic_tokens else (keywords[0] if keywords else lane_config["label"])

        secondary_templates = [
            f"{broad_focus} 案例",
            f"{broad_focus} 观点",
            f"{broad_focus} 复盘",
            f"{lane_config['label']} 最新",
        ]
        for item in secondary_templates:
            candidate = self._clean_text(item)
            if candidate and candidate not in queries:
                queries.append(candidate)
            if len(queries) >= max_queries:
                break
        return queries

    def _build_source_preferences(
        self,
        *,
        account_context: dict[str, Any],
        lane_config: dict[str, Any],
    ) -> list[str]:
        preferences = list(lane_config["source_preferences"])
        for source in account_context.get("reference_sources", []) if isinstance(account_context.get("reference_sources"), list) else []:
            if not isinstance(source, dict):
                continue
            name = self._clean_text(source.get("name"))
            source_type = self._clean_text(source.get("source_type"))
            if name:
                preferences.append(f"账号参考源: {name}")
            if source_type:
                preferences.append(f"优先覆盖 {source_type} 类型来源")
        return self._dedupe(preferences)[:6]

    def _build_banned_angles(
        self,
        *,
        account_context: dict[str, Any],
        ops_context: dict[str, Any],
        lane_config: dict[str, Any],
    ) -> list[str]:
        banned = list(lane_config["banned_angles"])
        banned.extend(
            [
                "和账号定位无关的泛热点追逐",
                "只复述资料、不形成判断",
                "只抄参考源结构、不结合账号读者",
            ]
        )
        banned.extend(
            self._normalize_string_list(
                (ops_context.get("run_strategy") or {}).get("avoid_recent_topics")
            )
        )
        banned.extend(
            self._normalize_string_list(
                (account_context.get("reference_style_guide") or {}).get("usage_rules")
            )
        )
        return self._dedupe(banned)[:8]

    def _pick_hot_topic(self, hot_topics: dict[str, Any]) -> str:
        items = hot_topics.get("hot_topics")
        if not isinstance(items, list):
            return ""
        for item in items:
            if isinstance(item, dict):
                title = self._clean_text(item.get("title"))
                if title:
                    return title
        return ""

    def _tokenize(self, text: str | None) -> list[str]:
        raw = self._clean_text(text)
        if not raw:
            return []
        tokens = re.split(r"[\s,，。！？、:：;；/\\\\\\-]+", raw)
        normalized: list[str] = []
        for token in tokens:
            clean = self._clean_text(token)
            if clean:
                normalized.append(clean)
        return normalized

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [self._clean_text(item) for item in value if self._clean_text(item)]

    def _dedupe(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            clean = self._clean_text(item)
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(clean)
        return normalized

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


query_planner_service = QueryPlannerService()
