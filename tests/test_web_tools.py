from __future__ import annotations

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


def test_browser_reader_url_strips_protocol_prefix() -> None:
    tool = BrowserTool(detail_provider="reader", reader_base_url="https://r.jina.ai/http://")

    assert tool._build_reader_url("https://example.com/path") == "https://r.jina.ai/http://example.com/path"