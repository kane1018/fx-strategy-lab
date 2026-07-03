"""Step 6G GMO official settlement route review.

This module records official-document settlement-route evidence as a no-POST
review result. It does not import or call broker, Private API, HTTP, env,
ledger, receipt, or live_order_once code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError

EXECUTION_STEP_GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW = (
    "GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW_NO_POST_C"
)
GMO_OFFICIAL_MANUAL_URL = (
    "https://coin.z.com/corp_imgs/manual/kawasefx-trading-manual.pdf"
)
GMO_OFFICIAL_TRADING_RULES_URL = "https://coin.z.com/jp/corp/product/info/fx/#rule"
GMO_OFFICIAL_API_DOCS_URL = "https://api.coin.z.com/fxdocs/"
OFFICIAL_SETTLEMENT_ROUTE_SAFE_LABEL = (
    "GMO_FX_DEDICATED_CLOSE_ORDER_ROUTE_OFFICIAL_DOC_LABEL"
)
OFFICIAL_SETTLEMENT_PARAMETERS_SAFE_LABEL = (
    "SYMBOL_SIDE_EXECUTION_TYPE_AND_SIZE_OR_POSITION_SPECIFIC_SELECTION"
)
OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED = "OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED"
OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST = (
    "OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST"
)
OFFICIAL_SETTLEMENT_ROUTE_ID_HANDLING_UNSAFE = (
    "OFFICIAL_SETTLEMENT_ROUTE_REQUIRES_UNSAFE_IDENTIFIER_HANDLING"
)
NEXT_STEP_OFFICIAL_SETTLEMENT_ROUTE_IMPLEMENTATION = (
    "Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-ROUTE-NO-POST-IMPLEMENTATION-C"
)
NEXT_STEP_GMO_FX_API_SETTLEMENT_DOCS_RETRIEVAL = (
    "Step 6G-PC-OX-R-GMO-FX-API-SETTLEMENT-DOCS-RETRIEVAL-C"
)
NEXT_STEP_UNSAFE_IDENTIFIER_DESIGN = (
    "Step 6G-PC-OX-R-SETTLEMENT-IDENTIFIER-SAFE-HANDLING-DESIGN-C"
)
CURRENT_POSITION_STATE_MANUAL_FLAT_RECONCILED = "NO_POSITION_AFTER_MANUAL_FLATTEN"
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_REVIEWED_NO_POST = (
    "OFFICIAL_SETTLEMENT_ROUTE_REVIEWED_NO_POST"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_MISSING = (
    "OFFICIAL_SETTLEMENT_ROUTE_MISSING_SAFE_STOP"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_IDENTIFIER_BLOCKED = (
    "OFFICIAL_SETTLEMENT_ROUTE_IDENTIFIER_HANDLING_BLOCKED"
)
NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_INCONCLUSIVE = (
    "OFFICIAL_SETTLEMENT_ROUTE_REVIEW_INCONCLUSIVE"
)


class GmoOfficialSettlementRouteReviewCase(str, Enum):
    CASE_1 = "OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST"
    CASE_2 = "OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED"
    CASE_3 = "ROUTE_REQUIRES_RAW_ID_VALUE_UNSAFE_HANDLING"
    CASE_4 = "INCONCLUSIVE"


class GmoOfficialSettlementRouteReviewStatus(str, Enum):
    CONFIRMED_NO_POST = "OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST"
    NOT_CONFIRMED = "OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED"
    UNSAFE_IDENTIFIER_HANDLING_BLOCKED = (
        "OFFICIAL_SETTLEMENT_ROUTE_UNSAFE_IDENTIFIER_HANDLING_BLOCKED"
    )
    UNSAFE_EXPOSURE_BLOCKED = "UNSAFE_EXPOSURE_BLOCKED"
    INCONCLUSIVE_FAIL_CLOSED = "INCONCLUSIVE_FAIL_CLOSED"


@dataclass(frozen=True)
class GmoOfficialSettlementRouteReviewInput:
    official_manual_url_recorded: bool = True
    official_trading_rules_url_recorded: bool = True
    official_api_docs_url_recorded: bool = True
    official_manual_accessed: bool = False
    official_rules_accessed: bool = False
    official_api_docs_accessed: bool = False
    manual_settlement_flow_found: bool = False
    manual_position_summary_settlement_button_found: bool = False
    manual_position_list_settlement_button_found: bool = False
    manual_buy_sell_not_netted_confirmed: bool = False
    manual_generic_opposite_order_as_settlement_supported: bool = False
    rules_api_new_order_min_confirmed: bool = False
    rules_settlement_quantity_no_lower_limit_confirmed: bool = False
    rules_hedging_possible_confirmed: bool = False
    rules_trading_time_recorded: bool = False
    rules_order_reception_time_recorded: bool = False
    repo_official_api_docs_found: bool = False
    repo_settlement_endpoint_found: bool = False
    repo_settlement_parameter_found: bool = False
    repo_settlement_requires_position_identifier: bool | None = None
    official_settlement_size_without_position_identifier_confirmed: bool = False
    repo_settlement_safe_identifier_handling_ready: bool = False
    repo_generic_order_endpoint_only: bool = True
    repo_generic_order_is_not_settlement: bool = True
    generic_opposite_order_as_close_forbidden: bool = True
    generic_close_primitive_revoked: bool = True
    manual_flatten_reconciled: bool = True
    current_position_state: str = CURRENT_POSITION_STATE_MANUAL_FLAT_RECONCILED
    actual_entry_post_attempted_this_step: bool = False
    actual_close_post_attempted_this_step: bool = False
    retry_attempted_this_step: bool = False
    repost_attempted_this_step: bool = False
    second_close_post_attempted_this_step: bool = False
    ledger_update_attempted_this_step: bool = False
    receipt_handoff_attempted_this_step: bool = False
    raw_request_exposure_attempted_this_step: bool = False
    raw_response_exposure_attempted_this_step: bool = False
    broker_api_response_exposure_attempted_this_step: bool = False
    account_id_exposure_attempted_this_step: bool = False
    order_id_exposure_attempted_this_step: bool = False
    transaction_id_exposure_attempted_this_step: bool = False
    position_id_exposure_attempted_this_step: bool = False
    trade_id_exposure_attempted_this_step: bool = False
    credential_value_exposure_attempted_this_step: bool = False
    signature_value_exposure_attempted_this_step: bool = False
    headers_value_exposure_attempted_this_step: bool = False
    actual_market_price_exposure_attempted_this_step: bool = False
    actual_pnl_exposure_attempted_this_step: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("current_position_state", self.current_position_state)
        if (
            self.repo_settlement_requires_position_identifier is not None
            and type(self.repo_settlement_requires_position_identifier) is not bool
        ):
            raise LiveVerificationValidationError(
                "repo_settlement_requires_position_identifier must be bool or None",
            )
        _validate_bool_fields(self, _INPUT_BOOL_FIELDS)


@dataclass(frozen=True)
class GmoOfficialSettlementRouteReviewResult:
    case: GmoOfficialSettlementRouteReviewCase
    review_status: GmoOfficialSettlementRouteReviewStatus
    gmo_official_settlement_route_review_ready: bool
    execution_step: str
    official_manual_url_recorded: bool
    official_trading_rules_url_recorded: bool
    official_api_docs_url_recorded: bool
    official_manual_accessed: bool
    official_rules_accessed: bool
    official_api_docs_accessed: bool
    manual_settlement_flow_found: bool
    manual_position_summary_settlement_button_found: bool
    manual_position_list_settlement_button_found: bool
    manual_buy_sell_not_netted_confirmed: bool
    manual_generic_opposite_order_as_settlement_supported: bool
    official_manual_supports_generic_opposite_order_as_settlement: bool
    manual_review_raw_text_exposed: bool
    rules_api_new_order_min_confirmed: bool
    rules_settlement_quantity_no_lower_limit_confirmed: bool
    rules_hedging_possible_confirmed: bool
    rules_trading_time_recorded: bool
    rules_order_reception_time_recorded: bool
    rules_review_raw_text_exposed: bool
    repo_official_api_docs_found: bool
    repo_settlement_endpoint_found: bool
    repo_settlement_endpoint_safe_label: str
    repo_settlement_parameter_found: bool
    repo_settlement_parameter_safe_label: str
    repo_settlement_requires_position_identifier: bool | None
    official_settlement_size_without_position_identifier_confirmed: bool
    repo_settlement_safe_identifier_handling_ready: bool
    repo_generic_order_endpoint_only: bool
    repo_generic_order_is_not_settlement: bool
    generic_opposite_order_as_close_forbidden: bool
    generic_close_primitive_revoked: bool
    official_settlement_route_confirmed: bool
    official_settlement_route_confirmation_basis: str
    official_settlement_route_missing_reason: str
    actual_close_post_allowed_now: bool
    future_actual_close_post_requires_dedicated_settlement_gate: bool
    future_actual_close_post_requires_no_raw_id_value_exposure: bool
    current_position_state: str
    manual_flatten_reconciled: bool
    level5_minimal_cycle_completed: bool
    level5_full_auto_cycle_completed: bool
    fresh_cycle_allowed: bool
    close_execution_allowed_until_official_route: bool
    next_cycle_state: str
    recommended_next_step: str
    actual_entry_post: bool
    actual_close_post: bool
    retry_repost: bool
    second_close_post: bool
    ledger_update: bool
    receipt_handoff: bool
    raw_request_exposed: bool
    raw_response_exposed: bool
    broker_api_response_exposed: bool
    account_id_exposed: bool
    order_id_exposed: bool
    transaction_id_exposed: bool
    position_id_exposed: bool
    trade_id_exposed: bool
    credential_value_exposed: bool
    signature_value_exposed: bool
    headers_value_exposed: bool
    actual_market_price_exposed: bool
    actual_pnl_exposed: bool
    blocked_reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.case, GmoOfficialSettlementRouteReviewCase):
            raise LiveVerificationValidationError("case must be controlled enum")
        if not isinstance(self.review_status, GmoOfficialSettlementRouteReviewStatus):
            raise LiveVerificationValidationError(
                "review_status must be controlled enum",
            )
        if (
            self.repo_settlement_requires_position_identifier is not None
            and type(self.repo_settlement_requires_position_identifier) is not bool
        ):
            raise LiveVerificationValidationError(
                "repo_settlement_requires_position_identifier must be bool or None",
            )
        for field_name in (
            "execution_step",
            "repo_settlement_endpoint_safe_label",
            "repo_settlement_parameter_safe_label",
            "official_settlement_route_confirmation_basis",
            "official_settlement_route_missing_reason",
            "current_position_state",
            "next_cycle_state",
            "recommended_next_step",
        ):
            _require_non_empty(field_name, getattr(self, field_name))
        _validate_bool_fields(self, _RESULT_BOOL_FIELDS)
        _validate_blocked_reasons(self.blocked_reasons)


def build_gmo_official_settlement_route_review_controlled(
    review_input: GmoOfficialSettlementRouteReviewInput | None = None,
) -> GmoOfficialSettlementRouteReviewResult:
    snapshot = review_input or GmoOfficialSettlementRouteReviewInput()
    current_step_blockers = _current_step_blocked_reasons(snapshot)
    route_evidence_ready = _route_evidence_ready(snapshot)
    manual_rules_ready = _manual_and_rules_ready(snapshot)
    identifier_blocked = (
        snapshot.repo_settlement_requires_position_identifier is True
        and not snapshot.repo_settlement_safe_identifier_handling_ready
        and not snapshot.official_settlement_size_without_position_identifier_confirmed
    )

    if current_step_blockers:
        case = GmoOfficialSettlementRouteReviewCase.CASE_4
        status = GmoOfficialSettlementRouteReviewStatus.UNSAFE_EXPOSURE_BLOCKED
        route_confirmed = False
        basis = "UNSAFE_CURRENT_STEP_ATTEMPT_BLOCKED"
        missing_reason = "CURRENT_STEP_EXECUTION_OR_EXPOSURE_ATTEMPTED"
        next_state = NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_INCONCLUSIVE
        recommended_next_step = "stop_current_step_no_post"
        blocked_reasons = current_step_blockers
    elif identifier_blocked:
        case = GmoOfficialSettlementRouteReviewCase.CASE_3
        status = (
            GmoOfficialSettlementRouteReviewStatus
            .UNSAFE_IDENTIFIER_HANDLING_BLOCKED
        )
        route_confirmed = False
        basis = OFFICIAL_SETTLEMENT_ROUTE_ID_HANDLING_UNSAFE
        missing_reason = "SETTLEMENT_IDENTIFIER_SAFE_HANDLING_NOT_READY"
        next_state = NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_IDENTIFIER_BLOCKED
        recommended_next_step = NEXT_STEP_UNSAFE_IDENTIFIER_DESIGN
        blocked_reasons = ("settlement_identifier_safe_handling_not_ready",)
    elif route_evidence_ready:
        case = GmoOfficialSettlementRouteReviewCase.CASE_1
        status = GmoOfficialSettlementRouteReviewStatus.CONFIRMED_NO_POST
        route_confirmed = True
        basis = OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST
        missing_reason = "NONE"
        next_state = NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_REVIEWED_NO_POST
        recommended_next_step = NEXT_STEP_OFFICIAL_SETTLEMENT_ROUTE_IMPLEMENTATION
        blocked_reasons = ()
    elif manual_rules_ready:
        case = GmoOfficialSettlementRouteReviewCase.CASE_2
        status = GmoOfficialSettlementRouteReviewStatus.NOT_CONFIRMED
        route_confirmed = False
        basis = OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
        missing_reason = "OFFICIAL_API_SETTLEMENT_ROUTE_OR_PARAMETERS_NOT_CONFIRMED"
        next_state = NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_MISSING
        recommended_next_step = NEXT_STEP_GMO_FX_API_SETTLEMENT_DOCS_RETRIEVAL
        blocked_reasons = ("official_api_settlement_route_not_confirmed",)
    else:
        case = GmoOfficialSettlementRouteReviewCase.CASE_4
        status = GmoOfficialSettlementRouteReviewStatus.INCONCLUSIVE_FAIL_CLOSED
        route_confirmed = False
        basis = "INCONCLUSIVE_FAIL_CLOSED"
        missing_reason = "OFFICIAL_MANUAL_RULES_OR_API_DOCS_REVIEW_INCOMPLETE"
        next_state = NEXT_CYCLE_STATE_OFFICIAL_SETTLEMENT_ROUTE_INCONCLUSIVE
        recommended_next_step = NEXT_STEP_GMO_FX_API_SETTLEMENT_DOCS_RETRIEVAL
        blocked_reasons = ("official_review_incomplete",)

    return GmoOfficialSettlementRouteReviewResult(
        case=case,
        review_status=status,
        gmo_official_settlement_route_review_ready=case
        is not GmoOfficialSettlementRouteReviewCase.CASE_4,
        execution_step=EXECUTION_STEP_GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW,
        official_manual_url_recorded=snapshot.official_manual_url_recorded,
        official_trading_rules_url_recorded=(
            snapshot.official_trading_rules_url_recorded
        ),
        official_api_docs_url_recorded=snapshot.official_api_docs_url_recorded,
        official_manual_accessed=snapshot.official_manual_accessed,
        official_rules_accessed=snapshot.official_rules_accessed,
        official_api_docs_accessed=snapshot.official_api_docs_accessed,
        manual_settlement_flow_found=snapshot.manual_settlement_flow_found,
        manual_position_summary_settlement_button_found=(
            snapshot.manual_position_summary_settlement_button_found
        ),
        manual_position_list_settlement_button_found=(
            snapshot.manual_position_list_settlement_button_found
        ),
        manual_buy_sell_not_netted_confirmed=(
            snapshot.manual_buy_sell_not_netted_confirmed
        ),
        manual_generic_opposite_order_as_settlement_supported=(
            snapshot.manual_generic_opposite_order_as_settlement_supported
        ),
        official_manual_supports_generic_opposite_order_as_settlement=False,
        manual_review_raw_text_exposed=False,
        rules_api_new_order_min_confirmed=(
            snapshot.rules_api_new_order_min_confirmed
        ),
        rules_settlement_quantity_no_lower_limit_confirmed=(
            snapshot.rules_settlement_quantity_no_lower_limit_confirmed
        ),
        rules_hedging_possible_confirmed=snapshot.rules_hedging_possible_confirmed,
        rules_trading_time_recorded=snapshot.rules_trading_time_recorded,
        rules_order_reception_time_recorded=(
            snapshot.rules_order_reception_time_recorded
        ),
        rules_review_raw_text_exposed=False,
        repo_official_api_docs_found=snapshot.repo_official_api_docs_found,
        repo_settlement_endpoint_found=snapshot.repo_settlement_endpoint_found,
        repo_settlement_endpoint_safe_label=OFFICIAL_SETTLEMENT_ROUTE_SAFE_LABEL,
        repo_settlement_parameter_found=snapshot.repo_settlement_parameter_found,
        repo_settlement_parameter_safe_label=(
            OFFICIAL_SETTLEMENT_PARAMETERS_SAFE_LABEL
        ),
        repo_settlement_requires_position_identifier=(
            snapshot.repo_settlement_requires_position_identifier
        ),
        official_settlement_size_without_position_identifier_confirmed=(
            snapshot.official_settlement_size_without_position_identifier_confirmed
        ),
        repo_settlement_safe_identifier_handling_ready=(
            snapshot.repo_settlement_safe_identifier_handling_ready
        ),
        repo_generic_order_endpoint_only=snapshot.repo_generic_order_endpoint_only,
        repo_generic_order_is_not_settlement=(
            snapshot.repo_generic_order_is_not_settlement
        ),
        generic_opposite_order_as_close_forbidden=(
            snapshot.generic_opposite_order_as_close_forbidden
        ),
        generic_close_primitive_revoked=snapshot.generic_close_primitive_revoked,
        official_settlement_route_confirmed=route_confirmed,
        official_settlement_route_confirmation_basis=basis,
        official_settlement_route_missing_reason=missing_reason,
        actual_close_post_allowed_now=False,
        future_actual_close_post_requires_dedicated_settlement_gate=True,
        future_actual_close_post_requires_no_raw_id_value_exposure=True,
        current_position_state=snapshot.current_position_state,
        manual_flatten_reconciled=snapshot.manual_flatten_reconciled,
        level5_minimal_cycle_completed=False,
        level5_full_auto_cycle_completed=False,
        fresh_cycle_allowed=False,
        close_execution_allowed_until_official_route=False,
        next_cycle_state=next_state,
        recommended_next_step=recommended_next_step,
        actual_entry_post=False,
        actual_close_post=False,
        retry_repost=False,
        second_close_post=False,
        ledger_update=False,
        receipt_handoff=False,
        raw_request_exposed=False,
        raw_response_exposed=False,
        broker_api_response_exposed=False,
        account_id_exposed=False,
        order_id_exposed=False,
        transaction_id_exposed=False,
        position_id_exposed=False,
        trade_id_exposed=False,
        credential_value_exposed=False,
        signature_value_exposed=False,
        headers_value_exposed=False,
        actual_market_price_exposed=False,
        actual_pnl_exposed=False,
        blocked_reasons=blocked_reasons,
    )


def render_gmo_official_settlement_route_review_markdown(
    result: GmoOfficialSettlementRouteReviewResult,
) -> str:
    if not isinstance(result, GmoOfficialSettlementRouteReviewResult):
        raise LiveVerificationValidationError(
            "result must be GmoOfficialSettlementRouteReviewResult",
        )
    lines = [
        "# GMO Official Settlement Route Review",
        "",
        f"case: {result.case.value}",
        f"review_status: {result.review_status.value}",
        f"official_manual_accessed: {_bool_text(result.official_manual_accessed)}",
        f"official_rules_accessed: {_bool_text(result.official_rules_accessed)}",
        f"official_api_docs_accessed: {_bool_text(result.official_api_docs_accessed)}",
        (
            "manual_settlement_flow_found: "
            f"{_bool_text(result.manual_settlement_flow_found)}"
        ),
        (
            "manual_buy_sell_not_netted_confirmed: "
            f"{_bool_text(result.manual_buy_sell_not_netted_confirmed)}"
        ),
        (
            "manual_generic_opposite_order_as_settlement_supported: "
            f"{_bool_text(result.manual_generic_opposite_order_as_settlement_supported)}"
        ),
        (
            "rules_api_new_order_min_confirmed: "
            f"{_bool_text(result.rules_api_new_order_min_confirmed)}"
        ),
        (
            "rules_settlement_quantity_no_lower_limit_confirmed: "
            f"{_bool_text(result.rules_settlement_quantity_no_lower_limit_confirmed)}"
        ),
        (
            "rules_hedging_possible_confirmed: "
            f"{_bool_text(result.rules_hedging_possible_confirmed)}"
        ),
        (
            "repo_settlement_endpoint_found: "
            f"{_bool_text(result.repo_settlement_endpoint_found)}"
        ),
        (
            "repo_settlement_parameter_found: "
            f"{_bool_text(result.repo_settlement_parameter_found)}"
        ),
        (
            "repo_settlement_requires_position_identifier: "
            f"{_tri_state_text(result.repo_settlement_requires_position_identifier)}"
        ),
        (
            "repo_settlement_safe_identifier_handling_ready: "
            f"{_bool_text(result.repo_settlement_safe_identifier_handling_ready)}"
        ),
        (
            "generic_opposite_order_as_close_forbidden: "
            f"{_bool_text(result.generic_opposite_order_as_close_forbidden)}"
        ),
        f"generic_close_primitive_revoked: {_bool_text(result.generic_close_primitive_revoked)}",
        (
            "official_settlement_route_confirmed: "
            f"{_bool_text(result.official_settlement_route_confirmed)}"
        ),
        (
            "actual_close_post_allowed_now: "
            f"{_bool_text(result.actual_close_post_allowed_now)}"
        ),
        (
            "future_actual_close_post_requires_dedicated_settlement_gate: "
            f"{_bool_text(result.future_actual_close_post_requires_dedicated_settlement_gate)}"
        ),
        f"manual_flatten_reconciled: {_bool_text(result.manual_flatten_reconciled)}",
        (
            "level5_full_auto_cycle_completed: "
            f"{_bool_text(result.level5_full_auto_cycle_completed)}"
        ),
        f"fresh_cycle_allowed: {_bool_text(result.fresh_cycle_allowed)}",
        f"next_cycle_state: {result.next_cycle_state}",
        f"recommended_next_step: {result.recommended_next_step}",
        f"raw_request_exposed: {_bool_text(result.raw_request_exposed)}",
        f"raw_response_exposed: {_bool_text(result.raw_response_exposed)}",
        (
            "broker_api_response_exposed: "
            f"{_bool_text(result.broker_api_response_exposed)}"
        ),
        f"position_id_exposed: {_bool_text(result.position_id_exposed)}",
        f"credential_value_exposed: {_bool_text(result.credential_value_exposed)}",
        f"signature_value_exposed: {_bool_text(result.signature_value_exposed)}",
        f"headers_value_exposed: {_bool_text(result.headers_value_exposed)}",
        f"blocked_reasons: {', '.join(result.blocked_reasons) or 'none'}",
    ]
    return "\n".join(lines)


def _manual_and_rules_ready(snapshot: GmoOfficialSettlementRouteReviewInput) -> bool:
    return all(
        (
            snapshot.official_manual_url_recorded,
            snapshot.official_trading_rules_url_recorded,
            snapshot.official_manual_accessed,
            snapshot.official_rules_accessed,
            snapshot.manual_settlement_flow_found,
            snapshot.manual_position_summary_settlement_button_found,
            snapshot.manual_position_list_settlement_button_found,
            snapshot.manual_buy_sell_not_netted_confirmed,
            not snapshot.manual_generic_opposite_order_as_settlement_supported,
            snapshot.rules_api_new_order_min_confirmed,
            snapshot.rules_settlement_quantity_no_lower_limit_confirmed,
            snapshot.rules_hedging_possible_confirmed,
            snapshot.rules_trading_time_recorded,
            snapshot.rules_order_reception_time_recorded,
            snapshot.generic_opposite_order_as_close_forbidden,
            snapshot.generic_close_primitive_revoked,
            snapshot.repo_generic_order_is_not_settlement,
        )
    )


def _route_evidence_ready(snapshot: GmoOfficialSettlementRouteReviewInput) -> bool:
    return all(
        (
            _manual_and_rules_ready(snapshot),
            snapshot.official_api_docs_url_recorded,
            snapshot.official_api_docs_accessed,
            snapshot.repo_official_api_docs_found,
            snapshot.repo_settlement_endpoint_found,
            snapshot.repo_settlement_parameter_found,
            not snapshot.repo_generic_order_endpoint_only,
            (
                snapshot.official_settlement_size_without_position_identifier_confirmed
                or snapshot.repo_settlement_safe_identifier_handling_ready
            ),
        )
    )


def _current_step_blocked_reasons(
    snapshot: GmoOfficialSettlementRouteReviewInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name, reason in (
        ("actual_entry_post_attempted_this_step", "actual_entry_post_attempted"),
        ("actual_close_post_attempted_this_step", "actual_close_post_attempted"),
        ("retry_attempted_this_step", "retry_attempted"),
        ("repost_attempted_this_step", "repost_attempted"),
        ("second_close_post_attempted_this_step", "second_close_post_attempted"),
        ("ledger_update_attempted_this_step", "ledger_update_attempted"),
        ("receipt_handoff_attempted_this_step", "receipt_handoff_attempted"),
    ):
        if getattr(snapshot, field_name):
            reasons.append(reason)

    if any(
        (
            snapshot.raw_request_exposure_attempted_this_step,
            snapshot.raw_response_exposure_attempted_this_step,
            snapshot.broker_api_response_exposure_attempted_this_step,
            snapshot.account_id_exposure_attempted_this_step,
            snapshot.order_id_exposure_attempted_this_step,
            snapshot.transaction_id_exposure_attempted_this_step,
            snapshot.position_id_exposure_attempted_this_step,
            snapshot.trade_id_exposure_attempted_this_step,
            snapshot.credential_value_exposure_attempted_this_step,
            snapshot.signature_value_exposure_attempted_this_step,
            snapshot.headers_value_exposure_attempted_this_step,
            snapshot.actual_market_price_exposure_attempted_this_step,
            snapshot.actual_pnl_exposure_attempted_this_step,
        )
    ):
        reasons.append("raw_id_value_exposure_attempted")

    if not snapshot.generic_opposite_order_as_close_forbidden:
        reasons.append("generic_opposite_order_as_close_not_forbidden")
    if not snapshot.generic_close_primitive_revoked:
        reasons.append("generic_close_primitive_not_revoked")
    if snapshot.manual_generic_opposite_order_as_settlement_supported:
        reasons.append("manual_generic_opposite_order_as_settlement_claimed")
    return tuple(reasons)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _tri_state_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return _bool_text(value)


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_blocked_reasons(blocked_reasons: tuple[str, ...]) -> None:
    if not isinstance(blocked_reasons, tuple) or not all(
        isinstance(reason, str) and reason for reason in blocked_reasons
    ):
        raise LiveVerificationValidationError("blocked_reasons must be tuple[str, ...]")


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationValidationError(f"{field_name} is required")


_INPUT_BOOL_FIELDS = (
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "official_api_docs_url_recorded",
    "official_manual_accessed",
    "official_rules_accessed",
    "official_api_docs_accessed",
    "manual_settlement_flow_found",
    "manual_position_summary_settlement_button_found",
    "manual_position_list_settlement_button_found",
    "manual_buy_sell_not_netted_confirmed",
    "manual_generic_opposite_order_as_settlement_supported",
    "rules_api_new_order_min_confirmed",
    "rules_settlement_quantity_no_lower_limit_confirmed",
    "rules_hedging_possible_confirmed",
    "rules_trading_time_recorded",
    "rules_order_reception_time_recorded",
    "repo_official_api_docs_found",
    "repo_settlement_endpoint_found",
    "repo_settlement_parameter_found",
    "official_settlement_size_without_position_identifier_confirmed",
    "repo_settlement_safe_identifier_handling_ready",
    "repo_generic_order_endpoint_only",
    "repo_generic_order_is_not_settlement",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "manual_flatten_reconciled",
    "actual_entry_post_attempted_this_step",
    "actual_close_post_attempted_this_step",
    "retry_attempted_this_step",
    "repost_attempted_this_step",
    "second_close_post_attempted_this_step",
    "ledger_update_attempted_this_step",
    "receipt_handoff_attempted_this_step",
    "raw_request_exposure_attempted_this_step",
    "raw_response_exposure_attempted_this_step",
    "broker_api_response_exposure_attempted_this_step",
    "account_id_exposure_attempted_this_step",
    "order_id_exposure_attempted_this_step",
    "transaction_id_exposure_attempted_this_step",
    "position_id_exposure_attempted_this_step",
    "trade_id_exposure_attempted_this_step",
    "credential_value_exposure_attempted_this_step",
    "signature_value_exposure_attempted_this_step",
    "headers_value_exposure_attempted_this_step",
    "actual_market_price_exposure_attempted_this_step",
    "actual_pnl_exposure_attempted_this_step",
)

_RESULT_BOOL_FIELDS = (
    "gmo_official_settlement_route_review_ready",
    "official_manual_url_recorded",
    "official_trading_rules_url_recorded",
    "official_api_docs_url_recorded",
    "official_manual_accessed",
    "official_rules_accessed",
    "official_api_docs_accessed",
    "manual_settlement_flow_found",
    "manual_position_summary_settlement_button_found",
    "manual_position_list_settlement_button_found",
    "manual_buy_sell_not_netted_confirmed",
    "manual_generic_opposite_order_as_settlement_supported",
    "official_manual_supports_generic_opposite_order_as_settlement",
    "manual_review_raw_text_exposed",
    "rules_api_new_order_min_confirmed",
    "rules_settlement_quantity_no_lower_limit_confirmed",
    "rules_hedging_possible_confirmed",
    "rules_trading_time_recorded",
    "rules_order_reception_time_recorded",
    "rules_review_raw_text_exposed",
    "repo_official_api_docs_found",
    "repo_settlement_endpoint_found",
    "repo_settlement_parameter_found",
    "official_settlement_size_without_position_identifier_confirmed",
    "repo_settlement_safe_identifier_handling_ready",
    "repo_generic_order_endpoint_only",
    "repo_generic_order_is_not_settlement",
    "generic_opposite_order_as_close_forbidden",
    "generic_close_primitive_revoked",
    "official_settlement_route_confirmed",
    "actual_close_post_allowed_now",
    "future_actual_close_post_requires_dedicated_settlement_gate",
    "future_actual_close_post_requires_no_raw_id_value_exposure",
    "manual_flatten_reconciled",
    "level5_minimal_cycle_completed",
    "level5_full_auto_cycle_completed",
    "fresh_cycle_allowed",
    "close_execution_allowed_until_official_route",
    "actual_entry_post",
    "actual_close_post",
    "retry_repost",
    "second_close_post",
    "ledger_update",
    "receipt_handoff",
    "raw_request_exposed",
    "raw_response_exposed",
    "broker_api_response_exposed",
    "account_id_exposed",
    "order_id_exposed",
    "transaction_id_exposed",
    "position_id_exposed",
    "trade_id_exposed",
    "credential_value_exposed",
    "signature_value_exposed",
    "headers_value_exposed",
    "actual_market_price_exposed",
    "actual_pnl_exposed",
)

