"""Step 6G runtime bridge fake executor model.

This module is fake-only. It validates that a ready Step 6G POST route bridge
result can move into a future runtime boundary without crossing live execution
paths. It does not call APIs, import broker or Private API clients, import
live_order_once, build an order payload, or execute HTTP POST.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_real_step6g_post_route_bridge import (
    BridgeStatus,
    LiveOrderRealStep6GPostRouteBridgeCheckResult,
    LiveOrderRealStep6GPostRouteBridgeResult,
)

LIVE_ORDER_REAL_STEP6G_RUNTIME_BRIDGE_ID_PREFIX = "LOR6GEB-"
STEP6G_RUNTIME_BRIDGE_RECOMMENDED_NEXT_STEP = (
    "run_separate_step6g_execution_with_new_final_confirmation_"
    "fresh_preflight_and_real_adapter_review"
)


class LiveOrderRealStep6GRuntimeBridgeStatus(str, Enum):
    STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST = (
        "STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST"
    )
    STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST = (
        "STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST"
    )
    BLOCKED_STEP6G_RUNTIME_BRIDGE_NOT_READY = "BLOCKED_STEP6G_RUNTIME_BRIDGE_NOT_READY"
    BLOCKED_STEP6G_RUNTIME_BRIDGE_APPROVAL = "BLOCKED_STEP6G_RUNTIME_BRIDGE_APPROVAL"
    BLOCKED_STEP6G_RUNTIME_BRIDGE_PREFLIGHT = "BLOCKED_STEP6G_RUNTIME_BRIDGE_PREFLIGHT"
    BLOCKED_STEP6G_RUNTIME_BRIDGE_ATTEMPT_STATE = "BLOCKED_STEP6G_RUNTIME_BRIDGE_ATTEMPT_STATE"
    BLOCKED_STEP6G_RUNTIME_BRIDGE_ROUTE_UNSAFE = "BLOCKED_STEP6G_RUNTIME_BRIDGE_ROUTE_UNSAFE"
    BLOCKED_STEP6G_RUNTIME_BRIDGE_RAW_OR_SECRET_EXPOSURE = (
        "BLOCKED_STEP6G_RUNTIME_BRIDGE_RAW_OR_SECRET_EXPOSURE"
    )
    BLOCKED_STEP6G_RUNTIME_BRIDGE_FAKE_RETRY_OR_LOOP = (
        "BLOCKED_STEP6G_RUNTIME_BRIDGE_FAKE_RETRY_OR_LOOP"
    )
    BLOCKED_STEP6G_RUNTIME_BRIDGE_UNSUPPORTED = "BLOCKED_STEP6G_RUNTIME_BRIDGE_UNSUPPORTED"


class LiveOrderRealStep6GRuntimeExecutionMode(str, Enum):
    FAKE_ONLY_NO_API_NO_POST = "FAKE_ONLY_NO_API_NO_POST"


class LiveOrderRealStep6GFakePostResultCategory(str, Enum):
    FAKE_POST_ACCEPTED_NO_API_NO_POST = "FAKE_POST_ACCEPTED_NO_API_NO_POST"
    FAKE_POST_REJECTED_NO_RETRY_NO_API_NO_POST = "FAKE_POST_REJECTED_NO_RETRY_NO_API_NO_POST"
    FAKE_POST_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST = (
        "FAKE_POST_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST"
    )
    FAKE_POST_TIMEOUT_NO_RETRY_NO_API_NO_POST = "FAKE_POST_TIMEOUT_NO_RETRY_NO_API_NO_POST"


RuntimeStatus = LiveOrderRealStep6GRuntimeBridgeStatus
RuntimeExecutionMode = LiveOrderRealStep6GRuntimeExecutionMode
FakePostResultCategory = LiveOrderRealStep6GFakePostResultCategory


@dataclass(frozen=True)
class LiveOrderRealStep6GRuntimeBridgeRequest:
    source_bridge_id: str
    source_bridge_status: str
    execution_mode: LiveOrderRealStep6GRuntimeExecutionMode
    step6g_post_route_bridge_ready: bool
    step6g_post_route_bridge_status: str
    order_intent_exact_match: bool
    approval_artifact_reestablished: bool
    approval_validation_passed: bool
    approval_exact_match: bool
    approval_fingerprint_present: bool
    final_confirmation_exact_match: bool
    final_confirmation_reused: bool
    final_confirmation_preflight_passed: bool
    post_immediate_preflight_passed: bool
    post_attempt_limit: int
    post_attempt_count_before: int
    fake_attempt_count: int
    post_allowed_this_step: bool
    post_executed: bool
    allowed_for_live: bool
    allowed_for_live_persisted: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    raw_secret_id_exposure: bool
    route_unsafe: bool
    step4_spoofing: bool
    real_http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    broker_order_path_called: bool

    def __post_init__(self) -> None:
        _require_non_empty("source_bridge_id", self.source_bridge_id)
        _require_non_empty("source_bridge_status", self.source_bridge_status)
        if not isinstance(self.execution_mode, LiveOrderRealStep6GRuntimeExecutionMode):
            raise LiveVerificationValidationError("execution_mode must be Step 6G runtime mode")
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int("post_attempt_count_before", self.post_attempt_count_before)
        _validate_non_negative_int("fake_attempt_count", self.fake_attempt_count)
        _validate_bool_fields(
            self,
            (
                "step6g_post_route_bridge_ready",
                "order_intent_exact_match",
                "approval_artifact_reestablished",
                "approval_validation_passed",
                "approval_exact_match",
                "approval_fingerprint_present",
                "final_confirmation_exact_match",
                "final_confirmation_reused",
                "final_confirmation_preflight_passed",
                "post_immediate_preflight_passed",
                "post_allowed_this_step",
                "post_executed",
                "allowed_for_live",
                "allowed_for_live_persisted",
                "retry_allowed",
                "loop_allowed",
                "add_order_allowed",
                "change_order_allowed",
                "cancel_order_allowed",
                "close_order_allowed",
                "raw_secret_id_exposure",
                "route_unsafe",
                "step4_spoofing",
                "real_http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "broker_order_path_called",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GFakePostExecutorResult:
    fake_post_attempted: bool
    fake_post_result_category: LiveOrderRealStep6GFakePostResultCategory
    fake_attempt_count: int
    fake_retry_count: int = 0
    fake_loop_count: int = 0
    real_http_post_executed: bool = False
    order_endpoint_called: bool = False
    live_order_once_called: bool = False
    broker_order_path_called: bool = False
    raw_request_present: bool = False
    raw_response_present: bool = False
    headers_present: bool = False
    signature_present: bool = False
    credentials_present: bool = False
    real_order_id_present: bool = False
    real_execution_id_present: bool = False
    real_position_id_present: bool = False
    real_client_order_id_present: bool = False
    result_is_fake: bool = True

    def __post_init__(self) -> None:
        if not isinstance(
            self.fake_post_result_category, LiveOrderRealStep6GFakePostResultCategory
        ):
            raise LiveVerificationValidationError(
                "fake_post_result_category must be Step 6G fake category",
            )
        _validate_non_negative_int("fake_attempt_count", self.fake_attempt_count)
        _validate_non_negative_int("fake_retry_count", self.fake_retry_count)
        _validate_non_negative_int("fake_loop_count", self.fake_loop_count)
        _validate_bool_fields(
            self,
            (
                "fake_post_attempted",
                "real_http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "broker_order_path_called",
                "raw_request_present",
                "raw_response_present",
                "headers_present",
                "signature_present",
                "credentials_present",
                "real_order_id_present",
                "real_execution_id_present",
                "real_position_id_present",
                "real_client_order_id_present",
                "result_is_fake",
            ),
        )


@dataclass(frozen=True)
class LiveOrderRealStep6GRuntimeBridgeCheckResult:
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
class LiveOrderRealStep6GRuntimeBridgeResult:
    runtime_bridge_id: str
    created_at: datetime
    status: LiveOrderRealStep6GRuntimeBridgeStatus
    fake_runtime_ready: bool
    fake_post_attempted: bool
    fake_post_result_category: str
    real_http_post_executed: bool
    order_endpoint_called: bool
    live_order_once_called: bool
    broker_order_path_called: bool
    allowed_for_live: bool
    post_allowed_this_step: bool
    post_executed: bool
    post_attempt_limit: int
    fake_attempt_count: int
    recommended_next_step: str
    request: LiveOrderRealStep6GRuntimeBridgeRequest
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None
    source_bridge_checks: tuple[LiveOrderRealStep6GPostRouteBridgeCheckResult, ...]
    check_results: tuple[LiveOrderRealStep6GRuntimeBridgeCheckResult, ...]
    blocked_reasons: tuple[str, ...]

    @property
    def runtime_status(self) -> LiveOrderRealStep6GRuntimeBridgeStatus:
        return self.status

    def __post_init__(self) -> None:
        _require_non_empty("runtime_bridge_id", self.runtime_bridge_id)
        _ensure_aware(self.created_at)
        if not isinstance(self.status, LiveOrderRealStep6GRuntimeBridgeStatus):
            raise LiveVerificationValidationError("status must be Step 6G runtime status")
        _validate_non_negative_int("post_attempt_limit", self.post_attempt_limit)
        _validate_non_negative_int("fake_attempt_count", self.fake_attempt_count)
        _validate_bool_fields(
            self,
            (
                "fake_runtime_ready",
                "fake_post_attempted",
                "real_http_post_executed",
                "order_endpoint_called",
                "live_order_once_called",
                "broker_order_path_called",
                "allowed_for_live",
                "post_allowed_this_step",
                "post_executed",
            ),
        )
        _require_non_empty("fake_post_result_category", self.fake_post_result_category)
        _require_non_empty("recommended_next_step", self.recommended_next_step)
        if not isinstance(self.source_bridge_checks, tuple):
            raise LiveVerificationValidationError("source_bridge_checks must be tuple")
        if not isinstance(self.check_results, tuple):
            raise LiveVerificationValidationError("check_results must be tuple")
        if not isinstance(self.blocked_reasons, tuple):
            raise LiveVerificationValidationError("blocked_reasons must be tuple")
        if self.fake_runtime_ready and self.blocked_reasons:
            raise LiveVerificationValidationError("ready fake runtime cannot have blockers")
        if self.real_http_post_executed:
            raise LiveVerificationValidationError(
                "fake runtime must keep real_http_post_executed=false"
            )
        if self.order_endpoint_called:
            raise LiveVerificationValidationError(
                "fake runtime must keep order_endpoint_called=false"
            )
        if self.live_order_once_called:
            raise LiveVerificationValidationError(
                "fake runtime must keep live_order_once_called=false"
            )
        if self.broker_order_path_called:
            raise LiveVerificationValidationError(
                "fake runtime must keep broker_order_path_called=false"
            )
        if self.allowed_for_live:
            raise LiveVerificationValidationError("fake runtime must keep allowed_for_live=false")
        if self.post_allowed_this_step:
            raise LiveVerificationValidationError(
                "fake runtime must keep post_allowed_this_step=false"
            )
        if self.post_executed:
            raise LiveVerificationValidationError("fake runtime must keep post_executed=false")


def build_live_order_real_step6g_runtime_bridge(
    *,
    step6g_post_route_bridge_result: LiveOrderRealStep6GPostRouteBridgeResult,
    runtime_request: LiveOrderRealStep6GRuntimeBridgeRequest | None = None,
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None = None,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GRuntimeBridgeResult:
    """Build a fake-only Step 6G runtime bridge decision."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    request = runtime_request or make_live_order_real_step6g_runtime_bridge_request(
        step6g_post_route_bridge_result=step6g_post_route_bridge_result,
        fake_attempt_count=fake_executor_result.fake_attempt_count if fake_executor_result else 0,
    )

    not_ready_reasons = _not_ready_reasons(step6g_post_route_bridge_result, request)
    approval_reasons = _approval_reasons(request)
    preflight_reasons = _preflight_reasons(request)
    attempt_reasons = _attempt_state_reasons(request, fake_executor_result)
    retry_reasons = _retry_or_loop_reasons(request, fake_executor_result)
    route_reasons = _route_unsafe_reasons(request, fake_executor_result)
    raw_reasons = _raw_or_secret_exposure_reasons(request, fake_executor_result)
    unsupported_reasons = _unsupported_reasons(request)

    if not_ready_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_NOT_READY
        primary_reasons = not_ready_reasons
    elif approval_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_APPROVAL
        primary_reasons = approval_reasons
    elif preflight_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_PREFLIGHT
        primary_reasons = preflight_reasons
    elif attempt_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_ATTEMPT_STATE
        primary_reasons = attempt_reasons
    elif retry_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_FAKE_RETRY_OR_LOOP
        primary_reasons = retry_reasons
    elif route_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_ROUTE_UNSAFE
        primary_reasons = route_reasons
    elif raw_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_RAW_OR_SECRET_EXPOSURE
        primary_reasons = raw_reasons
    elif unsupported_reasons:
        status = RuntimeStatus.BLOCKED_STEP6G_RUNTIME_BRIDGE_UNSUPPORTED
        primary_reasons = unsupported_reasons
    elif fake_executor_result is None:
        status = RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST
        primary_reasons = ()
    else:
        status = RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST
        primary_reasons = ()

    all_reasons = _merge_reasons(
        primary_reasons,
        not_ready_reasons,
        approval_reasons,
        preflight_reasons,
        attempt_reasons,
        retry_reasons,
        route_reasons,
        raw_reasons,
        unsupported_reasons,
    )
    ready = status in {
        RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST,
        RuntimeStatus.STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST,
    }
    check_results = _build_check_results(
        bridge=step6g_post_route_bridge_result,
        request=request,
        fake_executor_result=fake_executor_result,
    )
    return LiveOrderRealStep6GRuntimeBridgeResult(
        runtime_bridge_id=make_live_order_real_step6g_runtime_bridge_id(created),
        created_at=created,
        status=status,
        fake_runtime_ready=ready,
        fake_post_attempted=bool(fake_executor_result and fake_executor_result.fake_post_attempted),
        fake_post_result_category=fake_executor_result.fake_post_result_category.value
        if fake_executor_result
        else "NOT_RUN_FAKE_ONLY_NO_API_NO_POST",
        real_http_post_executed=False,
        order_endpoint_called=False,
        live_order_once_called=False,
        broker_order_path_called=False,
        allowed_for_live=False,
        post_allowed_this_step=False,
        post_executed=False,
        post_attempt_limit=request.post_attempt_limit,
        fake_attempt_count=fake_executor_result.fake_attempt_count
        if fake_executor_result
        else request.fake_attempt_count,
        recommended_next_step=STEP6G_RUNTIME_BRIDGE_RECOMMENDED_NEXT_STEP
        if ready
        else "fix_step6g_runtime_bridge_blockers_no_api_no_post",
        request=request,
        fake_executor_result=fake_executor_result,
        source_bridge_checks=step6g_post_route_bridge_result.check_results,
        check_results=check_results,
        blocked_reasons=all_reasons,
    )


def run_live_order_real_step6g_fake_runtime_bridge(
    *,
    step6g_post_route_bridge_result: LiveOrderRealStep6GPostRouteBridgeResult,
    fake_post_result_category: LiveOrderRealStep6GFakePostResultCategory = (
        FakePostResultCategory.FAKE_POST_ACCEPTED_NO_API_NO_POST
    ),
    runtime_request: LiveOrderRealStep6GRuntimeBridgeRequest | None = None,
    created_at: datetime | None = None,
) -> LiveOrderRealStep6GRuntimeBridgeResult:
    """Run the fake-only runtime bridge without real API or POST execution."""
    request = runtime_request or make_live_order_real_step6g_runtime_bridge_request(
        step6g_post_route_bridge_result=step6g_post_route_bridge_result,
        fake_attempt_count=1,
    )
    fake_executor_result = LiveOrderRealStep6GFakePostExecutorResult(
        fake_post_attempted=True,
        fake_post_result_category=fake_post_result_category,
        fake_attempt_count=request.fake_attempt_count,
        fake_retry_count=0,
        fake_loop_count=0,
    )
    return build_live_order_real_step6g_runtime_bridge(
        step6g_post_route_bridge_result=step6g_post_route_bridge_result,
        runtime_request=request,
        fake_executor_result=fake_executor_result,
        created_at=created_at,
    )


def make_live_order_real_step6g_runtime_bridge_request(
    *,
    step6g_post_route_bridge_result: LiveOrderRealStep6GPostRouteBridgeResult,
    fake_attempt_count: int = 0,
) -> LiveOrderRealStep6GRuntimeBridgeRequest:
    """Convert a Step 6G PB result into a sanitized fake runtime request."""
    bridge = step6g_post_route_bridge_result
    approval = bridge.approval_snapshot
    preflight = bridge.preflight_snapshot
    attempt = bridge.attempt_state
    route = bridge.route_contract_snapshot
    return LiveOrderRealStep6GRuntimeBridgeRequest(
        source_bridge_id=bridge.bridge_id,
        source_bridge_status=bridge.status.value,
        execution_mode=RuntimeExecutionMode.FAKE_ONLY_NO_API_NO_POST,
        step6g_post_route_bridge_ready=bridge.bridge_ready,
        step6g_post_route_bridge_status=bridge.status.value,
        order_intent_exact_match=bridge.bridge_ready,
        approval_artifact_reestablished=approval.approval_artifact_reestablished,
        approval_validation_passed=approval.approval_validation_passed,
        approval_exact_match=approval.approval_exact_match_ready,
        approval_fingerprint_present=bool(
            approval.approval_command_fingerprint and approval.approval_sha256_prefix,
        ),
        final_confirmation_exact_match=(
            approval.step6g_final_confirmation_received
            and approval.step6g_final_confirmation_exact_match
        ),
        final_confirmation_reused=approval.final_confirmation_phrase_reused,
        final_confirmation_preflight_passed=preflight.final_confirmation_preflight_passed,
        post_immediate_preflight_passed=preflight.post_immediate_preflight_passed,
        post_attempt_limit=attempt.post_attempt_limit,
        post_attempt_count_before=attempt.post_attempt_count_before,
        fake_attempt_count=fake_attempt_count,
        post_allowed_this_step=bridge.post_allowed_this_step,
        post_executed=bridge.post_executed,
        allowed_for_live=bridge.allowed_for_live,
        allowed_for_live_persisted=attempt.allowed_for_live_persisted,
        retry_allowed=attempt.retry_allowed,
        loop_allowed=attempt.loop_allowed,
        add_order_allowed=attempt.add_order_allowed,
        change_order_allowed=attempt.change_order_allowed,
        cancel_order_allowed=attempt.cancel_order_allowed,
        close_order_allowed=attempt.close_order_allowed,
        raw_secret_id_exposure=_source_has_raw_or_secret_exposure(bridge),
        route_unsafe=_source_route_is_unsafe(bridge),
        step4_spoofing=_source_has_step4_spoofing(bridge),
        real_http_post_executed=route.http_post_executed,
        order_endpoint_called=bridge.order_endpoint_called or route.order_endpoint_called,
        live_order_once_called=bridge.live_order_once_called
        or route.calls_live_order_once_directly,
        broker_order_path_called=route.imports_broker,
    )


def render_live_order_real_step6g_runtime_bridge_markdown(
    result: LiveOrderRealStep6GRuntimeBridgeResult,
) -> str:
    """Render a sanitized fake runtime bridge report."""
    lines = [
        "# Step 6G Runtime Bridge Fake Executor",
        "",
        "This runtime bridge is fake only.",
        "This runtime bridge does not execute API calls.",
        "This runtime bridge does not execute HTTP POST.",
        "This runtime bridge does not call order endpoint.",
        "This runtime bridge does not call live_order_once.",
        "This runtime bridge does not reuse old final confirmation.",
        "Future real Step 6G execution requires a new final confirmation and fresh preflight.",
        "",
        "## Summary",
        f"- status: {result.status.value}",
        f"- fake_runtime_ready: {_bool_text(result.fake_runtime_ready)}",
        f"- fake_post_attempted: {_bool_text(result.fake_post_attempted)}",
        f"- fake_post_result_category: {result.fake_post_result_category}",
        f"- real_http_post_executed: {_bool_text(result.real_http_post_executed)}",
        f"- order_endpoint_called: {_bool_text(result.order_endpoint_called)}",
        f"- live_order_once_called: {_bool_text(result.live_order_once_called)}",
        f"- allowed_for_live: {_bool_text(result.allowed_for_live)}",
        f"- post_allowed_this_step: {_bool_text(result.post_allowed_this_step)}",
        f"- post_executed: {_bool_text(result.post_executed)}",
        f"- post_attempt_limit: {result.post_attempt_limit}",
        f"- fake_attempt_count: {result.fake_attempt_count}",
        "",
        "## Source Bridge",
        f"- source_bridge_id: {result.request.source_bridge_id}",
        f"- source_bridge_status: {result.request.source_bridge_status}",
        (
            "- step6g_post_route_bridge_ready: "
            f"{_bool_text(result.request.step6g_post_route_bridge_ready)}"
        ),
        "",
        "## Runtime Safety",
        (
            "- final_confirmation_exact_match: "
            f"{_bool_text(result.request.final_confirmation_exact_match)}"
        ),
        f"- final_confirmation_reused: {_bool_text(result.request.final_confirmation_reused)}",
        f"- approval_exact_match: {_bool_text(result.request.approval_exact_match)}",
        (
            "- final_confirmation_preflight_passed: "
            f"{_bool_text(result.request.final_confirmation_preflight_passed)}"
        ),
        (
            "- post_immediate_preflight_passed: "
            f"{_bool_text(result.request.post_immediate_preflight_passed)}"
        ),
        f"- retry_allowed: {_bool_text(result.request.retry_allowed)}",
        f"- loop_allowed: {_bool_text(result.request.loop_allowed)}",
        (
            "- add/change/cancel/close allowed: "
            f"{_bool_text(_any_order_mutation_allowed(result.request))}"
        ),
        "",
        "## Blocked Reasons",
        *[f"- {reason}" for reason in result.blocked_reasons],
        "",
        "## Check Results",
        *[
            (
                f"- {check.name}: {_bool_text(check.passed)} "
                f"({check.sanitized_value}; expected {check.expected})"
            )
            for check in result.check_results
        ],
        "",
        "## Recommended Next Step",
        f"- {result.recommended_next_step}",
    ]
    return "\n".join(lines) + "\n"


def make_live_order_real_step6g_runtime_bridge_id(created_at: datetime) -> str:
    created = _ensure_aware(created_at)
    return f"{LIVE_ORDER_REAL_STEP6G_RUNTIME_BRIDGE_ID_PREFIX}{created.strftime('%Y%m%dT%H%M%SZ')}"


def _not_ready_reasons(
    bridge: LiveOrderRealStep6GPostRouteBridgeResult,
    request: LiveOrderRealStep6GRuntimeBridgeRequest,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not bridge.bridge_ready:
        reasons.append("source_bridge_not_ready")
    if bridge.status is not BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST:
        reasons.append("source_bridge_status_not_ready")
    if not request.step6g_post_route_bridge_ready:
        reasons.append("runtime_request_bridge_not_ready")
    if (
        request.step6g_post_route_bridge_status
        != BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
    ):
        reasons.append("runtime_request_bridge_status_not_ready")
    if request.source_bridge_status != bridge.status.value:
        reasons.append("source_bridge_status_mismatch")
    return tuple(reasons)


def _approval_reasons(request: LiveOrderRealStep6GRuntimeBridgeRequest) -> tuple[str, ...]:
    reasons: list[str] = []
    if not request.final_confirmation_exact_match:
        reasons.append("final_confirmation_exact_match_missing")
    if request.final_confirmation_reused:
        reasons.append("final_confirmation_reused")
    if not request.approval_artifact_reestablished:
        reasons.append("approval_artifact_reestablished_missing")
    if not request.approval_validation_passed:
        reasons.append("approval_validation_passed_missing")
    if not request.approval_exact_match:
        reasons.append("approval_exact_match_missing")
    if not request.approval_fingerprint_present:
        reasons.append("approval_fingerprint_missing")
    return tuple(reasons)


def _preflight_reasons(request: LiveOrderRealStep6GRuntimeBridgeRequest) -> tuple[str, ...]:
    reasons: list[str] = []
    if not request.final_confirmation_preflight_passed:
        reasons.append("final_confirmation_preflight_missing")
    if not request.post_immediate_preflight_passed:
        reasons.append("post_immediate_preflight_missing")
    return tuple(reasons)


def _attempt_state_reasons(
    request: LiveOrderRealStep6GRuntimeBridgeRequest,
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.post_attempt_limit != 1:
        reasons.append("post_attempt_limit_not_one")
    if request.post_attempt_count_before != 0:
        reasons.append("post_attempt_count_before_not_zero")
    if request.fake_attempt_count > 1:
        reasons.append("fake_attempt_count_exceeds_one")
    if request.post_executed:
        reasons.append("post_executed_unsafe")
    if request.post_allowed_this_step:
        reasons.append("post_allowed_this_step_unsafe_for_fake_model")
    if request.allowed_for_live:
        reasons.append("allowed_for_live_unsafe")
    if request.allowed_for_live_persisted:
        reasons.append("allowed_for_live_persisted_unsafe")
    if fake_executor_result and fake_executor_result.fake_attempt_count > 1:
        reasons.append("fake_executor_attempt_count_exceeds_one")
    return tuple(reasons)


def _retry_or_loop_reasons(
    request: LiveOrderRealStep6GRuntimeBridgeRequest,
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for field_name in (
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(request, field_name):
            reasons.append(f"{field_name}_unsafe")
    if fake_executor_result:
        if fake_executor_result.fake_retry_count:
            reasons.append("fake_retry_count_non_zero")
        if fake_executor_result.fake_loop_count:
            reasons.append("fake_loop_count_non_zero")
    return tuple(reasons)


def _route_unsafe_reasons(
    request: LiveOrderRealStep6GRuntimeBridgeRequest,
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.route_unsafe:
        reasons.append("route_unsafe")
    if request.step4_spoofing:
        reasons.append("step4_spoofing")
    for field_name in (
        "real_http_post_executed",
        "order_endpoint_called",
        "live_order_once_called",
        "broker_order_path_called",
    ):
        if getattr(request, field_name):
            reasons.append(f"{field_name}_unsafe")
    if fake_executor_result:
        for field_name in (
            "real_http_post_executed",
            "order_endpoint_called",
            "live_order_once_called",
            "broker_order_path_called",
        ):
            if getattr(fake_executor_result, field_name):
                reasons.append(f"fake_executor_{field_name}_unsafe")
    return tuple(reasons)


def _raw_or_secret_exposure_reasons(
    request: LiveOrderRealStep6GRuntimeBridgeRequest,
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if request.raw_secret_id_exposure:
        reasons.append("raw_secret_id_exposure")
    if fake_executor_result:
        for field_name in (
            "raw_request_present",
            "raw_response_present",
            "headers_present",
            "signature_present",
            "credentials_present",
            "real_order_id_present",
            "real_execution_id_present",
            "real_position_id_present",
            "real_client_order_id_present",
        ):
            if getattr(fake_executor_result, field_name):
                reasons.append(f"fake_executor_{field_name}_unsafe")
        if not fake_executor_result.result_is_fake:
            reasons.append("fake_executor_result_not_fake")
    return tuple(reasons)


def _unsupported_reasons(request: LiveOrderRealStep6GRuntimeBridgeRequest) -> tuple[str, ...]:
    if request.execution_mode is RuntimeExecutionMode.FAKE_ONLY_NO_API_NO_POST:
        return ()
    return ("unsupported_runtime_execution_mode",)


def _source_has_step4_spoofing(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    approval = bridge.approval_snapshot
    route = bridge.route_contract_snapshot
    return (
        approval.step4_approval_phrase_used
        or approval.step4_approval_phrase_spoofed
        or approval.step4_approval_gate_reused_as_step6g
        or route.uses_step4_approval_phrase
        or route.spoofs_step4_approval_phrase
        or route.mutates_step4_ledger_state
    )


def _source_route_is_unsafe(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    route = bridge.route_contract_snapshot
    return (
        route.requires_step4_prepared_ledger
        or route.calls_live_order_once_directly
        or route.imports_live_order_once
        or route.imports_broker
        or route.imports_private_api
        or route.creates_new_order_endpoint
        or route.creates_new_payload_builder
        or route.order_endpoint_called
        or route.order_payload_generated
        or route.order_payload_sent
        or route.http_post_executed
        or route.retry_on_unknown
        or route.retry_on_timeout
        or route.retry_on_reject
    )


def _source_has_raw_or_secret_exposure(bridge: LiveOrderRealStep6GPostRouteBridgeResult) -> bool:
    approval = bridge.approval_snapshot
    preflight = bridge.preflight_snapshot
    route = bridge.route_contract_snapshot
    return (
        approval.approval_command_displayed
        or approval.approval_command_saved
        or approval.approval_command_copyable
        or approval.approval_command_pbcopy
        or approval.approval_command_full_text_present
        or preflight.raw_request_saved
        or preflight.raw_request_displayed
        or preflight.raw_response_saved
        or preflight.raw_response_displayed
        or preflight.headers_saved
        or preflight.headers_displayed
        or preflight.signature_saved
        or preflight.signature_displayed
        or preflight.credentials_displayed
        or preflight.order_ids_displayed
        or preflight.execution_ids_displayed
        or preflight.position_ids_displayed
        or preflight.client_order_ids_displayed
        or route.raw_request_displayed
        or route.raw_response_displayed
        or route.headers_displayed
        or route.signature_displayed
        or route.credentials_displayed
        or route.real_ids_displayed
    )


def _build_check_results(
    *,
    bridge: LiveOrderRealStep6GPostRouteBridgeResult,
    request: LiveOrderRealStep6GRuntimeBridgeRequest,
    fake_executor_result: LiveOrderRealStep6GFakePostExecutorResult | None,
) -> tuple[LiveOrderRealStep6GRuntimeBridgeCheckResult, ...]:
    checks: list[LiveOrderRealStep6GRuntimeBridgeCheckResult] = []

    def add(name: str, passed: bool, value: object, expected: str) -> None:
        checks.append(
            LiveOrderRealStep6GRuntimeBridgeCheckResult(
                name=name,
                passed=passed,
                reason="passed" if passed else "blocked",
                sanitized_value=_safe_value(value),
                expected=expected,
            ),
        )

    add(
        "source bridge ready",
        bridge.bridge_ready
        and bridge.status is BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST,
        request.step6g_post_route_bridge_status,
        BridgeStatus.STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST.value,
    )
    add(
        "final confirmation exact and not reused",
        request.final_confirmation_exact_match and not request.final_confirmation_reused,
        {
            "exact": request.final_confirmation_exact_match,
            "reused": request.final_confirmation_reused,
        },
        "exact=true reused=false",
    )
    add(
        "approval exact match",
        request.approval_artifact_reestablished
        and request.approval_validation_passed
        and request.approval_exact_match
        and request.approval_fingerprint_present,
        "present" if request.approval_fingerprint_present else "missing",
        "present",
    )
    add(
        "both preflights passed",
        request.final_confirmation_preflight_passed and request.post_immediate_preflight_passed,
        {
            "final": request.final_confirmation_preflight_passed,
            "post_immediate": request.post_immediate_preflight_passed,
        },
        "both true",
    )
    add(
        "attempt state one shot",
        request.post_attempt_limit == 1
        and request.post_attempt_count_before == 0
        and request.fake_attempt_count <= 1,
        {
            "limit": request.post_attempt_limit,
            "before": request.post_attempt_count_before,
            "fake": request.fake_attempt_count,
        },
        "limit=1 before=0 fake<=1",
    )
    add(
        "fake result has no retry or loop",
        not _retry_or_loop_reasons(request, fake_executor_result),
        "none" if not _retry_or_loop_reasons(request, fake_executor_result) else "unsafe",
        "none",
    )
    add(
        "route stays fake-only",
        not _route_unsafe_reasons(request, fake_executor_result),
        "none" if not _route_unsafe_reasons(request, fake_executor_result) else "unsafe",
        "none",
    )
    add(
        "no raw secret real ID exposure",
        not _raw_or_secret_exposure_reasons(request, fake_executor_result),
        "none" if not _raw_or_secret_exposure_reasons(request, fake_executor_result) else "unsafe",
        "none",
    )
    add(
        "real execution flags stay false",
        not (
            request.real_http_post_executed
            or request.order_endpoint_called
            or request.live_order_once_called
            or request.broker_order_path_called
        ),
        "false",
        "false",
    )
    add(
        "fake executor result is fake",
        fake_executor_result is None
        or (fake_executor_result.fake_post_attempted and fake_executor_result.result_is_fake),
        "fake" if fake_executor_result else "not_run",
        "fake or not_run",
    )
    return tuple(checks)


def _any_order_mutation_allowed(request: LiveOrderRealStep6GRuntimeBridgeRequest) -> bool:
    return (
        request.add_order_allowed
        or request.change_order_allowed
        or request.cancel_order_allowed
        or request.close_order_allowed
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{field_name} must be non-empty str")


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime value must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime value must be timezone-aware")
    return value.astimezone(UTC)


def _validate_non_negative_int(field_name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise LiveVerificationValidationError(f"{field_name} must be non-negative int")


def _validate_bool_fields(obj: object, field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if type(getattr(obj, field_name)) is not bool:
            raise LiveVerificationValidationError(f"{field_name} must be bool")


def _safe_value(value: object) -> str:
    if isinstance(value, bool):
        return _bool_text(value)
    if isinstance(value, int | float | str):
        return str(value)
    if isinstance(value, dict):
        return ",".join(f"{key}={_safe_value(item)}" for key, item in sorted(value.items()))
    return value.__class__.__name__


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
