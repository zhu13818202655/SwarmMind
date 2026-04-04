# 新的改动

## Role
### role的类别
现在定义
```
class AgentRole(str, Enum):
    """Logical roles used by the orchestrator."""

    PLANNER = "planner"
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    EXECUTOR = "executor"
    CODER = "coder"
    VERIFIER = "verifier"
    TESTER = "tester"
    REVIEWER = "reviewer"
    WRITER = "writer"
```
首先这个ROLE是不是足够了，我们目标是一个通用智能体服务解决任何任务，那么role的设计应该是通用的，不应该有特定于某个领域的角色出现。其次，这些角色的定义需要足够清晰，能够覆盖智能体在执行任务过程中可能涉及到的各个方面。
1. 现在的role需不需要修改
2. 需不需要添加role

### role的含义
目前没有针对每个role的具体定义和职责描述，这可能会导致在实际应用中对role的理解和使用出现偏差。我们需要为每个role提供一个清晰的定义，说明它在智能体系统中的职责和作用。例如：
- PLANNER：负责制定整体的任务执行计划，协调各个角色的工作，确保任务按时完成。
- COORDINATOR：负责协调各个角色之间的沟通和协作，确保信息的流畅传递和资源的合理分配。
...
那么需要一个data class来定义role的职责和能力要求吗？还是说我们直接在文档里描述清楚每个role的职责和能力要求就可以了？

### role和其他组件的关系
- tool
- tool group
- runtime kind
- skills

我是不是需要一份默认每个role对应的
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
