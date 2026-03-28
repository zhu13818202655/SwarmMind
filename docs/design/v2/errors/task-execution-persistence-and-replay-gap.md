# 任务执行中间结果无法回溯：默认 in-memory 模式导致 replay/artifact 不持久

## 1. 问题概述

当前系统并不是“没有中间结果模型”，而是“默认运行模式没有把这些中间结果放到可跨进程保存的存储里”。

从代码实现看，`task`、`run`、`subtask`、`artifact`、`replay` 这些对象都已经存在，查询 API 和事件流接口也已经接通；但默认配置下仓储层、事件总线、缓存和锁仍然主要使用 in-memory 实现。因此一旦 API 进程退出、重启，或者用户在另一个进程里查看，之前的执行过程就无法再回放。

这和“系统根本没有记录”是两回事：系统会在当前进程内记录，但默认不会 durable persistence。

---

## 2. 当前现状

## 2.1 已经存在的执行记录链路

当前仓库已经具备以下能力：

1. `Gateway.submit_task()` 在提交任务时会创建 `task`、`run` 和 `replay root`。
2. `ReplayRecorder` 已订阅 `*` 事件，并把事件持续追加到 `ReplayRepository`。
3. `ExecutionRunner` 会为子任务写入 `artifact`，并发布 `subtask.started`、`sandbox.created`、`sandbox.command_*`、`subtask.completed/failed` 等事件。
4. `QueryService.get_run_detail()` 可以聚合 `run + subtasks + artifacts`。
5. API 已暴露：
   - `GET /v1/runs/{run_id}`
   - `GET /v1/runs/{run_id}/events`
   - `GET /v1/runs/{run_id}/stream`

也就是说，从领域对象和查询接口的角度，系统已经有“回放整个任务执行中间结果”的骨架。

## 2.2 默认为什么还是看不到历史结果

问题出在默认装配：

1. `_build_repositories()` 只有在 `postgres.enabled=true` 时才会切到 PostgreSQL 仓储。
2. 否则默认返回：
   - `InMemoryTaskRepository`
   - `InMemorySessionRepository`
   - `InMemoryRunRepository`
   - `InMemorySubTaskRepository`
   - `InMemoryArtifactRepository`
   - `InMemoryReplayRepository`
3. 默认配置 `configs/default.yaml` 中：
   - `postgres.enabled=false`
   - `redis.enabled=false`
   - `vector_store.provider=memory`
   - `vector_store.enabled=false`

这意味着：

1. 当前进程内提交任务后，`run detail`、`artifacts`、`replay entries` 都能查到。
2. 但这些数据只活在 Python 进程内存里。
3. API 重启后，之前的任务执行轨迹直接丢失。
4. 如果未来变成多 worker/多实例，in-memory 模式也无法跨实例共享。

## 2.3 现在系统里实际存在的“模式”

当前并不是一个统一的 `mode=in_memory|persistent` 开关，而是多套基础设施分别切换。

### A. 执行状态仓储模式

这一层决定 `task/run/subtask/artifact/replay` 是否可持久化。

1. `in-memory`：默认模式。进程内可查，进程重启即丢。
2. `postgres`：持久化模式。`tasks/runs/subtasks/artifacts/replays` 全部落 PostgreSQL。

这是“能否回溯任务执行中间结果”的核心开关。

### B. 事件总线模式

这一层决定事件传播是否仅限单进程，是否适合多 worker。

1. `in-memory event bus`
2. `redis buffered event bus`

注意：

1. Redis 事件总线本身不等于 replay 持久化。
2. 即使开了 Redis，但仓储还是 in-memory，历史 `replay root` 仍然不会跨进程保存。

### C. Cache / Lock 模式

这一层影响缓存与分布式锁，不直接决定 replay 是否可回放。

1. `in-memory cache + in-memory lock`
2. `redis cache + redis lock`

### D. 长期记忆模式

这一层是 agent long-term memory，不是任务执行主状态仓储。

当前代码实际支持：

1. `memory`
2. `qdrant`
3. `chroma`

但配置 schema 与默认配置目前主要围绕 `memory/qdrant` 暴露，`chroma` 已有代码路径但还没有完全对齐配置文档。

### E. 实际可用的组合模式

从执行链路角度，当前可以整理成三种典型运行方式：

1. `纯本地演示模式`
   - repos: in-memory
   - event bus: in-memory
   - cache/lock: in-memory
   - long-term memory: memory
   - 特点：启动简单，但不可回放历史任务

2. `最小持久化模式`
   - repos: postgres
   - event bus: in-memory
   - cache/lock: in-memory
   - long-term memory: memory
   - 特点：单实例下已经能保留 task/run/subtask/artifact/replay

3. `完整基础设施模式`
   - repos: postgres
   - event bus: redis
   - cache/lock: redis
   - long-term memory: qdrant
   - 特点：适合多实例、可观测和后续 worker 化

---

## 3. 为什么这是一个真实缺口

这个问题会直接影响你现在做系统测试时的判断：

1. 用户从 API 视角看到任务已完成，但稍后想追溯 planner 输出、subtask 中间状态、artifact、replay timeline 时，数据可能已经不存在。
2. 当前 `/events` 和 `/stream` 接口在默认部署里更像“进程内临时观察窗口”，而不是审计记录。
3. 一旦后面把执行器拆成 worker，in-memory repos 会让 Gateway、Worker、Query 三者对执行历史产生不同视图。
4. 这会让“任务可回放、可审计、可诊断”这一条产品承诺在默认环境下不成立。

---

## 4. 根因分析

## 4.1 默认配置偏向 Demo，而不是偏向审计

当前默认配置更像“本地快速跑通任务流”的开发配置，而不是“默认保留执行证据”的配置。

这本身不是错，但缺少足够明确的模式说明，导致用户会自然认为：既然系统已经有 replay/artifact API，就应该默认能回看历史。

## 4.2 系统没有一个明确的“执行状态存储模式”概念

仓库里实际存在多套模式开关，但没有一个统一抽象告诉用户：

1. 哪个开关决定任务状态是否 durable。
2. 哪个开关只影响 event propagation。
3. 哪个开关只影响 long-term memory。

结果就是“有很多 mode”，但它们的职责边界不清晰。

## 4.3 回放相关接口已经暴露，但默认环境不保证数据寿命

这会产生认知落差：

1. 用户看到 `GET /v1/runs/{run_id}/events`，预期是历史回放接口。
2. 真实行为却取决于进程是否还活着、仓储是否切到 Postgres。

---

## 5. 解决方案建议

## 5.1 第一层：把“模式”从隐式组合改成显式说明

建议在文档和配置层明确区分四类能力：

1. `state_store_mode`：决定 task/run/subtask/artifact/replay 是否持久化。
2. `event_bus_mode`：决定事件分发是否跨实例。
3. `cache_lock_mode`：决定缓存与锁的实现。
4. `memory_store_mode`：决定 long-term memory 的向量存储。

即使底层仍然保留多段配置，也应该提供一个统一术语，避免用户把 replay、event bus、memory store 混为一谈。

## 5.2 第二层：提供一个默认可持久化的开发配置

建议新增一套明确命名的配置文件，例如：

1. `configs/dev-inmemory.yaml`
2. `configs/dev-persistent.yaml`
3. `configs/fullstack.yaml`

推荐含义：

1. `dev-inmemory`：本地快速调试，不保证历史回放。
2. `dev-persistent`：单机开发，但 task/run/subtask/artifact/replay 落 Postgres。
3. `fullstack`：Postgres + Redis + Qdrant 的完整基础设施模式。

这样用户在测试系统时，不会误把 demo 配置当成审计配置。

## 5.3 第三层：把 replay durable 作为默认验收能力

如果产品目标里要求“任务可回放”，建议把以下条件视为默认验收标准：

1. API 重启后仍能通过 `run_id` 查询到 `run detail`。
2. API 重启后仍能通过 `run_id` 获取 `replay entries`。
3. `artifacts` 与 `replay` 的数量在重启前后保持一致。

对应测试建议：

1. 保留现有 `test_v2_execution_flow.py` 作为进程内冒烟。
2. 参考 `test_infra_live_integration.py` 增加面向 API 的“重启后回查”测试。

## 5.4 第四层：启动时输出结构化基础设施摘要

建议服务启动时打印一段基础设施摘要，至少包含：

1. `repository_backend=in_memory|postgres`
2. `event_bus_backend=in_memory|redis`
3. `cache_backend=in_memory|redis`
4. `lock_backend=in_memory|redis`
5. `memory_backend=memory|qdrant|chroma`
6. `replay_durable=true|false`

这样用户在测试系统时，可以立刻知道当前环境是否具备回放能力。

## 5.5 第五层：后续为大体积 artifact/replay 引入分层存储

Postgres 可以解决当前的 durable replay 问题，但后续如果 artifact 体积变大，建议继续拆层：

1. PostgreSQL 保存结构化索引和轻量 metadata。
2. 对象存储保存大体积 stdout、报告、文件产物。
3. replay 中只引用 artifact locator，而不是长期把全部内容塞进热存储。

这不是当前阻塞项，但应作为下一阶段设计方向。

---

## 6. 推荐落地顺序

1. 先补文档，明确当前几种模式及其作用边界。
2. 新增 `dev-persistent` 配置，默认启用 PostgreSQL 仓储。
3. 启动日志增加基础设施摘要和 `replay_durable` 标记。
4. 增加“提交任务 -> 重启 API -> 回查 run/replay/artifact”集成测试。
5. 后续再评估 Redis/Qdrant 是否作为默认开发基础设施的一部分。

---

## 7. 结论

当前问题的本质不是“系统没有保存执行中间结果”，而是“系统默认保存到了进程内存里”。

因此这不是 replay 模型缺失，而是默认基础设施模式与产品预期不一致。短期最有效的修复，不是重写 replay 逻辑，而是：

1. 把模式说明清楚。
2. 提供默认可持久化的开发配置。
3. 让系统在启动时明确告诉用户当前是否具备 durable replay 能力。