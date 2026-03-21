# SwarmMind LLM 使用现状与硬编码逻辑审计

> 目的：回答“当前哪些地方真正用了 LLM，哪些地方仍是规则/死逻辑”，并给出优先改造建议。
>
> 时间：2026-03-15

---

## 1. 结论摘要

1. **任务拆解（Planner）目前没有用 LLM**，是固定规则生成子任务。
2. **LLM 当前主要用于子任务内容生成**（ExecutionRunner 中的 markdown 产物文本）。
3. 执行命令仍是固定模板（`python3 -c` + 写 `outputs/*.md`），不是根据任务动态生成可运行工程代码。
4. 如果你希望“核心能力依赖 LLM”，第一优先级应改造 `Planner.plan()`，其次改造 `ExecutionRunner._build_command_request()`。

---

## 2. 当前已使用 LLM 的位置

## 2.1 子任务内容生成（已接通）

代码位置：

- `swarmmind/orchestration/execution_runner.py`
  - `_render_subtask_content_with_model()`
  - `_compose_subtask_prompt()`

行为：

1. 当存在模型配置（`model_name` + `api_key/base_url`）时，创建 AgentScope agent。
2. 使用 prompt 让模型返回单个子任务的 markdown 输出。
3. 返回内容写入 sandbox 中 `outputs/<subtask>.md` 并作为 artifact 证据。

## 2.2 模型客户端工厂（已接通）

代码位置：

- `swarmmind/agents/factory.py`

行为：

1. 通过 `OpenAIChatModel` 创建模型客户端。
2. 使用配置项注入 `model_name/temperature/max_tokens/base_url/api_key`。

---

## 3. 当前硬编码 / 死逻辑清单

## 3.1 任务拆解是固定分支（优先级最高）

代码位置：

- `swarmmind/orchestration/planner.py`

硬编码点：

1. 固定添加 `analyze-requirement`。
2. 固定添加 `prepare-implementation`。
3. 仅通过 `if "test" in goal` / `if "验证" in task.goal` 决定是否添加 `verify-result`。
4. 子任务的 `role/preferred_skill/required_tool_groups/acceptance_criteria` 都是内置常量或简化规则。

影响：

1. 无法根据真实任务复杂度拆分 DAG。
2. 对多语言、多阶段、多依赖任务表达能力弱。

## 3.2 执行命令是固定脚本模板

代码位置：

- `swarmmind/orchestration/execution_runner.py` 的 `_build_command_request()`

硬编码点：

1. 无论任务内容是什么，最终命令都是 `python3 -c '...'`。
2. 固定写 markdown 到 `outputs`。
3. `force_fail_subtask` 也是显式测试分支，不是策略层能力。

影响：

1. “写一个贪吃蛇”这类任务不会自动产出项目代码结构，只会产出计划/说明文档。
2. 工具链（构建、测试、修复）尚未被真实编排。

## 3.3 LLM 调用有静态模板回退

代码位置：

- `swarmmind/orchestration/execution_runner.py` 的 `_render_subtask_content_template()`

硬编码点：

1. 模型异常或不可用时直接回落到固定 markdown 模板。
2. 回退模板中内容结构完全固定。

影响：

1. 可用性高，但智能度低。
2. 会掩盖“实际上未调用 LLM”的事实，需要显式埋点区分。

## 3.4 调度/分配仍是最小规则实现（非 LLM）

代码位置：

- `swarmmind/orchestration/scheduler.py`
- `swarmmind/orchestration/coordinator.py`

硬编码点：

1. Scheduler 仅按依赖状态判断 ready，不做成本、优先级、并发预算等策略。
2. Coordinator 只是把现有字段写入 `execution_profile`，不做智能选型。

---

## 4. 建议改造优先级（从“必须”到“增强”）

P0（必须）：

1. **LLM Planner 化**：`Planner.plan()` 改为“prompt -> 结构化 JSON DAG 输出 -> schema 校验 -> 回退规则”。
2. 明确记录 `plan_source`：`llm` 或 `rule_fallback`，写入 `subtask.metadata`。

P1（建议）：

1. 执行命令从“固定 `python3 -c` 模板”升级为“LLM 生成执行计划 + 工具白名单执行器”。
2. 增加失败自修复循环（最多 N 次）。

P2（增强）：

1. 用 LLM 辅助调度（优先级、并行度、sandbox profile 选择）。
2. 引入评分器/审查器对 LLM 计划进行规则校验和风险拦截。

---

## 5. 提示词模板落地说明

本次已新增独立目录：

- `swarmmind/prompt_template/`

用于统一存放：

1. `planning`（任务拆解）
2. `execution`（子任务执行）
3. `review`（结果验证）

说明：

1. 当前代码中的 prompt 还未全部改为“文件加载模式”，但模板已沉淀，后续可按目录逐步接线。

---

## 6. 下一步建议（可直接执行）

1. 先改 `Planner`：实现 `LLM -> JSON DAG` 的最小可用版本，保留规则回退。
2. 给每次 plan 落地 `metadata.plan_source/model/version/prompt_version`。
3. 增加一个回归任务：输入“写一个 python 贪吃蛇并附测试”，验证 subtasks 数量、依赖和角色是否明显优于固定规则。
