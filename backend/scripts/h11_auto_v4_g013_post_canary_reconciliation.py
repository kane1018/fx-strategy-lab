"""One-use, generation-bound G013 post-canary broker reconciliation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.h11_auto.v4_actual_preparation_guard import (
    load_completed_preparation_evidence,
    load_external_preparation_gate,
)
from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from app.services.h11_v4_gmo_post_canary_reconciliation import (
    V4GmoHttpxPostCanaryReadOnlyClient,
    V4GmoPostCanaryReconciler,
    V4GmoPostCanaryReconciliationError,
    load_post_canary_origin_generation_digest,
)
from h11_v4_reviewed_digest import compute_reviewed_files_digest

REPOSITORY = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        repository = REPOSITORY.resolve()
        digest = compute_reviewed_files_digest(repository=repository)
        generation = load_v4_gmo_frozen_generation(
            repository=repository, implementation_digest=digest
        )
        gate = load_external_preparation_gate(repository=repository)
        load_completed_preparation_evidence(
            external_gate=gate, generation_digest=generation.digest
        )
        origin_digest = load_post_canary_origin_generation_digest(
            repository=repository,
            reviewed_files_digest=digest,
            generation_digest=generation.digest,
        )
        origin_root = v4_gmo_runtime_state_root(
            repository=repository, generation_digest=origin_digest
        )
        origin_ledger = origin_root / "coordinator.sqlite3"
        if not origin_ledger.is_file() or origin_ledger.is_symlink():
            raise V4GmoPostCanaryReconciliationError(
                "G013_POST_CANARY_ORIGIN_LEDGER_UNAVAILABLE"
            )
        cycle_ref = _load_origin_cycle_ref_read_only(origin_ledger)
        result = V4GmoPostCanaryReconciler(
            repository=repository,
            target_generation_digest=generation.digest,
            origin_generation_digest=origin_digest,
            cycle_ref=cycle_ref,
            client=V4GmoHttpxPostCanaryReadOnlyClient.from_keychain(),
        ).reconcile_once()
        print(json.dumps(result.safe_dict(), sort_keys=True))
        return 0 if result.result_known else 2
    except Exception:
        print(json.dumps(_safe_failure(), sort_keys=True))
        return 2


def _safe_failure() -> dict[str, object]:
    return {
        "status": "G013_POST_CANARY_RESULT_UNKNOWN_PERSISTENT_HALT",
        "result_known": False,
        "subject_entry_observed": False,
        "account_flat": False,
        "active_orders_zero": False,
        "broker_read_count": 0,
        "broker_write_attempt_count": 0,
        "raw_response_retained": False,
        "identifier_exposed": False,
    }


def _load_origin_cycle_ref_read_only(origin_ledger: Path) -> str:
    """Read the sole origin cycle through SQLite mode=ro with no schema mutation."""

    try:
        connection = sqlite3.connect(
            origin_ledger.resolve().as_uri() + "?mode=ro", uri=True
        )
    except sqlite3.Error:
        raise V4GmoPostCanaryReconciliationError(
            "G013_POST_CANARY_ORIGIN_LEDGER_UNAVAILABLE"
        ) from None
    try:
        rows = connection.execute(
            "SELECT signal_fingerprint FROM cycles ORDER BY created_at_utc"
        ).fetchall()
        if len(rows) != 1 or not isinstance(rows[0][0], str):
            raise V4GmoPostCanaryReconciliationError(
                "G013_POST_CANARY_ORIGIN_CYCLE_UNAVAILABLE"
            )
        row = connection.execute(
            "SELECT cycle_ref FROM cycles WHERE signal_fingerprint=?", (rows[0][0],)
        ).fetchone()
        cycle_ref = None if row is None else row[0]
        if (
            not isinstance(cycle_ref, str)
            or len(cycle_ref) != 64
            or any(character not in "0123456789abcdef" for character in cycle_ref)
        ):
            raise V4GmoPostCanaryReconciliationError(
                "G013_POST_CANARY_ORIGIN_CYCLE_UNAVAILABLE"
            )
        return cycle_ref
    except sqlite3.Error:
        raise V4GmoPostCanaryReconciliationError(
            "G013_POST_CANARY_ORIGIN_CYCLE_UNAVAILABLE"
        ) from None
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
