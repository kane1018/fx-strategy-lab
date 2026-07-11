"""No-POST tests for the bounded H-11 v3 synthetic fault soak."""

from __future__ import annotations

import inspect

from app.services.h11_v3_fault_soak import (
    H11_V3_MIN_SYNTHETIC_SOAK_CYCLES,
    H11V3FaultSoakStatus,
    build_h11_v3_fault_scenarios,
    run_h11_v3_fault_soak_no_post,
)


def test_scenario_suite_covers_success_and_fail_closed_families() -> None:
    names = {scenario.name_safe_label for scenario in build_h11_v3_fault_scenarios()}
    assert {
        "SUCCESS_BROKER_OCO",
        "SUCCESS_DEDICATED_SETTLEMENT",
        "ENTRY_TIMEOUT",
        "ENTRY_NETWORK_ERROR",
        "PROTECTION_NOT_RECONCILED",
        "SETTLEMENT_UNKNOWN",
        "BOOT_RECONCILIATION_MISSING",
        "DEAD_MAN_MISSING",
        "NOTIFICATION_PATH_MISSING",
        "PENDING_EXPIRY_UNKNOWN",
        "SEALED_CREDENTIAL_BOUNDARY_MISSING",
    } <= names


def test_minimum_synthetic_fault_soak_passes_no_post() -> None:
    report = run_h11_v3_fault_soak_no_post()
    assert report.status is H11V3FaultSoakStatus.PASSED_SYNTHETIC_NO_POST
    assert report.synthetic_cycle_count == H11_V3_MIN_SYNTHETIC_SOAK_CYCLES
    assert report.matched_cycle_count == report.synthetic_cycle_count
    assert report.mismatched_scenarios == ()
    assert report.journal_verification_failures == 0
    assert report.notification_failures == 0
    assert report.max_entry_attempts_observed == 1
    assert report.max_settlement_attempts_observed == 1
    assert report.duplicate_attempt_invariant_ok is True
    assert report.no_retry_invariant_ok is True
    assert report.actual_post_count == 0
    assert report.broker_read_performed is False
    assert report.credential_env_read is False
    assert report.raw_id_value_exposure is False
    assert report.wall_clock_24h_soak_completed is False
    assert report.actual_activation_ready is False


def test_short_soak_is_blocked() -> None:
    report = run_h11_v3_fault_soak_no_post(target_cycle_count=99)
    assert report.status is H11V3FaultSoakStatus.BLOCKED_PLAN_INVALID
    assert report.synthetic_cycle_count == 0
    assert report.actual_post_count == 0


def test_soak_module_has_no_external_capability() -> None:
    import app.services.h11_v3_fault_soak as module

    source = inspect.getsource(module)
    for marker in (
        "httpx",
        "requests",
        "os.environ",
        "getenv",
        "load_dotenv",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "allow=True",
    ):
        assert marker not in source
