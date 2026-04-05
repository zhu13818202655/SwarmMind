from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


PLANNER_SUPPORTED_ROLES = (
    "coder",     # 编码者，负责编写代码实现任务，前后端通用
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


PLANNER_EXECUTION_CONFIGURATION_EXAMPLE_JSON = """
合法 JSON 示例 1（简单目标，不拆分）：
{{
  "subtasks": [
    {{
      "name": "fix-readme-typo",
      "description": "修正 README.md 中 Installation 章节第三行的拼写错误。",
      "role": "coder",
      "acceptance_criteria": [
        "README.md 中的指定拼写错误已被修正。",
        "文件仍能被正常解析为 Markdown。"
      ],
      "expected_artifacts": ["code_changes"],
      "dependencies": []
    }}
  ]
}}

合法 JSON 示例 2（复杂研究+撰写任务）：
{{
  "subtasks": [
    {{
      "name": "research-gold-market",
      "description": "收集近 3 个月黄金价格走势数据、影响金价的宏观经济事件，以及主流机构对未来价格的预测观点。",
      "role": "researcher",
      "acceptance_criteria": [
        "包含近 3 个月黄金价格的关键价位变化（至少 5 个时间节点）。",
        "列出了至少 3 家主流机构（如高盛、瑞银、世界黄金协会）的预测观点及来源。",
        "标注了所有关键数据的来源链接。"
      ],
      "expected_artifacts": ["research_summary"],
      "dependencies": []
    }},
    {{
      "name": "draft-investment-ppt",
      "description": "基于研究结果撰写黄金投资建议 PPT，内容包含：走势分析、未来预测、风险提示、投资建议。",
      "role": "writer",
      "acceptance_criteria": [
        "PPT 包含走势分析、未来预测、风险提示、投资建议四个完整章节。",
        "每页内容有明确的数据或观点支撑，无空占位符。",
        "输出为可直接打开的 .pptx 或 .pdf 文件。"
      ],
      "expected_artifacts": ["presentation"],
      "dependencies": ["research-gold-market"]
    }},
    {{
      "name": "review-ppt-content",
      "description": "审查 PPT 中的数据准确性、投资逻辑一致性和页面排版可读性，提出修改建议。",
      "role": "reviewer",
      "acceptance_criteria": [
        "所有引用的数据与来源一致，无事实性错误。",
        "投资逻辑不存在自相矛盾。",
        "列出至少 3 条具体的改进建议（如有）。"
      ],
      "expected_artifacts": ["review_comments"],
      "dependencies": ["draft-investment-ppt"]
    }}
  ]
}}"""


PLANNER_SYSTEM_PROMPT = PromptTemplate(
    name="planner_system",
    template="""你是一个规划代理，负责将用户目标拆解为结构化的子任务 DAG。只返回严格的 JSON，不要包含 Markdown 代码块标记（如 ```json）或任何额外解释。""",
)

PLANNER_TASK_DECOMPOSITION_PROMPT = PromptTemplate(
    name="planner_task_decomposition",
    template=f"""请根据输入生成一个符合如下结构的计划 JSON。

## 输出 Schema：
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


## 字段说明：
- `name`: 子任务唯一标识，kebab-case，在同一个 DAG 内不可重复。
- `description`:
  - 必须具体、可执行、无歧义。禁止使用 "可能需要..." "视情况而定..." "视具体环境..." 等模糊措辞。
  - 当 `role` 为 `coder` 时，必须明确是「架构设计」「核心编码」「Bug 排查/调试」还是「CI/部署脚本」。
  - 当 `role` 为 `coordinator` 时，必须明确协调的具体内容和预期决策。
- `role`: 只能为上述可用角色之一（`planner` 通常不作为子任务出现，因为它就是当前执行规划的角色本身）。
- `acceptance_criteria`:
  - 每条标准必须是**可观察、可验证**的。
  - 下游 `verifier` 仅通过查看代码、文档或运行结果就能给出明确的「通过/不通过」，不需要主观判断。
  - 禁止出现 "质量较高" "逻辑清晰" "结构合理" 等无法直接验证的抽象描述。
- `expected_artifacts`:
  - 该子任务完成后应产出的**可验证交付物**清单。
  - 对于非产出型角色（如部分 `verifier` 或 `coordinator`），如果确实没有固定交付物，可设为 `["verification_conclusion"]` 或 `["sync_summary"]`，**禁止留空字符串**。
- `dependencies`:
  - 只有当子任务**确实需要**其它任务的产出作为输入时才写依赖。
  - 不要为了人为制造顺序而强行加依赖。如果两个任务可以并行，就让它并行。

## 任务拆分规则：
1. **能不拆就不拆**：如果目标单一（5 分钟内、一个角色可完成、无并行需求），直接输出 1 个子任务。
2. **拆分的触发条件**（满足任一）：
    a. 涉及 2 个及以上不同专业领域
    b. 存在天然并行路径
    c. 需要独立验证/审查环节
    d. 存在先研后产、先设计后实现的强依赖
3. **角色选择原则（按任务本质选择，执行能力由底层工具统一支持）**：
    - 最终产出是面向人类的文档、报告、PPT、邮件内容 → `writer`
    - 需要先收集外部信息、查资料、做市场或技术调研 → `researcher`
    - 涉及代码编写、脚本开发、系统架构、CI/CD 配置、技术调试 → `coder`
    - 需要编写测试用例并验证代码正确性 → `tester`
    - 需要评估质量、可读性、一致性并提出改进建议 → `reviewer`
    - 需要从全局视角对照验收标准做最终检查并给出通过/不通过结论 → `verifier`
    执行动作的分配：如果 `writer`、`researcher` 或 `coder` 的任务中涉及调用 API、发送通知、运行命令等动作，由该角色在执行阶段直接调用对应工具完成，无需切换角色。
    例如：writer 撰写邮件后可直接调用邮件发送工具；researcher 调研后可直接调用下载工具保存数据；coder 编写脚本后可直接运行测试命令。
4. **数量限制**：子任务总数建议 1-5 个，绝对不要超过 7 个。超过 7 个说明分解过细，请合并同类任务。

## 合法 JSON 示例：
{PLANNER_EXAMPLE_JSON}

## 自检清单（在输出 JSON 前必须确认）：
1. `dependencies` 中引用的 `name` 是否都在 `subtasks` 中存在？
2. 是否存在循环依赖？
3. `role` 是否都来自允许列表，且没有使用 `planner` 作为子任务角色？
4. `acceptance_criteria` 是否都是可观察、可验证的具体标准（没有 "质量好" "逻辑清晰" 这类词）？
5. `description` 中是否没有 "可能" "视情况" 等模糊词？
6. 子任务数量是否在 1-7 之间？

## 输入：
- 目标：{{{{ task_goal }}}}
- 约束：{{{{ constraints_json }}}}
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
- 角色定义：
{{{{ role_definitions }}}}"""
)