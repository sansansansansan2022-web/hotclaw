"""Ranking helpers for scholar paper selection."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any


def _tokenize(text: str) -> list[str]:
    return [item for item in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", text.lower()) if len(item) >= 2]


class PaperRanker:
    """Rank and deduplicate paper candidates with multiple quality signals."""

    TOP_VENUE_HINTS = (
        "neurips",
        "icml",
        "iclr",
        "cvpr",
        "eccv",
        "iccv",
        "acl",
        "emnlp",
        "naacl",
        "kdd",
        "sigir",
        "nature",
        "science",
    )

    def rank(self, *, topic: str, papers: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
        topic_tokens = _tokenize(topic)
        unique = self._deduplicate(papers)
        scored = [self._score_paper(topic_tokens, paper) for paper in unique]
        scored.sort(key=lambda item: item["score_breakdown"]["overall"], reverse=True)
        return scored[:max_results]

    def build_reading_path(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        reading_path: list[dict[str, Any]] = []
        if not papers:
            return reading_path
        first = papers[0]
        reading_path.append({"step": 1, "title": first["title"], "reason": "Start with the strongest anchor paper."})
        if len(papers) > 1:
            reading_path.append({"step": 2, "title": papers[1]["title"], "reason": "Then compare with a fresher or more practical follow-up."})
        if len(papers) > 2:
            reading_path.append({"step": 3, "title": papers[2]["title"], "reason": "Finish with a contrastive or limitation-aware read."})
        return reading_path

    def _deduplicate(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for paper in papers:
            doi = str(paper.get("doi") or "").strip().lower()
            title = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(paper.get("title") or "").lower())
            key = doi or title
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(paper)
        return deduped

    def _score_paper(self, topic_tokens: list[str], paper: dict[str, Any]) -> dict[str, Any]:
        title = str(paper.get("title") or "").strip()
        summary = str(paper.get("abstract_or_summary") or "").strip()
        venue = str(paper.get("venue") or "").strip()
        text_blob = " ".join([title, summary, venue]).lower()
        relevance = min(1.0, 0.22 + 0.18 * sum(1 for token in topic_tokens if token in text_blob))
        venue_quality = self._venue_quality(venue, paper.get("paper_type"))
        citation_quality = self._citation_quality(int(paper.get("citation_count") or 0), paper.get("year"))
        freshness = self._freshness(paper.get("year"))
        reproducibility = 0.3
        if paper.get("doi"):
            reproducibility += 0.15
        if summary:
            reproducibility += 0.2
        if paper.get("url"):
            reproducibility += 0.1
        reproducibility = min(reproducibility, 1.0)

        overall = (
            relevance * 0.3
            + venue_quality * 0.2
            + citation_quality * 0.18
            + freshness * 0.16
            + reproducibility * 0.16
        )

        risk_flags: list[str] = []
        if not summary:
            risk_flags.append("missing_abstract")
        if str(paper.get("paper_type") or "").lower() == "preprint":
            risk_flags.append("preprint_only")
        if not paper.get("doi"):
            risk_flags.append("missing_doi")

        return {
            **paper,
            "why_selected": (
                f"Selected because it stays relevant ({relevance:.2f}) while balancing venue quality "
                f"({venue_quality:.2f}) and reproducibility signal ({reproducibility:.2f})."
            ),
            "why_relevant": f"The paper directly overlaps with the topic framing around '{title}'.",
            "score_breakdown": {
                "relevance": round(relevance, 4),
                "venue_quality": round(venue_quality, 4),
                "citation_quality": round(citation_quality, 4),
                "freshness": round(freshness, 4),
                "reproducibility_signal": round(reproducibility, 4),
                "overall": round(overall, 4),
            },
            "risk_flags": risk_flags,
        }

    def _venue_quality(self, venue: str, paper_type: Any) -> float:
        lower = venue.lower()
        if any(token in lower for token in self.TOP_VENUE_HINTS):
            return 0.95
        if "journal" in lower or "proceedings" in lower:
            return 0.72
        if str(paper_type or "").lower() == "preprint":
            return 0.45
        return 0.58

    def _citation_quality(self, citations: int, year: Any) -> float:
        if citations <= 0:
            return 0.2
        age = max(datetime.now().year - int(year or datetime.now().year), 0) + 1
        return min(1.0, math.log10(citations / age + 1) / 2.3)

    def _freshness(self, year: Any) -> float:
        if not year:
            return 0.35
        age = max(datetime.now().year - int(year), 0)
        if age <= 1:
            return 1.0
        if age <= 2:
            return 0.85
        if age <= 4:
            return 0.68
        if age <= 6:
            return 0.52
        return 0.36


paper_ranker = PaperRanker()
