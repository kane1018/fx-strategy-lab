"""Official GMO FX settlement actual HTTP POST sender boundary, no POST.

This module adds the dedicated official settlement sender callable boundary that
the next execution gate can target after fresh runtime, operator readiness, and
settlement-specific confirmation are all satisfied. It does not invoke the
sender, perform HTTP, read env files, or import generic order executors,
live_order_once, broker clients, ledger, or receipt code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_actual_post_live_enablement_no_post_controlled import (  # noqa: E501
    OfficialSettlementActualPostLiveEnablementResult,
    build_official_settlement_actual_post_live_enablement_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (  # noqa: E501
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)

EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_NO_POST = (
    "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_NO_POST_C"
)
SAFE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_LABEL = (
    "STEP6G_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_NO_POST"
)
SAFE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_CALLABLE_LABEL = (
    "DEDICATED_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_CALLABLE"
)
SAFE_FAKE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_ADAPTER_LABEL = (
    "FAKE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_ADAPTER_NO_NETWORK"
)
RESULT_ACTUAL_HTTP_POST_SENDER_READY_NO_POST_SANITIZED = (
    "RESULT_ACTUAL_HTTP_POST_SENDER_READY_NO_POST_SANITIZED"
)
RESULT_ACTUAL_HTTP_POST_SENDER_BLOCKED_NO_POST_SANITIZED = (
    "RESULT_ACTUAL_HTTP_POST_SENDER_BLOCKED_NO_POST_SANITIZED"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C"
)
NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER = (
    "fix_official_settlement_actual_http_post_sender_no_post"
)


class OfficialSettlementActualHttpPostSenderStatus(str, Enum):
    READY_NO_POST = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_READY_NO_POST"
    BLOCKED_REPOSITORY = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_REPOSITORY"
    BLOCKED_CREDENTIAL = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_CREDENTIAL"
    BLOCKED_POSITION = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_POSITION"
    BLOCKED_ROUTE = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_ROUTE"
    BLOCKED_TRANSPORT = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_TRANSPORT"
    BLOCKED_SENDER = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_SENDER"
    BLOCKED_OPERATOR = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_OPERATOR"
    BLOCKED_CONFIRMATION = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_CONFIRMATION"
    BLOCKED_LIFECYCLE = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_LIFECYCLE"
    BLOCKED_UNSAFE = "OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_BLOCKED_UNSAFE"


@dataclass(frozen=True)
class OfficialSettlementActualHttpPostSenderInput:
    repository_clean: bool = True
    head_equals_origin_main: bool = True
    credential_presence_available: bool = True
    official_settlement_no_post_preview_ready: bool = True
    official_settlement_executor_preview_ready: bool = True
    dedicated_settlement_actual_executor_compatibility_ready: bool = True
    dedicated_actual_official_settlement_post_executor_available: bool = True
    dedicated_actual_official_settlement_transport_boundary_ready: bool = True
    actual_settlement_post_live_capable_transport_available: bool = True
    actual_settlement_post_can_be_allowed_after_fresh_execution_gates: bool = True
    dedicated_official_settlement_actual_http_post_sender_confirmed: bool = True
    dedicated_official_settlement_actual_http_post_sender_callable_available: bool = True
    dedicated_official_settlement_actual_http_post_sender_boundary_ready: bool = True
    dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route: (
        bool
    ) = True
    dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route: (
        bool
    ) = False
    dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor: (
        bool
    ) = False
    dedicated_official_settlement_actual_http_post_sender_uses_live_order_once: bool = (
        False
    )
    dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order: (
        bool
    ) = False
    dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path: (
        bool
    ) = False
    settlement_route_kind: str = SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED
    settlement_route_is_generic_order: bool = False
    settlement_route_is_dedicated: bool = True
    generic_order_executor_used_for_settlement: bool = False
    live_order_once_used_for_settlement: bool = False
    generic_order_endpoint_used_for_settlement: bool = False
    one_shot_generic_order_path_used_for_settlement: bool = False
    position_specific_path_used: bool = False
    position_specific_identifier_safe_handling_ready: bool = False
    position_specific_preview_allowed: bool = False
    size_based_preview_allowed: bool = True
    runtime_position_status: PositionReadOnlyControlledStatus = (
        PositionReadOnlyControlledStatus.ONE_POSITION_OPEN
    )
    position_count_safe: int = 1
    has_exactly_one_position: bool = True
    has_multiple_positions: bool = False
    operator_broker_ui_checked: bool = True
    operator_broker_ui_open_position_visible: bool = True
    operator_broker_ui_values_or_ids_provided: bool = False
    operator_can_monitor: bool = True
    operator_approves_settlement_attempt: bool = True
    sanitized_settlement_preview_shown: bool = True
    settlement_specific_confirmation_current_turn: bool = True
    settlement_specific_confirmation_exact_match: bool = True
    one_settlement_post_max: bool = True
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_settlement_allowed: bool = False
    entry_post_allowed: bool = False
    generic_close_allowed: bool = False
    ledger_update_allowed: bool = False
    receipt_handoff_allowed: bool = False
    raw_id_value_credential_header_exposure: bool = False
    execution_gate_authorization_uses_fake_sender_adapter: bool = True
    execution_gate_authorization_http_post_executed: bool = False
    this_step_actual_http_post_sender_invoked: bool = False
    this_step_actual_settlement_post_executed: bool = False
    settlement_post_count: int = 0
    sender_call_count: int = 0
    transport_call_count: int = 0
    http_post_executed: bool = False
    entry_post_executed: bool = False
    generic_close_post_executed: bool = False
    live_order_once_executed: bool = False
    external_api_write_executed: bool = False
    env_read: bool = False
    next_execution_gate_still_requires_fresh_runtime_read: bool = True
    next_execution_gate_still_requires_operator_readiness: bool = True
    next_execution_gate_still_requires_settlement_specific_confirmation: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_position_status, PositionReadOnlyControlledStatus):
            raise LiveVerificationValidationError(
                "runtime_position_status must be controlled enum",
            )
        _require_non_empty("settlement_route_kind", self.settlement_route_kind)
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("sender_call_count", self.sender_call_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementActualHttpPostSenderPlan:
    sender_plan_label: str
    dedicated_official_settlement_actual_http_post_sender_confirmed: bool
    dedicated_official_settlement_actual_http_post_sender_callable_available: bool
    dedicated_official_settlement_actual_http_post_sender_boundary_ready: bool
    sender_can_be_called_only_after_execution_gate_authorization: bool
    dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route: bool
    dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_live_order_once: bool
    dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path: (
        bool
    )
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    one_settlement_post_max: bool
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    entry_post_allowed: bool
    generic_close_allowed: bool

    def __post_init__(self) -> None:
        _require_non_empty("sender_plan_label", self.sender_plan_label)
        _require_non_empty("settlement_route_kind", self.settlement_route_kind)
        _validate_bool_fields(self, _PLAN_BOOL_FIELDS)


@dataclass(frozen=True)
class FakeOfficialSettlementActualHttpPostSenderAdapter:
    fake_sender_adapter_label: str
    execution_gate_authorization_uses_fake_sender_adapter: bool
    execution_gate_authorization_http_post_executed: bool
    simulated_sender_call_count: int
    simulated_settlement_post_count: int
    sender_call_count: int
    transport_call_count: int
    http_post_executed: bool
    external_api_write_executed: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool

    def __post_init__(self) -> None:
        _require_non_empty("fake_sender_adapter_label", self.fake_sender_adapter_label)
        _validate_non_negative_int(
            "simulated_sender_call_count",
            self.simulated_sender_call_count,
        )
        _validate_non_negative_int(
            "simulated_settlement_post_count",
            self.simulated_settlement_post_count,
        )
        _validate_non_negative_int("sender_call_count", self.sender_call_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _FAKE_ADAPTER_BOOL_FIELDS)


class OfficialSettlementActualHttpPostSenderAdapterProtocol(Protocol):
    """Adapter contract for a later execution step; not invoked in this step."""

    def send_authorized_official_settlement_post(
        self,
        plan: OfficialSettlementActualHttpPostSenderPlan,
    ) -> FakeOfficialSettlementActualHttpPostSenderAdapter:
        """Send after execution-gate authorization in a later step."""


@dataclass(frozen=True)
class OfficialSettlementActualHttpPostSenderResult:
    status: OfficialSettlementActualHttpPostSenderStatus
    safe_sender_label: str
    dedicated_official_settlement_actual_http_post_sender_confirmed: bool
    dedicated_official_settlement_actual_http_post_sender_callable_available: bool
    dedicated_official_settlement_actual_http_post_sender_boundary_ready: bool
    dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_live_order_once: bool
    dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order: (
        bool
    )
    dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path: (
        bool
    )
    sender_plan: OfficialSettlementActualHttpPostSenderPlan
    fake_sender_adapter: FakeOfficialSettlementActualHttpPostSenderAdapter
    actual_settlement_post_live_capable_transport_available: bool
    actual_settlement_post_can_be_allowed_after_fresh_execution_gates: bool
    execution_gate_authorization_can_reach_dedicated_http_sender: bool
    execution_gate_authorization_uses_fake_sender_adapter: bool
    execution_gate_authorization_http_post_executed: bool
    official_settlement_no_post_preview_ready: bool
    official_settlement_executor_preview_ready: bool
    dedicated_settlement_actual_executor_compatibility_ready: bool
    dedicated_actual_official_settlement_post_executor_available: bool
    dedicated_actual_official_settlement_transport_boundary_ready: bool
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    generic_order_endpoint_used_for_settlement: bool
    one_shot_generic_order_path_used_for_settlement: bool
    position_specific_path_used: bool
    position_specific_identifier_safe_handling_ready: bool
    position_specific_preview_allowed: bool
    size_based_preview_allowed: bool
    this_step_actual_http_post_sender_invoked: bool
    this_step_actual_settlement_post_executed: bool
    settlement_post_count: int
    sender_call_count: int
    transport_call_count: int
    http_post_executed: bool
    entry_post_executed: bool
    generic_close_post_executed: bool
    live_order_once_executed: bool
    external_api_write_executed: bool
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_id_value_credential_header_exposure: bool
    env_read: bool
    next_execution_gate_can_call_dedicated_actual_http_post_sender_after_confirmation: (
        bool
    )
    next_execution_gate_still_requires_fresh_runtime_read: bool
    next_execution_gate_still_requires_operator_readiness: bool
    next_execution_gate_still_requires_settlement_specific_confirmation: bool
    result_safe_category: str
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, OfficialSettlementActualHttpPostSenderStatus):
            raise LiveVerificationValidationError("status must be sender enum")
        _require_non_empty("safe_sender_label", self.safe_sender_label)
        _require_non_empty("settlement_route_kind", self.settlement_route_kind)
        _require_non_empty("result_safe_category", self.result_safe_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("sender_call_count", self.sender_call_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_actual_http_post_sender_no_post_controlled(
    input_snapshot: OfficialSettlementActualHttpPostSenderInput | None = None,
    *,
    live_enablement_result: OfficialSettlementActualPostLiveEnablementResult | None = None,
) -> OfficialSettlementActualHttpPostSenderResult:
    """Build a dedicated sender boundary without invoking the sender or HTTP."""
    snapshot = input_snapshot or _input_from_live_enablement(
        live_enablement_result
        or build_official_settlement_actual_post_live_enablement_no_post_controlled(),
    )
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    status = _status_from_reasons(reasons)
    plan = _sender_plan(snapshot, ready)
    fake_adapter = _fake_sender_adapter(snapshot)

    return OfficialSettlementActualHttpPostSenderResult(
        status=status,
        safe_sender_label=SAFE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_LABEL,
        dedicated_official_settlement_actual_http_post_sender_confirmed=(
            snapshot.dedicated_official_settlement_actual_http_post_sender_confirmed
            and ready
        ),
        dedicated_official_settlement_actual_http_post_sender_callable_available=(
            snapshot.dedicated_official_settlement_actual_http_post_sender_callable_available
            and ready
        ),
        dedicated_official_settlement_actual_http_post_sender_boundary_ready=(
            snapshot.dedicated_official_settlement_actual_http_post_sender_boundary_ready
            and ready
        ),
        dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route=(
            snapshot.dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route
            and ready
        ),
        dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route=False,
        dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor=False,
        dedicated_official_settlement_actual_http_post_sender_uses_live_order_once=False,
        dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order=False,
        dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path=False,
        sender_plan=plan,
        fake_sender_adapter=fake_adapter,
        actual_settlement_post_live_capable_transport_available=(
            snapshot.actual_settlement_post_live_capable_transport_available and ready
        ),
        actual_settlement_post_can_be_allowed_after_fresh_execution_gates=(
            snapshot.actual_settlement_post_can_be_allowed_after_fresh_execution_gates
            and ready
        ),
        execution_gate_authorization_can_reach_dedicated_http_sender=ready,
        execution_gate_authorization_uses_fake_sender_adapter=(
            snapshot.execution_gate_authorization_uses_fake_sender_adapter
        ),
        execution_gate_authorization_http_post_executed=False,
        official_settlement_no_post_preview_ready=(
            snapshot.official_settlement_no_post_preview_ready
        ),
        official_settlement_executor_preview_ready=(
            snapshot.official_settlement_executor_preview_ready
        ),
        dedicated_settlement_actual_executor_compatibility_ready=(
            snapshot.dedicated_settlement_actual_executor_compatibility_ready
        ),
        dedicated_actual_official_settlement_post_executor_available=(
            snapshot.dedicated_actual_official_settlement_post_executor_available
        ),
        dedicated_actual_official_settlement_transport_boundary_ready=(
            snapshot.dedicated_actual_official_settlement_transport_boundary_ready
        ),
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        generic_order_endpoint_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_used=False,
        position_specific_identifier_safe_handling_ready=(
            snapshot.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=snapshot.position_specific_preview_allowed,
        size_based_preview_allowed=snapshot.size_based_preview_allowed,
        this_step_actual_http_post_sender_invoked=False,
        this_step_actual_settlement_post_executed=False,
        settlement_post_count=0,
        sender_call_count=0,
        transport_call_count=0,
        http_post_executed=False,
        entry_post_executed=False,
        generic_close_post_executed=False,
        live_order_once_executed=False,
        external_api_write_executed=False,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_credential_header_exposure=(
            snapshot.raw_id_value_credential_header_exposure
        ),
        env_read=False,
        next_execution_gate_can_call_dedicated_actual_http_post_sender_after_confirmation=(
            ready
        ),
        next_execution_gate_still_requires_fresh_runtime_read=True,
        next_execution_gate_still_requires_operator_readiness=True,
        next_execution_gate_still_requires_settlement_specific_confirmation=True,
        result_safe_category=(
            RESULT_ACTUAL_HTTP_POST_SENDER_READY_NO_POST_SANITIZED
            if ready
            else RESULT_ACTUAL_HTTP_POST_SENDER_BLOCKED_NO_POST_SANITIZED
        ),
        recommended_next_step=(
            NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE
            if ready
            else NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER
        ),
        blocked_reasons=reasons,
    )


def dedicated_official_settlement_actual_http_post_sender_callable(
    plan: OfficialSettlementActualHttpPostSenderPlan,
    adapter: OfficialSettlementActualHttpPostSenderAdapterProtocol,
) -> FakeOfficialSettlementActualHttpPostSenderAdapter:
    """Callable boundary for a later execution step after confirmation."""
    if not isinstance(plan, OfficialSettlementActualHttpPostSenderPlan):
        raise LiveVerificationValidationError("plan must be dedicated sender plan")
    if not plan.sender_can_be_called_only_after_execution_gate_authorization:
        raise LiveVerificationValidationError("execution gate authorization required")
    if not plan.dedicated_official_settlement_actual_http_post_sender_callable_available:
        raise LiveVerificationValidationError("dedicated sender callable unavailable")
    sender_uses_official_route = (
        plan.dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route
    )
    if not sender_uses_official_route:
        raise LiveVerificationValidationError("official settlement route required")
    if plan.dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route:
        raise LiveVerificationValidationError("generic order route forbidden")
    if plan.dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor:
        raise LiveVerificationValidationError("generic order executor forbidden")
    if plan.dedicated_official_settlement_actual_http_post_sender_uses_live_order_once:
        raise LiveVerificationValidationError("live_order_once forbidden")
    if plan.dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order:
        raise LiveVerificationValidationError("one-shot generic order forbidden")
    if plan.dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path:
        raise LiveVerificationValidationError("position-specific path forbidden")
    if plan.retry_allowed or plan.repost_allowed or plan.second_settlement_allowed:
        raise LiveVerificationValidationError("retry/repost/second settlement forbidden")
    if plan.entry_post_allowed or plan.generic_close_allowed:
        raise LiveVerificationValidationError("entry and generic close forbidden")
    return adapter.send_authorized_official_settlement_post(plan)


def render_official_settlement_actual_http_post_sender_no_post_markdown(
    result: OfficialSettlementActualHttpPostSenderResult,
) -> str:
    """Render a sanitized dedicated sender boundary summary."""
    if not isinstance(result, OfficialSettlementActualHttpPostSenderResult):
        raise LiveVerificationValidationError(
            "result must be official settlement sender result",
        )
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Official Settlement Actual HTTP POST Sender No-POST",
            "",
            (
                "execution_step: "
                f"{EXECUTION_STEP_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_NO_POST}"
            ),
            f"status: {result.status.value}",
            (
                "dedicated_official_settlement_actual_http_post_sender_confirmed: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_confirmed)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_callable_available: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_callable_available)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_boundary_ready: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_boundary_ready)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_uses_"
                "official_settlement_route: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_uses_"
                "generic_order_executor: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_uses_live_order_once: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_uses_live_order_once)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_uses_"
                "one_shot_generic_order: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_uses_"
                "position_specific_path: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path)}"
            ),
            (
                "actual_settlement_post_live_capable_transport_available: "
                f"{_bool_text(result.actual_settlement_post_live_capable_transport_available)}"
            ),
            (
                "actual_settlement_post_can_be_allowed_after_fresh_execution_gates: "
                f"{_bool_text(result.actual_settlement_post_can_be_allowed_after_fresh_execution_gates)}"
            ),
            (
                "execution_gate_authorization_can_reach_dedicated_http_sender: "
                f"{_bool_text(result.execution_gate_authorization_can_reach_dedicated_http_sender)}"
            ),
            (
                "execution_gate_authorization_uses_fake_sender_adapter: "
                f"{_bool_text(result.execution_gate_authorization_uses_fake_sender_adapter)}"
            ),
            (
                "execution_gate_authorization_http_post_executed: "
                f"{_bool_text(result.execution_gate_authorization_http_post_executed)}"
            ),
            (
                "official_settlement_no_post_preview_ready: "
                f"{_bool_text(result.official_settlement_no_post_preview_ready)}"
            ),
            (
                "official_settlement_executor_preview_ready: "
                f"{_bool_text(result.official_settlement_executor_preview_ready)}"
            ),
            (
                "dedicated_settlement_actual_executor_compatibility_ready: "
                f"{_bool_text(result.dedicated_settlement_actual_executor_compatibility_ready)}"
            ),
            (
                "dedicated_actual_official_settlement_post_executor_available: "
                f"{_bool_text(result.dedicated_actual_official_settlement_post_executor_available)}"
            ),
            (
                "dedicated_actual_official_settlement_transport_boundary_ready: "
                f"{_bool_text(result.dedicated_actual_official_settlement_transport_boundary_ready)}"
            ),
            f"settlement_route_kind: {result.settlement_route_kind}",
            (
                "settlement_route_is_generic_order: "
                f"{_bool_text(result.settlement_route_is_generic_order)}"
            ),
            (
                "settlement_route_is_dedicated: "
                f"{_bool_text(result.settlement_route_is_dedicated)}"
            ),
            (
                "generic_order_executor_used_for_settlement: "
                f"{_bool_text(result.generic_order_executor_used_for_settlement)}"
            ),
            (
                "live_order_once_used_for_settlement: "
                f"{_bool_text(result.live_order_once_used_for_settlement)}"
            ),
            (
                "generic_order_endpoint_used_for_settlement: "
                f"{_bool_text(result.generic_order_endpoint_used_for_settlement)}"
            ),
            (
                "one_shot_generic_order_path_used_for_settlement: "
                f"{_bool_text(result.one_shot_generic_order_path_used_for_settlement)}"
            ),
            f"position_specific_path_used: {_bool_text(result.position_specific_path_used)}",
            (
                "position_specific_identifier_safe_handling_ready: "
                f"{_bool_text(result.position_specific_identifier_safe_handling_ready)}"
            ),
            (
                "position_specific_preview_allowed: "
                f"{_bool_text(result.position_specific_preview_allowed)}"
            ),
            f"size_based_preview_allowed: {_bool_text(result.size_based_preview_allowed)}",
            (
                "this_step_actual_http_post_sender_invoked: "
                f"{_bool_text(result.this_step_actual_http_post_sender_invoked)}"
            ),
            (
                "this_step_actual_settlement_post_executed: "
                f"{_bool_text(result.this_step_actual_settlement_post_executed)}"
            ),
            f"settlement_post_count: {result.settlement_post_count}",
            f"sender_call_count: {result.sender_call_count}",
            f"transport_call_count: {result.transport_call_count}",
            f"http_post_executed: {_bool_text(result.http_post_executed)}",
            f"entry_post_executed: {_bool_text(result.entry_post_executed)}",
            f"generic_close_post_executed: {_bool_text(result.generic_close_post_executed)}",
            f"live_order_once_executed: {_bool_text(result.live_order_once_executed)}",
            f"external_api_write_executed: {_bool_text(result.external_api_write_executed)}",
            f"retry_allowed: {_bool_text(result.retry_allowed)}",
            f"repost_allowed: {_bool_text(result.repost_allowed)}",
            f"second_settlement_allowed: {_bool_text(result.second_settlement_allowed)}",
            f"ledger_update: {_bool_text(result.ledger_update)}",
            f"receipt_handoff: {_bool_text(result.receipt_handoff)}",
            (
                "raw_id_value_credential_header_exposure: "
                f"{_bool_text(result.raw_id_value_credential_header_exposure)}"
            ),
            f"env_read: {_bool_text(result.env_read)}",
            (
                "next_execution_gate_can_call_dedicated_actual_http_post_sender_"
                "after_confirmation: "
                f"{_bool_text(result.next_execution_gate_can_call_dedicated_actual_http_post_sender_after_confirmation)}"
            ),
            (
                "next_execution_gate_still_requires_fresh_runtime_read: "
                f"{_bool_text(result.next_execution_gate_still_requires_fresh_runtime_read)}"
            ),
            (
                "next_execution_gate_still_requires_operator_readiness: "
                f"{_bool_text(result.next_execution_gate_still_requires_operator_readiness)}"
            ),
            (
                "next_execution_gate_still_requires_settlement_specific_confirmation: "
                f"{_bool_text(result.next_execution_gate_still_requires_settlement_specific_confirmation)}"
            ),
            f"result_safe_category: {result.result_safe_category}",
            f"blocked_reasons: {blocked}",
            f"recommended_next_step: {result.recommended_next_step}",
        ),
    ) + "\n"


def _input_from_live_enablement(
    result: OfficialSettlementActualPostLiveEnablementResult,
) -> OfficialSettlementActualHttpPostSenderInput:
    return OfficialSettlementActualHttpPostSenderInput(
        official_settlement_no_post_preview_ready=(
            result.official_settlement_no_post_preview_ready
        ),
        official_settlement_executor_preview_ready=(
            result.official_settlement_executor_preview_ready
        ),
        dedicated_settlement_actual_executor_compatibility_ready=(
            result.dedicated_settlement_actual_executor_compatibility_ready
        ),
        dedicated_actual_official_settlement_post_executor_available=(
            result.dedicated_actual_official_settlement_post_executor_available
        ),
        dedicated_actual_official_settlement_transport_boundary_ready=(
            result.dedicated_actual_official_settlement_transport_boundary_ready
        ),
        actual_settlement_post_live_capable_transport_available=(
            result.actual_settlement_post_live_capable_transport_available
        ),
        actual_settlement_post_can_be_allowed_after_fresh_execution_gates=(
            result.actual_settlement_post_can_be_allowed_after_fresh_execution_gates
        ),
        settlement_route_kind=result.settlement_route_kind,
        settlement_route_is_generic_order=result.settlement_route_is_generic_order,
        settlement_route_is_dedicated=result.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=(
            result.generic_order_executor_used_for_settlement
        ),
        live_order_once_used_for_settlement=result.live_order_once_used_for_settlement,
        generic_order_endpoint_used_for_settlement=(
            result.generic_order_endpoint_used_for_settlement
        ),
        one_shot_generic_order_path_used_for_settlement=(
            result.one_shot_generic_order_path_used_for_settlement
        ),
        position_specific_path_used=result.position_specific_path_used,
        position_specific_identifier_safe_handling_ready=(
            result.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=result.position_specific_preview_allowed,
        size_based_preview_allowed=result.size_based_preview_allowed,
        raw_id_value_credential_header_exposure=(
            result.raw_id_value_credential_header_exposure
        ),
    )


def _blocked_reasons(
    snapshot: OfficialSettlementActualHttpPostSenderInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.repository_clean:
        reasons.append("repository_clean_required")
    if not snapshot.head_equals_origin_main:
        reasons.append("head_equals_origin_main_required")
    if not snapshot.credential_presence_available:
        reasons.append("credential_presence_available_required")
    if not snapshot.official_settlement_no_post_preview_ready:
        reasons.append("official_settlement_no_post_preview_not_ready")
    if not snapshot.official_settlement_executor_preview_ready:
        reasons.append("official_settlement_executor_preview_not_ready")
    if not snapshot.dedicated_settlement_actual_executor_compatibility_ready:
        reasons.append("dedicated_settlement_actual_executor_compatibility_not_ready")
    if not snapshot.dedicated_actual_official_settlement_post_executor_available:
        reasons.append("dedicated_actual_official_settlement_post_executor_not_available")
    if not snapshot.dedicated_actual_official_settlement_transport_boundary_ready:
        reasons.append("dedicated_actual_official_settlement_transport_boundary_not_ready")
    if not snapshot.actual_settlement_post_live_capable_transport_available:
        reasons.append("actual_settlement_post_live_capable_transport_not_available")
    if not snapshot.actual_settlement_post_can_be_allowed_after_fresh_execution_gates:
        reasons.append("actual_settlement_post_cannot_be_allowed_after_fresh_gates")
    if not snapshot.dedicated_official_settlement_actual_http_post_sender_confirmed:
        reasons.append("dedicated_actual_http_post_sender_not_confirmed")
    if not snapshot.dedicated_official_settlement_actual_http_post_sender_callable_available:
        reasons.append("dedicated_actual_http_post_sender_callable_not_available")
    if not snapshot.dedicated_official_settlement_actual_http_post_sender_boundary_ready:
        reasons.append("dedicated_actual_http_post_sender_boundary_not_ready")
    sender_uses_official_route = (
        snapshot.dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route
    )
    if not sender_uses_official_route:
        reasons.append("dedicated_sender_must_use_official_settlement_route")
    if snapshot.dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route:
        reasons.append("dedicated_sender_uses_generic_order_route")
    if snapshot.dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor:
        reasons.append("dedicated_sender_uses_generic_order_executor")
    if snapshot.dedicated_official_settlement_actual_http_post_sender_uses_live_order_once:
        reasons.append("dedicated_sender_uses_live_order_once")
    if snapshot.dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order:
        reasons.append("dedicated_sender_uses_one_shot_generic_order")
    if snapshot.dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path:
        reasons.append("dedicated_sender_uses_position_specific_path")
    if snapshot.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        reasons.append("official_size_based_settlement_route_required")
    if snapshot.settlement_route_is_generic_order:
        reasons.append("settlement_route_must_not_be_generic_order")
    if not snapshot.settlement_route_is_dedicated:
        reasons.append("settlement_route_must_be_dedicated")
    if snapshot.generic_order_executor_used_for_settlement:
        reasons.append("generic_order_executor_used_for_settlement")
    if snapshot.live_order_once_used_for_settlement:
        reasons.append("live_order_once_used_for_settlement")
    if snapshot.generic_order_endpoint_used_for_settlement:
        reasons.append("generic_order_endpoint_used_for_settlement")
    if snapshot.one_shot_generic_order_path_used_for_settlement:
        reasons.append("one_shot_generic_order_path_used_for_settlement")
    if snapshot.position_specific_path_used:
        reasons.append("position_specific_path_used")
    if snapshot.position_specific_identifier_safe_handling_ready:
        reasons.append("position_specific_identifier_handling_not_this_step")
    if snapshot.position_specific_preview_allowed:
        reasons.append("position_specific_preview_must_remain_blocked")
    if not snapshot.size_based_preview_allowed:
        reasons.append("size_based_preview_not_allowed")
    if snapshot.runtime_position_status is not PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        reasons.append("runtime_position_status_not_one_position_open")
    if snapshot.position_count_safe != 1:
        reasons.append("position_count_safe_not_1")
    if not snapshot.has_exactly_one_position:
        reasons.append("has_exactly_one_position_required")
    if snapshot.has_multiple_positions:
        reasons.append("has_multiple_positions_blocked")
    if not snapshot.operator_broker_ui_checked:
        reasons.append("operator_broker_ui_checked_required")
    if not snapshot.operator_broker_ui_open_position_visible:
        reasons.append("operator_broker_ui_open_position_visible_required")
    if snapshot.operator_broker_ui_values_or_ids_provided:
        reasons.append("operator_broker_ui_values_or_ids_provided_blocked")
    if not snapshot.operator_can_monitor:
        reasons.append("operator_can_monitor_required")
    if not snapshot.operator_approves_settlement_attempt:
        reasons.append("operator_approves_settlement_attempt_required")
    if not snapshot.sanitized_settlement_preview_shown:
        reasons.append("sanitized_settlement_preview_required")
    if not snapshot.settlement_specific_confirmation_current_turn:
        reasons.append("settlement_specific_confirmation_current_turn_required")
    if not snapshot.settlement_specific_confirmation_exact_match:
        reasons.append("settlement_specific_confirmation_exact_match_required")
    if not snapshot.one_settlement_post_max:
        reasons.append("one_settlement_post_max_required")
    for field_name in _BOOLEAN_BLOCKED_FIELDS:
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.settlement_post_count != 0:
        reasons.append("settlement_post_count_must_remain_0")
    if snapshot.sender_call_count != 0:
        reasons.append("sender_call_count_must_remain_0")
    if snapshot.transport_call_count != 0:
        reasons.append("transport_call_count_must_remain_0")
    if not snapshot.execution_gate_authorization_uses_fake_sender_adapter:
        reasons.append("execution_gate_authorization_must_use_fake_sender_adapter")
    for field_name in (
        "next_execution_gate_still_requires_fresh_runtime_read",
        "next_execution_gate_still_requires_operator_readiness",
        "next_execution_gate_still_requires_settlement_specific_confirmation",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(field_name)
    return tuple(dict.fromkeys(reasons))


def _status_from_reasons(
    reasons: tuple[str, ...],
) -> OfficialSettlementActualHttpPostSenderStatus:
    if not reasons:
        return OfficialSettlementActualHttpPostSenderStatus.READY_NO_POST
    if any(reason.startswith("repository") or reason.startswith("head_") for reason in reasons):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_REPOSITORY
    if any("credential_presence" in reason for reason in reasons):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_CREDENTIAL
    if any(
        reason.startswith("runtime_position")
        or "position_count" in reason
        or reason == "has_exactly_one_position_required"
        or reason == "has_multiple_positions_blocked"
        for reason in reasons
    ):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_POSITION
    if any("operator_" in reason for reason in reasons):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_OPERATOR
    if any("confirmation" in reason for reason in reasons):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_CONFIRMATION
    if any(
        reason in _LIFECYCLE_BLOCKED_REASONS
        or reason.endswith("_must_remain_0")
        or reason.startswith("next_execution_gate_still_requires")
        for reason in reasons
    ):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_LIFECYCLE
    if any(
        "transport" in reason
        or "executor" in reason
        or "compatibility" in reason
        or "preview" in reason
        or "actual_settlement_post" in reason
        for reason in reasons
    ):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_TRANSPORT
    if any(
        "dedicated_sender" in reason or "actual_http_post_sender" in reason
        for reason in reasons
    ):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_SENDER
    if any(
        "generic" in reason
        or "live_order_once" in reason
        or "one_shot" in reason
        or "route" in reason
        or "position_specific" in reason
        for reason in reasons
    ):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_ROUTE
    if any("exposure" in reason or reason == "env_read" for reason in reasons):
        return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_UNSAFE
    return OfficialSettlementActualHttpPostSenderStatus.BLOCKED_ROUTE


def _sender_plan(
    snapshot: OfficialSettlementActualHttpPostSenderInput,
    ready: bool,
) -> OfficialSettlementActualHttpPostSenderPlan:
    return OfficialSettlementActualHttpPostSenderPlan(
        sender_plan_label=SAFE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_CALLABLE_LABEL,
        dedicated_official_settlement_actual_http_post_sender_confirmed=ready,
        dedicated_official_settlement_actual_http_post_sender_callable_available=ready,
        dedicated_official_settlement_actual_http_post_sender_boundary_ready=ready,
        sender_can_be_called_only_after_execution_gate_authorization=ready,
        dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route=ready,
        dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route=False,
        dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor=False,
        dedicated_official_settlement_actual_http_post_sender_uses_live_order_once=False,
        dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order=False,
        dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path=False,
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        one_settlement_post_max=snapshot.one_settlement_post_max,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        entry_post_allowed=False,
        generic_close_allowed=False,
    )


def _fake_sender_adapter(
    snapshot: OfficialSettlementActualHttpPostSenderInput,
) -> FakeOfficialSettlementActualHttpPostSenderAdapter:
    return FakeOfficialSettlementActualHttpPostSenderAdapter(
        fake_sender_adapter_label=(
            SAFE_FAKE_OFFICIAL_SETTLEMENT_ACTUAL_HTTP_POST_SENDER_ADAPTER_LABEL
        ),
        execution_gate_authorization_uses_fake_sender_adapter=(
            snapshot.execution_gate_authorization_uses_fake_sender_adapter
        ),
        execution_gate_authorization_http_post_executed=False,
        simulated_sender_call_count=0,
        simulated_settlement_post_count=0,
        sender_call_count=0,
        transport_call_count=0,
        http_post_executed=False,
        external_api_write_executed=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
    )


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _validate_bool_fields(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        if type(getattr(instance, name)) is not bool:
            raise LiveVerificationValidationError(f"{name} must be bool")


def _validate_non_negative_int(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{name} must be non-negative int")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _require_non_empty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{name} must be non-empty")


_INPUT_BOOL_FIELDS = (
    "repository_clean",
    "head_equals_origin_main",
    "credential_presence_available",
    "official_settlement_no_post_preview_ready",
    "official_settlement_executor_preview_ready",
    "dedicated_settlement_actual_executor_compatibility_ready",
    "dedicated_actual_official_settlement_post_executor_available",
    "dedicated_actual_official_settlement_transport_boundary_ready",
    "actual_settlement_post_live_capable_transport_available",
    "actual_settlement_post_can_be_allowed_after_fresh_execution_gates",
    "dedicated_official_settlement_actual_http_post_sender_confirmed",
    "dedicated_official_settlement_actual_http_post_sender_callable_available",
    "dedicated_official_settlement_actual_http_post_sender_boundary_ready",
    "dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route",
    "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route",
    "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor",
    "dedicated_official_settlement_actual_http_post_sender_uses_live_order_once",
    "dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order",
    "dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "generic_order_executor_used_for_settlement",
    "live_order_once_used_for_settlement",
    "generic_order_endpoint_used_for_settlement",
    "one_shot_generic_order_path_used_for_settlement",
    "position_specific_path_used",
    "position_specific_identifier_safe_handling_ready",
    "position_specific_preview_allowed",
    "size_based_preview_allowed",
    "has_exactly_one_position",
    "has_multiple_positions",
    "operator_broker_ui_checked",
    "operator_broker_ui_open_position_visible",
    "operator_broker_ui_values_or_ids_provided",
    "operator_can_monitor",
    "operator_approves_settlement_attempt",
    "sanitized_settlement_preview_shown",
    "settlement_specific_confirmation_current_turn",
    "settlement_specific_confirmation_exact_match",
    "one_settlement_post_max",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "raw_id_value_credential_header_exposure",
    "execution_gate_authorization_uses_fake_sender_adapter",
    "execution_gate_authorization_http_post_executed",
    "this_step_actual_http_post_sender_invoked",
    "this_step_actual_settlement_post_executed",
    "http_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "live_order_once_executed",
    "external_api_write_executed",
    "env_read",
    "next_execution_gate_still_requires_fresh_runtime_read",
    "next_execution_gate_still_requires_operator_readiness",
    "next_execution_gate_still_requires_settlement_specific_confirmation",
)

_PLAN_BOOL_FIELDS = (
    "dedicated_official_settlement_actual_http_post_sender_confirmed",
    "dedicated_official_settlement_actual_http_post_sender_callable_available",
    "dedicated_official_settlement_actual_http_post_sender_boundary_ready",
    "sender_can_be_called_only_after_execution_gate_authorization",
    "dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route",
    "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route",
    "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor",
    "dedicated_official_settlement_actual_http_post_sender_uses_live_order_once",
    "dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order",
    "dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "one_settlement_post_max",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
)

_FAKE_ADAPTER_BOOL_FIELDS = (
    "execution_gate_authorization_uses_fake_sender_adapter",
    "execution_gate_authorization_http_post_executed",
    "http_post_executed",
    "external_api_write_executed",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
)

_RESULT_BOOL_FIELDS = (
    "dedicated_official_settlement_actual_http_post_sender_confirmed",
    "dedicated_official_settlement_actual_http_post_sender_callable_available",
    "dedicated_official_settlement_actual_http_post_sender_boundary_ready",
    "dedicated_official_settlement_actual_http_post_sender_uses_official_settlement_route",
    "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_route",
    "dedicated_official_settlement_actual_http_post_sender_uses_generic_order_executor",
    "dedicated_official_settlement_actual_http_post_sender_uses_live_order_once",
    "dedicated_official_settlement_actual_http_post_sender_uses_one_shot_generic_order",
    "dedicated_official_settlement_actual_http_post_sender_uses_position_specific_path",
    "actual_settlement_post_live_capable_transport_available",
    "actual_settlement_post_can_be_allowed_after_fresh_execution_gates",
    "execution_gate_authorization_can_reach_dedicated_http_sender",
    "execution_gate_authorization_uses_fake_sender_adapter",
    "execution_gate_authorization_http_post_executed",
    "official_settlement_no_post_preview_ready",
    "official_settlement_executor_preview_ready",
    "dedicated_settlement_actual_executor_compatibility_ready",
    "dedicated_actual_official_settlement_post_executor_available",
    "dedicated_actual_official_settlement_transport_boundary_ready",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "generic_order_executor_used_for_settlement",
    "live_order_once_used_for_settlement",
    "generic_order_endpoint_used_for_settlement",
    "one_shot_generic_order_path_used_for_settlement",
    "position_specific_path_used",
    "position_specific_identifier_safe_handling_ready",
    "position_specific_preview_allowed",
    "size_based_preview_allowed",
    "this_step_actual_http_post_sender_invoked",
    "this_step_actual_settlement_post_executed",
    "http_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "live_order_once_executed",
    "external_api_write_executed",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "ledger_update",
    "receipt_handoff",
    "raw_id_value_credential_header_exposure",
    "env_read",
    "next_execution_gate_can_call_dedicated_actual_http_post_sender_after_confirmation",
    "next_execution_gate_still_requires_fresh_runtime_read",
    "next_execution_gate_still_requires_operator_readiness",
    "next_execution_gate_still_requires_settlement_specific_confirmation",
)

_BOOLEAN_BLOCKED_FIELDS = (
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "raw_id_value_credential_header_exposure",
    "execution_gate_authorization_http_post_executed",
    "this_step_actual_http_post_sender_invoked",
    "this_step_actual_settlement_post_executed",
    "http_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "live_order_once_executed",
    "external_api_write_executed",
    "env_read",
)

_LIFECYCLE_BLOCKED_REASONS = {
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "execution_gate_authorization_must_use_fake_sender_adapter",
    "execution_gate_authorization_http_post_executed",
    "this_step_actual_http_post_sender_invoked",
    "this_step_actual_settlement_post_executed",
    "http_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "live_order_once_executed",
    "external_api_write_executed",
}
