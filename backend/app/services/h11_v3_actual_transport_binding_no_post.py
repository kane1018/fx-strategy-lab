"""Disabled H-11 v3 sender injection boundary (fake-only, no-POST).

The production sender contract and injection point are defined here so the
boundary can be reviewed before activation.  This module intentionally ships
without a production sender implementation.  The default sender refuses, and
the only executable binding is a locally constructed fake transport.

No network package, credential source, environment lookup, broker endpoint, or
hard-guard allow path is imported by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from app.private_api.order_builders import (
    GMO_FX_IFDOCO_ORDER_PATH,
    REQUEST_KIND_IFDOCO_PROTECTED_ENTRY,
    GmoFxPrivateRequestPlanSafeSummary,
)


class H11V3TransportBindingError(RuntimeError):
    """Fail-closed error containing safe labels only."""


class H11V3SenderOutcome(str, Enum):
    REFUSED_DISABLED = "REFUSED_DISABLED"
    ACCEPTED_SYNTHETIC = "ACCEPTED_SYNTHETIC"
    UNKNOWN_SYNTHETIC = "UNKNOWN_SYNTHETIC"


@dataclass(frozen=True)
class H11V3SenderSafeResult:
    outcome: H11V3SenderOutcome
    request_kind_safe_label: str
    route_safe_label: str
    fake_request_count: int
    actual_post_count: int = 0
    broker_write: bool = False
    credential_read: bool = False

    def __bool__(self) -> bool:
        return False


@runtime_checkable
class H11V3IfdocoSender(Protocol):
    """Future sender interface; a real implementation is deliberately absent."""

    fake_only: bool

    def send_ifdoco_once_sanitized(
        self, plan_summary: GmoFxPrivateRequestPlanSafeSummary
    ) -> H11V3SenderSafeResult: ...


@dataclass(frozen=True)
class H11V3RefusingIfdocoSender:
    """Default sender.  It cannot be configured to send."""

    fake_only: bool = True

    def send_ifdoco_once_sanitized(
        self, plan_summary: GmoFxPrivateRequestPlanSafeSummary
    ) -> H11V3SenderSafeResult:
        _validate_plan_summary(plan_summary)
        raise H11V3TransportBindingError(
            "H-11 v3 actual sender is disabled in the no-POST build"
        )

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3FakeSealedCredential:
    """Synthetic capability marker; it never stores a credential value."""

    synthetic_label: str = "FAKE_SEALED_CREDENTIAL"
    credential_read: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.synthetic_label != "FAKE_SEALED_CREDENTIAL":
            raise H11V3TransportBindingError(
                "only the fixed synthetic credential label is accepted"
            )

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3FakeHttpxClient:
    """Httpx-shaped fake with no URL, headers, body, or network surface."""

    outcome: H11V3SenderOutcome = H11V3SenderOutcome.ACCEPTED_SYNTHETIC
    fake_request_count: int = field(default=0, init=False)
    network_enabled: bool = field(default=False, init=False)
    actual_post_count: int = field(default=0, init=False)

    def simulate_ifdoco_request(
        self,
        *,
        plan_summary: GmoFxPrivateRequestPlanSafeSummary,
        credential: H11V3FakeSealedCredential,
    ) -> H11V3SenderSafeResult:
        _validate_plan_summary(plan_summary)
        if not isinstance(credential, H11V3FakeSealedCredential):
            raise H11V3TransportBindingError("fake sealed credential is required")
        if self.outcome is H11V3SenderOutcome.REFUSED_DISABLED:
            raise H11V3TransportBindingError("fake client is configured to refuse")
        self.fake_request_count += 1
        return H11V3SenderSafeResult(
            outcome=self.outcome,
            request_kind_safe_label=plan_summary.request_kind,
            route_safe_label=plan_summary.path,
            fake_request_count=self.fake_request_count,
        )

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3FakeIfdocoSender:
    """Only executable sender implementation in the no-POST build."""

    client: H11V3FakeHttpxClient
    credential: H11V3FakeSealedCredential
    fake_only: bool = field(default=True, init=False)

    def send_ifdoco_once_sanitized(
        self, plan_summary: GmoFxPrivateRequestPlanSafeSummary
    ) -> H11V3SenderSafeResult:
        return self.client.simulate_ifdoco_request(
            plan_summary=plan_summary,
            credential=self.credential,
        )

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3DisabledTransportBinding:
    """Reviewed injection point that accepts fake-only senders and never activates."""

    sender: H11V3IfdocoSender = field(default_factory=H11V3RefusingIfdocoSender)
    actual_post_allowed: bool = field(default=False, init=False)
    actual_transport_bound: bool = field(default=False, init=False)
    activation_token_constructible: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sender, H11V3IfdocoSender):
            raise H11V3TransportBindingError("sender does not match the H-11 contract")
        if self.sender.fake_only is not True:
            raise H11V3TransportBindingError(
                "non-fake sender binding is structurally rejected"
            )

    def execute_fake_review(
        self, plan_summary: GmoFxPrivateRequestPlanSafeSummary
    ) -> H11V3SenderSafeResult:
        _validate_plan_summary(plan_summary)
        if not isinstance(self.sender, H11V3FakeIfdocoSender):
            raise H11V3TransportBindingError(
                "default disabled binding refuses execution"
            )
        result = self.sender.send_ifdoco_once_sanitized(plan_summary)
        if (
            result.actual_post_count != 0
            or result.broker_write
            or result.credential_read
        ):
            raise H11V3TransportBindingError("fake sender violated no-POST invariants")
        return result

    def __bool__(self) -> bool:
        return False


def _validate_plan_summary(plan_summary: GmoFxPrivateRequestPlanSafeSummary) -> None:
    if plan_summary.request_kind != REQUEST_KIND_IFDOCO_PROTECTED_ENTRY:
        raise H11V3TransportBindingError("IFDOCO protected-entry plan is required")
    if plan_summary.path != GMO_FX_IFDOCO_ORDER_PATH:
        raise H11V3TransportBindingError("IFDOCO route is required")
