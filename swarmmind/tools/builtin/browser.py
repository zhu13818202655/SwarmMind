"""Browser tool for web browsing and content extraction."""

import httpx
from typing import Any


class BrowserTool:
    """Tool for web browsing and content extraction."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get(self, url: str) -> str:
        """Get page content.

        Args:
            url: URL to fetch

        Returns:
            Page content as text
        """
        try:
            response = await self._client.get(url)
            response.raise_for_status()

            # Try to extract text content
            content_type = response.headers.get("content-type", "")

            if "html" in content_type:
                return self._extract_text(response.text)
            else:
                return response.text[:10000]  # Limit for non-HTML

        except Exception as e:
            return f"Error fetching {url}: {str(e)}"

    async def screenshot(self, url: str) -> str:
        """Take a screenshot of a page.

        Note: This is a placeholder. In production, use a headless browser.

        Args:
            url: URL to screenshot

        Returns:
            Screenshot status
        """
        return f"Screenshot not implemented. Use 'get' to fetch content."

    def _extract_text(self, html: str) -> str:
        """Extract text from HTML."""
        import re

        # Remove scripts and styles
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Replace common tags with newlines
        html = re.sub(r'</?p[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?br[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?div[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?h[1-6][^>]*>', '\n\n', html, flags=re.IGNORECASE)

        # Remove all remaining tags
        html = re.sub(r'<[^>]+>', '', html)

        # Decode HTML entities
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&amp;', '&')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&quot;', '"')

        # Clean up whitespace
        lines = [line.strip() for line in html.split('\n')]
        lines = [line for line in lines if line]
        return '\n'.join(lines[:200])  # Limit to 200 lines


# Tool function for AgentScope
async def browser_get(url: str) -> str:
    """Fetch a web page and extract its content.

    Args:
        url: The URL to fetch

    Returns:
        Extracted text content from the page
    """
    tool = BrowserTool()
    try:
        return await tool.get(url)
    finally:
        await tool.close()


async def browser_screenshot(url: str) -> str:
    """Take a screenshot of a web page.

    Note: This is a placeholder.

    Args:
        url: The URL to screenshot

    Returns:
        Status message
    """
    tool = BrowserTool()
    try:
        return await tool.screenshot(url)
    finally:
        await tool.close()
