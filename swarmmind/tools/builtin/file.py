"""File tool for reading and writing files."""

import os
from pathlib import Path
from typing import Any


class FileTool:
    """Tool for file operations."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base directory."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    async def read(self, path: str, encoding: str = "utf-8") -> str:
        """Read a file.

        Args:
            path: File path
            encoding: File encoding

        Returns:
            File content
        """
        try:
            file_path = self._resolve_path(path)
            return file_path.read_text(encoding=encoding)
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"

    async def write(self, path: str, content: str, encoding: str = "utf-8") -> str:
        """Write a file.

        Args:
            path: File path
            content: Content to write
            encoding: File encoding

        Returns:
            Success or error message
        """
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding=encoding)
            return f"File written: {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    async def list(self, path: str = ".") -> str:
        """List files in a directory.

        Args:
            path: Directory path

        Returns:
            List of files
        """
        try:
            dir_path = self._resolve_path(path)
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"

            items = []
            for item in dir_path.iterdir():
                item_type = "dir" if item.is_dir() else "file"
                items.append(f"{item.name} ({item_type})")

            return "\n".join(items) if items else "Empty directory"
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    async def exists(self, path: str) -> str:
        """Check if a file or directory exists.

        Args:
            path: File or directory path

        Returns:
            Yes or no
        """
        file_path = self._resolve_path(path)
        if file_path.exists():
            return f"Yes, exists: {path}"
        return f"No, does not exist: {path}"


# Tool function for AgentScope
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file's content.

    Args:
        path: File path to read
        encoding: File encoding (default: utf-8)

    Returns:
        File content as string
    """
    tool = FileTool()
    return await tool.read(path, encoding)


async def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write content to a file.

    Args:
        path: File path to write
        content: Content to write
        encoding: File encoding (default: utf-8)

    Returns:
        Success or error message
    """
    tool = FileTool()
    return await tool.write(path, content, encoding)


async def list_files(path: str = ".") -> str:
    """List files in a directory.

    Args:
        path: Directory path (default: current directory)

    Returns:
        List of files and directories
    """
    tool = FileTool()
    return await tool.list(path)


async def file_exists(path: str) -> str:
    """Check if a file or directory exists.

    Args:
        path: File or directory path

    Returns:
        Yes or no
    """
    tool = FileTool()
    return await tool.exists(path)
