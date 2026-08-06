"""One-use G075 release activation: three read-only GETs then local ARM ON."""

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
from app.services.h11_v4_g075_private_get_keychain import (  # noqa: E402
    G075PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_g075_runtime import (  # noqa: E402
    G075_GENERATION_LABEL,
    G075Error,
    G075SanitizedSnapshot,
    require_g075_no_unresolved_halt,
    run_g075_initial_atomic_activation,
    run_g075_reconciliation_cycle_once,
    verify_g075_review_artifacts,
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
        raise G075Error("G075_INITIAL_TRANSACTION_EXPLICIT_FLAG_REQUIRED")
    repository = args.repository.resolve()
    require_clean_main(repository=repository)
    # D-P1a: refuse BEFORE the initial-transaction_started marker is written,
    # so the marker is not burned on a guaranteed-UNKNOWN outcome.
    require_g075_no_unresolved_halt(repository=repository)
    reviewed = compute_reviewed_files_digest(repository=repository)
    generation = load_v4_gmo_frozen_generation(
        repository=repository, implementation_digest=reviewed
    )
    if generation.generation_label != G075_GENERATION_LABEL:
        raise G075Error("G075_CANONICAL_GENERATION_REQUIRED")
    verify_g075_review_artifacts(
        repository=repository,
        generation_digest=generation.digest,
        reviewed_files_digest=reviewed,
    )
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
                credential_pair=G075PrivateGetKeychainCredentialPair(), client=client
            )
        if not snapshot.account_flat or not snapshot.active_orders_zero:
            raise G075Error("G075_INITIAL_ACCOUNT_NOT_FLAT")
        return run_g075_reconciliation_cycle_once(
            state_root=state_root,
            generation_digest=generation.digest,
            reviewed_files_digest=reviewed,
            cycle_id="initial-activation",
            reconciler=lambda **_kwargs: G075SanitizedSnapshot(
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

    outcome = run_g075_initial_atomic_activation(
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
    print(f"G075_INITIAL_ATOMIC_ACTIVATION_{outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
