"""IntentParser prompt templates for the FlyReport domain.

Split into a concise system prompt (role + hard constraints) and a user
prompt template (input/output schema, rules, few-shot) that is rendered
with Jinja variables at call time.
"""

from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate

# ---------------------------------------------------------------------------
# System prompt — keep short; only identity + hard output constraint
# ---------------------------------------------------------------------------

INTENT_PARSE_SYSTEM_PROMPT = PromptTemplate(
    name="飞行服务平台飞行统计报告-意图分析-system",
    template="""\
你是飞行报告智能体的**意图解析节点**。
你的唯一职责：把用户提供的输入信息，转换成严格符合用户消息中所定义 schema 的 JSON。
只输出 JSON，不要解释、不要寒暄、不要使用 Markdown 代码块。""",
)

# ---------------------------------------------------------------------------
# User prompt — rendered by IntentParser._compose_parse_prompt()
#
# Available Jinja variables:
#   user_text            — 用户原始消息
#   now_iso              — 当前上海时间 ISO8601
#   dept_names_json      — 可选部门列表 JSON 数组
#   preference_json      — 用户偏好 JSON（预留）
#   existing_filter_json — 当前已解析的 FilterSpec JSON（多轮追加）
#   recent_turns_json    — 最近对话轮次 JSON 数组（多轮上下文）
# ---------------------------------------------------------------------------

INTENT_PARSE_USER_PROMPT = PromptTemplate(
    name="飞行服务平台飞行统计报告-意图分析-user",
    template="""\
请根据以下输入，输出一个严格符合输出 schema 的 JSON 对象。

## 输入

- 用户消息：{{ user_text }}
- 当前时间（上海时间，Asia/Shanghai，UTC+08:00）：{{ now_iso }}
- 可选的部门列表：{{ dept_names_json }}
- 用户偏好：{{ preference_json }}
- 当前已解析过滤条件（多轮追加场景）：{{ existing_filter_json }}
- 最近对话轮次：{{ recent_turns_json }}

## 输出 schema（严格遵守）

```json
{
  "period": {
    "kind": "weekly|monthly|custom",
    "start": "ISO8601(Asia/Shanghai)",
    "end": "ISO8601(Asia/Shanghai)"
  },
  "dept_names": ["部门A", "部门B"],
  "missing": [],
  "conflicts": []
}
```

要求：
- 必须输出完整 JSON 对象。
- 未提及且无法可靠确定的字段，使用 schema 默认值。
- `period` 无法可靠确定时输出 `null`，并把缺失原因写入 `missing`。

## 规则

1. 不要回答用户、不要解释、不要寒暄；**只输出 JSON**。
2. 所有时间字段与时间计算统一使用上海时间（Asia/Shanghai，UTC+08:00），并在输出中使用带 `+08:00` 偏移的 ISO8601 时间。
3. 相对时间必须解析成闭区间：开始时间为 `00:00:00+08:00`，结束时间为 `23:59:59+08:00`。
4. 如果用户查询中涉及部门维度，你需要在部门列表中匹配出用户可能的目标部门；如果无法确定具体部门但明确有部门维度，则输出 `dept_names: []` 并在 `missing` 里写明"部门目标不明确"。
5. 如果用户查询中没有涉及部门维度，则 `dept_names` 字段输出空列表（而不是省略），并且不写入 `missing`。
6. `missing` 用于"信息不足，无法唯一确定"的情况；`conflicts` 用于"用户要求之间互相冲突、超出支持范围、或明显不合法"的情况。
7. 对 `missing`，只记录缺什么，不要写解决方案；对 `conflicts`，只记录冲突点，不要写长解释。
8. 下列情况写入 `missing`：
   - 模糊时间没有可落地边界，如"最近飞行报告""前段时间"。
   - 指代不清，如"那个部门""上次那个飞手"。
   - 用户声明要按部门/飞手查看，但没有给出目标对象。
   - 用户说"对比一下"，但没有说明对比对象。
9. 下列情况写入 `conflicts`：
   - 请求未来时间报告。
   - 同一句里给出互斥周期，且无法同时成立，如"本周月报""上周和下个月的同一份报告"。
   - 用户要求超出 schema 支持范围的时间表达，且不能保守落地，如"从明天开始最近 7 天"。
10. 如果用户同时提供了可解析信息和冲突信息，保留可解析部分，但仍要写入 `conflicts`。
11. 如果提供了"当前已解析过滤条件"，说明这是多轮对话追加场景，请在已有条件基础上合并用户本次新增/修改的部分。

## few-shot

示例 1（总体周报，相对周期）：
- user: "这周的飞行报告"
- now（Asia/Shanghai）: "2026-04-15T09:00:00+08:00"
- 输出：
```json
{
  "period": {
    "kind": "weekly",
    "start": "2026-04-13T00:00:00+08:00",
    "end": "2026-04-19T23:59:59+08:00"
  },
  "dept_names": [],
  "missing": [],
  "conflicts": []
}
```

示例 2（总体月报，相对周期）：
- user: "本月部门A和B飞行报告"
- now（Asia/Shanghai）: "2026-04-21T10:30:00+08:00"
- 输出：
```json
{
  "period": {
    "kind": "monthly",
    "start": "2026-04-01T00:00:00+08:00",
    "end": "2026-04-30T23:59:59+08:00"
  },
  "dept_names": ["部门A", "部门B"],
  "missing": [],
  "conflicts": []
}
```

示例 3（自定义最近 N 天）：
- user: "最近7天A部门飞行报告"
- now（Asia/Shanghai）: "2026-04-21T10:30:00+08:00"
- 输出：
```json
{
  "period": {
    "kind": "custom",
    "start": "2026-04-15T00:00:00+08:00",
    "end": "2026-04-21T23:59:59+08:00"
  },
  "dept_names": ["部门A"],
  "missing": [],
  "conflicts": []
}
```

示例 4（时间模糊，应标记 missing）：
- user: "最近的飞行报告"
- now（Asia/Shanghai）: "2026-04-21T10:30:00+08:00"
- 输出：
```json
{
  "period": null,
  "dept_names": [],
  "missing": ["period"],
  "conflicts": []
}
```

示例 5（维度已指定但目标缺失，应标记 missing）：
- user: "看下上周那个部门的飞行报告"
- now（Asia/Shanghai）: "2026-04-21T10:30:00+08:00"
- 输出：
```json
{
  "period": {
    "kind": "weekly",
    "start": "2026-04-13T00:00:00+08:00",
    "end": "2026-04-19T23:59:59+08:00"
  },
  "dept_names": [],
  "missing": ["department_target"],
  "conflicts": []
}
```

示例 6（未来时间，应标记 conflicts）：
- user: "给我下个月的飞行报告"
- now（Asia/Shanghai）: "2026-04-21T10:30:00+08:00"
- 输出：
```json
{
  "period": {
    "kind": "monthly",
    "start": "2026-05-01T00:00:00+08:00",
    "end": "2026-05-31T23:59:59+08:00"
  },
  "dept_names": [],
  "missing": [],
  "conflicts": ["未来时间不支持生成报告"]
}
```

示例 7（互斥周期，应标记 conflicts）：
- user: "本周月报发我一下"
- now（Asia/Shanghai）: "2026-04-21T10:30:00+08:00"
- 输出：
```json
{
  "period": null,
  "dept_names": [],
  "missing": [],
  "conflicts": ["时间周期存在互斥"]
}
```
""",
)


__all__ = ["INTENT_PARSE_SYSTEM_PROMPT", "INTENT_PARSE_USER_PROMPT"]
