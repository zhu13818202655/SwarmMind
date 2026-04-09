# SwarmMind Reply 系统设计

这份文档解释当前仓库里“reply 系统”到底指什么、原来是什么样、这次修改后变成什么样，以及后续还需要补什么。

这里先统一术语。

- `reply`：指 AgentScope / OmniAgent 侧一次 `reply()` 调用及其内部的 reasoning、acting、tool call 生命周期。
- `replay`：指平台侧围绕 `task/run/subtask/tool/agent/sandbox` 形成的事件时间线，用于审计、排障、回放、查询。
- 在 SwarmMind 代码里，用户感知到的“reply 中间结果有没有固化”本质上不是单独一个 reply 对象，而是：`reply` 期间产生的事件和证据，是否被沉淀进 `replay` 与 `artifact`。

所以这套设计的真实问题，不是“有没有 reply 函数”，而是“reply 产生的中间态，是否可以按 run/subtask/tool 维度持久化和查询”。

## 1. 原来

## 1.1 总体结构

原来的链路已经具备基础闭环。

1. Gateway 提交任务时会创建 `task`、`run` 和 `replay root`。
2. Orchestrator / ExecutionRunner 在子任务执行过程中不断发布 `DomainEvent`。
3. `ReplayRecorder` 订阅事件总线，把带 `run_id` 的事件追加到 replay。
4. `ArtifactRepository` 负责保存产物，`QueryService` 和 API 负责查询。

也就是说，仓库原本并不是“完全没有 replay”，而是“有 replay 骨架，但默认行为和查询粒度不够支撑本地调试排障”。

## 1.2 原来的 reply 观测点

原来的 agent 侧 reply 生命周期已经有比较完整的事件发射。

1. `OmniAgent.reply()` 会发 `agent.started`、`agent.completed`、`agent.failed`。
2. `OmniAgent._acting()` 会发 `tool.started`、`tool.completed`、`tool.failed`。
3. `OmniAgentRunner.run()` 会发 `agent.step.started`、`agent.step.completed`、`agent.step.failed`。
4. `ExecutionRunner` 自己也会发 `execution.started`、`execution.completed`、`execution.failed`，以及 `subtask.started`、`subtask.completed`、`subtask.failed`、`subtask.terminal`、`subtask.summary`。
5. sandbox 路径还会发 `sandbox.command_started`、`sandbox.command_completed`。

这说明原来已经存在“reply 级可观测事件”，并且这些事件会带上 `task_id`、`run_id`、`subtask_id`，理论上可以进入 replay。

## 1.3 原来的持久化行为

原来的持久化行为分成两个层面。

### A. replay 层

1. `Gateway.submit_task()` 创建 `ReplayRoot`。
2. `ReplayRecorder.handle_event()` 会把 `DomainEvent` 追加为 `ReplayEntry`。
3. replay entry 的 payload 会补齐 `event_id`、`tenant_id`、`session_id`、`task_id`、`run_id`、`subtask_id`、`sandbox_id`。

### B. artifact 层

1. sandbox 执行后会生成 execution summary、stdout、stderr 等 artifact。
2. inline agent 执行会生成 markdown/report/json 类 artifact。
3. skill script 会把声明的 artifact 持久化。

所以原来不是“完全不固化”，而是“固化了一部分，而且偏结果导向，缺少排障导向的细节沉淀”。

## 1.4 原来真正存在的问题

原来的主要问题有四个。

### 问题 1：默认后端是内存

配置默认是：

- `repositories.replay_backend = memory`
- `repositories.artifact_backend = memory`

这意味着在默认本地调试方式下，即使 reply 过程产生了 replay 和 artifact，只要服务重启、调试会话结束、容器重建，这些中间结果就会丢失。

这正是“启用 Server + Sandbox 做测试时中间结果没有固化下来”的核心原因。

### 问题 2：reply 事件有了，但查询维度偏粗

原来的 API 只支持：

1. 查询 run 全量 events。
2. 查询 subtask 全量 events。
3. 查询 subtask artifacts。

但是它不支持直接按以下维度过滤：

1. 只看 `tool.failed`。
2. 只看某个具体 `tool_name`。
3. 在一个 subtask 内直接锁定某类 reply 失败事件。

所以排障时虽然“有数据”，但仍然要靠人工翻整条事件流。

### 问题 3：tool 失败只有事件，没有单独诊断 artifact

原来的 `tool.failed` 只会写入 replay event，不会额外固化为 artifact。

这会带来两个后果。

1. 故障信息只有事件 payload，缺少稳定的故障快照对象。
2. 后续如果想做“失败诊断面板”或导出单个失败报告，基础对象不够完整。

### 问题 4：sandbox stdout/stderr 原来只保留 preview

原来的 stdout/stderr artifact 只保留：

1. `content_length`
2. `preview`

没有保留完整内容。

这导致一个典型问题：任务失败时能看到大概发生了什么，但拿不到完整 stderr/stdout 做复盘。

## 1.5 原来设计的定位

从设计定位上看，原来的系统更像是“已经有审计基础设施，但还没有把本地调试体验打磨完”。

它已经具备：

1. 事件化。
2. run 级 replay。
3. subtask 级 artifact。
4. SSE / API 查询。

但还不具备：

1. 默认耐久化。
2. 故障优先查询接口。
3. 失败诊断对象。
4. 更完整的 stdout/stderr 固化。

## 2. 修改后

这次修改的目标不是推翻原设计，而是在保留现有 DomainEvent + ReplayRecorder + ArtifactRepository 架构的前提下，把它从“基础可用”推进到“本地调试可用”。

## 2.1 修改后的核心原则

修改后的 reply / replay 设计遵循三个原则。

1. 不新增一套并行的 reply 持久化模型，而是继续沿用现有 replay / artifact 体系。
2. reply 期间产生的关键中间结果，优先通过事件和 artifact 两条线同时沉淀。
3. 本地调试场景下默认开启文件持久化，优先保证可回查，而不是只追求内存态轻量执行。

## 2.2 修改点一：调试启动默认落盘

针对 `Server + Sandbox` 复合调试配置，新增了以下环境变量。

1. `SWARMMIND_REPOSITORIES__REPLAY_BACKEND=file`
2. `SWARMMIND_REPOSITORIES__ARTIFACT_BACKEND=file`
3. `SWARMMIND_REPOSITORIES__FILE_BASE_PATH=${workspaceFolder}/data`

这样本地启动时，reply 过程中的 replay 和 artifact 会直接落在工作区的 `data/` 下。

落盘后的目录语义是：

1. `data/replays/`：run 级 replay 文件。
2. `data/artifacts/`：run 级 artifact 文件。

这一步解决的是“调试过程结束后数据全没了”的问题。

## 2.3 修改点二：run/subtask events 支持按 topic 和 tool_name 过滤

API 层新增了 replay 过滤能力。

### 支持的过滤维度

1. `topic`
2. `tool_name`

### 作用到的接口

1. `GET /v1/runs/{run_id}/events`
2. `GET /v1/runs/{run_id}/subtasks/{subtask_id}/events`

### 示例

1. 只看 run 下所有失败工具：`/v1/runs/{run_id}/events?topic=tool.failed`
2. 只看某个 subtask 的 `sandbox_exec` 失败：`/v1/runs/{run_id}/subtasks/{subtask_id}/events?topic=tool.failed&tool_name=sandbox_exec`

这一步解决的是“有 replay 但不好查”的问题。

## 2.4 修改点三：tool 失败单独固化为 artifact

现在工具执行失败时，不仅会发 `tool.failed` 事件，还会额外创建一份 inline artifact。

artifact 的内容会包含：

1. `source = tool_failure`
2. `tool_name`
3. `sandbox_id`
4. `error`
5. `input`

这样做的意义不是重复事件，而是把“失败上下文”升级为一个稳定对象。

后续无论做以下哪种能力，都可以直接建立在 artifact 上。

1. 失败报告导出。
2. 故障诊断聚合。
3. UI 里单独展示失败工具证据。
4. 自动修复代理读取失败上下文。

## 2.5 修改点四：stdout/stderr 保存完整内容

现在 sandbox stdout/stderr artifact 除了 preview，还会保留完整 `content`。

修改后的 artifact 元数据会包含：

1. `content_length`
2. `preview`
3. `content`

这一步解决的是“知道失败了，但拿不到完整命令输出”的问题。

## 2.6 修改后的系统视图

修改后，这套系统可以概括成下面这条链路。

1. Agent 执行一次 `reply()`。
2. reply 内部的 step、tool、sandbox、subtask 都发 `DomainEvent`。
3. `ReplayRecorder` 把这些事件追加入 run replay。
4. 关键结果和失败快照写成 artifact。
5. 本地调试模式下 replay/artifact 默认落盘。
6. API 支持按 run、subtask、topic、tool_name 查询。

所以现在的 reply 设计已经从“过程事件化”提升成了“过程事件化 + 关键证据对象化 + 本地默认持久化”。

## 2.7 修改后的优点

### 优点 1：不破坏现有模型

没有新增一个复杂的 ReplyRepository，也没有引入第二套追踪模型。现有模型还是：`DomainEvent -> ReplayEntry`，`execution output -> Artifact`。

### 优点 2：调试体验明显改善

本地用 `Server + Sandbox` 启动后，中间结果会自动留在 `data/` 下，不需要额外手动改配置。

### 优点 3：故障定位路径更短

现在排障可以直接按下面路径定位：

1. 先拿 `run_id`。
2. 查 `tool.failed` 事件。
3. 根据 `subtask_id` 查该 subtask 的失败事件与 artifact。
4. 直接读取 stdout/stderr 或 tool failure artifact。

### 优点 4：为后续诊断聚合打基础

有了 topic/tool_name 过滤和 tool failure artifact，下一步做“run diagnostics”就不需要重构底层数据结构。

## 2.8 修改后的局限

虽然这次修改已经解决了本地调试最痛的点，但它仍然是一个阶段性方案。

当前仍有这些局限。

1. replay 还是 append-only 事件流，不是结构化诊断视图。
2. stdout/stderr 直接放在 artifact metadata 中，适合 MVP，不适合超大输出。
3. tool completed 事件只保留摘要，不保留完整 result 快照。
4. reply 级别还没有独立的 `reply_id` 概念。
5. API 仍偏底层，使用者需要知道 run/subtask/tool 的关系。

## 3. TODO

下面的 todo 按优先级分层，不是所有都要立刻做，但如果要把这套 reply 系统做成真正可运维、可产品化的能力，这些点迟早要补。

## 3.1 P0：排障效率继续提升

### TODO 1：增加 run diagnostics 聚合接口

建议新增一个聚合诊断接口，而不是让调用方手动拼多个 API。

建议返回：

1. run 基本状态。
2. 失败的 subtasks。
3. 失败的 tools。
4. 最新 stderr / stdout 摘要。
5. 关键 artifact 引用。

目标是让“为什么失败”可以一跳看到，而不是先读 replay 再读 artifact。

### TODO 2：任务失败时自动输出诊断索引

建议在任务失败时，把以下信息直接写进 task/run 的 result 或 summary。

1. `run_id`
2. `failed_subtask_ids`
3. `failed_tool_names`
4. 关键 artifact id 列表

这样脚本层和前端层都不用再自己扫 replay 才知道从哪里看。

## 3.2 P1：reply 级对象模型补全

### TODO 3：引入显式 `reply_id`

现在 reply 生命周期的事件大多挂在 `run_id/subtask_id` 上，这对任务排障已经够用，但还不够精确。

建议后续引入 `reply_id`，表示一次具体的 agent reply 调用。

好处是：

1. 一个 subtask 里多次 agent reply 可以区分。
2. 可以把 `agent.started -> tool.* -> agent.completed` 聚成一条 reply 轨迹。
3. 更容易做 reply 级重试分析、耗时分析、成本分析。

### TODO 4：把 agent step 和 agent reply 明确分层

当前系统里同时有：

1. `agent.started/completed/failed`
2. `agent.step.started/completed/failed`

这两层语义是合理的，但还不够清楚。

建议后续明确约定：

1. `agent.step.*`：平台视角的一次执行步骤。
2. `agent.*`：模型/agent 内部一次真实 reply 生命周期。

否则后面做查询和产品呈现时容易混淆。

## 3.3 P1：存储模型升级

### TODO 5：大输出迁移到对象存储

当前 stdout/stderr/content 直接写 artifact metadata 是最省事的做法，但不适合长期扩展。

建议后续变成：

1. 小内容继续 inline。
2. 大内容写对象存储或文件实体。
3. artifact metadata 只保留 `storage_ref`、摘要、长度、哈希。

这样能避免 replay/artifact JSON 文件无限膨胀。

### TODO 6：为 replay 增加索引视图

当前 replay 是纯 append-only entry list，查询过滤靠 API 现算。

后续如果 run 很长、事件很多，建议增加索引能力，例如：

1. 按 topic 建索引。
2. 按 subtask_id 建索引。
3. 按 tool_name 建索引。
4. 按失败级别建索引。

这可以显著降低诊断接口的读取和过滤成本。

## 3.4 P2：面向产品和运维的能力

### TODO 7：增加诊断摘要 artifact

除了原始事件和原始 stdout/stderr，建议在 run terminal 时生成一份 summary artifact。

内容可以包括：

1. 执行阶段概览。
2. 失败节点。
3. 关键证据链接。
4. 推荐下一步排查动作。

这样人看和机器看都会更高效。

### TODO 8：增加事件保留策略和清理策略

本地落盘之后，数据不会自动消失，这对调试是好事，但时间长了会积累很多历史 run。

后续应该补：

1. TTL。
2. 定期清理任务。
3. 历史 run 归档。
4. 开发环境与生产环境的不同保留策略。

### TODO 9：增加统一的“执行证据”抽象

长期看，reply 过程中的证据不止 replay event 和 artifact 两种，还可能包括：

1. prompt snapshot。
2. tool input/output snapshot。
3. sandbox 文件差异。
4. handoff 链路。

后续可以考虑做统一的 `ExecutionEvidence` 抽象，把 replay 和 artifact 作为不同证据类型收敛到同一个查询模型下。

## 3.5 建议的后续演进顺序

建议按下面顺序推进，而不是一次把模型做重。

1. 先补 `run diagnostics` 聚合接口。
2. 再补失败摘要写回 run/task result。
3. 再引入 `reply_id`。
4. 再做大文件存储与 replay 索引。
5. 最后再考虑统一 `ExecutionEvidence` 抽象。

这样可以确保每一步都直接改善调试与运维体验，而不是先做一套很重但短期用不上的模型。

## 4. 结论

当前仓库里的 reply 系统，本质上已经不是“有没有观测”的问题，而是“reply 观测结果是否默认持久化、是否足够容易排障”的问题。

原来的系统已经具备事件化和 replay 基础。

这次修改后，系统完成了三个关键升级。

1. 本地调试默认落盘。
2. replay 支持按 `topic/tool_name` 过滤。
3. tool 失败和完整 stdout/stderr 被进一步固化。

所以现在这套设计已经能支撑“任务失败后快速追到具体 task、subtask、tool、sandbox 输出”。

但如果目标是更高效的调试体验和更成熟的运维能力，下一阶段最值得做的不是继续堆事件，而是补聚合诊断视图和 reply 级显式标识。