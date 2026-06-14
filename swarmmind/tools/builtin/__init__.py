"""Built-in tools for SwarmMind."""

from swarmmind.tools.builtin.search import SearchTool, search
from swarmmind.tools.builtin.browser import BrowserTool, browser_get
from swarmmind.tools.builtin.mail import MailTool, send_mail
from swarmmind.tools.builtin.file import (
    FileTool,
    delete_file,
    file_exists,
    list_files,
    make_directory,
    read_file,
    rename_file,
    write_file,
)
from swarmmind.tools.builtin.skill import SkillTool, get_skill_details, list_skill_scripts, read_skill_reference, run_skill_script
from swarmmind.tools.builtin.workspace import WorkspaceTool, glob_search, grep_search
from swarmmind.tools.builtin.catalog import register_builtin_tools

__all__ = [
    # Search
    "SearchTool",
    "search",
    # Browser
    "BrowserTool",
    "browser_get",
    # Mail
    "MailTool",
    "send_mail",
    # File
    "FileTool",
    "read_file",
    "write_file",
    "list_files",
    "file_exists",
    "delete_file",
    "rename_file",
    "make_directory",
    # Workspace
    "WorkspaceTool",
    "glob_search",
    "grep_search",
    # Skill
    "SkillTool",
    "read_skill_reference",
    "list_skill_scripts",
    "get_skill_details",
    "run_skill_script",
    # Catalog
    "register_builtin_tools",
]
