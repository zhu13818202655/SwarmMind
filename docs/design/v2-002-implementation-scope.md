# SwarmMind V2 实施内容说明

> 这份文档定义“现在开始做 V2 时，我将实际实现什么”。
>
> 它不是重复 `v2-001` 的目标设计，也不是泛化路线图，而是把当前代码基线、第二轮目标、实现顺序、模块改造点和验收标准收敛成一份可以直接开工的文档。

关联文档：

- `010-current-code-implementation-status.md`
- `011-current-task-submit-sequence.md`
- `008-sandbox-system-design.md`
- `009-implementation-roadmap.md`
- `v2-001-sandbox-query-execution-plan.md`

---

## 1. 当前代码基线

基于当前仓库状态，已经落地并可工作的部分是：

1. FastAPI 已通过 `app container` 装配 `gateway / identity resolver / query service`。
2. `POST /v1/tasks` 已走 `gateway.submit_task()`，返回 `task_id / session_id / run_id / status`。
3. `GET /v1/tasks/{task_id}`、`GET /v1/tasks/{task_id}/detail`、`GET /v1/runs/{run_id}` 已可读取聚合状态。
4. `Gateway -> EventBus -> TaskOrchestrator` 的控制面链路已经接通。
5. Planner 可以生成 subtasks，Coordinator 可以给 subtasks 绑定 execution profile。
6. `SandboxManager`、`SandboxLease`、`SandboxExecution` 等执行面基础对象已经存在。

当前真正缺失的是：

1. `subtask.assigned` 之后没有执行器订阅。
2. sandbox 执行结果没有稳定写回 `subtask / run / task / artifact / replay`。
3. `run` 虽然进入 `executing`，但没有终态收敛逻辑。
4. 查询链虽然存在，但目前看到的主要仍是控制面状态，不是执行证据。

因此，V2 的本质不是重做 API 或重做模型，而是把“控制面已完成”推进成“执行面可运行、证据链可查询”。

---

## 2. 这轮 V2 的目标

这一轮 V2 我将完成四件事：

1. 把 `subtask.assigned` 接到真正的执行入口上，让 subtask 能进入 sandbox 执行。
2. 把执行输出沉淀成 artifact metadata 和 replay timeline，而不是只停留在内存对象里。
3. 把 `subtask -> run -> task` 的状态推进补齐，让任务能从 `executing` 进入最终状态。
4. 把脚本和查询接口调整到适合观察执行过程，而不是只看提交结果。

一句话描述：

**V2 要实现的是“subtask 被分配后能执行、执行后有证据、证据能查询、状态能收敛”的最小可运行闭环。**

### 2.1 V2 的基础设施选型

除了执行闭环本身，V2 的基础设施方向也明确固定为下面这组组合，不再继续保持模糊表述：

1. **关系数据库使用 PostgreSQL**
   用于保存 `task / session / run / subtask / artifact / replay / identity / policy` 等结构化主数据和元数据。

2. **缓存与热状态使用 Redis**
   用于保存热点查询缓存、运行中状态缓存、分布式锁，以及后续可演进到的 queue / stream 事件通道。

3. **向量检索使用 Qdrant**
   用于保存长期记忆 embedding、知识片段索引和后续 memory / retrieval 相关的语义召回数据。

这三个选型和现有设计文档是一致的：

1. PostgreSQL 是控制面元数据主库。
2. Redis 是运行态缓存与事件缓冲层。
3. Qdrant 是长期记忆和检索增强的向量底座。

也就是说，V2 不是抽象地说“未来会接数据库/缓存/向量库”，而是明确按 `PostgreSQL + Redis + Qdrant` 这个组合推进。

### 2.2 V2 的抽象原则

V2 应该保留“可替换能力”，但不应该为了可替换而做一层过度泛化的空接口。

推荐原则是：

1. **抽象业务能力边界，不抽象所有厂商差异。**
2. **先固定主实现，再保留替换点。**
3. **上层依赖协议或 repository，下层允许保留供应商特性。**

具体来说：

1. 对 PostgreSQL，不建议抽象成“任意关系数据库统一方言层”。
   V2 更合理的做法是抽象 `TaskRepository / RunRepository / ArtifactRepository / ReplayRepository / SessionRepository` 这类业务仓储接口，默认实现使用 PostgreSQL。

2. 对 Redis，不建议只定义一个非常宽泛的 `KeyValueStore` 然后要求所有缓存、锁、事件流都复用它。
   V2 更合理的做法是分别抽象：
   - `CacheStore`
   - `LockManager`
   - `EventBus` 或 `StreamBus`
   默认实现可以都落在 Redis 上，但接口语义要按能力拆开。

3. 对 Qdrant，不建议把所有向量库特性直接暴露到业务层。
   V2 更合理的做法是抽象 `LongTermMemory` 或 `VectorStore` 这类语义检索能力接口，由默认实现接 Qdrant；如果未来替换成 Milvus、pgvector 或 Weaviate，只替换这一层实现。

因此，V2 的目标不是“完全去供应商化”，而是：

1. 上层业务不直接写死 `psycopg/redis/qdrant-client`。
2. repository、cache、event bus、vector retrieval 的边界是稳定的。
3. 默认基础设施仍然明确选型为 `PostgreSQL + Redis + Qdrant`。

---

## 3. 这轮明确在范围内的内容

### 3.1 执行链接通

将新增一个执行层，把 `subtask.assigned` 事件接到 sandbox 执行上。

本轮会实现：

1. `ExecutionRunner` 或等价执行服务，负责消费 `subtask.assigned`。
2. 根据 `SubTask.metadata.execution_profile` 和 `sandbox_profile` 获取 sandbox lease。
3. 在 sandbox 中执行一个标准化命令或占位执行动作。
4. 生成 `SandboxExecution` 记录并回写 subtask 执行结果。

本轮不会实现：

1. 完整多智能体 ReAct 执行链。
2. 复杂 tool routing。
3. 真正的代码补丁生成和仓库级 agent 自主修改。

换句话说，这一轮先把“执行骨架”立住，再把复杂 agent 能力逐步挂上去。

### 3.2 证据链接通

将补齐 artifact 和 replay 两条证据写入路径。

本轮会实现：

1. `ArtifactCollector`，把 stdout、stderr、命令摘要和输出文件索引转成 `Artifact`。
2. `ReplayRecorder`，把关键事件追加到 `ReplayRoot.entries`。
3. 至少落地下面这些事件对应的 replay entry：
   - `subtask.assigned`
   - `subtask.started`
   - `sandbox.created`
   - `sandbox.command_started`
   - `sandbox.command_completed`
   - `artifact.created`
   - `subtask.completed`
   - `subtask.failed`
   - `run.updated`

本轮不会实现：

1. 对象存储上传。
2. 视频、截图、浏览器会话等富媒体回放。
3. 独立 replay UI。

### 3.3 状态收敛

将把当前停在 `run.phase=executing` 的流程推进到终态。

本轮会实现：

1. subtask 执行开始时，状态从 `pending` 更新到运行中间态或等价 metadata 标记。
2. subtask 执行完成后，更新为 `succeeded` 或 `failed`。
3. 每次 subtask 状态变化后，重新判断 run 是否完成。
4. 当全部 subtasks 完成时，推进 run 到 `succeeded/failed`。
5. run 终态后，推进 task 到 `succeeded/failed`，并写入结果摘要或错误摘要。

说明：当前 `TaskStatus` 已被 task 和 subtask 共用，本轮优先沿用现有模型，不额外引入一套全新的 subtask status enum，避免重构扩散。

### 3.4 查询与脚本观察能力增强

本轮会把现有查询链从“可查控制面”提升到“可查执行面摘要”。

本轮会实现：

1. `GET /v1/runs/{run_id}` 返回的 artifacts 不再只是空列表或占位列表。
2. `GET /v1/tasks/{task_id}/detail` 可以体现 run 的阶段推进与最终结果。
3. `scripts/submit_task.py` 优先轮询 run detail，并打印：
   - run status
   - run phase
   - subtasks 当前状态
   - artifact 摘要
4. 在任务结束后打印最终执行摘要，而不仅仅是初始提交结果。

---

## 4. 这轮明确不做的内容

为了保证 V2 能形成稳定闭环，这一轮不做下面这些高成本事项：

1. 第一阶段不强依赖 PostgreSQL / Redis / Qdrant 真正接通，允许先用 in-memory repository 跑通执行闭环。
2. 不做对象存储与真实 artifact 二进制上传，只先存 metadata。
3. 不做完整 OpenSandbox 生产级接入，只复用现有 adapter 和 manager 能力。
4. 不做 RBAC、多租户配额、审计后台等控制面增强。
5. 不做真正多 agent 协作执行，只保留未来接入点。
6. 不做前端 UI 或 replay 可视化界面。

这里要特别说明：

1. **V2 的目标存储架构已经确定为 PostgreSQL + Redis + Qdrant。**
2. **但本轮第一阶段实现允许先以内存实现打通主链，再替换到底层真实基础设施。**

这样做不是回避基础设施，而是为了避免“底层存储接入”和“执行闭环建立”两个高耦合任务相互阻塞。

---

## 5. 这轮计划新增或改造的模块

### 5.1 API 与应用装配

主要改动文件：

1. `swarmmind/api/server.py`
2. `swarmmind/app/container.py`

计划改动：

1. 保持现有 container 装配模式，不再回退到 API 层直接 new service。
2. 在 container 中注册新的执行相关服务。
3. 保持现有 `/v1/tasks`、`/v1/tasks/{task_id}/detail`、`/v1/runs/{run_id}` 路由不变，尽量只增强返回内容而不破坏接口形状。

### 5.2 Orchestration

主要改动文件：

1. `swarmmind/orchestration/task_orchestrator.py`
2. 新增 `swarmmind/orchestration/execution_runner.py`
3. 如有必要，新增 `swarmmind/orchestration/run_state_service.py` 或同类聚合服务

计划改动：

1. 保持 `TaskOrchestrator` 负责 planning/coordinating，不让它直接膨胀成“大一统执行器”。
2. 新增执行服务专门消费 `subtask.assigned`。
3. 执行服务负责 sandbox lease、命令执行、状态回写、事件发布。
4. run/task 终态收敛逻辑从单一方法中抽出，避免散落在 orchestrator 和 API 层。

### 5.3 Sandbox

主要改动文件：

1. `swarmmind/sandbox/manager.py`
2. 新增 `swarmmind/sandbox/artifact_collector.py`
3. 新增 `swarmmind/sandbox/replay_recorder.py`
4. 如有必要，补充 `swarmmind/sandbox/models.py`

计划改动：

1. 保留 `SandboxManager` 作为统一执行入口，不让上层直接调用 provider。
2. 将当前 `collect_artifacts()` 的占位实现升级为基于执行结果生成 metadata。
3. 为 replay 记录增加统一封装，避免各处手写 `ReplayEntry` 追加逻辑。
4. 如现有 `SandboxExecution` 字段不足，补充必要 metadata，但保持模型简单。

### 5.4 Query

主要改动文件：

1. `swarmmind/query/service.py`

计划改动：

1. 保持 `TaskDetail` 和 `RunDetail` 作为稳定读取模型。
2. 如需要，补充 replay 摘要或 artifact 摘要字段，但优先避免扩大响应面。
3. 确保 run detail 始终能反映 subtask 最新状态和 artifact 最新快照。

### 5.5 Script

主要改动文件：

1. `scripts/submit_task.py`

计划改动：

1. 默认按 run 视角输出状态。
2. 轮询时打印 phase 和 subtask 摘要。
3. 任务结束时打印 artifacts 摘要和失败原因。

### 5.6 Tests

计划新增或调整测试：

1. API 集成测试：提交任务后可通过 run detail 看到 subtasks 和 artifacts。
2. 执行链测试：`subtask.assigned` 被消费后能推进状态。
3. 失败场景测试：sandbox 执行失败后 run/task 能进入失败终态。
4. replay 测试：关键事件能写入 replay root。

### 5.7 Storage 与 Infrastructure 对接

这部分会作为 V2 的基础设施落点预留并逐步接入。

主要目标组件：

1. PostgreSQL
2. Redis
3. Qdrant

计划改动：

1. repository 接口保持稳定，允许先有 in-memory 实现，再补 PostgreSQL repository adapter。
2. query 层与 gateway 层不直接依赖具体存储实现，便于后续接 Redis cache。
3. memory 相关抽象保持与 Qdrant 兼容，避免后续再次改模型。
4. 事件总线后续优先向 Redis Streams 或同类机制演进，但不在第一阶段强制落地。

进一步约束：

1. PostgreSQL 通过 repository adapter 接入，而不是通过 `DatabaseProvider` 这种过宽接口直达业务层。
2. Redis 至少拆成 cache、lock、event stream 三类能力接口，避免一个抽象承载过多职责。
3. Qdrant 通过 `LongTermMemory` 或 `VectorStore` 抽象接入，embedding 生成逻辑与向量库存储逻辑分离。
4. 所有上层服务只能依赖抽象和 DTO，不能直接依赖第三方客户端对象。

---

## 6. 目标执行流

V2 完成后，主流程应收敛为下面这条链：

```text
POST /v1/tasks
  -> Gateway.submit_task()
  -> create session/task/run/replay root
  -> publish task.created
  -> TaskOrchestrator planning/coordinating
  -> publish subtask.assigned
  -> ExecutionRunner consumes subtask.assigned
  -> acquire sandbox lease
  -> publish subtask.started / sandbox.created
  -> execute command in sandbox
  -> collect artifacts
  -> append replay entries
  -> update subtask state
  -> aggregate run state
  -> aggregate task state
  -> GET /v1/runs/{run_id} can observe the whole process
```

这个流程的关键约束是：

1. API 不直接参与执行。
2. Orchestrator 不直接承担所有执行细节。
3. 所有 sandbox 副作用都通过 `SandboxManager` 落地。
4. 所有对外观察都围绕 `run detail` 展开。

---

## 7. 关键数据与事件约定

### 7.1 SubTask metadata

V2 会继续使用并规范下面这些 metadata 字段：

1. `run_id`
2. `execution_profile`
3. `sandbox_profile`
4. `sandbox_id` 或 `lease_id`
5. `last_execution` 摘要

原则是：

1. 核心字段优先放模型显式字段。
2. 过渡期的执行附加信息先进入 metadata。
3. 不在本轮为了“结构完美”而大规模重构模型。

### 7.2 Artifact metadata

本轮产出的 artifact 至少包含：

1. `task_id`
2. `run_id`
3. `subtask_id`
4. `name`
5. `type`
6. `storage_ref`
7. `metadata`，其中可包含：
   - command
   - exit_code
   - content_length
   - source

### 7.3 Replay entries

Replay entry 的 payload 至少包含：

1. 事件类型
2. task_id / run_id / subtask_id
3. sandbox_id 或 lease_id
4. 命令摘要
5. 退出码
6. 关联 artifact id 列表

---

## 8. 实施顺序

为了让每一步都可验证，V2 按下面顺序实现。

### Step 1. 执行服务接线

目标：让 `subtask.assigned` 有消费者。

完成标准：

1. container 订阅 `subtask.assigned`。
2. 执行服务能读取 subtask/run/task。
3. 执行服务能发布 `subtask.started`。

### Step 2. Sandbox 执行骨架

目标：让 subtask 能进入 sandbox 执行并返回标准结果。

完成标准：

1. 获取 sandbox lease。
2. 执行一个标准化命令。
3. 生成 `SandboxExecution`。
4. 执行失败时可回写错误。

### Step 3. Artifact 与 replay 写入

目标：让执行结果形成证据链。

完成标准：

1. stdout/stderr 至少形成日志型 artifact metadata。
2. replay root 能追加关键 timeline entries。
3. `/v1/runs/{run_id}` 可查到 artifacts。

### Step 4. Run / Task 终态收敛

目标：让任务不会永远停留在 `executing`。

完成标准：

1. subtask 全部成功时 run 成功。
2. 任一关键 subtask 失败时 run 失败。
3. task 跟随最新 run 进入终态。

### Step 5. 查询与脚本增强

目标：让调试者能直观看到执行进度和结果。

完成标准：

1. submit script 默认展示 run 执行摘要。
2. 失败时能看到失败 subtask 和错误原因。
3. 完成时能看到 artifact 摘要。

### Step 6. 基础设施替换到 PostgreSQL / Redis / Qdrant

目标：把第一阶段打通的内存闭环，替换为真实基础设施版本。

完成标准：

1. PostgreSQL 承接 task/run/subtask/artifact/replay 元数据。
2. Redis 承接热点状态缓存，并为后续事件流预留统一入口。
3. Qdrant 承接长期记忆与检索向量数据。
4. 上层 API、gateway、orchestration、query 不需要因存储替换而改接口。
5. 替换发生在 adapter 层，而不是传播到业务服务层。

---

## 9. 验收标准

V2 完成后，至少满足下面这些验收条件：

1. `POST /v1/tasks` 提交后，系统不只生成 subtasks，还会继续消费 `subtask.assigned`。
2. 至少一个 subtask 可以进入 sandbox 执行，并返回标准化执行结果。
3. `GET /v1/runs/{run_id}` 在执行中可看到 run phase、subtasks 状态和 artifacts 快照。
4. 任务结束后，run 会进入 `succeeded` 或 `failed`，不再永久停在 `executing`。
5. task 会跟随 run 进入终态，并带结果摘要或错误摘要。
6. replay repository 中能查到关键 timeline entries。
7. `scripts/submit_task.py --poll` 可以展示执行过程，而不只是初始提交结果。
8. V2 的存储架构说明明确固定为 `PostgreSQL + Redis + Qdrant`，并且 repository 边界足以支持后续平滑替换。

---

## 10. 风险与约束

V2 实施时需要明确以下约束：

1. 当前 repository 是 in-memory，实现要接受“服务重启后状态丢失”的事实。
2. 当前 event bus 是同进程同步消费，执行链接上后要控制好处理时间，避免 API 提交请求阻塞过久。
3. 现阶段应避免把复杂 agent 推理链直接塞进 `subtask.assigned` 处理逻辑，否则调试面会迅速失控。
4. artifact 先存 metadata，不在本轮引入额外对象存储复杂度。

对应的工程策略是：

1. 先让执行逻辑保持简单、确定、可测。
2. 先打通状态推进和证据回流，再逐步替换执行内容。
3. 所有复杂能力都通过新增 service 注入，而不是把现有 orchestrator 改成巨型类。

---

## 11. 这份文档对应的最终交付

按照这份文档推进后，这一轮 V2 的交付物应该是：

1. 一条从 `subtask.assigned` 到 sandbox 执行的最小闭环。
2. 一条从 sandbox 执行结果到 artifact/replay 的证据闭环。
3. 一条从 subtask 状态变化到 run/task 终态收敛的状态闭环。
4. 一条以 `GET /v1/runs/{run_id}` 为核心观察入口的查询闭环。

如果用一句话概括这轮 V2 的完成定义：

**用户提交任务后，系统不仅能规划，还能执行；不仅能执行，还能留下证据；不仅能留下证据，还能被查询和验证。**