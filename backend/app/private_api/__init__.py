"""Mocked GMO FX Private API read-only skeleton.

Phase 3B-1 is offline only: no real connection, no credential loading, no order path.
"""

from app.private_api.auth import build_auth_headers, create_signature
from app.private_api.errors import (
    PrivateApiAuthError,
    PrivateApiConnectionDisabledError,
    PrivateApiForbiddenEndpointError,
    PrivateApiReadonlyError,
    PrivateApiResponseError,
)
from app.private_api.readonly_client import (
    FORBIDDEN_ENDPOINTS,
    READ_ONLY_ENDPOINTS,
    PrivateReadonlyClient,
    ReadOnlyRequest,
    assert_readonly_endpoint,
    is_readonly_endpoint,
)
from app.private_api.schemas import (
    AccountAssets,
    ActiveOrder,
    Execution,
    OpenPosition,
    PositionSummary,
    PrivateApiError,
)

__all__ = [
    "AccountAssets",
    "ActiveOrder",
    "Execution",
    "FORBIDDEN_ENDPOINTS",
    "OpenPosition",
    "PositionSummary",
    "PrivateApiAuthError",
    "PrivateApiConnectionDisabledError",
    "PrivateApiError",
    "PrivateApiForbiddenEndpointError",
    "PrivateApiReadonlyError",
    "PrivateApiResponseError",
    "PrivateReadonlyClient",
    "READ_ONLY_ENDPOINTS",
    "ReadOnlyRequest",
    "assert_readonly_endpoint",
    "build_auth_headers",
    "create_signature",
    "is_readonly_endpoint",
]
