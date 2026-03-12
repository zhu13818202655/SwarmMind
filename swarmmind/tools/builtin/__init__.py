"""Built-in tools for SwarmMind."""

from swarmmind.tools.builtin.bash import BashTool, bash
from swarmmind.tools.builtin.search import SearchTool, search
from swarmmind.tools.builtin.browser import BrowserTool, browser_get, browser_screenshot
from swarmmind.tools.builtin.mail import MailTool, send_mail
from swarmmind.tools.builtin.pptx import PptxTool, generate_pptx
from swarmmind.tools.builtin.file import FileTool, read_file, write_file, list_files, file_exists

__all__ = [
    # Bash
    "BashTool",
    "bash",
    # Search
    "SearchTool",
    "search",
    # Browser
    "BrowserTool",
    "browser_get",
    "browser_screenshot",
    # Mail
    "MailTool",
    "send_mail",
    # Pptx
    "PptxTool",
    "generate_pptx",
    # File
    "FileTool",
    "read_file",
    "write_file",
    "list_files",
    "file_exists",
]
