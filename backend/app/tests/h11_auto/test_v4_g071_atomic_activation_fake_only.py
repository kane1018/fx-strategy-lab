from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.services.h11_v4_g070_candidate import EffectiveState, ReconciliationState
from app.services.h11_v4_g071_atomic_activation import (
    G071_PERSISTENT_HALT_FILE,
    G071_TRANSACTION_OUTCOME_FILE,
    G071_TRANSACTION_STARTED_FILE,
    G071Error,
    G071ResidentSupervisor,
    G071SanitizedSnapshot,
    run_g071_atomic_activation_once,
)
from scripts.h11_auto_v4_g071_operation_60_no_post import run_g071_operation_60_candidate

DIGEST = "sha256:" + "1" * 64
REVIEWED = "sha256:" + "2" * 64
NOW = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)


class Reader:
    def __init__(self, snapshot: G071SanitizedSnapshot, events: list[str]) -> None:
        self.snapshot = snapshot
        self.events = events
        self.calls = 0

    def read_once(self) -> G071SanitizedSnapshot:
        self.events.append("read")
        self.calls += 1
        return self.snapshot

    def safe_attempt_counts(self) -> tuple[int, int, int]:
        return (3 if self.calls else 0, 3 if self.calls else 0, 1 if self.calls else 0)


class Arm:
    def __init__(self, events: list[str], result: bool = True) -> None:
        self.events = events
        self.result = result
        self.calls = 0

    def arm_once(self, **_kwargs) -> bool:
        self.events.append("arm")
        self.calls += 1
        return self.result


class Waiter:
    def __init__(self, events: list[str], result: bool = True) -> None:
        self.events = events
        self.result = result
        self.expected = None

    def wait_once(
        self,
        *,
        expected_effective_state: str,
        generation_digest: str,
        reviewed_files_digest: str,
        not_before_utc: datetime,
        timeout_seconds: float,
    ) -> bool:
        self.events.append("wait")
        self.expected = expected_effective_state
        assert generation_digest == DIGEST
        assert reviewed_files_digest == REVIEWED
        assert not_before_utc == NOW
        assert timeout_seconds > 0
        return self.result


def run(tmp_path, snapshot, *, arm_result=True, wait_result=True):
    events: list[str] = []
    reader = Reader(snapshot, events)
    arm = Arm(events, arm_result)
    waiter = Waiter(events, wait_result)

    def precondition():
        events.append("precondition")
        assert not (tmp_path / G071_TRANSACTION_STARTED_FILE).exists()

    result = run_g071_atomic_activation_once(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        precondition_verifier=precondition,
        snapshot_reader=reader,
        arm_mutator=arm,
        projection_waiter=waiter,
        now_utc=NOW,
    )
    return result, events, reader, arm, waiter


def test_flat_transaction_is_atomic_and_exactly_once(tmp_path) -> None:
    result, events, reader, arm, waiter = run(
        tmp_path,
        G071SanitizedSnapshot(4, 0, 0),
    )
    assert events == ["precondition", "read", "arm", "wait"]
    assert reader.calls == arm.calls == 1
    assert waiter.expected == EffectiveState.ON_WAITING.value
    assert result.reconciliation_state is ReconciliationState.FRESH_FLAT
    assert result.broker_get_count == 3
    assert result.broker_post_count == 0
    assert result.actual_post_authorized is False
    assert json.loads((tmp_path / G071_TRANSACTION_OUTCOME_FILE).read_text())["status"] == "PASSED"


def test_protected_position_projects_exit_only(tmp_path) -> None:
    result, _events, _reader, _arm, waiter = run(
        tmp_path,
        G071SanitizedSnapshot(
            1, 1, 2, ownership_exact=True, quantity_matches=True, protection_confirmed=True
        ),
    )
    assert result.reconciliation_state is ReconciliationState.FRESH_PROTECTED
    assert waiter.expected == EffectiveState.ON_EXIT_ONLY.value


@pytest.mark.parametrize(
    "snapshot",
    [
        G071SanitizedSnapshot(0, 1, 2),
        G071SanitizedSnapshot(0, 0, 1),
        G071SanitizedSnapshot(
            0, 1, 0, ownership_exact=True, quantity_matches=False, protection_confirmed=True
        ),
    ],
)
def test_unknown_position_or_order_halts_before_arm(tmp_path, snapshot) -> None:
    events: list[str] = []
    with pytest.raises(G071Error, match="RECONCILIATION_NOT_CLEAR"):
        run_g071_atomic_activation_once(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            precondition_verifier=lambda: None,
            snapshot_reader=Reader(snapshot, events),
            arm_mutator=Arm(events),
            projection_waiter=Waiter(events),
            now_utc=NOW,
        )
    assert "arm" not in events
    assert (tmp_path / G071_PERSISTENT_HALT_FILE).is_file()
    assert json.loads((tmp_path / G071_TRANSACTION_OUTCOME_FILE).read_text())["status"] == "UNKNOWN"


def test_boundary_count_violation_is_unknown_without_arm(tmp_path) -> None:
    events: list[str] = []
    snapshot = G071SanitizedSnapshot(0, 0, 0, private_api_read_count=2)
    with pytest.raises(G071Error, match="BOUNDARY_VIOLATION"):
        run_g071_atomic_activation_once(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            precondition_verifier=lambda: None,
            snapshot_reader=Reader(snapshot, events),
            arm_mutator=Arm(events),
            projection_waiter=Waiter(events),
            now_utc=NOW,
        )
    assert "arm" not in events


def test_partial_reader_failure_records_only_observed_attempts(tmp_path) -> None:
    class PartialFailureReader:
        def read_once(self) -> G071SanitizedSnapshot:
            raise RuntimeError("synthetic endpoint failure")

        def safe_attempt_counts(self) -> tuple[int, int, int]:
            return (1, 1, 1)

    with pytest.raises(G071Error, match="UNKNOWN_NO_RETRY"):
        run_g071_atomic_activation_once(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            precondition_verifier=lambda: None,
            snapshot_reader=PartialFailureReader(),
            arm_mutator=Arm([]),
            projection_waiter=Waiter([]),
            now_utc=NOW,
        )
    outcome = json.loads((tmp_path / G071_TRANSACTION_OUTCOME_FILE).read_text())
    assert outcome["broker_get_count"] == 1
    assert outcome["private_api_read_count"] == 1
    assert outcome["credential_read_count"] == 1


def test_second_transaction_is_refused(tmp_path) -> None:
    run(tmp_path, G071SanitizedSnapshot(0, 0, 0))
    with pytest.raises(G071Error, match="OUTCOME_EXISTS"):
        run(tmp_path, G071SanitizedSnapshot(0, 0, 0))


def test_arm_failure_and_projection_timeout_are_unknown(tmp_path) -> None:
    with pytest.raises(G071Error, match="ARM_MUTATION_UNKNOWN"):
        run(tmp_path / "arm", G071SanitizedSnapshot(0, 0, 0), arm_result=False)
    with pytest.raises(G071Error, match="PROJECTION_TIMEOUT"):
        run(tmp_path / "wait", G071SanitizedSnapshot(0, 0, 0), wait_result=False)


def test_resident_is_no_post_and_disarmed_before_transaction(tmp_path) -> None:
    projection = G071ResidentSupervisor(tmp_path, DIGEST, REVIEWED).tick(
        now_utc=NOW,
        arm_state=__import__(
            "app.services.h11_v4_g070_candidate", fromlist=["ArmState"]
        ).ArmState.OFF,
    )
    assert projection.effective_state is EffectiveState.OFF
    status = json.loads((tmp_path / "g071-runtime-status.json").read_text())
    assert status["broker_write"] is False
    assert status["actual_post_count"] == 0


def test_operation_60_has_separate_windows_and_no_retry(tmp_path) -> None:
    clock = iter([0.0, 1.0, 100.0, 100.0])
    outcome = run_g071_operation_60_candidate(
        state_root=tmp_path,
        generation_digest=DIGEST,
        reviewed_files_digest=REVIEWED,
        installer=lambda: None,
        readiness_verifier=lambda: True,
        monotonic=lambda: next(clock),
    )
    assert outcome == "PASSED"
    with pytest.raises(G071Error, match="ALREADY_STARTED"):
        run_g071_operation_60_candidate(
            state_root=tmp_path,
            generation_digest=DIGEST,
            reviewed_files_digest=REVIEWED,
            installer=lambda: None,
            readiness_verifier=lambda: True,
        )


def test_g071_source_has_no_broker_write_transport() -> None:
    source = (
        __import__("pathlib", fromlist=["Path"])
        .Path("app/services/h11_v4_g071_atomic_activation.py")
        .read_text()
    )
    assert "actual_transport" not in source
    assert "live_order_once" not in source
    assert "allow_live_http_post" not in source
    assert 'actual_post_authorized": True' not in source
    assert '"runtime_activation_available": False' in source
    assert '"switch_only_rearm_available": False' in source

    control_source = (
        __import__("pathlib", fromlist=["Path"])
        .Path("app/h11_manual/unattended_control_api.py")
        .read_text()
    )
    assert 'verifier_kwargs["repository"] = REPOSITORY' in control_source
