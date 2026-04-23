"""Header builder for outbound dikong requests.

Dikong authenticates via a custom ``back-token`` request header (NOT the
standard ``Authorization`` header). The actual token is obtained either
statically from configuration or dynamically from
:class:`~swarmmind.domains.fly_report.dikong.token_provider.DikongTokenProvider`.
"""

from __future__ import annotations


def build_headers(
    *,
    token: str | None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the request headers for a dikong call.

    - ``back-token: <token>`` is added when ``token`` is non-empty.
    - ``extra`` headers, if provided, win over any of the above.
    """

    headers: dict[str, str] = {"Accept": "*/*"}
    if token:
        headers["back-token"] = token
    if extra:
        headers.update(extra)
    return headers


__all__ = ["build_headers"]
