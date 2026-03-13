# Sandbox 系统设计与使用方案

> 这份文档专门回答一个问题：
>
> 在 SwarmMind 里，sandbox 到底应该怎么用，什么时候创建，给谁用，怎么回收，怎么和 Agent / Tool / Memory / Artifact / Replay 协同。

这份设计承接：

- `002` 多智能体任务执行系统
- `005` Task / Session / Run / Artifact / Replay 数据模型
- `006` Repository / Storage / Event Bus 架构
- `009` 实施路线图

---

## 1. 先说结论

SwarmMind 里的 sandbox 不是“给 Agent 一个能跑命令的地方”这么简单。

更准确地说，sandbox 是平台的 **受控执行面（controlled execution plane）**，负责承接一切需要隔离、副作用、资源限制、超时治理和结果留痕的动作。

一句话定义：

**凡是可能修改文件、执行代码、安装依赖、访问受限网络、产生运行产物、或需要审计回放的动作，原则上都应进入 sandbox。**

因此，sandbox 在系统里的职责不是附属能力，而是平台主干之一。

---

## 2. 为什么必须把 sandbox 单独设计

如果不单独设计，系统很容易退化成下面这种模式：

1. Agent 直接在宿主机执行命令
2. Tool 直接读写本地工程目录
3. 测试输出直接混入 task result
4. 不同任务之间共享环境状态
5. 出错后无法复现“当时到底执行了什么”

这会直接带来几个严重问题：

1. 安全边界失控
2. 多任务执行互相污染
3. 无法限制 CPU / 内存 / 网络 / 时长
4. 结果不可审计、不可回放
5. 工具实现和执行环境强耦合

所以 SwarmMind 的原则应该明确：

**Agent 负责决策，Tool 负责动作抽象，Sandbox 负责副作用落地。**

---

## 3. Sandbox 在平台里的位置

```text
User Request
   -> Gateway
   -> Orchestrator
   -> Planner / Coordinator
   -> ExecutionProfile
   -> Agent Role + Skill + Tool Group
   -> Tool Runtime
   -> Sandbox Manager
   -> OpenSandbox
   -> Docker / Kubernetes Runtime
   -> Artifact / Transcript / Replay / Memory
```

重点是：

- Agent 不直接操作 Docker / K8s
- Tool 不直接创建容器
- 上层统一通过 `SandboxManager + SandboxProvider` 使用 sandbox

也就是：

**所有沙箱能力都必须走平台抽象层，不能散落在各个 tool 或 agent 实现里。**

---

## 4. Sandbox 的核心职责

建议明确为六类职责。

### 4.1 隔离执行

为每个 subtask 或一组相关 subtasks 提供独立执行环境，避免：

- 依赖污染
- 文件覆盖
- 端口冲突
- 进程残留

### 4.2 资源治理

负责执行期资源约束：

- CPU
- 内存
- GPU
- 最大运行时长
- 最大文件体积
- 并发数

### 4.3 网络治理

按 profile 控制：

- 禁网
- 白名单出网
- 浏览器访问
- HTTP API 访问

### 4.4 文件与命令执行承载

承接典型运行期动作：

- 写入工作文件
- 执行 shell / python / node 命令
- 读取中间文件
- 拉取测试报告
- 生成最终产物

### 4.5 审计与回放证据采集

每一次 sandbox 执行都应沉淀：

- 命令
- 参数
- stdout / stderr
- 退出码
- 输入文件摘要
- 输出文件索引
- 运行时元数据

### 4.6 生命周期管理

平台必须知道：

- 什么时候创建
- 谁在使用
- 是否需要续期
- 何时销毁
- 异常时如何兜底清理

---

## 5. 什么时候必须使用 sandbox

不是所有动作都要进 sandbox，但以下情况建议强制进入。

### 5.1 必须进 sandbox 的动作

1. 执行代码
2. 跑测试
3. 安装依赖
4. 修改工作区文件
5. 调用浏览器自动化
6. 处理不可信外部输入
7. 生成需要交付的产物文件
8. 任何需要审计回放的副作用操作

### 5.2 可以不进 sandbox 的动作

1. 纯 LLM 推理
2. 结构化任务拆解
3. 元数据查询
4. 向量检索
5. 只读配置查询
6. 小体量的纯字符串格式化

### 5.3 推荐判断规则

如果一个动作满足下面任意一条，就优先走 sandbox：

- 会产生副作用
- 会访问文件系统
- 会依赖系统环境
- 会消耗明显计算资源
- 需要输出证据链

---

## 6. 推荐使用模式

SwarmMind 不应只支持一种沙箱使用方式，而应至少支持三种模式。

### 6.1 Subtask Sandbox

最推荐的默认模式。

特点：

- 一个 subtask 对应一个 sandbox
- 生命周期清晰
- 最容易审计
- 最适合 MVP

适用场景：

- 编码
- 测试
- 报告生成
- 网页抓取

优点：

- 隔离最强
- 失败影响面最小
- 方便并发调度

代价：

- 创建成本较高
- 跨 subtask 共享状态不自然

### 6.2 Run Sandbox

一个 run 或一个 phase 共享同一个 sandbox。

特点：

- 多个相关 subtasks 共用环境
- 适合需要持续上下文的执行链

适用场景：

- 一个功能实现后立刻测试
- 需要多步文件迭代的构建任务

优点：

- 减少重复初始化
- 更利于共享中间文件

风险：

- 子任务之间相互污染
- 审计颗粒度下降

### 6.3 Session Sandbox

不建议作为默认模式，只适合少数高交互长会话任务。

适用场景：

- 长时间交互式分析
- 用户持续追加要求的实验环境

主要风险：

- 成本高
- 泄漏风险高
- 治理复杂

### 6.4 平台默认建议

MVP 阶段建议默认采用：

**`Subtask Sandbox` 为主，`Run Sandbox` 为辅，禁用 `Session Sandbox` 作为默认能力。**

---

## 7. Sandbox 与 Agent / Skill / Tool 的关系

### 7.1 正确关系

```text
SubTask
  -> Coordinator selects ExecutionProfile
  -> ExecutionProfile binds ToolGroups + SandboxProfile
  -> Agent executes Skill
  -> Skill invokes Tools
  -> Sandbox-aware Tool delegates to SandboxManager
```

也就是说：

- SubTask 决定执行目标
- Coordinator 决定是否需要 sandbox，以及用哪个 profile
- Agent 不关心底层容器实现
- Tool 只描述“要执行什么动作”
- SandboxManager 负责“把动作放到受控环境里执行”

### 7.2 Tool 要分为两类

建议明确区分：

1. **sandbox-aware tools**
   只能通过 sandbox 执行副作用动作。

2. **control-plane tools**
   用于查询元数据、检索记忆、查任务状态，不进入 sandbox。

### 7.3 典型映射

| Tool | 是否走 Sandbox | 说明 |
| --- | --- | --- |
| `run_command` | 是 | 命令执行必须隔离 |
| `write_file` | 是 | 文件落盘必须可审计 |
| `read_runtime_file` | 是 | 读取运行期文件 |
| `run_tests` | 是 | 测试是典型副作用动作 |
| `browser_automation` | 是 | 浏览器依赖环境和网络策略 |
| `search_memory` | 否 | 查询控制面数据 |
| `get_task_context` | 否 | 查询任务元数据 |
| `publish_artifact` | 否 | 这是平台存储动作，不是沙箱执行 |

---

## 8. Sandbox Profile 设计

profile 是治理核心，不应让 Agent 自由拼接环境。

建议每个 sandbox 都必须绑定 profile，由平台配置统一声明：

- 基础镜像
- 资源限制
- 网络策略
- 可见工具能力
- 最大超时
- 是否允许浏览器
- 是否允许安装依赖
- 是否允许上传工件

### 8.1 建议的 profile 清单

#### `secure-offline`

用途：

- 安全优先任务
- 禁止外网的代码/文本处理

策略：

- 无外网
- 只允许基础命令
- 较短 TTL

#### `py-basic`

用途：

- Python 代码生成与测试

策略：

- Python 运行时
- 允许 pytest / lint
- 默认禁外网或白名单出网

#### `node-basic`

用途：

- Node / 前端构建任务

策略：

- Node 运行时
- 允许 npm / pnpm / test

#### `research-net`

用途：

- 有限外部信息采集

策略：

- 白名单出网
- 限制下载和文件落盘

#### `browser-web`

用途：

- 网页打开、抓取、自动化验证

策略：

- 带浏览器环境
- 更高内存
- 更严格时长控制

#### `fullstack-lite`

用途：

- 需要 Python + Node 混合工具链的任务

策略：

- 成本更高
- 不建议作为默认 profile

### 8.2 Profile 选择原则

Coordinator 选 profile 时遵守：

1. 优先最小权限
2. 优先最小资源
3. 优先最短寿命
4. 优先最少网络能力
5. 不允许 Agent 自行升级 profile 权限

---

## 9. 生命周期设计

建议把 sandbox 生命周期明确建模，而不是只在代码里临时 create / kill。

### 9.1 生命周期状态

```text
REQUESTED
  -> CREATING
  -> READY
  -> ACTIVE
  -> IDLE
  -> EXPIRING
  -> TERMINATED

异常分支：
CREATING -> FAILED
ACTIVE -> ERROR
IDLE -> FORCE_KILLED
```

### 9.2 建议流程

1. Coordinator 识别 subtask 需要 sandbox
2. SandboxManager 根据 profile 申请 sandbox
3. 记录 `sandbox_id` 并绑定到 run / subtask
4. 准备注入文件、环境变量、metadata
5. Tool 在 sandbox 内执行动作
6. 收集日志、文件索引、执行结果
7. 回写 artifact / transcript / replay
8. 达到结束条件后主动销毁

### 9.3 续期规则

只有以下场景允许续期：

1. 长测试正在运行
2. 浏览器自动化尚未完成
3. Coordinator 评估继续保留比重新创建更划算

默认原则：

**宁可重新创建，不要无节制续期。**

---

## 10. 输入输出与文件策略

sandbox 不是最终存储，不应该承担长期保存责任。

### 10.1 输入进入 sandbox 的内容

1. subtask 输入参数
2. 必要工作文件
3. 模板文件
4. 只读参考资料
5. 必要环境变量

### 10.2 从 sandbox 取出的内容

1. stdout / stderr
2. 退出码
3. 测试报告
4. patch / diff
5. 生成的报告、邮件、PPT、代码文件
6. 执行摘要

### 10.3 文件治理原则

1. sandbox 文件系统只作为临时工作区
2. 重要产物必须导出到 artifact store
3. transcript 中只保存索引和摘要，不塞大文件正文
4. 大文件只保留 object store 引用

---

## 11. 与 Artifact / Replay / Memory 的协同

### 11.1 与 Artifact 的关系

sandbox 每次执行产出的可交付或可审计文件，都应该转成 artifact 元数据。

典型 artifact：

- `sandbox.stdout.log`
- `sandbox.stderr.log`
- `test-report.xml`
- `coverage.xml`
- `generated-report.md`
- `patch.diff`
- `screenshot.png`

### 11.2 与 Replay 的关系

Replay 不应该依赖“活着的 sandbox”，而应依赖留存证据：

- command list
- file manifest
- env summary
- execution result
- artifact refs

也就是说：

**回放是基于证据重建，不是基于原容器重连。**

### 11.3 与 Memory 的关系

不是所有 sandbox 输出都应该进入 memory。

推荐原则：

1. 原始日志不直接入长期记忆
2. 经过摘要和归因的经验可进入长期记忆
3. 失败模式、修复策略、环境约束可以沉淀为可检索记忆

例如：

- “某 profile 下缺失依赖导致 pytest 失败” 可以进入经验记忆
- 完整 5MB stdout 不应该直接入 memory

---

## 12. 安全与治理要求

### 12.1 最小权限

默认不允许：

- 宿主机目录任意挂载
- root 权限执行
- 任意出网
- 任意安装系统级依赖

### 12.2 身份与租户隔离

每个 sandbox 请求至少绑定：

- `tenant_id`
- `user_id` 或 `principal_id`
- `task_id`
- `run_id`
- `subtask_id`
- `agent_role`

### 12.3 配额控制

需要至少有：

- 每租户最大活跃 sandbox 数
- 每 run 最大 sandbox 数
- 单 sandbox 最大 TTL
- 单任务最大 artifact 体积

### 12.4 清理策略

必须支持：

- 主动正常回收
- 超时自动清理
- Worker 崩溃后的兜底清理
- 定时 orphan sandbox 扫描

---

## 13. 推荐模块拆分

建议后续代码拆成下面几层。

### 13.1 Domain / Models

- `SandboxProfile`
- `SandboxLease`
- `SandboxExecution`
- `SandboxStatus`

### 13.2 Provider Layer

- `SandboxProvider`
- `OpenSandboxAdapter`

### 13.3 Control Layer

- `SandboxManager`
- `SandboxLeaseManager`
- `SandboxPolicyEvaluator`

### 13.4 Tool Integration Layer

- `SandboxCommandTool`
- `SandboxFileTool`
- `SandboxBrowserTool`

### 13.5 Persistence / Audit Layer

- `SandboxExecutionRepository`
- `SandboxArtifactCollector`
- `SandboxReplayRecorder`

---

## 14. 事件设计建议

建议 sandbox 也进入统一 event bus，而不是只做同步调用。

### 14.1 建议事件

- `sandbox.requested`
- `sandbox.created`
- `sandbox.create_failed`
- `sandbox.file_staged`
- `sandbox.command_started`
- `sandbox.command_completed`
- `sandbox.command_failed`
- `sandbox.artifacts_collected`
- `sandbox.expiring`
- `sandbox.terminated`

### 14.2 事件必须带的上下文

- `tenant_id`
- `session_id`
- `task_id`
- `run_id`
- `subtask_id`
- `sandbox_id`
- `profile`
- `agent_role`

---

## 15. MVP 实施建议

不要一开始就把 sandbox 做成“万能远程计算平台”，建议按三步走。

### 15.1 第一步

先打通最小闭环：

- 一个 subtask 一个 sandbox
- 只支持 `py-basic`
- 只支持 `run_command / write_file / read_file`
- 每次执行都记录日志和退出码
- 执行完立即回收

### 15.2 第二步

增强 profile 和 artifact 能力：

- 引入 `node-basic` / `research-net`
- 接 artifact store
- 接 replay recorder
- 加入超时和 orphan cleanup

### 15.3 第三步

增强调度和多租户治理：

- sandbox lease
- 并发配额
- profile policy
- Redis / event bus 驱动
- K8s runtime

---

## 16. 明确几个反模式

下面这些做法建议明确禁止。

### 16.1 Agent 直接拿到宿主机 shell

这会让平台失去最基本的执行边界。

### 16.2 Tool 自己 new 一个 OpenSandbox client 到处调用

这会让执行治理分散，后面无法统一审计和配额。

### 16.3 把 sandbox 当长期状态容器

sandbox 是执行载体，不是主存储。

### 16.4 把所有输出直接塞进 Task.result

这会破坏对象边界，后续查询、审计、回放都会混乱。

### 16.5 用一个超大 profile 覆盖所有任务

这会造成权限过大、成本过高、治理失控。

---

## 17. 与当前项目代码的关系

结合当前代码现状，sandbox 这块不建议只在现有 `SandboxManager` 上做补丁。

原因很明确：

1. 当前实现还是“provider 的轻包装”，没有 lease、profile policy、artifact/replay、事件、审计概念。
2. 当前 orchestrator 还没有真正把 sandbox 作为执行面来调度。
3. 当前 tool 层还没有形成统一的 sandbox-aware tool runtime。

所以后续更合理的做法是：

- 保留 `SandboxProvider` 抽象思路
- 保留 `OpenSandboxAdapter` 作为 runtime adapter 方向
- 重写 `SandboxManager` 为真正的控制层
- 新增 profile policy、execution record、artifact collector、cleanup 机制

---

## 18. 最终建议

SwarmMind 对 sandbox 的定位应该非常明确：

**它不是可选插件，而是多智能体执行系统的标准副作用承载层。**

因此，平台后续落地时建议坚持这四条：

1. 所有副作用动作默认走 sandbox
2. 所有 sandbox 都必须绑定 profile 和身份上下文
3. 所有 sandbox 执行都必须沉淀为 transcript + artifact + replay 证据
4. 所有 sandbox 能力都必须通过统一平台抽象暴露，而不是在 agent/tool 中分散直连

如果这四条守住，后面的多智能体执行、审计、回放、租户治理、K8s 扩展才会真正站得住。