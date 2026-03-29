# Role-Driven OmniAgent 重构方案与 Story 拆分

## 目标

基于当前代码现状，回答 `.github/story/#7/req.md` 中提出的五类问题：

1. 目前判断是否成立。
2. 哪些点可以直接重构，哪些点需要渐进迁移。
3. 是否需要引入新的 `OmniAgent`。
4. planner / coordinator / execution runner / verifier / replay 应如何收敛。
5. 如何拆成可落地的 stories。

---

## 一、现状校验

先给结论：`req.md` 里对当前项目的几个核心判断，大部分是成立的，而且已经能从现有代码直接验证。

### 1. strategy/runtime/profile 仍然深度耦合

这个判断成立。

当前证据：

1. `swarmmind/orchestration/planner.py` 仍然要求 planner 输出 `preferred_strategy`、`candidate_runtime_kinds`、`preferred_skill_profiles`。
2. `swarmmind/prompt_template/planner.py` 仍然把 `preferred_strategy` 作为 planner 输出 JSON 的显式字段。
3. `swarmmind/orchestration/coordinator.py` 的 `assign()` 仍然会根据 role、strategy、runtime、skill profile 组合出 `ExecutionProfile`。
4. `swarmmind/models/execution.py` 的 `ExecutionProfile` 仍然保留 `preferred_strategy`、`candidate_runtime_kinds`、`resolved_runtime_kind`、`runtime_fallback_chain` 等字段。
5. `swarmmind/orchestration/task_orchestrator.py` 在 repair / review 衍生子任务时仍然会写死 `preferred_strategy="verification"`、`preferred_strategy="review"`。

结论：当前系统不是“role 主导执行”，而是“role + strategy + runtime kind + tool group + skill profile 混合驱动执行”。

### 2. `_execute_validation_subtask()` 不是 LLM verifier

这个判断成立。

当前 `swarmmind/orchestration/execution_runner.py` 中的 `_execute_validation_subtask()` 不是通过 `ReActAgent` 做验证，而是：

1. 读取依赖 subtask。
2. 读取 artifact。
3. 基于规则构造 `VerificationResult` 或 `ReviewDecision`。

这说明它更接近“规则化 verifier / reviewer”，而不是“具备工具调用能力的验证 agent”。

### 3. `_execute_agent_backed_subtask()` 和 `_execute_inline_runtime_subtask()` 已经部分同构

这个判断基本成立。

这两个分支虽然外层包装不同，但最终都会落到 `_render_subtask_content_with_model()`，而该方法内部会：

1. 创建 `AgentFactory`。
2. 创建 `Toolkit`。
3. 构造 `ReActAgent`。
4. 发送 prompt。
5. 接收 handoff / completion 输出。

所以从“LLM 主导执行”视角看，这两条链已经有共同内核，只是输入上下文、可用工具、fallback 和结果包装不同。

### 4. `_execute_sandbox_subtask()` 仍然是命令式执行分支

这个判断成立。

当前 sandbox 分支的核心是：

1. 申请 sandbox lease。
2. 组装命令请求。
3. 执行命令。
4. 采集 stdout/stderr/exit code/artifact。
5. 发布 sandbox 相关事件。

它现在不是一个 agent 在“推理后调用 sandbox 工具”，而是一套硬编码执行流程。也就是说，sandbox 目前是一个 executor branch，而不是一个统一 agent runtime。

### 5. 当前 toolkit/skill 扩展比原生 AgentScope 更复杂

这个判断成立，而且这是你提出 `OmniAgent` 的关键背景。

从 `swarmmind/agents/factory.py` 和 `swarmmind/agents/agent_skill.py` 可以确认：

1. 项目里的 skill 不只是 prompt 说明。
2. 项目还引入了 `skill_profiles`。
3. `create_toolkit()` 会自动注入 skill 相关文件工具。
4. 项目还存在 `SkillExecutionService` 和脚本执行链路。

这已经超出了 AgentScope 原生 `agent skill` 的能力边界。原生 `Toolkit` 更偏向：

1. tool function
2. MCP client
3. skill prompt 注入

但并不天然负责“skill 脚本生命周期 + 产物管理 + 事件审计 + sandbox 绑定”。

### 6. replay 骨架已经有，但默认 durable persistence 不足

这个判断成立。

当前证据：

1. `swarmmind/sandbox/replay_recorder.py` 已经会把事件追加到 replay timeline。
2. `swarmmind/api/server.py` 已经暴露 `/v1/runs/{run_id}`、`/v1/runs/{run_id}/events`、`/v1/runs/{run_id}/stream`。
3. `swarmmind/app/container.py` 默认 `_build_repositories()` 返回的是 `InMemory*Repository`。
4. `swarmmind/repositories/in_memory/__init__.py` 中 replay/artifact/task/run/subtask 默认都只是进程内存级存储。

结论：系统并不是没有 replay 模型，而是默认运行模式下 replay 记录不 durable，调试价值被严重削弱。

### 7. 当前 role 粒度偏粗

这个判断成立。

`swarmmind/models/capability.py` 当前角色集合仍然是：

1. planner
2. coordinator
3. researcher
4. executor
5. coder
6. tester
7. reviewer
8. writer

这里至少有两个明显问题：

1. `tester` 和 `reviewer` 的输入输出契约不够清晰。
2. `executor` 这种 role 语义过于泛化，容易成为兜底桶。

所以你提出把 verifier、tester、reviewer、designer、integrator 等区分出来，是合理的方向。

---

## 二、对你核心问题的直接回答

### 1. 目前这些 `_execute_agent_backed_subtask` 是否“已经可以完成”你想要的方向

只能说“部分可以”，不能说“已经完成”。

它们目前已经具备以下基础：

1. 以 `ReActAgent` 为核心进行推理和工具调用。
2. 可以根据不同 profile / toolkit / prompt 形成不同执行风格。
3. 已经能作为统一 agent executor 的雏形。

但它们还缺少你真正想要的几个关键能力：

1. 不能把 validation/review 真正纳入同一个 agent 执行框架。
2. 不能把 sandbox 作为 agent runtime 内部的一组 sandbox-aware tools 来使用。
3. skill 执行能力没有原生融进 agent 推理循环，只是外挂式扩展。
4. role 还不是一等配置对象，strategy/runtime 仍然在主导执行分流。

所以更准确的结论是：

当前 `_execute_agent_backed_subtask()` 和 `_execute_inline_runtime_subtask()` 可以作为未来统一执行器的基础，但还不足以直接支撑你的目标态。

### 2. 是否应该直接新写一个 `OmniAgent`

我认为应该做，但不建议第一步就直接 fork 整个 AgentScope `ReActAgent`。

更稳妥的演进方式是两阶段：

#### 第一阶段：先做 SwarmMind 自己的 agent runtime wrapper

先引入一个项目内的 `OmniAgent` 抽象，职责是：

1. 根据 role 装配 prompt。
2. 根据 execution profile 装配 toolkit。
3. 注入 skill profiles、artifact readers、memory readers、sandbox tools。
4. 统一 structured output 解析。
5. 统一 handoff、事件、artifact、replay 记录。

这一层底层仍可复用 AgentScope `ReActAgent`，但对上层暴露的是 SwarmMind 自己的执行语义。

#### 第二阶段：如果 AgentScope 限制明显，再下沉替换 agent loop

如果后续发现以下限制无法通过 wrapper 解掉，再考虑自研循环：

1. 多步 tool 调用中的审计粒度不够。
2. sandbox session / skill session 需要更强的生命周期管理。
3. 结构化输出约束和失败恢复不足。
4. tool call policy 和权限控制无法内嵌。

这样做的好处是：

1. 保留现有可用资产。
2. 缩小第一轮改造面。
3. 不会一开始就陷入“先重写 agent 框架再说”的高风险路径。

---

## 三、建议的目标架构

我建议把整个系统从“strategy 驱动执行”收敛为“role 驱动执行，runtime 只作为执行环境选择”。

### 1. planner 的目标职责

planner 只负责生成任务 DAG 和 subtask 契约。

planner 输出建议收敛为：

1. `name`
2. `description`
3. `role`
4. `acceptance_criteria`
5. `dependencies`
6. `expected_artifacts`
7. `tool_requirements`
8. `runtime_preferences`
9. `agent_profile_id` 可选

这里建议去掉 planner 对 `preferred_strategy` 的强绑定，不再让 planner 直接决定执行分支。

### 2. coordinator 的目标职责

coordinator 只负责把 planner 的 subtask 契约解析成执行配置，不再暴露 strategy 概念。

coordinator 应只负责：

1. 基于 role 选择 role spec。
2. 基于约束、tool requirement、runtime preference 解析 execution profile。
3. 基于环境能力决定是否需要 sandbox。
4. 生成最终的 `AssignedExecution`。

建议把 `ExecutionProfile` 改造成更贴近执行事实的模型，例如：

1. `role`
2. `resolved_runtime_kind`
3. `runtime_resolution_reason`
4. `runtime_fallback_chain`
5. `tool_allowlist`
6. `skill_profiles`
7. `sandbox_profile`
8. `output_schema`
9. `prompt_profile`

### 3. execution runner 的目标职责

execution runner 只保留一个主入口，但内部可以有多个 runtime adapter。

目标形态不是“多个业务分支函数”，而是：

1. `ExecutionRunner.handle_subtask_assigned()`
2. 读取 `AssignedExecution`
3. 构造 `OmniAgentContext`
4. 调用统一的 `OmniAgent.execute(context)`
5. 按结果写 artifact / state / replay / events

注意，这不等于完全没有 runtime 分层，而是 runtime 差异从“业务分支”下沉为“agent 可用工具和环境装配差异”。

### 4. verifier / reviewer / tester 的目标职责

这里建议彻底拆开：

1. `verifier`: 验证依赖产物是否满足 AC，输出结构化 `VerificationResult`
2. `tester`: 执行功能/E2E/性能/安全等测试任务，输出结构化测试报告
3. `reviewer`: 对代码、设计、方案、文档做审查，输出结构化 `ReviewDecision`

当前系统里 verifier/reviewer/tester 有语义重叠，重构后应分开建模，而不是只在 prompt 里模糊描述。

### 5. sandbox 的目标职责

sandbox 不再是单独的“命令式 subtask executor”，而应成为统一 agent runtime 的一种环境。

也就是说，future sandbox path 应该表现为：

1. agent 推理是否要运行命令
2. 调用 `sandbox_exec`
3. 读取 `sandbox_read_file`
4. 写入 `sandbox_write_file`
5. 采集 artifact

这样 sandbox 就从“执行分支”变成“tool-backed environment”。

---

## 四、Role 模型建议

建议把当前 `AgentRole` 改造成更细的角色集。

### 推荐角色

1. `planner`
2. `researcher`
3. `designer`
4. `coder`
5. `verifier`
6. `tester`
7. `reviewer`
8. `integrator`
9. `writer`

### 当前不建议保留的 role

1. `executor`
2. `coordinator`

原因：

1. `executor` 不是稳定业务角色，而是执行系统内部概念。
2. `coordinator` 更像 orchestration service，不应该作为 planner 输出给 subtask 的业务角色。

### role 与输出契约建议

每个 role 都应绑定固定的输出契约，而不是只绑定 prompt。

例如：

1. `coder`: 代码产物 + 变更摘要 + 自测结论
2. `verifier`: `VerificationResult`
3. `tester`: `TestExecutionReport`
4. `reviewer`: `ReviewDecision`
5. `writer`: markdown / json / pptx plan 等文档产物

这样 planner 输出 role 后，execution 层才能稳定地推导 prompt、工具权限、artifact schema 和 replay 记录方式。

---

## 五、Prompt 设计建议

你在 `req.md` 里对 prompt 的判断是对的，当前 prompt 设计确实偏散。

当前问题：

1. planner prompt 直接暴露 strategy 概念。
2. execution prompt 偏通用，不足以体现 role 差异。
3. review prompt 仍是文本格式指导，不是结构化 verifier/reviewer 契约。

### 建议的 prompt 分层

建议引入统一的 role prompt registry，而不是继续按 planner/execution/review 分散维护。

例如：

1. `role_specs/planner.py`
2. `role_specs/researcher.py`
3. `role_specs/designer.py`
4. `role_specs/coder.py`
5. `role_specs/verifier.py`
6. `role_specs/tester.py`
7. `role_specs/reviewer.py`
8. `role_specs/integrator.py`
9. `role_specs/writer.py`

每个 role spec 应至少定义：

1. system prompt
2. task prompt renderer
3. tool allowlist
4. preferred output schema
5. failure hint / retry hint
6. replay summary formatter

### verifier / reviewer / tester 尤其要结构化

这三类 role 不能只返回自由文本，应优先返回结构化对象，再由系统补充 markdown summary。

这样做的收益是：

1. 更容易自动判定 pass/fail。
2. 更容易串接 repair loop。
3. 更容易做 replay / query / analytics。

---

## 六、Replay 设计建议

你对 replay 的判断也是对的，但我建议把 replay 拆成三层问题来做，不要只理解成“落盘”。

### 1. durable persistence

调试阶段至少要支持 file-backed replay storage。

建议新增：

1. `FileReplayRepository`
2. `FileArtifactRepository`
3. 可选 `FileRunSnapshotWriter`

建议配置为：

1. 开发模式默认允许 `file` backend
2. 生产模式优先 `postgres`
3. `memory` 只保留给测试

### 2. terminal visibility

任务结束时应该显式发出 terminal event 和摘要日志。

建议至少增加：

1. `run.succeeded`
2. `run.failed`
3. `run.cancelled`
4. `subtask.summary`
5. `run.summary`

同时在 CLI / API stream 里清晰标出 terminal marker，而不只是状态字段变化。

### 3. subtask-scoped replay

你提的这个很重要。

当前 replay 主要以 run 为维度，但调试时经常只关心一个 subtask。

建议增加：

1. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events`
2. `GET /v1/subtasks/{subtask_id}`
3. `GET /v1/subtasks/{subtask_id}/artifacts`
4. `GET /v1/subtasks/{subtask_id}/replay`

同时 replay entry 应更稳定地携带：

1. `subtask_id`
2. `role`
3. `tool_call_id`
4. `tool_name`
5. `artifact_id`
6. `attempt`
7. `step`

---

## 七、建议的迁移路径

不建议一次性大爆炸重构。建议按下面顺序推进。

### Phase 1: 先把验证/审查 agent 化

这是最小但收益最高的一步。

原因：

1. 当前 `_execute_validation_subtask()` 与目标架构偏差最大。
2. `VerificationResult` / `ReviewDecision` 结构已经存在。
3. 这一步不会立刻触碰 sandbox 主链路。

产出：

1. 新的 `verifier` / `reviewer` role spec
2. LLM 主导的 validation/review executor
3. repair loop 与 review loop 接口保持兼容

### Phase 2: 合并 inline 与 agent-backed

这一步把“统一 agent executor”的主干先建立起来。

产出：

1. `OmniAgent` 第一版 wrapper
2. 统一 `execute_with_agent()` 路径
3. 删除 `_execute_inline_runtime_subtask()` 与 `_execute_agent_backed_subtask()` 的重复外壳

### Phase 3: 引入 role spec registry 并清理 strategy 暴露

这一步开始把语义从 strategy 切换到 role。

产出：

1. 新的 role enum
2. role 到 prompt/tool/schema 的显式绑定
3. planner prompt 去 strategy 化
4. coordinator 输出新的 assigned execution 结构

### Phase 4: sandbox agentization

这一步再把 sandbox 纳入统一 agent runtime。

产出：

1. sandbox-aware tools
2. sandbox session lifecycle manager
3. agent 内部按需调用 sandbox，而不是独立命令式 executor

### Phase 5: replay durable + subtask replay

最后补调试和可观测闭环。

产出：

1. file-backed replay/artifact storage
2. run/subtask terminal marker
3. subtask replay API

---

## 八、Story 拆分

下面这些 story 可以直接进入实现排期。

## Story 1：将 validation / review 改造成 LLM 主导的结构化 agent

### 目标

替换当前 `_execute_validation_subtask()` 的规则引擎实现，让 verifier/reviewer 成为真正的 agent role。

### 范围

1. 新增 `verifier` role。
2. 新增 verifier / reviewer role prompt spec。
3. 基于依赖摘要、artifact 摘要、AC 构造 agent 输入。
4. 输出仍落到 `VerificationResult` / `ReviewDecision`。

### 验收标准

1. validation/review 不再依赖硬编码规则组合。
2. repair loop 仍然可用。
3. replay 中可看到 verifier/reviewer 的输入摘要和结构化输出。

## Story 2：合并 inline 与 agent-backed 执行路径，落地 `OmniAgent` 第一版

### 目标

把当前两个 ReAct 分支收敛为统一 agent executor。

### 范围

1. 新增 `OmniAgent` wrapper。
2. 把 toolkit 装配、skill profile 注入、memory/artifact/sandbox tool 注入统一到一处。
3. 保留现有 AgentScope `ReActAgent` 作为底层实现。

### 验收标准

1. `_execute_inline_runtime_subtask()` 与 `_execute_agent_backed_subtask()` 不再分别维护 prompt/tool 装配逻辑。
2. 可按 role/profile 装配不同 toolkit。
3. 回放中可看到统一的 agent step 事件。

## Story 3：重构 capability 模型，建立 role-first 执行语义

### 目标

让 role 成为 planner 和 execution 间的主语义桥梁。

### 范围

1. 调整 `AgentRole`。
2. 删除或弱化 `StrategyProfile` 暴露。
3. 重新整理 `ToolGroup` 与 role/tool 权限映射。
4. 引入 role spec registry。

### 验收标准

1. planner 输出不再要求显式 `preferred_strategy`。
2. coordinator 以 role spec 解析执行配置。
3. `executor` 不再作为 planner 输出 role。

## Story 4：重构 planner / coordinator / assigned execution 契约

### 目标

把执行配置从“strategy 驱动”改成“role + runtime preference 驱动”。

### 范围

1. planner prompt 重写。
2. planner 输出新增 `expected_artifacts`、`runtime_preferences`、`tool_requirements`。
3. coordinator 生成新的 `AssignedExecution` 或等效模型。

### 验收标准

1. planner 输出契约更贴近 subtask 事实。
2. coordinator 不再对外暴露 strategy 概念。
3. run/subtask metadata 中可见 runtime 解析原因。

## Story 5：把 sandbox 从独立执行分支改成 agent runtime 环境

### 目标

让 sandbox 成为 `OmniAgent` 的一个可调用环境，而不是单独命令式 executor。

### 范围

1. 新增 sandbox-aware tools。
2. 设计 sandbox session lifecycle。
3. 让 agent 在推理循环中调用 sandbox tool。

### 验收标准

1. `_execute_sandbox_subtask()` 只保留兼容层或被删除。
2. sandbox 行为可以在 replay 中按 tool step 回放。
3. sandbox tool 权限可按 role/profile 控制。

## Story 6：补齐 file-backed replay、terminal marker 和 subtask replay API

### 目标

增强调试与回放可观测性。

### 范围

1. 新增 file-backed replay/artifact repository。
2. 增加 run/subtask terminal events 与 summary events。
3. 增加 subtask 级 replay / artifact 查询接口。

### 验收标准

1. 开发模式下任务结束后仍能查看完整 replay。
2. API/stream 中有明确 terminal marker。
3. 可单独查看某个 subtask 的执行过程。

---

## 九、实施顺序建议

建议执行顺序：

1. Story 1
2. Story 2
3. Story 3
4. Story 4
5. Story 5
6. Story 6

原因是：

1. Story 1 和 Story 2 可以最快验证“统一 agent executor”方向是否成立。
2. Story 3 和 Story 4 负责把字段语义和规划语义收拢干净。
3. Story 5 风险最高，应该放在统一 agent 主干稳定之后。
4. Story 6 对调试收益很高，但不阻塞核心语义收敛，可以并行或稍后补齐。

---

## 十、最终建议

我的建议不是“继续在当前四个 execution branch 上打补丁”，而是：

1. 明确承认当前架构正处于从“strategy/runtime 分流器”向“role-driven agent runtime”演进的中间态。
2. 先把 verifier/reviewer 和 inline/agent-backed 两个最明显的分裂点收敛掉。
3. 再把 capability、planner、coordinator 的字段语义调整过来。
4. 最后再做 sandbox agentization 和 durable replay。

如果只做 prompt 调整，不动 execution model，最终还是会回到现在这种分支越来越多、role 越来越虚、skill 越来越外挂的局面。

所以这次重构的重点不该是“多加几个 prompt”，而应该是：

1. 统一 agent 执行内核。
2. 让 role 成为一等公民。
3. 让 sandbox 成为 environment，而不是分支。
4. 让 replay 成为默认可调试基础设施，而不是附属能力。
