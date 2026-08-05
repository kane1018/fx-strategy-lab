"""One-use G079 release activation: three read-only GETs then local ARM ON.

The operator runs this script after G079 promotion and a PASSED
``g079-operation-60``.  It performs the one-use atomic transaction: fresh
read-only reconciliation (must be flat / zero-active), release capability
enable, and local ARM ON.  Any UNKNOWN is terminal and never retried.  Broker
POST stays forbidden (default-deny).
"""

from __future__ import annotations

import argparse
import sys
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
from app.services.h11_v4_g079_runtime import (  # noqa: E402
    G079_GENERATION_LABEL,
    G079Error,
    G079SanitizedSnapshot,
    run_g079_initial_atomic_activation,
    run_g079_reconciliation_cycle_once,
)
from app.services.h11_v4_unattended_live_arm_state import (  # noqa: E402
    V4ArmDesiredState,
    V4UnattendedLiveArmStore,
)
from app.services.h11_v4_unattended_live_paths import (  # noqa: E402
    v4_unattended_live_arm_state_path,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (  # noqa: E402
    read_v4_unattended_shadow_private_snapshot,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--execute-final-transaction", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.execute_final_transaction:
        raise G079Error("G079_INITIAL_TRANSACTION_EXPLICIT_FLAG_REQUIRED")
    repository = args.repository.resolve()
    require_clean_main(repository=repository)
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if generation.generation_label != G079_GENERATION_LABEL:
        raise G079Error("G079_CANONICAL_GENERATION_REQUIRED")
    state_root = v4_gmo_runtime_state_root(
        repository=repository, generation_digest=generation.digest
    )
    arm_store = V4UnattendedLiveArmStore(
        v4_unattended_live_arm_state_path(generation_digest=generation.digest)
    )
    observed_at = datetime.now(UTC)

    def reconcile_once():
        with httpx.Client(timeout=5.0) as client:
            snapshot = read_v4_unattended_shadow_private_snapshot(
                credential_pair=V4G026PrivateGetKeychainCredentialPair(),
                client=client,
            )
        if not snapshot.account_flat or not snapshot.active_orders_zero:
            raise G079Error("G079_INITIAL_ACCOUNT_NOT_FLAT")
        return run_g079_reconciliation_cycle_once(
            state_root=state_root,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
            cycle_id="initial-activation",
            reconciler=lambda **_kwargs: G079SanitizedSnapshot(
                latest_execution_count=snapshot.latest_executions_count,
                open_position_count=snapshot.open_positions_count,
                active_order_count=snapshot.active_orders_count,
                broker_get_count=snapshot.broker_get_count,
                private_api_read_count=snapshot.broker_get_count,
                credential_read_count=1,
            ),
            now_utc=observed_at,
        )

    def arm_on() -> None:
        current = arm_store.check(
            expected_generation_digest=generation.digest,
            expected_reviewed_files_digest=reviewed,
        )
        arm_store.set_desired_state(
            desired_state=V4ArmDesiredState.ARMED,
            expected_revision=current.revision,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
            changed_at_utc=datetime.now(UTC),
        )

    outcome = run_g079_initial_atomic_activation(
        state_root=state_root,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
        reconciliation_runner=reconcile_once,
        arm_mutator=arm_on,
        arm_state_verifier=lambda: arm_store.check(
            expected_generation_digest=generation.digest,
            expected_reviewed_files_digest=reviewed,
        ).armed,
        now_utc=observed_at,
    )
    print(f"G079_INITIAL_ATOMIC_ACTIVATION_{outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
