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
      "dependencies": ["write-module-tests", "setup-ci-pipeline"]
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
      "dependencies": ["subtask-name"],
      "execution_overrides": {{ "sandbox_profile": "string|null", "runtime_kind": "string|null" }} | null
    }}
  ]
}}

字段说明：
- `name`: 子任务唯一标识。
- `description`: 具体、可执行的任务描述。
  注意：当 `role` 为 `coder` 时，请在这里明确说明它负责的是**架构设计**、**核心编码**、**Bug 排查**还是 **CI/CD/部署脚本**。不同 coder 子任务各司其职即可，无需拆成多个不同 `role`。
- `role`: 只能是 {PLANNER_ROLE_ENUM} 之一。
- `acceptance_criteria`: 明确的验收标准，供下游验证者判断任务完成质量。
- `dependencies`: 依赖的其它子任务 `name` 列表。必须无环，且只能引用真实存在的子任务。
- `execution_overrides`: **仅在需要覆盖该 role 的默认执行配置时使用**。例如：
  - 某个 `coder` 需要运行不可信代码 → `{{"sandbox_profile": "python-sandbox", "runtime_kind": "sandbox"}}`
  - 绝大多数情况下直接设为 `null` 或省略。

规则：
1. 子任务必须精简、可执行、可验证。
2. 依赖关系必须构成 DAG，禁止循环依赖。
3. 任务需要测试时，必须显式产出 `tester` 子任务；需要验证时，必须显式产出 `verifier` 子任务。
4. 简单目标（5 分钟内可完成）优先不拆；复杂目标再展开为丰富 DAG，子任务总数建议 2-6 个，不要超过 8 个。
5. 每个子任务必须有具体且无歧义的验收标准。
6. 不需要的字段请使用 `null` 或省略，绝不要使用空字符串。

合法 JSON 示例：
{PLANNER_EXAMPLE_JSON}

在正式输出 JSON 之前，请完成以下自检：
1. `dependencies` 中的 `name` 是否都存在于 `subtasks` 里？
2. 是否存在循环依赖？
3. 输出是否只有纯 JSON，没有任何 Markdown 标记？

输入：
- 目标：{{{{ task_goal }}}}"""  # TODO 后续添加用户上传skill，知识库等上下文输入
)