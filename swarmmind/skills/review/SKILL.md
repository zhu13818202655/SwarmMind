---
name: review
description: 适用于基于验证证据做 accept、rework、escalate 决策的审核技能。
---

# Review Skill

## 适用场景

- 需要对验证结论做最终审核。
- 需要决定是接受、返工还是升级处理。

## 使用要求

1. 先读取验证结果和相关证据。
2. 如果证据充分且满足验收标准，给出 `accept`。
3. 如果存在可修复问题，给出 `rework`，并说明要修什么。
4. 如果问题超出当前执行范围，给出 `escalate`。

## 输出原则

- 决策必须清晰单一。
- rationale 要直接对应证据，不要给空泛评价。