"""Ranking helpers for GitHub repository curation."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any


def _tokenize(text: str) -> list[str]:
    return [item for item in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", text.lower()) if len(item) >= 2]


class RepoRanker:
    """Rank and bucket GitHub repositories using multiple signals."""

    CATEGORY_KEYWORDS = {
        "framework": ["framework", "sdk", "library", "agent", "model"],
        "application": ["app", "application", "assistant", "copilot", "ui", "studio"],
        "infrastructure": ["infra", "deployment", "orchestration", "server", "runtime", "pipeline"],
        "dataset": ["dataset", "data", "corpus"],
        "evaluation": ["benchmark", "eval", "evaluation", "leaderboard"],
        "curated_list": ["awesome", "curated", "list", "resources"],
    }

    def rank(self, *, topic: str, repos: list[dict[str, Any]], max_results: int) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        topic_tokens = _tokenize(topic)
        scored = [self._score_repo(topic_tokens, repo) for repo in repos]
        scored.sort(key=lambda item: item["score_breakdown"]["overall"], reverse=True)
        selected = scored[:max_results]
        buckets: dict[str, list[dict[str, Any]]] = {}
        for item in selected:
            buckets.setdefault(item["category"], []).append(
                {
                    "full_name": item["full_name"],
                    "url": item["url"],
                    "why_selected": item["why_selected"],
                }
            )
        return selected, buckets

    def _score_repo(self, topic_tokens: list[str], repo: dict[str, Any]) -> dict[str, Any]:
        full_name = str(repo.get("full_name") or "").strip()
        repo_name = str(repo.get("name") or full_name.split("/")[-1]).strip()
        description = str(repo.get("description") or "").strip()
        topics = [str(item).strip() for item in repo.get("topics") or [] if str(item).strip()]
        readme_text = str(repo.get("_readme_text") or "")
        text_blob = " ".join([full_name, description, " ".join(topics), readme_text]).lower()
        category = self._categorize(repo_name, description, topics)

        relevance = min(1.0, 0.2 + 0.18 * sum(1 for token in topic_tokens if token in text_blob))
        popularity = min(
            1.0,
            (math.log10((repo.get("stargazers_count") or 0) + 1) + 0.6 * math.log10((repo.get("forks_count") or 0) + 1)) / 6,
        )
        maintenance = self._maintenance_score(repo.get("pushed_at"), bool(repo.get("archived")))
        engineering = 0.25
        if repo.get("license"):
            engineering += 0.15
        if topics:
            engineering += min(0.18, len(topics) * 0.03)
        if repo.get("homepage"):
            engineering += 0.08
        if repo.get("has_issues"):
            engineering += 0.06
        if "test" in readme_text.lower() or "ci" in readme_text.lower():
            engineering += 0.12
        engineering = min(engineering, 1.0)

        docs = 0.18
        if len(readme_text) > 800:
            docs += 0.28
        if any(keyword in readme_text.lower() for keyword in ("install", "usage", "quickstart", "getting started", "example")):
            docs += 0.24
        if repo.get("homepage"):
            docs += 0.1
        docs = min(docs, 1.0)

        novelty = 0.35
        if maintenance > 0.8 and popularity > 0.45:
            novelty += 0.3
        if category == "curated_list":
            novelty -= 0.15
        novelty = max(0.0, min(novelty, 1.0))

        overall = (
            relevance * 0.28
            + popularity * 0.18
            + maintenance * 0.18
            + engineering * 0.16
            + docs * 0.1
            + novelty * 0.1
        )
        if category == "curated_list":
            overall -= 0.08

        risk_flags: list[str] = []
        if repo.get("archived"):
            risk_flags.append("archived")
        if maintenance < 0.45:
            risk_flags.append("stale")
        if not repo.get("license"):
            risk_flags.append("no_license")
        if docs < 0.4:
            risk_flags.append("docs_thin")
        if category == "curated_list":
            risk_flags.append("curated_list_lower_priority")

        return {
            "full_name": full_name,
            "repo_name": repo_name,
            "owner": full_name.split("/")[0] if "/" in full_name else "",
            "url": str(repo.get("html_url") or ""),
            "description": description or None,
            "primary_language": repo.get("language"),
            "stars": int(repo.get("stargazers_count") or 0),
            "forks": int(repo.get("forks_count") or 0),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
            "license": ((repo.get("license") or {}) if isinstance(repo.get("license"), dict) else {}).get("spdx_id"),
            "topics": topics,
            "category": category,
            "why_selected": self._why_selected(category, relevance, maintenance, engineering),
            "best_for": self._best_for(category),
            "score_breakdown": {
                "topic_relevance": round(relevance, 4),
                "popularity": round(popularity, 4),
                "maintenance": round(maintenance, 4),
                "engineering_quality": round(engineering, 4),
                "docs_quality": round(docs, 4),
                "signal_novelty": round(novelty, 4),
                "overall": round(max(overall, 0.0), 4),
            },
            "risk_flags": risk_flags,
        }

    def _categorize(self, repo_name: str, description: str, topics: list[str]) -> str:
        haystack = " ".join([repo_name, description, " ".join(topics)]).lower()
        curated_keywords = self.CATEGORY_KEYWORDS["curated_list"]
        if any(keyword in haystack for keyword in curated_keywords):
            return "curated_list"
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if category == "curated_list":
                continue
            if any(keyword in haystack for keyword in keywords):
                return category
        return "application"

    def _maintenance_score(self, pushed_at: Any, archived: bool) -> float:
        if archived:
            return 0.0
        if not pushed_at:
            return 0.3
        try:
            parsed = datetime.fromisoformat(str(pushed_at).replace("Z", "+00:00"))
        except ValueError:
            return 0.3
        days = max((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days, 0)
        if days <= 30:
            return 1.0
        if days <= 90:
            return 0.85
        if days <= 180:
            return 0.7
        if days <= 365:
            return 0.55
        return 0.35

    def _why_selected(self, category: str, relevance: float, maintenance: float, engineering: float) -> str:
        return (
            f"Selected as a {category} signal because it stays relevant ({relevance:.2f}) "
            f"while still showing usable maintenance ({maintenance:.2f}) and engineering quality ({engineering:.2f})."
        )

    def _best_for(self, category: str) -> str:
        mapping = {
            "framework": "engineers evaluating reusable building blocks",
            "application": "teams looking for end-user product patterns",
            "infrastructure": "platform or DevOps teams",
            "dataset": "teams needing data assets or corpora",
            "evaluation": "teams comparing methods or model quality",
            "curated_list": "broad discovery before deeper technical evaluation",
        }
        return mapping.get(category, "engineers scouting credible open-source signals")


repo_ranker = RepoRanker()
