from __future__ import annotations

from app.h11_auto.v4_gmo_soak import (
    MINIMUM_V4_GMO_SOAK_CYCLES,
    V4GmoSoakStatus,
    build_v4_gmo_soak_scenarios,
    run_v4_gmo_fault_soak_no_post,
)


def test_v4_gmo_fault_matrix_covers_core_relaxed_profile_failures() -> None:
    names = {scenario.name for scenario in build_v4_gmo_soak_scenarios()}
    assert {
        "FULL_FILL_PROTECTED",
        "PARTIAL_REMAINDER_CANCEL_THEN_PROTECT",
        "ENTRY_RECONCILIATION_UNKNOWN_HALT",
        "PROTECTION_MISSING_EMERGENCY_FLAT",
        "UNDERSIZED_PROTECTION_CANCEL_THEN_EMERGENCY_FLAT",
        "EMERGENCY_RESULT_UNKNOWN_HALT",
        "ORPHAN_PROTECTION_CANCELLED_FLAT",
    }.issubset(names)


def test_v4_gmo_fault_soak_passes_100_cycles_without_retry_or_post() -> None:
    report = run_v4_gmo_fault_soak_no_post(
        target_cycle_count=MINIMUM_V4_GMO_SOAK_CYCLES
    )
    assert report.status is V4GmoSoakStatus.PASSED_SYNTHETIC_NO_POST
    assert report.synthetic_cycle_count == 100
    assert report.matched_cycle_count == 100
    assert report.mismatched_scenarios == ()
    assert report.max_same_action_attempts_observed == 1
    assert report.one_attempt_per_action_invariant_ok is True
    assert report.journal_verification_failures == 0
    assert report.actual_post_count == 0
    assert report.broker_write_performed is False
    assert report.credential_read_performed is False
    assert report.network_access_performed is False
    assert report.live_ready is False
    assert report.unattended_live_supported is False


def test_v4_gmo_fault_soak_refuses_small_target() -> None:
    report = run_v4_gmo_fault_soak_no_post(target_cycle_count=99)
    assert report.status is V4GmoSoakStatus.BLOCKED_TARGET_TOO_SMALL
    assert report.synthetic_cycle_count == 0
    assert report.actual_post_count == 0
