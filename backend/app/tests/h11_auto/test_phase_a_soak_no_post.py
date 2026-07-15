from __future__ import annotations

import inspect

from app.h11_auto.soak import (
    MINIMUM_PHASE_A_SOAK_CYCLES,
    PhaseASoakStatus,
    build_phase_a_soak_scenarios,
    run_phase_a_fault_soak_no_post,
)


def test_fault_matrix_covers_required_phase_a_failures() -> None:
    names = {scenario.name for scenario in build_phase_a_soak_scenarios()}
    assert {
        "SUCCESS_FLAT",
        "ENTRY_UNKNOWN",
        "ENTRY_TIMEOUT",
        "PARTIAL_MISMATCH",
        "EXIT_UNKNOWN",
        "EXIT_TIMEOUT",
        "EXTERNAL_POSITION_BLOCK",
        "ACTIVE_ORDER_CONFLICT",
        "STALE_DATA_BLOCK",
        "STAY_NO_ACTION",
        "NOTIFICATION_FAILURE",
    } <= names


def test_bounded_phase_a_soak_passes_without_post_network_or_credentials() -> None:
    report = run_phase_a_fault_soak_no_post(
        target_cycle_count=MINIMUM_PHASE_A_SOAK_CYCLES
    )
    assert report.status is PhaseASoakStatus.PASSED_SYNTHETIC_NO_POST
    assert report.synthetic_cycle_count == 100
    assert report.matched_cycle_count == 100
    assert report.mismatched_scenarios == ()
    assert report.max_entry_attempts_observed == 1
    assert report.max_exit_attempts_observed == 1
    assert report.duplicate_attempt_invariant_ok is True
    assert report.no_retry_invariant_ok is True
    assert report.journal_verification_failures == 0
    assert report.actual_post_count == 0
    assert report.broker_write_performed is False
    assert report.network_access_performed is False
    assert report.credential_read_performed is False
    assert report.raw_id_value_exposure is False
    assert report.actual_activation_ready is False


def test_too_small_soak_is_refused_and_module_has_no_sleep_or_external_client() -> None:
    report = run_phase_a_fault_soak_no_post(target_cycle_count=99)
    assert report.status is PhaseASoakStatus.BLOCKED_TARGET_TOO_SMALL
    source = inspect.getsource(__import__("app.h11_auto.soak", fromlist=["*"]))
    for marker in ("time.sleep", "httpx", "requests", "app.private_api", "os.environ"):
        assert marker not in source
