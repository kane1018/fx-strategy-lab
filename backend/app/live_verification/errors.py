"""Errors for Phase 3C-1 live verification mocked core."""

from __future__ import annotations


class LiveVerificationError(RuntimeError):
    """Base error for live verification mocked core failures."""


class LiveVerificationValidationError(LiveVerificationError):
    """Raised when mocked live verification input violates fixed constraints."""


class LiveVerificationPrecheckError(LiveVerificationValidationError):
    """Raised when read-only precheck input or result is invalid."""


class LiveVerificationIntentError(LiveVerificationValidationError):
    """Raised when an order intent cannot be built safely."""


class LiveVerificationStateError(LiveVerificationValidationError):
    """Raised when a live verification state transition is invalid."""


class LiveVerificationCorrelationError(LiveVerificationValidationError):
    """Raised when mocked live verification IDs do not correlate safely."""


class LiveVerificationOrderReviewError(LiveVerificationValidationError):
    """Raised when order review or checklist inputs are unsafe."""


class LiveVerificationForbiddenActionError(LiveVerificationError):
    """Raised if mocked core is asked to cross the no-order boundary."""
