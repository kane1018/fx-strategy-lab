"""Official GMO FX settlement real-network client binding, no POST.

This module adds a settlement-specific concrete client/transport binding that a
later execution gate can call after fresh runtime, operator readiness, and
settlement-specific confirmation. This step exercises that concrete client only
with an injected fake HTTP transport and never performs real HTTP, broker
writes, env reads, generic order execution, live_order_once, ledger, or receipt
work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_real_network_live_sender_adapter_no_post_controlled import (  # noqa: E501
    OfficialSettlementRealNetworkLiveSenderAdapterResult,
    build_official_settlement_real_network_live_sender_adapter_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (  # noqa: E501
    SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET,
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
    SETTLEMENT_SIDE_SEMANTICS_CONFIRMED,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

EXECUTION_STEP_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_NO_POST = (
    "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_NO_POST_C"
)
SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_LABEL = (
    "STEP6G_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_NO_POST"
)
SAFE_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_LABEL = (
    "CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT"
)
SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_TRANSPORT_BINDING_LABEL = (
    "OFFICIAL_SETTLEMENT_REAL_NETWORK_TRANSPORT_BINDING"
)
SAFE_FAKE_HTTP_TRANSPORT_FOR_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_LABEL = (
    "FAKE_HTTP_TRANSPORT_FOR_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_NO_NETWORK"
)
RESULT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST_SANITIZED = (
    "RESULT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST_SANITIZED"
)
RESULT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_NO_POST_SANITIZED = (
    "RESULT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_NO_POST_SANITIZED"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C"
)
NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING = (
    "fix_official_settlement_real_network_client_binding_no_post"
)


class OfficialSettlementRealNetworkClientBindingStatus(str, Enum):
    READY_NO_POST = "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST"
    BLOCKED_REPOSITORY = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_REPOSITORY"
    )
    BLOCKED_CREDENTIAL = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_CREDENTIAL"
    )
    BLOCKED_POSITION = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_POSITION"
    )
    BLOCKED_ROUTE = "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_ROUTE"
    BLOCKED_CLIENT = "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_CLIENT"
    BLOCKED_OPERATOR = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_OPERATOR"
    )
    BLOCKED_CONFIRMATION = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_CONFIRMATION"
    )
    BLOCKED_LIFECYCLE = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_LIFECYCLE"
    )
    BLOCKED_UNSAFE = "OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_UNSAFE"


@dataclass(frozen=True)
class OfficialSettlementRealNetworkClientBindingInput:
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
    concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: (
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_callable_available: (  # noqa: E501
        bool
    ) = True
    concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization: (
        bool
    ) = True
    official_settlement_real_network_client_binding_confirmed: bool = True
    official_settlement_real_network_client_callable_available: bool = True
    official_settlement_real_network_transport_binding_ready: bool = True
    official_settlement_real_network_client_targets_official_settlement_route: (
        bool
    ) = True
    official_settlement_real_network_client_targets_generic_order_route: bool = False
    official_settlement_real_network_client_uses_generic_order_executor: bool = False
    official_settlement_real_network_client_uses_live_order_once: bool = False
    official_settlement_real_network_client_uses_one_shot_generic_order: bool = False
    official_settlement_real_network_client_uses_position_specific_path: bool = False
    fake_no_network_adapter_distinguished_from_real_network_client: bool = True
    real_network_client_accepts_injected_transport: bool = True
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
    symbol_safe_label: str = SUPPORTED_SYMBOL
    settlement_size_safe_label: str = str(SUPPORTED_UNITS)
    settlement_order_type_safe_label: str = SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET
    settlement_side_semantics_safe_label: str = SETTLEMENT_SIDE_SEMANTICS_CONFIRMED
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
    real_network_client_actual_http_post_executed: bool = False
    real_network_client_broker_write_executed: bool = False
    this_step_real_network_client_invoked: bool = False
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
        for field_name in (
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_non_negative_int("position_count_safe", self.position_count_safe)
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_non_negative_int("sender_call_count", self.sender_call_count)
        _validate_non_negative_int("transport_call_count", self.transport_call_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkClientBindingPlan:
    client_binding_plan_label: str
    concrete_client_label: str
    transport_binding_label: str
    official_settlement_real_network_client_binding_confirmed: bool
    official_settlement_real_network_client_callable_available: bool
    official_settlement_real_network_transport_binding_ready: bool
    official_settlement_real_network_client_targets_official_settlement_route: bool
    official_settlement_real_network_client_targets_generic_order_route: bool
    official_settlement_real_network_client_uses_generic_order_executor: bool
    official_settlement_real_network_client_uses_live_order_once: bool
    official_settlement_real_network_client_uses_one_shot_generic_order: bool
    official_settlement_real_network_client_uses_position_specific_path: bool
    real_network_client_binding_can_be_reached_after_execution_gate_authorization: bool
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool
    symbol_safe_label: str
    settlement_size_safe_label: str
    settlement_order_type_safe_label: str
    settlement_side_semantics_safe_label: str
    one_settlement_post_max: bool
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    entry_post_allowed: bool
    generic_close_allowed: bool

    def __post_init__(self) -> None:
        for field_name in (
            "client_binding_plan_label",
            "concrete_client_label",
            "transport_binding_label",
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _PLAN_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkClientBoundary:
    client_boundary_label: str
    transport_binding_label: str
    concrete_client_is_real_network_binding: bool
    concrete_client_is_fake_no_network_adapter: bool
    client_accepts_injected_transport: bool
    transport_binding_ready: bool
    client_targets_official_settlement_route: bool
    client_targets_generic_order_route: bool
    client_uses_generic_order_executor: bool
    client_uses_live_order_once: bool
    client_uses_one_shot_generic_order: bool
    client_uses_position_specific_path: bool
    fake_no_network_adapter_distinguished_from_real_network_client: bool
    default_no_post: bool

    def __post_init__(self) -> None:
        _require_non_empty("client_boundary_label", self.client_boundary_label)
        _require_non_empty("transport_binding_label", self.transport_binding_label)
        _validate_bool_fields(self, _BOUNDARY_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkClientBindingCallResult:
    safe_call_label: str
    real_network_client_code_path_exercised_with_fake_http_transport: bool
    fake_http_transport_used: bool
    fake_http_transport_call_count: int
    real_http_client_call_count: int
    real_network_client_actual_http_post_executed: bool
    real_network_client_broker_write_executed: bool
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
    sanitized_result_category: str

    def __post_init__(self) -> None:
        _require_non_empty("safe_call_label", self.safe_call_label)
        _require_non_empty("sanitized_result_category", self.sanitized_result_category)
        for field_name in (
            "fake_http_transport_call_count",
            "real_http_client_call_count",
            "simulated_settlement_post_count",
            "sender_call_count",
            "transport_call_count",
        ):
            _validate_non_negative_int(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _CALL_RESULT_BOOL_FIELDS)


class OfficialSettlementRealNetworkTransportProtocol(Protocol):
    def transmit_official_settlement(
        self,
        plan: OfficialSettlementRealNetworkClientBindingPlan,
    ) -> OfficialSettlementRealNetworkClientBindingCallResult:
        """Transmit through an injected transport after a later execution gate."""


@dataclass(frozen=True)
class FakeHttpTransportForOfficialSettlementRealNetworkClient:
    fake_http_transport_label: str = (
        SAFE_FAKE_HTTP_TRANSPORT_FOR_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_LABEL
    )

    def __post_init__(self) -> None:
        _require_non_empty("fake_http_transport_label", self.fake_http_transport_label)

    def transmit_official_settlement(
        self,
        plan: OfficialSettlementRealNetworkClientBindingPlan,
    ) -> OfficialSettlementRealNetworkClientBindingCallResult:
        _validate_real_network_client_plan_for_call(plan)
        return OfficialSettlementRealNetworkClientBindingCallResult(
            safe_call_label=self.fake_http_transport_label,
            real_network_client_code_path_exercised_with_fake_http_transport=True,
            fake_http_transport_used=True,
            fake_http_transport_call_count=1,
            real_http_client_call_count=0,
            real_network_client_actual_http_post_executed=False,
            real_network_client_broker_write_executed=False,
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
            sanitized_result_category=(
                RESULT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST_SANITIZED
            ),
        )


@dataclass(frozen=True)
class ConcreteOfficialSettlementRealNetworkClient:
    client_label: str = SAFE_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_LABEL
    is_real_network_client_binding: bool = True
    is_fake_no_network_adapter: bool = False
    accepts_injected_transport: bool = True
    default_no_post: bool = True
    targets_official_settlement_route: bool = True
    targets_generic_order_route: bool = False
    uses_generic_order_executor: bool = False
    uses_live_order_once: bool = False
    uses_one_shot_generic_order: bool = False
    uses_position_specific_path: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("client_label", self.client_label)
        _validate_bool_fields(self, _CONCRETE_CLIENT_BOOL_FIELDS)

    def transmit_after_execution_gate_authorization_with_transport(
        self,
        plan: OfficialSettlementRealNetworkClientBindingPlan,
        transport: OfficialSettlementRealNetworkTransportProtocol,
    ) -> OfficialSettlementRealNetworkClientBindingCallResult:
        """Run the concrete client path with an injected no-network transport."""
        _validate_concrete_real_network_client(self)
        _validate_real_network_client_plan_for_call(plan)
        return transport.transmit_official_settlement(plan)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkClientBindingResult:
    status: OfficialSettlementRealNetworkClientBindingStatus
    safe_client_binding_label: str
    official_settlement_real_network_client_binding_confirmed: bool
    official_settlement_real_network_client_callable_available: bool
    official_settlement_real_network_transport_binding_ready: bool
    official_settlement_real_network_client_targets_official_settlement_route: bool
    official_settlement_real_network_client_targets_generic_order_route: bool
    official_settlement_real_network_client_uses_generic_order_executor: bool
    official_settlement_real_network_client_uses_live_order_once: bool
    official_settlement_real_network_client_uses_one_shot_generic_order: bool
    official_settlement_real_network_client_uses_position_specific_path: bool
    real_network_client_binding_plan: OfficialSettlementRealNetworkClientBindingPlan
    real_network_client_boundary: OfficialSettlementRealNetworkClientBoundary
    concrete_real_network_client: ConcreteOfficialSettlementRealNetworkClient
    fake_http_transport: FakeHttpTransportForOfficialSettlementRealNetworkClient
    real_network_client_call_result: OfficialSettlementRealNetworkClientBindingCallResult
    concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: (
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_callable_available: (  # noqa: E501
        bool
    )
    concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization: (
        bool
    )
    real_network_client_binding_can_be_reached_after_execution_gate_authorization: bool
    next_execution_gate_can_call_real_network_client_after_confirmation: bool
    fake_no_network_adapter_distinguished_from_real_network_client: bool
    real_network_client_accepts_injected_transport: bool
    real_network_client_code_path_exercised_with_fake_http_transport: bool
    fake_http_transport_used: bool
    fake_http_transport_call_count: int
    real_http_client_call_count: int
    real_network_client_actual_http_post_executed: bool
    real_network_client_broker_write_executed: bool
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
    this_step_real_network_client_invoked: bool
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
    next_execution_gate_still_requires_fresh_runtime_read: bool
    next_execution_gate_still_requires_operator_readiness: bool
    next_execution_gate_still_requires_settlement_specific_confirmation: bool
    result_safe_category: str
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, OfficialSettlementRealNetworkClientBindingStatus):
            raise LiveVerificationValidationError(
                "status must be real-network client binding status",
            )
        for field_name in (
            "safe_client_binding_label",
            "settlement_route_kind",
            "result_safe_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        for field_name in (
            "fake_http_transport_call_count",
            "real_http_client_call_count",
            "settlement_post_count",
            "sender_call_count",
            "transport_call_count",
        ):
            _validate_non_negative_int(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_real_network_client_binding_no_post_controlled(
    input_snapshot: OfficialSettlementRealNetworkClientBindingInput | None = None,
    *,
    real_network_adapter_result: (
        OfficialSettlementRealNetworkLiveSenderAdapterResult | None
    ) = None,
) -> OfficialSettlementRealNetworkClientBindingResult:
    """Build and exercise the concrete client binding path with fake transport."""
    snapshot = input_snapshot or _input_from_real_network_adapter_result(
        real_network_adapter_result
        or build_official_settlement_real_network_live_sender_adapter_no_post_controlled(),
    )
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    status = _status_from_reasons(reasons)
    plan = _client_binding_plan(snapshot, ready)
    boundary = _client_boundary(snapshot, ready)
    concrete_client = ConcreteOfficialSettlementRealNetworkClient()
    fake_transport = FakeHttpTransportForOfficialSettlementRealNetworkClient()
    call_result = (
        concrete_client.transmit_after_execution_gate_authorization_with_transport(
            plan,
            fake_transport,
        )
        if ready
        else _blocked_call_result()
    )

    return OfficialSettlementRealNetworkClientBindingResult(
        status=status,
        safe_client_binding_label=SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_LABEL,
        official_settlement_real_network_client_binding_confirmed=(
            snapshot.official_settlement_real_network_client_binding_confirmed and ready
        ),
        official_settlement_real_network_client_callable_available=(
            snapshot.official_settlement_real_network_client_callable_available
            and ready
        ),
        official_settlement_real_network_transport_binding_ready=(
            snapshot.official_settlement_real_network_transport_binding_ready and ready
        ),
        official_settlement_real_network_client_targets_official_settlement_route=(
            snapshot.official_settlement_real_network_client_targets_official_settlement_route
            and ready
        ),
        official_settlement_real_network_client_targets_generic_order_route=False,
        official_settlement_real_network_client_uses_generic_order_executor=False,
        official_settlement_real_network_client_uses_live_order_once=False,
        official_settlement_real_network_client_uses_one_shot_generic_order=False,
        official_settlement_real_network_client_uses_position_specific_path=False,
        real_network_client_binding_plan=plan,
        real_network_client_boundary=boundary,
        concrete_real_network_client=concrete_client,
        fake_http_transport=fake_transport,
        real_network_client_call_result=call_result,
        concrete_real_network_official_settlement_live_http_sender_adapter_confirmed=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed
            and ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_callable_available=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
            and ready
        ),
        concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization=(
            snapshot.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization
            and ready
        ),
        real_network_client_binding_can_be_reached_after_execution_gate_authorization=(
            ready
        ),
        next_execution_gate_can_call_real_network_client_after_confirmation=ready,
        fake_no_network_adapter_distinguished_from_real_network_client=(
            snapshot.fake_no_network_adapter_distinguished_from_real_network_client
            and ready
        ),
        real_network_client_accepts_injected_transport=(
            snapshot.real_network_client_accepts_injected_transport and ready
        ),
        real_network_client_code_path_exercised_with_fake_http_transport=(
            call_result.real_network_client_code_path_exercised_with_fake_http_transport
        ),
        fake_http_transport_used=call_result.fake_http_transport_used,
        fake_http_transport_call_count=call_result.fake_http_transport_call_count,
        real_http_client_call_count=call_result.real_http_client_call_count,
        real_network_client_actual_http_post_executed=False,
        real_network_client_broker_write_executed=False,
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
        this_step_real_network_client_invoked=False,
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
            call_result.raw_request_exposed
            or call_result.raw_response_exposed
            or call_result.broker_api_response_exposed
            or call_result.id_exposed
            or call_result.credential_value_exposed
            or call_result.signature_value_exposed
            or call_result.headers_value_exposed
            or snapshot.raw_id_value_credential_header_exposure
        ),
        env_read=False,
        next_execution_gate_still_requires_fresh_runtime_read=True,
        next_execution_gate_still_requires_operator_readiness=True,
        next_execution_gate_still_requires_settlement_specific_confirmation=True,
        result_safe_category=call_result.sanitized_result_category,
        blocked_reasons=reasons,
        recommended_next_step=(
            NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE
            if ready
            else NEXT_STEP_FIX_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING
        ),
    )


def render_official_settlement_real_network_client_binding_no_post_markdown(
    result: OfficialSettlementRealNetworkClientBindingResult,
) -> str:
    """Render a sanitized client binding summary without raw request details."""
    lines = [
        "# Official Settlement Real-Network Client Binding No-POST",
        "",
        f"- status: {result.status.value}",
        (
            "- official_settlement_real_network_client_binding_confirmed: "
            f"{_bool_text(result.official_settlement_real_network_client_binding_confirmed)}"
        ),
        (
            "- official_settlement_real_network_client_callable_available: "
            f"{_bool_text(result.official_settlement_real_network_client_callable_available)}"
        ),
        (
            "- official_settlement_real_network_transport_binding_ready: "
            f"{_bool_text(result.official_settlement_real_network_transport_binding_ready)}"
        ),
        (
            "- official_settlement_real_network_client_targets_official_settlement_route: "
            f"{_bool_text(result.official_settlement_real_network_client_targets_official_settlement_route)}"
        ),
        (
            "- official_settlement_real_network_client_targets_generic_order_route: "
            f"{_bool_text(result.official_settlement_real_network_client_targets_generic_order_route)}"
        ),
        (
            "- official_settlement_real_network_client_uses_generic_order_executor: "
            f"{_bool_text(result.official_settlement_real_network_client_uses_generic_order_executor)}"
        ),
        (
            "- official_settlement_real_network_client_uses_live_order_once: "
            f"{_bool_text(result.official_settlement_real_network_client_uses_live_order_once)}"
        ),
        (
            "- official_settlement_real_network_client_uses_one_shot_generic_order: "
            f"{_bool_text(result.official_settlement_real_network_client_uses_one_shot_generic_order)}"
        ),
        (
            "- official_settlement_real_network_client_uses_position_specific_path: "
            f"{_bool_text(result.official_settlement_real_network_client_uses_position_specific_path)}"
        ),
        (
            "- real_network_client_binding_can_be_reached_after_execution_gate_authorization: "
            f"{_bool_text(result.real_network_client_binding_can_be_reached_after_execution_gate_authorization)}"
        ),
        (
            "- next_execution_gate_can_call_real_network_client_after_confirmation: "
            f"{_bool_text(result.next_execution_gate_can_call_real_network_client_after_confirmation)}"
        ),
        (
            "- real_network_client_code_path_exercised_with_fake_http_transport: "
            f"{_bool_text(result.real_network_client_code_path_exercised_with_fake_http_transport)}"
        ),
        f"- fake_http_transport_used: {_bool_text(result.fake_http_transport_used)}",
        f"- fake_http_transport_call_count: {result.fake_http_transport_call_count}",
        f"- real_http_client_call_count: {result.real_http_client_call_count}",
        (
            "- real_network_client_actual_http_post_executed: "
            f"{_bool_text(result.real_network_client_actual_http_post_executed)}"
        ),
        (
            "- real_network_client_broker_write_executed: "
            f"{_bool_text(result.real_network_client_broker_write_executed)}"
        ),
        f"- settlement_route_kind: {result.settlement_route_kind}",
        (
            "- settlement_route_is_generic_order: "
            f"{_bool_text(result.settlement_route_is_generic_order)}"
        ),
        (
            "- settlement_route_is_dedicated: "
            f"{_bool_text(result.settlement_route_is_dedicated)}"
        ),
        (
            "- generic_order_executor_used_for_settlement: "
            f"{_bool_text(result.generic_order_executor_used_for_settlement)}"
        ),
        (
            "- live_order_once_used_for_settlement: "
            f"{_bool_text(result.live_order_once_used_for_settlement)}"
        ),
        (
            "- one_shot_generic_order_path_used_for_settlement: "
            f"{_bool_text(result.one_shot_generic_order_path_used_for_settlement)}"
        ),
        f"- position_specific_path_used: {_bool_text(result.position_specific_path_used)}",
        f"- this_step_real_network_client_invoked: "
        f"{_bool_text(result.this_step_real_network_client_invoked)}",
        (
            "- this_step_actual_http_post_sender_invoked: "
            f"{_bool_text(result.this_step_actual_http_post_sender_invoked)}"
        ),
        (
            "- this_step_actual_settlement_post_executed: "
            f"{_bool_text(result.this_step_actual_settlement_post_executed)}"
        ),
        f"- settlement_post_count: {result.settlement_post_count}",
        f"- sender_call_count: {result.sender_call_count}",
        f"- transport_call_count: {result.transport_call_count}",
        f"- http_post_executed: {_bool_text(result.http_post_executed)}",
        f"- entry_post_executed: {_bool_text(result.entry_post_executed)}",
        (
            "- generic_close_post_executed: "
            f"{_bool_text(result.generic_close_post_executed)}"
        ),
        f"- live_order_once_executed: {_bool_text(result.live_order_once_executed)}",
        f"- retry_allowed: {_bool_text(result.retry_allowed)}",
        f"- repost_allowed: {_bool_text(result.repost_allowed)}",
        f"- second_settlement_allowed: {_bool_text(result.second_settlement_allowed)}",
        f"- ledger_update: {_bool_text(result.ledger_update)}",
        f"- receipt_handoff: {_bool_text(result.receipt_handoff)}",
        (
            "- raw_id_value_credential_header_exposure: "
            f"{_bool_text(result.raw_id_value_credential_header_exposure)}"
        ),
        f"- env_read: {_bool_text(result.env_read)}",
        (
            "- next_execution_gate_still_requires_fresh_runtime_read: "
            f"{_bool_text(result.next_execution_gate_still_requires_fresh_runtime_read)}"
        ),
        (
            "- next_execution_gate_still_requires_operator_readiness: "
            f"{_bool_text(result.next_execution_gate_still_requires_operator_readiness)}"
        ),
        (
            "- next_execution_gate_still_requires_settlement_specific_confirmation: "
            f"{_bool_text(result.next_execution_gate_still_requires_settlement_specific_confirmation)}"
        ),
        f"- result_safe_category: {result.result_safe_category}",
        f"- blocked_reasons: {_safe_reasons_text(result.blocked_reasons)}",
        f"- recommended_next_step: {result.recommended_next_step}",
    ]
    return "\n".join(lines)


def _input_from_real_network_adapter_result(
    result: OfficialSettlementRealNetworkLiveSenderAdapterResult,
) -> OfficialSettlementRealNetworkClientBindingInput:
    return OfficialSettlementRealNetworkClientBindingInput(
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
        dedicated_official_settlement_actual_http_post_sender_confirmed=(
            result.dedicated_official_settlement_actual_http_post_sender_confirmed
        ),
        dedicated_official_settlement_actual_http_post_sender_callable_available=(
            result.dedicated_official_settlement_actual_http_post_sender_callable_available
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_confirmed=(
            result.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_callable_available=(
            result.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
        ),
        concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization=(
            result.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization
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
        env_read=result.env_read,
    )


def _client_binding_plan(
    snapshot: OfficialSettlementRealNetworkClientBindingInput,
    ready: bool,
) -> OfficialSettlementRealNetworkClientBindingPlan:
    return OfficialSettlementRealNetworkClientBindingPlan(
        client_binding_plan_label=(
            SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_BINDING_LABEL
        ),
        concrete_client_label=SAFE_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_LABEL,
        transport_binding_label=SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_TRANSPORT_BINDING_LABEL,
        official_settlement_real_network_client_binding_confirmed=(
            snapshot.official_settlement_real_network_client_binding_confirmed
            and ready
        ),
        official_settlement_real_network_client_callable_available=(
            snapshot.official_settlement_real_network_client_callable_available
            and ready
        ),
        official_settlement_real_network_transport_binding_ready=(
            snapshot.official_settlement_real_network_transport_binding_ready and ready
        ),
        official_settlement_real_network_client_targets_official_settlement_route=(
            snapshot.official_settlement_real_network_client_targets_official_settlement_route
            and ready
        ),
        official_settlement_real_network_client_targets_generic_order_route=False,
        official_settlement_real_network_client_uses_generic_order_executor=False,
        official_settlement_real_network_client_uses_live_order_once=False,
        official_settlement_real_network_client_uses_one_shot_generic_order=False,
        official_settlement_real_network_client_uses_position_specific_path=False,
        real_network_client_binding_can_be_reached_after_execution_gate_authorization=(
            ready
        ),
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        symbol_safe_label=snapshot.symbol_safe_label,
        settlement_size_safe_label=snapshot.settlement_size_safe_label,
        settlement_order_type_safe_label=snapshot.settlement_order_type_safe_label,
        settlement_side_semantics_safe_label=(
            snapshot.settlement_side_semantics_safe_label
        ),
        one_settlement_post_max=snapshot.one_settlement_post_max,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        entry_post_allowed=False,
        generic_close_allowed=False,
    )


def _client_boundary(
    snapshot: OfficialSettlementRealNetworkClientBindingInput,
    ready: bool,
) -> OfficialSettlementRealNetworkClientBoundary:
    return OfficialSettlementRealNetworkClientBoundary(
        client_boundary_label=SAFE_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_CLIENT_LABEL,
        transport_binding_label=SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_TRANSPORT_BINDING_LABEL,
        concrete_client_is_real_network_binding=ready,
        concrete_client_is_fake_no_network_adapter=False,
        client_accepts_injected_transport=(
            snapshot.real_network_client_accepts_injected_transport and ready
        ),
        transport_binding_ready=(
            snapshot.official_settlement_real_network_transport_binding_ready and ready
        ),
        client_targets_official_settlement_route=(
            snapshot.official_settlement_real_network_client_targets_official_settlement_route
            and ready
        ),
        client_targets_generic_order_route=False,
        client_uses_generic_order_executor=False,
        client_uses_live_order_once=False,
        client_uses_one_shot_generic_order=False,
        client_uses_position_specific_path=False,
        fake_no_network_adapter_distinguished_from_real_network_client=(
            snapshot.fake_no_network_adapter_distinguished_from_real_network_client
            and ready
        ),
        default_no_post=True,
    )


def _blocked_call_result() -> OfficialSettlementRealNetworkClientBindingCallResult:
    return OfficialSettlementRealNetworkClientBindingCallResult(
        safe_call_label="BLOCKED_NO_CALL_NO_POST",
        real_network_client_code_path_exercised_with_fake_http_transport=False,
        fake_http_transport_used=False,
        fake_http_transport_call_count=0,
        real_http_client_call_count=0,
        real_network_client_actual_http_post_executed=False,
        real_network_client_broker_write_executed=False,
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
        sanitized_result_category=(
            RESULT_REAL_NETWORK_CLIENT_BINDING_BLOCKED_NO_POST_SANITIZED
        ),
    )


def _blocked_reasons(
    snapshot: OfficialSettlementRealNetworkClientBindingInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.repository_clean:
        reasons.append("repository_clean_required")
    if not snapshot.head_equals_origin_main:
        reasons.append("head_equals_origin_main_required")
    if not snapshot.credential_presence_available:
        reasons.append("credential_presence_available_required")
    for field_name in (
        "official_settlement_no_post_preview_ready",
        "official_settlement_executor_preview_ready",
        "dedicated_settlement_actual_executor_compatibility_ready",
        "dedicated_actual_official_settlement_post_executor_available",
        "dedicated_actual_official_settlement_transport_boundary_ready",
        "actual_settlement_post_live_capable_transport_available",
        "actual_settlement_post_can_be_allowed_after_fresh_execution_gates",
        "dedicated_official_settlement_actual_http_post_sender_confirmed",
        "dedicated_official_settlement_actual_http_post_sender_callable_available",
        "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
        "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
        "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization",
        "official_settlement_real_network_client_binding_confirmed",
        "official_settlement_real_network_client_callable_available",
        "official_settlement_real_network_transport_binding_ready",
        "official_settlement_real_network_client_targets_official_settlement_route",
        "fake_no_network_adapter_distinguished_from_real_network_client",
        "real_network_client_accepts_injected_transport",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_required")
    for field_name in (
        "official_settlement_real_network_client_targets_generic_order_route",
        "official_settlement_real_network_client_uses_generic_order_executor",
        "official_settlement_real_network_client_uses_live_order_once",
        "official_settlement_real_network_client_uses_one_shot_generic_order",
        "official_settlement_real_network_client_uses_position_specific_path",
        "settlement_route_is_generic_order",
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "generic_order_endpoint_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_used",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        reasons.append("settlement_route_kind_not_official_size_based")
    if not snapshot.settlement_route_is_dedicated:
        reasons.append("settlement_route_is_dedicated_required")
    if snapshot.position_specific_identifier_safe_handling_ready:
        reasons.append("position_specific_identifier_safe_handling_must_remain_false")
    if snapshot.position_specific_preview_allowed:
        reasons.append("position_specific_preview_must_remain_blocked")
    if not snapshot.size_based_preview_allowed:
        reasons.append("size_based_preview_required")
    if snapshot.runtime_position_status is not PositionReadOnlyControlledStatus.ONE_POSITION_OPEN:
        reasons.append("runtime_position_status_not_one_position_open")
    if snapshot.position_count_safe != 1:
        reasons.append("position_count_safe_not_1")
    if not snapshot.has_exactly_one_position:
        reasons.append("has_exactly_one_position_required")
    if snapshot.has_multiple_positions:
        reasons.append("has_multiple_positions_blocked")
    for field_name in (
        "operator_broker_ui_checked",
        "operator_broker_ui_open_position_visible",
        "operator_can_monitor",
        "operator_approves_settlement_attempt",
        "sanitized_settlement_preview_shown",
        "settlement_specific_confirmation_current_turn",
        "settlement_specific_confirmation_exact_match",
        "one_settlement_post_max",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_required")
    if snapshot.operator_broker_ui_values_or_ids_provided:
        reasons.append("operator_broker_ui_values_or_ids_provided")
    for field_name in (
        "retry_allowed",
        "repost_allowed",
        "second_settlement_allowed",
        "entry_post_allowed",
        "generic_close_allowed",
        "ledger_update_allowed",
        "receipt_handoff_allowed",
        "raw_id_value_credential_header_exposure",
        "real_network_client_actual_http_post_executed",
        "real_network_client_broker_write_executed",
        "this_step_real_network_client_invoked",
        "this_step_actual_http_post_sender_invoked",
        "this_step_actual_settlement_post_executed",
        "http_post_executed",
        "entry_post_executed",
        "generic_close_post_executed",
        "live_order_once_executed",
        "external_api_write_executed",
        "env_read",
    ):
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    for field_name in ("settlement_post_count", "sender_call_count", "transport_call_count"):
        if getattr(snapshot, field_name) != 0:
            reasons.append(f"{field_name}_must_be_0")
    for field_name in (
        "next_execution_gate_still_requires_fresh_runtime_read",
        "next_execution_gate_still_requires_operator_readiness",
        "next_execution_gate_still_requires_settlement_specific_confirmation",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_required")
    return tuple(reasons)


def _status_from_reasons(
    reasons: tuple[str, ...],
) -> OfficialSettlementRealNetworkClientBindingStatus:
    if not reasons:
        return OfficialSettlementRealNetworkClientBindingStatus.READY_NO_POST
    if any("repository" in reason or "head_equals" in reason for reason in reasons):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_REPOSITORY
    if any("credential_presence" in reason for reason in reasons):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_CREDENTIAL
    if any("operator" in reason for reason in reasons):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_OPERATOR
    if any("position" in reason or "multiple" in reason for reason in reasons):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_POSITION
    if any(
        "confirmation" in reason or "sanitized_settlement_preview" in reason
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_CONFIRMATION
    if any(
        reason.endswith("_allowed")
        or reason.endswith("_executed")
        or reason.endswith("_invoked")
        or reason.endswith("_must_be_0")
        or reason == "env_read"
        or reason == "real_network_client_broker_write_executed"
        or reason == "raw_id_value_credential_header_exposure"
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_LIFECYCLE
    if any(
        "route" in reason
        or "generic" in reason
        or "live_order_once" in reason
        or "one_shot" in reason
        or "official_settlement_no_post_preview" in reason
        or "official_settlement_executor_preview" in reason
        or "size_based_preview" in reason
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_ROUTE
    if any(
        "client" in reason
        or "transport" in reason
        or "adapter" in reason
        or "executor" in reason
        or "live_capable" in reason
        or "sender" in reason
        or "actual_http_post_sender" in reason
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_CLIENT
    if any(
        "retry" in reason
        or "repost" in reason
        or "settlement" in reason
        or "ledger" in reason
        or "receipt" in reason
        or "post" in reason
        or "http" in reason
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_LIFECYCLE
    return OfficialSettlementRealNetworkClientBindingStatus.BLOCKED_UNSAFE


def _validate_real_network_client_plan_for_call(
    plan: OfficialSettlementRealNetworkClientBindingPlan,
) -> None:
    if not plan.official_settlement_real_network_client_binding_confirmed:
        raise LiveVerificationValidationError("real-network client binding not confirmed")
    if not plan.official_settlement_real_network_client_callable_available:
        raise LiveVerificationValidationError("real-network client callable unavailable")
    if not plan.official_settlement_real_network_transport_binding_ready:
        raise LiveVerificationValidationError("real-network transport binding unavailable")
    if not plan.real_network_client_binding_can_be_reached_after_execution_gate_authorization:
        raise LiveVerificationValidationError("execution gate cannot reach client binding")
    if not plan.official_settlement_real_network_client_targets_official_settlement_route:
        raise LiveVerificationValidationError("official settlement route required")
    if plan.official_settlement_real_network_client_targets_generic_order_route:
        raise LiveVerificationValidationError("generic order route forbidden")
    if plan.official_settlement_real_network_client_uses_generic_order_executor:
        raise LiveVerificationValidationError("generic order executor forbidden")
    if plan.official_settlement_real_network_client_uses_live_order_once:
        raise LiveVerificationValidationError("live_order_once forbidden")
    if plan.official_settlement_real_network_client_uses_one_shot_generic_order:
        raise LiveVerificationValidationError("one-shot generic order forbidden")
    if plan.official_settlement_real_network_client_uses_position_specific_path:
        raise LiveVerificationValidationError("position-specific path forbidden")
    if plan.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        raise LiveVerificationValidationError("settlement route must be official size-based")
    if plan.settlement_route_is_generic_order:
        raise LiveVerificationValidationError("generic settlement route forbidden")
    if not plan.settlement_route_is_dedicated:
        raise LiveVerificationValidationError("dedicated settlement route required")
    if not plan.one_settlement_post_max:
        raise LiveVerificationValidationError("one settlement POST max required")
    for field_name in (
        "retry_allowed",
        "repost_allowed",
        "second_settlement_allowed",
        "entry_post_allowed",
        "generic_close_allowed",
    ):
        if getattr(plan, field_name):
            raise LiveVerificationValidationError(f"{field_name} forbidden")


def _validate_concrete_real_network_client(
    client: ConcreteOfficialSettlementRealNetworkClient,
) -> None:
    if not client.is_real_network_client_binding:
        raise LiveVerificationValidationError("client must be real-network binding")
    if client.is_fake_no_network_adapter:
        raise LiveVerificationValidationError("client must not be fake adapter")
    if not client.accepts_injected_transport:
        raise LiveVerificationValidationError("client must accept injected transport")
    if not client.default_no_post:
        raise LiveVerificationValidationError("client must default to no-POST")
    if not client.targets_official_settlement_route:
        raise LiveVerificationValidationError("client must target official settlement route")
    if client.targets_generic_order_route:
        raise LiveVerificationValidationError("generic order route forbidden")
    if client.uses_generic_order_executor:
        raise LiveVerificationValidationError("generic order executor forbidden")
    if client.uses_live_order_once:
        raise LiveVerificationValidationError("live_order_once forbidden")
    if client.uses_one_shot_generic_order:
        raise LiveVerificationValidationError("one-shot generic order forbidden")
    if client.uses_position_specific_path:
        raise LiveVerificationValidationError("position-specific path forbidden")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _safe_reasons_text(reasons: tuple[str, ...]) -> str:
    return "none" if not reasons else ",".join(reasons)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


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
    "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
    "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
    "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization",
    "official_settlement_real_network_client_binding_confirmed",
    "official_settlement_real_network_client_callable_available",
    "official_settlement_real_network_transport_binding_ready",
    "official_settlement_real_network_client_targets_official_settlement_route",
    "official_settlement_real_network_client_targets_generic_order_route",
    "official_settlement_real_network_client_uses_generic_order_executor",
    "official_settlement_real_network_client_uses_live_order_once",
    "official_settlement_real_network_client_uses_one_shot_generic_order",
    "official_settlement_real_network_client_uses_position_specific_path",
    "fake_no_network_adapter_distinguished_from_real_network_client",
    "real_network_client_accepts_injected_transport",
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
    "real_network_client_actual_http_post_executed",
    "real_network_client_broker_write_executed",
    "this_step_real_network_client_invoked",
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
    "official_settlement_real_network_client_binding_confirmed",
    "official_settlement_real_network_client_callable_available",
    "official_settlement_real_network_transport_binding_ready",
    "official_settlement_real_network_client_targets_official_settlement_route",
    "official_settlement_real_network_client_targets_generic_order_route",
    "official_settlement_real_network_client_uses_generic_order_executor",
    "official_settlement_real_network_client_uses_live_order_once",
    "official_settlement_real_network_client_uses_one_shot_generic_order",
    "official_settlement_real_network_client_uses_position_specific_path",
    "real_network_client_binding_can_be_reached_after_execution_gate_authorization",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "one_settlement_post_max",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
)
_BOUNDARY_BOOL_FIELDS = (
    "concrete_client_is_real_network_binding",
    "concrete_client_is_fake_no_network_adapter",
    "client_accepts_injected_transport",
    "transport_binding_ready",
    "client_targets_official_settlement_route",
    "client_targets_generic_order_route",
    "client_uses_generic_order_executor",
    "client_uses_live_order_once",
    "client_uses_one_shot_generic_order",
    "client_uses_position_specific_path",
    "fake_no_network_adapter_distinguished_from_real_network_client",
    "default_no_post",
)
_CALL_RESULT_BOOL_FIELDS = (
    "real_network_client_code_path_exercised_with_fake_http_transport",
    "fake_http_transport_used",
    "real_network_client_actual_http_post_executed",
    "real_network_client_broker_write_executed",
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
_CONCRETE_CLIENT_BOOL_FIELDS = (
    "is_real_network_client_binding",
    "is_fake_no_network_adapter",
    "accepts_injected_transport",
    "default_no_post",
    "targets_official_settlement_route",
    "targets_generic_order_route",
    "uses_generic_order_executor",
    "uses_live_order_once",
    "uses_one_shot_generic_order",
    "uses_position_specific_path",
)
_RESULT_BOOL_FIELDS = (
    "official_settlement_real_network_client_binding_confirmed",
    "official_settlement_real_network_client_callable_available",
    "official_settlement_real_network_transport_binding_ready",
    "official_settlement_real_network_client_targets_official_settlement_route",
    "official_settlement_real_network_client_targets_generic_order_route",
    "official_settlement_real_network_client_uses_generic_order_executor",
    "official_settlement_real_network_client_uses_live_order_once",
    "official_settlement_real_network_client_uses_one_shot_generic_order",
    "official_settlement_real_network_client_uses_position_specific_path",
    "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
    "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
    "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization",
    "real_network_client_binding_can_be_reached_after_execution_gate_authorization",
    "next_execution_gate_can_call_real_network_client_after_confirmation",
    "fake_no_network_adapter_distinguished_from_real_network_client",
    "real_network_client_accepts_injected_transport",
    "real_network_client_code_path_exercised_with_fake_http_transport",
    "fake_http_transport_used",
    "real_network_client_actual_http_post_executed",
    "real_network_client_broker_write_executed",
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
    "this_step_real_network_client_invoked",
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
    "next_execution_gate_still_requires_fresh_runtime_read",
    "next_execution_gate_still_requires_operator_readiness",
    "next_execution_gate_still_requires_settlement_specific_confirmation",
)

__all__ = [
    "RESULT_REAL_NETWORK_CLIENT_BINDING_READY_NO_POST_SANITIZED",
    "ConcreteOfficialSettlementRealNetworkClient",
    "FakeHttpTransportForOfficialSettlementRealNetworkClient",
    "OfficialSettlementRealNetworkClientBindingInput",
    "OfficialSettlementRealNetworkClientBindingResult",
    "OfficialSettlementRealNetworkClientBindingStatus",
    "build_official_settlement_real_network_client_binding_no_post_controlled",
    "render_official_settlement_real_network_client_binding_no_post_markdown",
]
