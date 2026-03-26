"""Review prompt templates."""

from __future__ import annotations

from swarmmind.prompt_template.base import PromptTemplate


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