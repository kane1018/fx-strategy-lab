"""The only real G071 activation entrypoint; never imports broker-write code."""

from __future__ import annotations

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
from app.h11_auto.v4_gmo_unattended_scheduler_launchd import (  # noqa: E402
    V4_GMO_UNATTENDED_SCHEDULER_LABEL,
)
from app.services.h11_v4_g026_private_get_keychain import (  # noqa: E402
    V4G026PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_g071_atomic_activation import (  # noqa: E402
    G071_GENERATION_LABEL,
    G071_OPERATION_60_RESULT_FILE,
    G071_RUNTIME_STATUS_FILE,
    G071ArmMutator,
    G071Error,
    G071ProjectionWaiter,
    G071SanitizedSnapshot,
    run_g071_atomic_activation_once,
    verify_g071_review_artifacts,
    verify_g071_scheduler_binding,
)
from app.services.h11_v4_unattended_live_arm_state import (  # noqa: E402
    V4ArmDesiredState,
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_paths import (  # noqa: E402
    DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    v4_unattended_live_arm_state_path,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (  # noqa: E402
    GMO_V4_PRIVATE_BASE_URL,
    read_v4_unattended_shadow_private_snapshot,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


class _SnapshotReader:
    def __init__(self) -> None:
        self.broker_get_count = 0
        self.private_api_read_count = 0
        self.credential_read_count = 0

    def _observe_request_attempt(self, count: int) -> None:
        self.broker_get_count = count
        self.private_api_read_count = count

    def safe_attempt_counts(self) -> tuple[int, int, int]:
        return (
            self.broker_get_count,
            self.private_api_read_count,
            self.credential_read_count,
        )

    def read_once(self) -> G071SanitizedSnapshot:
        self.credential_read_count = 1
        with httpx.Client(base_url=GMO_V4_PRIVATE_BASE_URL, timeout=15.0) as client:
            report = read_v4_unattended_shadow_private_snapshot(
                credential_pair=V4G026PrivateGetKeychainCredentialPair(),
                client=client,
                request_attempt_observer=self._observe_request_attempt,
            )
        return G071SanitizedSnapshot(
            latest_execution_count=report.latest_executions_count,
            open_position_count=report.open_positions_count,
            active_order_count=report.active_orders_count,
        )


class _ArmMutator(G071ArmMutator):
    def __init__(self, store: V4UnattendedLiveArmStore) -> None:
        self.store = store

    def arm_once(self, *, generation_digest: str, reviewed_files_digest: str) -> bool:
        current = self.store.check(
            expected_generation_digest=generation_digest,
            expected_reviewed_files_digest=reviewed_files_digest,
        )
        if current.armed:
            raise G071Error("G071_ARM_ALREADY_ON")
        changed = self.store.set_desired_state(
            desired_state=V4ArmDesiredState.ARMED,
            expected_revision=current.revision,
            generation_digest=generation_digest,
            reviewed_files_digest=reviewed_files_digest,
            changed_at_utc=datetime.now(UTC),
        )
        return changed.armed


class _ProjectionWaiter(G071ProjectionWaiter):
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
        path = self.state_root / G071_RUNTIME_STATUS_FILE
        while time.monotonic() <= deadline:
            if path.is_file() and not path.is_symlink():
                status = json.loads(path.read_text(encoding="utf-8"))
                heartbeat_at = datetime.fromisoformat(str(status.get("heartbeat_at_utc")))
                if (
                    status.get("arm_state") == "ON"
                    and status.get("effective_state") == expected_effective_state
                    and status.get("generation_digest") == generation_digest
                    and status.get("reviewed_files_digest") == reviewed_files_digest
                    and heartbeat_at.tzinfo is not None
                    and heartbeat_at >= not_before_utc
                    and status.get("broker_write") is False
                    and status.get("actual_post_count") == 0
                ):
                    return True
            time.sleep(0.5)
        return False


def main() -> int:
    repository = Path(__file__).resolve().parents[2]
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    plist_path = Path.home() / "Library/LaunchAgents" / f"{V4_GMO_UNATTENDED_SCHEDULER_LABEL}.plist"

    def preconditions() -> None:
        require_clean_main(repository=repository)
        if generation.generation_label != G071_GENERATION_LABEL:
            raise G071Error("G071_CANONICAL_GENERATION_REQUIRED")
        verify_g071_review_artifacts(
            repository=repository,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
        )
        operation_path = state_root / G071_OPERATION_60_RESULT_FILE
        if not operation_path.is_file() or operation_path.is_symlink():
            raise G071Error("G071_OPERATION_60_RESULT_INVALID")
        operation = json.loads(operation_path.read_text(encoding="utf-8"))
        if (
            operation.get("status") != "PASSED"
            or operation.get("generation_digest") != generation.digest
            or operation.get("reviewed_files_digest") != reviewed
            or operation.get("broker_post_count") != 0
            or operation.get("private_api_read_count") != 0
            or operation.get("credential_read_count") != 0
        ):
            raise G071Error("G071_OPERATION_60_NOT_PASSED")
        verify_g071_scheduler_binding(
            generation=generation,
            repository=repository,
            plist_path=plist_path,
            state_root=state_root,
            now_utc=datetime.now(UTC),
        )

    arm_store = V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(
            state_root=DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
            generation_digest=generation.digest,
        )
    )
    try:
        result = run_g071_atomic_activation_once(
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
    except Exception as error:
        label = str(error) if str(error) else "G071_ATOMIC_ACTIVATION_FAILED_NO_RETRY"
        print(json.dumps({"status": "UNKNOWN", "safe_reason": label, "broker_post_count": 0}))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
