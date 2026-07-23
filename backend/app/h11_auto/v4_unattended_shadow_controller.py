"""Deterministic H-11 v4 unattended controller in structurally no-POST shadow mode."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.v4_gmo_contracts import (
    V4GmoExecutionPolicy,
    V4GmoPreflightSnapshot,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH

V4_UNATTENDED_SHADOW_SCHEMA = "H11_V4_UNATTENDED_SHADOW_CONTROLLER_V1"
V4_UNATTENDED_SHADOW_SYMBOL = "USD_JPY"
V4_UNATTENDED_SHADOW_EXECUTION_TYPE = "MARKET"
V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH = (
    "sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d"
)
V4_UNATTENDED_SHADOW_MAX_SIGNAL_AGE_SECONDS = Decimal("120")
V4_UNATTENDED_SHADOW_MAX_QUOTE_AGE_SECONDS = Decimal("5")
V4_UNATTENDED_SHADOW_MAX_SPREAD_PIPS = Decimal("2.0")
V4_UNATTENDED_SHADOW_MAX_REFERENCE_DEVIATION_PIPS = Decimal("5.0")
_JST = ZoneInfo("Asia/Tokyo")
_SHADOW_EXPORT_ROOT = Path(__file__).resolve().parents[2] / "shadow_exports"


class V4UnattendedShadowError(RuntimeError):
    """Fail-closed shadow-controller error containing safe labels only."""


class V4ShadowDecisionStatus(str, Enum):
    SHADOW_WOULD_ENTER_NON_AUTHORIZING = "SHADOW_WOULD_ENTER_NON_AUTHORIZING"
    SHADOW_NO_ACTION_STAY = "SHADOW_NO_ACTION_STAY"
    SHADOW_BLOCKED_SAFE = "SHADOW_BLOCKED_SAFE"
    SHADOW_DUPLICATE_SIGNAL_REFUSED = "SHADOW_DUPLICATE_SIGNAL_REFUSED"
    SHADOW_HALTED = "SHADOW_HALTED"


@dataclass(frozen=True)
class V4UnattendedShadowSnapshot:
    preflight: V4GmoPreflightSnapshot
    market_open: bool
    quote_age_seconds: Decimal
    spread_pips: Decimal
    reference_deviation_pips: Decimal
    frozen_atr_24: Decimal
    planned_loss_bound_jpy: int

    def __post_init__(self) -> None:
        if type(self.preflight) is not V4GmoPreflightSnapshot:
            raise V4UnattendedShadowError("SHADOW_PREFLIGHT_INVALID")
        if type(self.market_open) is not bool:
            raise V4UnattendedShadowError("SHADOW_MARKET_FLAG_INVALID")
        for name in (
            "quote_age_seconds",
            "spread_pips",
            "reference_deviation_pips",
            "frozen_atr_24",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise V4UnattendedShadowError(f"SHADOW_{name.upper()}_INVALID")
        if self.spread_pips < 0 or self.frozen_atr_24 <= 0:
            raise V4UnattendedShadowError("SHADOW_MARKET_VALUE_INVALID")
        if (
            type(self.planned_loss_bound_jpy) is not int
            or self.planned_loss_bound_jpy <= 0
        ):
            raise V4UnattendedShadowError("SHADOW_PLANNED_LOSS_INVALID")


@dataclass(frozen=True)
class V4ShadowEntryIntent:
    cycle_ref: str
    signal_fingerprint: str
    policy_config_hash: str
    side: SignalDecision
    symbol: str
    size: int
    execution_type: str
    frozen_atr_24: Decimal
    planned_loss_bound_jpy: int
    broker_post_authorized: bool = False
    actual_post_count: int = 0

    def __post_init__(self) -> None:
        for digest in (self.cycle_ref, self.signal_fingerprint):
            if not _is_hex_digest(digest):
                raise V4UnattendedShadowError("SHADOW_INTENT_DIGEST_INVALID")
        if not _is_prefixed_hex_digest(self.policy_config_hash):
            raise V4UnattendedShadowError("SHADOW_POLICY_DIGEST_INVALID")
        if type(self.side) is not SignalDecision or self.side not in (
            SignalDecision.BUY,
            SignalDecision.SELL,
        ):
            raise V4UnattendedShadowError("SHADOW_INTENT_SIDE_INVALID")
        if (
            self.symbol != V4_UNATTENDED_SHADOW_SYMBOL
            or self.size != 1_000
            or self.execution_type != V4_UNATTENDED_SHADOW_EXECUTION_TYPE
        ):
            raise V4UnattendedShadowError("SHADOW_FIXED_ORDER_CONTRACT_MISMATCH")
        if (
            not isinstance(self.frozen_atr_24, Decimal)
            or not self.frozen_atr_24.is_finite()
            or self.frozen_atr_24 <= 0
            or type(self.planned_loss_bound_jpy) is not int
            or not 0 < self.planned_loss_bound_jpy <= 5_000
        ):
            raise V4UnattendedShadowError("SHADOW_INTENT_RISK_INVALID")
        if (
            self.broker_post_authorized is not False
            or type(self.actual_post_count) is not int
            or self.actual_post_count != 0
        ):
            raise V4UnattendedShadowError("SHADOW_INTENT_CANNOT_AUTHORIZE_POST")

    @property
    def digest(self) -> str:
        payload = asdict(self)
        payload["side"] = self.side.value
        payload["frozen_atr_24"] = format(self.frozen_atr_24, "f")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4ShadowControllerReport:
    status: V4ShadowDecisionStatus
    cycle_ref: str
    signal_fingerprint: str
    blocked_reasons: tuple[str, ...]
    recorded: bool
    shadow_intent: V4ShadowEntryIntent | None
    broker_post_authorized: bool = False
    actual_post_count: int = 0
    broker_read_performed: bool = False
    broker_write_performed: bool = False
    credential_read_performed: bool = False
    network_access_performed: bool = False
    live_ready: bool = False
    unattended_live_supported: bool = False

    def __post_init__(self) -> None:
        if type(self.status) is not V4ShadowDecisionStatus:
            raise V4UnattendedShadowError("SHADOW_REPORT_STATUS_INVALID")
        if not _is_hex_digest(self.cycle_ref) or not _is_hex_digest(
            self.signal_fingerprint
        ):
            raise V4UnattendedShadowError("SHADOW_REPORT_DIGEST_INVALID")
        if type(self.blocked_reasons) is not tuple:
            raise V4UnattendedShadowError("SHADOW_REPORT_REASONS_INVALID")
        for reason in self.blocked_reasons:
            _validate_safe_reason(reason)
        if type(self.recorded) is not bool:
            raise V4UnattendedShadowError("SHADOW_REPORT_RECORDED_INVALID")
        if (
            self.status
            is V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
        ):
            if (
                type(self.shadow_intent) is not V4ShadowEntryIntent
                or not self.recorded
                or self.shadow_intent.cycle_ref != self.cycle_ref
                or self.shadow_intent.signal_fingerprint
                != self.signal_fingerprint
            ):
                raise V4UnattendedShadowError("SHADOW_REPORT_INTENT_INVARIANT_FAILED")
        elif self.shadow_intent is not None:
            raise V4UnattendedShadowError("SHADOW_REPORT_INTENT_INVARIANT_FAILED")
        if (
            self.broker_post_authorized is not False
            or type(self.actual_post_count) is not int
            or self.actual_post_count != 0
            or self.broker_read_performed is not False
            or self.broker_write_performed is not False
            or self.credential_read_performed is not False
            or self.network_access_performed is not False
            or self.live_ready is not False
            or self.unattended_live_supported is not False
        ):
            raise V4UnattendedShadowError("SHADOW_REPORT_CANNOT_CLAIM_LIVE_ACTIVITY")

    def __bool__(self) -> bool:
        return False

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "blocked_reasons": list(self.blocked_reasons),
            "recorded": self.recorded,
            "shadow_intent_created": self.shadow_intent is not None,
            "broker_post_authorized": False,
            "actual_post_count": 0,
            "broker_read_performed": False,
            "broker_write_performed": False,
            "credential_read_performed": False,
            "network_access_performed": False,
            "live_ready": False,
            "unattended_live_supported": False,
        }


@dataclass(frozen=True)
class _StoredDecision:
    status: V4ShadowDecisionStatus
    blocked_reasons: tuple[str, ...]
    recorded: bool


class V4UnattendedShadowStore:
    """Generation-independent shadow ledger with no clear/reset operation."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._assert_confined_path()
        if self.path.is_symlink():
            raise V4UnattendedShadowError("SHADOW_LEDGER_SYMLINK_REFUSED")
        if self.path.exists() and not self.path.is_file():
            raise V4UnattendedShadowError("SHADOW_LEDGER_NOT_REGULAR_FILE")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._initialize()
        except sqlite3.Error as error:
            raise V4UnattendedShadowError("SHADOW_LEDGER_INITIALIZATION_FAILED") from error

    @property
    def path(self) -> Path:
        return self._path

    def _assert_confined_path(self) -> None:
        if not isinstance(self._path, Path):
            raise V4UnattendedShadowError("SHADOW_LEDGER_PATH_INVALID")
        resolved = self._path.resolve()
        root = _SHADOW_EXPORT_ROOT.resolve()
        if resolved == root or not resolved.is_relative_to(root):
            raise V4UnattendedShadowError("SHADOW_LEDGER_PATH_OUTSIDE_EXPORT_ROOT")

    def _connect(self) -> sqlite3.Connection:
        self._assert_confined_path()
        if self.path.is_symlink():
            raise V4UnattendedShadowError("SHADOW_LEDGER_SYMLINK_REFUSED")
        uri = f"{self.path.absolute().as_uri()}?mode=rwc&nofollow=1"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5.0)
        except sqlite3.Error as error:
            raise V4UnattendedShadowError("SHADOW_LEDGER_CONNECTION_FAILED") from error
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_fingerprint TEXT NOT NULL UNIQUE,
                    cycle_ref TEXT NOT NULL UNIQUE,
                    controller_digest TEXT NOT NULL,
                    trading_day_jst TEXT NOT NULL,
                    status TEXT NOT NULL,
                    intent_digest TEXT,
                    blocked_reasons_json TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL
                );
                """
            )
            self._bind_metadata(
                connection,
                key="schema",
                value=V4_UNATTENDED_SHADOW_SCHEMA,
            )

    @staticmethod
    def _bind_metadata(
        connection: sqlite3.Connection, *, key: str, value: str
    ) -> None:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES(?, ?)", (key, value)
            )
        elif row["value"] != value:
            raise V4UnattendedShadowError("SHADOW_LEDGER_BINDING_MISMATCH")

    def bind_controller(self, *, controller_digest: str) -> None:
        if not controller_digest.startswith("sha256:"):
            raise V4UnattendedShadowError("SHADOW_CONTROLLER_DIGEST_INVALID")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._bind_metadata(
                connection,
                key="controller_digest",
                value=controller_digest,
            )

    def halt_reason(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'halt_reason'"
            ).fetchone()
        return None if row is None else str(row["value"])

    def latch_halt(self, *, reason: str) -> None:
        _validate_safe_reason(reason)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'halt_reason'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES('halt_reason', ?)",
                    (reason,),
                )
            elif row["value"] != reason:
                raise V4UnattendedShadowError("SHADOW_DIFFERENT_HALT_ALREADY_LATCHED")

    def record_once(
        self,
        *,
        signal_fingerprint: str,
        cycle_ref: str,
        controller_digest: str,
        trading_day_jst: str,
        proposed_status: V4ShadowDecisionStatus,
        intent_digest: str | None,
        blocked_reasons: tuple[str, ...],
        recorded_at_utc: datetime,
    ) -> _StoredDecision:
        if recorded_at_utc.tzinfo is None:
            raise V4UnattendedShadowError("SHADOW_RECORDED_TIME_INVALID")
        for reason in blocked_reasons:
            _validate_safe_reason(reason)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            binding = connection.execute(
                "SELECT value FROM metadata WHERE key = 'controller_digest'"
            ).fetchone()
            if binding is None or binding["value"] != controller_digest:
                raise V4UnattendedShadowError("SHADOW_CONTROLLER_BINDING_MISMATCH")
            existing = connection.execute(
                "SELECT 1 FROM decisions WHERE signal_fingerprint = ?",
                (signal_fingerprint,),
            ).fetchone()
            if existing is not None:
                return _StoredDecision(
                    status=V4ShadowDecisionStatus.SHADOW_DUPLICATE_SIGNAL_REFUSED,
                    blocked_reasons=("DUPLICATE_SIGNAL_ALREADY_RECORDED",),
                    recorded=False,
                )
            final_status = proposed_status
            final_intent_digest = intent_digest
            final_reasons = blocked_reasons
            halt = connection.execute(
                "SELECT value FROM metadata WHERE key = 'halt_reason'"
            ).fetchone()
            if halt is not None:
                halt_reason = str(halt["value"])
                _validate_safe_reason(halt_reason)
                final_status = V4ShadowDecisionStatus.SHADOW_HALTED
                final_intent_digest = None
                final_reasons = (f"STICKY_HALT_{halt_reason}",)
            if proposed_status is V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING:
                count = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM decisions
                    WHERE trading_day_jst = ? AND status = ?
                    """,
                    (
                        trading_day_jst,
                        V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING.value,
                    ),
                ).fetchone()["count"]
                if halt is None and count >= 1:
                    final_status = V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
                    final_intent_digest = None
                    final_reasons = ("SHADOW_DAILY_ENTRY_CAP_REACHED",)
            connection.execute(
                """
                INSERT INTO decisions(
                    signal_fingerprint, cycle_ref, controller_digest,
                    trading_day_jst, status, intent_digest,
                    blocked_reasons_json, recorded_at_utc
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal_fingerprint,
                    cycle_ref,
                    controller_digest,
                    trading_day_jst,
                    final_status.value,
                    final_intent_digest,
                    json.dumps(final_reasons, separators=(",", ":")),
                    recorded_at_utc.astimezone(UTC).isoformat(),
                ),
            )
        return _StoredDecision(
            status=final_status,
            blocked_reasons=final_reasons,
            recorded=True,
        )


def run_v4_unattended_shadow_cycle_once(
    *,
    signal: FormalSignal,
    policy: V4GmoExecutionPolicy,
    snapshot: V4UnattendedShadowSnapshot,
    store: V4UnattendedShadowStore,
    lock_path: Path,
    now_utc: datetime,
) -> V4ShadowControllerReport:
    """Evaluate and durably record one non-authorizing shadow cycle."""

    if now_utc.tzinfo is None:
        raise V4UnattendedShadowError("SHADOW_CLOCK_INVALID")
    if (
        type(signal) is not FormalSignal
        or type(policy) is not V4GmoExecutionPolicy
        or type(snapshot) is not V4UnattendedShadowSnapshot
        or type(store) is not V4UnattendedShadowStore
    ):
        raise V4UnattendedShadowError("SHADOW_INPUT_TYPE_INVALID")
    lock_resolved = lock_path.resolve()
    root = _SHADOW_EXPORT_ROOT.resolve()
    if lock_resolved == root or not lock_resolved.is_relative_to(root):
        raise V4UnattendedShadowError("SHADOW_LOCK_PATH_OUTSIDE_EXPORT_ROOT")
    if store.path.resolve() == lock_path.resolve():
        raise V4UnattendedShadowError("SHADOW_PATHS_MUST_BE_SEPARATE")
    controller_digest = v4_unattended_shadow_controller_digest(policy=policy)
    cycle_ref = _build_shadow_cycle_ref(signal=signal, policy=policy)
    lock = H11AutoProcessLock(lock_path)
    if not lock.acquire():
        return V4ShadowControllerReport(
            status=V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
            cycle_ref=cycle_ref,
            signal_fingerprint=signal.fingerprint,
            blocked_reasons=("SHADOW_PROCESS_LOCK_HELD",),
            recorded=False,
            shadow_intent=None,
        )
    try:
        store.bind_controller(controller_digest=controller_digest)
        reasons = _blocked_reasons(
            signal=signal,
            policy=policy,
            snapshot=snapshot,
            now_utc=now_utc,
        )
        if reasons:
            proposed_status = V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
        elif signal.decision is SignalDecision.STAY:
            proposed_status = V4ShadowDecisionStatus.SHADOW_NO_ACTION_STAY
        else:
            proposed_status = (
                V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
            )
        intent = (
            V4ShadowEntryIntent(
                cycle_ref=cycle_ref,
                signal_fingerprint=signal.fingerprint,
                policy_config_hash=policy.config_hash,
                side=signal.decision,
                symbol=V4_UNATTENDED_SHADOW_SYMBOL,
                size=policy.requested_size,
                execution_type=V4_UNATTENDED_SHADOW_EXECUTION_TYPE,
                frozen_atr_24=snapshot.frozen_atr_24,
                planned_loss_bound_jpy=snapshot.planned_loss_bound_jpy,
            )
            if proposed_status
            is V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
            else None
        )
        stored = store.record_once(
            signal_fingerprint=signal.fingerprint,
            cycle_ref=cycle_ref,
            controller_digest=controller_digest,
            trading_day_jst=now_utc.astimezone(_JST).date().isoformat(),
            proposed_status=proposed_status,
            intent_digest=None if intent is None else intent.digest,
            blocked_reasons=reasons,
            recorded_at_utc=now_utc,
        )
        if (
            stored.status
            is not V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
        ):
            intent = None
        return V4ShadowControllerReport(
            status=stored.status,
            cycle_ref=cycle_ref,
            signal_fingerprint=signal.fingerprint,
            blocked_reasons=stored.blocked_reasons,
            recorded=stored.recorded,
            shadow_intent=intent,
        )
    finally:
        lock.release()


def v4_unattended_shadow_controller_digest(
    *, policy: V4GmoExecutionPolicy
) -> str:
    payload = {
        "schema": V4_UNATTENDED_SHADOW_SCHEMA,
        "policy_config_hash": policy.config_hash,
        "symbol": V4_UNATTENDED_SHADOW_SYMBOL,
        "size": 1_000,
        "execution_type": V4_UNATTENDED_SHADOW_EXECUTION_TYPE,
        "maximum_entries_per_day": 1,
        "maximum_signal_age_seconds": "120",
        "maximum_quote_age_seconds": "5",
        "maximum_spread_pips": "2.0",
        "maximum_reference_deviation_pips": "5.0",
        "broker_post_authorized": False,
        "live_ready": False,
        "unattended_live_supported": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _blocked_reasons(
    *,
    signal: FormalSignal,
    policy: V4GmoExecutionPolicy,
    snapshot: V4UnattendedShadowSnapshot,
    now_utc: datetime,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        policy.strategy_version != "SHORT_V1"
        or policy.signal_config_hash
        != V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH
        or policy.selected_horizon is not FormalHorizon.MINUTES_30
        or policy.requested_size != 1_000
        or policy.protection_contract_hash
        != H11_V4_GMO_PROTECTION_CONTRACT_HASH
        or policy.max_loss_per_trade_yen != 5_000
    ):
        reasons.append("CONTROLLER_POLICY_NOT_FROZEN")
    identity_matches = (
        signal.strategy_version == policy.strategy_version
        and signal.signal_config_hash == policy.signal_config_hash
        and signal.horizon is policy.selected_horizon
    )
    if not identity_matches:
        reasons.append("SIGNAL_POLICY_MISMATCH")
    age_seconds = (
        now_utc.astimezone(UTC) - signal.observed_at_utc.astimezone(UTC)
    ).total_seconds()
    age = Decimal(str(age_seconds))
    if age < Decimal("-5") or age > V4_UNATTENDED_SHADOW_MAX_SIGNAL_AGE_SECONDS:
        reasons.append("SIGNAL_AGE_OUT_OF_RANGE")
    if now_utc >= signal.valid_until_utc:
        reasons.append("SIGNAL_EXPIRED")
    if signal.decision not in (
        SignalDecision.BUY,
        SignalDecision.SELL,
        SignalDecision.STAY,
    ):
        reasons.append("SIGNAL_DECISION_INVALID")
    if not policy.entry_time_allowed(now_utc=now_utc):
        reasons.append("ENTRY_TIME_NOT_ALLOWED")
    reasons.extend(snapshot.preflight.blocked_reasons())
    checks = (
        (snapshot.market_open, "MARKET_NOT_OPEN"),
        (
            Decimal("-5")
            <= snapshot.quote_age_seconds
            <= V4_UNATTENDED_SHADOW_MAX_QUOTE_AGE_SECONDS,
            "QUOTE_AGE_OUT_OF_RANGE",
        ),
        (
            snapshot.spread_pips <= V4_UNATTENDED_SHADOW_MAX_SPREAD_PIPS,
            "SPREAD_LIMIT_EXCEEDED",
        ),
        (
            abs(snapshot.reference_deviation_pips)
            <= V4_UNATTENDED_SHADOW_MAX_REFERENCE_DEVIATION_PIPS,
            "REFERENCE_DEVIATION_LIMIT_EXCEEDED",
        ),
        (
            snapshot.planned_loss_bound_jpy <= policy.max_loss_per_trade_yen,
            "PLANNED_LOSS_LIMIT_EXCEEDED",
        ),
    )
    reasons.extend(reason for passed, reason in checks if not passed)
    return tuple(dict.fromkeys(reasons))


def _build_shadow_cycle_ref(
    *, signal: FormalSignal, policy: V4GmoExecutionPolicy
) -> str:
    canonical = "|".join(
        (
            V4_UNATTENDED_SHADOW_SCHEMA,
            policy.config_hash,
            signal.fingerprint,
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_safe_reason(reason: str) -> None:
    if (
        not isinstance(reason, str)
        or not reason
        or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for character in reason)
    ):
        raise V4UnattendedShadowError("SHADOW_REASON_INVALID")


def _is_hex_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_prefixed_hex_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and _is_hex_digest(value.removeprefix("sha256:"))
    )
