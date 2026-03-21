# SwarmMind V2 落地方案：Sandbox 执行、Artifact/Replay 证据链与 Query API

> 这份文档回答第二轮改造的两个核心问题：
>
> 1. 如何把真正的 sandbox 执行、artifact 回收和 replay 证据链接到当前第一轮骨架上。
> 2. 如何把 FastAPI 切到新的 container / gateway / query service，并提供可查询 task/run 执行状态的 API。

这份文档是对 `008` 和 `009` 的继续，不替代它们，而是把第二轮要做的事情收敛成一份可执行设计。

关联文档：

- `008` Sandbox 系统设计与使用方案
- `009` 实施路线图

---

## 1. 第二轮的目标

第一轮已经完成的事情是：

1. 建立 `task / session / run` 控制面对象
2. 建立 gateway / repository / event bus / orchestrator 的最小骨架
3. 支持通过 in-memory container 跑通提交任务到生成 subtasks 的闭环

第二轮要解决的是第一轮尚未真正接上的三条链：

1. **执行链**
   让 subtask 不只是“被分配”，而是进入真正的 sandbox 执行。

2. **证据链**
   让执行输出形成 artifact metadata 和 replay timeline，而不是只停留在内存对象中。

3. **查询链**
   让 API 和脚本能查询 task / run / subtask / artifact 的当前状态，支持“正在执行时查询”和“任务结束后查询”。

一句话说：

**第二轮的目标是把第一轮的控制面骨架，推进成一个可查询、可观察、可留证据的执行闭环。**

---

## 2. 第二轮范围

### 2.1 在范围内

1. 将 FastAPI 切到 `app container + gateway + query service`
2. 增加 `/v1/runs/{run_id}` 查询接口
3. 增加 task detail / run detail 查询能力
4. 建立 sandbox execution record 模型
5. 建立 artifact collector 和 replay recorder 抽象
6. 让 submit script 能打印 run/subtask 详情

### 2.2 不在范围内

1. 完整的 OpenSandbox 真实执行链
2. 真正的对象存储上传
3. 真实数据库持久化
4. 完整 RBAC / 多租户配额
5. 完整 replay UI

第二轮的重点仍然是“边界稳定”和“接口打通”，不是一次到位做成生产系统。

---

## 3. 第二轮总体思路

第二轮不重写新的主干，而是在现有第一轮骨架上补三层：

```text
Client / Script
   -> FastAPI
   -> App Container
   -> Gateway / QueryService
   -> Repositories / EventBus
   -> Orchestrator
   -> Coordinator
   -> SandboxManager
   -> ArtifactCollector / ReplayRecorder
```

### 3.1 API 层

FastAPI 不再直接 new `Gateway()`，而是通过 `app.get_container()` 获取：

- gateway
- identity resolver
- query service

这样 API 层和脚本、测试脚本共用同一套应用装配。

### 3.2 Query 层

新增两个稳定读取模型：

1. `TaskDetail`
2. `RunDetail`

其中 `RunDetail` 至少包含：

- run 基本状态
- run phase
- subtasks 列表
- artifacts 列表

### 3.3 Sandbox 层

第二轮先不追求完整真实执行，而是先建立：

1. `SandboxLease`
2. `SandboxExecution`
3. `ArtifactCollector`
4. `ReplayRecorder`

也就是说，先把“执行记录”和“证据留存”的契约立住，再把真实的 OpenSandbox 执行接进去。

---

## 4. API 改造方案

### 4.1 POST /v1/tasks

#### 当前问题

当前接口仍然使用旧的 `gateway.create_task()` 兼容路径，只返回简化 task 状态。

#### V2 调整

改成调用：

- `gateway.submit_task()`

返回值至少包含：

- `task_id`
- `session_id`
- `run_id`
- `status`

这样客户端在提交成功后就能立即拿到 run 入口。

### 4.2 GET /v1/tasks/{task_id}

保留这个接口作为 task summary 查询。

建议返回：

- task 基本信息
- 当前最新 run_id，可选
- 当前状态

### 4.3 GET /v1/tasks/{task_id}/detail

新增 detail 接口，用于获取更完整的 task 视图。

建议返回：

- task
- session
- runs[]

这个接口更适合调试和管理台使用。

### 4.4 GET /v1/runs/{run_id}

这是第二轮必须加的接口。

建议返回：

- run
- subtasks[]
- artifacts[]

这个接口是脚本、前端和后续运维排障的核心入口。

它需要支持两种状态：

1. **正在执行时可查**
   返回当前 run phase、已分配 subtasks、当前 artifacts。

2. **任务结束后可查**
   返回最终 run 状态、subtask 结果、artifacts 和错误摘要。

---

## 5. Submit Script 改造方案

第二轮后，`submit_task.py` 建议支持下面的输出路径：

### 5.1 提交后立即打印

- task_id
- session_id
- run_id
- status

### 5.2 轮询任务状态时

如果只查 task summary，用户只能看到 task 级状态，不足以判断执行细节。

因此建议改为：

1. 提交任务
2. 如果 response 带有 `run_id`，就优先轮询 `/v1/runs/{run_id}`
3. 打印：
   - run status
   - run phase
   - subtasks 数量
   - subtasks 当前状态

### 5.3 任务结束后打印

结束时打印：

- run 最终状态
- subtasks 最终结果摘要
- artifacts 摘要

这样脚本就不仅仅是“提交任务”，而是“观察一次执行过程”。

---

## 6. Sandbox 执行与证据链接入方案

### 6.1 当前问题

当前 orchestrator 只做：

1. planner 生成 subtasks
2. coordinator 绑定 execution profile
3. 发布 `subtask.assigned`

但没有真正执行 subtask，也没有产出 artifact/replay 记录。

### 6.2 第二轮要补的层

建议新增三个 service 抽象：

1. `ExecutionRunner`
   负责把 subtask 送入 sandbox manager 执行。

2. `ArtifactCollector`
   负责把 stdout/stderr/输出文件转成 artifact metadata。

3. `ReplayRecorder`
   负责把关键事件转成 replay entries。

### 6.3 典型执行流

```text
subtask.assigned
  -> Coordinator / Runner acquires sandbox lease
  -> SandboxManager executes command(s)
  -> SandboxExecution record created
  -> ArtifactCollector extracts metadata
  -> ReplayRecorder appends timeline entries
  -> Subtask status updates
  -> Run detail becomes queryable
```

### 6.4 第二轮不做什么

第二轮不要求：

1. 真正把 stdout 文件上传到对象存储
2. 真正恢复回放
3. 完整展示 browser/video/screenshot artifacts

但必须先把 metadata 和接口打通。

---

## 7. Repository 层需要补的内容

为了让 run 查询有意义，第二轮至少要补下面几类数据的写入：

1. `SubTaskRepository.save()` 在状态变化时及时持久化
2. `ArtifactRepository.create()` 支持 run 查询
3. `ReplayRepository.save()` 支持 replay timeline 增量更新

如果不把这些写入打通，API 虽然有 `/v1/runs/{run_id}`，但只能看到空数据。

---

## 8. 事件设计建议

第二轮建议固定一组 run 查询相关事件：

1. `subtask.assigned`
2. `subtask.started`
3. `sandbox.created`
4. `sandbox.command_started`
5. `sandbox.command_completed`
6. `artifact.created`
7. `subtask.completed`
8. `subtask.failed`
9. `run.updated`

这些事件的价值是：

1. replay timeline 可以基于它们构建
2. API 可以基于 repository 快照查询当前状态
3. 后续做 WebSocket 或 SSE 推送时也可以直接复用

---

## 9. 推荐代码改造点

### 9.1 API

- `swarmmind/api/server.py`

### 9.2 Query

- `swarmmind/query/service.py`

### 9.3 Orchestration

- `swarmmind/orchestration/task_orchestrator.py`
- 新增 `execution_runner.py`，可选

### 9.4 Sandbox

- `swarmmind/sandbox/manager.py`
- 新增 `artifact_collector.py`
- 新增 `replay_recorder.py`

### 9.5 Scripts

- `scripts/submit_task.py`

---

## 10. 验收标准

第二轮完成后，至少应该满足：

1. FastAPI 已切到 `app container`，不再在 API 层直接 new 旧 gateway。
2. `POST /v1/tasks` 返回 `task_id + session_id + run_id + status`。
3. `GET /v1/runs/{run_id}` 可以查询 run 当前状态。
4. run 查询结果包含 subtasks 列表。
5. 任务执行中可以查到当前 run phase。
6. 任务结束后可以查到最终 subtask 状态和 artifacts 摘要。
7. submit script 可以打印 run 详情，而不只是 task summary。

---

## 11. 最小落地顺序

推荐按下面顺序推进：

1. 先改 API 到 container/query service。
2. 再加 `/v1/runs/{run_id}` 和 `/v1/tasks/{task_id}/detail`。
3. 再改 submit script，让它优先轮询 run detail。
4. 再补 sandbox execution record / artifact collector / replay recorder 的抽象。
5. 最后再把真实 OpenSandbox 执行接进去。

这个顺序的好处是：

- 前三步先把“可观察性”补齐
- 后两步再把“真实执行和证据链”补齐

这样每一步都有可见价值，不会陷入长时间重构但无法验证的状态。

---

## 12. 最终建议

第二轮不要被理解成“把所有 sandbox 功能一次接完”。

更合理的理解是：

**先把 run 作为一等查询对象建立起来，再把 sandbox 执行和证据链逐步挂到 run 上。**

一旦 `run detail` 这条链稳定下来：

1. 用户能看到任务到底执行到哪一步
2. 脚本和 UI 能看到 subtasks 的实时状态
3. artifact 和 replay 就有了统一挂载点
4. 后续接真实 OpenSandbox 也只是在这个框架内填充实现

所以第二轮的真正核心不是“多做几个工具”，而是：

**把执行过程从不可见、不可查，变成可查询、可留证据、可扩展。**