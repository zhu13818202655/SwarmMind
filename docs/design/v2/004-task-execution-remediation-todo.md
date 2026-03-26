# SwarmMind 任务执行系统整改实施记录

> 目标：把 [docs/design/v2/002-task-execution-system-implementation-status.md](/home/admin2/proj/SwarmMind/docs/design/v2/002-task-execution-system-implementation-status.md) 中标记为“部分实现 / 未实现”的能力，按可执行顺序逐步接入主运行时，而不是继续停留在模型层和文档层。

---

## 1. 执行原则

1. 先补主链，再补抽象。
2. 每一步都要求“代码可运行 + 事件可追踪 + 测试可证明”。
3. 优先打通以下关键闭环：
   - 持续 DAG 调度
   - 细粒度 subtask 生命周期
   - verify / review 独立执行
   - rework / repair 局部返工
4. skill / tool / memory 的接入必须服务于运行时，而不是只新增模型字段。

---

## 2. 总体待办

## Phase A：运行时主链补强

- [x] A1. 新增 `SubTaskStatus`，把 subtask 生命周期从粗粒度 `pending/running/succeeded/failed` 细化为：
  - `queued`
  - `ready`
  - `assigned`
  - `sandbox_creating`
  - `executing`
  - `verifying`
  - `succeeded`
  - `failed`
  - `cancelled`
- [x] A2. 改造 `Scheduler`，只选择依赖满足且尚未派发的 subtasks。
- [x] A3. 改造 `Coordinator`，在分配时写入 `execution_profile` 并将 subtask 置为 `assigned`。
- [x] A4. 改造 `TaskOrchestrator`，从“一次性派发 ready subtasks”改为“任务创建后派发 + 每个 subtask 终态后重新调度”。
- [x] A5. 为 rework 生成补救链：`repair -> verify -> review`。

## Phase B：verify / review 独立化

- [x] B1. 新增结构化 `VerificationResult`。
- [x] B2. 新增结构化 `ReviewDecision`。
- [x] B3. 在 `ExecutionRunner` 中按角色分流执行：
  - coder / executor / writer / researcher 走 sandbox 执行
  - tester 走独立 verification 逻辑
  - reviewer 走独立 review 逻辑
- [x] B4. review 结果不再直接等价于命令退出码，而是输出 `accept / rework / escalate`。

## Phase C：skill / tool 进入回放链

- [x] C1. 每个 subtask 执行前后记录 `strategy.started / strategy.completed / strategy.failed`。
- [x] C2. 对 sandbox 执行、artifact 读取等关键原子动作记录 `tool.started / tool.completed / tool.failed`。
- [x] C3. 将已有 `SkillRegistry` / `ToolRegistry` 真正作为动态装配入口，而不只是元数据容器。

## Phase D：repair / rework 闭环继续深化

- [x] D1. reviewer 发出 `rework` 决策时，动态生成 repair 链。
- [x] D2. 增加 repair 预算控制，避免无限返工。
- [x] D3. 将“执行失败后的局部重试”从 reviewer rework 扩展到通用子任务失败恢复的第一版。

## Phase E：后续未完成项

- [x] E1. memory lookup / memory write 接入 planning、review、repair 的第一版。
- [ ] E2. 将真实 repo 修改 / pytest / lint / build 引入默认 `build_app` 执行链。
- [ ] E3. 将 verify / review 独立成更明确的阶段执行器，而不是仍由 `ExecutionRunner` 统一承载。
- [ ] E4. 引入 durable worker / consumer group / ack / dead-letter 异步消费模型。
- [ ] E5. 将 handoff 从 `task.constraints.handoff_requests` 演进为 orchestrator 审批式 delegation tree：
  - 定义 delegation request / approval / execution / completion 的领域对象与事件
  - 由 orchestrator 而不是单个 strategy 决定 delegation 是否生效
  - 为 delegation tree 增加 lineage、depth、target-profile、context-mode、audit 查询能力
  - 保持与现有 `agent_backed` 和 `HandoffPolicy` 兼容，作为下一阶段平台化演进路径

---

## 3. 实施顺序

1. 先改模型与调度。
2. 再改执行器分流。
3. 再接 rework 生成逻辑。
4. 最后补测试，把成功链、失败链、rework 链全部跑通。

---

## 4. 本轮实际执行记录

## Step 1：细化 subtask 状态机

- 意图：让调度器、执行器、查询层、回放层能看见真实子任务阶段，而不只是笼统的 `running`。
- 影响文件：
  - `swarmmind/models/task.py`
  - `swarmmind/orchestration/scheduler.py`
  - `swarmmind/orchestration/coordinator.py`

## Step 2：持续 DAG 调度

- 意图：让依赖图在 subtask 完成后继续推进，而不是只在 planning 结束时派发第一批。
- 影响文件：
  - `swarmmind/orchestration/task_orchestrator.py`
  - `swarmmind/app/container.py`

## Step 3：独立 verify / review

- 意图：把 tester / reviewer 从“通用 markdown 生成器”里拆出来，至少先具备独立判定能力。
- 影响文件：
  - `swarmmind/models/execution.py`
  - `swarmmind/orchestration/execution_runner.py`
  - `swarmmind/orchestration/run_state_service.py`

## Step 4：repair / rework 链

- 意图：让 reviewer 不是只能把整个 run 判死，而是可以要求局部返工并重进验证链。
- 影响文件：
  - `swarmmind/orchestration/task_orchestrator.py`
  - `swarmmind/orchestration/run_state_service.py`

## Step 5：测试补齐

- 意图：避免这轮重构只改出“能看不能跑”的代码。
- 影响文件：
  - `tests/test_planner_llm_fallback.py`
  - `tests/test_v2_execution_flow.py`

---

## 5. 当前状态

- 已完成：Phase A、Phase B、Phase C、Phase D 的第一版、Phase E1 的 memory lookup/write 第一版。
- 未完成：真实 repo 修改与测试执行、durable worker。
- 下一轮建议：优先做 `SkillRegistry/ToolRegistry` 动态装配和真实代码仓库执行链，而不是继续扩充文档模型。