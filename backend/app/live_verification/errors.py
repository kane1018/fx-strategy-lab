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


class LiveVerificationBrokerBoundaryError(LiveVerificationValidationError):
    """Raised when a no-network broker boundary result is internally invalid."""


class LiveVerificationPayloadCandidateError(LiveVerificationValidationError):
    """Raised when a mocked payload candidate would cross a safety boundary."""


class LiveVerificationOrderClientSkeletonError(LiveVerificationValidationError):
    """Raised when a disabled no-network client plan is unsafe."""


class LiveVerificationSignatureRequestDesignError(LiveVerificationValidationError):
    """Raised when a mocked request design model crosses a safety boundary."""


class LiveVerificationHttpRequestSkeletonError(LiveVerificationValidationError):
    """Raised when a disabled HTTP skeleton plan crosses a safety boundary."""


class LiveVerificationSignatureHeadersBodyPlanError(LiveVerificationValidationError):
    """Raised when a plan-only body/header/signing boundary is unsafe."""


class LiveVerificationActualOrderBodyError(LiveVerificationValidationError):
    """Raised when an actual body model crosses a safety boundary."""


class LiveVerificationActualHeadersSignatureError(LiveVerificationValidationError):
    """Raised when signed header construction crosses a safety boundary."""


class LiveVerificationMockSignedTransportError(LiveVerificationValidationError):
    """Raised when mock signed transport crosses a safety boundary."""


class LiveVerificationOrderSubmissionSkeletonError(LiveVerificationValidationError):
    """Raised when a disabled order submission skeleton is unsafe."""


class LiveVerificationLiveOrderPreflightError(LiveVerificationValidationError):
    """Raised when Step 3 live order preflight audit state is invalid."""


class LiveVerificationForbiddenActionError(LiveVerificationError):
    """Raised if mocked core is asked to cross the no-order boundary."""
