"""Independent Step 3 preflight audit before any live order approval."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.live_verification.errors import LiveVerificationLiveOrderPreflightError

READY_FOR_STEP4_PROMPT = "READY_FOR_STEP4_PROMPT"
NO_GO = "NO_GO"


@dataclass(frozen=True)
class LiveOrderPreflightSnapshot:
    preflight_snapshot_id: str
    api_key_present: bool
    api_secret_present: bool
    readonly_assets_check_passed: bool
    readonly_open_positions_check_passed: bool
    readonly_active_orders_check_passed: bool
    open_positions_count: int
    active_orders_count: int
    previous_result_known: bool
    result_unknown: bool
    step2_skeleton_passed: bool
    mock_submission_passed: bool
    tests_passed: bool
    ruff_passed: bool
    git_clean: bool
    market_window_allowed: bool
    maintenance_active: bool
    important_event_window_active: bool
    initial_live_order_only: bool
    manual_approval_required: bool
    manual_approval_present_for_execution: bool
    max_daily_attempts: int
    session_attempt_count: int
    daily_attempt_count: int
    retry_enabled: bool
    loop_enabled: bool
    kill_switch_active: bool
    safety_violation_detected: bool
    http_post_enabled: bool
    real_order_attempted: bool

    def __post_init__(self) -> None:
        if not _has_text(self.preflight_snapshot_id):
            raise LiveVerificationLiveOrderPreflightError(
                "preflight_snapshot_id is required"
            )


@dataclass(frozen=True)
class LiveOrderPreflightDecision:
    preflight_decision_id: str
    preflight_status: str
    preflight_passed: bool
    ready_for_step4_prompt: bool
    live_order_allowed_now: bool
    requires_separate_user_approval: bool
    no_go_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_preflight_decision(self)


def evaluate_live_order_preflight(
    snapshot: LiveOrderPreflightSnapshot,
) -> LiveOrderPreflightDecision:
    """Return a Step 3 Go/No-Go decision; never authorize a live order now."""
    if not isinstance(snapshot, LiveOrderPreflightSnapshot):
        raise LiveVerificationLiveOrderPreflightError(
            "live order preflight snapshot is required"
        )
    no_go_reasons = _dedupe_reasons(_snapshot_no_go_reasons(snapshot))
    preflight_passed = not no_go_reasons
    return LiveOrderPreflightDecision(
        preflight_decision_id=make_live_order_preflight_decision_id(snapshot),
        preflight_status=READY_FOR_STEP4_PROMPT if preflight_passed else NO_GO,
        preflight_passed=preflight_passed,
        ready_for_step4_prompt=preflight_passed,
        live_order_allowed_now=False,
        requires_separate_user_approval=True,
        no_go_reasons=no_go_reasons,
    )


def make_live_order_preflight_snapshot_id(
    *,
    api_key_present: bool,
    api_secret_present: bool,
    readonly_assets_check_passed: bool,
    readonly_open_positions_check_passed: bool,
    readonly_active_orders_check_passed: bool,
    open_positions_count: int,
    active_orders_count: int,
    previous_result_known: bool,
    result_unknown: bool,
    step2_skeleton_passed: bool,
    mock_submission_passed: bool,
    tests_passed: bool,
    ruff_passed: bool,
    git_clean: bool,
    market_window_allowed: bool,
    maintenance_active: bool,
    important_event_window_active: bool,
    initial_live_order_only: bool,
    manual_approval_required: bool,
    manual_approval_present_for_execution: bool,
    max_daily_attempts: int,
    session_attempt_count: int,
    daily_attempt_count: int,
    retry_enabled: bool,
    loop_enabled: bool,
    kill_switch_active: bool,
    safety_violation_detected: bool,
    http_post_enabled: bool,
    real_order_attempted: bool,
) -> str:
    digest = _short_hash({
        "active_orders_count": active_orders_count,
        "api_key_present": api_key_present,
        "api_secret_present": api_secret_present,
        "daily_attempt_count": daily_attempt_count,
        "git_clean": git_clean,
        "http_post_enabled": http_post_enabled,
        "important_event_window_active": important_event_window_active,
        "initial_live_order_only": initial_live_order_only,
        "kill_switch_active": kill_switch_active,
        "loop_enabled": loop_enabled,
        "maintenance_active": maintenance_active,
        "manual_approval_present_for_execution": manual_approval_present_for_execution,
        "manual_approval_required": manual_approval_required,
        "market_window_allowed": market_window_allowed,
        "max_daily_attempts": max_daily_attempts,
        "mock_submission_passed": mock_submission_passed,
        "open_positions_count": open_positions_count,
        "previous_result_known": previous_result_known,
        "readonly_active_orders_check_passed": readonly_active_orders_check_passed,
        "readonly_assets_check_passed": readonly_assets_check_passed,
        "readonly_open_positions_check_passed": readonly_open_positions_check_passed,
        "real_order_attempted": real_order_attempted,
        "result_unknown": result_unknown,
        "retry_enabled": retry_enabled,
        "ruff_passed": ruff_passed,
        "safety_violation_detected": safety_violation_detected,
        "session_attempt_count": session_attempt_count,
        "step2_skeleton_passed": step2_skeleton_passed,
        "tests_passed": tests_passed,
    })
    return f"live_order_preflight_{digest}"


def make_live_order_preflight_decision_id(
    snapshot: LiveOrderPreflightSnapshot,
) -> str:
    if not isinstance(snapshot, LiveOrderPreflightSnapshot):
        raise LiveVerificationLiveOrderPreflightError(
            "live order preflight snapshot is required"
        )
    digest = _short_hash({
        "preflight_snapshot_id": snapshot.preflight_snapshot_id,
        "no_go_reasons": _snapshot_no_go_reasons(snapshot),
    })
    return f"live_order_preflight_decision_{digest}"


def _snapshot_no_go_reasons(snapshot: LiveOrderPreflightSnapshot) -> tuple[str, ...]:
    reasons: list[str] = []
    reasons.extend(_bool_flag_reasons(snapshot))
    reasons.extend(_count_reasons(snapshot))
    return tuple(reasons)


def _bool_flag_reasons(snapshot: LiveOrderPreflightSnapshot) -> tuple[str, ...]:
    expected_true = {
        "api_key_present": snapshot.api_key_present,
        "api_secret_present": snapshot.api_secret_present,
        "readonly_assets_check_passed": snapshot.readonly_assets_check_passed,
        "readonly_open_positions_check_passed": (
            snapshot.readonly_open_positions_check_passed
        ),
        "readonly_active_orders_check_passed": (
            snapshot.readonly_active_orders_check_passed
        ),
        "previous_result_known": snapshot.previous_result_known,
        "step2_skeleton_passed": snapshot.step2_skeleton_passed,
        "mock_submission_passed": snapshot.mock_submission_passed,
        "tests_passed": snapshot.tests_passed,
        "ruff_passed": snapshot.ruff_passed,
        "git_clean": snapshot.git_clean,
        "market_window_allowed": snapshot.market_window_allowed,
        "initial_live_order_only": snapshot.initial_live_order_only,
        "manual_approval_required": snapshot.manual_approval_required,
    }
    expected_false = {
        "result_unknown": snapshot.result_unknown,
        "maintenance_active": snapshot.maintenance_active,
        "important_event_window_active": snapshot.important_event_window_active,
        "manual_approval_present_for_execution": (
            snapshot.manual_approval_present_for_execution
        ),
        "retry_enabled": snapshot.retry_enabled,
        "loop_enabled": snapshot.loop_enabled,
        "kill_switch_active": snapshot.kill_switch_active,
        "safety_violation_detected": snapshot.safety_violation_detected,
        "http_post_enabled": snapshot.http_post_enabled,
        "real_order_attempted": snapshot.real_order_attempted,
    }
    reasons: list[str] = []
    for name, value in expected_true.items():
        if not _is_bool(value):
            reasons.append(f"{name}_not_bool")
        elif not value:
            reasons.append(name)
    for name, value in expected_false.items():
        if not _is_bool(value):
            reasons.append(f"{name}_not_bool")
        elif value:
            reasons.append(name)
    return tuple(reasons)


def _count_reasons(snapshot: LiveOrderPreflightSnapshot) -> tuple[str, ...]:
    count_values = {
        "open_positions_count": snapshot.open_positions_count,
        "active_orders_count": snapshot.active_orders_count,
        "max_daily_attempts": snapshot.max_daily_attempts,
        "session_attempt_count": snapshot.session_attempt_count,
        "daily_attempt_count": snapshot.daily_attempt_count,
    }
    reasons: list[str] = []
    for name, value in count_values.items():
        if not _is_int_count(value):
            reasons.append(f"{name}_not_int")
            continue
        if value < 0:
            reasons.append(f"{name}_negative")
    if _is_int_count(snapshot.open_positions_count) and snapshot.open_positions_count > 0:
        reasons.append("open_positions_count")
    if _is_int_count(snapshot.active_orders_count) and snapshot.active_orders_count > 0:
        reasons.append("active_orders_count")
    if _is_int_count(snapshot.max_daily_attempts) and snapshot.max_daily_attempts != 1:
        reasons.append("max_daily_attempts")
    if (
        _is_int_count(snapshot.session_attempt_count)
        and snapshot.session_attempt_count != 0
    ):
        reasons.append("session_attempt_count")
    if _is_int_count(snapshot.daily_attempt_count) and snapshot.daily_attempt_count != 0:
        reasons.append("daily_attempt_count")
    return tuple(reasons)


def _validate_preflight_decision(decision: LiveOrderPreflightDecision) -> None:
    _require_non_empty("preflight_decision_id", decision.preflight_decision_id)
    if decision.preflight_status not in {READY_FOR_STEP4_PROMPT, NO_GO}:
        raise LiveVerificationLiveOrderPreflightError("preflight_status is invalid")
    _validate_bool_map({
        "preflight_passed": decision.preflight_passed,
        "ready_for_step4_prompt": decision.ready_for_step4_prompt,
        "live_order_allowed_now": decision.live_order_allowed_now,
        "requires_separate_user_approval": decision.requires_separate_user_approval,
    })
    if not isinstance(decision.no_go_reasons, tuple) or any(
        not isinstance(reason, str) or not reason for reason in decision.no_go_reasons
    ):
        raise LiveVerificationLiveOrderPreflightError(
            "no_go_reasons must be tuple[str, ...]"
        )
    if decision.live_order_allowed_now:
        raise LiveVerificationLiveOrderPreflightError(
            "Step 3 cannot allow live order execution now"
        )
    if not decision.requires_separate_user_approval:
        raise LiveVerificationLiveOrderPreflightError(
            "Step 4 requires separate user approval"
        )
    if decision.preflight_passed != decision.ready_for_step4_prompt:
        raise LiveVerificationLiveOrderPreflightError(
            "preflight and prompt readiness must match"
        )
    if decision.preflight_passed and decision.no_go_reasons:
        raise LiveVerificationLiveOrderPreflightError(
            "passed preflight cannot contain no-go reasons"
        )
    if not decision.preflight_passed and not decision.no_go_reasons:
        raise LiveVerificationLiveOrderPreflightError(
            "failed preflight requires no-go reasons"
        )
    if decision.preflight_passed and decision.preflight_status != READY_FOR_STEP4_PROMPT:
        raise LiveVerificationLiveOrderPreflightError("passed preflight status mismatch")
    if not decision.preflight_passed and decision.preflight_status != NO_GO:
        raise LiveVerificationLiveOrderPreflightError("failed preflight status mismatch")


def _validate_bool_map(flags: dict[str, bool]) -> None:
    for name, value in flags.items():
        if not _is_bool(value):
            raise LiveVerificationLiveOrderPreflightError(f"{name} must be bool")


def _require_non_empty(field_name: str, value: str) -> None:
    if not _has_text(value):
        raise LiveVerificationLiveOrderPreflightError(f"{field_name} is required")


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_bool(value: object) -> bool:
    return type(value) is bool


def _is_int_count(value: object) -> bool:
    return type(value) is int


def _dedupe_reasons(reasons: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(reason for reason in reasons if reason))


def _short_hash(data: dict[str, object]) -> str:
    canonical = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
