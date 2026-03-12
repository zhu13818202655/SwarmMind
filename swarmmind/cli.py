"""CLI entry point for SwarmMind."""

import asyncio
import json
import sys
from typing import Optional

import click
from swarmmind.models.config import SwarmMindConfig
from swarmmind.models.task import TaskRequest
from swarmmind.gateway.gateway import Gateway
from swarmmind.sandbox.opensandbox_adapter import OpenSandboxAdapter
from swarmmind.sandbox.manager import SandboxManager
from swarmmind.agents.factory import AgentFactory
from swarmmind.agents.config import AgentConfig
from swarmmind.tools.registry import ToolRegistry


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """SwarmMind - A general-purpose AI task assistant."""
    pass


@cli.command()
@click.argument("goal")
@click.option("--output", "-o", type=click.Path(), help="Output file for result")
@click.option("--profile", default="py-basic", help="Sandbox profile")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
@click.option("--sandbox-key", envvar="OPEN_SANDBOX_API_KEY", help="OpenSandbox API key")
def run(goal: str, output: Optional[str], profile: str, api_key: Optional[str], sandbox_key: Optional[str]):
    """Run a task with SwarmMind."""
    asyncio.run(_run_task(goal, output, profile, api_key, sandbox_key))


async def _run_task(goal: str, output: Optional[str], profile: str, api_key: Optional[str], sandbox_key: Optional[str]):
    """Run task asynchronously."""
    click.echo(f"Task: {goal}")

    # Initialize components
    config = SwarmMindConfig()

    # Setup sandbox
    sandbox_key = sandbox_key or "dev-key"
    sandbox_adapter = OpenSandboxAdapter(
        api_key=sandbox_key,
        base_url="http://localhost:45698",
    )
    sandbox_manager = SandboxManager(sandbox_adapter)

    # Setup agent
    agent_config = AgentConfig(
        name="main",
        scope_config=config.agent.model,
    )
    agent_factory = AgentFactory(agent_config)

    # Setup gateway
    gateway = Gateway()

    try:
        # Create task
        request = TaskRequest(
            goal=goal,
            profile=profile,
        )
        task = await gateway.create_task(request)
        click.echo(f"Task ID: {task.id}")

        # Create session
        session = gateway.create_session(task.id)
        transcript = session["transcript"]

        # Mark task as running
        task.start()
        await gateway.update_task(task)
        transcript.add_event("task_started", {"goal": goal})

        # Create agent with tools
        from swarmmind.tools.builtin.search import search
        tool_registry = ToolRegistry()
        tool_registry.register(search, name="search", description="Search the web for information")

        # Create agent (without tools for now, just basic)
        # In production, tools would be registered
        agent = agent_factory.create_main_agent()

        # Run agent
        transcript.add_message("user", goal)
        result = await agent(goal)

        # Task completed
        task.succeed({"result": result, "task_id": task.id})
        await gateway.update_task(task)
        transcript.add_event("task_completed", {"result": str(result)[:500]})

        # Output result
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(task.result, f, ensure_ascii=False, indent=2)
            click.echo(f"Result saved to {output}")
        else:
            click.echo(f"Result: {result}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        task.fail(str(e))
        await gateway.update_task(task)
        sys.exit(1)
    finally:
        # Cleanup sandbox
        await sandbox_manager.destroy_all()


@cli.command()
def version():
    """Show version."""
    click.echo("SwarmMind v0.1.0")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
