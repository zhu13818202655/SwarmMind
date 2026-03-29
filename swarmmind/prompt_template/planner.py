from __future__ import annotations

from swarmmind.models.capability import DEFAULT_STRATEGY_PROFILES, RuntimeKind, ToolGroup
from swarmmind.prompt_template.base import PromptTemplate


PLANNER_SUPPORTED_ROLES = (
    "planner",
    "coder",
  "verifier",
    "tester",
    "reviewer",
    "researcher",
    "writer",
    "executor",
)
PLANNER_ROLE_ENUM = "|".join(PLANNER_SUPPORTED_ROLES)
PLANNER_TOOL_GROUP_ENUM = "|".join(tool_group.value for tool_group in ToolGroup)
PLANNER_RUNTIME_KIND_ENUM = "|".join(runtime_kind.value for runtime_kind in RuntimeKind)
PLANNER_STRATEGY_ENUM = "|".join(DEFAULT_STRATEGY_PROFILES)
PLANNER_EXAMPLE_JSON = """{
  \"subtasks\": [
    {
      \"name\": \"draft-release-summary\",
      \"description\": \"研究本次发布变更并撰写一份简明的发布摘要。\",
      \"agent_profile_id\": \"writer-default\",
      \"role\": \"writer\",
      \"preferred_strategy\": \"write_report\",
      \"required_tool_groups\": [\"web_search\", \"browser_read\", \"project_write\"],
      \"candidate_runtime_kinds\": [\"llm_only\", \"host_tools\"],
      \"preferred_skill_profiles\": [\"write_report\"],
      \"sandbox_profile\": null,
      \"acceptance_criteria\": [
        \"摘要覆盖了要求的发布范围。\",
        \"输出内容可直接发布，且不存在空占位符。\"
      ],
      \"dependencies\": []
    }
  ]
}"""


PLANNER_SYSTEM_PROMPT = PromptTemplate(
    name="planner_system",
  template="""你是一个规划代理，需要将目标拆解为可执行的 JSON 任务 DAG。
只返回严格的 JSON。""",
)

PLANNER_TASK_DECOMPOSITION_PROMPT = PromptTemplate(
    name="planner_task_decomposition",
  template=f"""请根据输入生成一个符合如下结构的计划 JSON：
{{
  "subtasks": [
    {{
      "name": "string-kebab-case",
      "description": "string",
      "agent_profile_id": "string|null",
      "role": "{PLANNER_ROLE_ENUM}",
      "preferred_strategy": "{PLANNER_STRATEGY_ENUM}|null",
      "required_tool_groups": ["{PLANNER_TOOL_GROUP_ENUM}"],
      "candidate_runtime_kinds": ["{PLANNER_RUNTIME_KIND_ENUM}"],
      "preferred_skill_profiles": ["string"],
      "sandbox_profile": "string|null",
      "acceptance_criteria": ["string"],
      "dependencies": ["subtask-name"]
    }}
  ]
}}

规则：
1) 子任务必须足够精简，并且可执行、可验证。
2) 依赖关系必须无环。
3) 当任务要求测试或验证时，必须包含验证类子任务。
4) 简单目标优先使用更少的子任务，复杂目标可以使用更丰富的 DAG。
5) 确保每个子任务都有具体的验收标准。
6) 只有在子任务确实需要显式执行配置时才使用 `agent_profile_id`；否则请省略或设为 null。
7) `agent_profile_id` 必须来自可用配置列表，并且要与子任务角色兼容。
8) 可选字段绝不能使用空字符串；请使用 null 或直接省略。
9) `role`、`preferred_strategy` 和 `agent_profile_id` 必须彼此兼容。
10) `write_report` 通常应使用 `writer`，`research` 通常应使用 `researcher` 或 `writer`。
11) 当 `research` 任务需要相关能力时，应优先选择 `web_search`、`browser_read` 和 `project_read`。
12) `candidate_runtime_kinds` 应按优先级顺序列出 1 到 n 个运行时选项。
13) 除非沙箱确实是合理的运行时候选项，否则 `sandbox_profile` 应为 null。
14) `preferred_skill_profiles` 表示可复用的能力包，不需要与 `preferred_strategy` 一一对应。

合法 JSON 示例：
{PLANNER_EXAMPLE_JSON}

输入：
- 目标：{{{{ task_goal }}}}
- 约束 JSON：{{{{ constraints_json }}}}
- 首选 Profile：{{{{ profile }}}}
- 首选策略：{{{{ preferred_strategy }}}}
- 可用 Agent Profiles JSON：{{{{ agent_profiles_json }}}}""",
)