# SwarmMind 用户任务完成链路与 OpenAkita 参考分析

> 目的：把当前 SwarmMind 在“用户发送一个任务后，系统如何一步步把它完成”的真实处理链路讲清楚，并对照 `openakita/docs/agent-execution-flow.md` 判断哪些设计值得借鉴，哪些不适合直接照搬。

关联材料：

- `swarmmind/gateway/gateway.py`
- `swarmmind/app/container.py`
- `swarmmind/orchestration/task_orchestrator.py`
- `swarmmind/orchestration/coordinator.py`
- `swarmmind/orchestration/scheduler.py`
- `swarmmind/orchestration/execution_runner.py`
- `swarmmind/orchestration/run_state_service.py`
- `swarmmind/skill_system/service.py`
- `openakita/docs/agent-execution-flow.md`

---

## 1. 一句话结论

当前 SwarmMind 的主链路本质上是：

**Gateway 接住任务 -> Orchestrator 明确规划 subtasks -> Coordinator/Scheduler 选择可执行子任务 -> ExecutionRunner 按 strategy 和 tool 执行 -> Artifact / Replay / RunState 汇总 -> 必要时进入 repair/rework -> 最终收敛为 task/run 终态。**

这是一条典型的：

1. **事件驱动**
2. **plan-first**
3. **结构化 subtask**
4. **sandbox-aware**
5. **可审计、可回放**

的任务执行链。

而 OpenAkita 默认主链更接近：

1. 当前主 Agent 先进入统一的推理执行循环
2. 在推理过程中按需调用委派工具
3. 再由 orchestrator 负责运行时调度和监督

所以两者的差异不是“谁更先进”，而是**控制权放在编排器还是放在当前主 Agent 的推理循环里**。

---

## 2. 当前 SwarmMind 的真实任务完成链路

下面按真实运行顺序描述，而不是按理想架构图描述。

## 2.1 任务入口：Gateway 接住任务并建立执行上下文

用户提交任务后，首先进入 `Gateway.submit_task()`。

这一层当前负责的事情包括：

1. 对请求做 admission 与 normalize
2. 获取或创建 session
3. 创建 `Task`
4. 创建 `Run`
5. 创建 `ReplayRoot`
6. 把 `profile`、`preferred_strategy`、`tenant_id` 等信息写入 task metadata
7. 发布 `task.created` 事件

这一层的关键设计点是：

1. API / CLI 不直接串行推动后续业务
2. 用户请求在入口被转换为领域对象和事件
3. 后续执行链由事件订阅者推进

这意味着 SwarmMind 的任务从一开始就不是“某个大 Agent 直接开干”，而是先进入平台自己的控制面。

## 2.2 编排起点：TaskOrchestrator 负责初次规划与派发

`task.created` 事件由 `TaskOrchestrator.handle_task_created()` 消费。

这一层会做：

1. 将 task 状态推进到 `PLANNING`
2. 将 run 状态推进到 `PLANNING`
3. 调用 `Planner.plan(task, run)` 生成 subtasks
4. 持久化 subtasks
5. 把 subtask ids 挂到 run 上
6. 发布 `task.planning.completed`
7. 调用 `_dispatch_ready_subtasks()` 派发第一批 ready subtasks

这里说明一件很关键的事：

**SwarmMind 当前是明确的 plan-first 模式。**

也就是：

1. 先得到结构化 subtasks
2. 再由后续执行链消费 subtasks

而不是让某个主 Agent 一边思考一边临时决定下一步做什么。

## 2.3 规划阶段：Planner 产出结构化任务图而不是自由文本步骤

当前 `Planner` 的输出不是随意文本，而是结构化的 `SubTask` 列表，每个 subtask 至少带：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`
4. `sandbox_profile`
5. `acceptance_criteria`
6. `dependencies`

这一步的价值是：

1. 后续调度有明确的依赖图
2. execution runner 不必再自己猜“我要用什么能力包”
3. 验证、审查、repair 可以围绕 subtask 继续追加链路

当前 Planner 也会先尝试 LLM，再回退到规则规划，因此系统不是纯规则死板执行，也不是完全把控制权交给 LLM。

## 2.4 调度与分配：Scheduler + Coordinator 负责把 subtasks 变成可执行单元

在 orchestrator 内部：

1. `Scheduler.get_ready_subtasks()` 根据 `dependencies` 选择可执行 subtasks
2. `Coordinator.assign()` 把 ready subtask 绑定到 `ExecutionProfile`

当前 `ExecutionProfile` 至少包含：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`
4. `sandbox_profile`

然后 orchestrator 会发布 `subtask.assigned` 事件。

这里要注意：

1. SwarmMind 目前没有像 OpenAkita 那样让主 Agent 自己决定“我要不要把工作委派给另一个 agent”
2. 它是平台编排器显式决定：哪些 subtask 已 ready，哪些 subtask 被 assigned

这是一种更可控、更容易做 replay 的执行模型。

## 2.5 执行入口：ExecutionRunner 消费 assigned subtask

`subtask.assigned` 事件由 `ExecutionRunner.handle_subtask_assigned()` 消费。

这一层的实际动作可以拆成 5 步：

1. 加载 task / run / subtask
2. 解析 `preferred_strategy` 或按 role 推导默认 strategy
3. 计算当前 subtask 的 selected tools
4. 发布 `strategy.started`
5. 进入对应 strategy 的执行逻辑

也就是说，当前 SwarmMind 的真正执行者不是 `TaskOrchestrator`，而是 `ExecutionRunner`。

但是 `ExecutionRunner` 仍然是在平台编排框架里工作，而不是一个自由漫游的主 Agent。

## 2.6 Strategy 层：当前执行被建模为 runtime strategy，而不是“委派给另一个 Agent”

当前默认 strategies 包括：

1. `build_app`
2. `research`
3. `write_report`
4. `task_planning`
5. `verification`
6. `review`

它们被注册在 `ExecutionStrategyRegistry` 中，并通过 `CallbackStrategy` 指向具体处理器。

这说明当前 SwarmMind 的执行模型是：

1. **先选 strategy**
2. **再执行 strategy 内部的工具和 sandbox 逻辑**

而不是：

1. 先创建一个新的子 Agent
2. 再把任务完整委托给那个子 Agent 自己 ReAct

当前 `Planner` 和 `ExecutionRunner` 内部确实会借用 AgentScope 模型能力生成内容或规划文本，但整体主链仍然不是“统一 agent runtime + 委派工具”模式。

## 2.7 Tool 层：ExecutionRunner 会显式注册和选择运行时工具

`ExecutionRunner` 当前会往 `ToolRegistry` 注册一组默认工具，包括：

1. `sandbox_exec`
2. `artifact_read`
3. `memory_lookup`
4. `memory_write`
5. `project_read`
6. `project_write`
7. `project_list`
8. `project_exists`
9. `web_search`
10. `browser_read`
11. `list_skill_scripts`
12. `get_skill_details`
13. `run_skill_script`

然后根据 `required_tool_groups` 和 role 选择当前 subtask 的可用工具集合。

这一步很重要，因为它说明 SwarmMind 已经不是“执行器内部硬编码所有动作”，而是在逐步向：

1. strategy 决定运行路径
2. tool 决定原子能力

这两层解耦的方向上前进。

## 2.8 Sandbox 执行：普通执行型 subtask 进入隔离环境

对 coder / executor / writer / researcher / planner 等偏执行型子任务，当前主链会走 sandbox execution。

主要步骤是：

1. subtask 进入 `SANDBOX_CREATING`
2. 通过 `SandboxManager.acquire()` 申请 lease
3. 发布 `sandbox.created`
4. 构建 `CommandRequest`
5. 通过 `sandbox_exec` 工具执行命令
6. 采集 stdout / stderr / exit_code
7. 生成 artifacts
8. 发布 `artifact.created`
9. 根据 exit code 决定 subtask succeed / fail

这一层体现的核心原则是：

1. 任务执行必须可隔离
2. 执行要留下 artifact 和事件痕迹
3. sandbox 是平台受控资源，不是 Agent 自己本地乱跑 shell

## 2.9 Verification / Review：测试与审查不是简单 exit code 判断

当前 tester / reviewer 角色已经不是简单走“和 coder 一样的 sandbox markdown 输出”。

当前逻辑是：

1. tester 进入 `verification` strategy
2. reviewer 进入 `review` strategy
3. `ExecutionRunner` 会读取依赖 subtasks 和 artifacts
4. 生成结构化 `VerificationResult` 或 `ReviewDecision`
5. 再将结果持久化为 subtask result 和 artifact

这一步意味着：

1. 系统已经开始具备独立验证和独立审查的运行时语义
2. 成功不再只看一条 shell 命令的退出码

虽然它还没有演进成 OpenAkita 那种“由统一 Agent Runtime 中的专业子 Agent 独立完成验证 / 审查”，但在平台主链里已经具备了质量闸门雏形。

## 2.10 Skill 执行：skill script 已经是正式平台能力，而不是内部 helper

当前 skill 执行链是：

1. `SkillExecutionService`
2. `SkillTool`
3. `run_skill_script`

并且 skill script 执行会：

1. 通过 sandbox 执行
2. 发布 `skill.script.started / completed / failed`
3. 持久化 artifacts
4. 进入 replay timeline

这说明当前 skill 已经开始从“知识目录”走向“可执行能力对象”，但它仍然是平台显式授权和调度的能力，不是任何 agent 默认自由可用的委派动作。

## 2.11 RunState 收敛：执行完成后由平台统一判断任务是否完成

每次 subtask 执行结束后，`RunStateService.reconcile()` 会重新聚合：

1. 哪些 subtasks succeeded
2. 哪些 subtasks failed
3. 是否有 unresolved rework
4. 当前 run / task 应进入什么 phase / status

然后在状态变化时发布 `run.updated`。

也就是说，最终“任务是否完成”不是某个 agent 自己宣布，而是平台状态机统一收口。

这和 OpenAkita 那种由主 Agent 最终整合和回复用户的模型，控制点明显不同。

## 2.12 Repair / Rework：任务失败后不是只能整单报错

当前 orchestrator 还支持两种补救链：

1. reviewer 给出 `rework` 决策后，动态生成 `repair -> verify -> review`
2. 普通执行型 subtask 失败后，在允许时生成 failure repair chain

这说明当前系统已经不是单向流水线，而是开始具备：

1. 局部重试
2. 局部返工
3. 继续验证
4. 再次审查

这类平台级控制能力。

---

## 3. 用一句更准确的话描述当前 SwarmMind

如果要压缩成一句话，当前 SwarmMind 更准确的定义应该是：

> 一个以平台编排器为主导、以结构化 subtasks 为执行单元、以 strategy 和 tools 为运行时能力边界、以 sandbox / artifacts / replay / run-state 为审计和收敛机制的任务执行系统。

这句话强调四件事：

1. 平台编排器主导，而不是主 Agent 主导
2. subtasks 是一等执行对象
3. strategy/tool 是运行时能力边界
4. replay 和 run-state 是主链的一部分

---

## 4. OpenAkita 的执行流给我们的核心启发

`openakita/docs/agent-execution-flow.md` 的核心价值，不在于“它比我们好”，而在于它把另一种控制权分配方式讲得很清楚。

它强调的是：

1. 主 Agent 先进入统一执行循环
2. 委派被建模为工具调用
3. orchestrator 是 runtime coordinator，不是默认总脑
4. 子 Agent 仍然是同构 Agent Runtime，只是 profile / prompt /权限不同

这些点里，有些很值得借鉴，有些不适合直接照搬。

---

## 5. 明确可借鉴的部分

## 5.1 可借鉴一：把“运行时协调器”和“思考者”明确区分

OpenAkita 最值得借鉴的一点，是它明确区分：

1. 当前主 Agent 是主要思考者
2. orchestrator 是运行时协调器

对 SwarmMind 的意义在于：

1. 我们也需要进一步明确哪些判断属于 orchestrator
2. 哪些判断属于 planner / execution model / future specialized agent

当前 SwarmMind 虽然已有 Planner、Coordinator、ExecutionRunner、RunStateService 分层，但“谁是真正的决策者”仍然不够清晰，尤其在未来引入 `AgentProfile / skill_mode / tool_policy` 后更需要明确边界。

可借鉴结论：

1. 保持 orchestrator 偏控制面
2. 让 agent / planner / reviewer 等角色承担更明确的认知职责
3. 避免把所有事情重新塞回一个万能 ExecutionRunner

## 5.2 可借鉴二：能力边界要显式建模，而不是隐式挂在工厂或 prompt 上

OpenAkita 的 `AgentProfile + skills + skills_mode + custom_prompt + preferred_endpoint` 这套思路，对 SwarmMind 非常有参考价值。

当前 SwarmMind 已有：

1. `preferred_strategy`
2. `required_tool_groups`
3. native skill catalog
4. formal skill tools

但还缺：

1. `AgentProfile`
2. `skill_mode`
3. `tool_policy`
4. role/profile 级的显式能力边界

这一点是当前最值得借鉴的后续方向。

可借鉴结论：

1. 给 agent 引入 profile 层
2. 让 profile 显式决定 skills/tools/policies
3. orchestration 下发的执行上下文应和 profile 约束统一

## 5.3 可借鉴三：把 handoff / delegation / skill use 做成可观察的运行时动作

OpenAkita 里一个重要优点是：

1. 委派不是黑盒
2. 它被建模成工具调用
3. 前端和系统都能观察 handoff 状态

这对 SwarmMind 的启发不是“马上改成 delegate_to_agent”，而是：

1. 后续 skill 使用边界要继续事件化
2. 后续如果引入 specialized agents，handoff 也必须是显式事件，而不是内部函数跳转
3. UI / query 层要能看见 delegation / handoff / policy decision 的轨迹

我们现在已经有：

1. `strategy.*`
2. `tool.*`
3. `skill.script.*`

后续可以继续扩展到：

1. `agent.handoff.started`
2. `agent.handoff.completed`
3. `policy.denied`

这类事件。

## 5.4 可借鉴四：对子执行单元增加更严格的递归和权限约束

OpenAkita 对 sub-agent 有两层硬约束：

1. prompt 层说明你是子 Agent，不允许继续委派
2. tool handler 在运行时硬拦截再次委派

SwarmMind 当前还没有真正的 sub-agent delegation 主链，但一旦未来增加 specialized agent execution，这一点很值得借鉴。

原因是：

1. 平台要防止无限委派
2. 要防止子执行单元突破 policy 边界
3. 要让 replay 中的 delegation tree 可控可解释

可借鉴结论：

1. 如果未来引入 agent-to-agent handoff，必须有递归深度限制
2. 必须有平台层硬拦截，而不只靠 prompt 自觉

## 5.5 可借鉴五：把“自由执行循环”和“显式计划模式”分开

OpenAkita 里 `ask / plan / agent` 三种模式的区分，也有参考意义。

SwarmMind 虽然当前是 plan-first，但未来也会遇到一个问题：

1. 不是所有任务都需要完整 DAG + repair/review
2. 有些任务只是轻量研究、轻量读写、轻量说明

所以可以借鉴的不是“取消 plan-first”，而是：

1. 未来引入更明确的 execution modes
2. 区分轻量直接执行、显式规划执行、强审计执行三种运行路径

这比当前所有任务都走同一条重型编排链，会更灵活。

---

## 6. 不适合直接照搬的部分

## 6.1 不适合一：把主链改成 agent-first、按需自由委派

OpenAkita 默认让主 Agent 先进入统一推理循环，再按需委派。

这套方式对 SwarmMind 当前阶段并不适合直接照搬，原因有三点：

1. SwarmMind 当前的核心优势就是结构化 subtasks、replay、run-state、repair/rework 主链清晰
2. 如果改成自由委派，任务边界、审计粒度、repair 触发点会立刻变模糊
3. 我们现在更需要确定性和可控性，而不是更强的自由度

所以当前不应该把主链从：

1. `Gateway -> Orchestrator -> SubTasks -> ExecutionRunner`

改成：

1. `Main Agent -> Delegation Tools -> Child Agents`

这会削弱当前已经有的控制面能力。

## 6.2 不适合二：让 planner 降级为可选模式

OpenAkita 的 `plan` 更像显式人机交互模式，不是默认必经阶段。

这不适合当前 SwarmMind 直接照搬，因为：

1. 我们的 repair/rework、acceptance criteria、sandbox profile 都依赖结构化 subtasks
2. DAG / Scheduler / Coordinator 都建立在 planning 结果之上
3. 一旦 planning 变成可选，后续主链的大量能力都需要重写

所以对 SwarmMind 而言：

1. 规划阶段仍应是默认主链的一部分
2. 真正可借鉴的是未来增加更轻模式，而不是把 planning 从主链去掉

## 6.3 不适合三：让子执行单元默认共享完整会话上下文

OpenAkita 的子 Agent 更像复用同一会话历史，再附加一条 delegated message。

对 SwarmMind 来说，这种共享模式风险较高：

1. 容易造成 subtask 上下文污染
2. 不利于 subtask 结果和责任边界隔离
3. 不利于 replay 和 deterministic repair

SwarmMind 更适合坚持：

1. subtask 拿结构化 task spec
2. 明确 dependencies / artifacts / accepted context
3. 少量引入 memory / reference，而不是完整共享会话历史

## 6.4 不适合四：把协作完全建模为普通工具，不再经过平台编排状态机

OpenAkita 把 delegation 建模成工具调用，这在 agent-first 系统里很合理。

但对 SwarmMind 当前阶段，如果把“创建 / 指派 / 继续调度 / repair”全部退化成普通工具调用，会有几个问题：

1. orchestrator 状态机会被削弱
2. subtask 生命周期会重新变得不清晰
3. event sourcing 和 replay 会失去统一入口

所以当前更适合的是：

1. 平台编排动作仍走 orchestrator / event bus
2. 未来如引入 handoff，可把“申请 handoff”建模为工具
3. 但真正的 handoff 生效仍应由 orchestrator 审批和落地

换句话说，**可以把协作请求工具化，但不能把平台状态推进完全工具化。**

## 6.5 不适合五：过早引入大量 ephemeral agent / clone 机制

OpenAkita 的 `spawn_agent`、`delegate_parallel`、ephemeral clone 很灵活。

但对 SwarmMind 当前阶段，直接引入会带来：

1. profile 管理复杂度暴增
2. replay / audit 模型复杂度暴增
3. policy 边界和资源配额管理难度暴增

所以在我们还没有把 `AgentProfile / skill_mode / tool_policy` 落实之前，不适合直接引入这类机制。

---

## 7. 更适合 SwarmMind 的参考姿势：有限借鉴，而不是架构照抄

综合来看，更合理的方向不是把 SwarmMind 改造成 OpenAkita，而是借它的优点补我们自己的短板。

建议的参考姿势是：

## 7.1 保持现有主链不变

继续保持：

1. Gateway 作为唯一任务入口
2. Orchestrator 负责 planning / scheduling / repair/rework
3. ExecutionRunner 负责 runtime execution
4. RunStateService 负责状态收敛

这是当前系统最有价值的基础。

## 7.2 在现有主链上引入显式 AgentProfile

最值得优先做的是：

1. `AgentProfile`
2. `skill_mode`
3. `tool_policy`
4. role/profile 级约束

也就是把 OpenAkita 在 profile 侧做得较清楚的部分，吸收到 SwarmMind 里。

## 7.3 后续如果引入 specialized agent，只把它作为 execution strategy 的一种后端

未来如果我们要引入更强的多 agent 协作，比较合适的方式不是推翻主链，而是：

1. 继续由 orchestrator 决定 subtask
2. 让某些 strategy 选择“由 specialized agent runtime 执行”
3. handoff 与 delegation 作为 strategy 内部的一种受控实现

这样可以同时保留：

1. 平台确定性
2. 事件可回放
3. policy 可控
4. agent 协作灵活性

## 7.4 delegation 应该先成为“受控能力”，再成为“默认能力”

如果未来要引入 delegation，建议顺序是：

1. 先把 `AgentProfile / policy / event` 做好
2. 再允许某些 role 或 strategy 有 handoff 能力
3. 最后才考虑是否默认给主执行单元自由委派

这样更符合 SwarmMind 当前平台导向的设计目标。

---

## 8. 最终判断

最终可以把判断归纳成 6 句话：

1. **SwarmMind 当前是平台编排主导的 plan-first 执行系统，不是 agent-first 的自由委派系统。**
2. **用户任务是否完成，当前由 orchestrator + execution runner + run-state service 共同决定，而不是由某个主 Agent 自己宣布。**
3. **OpenAkita 最值得借鉴的是能力边界显式建模、handoff 的可观察性、以及对递归委派的硬约束。**
4. **OpenAkita 不适合直接照搬的，是把主链改成 agent-first、把 planning 变成可选、以及让子执行单元共享整段会话上下文。**
5. **SwarmMind 更合理的演进方向，是在保留现有事件驱动编排主链的前提下，引入 `AgentProfile / skill_mode / tool_policy` 和受控 handoff。**
6. **也就是说，我们应该借鉴 OpenAkita 的 profile 和协作边界设计，而不是复制它的控制权分配方式。**

---

## 9. 建议的下一步

基于这份对照，下一步最值得落地的事项有三项：

1. 引入 `AgentProfile`，把 skill、tool、policy 从隐式配置提升为显式模型
2. 在 orchestration/execution profile 中增加 skill allowlist / script allowlist / handoff policy
3. 为未来 specialized agent execution 预留 `agent-backed strategy` 这种受控 strategy 类型，而不是直接把主链切成 agent-first

---

## 10. SwarmMind 中 `role / strategy / tool_group / sandbox_profile` 的职责分层图

前面对 `strategy` 的讨论，容易和 `role`、`tool`、未来的 `AgentProfile` 混在一起。

更准确的拆法应该是：

1. `role` 决定“这类子任务在语义上是谁来负责”
2. `strategy` 决定“这类子任务按什么执行路径完成”
3. `tool_group` 决定“为这类执行装备哪一组原子能力”
4. `tool` 决定“真正可以调用的最小能力单元是什么”
5. `sandbox_profile` 决定“执行环境、隔离级别和资源限制是什么”
6. `ExecutionProfile` 决定“当前 subtask 在本次运行里最终拿到的能力打包结果”

可以把它画成下面这张分层图：

```text
User Goal
	-> Task
		-> SubTask
			-> ExecutionProfile
				|- role                = 谁负责这类工作
				|- preferred_strategy  = 走哪条执行路径
				|- required_tool_groups= 装备哪些能力包
				|- sandbox_profile     = 在什么环境里执行
							|
							+-> StrategyProfile / ExecutionStrategy
							|      -> 定义执行语义与执行后端
							|
							+-> ToolGroup
							|      -> 选择一组原子 tools
							|
							+-> SandboxManager
									 -> 创建/分配对应 sandbox
```

如果进一步压缩成一句话：

> `role` 回答“谁负责”，`strategy` 回答“怎么跑”，`tool_group` 回答“能用什么能力包”，`sandbox_profile` 回答“在哪种受控环境里跑”，`ExecutionProfile` 则是它们在一次 subtask 执行时的运行时绑定结果。

## 10.1 `role` 的职责

`role` 的作用不是调度代码，不是创建 agent，更不是决定全部工具细节。

它主要负责：

1. 给 subtask 一个明确的职责语义，例如 `coder`、`tester`、`reviewer`
2. 为默认 `strategy` 选择提供回退依据
3. 为默认 `tool_group` 和验收逻辑提供语义上下文

也就是说，`role` 更接近“责任身份”，不是“执行后端”。

## 10.2 `strategy` 的职责

`strategy` 在 SwarmMind 里更像 **runtime execution path**，不是 agent 身份，也不是单个技能。

它主要负责：

1. 指定当前 subtask 应进入哪种执行逻辑
2. 绑定对应的执行 handler
3. 决定结果如何被产出和解释

当前仓库里，`strategy` 已经分成两类：

1. **执行型 strategy**：如 `build_app`、`research`、`write_report`、`task_planning`
	这类目前大多仍复用 sandbox 执行主路径
2. **判定型 strategy**：如 `verification`、`review`
	这类不只是跑命令，而是要产出结构化验证/审查结果

因此 `strategy` 的真正价值不在于名字本身，而在于它定义了：

1. 这类任务走哪条 runtime path
2. 这条 path 对结果和证据的要求是什么
3. 后续 run-state 和 repair/rework 如何理解这个结果

## 10.3 `tool_group` 与 `tool` 的职责

`tool_group` 和 `tool` 是两层：

1. `tool_group` 是能力包
2. `tool` 是原子能力

例如：

1. `project_read`
2. `project_write`
3. `sandbox_exec`
4. `artifact_read`

这些是 orchestration 层关心的能力包。

而真正注册到 `ToolRegistry` 并可被执行的，是更细粒度的工具，例如：

1. `project_read`
2. `project_write`
3. `project_list`
4. `project_exists`
5. `sandbox_exec`
6. `artifact_read`
7. `run_skill_script`

所以更精确地说：

1. orchestration 负责声明“要哪类能力”
2. runtime 负责把它展开成“具体可调用的工具集合”

## 10.4 `sandbox_profile` 的职责

`sandbox_profile` 不回答“做什么”，而回答“在什么执行环境里做”。

它主要负责：

1. 镜像/运行时选择
2. 网络权限
3. CPU / memory 配额
4. 超时和隔离级别
5. 可用命令和依赖环境

所以它和 `strategy` 是正交关系：

1. `strategy` 是执行路径
2. `sandbox_profile` 是执行环境

例如：

1. 一个 `build_app` strategy 可以跑在 `py-basic`
2. 一个 `research` strategy 可以跑在 `research-net`
3. 未来一个 `agent-backed` strategy 也可能仍使用某种 sandbox profile 承载其工具执行

## 10.5 `ExecutionProfile` 的职责

当前 SwarmMind 里，真正把这些信息在执行前绑定起来的是 `ExecutionProfile`。

它更像：

> subtask 在本次执行里的“运行时能力清单”。

它当前至少包含：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`
4. `sandbox_profile`

所以它不是 AgentProfile，也不是 StrategyProfile，而是 orchestrator 在 subtask 被 assign 时生成的 **一次性执行绑定结果**。

## 10.6 一个更稳的抽象边界

如果把上面这些概念按“从业务语义到执行落地”排一遍，更稳的顺序应该是：

1. `SubTask`：这件事是什么，验收标准是什么
2. `role`：谁负责这类事
3. `ExecutionProfile`：这次执行最终装备什么
4. `strategy`：按什么路径执行
5. `tool_group` / `tool`：可以调用什么能力
6. `sandbox_profile`：在什么受控环境里执行

这条边界很重要，因为它能避免后续把：

1. 职责身份
2. 执行路径
3. 工具权限
4. 运行环境

全部揉成一个大而全的“agent 配置对象”。

---

## 11. 适配 SwarmMind 的 `AgentProfile` 设计草案

前面提到可以借鉴 OpenAkita 的 `AgentProfile`，但这里必须先明确：

> `AgentProfile` 不应该替代 `ExecutionProfile`，也不应该替代 `strategy`。它应该补上的是“agent 能力边界和协作边界”的那一层。

换句话说：

1. `ExecutionProfile` 解决的是“这次 subtask 怎么执行”
2. `AgentProfile` 解决的是“如果这次执行要由某个 agent runtime 承担，那么这个 agent 是什么形态、有什么边界”

## 11.1 为什么 SwarmMind 需要 `AgentProfile`

当前 SwarmMind 已经有：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`
4. `sandbox_profile`

但仍缺少一层显式对象来回答这些问题：

1. 这个执行单元允许使用哪些 skill
2. 这个执行单元允许使用哪些 script / tool
3. 这个执行单元是否允许 handoff
4. 这个执行单元使用什么 prompt/persona
5. 这个执行单元优先用哪个 model endpoint

这些内容如果继续散落在：

1. prompt 模板
2. 工具过滤逻辑
3. strategy handler
4. 各种 metadata

里，后面会很难治理。

所以 `AgentProfile` 的必要性，不在于“让系统更像 OpenAkita”，而在于把现在分散的能力边界收拢成显式模型。

## 11.2 `AgentProfile` 不是什么

为了避免边界混乱，需要先明确它不应该承担什么：

1. 不负责替代 `SubTask`
	`SubTask` 仍然描述具体工作目标、依赖和验收标准
2. 不负责替代 `strategy`
	`strategy` 仍然描述执行路径和执行后端
3. 不负责替代 `sandbox_profile`
	环境约束仍应该留在 sandbox 层
4. 不负责替代 orchestrator
	profile 不应该自己决定什么时候派发、什么时候 repair

也就是说，`AgentProfile` 不是万能控制对象，而是 agent 侧的“能力与行为边界合同”。

## 11.3 适配 SwarmMind 后，它应该承担什么

适合放到 `AgentProfile` 里的内容，建议分成 5 组：

### A. 身份与认知层

1. `id`
2. `name`
3. `description`
4. `role`
5. `system_prompt` 或 `prompt_template`

这一层回答“这个 agent 在认知上扮演什么角色”。

### B. 能力边界层

1. `skill_mode`
2. `allowed_skills`
3. `allowed_tool_groups`
4. `allowed_tools`
5. `allowed_skill_scripts`

这一层回答“这个 agent 被允许用哪些能力”。

### C. 执行策略约束层

1. `allowed_strategies`
2. `default_strategy`
3. `default_sandbox_profile`
4. `allow_sandbox_exec`

这一层不是替代 strategy，而是回答“这个 agent 能落到哪些 strategy 上”。

### D. 协作与委派策略层

1. `allow_handoff`
2. `allowed_handoff_targets`
3. `max_handoff_depth`
4. `inherit_context_mode`

这一层回答“这个 agent 能不能委派、能委派给谁、上下文怎么传”。

### E. 模型与路由层

1. `preferred_model`
2. `preferred_endpoint`
3. `fallback_profile_id`
4. `cost_budget`
5. `time_budget_sec`

这一层回答“这个 agent 优先通过什么计算资源执行”。

## 11.4 建议中的模型关系

引入 `AgentProfile` 后，比较合理的关系不是替换现有对象，而是形成下面这组分工：

```text
Task / SubTask
	-> 描述要完成的工作

ExecutionProfile
	-> 描述这次 subtask 的运行时绑定结果

StrategyProfile / ExecutionStrategy
	-> 描述执行路径与执行后端

AgentProfile
	-> 描述执行该路径时，agent 侧允许具备什么认知和能力边界
```

用一句话概括就是：

1. `SubTask` 定义工作
2. `ExecutionProfile` 定义这次执行装备
3. `Strategy` 定义怎么跑
4. `AgentProfile` 定义由 agent runtime 执行时，这个 agent 能长成什么样

## 11.5 和 OpenAkita `AgentProfile` 的关系

OpenAkita 里的 `AgentProfile` 有两个最值得参考的点：

1. 它是一个显式蓝图对象，而不是散落在 prompt 和工厂里的隐式配置
2. 它支持用 profile 来创建或复用特定 agent 实例，并支持 `ephemeral`、`inherit_from` 这种临时派生形态

这意味着它确实可以支撑下面这种模式：

1. 主执行单元根据策略申请一个 specialized agent
2. orchestrator 选择某个 `AgentProfile`
3. runtime 基于该 profile 创建一个带有特定 prompt、skills、endpoint、policy 的 agent
4. 任务结束后，如为临时 agent，则回收对应 profile / instance

因此，对 SwarmMind 来说，最有价值的借鉴不是“照搬 OpenAkita 的 agent-first 控制流”，而是：

1. 学它把 agent 边界做成显式模型
2. 学它把临时派生 agent 也纳入统一 profile 抽象
3. 但不把 SwarmMind 的平台主链控制权交出去

## 11.6 SwarmMind 中更合适的落位方式

如果 SwarmMind 引入 `AgentProfile`，更合适的落位方式应该是：

1. `Planner` 继续输出 `SubTask`
2. `Coordinator` 在 assign 时除了解析 `ExecutionProfile`，还可补充 `agent_profile_id`
3. `ExecutionRunner` 根据 `strategy` 决定：
	- 继续走现有 sandbox execution
	- 或进入未来的 `agent-backed strategy`
4. 如果进入 `agent-backed strategy`，再根据 `agent_profile_id` 创建或选择对应 agent runtime

这意味着 `AgentProfile` 不必一开始就接管全部主链，而可以先只在部分 strategy 中生效。

这是比“直接把主链改成 agent-first”更稳的演进路径。

## 11.7 建议的数据模型草案

下面是一版更适配 SwarmMind 的草案字段：

```python
class AgentProfile(BaseModel):
	 id: str
	 name: str
	 description: str = ""
	 role: AgentRole

	 prompt_template: str | None = None
	 custom_prompt: str | None = None

	 skill_mode: Literal["all", "allowlist", "denylist"] = "all"
	 allowed_skills: list[str] = []
	 allowed_tool_groups: list[ToolGroup] = []
	 allowed_tools: list[str] = []
	 allowed_skill_scripts: list[str] = []

	 allowed_strategies: list[str] = []
	 default_strategy: str | None = None
	 default_sandbox_profile: str | None = None

	 allow_handoff: bool = False
	 allowed_handoff_targets: list[str] = []
	 max_handoff_depth: int = 0
	 inherit_context_mode: Literal["none", "summary", "artifacts", "full"] = "summary"

	 preferred_model: str | None = None
	 preferred_endpoint: str | None = None
	 fallback_profile_id: str | None = None

	 ephemeral: bool = False
	 inherit_from: str | None = None
```

这版草案里最重要的不是字段多少，而是它保持了下面这个原则：

1. profile 定义 agent 边界
2. strategy 定义执行路径
3. execution profile 定义一次执行绑定

三者不互相吞并。

## 11.8 一条推荐的落地顺序

为了避免一次性引入太多复杂度，建议按下面顺序推进：

1. **第一步**：先定义 `AgentProfile` 数据模型，但暂不支持真正的 agent-to-agent handoff
2. **第二步**：在 `ExecutionProfile` 中增加 `agent_profile_id`
3. **第三步**：只允许少数 strategy 支持 `agent-backed strategy`
4. **第四步**：补齐 `handoff.started / completed / denied` 事件
5. **第五步**：最后再考虑是否开放更自由的 delegation

这样做的好处是：

1. 不破坏现有主链
2. 能逐步验证 profile/policy 是否合理
3. replay、审计、配额、权限都还能保持平台可控

## 11.9 最后的设计判断

把 `strategy` 和 `AgentProfile` 放在一起看，最容易出错的地方是把它们当成同一个抽象。

但实际上它们回答的是不同问题：

1. `strategy` 回答“这件事按哪条执行路径完成”
2. `AgentProfile` 回答“如果由 agent runtime 完成，这个 agent 被允许成为什么样子”

因此更合理的目标不是：

1. 用 `AgentProfile` 替换 `strategy`

而是：

1. 用 `AgentProfile` 补足 SwarmMind 当前缺失的 agent 边界模型
2. 用 `agent-backed strategy` 作为未来 specialized agent 执行的受控入口
3. 继续让 orchestrator、run-state、replay 保持主链控制权

---

## 12. 当前实现态对齐

前面的第 10 节和第 11 节最初是设计草案。结合当前代码，下面把已经真实落地的部分明确写清楚，避免文档继续停留在“计划态”。

## 12.1 `agent_profile_id` 已进入主链，而不是只停留在设计层

当前 `agent_profile_id` 已经贯通以下路径：

1. API 请求模型
2. Gateway submit request
3. `TaskRequest`
4. `SubTask`
5. `Coordinator.assign()` 生成的 `ExecutionProfile`

当前实际语义是：

1. 任务级可以声明默认 `agent_profile_id`
2. planner 也可以为单个 subtask 显式给出 `agent_profile_id`
3. coordinator 在 assign 时会做最终解析
4. 如果指定 profile 与当前 subtask `role` 不兼容，则不会强行套用，而是回退到角色默认 profile

也就是说，`agent_profile_id` 现在已经不是“未来也许会用”的字段，而是当前运行时已经生效的选择信号。

## 12.2 planner 已显式暴露和解析 agent profile

当前 planner 已经不是只输出：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`

而是还会显式处理：

1. `agent_profile_id`

已落地行为包括：

1. planner prompt 会注入“Available Agent Profiles JSON”
2. LLM 规划结果可以返回 `agent_profile_id`
3. rule-based fallback 也会为各角色补齐合适的默认 profile
4. planner 在构造 `SubTask` 时会通过 `AgentProfileStore` 做角色兼容性校验和回退

这一步的意义是：

1. profile 选择开始前移到 planning 阶段
2. 但最终仍由 coordinator 再次收口，避免 planner 直接突破运行时边界

## 12.3 `agent_backed` 已作为受控 strategy 落地

当前系统中已经存在保留 strategy：

1. `agent_backed`

它的真实定位不是“替代现有 orchestrator 主链”，而是：

1. 作为某些 subtask 的受控执行后端
2. 允许 `ExecutionRunner` 在不进入默认 sandbox command path 的情况下，走 profile 约束的 agent runtime
3. 仍然保留 subtask lifecycle、artifact、replay、run-state 收敛

因此现在更准确的说法应该是：

1. SwarmMind 仍然是 orchestrator-led
2. 只是 execution backend 新增了一种 `agent_backed` 受控变体

## 12.4 `ExecutionProfile` 已承载 profile 约束结果

当前 `ExecutionProfile` 已不只是：

1. `role`
2. `preferred_strategy`
3. `required_tool_groups`
4. `sandbox_profile`

还已经承载了以下来自 `AgentProfile` 的运行时约束：

1. `agent_profile_id`
2. `allowed_tool_groups`
3. `allowed_tool_names`
4. `skill_mode`
5. `skill_profiles`
6. `allowed_skill_scripts`
7. `handoff_policy`

这意味着：

1. `AgentProfile` 负责定义边界合同
2. `ExecutionProfile` 负责把该合同绑定到一次具体 subtask execution

这正符合前文定义的抽象分层，没有发生 profile 吞并 execution profile 的问题。

## 12.5 handoff 事件已经真实存在，但范围仍然受限

当前系统已经真实发出以下事件：

1. `agent.handoff.started`
2. `agent.handoff.completed`
3. `agent.handoff.denied`
4. `policy.denied`

但要明确当前边界：

1. handoff 只在 `agent_backed` strategy 内支持
2. handoff 请求目前来自 `task.constraints.handoff_requests`
3. 是否允许 handoff 由 `HandoffPolicy` 决定
4. 目标 profile、最大深度、上下文模式都会在运行时检查
5. 若不允许，则不会创建新的 delegation tree，只会记录 denied 事件并回退到本地执行

所以当前更准确的状态不是“SwarmMind 已支持通用 agent delegation”，而是：

1. 已支持第一版受控 handoff runtime
2. 但还没有演进成 orchestrator 审批式、多层级、可查询的 delegation tree

## 12.6 当前真实落地状态总结

把实现态压缩成一句话：

> SwarmMind 当前已经完成了 `agent_profile_id` 的 planning-to-execution 贯通、完成了 `agent_backed` 这一受控 agent runtime strategy 的落地、并完成了第一版 handoff 事件与 policy enforcement，但 handoff 仍然只是 strategy 内部的受控切换，而不是完整的 orchestrator-managed delegation tree。

## 12.7 下一阶段不再是“是否做”，而是“怎么把 handoff 提升为平台对象”

基于当前实现态，下一步真正要推进的已经不是：

1. 要不要有 `agent_profile_id`
2. 要不要有 `agent_backed`
3. 要不要记录 handoff 事件

而是：

1. 如何把 handoff 从 `task.constraints.handoff_requests` 提升为正式平台对象
2. 如何让 orchestrator 对 delegation request 做审批、落库、调度和回放
3. 如何形成真正的 delegation tree，而不只是 strategy 内的 profile 切换