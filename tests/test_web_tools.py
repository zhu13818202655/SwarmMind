from __future__ import annotations

import httpx
import pytest

from swarmmind.tools.builtin.browser import BrowserTool
from swarmmind.tools.builtin.search import SearchTool


def test_duckduckgo_parser_normalizes_redirect_links() -> None:
    html = """
    <html>
      <body>
        <div class=\"result\">
          <a class=\"result__a\" href=\"//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle\">Example Result</a>
          <a class=\"result__snippet\">A concise summary.</a>
        </div>
      </body>
    </html>
    """

    items = SearchTool()._parse_duckduckgo_html(html, max_results=5)

    assert len(items) == 1
    assert items[0].title == "Example Result"
    assert items[0].url == "https://example.com/article"
    assert items[0].snippet == "A concise summary."


def test_browser_extract_document_prefers_main_content() -> None:
    html = """
    <html>
      <head>
        <title>Article Title</title>
        <meta name=\"description\" content=\"Page summary\" />
      </head>
      <body>
        <nav>Navigation</nav>
        <main>
          <h1>Article Title</h1>
          <p>First paragraph.</p>
          <p>Second paragraph.</p>
        </main>
      </body>
    </html>
    """

    content = BrowserTool()._extract_document(html, "https://example.com/article")

    assert "URL: https://example.com/article" in content
    assert "Title: Article Title" in content
    assert "Description: Page summary" in content
    assert "First paragraph." in content
    assert "Second paragraph." in content


@pytest.mark.asyncio
async def test_browser_reader_falls_back_to_direct_on_reader_failure(monkeypatch) -> None:
    tool = BrowserTool(detail_provider="reader", reader_base_url="https://r.jina.ai/http://")

    async def fake_reader(url: str) -> str:
        raise httpx.HTTPError("reader unavailable")

    async def fake_direct(url: str) -> str:
        return f"direct:{url}"

    monkeypatch.setattr(tool, "_get_via_reader", fake_reader)
    monkeypatch.setattr(tool, "_get_direct", fake_direct)

    try:
        assert await tool.get("https://example.com") == "direct:https://example.com"
    finally:
        await tool.close()
