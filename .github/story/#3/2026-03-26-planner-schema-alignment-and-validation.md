# Planner 计划 Schema 对齐与校验 Story

## Story 名称

Planner 输出 schema 与运行时契约对齐，并增加显式校验与归一化可观测性。

## 背景

当前 planner 的 prompt 定义与运行时真实能力已经发生漂移，导致 LLM 可以生成“结构看起来正确、但语义上部分无效”的计划 JSON。

已知问题包括：

1. prompt 中的 `role` 与 `required_tool_groups` 枚举过时。
2. planner 可能生成不兼容的 `role`、`preferred_strategy`、`agent_profile_id` 组合。
3. 可选字段会输出空字符串，而不是 `null` 或省略。
4. 运行时会静默兜底修复这些问题，但当前缺少显式 warning 和审计信息。

当前相关实现入口主要在：

1. `swarmmind/prompt_template/planner.py`
2. `swarmmind/orchestration/planner.py`

## 问题定义

当前问题不是 planner 完全无法产出计划，而是 planner 输出与运行时契约不再严格一致。结果是：

1. LLM 的原始意图与实际执行路径可能不一致。
2. 某些非法字段会在运行时被静默修正，降低可解释性。
3. 调试时很难区分“模型规划能力问题”和“运行时容错掩盖问题”。

## 目标

1. 让 planner prompt 中的 schema 与运行时真实枚举保持一致。
2. 在 planner 构建 subtasks 前增加显式校验与归一化层。
3. 保留当前运行时 fallback 能力，但把修复过程写入 metadata 和 warning。
4. 为典型异常输入补齐测试，避免 schema 再次漂移。

## 非目标

1. 本次不重做整套 planner 架构。
2. 本次不扩展新的 agent orchestration 流程。
3. 本次不引入新的任务类型或新的执行引擎。

## 实施范围

### 1. Prompt schema 对齐

修改 `swarmmind/prompt_template/planner.py` 中的 `PLANNER_TASK_DECOMPOSITION_PROMPT`：

1. 将 `role` 枚举更新为运行时真实集合：
   - `planner|coder|tester|reviewer|researcher|writer|executor`
2. 将 `required_tool_groups` 更新为运行时真实集合：
   - `project_read|project_write|web_search|browser_read|sandbox_exec|artifact_read|memory_lookup|task_admin|mail|presentation`
3. 将 `preferred_strategy` 约束为当前已知策略：
   - `task_planning|research|build_app|verification|review|write_report|agent_backed`
4. 明确规定可选字段不可输出空字符串，必须使用 `null` 或省略。
5. 增加显式兼容性规则：
   - `role`、`preferred_strategy`、`agent_profile_id` 必须一致。
   - `write_report` 优先配 `writer`。
   - `research` 优先配 `web_search`、`browser_read`、`project_read`。
6. 在 prompt 中增加一个小型、合法、规范的 JSON 输出示例。

### 2. Planner 输出校验与归一化

在 `swarmmind/orchestration/planner.py` 中，位于 `_extract_json_payload()` 与 `_build_subtasks_from_plan()` 之间增加明确的校验/归一化流程。

建议实现要求：

1. 校验 `role` 是否属于 `AgentRole`。
2. 校验 `required_tool_groups` 是否属于 `ToolGroup`。
3. 校验 `preferred_strategy` 是否属于已知策略集合。
4. 将空字符串标准化为 `None`。
5. 对不兼容的 `agent_profile_id`、`role`、`preferred_strategy` 组合进行：
   - 显式 warning 记录；以及
   - 必要的归一化处理。
6. 保持当前系统仍可继续执行，不因为可恢复问题直接失败。

### 3. 归一化透明化

当 planner 输出被修复时，把修复信息写入 subtask metadata，例如：

1. `planner_validation_warnings`
2. `original_role`
3. `original_preferred_strategy`
4. `original_agent_profile_id`
5. `resolved_agent_profile_id`
6. `normalized_tool_groups`
7. `original_sandbox_profile`

### 4. 测试补充

补充或更新测试，覆盖至少以下场景：

1. 非法工具组 `http` 被识别并处理。
2. `writer-default` 与 `reviewer` 角色不兼容时的归一化行为。
3. `sandbox_profile` 为空字符串时的标准化行为。
4. `agent_profile_id` 省略、显式为 `null`、显式给错值时的行为。
5. 无合法工具组时，是否按角色默认工具组回退。

## 交付物

1. 更新后的 planner prompt 模板。
2. planner 输出校验/归一化实现。
3. subtask metadata 中新增的 warning / normalization 信息。
4. 对应单元测试或集成测试。
5. 一份可以说明本次修复范围的 GitHub issue。

## 验收标准

1. planner prompt 中的 schema 与当前运行时代码定义一致。
2. planner 面对非法枚举值时，不会无声吞掉问题，至少会在 metadata 中保留 warning。
3. `writer-default + reviewer + write_report` 这类冲突输入会被稳定归一化，并留下原始值与修复值。
4. `sandbox_profile=""` 不再以空字符串进入 subtask，统一转换为 `None` 或任务默认 profile。
5. 测试覆盖上述关键场景，并在本地通过。

## 风险与注意事项

1. 如果策略集合在别处还有隐式定义，需要统一来源，避免 prompt 与代码再次漂移。
2. 若校验过于严格，可能会影响当前依赖宽松容错的任务流；因此本次应以“记录 warning + 可恢复归一化”为主。
3. metadata 字段增加后，要注意下游序列化与日志展示是否兼容。

## 建议实施顺序

1. 先改 prompt schema 和示例。
2. 再加 planner 输出校验/归一化层。
3. 然后补 metadata warning。
4. 最后补测试并用一个真实 planner 样例回归验证。

---

## GitHub Issue 模板

以下内容可直接复制为 GitHub issue：

```md
## Title

Planner 输出 schema 与运行时契约对齐，并增加显式校验与归一化记录

## Background

当前 planner prompt 与运行时真实 schema 已发生漂移，导致 LLM 能生成结构合法但语义不完全合法的计划 JSON。运行时虽然会做兜底修复，但当前缺少显式 warning 和审计信息，影响可解释性与调试效率。

## Problem

已观察到以下问题：

1. `required_tool_groups` 仍可能生成非法值，如 `http`
2. `agent_profile_id`、`role`、`preferred_strategy` 可能互相冲突
3. `sandbox_profile` 可能输出空字符串
4. 运行时存在静默归一化，当前缺少可观测记录

## Scope

本次 issue 处理以下内容：

1. 更新 planner prompt schema，使其与运行时真实枚举一致
2. 在 planner 中增加输出校验/归一化层
3. 在 subtask metadata 中记录 planner warning 和归一化结果
4. 增加覆盖典型异常输入的测试

## Implementation Checklist

- [ ] 更新 `swarmmind/prompt_template/planner.py` 中的 planner task decomposition prompt
- [ ] 增加合法的 role / tool group / strategy 枚举与兼容性规则
- [ ] 在 prompt 中加入一个规范 JSON 输出示例
- [ ] 在 `swarmmind/orchestration/planner.py` 中增加 planner 输出校验与归一化逻辑
- [ ] 将空字符串标准化为 `None`
- [ ] 为非法工具组、角色/profile 冲突、空字符串 sandbox profile 增加 warning
- [ ] 将 warning 和归一化结果写入 subtask metadata
- [ ] 增加或更新测试用例

## Acceptance Criteria

1. planner prompt schema 与运行时一致
2. 非法 `required_tool_groups` 不会静默丢失，metadata 中可看到 warning
3. 不兼容的 `role` / `preferred_strategy` / `agent_profile_id` 会被稳定归一化，并记录原始值与最终值
4. `sandbox_profile=""` 不会原样进入 subtask
5. 测试通过，覆盖至少 `http`、`writer-default + reviewer`、空字符串 `sandbox_profile`、`agent_profile_id` 省略/错误值 场景

## Risks / Notes

1. 需要确认运行时真实策略集合的唯一来源，避免再次漂移
2. 归一化逻辑应优先“保运行 + 记 warning”，不要轻易把可恢复问题升级为 hard failure
3. 如果 metadata 结构发生变化，需要同步检查日志与下游消费逻辑

## Test Plan

1. 运行 planner 相关测试
2. 增加针对非法 planner JSON 的单元测试
3. 用一个真实目标样例验证 planner 生成、归一化和 metadata 输出
```