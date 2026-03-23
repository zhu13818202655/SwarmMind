---
name: task_planning
description: 适用于把用户目标拆分成结构化子任务、依赖关系、角色和验收标准的规划技能。
---

# Task Planning Skill

## 适用场景

- 把复杂任务拆解成可执行子任务。
- 需要明确依赖顺序、角色、策略偏好和验收标准。

## 使用要求

1. 优先输出结构化任务分解。
2. 每个子任务都要有：
   - 名称
   - 描述
   - role
   - preferred_strategy
   - required_tool_groups
   - acceptance_criteria
   - dependencies
3. 依赖只引用前面已经定义的子任务。
4. 如果用户目标包含测试、验证、审核语义，要显式规划 verify / review 节点。

## 输出原则

- 尽量避免过度拆分。
- 子任务应该能被独立调度和验证。