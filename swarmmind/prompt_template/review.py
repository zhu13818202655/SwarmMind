"""Review prompt templates."""

from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


VALIDATION_AGENT_SYSTEM_PROMPT = PromptTemplate(
    name="validation_agent_system_v1",
    template="""You are a precise verification and review agent.
Return strict JSON only and make decisions solely from the provided evidence.""",
)


VERIFICATION_RESULT_PROMPT = PromptTemplate(
    name="verification_result_prompt_v1",
    template="""You are executing a verification subtask.

Task Goal: {{ task_goal }}
Subtask Name: {{ subtask_name }}
Subtask Description: {{ subtask_description }}
Acceptance Criteria: {{ acceptance_criteria_json }}
Dependency Summary JSON: {{ dependency_summary_json }}
Artifact Summary JSON: {{ artifact_summary_json }}

Return strict JSON with this schema:
{
  "passed": true,
  "summary": "string",
  "criteria_results": [
    {
      "criterion": "string",
      "passed": true,
      "evidence": "string"
    }
  ],
  "evidence_subtask_ids": ["string"],
  "artifact_ids": ["string"]
}

Rules:
1. Return JSON only.
2. Each acceptance criterion must appear exactly once in `criteria_results`.
3. Evidence must cite dependency or artifact facts from the input.
4. Mark `passed=false` if evidence is insufficient.""",
)


REVIEW_DECISION_PROMPT = PromptTemplate(
    name="review_decision_prompt_v1",
    template="""You are executing a review subtask.

Task Goal: {{ task_goal }}
Subtask Name: {{ subtask_name }}
Subtask Description: {{ subtask_description }}
Acceptance Criteria: {{ acceptance_criteria_json }}
Dependency Summary JSON: {{ dependency_summary_json }}
Artifact Summary JSON: {{ artifact_summary_json }}

Return strict JSON with this schema:
{
  "decision": "accept|rework|escalate",
  "summary": "string",
  "rationale": "string",
  "follow_up_actions": ["string"]
}

Rules:
1. Return JSON only.
2. Choose `accept` only when the evidence clearly satisfies the acceptance criteria.
3. Choose `rework` when targeted follow-up work could resolve the issues.
4. Choose `escalate` when the evidence is too ambiguous or blocked for an automated decision.""",
)


REVIEW_SUBTASK_VERIFICATION_PROMPT = PromptTemplate(
    name="review_subtask_verification_v1",
    template="""Review the subtask result.

Subtask: {{ subtask_name }}
Description: {{ subtask_description }}
Acceptance Criteria: {{ acceptance_criteria_json }}
Execution Output Preview: {{ stdout_preview }}
Artifacts: {{ artifact_list_json }}

Output format:
- Verdict: pass/fail
- Criteria Check:
  - [ ] item 1
  - [ ] item 2
- Evidence:
- Risks:
- Next Action:""",
)