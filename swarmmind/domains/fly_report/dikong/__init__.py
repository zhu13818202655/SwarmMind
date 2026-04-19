"""Dikong upstream client subpackage.

Public surface (will grow as Step 2 lands):

- ``DikongClient`` - thin async HTTP wrapper around dikong's REST API
- ``EndpointKey`` - stable identifiers for the §6 endpoint matrix
- ``DikongEnvelope`` - shared response envelope ``{code, msg, data, ...}``
"""

from swarmmind.domains.fly_report.dikong.endpoints import (
    ENDPOINTS,
    EndpointGroup,
    EndpointKey,
    EndpointSpec,
    HttpMethod,
    get_endpoint,
)

__all__ = [
    "ENDPOINTS",
    "EndpointGroup",
    "EndpointKey",
    "EndpointSpec",
    "HttpMethod",
    "get_endpoint",
]
