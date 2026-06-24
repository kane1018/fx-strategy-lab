"""Authentication helpers for mocked Private API read-only tests.

The helpers use only values passed by the caller. They do not load process config,
files, or any local credential store.
"""

from __future__ import annotations

import hashlib
import hmac


def create_signature(
    api_secret: str,
    timestamp: str,
    method: str,
    path: str,
    body: str = "",
) -> str:
    """Return GMO-style HMAC-SHA256 hex digest for an injected request shape."""
    if not api_secret:
        raise ValueError("api_secret is required")
    if not timestamp:
        raise ValueError("timestamp is required")
    if not method:
        raise ValueError("method is required")
    if not path.startswith("/"):
        raise ValueError("path must start with '/'")

    payload = f"{timestamp}{method.upper()}{path}{body}"
    return hmac.new(
        api_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_auth_headers(
    api_key: str,
    api_secret: str,
    timestamp: str,
    method: str,
    path: str,
    body: str = "",
) -> dict[str, str]:
    """Build auth headers from injected sample values only."""
    if not api_key:
        raise ValueError("api_key is required")
    return {
        "API-KEY": api_key,
        "API-TIMESTAMP": timestamp,
        "API-SIGN": create_signature(
            api_secret=api_secret,
            timestamp=timestamp,
            method=method,
            path=path,
            body=body,
        ),
    }
