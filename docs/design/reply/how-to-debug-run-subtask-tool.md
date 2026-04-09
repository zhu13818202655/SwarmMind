# Reply 故障排查接口说明

这份文档只回答一个问题：当一个任务执行失败，或者你怀疑某个中间步骤有问题时，应该如何通过现有接口去定位 `run`、`subtask`、`tool` 三级故障。

这不是底层实现文档，而是一份偏接口视角的排障手册。

## 1. 先建立排障视角

当前 SwarmMind 的排障入口不是单一的 `reply` 对象，而是三层对象。

1. `run`：一次任务执行实例，是总排障入口。
2. `subtask`：run 内的执行单元，用来定位具体失败阶段。
3. `tool`：subtask 内的工具调用，用来定位具体执行动作和失败点。

所以实际排障顺序通常不是“直接查 reply”，而是：

1. 先拿到 `run_id`。
2. 看 run 整体状态和全量事件。
3. 缩小到失败 subtask。
4. 再缩小到失败 tool。
5. 最后结合 artifact 看 stdout、stderr、失败快照。

## 2. 你现在能查到什么

当前系统对外暴露的排障相关能力主要有五类。

## 2.1 run 聚合详情

接口：`GET /v1/runs/{run_id}`

用途：

1. 看 run 当前状态。
2. 看 run 下有哪些 subtasks。
3. 看 run 下有哪些 artifacts。

这是最适合做“先看全貌”的接口。

### 返回重点

1. `run.status`
2. `run.phase`
3. `subtasks[]`
4. `artifacts[]`

### 适用场景

1. 用户反馈任务失败，但你还不知道卡在哪一层。
2. 想快速知道是否已经有产物或失败证据落盘。

## 2.2 run 状态摘要

接口：`GET /v1/runs/{run_id}/status`

用途：

1. 快速查看 run 是否结束。
2. 快速查看 subtask 数量和 artifact 数量。

这个接口信息量较少，但适合轮询或脚本判断。

### 返回重点

1. `status`
2. `phase`
3. `subtask_count`
4. `artifact_count`
5. `error`

### 适用场景

1. 只想先确认 run 是不是已经失败。
2. 想在 UI 或脚本里做轻量状态检测。

## 2.3 run 事件流

接口：`GET /v1/runs/{run_id}/events`

用途：

1. 查看 run 维度下所有 replay 事件。
2. 按时间顺序还原执行过程。
3. 初步判断失败是发生在 planning、execution、validation 还是 tool 调用阶段。

### 支持参数

1. `cursor`：分页起点。
2. `limit`：单页条数。
3. `topic`：按事件类型过滤。
4. `tool_name`：按工具名过滤。

### 常见 `topic`

1. `execution.started`
2. `execution.failed`
3. `subtask.started`
4. `subtask.failed`
5. `subtask.terminal`
6. `tool.started`
7. `tool.completed`
8. `tool.failed`
9. `sandbox.command_started`
10. `sandbox.command_completed`
11. `agent.step.started`
12. `agent.step.failed`
13. `run.terminal`
14. `run.summary`

### 示例

查看一个 run 下所有失败工具：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/events?topic=tool.failed"
```

查看一个 run 下所有 `sandbox_exec` 相关事件：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/events?tool_name=sandbox_exec"
```

### 适用场景

1. 你知道 run 出问题了，但还不知道是哪一个 subtask。
2. 你怀疑多个 subtask 都执行过同一个 tool，想先从 tool 维度筛一遍。

## 2.4 subtask 事件流

接口：`GET /v1/runs/{run_id}/subtasks/{subtask_id}/events`

用途：

1. 只查看某一个 subtask 的 replay。
2. 看该 subtask 内的 agent、tool、sandbox、summary 事件。
3. 判断这个 subtask 是在哪个具体动作失败的。

### 支持参数

1. `cursor`
2. `limit`
3. `topic`
4. `tool_name`

### 示例

查看某个 subtask 下所有工具失败：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/subtasks/<subtask_id>/events?topic=tool.failed"
```

查看某个 subtask 下 `sandbox_exec` 的失败：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/subtasks/<subtask_id>/events?topic=tool.failed&tool_name=sandbox_exec"
```

查看某个 subtask 下所有 agent step 失败：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/subtasks/<subtask_id>/events?topic=agent.step.failed"
```

### 适用场景

1. 你已经知道是哪个 subtask 出问题。
2. 想把排障范围从整个 run 缩小到单个执行单元。
3. 想区分是 agent 输出失败、tool 失败，还是 sandbox 命令失败。

## 2.5 subtask artifacts

接口：`GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

用途：

1. 查看某个 subtask 产出的证据对象。
2. 读取 stdout、stderr、execution summary、tool failure 快照、verification report 等内容。
3. 将事件流里的“发生了什么”转成“具体证据是什么”。

### 常见 artifact 类型

1. `log`
2. `report`
3. `test_result`
4. `file`

### 当前常见 artifact 名称模式

1. `<subtask_name>-execution-summary.json`
2. `<subtask_name>-stdout.log`
3. `<subtask_name>-stderr.log`
4. `<subtask_name>-<tool_name>-tool-failure.json`
5. `<subtask_name>-verification.json`
6. `<subtask_name>-review.json`
7. `<subtask_name>-<runtime_kind>.md`

### 适用场景

1. 你已经知道哪一个 subtask 或 tool 有问题。
2. 现在需要拿到 stdout、stderr、错误上下文、诊断快照做细查。

## 3. 推荐排障路径

下面给出三条建议路径，分别对应不同排障起点。

## 3.1 从 run 开始查

这是最常见的排障路径。

### 第一步：拿 run 全貌

调用：`GET /v1/runs/{run_id}`

先看：

1. `run.status`
2. `run.phase`
3. 哪些 `subtasks` 状态异常
4. 是否已经有 artifacts

如果这里已经能看到某个 subtask 的 `status = failed`，就直接记下这个 `subtask_id`。

### 第二步：看 run 失败事件

调用：`GET /v1/runs/{run_id}/events?topic=subtask.failed`

目标：

1. 找到失败 subtask。
2. 看失败 payload 里的错误摘要。

如果你怀疑是工具调用问题，再继续查：

`GET /v1/runs/{run_id}/events?topic=tool.failed`

### 第三步：缩小到 subtask

调用：`GET /v1/runs/{run_id}/subtasks/{subtask_id}/events`

目标：

1. 看这个 subtask 的完整过程。
2. 确认失败是 agent、tool 还是 sandbox 命令导致。

### 第四步：拿证据

调用：`GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

重点查看：

1. `stderr.log`
2. `stdout.log`
3. `tool-failure.json`
4. `execution-summary.json`

这条路径适合绝大多数“任务失败了，我要定位问题”的情况。

## 3.2 从 subtask 开始查

这种路径适用于你已经通过 UI、日志或数据库知道某个 `subtask_id` 有问题。

### 第一步：看 subtask replay

调用：`GET /v1/runs/{run_id}/subtasks/{subtask_id}/events`

建议优先看以下 topic。

1. `subtask.started`
2. `tool.started`
3. `tool.failed`
4. `subtask.failed`
5. `subtask.summary`

### 第二步：如果怀疑是工具问题，继续过滤

示例：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/subtasks/<subtask_id>/events?topic=tool.failed"
```

如果已知可疑 tool，再加 `tool_name`。

### 第三步：取 artifact 对照

调用：`GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

比对事件和 artifact，确认：

1. tool 失败的输入参数是什么。
2. 命令 stderr 是什么。
3. 是否有 execution summary 记录 exit code。

## 3.3 从 tool 开始查

这种路径适用于你怀疑某个基础 tool 本身不稳定，例如：

1. `sandbox_exec`
2. `artifact_read`
3. `run_skill_script`
4. 某个浏览器或搜索类工具

### 第一步：按 tool_name 扫 run 级 replay

调用：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/events?tool_name=<tool_name>"
```

如果只关心失败，再加：

```bash
curl "http://127.0.0.1:8000/v1/runs/<run_id>/events?topic=tool.failed&tool_name=<tool_name>"
```

### 第二步：找到对应 subtask_id

从事件 payload 里拿：

1. `subtask_id`
2. `sandbox_id`
3. `error`

### 第三步：深入 subtask 证据

对命中的 subtask，调用：

1. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?tool_name=<tool_name>`
2. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

这条路径适合做“某个公共工具最近是不是全线不稳定”的排查。

## 4. 不同故障类型怎么查

下面按故障类型给出建议查法。

## 4.1 run 整体失败

症状：

1. 任务失败。
2. run 最终状态是 `failed`。

建议顺序：

1. `GET /v1/runs/{run_id}/status`
2. `GET /v1/runs/{run_id}`
3. `GET /v1/runs/{run_id}/events?topic=subtask.failed`
4. `GET /v1/runs/{run_id}/events?topic=run.summary`

关注点：

1. 第一个失败的 subtask 是谁。
2. run.summary 有没有聚合错误信息。
3. artifact 数量是否为 0。

## 4.2 subtask 执行失败

症状：

1. 某个 subtask 没有完成。
2. subtask 状态是 `failed`。

建议顺序：

1. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events`
2. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=tool.failed`
3. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

关注点：

1. subtask 失败前最后一个事件是什么。
2. 有没有 `tool.failed`。
3. 有没有 stderr artifact。

## 4.3 tool 失败

症状：

1. replay 里出现 `tool.failed`。
2. subtask 没有预期结果。

建议顺序：

1. `GET /v1/runs/{run_id}/events?topic=tool.failed&tool_name=<tool_name>`
2. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=tool.failed&tool_name=<tool_name>`
3. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

关注点：

1. `error`
2. `input`
3. `sandbox_id`
4. 对应 stdout/stderr

## 4.4 sandbox 命令失败

症状：

1. `sandbox.command_completed` 的 `exit_code != 0`
2. 或 subtask 直接失败

建议顺序：

1. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=sandbox.command_completed`
2. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

关注点：

1. `command`
2. `exit_code`
3. `stdout.log`
4. `stderr.log`
5. `execution-summary.json`

## 4.5 agent step 失败

症状：

1. `agent.step.failed`
2. 可能没有进入 tool 调用阶段就失败

建议顺序：

1. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=agent.step.failed`
2. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=agent.failed`
3. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`

关注点：

1. 是 step 失败还是整个 agent reply 失败。
2. 有没有产出 markdown/report artifact。
3. 是否存在上游依赖证据缺失。

## 5. 一个完整排障示例

假设你已经知道某个任务失败，并拿到了 `run_id = run-123`。

### 第一步：确认 run 状态

```bash
curl "http://127.0.0.1:8000/v1/runs/run-123/status"
```

如果状态是 `failed`，继续下一步。

### 第二步：列出 run 详情

```bash
curl "http://127.0.0.1:8000/v1/runs/run-123"
```

目标是找到失败的 `subtask_id`。

### 第三步：只看失败工具

```bash
curl "http://127.0.0.1:8000/v1/runs/run-123/events?topic=tool.failed"
```

如果输出里出现：

1. `tool_name = sandbox_exec`
2. `subtask_id = subtask-456`

那就说明重点要看 `subtask-456`。

### 第四步：缩到这个 subtask

```bash
curl "http://127.0.0.1:8000/v1/runs/run-123/subtasks/subtask-456/events?topic=tool.failed&tool_name=sandbox_exec"
```

确认报错信息后，再查 artifact。

### 第五步：取证据

```bash
curl "http://127.0.0.1:8000/v1/runs/run-123/subtasks/subtask-456/artifacts"
```

然后重点找：

1. `subtask-456-stderr.log`
2. `subtask-456-stdout.log`
3. `subtask-456-sandbox_exec-tool-failure.json`
4. `subtask-456-execution-summary.json`

到这一步，通常已经能定位到是命令错误、环境错误、输入错误，还是 sandbox 本身的问题。

## 6. 当前接口设计的优点和边界

## 6.1 优点

1. run、subtask、tool 三层排障路径已经打通。
2. replay 和 artifact 可以互相印证。
3. 支持从“全局看 run”逐步缩到“单个 tool 调用”。
4. 本地调试模式下数据已经默认落盘，便于复查。

## 6.2 边界

当前接口仍然偏底层，调用方需要自己理解对象关系。

具体来说还有这些边界。

1. 没有单独的 `run diagnostics` 聚合接口。
2. 没有“直接返回失败链路摘要”的接口。
3. 没有按严重级别、阶段、角色等更高层维度过滤。
4. 还没有显式 `reply_id`，所以一次 subtask 内多次 reply 不容易完全分开看。

## 7. 当前最推荐的排障用法

如果你只是想快速定位问题，不想自己设计查询流程，建议固定使用下面这套顺序。

1. 先查 `GET /v1/runs/{run_id}`。
2. 再查 `GET /v1/runs/{run_id}/events?topic=tool.failed`。
3. 找到 `subtask_id` 后，查 `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=tool.failed`。
4. 最后查 `GET /v1/runs/{run_id}/subtasks/{subtask_id}/artifacts`。

这条路径兼顾了效率和完整性，是当前仓库里最适合本地调试和线上排障的默认流程。

## 8. 后续建议

如果后面继续增强接口层，我建议优先做两件事。

1. 增加 `GET /v1/runs/{run_id}/diagnostics`，直接聚合 failed subtasks、failed tools、关键 artifacts。
2. 在任务失败响应里直接返回关键诊断索引，例如 `run_id`、`failed_subtask_ids`、`failed_tool_names`。

这样调用方就不需要每次都从底层 replay 自己拼故障视图。