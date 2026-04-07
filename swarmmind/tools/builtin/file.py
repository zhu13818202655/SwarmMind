"""File tool for reading and writing files."""

from pathlib import Path


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

    async def delete(self, path: str) -> str:
        """Delete a file or directory."""
        try:
            target_path = self._resolve_path(path)
            if not target_path.exists():
                return f"Error: Path not found: {path}"
            if target_path.is_dir():
                for child in sorted(target_path.rglob("*"), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                target_path.rmdir()
            else:
                target_path.unlink()
            return f"Deleted: {path}"
        except Exception as e:
            return f"Error deleting path: {str(e)}"

    async def rename(self, source_path: str, destination_path: str) -> str:
        """Rename or move a file or directory."""
        try:
            source = self._resolve_path(source_path)
            destination = self._resolve_path(destination_path)
            if not source.exists():
                return f"Error: Path not found: {source_path}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            return f"Renamed: {source_path} -> {destination_path}"
        except Exception as e:
            return f"Error renaming path: {str(e)}"

    async def make_directory(self, path: str) -> str:
        """Create a directory recursively."""
        try:
            dir_path = self._resolve_path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            return f"Directory created: {path}"
        except Exception as e:
            return f"Error creating directory: {str(e)}"


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


async def delete_file(path: str) -> str:
    """Delete a file or directory.

    Args:
        path: Target path to delete

    Returns:
        Success or error message
    """
    tool = FileTool()
    return await tool.delete(path)


async def rename_file(source_path: str, destination_path: str) -> str:
    """Rename or move a file or directory.

    Args:
        source_path: Existing path
        destination_path: New target path

    Returns:
        Success or error message
    """
    tool = FileTool()
    return await tool.rename(source_path, destination_path)


async def make_directory(path: str) -> str:
    """Create a directory recursively.

    Args:
        path: Directory path to create

    Returns:
        Success or error message
    """
    tool = FileTool()
    return await tool.make_directory(path)
