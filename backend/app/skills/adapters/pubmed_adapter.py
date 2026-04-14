"""Real PubMed adapter for biomedical paper discovery."""

from __future__ import annotations

import os
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from app.core.config import settings
from app.core.exceptions import ConfigError, ExternalAPIError
from app.core.logger import get_logger
from app.skills.adapters.scholar_provider_config import provider_includes

logger = get_logger(__name__)


def _get_proxy_url() -> str | None:
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if http_proxy:
        return http_proxy
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return https_proxy


class PubmedAdapter:
    """PubMed client using esearch + efetch."""

    def __init__(self) -> None:
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.timeout = settings.scholar_skill_timeout_seconds

    def validate_config(self) -> None:
        if not settings.enable_scholar_skill:
            raise ConfigError("Scholar skill is disabled. Set ENABLE_SCHOLAR_SKILL=1 to enable it.")
        if not provider_includes(settings.scholar_provider, "pubmed"):
            raise ConfigError("PubMed adapter requires SCHOLAR_PROVIDER to include pubmed.")

    async def search_papers(
        self,
        *,
        topic: str,
        year_from: int | None,
        year_to: int | None,
        max_results: int,
        must_have: list[str] | None,
        exclude_terms: list[str] | None,
    ) -> dict[str, Any]:
        self.validate_config()
        pmids = await self._search_ids(
            topic=self._build_search(topic, must_have, exclude_terms),
            year_from=year_from,
            year_to=year_to,
            max_results=max_results,
        )
        if not pmids:
            return {"results": []}
        return {"results": await self._fetch_records(pmids)}

    async def _search_ids(
        self,
        *,
        topic: str,
        year_from: int | None,
        year_to: int | None,
        max_results: int,
    ) -> list[str]:
        params = {
            "db": "pubmed",
            "term": topic,
            "retmax": min(max(max_results * 3, 10), 30),
            "retmode": "json",
        }
        if year_from:
            params["mindate"] = f"{year_from}/01/01"
        if year_to:
            params["maxdate"] = f"{year_to}/12/31"
        if year_from or year_to:
            params["datetype"] = "pdat"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=_get_proxy_url(), trust_env=False) as client:
                response = await client.get(f"{self.base_url}/esearch.fcgi", params=params)
        except httpx.TimeoutException as exc:
            raise ExternalAPIError("PubMed search timed out", details={"path": "/esearch.fcgi"}) from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError("PubMed search failed", details={"path": "/esearch.fcgi"}) from exc
        if response.status_code >= 400:
            raise ExternalAPIError(
                "PubMed search failed",
                details={"status_code": response.status_code, "body": response.text[:300]},
            )
        payload = response.json()
        return [str(item).strip() for item in ((payload.get("esearchresult") or {}).get("idlist") or []) if str(item).strip()]

    async def _fetch_records(self, pmids: list[str]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=_get_proxy_url(), trust_env=False) as client:
                response = await client.get(
                    f"{self.base_url}/efetch.fcgi",
                    params={
                        "db": "pubmed",
                        "id": ",".join(pmids),
                        "retmode": "xml",
                        "rettype": "abstract",
                    },
                )
        except httpx.TimeoutException as exc:
            raise ExternalAPIError("PubMed fetch timed out", details={"path": "/efetch.fcgi"}) from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError("PubMed fetch failed", details={"path": "/efetch.fcgi"}) from exc
        if response.status_code >= 400:
            raise ExternalAPIError(
                "PubMed fetch failed",
                details={"status_code": response.status_code, "body": response.text[:300]},
            )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ExternalAPIError("PubMed XML parse failed", details={"error": str(exc)}) from exc

        results: list[dict[str, Any]] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = self._node_text(article, ".//PMID")
            title = self._iter_text(article.find(".//ArticleTitle"))
            abstract_parts: list[str] = []
            for node in article.findall(".//AbstractText"):
                label = str(node.attrib.get("Label") or "").strip()
                text = self._iter_text(node)
                if not text:
                    continue
                abstract_parts.append(f"{label}: {text}" if label else text)
            year = self._extract_year(article)
            authors: list[str] = []
            for author in article.findall(".//Author"):
                last = self._node_text(author, "LastName")
                first = self._node_text(author, "ForeName")
                name = " ".join(part for part in [first, last] if part)
                if name:
                    authors.append(name)
            venue = self._node_text(article, ".//Journal/Title")
            doi = None
            for node in article.findall(".//ArticleId"):
                if str(node.attrib.get("IdType") or "").lower() == "doi":
                    doi = (node.text or "").strip()
                    break
            results.append(
                {
                    "id": pmid,
                    "pmid": pmid,
                    "doi": doi,
                    "title": title,
                    "year": year,
                    "authors": authors,
                    "abstract": " ".join(abstract_parts).strip() or None,
                    "venue": venue,
                    "source": "pubmed",
                }
            )
        return results

    def _build_search(
        self,
        topic: str,
        must_have: list[str] | None,
        exclude_terms: list[str] | None,
    ) -> str:
        parts = [topic.strip()]
        parts.extend(item.strip() for item in must_have or [] if item.strip())
        parts.extend(f"NOT {item.strip()}" for item in exclude_terms or [] if item.strip())
        return " ".join(part for part in parts if part)

    def _extract_year(self, article: ET.Element) -> int | None:
        for path in (".//PubDate/Year", ".//ArticleDate/Year"):
            value = self._node_text(article, path)
            if value and value.isdigit():
                return int(value)
        medline_date = self._node_text(article, ".//PubDate/MedlineDate")
        if medline_date:
            year = medline_date.split(" ", 1)[0]
            if year.isdigit():
                return int(year)
        return None

    def _node_text(self, node: ET.Element, path: str) -> str | None:
        child = node.find(path)
        if child is None or child.text is None:
            return None
        return child.text.strip()

    def _iter_text(self, node: ET.Element | None) -> str | None:
        if node is None:
            return None
        text = "".join(node.itertext()).strip()
        return text or None


pubmed_adapter = PubmedAdapter()
