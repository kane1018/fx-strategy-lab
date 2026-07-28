import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.services.h11_v4_unattended_exit_recovery_no_post import (
    V4ExitRecoverySnapshot,
)
from app.services.h11_v4_unattended_restart_safe_exit_no_post import (
    V4FakePositionSpecificExitResult,
    V4RestartSafeExitStatus,
    V4RestartSafeExitStore,
)


def _due_snapshot(**overrides: bool | datetime | str) -> V4ExitRecoverySnapshot:
    values = {
        "reviewed_files_digest_matches": True,
        "generation_digest_matches": True,
        "cycle_binding_digest": "sha256:" + ("a" * 64),
        "expected_cycle_binding_digest": "sha256:" + ("a" * 64),
        "exact_protection_confirmed": True,
        "flat_reconciled": False,
        "transport_action_pending": False,
        "result_unknown": False,
        "persistent_operator_halt": False,
        "process_lock_available": True,
        "scheduled_exit_at_utc": datetime(2026, 7, 28, 1, 30, tzinfo=UTC),
        "previous_observed_at_utc": datetime(2026, 7, 28, 1, 29, 30, tzinfo=UTC),
        "observed_at_utc": datetime(2026, 7, 28, 1, 30, tzinfo=UTC),
        "time_exit_marker_claimed": False,
    }
    values.update(overrides)
    return V4ExitRecoverySnapshot(**values)


def _known_flat() -> V4FakePositionSpecificExitResult:
    return V4FakePositionSpecificExitResult(
        fake_only=True,
        result_known=True,
        flat_reconciled=True,
    )


def _binding() -> dict[str, str]:
    return {
        "reviewed_files_digest": "sha256:" + ("b" * 64),
        "generation_digest": "sha256:" + ("c" * 64),
    }


def test_fake_exit_is_claimed_once_and_completed_without_post(tmp_path: Path) -> None:
    store = V4RestartSafeExitStore(tmp_path / "exit.sqlite3")
    first = store.run_once(
        snapshot=_due_snapshot(), fake_result=_known_flat(), **_binding()
    )
    second = store.run_once(
        snapshot=_due_snapshot(), fake_result=_known_flat(), **_binding()
    )

    assert first.status is V4RestartSafeExitStatus.FAKE_EXIT_COMPLETED_NO_POST
    assert first.persistent_halt is False
    assert first.broker_write is False
    assert first.actual_post_count == 0
    assert first.fake_outcome_applied is True
    assert second.status is V4RestartSafeExitStatus.COMPLETE_FLAT_NO_WRITE
    assert (
        store.scope_status(cycle_binding_digest=_due_snapshot().cycle_binding_digest)
        == "COMPLETE"
    )


def test_restart_after_claim_halts_without_a_second_fake_exit(tmp_path: Path) -> None:
    database = tmp_path / "exit.sqlite3"
    store = V4RestartSafeExitStore(database)
    cycle = _due_snapshot().cycle_binding_digest
    assert store._claim_once(cycle, **_binding()) is True
    restarted = V4RestartSafeExitStore(database)
    result = restarted.run_once(
        snapshot=_due_snapshot(), fake_result=_known_flat(), **_binding()
    )

    assert result.status is V4RestartSafeExitStatus.PERSISTENT_HALT_NO_RETRY
    assert result.persistent_halt is True
    assert result.fake_outcome_applied is False
    assert restarted.scope_status(cycle_binding_digest=cycle) == "HALTED"


def test_unknown_or_write_capable_fake_result_halts_without_repost(tmp_path: Path) -> None:
    for result in (
        V4FakePositionSpecificExitResult(
            fake_only=True,
            result_known=False,
            flat_reconciled=False,
        ),
        V4FakePositionSpecificExitResult(
            fake_only=True,
            result_known=True,
            flat_reconciled=True,
            broker_write=True,
        ),
    ):
        database = tmp_path / f"{result.result_known}-{result.broker_write}.sqlite3"
        store = V4RestartSafeExitStore(database)
        decision = store.run_once(
            snapshot=_due_snapshot(), fake_result=result, **_binding()
        )

        assert decision.status is V4RestartSafeExitStatus.PERSISTENT_HALT_NO_RETRY
        assert decision.fake_outcome_applied is False


def test_pre_deadline_and_already_flat_never_apply_fake_outcome(tmp_path: Path) -> None:
    store = V4RestartSafeExitStore(tmp_path / "exit.sqlite3")

    monitoring = store.run_once(
        snapshot=_due_snapshot(
            observed_at_utc=datetime(2026, 7, 28, 1, 29, 59, tzinfo=UTC)
        ),
        fake_result=_known_flat(),
        **_binding(),
    )
    flat = store.run_once(
        snapshot=_due_snapshot(flat_reconciled=True),
        fake_result=_known_flat(),
        **_binding(),
    )

    assert monitoring.status is V4RestartSafeExitStatus.MONITORING_NO_WRITE
    assert flat.status is V4RestartSafeExitStatus.COMPLETE_FLAT_NO_WRITE
    assert monitoring.fake_outcome_applied is False
    assert flat.fake_outcome_applied is False


def test_non_fake_outcome_is_persistently_halted(tmp_path: Path) -> None:
    store = V4RestartSafeExitStore(tmp_path / "exit.sqlite3")
    result = store.run_once(
        snapshot=_due_snapshot(),
        fake_result=V4FakePositionSpecificExitResult(
            fake_only=False, result_known=True, flat_reconciled=True
        ),
        **_binding(),
    )

    assert result.status is V4RestartSafeExitStatus.PERSISTENT_HALT_NO_RETRY
    assert (
        store.scope_status(cycle_binding_digest=_due_snapshot().cycle_binding_digest)
        == "HALTED"
    )


def test_claimed_scope_cannot_be_bypassed_by_later_flat_snapshot(tmp_path: Path) -> None:
    store = V4RestartSafeExitStore(tmp_path / "exit.sqlite3")
    cycle = _due_snapshot().cycle_binding_digest
    assert store._claim_once(cycle, **_binding()) is True

    result = store.run_once(
        snapshot=_due_snapshot(flat_reconciled=True),
        fake_result=_known_flat(),
        **_binding(),
    )

    assert result.status is V4RestartSafeExitStatus.PERSISTENT_HALT_NO_RETRY
    assert store.scope_status(cycle_binding_digest=cycle) == "HALTED"


def test_storage_failure_applies_no_fake_outcome(tmp_path: Path, monkeypatch) -> None:
    store = V4RestartSafeExitStore(tmp_path / "exit.sqlite3")

    def _unavailable(_: str) -> None:
        raise sqlite3.OperationalError("fixture")

    monkeypatch.setattr(store, "_scope", _unavailable)
    result = store.run_once(
        snapshot=_due_snapshot(), fake_result=_known_flat(), **_binding()
    )

    assert result.status is V4RestartSafeExitStatus.STORAGE_UNAVAILABLE_NO_POST
    assert result.persistent_halt is False
    assert result.fake_outcome_applied is False


def test_initialization_failure_reports_storage_unavailable_without_outcome(
    tmp_path: Path,
) -> None:
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("fixture", encoding="utf-8")
    store = V4RestartSafeExitStore(parent_file / "exit.sqlite3")

    result = store.run_once(
        snapshot=_due_snapshot(), fake_result=_known_flat(), **_binding()
    )

    assert result.status is V4RestartSafeExitStatus.STORAGE_UNAVAILABLE_NO_POST
    assert result.fake_outcome_applied is False
