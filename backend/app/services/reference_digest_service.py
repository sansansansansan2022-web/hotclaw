"""Shared source scouting and reference digestion helpers."""

from __future__ import annotations

import re
from typing import Any


class ReferenceDigestService:
    """Normalize account references and hot-topic sources into reusable digests."""

    def build_account_reference_digest(
        self,
        reference_sources: list[dict[str, Any]] | None,
        *,
        preferred_source_ids: list[str] | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        account_context = {
            "reference_sources": reference_sources or [],
            "reference_source_briefs": reference_sources or [],
        }
        ops_context = {
            "run_strategy": {
                "preferred_reference_source_ids": preferred_source_ids or [],
            }
        }
        return self.build_reference_digest(
            account_context=account_context,
            ops_context=ops_context,
            limit=limit,
        )

    def build_source_scout_package(
        self,
        *,
        search_results: list[dict[str, Any]] | None,
        query_plan: dict[str, Any] | None,
        account_context: dict[str, Any] | None = None,
        ops_context: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        """Turn raw search results into source candidates and a shared digest."""

        query_plan = query_plan if isinstance(query_plan, dict) else {}
        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        search_results = search_results if isinstance(search_results, list) else []

        query_tokens = self._build_match_tokens(
            query_plan.get("selected_topic"),
            query_plan.get("selected_title"),
            query_plan.get("primary_queries"),
            query_plan.get("account_keywords"),
        )
        source_preferences = self._normalize_string_list(query_plan.get("source_preferences"))

        candidates: list[dict[str, Any]] = []
        for index, item in enumerate(search_results):
            if not isinstance(item, dict):
                continue
            source_title = self._clean_text(item.get("title"))
            if not source_title:
                continue
            source_name = self._clean_text(item.get("source")) or self._clean_text(item.get("source_type")) or "Search result"
            source_type = self._clean_text(item.get("source_type")) or "search_result"
            snippet = self._clip_text(
                item.get("snippet") or item.get("summary") or source_title,
                180,
            )
            fit_score = self._estimate_fit(
                text=" ".join(filter(None, [source_title, snippet, source_name])),
                match_tokens=query_tokens,
                source_preferences=source_preferences,
                source_name=source_name,
                source_type=source_type,
            )
            candidates.append(
                {
                    "source_id": self._clean_text(item.get("source_id")) or f"scout:{source_type}:{index + 1}",
                    "source_type": source_type,
                    "source_name": source_name,
                    "source_title": source_title,
                    "url": self._clean_text(item.get("url")) or None,
                    "snippet": snippet,
                    "fit_score": round(fit_score, 3),
                    "origin": "source_scout",
                    "why_selected": self._build_candidate_reason(
                        source_name=source_name,
                        source_type=source_type,
                        snippet=snippet,
                        query_tokens=query_tokens,
                    ),
                }
            )

        candidates.sort(
            key=lambda item: (
                -float(item.get("fit_score") or 0.0),
                self._clean_text(item.get("source_name")),
                self._clean_text(item.get("source_title")),
            )
        )
        selected_candidates = candidates[:limit]
        reference_digest = self.build_reference_digest(
            account_context=account_context,
            ops_context=ops_context,
            query_plan=query_plan,
            source_candidates=selected_candidates,
            limit=min(4, max(1, limit)),
        )
        return {
            "source_candidates": selected_candidates,
            "source_snippets": [
                {
                    "source_id": item.get("source_id"),
                    "source_title": item.get("source_title"),
                    "source_type": item.get("source_type"),
                    "snippet": item.get("snippet"),
                }
                for item in selected_candidates[: min(6, len(selected_candidates))]
            ],
            "reference_digest": reference_digest,
        }

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None = None,
        ops_context: dict[str, Any] | None = None,
        query_plan: dict[str, Any] | None = None,
        source_candidates: list[dict[str, Any]] | None = None,
        selected_topic: str | None = None,
        selected_title: str | None = None,
        limit: int = 4,
    ) -> dict[str, Any]:
        """Build a shared digest for writers and reviewers."""

        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        query_plan = query_plan if isinstance(query_plan, dict) else {}
        source_candidates = source_candidates if isinstance(source_candidates, list) else []

        preferred_source_ids = {
            str(item).strip()
            for item in ((ops_context.get("run_strategy") or {}).get("preferred_reference_source_ids") or [])
            if str(item).strip()
        }
        match_tokens = self._build_match_tokens(
            selected_topic or query_plan.get("selected_topic"),
            selected_title or query_plan.get("selected_title"),
            query_plan.get("primary_queries"),
            query_plan.get("account_keywords"),
        )

        account_sources = self._normalize_account_sources(account_context, preferred_source_ids)
        scout_sources = self._normalize_source_candidates(source_candidates)
        selected_sources = self._select_balanced_sources(
            account_sources=account_sources,
            scout_sources=scout_sources,
            match_tokens=match_tokens,
            preferred_source_ids=preferred_source_ids,
            limit=limit,
        )

        source_digests = [self._build_source_digest(item, match_tokens) for item in selected_sources]
        style_takeaways = self._dedupe(
            [
                f"{digest.get('source_name') or digest.get('source_title')}: {digest['style_brief']}"
                for digest in source_digests
                if digest.get("style_brief")
            ]
        )[:limit]
        structure_takeaways = self._dedupe(
            [
                f"{digest.get('source_name') or digest.get('source_title')}: {digest['structure_brief']}"
                for digest in source_digests
                if digest.get("structure_brief")
            ]
        )[:limit]
        useful_points = self._dedupe(
            [
                point
                for digest in source_digests
                for point in digest.get("useful_points", [])
                if self._clean_text(point)
            ]
        )[: max(limit * 2, 4)]

        account_source_count = sum(1 for item in selected_sources if item.get("origin") == "account_reference")
        scout_source_count = sum(1 for item in selected_sources if item.get("origin") == "source_scout")

        return {
            "summary": self._build_digest_summary(
                account_source_count=account_source_count,
                scout_source_count=scout_source_count,
                preferred_names=[item.get("source_name") or item.get("source_title") for item in selected_sources],
            ),
            "source_count": len(account_sources) + len(scout_sources),
            "selected_source_ids": [item.get("source_id") for item in selected_sources if item.get("source_id")],
            "preferred_source_names": self._dedupe(
                [item.get("source_name") or item.get("source_title") for item in selected_sources]
            )[:limit],
            "style_takeaways": style_takeaways,
            "structure_takeaways": structure_takeaways,
            "useful_points": useful_points,
            "usage_rules": [
                "Use account references to calibrate voice and pacing, not to copy sentences.",
                "Use source-scout candidates for timely texture, examples, and angle checks, not as raw article templates.",
                "If references conflict with the selected topic, keep the topic accurate and only borrow the useful framing pattern.",
            ],
            "source_digests": source_digests,
            "source_snippets": [
                {
                    "source_id": digest.get("source_id"),
                    "source_title": digest.get("source_title"),
                    "source_type": digest.get("source_type"),
                    "snippet": digest.get("snippet"),
                }
                for digest in source_digests
            ],
        }

    def _normalize_account_sources(
        self,
        account_context: dict[str, Any],
        preferred_source_ids: set[str],
    ) -> list[dict[str, Any]]:
        raw_sources = account_context.get("reference_source_briefs")
        if not isinstance(raw_sources, list):
            raw_sources = account_context.get("reference_sources") or []

        normalized: list[dict[str, Any]] = []
        for item in raw_sources:
            if not isinstance(item, dict):
                continue
            source_id = self._clean_text(item.get("source_id") or item.get("id"))
            source_name = self._clean_text(item.get("name") or item.get("source_name") or item.get("source_title"))
            source_title = self._clean_text(
                item.get("source_title") or item.get("resolved_title") or source_name
            ) or source_name or "Reference source"
            preview = self._clip_text(
                item.get("preview") or item.get("structure_brief") or item.get("snippet"),
                240,
            )
            notes = self._clip_text(
                item.get("notes") or item.get("style_clues") or item.get("style_brief"),
                180,
            )
            normalized.append(
                {
                    "source_id": source_id or source_title,
                    "source_type": self._clean_text(item.get("source_type")) or "reference",
                    "source_name": source_name or source_title,
                    "source_title": source_title,
                    "snippet": preview,
                    "preview": preview,
                    "notes": notes,
                    "style_hint": notes,
                    "structure_hint": preview or source_title,
                    "origin": "account_reference",
                    "is_preferred": source_id in preferred_source_ids if source_id else False,
                    "fit_score": 0.72 if source_id in preferred_source_ids else 0.58,
                }
            )
        return normalized

    def _normalize_source_candidates(
        self,
        source_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(source_candidates):
            if not isinstance(item, dict):
                continue
            source_title = self._clean_text(item.get("source_title") or item.get("title"))
            if not source_title:
                continue
            snippet = self._clip_text(item.get("snippet") or item.get("summary") or source_title, 220)
            normalized.append(
                {
                    "source_id": self._clean_text(item.get("source_id")) or f"candidate:{index + 1}",
                    "source_type": self._clean_text(item.get("source_type")) or "search_result",
                    "source_name": self._clean_text(item.get("source_name") or item.get("source")) or "Search result",
                    "source_title": source_title,
                    "snippet": snippet,
                    "preview": snippet,
                    "notes": self._clean_text(item.get("why_selected")),
                    "style_hint": self._clean_text(item.get("style_brief")),
                    "structure_hint": self._clean_text(item.get("structure_brief")) or snippet,
                    "origin": self._clean_text(item.get("origin")) or "source_scout",
                    "is_preferred": False,
                    "fit_score": float(item.get("fit_score") or 0.55),
                }
            )
        return normalized

    def _select_balanced_sources(
        self,
        *,
        account_sources: list[dict[str, Any]],
        scout_sources: list[dict[str, Any]],
        match_tokens: list[str],
        preferred_source_ids: set[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        ranked_account = sorted(
            account_sources,
            key=lambda item: (
                0 if item.get("source_id") in preferred_source_ids else 1,
                -self._topic_overlap(item.get("preview"), match_tokens),
                self._clean_text(item.get("source_name")),
            ),
        )
        ranked_scout = sorted(
            scout_sources,
            key=lambda item: (
                -float(item.get("fit_score") or 0.0),
                -self._topic_overlap(item.get("preview"), match_tokens),
                self._clean_text(item.get("source_name")),
            ),
        )

        selected: list[dict[str, Any]] = []
        account_quota = min(len(ranked_account), 2 if ranked_scout else limit)
        scout_quota = min(len(ranked_scout), 2 if ranked_account else limit)

        selected.extend(ranked_account[:account_quota])
        selected.extend(ranked_scout[:scout_quota])

        remainder = ranked_account[account_quota:] + ranked_scout[scout_quota:]
        remainder.sort(
            key=lambda item: (
                0 if item.get("source_id") in preferred_source_ids else 1,
                -float(item.get("fit_score") or 0.0),
                -self._topic_overlap(item.get("preview"), match_tokens),
            )
        )
        for item in remainder:
            if len(selected) >= limit:
                break
            selected.append(item)
        return selected[:limit]

    def _build_source_digest(
        self,
        source: dict[str, Any],
        match_tokens: list[str],
    ) -> dict[str, Any]:
        source_title = self._clean_text(source.get("source_title"))
        preview = self._clip_text(source.get("preview") or source.get("snippet"), 220)
        notes = self._clip_text(source.get("notes") or source.get("style_hint"), 180)
        origin = self._clean_text(source.get("origin"))
        source_name = self._clean_text(source.get("source_name")) or source_title

        if notes:
            style_brief = notes
        elif origin == "account_reference":
            style_brief = f"{source_name} can calibrate the account voice with a sharper hook and more grounded phrasing."
        else:
            style_brief = f"{source_name} is better used as timely texture and angle pressure than as a prose template."

        structure_brief = (
            self._clean_text(source.get("structure_hint"))
            or preview
            or source_title
        )
        useful_points = self._extract_useful_points(
            source_title=source_title,
            preview=preview,
            notes=notes,
            match_tokens=match_tokens,
        )

        return {
            "source_id": self._clean_text(source.get("source_id")),
            "source_type": self._clean_text(source.get("source_type")) or "reference",
            "source_name": source_name,
            "source_title": source_title,
            "style_brief": style_brief,
            "structure_brief": structure_brief,
            "useful_points": useful_points,
            "snippet": preview,
            "origin": origin or None,
            "fit_score": round(float(source.get("fit_score") or 0.0), 3),
        }

    def _extract_useful_points(
        self,
        *,
        source_title: str,
        preview: str,
        notes: str,
        match_tokens: list[str],
    ) -> list[str]:
        candidates: list[str] = []
        candidates.extend(self._split_fragments(notes))
        candidates.extend(self._split_fragments(preview))
        if source_title:
            candidates.append(source_title)

        prioritized: list[str] = []
        for item in candidates:
            clean = self._clip_text(item, 120)
            if not clean:
                continue
            if match_tokens and self._topic_overlap(clean, match_tokens) > 0:
                prioritized.append(clean)

        merged = prioritized + candidates
        return self._dedupe([self._clip_text(item, 120) for item in merged if self._clean_text(item)])[:3]

    def _build_digest_summary(
        self,
        *,
        account_source_count: int,
        scout_source_count: int,
        preferred_names: list[str | None],
    ) -> str:
        names = [self._clean_text(item) for item in preferred_names if self._clean_text(item)]
        if account_source_count and scout_source_count:
            return (
                f"Blend {account_source_count} account reference(s) for voice calibration and "
                f"{scout_source_count} scout source(s) for timely angle support."
            )
        if account_source_count:
            joined = ", ".join(names[:2]) if names else "account references"
            return f"Use {joined} to calibrate voice, pacing, and close-form decisions."
        if scout_source_count:
            joined = ", ".join(names[:2]) if names else "scout sources"
            return f"Use {joined} to keep the selected topic grounded in timely source texture."
        return "No strong reference sources were available, so rely on the account voice and topic accuracy."

    def _build_candidate_reason(
        self,
        *,
        source_name: str,
        source_type: str,
        snippet: str,
        query_tokens: list[str],
    ) -> str:
        overlap = self._topic_overlap(snippet, query_tokens)
        if overlap > 1:
            return f"{source_name} matches multiple query signals and can provide a sharper factual angle."
        if source_type in {"weixin", "wechat_account"}:
            return f"{source_name} is likely to mirror public-account framing and reader expectations."
        return f"{source_name} adds another angle to validate whether the topic is worth writing."

    def _estimate_fit(
        self,
        *,
        text: str,
        match_tokens: list[str],
        source_preferences: list[str],
        source_name: str,
        source_type: str,
    ) -> float:
        score = 0.35
        overlap = self._topic_overlap(text, match_tokens)
        score += min(overlap * 0.12, 0.36)

        lower_name = source_name.lower()
        lower_text = text.lower()
        if any(pref.lower() in lower_name or pref.lower() in lower_text for pref in source_preferences):
            score += 0.12
        if source_type in {"weixin", "article_url", "search_result"}:
            score += 0.08
        return max(0.0, min(score, 0.98))

    def _topic_overlap(self, text: Any, match_tokens: list[str]) -> int:
        haystack = self._clean_text(text).lower()
        if not haystack or not match_tokens:
            return 0
        return sum(1 for token in match_tokens if token and token.lower() in haystack)

    def _build_match_tokens(self, *values: Any) -> list[str]:
        tokens: list[str] = []
        for value in values:
            if isinstance(value, list):
                for item in value:
                    tokens.extend(self._tokenize(self._clean_text(item)))
            else:
                tokens.extend(self._tokenize(self._clean_text(value)))
        return self._dedupe(tokens)[:12]

    def _tokenize(self, text: str) -> list[str]:
        raw = self._clean_text(text)
        if not raw:
            return []
        tokens = re.split(r"[\s,，。！？、:：;；/\\\\\\-]+", raw)
        normalized: list[str] = []
        for token in tokens:
            clean = self._clean_text(token)
            if len(clean) >= 2:
                normalized.append(clean)
        return normalized

    def _split_fragments(self, text: Any) -> list[str]:
        raw = self._clean_text(text)
        if not raw:
            return []
        return [
            fragment.strip()
            for fragment in re.split(r"[。！？!?；;]\\s*", raw)
            if fragment.strip()
        ]

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [self._clean_text(item) for item in value if self._clean_text(item)]

    def _dedupe(self, values: list[Any]) -> list[str]:
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

    def _clip_text(self, value: Any, limit: int) -> str:
        text = self._clean_text(value)
        if len(text) <= limit:
            return text
        return f"{text[: max(limit - 3, 0)].rstrip()}..."

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


reference_digest_service = ReferenceDigestService()
