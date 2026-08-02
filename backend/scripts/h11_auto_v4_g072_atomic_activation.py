"""G072 final one-shot activation entrypoint.

This command is intentionally blocked unless the caller supplies the explicit
final-transaction flag. It is not used by UI ON and is not run during G072
implementation, review, or operation 60.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.h11_auto.v4_actual_preparation_guard import require_clean_main  # noqa: E402
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation  # noqa: E402
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root  # noqa: E402
from app.services.h11_v4_g026_private_get_keychain import (  # noqa: E402
    V4G026PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_g072_switch_control import (  # noqa: E402
    G072_GENERATION_LABEL,
    G072_RUNTIME_STATUS_FILE,
    G072ArmMutator,
    G072AtomicActivationResult,
    G072Error,
    G072ProjectionWaiter,
    G072SanitizedSnapshot,
    G072SnapshotReader,
    run_g072_initial_atomic_activation_once,
    verify_g072_review_artifacts,
    verify_g072_scheduler_binding,
)
from app.services.h11_v4_unattended_live_arm_state import (  # noqa: E402
    V4ArmDesiredState,
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_paths import (  # noqa: E402
    v4_unattended_live_arm_state_path,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (  # noqa: E402
    GMO_V4_PRIVATE_BASE_URL,
    read_v4_unattended_shadow_private_snapshot,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


class _SnapshotReader(G072SnapshotReader):
    def __init__(self) -> None:
        self.broker_get_count = 0
        self.private_api_read_count = 0
        self.credential_read_count = 0

    def _observe_request_attempt(self, count: int) -> None:
        self.broker_get_count = count
        self.private_api_read_count = count

    def safe_attempt_counts(self) -> tuple[int, int, int]:
        return self.broker_get_count, self.private_api_read_count, self.credential_read_count

    def read_once(self) -> G072SanitizedSnapshot:
        self.credential_read_count = 1
        with httpx.Client(base_url=GMO_V4_PRIVATE_BASE_URL, timeout=15.0) as client:
            report = read_v4_unattended_shadow_private_snapshot(
                credential_pair=V4G026PrivateGetKeychainCredentialPair(),
                client=client,
                request_attempt_observer=self._observe_request_attempt,
            )
        return G072SanitizedSnapshot(
            latest_execution_count=report.latest_executions_count,
            open_position_count=report.open_positions_count,
            active_order_count=report.active_orders_count,
        )


class _ArmMutator(G072ArmMutator):
    def __init__(self, store: V4UnattendedLiveArmStore) -> None:
        self.store = store

    def arm_once(self, *, generation_digest: str, reviewed_files_digest: str) -> bool:
        current = self.store.check(
            expected_generation_digest=generation_digest,
            expected_reviewed_files_digest=reviewed_files_digest,
        )
        if current.armed:
            raise G072Error("G072_ARM_ALREADY_ON")
        return self.store.set_desired_state(
            desired_state=V4ArmDesiredState.ARMED,
            expected_revision=current.revision,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            changed_at_utc=datetime.now(UTC),
        ).armed


class _ProjectionWaiter(G072ProjectionWaiter):
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root

    def wait_once(
        self,
        *,
        expected_effective_state: str,
        generation_digest: str,
        reviewed_files_digest: str,
        not_before_utc: datetime,
        timeout_seconds: float,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        path = self.state_root / G072_RUNTIME_STATUS_FILE
        while time.monotonic() <= deadline:
            if path.is_file() and not path.is_symlink():
                try:
                    status = json.loads(path.read_text(encoding="utf-8"))
                    heartbeat_at = datetime.fromisoformat(str(status["heartbeat_at_utc"]))
                except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                    heartbeat_at = None
                    status = {}
                if (
                    status.get("arm_state") == "ON"
                    and status.get("effective_state") == expected_effective_state
                    and status.get("generation_digest") == generation_digest
                    and status.get("reviewed_files_digest") == reviewed_files_digest
                    and heartbeat_at is not None
                    and heartbeat_at.tzinfo is not None
                    and heartbeat_at >= not_before_utc
                    and status.get("broker_write") is False
                    and status.get("actual_post_count") == 0
                ):
                    return True
            time.sleep(0.5)
        return False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-transaction", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.final_transaction:
        print("G072_FINAL_TRANSACTION_REQUIRES_SEPARATE_APPROVAL")
        return 4
    repository = Path(__file__).resolve().parents[2]
    require_clean_main(repository=repository)
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=reviewed,
    )
    if generation.generation_label != G072_GENERATION_LABEL:
        print("G072_GENERATION_REQUIRED")
        return 4
    verify_g072_review_artifacts(
        repository=repository,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=generation.digest,
    )
    plist_path = (
        Path.home()
        / "Library/LaunchAgents"
        / "com.fxstrategylab.h11v4.unattended.scheduler.plist"
    )

    def preconditions() -> None:
        verify_g072_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist_path,
            state_root=state_root,
            now_utc=datetime.now(UTC),
        )

    arm_store = V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(generation_digest=generation.digest)
    )
    result: G072AtomicActivationResult = run_g072_initial_atomic_activation_once(
        state_root=state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
        precondition_verifier=preconditions,
        snapshot_reader=_SnapshotReader(),
        arm_mutator=_ArmMutator(arm_store),
        projection_waiter=_ProjectionWaiter(state_root),
        now_utc=datetime.now(UTC),
    )
    print(json.dumps(asdict(result), sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
