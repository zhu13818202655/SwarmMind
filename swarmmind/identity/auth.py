"""Authentication helpers."""

from swarmmind.identity.models import IdentityContext
from swarmmind.identity.resolver import IdentityResolver


async def authenticate(api_key: str | None, resolver: IdentityResolver) -> IdentityContext:
    """Resolve an identity context from an API key or local defaults."""
    return await resolver.resolve(api_key=api_key)
