from __future__ import annotations

from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE
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
PLANNER_EXAMPLE_JSON = """
合法 JSON 示例 1（简单目标，不拆分）：
{
  "subtasks": [
    {
      "name": "fix-readme-typo",
      "description": "修正 README.md 中 Installation 章节第三行的拼写错误。",
      "role": "coder",
      "acceptance_criteria": [
        "README.md 中的指定拼写错误已被修正。",
        "文件仍能被正常解析为 Markdown。"
      ],
      "expected_artifacts": ["code_changes"],
      "dependencies": []
    }
  ]
}

合法 JSON 示例 2（复杂研究+撰写任务）：
{
  "subtasks": [
    {
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
    },
    {
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
    },
    {
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
    }
  ]
}"""


PLANNER_EXECUTION_CANDIDATE_EXAMPLE_JSON = """
合法 JSON 示例 1（代码实现子任务）：
{
  "name": "implement-core-module",
  "tool_groups": ["workspace", "code_exec", "artifact"],
  "runtime_kinds": ["sandbox", "host_tools"],
  "skill_profiles": []
}

合法 JSON 示例 2（调研子任务）：
{
  "name": "research-gold-market",
  "tool_groups": ["web_search", "browser", "workspace", "artifact"],
  "runtime_kinds": ["host_tools", "llm_only"],
  "skill_profiles": ["deep-research"]
}"""


PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT = PromptTemplate(
    name="planner_task_decomposition_system",
    template="""你是一个任务拆解规划代理，负责将用户目标拆解为结构化的子任务 DAG。只返回严格的 JSON，不要包含 Markdown 代码块标记（如 ```json）或任何额外解释。

当前阶段只负责任务拆解：
- 只关注子任务划分、角色分配、依赖关系、验收标准和预期产物。""",
)


PLANNER_EXECUTION_CONFIGURATION_SYSTEM_PROMPT = PromptTemplate(
    name="planner_execution_configuration_system",
    template=f"""你是一个 execution candidate 规划代理，负责为单个已确定的子任务补全执行配置。只返回严格的 JSON，不要包含 Markdown 代码块标记（如 ```json）或任何额外解释。

执行环境硬约束：
- 当前系统的 sandbox 能力统一由 `{DEFAULT_SANDBOX_PROFILE}` 提供。
- 规划和 execution candidate 输出中，不需要模型选择或输出 sandbox profile；只需要判断任务是否需要 sandbox runtime。
- 不要把 sandbox profile 当成能力类型枚举来发明新名字；能力边界由 tool groups 和 runtime 决定，不由 profile 名称决定。""",
)


PLANNER_SYSTEM_PROMPT = PLANNER_TASK_DECOMPOSITION_SYSTEM_PROMPT

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
    tool group 能力边界：
    - `web_search` 只负责搜索候选来源和摘要，不代表能直接完成网页交互。
    - `browser` 负责打开页面、读取渲染内容、动态交互和截图。
    - `workspace` 负责仓库内文件读写、搜索和项目级修改。
    - `artifact` 负责读取依赖产物、附件和已生成输出，不等于任意文件系统访问。
    - `code_exec` 负责运行代码、命令、测试、构建、转换和部署类命令，不等于自动拥有其它工具组能力。
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
    template=f"""请基于单个子任务事实，从系统给定候选空间中选择 execution candidate。

输出 Schema：
{{
  "name": "string-kebab-case",
  "tool_groups": ["file_system|workspace|web_search|browser|code_exec|memory|artifact|communication"],
  "runtime_kinds": ["llm_only|host_tools|sandbox"],
  "skill_profiles": ["string"]
}}

规则：
1. `name` 必须与输入子任务名称完全一致。
2. `tool_groups` 只能从给定 `available_tool_groups` 中选择。
3. `runtime_kinds` 只能从给定 `available_runtime_kinds` 中选择，且按优先级排序。
4. 当 `runtime_kinds` 包含 `sandbox` 时，表示该子任务需要 sandbox 能力；系统会自动绑定 `{DEFAULT_SANDBOX_PROFILE}`，不要额外输出 `sandbox_profile` 字段。
5. `skill_profiles` 只能从给定 `available_skill_profiles` 中选择；若不需要技能可输出空数组。
6. 这是 candidate 选择，不是最终执行决策；不要输出 agent profile、sandbox profile 或其它执行器内部字段。
7. 不要把 tool group 混用成能力幻想：需要动态页面交互时必须包含 `browser`；需要执行命令、测试、构建、转换或部署动作时必须包含 `code_exec`；需要修改仓库文件时必须包含 `workspace`。

合法 JSON 示例：
{PLANNER_EXECUTION_CANDIDATE_EXAMPLE_JSON}

输入：
- 用户目标：{{{{ task_goal }}}}
- 任务约束：{{{{ constraints_json }}}}
- 子任务 JSON：{{{{ subtask_json }}}}
- 可用 tool groups：{{{{ available_tool_groups_json }}}}
- 可用 runtime kinds：{{{{ available_runtime_kinds_json }}}}
- 可用 skill profiles：{{{{ available_skill_profiles_json }}}}"""
)