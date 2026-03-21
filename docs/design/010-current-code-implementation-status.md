# SwarmMind 当前代码实现说明

当前代码时间，基于commit：89a016923949b9bdc223bda23a004a70304fb344

> 本文档不是目标设计，也不是路线图，而是对当前 `swarmmind/` 目录下真实代码实现状态的说明。
>
> 适用场景：
>
> 1. 新成员快速了解当前系统已经具备什么能力。
> 2. 对照 `007-010` 设计文档，区分“已落地”和“尚未接通”的部分。
> 3. 调试 API、submit 脚本、task/run 查询链路时，建立统一认知。

---

## 1. 当前版本一句话结论

当前代码已经实现了一个**以 FastAPI + Gateway + in-memory repositories + in-process event bus + Orchestrator 为核心的控制面骨架**，支持：

1. 提交任务。
2. 创建 session / task / run / replay root。
3. 通过事件总线触发 orchestrator。
4. 生成 subtasks。
5. 为 subtasks 绑定 execution profile。
6. 提供 task/run 查询 API。

当前代码**尚未形成真正的执行闭环**。`subtask.assigned` 之后还没有接上真实执行器，因此目前系统更接近“控制面 MVP”，而不是“完整多智能体执行平台”。

---

## 2. 当前已实现的模块

## 2.1 API 与应用装配

当前 API 入口已经切到新的应用装配模式。

已实现内容：

1. FastAPI 应用工厂 `create_app()`。
2. 生命周期中构建并缓存应用级 container。
3. 通过 container 获取 gateway、identity resolver、query service。
4. 暴露 task / run 查询相关 HTTP 接口。

对应代码：

- `swarmmind/api/server.py`
- `swarmmind/app/bootstrap.py`
- `swarmmind/app/container.py`

当前可用接口：

1. `GET /`
2. `GET /health`
3. `POST /v1/tasks`
4. `GET /v1/tasks`
5. `GET /v1/tasks/{task_id}`
6. `GET /v1/tasks/{task_id}/detail`
7. `GET /v1/runs/{run_id}`
8. `GET /v1/runs/{run_id}/status`
9. `DELETE /v1/tasks/{task_id}`

这意味着 API 查询链已经不是占位，而是可以真实读取当前内存中的 task/run/subtask/artifact 聚合视图。

---

## 2.2 Gateway 入口控制面

当前 Gateway 已经承担了设计中的入口职责，但仍然是第一轮简化实现。

已实现内容：

1. 请求准入校验。
2. 请求归一化。
3. session 获取或创建。
4. task / run / replay root 创建。
5. 事件派发。
6. task 查询、更新、兼容 transcript session。

对应代码：

- `swarmmind/gateway/gateway.py`
- `swarmmind/gateway/admission.py`
- `swarmmind/gateway/request_normalizer.py`
- `swarmmind/gateway/session_manager.py`
- `swarmmind/gateway/dispatcher.py`
- `swarmmind/gateway/envelopes.py`

`submit_task()` 的当前真实行为是：

1. 校验 identity 是否有提交权限。
2. 校验请求是否合法。
3. 归一化 `TaskSubmitRequest`。
4. 获取或创建 `Session`。
5. 创建 `Task`。
6. 创建 `Run`。
7. 创建 `ReplayRoot`。
8. 发布 `run.created` 和 `task.created` 事件。

这里已经符合“Gateway 负责入口控制，不直接内联执行”的设计方向。

---

## 2.3 Identity 与权限骨架

当前身份与权限模块已经落地，但还是开发态实现。

已实现内容：

1. `IdentityContext` 模型。
2. `StaticIdentityResolver`。
3. 简单的 `AuthorizationPolicy`。

对应代码：

- `swarmmind/identity/models.py`
- `swarmmind/identity/resolver.py`
- `swarmmind/identity/policy.py`

当前行为特点：

1. 默认返回固定的本地 identity。
2. scope 检查已接入 task submit / task read / run read。
3. 还没有真实 API key、JWT、租户系统后端。

因此目前 identity 是“边界接口已经稳定，真实后端尚未接入”的状态。

---

## 2.4 核心领域模型

当前项目已经形成一套较完整的控制面对象模型。

已落地模型包括：

1. `Task`
2. `SubTask`
3. `Run`
4. `Session`
5. `Artifact`
6. `ReplayRoot`
7. `DomainEvent`
8. `ExecutionProfile`
9. `AgentRole`
10. `ToolGroup`
11. `SkillProfile`

对应目录：

- `swarmmind/models/`

这部分已经不再是草图，很多上层模块都在直接使用这些模型。

---

## 2.5 Repository 抽象与内存实现

当前 repository 层已经完成了第一轮抽象，并提供了 in-memory 实现。

已实现内容：

1. `TaskRepository`
2. `SessionRepository`
3. `RunRepository`
4. `SubTaskRepository`
5. `ArtifactRepository`
6. `ReplayRepository`
7. 上述仓储的内存版实现

对应代码：

- `swarmmind/repositories/*.py`
- `swarmmind/repositories/in_memory/__init__.py`

当前特征：

1. 所有数据都保存在进程内内存中。
2. 服务重启后 task/run/session/subtask/artifact/replay 数据会丢失。
3. 上层模块已经大多依赖 repository，而不是直接维护裸字典。

这说明 repository 抽象已经接通，但持久化后端还没有接进来。

---

## 2.6 Event Bus 与事件驱动启动链

事件总线已经真实启用，不是设计占位。

已实现内容：

1. `EventBus` 协议。
2. `InMemoryEventBus`。
3. `RedisBufferedEventBus`。
3. 应用启动时注册 `task.created -> orchestrator.handle_task_created`。

对应代码：

- `swarmmind/events/bus.py`
- `swarmmind/events/in_memory_bus.py`
- `swarmmind/events/redis_buffered_bus.py`
- `swarmmind/app/container.py`

当前行为特点：

1. 总线抽象已经独立出来，上层依赖的是 `EventBus` 协议，而不是具体后端。
2. 默认可以按配置切到 in-memory 或 Redis buffered 实现。
3. 两种实现都会先在当前进程内分发给本地 subscriber。
4. `publish()` 对本地 handler 仍然是同步 await，而不是后台消费队列。
5. `task.created` 发布后，orchestrator 会立刻执行。

`RedisBufferedEventBus` 当前的定位需要明确：

1. 它不是完整的独立 consumer 架构。
2. 它会把事件同时写入 Redis Stream，并发布到 Redis Pub/Sub channel。
3. 它保留本地 subscriber 分发语义，因此当前更像“带外部缓冲能力的本地事件总线”，而不是“真正的异步 worker 总线”。
4. 这使得它已经具备后续做审计、外部消费、进度流和回放的演进入口，但还没有建立 consumer group、重试、ack、死信这些生产级机制。

这意味着任务提交和 planning 之间没有后台 worker 边界，当前是同进程直接推进。

也就是说，`swarmmind/events` 目录当前承担的是“平台领域事件基础设施”的角色，而不是 AgentScope `MsgHub` 那种 Agent 会话广播能力。

---

## 2.7 Orchestrator / Planner / Coordinator / Scheduler

这一组模块已经构成当前系统的执行控制核心，但还停留在“任务图构建与分配”阶段。

对应代码：

- `swarmmind/orchestration/task_orchestrator.py`
- `swarmmind/orchestration/planner.py`
- `swarmmind/orchestration/coordinator.py`
- `swarmmind/orchestration/scheduler.py`

### TaskOrchestrator 当前已实现

`handle_task_created()` 当前会做：

1. 读取 task 和 run。
2. 将 task 状态切到 `planning`。
3. 将 run 状态切到 `running`，phase 切到 `planning`。
4. 调用 planner 生成 subtasks。
5. 保存 subtasks 并挂到 run。
6. 将 run phase 切到 `coordinating`。
7. 发布 `task.planning.completed`。
8. 调用 scheduler 选出 ready subtasks。
9. 调用 coordinator 为 ready subtasks 补执行元数据。
10. 为每个 subtask 发布 `subtask.assigned`。
11. 将 task 切到 `running`。
12. 将 run phase 切到 `executing`。

### Planner 当前已实现

Planner 不是 LLM planner，而是规则式 planner。

当前规则：

1. 一定创建 `analyze-requirement`。
2. 一定创建 `prepare-implementation`。
3. 如果目标里包含 `test` 或 `验证`，再创建 `verify-result`。

Planner 已经会写入：

1. role
2. preferred skill
3. required tool groups
4. sandbox profile
5. acceptance criteria

### Coordinator 当前已实现

Coordinator 当前不会真正执行 subtask，只会为 subtask 绑定 `ExecutionProfile` 并写入 metadata。

### Scheduler 当前已实现

Scheduler 会根据依赖关系，找出处于 `PENDING` 且依赖已满足的 subtasks。

---

## 2.8 Query 查询链

查询链是当前代码里已经比较完整的一块。

已实现内容：

1. 按 task 聚合读取 task、session、runs。
2. 按 run 聚合读取 run、subtasks、artifacts。
3. API 已接到 QueryService。
4. submit 脚本支持轮询 task 或 run。

对应代码：

- `swarmmind/query/service.py`
- `swarmmind/api/server.py`
- `scripts/submit_task.py`

这意味着当前系统虽然还没有真实执行器，但“提交后查看 run/subtask 状态”的查询面已经可以工作。

---

## 2.9 Sandbox 抽象与 OpenSandbox 适配

Sandbox 层已经具备较明确的接口和一版 OpenSandbox 适配器。

对应代码：

- `swarmmind/sandbox/provider.py`
- `swarmmind/sandbox/manager.py`
- `swarmmind/sandbox/opensandbox_adapter.py`
- `swarmmind/sandbox/models.py`
- `swarmmind/sandbox/profiles.py`

当前已实现能力：

1. 创建 sandbox。
2. 带重试创建 sandbox。
3. 在 sandbox 中执行命令。
4. 写文件、读文件、销毁 sandbox。
5. `SandboxLease` 与 `SandboxExecution` 模型。
6. profile 选择和 connection config 构造。

当前限制：

1. SandboxManager 还没有被 orchestrator 执行链真正消费。
2. `collect_artifacts()` 仍然返回占位 artifact metadata。
3. 还没有把 stdout/stderr/输出文件真正入库到 artifact repository。

因此 sandbox 这层属于“能力已可单独调用，但尚未接入主执行闭环”。

---

## 2.10 Agent / Tool / Skill 基础设施

这部分模块已经有真实代码，但当前还没有真正接入 subtask 执行主线。

### AgentFactory

对应代码：

- `swarmmind/agents/factory.py`
- `swarmmind/agents/config.py`

当前已实现：

1. 基于 AgentScope 创建 `OpenAIChatModel`。
2. 创建 `OpenAIChatFormatter`。
3. 创建 `Toolkit` 并注册普通工具函数。
4. 创建 `ReActAgent`。

这部分目前主要用于 CLI 单 agent 试跑，不在 orchestrator 主链中。

### ToolRegistry

对应代码：

- `swarmmind/tools/registry.py`
- `swarmmind/tools/builtin/`

当前已实现：

1. 注册工具函数。
2. 记录工具说明。
3. 按 `ToolGroup` 查询可用工具 schema。
4. 直接执行指定工具函数。

### SkillRegistry

对应代码：

- `swarmmind/skills/base.py`
- `swarmmind/skills/registry.py`
- `swarmmind/skills/*.py`

当前已实现：

1. `Skill`/`SkillResult` 基础抽象。
2. skill 注册与执行。
3. 默认 `SkillProfile` 与 role 推荐关系。

当前限制：

1. role -> skill -> tool group 的装配还没有进入 orchestrator 执行主链。
2. subtask 被 assigned 后，没有真实的 skill runner 去消费。

---

## 2.11 Memory 模块

当前 memory 已经拆成短期和长期两类，但使用深度差异较大。

对应代码：

- `swarmmind/memory/manager.py`
- `swarmmind/memory/long_term.py`
- `swarmmind/memory/transcript.py`

当前已实现：

1. `MemoryManager` 基于 AgentScope `InMemoryMemory` 提供短期消息缓存。
2. 本地裁剪 session memory block 数量。
3. `Transcript` 用于兼容式事件/消息记录。
4. `InMemoryLongTermMemory`。
5. `QdrantLongTermMemory` / `ChromaLongTermMemory` 的初版适配。

当前限制：

1. orchestrator 主链没有真实使用 long-term memory。
2. long-term memory 检索还没有接 embedding 真实实现，部分实现使用占位向量。
3. transcript 主要还是兼容路径，没有成为统一 replay 时间线。

---

## 3. 当前真实可运行的主流程

如果按“启动 FastAPI 服务 + 运行 `scripts/submit_task.py`”这条路径看，当前系统的真实流程是：

1. 脚本读取用户输入，组装 payload。
2. 调用 `POST /v1/tasks`。
3. API 通过 container 拿到 gateway。
4. gateway 创建 session / task / run / replay root。
5. gateway 发布 `run.created` 和 `task.created`。
6. in-memory event bus 立即触发 orchestrator。
7. orchestrator 调 planner 生成 subtasks。
8. scheduler 选出 ready subtasks。
9. coordinator 为 subtasks 绑定 execution profile。
10. orchestrator 发布 `subtask.assigned`。
11. task 状态进入 `running`，run phase 进入 `executing`。
12. 脚本随后可以轮询 `/v1/tasks/{task_id}` 或 `/v1/runs/{run_id}` 查看聚合状态。

这条路径当前已经可以跑通。

---

## 4. 当前尚未接通的关键能力

下面这些能力在设计文档中是核心能力，但当前代码还没有真正接上。

## 4.1 `subtask.assigned` 之后的真实执行链

当前没有任何模块订阅 `subtask.assigned` 去启动真实执行。

这意味着现在不会自动发生：

1. 创建 agent 执行 subtask。
2. 创建 sandbox lease。
3. 写文件、跑命令、跑测试。
4. 产生执行日志并更新 subtask 状态。

这是当前系统和目标平台之间最大的差距。

## 4.2 Run / SubTask 的完成态闭环

当前 orchestrator 只把 run phase 推到 `executing`，但没有后续逻辑去：

1. 标记 subtask `SUCCEEDED` / `FAILED`
2. 推进 run `SUCCEEDED` / `FAILED`
3. 推进 task `SUCCEEDED` / `FAILED`

所以如果没有额外代码介入，任务会停在中间态。

## 4.3 Artifact / Replay 证据链闭环

当前虽然有模型和 repository，但还没有完整证据链。

未接通的部分包括：

1. stdout/stderr 自动转 artifact。
2. sandbox 输出文件自动归档。
3. replay timeline 按事件持续追加。
4. API 返回真实执行证据，而不只是控制面对象。

## 4.4 持久化基础设施

当前所有 repository 都是 in-memory 实现，尚未接入：

1. 数据库持久化。
2. 对象存储。
3. 外部事件总线。
4. 可跨进程恢复的 session/run 状态。

## 4.5 真正的多智能体执行

当前有 agent factory、skill registry、tool registry，但 orchestrator 主流程并未真正驱动：

1. 多角色 agent 实例化。
2. subtask 对应 skill 激活。
3. tool group 裁剪后执行。
4. 子任务级消息、记忆、推理与行动闭环。

因此现在更准确的描述是“已经有多智能体基础设施部件”，而不是“已经实现多智能体执行平台”。

---

## 5. 与设计文档的对应关系

对照 `007-010` 设计文档，当前实现大致处于下面这个位置：

### 已经基本落地的部分

1. Gateway 骨架。
2. Identity/Authorization 骨架。
3. Task / Session / Run / Replay / Artifact 基础模型。
4. Repository 抽象和内存版实现。
5. Event Bus MVP。
6. Orchestrator / Planner / Coordinator / Scheduler 第一轮骨架。
7. Query API 和 submit script 查询链。
8. SandboxProvider / OpenSandboxAdapter 的基础能力。

### 已有接口但未形成主闭环的部分

1. AgentFactory。
2. ToolRegistry。
3. SkillRegistry。
4. MemoryManager / LongTermMemory。
5. SandboxManager 与 artifact placeholder。

### 仍未落地的关键部分

1. subtask 真正执行。
2. run/task 终态推进。
3. 证据链与 replay 持续记录。
4. 持久化后端。
5. 真实多租户认证与策略。

---

## 6. 当前代码库最准确的阶段判断

如果用一句更工程化的话来描述当前状态：

**SwarmMind 当前已经完成了“任务提交、控制面建模、事件驱动规划、查询接口”这一层，但还没有完成“subtask 执行、证据回流、结果收敛”这一层。**

因此它现在最适合被视为：

1. 一个可运行的控制面原型。
2. 一个可继续接执行链的主干骨架。
3. 一个已经能支持 API 调试、task/run 查询和后续执行面扩展的基础版本。

而不应被描述为：

1. 已完成的多智能体执行平台。
2. 已完成的 sandbox 自动执行系统。
3. 已完成的 artifact/replay 完整闭环系统。

---

## 7. 建议如何阅读当前代码

如果要理解当前实现，推荐按下面顺序读：

1. `swarmmind/api/server.py`
2. `swarmmind/app/container.py`
3. `swarmmind/gateway/gateway.py`
4. `swarmmind/orchestration/task_orchestrator.py`
5. `swarmmind/orchestration/planner.py`
6. `swarmmind/query/service.py`
7. `swarmmind/sandbox/manager.py`
8. `swarmmind/agents/factory.py`

这样可以先建立当前“已经接通”的控制面主线，再去看那些已经写了但还没有挂进主流程的执行基础设施。
