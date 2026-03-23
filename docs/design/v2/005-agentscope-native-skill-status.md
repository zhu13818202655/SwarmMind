# SwarmMind Skill 现状与 AgentScope 原生 Skill 对照

> 目的：澄清当前项目里“skill”一词的两层含义，并基于 AgentScope 源码判断：哪些自定义 skill 相关实现可以删除，哪些不能直接删除。

关联文件：

- `swarmmind/agents/factory.py`
- `swarmmind/agent_skills/*/SKILL.md`
- `swarmmind/orchestration/execution_runner.py`
- `swarmmind/skills/execution_strategy_registry.py`
- `swarmmind/skills/strategy.py`
- `swarmmind/models/capability.py`
- `/.venv/lib/python3.12/site-packages/agentscope/tool/_toolkit.py`
- `/.venv/lib/python3.12/site-packages/agentscope/agent/_react_agent.py`

---

## 1. 先说结论

当前仓库里与 skill 相关的能力实际上分成两层：

1. **AgentScope 原生 agent skill**
2. **SwarmMind 自己的运行时策略注册器**

这两层不是同一个概念，也不能简单互相替代。

更准确地说：

1. **AgentScope 原生 skill 已经适合承担“Agent 知识增强 / 目录化能力包”这件事。**
2. **SwarmMind 自定义的 `SkillRegistry` 不应该继续叫 skill，它本质上是运行时策略分发器。**
3. **如果继续保留自定义这层，应该改名；如果未来能把运行时彻底改造成 Agent 自主读取 skill + 调工具执行，再考虑删除。**

---

## 2. AgentScope 原生 skill 到底是什么

从 AgentScope 源码看，原生 skill 的核心实现都在 `Toolkit` 内。

源码证据：

### 2.1 `Toolkit.register_agent_skill()` 的行为

`agentscope/tool/_toolkit.py` 中 `register_agent_skill()` 做的事情是：

1. 检查给定目录是否存在。
2. 检查顶层是否有 `SKILL.md`。
3. 读取 `SKILL.md` 的 YAML Front Matter。
4. 提取 `name` 和 `description`。
5. 把它存到 `self.skills` 中。

它**没有**做这些事：

1. 没有把 skill 变成可调用函数。
2. 没有把 skill 变成 Python 回调执行器。
3. 没有构造某种 runtime dispatch graph。
4. 没有自动读取目录里的其他文件并执行。

也就是说，**原生 skill 是目录元信息注册，不是执行器注册。**

### 2.2 `Toolkit.get_agent_skill_prompt()` 的行为

源码里 `get_agent_skill_prompt()` 会把已注册的 skill 格式化成系统提示词附加段。

默认指令非常关键，它本质上是在告诉 Agent：

- 这些 skill 是一些目录化的说明、脚本和资源；
- 如果要使用 skill，必须认真阅读对应目录里的 `SKILL.md`。

这说明 AgentScope 的设计假设是：

1. **skill 是一种“让 Agent 知道某个目录可用”的机制。**
2. **真正的使用动作要靠 Agent 自己去读文件 / 调工具。**

### 2.3 `ReActAgent.sys_prompt` 的行为

`agentscope/agent/_react_agent.py` 中 `sys_prompt` 属性会把：

1. 原始系统提示词 `_sys_prompt`
2. `toolkit.get_agent_skill_prompt()` 返回的 skill 提示

拼接起来。

所以原生 skill 的实际作用链路是：

`register_agent_skill` -> `get_agent_skill_prompt` -> `ReActAgent.sys_prompt`

这是一条**提示词增强链**，不是**代码执行链**。

---

## 3. 这对 SwarmMind 意味着什么

## 3.1 哪些东西适合用 AgentScope 原生 skill

以下能力适合用原生 skill：

1. 规划指导词
2. 代码实现规范
3. verify / review 的审查规则
4. 报告撰写模板
5. 研究步骤和证据组织规范

这些都属于：

- 面向 Agent 的知识包
- 可以目录化
- 通过 `SKILL.md` 指导 Agent 行为

这一层当前已经开始落地：

- `swarmmind/agent_skills/build_app/SKILL.md`
- `swarmmind/agent_skills/task_planning/SKILL.md`
- `swarmmind/agent_skills/verification/SKILL.md`
- `swarmmind/agent_skills/review/SKILL.md`
- `swarmmind/agent_skills/research/SKILL.md`
- `swarmmind/agent_skills/write_report/SKILL.md`

## 3.2 哪些东西不能直接用原生 skill 替代

以下能力不能直接被原生 skill 取代：

1. 根据 subtask role 选择执行路径
2. 在 Python 里决定某个 subtask 应该走 sandbox 还是 verification
3. 在事件驱动主链里分发执行策略
4. 在运行时返回结构化执行结果对象
5. 在不依赖 LLM 自主决策的情况下，强制按流程推进执行

原因很简单：

**这些都是 runtime orchestration 问题，不是 prompt augmentation 问题。**

AgentScope 原生 skill 只负责告诉 Agent：

“这里有一个目录技能，你如果要用，请读 `SKILL.md`。”

它并不负责：

- 把一个 subtask 绑定到某条 Python 执行分支；
- 保证系统一定走某条执行器逻辑；
- 把返回结果变成结构化运行时结果对象 / `VerificationResult` / `ReviewDecision`；
- 与 sandbox 生命周期、artifact 收集、run 收敛逻辑耦合。

---

## 4. 当前仓库里有问题的地方

## 4.1 `SkillRegistry` 这个命名已经误导

在本轮清理之前，`swarmmind/skills/registry.py` 中的 `SkillRegistry` 做的不是 AgentScope 原生 skill 那件事。

它做的是：

1. 注册 Python skill 对象
2. 根据名字取出 skill
3. 调用 `execute()`
4. 返回结构化运行时结果对象

这本质上是一个：

**运行时策略 / 执行回调注册器**

而不是 AgentScope 所说的：

**目录技能注册器**

所以继续沿用 `SkillRegistry` 名字会产生两个问题：

1. 代码阅读时混淆 AgentScope native skill 与项目 runtime strategy。
2. 后续如果继续扩展 AgentScope skill，会越来越难判断“这里的 skill 是哪一层”。

## 4.2 `swarmmind/skills/base.py` 里曾经还有一份重复的 `SkillRegistry`

这是当前实现的另一个问题：

在清理前，`skills/base.py` 里有一份 `SkillRegistry`，`skills/registry.py` 里又有一份更完整的 `SkillRegistry`。

这不是能力增强，而是重复定义。

如果不清理，后续维护时很容易出现：

1. 一处改了，另一处没改。
2. import 指向不同实现。

---

## 5. 是否可以删除项目里所有“自定义 skill”

答案是：**现在不能一刀切删除。**

更细一点说：

### 5.1 可以逐步删除的部分

以下部分有希望被原生 AgentScope skill 替代：

1. 面向 Agent 的技能说明文案
2. “做规划时怎么拆任务”这类指导模板
3. “做 review 时怎么判 accept/rework/escalate”这类规则模板
4. 一些只服务于 LLM 提示增强的 skill 类

### 5.2 当前还不能删除的部分

以下部分暂时不能直接删除：

1. 运行时根据 subtask 选择执行策略的注册层
2. 执行结果统一包装为结构化结果的 Python 层
3. 与 event bus / sandbox / artifact / replay / run 收敛紧耦合的执行代码

因为一旦删除这一层，当前系统会失去：

1. 稳定、确定性的运行时分发能力
2. 不依赖 LLM 自主发挥的执行闭环

换句话说，**如果想彻底删除这层，必须先把主链改造成“Agent 真正主导执行”的架构，而当前项目还不是这个阶段。**

---

## 6. 当前最合理的处理方案

基于 AgentScope 源码和当前仓库状态，最合理的方案是：

1. **保留 AgentScope 原生 skill，负责 Agent 知识增强。**
2. **保留项目自己的运行时执行注册器，但改名。**
3. **把“能删的自定义 skill 类”逐步收缩或废弃。**

推荐命名：

- `ExecutionStrategyRegistry`

这个名字更准确，因为它强调的是：

- runtime
- strategy dispatch

而不是 AgentScope skill。

---

## 7. 本轮落地建议

建议按以下顺序推进：

1. 把 `SkillRegistry` 改名为 `ExecutionStrategyRegistry`。
2. 去掉当时 `skills/base.py` 中重复定义的 `SkillRegistry`。
3. 将运行时基类改成 `ExecutionStrategy` / `StrategyResult`，不再继续沿用 `Skill` 这个词。
4. 后面如果要进一步收缩自定义 skill 体系，再把：
   - `BuildAppSkill`
   - `WriteReportSkill`
   - `MonitorStockSkill`
   这类未进入主链的类逐步淘汰或迁到 samples/examples。

---

## 8. 最终判断

最准确的结论是：

1. **AgentScope 原生 skill 已经适合承担 Agent 的技能知识包能力。**
2. **SwarmMind 运行时注册器不是原生 skill，应该使用 execution strategy 语义。**
3. **当前阶段不能把所有运行时 strategy 相关代码全部删除，因为 runtime dispatch 还需要 Python 层确定性控制。**
4. **正确方向不是“一刀切删除”，而是“Agent 知识增强原生化，运行时策略命名纠偏并逐步收缩”。**

---

## 9. 本轮已经完成的收缩

本轮已经完成以下清理：

1. 将自定义 `SkillRegistry` 改名为 `ExecutionStrategyRegistry`。
2. 删除当时 `skills/base.py` 中重复的注册器定义。
3. 删除未被主链使用的遗留类：
   - `BuildAppSkill`
   - `WriteReportSkill`
   - `MonitorStockSkill`
4. `swarmmind.skills` 包导出现在只保留：
   - `Skill`
   - `StrategyResult`
   - `ExecutionStrategyRegistry`
   - `CallbackStrategy`

这意味着当前仓库已经不再把这些历史类误暴露成“正式运行时能力”，主链统一收敛为：

1. AgentScope native skill 目录
2. `ExecutionStrategyRegistry`
3. `ExecutionRunner` 内置默认运行时策略

补充说明：

1. 运行时主链内部已经切到 `preferred_strategy` / `StrategyProfile`。
2. 运行时输入与内部模型统一使用 `preferred_strategy` / `StrategyProfile`。