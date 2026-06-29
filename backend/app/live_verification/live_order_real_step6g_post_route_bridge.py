"""Step 6G POST route bridge pure model.

This module connects sanitized Step 6G evidence into a future route contract.
It is a pure model only: it does not call APIs, import broker or Private API
clients, import live_order_once, build an order payload, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

LIVE_ORDER_REAL_STEP6G_POST_ROUTE_BRIDGE_ID_PREFIX = "LOR6GPB-"
STEP6G_BRIDGE_READY_RECOMMENDED_NEXT_STEP = (
    "implement_or_run_separate_step6g_execution_with_fresh_preflight_and_new_final_confirmation"
)
STEP6G_MARKET_OPEN_STATE = "OPEN"
STEP6G_MAX_SPREAD_JPY = 0.01
STEP6G_MAX_TICKER_AGE_SECONDS = 30
STEP6G_MIN_TICKER_AGE_SECONDS = -5


class LiveOrderRealStep6GPostRouteBridgeStatus(str, Enum):
    STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST = "STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST"
    BLOCKED_STEP6G_BRIDGE_ORDER_INTENT = "BLOCKED_STEP6G_BRIDGE_ORDER_INTENT"
    BLOCKED_STEP6G_BRIDGE_APPROVAL = "BLOCKED_STEP6G_BRIDGE_APPROVAL"
    BLOCKED_STEP6G_BRIDGE_PREFLIGHT = "BLOCKED_STEP6G_BRIDGE_PREFLIGHT"
    BLOCKED_STEP6G_BRIDGE_ATTEMPT_STATE = "BLOCKED_STEP6G_BRIDGE_ATTEMPT_STATE"
    BLOCKED_STEP6G_BRIDGE_ROUTE_UNSAFE = "BLOCKED_STEP6G_BRIDGE_ROUTE_UNSAFE"
    BLOCKED_STEP6G_BRIDGE_STEP4_SPOOFING = "BLOCKED_STEP6G_BRIDGE_STEP4_SPOOFING"
    BLOCKED_STEP6G_BRIDGE_RAW_OR_SECRET_EXPOSURE = "BLOCKED_STEP6G_BRIDGE_RAW_OR_SECRET_EXPOSURE"
    BLOCKED_STEP6G_BRIDGE_UNSUPPORTED = "BLOCKED_STEP6G_BRIDGE_UNSUPPORTED"


BridgeStatus = LiveOrderRealStep6GPostRouteBridgeStatus


@dataclass(frozen=True)
class LiveOrderRealStep6GPostRouteBridgeCheckResult:
    name: str
    passed: bool
    reason: str
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("passed must be bool")
        _require_non_empty("reason", self.reason)
        _require_non_empty("sanitized_value", self.sanitized_value)
        _require_non_empty("expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealStep6GOrderIntentSnapshot:
    symbol: str
    side: str
    size: int
    executionType: str
    source_label: str
    codex_inferred_side: bool
    codex_inferred_symbol: bool
    codex_inferred_size: bool
    codex_inferred_execution_type: bool

    def __post_init__(self) -> None:
        _require_non_empty("symbol", self.symbol)
        _require_non_empty("side", self.side)
        _validate_non_negative_int("size", self.size)
        _require_non_empty("executionType", self.executionType)
        _require_non_empty("source_label", self.source_label)
        _validate_bool_fields(
            self,
            (
                "codex_inferred_side",
                "codex_inferred_symbol",
                "codex_inferred_size",
                "codex_inferred_execution_type",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GApprovalSnapshot:
    step6g_final_confirmation_received: bool
    step6g_final_confirmation_exact_match: bool
    final_confirmation_phrase_reused: bool
    approval_artifact_reestablished: bool
    approval_validation_passed: bool
    approval_exact_match_ready: bool
    approval_command_fingerprint: str
    approval_sha256_prefix: str
    approval_command_displayed: bool
    approval_command_saved: bool
    approval_command_copyable: bool
    approval_command_pbcopy: bool
    step4_approval_phrase_used: bool
    step4_approval_phrase_spoofed: bool
    step4_approval_gate_reused_as_step6g: bool
    approval_command_full_text_present: bool

    def __post_init__(self) -> None:
        _validate_bool_fields(
            self,
            (
                "step6g_final_confirmation_received",
                "step6g_final_confirmation_exact_match",
                "final_confirmation_phrase_reused",
                "approval_artifact_reestablished",
                "approval_validation_passed",
                "approval_exact_match_ready",
                "approval_command_displayed",
                "approval_command_saved",
                "approval_command_copyable",
                "approval_command_pbcopy",
                "step4_approval_phrase_used",
                "step4_approval_phrase_spoofed",
                "step4_approval_gate_reused_as_step6g",
                "approval_command_full_text_present",
            ),
        )
        if not isinstance(self.approval_command_fingerprint, str):
            raise LiveVerificationValidationError(
                "approval_command_fingerprint must be str",
            )
        if not isinstance(self.approval_sha256_prefix, str):
            raise LiveVerificationValidationError("approval_sha256_prefix must be str")


@dataclass(frozen=True)
class LiveOrderRealStep6GPreflightSnapshot:
    final_confirmation_preflight_passed: bool
    post_immediate_preflight_passed: bool
    market_session_state: str
    market_window_allowed: bool
    broker_maintenance_active: bool
    holiday_or_special_close: bool
    market_hours_unknown: bool
    open_positions_count: int
    active_orders_count: int
    ticker_symbol: str
    ticker_spread_jpy: float
    ticker_age_seconds: float
    ticker_check_passed: bool
    permission_scope_check_passed: bool
    ip_account_binding_check_passed: bool
    previous_result_unknown_check_passed: bool
    raw_request_saved: bool = False
    raw_request_displayed: bool = False
    raw_response_saved: bool = False
    raw_response_displayed: bool = False
    headers_saved: bool = False
    headers_displayed: bool = False
    signature_saved: bool = False
    signature_displayed: bool = False
    credentials_displayed: bool = False
    order_ids_displayed: bool = False
    execution_ids_displayed: bool = False
    position_ids_displayed: bool = False
    client_order_ids_displayed: bool = False

    def __post_init__(self) -> None:
        _validate_bool_fields(
            self,
            (
                "final_confirmation_preflight_passed",
                "post_immediate_preflight_passed",
                "market_window_allowed",
                "broker_maintenance_active",
                "holiday_or_special_close",
                "market_hours_unknown",
                "ticker_check_passed",
                "permission_scope_check_passed",
                "ip_account_binding_check_passed",
                "previous_result_unknown_check_passed",
                "raw_request_saved",
                "raw_request_displayed",
                "raw_response_saved",
                "raw_response_displayed",
                "headers_saved",
                "headers_displayed",
                "signature_saved",
                "signature_displayed",
                "credentials_displayed",
                "order_ids_displayed",
                "execution_ids_displayed",
                "position_ids_displayed",
                "client_order_ids_displayed",
            ),
        )
        _require_non_empty("market_session_state", self.market_session_state)
        _validate_non_negative_int("open_positions_count", self.open_positions_count)
        _validate_non_negative_int("active_orders_count", self.active_orders_count)
        _require_non_empty("ticker_symbol", self.ticker_symbol)
        _validate_number("ticker_spread_jpy", self.ticker_spread_jpy)
        _validate_number("ticker_age_seconds", self.ticker_age_seconds)


@dataclass(frozen=True)
class LiveOrderRealStep6GAttemptState:
    post_attempt_limit: int
    post_attempt_count_before: int
    post_attempt_count_after: int
    post_executed: bool
    post_allowed_this_step: bool
    allowed_for_live_before: bool
    allowed_for_live_persisted: bool
    allowed_for_live_after: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool

    def __post_init__(self) -> None:
        for field_name in (
            "post_attempt_limit",
            "post_attempt_count_before",
            "post_attempt_count_after",
        ):
            _validate_non_negative_int(field_name, getattr(self, field_name))
        _validate_bool_fields(
            self,
            (
                "post_executed",
                "post_allowed_this_step",
                "allowed_for_live_before",
                "allowed_for_live_persisted",
                "allowed_for_live_after",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GRouteContractSnapshot:
    route_contract_name: str
    route_contract_kind: str
    uses_step4_approval_phrase: bool
    spoofs_step4_approval_phrase: bool
    mutates_step4_ledger_state: bool
    requires_step4_prepared_ledger: bool
    uses_step6g_dedicated_attempt_state: bool
    calls_live_order_once_directly: bool
    imports_live_order_once: bool
    imports_broker: bool
    imports_private_api: bool
    creates_new_order_endpoint: bool
    creates_new_payload_builder: bool
    order_endpoint_called: bool
    order_payload_generated: bool
    order_payload_sent: bool
    http_post_executed: bool
    raw_request_displayed: bool
    raw_response_displayed: bool
    headers_displayed: bool
    signature_displayed: bool
    credentials_displayed: bool
    real_ids_displayed: bool
    retry_on_unknown: bool
    retry_on_timeout: bool
    retry_on_reject: bool
    explicit_safe_adapter_contract: bool = False

    def __post_init__(self) -> None:
        _require_non_empty("route_contract_name", self.route_contract_name)
        _require_non_empty("route_contract_kind", self.route_contract_kind)
        _validate_bool_fields(
            self,
            (
                "uses_step4_approval_phrase",
                "spoofs_step4_approval_phrase",
                "mutates_step4_ledger_state",
                "requires_step4_prepared_ledger",
                "uses_step6g_dedicated_attempt_state",
                "calls_live_order_once_directly",
                "imports_live_order_once",
                "imports_broker",
                "imports_private_api",
                "creates_new_order_endpoint",
                "creates_new_payload_builder",
                "order_endpoint_called",
                "order_payload_generated",
                "order_payload_sent",
                "http_post_executed",
                "raw_request_displayed",
                "raw_response_displayed",
                "headers_displayed",
                "signature_displayed",
                "credentials_displayed",
                "real_ids_displayed",
                "retry_on_unknown",
                "retry_on_timeout",
                "retry_on_reject",
                "explicit_safe_adapter_contract",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GPostRouteBridgeResult:
    bridge_id: str
    created_at: datetime
    status: LiveOrderRealStep6GPostRouteBridgeStatus
    bridge_ready: bool
    eligible_for_future_step6g_execution_attempt: bool
    no_api_executed: bool
    no_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    allowed_for_live: bool
    post_allowed_this_step: bool
    post_executed: bool
    recommended_next_step: str
    order_intent_snapshot: LiveOrderRealStep6GOrderIntentSnapshot
    approval_snapshot: LiveOrderRealStep6GApprovalSnapshot
    preflight_snapshot: LiveOrderRealStep6GPreflightSnapshot
    attempt_state: LiveOrderRealStep6GAttemptState
    route_contract_snapshot: LiveOrderRealStep6GRouteContractSnapshot
    check_results: tuple[LiveOrderRealStep6GPostRouteBridgeCheckResult, ...]
    blocked_reasons: tuple[str, ...]

    @property
    def bridge_status(self) -> LiveOrderRealStep6GPostRouteBridgeStatus:
        return self.status

    def __post_init__(self) -> None:
        _require_non_empty("bridge_id", self.bridge_id)
        _ensure_aware(self.created_at)
        if not isinstance(self.status, LiveOrderRealStep6GPostRouteBridgeStatus):
            raise LiveVerificationValidationError("status must be Step 6G bridge status")
        _validate_bool_fields(
            self,
            (
                "bridge_ready",
                "eligible_for_future_step6g_execution_attempt",
                "no_api_executed",
                "no_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "allowed_for_live",
                "post_allowed_this_step",
                "post_executed",
            ),
        )
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        if self.bridge_ready and self.blocked_reasons:
            raise LiveVerificationValidationError("ready bridge cannot have blocked reasons")
        if (
            self.bridge_ready
            and self.status is not BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
        ):
            raise LiveVerificationValidationError("ready bridge status mismatch")
        if self.post_allowed_this_step:
            raise LiveVerificationValidationError(
                "pure bridge must keep post_allowed_this_step=false",
            )
        if self.allowed_for_live:
            raise LiveVerificationValidationError("pure bridge must keep allowed_for_live=false")
        if self.post_executed:
            raise LiveVerificationValidationError("pure bridge must keep post_executed=false")


def build_live_order_real_step6g_post_route_bridge(
    *,
    order_intent_snapshot: LiveOrderRealStep6GOrderIntentSnapshot,
    approval_snapshot: LiveOrderRealStep6GApprovalSnapshot,
    preflight_snapshot: LiveOrderRealStep6GPreflightSnapshot,
    attempt_state: LiveOrderRealStep6GAttemptState,
    route_contract_snapshot: LiveOrderRealStep6GRouteContractSnapshot,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GPostRouteBridgeResult:
    """Build a pure Step 6G bridge decision without API or POST execution."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    order_reasons = _order_intent_blocked_reasons(order_intent_snapshot)
    step4_reasons = _step4_spoofing_reasons(approval_snapshot, route_contract_snapshot)
    raw_reasons = _raw_or_secret_exposure_reasons(
        approval_snapshot,
        preflight_snapshot,
        route_contract_snapshot,
    )
    approval_reasons = _approval_blocked_reasons(approval_snapshot)
    preflight_reasons = _preflight_blocked_reasons(preflight_snapshot)
    attempt_reasons = _attempt_state_blocked_reasons(attempt_state)
    route_reasons = _route_unsafe_reasons(route_contract_snapshot)
    unsupported_reasons = _unsupported_reasons(route_contract_snapshot)

    if order_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_ORDER_INTENT
        primary_reasons = order_reasons
    elif step4_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_STEP4_SPOOFING
        primary_reasons = step4_reasons
    elif raw_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_RAW_OR_SECRET_EXPOSURE
        primary_reasons = raw_reasons
    elif approval_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_APPROVAL
        primary_reasons = approval_reasons
    elif preflight_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_PREFLIGHT
        primary_reasons = preflight_reasons
    elif attempt_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_ATTEMPT_STATE
        primary_reasons = attempt_reasons
    elif route_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_ROUTE_UNSAFE
        primary_reasons = route_reasons
    elif unsupported_reasons:
        status = BridgeStatus.BLOCKED_STEP6G_BRIDGE_UNSUPPORTED
        primary_reasons = unsupported_reasons
    else:
        status = BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
        primary_reasons = ()

    all_reasons = _merge_reasons(
        primary_reasons,
        order_reasons,
        step4_reasons,
        raw_reasons,
        approval_reasons,
        preflight_reasons,
        attempt_reasons,
        route_reasons,
        unsupported_reasons,
    )
    ready = status is BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
    check_results = _build_check_results(
        order_intent_snapshot=order_intent_snapshot,
        approval_snapshot=approval_snapshot,
        preflight_snapshot=preflight_snapshot,
        attempt_state=attempt_state,
        route_contract_snapshot=route_contract_snapshot,
    )
    return LiveOrderRealStep6GPostRouteBridgeResult(
        bridge_id=make_live_order_real_step6g_post_route_bridge_id(created),
        created_at=created,
        status=status,
        bridge_ready=ready,
        eligible_for_future_step6g_execution_attempt=ready,
        no_api_executed=True,
        no_post_executed=True,
        order_endpoint_called=route_contract_snapshot.order_endpoint_called,
        live_order_once_called=route_contract_snapshot.calls_live_order_once_directly,
        allowed_for_live=False,
        post_allowed_this_step=False,
        post_executed=attempt_state.post_executed,
        recommended_next_step=STEP6G_BRIDGE_READY_RECOMMENDED_NEXT_STEP
        if ready
        else "fix_step6g_post_route_bridge_blockers_no_api_no_post",
        order_intent_snapshot=order_intent_snapshot,
        approval_snapshot=approval_snapshot,
        preflight_snapshot=preflight_snapshot,
        attempt_state=attempt_state,
        route_contract_snapshot=route_contract_snapshot,
        check_results=check_results,
        blocked_reasons=all_reasons,
    )


def render_live_order_real_step6g_post_route_bridge_markdown(
    bridge: LiveOrderRealStep6GPostRouteBridgeResult,
) -> str:
    """Render a sanitized Step 6G bridge report."""
    lines = [
        "# Step 6G POST Route Bridge",
        "",
        "This bridge is pure model only.",
        "This bridge does not execute API calls.",
        "This bridge does not execute HTTP POST.",
        "This bridge does not call order endpoint.",
        "This bridge does not call live_order_once.",
        "This bridge does not authorize reusing old final confirmation.",
        "Future Step 6G execution requires a new final confirmation and fresh preflight.",
        "",
        "## Summary",
        f"- status: {bridge.status.value}",
        f"- bridge_ready: {_bool_text(bridge.bridge_ready)}",
        (
            "- eligible_for_future_step6g_execution_attempt: "
            f"{_bool_text(bridge.eligible_for_future_step6g_execution_attempt)}"
        ),
        f"- no_api_executed: {_bool_text(bridge.no_api_executed)}",
        f"- no_post_executed: {_bool_text(bridge.no_post_executed)}",
        f"- allowed_for_live: {_bool_text(bridge.allowed_for_live)}",
        f"- post_allowed_this_step: {_bool_text(bridge.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(bridge.post_executed)}",
        "",
        "## Order Intent",
        f"- symbol: {bridge.order_intent_snapshot.symbol}",
        f"- side: {bridge.order_intent_snapshot.side}",
        f"- size: {bridge.order_intent_snapshot.size}",
        f"- executionType: {bridge.order_intent_snapshot.executionType}",
        f"- source_label: {bridge.order_intent_snapshot.source_label}",
        "",
        "## Approval",
        (
            "- step6g_final_confirmation_exact_match: "
            f"{_bool_text(bridge.approval_snapshot.step6g_final_confirmation_exact_match)}"
        ),
        (
            "- final_confirmation_phrase_reused: "
            f"{_bool_text(bridge.approval_snapshot.final_confirmation_phrase_reused)}"
        ),
        (
            "- approval_artifact_reestablished: "
            f"{_bool_text(bridge.approval_snapshot.approval_artifact_reestablished)}"
        ),
        (
            "- approval_validation_passed: "
            f"{_bool_text(bridge.approval_snapshot.approval_validation_passed)}"
        ),
        f"- approval_fingerprint: {bridge.approval_snapshot.approval_command_fingerprint}",
        f"- sha256_prefix: {bridge.approval_snapshot.approval_sha256_prefix}",
        "",
        "## Preflight",
        (
            "- final_confirmation_preflight_passed: "
            f"{_bool_text(bridge.preflight_snapshot.final_confirmation_preflight_passed)}"
        ),
        (
            "- post_immediate_preflight_passed: "
            f"{_bool_text(bridge.preflight_snapshot.post_immediate_preflight_passed)}"
        ),
        f"- market_session_state: {bridge.preflight_snapshot.market_session_state}",
        f"- open_positions_count: {bridge.preflight_snapshot.open_positions_count}",
        f"- active_orders_count: {bridge.preflight_snapshot.active_orders_count}",
        f"- ticker_symbol: {bridge.preflight_snapshot.ticker_symbol}",
        f"- ticker_spread_jpy: {bridge.preflight_snapshot.ticker_spread_jpy}",
        f"- ticker_age_seconds: {bridge.preflight_snapshot.ticker_age_seconds}",
        "",
        "## Attempt State",
        f"- post_attempt_limit: {bridge.attempt_state.post_attempt_limit}",
        f"- post_attempt_count_before: {bridge.attempt_state.post_attempt_count_before}",
        f"- post_attempt_count_after: {bridge.attempt_state.post_attempt_count_after}",
        f"- retry_allowed: {_bool_text(bridge.attempt_state.retry_allowed)}",
        f"- loop_allowed: {_bool_text(bridge.attempt_state.loop_allowed)}",
        (
            "- add/change/cancel/close allowed: "
            f"{_bool_text(_any_order_mutation_allowed(bridge.attempt_state))}"
        ),
        "",
        "## Route Safety",
        f"- route_contract_name: {bridge.route_contract_snapshot.route_contract_name}",
        f"- route_contract_kind: {bridge.route_contract_snapshot.route_contract_kind}",
        (
            "- uses_step6g_dedicated_attempt_state: "
            f"{_bool_text(bridge.route_contract_snapshot.uses_step6g_dedicated_attempt_state)}"
        ),
        (
            "- explicit_safe_adapter_contract: "
            f"{_bool_text(bridge.route_contract_snapshot.explicit_safe_adapter_contract)}"
        ),
        (
            "- calls_live_order_once_directly: "
            f"{_bool_text(bridge.route_contract_snapshot.calls_live_order_once_directly)}"
        ),
        (
            "- order_endpoint_called: "
            f"{_bool_text(bridge.route_contract_snapshot.order_endpoint_called)}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in bridge.blocked_reasons],
        "",
        "## Check Results",
        *[
            (
                f"- {check.name}: {_bool_text(check.passed)} "
                f"({check.sanitized_value}; expected {check.expected})"
            )
            for check in bridge.check_results
        ],
        "",
        "## Recommended Next Step",
        f"- {bridge.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def make_live_order_real_step6g_post_route_bridge_id(created_at: datetime) -> str:
    created = _ensure_aware(created_at)
    return (
        f"{LIVE_ORDER_REAL_STEP6G_POST_ROUTE_BRIDGE_ID_PREFIX}{created.strftime('%Y%m%dT%H%M%SZ')}"
    )


def _order_intent_blocked_reasons(
    snapshot: LiveOrderRealStep6GOrderIntentSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if snapshot.symbol != SUPPORTED_SYMBOL:
        reasons.append("symbol_not_usd_jpy")
    if snapshot.side != "BUY":
        reasons.append("side_not_buy")
    if snapshot.size != LIVE_ORDER_CANDIDATE_SIZE:
        reasons.append("size_not_100")
    if snapshot.executionType != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        reasons.append("execution_type_not_market")
    for field_name in (
        "codex_inferred_side",
        "codex_inferred_symbol",
        "codex_inferred_size",
        "codex_inferred_execution_type",
    ):
        if getattr(snapshot, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _approval_blocked_reasons(
    snapshot: LiveOrderRealStep6GApprovalSnapshot,
) -> tuple[str, ...]:
    checks = (
        ("step6g_final_confirmation_received", snapshot.step6g_final_confirmation_received),
        (
            "step6g_final_confirmation_exact_match",
            snapshot.step6g_final_confirmation_exact_match,
        ),
        ("approval_artifact_reestablished", snapshot.approval_artifact_reestablished),
        ("approval_validation_passed", snapshot.approval_validation_passed),
        ("approval_exact_match_ready", snapshot.approval_exact_match_ready),
    )
    reasons = [f"{name}_missing" for name, passed in checks if not passed]
    if snapshot.final_confirmation_phrase_reused:
        reasons.append("final_confirmation_phrase_reused")
    if not snapshot.approval_command_fingerprint:
        reasons.append("approval_command_fingerprint_missing")
    if not snapshot.approval_sha256_prefix:
        reasons.append("approval_sha256_prefix_missing")
    return tuple(reasons)


def _step4_spoofing_reasons(
    approval: LiveOrderRealStep6GApprovalSnapshot,
    route: LiveOrderRealStep6GRouteContractSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if approval.step4_approval_phrase_used or route.uses_step4_approval_phrase:
        reasons.append("step4_approval_phrase_used")
    if approval.step4_approval_phrase_spoofed or route.spoofs_step4_approval_phrase:
        reasons.append("step4_approval_phrase_spoofed")
    if approval.step4_approval_gate_reused_as_step6g:
        reasons.append("step4_approval_gate_reused_as_step6g")
    if route.mutates_step4_ledger_state:
        reasons.append("step4_ledger_state_mutation")
    return tuple(reasons)


def _preflight_blocked_reasons(
    snapshot: LiveOrderRealStep6GPreflightSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not snapshot.final_confirmation_preflight_passed:
        reasons.append("final_confirmation_preflight_not_passed")
    if not snapshot.post_immediate_preflight_passed:
        reasons.append("post_immediate_preflight_not_passed")
    if snapshot.market_session_state != STEP6G_MARKET_OPEN_STATE:
        reasons.append("market_session_not_open")
    if not snapshot.market_window_allowed:
        reasons.append("market_window_not_allowed")
    if snapshot.broker_maintenance_active:
        reasons.append("broker_maintenance_active")
    if snapshot.holiday_or_special_close:
        reasons.append("holiday_or_special_close")
    if snapshot.market_hours_unknown:
        reasons.append("market_hours_unknown")
    if snapshot.open_positions_count != 0:
        reasons.append("open_positions_not_zero")
    if snapshot.active_orders_count != 0:
        reasons.append("active_orders_not_zero")
    if snapshot.ticker_symbol != SUPPORTED_SYMBOL:
        reasons.append("ticker_symbol_not_usd_jpy")
    if snapshot.ticker_spread_jpy > STEP6G_MAX_SPREAD_JPY:
        reasons.append("ticker_spread_too_wide")
    if snapshot.ticker_age_seconds > STEP6G_MAX_TICKER_AGE_SECONDS:
        reasons.append("ticker_age_stale")
    if snapshot.ticker_age_seconds < STEP6G_MIN_TICKER_AGE_SECONDS:
        reasons.append("ticker_age_future_skew_too_large")
    if not snapshot.ticker_check_passed:
        reasons.append("ticker_check_failed")
    if not snapshot.permission_scope_check_passed:
        reasons.append("permission_scope_check_failed")
    if not snapshot.ip_account_binding_check_passed:
        reasons.append("ip_account_binding_check_failed")
    if not snapshot.previous_result_unknown_check_passed:
        reasons.append("previous_result_unknown_check_failed")
    return tuple(reasons)


def _attempt_state_blocked_reasons(
    state: LiveOrderRealStep6GAttemptState,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if state.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if state.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    if state.post_attempt_count_after != 0:
        reasons.append("post_attempt_count_after_not_zero")
    if state.post_executed:
        reasons.append("post_executed_unsafe")
    if state.post_allowed_this_step:
        reasons.append("post_allowed_this_step_unsafe_for_pure_model")
    if state.allowed_for_live_before:
        reasons.append("allowed_for_live_before_unsafe")
    if state.allowed_for_live_persisted:
        reasons.append("allowed_for_live_persisted_unsafe")
    if state.allowed_for_live_after:
        reasons.append("allowed_for_live_after_unsafe")
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(state, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _route_unsafe_reasons(
    route: LiveOrderRealStep6GRouteContractSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if route.requires_step4_prepared_ledger:
        reasons.append("requires_step4_prepared_ledger")
    for field_name in (
        "calls_live_order_once_directly",
        "imports_live_order_once",
        "imports_broker",
        "imports_private_api",
        "creates_new_order_endpoint",
        "creates_new_payload_builder",
        "order_endpoint_called",
        "order_payload_generated",
        "order_payload_sent",
        "http_post_executed",
        "retry_on_unknown",
        "retry_on_timeout",
        "retry_on_reject",
    ):
        if getattr(route, field_name):
            reasons.append(f"{field_name}_unsafe")
    return tuple(reasons)


def _unsupported_reasons(
    route: LiveOrderRealStep6GRouteContractSnapshot,
) -> tuple[str, ...]:
    if route.uses_step6g_dedicated_attempt_state or route.explicit_safe_adapter_contract:
        return ()
    return ("missing_step6g_dedicated_attempt_state_or_safe_adapter",)


def _raw_or_secret_exposure_reasons(
    approval: LiveOrderRealStep6GApprovalSnapshot,
    preflight: LiveOrderRealStep6GPreflightSnapshot,
    route: LiveOrderRealStep6GRouteContractSnapshot,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "approval_command_displayed",
        "approval_command_saved",
        "approval_command_copyable",
        "approval_command_pbcopy",
        "approval_command_full_text_present",
    ):
        if getattr(approval, field_name):
            reasons.append(f"{field_name}_unsafe")
    for field_name in (
        "raw_request_saved",
        "raw_request_displayed",
        "raw_response_saved",
        "raw_response_displayed",
        "headers_saved",
        "headers_displayed",
        "signature_saved",
        "signature_displayed",
        "credentials_displayed",
        "order_ids_displayed",
        "execution_ids_displayed",
        "position_ids_displayed",
        "client_order_ids_displayed",
    ):
        if getattr(preflight, field_name):
            reasons.append(f"{field_name}_unsafe")
    for field_name in (
        "raw_request_displayed",
        "raw_response_displayed",
        "headers_displayed",
        "signature_displayed",
        "credentials_displayed",
        "real_ids_displayed",
    ):
        if getattr(route, field_name):
            reasons.append(f"route_{field_name}_unsafe")
    return tuple(reasons)


def _build_check_results(
    *,
    order_intent_snapshot: LiveOrderRealStep6GOrderIntentSnapshot,
    approval_snapshot: LiveOrderRealStep6GApprovalSnapshot,
    preflight_snapshot: LiveOrderRealStep6GPreflightSnapshot,
    attempt_state: LiveOrderRealStep6GAttemptState,
    route_contract_snapshot: LiveOrderRealStep6GRouteContractSnapshot,
) -> tuple[LiveOrderRealStep6GPostRouteBridgeCheckResult, ...]:
    checks: list[LiveOrderRealStep6GPostRouteBridgeCheckResult] = []

    def add(name: str, passed: bool, value: object, expected: str) -> None:
        checks.append(
            LiveOrderRealStep6GPostRouteBridgeCheckResult(
                name=name,
                passed=passed,
                reason="passed" if passed else "blocked",
                sanitized_value=_safe_value(value),
                expected=expected,
            ),
        )

    add(
        "order symbol USD_JPY",
        order_intent_snapshot.symbol == SUPPORTED_SYMBOL,
        order_intent_snapshot.symbol,
        SUPPORTED_SYMBOL,
    )
    add("order side BUY", order_intent_snapshot.side == "BUY", order_intent_snapshot.side, "BUY")
    add(
        "order size 100",
        order_intent_snapshot.size == LIVE_ORDER_CANDIDATE_SIZE,
        order_intent_snapshot.size,
        str(LIVE_ORDER_CANDIDATE_SIZE),
    )
    add(
        "order executionType MARKET",
        order_intent_snapshot.executionType == LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
        order_intent_snapshot.executionType,
        LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    )
    add(
        "Codex did not infer order intent",
        not _any_order_intent_inferred(order_intent_snapshot),
        _any_order_intent_inferred(order_intent_snapshot),
        "false",
    )
    add(
        "Step 6G final confirmation exact match",
        approval_snapshot.step6g_final_confirmation_received
        and approval_snapshot.step6g_final_confirmation_exact_match,
        approval_snapshot.step6g_final_confirmation_exact_match,
        "true",
    )
    add(
        "final confirmation not reused",
        not approval_snapshot.final_confirmation_phrase_reused,
        approval_snapshot.final_confirmation_phrase_reused,
        "false",
    )
    add(
        "approval artifact reestablished",
        approval_snapshot.approval_artifact_reestablished,
        approval_snapshot.approval_artifact_reestablished,
        "true",
    )
    add(
        "approval validation passed",
        approval_snapshot.approval_validation_passed,
        approval_snapshot.approval_validation_passed,
        "true",
    )
    add(
        "approval exact match ready",
        approval_snapshot.approval_exact_match_ready,
        approval_snapshot.approval_exact_match_ready,
        "true",
    )
    add(
        "approval fingerprint present",
        bool(approval_snapshot.approval_command_fingerprint),
        "present" if approval_snapshot.approval_command_fingerprint else "missing",
        "present",
    )
    add(
        "approval sha256 prefix present",
        bool(approval_snapshot.approval_sha256_prefix),
        "present" if approval_snapshot.approval_sha256_prefix else "missing",
        "present",
    )
    add(
        "Step 4 approval not used or spoofed",
        not _step4_spoofing_reasons(approval_snapshot, route_contract_snapshot),
        bool(_step4_spoofing_reasons(approval_snapshot, route_contract_snapshot)),
        "false",
    )
    add(
        "final confirmation preflight passed",
        preflight_snapshot.final_confirmation_preflight_passed,
        preflight_snapshot.final_confirmation_preflight_passed,
        "true",
    )
    add(
        "POST immediate preflight passed",
        preflight_snapshot.post_immediate_preflight_passed,
        preflight_snapshot.post_immediate_preflight_passed,
        "true",
    )
    add(
        "market session open",
        preflight_snapshot.market_session_state == STEP6G_MARKET_OPEN_STATE,
        preflight_snapshot.market_session_state,
        STEP6G_MARKET_OPEN_STATE,
    )
    add(
        "open positions zero",
        preflight_snapshot.open_positions_count == 0,
        preflight_snapshot.open_positions_count,
        "0",
    )
    add(
        "active orders zero",
        preflight_snapshot.active_orders_count == 0,
        preflight_snapshot.active_orders_count,
        "0",
    )
    add(
        "ticker spread within limit",
        preflight_snapshot.ticker_spread_jpy <= STEP6G_MAX_SPREAD_JPY,
        preflight_snapshot.ticker_spread_jpy,
        f"<= {STEP6G_MAX_SPREAD_JPY}",
    )
    add(
        "ticker age within range",
        STEP6G_MIN_TICKER_AGE_SECONDS
        <= preflight_snapshot.ticker_age_seconds
        <= STEP6G_MAX_TICKER_AGE_SECONDS,
        preflight_snapshot.ticker_age_seconds,
        f"{STEP6G_MIN_TICKER_AGE_SECONDS}..{STEP6G_MAX_TICKER_AGE_SECONDS}",
    )
    add(
        "permission IP previous checks passed",
        preflight_snapshot.permission_scope_check_passed
        and preflight_snapshot.ip_account_binding_check_passed
        and preflight_snapshot.previous_result_unknown_check_passed,
        "all_passed"
        if preflight_snapshot.permission_scope_check_passed
        and preflight_snapshot.ip_account_binding_check_passed
        and preflight_snapshot.previous_result_unknown_check_passed
        else "blocked",
        "all_passed",
    )
    add(
        "post attempt limit one",
        attempt_state.post_attempt_limit == 1,
        attempt_state.post_attempt_limit,
        "1",
    )
    add(
        "post attempt count before zero",
        attempt_state.post_attempt_count_before == 0,
        attempt_state.post_attempt_count_before,
        "0",
    )
    add(
        "pure model keeps post disallowed",
        not attempt_state.post_allowed_this_step,
        attempt_state.post_allowed_this_step,
        "false",
    )
    add("post not executed", not attempt_state.post_executed, attempt_state.post_executed, "false")
    add(
        "retry loop order mutation disabled",
        not _any_retry_loop_or_mutation_allowed(attempt_state),
        _any_retry_loop_or_mutation_allowed(attempt_state),
        "false",
    )
    add(
        "route does not call live_order_once",
        not route_contract_snapshot.calls_live_order_once_directly
        and not route_contract_snapshot.imports_live_order_once,
        "not_called"
        if not route_contract_snapshot.calls_live_order_once_directly
        and not route_contract_snapshot.imports_live_order_once
        else "unsafe",
        "not_called",
    )
    add(
        "route has Step 6G attempt contract",
        route_contract_snapshot.uses_step6g_dedicated_attempt_state
        or route_contract_snapshot.explicit_safe_adapter_contract,
        "present"
        if route_contract_snapshot.uses_step6g_dedicated_attempt_state
        or route_contract_snapshot.explicit_safe_adapter_contract
        else "missing",
        "present",
    )
    add(
        "route does not create endpoint or payload builder",
        not route_contract_snapshot.creates_new_order_endpoint
        and not route_contract_snapshot.creates_new_payload_builder,
        "not_created"
        if not route_contract_snapshot.creates_new_order_endpoint
        and not route_contract_snapshot.creates_new_payload_builder
        else "unsafe",
        "not_created",
    )
    add(
        "no raw secret real ID exposure",
        not _raw_or_secret_exposure_reasons(
            approval_snapshot, preflight_snapshot, route_contract_snapshot
        ),
        "none"
        if not _raw_or_secret_exposure_reasons(
            approval_snapshot, preflight_snapshot, route_contract_snapshot
        )
        else "unsafe",
        "none",
    )
    return tuple(checks)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _any_order_intent_inferred(
    snapshot: LiveOrderRealStep6GOrderIntentSnapshot,
) -> bool:
    return (
        snapshot.codex_inferred_side
        or snapshot.codex_inferred_symbol
        or snapshot.codex_inferred_size
        or snapshot.codex_inferred_execution_type
    )


def _any_retry_loop_or_mutation_allowed(state: LiveOrderRealStep6GAttemptState) -> bool:
    return state.retry_allowed or state.loop_allowed or _any_order_mutation_allowed(state)


def _any_order_mutation_allowed(state: LiveOrderRealStep6GAttemptState) -> bool:
    return (
        state.add_order_allowed
        or state.change_order_allowed
        or state.cancel_order_allowed
        or state.close_order_allowed
    )


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime value must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime value must be timezone-aware")
    return value.astimezone(UTC)


def _validate_bool_fields(target: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(target, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_number(field_name: str, value: float) -> None:
    if type(value) not in {int, float}:
        raise LiveVerificationValidationError(f"{field_name} must be number")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _safe_value(value: object) -> str:
    if type(value) is bool:
        return _bool_text(value)
    return str(value)
