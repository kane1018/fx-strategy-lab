"""No-POST entry transport boundary for GMO live execution.

Defines the entry-only transport interface, a fake transport for tests, an
explicit "production transport not implemented" fail-closed transport, and a
single-use fake state machine. No real HTTP is performed anywhere here.

Hard rules enforced by construction:

- Entry-only. There is no settlement/close/cancel/change method on the
  interface; a fake asked for such a scope raises.
- One POST max and no resend: a rejected/unknown/timeout outcome never
  triggers a retry, repost, or second POST.
- Results are sanitized categories only (ACCEPTED / REJECTED / UNKNOWN).
  There is no field carrying a raw request/response, an error body, an ID,
  or a broker value.
- The production real transport stays unimplemented and fails closed; the
  fake state machine refuses to run against anything other than a fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class GmoEntryPostResultCategory(str, Enum):
    RESULT_ACCEPTED_SANITIZED = "RESULT_ACCEPTED_SANITIZED"
    RESULT_REJECTED_SANITIZED = "RESULT_REJECTED_SANITIZED"
    RESULT_UNKNOWN_SANITIZED = "RESULT_UNKNOWN_SANITIZED"


class GmoEntryTransportError(RuntimeError):
    """Raised for fail-closed / entry-only violations. Never carries a body."""


@dataclass(frozen=True)
class GmoEntryPostSanitizedPreview:
    """Safe preview shown just before an entry POST. Never raw/ID/value."""

    operator_signal_safe_label: str
    order_side_safe_label: str
    symbol_safe_label: str
    execution_type_safe_label: str
    runtime_position_safe_status: str
    position_count_safe: int
    active_pending_safe_status: str
    credential_presence_safe_boolean: bool
    entry_post_max_count: int = 1
    retry: bool = False
    repost: bool = False
    second_post: bool = False
    settlement_post: bool = False
    generic_close: bool = False
    credential_value_exposed: bool = False
    raw_id_value_exposure: bool = False

    def __bool__(self) -> bool:
        return False


@runtime_checkable
class GmoEntryTransport(Protocol):
    """Entry-only transport. Returns a sanitized result category only."""

    def send_entry_order_sanitized(self) -> GmoEntryPostResultCategory:
        """Send exactly one entry order and return only a sanitized category."""


@dataclass(frozen=True)
class FakeEntryTransport:
    """Test-only transport returning a preset sanitized category.

    Performs no HTTP. Entry-only: it exposes no settlement/close method, and
    ``is_real_transport`` is false so the state machine will accept it.
    """

    preset_result: GmoEntryPostResultCategory = (
        GmoEntryPostResultCategory.RESULT_UNKNOWN_SANITIZED
    )
    is_real_transport: bool = False

    def send_entry_order_sanitized(self) -> GmoEntryPostResultCategory:
        return self.preset_result


@dataclass(frozen=True)
class ProductionEntryTransportNotImplemented:
    """Fail-closed stand-in proving real entry transport is not implemented."""

    is_real_transport: bool = True

    def send_entry_order_sanitized(self) -> GmoEntryPostResultCategory:
        raise GmoEntryTransportError(
            "GMO entry transport is not implemented (no-POST phase); real "
            "broker HTTP is intentionally absent"
        )


class GmoEntryPostStateMachineStatus(str, Enum):
    ENTRY_POST_NOT_ATTEMPTED = "ENTRY_POST_NOT_ATTEMPTED"
    ENTRY_POST_BLOCKED_PERMIT_NOT_USABLE = "ENTRY_POST_BLOCKED_PERMIT_NOT_USABLE"
    ENTRY_POST_BLOCKED_REAL_TRANSPORT_FORBIDDEN_IN_NO_POST = (
        "ENTRY_POST_BLOCKED_REAL_TRANSPORT_FORBIDDEN_IN_NO_POST"
    )
    ENTRY_POST_FAKE_SANITIZED_COMPLETED = "ENTRY_POST_FAKE_SANITIZED_COMPLETED"


@dataclass(frozen=True)
class GmoEntryPostStateMachineResult:
    status: GmoEntryPostStateMachineStatus
    result_category: GmoEntryPostResultCategory | None
    fake_post_count: int
    real_post_count: int = 0
    retry_performed: bool = False
    repost_performed: bool = False
    second_post_performed: bool = False
    next_recommended_step: str = ""

    def __bool__(self) -> bool:
        return False


_NEXT_STEP_BY_RESULT = {
    GmoEntryPostResultCategory.RESULT_ACCEPTED_SANITIZED: (
        "POST_ENTRY_READ_ONLY_CONFIRMATION_NO_POST"
    ),
    GmoEntryPostResultCategory.RESULT_REJECTED_SANITIZED: (
        "REJECTED_SAFE_REVIEW_NO_POST"
    ),
    GmoEntryPostResultCategory.RESULT_UNKNOWN_SANITIZED: (
        "UNKNOWN_RESULT_SAFE_REVIEW_NO_POST"
    ),
}


def simulate_gmo_entry_post_once_fake_only(
    *,
    transport: GmoEntryTransport,
    permit_usable_for_one_entry_post: bool,
) -> GmoEntryPostStateMachineResult:
    """Run at most one FAKE entry POST and never resend on any outcome.

    Refuses any transport whose ``is_real_transport`` is true: this state
    machine is a fake-only no-POST simulation and must never drive a real
    broker write. Regardless of the sanitized outcome, it performs exactly
    one fake call and then stops -- there is no retry/repost/second POST
    path in this function at all.
    """

    if not permit_usable_for_one_entry_post:
        return GmoEntryPostStateMachineResult(
            status=GmoEntryPostStateMachineStatus.ENTRY_POST_BLOCKED_PERMIT_NOT_USABLE,
            result_category=None,
            fake_post_count=0,
        )

    if getattr(transport, "is_real_transport", False):
        return GmoEntryPostStateMachineResult(
            status=(
                GmoEntryPostStateMachineStatus
                .ENTRY_POST_BLOCKED_REAL_TRANSPORT_FORBIDDEN_IN_NO_POST
            ),
            result_category=None,
            fake_post_count=0,
        )

    category = transport.send_entry_order_sanitized()
    return GmoEntryPostStateMachineResult(
        status=GmoEntryPostStateMachineStatus.ENTRY_POST_FAKE_SANITIZED_COMPLETED,
        result_category=category,
        fake_post_count=1,
        real_post_count=0,
        retry_performed=False,
        repost_performed=False,
        second_post_performed=False,
        next_recommended_step=_NEXT_STEP_BY_RESULT[category],
    )
