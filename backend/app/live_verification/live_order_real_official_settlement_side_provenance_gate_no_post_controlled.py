"""Official settlement side provenance gate for Step 6G.

This module proves, without POSTing, that the settlement side used by the
official settlement transport comes from an approved safe artifact. It never
uses operator-entered side values, raw broker values, position identifiers,
generic opposite orders, HTTP clients, credentials, ledgers, or receipts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_close_order_execution_route_controlled import (
    SAFE_SIDE_BUY,
    SAFE_SIDE_SELL,
    SIDE_NOT_PROVIDED,
    SIDE_SOURCE_FRESH_ENTRY,
    SIDE_SOURCE_MULTIPLE_SAFE_INPUTS,
    SIDE_SOURCE_POSITION_SIDE,
    CloseOrderExecutionRouteControlledInput,
    derive_close_side_safe_label,
)
from app.live_verification.live_order_real_fresh_post_entry_position_confirmation_gate_controlled import (  # noqa: E501
    FreshEntryPostSafeSummaryInput,
)
from app.live_verification.live_order_real_official_settlement_route_no_post_controlled import (
    SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED,
    SETTLEMENT_SIDE_SEMANTICS_CONFIRMED,
    build_official_settlement_route_no_post_controlled,
)
from app.live_verification.live_order_real_one_shot_post_execution_controlled import (
    LiveOrderRealExecutableOrderPreviewInput,
    LiveOrderRealExecutableOrderPreviewStatus,
    build_live_order_real_executable_order_preview,
)
from app.live_verification.live_order_real_position_read_only_controlled import (
    PositionReadOnlyControlledStatus,
)
from app.live_verification.live_order_real_sanitized_post_result import (
    SafePostResultCategory,
    SafeReconciliationStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL, SUPPORTED_UNITS

STEP_NAME = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-"
    "SIDE-PROVENANCE-GATE-NO-POST-C"
)

RESULT_SETTLEMENT_SIDE_PROVENANCE_CONFIRMED = (
    "RESULT_SETTLEMENT_SIDE_PROVENANCE_CONFIRMED_NO_POST_SANITIZED"
)
RESULT_SETTLEMENT_SIDE_PROVENANCE_BLOCKED = (
    "RESULT_SETTLEMENT_SIDE_PROVENANCE_BLOCKED_NO_POST_SANITIZED"
)

APPROVED_SAFE_ARTIFACT_KIND = "APPROVED_SAFE_ARTIFACT"
SETTLEMENT_SIDE_SOURCE_APPROVED_SAFE_ARTIFACT_LABEL = (
    "SETTLEMENT_SIDE_FROM_APPROVED_SAFE_ARTIFACT"
)
FRESH_ENTRY_SAFE_SIDE_ARTIFACT_SOURCE_LABEL = "FRESH_ENTRY_SAFE_SIDE_ARTIFACT"
APPROVED_SAFE_POSITION_SIDE_ARTIFACT_SOURCE_LABEL = (
    "APPROVED_SAFE_POSITION_SIDE_ARTIFACT"
)
MULTIPLE_APPROVED_SAFE_ARTIFACTS_SOURCE_LABEL = "MULTIPLE_APPROVED_SAFE_ARTIFACTS"
SIDE_PROVENANCE_NOT_CONFIRMED_LABEL = "SIDE_PROVENANCE_NOT_CONFIRMED"

_CONCRETE_SIDE_LABELS = frozenset({SAFE_SIDE_BUY, SAFE_SIDE_SELL})


class OfficialSettlementSideProvenanceStatus(StrEnum):
    READY_NO_POST = "SIDE_PROVENANCE_READY_NO_POST"
    BLOCKED_NO_POST = "SIDE_PROVENANCE_BLOCKED_NO_POST"


@dataclass(frozen=True)
class OfficialSettlementSideProvenanceArtifact:
    artifact_kind: str
    source_artifact_label: str
    source_side_safe_label: str
    settlement_side_safe_label: str
    settlement_side_source_safe_label: str
    derived_from_fresh_entry_safe_artifact: bool
    derived_from_approved_safe_position_artifact: bool
    side_mismatch_detected: bool
    codex_inferred_side: bool

    def __post_init__(self) -> None:
        for field_name in (
            "artifact_kind",
            "source_artifact_label",
            "source_side_safe_label",
            "settlement_side_safe_label",
            "settlement_side_source_safe_label",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _ARTIFACT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementSideProvenanceInput:
    fresh_entry_summary: FreshEntryPostSafeSummaryInput = field(
        default_factory=FreshEntryPostSafeSummaryInput,
    )
    fresh_entry_preview: LiveOrderRealExecutableOrderPreviewInput = field(
        default_factory=LiveOrderRealExecutableOrderPreviewInput,
    )
    fresh_entry_safe_side_artifact_found: bool = True
    approved_safe_position_side_artifact_found: bool = False
    approved_safe_position_side_artifact_required: bool = False
    approved_safe_position_side_label: str = SIDE_NOT_PROVIDED

    settlement_side_source_safe_artifact_kind: str = APPROVED_SAFE_ARTIFACT_KIND
    settlement_side_source_is_default_value: bool = False
    settlement_side_source_is_operator_input: bool = False
    settlement_side_source_is_raw_broker_value: bool = False
    settlement_side_source_is_position_specific_identifier: bool = False
    settlement_side_source_is_generic_opposite_order: bool = False

    settlement_side_safe_artifact_propagated_to_official_settlement_preview: bool = True
    settlement_side_safe_artifact_propagated_to_actual_transport_plan: bool = True
    settlement_side_safe_artifact_propagated_to_execution_gate: bool = True

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

    retry_allowed: bool = False
    repost_allowed: bool = False
    second_settlement_allowed: bool = False
    entry_post_executed: bool = False
    generic_close_post_executed: bool = False
    ledger_update: bool = False
    receipt_handoff: bool = False
    raw_id_value_credential_header_exposure: bool = False
    actual_settlement_post_executed: bool = False
    real_http_post_executed: bool = False
    broker_write_executed: bool = False
    real_network_client_invocation_count: int = 0
    settlement_post_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.fresh_entry_summary, FreshEntryPostSafeSummaryInput):
            raise LiveVerificationValidationError(
                "fresh_entry_summary must be FreshEntryPostSafeSummaryInput",
            )
        if not isinstance(
            self.fresh_entry_preview,
            LiveOrderRealExecutableOrderPreviewInput,
        ):
            raise LiveVerificationValidationError(
                "fresh_entry_preview must be LiveOrderRealExecutableOrderPreviewInput",
            )
        _require_non_empty(
            "approved_safe_position_side_label",
            self.approved_safe_position_side_label,
        )
        _require_non_empty(
            "settlement_side_source_safe_artifact_kind",
            self.settlement_side_source_safe_artifact_kind,
        )
        _require_non_empty("settlement_route_kind", self.settlement_route_kind)
        _validate_non_negative_int(
            "real_network_client_invocation_count",
            self.real_network_client_invocation_count,
        )
        _validate_non_negative_int("settlement_post_count", self.settlement_post_count)
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class OfficialSettlementSideProvenanceResult:
    step_name: str
    status: OfficialSettlementSideProvenanceStatus
    sanitized_result_category: str
    blocked_reasons: tuple[str, ...]

    settlement_side_provenance_gate_confirmed: bool
    settlement_side_source_safe_artifact_available: bool
    settlement_side_source_safe_artifact_kind: str
    settlement_side_source_is_default_value: bool
    settlement_side_source_is_operator_input: bool
    settlement_side_source_is_raw_broker_value: bool
    settlement_side_source_is_position_specific_identifier: bool
    settlement_side_source_is_generic_opposite_order: bool

    fresh_entry_safe_side_artifact_found: bool
    approved_safe_position_side_artifact_found: bool
    settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact: bool
    settlement_side_matches_official_settlement_side_semantics: bool
    settlement_side_safe_artifact_propagated_to_official_settlement_preview: bool
    settlement_side_safe_artifact_propagated_to_actual_transport_plan: bool
    settlement_side_safe_artifact_propagated_to_execution_gate: bool
    settlement_side_provenance_mechanically_confirmed: bool

    actual_transport_side_currently_default: bool
    actual_transport_side_currently_operator_input: bool
    actual_transport_side_currently_raw_broker_value: bool
    actual_transport_side_currently_generic_opposite_order: bool

    execution_gate_can_verify_settlement_side_provenance_before_post: bool
    execution_gate_can_call_actual_transport_after_confirmation: bool
    next_execution_gate_has_no_known_side_provenance_blocker: bool

    official_settlement_actual_transport_confirmed: bool
    official_settlement_real_network_client_binding_confirmed: bool
    official_settlement_no_post_preview_ready: bool
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

    this_step_actual_settlement_post_executed: bool
    official_settlement_post_count: int
    real_http_post_executed: bool
    broker_write_executed: bool
    real_network_client_invocation_count: int
    retry_allowed: bool
    repost_allowed: bool
    second_settlement_allowed: bool
    entry_post_executed: bool
    generic_close_post_executed: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_id_value_credential_header_exposure: bool

    next_execution_gate_still_requires_fresh_runtime_read: bool
    next_execution_gate_still_requires_operator_readiness: bool
    next_execution_gate_still_requires_settlement_specific_confirmation: bool

    side_provenance_artifact: OfficialSettlementSideProvenanceArtifact | None = field(
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.status, OfficialSettlementSideProvenanceStatus):
            raise LiveVerificationValidationError("status must be side provenance enum")
        _require_non_empty("step_name", self.step_name)
        _require_non_empty("sanitized_result_category", self.sanitized_result_category)
        _require_non_empty(
            "settlement_side_source_safe_artifact_kind",
            self.settlement_side_source_safe_artifact_kind,
        )
        _require_non_empty("settlement_route_kind", self.settlement_route_kind)
        _validate_non_negative_int(
            "official_settlement_post_count",
            self.official_settlement_post_count,
        )
        _validate_non_negative_int(
            "real_network_client_invocation_count",
            self.real_network_client_invocation_count,
        )
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_official_settlement_side_provenance_gate_no_post_controlled(
    input_snapshot: OfficialSettlementSideProvenanceInput | None = None,
) -> OfficialSettlementSideProvenanceResult:
    snapshot = input_snapshot or OfficialSettlementSideProvenanceInput()
    entry_preview = build_live_order_real_executable_order_preview(
        snapshot.fresh_entry_preview,
    )
    route_result = build_official_settlement_route_no_post_controlled()
    side_summary = derive_close_side_safe_label(_side_derivation_input(snapshot, entry_preview))
    reasons = _blocked_reasons(snapshot, entry_preview, route_result, side_summary)
    ready = not reasons
    source_artifact_available = (
        snapshot.fresh_entry_safe_side_artifact_found
        or snapshot.approved_safe_position_side_artifact_found
    )
    side_semantics_confirmed = (
        route_result.preview.settlement_side_semantics_safe_label
        == SETTLEMENT_SIDE_SEMANTICS_CONFIRMED
    )
    source_kind = (
        APPROVED_SAFE_ARTIFACT_KIND
        if ready
        else snapshot.settlement_side_source_safe_artifact_kind
    )
    source_label = _source_artifact_label(side_summary.close_side_derivation_source)
    artifact = (
        OfficialSettlementSideProvenanceArtifact(
            artifact_kind=source_kind,
            source_artifact_label=source_label,
            source_side_safe_label=side_summary.input_side_safe_label,
            settlement_side_safe_label=side_summary.close_side_safe_label,
            settlement_side_source_safe_label=(
                SETTLEMENT_SIDE_SOURCE_APPROVED_SAFE_ARTIFACT_LABEL
            ),
            derived_from_fresh_entry_safe_artifact=(
                side_summary.close_side_derivation_source
                in {SIDE_SOURCE_FRESH_ENTRY, SIDE_SOURCE_MULTIPLE_SAFE_INPUTS}
            ),
            derived_from_approved_safe_position_artifact=(
                side_summary.close_side_derivation_source
                in {SIDE_SOURCE_POSITION_SIDE, SIDE_SOURCE_MULTIPLE_SAFE_INPUTS}
            ),
            side_mismatch_detected=side_summary.side_mismatch_detected,
            codex_inferred_side=side_summary.codex_inferred_side,
        )
        if ready
        else None
    )
    mechanically_confirmed = (
        ready
        and artifact is not None
        and source_artifact_available
        and side_semantics_confirmed
        and snapshot.settlement_side_safe_artifact_propagated_to_official_settlement_preview
        and snapshot.settlement_side_safe_artifact_propagated_to_actual_transport_plan
        and snapshot.settlement_side_safe_artifact_propagated_to_execution_gate
        and side_summary.side_concrete
        and not side_summary.codex_inferred_side
        and not side_summary.side_mismatch_detected
    )

    return OfficialSettlementSideProvenanceResult(
        step_name=STEP_NAME,
        status=(
            OfficialSettlementSideProvenanceStatus.READY_NO_POST
            if ready
            else OfficialSettlementSideProvenanceStatus.BLOCKED_NO_POST
        ),
        sanitized_result_category=(
            RESULT_SETTLEMENT_SIDE_PROVENANCE_CONFIRMED
            if ready
            else RESULT_SETTLEMENT_SIDE_PROVENANCE_BLOCKED
        ),
        blocked_reasons=reasons,
        settlement_side_provenance_gate_confirmed=ready,
        settlement_side_source_safe_artifact_available=(
            source_artifact_available and ready
        ),
        settlement_side_source_safe_artifact_kind=source_kind,
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
        fresh_entry_safe_side_artifact_found=(
            snapshot.fresh_entry_safe_side_artifact_found and ready
        ),
        approved_safe_position_side_artifact_found=(
            snapshot.approved_safe_position_side_artifact_found and ready
        ),
        settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact=(
            ready
            and side_summary.close_side_derivation_source
            in {
                SIDE_SOURCE_FRESH_ENTRY,
                SIDE_SOURCE_POSITION_SIDE,
                SIDE_SOURCE_MULTIPLE_SAFE_INPUTS,
            }
        ),
        settlement_side_matches_official_settlement_side_semantics=(
            ready and side_semantics_confirmed
        ),
        settlement_side_safe_artifact_propagated_to_official_settlement_preview=(
            snapshot.settlement_side_safe_artifact_propagated_to_official_settlement_preview
            and ready
        ),
        settlement_side_safe_artifact_propagated_to_actual_transport_plan=(
            snapshot.settlement_side_safe_artifact_propagated_to_actual_transport_plan
            and ready
        ),
        settlement_side_safe_artifact_propagated_to_execution_gate=(
            snapshot.settlement_side_safe_artifact_propagated_to_execution_gate and ready
        ),
        settlement_side_provenance_mechanically_confirmed=mechanically_confirmed,
        actual_transport_side_currently_default=(
            snapshot.settlement_side_source_is_default_value
        ),
        actual_transport_side_currently_operator_input=(
            snapshot.settlement_side_source_is_operator_input
        ),
        actual_transport_side_currently_raw_broker_value=(
            snapshot.settlement_side_source_is_raw_broker_value
        ),
        actual_transport_side_currently_generic_opposite_order=(
            snapshot.settlement_side_source_is_generic_opposite_order
        ),
        execution_gate_can_verify_settlement_side_provenance_before_post=(
            mechanically_confirmed
        ),
        execution_gate_can_call_actual_transport_after_confirmation=mechanically_confirmed,
        next_execution_gate_has_no_known_side_provenance_blocker=mechanically_confirmed,
        official_settlement_actual_transport_confirmed=ready,
        official_settlement_real_network_client_binding_confirmed=ready,
        official_settlement_no_post_preview_ready=(
            route_result.official_settlement_no_post_preview_ready and ready
        ),
        settlement_route_kind=snapshot.settlement_route_kind,
        settlement_route_is_generic_order=snapshot.settlement_route_is_generic_order,
        settlement_route_is_dedicated=snapshot.settlement_route_is_dedicated,
        generic_order_executor_used_for_settlement=(
            snapshot.generic_order_executor_used_for_settlement
        ),
        live_order_once_used_for_settlement=snapshot.live_order_once_used_for_settlement,
        generic_order_endpoint_used_for_settlement=(
            snapshot.generic_order_endpoint_used_for_settlement
        ),
        one_shot_generic_order_path_used_for_settlement=(
            snapshot.one_shot_generic_order_path_used_for_settlement
        ),
        position_specific_path_used=snapshot.position_specific_path_used,
        position_specific_identifier_safe_handling_ready=(
            snapshot.position_specific_identifier_safe_handling_ready
        ),
        position_specific_preview_allowed=snapshot.position_specific_preview_allowed,
        size_based_preview_allowed=snapshot.size_based_preview_allowed and ready,
        this_step_actual_settlement_post_executed=False,
        official_settlement_post_count=0,
        real_http_post_executed=False,
        broker_write_executed=False,
        real_network_client_invocation_count=0,
        retry_allowed=False,
        repost_allowed=False,
        second_settlement_allowed=False,
        entry_post_executed=False,
        generic_close_post_executed=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_id_value_credential_header_exposure=False,
        next_execution_gate_still_requires_fresh_runtime_read=True,
        next_execution_gate_still_requires_operator_readiness=True,
        next_execution_gate_still_requires_settlement_specific_confirmation=True,
        side_provenance_artifact=artifact,
    )


def render_official_settlement_side_provenance_gate_no_post_markdown(
    result: OfficialSettlementSideProvenanceResult,
) -> str:
    blocked = ", ".join(result.blocked_reasons) or "none"
    return "\n".join(
        (
            "# Official Settlement Side Provenance Gate No-POST",
            "",
            f"- step_name: {result.step_name}",
            f"- status: {result.status.value}",
            f"- sanitized_result_category: {result.sanitized_result_category}",
            (
                "- settlement_side_provenance_gate_confirmed: "
                f"{_bool_text(result.settlement_side_provenance_gate_confirmed)}"
            ),
            (
                "- settlement_side_source_safe_artifact_available: "
                f"{_bool_text(result.settlement_side_source_safe_artifact_available)}"
            ),
            (
                "- settlement_side_source_safe_artifact_kind: "
                f"{result.settlement_side_source_safe_artifact_kind}"
            ),
            (
                "- settlement_side_source_is_default_value: "
                f"{_bool_text(result.settlement_side_source_is_default_value)}"
            ),
            (
                "- settlement_side_source_is_operator_input: "
                f"{_bool_text(result.settlement_side_source_is_operator_input)}"
            ),
            (
                "- settlement_side_source_is_raw_broker_value: "
                f"{_bool_text(result.settlement_side_source_is_raw_broker_value)}"
            ),
            (
                "- settlement_side_source_is_generic_opposite_order: "
                f"{_bool_text(result.settlement_side_source_is_generic_opposite_order)}"
            ),
            (
                "- settlement_side_safe_artifact_propagated_to_actual_transport_plan: "
                f"{_bool_text(result.settlement_side_safe_artifact_propagated_to_actual_transport_plan)}"
            ),
            (
                "- settlement_side_safe_artifact_propagated_to_execution_gate: "
                f"{_bool_text(result.settlement_side_safe_artifact_propagated_to_execution_gate)}"
            ),
            (
                "- settlement_side_provenance_mechanically_confirmed: "
                f"{_bool_text(result.settlement_side_provenance_mechanically_confirmed)}"
            ),
            (
                "- execution_gate_can_verify_settlement_side_provenance_before_post: "
                f"{_bool_text(result.execution_gate_can_verify_settlement_side_provenance_before_post)}"
            ),
            (
                "- next_execution_gate_has_no_known_side_provenance_blocker: "
                f"{_bool_text(result.next_execution_gate_has_no_known_side_provenance_blocker)}"
            ),
            f"- actual_settlement_post_executed: {_bool_text(False)}",
            f"- real_http_post_executed: {_bool_text(False)}",
            f"- broker_write_executed: {_bool_text(False)}",
            f"- official_settlement_post_count: {result.official_settlement_post_count}",
            f"- blocked_reasons: {blocked}",
        ),
    ) + "\n"


def as_safe_dict(result: OfficialSettlementSideProvenanceResult) -> dict[str, object]:
    safe = asdict(result)
    safe.pop("side_provenance_artifact", None)
    return safe


def _side_derivation_input(
    snapshot: OfficialSettlementSideProvenanceInput,
    entry_preview,
) -> CloseOrderExecutionRouteControlledInput:
    return CloseOrderExecutionRouteControlledInput(
        runtime_position_status=PositionReadOnlyControlledStatus.ONE_POSITION_OPEN,
        position_count_safe=1,
        has_exactly_one_position=True,
        has_multiple_positions=False,
        close_route_ready=True,
        close_planning_allowed=True,
        fresh_entry_side_safe_label=(
            entry_preview.side
            if snapshot.fresh_entry_safe_side_artifact_found
            else SIDE_NOT_PROVIDED
        ),
        safe_position_side_label=(
            snapshot.approved_safe_position_side_label
            if snapshot.approved_safe_position_side_artifact_found
            else SIDE_NOT_PROVIDED
        ),
        close_symbol_safe_label=SUPPORTED_SYMBOL,
        close_units_fixed=SUPPORTED_UNITS,
        approved_close_post_primitive_kind="CLOSE_SPECIFIC_APPROVED_PRIMITIVE_NO_POST",
        approved_close_post_primitive_is_close_specific=True,
        approved_close_post_primitive_is_generic_order=False,
        generic_order_accepted_as_close_only_with_exact_one_position_guard=False,
        official_settlement_route_confirmed=True,
    )


def _blocked_reasons(
    snapshot: OfficialSettlementSideProvenanceInput,
    entry_preview,
    route_result,
    side_summary,
) -> tuple[str, ...]:
    reasons: list[str] = []
    reasons.extend(_fresh_entry_summary_reasons(snapshot.fresh_entry_summary))
    if (
        entry_preview.status
        is not LiveOrderRealExecutableOrderPreviewStatus
        .EXECUTABLE_ORDER_PREVIEW_AVAILABLE_SAFE_SUMMARY
    ):
        reasons.append("fresh_entry_safe_side_artifact_preview_not_ready")
    if not entry_preview.sanitized_order_preview_available:
        reasons.append("fresh_entry_safe_side_artifact_preview_unavailable")
    if entry_preview.blocked_reasons:
        reasons.extend(f"fresh_entry_preview:{reason}" for reason in entry_preview.blocked_reasons)
    if entry_preview.side not in _CONCRETE_SIDE_LABELS:
        reasons.append("fresh_entry_safe_side_artifact_not_concrete")
    if entry_preview.safe_order_source_label != "STEP6G_REPO_DEFINED_ORDER_INTENT":
        reasons.append("fresh_entry_safe_side_artifact_source_not_repo_defined")
    for field_name in (
        "codex_inferred_symbol",
        "codex_inferred_side",
        "codex_inferred_size",
        "codex_inferred_order_type",
    ):
        if getattr(entry_preview, field_name):
            reasons.append(f"{field_name}=true")
    if not (
        snapshot.fresh_entry_safe_side_artifact_found
        or snapshot.approved_safe_position_side_artifact_found
    ):
        reasons.append("settlement_side_source_safe_artifact_missing")
    if (
        snapshot.approved_safe_position_side_artifact_required
        and not snapshot.approved_safe_position_side_artifact_found
    ):
        reasons.append("approved_safe_position_side_artifact_missing")
    if (
        snapshot.approved_safe_position_side_artifact_found
        and snapshot.approved_safe_position_side_label not in _CONCRETE_SIDE_LABELS
    ):
        reasons.append("approved_safe_position_side_artifact_not_concrete")
    if snapshot.settlement_side_source_safe_artifact_kind != APPROVED_SAFE_ARTIFACT_KIND:
        reasons.append("settlement_side_source_safe_artifact_kind_not_approved")
    for name in (
        "settlement_side_source_is_default_value",
        "settlement_side_source_is_operator_input",
        "settlement_side_source_is_raw_broker_value",
        "settlement_side_source_is_position_specific_identifier",
        "settlement_side_source_is_generic_opposite_order",
    ):
        if getattr(snapshot, name):
            reasons.append(f"{name}=true")
    if not side_summary.side_concrete:
        reasons.append("settlement_side_not_concrete")
    if side_summary.side_mismatch_detected:
        reasons.append("settlement_side_safe_artifact_mismatch")
    if side_summary.codex_inferred_side:
        reasons.append("settlement_side_codex_inferred")
    if side_summary.opposite_placeholder_accepted:
        reasons.append("settlement_side_opposite_placeholder_accepted")
    if side_summary.close_side_safe_label not in _CONCRETE_SIDE_LABELS:
        reasons.append("settlement_side_safe_label_not_concrete")
    if not route_result.official_settlement_no_post_preview_ready:
        reasons.append("official_settlement_no_post_preview_not_ready")
    if snapshot.settlement_route_kind != SETTLEMENT_ROUTE_KIND_OFFICIAL_SIZE_BASED:
        reasons.append(f"settlement_route_kind={snapshot.settlement_route_kind}")
    if snapshot.settlement_route_is_generic_order:
        reasons.append("settlement_route_is_generic_order=true")
    if not snapshot.settlement_route_is_dedicated:
        reasons.append("settlement_route_is_dedicated=false")
    if (
        route_result.preview.settlement_side_semantics_safe_label
        != SETTLEMENT_SIDE_SEMANTICS_CONFIRMED
    ):
        reasons.append("settlement_side_semantics_not_confirmed")
    required_propagation = {
        "settlement_side_safe_artifact_propagated_to_official_settlement_preview": (
            snapshot.settlement_side_safe_artifact_propagated_to_official_settlement_preview
        ),
        "settlement_side_safe_artifact_propagated_to_actual_transport_plan": (
            snapshot.settlement_side_safe_artifact_propagated_to_actual_transport_plan
        ),
        "settlement_side_safe_artifact_propagated_to_execution_gate": (
            snapshot.settlement_side_safe_artifact_propagated_to_execution_gate
        ),
        "size_based_preview_allowed": snapshot.size_based_preview_allowed,
    }
    for name, value in required_propagation.items():
        if not value:
            reasons.append(f"{name}=false")
    for name in (
        "generic_order_executor_used_for_settlement",
        "live_order_once_used_for_settlement",
        "generic_order_endpoint_used_for_settlement",
        "one_shot_generic_order_path_used_for_settlement",
        "position_specific_path_used",
        "position_specific_identifier_safe_handling_ready",
        "position_specific_preview_allowed",
        "retry_allowed",
        "repost_allowed",
        "second_settlement_allowed",
        "entry_post_executed",
        "generic_close_post_executed",
        "ledger_update",
        "receipt_handoff",
        "raw_id_value_credential_header_exposure",
        "actual_settlement_post_executed",
        "real_http_post_executed",
        "broker_write_executed",
    ):
        if getattr(snapshot, name):
            reasons.append(f"{name}=true")
    if snapshot.real_network_client_invocation_count != 0:
        reasons.append("real_network_client_invocation_count_not_zero")
    if snapshot.settlement_post_count != 0:
        reasons.append("settlement_post_count_not_zero")
    return tuple(dict.fromkeys(reasons))


def _fresh_entry_summary_reasons(summary: FreshEntryPostSafeSummaryInput) -> list[str]:
    reasons: list[str] = []
    if not summary.fresh_entry_http_post_executed:
        reasons.append("fresh_entry_post_not_executed")
    if summary.fresh_entry_post_execution_count != 1:
        reasons.append("fresh_entry_post_count_not_one")
    if (
        summary.fresh_entry_sanitized_result_category
        != SafePostResultCategory.RESULT_ACCEPTED_SANITIZED.value
    ):
        reasons.append("fresh_entry_result_not_accepted_sanitized")
    if (
        summary.fresh_entry_safe_reconciliation_status
        != SafeReconciliationStatus.RECONCILIATION_READY_NO_RECEIPT_HANDOFF.value
    ):
        reasons.append("fresh_entry_reconciliation_not_ready")
    for name in (
        "fresh_entry_retry_attempted",
        "fresh_entry_repost_attempted",
        "fresh_entry_second_post_attempted",
        "close_post_executed",
        "ledger_updated",
        "receipt_handoff_executed",
        "raw_request_exposed",
        "raw_response_exposed",
        "broker_api_response_exposed",
        "credential_value_exposed",
        "signature_value_exposed",
        "headers_value_exposed",
        "real_id_exposed",
        "account_id_exposed",
        "order_id_exposed",
        "transaction_id_exposed",
        "position_id_exposed",
        "client_order_id_actual_value_exposed",
    ):
        if getattr(summary, name):
            reasons.append(f"{name}=true")
    return reasons


def _source_artifact_label(derivation_source: str) -> str:
    if derivation_source == SIDE_SOURCE_FRESH_ENTRY:
        return FRESH_ENTRY_SAFE_SIDE_ARTIFACT_SOURCE_LABEL
    if derivation_source == SIDE_SOURCE_POSITION_SIDE:
        return APPROVED_SAFE_POSITION_SIDE_ARTIFACT_SOURCE_LABEL
    if derivation_source == SIDE_SOURCE_MULTIPLE_SAFE_INPUTS:
        return MULTIPLE_APPROVED_SAFE_ARTIFACTS_SOURCE_LABEL
    return SIDE_PROVENANCE_NOT_CONFIRMED_LABEL


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty string")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(instance: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if not isinstance(getattr(instance, field_name), bool):
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_blocked_reasons(reasons: tuple[str, ...]) -> None:
    if not isinstance(reasons, tuple):
        raise LiveVerificationValidationError("blocked_reasons must be tuple")
    for reason in reasons:
        _require_non_empty("blocked_reason", reason)


def _bool_text(value: bool) -> str:
    return str(value).lower()


_ARTIFACT_BOOL_FIELDS = (
    "derived_from_fresh_entry_safe_artifact",
    "derived_from_approved_safe_position_artifact",
    "side_mismatch_detected",
    "codex_inferred_side",
)

_INPUT_BOOL_FIELDS = (
    "fresh_entry_safe_side_artifact_found",
    "approved_safe_position_side_artifact_found",
    "approved_safe_position_side_artifact_required",
    "settlement_side_source_is_default_value",
    "settlement_side_source_is_operator_input",
    "settlement_side_source_is_raw_broker_value",
    "settlement_side_source_is_position_specific_identifier",
    "settlement_side_source_is_generic_opposite_order",
    "settlement_side_safe_artifact_propagated_to_official_settlement_preview",
    "settlement_side_safe_artifact_propagated_to_actual_transport_plan",
    "settlement_side_safe_artifact_propagated_to_execution_gate",
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
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_executed",
    "generic_close_post_executed",
    "ledger_update",
    "receipt_handoff",
    "raw_id_value_credential_header_exposure",
    "actual_settlement_post_executed",
    "real_http_post_executed",
    "broker_write_executed",
)

_RESULT_BOOL_FIELDS = (
    "settlement_side_provenance_gate_confirmed",
    "settlement_side_source_safe_artifact_available",
    "settlement_side_source_is_default_value",
    "settlement_side_source_is_operator_input",
    "settlement_side_source_is_raw_broker_value",
    "settlement_side_source_is_position_specific_identifier",
    "settlement_side_source_is_generic_opposite_order",
    "fresh_entry_safe_side_artifact_found",
    "approved_safe_position_side_artifact_found",
    "settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact",
    "settlement_side_matches_official_settlement_side_semantics",
    "settlement_side_safe_artifact_propagated_to_official_settlement_preview",
    "settlement_side_safe_artifact_propagated_to_actual_transport_plan",
    "settlement_side_safe_artifact_propagated_to_execution_gate",
    "settlement_side_provenance_mechanically_confirmed",
    "actual_transport_side_currently_default",
    "actual_transport_side_currently_operator_input",
    "actual_transport_side_currently_raw_broker_value",
    "actual_transport_side_currently_generic_opposite_order",
    "execution_gate_can_verify_settlement_side_provenance_before_post",
    "execution_gate_can_call_actual_transport_after_confirmation",
    "next_execution_gate_has_no_known_side_provenance_blocker",
    "official_settlement_actual_transport_confirmed",
    "official_settlement_real_network_client_binding_confirmed",
    "official_settlement_no_post_preview_ready",
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
    "this_step_actual_settlement_post_executed",
    "real_http_post_executed",
    "broker_write_executed",
    "retry_allowed",
    "repost_allowed",
    "second_settlement_allowed",
    "entry_post_executed",
    "generic_close_post_executed",
    "ledger_update",
    "receipt_handoff",
    "raw_id_value_credential_header_exposure",
    "next_execution_gate_still_requires_fresh_runtime_read",
    "next_execution_gate_still_requires_operator_readiness",
    "next_execution_gate_still_requires_settlement_specific_confirmation",
)
