# Task / Session / Run / Artifact / Replay 数据模型设计

> 这份文档定义 SwarmMind 平台里最核心的一组对象模型，用于承接前面几份设计文档：
>
> - `001` 记忆系统
> - `002` 多智能体任务执行系统
> - `003` Gateway 系统
> - `004` Tenant / User / Auth 系统

这份文档的目标是回答：系统里哪些对象是第一层公民，它们之间如何关联，以及后续代码应该围绕哪些模型来组织。

---

## 1. 结论先说

SwarmMind 后续不应只围绕一个 `Task` 模型扩展，而应该明确五个核心对象：

1. `Task`
2. `Session`
3. `Run`
4. `Artifact`
5. `Replay`

这五个对象分别解决不同问题：

- `Task` 解决“用户要完成什么”
- `Session` 解决“这次交互上下文是谁、在哪个会话里”
- `Run` 解决“这一次具体执行实例是什么”
- `Artifact` 解决“执行过程中产出了什么”
- `Replay` 解决“如何回放和审计整个执行过程”

如果这五层不拆开，后面所有信息都会堆进 `Task.result` 或 transcript 里，最终难以扩展。

---

## 2. 核心对象关系

推荐关系如下：

```text
Tenant
  -> User / ServicePrincipal
      -> Session
          -> Task
              -> Run (1..n)
                  -> Artifact (0..n)
                  -> Replay (1)
```

进一步展开：

- 一个 tenant 下有多个 user。
- 一个 user 可以有多个 session。
- 一个 session 里可以提交多个 task。
- 一个 task 可以被执行多次，因此有多个 run。
- 一个 run 会产出多个 artifact。
- 一个 run 应对应一个 replay 视图或 replay 根对象。

---

## 3. Task 模型

### 3.1 Task 的职责

Task 表示“用户目标的稳定业务对象”。

它不应该承载所有运行期细节，而是聚焦：

- 目标
- 约束
- 所有权
- 当前状态
- 最新结果摘要

### 3.2 Task 建议字段

- `task_id`
- `tenant_id`
- `session_id`
- `created_by`
- `goal`
- `constraints`
- `priority`
- `status`
- `current_run_id`
- `latest_result_summary`
- `latest_error_summary`
- `created_at`
- `updated_at`
- `started_at`
- `finished_at`
- `metadata`

### 3.3 Task 不应该直接塞入的内容

不建议把下面这些大对象直接塞进 task：

- 完整 transcript
- 所有工具调用日志
- 所有 patch 内容
- 所有测试报告

这些应该通过 `Artifact` 和 `Replay` 引用出去。

---

## 4. Session 模型

### 4.1 Session 的职责

Session 表示一次连续交互上下文。

它的重点不是任务执行本身，而是：

- 这是谁的上下文
- 这组交互是否连续
- 应该挂载哪些 memory scope

### 4.2 Session 建议字段

- `session_id`
- `tenant_id`
- `principal_id`
- `user_id`
- `status`
- `channel`
  - `cli`
  - `api`
  - `ui`
  - `webhook`
- `title`
- `context_summary`
- `active_task_ids`
- `memory_scope_refs`
- `transcript_root_ref`
- `created_at`
- `last_active_at`
- `closed_at`

### 4.3 Session 和 Memory 的关系

Session 应天然关联：

- working memory
- session memory
- transcript root

也就是说，session 是 memory 和 task 之间的桥梁对象之一。

---

## 5. Run 模型

### 5.1 为什么必须有 Run

Task 是稳定对象，但一次 task 可能多次执行。

例如：

1. 初次执行失败
2. 触发 repair run
3. 再次重试

如果没有 `Run`，你就没法区分：

- 第几次执行
- 哪次执行成功
- 哪次执行产出了哪些 artifact

### 5.2 Run 的职责

Run 表示 task 的一次具体执行实例。

它应该承载：

- 执行上下文
- 执行版本
- 运行状态
- replay 根引用

### 5.3 Run 建议字段

- `run_id`
- `task_id`
- `tenant_id`
- `session_id`
- `triggered_by`
- `run_type`
  - `initial`
  - `retry`
  - `repair`
  - `manual`
- `attempt`
- `status`
- `execution_plan_ref`
- `current_phase`
- `current_subtask_id`
- `replay_ref`
- `started_at`
- `finished_at`
- `error_summary`
- `cost_summary`
- `metadata`

---

## 6. Artifact 模型

### 6.1 Artifact 的职责

Artifact 表示执行过程中产出的具名结果对象。

它应该统一承载：

- 文件
- 报告
- patch
- 日志
- 截图
- JSON 结果

### 6.2 为什么 Artifact 必须独立建模

如果 artifact 不独立建模，最后会出现：

- patch 塞进 task result
- 测试报告塞进 transcript
- 文档内容塞进 run metadata

这样查询和审计都会变得很差。

### 6.3 Artifact 建议字段

- `artifact_id`
- `tenant_id`
- `task_id`
- `run_id`
- `subtask_id`
- `kind`
  - `patch`
  - `report`
  - `test_report`
  - `log`
  - `screenshot`
  - `json_output`
  - `document`
- `name`
- `mime_type`
- `storage_ref`
- `size_bytes`
- `checksum`
- `created_by_agent`
- `created_at`
- `metadata`

### 6.4 Artifact 存储建议

Artifact 元数据存数据库，内容存对象存储。

例如：

- Postgres 保存元数据
- MinIO / S3 保存内容

`storage_ref` 示例：

- `s3://swarmmind-artifacts/task_001/run_003/patch.diff`

---

## 7. Replay 模型

### 7.1 Replay 的职责

Replay 表示一条可回放的执行轨迹入口。

它不是简单的 transcript 文件名，而是：

- 一次 run 的回放根对象
- 指向 transcript、artifact、subtask timeline 的汇总视图

### 7.2 Replay 为什么必须独立存在

因为 transcript 是原始事件流，Replay 是“可消费的回放视图”。

两者区别：

- Transcript 偏原始日志
- Replay 偏产品和调试可视化入口

### 7.3 Replay 建议字段

- `replay_id`
- `tenant_id`
- `task_id`
- `run_id`
- `session_id`
- `transcript_ref`
- `timeline_ref`
- `artifact_index_ref`
- `summary_ref`
- `started_at`
- `finished_at`
- `status`
- `metadata`

---

## 8. Transcript 与 Replay 的关系

推荐这样理解：

```text
Transcript = 原始事件流
Replay = 基于原始事件流构建的回放视图
```

Transcript 适合：

- 审计
- 离线分析
- 原始事件追踪

Replay 适合：

- UI 回放
- 开发调试
- 任务执行解释

因此一个 run 最好同时有：

- 原始 transcript
- replay root object

---

## 9. 推荐对象主键与关联键

建议所有核心对象统一使用显式主键：

- `tenant_id`
- `user_id`
- `session_id`
- `task_id`
- `run_id`
- `artifact_id`
- `replay_id`

关键关联建议：

- `Task.session_id -> Session.session_id`
- `Run.task_id -> Task.task_id`
- `Artifact.run_id -> Run.run_id`
- `Replay.run_id -> Run.run_id`

这样后续查询链路会比较稳定。

---

## 10. 查询视角设计

后续 API 或 UI 应至少支持这几种视角：

### 10.1 Task 视角

看这个任务当前怎么样：

- 当前状态
- 最新 run
- 最新结果摘要

### 10.2 Session 视角

看这次会话里发生了什么：

- 关联任务
- transcript 根
- memory scope

### 10.3 Run 视角

看某次执行到底干了什么：

- 当前 phase
- subtask timeline
- artifacts
- replay

### 10.4 Artifact 视角

看某次执行产出了什么：

- patch
- test report
- report document
- logs

### 10.5 Replay 视角

看一条完整执行轨迹：

- 时间线
- Agent 调用
- tool 调用
- sandbox 结果
- artifacts 索引

---

## 11. 与前面几份设计的映射关系

### 对 `001 记忆系统`

- `Session` 提供 session memory 归属
- `Task` 提供 task shared memory 归属
- `Run` 提供一次执行的 capture/recall 范围

### 对 `002 多智能体执行系统`

- `Task` 是目标对象
- `Run` 是执行对象
- `Artifact` 是产物对象
- `Replay` 是回放对象

### 对 `003 Gateway`

- Gateway 负责创建 `Session / Task / Run`
- Gateway 负责查询 `Task / Run / Artifact / Replay`

### 对 `004 Tenant / User / Auth`

- 所有对象必须绑定 `tenant_id`
- `Session / Task / Run` 必须绑定提交主体

---

## 12. 推荐最小落地方案

如果后续代码实现要分阶段推进，建议先做到下面这套最小对象：

### MVP 对象

1. `Task`
2. `Session`
3. `Run`
4. `Artifact`

### Replay MVP

Replay 第一阶段可以先简化成：

- `replay_id`
- `run_id`
- `transcript_ref`
- `artifact_index_ref`

也就是先把 replay 作为回放入口对象，而不是一开始就构建复杂可视化模型。

---

## 13. 推荐建模原则

1. `Task` 保持稳定，少放大对象。
2. `Run` 承载运行期细节，不污染 `Task`。
3. `Artifact` 统一承载所有输出物。
4. `Replay` 作为回放入口，而不是把 transcript 直接暴露给上层。
5. 所有对象都要带 `tenant_id`，关键对象带 `session_id` 和 `run_id`。

---

## 14. 最终建议

SwarmMind 后续代码重构时，不应该继续以“一个 Task 模型 + 一个 Transcript 文件”支撑整个系统，而应该尽快切换到：

- `Task` 作为稳定业务对象
- `Session` 作为交互上下文对象
- `Run` 作为执行实例对象
- `Artifact` 作为输出物对象
- `Replay` 作为回放入口对象

一句话总结：

**Task 负责目标，Session 负责上下文，Run 负责执行，Artifact 负责产物，Replay 负责解释。**
