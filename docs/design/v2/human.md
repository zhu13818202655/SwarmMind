# 新的改动
## Plan

1. 修改plan，每一个角色不用提前绑定tool，只需要给出role ac dependency

## runtime kind
```
class RuntimeKind(str, Enum):
    """Execution backends available to a subtask attempt."""

    LLM_ONLY = "llm_only"
    HOST_TOOLS = "host_tools"
    SANDBOX = "sandbox"
    BROWSER_AUTOMATION = "browser_automation"
    AGENT_BACKED = "agent_backed"
```
我觉得只需要保留
- LLM_ONLY
- HOST_TOOLS
- SANDBOX

## ToolGroup
```
class ToolGroup(str, Enum):
    """Groups of atomic tools equipped per subtask."""

    PROJECT_READ = "project_read"
    PROJECT_WRITE = "project_write"
    WEB_SEARCH = "web_search"
    BROWSER_READ = "browser_read"
    SANDBOX_EXEC = "sandbox_exec"
    ARTIFACT_READ = "artifact_read"
    MEMORY_LOOKUP = "memory_lookup"
    TASK_ADMIN = "task_admin"
    MAIL = "mail"
    PRESENTATION = "presentation"
```
这是一组能力的包装，这一组能力我觉得需要固化下来，不能让LLM每次随意发挥

## skill repo
- [x] pptx
- [x] frontend-design
- [x]
