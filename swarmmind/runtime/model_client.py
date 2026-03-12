"""Model client wrapper."""

from typing import Any
from agentscope.models import OpenAIChatWrapper


def create_model_client(
    provider: str = "openai",
    model: str = "gpt-4o",
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> OpenAIChatWrapper:
    """Create a model client.

    Args:
        provider: Model provider (openai, anthropic, etc.)
        model: Model name
        api_key: API key
        base_url: Base URL for API
        **kwargs: Additional arguments

    Returns:
        Model client
    """
    if provider == "openai":
        return OpenAIChatWrapper(
            model=model,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")
