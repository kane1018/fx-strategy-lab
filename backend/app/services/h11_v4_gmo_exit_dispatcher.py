"""Finite generation-bound time-exit dispatcher for H-11 v4 G013.

The monitor-only supervisor never imports this module.  A future activated
runtime may call this dispatcher once after the supervisor emits the reviewed
dispatch-required marker.  The dispatcher claims that marker before any I/O,
uses only the coordinated actual path, and never retries an unknown action.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from app.h11_auto.v4_gmo_contracts import V4GmoAction, build_v4_action_plan
from app.services.h11_v4_gmo_actual_adapter import V4GmoPrivateOutcome
from app.services.h11_v4_gmo_coordinated_actual_path import (
    V4GmoCoordinatedActualPath,
)
from app.services.h11_v4_gmo_public_market_status import (
    V4GmoPublicMarketStatusReader,
)


class V4GmoExitDispatcherError(RuntimeError):
    """Fixed safe dispatcher failure."""


def _valid_trading_day_jst(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


@dataclass(frozen=True)
class V4GmoExitDispatchResult:
    claimed: bool
    protection_cancel_accepted: bool
    position_close_accepted: bool
    flat_reconciled: bool
    broker_post_attempt_count: int

    def __bool__(self) -> bool:
        return False


class V4GmoExitDispatcher:
    def __init__(
        self,
        *,
        coordinated_path: V4GmoCoordinatedActualPath,
        state_root: Path,
    ) -> None:
        expected_root = coordinated_path.store.path.parent.resolve()
        if (
            state_root.resolve() != expected_root
            or state_root.is_symlink()
            or not coordinated_path.process_lock.held
        ):
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_RUNTIME_INVALID")
        self.path = coordinated_path
        self.state_root = state_root.resolve()

    def dispatch_once(
        self,
        *,
        public_cancel_reader: V4GmoPublicMarketStatusReader,
        public_close_reader: V4GmoPublicMarketStatusReader,
        observed_at_utc: datetime,
        cycle_day_jst: str,
    ) -> V4GmoExitDispatchResult:
        if observed_at_utc.tzinfo is None:
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_TIME_INVALID")
        if not _valid_trading_day_jst(cycle_day_jst):
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_TRADING_DAY_INVALID")
        self._claim_once(observed_at_utc=observed_at_utc, cycle_day_jst=cycle_day_jst)
        store = self.path.store
        try:
            signal_fingerprint = store.load_single_signal_fingerprint_internal()
            cycle_ref = store.cycle_ref_for_signal_internal(signal_fingerprint)
            side = store.side_for_signal_internal(signal_fingerprint)
            requested_size = store.expected_closed_size_for_signal_internal(
                signal_fingerprint
            )
            cancel_evidence = self.path.reconcile_once_fixed(
                cycle_ref=cycle_ref,
                side=side,
                requested_size=requested_size,
            )
            # Natural OCO settlement shortcut: when the broker already settled the
            # position (SL/TP filled), the OCO no longer exists — cancelling it
            # would only fail. Record the flat result from this same evidence and
            # complete with ZERO additional POSTs.
            if self.path.reconciliation_shows_natural_flat(
                signal_fingerprint=signal_fingerprint,
                reconciliation_evidence=cancel_evidence,
            ):
                flat = self.path.record_flat_closed_result_once(
                    signal_fingerprint=signal_fingerprint,
                    reconciliation_evidence=cancel_evidence,
                )
                if flat is not True:
                    raise V4GmoExitDispatcherError("V4_EXIT_FLAT_NOT_RECONCILED")
                self._write_terminal_marker(
                    f"exit-sequence-dispatch-completed.{cycle_day_jst}.json",
                    status="EXIT_DISPATCH_COMPLETED_NATURAL_SETTLEMENT_FLAT",
                    observed_at_utc=observed_at_utc,
                )
                return V4GmoExitDispatchResult(
                    claimed=True,
                    protection_cancel_accepted=False,
                    position_close_accepted=False,
                    flat_reconciled=True,
                    broker_post_attempt_count=0,
                )
            cancel_plan = build_v4_action_plan(
                cycle_ref=cycle_ref,
                action=V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
                side=side,
                requested_size=requested_size,
                protection_contract_hash=self.path.generation.protection_contract_hash,
            )
            cancel_outcome = self.path.perform_risk_reducing_once(
                signal_fingerprint=signal_fingerprint,
                plan=cancel_plan,
                reconciliation_evidence=cancel_evidence,
                market_status_evidence=public_cancel_reader.read_once(),
            )
            if cancel_outcome is not V4GmoPrivateOutcome.ACCEPTED_SANITIZED:
                raise V4GmoExitDispatcherError("V4_EXIT_CANCEL_NOT_ACCEPTED")
            cancel_recovery_evidence = self.path.reconcile_once_fixed(
                cycle_ref=cycle_ref,
                side=side,
                requested_size=requested_size,
            )
            cancel_recovery, close_action_evidence = (
                self.path.recover_pending_transport_and_carry_once(
                    cycle_ref=cycle_ref,
                    reconciliation_evidence=cancel_recovery_evidence,
                )
            )
            if cancel_recovery.classification != "FILLED_UNPROTECTED":
                raise V4GmoExitDispatcherError("V4_EXIT_CANCEL_RECONCILIATION_INVALID")
            close_plan = build_v4_action_plan(
                cycle_ref=cycle_ref,
                action=V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
                side=side,
                requested_size=requested_size,
                protection_contract_hash=self.path.generation.protection_contract_hash,
            )
            close_outcome = self.path.perform_risk_reducing_once(
                signal_fingerprint=signal_fingerprint,
                plan=close_plan,
                reconciliation_evidence=close_action_evidence,
                market_status_evidence=public_close_reader.read_once(),
            )
            if close_outcome is not V4GmoPrivateOutcome.ACCEPTED_SANITIZED:
                raise V4GmoExitDispatcherError("V4_EXIT_CLOSE_NOT_ACCEPTED")
            close_recovery_evidence = self.path.reconcile_once_fixed(
                cycle_ref=cycle_ref,
                side=side,
                requested_size=requested_size,
            )
            close_recovery, flat_evidence = (
                self.path.recover_pending_transport_and_carry_once(
                    cycle_ref=cycle_ref,
                    reconciliation_evidence=close_recovery_evidence,
                )
            )
            if close_recovery.classification != "FLAT_OR_REJECTED":
                raise V4GmoExitDispatcherError("V4_EXIT_CLOSE_RECONCILIATION_INVALID")
            flat = self.path.record_flat_closed_result_once(
                signal_fingerprint=signal_fingerprint,
                reconciliation_evidence=flat_evidence,
            )
            if flat is not True:
                raise V4GmoExitDispatcherError("V4_EXIT_FLAT_NOT_RECONCILED")
        except BaseException as error:
            store.engage_unknown_halt()
            self._write_terminal_marker(
                f"exit-sequence-dispatch-failed.{cycle_day_jst}.json",
                status="PERSISTENT_HALT_EXIT_DISPATCH_FAILED_NO_RETRY",
                observed_at_utc=observed_at_utc,
            )
            if isinstance(error, V4GmoExitDispatcherError):
                raise
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_FAILED") from error
        self._write_terminal_marker(
            f"exit-sequence-dispatch-completed.{cycle_day_jst}.json",
            status="EXIT_DISPATCH_COMPLETED_FLAT_RECONCILED",
            observed_at_utc=observed_at_utc,
        )
        return V4GmoExitDispatchResult(
            claimed=True,
            protection_cancel_accepted=True,
            position_close_accepted=True,
            flat_reconciled=True,
            broker_post_attempt_count=2,
        )

    def _claim_once(self, *, observed_at_utc: datetime, cycle_day_jst: str) -> None:
        required = (
            self.state_root / f"exit-sequence-dispatch-required.{cycle_day_jst}.json"
        )
        if not required.is_file() or required.is_symlink():
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_NOT_REQUIRED")
        try:
            payload = json.loads(required.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_MARKER_INVALID") from error
        if (
            not isinstance(payload, dict)
            or payload.get("generation_digest") != self.path.generation.digest
            or payload.get("status") != "GENERATION_BOUND_EXIT_DISPATCH_REQUIRED"
        ):
            raise V4GmoExitDispatcherError("V4_EXIT_DISPATCH_GENERATION_MISMATCH")
        self._write_terminal_marker(
            f"exit-sequence-dispatch-claimed.{cycle_day_jst}.json",
            status="EXIT_DISPATCH_CLAIMED_ONE_USE",
            observed_at_utc=observed_at_utc,
            exclusive=True,
        )

    def _write_terminal_marker(
        self,
        name: str,
        *,
        status: str,
        observed_at_utc: datetime,
        exclusive: bool = False,
    ) -> None:
        path = self.state_root / name
        payload = {
            "generation_digest": self.path.generation.digest,
            "observed_at_utc": observed_at_utc.astimezone(UTC).isoformat(),
            "status": status,
        }
        flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
        try:
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except FileExistsError as error:
            raise V4GmoExitDispatcherError(
                "V4_EXIT_DISPATCH_ALREADY_CLAIMED_NO_RETRY"
            ) from error
        except OSError as error:
            raise V4GmoExitDispatcherError(
                "V4_EXIT_DISPATCH_MARKER_WRITE_FAILED"
            ) from error

    def __repr__(self) -> str:
        return "V4GmoExitDispatcher(<generation-bound-one-shot>)"

    def __bool__(self) -> bool:
        return False
