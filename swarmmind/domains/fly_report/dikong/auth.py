"""Header builder for outbound dikong requests.

Step 2 keeps it deliberately simple: a static bearer token from settings plus
an optional tenant id.  Token rotation / refresh hooks can be layered on top
later by passing a callable into :class:`DikongClient` instead of a string.
"""

from __future__ import annotations


def build_headers(
    *,
    token: str | None,
    tenant_id: str | None,
    tenant_header: str = "X-Tenant-Id",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the request headers for a dikong call.

    - ``Authorization: Bearer <token>`` is added when ``token`` is non-empty.
    - The configured ``tenant_header`` is added when ``tenant_id`` is non-empty.
    - ``extra`` headers, if provided, win over any of the above.
    """

    headers: dict[str, str] = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if tenant_id:
        headers[tenant_header] = tenant_id
    if extra:
        headers.update(extra)
    return headers


__all__ = ["build_headers"]
