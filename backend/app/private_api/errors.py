"""Errors for the mocked Private API read-only skeleton."""

from __future__ import annotations

from typing import Any


class PrivateApiReadonlyError(RuntimeError):
    """Base error for Phase 3B read-only skeleton failures."""


class PrivateApiAuthError(PrivateApiReadonlyError):
    """Raised when mocked auth metadata is invalid."""


class PrivateApiResponseError(PrivateApiReadonlyError):
    """Raised when a mocked response cannot be sanitized."""

    def __init__(self, message: str, *, api_error: Any | None = None) -> None:
        super().__init__(message)
        self.api_error = api_error


class PrivateApiForbiddenEndpointError(PrivateApiReadonlyError):
    """Raised when a non-read-only endpoint is requested."""


class PrivateApiConnectionDisabledError(PrivateApiReadonlyError):
    """Raised when code attempts a real connection in Phase 3B-1."""
