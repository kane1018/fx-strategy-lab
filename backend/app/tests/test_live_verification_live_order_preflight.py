from __future__ import annotations

from dataclasses import asdict, fields

import pytest

from app.live_verification.errors import LiveVerificationLiveOrderPreflightError
from app.live_verification.live_order_preflight import (
    NO_GO,
    READY_FOR_STEP4_PROMPT,
    LiveOrderPreflightDecision,
    LiveOrderPreflightSnapshot,
    evaluate_live_order_preflight,
    make_live_order_preflight_decision_id,
    make_live_order_preflight_snapshot_id,
)

EXPECTED_SNAPSHOT_FIELDS = {
    "preflight_snapshot_id",
    "api_key_present",
    "api_secret_present",
    "readonly_assets_check_passed",
    "readonly_open_positions_check_passed",
    "readonly_active_orders_check_passed",
    "open_positions_count",
    "active_orders_count",
    "previous_result_known",
    "result_unknown",
    "step2_skeleton_passed",
    "mock_submission_passed",
    "tests_passed",
    "ruff_passed",
    "git_clean",
    "market_window_allowed",
    "maintenance_active",
    "important_event_window_active",
    "initial_live_order_only",
    "manual_approval_required",
    "manual_approval_present_for_execution",
    "max_daily_attempts",
    "session_attempt_count",
    "daily_attempt_count",
    "retry_enabled",
    "loop_enabled",
    "kill_switch_active",
    "safety_violation_detected",
    "http_post_enabled",
    "real_order_attempted",
}
EXPECTED_DECISION_FIELDS = {
    "preflight_decision_id",
    "preflight_status",
    "preflight_passed",
    "ready_for_step4_prompt",
    "live_order_allowed_now",
    "requires_separate_user_approval",
    "no_go_reasons",
}
BLOCKED_PUBLIC_FIELDS = {
    "api_key",
    "api_secret",
    "secret",
    "token",
    "credential",
    "credentials",
    "authorization",
    "headers",
    "actual_headers",
    "header_values",
    "signature",
    "actual_signature",
    "signature_value",
    "api_sign",
    "hmac_digest",
    "raw_headers",
    "raw_signature",
    "raw_request",
    "raw_response",
    "request_url",
    "url",
    "http_client",
    "response",
    "status_code",
    "response_body",
    "request_body",
    "request_headers",
    "account_balance",
    "account_assets",
    "open_positions",
    "active_orders",
    "position_detail",
    "order_detail",
}


def _snapshot_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "api_key_present": True,
        "api_secret_present": True,
        "readonly_assets_check_passed": True,
        "readonly_open_positions_check_passed": True,
        "readonly_active_orders_check_passed": True,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "previous_result_known": True,
        "result_unknown": False,
        "step2_skeleton_passed": True,
        "mock_submission_passed": True,
        "tests_passed": True,
        "ruff_passed": True,
        "git_clean": True,
        "market_window_allowed": True,
        "maintenance_active": False,
        "important_event_window_active": False,
        "initial_live_order_only": True,
        "manual_approval_required": True,
        "manual_approval_present_for_execution": False,
        "max_daily_attempts": 1,
        "session_attempt_count": 0,
        "daily_attempt_count": 0,
        "retry_enabled": False,
        "loop_enabled": False,
        "kill_switch_active": False,
        "safety_violation_detected": False,
        "http_post_enabled": False,
        "real_order_attempted": False,
    }
    values.update(overrides)
    return values


def _snapshot(**overrides: object) -> LiveOrderPreflightSnapshot:
    values = _snapshot_values(**overrides)
    return LiveOrderPreflightSnapshot(
        preflight_snapshot_id=make_live_order_preflight_snapshot_id(**values),
        **values,
    )


def test_live_order_preflight_passes_for_safe_snapshot() -> None:
    snapshot = _snapshot()

    decision = evaluate_live_order_preflight(snapshot)
    same = evaluate_live_order_preflight(snapshot)

    assert isinstance(decision, LiveOrderPreflightDecision)
    assert decision.preflight_decision_id == same.preflight_decision_id
    assert decision.preflight_decision_id == make_live_order_preflight_decision_id(
        snapshot
    )
    assert decision.preflight_status == READY_FOR_STEP4_PROMPT
    assert decision.preflight_passed is True
    assert decision.ready_for_step4_prompt is True
    assert decision.live_order_allowed_now is False
    assert decision.requires_separate_user_approval is True
    assert decision.no_go_reasons == ()
    assert snapshot.max_daily_attempts == 1
    assert snapshot.session_attempt_count == 0
    assert snapshot.daily_attempt_count == 0
    assert set(asdict(snapshot)) == EXPECTED_SNAPSHOT_FIELDS
    assert {field.name for field in fields(LiveOrderPreflightSnapshot)} == (
        EXPECTED_SNAPSHOT_FIELDS
    )
    assert set(asdict(decision)) == EXPECTED_DECISION_FIELDS
    assert {field.name for field in fields(LiveOrderPreflightDecision)} == (
        EXPECTED_DECISION_FIELDS
    )


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"api_key_present": False}, "api_key_present"),
        ({"api_secret_present": False}, "api_secret_present"),
        ({"readonly_assets_check_passed": False}, "readonly_assets_check_passed"),
        (
            {"readonly_open_positions_check_passed": False},
            "readonly_open_positions_check_passed",
        ),
        (
            {"readonly_active_orders_check_passed": False},
            "readonly_active_orders_check_passed",
        ),
        ({"open_positions_count": 1}, "open_positions_count"),
        ({"active_orders_count": 1}, "active_orders_count"),
        ({"previous_result_known": False}, "previous_result_known"),
        ({"result_unknown": True}, "result_unknown"),
        ({"step2_skeleton_passed": False}, "step2_skeleton_passed"),
        ({"mock_submission_passed": False}, "mock_submission_passed"),
        ({"tests_passed": False}, "tests_passed"),
        ({"ruff_passed": False}, "ruff_passed"),
        ({"git_clean": False}, "git_clean"),
        ({"market_window_allowed": False}, "market_window_allowed"),
        ({"maintenance_active": True}, "maintenance_active"),
        ({"important_event_window_active": True}, "important_event_window_active"),
        ({"initial_live_order_only": False}, "initial_live_order_only"),
        ({"manual_approval_required": False}, "manual_approval_required"),
        (
            {"manual_approval_present_for_execution": True},
            "manual_approval_present_for_execution",
        ),
        ({"max_daily_attempts": 2}, "max_daily_attempts"),
        ({"session_attempt_count": 1}, "session_attempt_count"),
        ({"daily_attempt_count": 1}, "daily_attempt_count"),
        ({"retry_enabled": True}, "retry_enabled"),
        ({"loop_enabled": True}, "loop_enabled"),
        ({"kill_switch_active": True}, "kill_switch_active"),
        ({"safety_violation_detected": True}, "safety_violation_detected"),
        ({"http_post_enabled": True}, "http_post_enabled"),
        ({"real_order_attempted": True}, "real_order_attempted"),
    ],
)
def test_live_order_preflight_fails_closed(
    overrides: dict[str, object],
    expected_reason: str,
) -> None:
    decision = evaluate_live_order_preflight(_snapshot(**overrides))

    assert decision.preflight_status == NO_GO
    assert decision.preflight_passed is False
    assert decision.ready_for_step4_prompt is False
    assert decision.live_order_allowed_now is False
    assert decision.requires_separate_user_approval is True
    assert expected_reason in decision.no_go_reasons


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    [
        ("open_positions_count", "open_positions_count_negative"),
        ("active_orders_count", "active_orders_count_negative"),
        ("max_daily_attempts", "max_daily_attempts_negative"),
        ("session_attempt_count", "session_attempt_count_negative"),
        ("daily_attempt_count", "daily_attempt_count_negative"),
    ],
)
def test_live_order_preflight_rejects_negative_counts(
    field_name: str,
    expected_reason: str,
) -> None:
    decision = evaluate_live_order_preflight(_snapshot(**{field_name: -1}))

    assert decision.preflight_passed is False
    assert expected_reason in decision.no_go_reasons


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    [
        ("open_positions_count", "open_positions_count_not_int"),
        ("active_orders_count", "active_orders_count_not_int"),
        ("max_daily_attempts", "max_daily_attempts_not_int"),
        ("session_attempt_count", "session_attempt_count_not_int"),
        ("daily_attempt_count", "daily_attempt_count_not_int"),
    ],
)
def test_live_order_preflight_rejects_bool_counts(
    field_name: str,
    expected_reason: str,
) -> None:
    decision = evaluate_live_order_preflight(_snapshot(**{field_name: False}))

    assert decision.preflight_passed is False
    assert expected_reason in decision.no_go_reasons


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    [
        ("open_positions_count", "open_positions_count_not_int"),
        ("active_orders_count", "active_orders_count_not_int"),
        ("max_daily_attempts", "max_daily_attempts_not_int"),
        ("session_attempt_count", "session_attempt_count_not_int"),
        ("daily_attempt_count", "daily_attempt_count_not_int"),
    ],
)
def test_live_order_preflight_rejects_non_int_counts(
    field_name: str,
    expected_reason: str,
) -> None:
    decision = evaluate_live_order_preflight(_snapshot(**{field_name: "0"}))

    assert decision.preflight_passed is False
    assert expected_reason in decision.no_go_reasons


@pytest.mark.parametrize(
    ("field_name", "expected_reason"),
    [
        ("api_key_present", "api_key_present_not_bool"),
        ("api_secret_present", "api_secret_present_not_bool"),
        ("readonly_assets_check_passed", "readonly_assets_check_passed_not_bool"),
        (
            "readonly_open_positions_check_passed",
            "readonly_open_positions_check_passed_not_bool",
        ),
        (
            "readonly_active_orders_check_passed",
            "readonly_active_orders_check_passed_not_bool",
        ),
        ("previous_result_known", "previous_result_known_not_bool"),
        ("result_unknown", "result_unknown_not_bool"),
        ("step2_skeleton_passed", "step2_skeleton_passed_not_bool"),
        ("mock_submission_passed", "mock_submission_passed_not_bool"),
        ("tests_passed", "tests_passed_not_bool"),
        ("ruff_passed", "ruff_passed_not_bool"),
        ("git_clean", "git_clean_not_bool"),
        ("market_window_allowed", "market_window_allowed_not_bool"),
        ("maintenance_active", "maintenance_active_not_bool"),
        (
            "important_event_window_active",
            "important_event_window_active_not_bool",
        ),
        ("initial_live_order_only", "initial_live_order_only_not_bool"),
        ("manual_approval_required", "manual_approval_required_not_bool"),
        (
            "manual_approval_present_for_execution",
            "manual_approval_present_for_execution_not_bool",
        ),
        ("retry_enabled", "retry_enabled_not_bool"),
        ("loop_enabled", "loop_enabled_not_bool"),
        ("kill_switch_active", "kill_switch_active_not_bool"),
        ("safety_violation_detected", "safety_violation_detected_not_bool"),
        ("http_post_enabled", "http_post_enabled_not_bool"),
        ("real_order_attempted", "real_order_attempted_not_bool"),
    ],
)
def test_live_order_preflight_rejects_non_bool_flags(
    field_name: str,
    expected_reason: str,
) -> None:
    decision = evaluate_live_order_preflight(_snapshot(**{field_name: "unsafe"}))

    assert decision.preflight_passed is False
    assert expected_reason in decision.no_go_reasons


def test_live_order_preflight_keeps_multiple_no_go_reasons() -> None:
    decision = evaluate_live_order_preflight(
        _snapshot(
            api_key_present=False,
            api_secret_present=False,
            readonly_assets_check_passed=False,
            open_positions_count=1,
            active_orders_count=1,
            result_unknown=True,
            tests_passed=False,
            ruff_passed=False,
            git_clean=False,
            manual_approval_present_for_execution=True,
            max_daily_attempts=2,
            session_attempt_count=1,
            daily_attempt_count=1,
            retry_enabled=True,
            loop_enabled=True,
            http_post_enabled=True,
            real_order_attempted=True,
        )
    )

    assert decision.preflight_passed is False
    assert set(decision.no_go_reasons) >= {
        "api_key_present",
        "api_secret_present",
        "readonly_assets_check_passed",
        "open_positions_count",
        "active_orders_count",
        "result_unknown",
        "tests_passed",
        "ruff_passed",
        "git_clean",
        "manual_approval_present_for_execution",
        "max_daily_attempts",
        "session_attempt_count",
        "daily_attempt_count",
        "retry_enabled",
        "loop_enabled",
        "http_post_enabled",
        "real_order_attempted",
    }


def test_live_order_preflight_public_views_do_not_leak_credentials_or_raw_data() -> None:
    snapshot = _snapshot()
    decision = evaluate_live_order_preflight(snapshot)
    forbidden_values = {
        "real_api_key_value_must_not_appear",
        "real_api_secret_value_must_not_appear",
        "real_signature_value_must_not_appear",
        "raw_account_assets_response",
        "raw_open_positions_response",
        "raw_active_orders_response",
        "https://forex-api.coin.z.com/private/v1/account/assets",
    }
    public_views = (
        repr(snapshot),
        str(snapshot),
        repr(asdict(snapshot)),
        str(asdict(snapshot)),
        repr(decision),
        str(decision),
        repr(asdict(decision)),
        str(asdict(decision)),
    )

    for view in public_views:
        assert all(value not in view for value in forbidden_values)
    assert set(asdict(snapshot)).isdisjoint(BLOCKED_PUBLIC_FIELDS)
    assert set(asdict(decision)).isdisjoint(BLOCKED_PUBLIC_FIELDS)
    assert all(not hasattr(snapshot, field_name) for field_name in BLOCKED_PUBLIC_FIELDS)
    assert all(not hasattr(decision, field_name) for field_name in BLOCKED_PUBLIC_FIELDS)


def test_live_order_preflight_requires_snapshot_input() -> None:
    with pytest.raises(LiveVerificationLiveOrderPreflightError):
        evaluate_live_order_preflight(object())  # type: ignore[arg-type]


def test_live_order_preflight_snapshot_requires_id() -> None:
    values = _snapshot_values()

    with pytest.raises(LiveVerificationLiveOrderPreflightError):
        LiveOrderPreflightSnapshot(preflight_snapshot_id="", **values)


def test_live_order_preflight_decision_cannot_allow_live_order_now() -> None:
    with pytest.raises(LiveVerificationLiveOrderPreflightError):
        LiveOrderPreflightDecision(
            preflight_decision_id="decision",
            preflight_status=READY_FOR_STEP4_PROMPT,
            preflight_passed=True,
            ready_for_step4_prompt=True,
            live_order_allowed_now=True,
            requires_separate_user_approval=True,
            no_go_reasons=(),
        )


def test_live_order_preflight_decision_requires_separate_step4_approval() -> None:
    with pytest.raises(LiveVerificationLiveOrderPreflightError):
        LiveOrderPreflightDecision(
            preflight_decision_id="decision",
            preflight_status=READY_FOR_STEP4_PROMPT,
            preflight_passed=True,
            ready_for_step4_prompt=True,
            live_order_allowed_now=False,
            requires_separate_user_approval=False,
            no_go_reasons=(),
        )
