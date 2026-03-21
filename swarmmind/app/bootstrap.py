"""Bootstrap helpers for application services."""

from swarmmind.config import SwarmMindConfig
from swarmmind.app.container import AppContainer, build_container

_container: AppContainer | None = None


async def get_container(settings: SwarmMindConfig | None = None) -> AppContainer:
    """Return a singleton-like application container."""
    global _container
    if _container is None:
        _container = await build_container(settings)
    return _container


def reset_container() -> None:
    """Reset the cached container, primarily for tests and scripts."""
    global _container
    _container = None
