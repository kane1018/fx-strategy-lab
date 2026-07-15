from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.h11_auto.contracts import build_intent_id
from app.h11_auto.persistence import H11AutoProcessLock, H11AutoStateStore
from app.h11_auto.recovery import RecoveryAction, evaluate_restart_recovery
from app.h11_auto.state_machine import AutoCycleState, SafeBrokerState
from app.tests.h11_auto.crash_worker import build_fixture


def test_sigkill_after_attempt_persists_state_releases_lock_and_never_resends(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.tests.h11_auto.crash_worker",
            "--state-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode < 0
    assert completed.stdout == ""
    assert completed.stderr == ""

    lock = H11AutoProcessLock(tmp_path / "auto.lock")
    assert lock.acquire() is True
    lock.release()

    signal, policy = build_fixture()
    intent_id = build_intent_id(signal=signal, policy=policy)
    cycle = H11AutoStateStore(tmp_path / "state.sqlite3").load_cycle(intent_id)
    assert cycle.state is AutoCycleState.PROTECTED_ENTRY_PENDING
    assert cycle.attempt_count == 1
    decision = evaluate_restart_recovery(
        cycle=cycle,
        broker_state=SafeBrokerState.PROTECTED_ENTRY_PENDING,
        safe_read_fresh=True,
    )
    assert decision.action is RecoveryAction.OBSERVE_PENDING_NO_RESEND
    assert decision.entry_resend_allowed is False
    assert decision.exit_resend_allowed is False
    assert decision.actual_post_allowed is False
