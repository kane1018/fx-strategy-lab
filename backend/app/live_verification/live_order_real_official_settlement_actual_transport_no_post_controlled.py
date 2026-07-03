from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Protocol

import httpx

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_official_settlement_real_network_live_sender_adapter_no_post_controlled import (  # noqa: E501
    build_official_settlement_real_network_live_sender_adapter_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
    build_official_settlement_route_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_side_provenance_gate_no_post_controlled import (  # noqa: E501
    APPROVED_SAFE_ARTIFACT_KIND,
    SETTLEMENT_SIDE_SOURCE_APPROVED_SAFE_ARTIFACT_LABEL,
    SIDE_PROVENANCE_NOT_CONFIRMED_LABEL,
    build_official_settlement_side_provenance_gate_no_post_controlled,
)
from app.live_verification.live_order_real_position_runtime_safe_read_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_step6g_level5_fast_mvp_controlled import (
    SUPPORTED_SYMBOL,
    SUPPORTED_UNITS,
)
from app.private_api.auth import build_auth_headers

STEP_NAME = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-"
    "PRE-EXECUTION-STOP-CONDITIONS-ELIMINATION-NO-POST-C"
)

OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_METHOD = "POST"
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BASE_URL = "https://forex-api.coin.z.com"
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_SIGNING_PATH = "/private/v1/closeOrder"
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_ENDPOINT_URL = (
    f"{OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BASE_URL}"
    f"{OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_SIGNING_PATH}"
)
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_ROUTE_SAFE_LABEL = (
    "GMO_FX_DEDICATED_CLOSE_ORDER_ROUTE_OFFICIAL_DOC_LABEL"
)
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_PARAMETER_SHAPE_SAFE_LABEL = (
    "SYMBOL_SIDE_EXECUTION_TYPE_AND_SIZE"
)
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_READY_RESULT = (
    "RESULT_OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_READY_NO_POST_SANITIZED"
)
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BLOCKED_RESULT = (
    "RESULT_OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BLOCKED_NO_POST_SANITIZED"
)
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_ACCEPTED_RESULT = "RESULT_ACCEPTED_SANITIZED"
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_REJECTED_RESULT = "RESULT_REJECTED_SANITIZED"
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_UNKNOWN_RESULT = "RESULT_UNKNOWN_SANITIZED"
OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_FAILED_RESULT = "RESULT_FAILED_SANITIZED"

SETTLEMENT_SIDE_NOT_CONFIRMED_SAFE_LABEL = "SIDE_PROVENANCE_NOT_CONFIRMED"
DEFAULT_SETTLEMENT_EXECUTION_TYPE_SAFE_LABEL = "MARKET"


class OfficialSettlementActualTransportStatus(StrEnum):
    READY_NO_POST = "READY_NO_POST"
    BLOCKED_NO_POST = "BLOCKED_NO_POST"


@dataclass(frozen=True)
class OfficialSettlementActualTransportInput:
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
    concrete_real_network_official_settlement_live_http_sender_adapter_confirmed: (
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_callable_available: (
        bool
    ) = True
    concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready: bool = True
    concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization: bool = True

    official_settlement_real_network_client_binding_confirmed: bool = True
    official_settlement_real_network_client_callable_available: bool = True
    official_settlement_real_network_transport_binding_ready: bool = True
    official_settlement_real_network_client_targets_official_settlement_route: bool = True
    official_settlement_real_network_client_targets_generic_order_route: bool = False
    official_settlement_real_network_client_uses_generic_order_executor: bool = False
    official_settlement_real_network_client_uses_live_order_once: bool = False
    official_settlement_real_network_client_uses_one_shot_generic_order: bool = False
    official_settlement_real_network_client_uses_position_specific_path: bool = False
    real_network_client_binding_can_be_reached_after_execution_gate_authorization: bool = True
    next_execution_gate_can_call_real_network_client_after_confirmation: bool = True

    runtime_position_status: str = PositionReadOnlyControlledStatus.ONE_POSITION_OPEN.value
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

    settlement_side_provenance_gate_confirmed: bool = False
    settlement_side_source_safe_artifact_available: bool = False
    settlement_side_source_safe_artifact_kind: str = SIDE_PROVENANCE_NOT_CONFIRMED_LABEL
    settlement_side_source_is_default_value: bool = True
    settlement_side_source_is_operator_input: bool = False
    settlement_side_source_is_raw_broker_value: bool = False
    settlement_side_source_is_position_specific_identifier: bool = False
    settlement_side_source_is_generic_opposite_order: bool = False
    settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact: (
        bool
    ) = False
    settlement_side_matches_official_settlement_side_semantics: bool = False
    settlement_side_safe_artifact_propagated_to_official_settlement_preview: bool = False
    settlement_side_safe_artifact_propagated_to_actual_transport_plan: bool = False
    settlement_side_safe_artifact_propagated_to_execution_gate: bool = False
    settlement_side_provenance_mechanically_confirmed: bool = False
    execution_gate_can_verify_settlement_side_provenance_before_post: bool = False
    next_execution_gate_has_no_known_side_provenance_blocker: bool = False

    settlement_symbol_safe_label: str = SUPPORTED_SYMBOL
    settlement_side_safe_label: str = SETTLEMENT_SIDE_NOT_CONFIRMED_SAFE_LABEL
    settlement_side_source_safe_label: str = SIDE_PROVENANCE_NOT_CONFIRMED_LABEL
    settlement_execution_type_safe_label: str = DEFAULT_SETTLEMENT_EXECUTION_TYPE_SAFE_LABEL
    settlement_size_safe_value: int = SUPPORTED_UNITS

    one_settlement_post_max: bool = True
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_settlement_allowed: bool = False
    entry_post_allowed: bool = False
    generic_close_allowed: bool = False
    ledger_update_allowed: bool = False
    receipt_handoff_allowed: bool = False
    raw_id_value_credential_header_exposure: bool = False
    env_read: bool = False


@dataclass(frozen=True)
class OfficialSettlementActualTransportPlan:
    step_name: str
    route_kind: str
    route_safe_label: str
    parameter_shape_safe_label: str
    method_safe_label: str
    settlement_symbol_safe_label: str
    settlement_side_safe_label: str
    settlement_side_source_safe_label: str
    settlement_execution_type_safe_label: str
    settlement_size_safe_value: int
    size_based_settlement: bool
    position_specific_identifier_required: bool
    one_settlement_post_max: bool
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    entry_post_allowed: bool
    generic_close_allowed: bool
    raw_id_value_credential_header_exposure: bool


@dataclass(frozen=True)
class OfficialSettlementActualTransportClientResult:
    sanitized_result_category: str
    fake_http_transport_used: bool
    fake_http_transport_call_count: int
    real_http_client_call_count: int
    actual_transport_real_http_post_executed: bool
    actual_transport_broker_write_executed: bool
    simulated_settlement_post_count: int


@dataclass(frozen=True)
class OfficialSettlementActualTransportResult:
    step_name: str
    status: OfficialSettlementActualTransportStatus
    sanitized_result_category: str
    blocked_reasons: tuple[str, ...]

    all_pre_execution_code_stop_conditions_eliminated: bool
    official_settlement_actual_transport_confirmed: bool
    official_settlement_actual_transport_callable_available: bool
    official_settlement_actual_transport_binding_ready: bool
    official_settlement_actual_transport_targets_official_settlement_route: bool
    official_settlement_actual_transport_targets_generic_order_route: bool
    official_settlement_actual_transport_uses_generic_order_executor: bool
    official_settlement_actual_transport_uses_live_order_once: bool
    official_settlement_actual_transport_uses_one_shot_generic_order: bool
    official_settlement_actual_transport_uses_position_specific_path: bool

    official_settlement_real_network_client_binding_confirmed: bool
    official_settlement_real_network_client_callable_available: bool
    official_settlement_real_network_transport_binding_ready: bool
    real_network_client_binding_can_be_reached_after_execution_gate_authorization: bool
    execution_gate_can_call_actual_transport_after_confirmation: bool
    next_execution_gate_has_no_known_code_blocker: bool

    fake_http_transport_used: bool
    fake_http_transport_call_count: int
    real_http_client_call_count: int
    actual_transport_real_http_post_executed: bool
    actual_transport_broker_write_executed: bool

    official_settlement_no_post_preview_ready: bool
    settlement_route_kind: str
    settlement_route_is_generic_order: bool
    settlement_route_is_dedicated: bool

    settlement_side_provenance_gate_confirmed: bool
    settlement_side_source_safe_artifact_available: bool
    settlement_side_source_safe_artifact_kind: str
    settlement_side_source_is_default_value: bool
    settlement_side_source_is_operator_input: bool
    settlement_side_source_is_raw_broker_value: bool
    settlement_side_source_is_position_specific_identifier: bool
    settlement_side_source_is_generic_opposite_order: bool
    settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact: (
        bool
    )
    settlement_side_matches_official_settlement_side_semantics: bool
    settlement_side_safe_artifact_propagated_to_official_settlement_preview: bool
    settlement_side_safe_artifact_propagated_to_actual_transport_plan: bool
    settlement_side_safe_artifact_propagated_to_execution_gate: bool
    settlement_side_provenance_mechanically_confirmed: bool
    execution_gate_can_verify_settlement_side_provenance_before_post: bool
    next_execution_gate_has_no_known_side_provenance_blocker: bool

    generic_order_executor_used_for_settlement: bool
    live_order_once_used_for_settlement: bool
    generic_order_endpoint_used_for_settlement: bool
    one_shot_generic_order_path_used_for_settlement: bool
    position_specific_path_used: bool
    position_specific_identifier_safe_handling_ready: bool
    position_specific_preview_allowed: bool
    size_based_preview_allowed: bool

    this_step_actual_transport_invoked: bool
    this_step_actual_settlement_post_executed: bool
    settlement_post_count: int
    sender_call_count: int
    transport_call_count: int
    http_post_executed: bool
    entry_post_executed: bool
    generic_close_post_executed: bool
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

    actual_transport_plan: OfficialSettlementActualTransportPlan | None = field(repr=False)


class OfficialSettlementActualTransportHttpClientProtocol(Protocol):
    def send_official_settlement(
        self,
        *,
        plan: OfficialSettlementActualTransportPlan,
    ) -> OfficialSettlementActualTransportClientResult:
        ...


class OfficialSettlementActualTransportFakeHttpClient:
    def __init__(self) -> None:
        self.call_count = 0

    def send_official_settlement(
        self,
        *,
        plan: OfficialSettlementActualTransportPlan,
    ) -> OfficialSettlementActualTransportClientResult:
        _validate_plan_is_official_settlement_only(plan)
        self.call_count += 1
        return OfficialSettlementActualTransportClientResult(
            sanitized_result_category=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_READY_RESULT,
            fake_http_transport_used=True,
            fake_http_transport_call_count=self.call_count,
            real_http_client_call_count=0,
            actual_transport_real_http_post_executed=False,
            actual_transport_broker_write_executed=False,
            simulated_settlement_post_count=0,
        )


class OfficialSettlementActualTransportHttpxClient:
    """Concrete live-capable transport for a later gate-authorized single settlement POST."""

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        timestamp_factory: Callable[[], str],
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._timestamp_factory = timestamp_factory
        self._timeout_seconds = timeout_seconds

    def __repr__(self) -> str:
        return "OfficialSettlementActualTransportHttpxClient(<redacted>)"

    def send_official_settlement(
        self,
        *,
        plan: OfficialSettlementActualTransportPlan,
    ) -> OfficialSettlementActualTransportClientResult:
        _validate_plan_is_official_settlement_only(plan)
        body = _serialize_official_settlement_body(plan)
        timestamp = self._timestamp_factory()
        headers = build_auth_headers(
            api_key=self._api_key,
            api_secret=self._api_secret,
            timestamp=timestamp,
            method=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_METHOD,
            path=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_SIGNING_PATH,
            body=body,
        )

        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_ENDPOINT_URL,
                    content=body,
                    headers=headers,
                )
        except httpx.HTTPError:
            return OfficialSettlementActualTransportClientResult(
                sanitized_result_category=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_UNKNOWN_RESULT,
                fake_http_transport_used=False,
                fake_http_transport_call_count=0,
                real_http_client_call_count=1,
                actual_transport_real_http_post_executed=True,
                actual_transport_broker_write_executed=True,
                simulated_settlement_post_count=1,
            )

        return OfficialSettlementActualTransportClientResult(
            sanitized_result_category=_sanitize_http_response_status(response),
            fake_http_transport_used=False,
            fake_http_transport_call_count=0,
            real_http_client_call_count=1,
            actual_transport_real_http_post_executed=True,
            actual_transport_broker_write_executed=True,
            simulated_settlement_post_count=1,
        )


class OfficialSettlementActualTransport:
    def send_after_execution_gate_authorization(
        self,
        *,
        plan: OfficialSettlementActualTransportPlan,
        client: OfficialSettlementActualTransportHttpClientProtocol,
    ) -> OfficialSettlementActualTransportClientResult:
        _validate_plan_is_official_settlement_only(plan)
        return client.send_official_settlement(plan=plan)


def build_official_settlement_actual_transport_no_post_controlled(
    input_snapshot: OfficialSettlementActualTransportInput | None = None,
    *,
    client: OfficialSettlementActualTransportHttpClientProtocol | None = None,
) -> OfficialSettlementActualTransportResult:
    snapshot = input_snapshot or _default_input_snapshot()
    blocked_reasons = _blocked_reasons(snapshot)
    status = (
        OfficialSettlementActualTransportStatus.READY_NO_POST
        if not blocked_reasons
        else OfficialSettlementActualTransportStatus.BLOCKED_NO_POST
    )

    plan = (
        _build_plan(snapshot)
        if status is OfficialSettlementActualTransportStatus.READY_NO_POST
        else None
    )
    client_result = _no_call_client_result()
    if plan is not None:
        fake_client = client or OfficialSettlementActualTransportFakeHttpClient()
        client_result = OfficialSettlementActualTransport().send_after_execution_gate_authorization(
            plan=plan,
            client=fake_client,
        )

    ready = status is OfficialSettlementActualTransportStatus.READY_NO_POST
    fake_path_exercised = ready and client_result.fake_http_transport_used
    no_real_post = not client_result.actual_transport_real_http_post_executed
    no_broker_write = not client_result.actual_transport_broker_write_executed
    no_settlement_post = client_result.simulated_settlement_post_count == 0
    plan_side_provenance_confirmed = (
        plan is not None
        and snapshot.settlement_side_provenance_mechanically_confirmed
        and snapshot.settlement_side_safe_artifact_propagated_to_actual_transport_plan
        and snapshot.settlement_side_safe_artifact_propagated_to_execution_gate
        and plan.settlement_side_safe_label == snapshot.settlement_side_safe_label
        and plan.settlement_side_source_safe_label
        == SETTLEMENT_SIDE_SOURCE_APPROVED_SAFE_ARTIFACT_LABEL
    )
    no_known_code_blocker = (
        ready
        and plan_side_provenance_confirmed
        and fake_path_exercised
        and no_real_post
        and no_broker_write
        and no_settlement_post
    )

    return OfficialSettlementActualTransportResult(
        step_name=STEP_NAME,
        status=status,
        sanitized_result_category=(
            OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_READY_RESULT
            if ready
            else OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BLOCKED_RESULT
        ),
        blocked_reasons=blocked_reasons,
        all_pre_execution_code_stop_conditions_eliminated=no_known_code_blocker,
        official_settlement_actual_transport_confirmed=ready,
        official_settlement_actual_transport_callable_available=ready,
        official_settlement_actual_transport_binding_ready=ready,
        official_settlement_actual_transport_targets_official_settlement_route=ready,
        official_settlement_actual_transport_targets_generic_order_route=False,
        official_settlement_actual_transport_uses_generic_order_executor=False,
        official_settlement_actual_transport_uses_live_order_once=False,
        official_settlement_actual_transport_uses_one_shot_generic_order=False,
        official_settlement_actual_transport_uses_position_specific_path=False,
        official_settlement_real_network_client_binding_confirmed=(
            snapshot.official_settlement_real_network_client_binding_confirmed and ready
        ),
        official_settlement_real_network_client_callable_available=(
            snapshot.official_settlement_real_network_client_callable_available and ready
        ),
        official_settlement_real_network_transport_binding_ready=ready,
        real_network_client_binding_can_be_reached_after_execution_gate_authorization=(
            snapshot.real_network_client_binding_can_be_reached_after_execution_gate_authorization
            and ready
        ),
        execution_gate_can_call_actual_transport_after_confirmation=no_known_code_blocker,
        next_execution_gate_has_no_known_code_blocker=no_known_code_blocker,
        fake_http_transport_used=client_result.fake_http_transport_used,
        fake_http_transport_call_count=client_result.fake_http_transport_call_count,
        real_http_client_call_count=client_result.real_http_client_call_count,
        actual_transport_real_http_post_executed=(
            client_result.actual_transport_real_http_post_executed
        ),
        actual_transport_broker_write_executed=client_result.actual_transport_broker_write_executed,
        official_settlement_no_post_preview_ready=(
            snapshot.official_settlement_no_post_preview_ready and ready
        ),
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        settlement_side_provenance_gate_confirmed=(
            snapshot.settlement_side_provenance_gate_confirmed and ready
        ),
        settlement_side_source_safe_artifact_available=(
            snapshot.settlement_side_source_safe_artifact_available and ready
        ),
        settlement_side_source_safe_artifact_kind=(
            snapshot.settlement_side_source_safe_artifact_kind
        ),
        settlement_side_source_is_default_value=(
            snapshot.settlement_side_source_is_default_value
        ),
        settlement_side_source_is_operator_input=(
            snapshot.settlement_side_source_is_operator_input
        ),
        settlement_side_source_is_raw_broker_value=(
            snapshot.settlement_side_source_is_raw_broker_value
        ),
        settlement_side_source_is_position_specific_identifier=(
            snapshot.settlement_side_source_is_position_specific_identifier
        ),
        settlement_side_source_is_generic_opposite_order=(
            snapshot.settlement_side_source_is_generic_opposite_order
        ),
        settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact=(
            snapshot.settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact
            and ready
        ),
        settlement_side_matches_official_settlement_side_semantics=(
            snapshot.settlement_side_matches_official_settlement_side_semantics and ready
        ),
        settlement_side_safe_artifact_propagated_to_official_settlement_preview=(
            snapshot.settlement_side_safe_artifact_propagated_to_official_settlement_preview
            and ready
        ),
        settlement_side_safe_artifact_propagated_to_actual_transport_plan=(
            plan_side_provenance_confirmed
        ),
        settlement_side_safe_artifact_propagated_to_execution_gate=(
            snapshot.settlement_side_safe_artifact_propagated_to_execution_gate and ready
        ),
        settlement_side_provenance_mechanically_confirmed=(
            plan_side_provenance_confirmed
        ),
        execution_gate_can_verify_settlement_side_provenance_before_post=(
            plan_side_provenance_confirmed
        ),
        next_execution_gate_has_no_known_side_provenance_blocker=(
            plan_side_provenance_confirmed
        ),
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        generic_order_endpoint_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_used=False,
        position_specific_identifier_safe_handling_ready=False,
        position_specific_preview_allowed=False,
        size_based_preview_allowed=snapshot.size_based_preview_allowed and ready,
        this_step_actual_transport_invoked=False,
        this_step_actual_settlement_post_executed=False,
        settlement_post_count=0,
        sender_call_count=0,
        transport_call_count=0,
        http_post_executed=False,
        entry_post_executed=False,
        generic_close_post_executed=False,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_credential_header_exposure=False,
        env_read=False,
        next_execution_gate_still_requires_fresh_runtime_read=True,
        next_execution_gate_still_requires_operator_readiness=True,
        next_execution_gate_still_requires_settlement_specific_confirmation=True,
        actual_transport_plan=plan,
    )


def render_official_settlement_actual_transport_no_post_markdown(
    result: OfficialSettlementActualTransportResult,
) -> str:
    lines = [
        "# Official Settlement Actual Transport No-POST",
        "",
        f"- step_name: {result.step_name}",
        f"- status: {result.status.value}",
        f"- sanitized_result_category: {result.sanitized_result_category}",
        (
            "- all_pre_execution_code_stop_conditions_eliminated: "
            f"{str(result.all_pre_execution_code_stop_conditions_eliminated).lower()}"
        ),
        (
            "- official_settlement_actual_transport_confirmed: "
            f"{str(result.official_settlement_actual_transport_confirmed).lower()}"
        ),
        (
            "- official_settlement_actual_transport_callable_available: "
            f"{str(result.official_settlement_actual_transport_callable_available).lower()}"
        ),
        (
            "- official_settlement_actual_transport_binding_ready: "
            f"{str(result.official_settlement_actual_transport_binding_ready).lower()}"
        ),
        (
            "- official_settlement_actual_transport_targets_official_settlement_route: "
            f"{str(result.official_settlement_actual_transport_targets_official_settlement_route).lower()}"
        ),
        (
            "- official_settlement_actual_transport_targets_generic_order_route: "
            f"{str(result.official_settlement_actual_transport_targets_generic_order_route).lower()}"
        ),
        (
            "- official_settlement_actual_transport_uses_generic_order_executor: "
            f"{str(result.official_settlement_actual_transport_uses_generic_order_executor).lower()}"
        ),
        (
            "- official_settlement_actual_transport_uses_live_order_once: "
            f"{str(result.official_settlement_actual_transport_uses_live_order_once).lower()}"
        ),
        (
            "- official_settlement_actual_transport_uses_one_shot_generic_order: "
            f"{str(result.official_settlement_actual_transport_uses_one_shot_generic_order).lower()}"
        ),
        (
            "- official_settlement_actual_transport_uses_position_specific_path: "
            f"{str(result.official_settlement_actual_transport_uses_position_specific_path).lower()}"
        ),
        (
            "- execution_gate_can_call_actual_transport_after_confirmation: "
            f"{str(result.execution_gate_can_call_actual_transport_after_confirmation).lower()}"
        ),
        (
            "- next_execution_gate_has_no_known_code_blocker: "
            f"{str(result.next_execution_gate_has_no_known_code_blocker).lower()}"
        ),
        f"- fake_http_transport_used: {str(result.fake_http_transport_used).lower()}",
        f"- fake_http_transport_call_count: {result.fake_http_transport_call_count}",
        f"- real_http_client_call_count: {result.real_http_client_call_count}",
        (
            "- actual_transport_real_http_post_executed: "
            f"{str(result.actual_transport_real_http_post_executed).lower()}"
        ),
        (
            "- actual_transport_broker_write_executed: "
            f"{str(result.actual_transport_broker_write_executed).lower()}"
        ),
        f"- settlement_post_count: {result.settlement_post_count}",
        "",
        "```text",
        f"settlement_route_kind={result.settlement_route_kind}",
        f"settlement_route_is_generic_order={result.settlement_route_is_generic_order}",
        f"settlement_route_is_dedicated={result.settlement_route_is_dedicated}",
        (
            "settlement_side_provenance_gate_confirmed="
            f"{result.settlement_side_provenance_gate_confirmed}"
        ),
        (
            "settlement_side_source_safe_artifact_available="
            f"{result.settlement_side_source_safe_artifact_available}"
        ),
        (
            "settlement_side_source_is_default_value="
            f"{result.settlement_side_source_is_default_value}"
        ),
        (
            "settlement_side_safe_artifact_propagated_to_actual_transport_plan="
            f"{result.settlement_side_safe_artifact_propagated_to_actual_transport_plan}"
        ),
        (
            "settlement_side_safe_artifact_propagated_to_execution_gate="
            f"{result.settlement_side_safe_artifact_propagated_to_execution_gate}"
        ),
        (
            "settlement_side_provenance_mechanically_confirmed="
            f"{result.settlement_side_provenance_mechanically_confirmed}"
        ),
        (
            "next_execution_gate_still_requires_fresh_runtime_read="
            f"{result.next_execution_gate_still_requires_fresh_runtime_read}"
        ),
        (
            "next_execution_gate_still_requires_operator_readiness="
            f"{result.next_execution_gate_still_requires_operator_readiness}"
        ),
        (
            "next_execution_gate_still_requires_settlement_specific_confirmation="
            f"{result.next_execution_gate_still_requires_settlement_specific_confirmation}"
        ),
        "```",
    ]
    if result.blocked_reasons:
        lines.append("")
        lines.append("- blocked_reasons:")
        lines.extend(f"  - {reason}" for reason in result.blocked_reasons)
    return "\n".join(lines)


def _default_input_snapshot() -> OfficialSettlementActualTransportInput:
    route_result = build_official_settlement_route_no_post_controlled()
    sender_adapter_result = (
        build_official_settlement_real_network_live_sender_adapter_no_post_controlled()
    )
    side_provenance_result = (
        build_official_settlement_side_provenance_gate_no_post_controlled()
    )
    side_artifact = side_provenance_result.side_provenance_artifact
    return OfficialSettlementActualTransportInput(
        official_settlement_no_post_preview_ready=(
            route_result.official_settlement_no_post_preview_ready
        ),
        official_settlement_executor_preview_ready=(
            route_result.official_settlement_no_post_preview_ready
        ),
        dedicated_settlement_actual_executor_compatibility_ready=(
            sender_adapter_result.dedicated_settlement_actual_executor_compatibility_ready
        ),
        dedicated_actual_official_settlement_post_executor_available=(
            sender_adapter_result.dedicated_actual_official_settlement_post_executor_available
        ),
        dedicated_actual_official_settlement_transport_boundary_ready=(
            sender_adapter_result.dedicated_actual_official_settlement_transport_boundary_ready
        ),
        actual_settlement_post_live_capable_transport_available=(
            sender_adapter_result.actual_settlement_post_live_capable_transport_available
        ),
        actual_settlement_post_can_be_allowed_after_fresh_execution_gates=(
            sender_adapter_result.actual_settlement_post_can_be_allowed_after_fresh_execution_gates
        ),
        dedicated_official_settlement_actual_http_post_sender_confirmed=(
            sender_adapter_result.dedicated_official_settlement_actual_http_post_sender_confirmed
        ),
        dedicated_official_settlement_actual_http_post_sender_callable_available=(
            sender_adapter_result.dedicated_official_settlement_actual_http_post_sender_callable_available
        ),
        dedicated_official_settlement_live_http_sender_adapter_confirmed=(
            sender_adapter_result.dedicated_official_settlement_live_http_sender_adapter_confirmed
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_confirmed=(
            sender_adapter_result.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_callable_available=(
            sender_adapter_result.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
        ),
        concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready=(
            sender_adapter_result.concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready
        ),
        concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization=(
            sender_adapter_result.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization
        ),
        settlement_route_kind=route_result.preview.settlement_route_kind,
        settlement_route_is_generic_order=route_result.preview.settlement_route_is_generic_order,
        settlement_route_is_dedicated=route_result.preview.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=False,
        live_order_once_used_for_settlement=False,
        generic_order_endpoint_used_for_settlement=False,
        one_shot_generic_order_path_used_for_settlement=False,
        position_specific_path_used=False,
        position_specific_identifier_safe_handling_ready=(
            route_result.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=route_result.position_specific_preview_allowed,
        size_based_preview_allowed=route_result.size_based_preview_allowed,
        settlement_side_provenance_gate_confirmed=(
            side_provenance_result.settlement_side_provenance_gate_confirmed
        ),
        settlement_side_source_safe_artifact_available=(
            side_provenance_result.settlement_side_source_safe_artifact_available
        ),
        settlement_side_source_safe_artifact_kind=(
            side_provenance_result.settlement_side_source_safe_artifact_kind
        ),
        settlement_side_source_is_default_value=(
            side_provenance_result.settlement_side_source_is_default_value
        ),
        settlement_side_source_is_operator_input=(
            side_provenance_result.settlement_side_source_is_operator_input
        ),
        settlement_side_source_is_raw_broker_value=(
            side_provenance_result.settlement_side_source_is_raw_broker_value
        ),
        settlement_side_source_is_position_specific_identifier=(
            side_provenance_result
            .settlement_side_source_is_position_specific_identifier
        ),
        settlement_side_source_is_generic_opposite_order=(
            side_provenance_result.settlement_side_source_is_generic_opposite_order
        ),
        settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact=(
            side_provenance_result
            .settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact
        ),
        settlement_side_matches_official_settlement_side_semantics=(
            side_provenance_result
            .settlement_side_matches_official_settlement_side_semantics
        ),
        settlement_side_safe_artifact_propagated_to_official_settlement_preview=(
            side_provenance_result
            .settlement_side_safe_artifact_propagated_to_official_settlement_preview
        ),
        settlement_side_safe_artifact_propagated_to_actual_transport_plan=(
            side_provenance_result
            .settlement_side_safe_artifact_propagated_to_actual_transport_plan
        ),
        settlement_side_safe_artifact_propagated_to_execution_gate=(
            side_provenance_result
            .settlement_side_safe_artifact_propagated_to_execution_gate
        ),
        settlement_side_provenance_mechanically_confirmed=(
            side_provenance_result.settlement_side_provenance_mechanically_confirmed
        ),
        execution_gate_can_verify_settlement_side_provenance_before_post=(
            side_provenance_result
            .execution_gate_can_verify_settlement_side_provenance_before_post
        ),
        next_execution_gate_has_no_known_side_provenance_blocker=(
            side_provenance_result
            .next_execution_gate_has_no_known_side_provenance_blocker
        ),
        settlement_side_safe_label=(
            side_artifact.settlement_side_safe_label
            if side_artifact is not None
            else SETTLEMENT_SIDE_NOT_CONFIRMED_SAFE_LABEL
        ),
        settlement_side_source_safe_label=(
            side_artifact.settlement_side_source_safe_label
            if side_artifact is not None
            else SIDE_PROVENANCE_NOT_CONFIRMED_LABEL
        ),
    )


def _blocked_reasons(snapshot: OfficialSettlementActualTransportInput) -> tuple[str, ...]:
    reasons: list[str] = []
    required_true = {
        "repository_clean": snapshot.repository_clean,
        "head_equals_origin_main": snapshot.head_equals_origin_main,
        "credential_presence_available": snapshot.credential_presence_available,
        "official_settlement_no_post_preview_ready": (
            snapshot.official_settlement_no_post_preview_ready
        ),
        "official_settlement_executor_preview_ready": (
            snapshot.official_settlement_executor_preview_ready
        ),
        "dedicated_settlement_actual_executor_compatibility_ready": (
            snapshot.dedicated_settlement_actual_executor_compatibility_ready
        ),
        "dedicated_actual_official_settlement_post_executor_available": (
            snapshot.dedicated_actual_official_settlement_post_executor_available
        ),
        "dedicated_actual_official_settlement_transport_boundary_ready": (
            snapshot.dedicated_actual_official_settlement_transport_boundary_ready
        ),
        "actual_settlement_post_live_capable_transport_available": (
            snapshot.actual_settlement_post_live_capable_transport_available
        ),
        "actual_settlement_post_can_be_allowed_after_fresh_execution_gates": (
            snapshot.actual_settlement_post_can_be_allowed_after_fresh_execution_gates
        ),
        "dedicated_official_settlement_actual_http_post_sender_confirmed": (
            snapshot.dedicated_official_settlement_actual_http_post_sender_confirmed
        ),
        "dedicated_official_settlement_actual_http_post_sender_callable_available": (
            snapshot.dedicated_official_settlement_actual_http_post_sender_callable_available
        ),
        "dedicated_official_settlement_live_http_sender_adapter_confirmed": (
            snapshot.dedicated_official_settlement_live_http_sender_adapter_confirmed
        ),
        "concrete_real_network_official_settlement_live_http_sender_adapter_confirmed": (
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_confirmed
        ),
        "concrete_real_network_official_settlement_live_http_sender_adapter_callable_available": (
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_callable_available
        ),
        "concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready": (
            snapshot.concrete_real_network_official_settlement_live_http_sender_adapter_boundary_ready
        ),
        "concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization": (
            snapshot.concrete_real_network_adapter_can_be_reached_after_execution_gate_authorization
        ),
        "official_settlement_real_network_client_binding_confirmed": (
            snapshot.official_settlement_real_network_client_binding_confirmed
        ),
        "official_settlement_real_network_client_callable_available": (
            snapshot.official_settlement_real_network_client_callable_available
        ),
        "official_settlement_real_network_transport_binding_ready": (
            snapshot.official_settlement_real_network_transport_binding_ready
        ),
        "official_settlement_real_network_client_targets_official_settlement_route": (
            snapshot.official_settlement_real_network_client_targets_official_settlement_route
        ),
        "real_network_client_binding_can_be_reached_after_execution_gate_authorization": (
            snapshot.real_network_client_binding_can_be_reached_after_execution_gate_authorization
        ),
        "next_execution_gate_can_call_real_network_client_after_confirmation": (
            snapshot.next_execution_gate_can_call_real_network_client_after_confirmation
        ),
        "has_exactly_one_position": snapshot.has_exactly_one_position,
        "operator_broker_ui_checked": snapshot.operator_broker_ui_checked,
        "operator_broker_ui_open_position_visible": (
            snapshot.operator_broker_ui_open_position_visible
        ),
        "operator_can_monitor": snapshot.operator_can_monitor,
        "operator_approves_settlement_attempt": snapshot.operator_approves_settlement_attempt,
        "sanitized_settlement_preview_shown": snapshot.sanitized_settlement_preview_shown,
        "settlement_specific_confirmation_current_turn": (
            snapshot.settlement_specific_confirmation_current_turn
        ),
        "settlement_specific_confirmation_exact_match": (
            snapshot.settlement_specific_confirmation_exact_match
        ),
        "settlement_route_is_dedicated": snapshot.settlement_route_is_dedicated,
        "size_based_preview_allowed": snapshot.size_based_preview_allowed,
        "one_settlement_post_max": snapshot.one_settlement_post_max,
        "settlement_side_provenance_gate_confirmed": (
            snapshot.settlement_side_provenance_gate_confirmed
        ),
        "settlement_side_source_safe_artifact_available": (
            snapshot.settlement_side_source_safe_artifact_available
        ),
        (
            "settlement_side_derived_from_fresh_entry_safe_artifact_"
            "or_approved_safe_position_artifact"
        ): (
            snapshot
            .settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact
        ),
        "settlement_side_matches_official_settlement_side_semantics": (
            snapshot.settlement_side_matches_official_settlement_side_semantics
        ),
        "settlement_side_safe_artifact_propagated_to_official_settlement_preview": (
            snapshot.settlement_side_safe_artifact_propagated_to_official_settlement_preview
        ),
        "settlement_side_safe_artifact_propagated_to_actual_transport_plan": (
            snapshot.settlement_side_safe_artifact_propagated_to_actual_transport_plan
        ),
        "settlement_side_safe_artifact_propagated_to_execution_gate": (
            snapshot.settlement_side_safe_artifact_propagated_to_execution_gate
        ),
        "settlement_side_provenance_mechanically_confirmed": (
            snapshot.settlement_side_provenance_mechanically_confirmed
        ),
        "execution_gate_can_verify_settlement_side_provenance_before_post": (
            snapshot.execution_gate_can_verify_settlement_side_provenance_before_post
        ),
        "next_execution_gate_has_no_known_side_provenance_blocker": (
            snapshot.next_execution_gate_has_no_known_side_provenance_blocker
        ),
    }
    for name, value in required_true.items():
        if not value:
            reasons.append(f"{name}=false")

    required_false = {
        "official_settlement_real_network_client_targets_generic_order_route": (
            snapshot.official_settlement_real_network_client_targets_generic_order_route
        ),
        "official_settlement_real_network_client_uses_generic_order_executor": (
            snapshot.official_settlement_real_network_client_uses_generic_order_executor
        ),
        "official_settlement_real_network_client_uses_live_order_once": (
            snapshot.official_settlement_real_network_client_uses_live_order_once
        ),
        "official_settlement_real_network_client_uses_one_shot_generic_order": (
            snapshot.official_settlement_real_network_client_uses_one_shot_generic_order
        ),
        "official_settlement_real_network_client_uses_position_specific_path": (
            snapshot.official_settlement_real_network_client_uses_position_specific_path
        ),
        "settlement_side_source_is_default_value": (
            snapshot.settlement_side_source_is_default_value
        ),
        "settlement_side_source_is_operator_input": (
            snapshot.settlement_side_source_is_operator_input
        ),
        "settlement_side_source_is_raw_broker_value": (
            snapshot.settlement_side_source_is_raw_broker_value
        ),
        "settlement_side_source_is_position_specific_identifier": (
            snapshot.settlement_side_source_is_position_specific_identifier
        ),
        "settlement_side_source_is_generic_opposite_order": (
            snapshot.settlement_side_source_is_generic_opposite_order
        ),
        "has_multiple_positions": snapshot.has_multiple_positions,
        "operator_broker_ui_values_or_ids_provided": (
            snapshot.operator_broker_ui_values_or_ids_provided
        ),
        "settlement_route_is_generic_order": snapshot.settlement_route_is_generic_order,
        "generic_order_executor_used_for_settlement": (
            snapshot.generic_order_executor_used_for_settlement
        ),
        "live_order_once_used_for_settlement": snapshot.live_order_once_used_for_settlement,
        "generic_order_endpoint_used_for_settlement": (
            snapshot.generic_order_endpoint_used_for_settlement
        ),
        "one_shot_generic_order_path_used_for_settlement": (
            snapshot.one_shot_generic_order_path_used_for_settlement
        ),
        "position_specific_path_used": snapshot.position_specific_path_used,
        "position_specific_identifier_safe_handling_ready": (
            snapshot.position_specific_identifier_safe_handling_ready
        ),
        "position_specific_preview_allowed": snapshot.position_specific_preview_allowed,
        "retry_allowed": snapshot.retry_allowed,
        "repost_allowed": snapshot.repost_allowed,
        "second_settlement_allowed": snapshot.second_settlement_allowed,
        "entry_post_allowed": snapshot.entry_post_allowed,
        "generic_close_allowed": snapshot.generic_close_allowed,
        "ledger_update_allowed": snapshot.ledger_update_allowed,
        "receipt_handoff_allowed": snapshot.receipt_handoff_allowed,
        "raw_id_value_credential_header_exposure": (
            snapshot.raw_id_value_credential_header_exposure
        ),
        "env_read": snapshot.env_read,
    }
    for name, value in required_false.items():
        if value:
            reasons.append(f"{name}=true")

    if snapshot.runtime_position_status != PositionReadOnlyControlledStatus.ONE_POSITION_OPEN.value:
        reasons.append(f"runtime_position_status={snapshot.runtime_position_status}")
    if snapshot.position_count_safe != 1:
        reasons.append(f"position_count_safe={snapshot.position_count_safe}")
    if snapshot.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        reasons.append(f"settlement_route_kind={snapshot.settlement_route_kind}")
    if snapshot.settlement_size_safe_value != SUPPORTED_UNITS:
        reasons.append("settlement_size_safe_value_not_supported")
    if not snapshot.settlement_symbol_safe_label:
        reasons.append("settlement_symbol_safe_label=empty")
    if snapshot.settlement_side_source_safe_artifact_kind != APPROVED_SAFE_ARTIFACT_KIND:
        reasons.append("settlement_side_source_safe_artifact_kind_not_approved")
    if (
        snapshot.settlement_side_source_safe_label
        != SETTLEMENT_SIDE_SOURCE_APPROVED_SAFE_ARTIFACT_LABEL
    ):
        reasons.append("settlement_side_source_safe_label_not_approved_artifact")
    if (
        not snapshot.settlement_side_safe_label
        or snapshot.settlement_side_safe_label == SETTLEMENT_SIDE_NOT_CONFIRMED_SAFE_LABEL
    ):
        reasons.append("settlement_side_safe_label=empty")
    if not snapshot.settlement_execution_type_safe_label:
        reasons.append("settlement_execution_type_safe_label=empty")

    return tuple(reasons)


def _build_plan(
    snapshot: OfficialSettlementActualTransportInput,
) -> OfficialSettlementActualTransportPlan:
    return OfficialSettlementActualTransportPlan(
        step_name=STEP_NAME,
        route_kind=snapshot.settlement_route_kind,
        route_safe_label=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_ROUTE_SAFE_LABEL,
        parameter_shape_safe_label=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_PARAMETER_SHAPE_SAFE_LABEL,
        method_safe_label=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_METHOD,
        settlement_symbol_safe_label=snapshot.settlement_symbol_safe_label,
        settlement_side_safe_label=snapshot.settlement_side_safe_label,
        settlement_side_source_safe_label=snapshot.settlement_side_source_safe_label,
        settlement_execution_type_safe_label=snapshot.settlement_execution_type_safe_label,
        settlement_size_safe_value=snapshot.settlement_size_safe_value,
        size_based_settlement=True,
        position_specific_identifier_required=False,
        one_settlement_post_max=snapshot.one_settlement_post_max,
        retry_allowed=snapshot.retry_allowed,
        repost_allowed=snapshot.repost_allowed,
        second_settlement_allowed=snapshot.second_settlement_allowed,
        entry_post_allowed=snapshot.entry_post_allowed,
        generic_close_allowed=snapshot.generic_close_allowed,
        raw_id_value_credential_header_exposure=(
            snapshot.raw_id_value_credential_header_exposure
        ),
    )


def _validate_plan_is_official_settlement_only(
    plan: OfficialSettlementActualTransportPlan,
) -> None:
    errors: list[str] = []
    if plan.route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        errors.append("route_kind_not_official_size_based")
    if not plan.size_based_settlement:
        errors.append("size_based_settlement=false")
    if plan.position_specific_identifier_required:
        errors.append("position_specific_identifier_required=true")
    if not plan.one_settlement_post_max:
        errors.append("one_settlement_post_max=false")
    if plan.retry_allowed:
        errors.append("retry_allowed=true")
    if plan.repost_allowed:
        errors.append("repost_allowed=true")
    if plan.second_settlement_allowed:
        errors.append("second_settlement_allowed=true")
    if plan.entry_post_allowed:
        errors.append("entry_post_allowed=true")
    if plan.generic_close_allowed:
        errors.append("generic_close_allowed=true")
    if plan.raw_id_value_credential_header_exposure:
        errors.append("raw_id_value_credential_header_exposure=true")
    if plan.settlement_side_safe_label == SETTLEMENT_SIDE_NOT_CONFIRMED_SAFE_LABEL:
        errors.append("settlement_side_provenance_not_confirmed")
    if (
        plan.settlement_side_source_safe_label
        != SETTLEMENT_SIDE_SOURCE_APPROVED_SAFE_ARTIFACT_LABEL
    ):
        errors.append("settlement_side_source_not_approved_safe_artifact")
    if errors:
        raise LiveVerificationValidationError(
            "official settlement actual transport plan blocked: " + ",".join(errors)
        )


def _serialize_official_settlement_body(
    plan: OfficialSettlementActualTransportPlan,
) -> str:
    _validate_plan_is_official_settlement_only(plan)
    body = {
        "symbol": plan.settlement_symbol_safe_label,
        "side": plan.settlement_side_safe_label,
        "executionType": plan.settlement_execution_type_safe_label,
        "size": str(plan.settlement_size_safe_value),
    }
    return json.dumps(body, separators=(",", ":"), sort_keys=True)


def _sanitize_http_response_status(response: httpx.Response) -> str:
    if response.status_code >= 500:
        return OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_UNKNOWN_RESULT
    if response.status_code >= 400:
        return OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_REJECTED_RESULT
    try:
        payload: Mapping[str, object] = response.json()
    except ValueError:
        return OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_UNKNOWN_RESULT
    if payload.get("status") == 0:
        return OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_ACCEPTED_RESULT
    return OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_REJECTED_RESULT


def _no_call_client_result() -> OfficialSettlementActualTransportClientResult:
    return OfficialSettlementActualTransportClientResult(
        sanitized_result_category=OFFICIAL_SETTLEMENT_ACTUAL_TRANSPORT_BLOCKED_RESULT,
        fake_http_transport_used=False,
        fake_http_transport_call_count=0,
        real_http_client_call_count=0,
        actual_transport_real_http_post_executed=False,
        actual_transport_broker_write_executed=False,
        simulated_settlement_post_count=0,
    )


def as_safe_dict(result: OfficialSettlementActualTransportResult) -> dict[str, object]:
    safe = asdict(result)
    safe.pop("actual_transport_plan", None)
    return safe
