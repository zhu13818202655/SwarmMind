"""Browser/detail tool for provider-aware page fetching and article extraction."""

from __future__ import annotations

from html import unescape
import re

import httpx

from swarmmind.config import get_settings


class BrowserTool:
    """Tool for detail-page retrieval and content extraction."""

    def __init__(
        self,
        detail_provider: str = "direct",
        reader_base_url: str = "https://r.jina.ai/http://",
        timeout_seconds: float = 30.0,
        user_agent: str = "SwarmMindBrowser/1.0",
    ):
        self._detail_provider = detail_provider.strip().lower()
        self._reader_base_url = reader_base_url
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    @classmethod
    def from_settings(cls, detail_provider: str | None = None) -> "BrowserTool":
        settings = get_settings()
        config = settings.browser
        return cls(
            detail_provider=detail_provider or config.detail_provider,
            reader_base_url=config.reader_base_url,
            timeout_seconds=config.timeout_seconds,
            user_agent=config.user_agent,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get(self, url: str) -> str:
        """Get detail-page content using the configured extraction provider."""
        try:
            if self._detail_provider in {"reader", "jina", "jina_reader"}:
                return await self._get_via_reader(url)
            return await self._get_direct(url)
        except Exception as exc:
            return f"Error fetching {url}: {exc}"

    async def screenshot(self, url: str) -> str:
        """Take a screenshot of a page."""
        return f"Screenshot not implemented for {url}. Use browser_get for detail retrieval."

    async def _get_direct(self, url: str) -> str:
        response = await self._client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type:
            return response.text[:10000]
        return self._extract_document(response.text, url)

    async def _get_via_reader(self, url: str) -> str:
        response = await self._client.get(self._build_reader_url(url))
        response.raise_for_status()
        return response.text[:15000]

    def _build_reader_url(self, url: str) -> str:
        normalized = re.sub(r"^https?://", "", url.strip())
        return f"{self._reader_base_url}{normalized}"

    def _extract_document(self, html: str, url: str) -> str:
        title = self._extract_title(html)
        description = self._extract_meta_description(html)
        body = self._extract_text(html)
        lines = [f"URL: {url}"]
        if title:
            lines.append(f"Title: {title}")
        if description:
            lines.append(f"Description: {description}")
        lines.append("Content:")
        lines.append(body)
        return "\n".join(lines)

    @staticmethod
    def _extract_title(html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        return BrowserTool._clean_text(match.group(1)) if match else ""

    @staticmethod
    def _extract_meta_description(html: str) -> str:
        patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return BrowserTool._clean_text(match.group(1))
        return ""

    def _extract_text(self, html: str) -> str:
        focused_html = self._focus_main_content(html)
        cleaned = re.sub(r"<script[^>]*>.*?</script>", "", focused_html, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"</?(article|section|main|div|p|br|li|ul|ol|h[1-6])[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        lines = [self._clean_text(line) for line in cleaned.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines[:240])

    @staticmethod
    def _focus_main_content(html: str) -> str:
        for tag in ["article", "main", "body"]:
            match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)
        return html

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", unescape(value)).strip()


async def browser_get(url: str, detail_provider: str | None = None) -> str:
    """Fetch a detail page and extract its main content.

    Args:
        url: The URL to fetch
        detail_provider: Optional detail provider override

    Returns:
        Extracted article/detail content
    """
    tool = BrowserTool.from_settings(detail_provider=detail_provider)
    try:
        return await tool.get(url)
    finally:
        await tool.close()


async def browser_screenshot(url: str) -> str:
    """Take a screenshot of a web page.

    Args:
        url: The URL to screenshot

    Returns:
        Status message
    """
    tool = BrowserTool.from_settings()
    try:
        return await tool.screenshot(url)
    finally:
        await tool.close()
