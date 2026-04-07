"""Search tool for provider-aware web search result pages."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import re
from urllib.parse import parse_qs, urlparse

import httpx

from swarmmind.config import get_settings


@dataclass(slots=True)
class SearchResultItem:
    title: str
    url: str
    snippet: str
    source: str
    rank: int


@dataclass(slots=True)
class SearchResponse:
    provider: str
    query: str
    items: list[SearchResultItem]


class SearchTool:
    """Tool for list-page web search across multiple providers."""

    def __init__(
        self,
        provider: str = "duckduckgo",
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        default_max_results: int = 5,
        google_cse_id: str | None = None,
        market: str = "en-US",
        safe_search: str = "moderate",
    ):
        self._provider = provider.strip().lower()
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._default_max_results = default_max_results
        self._google_cse_id = google_cse_id
        self._market = market
        self._safe_search = safe_search

    @classmethod
    def from_settings(cls, provider: str | None = None) -> "SearchTool":
        settings = get_settings()
        config = settings.search
        return cls(
            provider=provider or config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            default_max_results=config.default_max_results,
            google_cse_id=config.google_cse_id,
            market=config.market,
            safe_search=config.safe_search,
        )

    async def search(self, query: str, max_results: int = 5) -> str:
        normalized_max_results = max_results or self._default_max_results
        try:
            response = await self.search_results(query, normalized_max_results)
        except Exception as exc:
            return f"Search error [{self._provider}]: {exc}"
        if not response.items:
            return f"Search provider: {response.provider}\nQuery: {query}\nNo results found"
        return self._format_results(response)

    async def search_results(self, query: str, max_results: int) -> SearchResponse:
        async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
            if self._provider in {"duckduckgo", "ddg"}:
                items = await self._search_duckduckgo(client, query, max_results)
                return SearchResponse(provider="duckduckgo", query=query, items=items)
            if self._provider == "brave":
                items = await self._search_brave(client, query, max_results)
                return SearchResponse(provider="brave", query=query, items=items)
            if self._provider == "tavily":
                items = await self._search_tavily(client, query, max_results)
                return SearchResponse(provider="tavily", query=query, items=items)
            if self._provider == "serpapi":
                items = await self._search_serpapi(client, query, max_results)
                return SearchResponse(provider="serpapi", query=query, items=items)
            if self._provider == "bing":
                items = await self._search_bing(client, query, max_results)
                return SearchResponse(provider="bing", query=query, items=items)
            if self._provider in {"google", "google_cse"}:
                items = await self._search_google_cse(client, query, max_results)
                return SearchResponse(provider="google_cse", query=query, items=items)
        raise ValueError(f"Unsupported search provider: {self._provider}")

    async def _search_duckduckgo(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[SearchResultItem]:
        response = await client.get(self._base_url or "https://html.duckduckgo.com/html/", params={"q": query})
        response.raise_for_status()
        return self._parse_duckduckgo_html(response.text, max_results)

    async def _search_brave(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[SearchResultItem]:
        self._require_api_key("brave")
        response = await client.get(
            self._base_url or "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results, "country": self._market.split("-")[-1]},
            headers={"X-Subscription-Token": self._api_key or ""},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("web", {}).get("results", []) if isinstance(payload, dict) else []
        return [
            SearchResultItem(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("description") or ""),
                source="brave",
                rank=index,
            )
            for index, item in enumerate(items[:max_results], start=1)
        ]

    async def _search_tavily(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[SearchResultItem]:
        self._require_api_key("tavily")
        response = await client.post(
            self._base_url or "https://api.tavily.com/search",
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("results", []) if isinstance(payload, dict) else []
        return [
            SearchResultItem(
                title=str(item.get("title") or item.get("url") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or item.get("snippet") or ""),
                source="tavily",
                rank=index,
            )
            for index, item in enumerate(items[:max_results], start=1)
        ]

    async def _search_serpapi(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[SearchResultItem]:
        self._require_api_key("serpapi")
        response = await client.get(
            self._base_url or "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": self._api_key, "num": max_results},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("organic_results", []) if isinstance(payload, dict) else []
        return [
            SearchResultItem(
                title=str(item.get("title") or ""),
                url=str(item.get("link") or ""),
                snippet=str(item.get("snippet") or ""),
                source="serpapi",
                rank=index,
            )
            for index, item in enumerate(items[:max_results], start=1)
        ]

    async def _search_bing(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[SearchResultItem]:
        self._require_api_key("bing")
        response = await client.get(
            self._base_url or "https://api.bing.microsoft.com/v7.0/search",
            params={"q": query, "count": max_results, "mkt": self._market, "safeSearch": self._safe_search},
            headers={"Ocp-Apim-Subscription-Key": self._api_key or ""},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("webPages", {}).get("value", []) if isinstance(payload, dict) else []
        return [
            SearchResultItem(
                title=str(item.get("name") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("snippet") or ""),
                source="bing",
                rank=index,
            )
            for index, item in enumerate(items[:max_results], start=1)
        ]

    async def _search_google_cse(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[SearchResultItem]:
        self._require_api_key("google_cse")
        if not self._google_cse_id:
            raise ValueError("Google Custom Search requires google_cse_id")
        response = await client.get(
            self._base_url or "https://www.googleapis.com/customsearch/v1",
            params={"q": query, "num": max_results, "key": self._api_key, "cx": self._google_cse_id},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [
            SearchResultItem(
                title=str(item.get("title") or ""),
                url=str(item.get("link") or ""),
                snippet=str(item.get("snippet") or ""),
                source="google_cse",
                rank=index,
            )
            for index, item in enumerate(items[:max_results], start=1)
        ]

    def _parse_duckduckgo_html(self, html: str, max_results: int) -> list[SearchResultItem]:
        result_pattern = re.compile(r'<a class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', flags=re.DOTALL)
        snippet_pattern = re.compile(
            r'<(?:a|div) class="result__snippet"[^>]*>(.*?)</(?:a|div)>',
            flags=re.DOTALL,
        )
        snippets = [self._strip_tags(match.group(1)) for match in snippet_pattern.finditer(html)]
        items: list[SearchResultItem] = []
        for index, match in enumerate(result_pattern.finditer(html), start=1):
            items.append(
                SearchResultItem(
                    title=self._strip_tags(match.group(2)),
                    url=self._normalize_duckduckgo_url(match.group(1)),
                    snippet=snippets[index - 1] if index - 1 < len(snippets) else "",
                    source="duckduckgo",
                    rank=index,
                )
            )
            if len(items) >= max_results:
                break
        return items

    @staticmethod
    def _normalize_duckduckgo_url(url: str) -> str:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if "uddg" in query_params and query_params["uddg"]:
            return query_params["uddg"][0]
        return unescape(url)

    @staticmethod
    def _strip_tags(value: str) -> str:
        text = re.sub(r"<[^>]+>", "", value)
        return re.sub(r"\s+", " ", unescape(text)).strip()

    def _require_api_key(self, provider: str) -> None:
        if not self._api_key:
            raise ValueError(f"Search provider '{provider}' requires an api_key")

    @staticmethod
    def _format_results(response: SearchResponse) -> str:
        payload = {
            "provider": response.provider,
            "query": response.query,
            "results": [
                {
                    "rank": item.rank,
                    "title": item.title,
                    "url": item.url,
                    "snippet": item.snippet,
                    "source": item.source,
                }
                for item in response.items
            ],
        }
        lines = [f"Search provider: {response.provider}", f"Query: {response.query}", "Results:"]
        for item in response.items:
            lines.append(f"{item.rank}. {item.title}")
            lines.append(f"   URL: {item.url}")
            if item.snippet:
                lines.append(f"   Snippet: {item.snippet[:240]}")
        lines.append("")
        lines.append("Structured payload:")
        lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
        return "\n".join(lines)


async def search(query: str, max_results: int = 5, provider: str | None = None) -> str:
    """Search the web for result-page items.

    Args:
        query: Search query
        max_results: Maximum number of results
        provider: Optional provider override

    Returns:
        Human-readable results plus a structured JSON payload
    """
    tool = SearchTool.from_settings(provider=provider)
    return await tool.search(query, max_results)
