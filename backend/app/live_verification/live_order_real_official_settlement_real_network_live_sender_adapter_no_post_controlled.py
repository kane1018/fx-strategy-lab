"""Official GMO FX settlement real-network live sender adapter, no POST.

This module adds the settlement-specific concrete real-network adapter boundary
that a later execution gate can target after fresh runtime, operator readiness,
and settlement-specific confirmation. The concrete adapter delegates to an
injected real-network client protocol, but this step injects only a fake client
and never performs real HTTP, broker writes, env reads, generic order execution,
live_order_once, ledger, or receipt work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_live_http_sender_adapter_no_post_controlled import (  # noqa: E501
    OfficialSettlementLiveHttpSenderAdapterResult,
    build_official_settlement_live_http_sender_adapter_no_post_controlled,
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

EXECUTION_STEP_OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_NO_POST = (
    "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_NO_POST_C"
)
SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_LABEL = (
    "STEP6G_OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_NO_POST"
)
SAFE_CONCRETE_REAL_NETWORK_OFFICIAL_SETTLEMENT_LIVE_SENDER_ADAPTER_LABEL = (
    "CONCRETE_REAL_NETWORK_OFFICIAL_SETTLEMENT_LIVE_SENDER_ADAPTER"
)
SAFE_FAKE_CLIENT_FOR_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_SENDER_LABEL = (
    "FAKE_CLIENT_FOR_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_SENDER_NO_NETWORK"
)
RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_READY_NO_POST_SANITIZED = (
    "RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_READY_NO_POST_SANITIZED"
)
RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_NO_POST_SANITIZED = (
    "RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_NO_POST_SANITIZED"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C"
)
NEXT_STEP_FIX_REAL_NETWORK_LIVE_SENDER_ADAPTER = (
    "fix_official_settlement_real_network_live_sender_adapter_no_post"
)


class OfficialSettlementRealNetworkLiveSenderAdapterStatus(str, Enum):
    READY_NO_POST = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_READY_NO_POST"
    )
    BLOCKED_REPOSITORY = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_REPOSITORY"
    )
    BLOCKED_CREDENTIAL = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_CREDENTIAL"
    )
    BLOCKED_POSITION = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_POSITION"
    )
    BLOCKED_ROUTE = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_ROUTE"
    )
    BLOCKED_SENDER = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_SENDER"
    )
    BLOCKED_OPERATOR = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_OPERATOR"
    )
    BLOCKED_CONFIRMATION = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_CONFIRMATION"
    )
    BLOCKED_LIFECYCLE = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_LIFECYCLE"
    )
    BLOCKED_UNSAFE = (
        "OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_UNSAFE"
    )


@dataclass(frozen=True)
class OfficialSettlementRealNetworkLiveSenderAdapterInput:
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
    dedicated_official_settlement_live_http_sender_adapter_confirmed: bool = True
    dedicated_official_settlement_live_http_sender_adapter_callable_available: (
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: (
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_callable_available: (  # noqa: E501
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready: (  # noqa: E501
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route: (  # noqa: E501
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route: (  # noqa: E501
        bool
    ) = False
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor: (  # noqa: E501
        bool
    ) = False
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once: (  # noqa: E501
        bool
    ) = False
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order: (  # noqa: E501
        bool
    ) = False
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path: (  # noqa: E501
        bool
    ) = False
    fake_no_network_adapter_distinguished_from_concrete_adapter: bool = True
    concrete_adapter_accepts_injected_real_network_client: bool = True
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
    fake_http_client_used: bool = True
    concrete_real_network_adapter_code_path_exercised_with_fake_http_client: (
        bool
    ) = True
    concrete_real_network_adapter_real_http_post_executed: bool = False
    concrete_real_network_adapter_broker_write_executed: bool = False
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
class OfficialSettlementRealNetworkLiveSenderAdapterPlan:
    adapter_plan_label: str
    concrete_adapter_label: str
    concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: (
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_callable_available: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready: (  # noqa: E501
        bool
    )
    concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization: (
        bool
    )
    fake_no_network_adapter_distinguished_from_concrete_adapter: bool
    concrete_adapter_accepts_injected_real_network_client: bool
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path: (  # noqa: E501
        bool
    )
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
    ledger_update_allowed: bool
    receipt_handoff_allowed: bool
    raw_id_value_credential_header_exposure: bool

    def __post_init__(self) -> None:
        for field_name in (
            "adapter_plan_label",
            "concrete_adapter_label",
            "settlement_route_kind",
            "symbol_safe_label",
            "settlement_size_safe_label",
            "settlement_order_type_safe_label",
            "settlement_side_semantics_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _PLAN_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkLiveSenderAdapterBoundary:
    boundary_label: str
    concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready: (  # noqa: E501
        bool
    )
    adapter_is_concrete_real_network: bool
    adapter_is_fake_no_network_adapter: bool
    fake_no_network_adapter_distinguished_from_concrete_adapter: bool
    adapter_accepts_injected_real_network_client: bool
    adapter_uses_official_settlement_route: bool
    adapter_uses_generic_order_route: bool
    adapter_uses_generic_order_executor: bool
    adapter_uses_live_order_once: bool
    adapter_uses_one_shot_generic_order: bool
    adapter_uses_position_specific_path: bool
    adapter_requires_position_identifier: bool
    adapter_allows_retry: bool
    adapter_allows_repost: bool
    adapter_allows_second_settlement: bool
    adapter_default_no_post: bool

    def __post_init__(self) -> None:
        _require_non_empty("boundary_label", self.boundary_label)
        _validate_bool_fields(self, _BOUNDARY_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkLiveSenderAdapterCallResult:
    safe_call_label: str
    concrete_real_network_adapter_code_path_exercised_with_fake_http_client: bool
    fake_http_client_used: bool
    fake_http_client_call_count: int
    real_http_client_call_count: int
    concrete_real_network_adapter_real_http_post_executed: bool
    concrete_real_network_adapter_broker_write_executed: bool
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
            "fake_http_client_call_count",
            "real_http_client_call_count",
            "simulated_settlement_post_count",
            "sender_call_count",
            "transport_call_count",
        ):
            _validate_non_negative_int(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _CALL_RESULT_BOOL_FIELDS)


class OfficialSettlementRealNetworkClientProtocol(Protocol):
    def transmit_official_settlement_real_network(
        self,
        plan: OfficialSettlementRealNetworkLiveSenderAdapterPlan,
    ) -> OfficialSettlementRealNetworkLiveSenderAdapterCallResult:
        """Transmit through an injected client after a later execution gate."""


@dataclass(frozen=True)
class FakeHttpClientForConcreteOfficialSettlementRealNetworkSender:
    fake_http_client_label: str = (
        SAFE_FAKE_CLIENT_FOR_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_SENDER_LABEL
    )

    def __post_init__(self) -> None:
        _require_non_empty("fake_http_client_label", self.fake_http_client_label)

    def transmit_official_settlement_real_network(
        self,
        plan: OfficialSettlementRealNetworkLiveSenderAdapterPlan,
    ) -> OfficialSettlementRealNetworkLiveSenderAdapterCallResult:
        _validate_real_network_adapter_plan_for_call(plan)
        return OfficialSettlementRealNetworkLiveSenderAdapterCallResult(
            safe_call_label=self.fake_http_client_label,
            concrete_real_network_adapter_code_path_exercised_with_fake_http_client=True,
            fake_http_client_used=True,
            fake_http_client_call_count=1,
            real_http_client_call_count=0,
            concrete_real_network_adapter_real_http_post_executed=False,
            concrete_real_network_adapter_broker_write_executed=False,
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
                RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_READY_NO_POST_SANITIZED
            ),
        )


@dataclass(frozen=True)
class ConcreteRealNetworkOfficialSettlementLiveHttpSenderAdapter:
    adapter_label: str = (
        SAFE_CONCRETE_REAL_NETWORK_OFFICIAL_SETTLEMENT_LIVE_SENDER_ADAPTER_LABEL
    )
    is_real_network_capable: bool = True
    is_fake_no_network_adapter: bool = False
    accepts_injected_real_network_client: bool = True
    default_no_post: bool = True
    uses_official_settlement_route: bool = True
    uses_generic_order_route: bool = False
    uses_generic_order_executor: bool = False
    uses_live_order_once: bool = False
    uses_one_shot_generic_order: bool = False
    uses_position_specific_path: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("adapter_label", self.adapter_label)
        _validate_bool_fields(self, _CONCRETE_ADAPTER_BOOL_FIELDS)

    def exercise_authorized_real_network_code_path_with_fake_client(
        self,
        plan: OfficialSettlementRealNetworkLiveSenderAdapterPlan,
        network_client: OfficialSettlementRealNetworkClientProtocol,
    ) -> OfficialSettlementRealNetworkLiveSenderAdapterCallResult:
        """Run the concrete adapter path with an injected no-network client."""
        _validate_concrete_real_network_adapter(self)
        _validate_real_network_adapter_plan_for_call(plan)
        return network_client.transmit_official_settlement_real_network(plan)


@dataclass(frozen=True)
class OfficialSettlementRealNetworkLiveSenderAdapterResult:
    status: OfficialSettlementRealNetworkLiveSenderAdapterStatus
    safe_adapter_label: str
    concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: (
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_callable_available: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order: (  # noqa: E501
        bool
    )
    concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path: (  # noqa: E501
        bool
    )
    real_network_adapter_plan: OfficialSettlementRealNetworkLiveSenderAdapterPlan
    real_network_adapter_boundary: OfficialSettlementRealNetworkLiveSenderAdapterBoundary
    concrete_real_network_adapter: ConcreteRealNetworkOfficialSettlementLiveHttpSenderAdapter
    fake_http_client: FakeHttpClientForConcreteOfficialSettlementRealNetworkSender
    real_network_adapter_call_result: OfficialSettlementRealNetworkLiveSenderAdapterCallResult
    dedicated_official_settlement_actual_http_post_sender_confirmed: bool
    dedicated_official_settlement_actual_http_post_sender_callable_available: bool
    dedicated_official_settlement_live_http_sender_adapter_confirmed: bool
    dedicated_official_settlement_live_http_sender_adapter_callable_available: bool
    actual_settlement_post_live_capable_transport_available: bool
    actual_settlement_post_can_be_allowed_after_fresh_execution_gates: bool
    concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization: bool
    next_execution_gate_can_call_concrete_real_network_live_http_sender_adapter_after_confirmation: (  # noqa: E501
        bool
    )
    fake_no_network_adapter_distinguished_from_concrete_adapter: bool
    concrete_adapter_accepts_injected_real_network_client: bool
    concrete_real_network_adapter_code_path_exercised_with_fake_http_client: bool
    fake_http_client_used: bool
    fake_http_client_call_count: int
    real_http_client_call_count: int
    concrete_real_network_adapter_real_http_post_executed: bool
    concrete_real_network_adapter_broker_write_executed: bool
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
    next_execution_gate_still_requires_fresh_runtime_read: bool
    next_execution_gate_still_requires_operator_readiness: bool
    next_execution_gate_still_requires_settlement_specific_confirmation: bool
    result_safe_category: str
    recommended_next_step: str
    blocked_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            OfficialSettlementRealNetworkLiveSenderAdapterStatus,
        ):
            raise LiveVerificationValidationError("status must be real adapter enum")
        if not isinstance(
            self.real_network_adapter_plan,
            OfficialSettlementRealNetworkLiveSenderAdapterPlan,
        ):
            raise LiveVerificationValidationError("real_network_adapter_plan required")
        if not isinstance(
            self.real_network_adapter_boundary,
            OfficialSettlementRealNetworkLiveSenderAdapterBoundary,
        ):
            raise LiveVerificationValidationError("real_network_adapter_boundary required")
        if not isinstance(
            self.concrete_real_network_adapter,
            ConcreteRealNetworkOfficialSettlementLiveHttpSenderAdapter,
        ):
            raise LiveVerificationValidationError("concrete_real_network_adapter required")
        if not isinstance(
            self.fake_http_client,
            FakeHttpClientForConcreteOfficialSettlementRealNetworkSender,
        ):
            raise LiveVerificationValidationError("fake_http_client required")
        if not isinstance(
            self.real_network_adapter_call_result,
            OfficialSettlementRealNetworkLiveSenderAdapterCallResult,
        ):
            raise LiveVerificationValidationError("real_network_adapter_call_result required")
        for field_name in (
            "safe_adapter_label",
            "settlement_route_kind",
            "result_safe_category",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        for field_name in (
            "fake_http_client_call_count",
            "real_http_client_call_count",
            "settlement_post_count",
            "sender_call_count",
            "transport_call_count",
        ):
            _validate_non_negative_int(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_real_network_live_sender_adapter_no_post_controlled(
    input_snapshot: OfficialSettlementRealNetworkLiveSenderAdapterInput | None = None,
    *,
    live_adapter_result: OfficialSettlementLiveHttpSenderAdapterResult | None = None,
) -> OfficialSettlementRealNetworkLiveSenderAdapterResult:
    """Build and exercise the concrete real-network adapter path with a fake client."""
    snapshot = input_snapshot or _input_from_live_adapter_result(
        live_adapter_result
        or build_official_settlement_live_http_sender_adapter_no_post_controlled(),
    )
    reasons = _blocked_reasons(snapshot)
    ready = not reasons
    status = _status_from_reasons(reasons)
    plan = _real_network_adapter_plan(snapshot, ready)
    boundary = _real_network_adapter_boundary(snapshot, ready)
    concrete_adapter = ConcreteRealNetworkOfficialSettlementLiveHttpSenderAdapter()
    fake_client = FakeHttpClientForConcreteOfficialSettlementRealNetworkSender()
    call_result = (
        concrete_adapter.exercise_authorized_real_network_code_path_with_fake_client(
            plan,
            fake_client,
        )
        if ready
        else _blocked_call_result()
    )

    return OfficialSettlementRealNetworkLiveSenderAdapterResult(
        status=status,
        safe_adapter_label=(
            SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_LABEL
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_confirmed=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed
            and ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_callable_available=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
            and ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready
            and ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route
            and ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path=False,
        real_network_adapter_plan=plan,
        real_network_adapter_boundary=boundary,
        concrete_real_network_adapter=concrete_adapter,
        fake_http_client=fake_client,
        real_network_adapter_call_result=call_result,
        dedicated_official_settlement_actual_http_post_sender_confirmed=(
            snapshot.dedicated_official_settlement_actual_http_post_sender_confirmed
            and ready
        ),
        dedicated_official_settlement_actual_http_post_sender_callable_available=(
            snapshot.dedicated_official_settlement_actual_http_post_sender_callable_available
            and ready
        ),
        dedicated_official_settlement_live_http_sender_adapter_confirmed=(
            snapshot.dedicated_official_settlement_live_http_sender_adapter_confirmed
            and ready
        ),
        dedicated_official_settlement_live_http_sender_adapter_callable_available=(
            snapshot.dedicated_official_settlement_live_http_sender_adapter_callable_available
            and ready
        ),
        actual_settlement_post_live_capable_transport_available=(
            snapshot.actual_settlement_post_live_capable_transport_available and ready
        ),
        actual_settlement_post_can_be_allowed_after_fresh_execution_gates=(
            snapshot.actual_settlement_post_can_be_allowed_after_fresh_execution_gates
            and ready
        ),
        concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization=(
            ready
        ),
        next_execution_gate_can_call_concrete_real_network_live_http_sender_adapter_after_confirmation=(
            ready
        ),
        fake_no_network_adapter_distinguished_from_concrete_adapter=(
            snapshot.fake_no_network_adapter_distinguished_from_concrete_adapter
            and ready
        ),
        concrete_adapter_accepts_injected_real_network_client=(
            snapshot.concrete_adapter_accepts_injected_real_network_client and ready
        ),
        concrete_real_network_adapter_code_path_exercised_with_fake_http_client=(
            call_result.concrete_real_network_adapter_code_path_exercised_with_fake_http_client
        ),
        fake_http_client_used=call_result.fake_http_client_used,
        fake_http_client_call_count=call_result.fake_http_client_call_count,
        real_http_client_call_count=call_result.real_http_client_call_count,
        concrete_real_network_adapter_real_http_post_executed=False,
        concrete_real_network_adapter_broker_write_executed=False,
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
        next_execution_gate_still_requires_fresh_runtime_read=True,
        next_execution_gate_still_requires_operator_readiness=True,
        next_execution_gate_still_requires_settlement_specific_confirmation=True,
        result_safe_category=(
            RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_READY_NO_POST_SANITIZED
            if ready
            else RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_NO_POST_SANITIZED
        ),
        recommended_next_step=(
            NEXT_STEP_OFFICIAL_SETTLEMENT_EXECUTION_GATE
            if ready
            else NEXT_STEP_FIX_REAL_NETWORK_LIVE_SENDER_ADAPTER
        ),
        blocked_reasons=reasons,
    )


def render_official_settlement_real_network_live_sender_adapter_no_post_markdown(
    result: OfficialSettlementRealNetworkLiveSenderAdapterResult,
) -> str:
    """Render a sanitized real-network adapter summary."""
    if not isinstance(result, OfficialSettlementRealNetworkLiveSenderAdapterResult):
        raise LiveVerificationValidationError("result must be real-network result")
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Official Settlement Real Network Live Sender Adapter No-POST",
            "",
            (
                "execution_step: "
                f"{EXECUTION_STEP_OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_NO_POST}"
            ),
            f"status: {result.status.value}",
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "callable_available: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "boundary_ready: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "uses_official_settlement_route: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "uses_generic_order_route: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "uses_generic_order_executor: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "uses_live_order_once: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "uses_one_shot_generic_order: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order)}"
            ),
            (
                "concrete_real_network_official_settlement_live_http_sender_adapter_"
                "uses_position_specific_path: "
                f"{_bool_text(result.concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path)}"
            ),
            (
                "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization: "
                f"{_bool_text(result.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization)}"
            ),
            (
                "next_execution_gate_can_call_concrete_real_network_live_http_"
                "sender_adapter_after_confirmation: "
                f"{_bool_text(result.next_execution_gate_can_call_concrete_real_network_live_http_sender_adapter_after_confirmation)}"
            ),
            (
                "fake_no_network_adapter_distinguished_from_concrete_adapter: "
                f"{_bool_text(result.fake_no_network_adapter_distinguished_from_concrete_adapter)}"
            ),
            (
                "concrete_adapter_accepts_injected_real_network_client: "
                f"{_bool_text(result.concrete_adapter_accepts_injected_real_network_client)}"
            ),
            (
                "concrete_real_network_adapter_code_path_exercised_with_fake_http_client: "
                f"{_bool_text(result.concrete_real_network_adapter_code_path_exercised_with_fake_http_client)}"
            ),
            f"fake_http_client_used: {_bool_text(result.fake_http_client_used)}",
            f"fake_http_client_call_count: {result.fake_http_client_call_count}",
            f"real_http_client_call_count: {result.real_http_client_call_count}",
            (
                "concrete_real_network_adapter_real_http_post_executed: "
                f"{_bool_text(result.concrete_real_network_adapter_real_http_post_executed)}"
            ),
            (
                "concrete_real_network_adapter_broker_write_executed: "
                f"{_bool_text(result.concrete_real_network_adapter_broker_write_executed)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_confirmed: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_confirmed)}"
            ),
            (
                "dedicated_official_settlement_actual_http_post_sender_callable_available: "
                f"{_bool_text(result.dedicated_official_settlement_actual_http_post_sender_callable_available)}"
            ),
            (
                "dedicated_official_settlement_live_http_sender_adapter_confirmed: "
                f"{_bool_text(result.dedicated_official_settlement_live_http_sender_adapter_confirmed)}"
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


def _input_from_live_adapter_result(
    result: OfficialSettlementLiveHttpSenderAdapterResult,
) -> OfficialSettlementRealNetworkLiveSenderAdapterInput:
    return OfficialSettlementRealNetworkLiveSenderAdapterInput(
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
        dedicated_official_settlement_live_http_sender_adapter_confirmed=(
            result.dedicated_official_settlement_live_http_sender_adapter_confirmed
        ),
        dedicated_official_settlement_live_http_sender_adapter_callable_available=(
            result.dedicated_official_settlement_live_http_sender_adapter_callable_available
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
    snapshot: OfficialSettlementRealNetworkLiveSenderAdapterInput,
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
        "dedicated_official_settlement_live_http_sender_adapter_confirmed",
        "dedicated_official_settlement_live_http_sender_adapter_callable_available",
        "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
        "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
        "concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready",
    ):
        if not getattr(snapshot, field_name):
            reasons.append(f"{field_name}_required")
    if not (
        snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route
    ):
        reasons.append("concrete_real_network_adapter_must_use_official_settlement_route")
    if (
        snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route
    ):
        reasons.append("concrete_real_network_adapter_uses_generic_order_route")
    if (
        snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor
    ):
        reasons.append("concrete_real_network_adapter_uses_generic_order_executor")
    if (
        snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once
    ):
        reasons.append("concrete_real_network_adapter_uses_live_order_once")
    if (
        snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order
    ):
        reasons.append("concrete_real_network_adapter_uses_one_shot_generic_order")
    if (
        snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path
    ):
        reasons.append("concrete_real_network_adapter_uses_position_specific_path")
    if not snapshot.fake_no_network_adapter_distinguished_from_concrete_adapter:
        reasons.append("fake_no_network_adapter_must_be_distinguished")
    if not snapshot.concrete_adapter_accepts_injected_real_network_client:
        reasons.append("concrete_adapter_must_accept_injected_real_network_client")
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
    if snapshot.symbol_safe_label != SUPPORTED_SYMBOL:
        reasons.append("symbol_safe_label_mismatch")
    if snapshot.settlement_size_safe_label != str(SUPPORTED_UNITS):
        reasons.append("settlement_size_safe_label_mismatch")
    if snapshot.settlement_order_type_safe_label != SETTLEMENT_ORDER_TYPE_SAFE_LABEL_MARKET:
        reasons.append("settlement_order_type_safe_label_mismatch")
    if snapshot.settlement_side_semantics_safe_label != SETTLEMENT_SIDE_SEMANTICS_CONFIRMED:
        reasons.append("settlement_side_semantics_safe_label_mismatch")
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
    if not snapshot.fake_http_client_used:
        reasons.append("fake_http_client_required")
    if not snapshot.concrete_real_network_adapter_code_path_exercised_with_fake_http_client:
        reasons.append("fake_http_client_code_path_required")
    for field_name in _BOOLEAN_BLOCKED_FIELDS:
        if getattr(snapshot, field_name):
            reasons.append(field_name)
    if snapshot.settlement_post_count != 0:
        reasons.append("settlement_post_count_must_remain_0")
    if snapshot.sender_call_count != 0:
        reasons.append("sender_call_count_must_remain_0")
    if snapshot.transport_call_count != 0:
        reasons.append("transport_call_count_must_remain_0")
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
) -> OfficialSettlementRealNetworkLiveSenderAdapterStatus:
    if not reasons:
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.READY_NO_POST
    if any(reason.startswith("repository") or reason.startswith("head_") for reason in reasons):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_REPOSITORY
    if any("credential_presence" in reason for reason in reasons):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_CREDENTIAL
    if any(
        reason.startswith("runtime_position")
        or "position_count" in reason
        or reason == "has_exactly_one_position_required"
        or reason == "has_multiple_positions_blocked"
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_POSITION
    if any("operator_" in reason for reason in reasons):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_OPERATOR
    if any("confirmation" in reason for reason in reasons):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_CONFIRMATION
    if any(
        reason in _LIFECYCLE_BLOCKED_REASONS
        or reason.endswith("_must_remain_0")
        or reason.startswith("next_execution_gate_still_requires")
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_LIFECYCLE
    if any("concrete_real_network_adapter" in reason for reason in reasons):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_SENDER
    if any(
        "generic" in reason
        or "live_order_once" in reason
        or "one_shot" in reason
        or "route" in reason
        or "position_specific" in reason
        for reason in reasons
    ):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_ROUTE
    if any("exposure" in reason or reason == "env_read" for reason in reasons):
        return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_UNSAFE
    return OfficialSettlementRealNetworkLiveSenderAdapterStatus.BLOCKED_ROUTE


def _real_network_adapter_plan(
    snapshot: OfficialSettlementRealNetworkLiveSenderAdapterInput,
    ready: bool,
) -> OfficialSettlementRealNetworkLiveSenderAdapterPlan:
    return OfficialSettlementRealNetworkLiveSenderAdapterPlan(
        adapter_plan_label=SAFE_OFFICIAL_SETTLEMENT_REAL_NETWORK_LIVE_SENDER_ADAPTER_LABEL,
        concrete_adapter_label=(
            SAFE_CONCRETE_REAL_NETWORK_OFFICIAL_SETTLEMENT_LIVE_SENDER_ADAPTER_LABEL
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_confirmed=(
            ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_callable_available=(
            ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready=(
            ready
        ),
        concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization=(
            ready
        ),
        fake_no_network_adapter_distinguished_from_concrete_adapter=ready,
        concrete_adapter_accepts_injected_real_network_client=ready,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route=(
            ready
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order=False,
        concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path=False,
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        symbol_safe_label=snapshot.symbol_safe_label,
        settlement_size_safe_label=snapshot.settlement_size_safe_label,
        settlement_order_type_safe_label=snapshot.settlement_order_type_safe_label,
        settlement_side_semantics_safe_label=snapshot.settlement_side_semantics_safe_label,
        one_settlement_post_max=snapshot.one_settlement_post_max,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        entry_post_allowed=False,
        generic_close_allowed=False,
        ledger_update_allowed=False,
        receipt_handoff_allowed=False,
        raw_id_value_credential_header_exposure=False,
    )


def _real_network_adapter_boundary(
    snapshot: OfficialSettlementRealNetworkLiveSenderAdapterInput,
    ready: bool,
) -> OfficialSettlementRealNetworkLiveSenderAdapterBoundary:
    return OfficialSettlementRealNetworkLiveSenderAdapterBoundary(
        boundary_label=(
            SAFE_CONCRETE_REAL_NETWORK_OFFICIAL_SETTLEMENT_LIVE_SENDER_ADAPTER_LABEL
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready=(
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready
            and ready
        ),
        adapter_is_concrete_real_network=True,
        adapter_is_fake_no_network_adapter=False,
        fake_no_network_adapter_distinguished_from_concrete_adapter=ready,
        adapter_accepts_injected_real_network_client=ready,
        adapter_uses_official_settlement_route=ready,
        adapter_uses_generic_order_route=False,
        adapter_uses_generic_order_executor=False,
        adapter_uses_live_order_once=False,
        adapter_uses_one_shot_generic_order=False,
        adapter_uses_position_specific_path=False,
        adapter_requires_position_identifier=False,
        adapter_allows_retry=False,
        adapter_allows_repost=False,
        adapter_allows_second_settlement=False,
        adapter_default_no_post=True,
    )


def _blocked_call_result() -> OfficialSettlementRealNetworkLiveSenderAdapterCallResult:
    return OfficialSettlementRealNetworkLiveSenderAdapterCallResult(
        safe_call_label=(
            SAFE_FAKE_CLIENT_FOR_CONCRETE_OFFICIAL_SETTLEMENT_REAL_NETWORK_SENDER_LABEL
        ),
        concrete_real_network_adapter_code_path_exercised_with_fake_http_client=False,
        fake_http_client_used=True,
        fake_http_client_call_count=0,
        real_http_client_call_count=0,
        concrete_real_network_adapter_real_http_post_executed=False,
        concrete_real_network_adapter_broker_write_executed=False,
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
            RESULT_REAL_NETWORK_LIVE_SENDER_ADAPTER_BLOCKED_NO_POST_SANITIZED
        ),
    )


def _validate_concrete_real_network_adapter(
    adapter: ConcreteRealNetworkOfficialSettlementLiveHttpSenderAdapter,
) -> None:
    if not adapter.is_real_network_capable:
        raise LiveVerificationValidationError("real-network capable adapter required")
    if adapter.is_fake_no_network_adapter:
        raise LiveVerificationValidationError("fake no-network adapter is not concrete")
    if not adapter.accepts_injected_real_network_client:
        raise LiveVerificationValidationError("injected real-network client required")
    if not adapter.default_no_post:
        raise LiveVerificationValidationError("default no-POST mode required")
    if not adapter.uses_official_settlement_route:
        raise LiveVerificationValidationError("official settlement route required")
    if adapter.uses_generic_order_route or adapter.uses_generic_order_executor:
        raise LiveVerificationValidationError("generic order route/executor forbidden")
    if adapter.uses_live_order_once:
        raise LiveVerificationValidationError("live_order_once forbidden")
    if adapter.uses_one_shot_generic_order:
        raise LiveVerificationValidationError("one-shot generic order forbidden")
    if adapter.uses_position_specific_path:
        raise LiveVerificationValidationError("position-specific path forbidden")


def _validate_real_network_adapter_plan_for_call(
    plan: OfficialSettlementRealNetworkLiveSenderAdapterPlan,
) -> None:
    if not isinstance(plan, OfficialSettlementRealNetworkLiveSenderAdapterPlan):
        raise LiveVerificationValidationError("plan must be real-network adapter plan")
    if not plan.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization:
        raise LiveVerificationValidationError("execution gate authorization required")
    if not (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
    ):
        raise LiveVerificationValidationError("concrete real-network callable unavailable")
    if not (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready
    ):
        raise LiveVerificationValidationError("concrete real-network boundary unavailable")
    if not plan.fake_no_network_adapter_distinguished_from_concrete_adapter:
        raise LiveVerificationValidationError("fake adapter distinction required")
    if not plan.concrete_adapter_accepts_injected_real_network_client:
        raise LiveVerificationValidationError("injected real-network client required")
    if not (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route
    ):
        raise LiveVerificationValidationError("official settlement route required")
    if (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route
    ):
        raise LiveVerificationValidationError("generic order route forbidden")
    if (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor
    ):
        raise LiveVerificationValidationError("generic order executor forbidden")
    if plan.concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once:
        raise LiveVerificationValidationError("live_order_once forbidden")
    if (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order
    ):
        raise LiveVerificationValidationError("one-shot generic order forbidden")
    if (
        plan.concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path
    ):
        raise LiveVerificationValidationError("position-specific path forbidden")
    if plan.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        raise LiveVerificationValidationError("official size-based settlement required")
    if plan.settlement_route_is_generic_order or not plan.settlement_route_is_dedicated:
        raise LiveVerificationValidationError("dedicated non-generic route required")
    if plan.retry_allowed or plan.repost_allowed or plan.second_settlement_allowed:
        raise LiveVerificationValidationError("retry/repost/second settlement forbidden")
    if plan.entry_post_allowed or plan.generic_close_allowed:
        raise LiveVerificationValidationError("entry/generic close forbidden")
    if plan.ledger_update_allowed or plan.receipt_handoff_allowed:
        raise LiveVerificationValidationError("ledger/receipt forbidden")
    if plan.raw_id_value_credential_header_exposure:
        raise LiveVerificationValidationError("raw/id/credential/header exposure forbidden")


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
    "dedicated_official_settlement_live_http_sender_adapter_confirmed",
    "dedicated_official_settlement_live_http_sender_adapter_callable_available",
    "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
    "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
    "concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path",
    "fake_no_network_adapter_distinguished_from_concrete_adapter",
    "concrete_adapter_accepts_injected_real_network_client",
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
    "fake_http_client_used",
    "concrete_real_network_adapter_code_path_exercised_with_fake_http_client",
    "concrete_real_network_adapter_real_http_post_executed",
    "concrete_real_network_adapter_broker_write_executed",
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
    "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
    "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
    "concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready",
    "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization",
    "fake_no_network_adapter_distinguished_from_concrete_adapter",
    "concrete_adapter_accepts_injected_real_network_client",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path",
    "settlement_route_is_generic_order",
    "settlement_route_is_dedicated",
    "one_settlement_post_max",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_allowed",
    "generic_close_allowed",
    "ledger_update_allowed",
    "receipt_handoff_allowed",
    "raw_id_value_credential_header_exposure",
)

_BOUNDARY_BOOL_FIELDS = (
    "concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready",
    "adapter_is_concrete_real_network",
    "adapter_is_fake_no_network_adapter",
    "fake_no_network_adapter_distinguished_from_concrete_adapter",
    "adapter_accepts_injected_real_network_client",
    "adapter_uses_official_settlement_route",
    "adapter_uses_generic_order_route",
    "adapter_uses_generic_order_executor",
    "adapter_uses_live_order_once",
    "adapter_uses_one_shot_generic_order",
    "adapter_uses_position_specific_path",
    "adapter_requires_position_identifier",
    "adapter_allows_retry",
    "adapter_allows_repost",
    "adapter_allows_second_settlement",
    "adapter_default_no_post",
)

_CALL_RESULT_BOOL_FIELDS = (
    "concrete_real_network_adapter_code_path_exercised_with_fake_http_client",
    "fake_http_client_used",
    "concrete_real_network_adapter_real_http_post_executed",
    "concrete_real_network_adapter_broker_write_executed",
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

_CONCRETE_ADAPTER_BOOL_FIELDS = (
    "is_real_network_capable",
    "is_fake_no_network_adapter",
    "accepts_injected_real_network_client",
    "default_no_post",
    "uses_official_settlement_route",
    "uses_generic_order_route",
    "uses_generic_order_executor",
    "uses_live_order_once",
    "uses_one_shot_generic_order",
    "uses_position_specific_path",
)

_RESULT_BOOL_FIELDS = (
    "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed",
    "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available",
    "concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_official_settlement_route",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_route",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_generic_order_executor",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_live_order_once",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_one_shot_generic_order",
    "concrete_real_network_official_settlement_live_http_sender_adapter_uses_position_specific_path",
    "dedicated_official_settlement_actual_http_post_sender_confirmed",
    "dedicated_official_settlement_actual_http_post_sender_callable_available",
    "dedicated_official_settlement_live_http_sender_adapter_confirmed",
    "dedicated_official_settlement_live_http_sender_adapter_callable_available",
    "actual_settlement_post_live_capable_transport_available",
    "actual_settlement_post_can_be_allowed_after_fresh_execution_gates",
    "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization",
    "next_execution_gate_can_call_concrete_real_network_live_http_sender_adapter_after_confirmation",
    "fake_no_network_adapter_distinguished_from_concrete_adapter",
    "concrete_adapter_accepts_injected_real_network_client",
    "concrete_real_network_adapter_code_path_exercised_with_fake_http_client",
    "fake_http_client_used",
    "concrete_real_network_adapter_real_http_post_executed",
    "concrete_real_network_adapter_broker_write_executed",
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
    "concrete_real_network_adapter_real_http_post_executed",
    "concrete_real_network_adapter_broker_write_executed",
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
    "concrete_real_network_adapter_real_http_post_executed",
    "concrete_real_network_adapter_broker_write_executed",
    "this_step_actual_http_post_sender_invoked",
    "this_step_actual_settlement_post_executed",
    "http_post_executed",
    "entry_post_executed",
    "generic_close_post_executed",
    "live_order_once_executed",
    "external_api_write_executed",
}
