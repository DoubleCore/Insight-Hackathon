from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


@dataclass(slots=True)
class WebSearchHit:
    provider: str
    title: str
    url: str
    content: str = ""
    published_at: str | None = None
    score: float | None = None


class WebSearchService:
    def __init__(
        self, settings: Settings, client: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=20)
        self._owned_client = client is None

    async def close(self) -> None:
        if self._owned_client:
            await self.client.aclose()

    async def search(
        self,
        query: str,
        *,
        providers: list[str],
        max_results: int,
    ) -> list[WebSearchHit]:
        results: list[WebSearchHit] = []
        if "tavily" in providers and self.settings.tavily_api_key:
            results.extend(await self._search_tavily(query, max_results=max_results))
        if (
            "bocha" in providers
            and self.settings.bocha_api_key
            and self.settings.bocha_search_url
        ):
            results.extend(await self._search_bocha(query, max_results=max_results))
        return _dedupe_hits(results)[:max_results]

    async def _search_tavily(
        self, query: str, *, max_results: int
    ) -> list[WebSearchHit]:
        response = await self.client.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {self.settings.tavily_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return [
            WebSearchHit(
                provider="tavily",
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                content=str(item.get("content") or ""),
                score=float(item["score"]) if item.get("score") is not None else None,
            )
            for item in payload.get("results", [])
            if isinstance(item, dict) and item.get("url")
        ]

    async def _search_bocha(
        self, query: str, *, max_results: int
    ) -> list[WebSearchHit]:
        response = await self.client.post(
            self.settings.bocha_search_url,
            headers={
                "Authorization": f"Bearer {self.settings.bocha_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "count": max_results,
            },
        )
        response.raise_for_status()
        payload = response.json()
        raw_items: Any = payload.get("data", {}).get("webPages", {}).get("value", [])
        if not isinstance(raw_items, list):
            raw_items = payload.get("results", [])
        return [
            WebSearchHit(
                provider="bocha",
                title=str(item.get("name") or item.get("title") or ""),
                url=str(item.get("url") or ""),
                content=str(
                    item.get("snippet")
                    or item.get("summary")
                    or item.get("content")
                    or ""
                ),
                published_at=item.get("datePublished") or item.get("published_at"),
            )
            for item in raw_items
            if isinstance(item, dict) and item.get("url")
        ]


def _dedupe_hits(hits: list[WebSearchHit]) -> list[WebSearchHit]:
    seen: set[str] = set()
    deduped: list[WebSearchHit] = []
    for hit in hits:
        if hit.url in seen:
            continue
        seen.add(hit.url)
        deduped.append(hit)
    return deduped
