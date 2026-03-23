# SwarmMind 任务执行系统实现现状对照（基于 002 文档）

> 本文档基于 `docs/design/002-multi-agent-task-execution-system.md` 与当前 `swarmmind/` 真实代码实现做逐项对照，回答两个问题：
>
> 1. 002 文档里哪些能力已经落地。
> 2. 哪些能力只是部分实现，或者仍然没有真正接通。

关联文档：

- `docs/design/002-multi-agent-task-execution-system.md`
- `docs/design/010-current-code-implementation-status.md`
- `docs/design/v2-002-implementation-scope.md`
- `docs/design/v2-003-infrastructure-abstraction-design.md`

---

## 1. 一句话结论

当前 `swarmmind/` 已经不再只是“控制面骨架”，而是已经形成了一个**可运行的任务提交 -> 规划 -> 子任务分配 -> sandbox 执行 -> artifact/replay 回收 -> run/task 状态收敛**的最小闭环。

但它距离 002 文档所定义的“Coordinator 驱动、DAG 调度、角色清晰、verify/review 独立、支持 repair/rework 的多智能体执行系统”还有明显差距。

更准确地说，当前实现状态是：

1. **主链路 MVP 已经打通。**
2. **多角色语义已经进入模型层和 planner 输出。**
3. **真正的多智能体协作、动态调度、独立验收、返工闭环还没有完成。**

另外需要明确一点：`docs/design/010-current-code-implementation-status.md` 中“`subtask.assigned` 之后还没有接上真实执行器”的结论已经过时。当前代码里 `ExecutionRunner` 已经接到了主链上。

---

## 2. 对照口径

本文将 002 文档里的能力分成三类来判断：

1. **已实现**：主链路中真实接通，代码和测试都能证明。
2. **部分实现**：有模型、接口、基础设施，或者有第一版实现，但离 002 的目标语义还差一截。
3. **未实现**：002 明确要求的关键能力在主链中还不存在，或者只有概念占位。

---

## 3. 已实现的部分

## 3.1 Gateway -> Orchestrator 的入口主链已经实现

这部分和 002 文档中 “Intake” 阶段的目标基本一致，已经落地。

当前已实现：

1. `Gateway.submit_task()` 会做准入、归一化、session 获取或创建、task 创建、run 创建、replay root 创建。
2. 提交后会发布 `task.created` 事件，而不是在 API 层直接串行执行业务逻辑。
3. `task.created` 已订阅到 `TaskOrchestrator.handle_task_created()`。

对应代码：

- `swarmmind/gateway/gateway.py`
- `swarmmind/app/container.py`
- `swarmmind/orchestration/task_orchestrator.py`

这意味着 002 所说的 “User Request -> Gateway -> Task Orchestrator” 已经是真实链路，不是设计图。

## 3.2 Planner 已经能产出结构化 subtasks

002 文档里要求 Planner 输出结构化任务图，当前代码已经实现了第一版。

当前已实现：

1. `Planner.plan()` 先尝试 LLM 规划，失败后退回规则规划。
2. 每个 `SubTask` 已经具备这些关键字段：
   - `role`
   - `preferred_strategy`
   - `required_tool_groups`
   - `sandbox_profile`
   - `acceptance_criteria`
   - `dependencies`
3. LLM 规划结果会被规范化，并映射成 `SubTask` 列表。
4. fallback planner 也会写入角色、技能、工具组和验收条件。

对应代码：

- `swarmmind/orchestration/planner.py`
- `swarmmind/models/task.py`
- `swarmmind/models/capability.py`

测试覆盖：

- `tests/test_planner_llm_fallback.py`

因此，002 中 “任务图先行” 这个方向已经开始落地，不再只是 `name + description` 级别的 subtask。

## 3.3 Coordinator / Scheduler / ExecutionProfile 第一版已经实现

002 文档强调 Coordinator 驱动和 capability 装配，这部分已经有第一轮实现。

当前已实现：

1. `Scheduler.get_ready_subtasks()` 会根据 `dependencies` 计算 ready subtasks。
2. `Coordinator.assign()` 会给 ready subtask 绑定 `ExecutionProfile`。
3. `ExecutionProfile` 已包含：
   - `role`
   - `preferred_strategy`
   - `required_tool_groups`
   - `sandbox_profile`
4. 这些执行元数据会被写入 `subtask.metadata["execution_profile"]`。

对应代码：

- `swarmmind/orchestration/scheduler.py`
- `swarmmind/orchestration/coordinator.py`
- `swarmmind/models/execution.py`

这说明 002 提到的 “role -> skill -> tool -> sandbox profile” 至少已经进入了运行时元数据，而不是只停留在设计文档。

## 3.4 `subtask.assigned` 之后的真实执行链已经实现

这是当前代码最关键的变化，也是和旧文档最大的差异。

当前已实现：

1. `app/container.py` 已经把 `subtask.assigned` 订阅到 `ExecutionRunner.handle_subtask_assigned()`。
2. `ExecutionRunner` 会：
   - 读取 task/run/subtask
   - 把 subtask 置为运行中
   - 获取 sandbox lease
   - 执行命令
   - 记录执行摘要
   - 生成 artifact
   - 发布 `subtask.completed` 或 `subtask.failed`
   - 释放 sandbox
   - 调用 `RunStateService.reconcile()` 做 run/task 收敛
3. 当前默认执行方式是生成一段子任务内容，然后在 sandbox 里写入 `outputs/*.md` 文件并输出日志。
4. 这条链已经被测试证明可成功和失败两种路径。

对应代码：

- `swarmmind/app/container.py`
- `swarmmind/orchestration/execution_runner.py`
- `tests/test_v2_execution_flow.py`

因此，系统已经具备最小执行闭环，而不只是分配 subtask。

## 3.5 SandboxProvider 抽象和本地 / OpenSandbox 双实现已经存在

002 文档要求执行必须统一走 `SandboxProvider` 抽象，这部分已经实现。

当前已实现：

1. `SandboxProvider` 协议已经定义了 `create / run_command / write_files / read_file / kill`。
2. `SandboxManager` 负责 sandbox lease、执行、销毁等生命周期封装。
3. `LocalSandboxAdapter` 提供本地临时目录版 sandbox，适合开发和测试。
4. `OpenSandboxAdapter` 已接入 OpenSandbox SDK，并支持：
   - profile 选择
   - create retry
   - backoff
   - command execution
   - file read/write
5. `SandboxConfig` 已支持 provider、api key、base url、retry、timeout 等配置。

对应代码：

- `swarmmind/sandbox/provider.py`
- `swarmmind/sandbox/manager.py`
- `swarmmind/sandbox/local_adapter.py`
- `swarmmind/sandbox/opensandbox_adapter.py`
- `swarmmind/config/schema.py`

这一点和 002 设计是一致的，且已经具备“抽象稳定、实现可替换”的基础。

## 3.6 Artifact / Replay / 查询链已经实现

002 文档要求系统可审计、可回放，这部分当前已经有第一版落地。

当前已实现：

1. `ArtifactCollector` 会把执行摘要、stdout、stderr 转成 artifact metadata。
2. `ReplayRecorder` 会订阅全部事件并写入 run replay timeline。
3. `RunStateService` 会根据 subtask 状态更新 run/task 终态。
4. 查询层已能返回聚合后的 run detail。
5. API 已支持：
   - `GET /v1/runs/{run_id}`
   - `GET /v1/runs/{run_id}/events`
   - `GET /v1/runs/{run_id}/stream`

对应代码：

- `swarmmind/sandbox/artifact_collector.py`
- `swarmmind/sandbox/replay_recorder.py`
- `swarmmind/orchestration/run_state_service.py`
- `swarmmind/query/service.py`
- `swarmmind/api/server.py`

测试覆盖：

- `tests/test_v2_execution_flow.py`

所以从“是否有完整事件轨迹和 artifact 聚合视图”这个角度看，系统已经有第一版答案。

## 3.7 Repository / Redis / Postgres / Qdrant 基础设施抽象已经落地

002 文档强调平台级基础设施要独立，当前代码这部分已经实现得比 002 还更明确。

当前已实现：

1. Repository 协议和内存版 / PostgreSQL 版实现已存在。
2. Event bus 有 in-memory 和 Redis buffered 两种实现。
3. Cache 和 lock 已抽象成独立能力，并有 Redis 实现。
4. 长期记忆已抽象成 `LongTermMemoryBase`，并有 memory / Qdrant / Chroma 实现。
5. 容器装配逻辑会根据配置切换实现。

对应代码：

- `swarmmind/repositories/`
- `swarmmind/events/`
- `swarmmind/cache/`
- `swarmmind/locks/`
- `swarmmind/memory/long_term.py`
- `swarmmind/app/container.py`

测试覆盖：

- `tests/test_infra_selection.py`
- `tests/test_infra_live_integration.py`

这意味着当前仓库已经不是单纯的内存 demo，而是已经具备切到 `PostgreSQL + Redis + Qdrant` 的能力。

---

## 4. 部分实现的部分

## 4.1 DAG 模型已经存在，但动态调度只做了第一步

002 文档要求的是 DAG 调度，不只是一次性挑 ready subtasks。

当前状态：

1. `SubTask.dependencies` 已存在。
2. `Scheduler.get_ready_subtasks()` 也会检查依赖是否完成。
3. 但 `TaskOrchestrator` 只在 planning 完成后调用一次 scheduler。
4. subtask 完成后，系统目前只会做 run/task 状态收敛，不会继续挑选下一批 ready subtasks 并派发。

这意味着：

1. **有 DAG 字段。**
2. **有 ready 计算函数。**
3. **没有真正的持续调度循环。**

因此这一项只能算部分实现，距离 002 所说的 Coordinator 调度循环还有明显差距。

## 4.2 角色体系已经进模型层，但执行时仍然是通用执行器

002 文档希望 Planner、Coordinator、Coder、Tester、Reviewer 等角色职责清晰分离。

当前状态：

1. `AgentRole` 枚举已经定义了 planner / coordinator / researcher / executor / coder / tester / reviewer / writer。
2. Planner 输出的 subtask 也会带 role。
3. 但是主链里真正负责执行的只有一个 `ExecutionRunner`。
4. `ExecutionRunner` 并不会根据角色切换到不同的专业 agent 实现。
5. `Planner` 和 `ExecutionRunner` 虽然都能调用 AgentScope 模型，但本质上仍然是两个通用调用点，而不是多角色 agent runtime。

所以这部分是“语义层已建模，执行层未分化”。

## 4.3 Skill / Tool 体系已经建好模型和注册器，但还没真正进入执行主链

002 文档把 `skill` 定义为任务套路层，把 `tool` 定义为原子动作层，并强调它们应被 Coordinator 动态装配。

当前状态：

1. `StrategyProfile`、`DEFAULT_STRATEGY_PROFILES`、`ToolGroup` 都已经存在。
2. `SkillRegistry`、`ToolRegistry`、若干内建 tools、若干 skills 也已经实现。
3. Planner 会给 subtask 写入 `preferred_strategy` 与 `required_tool_groups`。
4. Coordinator 会把这些信息打包进 `ExecutionProfile`。
5. 但 `ExecutionRunner` 当前没有按 skill 执行，也没有根据 tool group 动态装配工具箱。
6. 当前执行仍然是“生成一段内容 -> 在 sandbox 中写 markdown 文件”的统一流程。

因此这部分是“模型和框架已在，运行时编排还没有接通”。

## 4.4 Verify / Review 的语义存在，但没有真正独立成质量闸门

002 文档明确要求：

1. 执行者不能自己验收自己。
2. Tester 要独立验证。
3. Reviewer 要独立决策 accept / rework / escalate。

当前状态：

1. planner fallback 的确会生成 `verify-result` 这类 tester subtask。
2. `AgentRole.TESTER`、`AgentRole.REVIEWER` 也都存在。
3. `RunPhase` 里也有 `REVIEWING`。
4. 但是主链中没有独立的 `TesterAgent` 或 `ReviewerAgent`。
5. 也没有 `VerificationResult`、`ReviewDecision` 这样的结构化结果对象。
6. 当前任务成功与否，本质上由 subtask 命令退出码和 `RunStateService` 聚合逻辑决定。

所以 verify/review 目前只有“角色名和阶段名”，还没有成为真正的质量控制节点。

## 4.5 记忆和上下文能力存在，但没有进入主执行链

002 文档强调 memory 应参与 planning、coordination、review 和经验沉淀。

当前状态：

1. `LongTermMemoryBase`、Qdrant、Chroma、in-memory 都已实现。
2. `MemoryManager` 也存在。
3. 容器会构建 long-term memory。
4. 但 Gateway、Planner、Coordinator、ExecutionRunner 目前没有把 memory lookup 真正注入主链。
5. replay 和 artifact 会沉淀，但长期记忆并未随任务自动写入或读取。

所以 memory 目前更像“基础设施已到位”，而不是“任务执行系统的一部分”。

## 4.6 RedisBufferedEventBus 已实现缓冲，但仍不是独立 worker 架构

002 文档强调平台级异步解耦和可回放。

当前状态：

1. `RedisBufferedEventBus` 会把事件写进 Redis Stream 并发布到 Pub/Sub channel。
2. 但它仍然会在当前进程内同步分发本地订阅者。
3. 当前没有 consumer group、ack、重试、死信或独立 worker 消费模型。

因此它已经比普通内存事件总线更进一步，但还不是完整的异步执行底座。

---

## 5. 还没有实现的部分

## 5.1 真正的 Coordinator 驱动阶段流转还没有实现

002 文档中的目标是：

1. Intake
2. Plan
3. Prepare
4. Execute
5. Verify
6. Review
7. Deliver

当前代码虽然有 `RunPhase`，但真实的阶段控制仍然比较粗：

1. `planning`
2. `coordinating`
3. `executing`
4. `reviewing`（失败路径）
5. `delivering`（成功路径）

缺失的关键点：

1. 没有单独的 prepare 阶段对象和逻辑。
2. 没有 verify / review 的真实阶段执行器。
3. 没有按阶段选择不同 agent 和上下文裁剪的统一控制器。

## 5.2 repair / rework / retry 闭环没有实现

002 文档要求支持局部失败重试，而不是整单任务重跑。

当前代码没有这些能力：

1. 基于失败证据生成 repair subtask。
2. 仅重跑失败链路相关 subtasks。
3. reviewer 决定 rework 并回退到前一阶段。
4. 子任务级重试预算和停止条件。

当前失败路径基本是：

1. subtask fail
2. run fail
3. task fail

这离 002 所说的“局部恢复”还差很远。

## 5.3 MsgHub 局部协作和多 agent 讨论没有实现

002 文档明确提出：

1. 全局是状态机。
2. 局部可以是 MsgHub / fanout / gather。

当前代码虽然使用了 AgentScope，但没有看到：

1. `MsgHub` 的实际接入。
2. Planner/Researcher/Architect 的局部讨论。
3. 多候选方案并行生成与收敛。

因此现在还不能说已经实现了“多智能体协作”，更准确地说是“带 AgentScope 接口的单执行链”。

## 5.4 tool runtime 与 sandbox-aware tools 还没有真正落地

002 文档要求：

1. agent 不直接操作环境。
2. skill 也不能绕过统一工具层。
3. tool 调用要可审计、可重放。

当前主链没有实现这些关键点：

1. 角色执行时没有真正通过 `ToolRegistry` 动态装配工具。
2. built-in tools 没有成为 `ExecutionRunner` 的标准执行方式。
3. skill event 和 tool event 没有进入 replay 的统一记录。
4. 还没有“skill orchestration -> tool calls -> sandbox execution”这条完整链。

## 5.5 Subtask 状态机没有细化到 002 文档要求的粒度

002 文档推荐 subtask 状态：

`QUEUED -> READY -> ASSIGNED -> SANDBOX_CREATING -> EXECUTING -> VERIFYING -> DONE / ERROR`

当前代码仍然复用了 `TaskStatus` 作为 subtask status：

1. `pending`
2. `running`
3. `succeeded`
4. `failed`
5. 其他 task 级状态

这会导致：

1. 子任务状态语义不够细。
2. 并发调度、恢复、监控和回放的粒度不足。

## 5.6 真实业务执行还没有进入 repo 修改 / test / review 场景

当前 `ExecutionRunner` 的执行结果本质上是写 markdown 产物，不是对代码仓库做真实修改。

因此以下能力还没有真正实现：

1. 在仓库中读写业务代码。
2. 运行 pytest / lint / build 作为真实验证。
3. 生成 patch 并交给 reviewer 判定。
4. 基于 artifact 和 test report 做最终交付。

当前更像“可执行的流程骨架”，而不是“真正的软件开发多 agent 平台”。

---

## 6. 按 002 文档核心主张逐项判断

| 002 核心主张 | 当前状态 | 判断 |
| --- | --- | --- |
| Gateway 接收任务并建立 task/session/run | 已接通 | 已实现 |
| Planner 先产出结构化任务图 | LLM + fallback rule planner 已支持 | 已实现 |
| Coordinator 负责能力装配 | 只做 execution profile 绑定 | 部分实现 |
| Scheduler 基于 DAG 持续调度 | 仅初次 ready 计算 | 部分实现 |
| 每个 subtask 可创建 sandbox 执行 | 已接通 local / opensandbox | 已实现 |
| 结果回收到 artifact / replay | 已接通 | 已实现 |
| task/run 能自动收敛到终态 | 已接通 | 已实现 |
| verify 独立于 execute | 还没有独立验证运行时 | 未实现 |
| review 决策 accept/rework/escalate | 没有 reviewer decision | 未实现 |
| repair / rework 仅重跑失败链路 | 没有 | 未实现 |
| role -> skill -> tool 动态装配 | 只在模型层与 metadata 层 | 部分实现 |
| tool runtime 统一审计 | 主链未接通 | 未实现 |
| memory 参与 planning / coordination / review | 基础设施已在，主链未接 | 部分实现 |
| MsgHub 局部协作 | 没有看到实际使用 | 未实现 |
| 多租户 / worker / durable async 架构 | 只有第一版基础设施 | 部分实现 |

---

## 7. 对当前代码阶段的判断

如果按照 002 文档的目标层级来定义，当前代码更适合被定义为：

**“执行闭环已经打通的 Phase 1.5 / V2 early stage 实现”**

而不是：

1. 纯控制面骨架
2. 完整多智能体执行平台

它的真实位置更接近：

1. 入口控制面已成型。
2. 结构化规划已具备。
3. sandbox 执行闭环已具备。
4. 基础设施抽象已较完整。
5. 但执行策略仍然比较单通道，远未达到 002 文档里“多角色、多阶段、可返工、可局部恢复”的成熟度。

---

## 8. 下一阶段最值得补的缺口

如果继续沿 002 文档推进，优先级最高的不是再补概念模型，而是把下面几项真正接到主链上：

### 8.1 做持续 DAG 调度

核心目标：

1. subtask 完成后重新计算 ready subtasks。
2. 只派发依赖满足的下一批 subtasks。
3. run 终态只在没有待调度任务时才关闭。

### 8.2 做 verify / review 独立执行器

核心目标：

1. 把 tester 和 reviewer 从通用 execution runner 中分出来。
2. 引入结构化 `VerificationResult` 和 `ReviewDecision`。
3. 成功不再只看 exit code，而要看是否满足 acceptance criteria。

### 8.3 把 skill / tool 真正接入执行链

核心目标：

1. 根据 `ExecutionProfile` 动态选择 skill。
2. skill 内部通过 tool runtime 调用具体工具。
3. tool 调用和 skill 调用都进入 replay 审计链。

### 8.4 做 repair / rework 闭环

核心目标：

1. tester/reviewer 失败后生成 repair subtask。
2. 只重跑失败链路。
3. 为 retry / rework 增加预算与停止条件。

---

## 9. 最终结论

结合 002 文档和当前 `swarmmind/` 代码，最准确的结论是：

1. **已经实现的，不只是模型层，而是主链路执行闭环。**
2. **还没实现的，不是“能不能跑”，而是“能不能像 002 设计那样稳定地多角色协作、独立验收、动态修复”。**
3. **下一阶段的重点应从“补更多抽象”转向“把 verify/review/DAG/rework 接到真实运行时”。**

因此，当前项目已经跨过“概念架构”阶段，但还没有达到 002 文档定义的“完整多智能体任务执行系统”。
