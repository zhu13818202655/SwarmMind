---
type: todo
date: 2026-03-23
topic: skill-system-remaining-work
status: open
owner: copilot
---

# Skill System Remaining Work TODO

> 这份文档只保留 `docs/todo/20260323/skill-system-refactor-todo.md` 与 `docs/todo/20260323/skill-execution-agent-followup-todo.md` 中截至当前代码状态**仍未完成**的事项。
>
> 结论先说：
>
> 1. P0 已完成：目录迁移与命名收口已落地。
> 2. follow-up A 已完成：`SkillExecutionService` 与 formal tools 已接入。
> 3. follow-up B 已完成：`skill.script.*` 事件、artifact 落库、replay 链路已接入。
> 4. 目前主剩余项集中在：skill 适配 agent 使用、skill 质量体系、少量 catalog/governance/validation 收尾。

---

## 1. 当前确认仍未完成的主线

按影响范围排序，当前仍未完成的工作有四块：

1. **skill 适配 agent 使用**
2. **skill 质量体系与评测**
3. **catalog / metadata / validate 的剩余增强项**
4. **orchestration 对 skill 使用边界的显式控制**

---

## 2. P0: 目录迁移与命名收口（已完成）

这部分已经完成，当前目录职责已经收口到目标语义。

### 2.1 目标

让目录名和职责语义最终一致：

1. `swarmmind/skills/` 只表示具体 skill package
2. `swarmmind/execution_strategies/` 只表示 runtime execution strategy
3. `swarmmind/skill_system/` 继续只承载 skill 基础设施代码

### 2.2 完成后的现状

当前实际目录已经变成：

1. `swarmmind/skills/` 里放的是具体 skill package
2. `swarmmind/execution_strategies/` 里放的是 runtime execution strategy 代码
3. `swarmmind/skill_system/` 继续承载 skill 基础设施代码

### 2.3 已完成事项

1. 已新建并接入 `swarmmind/execution_strategies/`
2. 已将 runtime strategy Python 文件迁移到 `swarmmind/execution_strategies/`
3. 已更新运行时代码中的 Python import
4. 已将具体 skill package 从 `swarmmind/agent_skills/` 迁移到 `swarmmind/skills/`
5. 已更新 `get_skill_package_root()` 与 agent skill root 逻辑，去掉 `agent_skills` 作为主路径的依赖
6. 本文档已同步 P0 状态

### 2.4 验收标准

1. `swarmmind/skills/` 下不再出现 runtime strategy Python 代码
2. `swarmmind/agent_skills/` 不再作为主目录使用
3. skill package / skill system / execution strategy 三层目录语义完全一致

---

## 3. P1: skill 适配 agent 使用

这是 follow-up todo 里工作流 C，对应主 refactor todo 的 Phase 6。

### 3.1 当前已完成到什么程度

已完成：

1. AgentFactory 可以注册 native skill 目录
2. toolkit 上已经挂了 compact / expanded catalog 数据
3. formal tools 已存在：
   - `list_skill_scripts`
   - `get_skill_details`
   - `run_skill_script`

但仍缺的不是“能不能调用”，而是“agent 的 skill 使用边界是否被显式建模”。

### 3.2 当前仍缺失的能力

1. 缺少 `AgentProfile` 概念
2. 缺少 `skill_mode` 配置
3. 缺少 `tool_policy` / `custom_prompt` 等 profile 级边界字段
4. agent 还没有统一入口显式消费 skill catalog / details
5. orchestration 还不能显式指定某个 subtask：
   - 可否使用 skill
   - 可使用哪些 skill
   - 可否执行 scripts

### 3.3 待做事项

1. 设计 `AgentProfile` 模型
2. 为 `AgentProfile` 增加：
   - `skills`
   - `skill_mode`
   - `tool_policy`
   - `custom_prompt`
3. 让 `AgentFactory` 支持从 profile 构建 skill 能力边界
4. 为 agent 侧增加显式 skill 消费入口，而不是只把数据挂在 toolkit 私有字段上
5. 明确 planner / coder / tester / reviewer / researcher 的默认 skill 能力边界
6. 让 orchestration 能按 subtask 明确下发 skill 使用范围

### 3.4 验收标准

1. skill 使用边界由 profile / policy / orchestration 共同控制
2. agent 不再只依赖目录 prompt 注入来“隐式会用 skill”
3. skill execution 能力可按角色、profile、subtask 做精细授权

---

## 4. P1: orchestration 对 skill 的显式控制

这部分和上面的 agent 适配有关，但更偏运行时主链，因此单独列出。

### 4.1 当前问题

虽然 `run_skill_script` 已接入 ToolRegistry，但 orchestration 还没有把它当成一个受控运行时能力来调度。

当前缺口包括：

1. subtask metadata 里没有标准化的 skill 使用策略字段
2. execution profile 里没有明确的 skill allowlist / script allowlist
3. planner / coordinator / execution runner 没有统一约束“什么时候允许脚本执行”

### 4.2 待做事项

1. 在 execution profile 或等价结构中增加 skill 使用边界字段
2. 让 planner 可以显式规划“本 subtask 需要依赖哪个 skill”
3. 让 coordinator 在分配时把 skill 能力约束写入 subtask execution context
4. 让 execution runner 只在显式允许时注册或暴露 `run_skill_script`
5. 明确 script execution 的 profile 级和 subtask 级开关

### 4.3 验收标准

1. `run_skill_script` 不再是默认全暴露能力
2. orchestration 可以控制 skill 的发现、读取、执行三个阶段边界

---

## 5. P2: skill 质量体系与评测

这是主 refactor todo 的 Phase 7，当前完全没开始。

### 5.1 待做事项

1. 制定统一的 `SKILL.md` 编写模板
2. 建立 skill lint / validate 流程
3. 建立 eval dataset
4. 建立 trigger evaluation
5. 建立 benchmark / human review 流程
6. 明确 references / scripts / assets 的编写规范

### 5.2 当前明确还缺的实现

1. 没有 skill benchmark 目录或数据
2. 没有 skill regression 测试机制
3. 没有 skill 编写模板或 review 清单
4. 没有“新增一个 skill 后如何验证质量”的标准流程

### 5.3 验收标准

1. 新 skill 增加时有统一模板
2. skill 触发效果和内容质量可以做回归验证
3. skill 改动可以通过 benchmark 或 review 流程判断是否回退

---

## 6. P2: catalog / metadata / validate 的剩余增强项

这些能力有基础版，但还没有做完整收口。

### 6.1 catalog 剩余项

当前已完成：

1. compact catalog
2. expanded catalog
3. toolkit 上暴露 catalog 数据

仍待完成：

1. 按 role / profile 的更细粒度 catalog 过滤
2. 更显式的 agent 侧 catalog 消费路径
3. orchestration 侧 catalog 消费接口

### 6.2 metadata 治理剩余项

当前已完成：

1. `version / license / compatibility / source_url / source_type`
2. `disabled / allowed_tools / required_env / required_bins`
3. 基础可用性过滤

仍待完成：

1. 更完整的 install lifecycle 管理
2. 更完整的来源管理和诊断接口
3. enable / disable / invalid 之外更明确的安装态切换流程

### 6.3 validate 剩余项

当前代码已有 validator 模块，但缺少显式入口。

仍待完成：

1. 增加 `skills validate <path>` 或等价 CLI/API 入口
2. 增加面向仓库使用者的 validation 入口说明

---

## 7. 当前不再列为未完成项的内容

下面这些在新文档中不再算未完成项：

1. 目录迁移与命名收口：已完成
2. `SkillExecutionService`：已完成
3. formal tools：已完成
4. `skill.script.started / completed / failed`：已完成
5. artifact 落库与 replay 事件链：已完成

说明：

1. P0 已完成
2. follow-up todo 的工作流 A 已完成
3. follow-up todo 的工作流 B 已完成
4. 这三部分后续只需在老文档中补状态同步，不再算新的剩余工作

---

## 8. 推荐实施顺序

建议接下来按下面顺序继续：

1. 先做 AgentProfile / skill_mode / tool_policy
2. 再做 orchestration 对 skill 的显式控制
3. 然后补 skill validate 入口与 catalog 收口
4. 最后补 skill 质量体系与评测

原因：

1. profile / policy 是 skill 真正进入 agent 主链的前提
2. orchestration 边界稳定后再补 validate / catalog 收口更合理
3. 质量体系可以在运行时边界稳定后再补

---

## 9. Definition of Done

当以下条件同时满足时，可以认为这轮剩余工作完成：

1. `swarmmind/skills/` 已变成真实 skill package 根目录
2. `swarmmind/execution_strategies/` 已替代当前 runtime `skills/` 目录
3. `AgentProfile` / `skill_mode` / `tool_policy` 已进入 agent 构建和运行时边界
4. orchestration 能显式控制 skill 的发现、读取和脚本执行边界
5. skill validate 入口可用
6. skill 质量体系至少具备模板、lint/validate、基础 eval 流程