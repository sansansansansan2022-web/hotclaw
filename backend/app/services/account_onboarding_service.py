"""Services for account onboarding and existing-account analysis."""

from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.logger import get_logger
from app.llm.base import LLMCallOptions
from app.llm.exceptions import LLMCallError, LLMConfigurationError
from app.llm.gateway import get_llm_gateway
from app.platforms import normalize_content_platform, platform_label
from app.schemas.account_onboarding import (
    ExistingAccountAnalysisRequest,
    ExistingAccountAnalysisResponse,
)

logger = get_logger(__name__)

_EXISTING_ACCOUNT_SYSTEM_PROMPT = """\
你是一位多平台内容账号接入顾问。你的任务不是直接创建账号，而是根据历史图文/文章，为接入向导输出一版结构化初始化建议。

请严格返回 JSON 对象，不要包含 markdown 代码块，不要输出额外解释。

返回字段：
- inferred_positioning: 一段 1-3 句的账号定位总结
- inferred_audience: 一段简洁的目标受众描述
- inferred_tone_style: 一段简洁的语言风格描述
- inferred_content_strategy: 一段 2-4 句的内容策略摘要
- inferred_reference_accounts_summary: 如无法判断可返回 null
- recommended_operation_mode: manual / semi_auto / full_auto，老公众号默认优先 semi_auto
- onboarding_notes: 数组，给出 2-5 条接入建议或风险提示
- extracted_topics: 数组，提取 3-8 个常见主题/栏目
- style_summary: 一段简洁风格总结

规则：
- 如果材料不足，请保守输出，并在 onboarding_notes 里明确提示低置信度
- 不要编造精确数据
- 推荐模式优先稳妥，除非材料非常充分且风格稳定，否则不要推荐 full_auto
- 如果 content_platform 是 xiaohongshu，请重点分析小红书图文账号：封面钩子、首图承诺、滑动卡片结构、正文前三行、标签/搜索词、评论互动、种草/避坑/清单/经验等笔记类型。
- 如果 content_platform 是 wechat，请重点分析公众号：长文结构、标题风格、导语、分节方式、观点密度和发布节奏。
"""


class AccountOnboardingService:
    """Onboarding analysis logic for new and existing accounts."""

    async def analyze_existing_account(
        self, payload: ExistingAccountAnalysisRequest
    ) -> ExistingAccountAnalysisResponse:
        account_name = payload.account_name.strip()
        content_platform = normalize_content_platform(payload.content_platform)
        article_urls = self._normalize_urls(payload.article_urls)
        article_texts = self._normalize_texts(payload.article_texts)

        if not article_urls and not article_texts:
            raise ValueError("Provide at least one article URL or pasted article text.")

        fetch_notes: list[str] = []
        fetched_url_texts = await self._fetch_url_texts(article_urls, fetch_notes)
        usable_texts = article_texts + fetched_url_texts
        analysis_confidence = self._estimate_confidence(article_texts, fetched_url_texts)

        if not usable_texts:
            logger.warning(
                "existing_account_analysis_no_text_material",
                account_name=account_name,
                url_count=len(article_urls),
            )
            return self._build_heuristic_response(
                account_name=account_name,
                content_platform=content_platform,
                article_urls=article_urls,
                article_texts=[],
                fetch_notes=fetch_notes,
                analysis_confidence="low",
            )

        try:
            analysis = await self._analyze_with_llm(
                account_name=account_name,
                content_platform=content_platform,
                article_urls=article_urls,
                article_texts=usable_texts,
            )
            response = self._coerce_response(
                account_name=account_name,
                content_platform=content_platform,
                raw=analysis,
                article_urls=article_urls,
                article_texts=usable_texts,
                fetch_notes=fetch_notes,
                analysis_confidence=analysis_confidence,
            )
        except (LLMConfigurationError, LLMCallError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "existing_account_analysis_fallback",
                account_name=account_name,
                error=str(exc),
            )
            response = self._build_heuristic_response(
                account_name=account_name,
                content_platform=content_platform,
                article_urls=article_urls,
                article_texts=usable_texts,
                fetch_notes=fetch_notes,
                analysis_confidence=analysis_confidence,
            )

        logger.info(
            "existing_account_analyzed",
            account_name=account_name,
            input_url_count=len(article_urls),
            pasted_text_count=len(article_texts),
            fetched_url_text_count=len(fetched_url_texts),
            used_article_count=response.used_article_count,
            analysis_confidence=response.analysis_confidence,
        )
        return response

    async def _analyze_with_llm(
        self,
        *,
        account_name: str,
        content_platform: str,
        article_urls: list[str],
        article_texts: list[str],
    ) -> dict:
        gateway = get_llm_gateway()
        excerpts = []
        for index, text in enumerate(article_texts[:6], start=1):
            excerpts.append(
                {
                    "article_index": index,
                    "excerpt": text[:2500],
                }
            )

        prompt = json.dumps(
            {
                "account_name": account_name,
                "content_platform": content_platform,
                "platform_label": platform_label(content_platform),
                "article_urls": article_urls[:10],
                "historical_articles": excerpts,
                "task": "Analyze historical content for platform-specific onboarding.",
            },
            ensure_ascii=False,
        )

        response = await gateway.complete(
            agent_id="account_onboarding_existing_analysis",
            prompt=prompt,
            options=LLMCallOptions(
                system_prompt=_EXISTING_ACCOUNT_SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=1200,
            ),
        )
        return self._parse_json(response.content)

    async def _fetch_url_texts(self, urls: list[str], fetch_notes: list[str]) -> list[str]:
        if not urls:
            return []

        results = await asyncio.gather(
            *(asyncio.to_thread(self._fetch_single_url_text, url) for url in urls[:5]),
            return_exceptions=True,
        )

        texts: list[str] = []
        for url, result in zip(urls[:5], results):
            if isinstance(result, Exception):
                fetch_notes.append(f"URL fetch failed for {url}: {result}")
                continue

            text, note = result
            if text:
                texts.append(text)
            if note:
                fetch_notes.append(note)
        return texts

    def _fetch_single_url_text(self, url: str) -> tuple[str | None, str | None]:
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "HotClawAccountOnboarding/1.0",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            with urlopen(request, timeout=8) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            return None, f"Could not fetch {url}. Suggest pasting the article body directly. ({exc})"

        decoded = self._decode_bytes(raw)
        if not decoded:
            return None, f"Fetched {url} but could not decode the article body."

        extracted = self._html_to_text(decoded)
        if len(extracted) < 200:
            return None, f"Fetched {url} but extracted too little readable text. Suggest pasting the article body directly."

        return extracted[:4000], f"Fetched URL content from {url} for onboarding analysis."

    def _decode_bytes(self, raw: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    def _html_to_text(self, html_content: str) -> str:
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_content)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _coerce_response(
        self,
        *,
        account_name: str,
        content_platform: str,
        raw: dict,
        article_urls: list[str],
        article_texts: list[str],
        fetch_notes: list[str],
        analysis_confidence: str,
    ) -> ExistingAccountAnalysisResponse:
        topics = [str(item).strip() for item in raw.get("extracted_topics", []) if str(item).strip()]
        notes = [str(item).strip() for item in raw.get("onboarding_notes", []) if str(item).strip()]
        notes.extend(fetch_notes)

        if analysis_confidence == "low":
            notes.insert(0, "Historical material is limited, so this onboarding draft should be reviewed manually.")

        reference_summary = raw.get("inferred_reference_accounts_summary")
        if not reference_summary and article_urls:
            hosts = sorted({urlparse(url).netloc for url in article_urls if urlparse(url).netloc})
            if hosts:
                reference_summary = "Historical URLs observed from: " + ", ".join(hosts)

        recommended_mode = str(raw.get("recommended_operation_mode") or "semi_auto")
        if recommended_mode not in {"manual", "semi_auto", "full_auto"}:
            recommended_mode = "semi_auto"

        return ExistingAccountAnalysisResponse(
            account_name=account_name,
            content_platform=content_platform,
            inferred_positioning=str(raw.get("inferred_positioning") or "").strip() or self._fallback_positioning(account_name, topics, content_platform),
            inferred_audience=str(raw.get("inferred_audience") or "").strip() or "Existing readers of this account plus adjacent readers with similar interests.",
            inferred_tone_style=str(raw.get("inferred_tone_style") or "").strip() or (
                "Short, visual, note-like, with concrete scenes and interaction hooks."
                if content_platform == "xiaohongshu"
                else "Knowledge-first, readable, and suitable for human review before publishing."
            ),
            inferred_content_strategy=str(raw.get("inferred_content_strategy") or "").strip()
            or "Start from the recurring themes already visible in the historical material, then refine columns and cadence inside the account workspace.",
            inferred_reference_accounts_summary=str(reference_summary).strip() if reference_summary else None,
            recommended_operation_mode=recommended_mode,
            onboarding_notes=notes[:6],
            extracted_topics=topics[:8],
            style_summary=str(raw.get("style_summary") or "").strip()
            or (
                "The existing account should be treated as an image-text note account: cover promise, swipe-card structure, short body, and comment hook."
                if content_platform == "xiaohongshu"
                else "The existing account leans toward repeatable, explanatory long-form writing."
            ),
            analysis_confidence=analysis_confidence if analysis_confidence in {"low", "medium", "high"} else "medium",
            source_summary=self._build_source_summary(article_urls, article_texts, fetch_notes),
            used_article_count=len(article_texts),
        )

    def _build_heuristic_response(
        self,
        *,
        account_name: str,
        content_platform: str,
        article_urls: list[str],
        article_texts: list[str],
        fetch_notes: list[str],
        analysis_confidence: str,
    ) -> ExistingAccountAnalysisResponse:
        topics = self._extract_topics(article_texts)
        notes = list(fetch_notes)
        notes.insert(0, "Analysis fell back to a heuristic draft. You can still edit every field before creating the account.")
        if not article_texts:
            notes.append("URL-only input gives weaker results. Pasting 3-10 representative article bodies will improve accuracy.")

        return ExistingAccountAnalysisResponse(
            account_name=account_name,
            content_platform=content_platform,
            inferred_positioning=self._fallback_positioning(account_name, topics, content_platform),
            inferred_audience="Existing followers of this account and adjacent readers who already respond to its current topics.",
            inferred_tone_style=(
                "Limited evidence; verify cover style, note voice, card rhythm, tags, and comment bait before operating."
                if content_platform == "xiaohongshu"
                else "Existing-account style inferred from limited material; verify the tone before creating the account."
            ),
            inferred_content_strategy=(
                "Use the current historical material as a baseline, keep the strongest recurring topics, and iterate from the account workspace after the first run."
            ),
            inferred_reference_accounts_summary=(
                "Historical onboarding references came from these URLs: " + ", ".join(article_urls[:5])
                if article_urls
                else None
            ),
            recommended_operation_mode="semi_auto",
            onboarding_notes=notes[:6],
            extracted_topics=topics[:8],
            style_summary=(
                "The account appears to need Xiaohongshu image-text style learning, but the historical evidence is limited."
                if content_platform == "xiaohongshu"
                else "The account appears to rely on repeatable editorial patterns, but the historical evidence is limited."
            ),
            analysis_confidence=analysis_confidence if analysis_confidence in {"low", "medium", "high"} else "low",
            source_summary=self._build_source_summary(article_urls, article_texts, fetch_notes),
            used_article_count=len(article_texts),
        )

    def _normalize_urls(self, urls: list[str] | None) -> list[str]:
        return [item.strip() for item in (urls or []) if item and item.strip()]

    def _normalize_texts(self, texts: list[str] | None) -> list[str]:
        normalized = []
        for item in texts or []:
            text = re.sub(r"\s+", " ", item or "").strip()
            if text:
                normalized.append(text[:8000])
        return normalized[:10]

    def _estimate_confidence(self, pasted_texts: list[str], fetched_texts: list[str]) -> str:
        total_chars = sum(len(item) for item in pasted_texts + fetched_texts)
        if len(pasted_texts) >= 3 and total_chars >= 6000:
            return "high"
        if total_chars >= 1500:
            return "medium"
        return "low"

    def _fallback_positioning(self, account_name: str, topics: list[str], content_platform: str = "wechat") -> str:
        platform = platform_label(content_platform)
        if topics:
            return f"{account_name} is an existing {platform} account that appears to focus on {', '.join(topics[:3])}. Use this as the starting positioning draft and refine it after onboarding."
        return f"{account_name} is an existing {platform} account. Start from its historical themes, verify audience and tone, then refine the positioning inside the workspace."

    def _extract_topics(self, article_texts: list[str]) -> list[str]:
        counter: Counter[str] = Counter()
        for text in article_texts:
            for token in re.findall(r"[A-Za-z][A-Za-z\\-]{3,}|[\u4e00-\u9fff]{2,6}", text):
                if token.lower() in {"this", "that", "with", "from", "have", "your", "about"}:
                    continue
                counter[token] += 1
        return [item for item, _ in counter.most_common(6)]

    def _build_source_summary(
        self, article_urls: list[str], article_texts: list[str], fetch_notes: list[str]
    ) -> str:
        parts = [
            f"Pasted article bodies: {len(article_texts)}",
            f"URL inputs: {len(article_urls)}",
        ]
        if fetch_notes:
            parts.append(f"Fetch notes: {len(fetch_notes)}")
        return " | ".join(parts)

    def _parse_json(self, content: str) -> dict:
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)


account_onboarding_service = AccountOnboardingService()
