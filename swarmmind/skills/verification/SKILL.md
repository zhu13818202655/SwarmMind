---
name: verification
description: 适用于根据验收标准检查结果、汇总证据并形成验证结论的技能。
---

# Verification Skill

## 适用场景

- 需要核对执行结果是否满足 acceptance criteria。
- 需要基于已有 artifacts 或输出形成验证结论。

## 使用要求

1. 先读取依赖子任务的产出或 artifact。
2. 按 acceptance criteria 逐项判断是否通过。
3. 对每条结论附上简短证据说明。
4. 结论必须明确：通过或失败。

## 输出原则

- 不要把“命令退出成功”等同于“需求通过”。
- 关注证据、约束和验收条件是否一致。