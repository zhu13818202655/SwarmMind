"""Capability models for agent roles, strategy profiles, and tool groups."""

from dataclasses import dataclass
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class RoleSpec:
    """角色的规范化定义，供 Planner 和 Allocator 共同消费。"""
    name: str                          # 枚举键，如 "coder"
    description: str                   # 一句话定义该角色的核心定位
    typical_responsibilities: List[str] # 典型职责清单
    output_format_hint: str            # 该角色通常产出什么形式的成果
    notes_for_planner: str = ""        # 给 Planner 的额外提示（何时选它、边界在哪）


ROLE_SPECS = {
    "planner": RoleSpec(
        name="planner",
        description="规划者，负责将用户任务/目标拆解为可执行的子任务 DAG。",
        typical_responsibilities=[
            "分析需求并识别关键路径",
            "将复杂目标拆分为精简、可验证的子任务",
            "定义子任务间的依赖关系与验收标准"
        ],
        output_format_hint="JSON 格式的任务计划（subtasks + dependencies）",
        notes_for_planner="只在需要显式进行任务分解时分配，通常作为入口角色。"
    ),
    "coordinator": RoleSpec(
        name="coordinator",
        description="协调分配者，负责为已就绪子任务补全执行配置，并在关键节点决定任务如何继续流转。",
        typical_responsibilities=[
            "为子任务解析 agent profile、strategy、runtime 和 sandbox 配置",
            "补全技能、工具权限与执行元数据，确保下游执行器具备正确上下文",
            "根据评审或失败结果决定是否进入修复、验证、升级等后续流程"
        ],
        output_format_hint="已分配执行配置的子任务、状态摘要或后续流转决策",
        notes_for_planner="当你需要一个负责分派、路由和流转控制的角色时使用；不要把它当成具体实现者或广义的项目经理。"
    ),
    "researcher": RoleSpec(
        name="researcher",
        description="研究者，负责收集背景信息、技术文档、竞品方案或根因分析所需的数据。",
        typical_responsibilities=[
            "通过网络搜索、阅读文档获取信息",
            "分析日志、报错、技术方案",
            "整理研究结论供下游角色消费"
        ],
        output_format_hint="结构化研究报告、对比分析或关键发现摘要",
        notes_for_planner="适合目标不明确、需要先行调研的场景；不要让它直接写最终交付物。"
    ),
    "coder": RoleSpec(
        name="coder",
        description="技术实现者，负责与代码和工程配置相关的所有实现工作。",
        typical_responsibilities=[
            "系统架构设计与接口定义",
            "核心功能编码与重构",
            "Bug 排查与性能优化",
            "CI/CD 脚本、部署配置、基础设施代码编写"
        ],
        output_format_hint="代码文件、配置文件、设计文档或补丁",
        notes_for_planner=(
            "coder 是一个大技术方向角色。当任务涉及代码、脚本、配置时均可分配 coder，"
            "但要在 description 中明确它是负责「架构」「编码」「调试」还是「CI/部署」。"
        )
    ),
    "tester": RoleSpec(
        name="tester",
        description="测试者，负责编写测试用例并执行验证，确保实现满足预期。",
        typical_responsibilities=[
            "编写单元测试、集成测试、端到端测试",
            "设计边界条件与异常路径覆盖",
            "执行测试并报告覆盖率与失败项"
        ],
        output_format_hint="测试代码、测试报告或覆盖率统计",
        notes_for_planner="任何需要质量保证的功能实现后，都应考虑分配 tester。"
    ),
    "verifier": RoleSpec(
        name="verifier",
        description="验证者，负责从全局视角检查任务完成度和正确性，不编写新代码。",
        typical_responsibilities=[
            "对照验收标准逐项检查",
            "审查代码逻辑、文档完整性、配置一致性",
            "确认依赖任务全部闭环"
        ],
        output_format_hint="验证结论（通过/不通过）及问题清单",
        notes_for_planner="在 DAG 末端或关键里程碑后使用，独立评估前期所有产出。"
    ),
    "reviewer": RoleSpec(
        name="reviewer",
        description="审查者，负责评估输出质量、可读性、可维护性，并提出改进建议。",
        typical_responsibilities=[
            "代码审查（风格、设计模式、安全性）",
            "文档审查（清晰度、准确性、结构）",
            "输出质量评分与优化建议"
        ],
        output_format_hint="审查意见列表，含优先级和改进建议",
        notes_for_planner="侧重「质量优化」，与 verifier 的「正确性检查」互补。"
    ),
    "writer": RoleSpec(
        name="writer",
        description="撰写者，负责将信息整理成面向用户的文档、报告或演示材料。",
        typical_responsibilities=[
            "编写技术文档、README、Release Note",
            "撰写报告、PPT、邮件或博客",
            "整理和润色研究结论"
        ],
        output_format_hint="Markdown、Word、PPT、HTML 等可读性文档",
        notes_for_planner="当最终交付物是给人阅读的文档或报告时使用。"
    ),
}


class AgentRole(str, Enum):
    PLANNER = "planner"
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    CODER = "coder"
    VERIFIER = "verifier"
    TESTER = "tester"
    REVIEWER = "reviewer"
    WRITER = "writer"

    @property
    def spec(self) -> RoleSpec:
        return ROLE_SPECS[self.value]

    @classmethod
    def to_prompt_definitions(cls) -> str:
        """生成供 Prompt 注入的角色定义文本。"""
        lines = []
        for role in cls:
            sp = role.spec
            lines.append(f"【{role.value}】{sp.description}")
            lines.append(f"  典型职责：{' / '.join(sp.typical_responsibilities)}")
            lines.append(f"  通常产出：{sp.output_format_hint}")
            if sp.notes_for_planner:
                lines.append(f"  分配提示：{sp.notes_for_planner}")
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def names(cls) -> List[str]:
        return [r.value for r in cls]


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


class RuntimeKind(str, Enum):
    """Execution backends available to a subtask attempt."""

    LLM_ONLY = "llm_only"
    HOST_TOOLS = "host_tools"
    SANDBOX = "sandbox"
    BROWSER_AUTOMATION = "browser_automation"
    AGENT_BACKED = "agent_backed"


class ToolExecutionContract(BaseModel):
    """Execution metadata attached to an atomic tool function."""

    default_runtime: RuntimeKind = Field(
        default=RuntimeKind.HOST_TOOLS,
        description="Default runtime used when the agent selects this tool.",
    )
    allowed_runtimes: list[RuntimeKind] = Field(
        default_factory=list,
        description="Explicit runtimes that may execute this tool.",
    )
    read_only: bool = Field(default=False, description="Whether the tool is expected to avoid side effects.")
    expensive: bool = Field(default=False, description="Whether the tool is materially expensive in time or resources.")
    audit_required: bool = Field(default=False, description="Whether every invocation should be treated as auditable.")
    dangerous: bool = Field(default=False, description="Whether the tool can mutate state or execute untrusted actions.")
    sandbox_only: bool = Field(default=False, description="Whether the tool must run inside a sandbox runtime.")


class StrategyProfile(BaseModel):
    """Structured runtime strategy profile used to equip a subtask."""

    name: str = Field(..., description="Unique skill profile name")
    description: str = Field(..., description="What this profile is for")
    tool_groups: list[ToolGroup] = Field(
        default_factory=list,
        description="Tool groups required by the skill profile",
    )
    recommended_roles: list[AgentRole] = Field(
        default_factory=list,
        description="Roles that commonly use this profile",
    )
    candidate_runtime_kinds: list[RuntimeKind] = Field(
        default_factory=list,
        description="Candidate execution backends that may satisfy the workflow",
    )
    default_skill_profiles: list[str] = Field(
        default_factory=list,
        description="Reusable skill packages commonly attached to the workflow",
    )
    sandbox_profile: str | None = Field(
        default=None,
        description="Preferred sandbox profile for this skill profile",
    )


DEFAULT_STRATEGY_PROFILES: dict[str, StrategyProfile] = {
    "task_planning": StrategyProfile(
        name="task_planning",
        description="Decompose user goals into executable task graphs.",
        tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.PLANNER, AgentRole.COORDINATOR],
        candidate_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["task_planning"],
    ),
    "research": StrategyProfile(
        name="research",
        description="Research external information and summarize findings.",
        tool_groups=[ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_READ],
        recommended_roles=[AgentRole.RESEARCHER, AgentRole.WRITER],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.BROWSER_AUTOMATION],
    ),
    "build_app": StrategyProfile(
        name="build_app",
        description="Implement application code, write files, and run local validation.",
        tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.PROJECT_WRITE,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
        ],
        recommended_roles=[AgentRole.CODER],
        candidate_runtime_kinds=[RuntimeKind.SANDBOX, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["build_app"],
        sandbox_profile="py-basic",
    ),
    "verification": StrategyProfile(
        name="verification",
        description="Run tests and verify outputs against acceptance criteria.",
        tool_groups=[
            ToolGroup.PROJECT_READ,
            ToolGroup.SANDBOX_EXEC,
            ToolGroup.ARTIFACT_READ,
        ],
        recommended_roles=[AgentRole.VERIFIER, AgentRole.TESTER, AgentRole.REVIEWER],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["verification"],
    ),
    "review": StrategyProfile(
        name="review",
        description="Review results and decide whether to accept or rework.",
        tool_groups=[ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.REVIEWER, AgentRole.COORDINATOR],
        candidate_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["review"],
    ),
    "write_report": StrategyProfile(
        name="write_report",
        description="Research, draft, and save a structured report.",
        tool_groups=[
            ToolGroup.WEB_SEARCH,
            ToolGroup.BROWSER_READ,
            ToolGroup.PROJECT_WRITE,
        ],
        recommended_roles=[AgentRole.WRITER, AgentRole.RESEARCHER],
        candidate_runtime_kinds=[RuntimeKind.LLM_ONLY, RuntimeKind.HOST_TOOLS],
        default_skill_profiles=["write_report"],
    ),
    "presentation_delivery": StrategyProfile(
        name="presentation_delivery",
        description="Turn researched material into a presentation delivery artifact.",
        tool_groups=[ToolGroup.PRESENTATION, ToolGroup.ARTIFACT_READ, ToolGroup.PROJECT_WRITE],
        recommended_roles=[AgentRole.WRITER, AgentRole.REVIEWER],
        candidate_runtime_kinds=[RuntimeKind.HOST_TOOLS, RuntimeKind.SANDBOX],
        default_skill_profiles=["pptx"],
        sandbox_profile="py-basic",
    ),
    "agent_backed": StrategyProfile(
        name="agent_backed",
        description="Run a controlled agent runtime backend instead of the default sandbox strategy.",
        tool_groups=[ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
        recommended_roles=[AgentRole.PLANNER, AgentRole.RESEARCHER, AgentRole.WRITER, AgentRole.CODER],
        candidate_runtime_kinds=[RuntimeKind.AGENT_BACKED],
    ),
}



DEFAULT_ROLE_TOOL_GROUPS: dict[AgentRole, list[ToolGroup]] = {
    AgentRole.PLANNER: [ToolGroup.PROJECT_READ, ToolGroup.MEMORY_LOOKUP],
    AgentRole.COORDINATOR: [ToolGroup.TASK_ADMIN, ToolGroup.MEMORY_LOOKUP, ToolGroup.ARTIFACT_READ],
    AgentRole.RESEARCHER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_READ],
    AgentRole.CODER: [ToolGroup.PROJECT_READ, ToolGroup.PROJECT_WRITE, ToolGroup.SANDBOX_EXEC],
    AgentRole.VERIFIER: [ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
    AgentRole.TESTER: [ToolGroup.PROJECT_READ, ToolGroup.SANDBOX_EXEC, ToolGroup.ARTIFACT_READ],
    AgentRole.REVIEWER: [ToolGroup.ARTIFACT_READ, ToolGroup.MEMORY_LOOKUP],
    AgentRole.WRITER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER_READ, ToolGroup.PROJECT_WRITE],
}