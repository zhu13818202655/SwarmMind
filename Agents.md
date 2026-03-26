# SwarmMind Agents 方案（详细计划与实施指引）

> 目标：构建一个“多智能体协作 + 自动沙箱环境（Docker/Pod/K8s）”的平台，用于执行复杂任务，具备可扩展、可观测、可审计、可回放能力。
>
> 参考：
> - OpenSandbox（沙箱生命周期、执行 API、Docker/K8s 运行时）
> - AgentScope（多智能体、MsgHub、工作流、工具调用、记忆）

---

## 1. 产品目标与边界

## 1.1 核心目标

1. 支持用户提交复杂任务（如“实现一个功能并测试”）。
2. 任务自动拆解为子任务，由多个 Agent 协作完成。
3. 每个子任务可按需自动创建隔离执行环境（sandbox）。
4. 在 sandbox 中执行代码/命令/文件读写，产出可追踪结果。
5. 任务结束自动清理环境，保留完整日志与工件。

## 1.2 MVP 边界（第一阶段建议）

- 仅支持文本任务（不做 GUI/语音）。
- 仅支持 Python 生态的 Agent 编排。
- 沙箱运行时优先 Docker，本地单机跑通；K8s 作为第二阶段。
- 先支持 3~5 类工具：命令执行、文件读写、测试运行、Git 基础操作、HTTP 请求。

---

## 2. 总体架构

```text
[API/CLI]
   |
   v
[Task Orchestrator]
   |---> [Planner Agent] ---- task graph ----
   |---> [Coordinator Agent] ------------------------------+
   |                                                       |
   +--> [Execution Router] --> [Sandbox Manager Adapter] --+--> OpenSandbox Server
                                |                               |-- Docker runtime
                                |                               |-- Kubernetes runtime
                                |
                                +--> Sandbox lifecycle/create/exec/files/kill

[Agent Runtime (AgentScope)]
   |-- MsgHub / Pipeline
   |-- Role Agents (Coder/Reviewer/Tester/Researcher)
   |-- Memory (short/long term)
   |-- Toolkits (wrapped by sandbox-aware tools)

[Observability]
   |-- Structured logs
   |-- Traces (task_id, agent_id, sandbox_id)
   |-- Metrics (success rate, duration, cost)

[Storage]
   |-- Task state / events
   |-- Artifact store (logs, reports, patches)
```

---

## 3. 多智能体设计（参考 AgentScope）

## 3.1 推荐 Agent 角色

1. **PlannerAgent**：把用户目标拆成 DAG（子任务 + 依赖 + 验收标准）。
2. **CoordinatorAgent**：调度子任务、管理并发、处理失败重试。
3. **CoderAgent**：实现代码、生成补丁、运行静态检查。
4. **TesterAgent**：执行测试、分析失败、回传最小修复建议。
5. **ReviewerAgent**：审查输出是否满足验收标准。
6. **ResearcherAgent（可选）**：查文档与外部依赖信息。

## 3.2 编排模式

- 使用 AgentScope 的 `MsgHub` 管理会话与广播。
- 使用 pipeline（顺序/并行）执行子任务：
  - 顺序：需求分析 → 设计 → 编码 → 测试 → 审核
  - 并行：多个独立子任务可并发执行
- 每个子任务必须绑定：
  - `task_id`
  - `agent_id`
  - `sandbox_profile`（如 python-build, web-scrape）
  - `acceptance_criteria`

## 3.3 记忆与上下文

- 短期记忆：当前任务上下文（最近 N 轮消息、当前变更）。
- 长期记忆：历史任务模式、常见修复策略、项目约定。
- 限制上下文污染：不同子任务默认隔离，必要时仅共享“摘要事实”。

---

## 4. 自动开“虚拟机/沙箱”能力设计（参考 OpenSandbox）

> OpenSandbox 本质是“通用沙箱平台”，支持 sandbox 生命周期 API，运行时可选 Docker/Kubernetes，并支持命令执行、文件操作、网络策略与隔离能力。

## 4.1 接入原则

1. **统一抽象层**：在 SwarmMind 内定义 `SandboxProvider` 接口，避免业务直接耦合 OpenSandbox SDK。
2. **按需创建**：每个子任务在执行前创建 sandbox，不预先开太多环境。
3. **短生命周期**：默认 TTL（如 10~30 分钟），任务结束主动销毁。
4. **失败可恢复**：创建失败自动重试 + 切换 profile。
5. **安全优先**：最小权限、只读挂载优先、网络白名单。

## 4.2 SandboxProvider 建议接口

```python
class SandboxProvider(Protocol):
    async def create(self, profile: str, timeout_sec: int, env: dict) -> SandboxHandle: ...
    async def run_command(self, sandbox_id: str, cmd: str, cwd: str | None = None) -> ExecResult: ...
    async def write_files(self, sandbox_id: str, files: list[WriteEntry]) -> None: ...
    async def read_file(self, sandbox_id: str, path: str) -> str: ...
    async def copy_out(self, sandbox_id: str, remote_path: str, local_path: str) -> None: ...
    async def kill(self, sandbox_id: str) -> None: ...
```

## 4.3 OpenSandbox 适配层（关键流程）

1. `create(profile)`
   - 选择镜像（如 `opensandbox/code-interpreter:*`）
   - 注入 entrypoint/env/timeout
   - 返回 `sandbox_id`
2. `prepare`
   - 写入任务文件（代码、配置、输入）
3. `execute`
   - 执行 shell/python
   - 获取 stdout/stderr/exit_code
4. `collect`
   - 回收报告/测试结果/产物文件
5. `destroy`
   - 正常结束或异常兜底统一 kill

## 4.4 运行时策略

- **本地开发**：OpenSandbox + Docker（最先打通）
- **生产部署**：OpenSandbox + Kubernetes runtime
- **扩展选项**：高隔离场景可评估 gVisor/Kata/Firecracker 方案

## 4.5 沙箱规格（Profiles）建议

- `py-basic`：Python + pytest + lint
- `node-basic`：Node + npm + test
- `fullstack-lite`：Python + Node 混合
- `research-net`：允许外网白名单访问
- `secure-offline`：禁外网、仅本地工具

每个 profile 固定：
- 镜像
- CPU/内存限制
- 网络策略
- 最大执行时长
- 可挂载目录

---

## 5. 任务执行生命周期（端到端）

1. 用户提交任务（自然语言 + 附件 + 约束）
2. Planner 生成 DAG 子任务与验收标准
3. Coordinator 调度可并发子任务
4. 每个子任务：创建 sandbox → 下发上下文 → 执行工具链
5. 子任务产出（代码、日志、报告）回传
6. Reviewer 汇总并判断是否达标
7. 未达标则触发局部重试（限制次数）
8. 最终输出交付包 + 执行回放记录

---

## 6. 项目目录建议（可按此初始化）

```text
SwarmMind/
  apps/
    api/                     # FastAPI/HTTP 接口
    worker/                  # 异步任务执行器
  swarmmind/
    agents/
      planner.py
      coordinator.py
      coder.py
      tester.py
      reviewer.py
    orchestration/
      dag.py
      scheduler.py
      state_machine.py
    sandbox/
      provider.py            # SandboxProvider 抽象
      opensandbox_adapter.py # OpenSandbox 实现
      profiles.py
    tools/
      sandbox_tools.py       # run_cmd/read_file/write_file...
      git_tools.py
      test_tools.py
    memory/
      short_term.py
      long_term.py
    models/
      task.py
      event.py
      artifact.py
    observability/
      logging.py
      tracing.py
      metrics.py
  configs/
    profiles/
      py-basic.yaml
      secure-offline.yaml
  tests/
    unit/
    integration/
    e2e/
  Agents.md
```

---

## 7. 分阶段实施计划（详细）

## Phase 0：技术预研（1 周）- 已完成

- 跑通 OpenSandbox 本地最小示例：create/exec/files/kill。
- 跑通 AgentScope 最小多 Agent（2~3 agent + MsgHub）。
- 产出：
  - 技术可行性报告
  - 关键 API 清单
  - 风险列表（网络、隔离、成本、并发）

**验收标准**：
- 能通过一条脚本自动创建 sandbox 并执行命令后清理。
- 两个 agent 能完成一次简单协作对话并产出文本结果。

## Phase 1：MVP 核心链路（2~3 周）

- 实现 Task Orchestrator 与基础状态机。
- 实现 `SandboxProvider` + OpenSandbox 适配器。
- 接入 3 个 agent：Planner/Coder/Tester。
- 提供 CLI 或单 API：提交任务并返回最终结果。

**验收标准**：
- 连续 20 次任务执行成功率 ≥ 80%。
- 失败任务可定位（有 task_id/sandbox_id 日志）。
- sandbox 无明显泄漏（任务结束后可回收）。

## Phase 2：稳定性与可观测（2 周）

- 加入重试策略（创建失败、命令超时、工具异常）。
- 加入并发控制（队列、租户限流、资源配额）。
- 接入 tracing/metrics（成功率、时延、重试率、成本）。
- 增加审计日志与执行回放。

**验收标准**：
- 高并发压测下系统可控降级。
- 可按 task_id 追踪完整执行链路。

## Phase 3：K8s 化与安全增强（2~4 周）

- 迁移 OpenSandbox runtime 到 Kubernetes。
- 配置 network policy / egress policy。
- 引入更高隔离运行时（按需）。
- 增加 secrets 管理（Vault/K8s Secret）。

**验收标准**：
- 支持多节点调度与自动扩缩容。
- 安全扫描通过基线要求。

---

## 8. 关键实现细节（必须落实）

## 8.1 状态机设计

建议任务状态：
`PENDING -> PLANNING -> RUNNING -> REVIEWING -> SUCCEEDED/FAILED/CANCELLED`

子任务状态：
`QUEUED -> SANDBOX_CREATING -> EXECUTING -> VERIFYING -> DONE/ERROR`

## 8.2 失败处理策略

- sandbox 创建失败：指数退避重试 2~3 次。
- 命令执行超时：中断进程并标记 `TIMEOUT`。
- 工具调用失败：允许 agent 自我修复一次。
- 达到失败阈值：交由 Coordinator 触发 fallback（更保守 profile）。

## 8.3 成本与性能控制

- 任务级预算（token/time/sandbox count）。
- 统一超时策略：任务总超时 + 子任务超时。
- 大文件禁止全量传输，改为分片或摘要。

## 8.4 安全基线

- 默认禁外网，按任务显式开白名单。
- 运行用户非 root。
- 限制可执行命令集合（按 profile）。
- 对输出做敏感信息脱敏（token/key/path）。

---

## 9. API 设计建议（MVP）

## 9.1 提交任务

`POST /v1/tasks`

请求体：
- `goal`: string
- `constraints`: object
- `profile`: string（可选）
- `artifacts`: list（可选）

返回：
- `task_id`
- `status`

## 9.2 查询状态

`GET /v1/tasks/{task_id}`

返回：
- 总体状态
- 子任务列表
- 当前 agent
- sandbox 摘要信息

## 9.3 获取产物

`GET /v1/tasks/{task_id}/artifacts`

返回：
- 日志、测试报告、输出文件索引

---

## 10. 测试策略

- 单元测试：
  - DAG 拆解
  - 状态机转移
  - SandboxProvider mock
- 集成测试：
  - OpenSandbox 真实 create/exec/kill
  - 多 agent 协作闭环
- E2E：
  - “生成代码并跑测试”完整场景
  - 并发任务 + 失败恢复

**质量门禁建议**：
- 关键路径覆盖率 > 80%
- E2E 每日定时运行

---

## 11. 你可以直接执行的落地步骤（从今天开始）

1. 搭项目骨架（按第 6 节目录）。
2. 完成 `SandboxProvider` 抽象与 `OpenSandboxAdapter` 最小实现。
3. 用 AgentScope 接上 Planner/Coder/Tester 三角色。
4. 打通一个固定任务模板（例如：生成函数 + 编写测试 + 执行 pytest）。
5. 增加基础日志字段：`task_id/agent_id/sandbox_id/subtask_id`。
6. 补齐 10~15 个核心测试用例。
7. 做一次 20 任务回归，记录失败原因并修复。

---

## 12. 风险清单与应对

- **风险：沙箱泄漏导致资源爆炸**
  - 应对：TTL + 守护清理任务 + 配额。
- **风险：多 agent 相互干扰导致结论漂移**
  - 应对：严格角色职责 + 验收标准结构化。
- **风险：执行结果不可复现**
  - 应对：固定镜像版本 + 固定依赖锁 + 输入输出归档。
- **风险：外部依赖不稳定**
  - 应对：缓存、重试、fallback profile。

---

## 13. 里程碑定义（建议）

- **M1（第 1 周末）**：本地 Docker 沙箱 + 双 agent 协作 Demo。
- **M2（第 3~4 周）**：MVP 可提交任务并稳定产出结果。
- **M3（第 6 周）**：可观测、重试、并发控制完成。
- **M4（第 8~10 周）**：K8s 生产化与安全增强完成。

---

## 14. 参考实现提示

- OpenSandbox：优先复用其 SDK 的生命周期能力（create/run/files/kill），不要在业务层直接写 Docker/K8s 命令。
- AgentScope：优先用 MsgHub + pipeline 做编排，不要一开始就做复杂自研对话总线。
- 所有工具调用都走“sandbox-aware tool wrapper”，确保每次执行都可追踪到具体 sandbox。

---

## 15. Definition of Done（DoD）

满足以下条件即可认为一期完成：

1. 用户提交复杂任务后，系统可自动拆解并由多 agent 协作执行。
2. 子任务可自动创建并销毁 sandbox（Docker runtime）。
3. 至少一个真实开发场景（编码 + 测试）可稳定通过。
4. 可按 task_id 完整回放执行过程与日志。
5. 出现失败时有明确错误分类与可执行修复建议。

---

如果你愿意，我下一步可以继续给你生成：

1. `OpenSandboxAdapter` 的 Python 代码模板；
2. `AgentScope` 三角色（Planner/Coder/Tester）最小可运行示例；
3. 一份 `docker-compose` 本地联调脚本（API + Worker + OpenSandbox）。

---

## 16. 仓库协作约定

当前仓库的 Git 与本地工作区约定如下：

1. `git add` 与 `git commit` 使用 `root` 账号执行。
2. `git push` 使用 `admin2` 账号执行。

如果后续调整了本地账号或工具链约束，应同步更新本节，避免自动化代理和人工操作出现不一致。
