# Plan Agent Output Schema is Out of Sync with Runtime Expectations
- Input
```markdown
Given the input, produce a plan JSON with schema:
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

Rules:
1) Subtasks must be minimal, executable, and verifiable.
2) Dependencies must be acyclic.
3) Include verification subtasks when task requests testing/validation.
4) Prefer fewer subtasks for simple goals, richer DAG for complex goals.
5) Ensure each subtask has concrete acceptance criteria.
6) Use `agent_profile_id` only when a subtask needs an explicit execution profile; otherwise omit it or set null.
7) `agent_profile_id` must come from the available profile list and should be role-compatible with the subtask.

Input:
- Goal: 做一个基于多agent产品的研究报告
- Constraints JSON: {}
- Preferred Profile: py-basic
- Preferred Strategy: build_app
- Available Agent Profiles JSON: [{"id": "planner-default", "role": "planner", "default_strategy": "task_planning", "allow_handoff": false}, {"id": "coder-default", "role": "coder", "default_strategy": "build_app", "allow_handoff": false}, {"id": "executor-default", "role": "executor", "default_strategy": "build_app", "allow_handoff": false}, {"id": "tester-default", "role": "tester", "default_strategy": "verification", "allow_handoff": false}, {"id": "reviewer-default", "role": "reviewer", "default_strategy": "review", "allow_handoff": false}, {"id": "researcher-default", "role": "researcher", "default_strategy": "research", "allow_handoff": false}, {"id": "writer-default", "role": "writer", "default_strategy": "write_report", "allow_handoff": false}, {"id": "agent-backed-default", "role": "executor", "default_strategy": "agent_backed", "allow_handoff": false}]
```

- Output
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

## Error Record

### Summary

The current planner prompt is semantically out of sync with the actual runtime schema and execution constraints. As a result, the LLM can produce plan JSON that looks structurally valid but is partially invalid or misleading for the SwarmMind runtime.

### Observed bad output characteristics

For the input goal `做一个基于多agent产品的研究报告`, the planner-generated plan showed several issues:

1. It emitted `required_tool_groups` values such as `http`, which are no longer valid runtime enums.
2. It emitted a `writer-default` profile together with role `reviewer`, which is incompatible.
3. It used `write_report` with role `reviewer`, even though that strategy should normally map to `writer`.
4. It filled `sandbox_profile` with empty strings instead of a valid value or `null`.
5. It overused `agent_profile_id` even though the prompt says it should be omitted unless explicitly needed.

### Root causes

#### 1. Prompt schema is stale

The prompt still declares these restricted enums:

- `role`: `planner|coder|tester|reviewer|researcher`
- `required_tool_groups`: `project_read|project_write|sandbox_exec|artifact_read|http`

But the actual runtime has evolved. The real enums now include additional roles and tool groups such as:

- roles: `writer`, `executor`
- tool groups: `web_search`, `browser_read`, `memory_lookup`, `task_admin`, `mail`, `presentation`

That mismatch directly invites invalid plans.

#### 2. Prompt does not encode compatibility rules strongly enough

The planner is asked to output:

- `role`
- `preferred_strategy`
- `agent_profile_id`
- `required_tool_groups`

But the prompt does not explicitly state that these must be mutually compatible.

The runtime, however, assumes compatibility. If they conflict, the runtime silently normalizes or falls back instead of preserving the model's original intent.

#### 3. Prompt has no valid example output

The schema is non-trivial and contains multiple coupled fields. Without a canonical example, the model can produce JSON that appears syntactically correct but semantically drifts from runtime expectations.

#### 4. Runtime normalization is too forgiving and too implicit

Current planner post-processing does this:

1. Invalid tool groups are silently dropped.
2. If no valid tool groups remain, role defaults are applied.
3. Incompatible `agent_profile_id` values are silently resolved to role-compatible defaults.
4. Empty `sandbox_profile` falls back to task-level default.

This prevents crashes, but it also hides prompt quality problems and makes debugging harder.

### Why this is a real problem

This is not just a prompt-style issue. It has execution consequences:

1. The LLM may intend one execution path, but runtime silently runs another.
2. Tool groups can be under-specified or wrong for the selected strategy.
3. Role/profile mismatches make plans less interpretable and less auditable.
4. Planner quality appears better than it actually is because invalid outputs are auto-corrected later.

---

## Solution Proposal

The fix should be done in three layers: prompt alignment, output validation, and runtime normalization transparency.

### Layer 1: Align the prompt with the real runtime schema

Update the planner prompt so that its schema exactly matches the runtime enums.

#### Recommended prompt changes

Replace the stale role and tool-group enums with the real runtime set:

- `role`: `planner|coder|tester|reviewer|researcher|writer|executor`
- `required_tool_groups`: `project_read|project_write|web_search|browser_read|sandbox_exec|artifact_read|memory_lookup|task_admin|mail|presentation`

Also constrain `preferred_strategy` to known runtime strategies:

- `task_planning|research|build_app|verification|review|write_report|agent_backed`

#### Add hard compatibility rules

Add rules such as:

1. `role`, `preferred_strategy`, and `agent_profile_id` must be compatible.
2. Use only enum values listed in the schema.
3. Do not emit empty strings for optional fields; use `null` or omit.
4. For `write_report`, prefer role `writer`.
5. For `research`, prefer `web_search`, `browser_read`, and `project_read`.
6. Use `agent_profile_id` only when the task explicitly requires a profile override.

#### Add one canonical example output

Add a small example with:

1. `agent_profile_id: null`
2. valid `writer` usage
3. valid `research` tool groups
4. a valid `sandbox_profile` or `null`

This will reduce schema-looking-but-invalid outputs.

### Layer 2: Add explicit planner output validation before building subtasks

Introduce a validation/normalization layer between `_extract_json_payload()` and `_build_subtasks_from_plan()`.

#### What the validator should check

1. Role must be a valid runtime role.
2. Strategy must be a known runtime strategy.
3. Tool groups must be valid runtime tool groups.
4. `agent_profile_id` must exist and be compatible with role.
5. Empty string values should become `null`.
6. Strategy-role-profile combinations should either:
  - be rejected, or
  - be normalized with a recorded warning.

#### What the validator should return

Prefer returning:

1. normalized plan JSON
2. validation warnings list
3. optional hard errors for unrecoverable conflicts

This makes it possible to inspect how much repair was needed.

### Layer 3: Make runtime normalization transparent

Keep runtime fallback behavior, but make it visible.

#### Recommended changes

When planner output is repaired, store structured metadata such as:

1. `planner_validation_warnings`
2. `normalized_tool_groups`
3. `resolved_agent_profile_id`
4. `original_agent_profile_id`
5. `original_role`
6. `original_preferred_strategy`

This preserves debuggability and lets the team evaluate planner quality over time.

---

## Practical rollout plan

### Step 1

Update `swarmmind/prompt_template/planner_task_decomposition_v1.md` so it matches runtime enums and includes one valid example.

### Step 2

Add a planner output validator/normalizer before `_build_subtasks_from_plan()`.

### Step 3

Emit warnings into subtask metadata when normalization changes the LLM output.

### Step 4

Add tests for these cases:

1. invalid tool group like `http`
2. incompatible `writer-default` + `reviewer`
3. empty-string `sandbox_profile`
4. omitted vs explicit `agent_profile_id`

---

## Short conclusion

The current problem is not that the LLM cannot produce a plan. The real problem is that the planner prompt and the runtime contract have drifted apart.

The correct fix is:

1. update the prompt to match reality,
2. validate the model output explicitly,
3. keep runtime fallback behavior but expose normalization instead of hiding it.
