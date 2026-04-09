from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from swarmmind.app.container import build_container
from swarmmind.config import SwarmMindConfig
from swarmmind.models.capability import AgentRole
from swarmmind.models.run import Run
from swarmmind.models.task import SubTask, Task
from swarmmind.tools.builtin.search import SearchResponse, SearchResultItem, SearchTool, search


@pytest.mark.asyncio
async def test_builtin_web_search_accepts_time_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeSearchTool:
        async def search(
            self,
            query: str,
            max_results: int = 5,
            start_date: str | None = None,
            end_date: str | None = None,
            topic: str | None = None,
            include_domains: list[str] | None = None,
            exclude_domains: list[str] | None = None,
        ) -> str:
            captured["query"] = query
            captured["max_results"] = max_results
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            captured["topic"] = topic
            captured["include_domains"] = include_domains
            captured["exclude_domains"] = exclude_domains
            return "ok"

    monkeypatch.setattr(SearchTool, "from_settings", classmethod(lambda cls, provider=None: FakeSearchTool()))

    result = await search(
        "gold price",
        max_results=3,
        provider="tavily",
        start_date="2025-02-09",
        end_date="2025-12-29",
        topic="finance",
        include_domains=["gold.org"],
        exclude_domains=["example.com"],
    )

    assert result == "ok"
    assert captured == {
        "query": "gold price",
        "max_results": 3,
        "start_date": "2025-02-09",
        "end_date": "2025-12-29",
        "topic": "finance",
        "include_domains": ["gold.org"],
        "exclude_domains": ["example.com"],
    }


@pytest.mark.asyncio
async def test_execution_runner_web_search_wrapper_passes_time_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SwarmMindConfig(sandbox={"provider": "local"})
    container = await build_container(settings)
    runner = container.execution_runner
    task = Task(id="task-web-search", goal="Research recent gold price changes", metadata={"tenant_id": "local"})
    run = Run(id="run-web-search", task_id=task.id, session_id="session-web-search")
    subtask = SubTask(
        id="subtask-web-search",
        task_id=task.id,
        name="research-recent-prices",
        description="Search for recent gold price updates.",
        role=AgentRole.RESEARCHER,
        metadata={"selected_tools": ["web_search"]},
    )
    captured: dict[str, object] = {}

    async def fake_execute(tool_name: str, **kwargs):
        captured["tool_name"] = tool_name
        captured["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(runner._tool_registry, "execute", fake_execute)

    tool_functions = runner._build_agent_tool_functions(task, run, subtask)
    web_search_tool = next(tool for tool in tool_functions if getattr(tool, "__name__", "") == "web_search")

    result = await web_search_tool(
        query="recent gold price",
        max_results=4,
        provider="tavily",
        start_date="2025-02-09",
        end_date="2025-12-29",
        topic="finance",
        include_domains=["gold.org", "kitco.com"],
        exclude_domains=["spam.example"],
    )

    assert result == "ok"
    assert captured == {
        "tool_name": "web_search",
        "kwargs": {
            "query": "recent gold price",
            "max_results": 4,
            "provider": "tavily",
            "start_date": "2025-02-09",
            "end_date": "2025-12-29",
            "topic": "finance",
            "include_domains": ["gold.org", "kitco.com"],
            "exclude_domains": ["spam.example"],
        },
    }


@pytest.mark.asyncio
async def test_search_tool_tavily_maps_filters_to_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "results": [
                    {
                        "title": "Gold price update",
                        "url": "https://gold.org/update",
                        "content": "Recent finance update",
                    }
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())

    tool = SearchTool(provider="tavily", api_key="tvly-test")
    result = await tool.search(
        "recent gold price",
        max_results=4,
        start_date="2026-04-01",
        end_date="2026-04-09",
        topic="finance",
        include_domains=["gold.org", "kitco.com"],
        exclude_domains=["spam.example"],
    )

    assert "Gold price update" in result
    assert captured["json"] == {
        "api_key": "tvly-test",
        "query": "recent gold price",
        "max_results": 4,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
        "start_date": "2026-04-01",
        "end_date": "2026-04-09",
        "topic": "finance",
        "include_domains": ["gold.org", "kitco.com"],
        "exclude_domains": ["spam.example"],
    }


@pytest.mark.asyncio
async def test_search_tool_tavily_uses_explicit_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"results": []}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())

    tool = SearchTool(provider="tavily", api_key="tvly-test")
    await tool.search(
        "recent gold price",
        max_results=2,
        start_date="2025-02-09",
        end_date="2025-12-29",
    )

    assert captured["json"] == {
        "api_key": "tvly-test",
        "query": "recent gold price",
        "max_results": 2,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
        "start_date": "2025-02-09",
        "end_date": "2025-12-29",
    }