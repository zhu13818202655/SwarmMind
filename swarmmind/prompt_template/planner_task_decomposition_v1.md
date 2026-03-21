Given the input, produce a plan JSON with schema:
{
  "subtasks": [
    {
      "name": "string-kebab-case",
      "description": "string",
      "role": "planner|coder|tester|reviewer|researcher",
      "preferred_skill": "string",
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

Input:
- Goal: {{task_goal}}
- Constraints JSON: {{constraints_json}}
- Preferred Profile: {{profile}}
- Preferred Skill: {{preferred_skill}}
