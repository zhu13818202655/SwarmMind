# SwarmMind 实施路线图

> 这份文档基于 `001-008` 的设计结果，回答一个最实际的问题：
>
> 如果接下来开始改代码，应该按什么顺序推进，先改什么，后改什么，哪些是前置依赖，哪些可以并行。

当前阶段目标：

- 不直接写代码实现
- 先把实施顺序、模块拆分、验收标准和风险控制定下来

---

## 1. 总体原则

后续代码改造不建议“大爆炸式重构”，而应该遵循这四条原则：

1. **先立边界，再换实现**
   先确定对象模型、接口层和仓储抽象，再替换底层逻辑。

2. **先控制面，后执行面**
   先把 Gateway、Identity、Task/Run/Session 和 Repository 定下来，再推进多智能体执行链。

3. **先写模型和接口，再接基础设施**
   先定义统一模型与 repository 接口，再接 Postgres、Redis、MinIO、Qdrant、Event Bus。

4. **先形成闭环，再提升能力**
   先打通从用户请求到任务执行再到结果回放的最小闭环，再增强 memory、sandbox、RBAC、replay 等能力。

---

## 2. 推荐实施顺序

推荐分成 8 个阶段推进。

```text
Phase 0  基础建模与边界整理
Phase 1  Gateway / Identity 骨架
Phase 2  Task / Session / Run / Artifact / Replay 持久化
Phase 3  Event Bus 与状态流转
Phase 4  Orchestrator / Planner / Coordinator 重构
Phase 5  Skill / Tool / ExecutionProfile 装配闭环
Phase 6  Memory / Sandbox / Artifact / Replay 深度接入
Phase 7  Query API / Observability / Hardening
```

---

## 3. Phase 0：基础建模与边界整理

### 3.1 目标

把当前代码里最容易漂移的基础对象先统一掉。

### 3.2 要完成的内容

1. 明确并固定这些模型：
   - `Tenant`
   - `User`
   - `IdentityContext`
   - `Session`
   - `Task`
   - `Run`
   - `SubTask`
   - `Artifact`
   - `Replay`
   - `ExecutionProfile`

2. 明确这些枚举和能力模型：
   - `AgentRole`
   - `ToolGroup`
   - `SkillProfile`
   - task/subtask state enums

3. 清理模型职责边界：
   - `Task` 不再承载所有运行期细节
   - `Run` 承接执行态
   - `Artifact` 和 `Replay` 独立建模

### 3.3 主要影响文件

- `swarmmind/models/*`
- `swarmmind/agents/config.py`
- `swarmmind/orchestration/task_decomposer.py`

### 3.4 验收标准

1. 核心对象都能被稳定 import
2. 旧代码不再继续向 `Task.result` 塞杂项大对象
3. 后续模块都能围绕统一模型继续开发

---

## 4. Phase 1：Gateway / Identity 骨架

### 4.1 目标

把当前内存版 gateway 升级成“入口控制骨架”，但先不接复杂基础设施。

### 4.2 要完成的内容

1. 引入：
   - `TaskEnvelope`
   - `SessionContext`
   - `RunContext`

2. 拆分 Gateway 逻辑：
   - `request_normalizer`
   - `admission`
   - `session_manager`
   - `dispatcher`

3. 加入 Identity 骨架：
   - API key 验证接口
   - `IdentityResolver`
   - `AuthorizationPolicy` 占位实现

4. `create_task` 过程改成：
   - 接身份上下文
   - 生成 `task_id + session_id + run_id`
   - 提交任务而不是内联执行

### 4.3 主要影响文件

- `swarmmind/gateway/gateway.py`
- `swarmmind/api/server.py`
- 新增 `swarmmind/identity/*`
- 新增 `swarmmind/gateway/*`

### 4.4 验收标准

1. API/CLI 请求具备 `tenant/user/session/run` 上下文
2. Gateway 与 Orchestrator 边界清晰
3. 身份信息可进入 task 生命周期

---

## 5. Phase 2：Repository 与持久化骨架

### 5.1 目标

把当前内存表升级成 repository 抽象，先不追求所有底层都真实连接。

### 5.2 要完成的内容

1. 定义 repository 接口：
   - `TaskRepository`
   - `SessionRepository`
   - `RunRepository`
   - `ArtifactRepository`
   - `ReplayRepository`

2. 先提供内存版实现，便于不阻塞上层开发。

3. 定义 storage adapter 占位：
   - Postgres adapter
   - Object store adapter
   - Redis adapter

4. 所有上层模块改为只依赖 repository 接口。

### 5.3 主要影响文件

- 新增 `swarmmind/repositories/*`
- 新增 `swarmmind/storage/*`
- `swarmmind/gateway/*`
- `swarmmind/orchestration/*`

### 5.4 验收标准

1. Gateway / Orchestrator 不再直接维护 `_tasks/_sessions` 这类内部字典
2. 数据访问统一走 repository
3. 后续接数据库不会影响业务模块接口

---

## 6. Phase 3：Event Bus 与状态流转

### 6.1 目标

把“同步直接调用”逐步变成事件驱动的状态推进。

### 6.2 要完成的内容

1. 定义统一事件 envelope
2. 引入事件发布/订阅接口
3. 先实现内存总线或 Redis Streams MVP
4. 首批事件包括：
   - `task.created`
   - `run.created`
   - `task.planning.completed`
   - `subtask.assigned`
   - `subtask.completed`
   - `run.succeeded`
   - `run.failed`

### 6.3 主要影响文件

- 新增 `swarmmind/events/*`
- `swarmmind/gateway/*`
- `swarmmind/orchestration/*`
- `swarmmind/memory/*`

### 6.4 验收标准

1. task 创建后可以通过事件启动 orchestrator
2. 关键状态变化都有事件
3. 事件具备 `tenant_id / task_id / run_id / session_id`

---

## 7. Phase 4：Orchestrator / Planner / Coordinator 重构

### 7.1 目标

把当前串行 `TaskOrchestrator` 改造成真正的控制流核心。

### 7.2 要完成的内容

1. 引入 `TaskGraph`
2. 支持 ready queue / dependency resolution
3. 区分 `Planner` 和 `Coordinator` 逻辑
4. 引入 run phase 和 subtask state 流转
5. 支持 repair / retry / fallback

### 7.3 主要影响文件

- `swarmmind/orchestration/task_orchestrator.py`
- `swarmmind/orchestration/state_machine.py`
- `swarmmind/orchestration/task_decomposer.py`
- 新增 `dag.py`, `scheduler.py`, `coordinator.py`

### 7.4 验收标准

1. 一个 task 可以拆成多个 subtasks
2. subtasks 可以按依赖推进
3. 失败后可局部重试而不是整单重跑

---

## 8. Phase 5：Skill / Tool / ExecutionProfile 装配闭环

### 8.1 目标

把之前设计的 `role -> skill -> tool groups` 真正接入执行链。

### 8.2 要完成的内容

1. Coordinator 根据 subtask 生成 `ExecutionProfile`
2. Skill registry 支持按角色/skill profile 装配
3. Tool registry 支持按 `ToolGroup` 裁剪工具可见集合
4. Agent factory 支持临时装备 skills / tools

### 8.3 主要影响文件

- `swarmmind/skills/*`
- `swarmmind/tools/*`
- `swarmmind/agents/factory.py`
- `swarmmind/orchestration/*`

### 8.4 验收标准

1. 不同 subtask 可以拿到不同的 tool 可见集合
2. 同一角色可以按 skill profile 切换执行套路
3. Agent 不再以“固定全量工具集”运行

---

## 9. Phase 6：Memory / Sandbox / Artifact / Replay 深度接入

### 9.1 目标

把记忆系统、sandbox 执行面、artifact 留存和 replay 证据链真正接入运行闭环。

### 9.2 要完成的内容

1. Memory 分层：
    - working memory
    - task/session summary
    - long-term memory

2. Sandbox 重构：
    - 引入 `SandboxLease` / `SandboxExecution` / `SandboxStatus`
    - profile policy
    - artifact collector
    - cleanup / orphan scan

3. Artifact / Replay：
    - 统一 artifact metadata
    - transcript 与 object store 分离
    - replay 只依赖证据链，不依赖存活容器

### 9.3 主要影响文件

- `swarmmind/memory/*`
- `swarmmind/sandbox/*`
- 新增 `swarmmind/artifacts/*`
- 新增 `swarmmind/replay/*`
- `swarmmind/orchestration/*`

### 9.4 验收标准

1. 任一 sandbox 执行都能回收到 artifact metadata
2. transcript 不再承担大对象存储职责
3. 任务失败后可以基于证据链定位执行问题

---

## 10. Phase 7：Query API / Observability / Hardening

### 10.1 目标

把系统从“能跑”升级到“能查、能审、能运维”。

### 10.2 要完成的内容

1. 查询接口：
    - task detail
    - run detail
    - artifact list
    - replay entry

2. 可观测：
    - structured logs
    - metrics
    - trace ids

3. 加固：
    - quota
    - timeout policy
    - retry policy
    - idempotency

### 10.3 主要影响文件

- `swarmmind/api/*`
- `swarmmind/gateway/*`
- 新增 `swarmmind/observability/*`
- 新增 `swarmmind/query/*`

### 10.4 验收标准

1. 可以按 task_id 查询完整运行摘要
2. 可以按 run_id 查看 subtasks / artifacts / replay refs
3. 系统出现失败时可以定位到具体 phase / agent / sandbox

---

## 11. 按当前仓库的目录改造建议

这一节不是抽象路线，而是直接对应当前 `swarmmind/` 目录，说明哪些可以保留，哪些建议重写。

### 11.1 建议保留并演进的目录

1. `swarmmind/models`
2. `swarmmind/sandbox/provider.py`
3. `swarmmind/sandbox/opensandbox_adapter.py`
4. `swarmmind/skills`
5. `swarmmind/tools`

保留的意思不是不改，而是：

- 可以继续作为接口层或领域层演进
- 不需要为了新架构彻底删除

### 11.2 建议整体重写的目录或文件

1. `swarmmind/gateway`
2. `swarmmind/api/server.py`
3. `swarmmind/orchestration`
4. `swarmmind/memory`
5. `swarmmind/cli.py`
6. `swarmmind/agents/factory.py`

### 11.3 建议新增的目录

1. `swarmmind/identity`
2. `swarmmind/repositories`
3. `swarmmind/storage`
4. `swarmmind/events`
5. `swarmmind/artifacts`
6. `swarmmind/replay`
7. `swarmmind/observability`
8. `swarmmind/query`

### 11.4 建议的 sandbox 目录重组

当前 `swarmmind/sandbox` 只有：

- `provider.py`
- `opensandbox_adapter.py`
- `profiles.py`
- `manager.py`

后续建议拆成：

```text
swarmmind/sandbox/
   __init__.py
   models.py                 # SandboxProfile / SandboxLease / SandboxExecution / SandboxStatus
   provider.py               # provider protocol
   runtime/
      __init__.py
      opensandbox_adapter.py
   policy/
      __init__.py
      profile_policy.py
      quota_policy.py
   manager/
      __init__.py
      sandbox_manager.py
      lease_manager.py
      cleanup_manager.py
   tools/
      __init__.py
      command_tool.py
      file_tool.py
      browser_tool.py
   audit/
      __init__.py
      execution_recorder.py
      artifact_collector.py
      replay_recorder.py
   profiles.py
```

这样拆的目的很明确：

1. runtime 适配层和控制层分开
2. policy 单独治理 profile / quota / timeout
3. audit 能独立承接 artifact / replay 证据留存
4. sandbox-aware tools 不再散落到通用 tool 层里

---

## 12. 第一轮重写建议交付物

如果按“受控重写”推进，建议第一轮不要试图把所有能力一次写完，而是只交付一个可闭环的骨架版本。

### 12.1 第一轮必须交付

1. 新的 `identity` 骨架
2. 新的 `gateway` 骨架
3. `Task / Session / Run` repository 接口 + 内存实现
4. event bus 内存实现
5. 新的 orchestrator interface
6. sandbox profile + manager 重构骨架

### 12.2 第一轮可以暂缓

1. 真正的 Postgres
2. 真正的 Redis Streams
3. 真正的 Qdrant
4. 完整 RBAC
5. 完整 replay UI

### 12.3 第一轮验收方式

建议用一个固定场景验收：

1. 用户提交一个 build/test 类任务
2. gateway 生成 `task/session/run`
3. orchestrator 生成 subtasks
4. coordinator 为执行 subtask 申请 sandbox
5. tool 在 sandbox 里执行命令
6. stdout / stderr / output file 被收集为 artifacts
7. API 能查询 task 和 run 摘要

只要这条链打通，后续所有增强都可以围绕它展开。

---

## 13. 目标代码结构

为了让 `009` 能直接指导改造，下面给出一版目标目录结构。它不是必须一步到位全部创建，而是作为重写过程中的稳定目标。

```text
swarmmind/
   __init__.py
   app/
      __init__.py
      bootstrap.py
      container.py
   api/
      __init__.py
      server.py
      deps.py
      schemas.py
   identity/
      __init__.py
      models.py
      resolver.py
      policy.py
      auth.py
   gateway/
      __init__.py
      gateway.py
      request_normalizer.py
      admission.py
      session_manager.py
      dispatcher.py
      envelopes.py
   models/
      __init__.py
      capability.py
      execution.py
      task.py
      run.py
      session.py
      artifact.py
      replay.py
      event.py
   repositories/
      __init__.py
      task_repository.py
      run_repository.py
      session_repository.py
      artifact_repository.py
      replay_repository.py
      memory_repository.py
      in_memory/
         __init__.py
         task_repository.py
         run_repository.py
         session_repository.py
         artifact_repository.py
         replay_repository.py
   storage/
      __init__.py
      object_store.py
      postgres.py
      redis.py
      vector_store.py
   events/
      __init__.py
      bus.py
      models.py
      publishers.py
      subscribers.py
      in_memory_bus.py
   orchestration/
      __init__.py
      task_orchestrator.py
      planner.py
      coordinator.py
      scheduler.py
      dag.py
      state_machine.py
      task_decomposer.py
   agents/
      __init__.py
      config.py
      factory.py
      prompts/
   memory/
      __init__.py
      manager.py
      working_memory.py
      summarizer.py
      long_term.py
      transcript.py
      capture.py
      recall.py
   sandbox/
      __init__.py
      models.py
      provider.py
      profiles.py
      runtime/
         __init__.py
         opensandbox_adapter.py
      policy/
         __init__.py
         profile_policy.py
         quota_policy.py
      manager/
         __init__.py
         sandbox_manager.py
         lease_manager.py
         cleanup_manager.py
      tools/
         __init__.py
         command_tool.py
         file_tool.py
         browser_tool.py
      audit/
         __init__.py
         execution_recorder.py
         artifact_collector.py
         replay_recorder.py
   artifacts/
      __init__.py
      service.py
      models.py
   replay/
      __init__.py
      service.py
      timeline.py
   skills/
      __init__.py
      base.py
      registry.py
      build_app.py
      write_report.py
   tools/
      __init__.py
      registry.py
      builtin/
         __init__.py
         search.py
         browser.py
         mail.py
   observability/
      __init__.py
      logging.py
      tracing.py
      metrics.py
   query/
      __init__.py
      service.py
```

---

## 14. 模块级落地说明

### 14.1 app

`app` 层负责装配，不承载业务规则。

需要完成：

1. 统一容器创建顺序
2. 统一注册 repositories / event bus / gateway / orchestrator
3. 给 API 和 CLI 提供相同的 bootstrap 入口

### 14.2 api

`api` 层只负责 HTTP 协议适配，不应直接写业务逻辑。

需要完成：

1. 把路由模型和领域模型分开
2. 通过依赖注入获取 gateway 和 query service
3. 保持 API 只做 request/response 转换

### 14.3 identity

这是当前仓库缺失最明显的一层。

第一轮至少要有：

1. `IdentityContext`
2. `IdentityResolver`
3. `AuthorizationPolicy`
4. API key 或 token 的最小校验流程

### 14.4 gateway

重写后的 gateway 只承担四件事：

1. 请求归一化
2. 准入控制
3. session / task / run 上下文建立
4. 提交执行请求并暴露查询入口

它不负责：

1. 具体 subtask 调度
2. tool 调用
3. sandbox 生命周期细节

### 14.5 repositories

先定义接口，再提供内存实现。第一轮不要求接真实数据库。

接口必须保证：

1. 方法名是业务语义
2. 返回的是领域对象
3. 上层不关心底层是内存还是数据库

### 14.6 events

第一轮直接使用 in-memory event bus 即可，但事件 envelope 必须一次设计对。

第一批事件建议固定为：

1. `task.created`
2. `run.created`
3. `task.planning.completed`
4. `subtask.ready`
5. `subtask.assigned`
6. `subtask.completed`
7. `subtask.failed`
8. `run.succeeded`
9. `run.failed`
10. `sandbox.created`
11. `sandbox.command_completed`
12. `artifact.created`

### 14.7 orchestration

这一层是整次重写的核心。

建议拆分为：

1. `TaskOrchestrator`
    负责接事件、推进任务阶段。
2. `Planner`
    负责生成 task graph。
3. `Coordinator`
    负责选 ready subtasks、绑定 execution profile、触发执行。
4. `Scheduler`
    负责 ready queue 和依赖判断。
5. `StateMachine`
    负责 task/run/subtask 状态流转校验。

### 14.8 agents

AgentFactory 需要从“创建单个 ReActAgent”改为“按 execution profile 动态装配 agent”。

第一轮至少要支持：

1. 按 `AgentRole` 选择 prompt
2. 按 `SkillProfile` 选择 skills
3. 按 `ToolGroup` 裁剪 tools

### 14.9 memory

第一轮不追求复杂 RAG，但至少要分开三层：

1. working memory
2. transcript / summary
3. long-term memory

其中 transcript 必须保留，但不再承担全部 memory 责任。

### 14.10 sandbox

按 `008` 的设计执行。第一轮重点不是 feature 多，而是边界对。

第一轮优先级：

1. 统一 `SandboxProfile`
2. 统一 `SandboxLease`
3. 统一 `SandboxExecution`
4. 统一 artifact 回收
5. 统一 cleanup 机制

### 14.11 artifacts / replay

这两层第一轮先做 service abstraction 即可。

要求：

1. artifact 有 metadata 和 storage ref
2. replay 有 root 和 timeline entry
3. sandbox / orchestrator / query 都只操作 service 接口

### 14.12 query / observability

第一轮只要做最小闭环：

1. task detail query
2. run detail query
3. 统一结构化日志
4. trace ids 串 task/run/subtask/sandbox

---

## 15. 第一轮实际开发包

为了避免一次性铺太大，建议把第一轮拆成四个开发包。

### 包 A：统一模型和上下文

交付：

1. `Run` / `Session` / `Artifact` / `Replay` 模型
2. `IdentityContext`
3. `TaskEnvelope` / `RunContext` / `SessionContext`

验收：

1. API 创建任务时可以生成 task/session/run 三元组

### 包 B：入口与持久化骨架

交付：

1. 新 gateway
2. repositories 接口
3. repositories 内存实现
4. API 改接 gateway service

验收：

1. API 不再直接依赖内存字典

### 包 C：执行控制流骨架

交付：

1. event bus 内存实现
2. orchestrator / planner / coordinator / scheduler 骨架
3. subtask state machine

验收：

1. task 创建后可以异步推进到 subtasks

### 包 D：sandbox 闭环

交付：

1. sandbox manager 新骨架
2. sandbox-aware command/file tools
3. artifact collector
4. run 级 execution record

验收：

1. 一个 build/test 任务可以在 sandbox 中执行并收集 artifacts

---

## 16. 接口契约建议

下面这些接口建议尽早固定，因为一旦定住，上下游就能并行开发。

### 16.1 Gateway

```python
class Gateway(Protocol):
      async def submit_task(self, request: TaskSubmitRequest, identity: IdentityContext) -> TaskSubmissionResult: ...
      async def get_task(self, task_id: str, identity: IdentityContext) -> TaskDetail | None: ...
      async def get_run(self, run_id: str, identity: IdentityContext) -> RunDetail | None: ...
```

### 16.2 EventBus

```python
class EventBus(Protocol):
      async def publish(self, event: DomainEvent) -> None: ...
      async def subscribe(self, topic: str, handler: EventHandler) -> None: ...
```

### 16.3 TaskRepository

```python
class TaskRepository(Protocol):
      async def create(self, task: Task) -> Task: ...
      async def get(self, task_id: str) -> Task | None: ...
      async def save(self, task: Task) -> Task: ...
      async def list_by_status(self, status: TaskStatus | None = None) -> list[Task]: ...
```

### 16.4 RunRepository

```python
class RunRepository(Protocol):
      async def create(self, run: Run) -> Run: ...
      async def get(self, run_id: str) -> Run | None: ...
      async def save(self, run: Run) -> Run: ...
      async def list_for_task(self, task_id: str) -> list[Run]: ...
```

### 16.5 SandboxManager

```python
class SandboxManager(Protocol):
      async def acquire(self, request: SandboxLeaseRequest) -> SandboxLease: ...
      async def run_command(self, lease: SandboxLease, command: CommandRequest) -> SandboxExecution: ...
      async def write_files(self, lease: SandboxLease, files: list[WriteFileEntry]) -> None: ...
      async def collect_artifacts(self, lease: SandboxLease) -> list[Artifact]: ...
      async def release(self, lease_id: str) -> None: ...
```

### 16.6 QueryService

```python
class QueryService(Protocol):
      async def get_task_detail(self, task_id: str, identity: IdentityContext) -> TaskDetail | None: ...
      async def get_run_detail(self, run_id: str, identity: IdentityContext) -> RunDetail | None: ...
```

---

## 17. 迭代顺序与时长建议

如果按小团队推进，建议按 4 个 sprint 来做第一轮重写。

### Sprint 1

范围：

1. models
2. identity
3. gateway envelopes
4. repository interfaces

产出：

1. 新对象模型稳定
2. API 可以产出标准 task/session/run 上下文

### Sprint 2

范围：

1. gateway 重写
2. API 改接 service
3. in-memory repositories
4. in-memory event bus

产出：

1. 从 HTTP/CLI 到 gateway/repository/event bus 的入口闭环

### Sprint 3

范围：

1. orchestrator
2. planner
3. coordinator
4. scheduler
5. state machine

产出：

1. 一个 task 可以拆成 subtasks 并推进生命周期

### Sprint 4

范围：

1. sandbox manager
2. sandbox-aware tools
3. artifact collector
4. query service
5. structured logging

产出：

1. build/test 场景完整跑通

---

## 18. 风险、迁移与最终建议

### 18.1 关键风险

1. 一边重写一边继续补旧 gateway/orchestrator，最终会形成双轨代码。
2. 过早接真实基础设施，会把接口层绑死在 SDK 细节上。
3. 继续让 `Task.result` 承担执行明细，会让对象边界再次失控。

### 18.2 迁移策略

建议采用“旁路重写”而不是“原地缝补”。

具体做法：

1. 先保留旧代码，但不再扩展旧主链路。
2. 新代码按新目录和新接口落地。
3. API 先切到新 gateway。
4. orchestrator、sandbox、query 再逐步切换。
5. 当新链路打通后，再删除旧 gateway / memory / orchestrator 的旧实现。

### 18.3 最终建议

如果现在开始真正动手，最合理的起点不是写功能，而是先建立这五个稳定边界：

1. `IdentityContext`
2. `Task/Session/Run` 对象关系
3. repository interfaces
4. event bus envelope
5. sandbox manager protocol

这五个边界一旦稳定，后面的实现就会从“边写边猜”变成“按契约装配”。

一句话总结：

**`009` 的真正落地方式不是继续补当前 demo，而是围绕统一边界做一次受控重写，并用四个 sprint 打穿第一条闭环。**
