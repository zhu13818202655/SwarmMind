# SwarmMind 子任务运行时与能力模型对齐实现总结

> 本文档记录 Issue #5 / PR #6 对 `subtask / strategy / skill / tool / runtime / agent` 职责边界对齐所完成的实际改动，用来回答三个问题：
>
> 1. 这次代码层到底改了什么。
> 2. 哪些设计目标已经进入主链路。
> 3. 哪些设计目标仍然只是部分落地。

关联文档：

- [docs/design/v2/009-subtask-runtime-and-capability-model-design.md](/home/admin2/proj/SwarmMind/docs/design/v2/009-subtask-runtime-and-capability-model-design.md)
- [docs/design/v2/002-task-execution-system-implementation-status.md](/home/admin2/proj/SwarmMind/docs/design/v2/002-task-execution-system-implementation-status.md)
- [docs/design/v2/004-task-execution-remediation-todo.md](/home/admin2/proj/SwarmMind/docs/design/v2/004-task-execution-remediation-todo.md)
- [tests/test_runtime_resolution.py](/home/admin2/proj/SwarmMind/tests/test_runtime_resolution.py)
- [tests/test_v2_execution_flow.py](/home/admin2/proj/SwarmMind/tests/test_v2_execution_flow.py)

---

## 1. 一句话结论

这次改动已经把 `runtime` 从 `strategy` 的隐式副作用中拆出来，形成了一个真正进入执行主链的最小实现：

1. `SubTask` 能显式声明候选 runtime 和偏好 skill。
2. `Coordinator` 会解析出唯一的 `resolved_runtime_kind`。
3. `ExecutionRunner` 会按解析后的 runtime 分流执行，而不是继续主要依赖 strategy 推断执行后端。
4. 审计和回放中已经能看到 runtime 解析结果、原因和 fallback 链。

但这次还没有把设计文档中的所有目标态一次性做完。

更准确地说，当前状态是：

1. 规划层字段已经到位。
2. 运行时解析入口已经统一。
3. 执行器分流已经开始按 runtime 生效。
4. `browser_automation` 和独立 `ExecutionAttempt` 持久化仍然没有完全落地。

---

## 2. 本次实现范围

本次实现围绕 009 文档定义的三层模型做了最小闭环改造。

### 2.1 控制面

在 `SubTask` 上新增并接通了：

1. `candidate_runtime_kinds`
2. `preferred_skill_profiles`

对应代码：

- [swarmmind/models/task.py](/home/admin2/proj/SwarmMind/swarmmind/models/task.py)
- [swarmmind/orchestration/planner.py](/home/admin2/proj/SwarmMind/swarmmind/orchestration/planner.py)

### 2.2 能力面

在能力模型里新增了显式 `RuntimeKind` 枚举，并把默认 runtime 候选和默认 skill 画像挂回 strategy profile：

1. `RuntimeKind`
2. `StrategyProfile.candidate_runtime_kinds`
3. `StrategyProfile.default_skill_profiles`
4. 新增 `presentation_delivery` strategy，并允许它绑定 `pptx` skill

对应代码：

- [swarmmind/models/capability.py](/home/admin2/proj/SwarmMind/swarmmind/models/capability.py)

### 2.3 执行面

在 `ExecutionProfile` 上新增并接通了：

1. `candidate_runtime_kinds`
2. `resolved_runtime_kind`
3. `runtime_resolution_reason`
4. `runtime_fallback_chain`
5. `preferred_skill_profiles`

对应代码：

- [swarmmind/models/execution.py](/home/admin2/proj/SwarmMind/swarmmind/models/execution.py)

---

## 3. 已完成的核心改动

## 3.1 `RuntimeKind` 已经成为一等模型字段

这次不再只在文档里讨论 runtime taxonomy，而是已经在代码里定义为显式枚举：

1. `llm_only`
2. `host_tools`
3. `sandbox`
4. `browser_automation`
5. `agent_backed`

这意味着后续不需要继续用 “某个 strategy 看起来像 sandbox” 这种隐式语义来表达执行后端。

---

## 3.2 `SubTask` 已能表达候选 runtime 和偏好 skill

这次改动后，planner 与规则 fallback 产出的 subtask 已经不再只有：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`

而是进一步具备：

1. `candidate_runtime_kinds`
2. `preferred_skill_profiles`

这一步的意义是：

1. planner 终于可以表达“一个 subtask 有多个候选 runtime”。
2. `skill` 不再被迫退化成和 strategy 同名的别名。

当前规则 planner 中已经做了第一轮默认值绑定：

1. `task_planning` 默认 `llm_only -> host_tools`
2. `build_app` 默认 `sandbox -> host_tools`
3. `review` 默认 `llm_only -> host_tools`
4. `verification` 当前默认 `host_tools`

注意：这里的 `verification` 目前仍然走验证专用逻辑，不是一个完全通用的 host-tools executor。

---

## 3.3 `Coordinator` 已成为 runtime resolution 的唯一入口

这是本次最关键的主链改动。

改动前：

1. `preferred_strategy` 容易一路被执行层直接拿来当 runtime selector。
2. sandbox profile 也容易在 strategy 语义下被隐式带出。

改动后：

1. `Coordinator.assign()` 会先解析 `effective_strategy`
2. 再解析 `candidate_runtime_kinds`
3. 再解析 `preferred_skill_profiles`
4. 然后生成唯一的：
   - `resolved_runtime_kind`
   - `runtime_resolution_reason`
   - `runtime_fallback_chain`
5. `sandbox_profile` 只会在 `resolved_runtime_kind == sandbox` 时才真正下沉

这一步意味着：

1. runtime resolution 已经有统一入口。
2. planner、runner、repair 链不再各自偷偷做一套 runtime 推断。

---

## 3.4 `ExecutionRunner` 已按 resolved runtime 分流

这是本次把模型真正接到执行层的地方。

改动后，`ExecutionRunner` 的执行选择逻辑变成：

1. `verification` / `review` 继续进入验证与审查专用逻辑
2. `resolved_runtime_kind == sandbox` 进入 sandbox 执行链
3. `resolved_runtime_kind == agent_backed` 进入 agent-backed 执行链
4. 其他 runtime 进入新的 inline runtime 执行链

这意味着：

1. 不是所有非 review / verification 任务都默认进 sandbox。
2. `llm_only` 与 `host_tools` 已经能走非 sandbox 路径完成执行。

当前 inline runtime 的第一版实现仍然偏简单：

1. 它会渲染 subtask 内容
2. 产出 inline artifact
3. 写回 `runtime_kind`

也就是说，它已经足够支撑规划、写作、轻量研究类任务不必默认起 sandbox，但还不是一个高度丰富的 host-tools runtime。

---

## 3.5 审计字段已经写入 subtask metadata 和事件流

这次不仅改了模型，也把运行时解析信息放进了执行证据里。

当前已经能在 `subtask.metadata` 中看到：

1. `resolved_strategy_name`
2. `resolved_runtime_kind`
3. `runtime_resolution_reason`
4. `runtime_fallback_chain`
5. `selected_tools`
6. `execution_profile`

同时 `strategy.started` 事件也会带上：

1. runtime 解析结果
2. 解析原因
3. fallback 链

这使得 replay 和调试时终于可以回答：

1. 这个 subtask 候选 runtime 是什么
2. 为什么最终选择了当前 runtime
3. 实际拿到了哪些工具

---

## 3.6 `presentation_delivery + pptx` 已成为明确的非同名绑定示例

本次实现补了一个非常关键的建模信号：

1. 新增 `presentation_delivery` strategy
2. 它的默认 skill 画像是 `pptx`

这件事本身就证明了：

1. strategy 和 skill 已经不是强制同名关系
2. `pptx` 可以作为能力包挂到 presentation workflow 之下

这正是 009 文档里强调的边界拆分方向。

---

## 3.7 repair / rework 链已经带上新的 runtime 元数据

本次没有只改主 planner 输出，还把 repair / rework 生成的子任务也一起对齐了。

也就是说：

1. review 触发 rework 时，新生成的 repair subtasks 会保留候选 runtime 和 skill 偏好
2. failure repair 链也会带上同样的 runtime 元数据

这一点很重要，因为如果只改首轮 subtask，不改 repair 链，系统会在重试路径上重新退回旧语义。

---

## 4. 测试与验证

本次实现完成后，至少做了三层验证。

## 4.1 planner 与字段归一化测试

已验证：

1. planner prompt 已包含 `candidate_runtime_kinds` 和 `preferred_skill_profiles`
2. 规则 fallback 能为 coding 场景补默认 runtime 候选和默认 skill 画像
3. 无效 tool group 回退时，新的 runtime 字段也会一起回退

对应测试：

- [tests/test_planner_llm_fallback.py](/home/admin2/proj/SwarmMind/tests/test_planner_llm_fallback.py)

## 4.2 runtime resolution 单元测试

已验证两个典型场景：

1. `presentation_delivery` 会绑定 `pptx` skill，并优先解析到 `host_tools`
2. research 类场景可声明 `browser_automation -> host_tools`，当前实现会显式记录 fallback 到 `host_tools`

对应测试：

- [tests/test_runtime_resolution.py](/home/admin2/proj/SwarmMind/tests/test_runtime_resolution.py)

## 4.3 执行主链与回放测试

已验证：

1. coding 主任务仍然会解析到 `sandbox`
2. 执行结果中能看到 `resolved_runtime_kind`
3. repair / rework 链仍然正常
4. replay 主链没有因为新字段而断裂

对应测试：

- [tests/test_v2_execution_flow.py](/home/admin2/proj/SwarmMind/tests/test_v2_execution_flow.py)

## 4.4 本地端到端验证

实际运行过一次真实提交：

1. 启动本地 API
2. 提交“实现一个导出 Excel 功能并补测试”
3. 轮询到 run `succeeded`
4. 返回的 run detail 中已看到：
   - `candidate_runtime_kinds`
   - `resolved_runtime_kind`
   - `runtime_resolution_reason`
   - `runtime_fallback_chain`

验证时需要显式设置：

1. `OPEN_SANDBOX_BASE_URL=http://127.0.0.1:45698`

原因不是这次 runtime 对齐改动本身，而是当前环境里的 sandbox 配置解析会把 `base_url` 解析成 `null`，这是一个独立配置问题。

---

## 5. 这次没有完成的部分

本次实现虽然已经把模型接进主链，但仍然保留了几个明显的未完成点。

## 5.1 `browser_automation` 仍然只是显式候选，不是独立执行器

当前系统已经能：

1. 声明 `browser_automation` 为 candidate runtime
2. 在 resolution reason 里记录为什么 fallback 到 `host_tools`

但当前还没有：

1. 真正的 `browser_automation` executor
2. 独立的 browser runtime backend

所以这一步目前还是“显式建模 + 审计可见”，不是“真正可执行”。

## 5.2 还没有独立的 `ExecutionAttempt` 实体持久化

目前运行时解析结果仍然主要保存在：

1. `ExecutionProfile`
2. `subtask.metadata`
3. replay 事件

还没有单独建出：

1. `ExecutionAttempt`
2. 每次 attempt 独立持久化的 runtime 记录

因此严格来说，009 文档里“规划层多对多，attempt 层一对一”的目标语义目前只完成了一半。

## 5.3 `verification` / `review` 仍然带有特化分支

当前 `ExecutionRunner` 已经按 runtime 分流，但：

1. `verification`
2. `review`

仍然优先进入特化逻辑，而不是完全由 runtime 决定执行器。

这符合当前系统的现实需要，但也说明系统还没有完全走到“所有执行都先看 runtime，strategy 只定义 workflow”的最终形态。

## 5.4 对外 API 和任务提交口径还没有完全开放这些新字段

本次主要打通了内部 planner -> coordinator -> runner 主链。

当前还没有系统化完成：

1. API 请求直接提交 `candidate_runtime_kinds`
2. 外部任务提交直接指定 `preferred_skill_profiles`
3. 查询层把这些字段做成更稳定的外部契约说明

所以这次仍然主要是“内部主链对齐”，不是“外部产品接口全面升级”。

---

## 6. 对 009 设计文档的落实情况判断

如果把 009 文档拆成三类目标，那么这次的落实情况可以归纳为：

### 已落实

1. `SubTask` 不再只依赖 `strategy + sandbox_profile` 表达执行语义
2. `candidate_runtime_kinds` 已进入规划模型
3. `resolved_runtime_kind` 已进入执行模型
4. `runtime_resolution_reason` 与 `runtime_fallback_chain` 已进入主链审计
5. `strategy` 与 `skill` 已经出现非同名绑定
6. `ExecutionRunner` 已开始按 runtime 分流

### 部分落实

1. `skill` 和 `strategy` 仍然存在兼容字段并存阶段
2. `verification` / `review` 仍然保留策略特化分支
3. `browser_automation` 目前只有建模和 fallback，没有独立 runtime 实现
4. `ExecutionAttempt` 仍未成为独立持久化模型

### 尚未落实

1. 真正的 browser automation executor
2. attempt 级 runtime 持久化实体
3. 完整的外部 API 字段开放与文档契约升级

---

## 7. 建议的下一步

如果继续沿着 009 文档推进，下一步最合理的是：

1. 引入独立 `ExecutionAttempt` 记录，把 runtime resolution 从 `subtask.metadata` 提升为真正持久化对象
2. 补一个真正的 `browser_automation` executor，而不是只在 resolution 时做 fallback 说明
3. 继续收敛 `verification` / `review` 的特化分支，明确哪些是 workflow 逻辑，哪些是 runtime 逻辑
4. 把新的 runtime / skill 字段逐步开放到外部 API 与查询契约

---

## 8. 总结

这次改动的意义不在于“又加了几个字段”，而在于它首次把 009 文档里的核心边界拆分接进了真实执行链。

当前系统已经能够明确地区分：

1. `strategy` 是 workflow 语义
2. `skill` 是能力包
3. `runtime_kind` 是执行后端
4. `agent` 只是某些 runtime 下的执行实现

从这个节点开始，后续再接 `browser_automation`、`pptx`、更细粒度 execution attempt、以及更多 workflow，都已经有了更清晰的落点，而不是继续把 strategy 当成所有事情的混合入口。