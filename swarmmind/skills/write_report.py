"""Write Report Skill - Research, outline, and write reports."""

from typing import Any
from swarmmind.skills.base import Skill, SkillResult


class WriteReportSkill(Skill):
    """Skill for writing reports."""

    name = "write_report"
    description = "Research a topic and write a comprehensive report"

    def __init__(self, search_tool=None, file_tool=None):
        super().__init__()
        self._search_tool = search_tool
        self._file_tool = file_tool

    def get_parameters_schema(self) -> dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The report topic",
                },
                "output_path": {
                    "type": "string",
                    "description": "Where to save the report",
                },
                "style": {
                    "type": "string",
                    "enum": ["formal", "casual", "technical"],
                    "default": "formal",
                    "description": "Report style",
                },
            },
            "required": ["topic"],
        }

    async def execute(self, **kwargs) -> SkillResult:
        """Execute the skill."""
        topic = kwargs.get("topic", "")
        output_path = kwargs.get("output_path", "report.md")
        style = kwargs.get("style", "formal")

        if not topic:
            return SkillResult(success=False, error="Topic is required")

        try:
            # Step 1: Research
            research_results = ""
            if self._search_tool:
                search_result = await self._search_tool(query=f"{topic} overview")
                research_results = str(search_result)

            # Step 2: Write report
            report_content = self._generate_report(topic, research_results, style)

            # Step 3: Save
            if self._file_tool:
                await self._file_tool(path=output_path, content=report_content)

            return SkillResult(
                success=True,
                output={
                    "topic": topic,
                    "path": output_path,
                    "preview": report_content[:500],
                },
                metadata={"steps": ["research", "write", "save"]},
            )

        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def _generate_report(self, topic: str, research: str, style: str) -> str:
        """Generate report content."""
        if style == "formal":
            header = f"# {topic.title()}\n\n"
            intro = f"## Introduction\n\nThis report provides a comprehensive overview of {topic}.\n\n"
            body = f"## Research Findings\n\n{research[:2000]}\n\n"
            conclusion = f"## Conclusion\n\nThis report has covered the key aspects of {topic}.\n"
        else:
            header = f"# {topic.title()}\n\n"
            intro = f"## Overview\n\nLet's talk about {topic}.\n\n"
            body = f"## What We Found\n\n{research[:2000]}\n\n"
            conclusion = "## Wrapping Up\n\nThat's the gist of it!\n"

        return header + intro + body + conclusion
