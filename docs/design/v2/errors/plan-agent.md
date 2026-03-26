# 计划 Agent 输出 Schema 与运行时预期不同步
- 输入
```markdown
给定输入，产出符合以下 schema 的计划 JSON：
{
  "subtasks": [
    {
      "name": "string-kebab-case",
      "description": "string",
      "agent_profile_id": "string|null",
      "role": "planner|coder|tester|reviewer|researcher",
      "preferred_strategy": "string",
      "required_tool_groups": ["project_read|project_write|sandbox_exec|artifact_read|http"],
      "sandbox_profile": "string",
      "acceptance_criteria": ["string"],
      "dependencies": ["subtask-name"]
    }
  ]
}

规则：
1) 子任务必须足够小、可执行、可验证。
2) 依赖关系必须无环。
3) 当任务要求测试或校验时，必须包含验证类子任务。
4) 简单目标尽量减少子任务数量，复杂目标可以使用更丰富的 DAG。
5) 每个子任务都必须有明确、具体的验收标准。
6) 仅当子任务确实需要显式执行配置时才使用 `agent_profile_id`；否则省略或设为 null。
7) `agent_profile_id` 必须来自可用 profile 列表，并且要与子任务角色兼容。

输入：
- Goal: 做一个基于多agent产品的研究报告
- Constraints JSON: {}
- Preferred Profile: py-basic
- Preferred Strategy: build_app
- Available Agent Profiles JSON: [{"id": "planner-default", "role": "planner", "default_strategy": "task_planning", "allow_handoff": false}, {"id": "coder-default", "role": "coder", "default_strategy": "build_app", "allow_handoff": false}, {"id": "executor-default", "role": "executor", "default_strategy": "build_app", "allow_handoff": false}, {"id": "tester-default", "role": "tester", "default_strategy": "verification", "allow_handoff": false}, {"id": "reviewer-default", "role": "reviewer", "default_strategy": "review", "allow_handoff": false}, {"id": "researcher-default", "role": "researcher", "default_strategy": "research", "allow_handoff": false}, {"id": "writer-default", "role": "writer", "default_strategy": "write_report", "allow_handoff": false}, {"id": "agent-backed-default", "role": "executor", "default_strategy": "agent_backed", "allow_handoff": false}]
```

- 输出
```json
{
  "subtasks": [
    {
      "name": "research-multi-agent-landscape",
      "description": "调研多agent产品的定义、技术架构、代表性产品与应用场景，收集一手与二手资料。",
      "agent_profile_id": "researcher-default",
      "role": "researcher",
      "preferred_strategy": "research",
      "required_tool_groups": ["http", "artifact_read"],
      "sandbox_profile": "",
      "acceptance_criteria": [
        "列出不少于5个主流多agent产品或框架",
        "总结多agent产品的核心特征与技术路线",
        "给出清晰的资料来源或参考链接"
      ],
      "dependencies": []
    },
    {
      "name": "outline-research-report",
      "description": "基于调研结果，设计多agent产品研究报告的大纲与章节结构。",
      "agent_profile_id": "planner-default",
      "role": "planner",
      "preferred_strategy": "task_planning",
      "required_tool_groups": ["artifact_read"],
      "sandbox_profile": "",
      "acceptance_criteria": [
        "形成完整的报告大纲，包含引言、技术分析、案例分析与总结",
        "每个章节有明确研究重点说明"
      ],
      "dependencies": ["research-multi-agent-landscape"]
    },
    {
      "name": "write-multi-agent-report",
      "description": "根据大纲撰写完整的多agent产品研究报告正文。",
      "agent_profile_id": "writer-default",
      "role": "reviewer",
      "preferred_strategy": "write_report",
      "required_tool_groups": ["project_write", "artifact_read"],
      "sandbox_profile": "",
      "acceptance_criteria": [
        "报告内容结构完整，与大纲一致",
        "文字逻辑清晰、专业术语使用准确",
        "字数达到研究报告基本要求（如不少于3000字）"
      ],
      "dependencies": ["outline-research-report"]
    },
    {
      "name": "review-and-validate-report",
      "description": "对研究报告进行事实、逻辑与表达层面的审阅和验证。",
      "agent_profile_id": "reviewer-default",
      "role": "reviewer",
      "preferred_strategy": "review",
      "required_tool_groups": ["artifact_read"],
      "sandbox_profile": "",
      "acceptance_criteria": [
        "指出并修正明显事实或逻辑错误",
        "给出整体质量评价与改进建议",
        "确认报告可作为正式研究输出"
      ],
      "dependencies": ["write-multi-agent-report"]
    }
  ]
}
```

---

## 错误记录

### 概要

当前 planner prompt 在语义上已经与真实运行时 schema 和执行约束脱节。因此，LLM 可以生成看起来结构合法、但对 SwarmMind 运行时而言部分无效或具有误导性的计划 JSON。

### 已观察到的问题输出特征

对于输入目标 `做一个基于多agent产品的研究报告`，planner 生成的计划存在以下问题：

1. 它输出了 `http` 这样的 `required_tool_groups` 值，但该值已经不是当前运行时认可的枚举值。
2. 它输出了 `writer-default` profile，却配上了 `reviewer` 角色，两者不兼容。
3. 它将 `write_report` 与 `reviewer` 角色组合使用，但这个策略通常应当对应 `writer`。
4. 它将 `sandbox_profile` 填成空字符串，而不是合法值或 `null`。
5. 它过度使用了 `agent_profile_id`，而 prompt 本身又要求仅在显式需要时才使用。

### 根因分析

#### 1. Prompt schema 已经过时

当前 prompt 仍然声明以下受限枚举：

- `role`: `planner|coder|tester|reviewer|researcher`
- `required_tool_groups`: `project_read|project_write|sandbox_exec|artifact_read|http`

但真实运行时已经演进，实际枚举现在还包含更多角色和工具组，例如：

- 角色：`writer`、`executor`
- 工具组：`web_search`、`browser_read`、`memory_lookup`、`task_admin`、`mail`、`presentation`

这种不一致会直接诱导模型生成无效计划。

#### 2. Prompt 没有足够明确地编码兼容性规则

planner 被要求输出以下字段：

- `role`
- `preferred_strategy`
- `agent_profile_id`
- `required_tool_groups`

但 prompt 没有明确说明这些字段之间必须彼此兼容。

而运行时实际上默认它们是兼容的。一旦冲突，运行时会静默做归一化或回退，而不是保留模型的原始意图。

#### 3. Prompt 缺少一个合法的输出示例

这个 schema 并不简单，包含多个相互耦合的字段。如果没有规范示例，模型很容易生成语法正确、但语义上偏离运行时预期的 JSON。

#### 4. 运行时归一化过于宽松且过于隐式

当前 planner 后处理逻辑会执行以下操作：

1. 静默丢弃无效工具组。
2. 如果没有剩余合法工具组，则套用角色默认值。
3. 对不兼容的 `agent_profile_id` 静默解析为与角色兼容的默认 profile。
4. 空字符串 `sandbox_profile` 会回退到任务级默认值。

这些行为可以避免运行时报错，但也掩盖了 prompt 质量问题，并让调试变得更困难。

### 为什么这是一个真实问题

这不只是 prompt 写法问题，它会直接影响执行结果：

1. LLM 可能表达的是一种执行路径，但运行时静默执行的是另一种。
2. 所选策略对应的工具组可能不完整，或者干脆就是错误的。
3. 角色与 profile 不匹配，会让计划更难理解、更难审计。
4. 因为后续被自动纠正，planner 的质量看起来会比真实情况更好。

---

## 解决方案建议

修复应分三层推进：prompt 对齐、输出校验、运行时归一化透明化。

### 第一层：让 prompt 与真实运行时 schema 对齐

更新 planner prompt，使其 schema 与运行时真实枚举完全一致。

#### 建议的 prompt 修改

将已经过时的角色与工具组枚举替换为当前真实运行时集合：

- `role`: `planner|coder|tester|reviewer|researcher|writer|executor`
- `required_tool_groups`: `project_read|project_write|web_search|browser_read|sandbox_exec|artifact_read|memory_lookup|task_admin|mail|presentation`

同时将 `preferred_strategy` 限制为运行时已知策略：

- `task_planning|research|build_app|verification|review|write_report|agent_backed`

#### 增加硬性兼容性规则

加入如下规则：

1. `role`、`preferred_strategy` 和 `agent_profile_id` 必须相互兼容。
2. 只能使用 schema 中列出的枚举值。
3. 可选字段不得输出空字符串，应使用 `null` 或直接省略。
4. 对于 `write_report`，优先使用 `writer` 角色。
5. 对于 `research`，优先使用 `web_search`、`browser_read` 和 `project_read`。
6. 只有在任务明确要求 profile 覆盖时才使用 `agent_profile_id`。

#### 增加一个规范示例输出

添加一个小而完整的合法示例，至少包含：

1. `agent_profile_id: null`
2. 合法的 `writer` 用法
3. 合法的 `research` 工具组
4. 合法的 `sandbox_profile` 或 `null`

这会显著减少“看起来像合法 schema、实际上语义无效”的输出。

### 第二层：在构建子任务前增加显式校验与归一化

在 `_extract_json_payload()` 与 `_build_subtasks_from_plan()` 之间加入一层校验/归一化逻辑。

#### 校验器应检查的内容

1. `role` 是否为运行时合法角色。
2. `preferred_strategy` 是否为运行时已知策略。
3. `required_tool_groups` 是否全部为运行时合法工具组。
4. `agent_profile_id` 是否存在且与角色兼容。
5. 空字符串值是否应统一转换为 `null`。
6. `strategy-role-profile` 组合遇到冲突时，应当：
   - 直接拒绝，或
   - 在记录 warning 的前提下做归一化。

#### 校验器建议返回内容

建议返回：

1. 归一化后的计划 JSON
2. 校验 warning 列表
3. 对不可恢复冲突给出可选 hard error

这样可以清楚看出输出到底被修复了多少。

### 第三层：让运行时归一化变得可见

保留运行时 fallback 行为，但不要继续隐式处理。

#### 建议增加的记录信息

当 planner 输出被修复时，保存结构化元数据，例如：

1. `planner_validation_warnings`
2. `normalized_tool_groups`
3. `resolved_agent_profile_id`
4. `original_agent_profile_id`
5. `original_role`
6. `original_preferred_strategy`

这样既保留运行弹性，也保留可调试性，并能长期评估 planner 质量。

---

## 实际落地计划

### 第 1 步

更新 `swarmmind/prompt_template/task_decomposer.py`，使其与运行时枚举一致，并加入一个合法示例。

### 第 2 步

在 `_build_subtasks_from_plan()` 之前加入 planner 输出校验/归一化逻辑。

### 第 3 步

当归一化修改了 LLM 原始输出时，将 warning 写入子任务 metadata。

### 第 4 步

为以下场景补充测试：

1. 非法工具组，例如 `http`
2. 不兼容组合，例如 `writer-default` + `reviewer`
3. 空字符串 `sandbox_profile`
4. `agent_profile_id` 的省略与显式赋值差异

---

## 简短结论

当前问题不是 LLM 不会生成计划，而是 planner prompt 与运行时契约已经发生漂移。

正确修复方式是：

1. 先让 prompt 与现实对齐；
2. 对模型输出做显式校验；
3. 保留运行时 fallback，但把归一化过程暴露出来，而不是继续隐藏。
