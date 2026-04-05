from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


PLANNER_SUPPORTED_ROLES = (
    "coder",     # 编码者，负责编写代码实现任务
  	"verifier",  # 验证者，负责验证任务的正确性和完整性
    "tester",    # 测试者，负责编写和执行测试用例
    "reviewer",  # 审查者，负责审查任务的输出质量
    "researcher",# 研究者，负责进行背景研究和信息收集，主要使用搜索工具和沙盒进行浏览器搜索和文档阅读
    "writer",    # 撰写者，负责编写文档和报告，主要使用撰写工具和阅读工具，写成PPT、Word、Excel、Markdown、HTML等格式
)
PLANNER_ROLE_ENUM = "|".join(PLANNER_SUPPORTED_ROLES)


# =============================================================================
# Few-shot 示例（展示 description 如何在大角色内细分职责 + DAG 依赖）
# =============================================================================
PLANNER_EXAMPLE_JSON = """{
  "subtasks": [
    {
      "name": "design-system-architecture",
      "description": "负责系统整体架构设计：定义模块边界、接口契约、数据库模型与技术选型。",
      "role": "coder",
      "acceptance_criteria": [
        "包含模块关系图或接口定义文档。",
        "技术选型说明了对比理由。"
      ],
      "expected_artifacts": ["design_doc"],
      "dependencies": []
    },
    {
      "name": "implement-core-module",
      "description": "根据架构设计实现核心模块的业务逻辑代码。",
      "role": "coder",
      "acceptance_criteria": [
        "代码通过编译/解释且无运行时错误。",
        "关键路径包含基础异常处理。"
      ],
      "expected_artifacts": ["code_changes"],
      "dependencies": ["design-system-architecture"]
    },
    {
      "name": "setup-ci-pipeline",
      "description": "编写 CI/CD 配置文件（如 GitHub Actions）并验证构建流程可正常跑通。",
      "role": "coder",
      "acceptance_criteria": [
        "CI 配置文件已提交到仓库。",
        "在测试分支上触发构建成功。"
      ],
      "expected_artifacts": ["ci_config"],
      "dependencies": ["implement-core-module"]
    },
    {
      "name": "write-module-tests",
      "description": "为核心模块编写单元测试和集成测试。",
      "role": "tester",
      "acceptance_criteria": [
        "覆盖正常路径与至少 2 种异常路径。",
        "测试用例在本地可直接运行。"
      ],
      "expected_artifacts": ["test_code", "test_report"],
      "dependencies": ["implement-core-module"]
    },
    {
      "name": "verify-release-readiness",
      "description": "验证代码、测试、CI 流程是否满足发布标准。",
      "role": "verifier",
      "acceptance_criteria": [
        "所有子任务的验收标准已满足。",
        "未发现阻塞性缺陷。"
      ],
      "expected_artifacts": ["verification_report"],
      "dependencies": ["write-module-tests", "setup-ci-pipeline"]
    }
  ]
}"""


PLANNER_EXECUTION_CONFIGURATION_EXAMPLE_JSON = """{
  "subtasks": [
    {
      "name": "design-system-architecture",
      "runtime_kind": "host_tools",
      "tool_requirements": ["workspace", "memory"],
      "sandbox_profile": null,
      "skill_profiles": ["task_planning"]
    },
    {
      "name": "implement-core-module",
      "runtime_kind": "sandbox",
      "tool_requirements": ["workspace", "code_exec"],
      "sandbox_profile": "py-basic",
      "skill_profiles": ["build_app"]
    }
  ]
}"""


PLANNER_SYSTEM_PROMPT = PromptTemplate(
    name="planner_system",
    template="""你是一个规划代理，负责将用户目标拆解为结构化的子任务 DAG。只返回严格的 JSON，不要包含 Markdown 代码块标记（如 ```json）或任何额外解释。""",
)

PLANNER_TASK_DECOMPOSITION_PROMPT = PromptTemplate(
    name="planner_task_decomposition",
    template=f"""请根据输入生成一个符合如下结构的计划 JSON。

输出 Schema：
{{
  "subtasks": [
    {{
      "name": "string-kebab-case",
      "description": "string",
      "role": "{PLANNER_ROLE_ENUM}",
      "acceptance_criteria": ["string"],
      "expected_artifacts": ["string"],
      "dependencies": ["subtask-name"]
    }}
  ]
}}

字段说明：
- `name`: 子任务唯一标识。
- `description`: 具体、可执行的任务描述。
  注意：当 `role` 为 `coder` 时，请在这里明确说明它负责的是**架构设计**、**核心编码**、**Bug 排查**还是 **CI/CD/部署脚本**。不同 coder 子任务各司其职即可，无需拆成多个不同 `role`。
- `role`: 只能是 {PLANNER_ROLE_ENUM} 之一。
- `acceptance_criteria`: 明确的验收标准，供下游验证者判断任务完成质量。
- `expected_artifacts`: 该子任务完成后应产出的可验证交付物类型。
- `dependencies`: 依赖的其它子任务 `name` 列表。必须无环，且只能引用真实存在的子任务。


规则：
1. 子任务必须精简、可执行、可验证。
2. 依赖关系必须构成 DAG，禁止循环依赖。
3. 任务需要测试时，必须显式产出 `tester` 子任务；需要验证时，必须显式产出 `verifier` 子任务。
4. 简单目标（5 分钟内可完成）优先不拆；复杂目标再展开为丰富 DAG，子任务总数建议 2-6 个，不要超过 8 个。
5. 每个子任务必须有具体且无歧义的验收标准。
6. 每个子任务必须提供 `expected_artifacts`。
7. 不需要的字段请使用 `null` 或省略，绝不要使用空字符串。

合法 JSON 示例：
{PLANNER_EXAMPLE_JSON}

在正式输出 JSON 之前，请完成以下自检：
1. `dependencies` 中的 `name` 是否都存在于 `subtasks` 里？
2. 是否存在循环依赖？
3. 输出是否只有纯 JSON，没有任何 Markdown 标记？

输入：
- 目标：{{{{ task_goal }}}}
- 约束：{{{{ constraints_json }}}}
- 可用 Agent Profiles JSON：{{{{ agent_profiles_json }}}}
- 角色定义：
{{{{ role_definitions }}}}"""  # TODO 后续添加用户上传skill，知识库等上下文输入
)


PLANNER_EXECUTION_CONFIGURATION_PROMPT = PromptTemplate(
    name="planner_execution_configuration",
    template=f"""请基于已经生成的子任务 DAG，为每个子任务生成 execution configuration。

输出 Schema：
{{
  "subtasks": [
    {{
      "name": "string-kebab-case",
      "runtime_kind": "llm_only|host_tools|sandbox|null",
      "tool_requirements": ["file_system|workspace|web_search|browser|code_exec|memory|artifact|communication"],
      "sandbox_profile": "string|null",
      "skill_profiles": ["string"]
    }}
  ]
}}

规则：
1. `name` 必须与输入子任务名称一一对应。
2. `runtime_kind` 只能使用 `llm_only`、`host_tools`、`sandbox`。
3. `tool_requirements` 必须从基础 ToolGroup 中选择，不允许输出 capability bundle 或内部执行器字段。
4. 仅当子任务确实需要隔离执行环境时才输出 `sandbox`。
5. `sandbox_profile` 仅在 `runtime_kind` 为 `sandbox` 时提供。
6. `skill_profiles` 只输出受控的技能名，不要自由发明实现细节。

合法 JSON 示例：
{PLANNER_EXECUTION_CONFIGURATION_EXAMPLE_JSON}

输入：
- 用户目标：{{{{ task_goal }}}}
- 任务约束：{{{{ constraints_json }}}}
- 默认 sandbox profile：{{{{ profile }}}}
- 子任务 DAG JSON：{{{{ subtasks_json }}}}
- 可用 Agent Profiles JSON：{{{{ agent_profiles_json }}}}
- 角色定义：
{{{{ role_definitions }}}}"""
)