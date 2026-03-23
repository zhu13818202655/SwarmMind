---
type: todo
date: 2026-03-23
topic: skill-execution-agent-followup
status: open
owner: copilot
---

# Skill Execution / Agent Follow-up TODO

> 这份文档承接 skill system 一期基础能力完成后的下一阶段工作，重点覆盖三条线：
>
> 1. 把 `SkillScriptExecutor` 接成正式 tool / service，让 agent 或 orchestration 能显式调用。
> 2. 给 script execution 增加完整的 audit / replay / event 发布链路。
> 3. 让 skill 真正适配 agent 使用，使 skill system 真正进入 agent 与 orchestration 运行时闭环。

---

## 1. 背景

当前已经具备的基础能力包括：

1. 本地 skill package 解析、校验、加载、注册
2. metadata 治理与可用性过滤
3. compact / expanded catalog
4. 通过 `SkillScriptExecutor` 在 sandbox 中执行已声明脚本

但目前仍有一个明显缺口：

1. script execution 还是一个底层能力对象
2. 它还没有成为 agent 或 orchestration 可以正式调用的能力接口
3. 执行结果还没有进入完整的事件、审计、replay 链路
4. skill system 还没有真正适配到 agent 的显式使用链路中

---

## 2. 总体目标

下一阶段目标是：

1. 让 skill script execution 成为正式平台能力，而不是内部 helper。
2. 让每一次 skill script 执行都有完整审计与回放痕迹。
3. 让 agent 能显式发现、读取、选择和执行 skill，而不是完全附着在现有 AgentFactory 的临时参数上。

---

## 3. 工作流 A：把 SkillScriptExecutor 接成正式 tool / service

## A.1 目标

让 agent 或 orchestration 层能够显式调用 skill script 执行，而不是只能在内部 import 一个 executor 类。

## A.2 建议设计

建议增加两层封装：

1. **service 层**
   - `SkillExecutionService`
   - 负责：
     - 装配 `SkillScriptExecutor`
     - 根据 skill name / script path 查询 skill entry
     - 应用 policy
     - 返回统一结果对象
2. **tool 层**
   - 例如 `run_skill_script`
   - 负责：
     - 给 agent 一个显式可调用的工具接口
     - 入参标准化
     - 调 service

## A.3 待做事项

1. 新建 `swarmmind/skill_system/service.py`
2. 定义 `SkillExecutionService`
3. 让 service 接入：
   - skill registry
   - sandbox manager
   - tool policy
4. 新建 tool 封装，例如：
   - `run_skill_script`
   - `list_skill_scripts`
   - `get_skill_details`
5. 明确 service 和 tool 的职责边界：
   - service 做业务逻辑
   - tool 做 agent 可调用接口

## A.4 验收标准

1. orchestration 层可以直接调用 service 执行 skill script。
2. agent 层可以通过正式 tool 调用 skill script。
3. 不需要直接 import `SkillScriptExecutor` 才能使用脚本执行能力。

---

## 4. 工作流 B：给 script execution 增加 audit / replay / event 链路

## B.1 目标

让 script execution 不只是返回 `SkillScriptExecutionResult`，而是成为可审计、可回放、可追踪的系统行为。

## B.2 建议设计

建议把 skill script execution 统一发布成事件，例如：

1. `skill.script.started`
2. `skill.script.completed`
3. `skill.script.failed`

每个事件至少携带：

1. `task_id`
2. `run_id`
3. `subtask_id`
4. `skill_name`
5. `script_path`
6. `sandbox_id`
7. `command`
8. `artifact_paths`
9. `exit_code`

## B.3 待做事项

1. 设计 skill script 事件 topic 与 payload schema
2. 在 service 层执行前后发布事件
3. 将结果写入 replay timeline
4. 将 artifact 信息纳入审计记录
5. 确保失败路径也会发出失败事件

## B.4 验收标准

1. 每次 skill script 执行都可按 run_id 检索事件链。
2. replay 中可看到 script execution 的开始、结束、失败记录。
3. 失败和成功路径都有完整事件。

---

## 5. 工作流 C：skill 适配 agent 使用

## C.1 目标

让 skill system 不只是“给现有 agent 附加 skill 目录”，而是进入 agent 的显式能力模型和执行链路。

## C.2 设计目标

这里的重点不是新增一个独立 agent，而是让现有 agent 体系真正会用 skill。

建议优先完成三件事：

1. **profile 适配**
   - agent profile 明确声明可用 skills
   - agent profile 明确声明 skill_mode
   - agent profile 明确声明 tool_policy
2. **使用路径适配**
   - agent 可以读取 compact skill catalog
   - agent 可以读取 expanded skill details
   - agent 在允许时可以调用 `run_skill_script`
3. **orchestration 适配**
   - orchestrator 可以显式指定某个 agent 是否可用 skill execution
   - orchestrator 可以控制 skill 使用边界，而不是让 agent 自由漂移

## C.3 建议落地方向

建议从已有角色出发，而不是新增角色：

1. `planner` 侧：
   - 负责决定某个子任务是否应该依赖 skill
2. `coder / executor / tester / reviewer` 侧：
   - 负责在各自边界内消费 skill
3. `AgentFactory` / `AgentProfile` 侧：
   - 负责把 skill、tool、policy 绑定成可配置能力

也就是说，当前 C 的核心不是“新增 agent”，而是：

**把 skill 从目录型 prompt 资产，推进成 agent 可以显式消费的能力对象。**

## C.4 待做事项

1. 设计 `AgentProfile` 对 skill 的显式配置字段：
   - `skills`
   - `skill_mode`
   - `tool_policy`
   - `custom_prompt`
2. 让 `AgentFactory` 从 profile 构建 skill 能力边界
3. 让 agent 侧有统一入口读取：
   - compact catalog
   - expanded details
4. 让 agent 侧在策略允许时调用 skill execution tool / service
5. 明确 planner / coder / tester / reviewer 各自的 skill 使用边界
6. 让 orchestration 能显式指定：
   - 某个 subtask 可否使用 skill
   - 可使用哪些 skill
   - 可否执行 scripts

## C.5 验收标准

1. 现有 agent 可以显式消费 skill，而不是只靠目录 prompt 注入。
2. agent 的 skill 使用边界由 profile / policy / orchestration 控制。
3. 不需要新增专门 agent，也能让 skill 真正进入 agent 使用闭环。

---

## 6. 推荐实施顺序

建议顺序如下：

1. 先做 A：tool / service 化
2. 再做 B：audit / replay / event 化
3. 最后做 C：skill 适配 agent 使用

原因：

1. 没有正式 service/tool，agent 无法稳定调用 skill execution。
2. 没有事件与回放，agent 就算能调用，也无法进入可观测闭环。
3. skill 适配 agent 使用应建立在前两者稳定后，否则只是把未稳定能力提前暴露给 agent。

---

## 7. 当前不建议做的事

这份 follow-up todo 当前不建议：

1. 直接让所有现有 agent 都能随意执行 skill scripts
2. 绕过 sandbox manager 做本地 shell 执行
3. 在 audit / replay 未接入前就把 skill execution 深度嵌进主执行链
4. 为了 skill 先急着新增一个独立 agent 角色

---

## 8. Definition of Done

当以下条件成立时，这一阶段可以视为完成：

1. skill script execution 已有正式 service 和 tool 接口。
2. 每次执行都会发布开始/结束/失败事件。
3. replay / audit 可以检索到完整 skill script 执行链。
4. 现有 agent 可以通过 profile / policy / orchestration 显式发现、读取和执行 skill。