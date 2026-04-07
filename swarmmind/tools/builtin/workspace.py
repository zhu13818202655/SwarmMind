"""Workspace-aware tools for project search and navigation."""

from __future__ import annotations

from pathlib import Path
import re


class WorkspaceTool:
    """Toolbox for project-level workspace operations."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)

    def _resolve_path(self, path: str) -> Path:
        target = Path(path)
        if target.is_absolute():
            return target
        return self.base_dir / target

    async def glob_search(self, pattern: str, base_path: str = ".", max_results: int = 200) -> list[str]:
        """Find files by glob pattern within a workspace subtree."""
        root = self._resolve_path(base_path)
        if not root.exists():
            return []
        matches = [str(path) for path in root.glob(pattern)]
        return sorted(matches)[:max_results]

    async def grep_search(
        self,
        query: str,
        base_path: str = ".",
        include_pattern: str = "**/*",
        is_regex: bool = False,
        max_results: int = 50,
    ) -> list[dict[str, object]]:
        """Search file contents inside the workspace."""
        root = self._resolve_path(base_path)
        if not root.exists():
            return []

        pattern = re.compile(query) if is_regex else None
        results: list[dict[str, object]] = []
        for candidate in root.glob(include_pattern):
            if not candidate.is_file():
                continue
            try:
                content = candidate.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            for line_number, line in enumerate(content.splitlines(), start=1):
                matched = bool(pattern.search(line)) if pattern is not None else query in line
                if not matched:
                    continue
                results.append(
                    {
                        "path": str(candidate),
                        "line": line_number,
                        "content": line.strip(),
                    }
                )
                if len(results) >= max_results:
                    return results
        return results


async def glob_search(pattern: str, base_path: str = ".", max_results: int = 200) -> list[str]:
    """Find files by glob pattern within a workspace subtree.

    Args:
        pattern: Glob pattern to match
        base_path: Workspace root or subdirectory
        max_results: Maximum number of matches to return

    Returns:
        Matching file paths
    """
    tool = WorkspaceTool()
    return await tool.glob_search(pattern, base_path, max_results)


async def grep_search(
    query: str,
    base_path: str = ".",
    include_pattern: str = "**/*",
    is_regex: bool = False,
    max_results: int = 50,
) -> list[dict[str, object]]:
    """Search file contents inside the workspace.

    Args:
        query: Text or regex pattern to search for
        base_path: Workspace root or subdirectory
        include_pattern: Glob limiting searched files
        is_regex: Whether query should be treated as a regex
        max_results: Maximum number of matches to return

    Returns:
        Structured match results with path, line and content
    """
    tool = WorkspaceTool()
    return await tool.grep_search(query, base_path, include_pattern, is_regex, max_results)