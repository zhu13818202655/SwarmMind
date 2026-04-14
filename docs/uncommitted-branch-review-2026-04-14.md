# 当前未提交代码审阅记录（2026-04-14）

本文档只记录当前工作树里尚未提交的改动，目标是给本次 push 前审阅用。

说明：

1. 本文档基于当前 `git diff --stat` 和工作树实际文件状态整理。
2. 已经被撤回的改动不计入本文档。
3. 本文档区分了“主线功能改动”和“调试/产物/临时文件”，便于决定是否需要拆 commit 或排除后再 push。

## 1. 当前未提交改动的总体情况

当前未提交改动覆盖 24 个文件，主要集中在以下几类：

1. skill 元数据模型与执行契约升级。
2. prompt 与 execution runner 调整，目的是让 agent 更稳定地产生真实文件，而不是只返回 Markdown 摘要。
3. OpenSandbox 二进制读取链路修复，目的是把 sandbox 内已经生成的 `.pptx` 真正读回并进入 artifact 持久化链路。
4. 测试与文档补齐。
5. 一批明显用于调试、复盘或本地验证的产物文件。

如果按 push 风险来判断，当前工作树不是一个单一主题的干净提交，而是“核心能力改动 + 调试辅助 + 生成产物 + 文档”的混合状态。

## 2. 这批代码主要做了什么

### 2.1 skill 元数据从简单声明升级为结构化执行契约

涉及文件：

1. `swarmmind/skill_system/models.py`
2. `swarmmind/skill_system/parser.py`
3. `swarmmind/skill_system/validator.py`
4. `swarmmind/skills/pptx/SKILL.md`
5. `swarmmind/tools/builtin/skill.py`
6. `swarmmind/skill_system/service.py`
7. `swarmmind/skill_system/executor.py`

这部分实际做的事情：

1. 引入 `runtime_requirements`，把 skill 运行依赖从旧的 Python-only 思路升级成通用结构，支持 `python_packages`、`node_packages`、`system_packages`、`bootstrap_commands`、镜像源覆盖等。
2. 引入 `script_specs`，给每个脚本声明 `runtime`、`argument_names`、`args_schema`、`examples`、`artifacts`、`environment`。
3. parser 增加了旧字段兼容逻辑，把历史字段自动归并到新结构里。
4. validator 增加了对 runtime requirements 和 script specs 的结构校验，避免 skill 元数据看起来可用但实际不可执行。
5. `run_skill_script` 参数归一化增强，兼容 `skill/script` 别名、嵌套 `args.input`、`script_input` 等不同调用形态。
6. execution 结果里新增 `resolved_artifact_paths`、`applied_defaults`、`failure_category`、`retry_suggestions`，为后续失败诊断做准备。

为什么要做这些事：

1. 之前 skill 脚本的调用主要靠 prompt 猜参数，稳定性不够。
2. 之前依赖安装方式分散且不结构化，不利于 sandbox bootstrap。
3. 对 `.pptx` 这类真实文件交付来说，只知道“调用了 skill”不够，系统必须知道脚本需要什么、会产出什么、失败后如何自省。

### 2.2 prompt 和 agent/tool 调用规则被重新收紧

涉及文件：

1. `swarmmind/prompt_template/execution.py`
2. `swarmmind/prompt_template/__init__.py`
3. `swarmmind/agents/omni_agent.py`
4. `swarmmind/agents/omni_runner.py`
5. `tests/test_prompt_templates.py`
6. `tests/test_omni_agent.py`
7. `tests/test_tool_registry.py`

这部分实际做的事情：

1. 执行 prompt 不再只给 skill 名称，而是增加 `selected_skill_context_json`，把选中 skill 的关键执行信息注入 prompt。
2. prompt 明确收紧 `run_skill_script` 规则，强调只能调用已声明脚本，不能把内联源码塞进 `script`。
3. 新增 `EXECUTION_SANDBOX_COMMAND_PROMPT`，给 sandbox 子任务单独生成“严格 JSON 命令”提示词，而不是混在普通 Markdown 交付 prompt 里。
4. OmniAgent 对 tool argument 的提取与兼容处理更健壮，能够接受 JSON string、`input` 别名等变体。
5. tool registry 测试更新，保证 `script_input` 这类新字段出现在工具参数 schema 中。

为什么要做这些事：

1. 之前 agent 很容易在 skill 选择和脚本调用上走歪，要么臆造脚本名，要么只写摘要不真正产出文件。
2. materialized output 场景要求 agent 严格执行真实命令和 skill，而不是“口头说完成”。
3. sandbox command planning 和普通内容生成本质上不是一个输出协议，需要拆 prompt。

### 2.3 execution runner 被改造成更偏“真实文件优先”的执行流

涉及文件：

1. `swarmmind/orchestration/execution_runner.py`
2. `swarmmind/defaults.py`
3. `swarmmind/sandbox/profiles.py`
4. `tests/test_v2_execution_flow.py`

这部分实际做的事情：

1. execution runner 引入 `EXECUTION_SANDBOX_COMMAND_PROMPT`，把 sandbox command plan 变成显式步骤。
2. 对 `.pptx`、`.pdf`、`.docx`、`.xlsx` 这类 materialized output 做了更强的识别，避免直接把这类任务降级成普通 inline summary。
3. 当子任务目标是需要真实文件且存在对应 skill profile 时，执行流更偏向 omni-agent + `run_skill_script` 路线，而不是普通 sandbox command 路线。
4. 运行时默认镜像源常量被引入 defaults。
5. sandbox profile 默认超时从原来的较短值提升到 30 分钟，避免较慢的依赖安装或 Office/PPT 生成任务中途超时。

为什么要做这些事：

1. 当前主问题就是“系统以为交付的是文件，但 agent 其实只给了摘要”或“文件生成了但执行链路没有按真实文件处理”。
2. PPT 生成这类任务往往需要较长 bootstrap 和 I/O，短超时容易制造假失败。
3. 真实文件交付必须在 orchestration 层被当成一等公民处理，而不是附属能力。

### 2.4 OpenSandbox 读取二进制 artifact 的链路被修正

涉及文件：

1. `swarmmind/sandbox/opensandbox_adapter.py`
2. `swarmmind/skill_system/executor.py`
3. `swarmmind/skill_system/service.py`
4. `tests/test_infra_selection.py`
5. `tests/test_skill_execution_service.py`

这部分实际做的事情：

1. `OpenSandboxAdapter.read_file()` 在 `encoding=None` 时，不再只走旧式 `read_file()`，而是优先尝试 SDK 的 `read_bytes()`。
2. 兼容旧接口：如果 SDK 没有 `read_bytes()`，才回退到 legacy 行为。
3. executor 在 artifact 收集失败时增加 warning 日志，不再无声吞掉读取异常。
4. service 在 `artifact.created` 事件里增加 `download_url`，让产物一创建就带上下载地址。
5. 二进制 `.pptx` artifact 持久化路径配套测试得到补强。

为什么要做这些事：

1. 这正是本次 PPT 问题的直接根因之一：容器内文件已经生成，但系统没有正确把二进制内容从 sandbox 拉回。
2. 如果读取异常被静默吞掉，系统只会暴露 `missing_artifacts`，但定位不到是路径问题、SDK 调用问题还是内容问题。
3. 文件一旦真正进入 artifact repository，就应该立刻能被 API 层和 replay 层消费，不应再靠上层二次拼接链接。

### 2.5 PPT skill 本身被补成“可从零生成演示文稿”的能力包

涉及文件：

1. `swarmmind/skills/pptx/SKILL.md`
2. `swarmmind/skills/pptx/scripts/create_presentation.py`
3. `tests/test_pptx_skill.py`
4. `tests/test_skill_system.py`

这部分实际做的事情：

1. 给 `pptx` skill 增加 `runtime_requirements`，补齐 `python-pptx`、`markitdown[pptx]`、`Pillow`、`defusedxml` 等依赖声明。
2. 给 `pptx` skill 增加多个 `script_specs`，包括 `create_presentation.py`、`add_slide.py`、`office/unpack.py`、`office/pack.py`。
3. 新增 `create_presentation.py`，允许直接根据 `deck_spec + output_file` 生成一个完整 `.pptx`，不再强依赖“先有模板/先解包再回打包”。
4. 对 pptx skill 元数据和新脚本增加单测覆盖。

为什么要做这些事：

1. 之前的 PPT 路径更偏“编辑已有 PPTX”工具链，不够适合从纯结构化数据直接起一份新演示文稿。
2. 当前任务就是从研究结果直接生成黄金投资建议 PPT，所以需要明确的 from-scratch 创建脚本。
3. 只有把创建脚本纳入 skill metadata，agent 才能稳定找到并调用它。

### 2.6 为调试和本地验证增加了若干辅助脚本/文件

涉及文件：

1. `scripts/submit_task.py`
2. `scripts/execute_task.py`
3. `scripts/group_artifacts_by_subtask.py`
4. `a.json`
5. `exec_prompt.md`
6. `output/黄金投资建议.pptx`

这部分实际做的事情：

1. `submit_task.py` 增强了任务/子任务/artifact 进度输出，便于看运行时到底发生了什么。
2. 新增 `execute_task.py`，用于本地提交任务并轮询运行结果。
3. 新增 `group_artifacts_by_subtask.py`，用于离线整理 artifact trace。
4. `a.json`、`exec_prompt.md` 明显是一次具体运行的输入/输出/复盘数据。
5. `output/黄金投资建议.pptx` 是本次任务产生的真实演示文稿文件。

为什么要做这些事：

1. 当前问题排查高度依赖 replay、artifact trace 和 prompt 输入复盘，单靠 API 结果不够。
2. 这些脚本和文件对调试很有用，但并不天然等于应该进入最终主线提交。

## 3. 当前未提交改动按“是否建议进入 push”来分组

### 3.1 倾向建议保留审阅并进入正式提交的部分

以下改动与当前 skill/sandbox/PPT 真实文件交付主线直接相关：

1. `swarmmind/skill_system/models.py`
2. `swarmmind/skill_system/parser.py`
3. `swarmmind/skill_system/validator.py`
4. `swarmmind/skill_system/service.py`
5. `swarmmind/skill_system/executor.py`
6. `swarmmind/tools/builtin/skill.py`
7. `swarmmind/orchestration/execution_runner.py`
8. `swarmmind/prompt_template/__init__.py`
9. `swarmmind/prompt_template/execution.py`
10. `swarmmind/sandbox/opensandbox_adapter.py`
11. `swarmmind/sandbox/profiles.py`
12. `swarmmind/defaults.py`
13. `swarmmind/skills/pptx/SKILL.md`
14. `swarmmind/skills/pptx/scripts/create_presentation.py`
15. 与上述功能直接相关的测试文件

原因：

1. 这些文件组成了从 skill 声明、prompt 注入、agent 调用、sandbox 执行、artifact 读取、artifact 持久化到测试覆盖的完整链路。
2. 当前问题的根因和修复主线都在这里。

### 3.2 需要单独判断是否保留的部分

以下改动可能有价值，但更像“辅助性支撑”，需要看你是否想一起 push：

1. `scripts/submit_task.py`
2. `scripts/execute_task.py`
3. `scripts/group_artifacts_by_subtask.py`
4. `docs/design/skill/skill-system-design.md`
5. `docs/design/skill/skill-authoring-guide.md`

原因：

1. 它们不是主修复路径的一部分，但对后续开发、联调和团队理解有帮助。
2. 如果你想保持这次提交足够聚焦，可以把这些拆到后续单独 commit。

### 3.3 明显建议不要直接一起 push 的部分

以下文件更像本地调试或运行产物，不建议直接混入主提交：

1. `a.json`
2. `exec_prompt.md`
3. `output/黄金投资建议.pptx`

原因：

1. 它们是某次具体运行的快照或产物，不是稳定源码。
2. 会把一次调试上下文固化进仓库，污染主线历史。
3. 尤其是二进制 `.pptx` 文件体积大、审阅成本高，除非本次需求明确要求把样例产物入库，否则不建议进入源码提交。


## 4. 当前这批代码为什么值得审阅，而不是直接 push

### 4.1 这不是一个纯 bugfix 小补丁

当前改动不只是修一个 OpenSandbox 读取二进制的问题，还顺带引入了：

1. skill 元数据模型升级。
2. prompt 合约变化。
3. execution runner 行为变化。
4. 新 PPT 生成脚本。
5. 一批测试与文档。

这意味着它的收益很大，但 blast radius 也明显大于单点修复。

### 4.2 当前工作树是“多主题混合态”

至少混在一起的主题包括：

1. skill runtime/contracts 升级。
2. materialized output orchestration 调整。
3. OpenSandbox 二进制读取修复。
4. 本地调试脚本与运行产物。
5. 可能来自其他议题的文档。

如果直接 push，会让后续回滚、定位问题、做 PR review 都更困难。

## 5. 我对这次 push 前整理的建议

### 方案 A：按主线能力拆成 2 到 3 个 commit

建议拆法：

1. `skill contract/runtime`：`models/parser/validator/service/executor/tool/skill` + prompt 的结构化调用支持。
2. `pptx materialized output`：`execution_runner`、`opensandbox_adapter`、`pptx skill`、相关测试。
3. `docs and utilities`：设计文档、authoring guide、调试脚本。

优点：

1. review 更清楚。
2. 如果其中一层出问题，更容易回滚。

### 方案 B：只保留本次问题主线，其余先不 push

如果你现在只想先把“PPT 真文件能落 artifact”推进去，建议只保留：

1. `swarmmind/sandbox/opensandbox_adapter.py`
2. `swarmmind/skill_system/service.py`
3. `swarmmind/skill_system/executor.py`
4. `swarmmind/skills/pptx/SKILL.md`
5. `swarmmind/skills/pptx/scripts/create_presentation.py`
6. 直接相关测试

同时先排除：

1. `a.json`
2. `exec_prompt.md`
3. `output/黄金投资建议.pptx`
4. 无关文档和脚本

优点：

1. 提交更聚焦当前 bug。
2. 风险更小。

## 6. 当前审阅结论

基于当前状态，我的判断是：

1. 当前工作树里确实包含对主问题有价值的代码，不是纯调试噪音。
2. 但当前状态还不适合“整包直接 push”，因为混入了明显的调试产物、辅助脚本和至少一个疑似无关文档主题。
3. 更合理的做法是先按“主线修复 / 辅助文档工具 / 运行产物”拆开，再决定哪些进入本次 push。

如果你认可这个判断，下一步更合适的是：

1. 先确定哪些文件属于本次必须提交的主线。
2. 把调试产物和无关文件排除出去。
3. 再做一次针对保留文件集合的最终审阅。