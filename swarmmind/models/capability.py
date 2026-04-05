"""Capability models for agent roles, runtime kinds, and tool groups."""

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
    """
    基础工具能力组，按「操作介质/环境」划分。
    每个子任务通过组合这些基础组来获得操作物理/数字世界的能力。
    """

    FILE_SYSTEM = "file_system"
    """本地文件系统操作：读文件、写文件、文件存在性检查、目录遍历、文件重命名/删除。"""

    WORKSPACE = "workspace"
    """项目工作区语义操作：基于项目路径的代码搜索(Grep/Glob)、批量编辑、跨文件重构、项目级读写。"""

    WEB_SEARCH = "web_search"
    """公开网络信息检索：搜索引擎查询、获取搜索结果摘要。只负责找信息，不负责浏览详情页。"""

    BROWSER = "browser"
    """浏览器环境操作：打开网页、页面导航、DOM 交互、表单填写、截图、获取页面详情内容。
    与 WEB_SEARCH 的区别：WEB_SEARCH 是『找』，BROWSER 是『看和交互』。"""

    CODE_EXEC = "code_exec"
    """代码执行环境：在隔离沙箱或宿主环境中运行代码/命令、安装依赖、查看执行输出。
    不包含文件读写（需要配合 FILE_SYSTEM 或 WORKSPACE）。"""

    MEMORY = "memory"
    """持久化记忆操作：读取/写入跨会话记忆、读取 CLAUDE.md、获取历史上下文摘要。"""

    ARTIFACT = "artifact"
    """产物/附件操作：读取用户上传的文件、解析 PDF/图片、下载远程资源。"""

    COMMUNICATION = "communication"
    """基础通信能力：发送邮件、调用 Webhook、发送 Slack/IM 消息。"""


class RuntimeKind(str, Enum):
    """Execution backends available to a subtask attempt."""

    LLM_ONLY = "llm_only"
    HOST_TOOLS = "host_tools"
    SANDBOX = "sandbox"


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


DEFAULT_ROLE_TOOL_GROUPS: dict[AgentRole, list[ToolGroup]] = {
    AgentRole.PLANNER: [ToolGroup.WORKSPACE, ToolGroup.MEMORY],
    AgentRole.COORDINATOR: [ToolGroup.WORKSPACE, ToolGroup.MEMORY, ToolGroup.ARTIFACT],
    AgentRole.RESEARCHER: [ToolGroup.WEB_SEARCH, ToolGroup.BROWSER, ToolGroup.WORKSPACE, ToolGroup.ARTIFACT],
    AgentRole.CODER: [ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.MEMORY],
    AgentRole.VERIFIER: [ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    AgentRole.TESTER: [ToolGroup.WORKSPACE, ToolGroup.CODE_EXEC, ToolGroup.ARTIFACT],
    AgentRole.REVIEWER: [ToolGroup.ARTIFACT, ToolGroup.MEMORY, ToolGroup.WORKSPACE],
    AgentRole.WRITER: [ToolGroup.WORKSPACE, ToolGroup.ARTIFACT, ToolGroup.WEB_SEARCH, ToolGroup.BROWSER],
}