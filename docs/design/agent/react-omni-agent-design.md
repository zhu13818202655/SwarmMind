# ReActAgent 与 SwarmMind OmniAgent 设计说明

## 1. 文档目的

本文以 AgentScope 官方 `ReActAgent` 为基准，说明四部分内容：

1. ReAct 模式本身的信息逻辑与典型适用场景。
2. AgentScope 对 `ReActAgent` 的实现能力、边界与使用方式。
3. SwarmMind 在 `omni_agent.py`、`factory.py`、`omni_runner.py` 中对 `ReActAgent` 的扩充点。
4. 四者组合后的端到端调用链，以及在本仓库中的推荐使用方式。

这里的“四个文件”分别是：

- AgentScope 官方实现：`agentscope/agent/_react_agent.py`
- SwarmMind 扩展：`swarmmind/agents/omni_agent.py`
- SwarmMind 扩展：`swarmmind/agents/factory.py`
- SwarmMind 扩展：`swarmmind/agents/omni_runner.py`

---

## 2. ReAct 作为基准：它解决什么问题

ReAct 的核心思想不是“直接回答”，而是把智能体运行拆成两个循环动作：

- Reason：模型先基于当前上下文做推理，决定下一步应该直接回答，还是调用工具。
- Act：如果模型选择了工具，就执行工具，把工具结果再写回上下文，然后继续下一轮推理。

这比单轮问答更适合处理以下任务：

- 需要查资料、读文件、执行命令、调用 API 的任务。
- 需要分多步验证的任务，例如“写代码并运行测试”。
- 需要根据中间结果修正策略的任务，例如“先查日志，再决定修哪个模块”。

从设计角度看，ReAct 解决的是“语言推理”和“外部行动”之间的闭环问题。

---

## 3. ReAct 的信息逻辑

如果只看逻辑主线，ReAct 的一次运行可以抽象成下面这条链路：

1. 接收用户消息。
2. 把消息写入短期记忆。
3. 在推理前补充额外上下文。
4. 用 system prompt + memory 组装模型输入。
5. 模型输出两类内容之一：
   - 直接文本回复
   - 工具调用请求
6. 如果是工具调用，则执行工具，并把结果写回 memory。
7. 再次进入推理阶段。
8. 在满足退出条件时返回最终结果。

其中第 3 步常见的补充上下文包括：

- 长期记忆检索结果
- 知识库检索结果
- 计划系统的 hint
- 上一轮工具返回的结构化结果

因此，ReAct 不是一个“单纯会调工具的聊天模型”，而是一个围绕 memory 组织的循环执行器。

### 3.1 ReAct 的最小闭环

最小闭环可以写成：

`用户输入 -> 写入 memory -> LLM 推理 -> 触发工具 -> 工具结果写回 memory -> LLM 再推理 -> 输出结果`

这条链路有几个关键点：

- memory 是状态载体，负责保存对话、工具调用和工具结果。
- toolkit 是动作边界，负责规定代理“能做什么”。
- sys_prompt 是策略边界，负责规定代理“应该怎么做”。
- max_iters 是安全边界，防止无限循环。

### 3.2 ReAct 适合的场景

适合：

- 编码代理
- 测试代理
- 运维排障代理
- 文档检索和汇总代理
- 需要根据中间结果迭代决策的工作流代理

不太适合：

- 完全固定流程、无需模型判断的纯工作流
- 极强确定性要求、且每步都能静态编排的任务
- 需要复杂并发图调度的任务，除非外层再包一层 orchestration

也就是说，ReAct 更像“单个智能体的执行内核”，而不是完整的多智能体调度系统。

---

## 4. AgentScope 的 `ReActAgent`：能力范围

AgentScope 的 `ReActAgent` 是一个通用的、可扩展的 ReAct 运行时。它在官方实现里已经覆盖了单代理场景下比较完整的一组基础能力。

### 4.1 核心能力

结合当前仓库内依赖版本的实现，`ReActAgent` 具备以下能力：

1. 短期记忆管理
   - 默认使用 `InMemoryMemory`。
   - 所有输入消息、推理输出、工具结果都会持续写入 memory。

2. 工具调用
   - 通过 `Toolkit` 暴露工具给模型。
   - 支持模型在推理阶段返回 `tool_use` 块，然后进入 `_acting()` 执行。

3. 并行工具调用
   - 当模型一次返回多个工具调用时，可选择并行执行。
   - 适合多个独立查询类工具一起跑。

4. 结构化输出
   - 可在 `reply()` 中传入 `structured_model`。
   - 内部通过 `generate_response` 工具生成并校验结构化结果。

5. 长期记忆接入
   - 支持在 reply 前检索长期记忆。
   - 也支持把 `record_to_memory` / `retrieve_from_memory` 作为工具交给代理自控。

6. RAG 接入
   - 支持知识库检索。
   - 支持在检索前对 query 重写。

7. Plan notebook 接入
   - 可以把规划工具挂到 toolkit 中。
   - 能把 planning hint 插入当前推理上下文。

8. 记忆压缩
   - 提供 `CompressionConfig`。
   - 当上下文过长时，自动总结旧 memory，保留最近消息。

9. 中断处理和 TTS 支持
   - 支持 interrupted 流程。
   - 支持 TTS 输出链路。

### 4.2 官方实现的运行主线

从实现上看，AgentScope 的 `ReActAgent.reply()` 可以概括为：

1. `memory.add(msg)` 记录输入。
2. `_retrieve_from_long_term_memory(msg)` 注入长期记忆。
3. `_retrieve_from_knowledge(msg)` 注入知识库结果。
4. 若要求结构化输出，则临时注册 `generate_response` 工具。
5. 进入循环：
   - `_compress_memory_if_needed()`
   - `_reasoning()`
   - `_acting()`
   - 检查是否结束
6. 如果循环次数耗尽，则调用 `_summarizing()` 兜底。
7. 若启用静态长期记忆写回，则在最后记录 memory。

这说明 `ReActAgent` 的本质是一个“围绕 memory 和 toolkit 组织起来的循环控制器”。

### 4.3 AgentScope `ReActAgent` 的边界

它很强，但边界也比较清楚。

1. 它是单代理执行内核，不负责多代理编排。
   - 多角色协作、任务拆解、依赖调度，应该由外层系统负责。

2. 它能调工具，但不天然理解“工具权限模型”。
   - 哪些工具危险、哪些只能在沙箱执行、哪些需要审计，这不是官方 `ReActAgent` 的强约束重点。

3. 它支持 memory 和 knowledge，但不自带你项目需要的审计语义。
   - 例如 task_id、sandbox_id、agent_profile 这些业务上下文，需要你自己补。

4. 它支持 toolkit，但不负责你项目里的工具分组、角色权限、profile 约束。

5. 它可以执行工具，但不等于具备运行时治理能力。
   - 比如 host tools 和 sandbox 的切换、fallback chain、工具 contract，不是它原生的重点。

6. 它是 agent runtime，不是旧系统兼容层。
   - 如果上层已经有既有 runner 接口，还需要自行封装适配器。

### 4.4 AgentScope `ReActAgent` 的典型使用方法

典型使用方式是：

1. 准备模型。
2. 准备 formatter。
3. 准备 toolkit，并注册工具函数。
4. 视需要挂入 memory、long-term memory、knowledge、plan notebook。
5. 实例化 `ReActAgent`。
6. 调用 `await agent.reply(...)` 或 `await agent(...)`。

适合的接入方式通常是：

- 作为单个功能代理直接使用。
- 作为更大系统中的一个执行内核，由外层 orchestration 调用。

---

## 5. 为什么 SwarmMind 还要再包三层

SwarmMind 的目标不是只做一个“会调工具的代理”，而是要做一个可约束、可审计、可运行时治理、可兼容现有调度接口的通用智能体执行层。

因此，SwarmMind 在 AgentScope `ReActAgent` 之上补了三层职责：

1. `omni_agent.py`
   - 给 ReAct 增加能力模型、运行时策略和审计事件。

2. `factory.py`
   - 负责按配置、角色、profile、execution policy 去构建 agent。

3. `omni_runner.py`
   - 把统一请求对象转成可执行 agent，并对外提供兼容旧接口的运行入口。

这三层不是重复造轮子，而是在官方 ReAct 核心外补齐工程化能力。

---

## 6. `omni_agent.py`：对 `ReActAgent` 的能力扩充

这个文件做了两件事：

1. 定义一组“能力模型”，把 agent 的权限、技能、运行时、审计策略结构化。
2. 在运行时层面继承 `ReActAgent`，补发事件、补工具执行元信息。

### 6.1 扩充了什么能力

#### 6.1.1 CapabilityBundle：把“代理能做什么”显式化

官方 `ReActAgent` 的能力主要体现在传入的参数里，比如 toolkit、memory、knowledge。SwarmMind 进一步把这些能力整理成 `CapabilityBundle`，其中包含：

- `role`
- `prompt_spec`
- `allowed_tool_groups`
- `allowed_tool_names`
- `resolved_tool_functions`
- `resolved_skills`
- `allowed_skill_scripts`
- `runtime_policy`
- `memory_policy`
- `handoff_policy`
- `audit_policy`
- `tool_contracts`
- `default_tool_runtime`

这一步的价值在于：

- 能把“提示词层能力”和“执行层能力”分开建模。
- 能把“允许什么”和“实际装配了什么”分开建模。
- 能把“工具名字”提升为带 contract 的治理对象。

#### 6.1.2 CapabilityResolver：从配置输入解析成可运行能力集

`CapabilityResolver.resolve()` 会根据：

- 角色
- system prompt
- tool functions
- skill profiles
- agent profile
- execution profile

解析出最终 `CapabilityBundle`。

这里最关键的补充是三类解析：

1. 运行时策略解析
   - 默认走 host tools 还是 sandbox。
   - 是否允许 runtime switch。
   - fallback chain 是什么。

2. 技能解析
   - 把 skill profile 转成 prompt 可见 catalog 和 detail。
   - 也把 skill 对应的脚本、资源路径显式化。

3. 工具 contract 解析
   - 默认 runtime
   - allowed runtimes
   - 是否只读
   - 是否要求审计
   - 是否危险
   - 是否 sandbox only

这已经超出官方 ReAct 的抽象范围，属于工程治理层能力。

#### 6.1.3 OmniAgent：增加可审计事件流

`OmniAgent` 直接继承 `ReActAgent`，但在两个关键点上增强了运行时可观测性：

1. 重写 `reply()`
   - 在运行前发 `agent.started`
   - 失败时发 `agent.failed`
   - 完成后发 `agent.completed`

2. 重写 `_acting()`
   - 工具开始前发 `tool.started`
   - 工具失败时发 `tool.failed`
   - 工具完成后发 `tool.completed`
   - 当执行的是 `run_skill_script` 时额外发 `skill.executed`

3. 追加运行时选择事件
   - `runtime.selected`
   - `tool.selected`
   - `skill.resolved`

这意味着 SwarmMind 的 `OmniAgent` 不只是“能跑”，而是“每一步能被追踪”。

### 6.2 这个文件的能力边界

`omni_agent.py` 主要负责单个代理实例的能力解析和执行增强，它不负责：

- 构建模型客户端
- 从项目配置装配 agent
- 对外提供统一 request/result 接口
- 多步任务调度

这些分别交给 `factory.py` 和 `omni_runner.py`，以及更外层 orchestration。

### 6.3 适用场景

适合：

- 需要审计事件的代理执行
- 需要 host/sandbox 运行时切换的代理
- 需要按 profile、角色、工具 contract 严格约束的代理
- 需要把 skill catalog 暴露给 prompt 的代理

不适合单独拿来做：

- 最简单的临时脚本式 agent；那种场景官方 `ReActAgent` 已经够用

### 6.4 如何使用

正常不建议手工直接 new `OmniAgent`，更推荐通过 `AgentFactory` 统一构建，因为 `CapabilityBundle`、toolkit、model、formatter 的组合关系已经比较复杂。

如果确实要直接使用，至少需要准备：

- 一个解析好的 `CapabilityBundle`
- 模型客户端
- formatter
- toolkit
- memory
- 可选事件发布器

---

## 7. `factory.py`：对代理构建阶段的扩充

如果说 `omni_agent.py` 解决的是“agent 运行时长什么样”，那 `factory.py` 解决的就是“agent 在创建时该怎么装起来”。

### 7.1 这个文件的核心职责

`AgentFactory` 是一个装配器，负责把分散的配置和约束整理成一个可执行 agent。它主要做以下事情：

1. 创建模型客户端
   - 使用 `AuditedOpenAIChatModel`
   - 统一传入模型名、base_url、temperature、max_tokens

2. 创建 formatter
   - 当前使用 `OpenAIChatFormatter`

3. 创建 memory
   - 当前默认 `InMemoryMemory`

4. 构建 ToolRegistry 和 Toolkit
   - 注册 builtin tools
   - 注册额外传入的 tools
   - 按 tool group 和 tool name 过滤
   - 按 runtime_kind 过滤

5. 解析 skill profiles
   - 归一化 profile 名称
   - 解析 skill entry
   - 注册到 AgentScope toolkit
   - 把 skill catalog / details 附着到 toolkit

6. 解析角色和执行约束
   - 从 config、AgentProfile、ExecutionProfile 中决定实际 equipped tool groups
   - 决定 active tool names
   - 决定 effective skill profiles

7. 构造 `CapabilityBundle`
   - 通过 `CapabilityResolver.resolve()` 完成

8. 最终创建 `OmniAgent`

### 7.2 它扩充了哪些官方没有显式处理的能力

#### 7.2.1 角色 / Profile / ExecutionProfile 三层合并

官方 `ReActAgent` 并不关心：

- 当前 agent 是哪个业务角色
- 当前任务是否临时限制了工具范围
- 当前 profile 是否要求特定 sandbox profile

`AgentFactory` 把这些合并成一个清晰的装配过程，优先级大致是：

- 显式传入的 execution profile
- agent profile
- factory config 默认值

#### 7.2.2 ToolRegistry 驱动的工具分组装配

这里不是简单地“把函数注册进 toolkit”，而是先进入 `ToolRegistry`，再根据：

- `active_groups`
- `active_tool_names`
- `runtime_kind`
- `strict_tool_names`

构建最终 toolkit。

这使得工具装配变成可策略化过程，而不是手工拼接。

#### 7.2.3 Skill 与 Tool 的联合装配

`factory.py` 同时处理：

- prompt 层的 skill catalog
- 运行时可见的 skill package
- tool 函数本身

这对于“技能说明”和“实际可执行动作”需要一起受控的系统非常关键。

### 7.3 这个文件的边界

`factory.py` 负责创建 agent，但不负责执行 agent，也不负责返回统一结果结构。它的边界是：

- 输入：配置、tools、profile、execution profile
- 输出：一个已经装配好的 `OmniAgent`

它不负责：

- 执行请求生命周期事件
- 结果标准化
- 异常转结果对象

这些由 `omni_runner.py` 负责。

### 7.4 适用场景

适合：

- 你的系统里有多个角色代理
- 不同任务有不同工具和技能白名单
- 需要根据 execution profile 切换 runtime 和 sandbox profile
- 不希望业务代码里手工拼装 model / toolkit / capability bundle

### 7.5 如何使用

最常见使用方式有三种：

1. `create_main_agent()`
   - 用默认系统配置创建主代理。

2. `create_profile_agent(profile, ...)`
   - 按 `AgentProfile` 创建受约束代理。

3. `create_agent(...)`
   - 较通用的底层入口，适合需要显式指定 prompt、tools、skill_profiles 的地方。

对于新代码，优先推荐：

- 面向业务角色时使用 `create_profile_agent()`
- 面向通用默认执行时使用 `create_main_agent()`

---

## 8. `omni_runner.py`：对执行入口和兼容层的扩充

如果说 `factory.py` 负责“造 agent”，那么 `omni_runner.py` 负责“把一个统一请求跑起来并收口结果”。

### 8.1 核心职责

这个文件提供三个关键抽象：

1. `OmniAgentRequest`
   - 定义一次统一 agent step 所需的输入。

2. `OmniAgentResult`
   - 定义一次执行后的标准输出。

3. `OmniAgentRunner`
   - 把 request 转换为 agent 实例，执行后返回 result。

### 8.2 它扩充了什么能力

#### 8.2.1 统一请求对象

`OmniAgentRequest` 把以下输入收口在一起：

- `agent_name`
- `prompt`
- `system_prompt`
- `step_kind`
- `tool_functions`
- `skill_profiles`
- `agent_profile`
- `execution_profile`

这使上游调度系统不用关心底层 agent 具体如何构造。

#### 8.2.2 统一结果对象

`OmniAgentResult` 统一了：

- `status`
- `content`
- `reason`
- `error`
- `tool_names`
- `skill_profiles`
- `agent_name`
- `agent_profile_id`
- `model_name`

这解决的是“底层 agent 的输出对象不稳定，上游不好消费”的问题。

#### 8.2.3 兼容旧 runner API

文件头部已经写明：这是一个 compatibility runner。也就是说，它的存在意义之一，是在不要求上层全面改造的情况下，把新 `OmniAgent` 接入原有执行体系。

#### 8.2.4 Step 级事件发布

在执行前后会发布：

- `agent.step.started`
- `agent.step.completed`
- `agent.step.failed`

相比 `OmniAgent` 内部更细粒度的 tool / runtime / skill 事件，`OmniAgentRunner` 提供的是“step 生命周期”这一层的事件。

### 8.3 这个文件的边界

`omni_runner.py` 是单次 step 执行入口，不负责：

- 多个 step 的 DAG 调度
- sandbox 生命周期管理
- 跨 step 的任务状态机
- 更高层的任务编排

它面向的是“执行一个已经决议好的 agent step”。

### 8.4 适用场景

适合：

- orchestration 层已经决定了当前该跑哪个 agent step
- 需要统一的 request/result 结构
- 需要对旧系统保留兼容接口
- 需要把 step 级事件送到上层事件总线

### 8.5 如何使用

标准方式是：

1. 组装一个 `OmniAgentRequest`
2. 创建 `OmniAgentRunner`
3. 调用 `await runner.run(request, publisher=...)`
4. 使用返回的 `OmniAgentResult`

一般上层不会直接与 `AgentFactory` 或 `OmniAgent` 打交道，而是通过 runner 收口。

---

## 9. 四者组合后的完整信息流

在 SwarmMind 中，这四部分组合后的信息流可以写成：

`上层 orchestration -> OmniAgentRunner -> AgentFactory -> CapabilityResolver -> OmniAgent(ReActAgent) -> Toolkit/Memory/Model`

再细化一点：

1. 上层任务系统构造 `OmniAgentRequest`
2. `OmniAgentRunner.run()` 根据 request 构造 `AgentConfig`
3. `AgentFactory` 按 profile、execution profile、tool groups、skill profiles 装配 agent
4. `CapabilityResolver` 解析出最终 `CapabilityBundle`
5. `OmniAgent` 继承 `ReActAgent` 执行标准 ReAct 循环
6. 在 reply 和 tool act 过程中补发审计事件
7. `OmniAgentRunner` 把结果标准化成 `OmniAgentResult`

因此，四个文件分工可以简写成：

- `ReActAgent`：执行内核
- `OmniAgent`：能力治理 + 审计增强
- `AgentFactory`：构造装配器
- `OmniAgentRunner`：统一执行入口

---

## 10. 能力范围与边界对比

| 维度 | AgentScope ReActAgent | SwarmMind OmniAgent | AgentFactory | OmniAgentRunner |
| --- | --- | --- | --- | --- |
| 核心定位 | 单代理 ReAct 执行内核 | 增强型通用代理运行时 | 代理装配器 | 兼容执行入口 |
| memory/knowledge/plan | 支持 | 继承支持 | 间接装配 | 不负责 |
| 工具调用 | 支持 | 支持并加审计 | 负责装配 | 不直接执行工具 |
| 结构化输出 | 支持 | 继承支持 | 不负责 | 透传结果 |
| 技能目录注册 | 原生支持 prompt 注入 | 增加 skill 解析语义 | 负责注册与过滤 | 不负责 |
| 运行时治理 | 弱 | 强 | 中 | 弱 |
| 工具 contract | 无显式强模型 | 有 | 负责接入 | 不负责 |
| 角色/profile 约束 | 无内建业务模型 | 通过 bundle 支持 | 强 | 透传 |
| 事件审计 | 有限 | 强 | 无执行期事件 | step 级事件 |
| 旧接口兼容 | 无 | 无 | 无 | 有 |

---

## 11. 推荐使用方式

### 11.1 什么时候只用官方 `ReActAgent`

当你只是要快速做一个单代理实验时，官方 `ReActAgent` 足够：

- 简单问答 + 工具调用
- 小规模研发验证
- 不需要复杂权限与运行时治理

### 11.2 什么时候用 `OmniAgent + AgentFactory`

当你已经进入工程化阶段，并且需要以下能力时，应该用 SwarmMind 的扩展层：

- 角色化 agent
- profile 约束
- skill profile 选择
- runtime policy
- tool contract
- 审计事件

### 11.3 什么时候用 `OmniAgentRunner`

当你面对的是任务系统或 orchestration 层，而不是单个 agent 实验时，优先通过 `OmniAgentRunner` 调用。原因是：

- 输入输出结构稳定
- 兼容老接口
- 便于挂 step 生命周期事件
- 上层不需要理解 agent 内部装配细节

---

## 12. 一个简单的理解方式

可以把这四个文件理解成四层：

1. `ReActAgent`
   - “怎么思考并调用工具”

2. `OmniAgent`
   - “这个代理被允许做什么，执行时如何审计”

3. `AgentFactory`
   - “如何把一个代理正确装出来”

4. `OmniAgentRunner`
   - “如何让上层系统以统一方式调用这个代理”

这也是 SwarmMind 当前通用智能体设计相对 AgentScope 官方基线的主要增量所在。
