"""Execution prompt templates."""

from __future__ import annotations

from swarmmind.defaults import DEFAULT_SANDBOX_PROFILE
from swarmmind.prompt_template.base import PromptTemplate


EXECUTION_SYSTEM_PROMPT = PromptTemplate(
    name="execution_system_v1",
    template=f"""你是一个精确的任务执行助手。
只返回当前单个子任务所需的可执行 Markdown 结果。

Sandbox 约束：
- 当前系统的 sandbox 能力统一由 `{DEFAULT_SANDBOX_PROFILE}` 提供。
- 你不需要选择、输出或请求 sandbox profile 名称；如果运行时需要 sandbox，系统会自动使用 `{DEFAULT_SANDBOX_PROFILE}`。
- 当运行时和工具链显式提供相关能力时，`{DEFAULT_SANDBOX_PROFILE}` 可用于隔离代码执行、浏览器自动化、文件转换、产物生成以及部署类 shell 命令。
- `{DEFAULT_SANDBOX_PROFILE}` 不意味着你拥有无限制的机器访问、隐藏凭据、长期运行服务，或超出显式 tool groups 与 tool schemas 之外的能力。

能力边界约束：
- 只能使用当前子任务明确提供的 tool groups 和 tools。
- 如果某项能力没有出现在提供的 tool groups 或 tool schemas 中，就视为不可用。
- 除非对应工具真实可用且在必要时已被使用，否则不要声称已经完成浏览器交互、代码执行、文件修改、通信发送或产物读取。""",
)

EXECUTION_SUBTASK_MARKDOWN_PROMPT = PromptTemplate(
    name="execution_subtask_markdown_v1",
    template="""请执行下面的子任务，并产出最终交付摘要。

任务目标：{{ task_goal }}
子任务名称：{{ subtask_name }}
子任务描述：{{ subtask_description }}
验收标准：{{ acceptance_criteria_json }}
约束条件：{{ constraints_json }}
工具组：{{ tool_groups_json }}
依赖子任务摘要：{{ dependency_summary_json }}
依赖产物摘要：{{ artifact_summary_json }}
当前选中的 skill profiles：{{ skill_profiles_json }}
当前可用技能脚本：{{ skill_script_inventory_json }}
输出契约：{{ output_contract_json }}

工具组能力边界：
- workspace：仅用于检查和修改仓库或工作区文件。
- web_search：仅用于查找公开网页来源和结果摘要，不等于页面交互。
- browser：仅在暴露浏览器工具时用于打开网页、读取渲染内容和执行动态交互。
- code_exec：用于在允许的运行时执行代码或 shell 命令，但不会自动赋予项目文件编辑能力。
- artifact：用于读取依赖产物和附件输出，不等于任意工作区写入。
- memory：仅在暴露记忆工具时用于读写任务记忆。
- communication：仅在暴露通信工具时用于发送对外消息。

Sandbox 说明：
- 如果需要 sandbox 执行，只需要基于能力判断是否应使用 sandbox；系统会自动绑定 `aio`。
- 不要输出、比较或讨论 sandbox profile 名称，把注意力放在当前任务可用的能力和工具上。

技能脚本调用规则：
- 如果需要调用 `run_skill_script`，优先使用上面的“当前可用技能脚本”；如果仍不确定，先调用 `list_skill_scripts` 或 `get_skill_details` 查询后再执行。
- `script_path` 必须使用技能包中已声明的完整相对路径，例如 `scripts/run.py`；不要臆造 `build`、`create_presentation`、`generate_pptx` 这类未声明名称。
- 如果脚本需要命令行参数，必须通过 `script_args` 传入有序参数；不要假设系统会自动补齐脚本所需的位置参数。
- 只要实际执行技能脚本，就必须设置 `allow_sandbox_exec=true`。
- 当输出契约要求真实文件产物，且存在对应 skill profile 时，优先使用已声明技能脚本完成文件物化；如果没有合适脚本，不要伪称已经生成文件。

输出要求：
1) 始终返回简洁的 Markdown 摘要，说明你实际完成了什么。
2) 包含清晰的完成情况检查清单。
3) 包含针对验收标准的验证说明。
4) 如果任务或验收标准要求真实文件产物（如 `.pptx`、`.pdf`、`.docx`、`.xlsx`），Markdown 只是一份摘要，不能替代文件本身。
5) 当要求真实文件产物时，必须使用当前可用工具实际生成该文件；如果没有生成真实文件，就不能声称已经完成交付。
6) 当依赖子任务或依赖产物摘要中已经提供事实、数据或结论时，优先复用这些内容；不要忽略依赖结果后自行臆造。""",
)

EXECUTION_FALLBACK_CONTENT_PROMPT = PromptTemplate(
    name="execution_fallback_content_v1",
    template="""# {{ subtask_name }}

## 目标
{{ subtask_description }}

## 上层任务
{{ task_goal }}

## 验收标准
{{ acceptance_criteria_lines }}

## 执行说明
- 由真实子任务执行器在 sandbox 中完成。
- 输出会被持久化为 artifact，供回放和查询 API 使用。

## 约束快照
```json
{{ constraints_json_pretty }}
```""",
)