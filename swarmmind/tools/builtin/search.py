"""Search tool for web search."""

import httpx


class SearchTool:
    """Tool for web search."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    async def search(self, query: str, max_results: int = 5) -> str:
        """Search the web.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            Search results as formatted string
        """
        # Simple search using DuckDuckGo (no API key required)
        # In production, use Google/Bing API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    timeout=10.0,
                )

            if response.status_code != 200:
                return f"Search failed: {response.status_code}"

            # Parse results (simplified)
            results = self._parse_results(response.text)
            if not results:
                return "No results found"

            output = f"Search results for '{query}':\n\n"
            for i, (title, url, snippet) in enumerate(results[:max_results], 1):
                output += f"{i}. {title}\n"
                output += f"   {url}\n"
                output += f"   {snippet[:200]}...\n\n"

            return output

        except Exception as e:
            return f"Search error: {str(e)}"

    def _parse_results(self, html: str) -> list[tuple[str, str, str]]:
        """Parse search results from HTML."""
        import re

        results = []
        # Simple regex-based parsing
        pattern = r'<a class="result__a" href="([^"]+)"[^>]*>(.+?)</a>'
        snippet_pattern = r'<a class="result__snippet"[^>]*>(.+?)</a>'

        matches = re.findall(pattern, html)
        snippet_matches = re.findall(snippet_pattern, html)

        for i, (url, title) in enumerate(matches[:10]):
            title = re.sub(r'<[^>]+>', '', title)
            snippet = snippet_matches[i] if i < len(snippet_matches) else ""
            snippet = re.sub(r'<[^>]+>', '', snippet)
            results.append((title, url, snippet))

        return results


# Tool function for AgentScope
async def search(query: str, max_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: Search query
        max_results: Maximum number of results (default 5)

    Returns:
        Search results with titles, URLs, and snippets
    """
    tool = SearchTool()
    return await tool.search(query, max_results)
