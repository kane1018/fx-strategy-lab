"""Persistent pre-canary coordinator for H-11 GMO relaxed v4.

The coordinator stops before transport.  It freezes the signal ATR, rejects a
planned loss above the operator limit, persists the MARKET attempt before any
future transport call, and persists the exact OCO plan before any protection
call.  No credential, network client, activation permit, or broker method is
imported here.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path

from app.h11_auto.contracts import FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_contracts import (
    V4GmoAction,
    V4GmoActionPlan,
    V4GmoBrokerSnapshot,
    V4GmoEntryStatus,
    V4GmoExecutionPolicy,
    V4GmoProtectionStatus,
    v4_gmo_scheduled_time_exit_at,
)
from app.h11_auto.v4_gmo_generation import V4GmoFrozenGeneration
from app.h11_auto.v4_gmo_persisted_authorization import (
    V4PersistedActionAuthorization,
    _issue_persisted_action_authorization,
    persisted_plan_digest,
)
from app.h11_auto.v4_gmo_protection import (
    V4GmoExactProtectionPlan,
    build_exact_fill_oco_plan_no_post,
)

V4_GMO_ACTUAL_COORDINATOR_SCHEMA = "H11_V4_GMO_ACTUAL_COORDINATOR_PRECANARY_V4"
V4_ENTRY_PREFLIGHT_MAX_AGE_SECONDS = 2.0
V4_CLOCK_STATUS_REQUIRED = "NETWORK_TIME_ENABLED_VERIFIED"
V4_NOTIFICATION_STATUS_REQUIRED = "PUSHOVER_ACK_AND_EMAIL_RECEIVED"
V4_ACCOUNT_EXCLUSIVITY_REQUIRED = "H11_V4_ACCOUNT_EXCLUSIVE_CURRENT_GENERATION"
_ENTRY_PREFLIGHT_ISSUER_TOKEN = object()


class V4GmoActualCoordinatorError(RuntimeError):
    """Fixed safe coordinator failure."""


@dataclass(frozen=True)
class V4FrozenSignalRisk:
    signal_fingerprint: str
    atr_24: str
    atr_digest: str
    adverse_slippage_allowance_pips: str
    planned_loss_bound_jpy: int

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4PreparedAttempt:
    cycle_ref: str
    action: str
    attempted_at_utc: str
    authorization: V4PersistedActionAuthorization
    transport_called: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4PendingTransportRecovery:
    cycle_ref: str
    previous_action: str
    classification: str
    reconciliation_digest: str
    pending_marker_cleared: bool
    unknown_halt_remains_latched: bool = True

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4CanaryEntryPreflightEvidence:
    """Exact sanitized facts required immediately before a MARKET attempt."""

    generation_digest: str
    cycle_ref: str
    signal_fingerprint: str
    clock_status_label: str
    notification_status_label: str
    account_exclusivity_label: str
    unowned_position_count: int
    active_order_count: int
    unowned_active_order_count: int

    def __post_init__(self) -> None:
        counts = (
            self.unowned_position_count,
            self.active_order_count,
            self.unowned_active_order_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise V4GmoActualCoordinatorError("v4 entry preflight evidence is invalid")

    def __bool__(self) -> bool:
        return False


class _V4VerifiedEntryPreflightAuthorization:
    """One-use capability minted only by the coordinated actual path."""

    __slots__ = (
        "_token",
        "_cycle_ref",
        "_signal_fingerprint",
        "_preflight_digest",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        cycle_ref: str,
        signal_fingerprint: str,
        preflight_digest: str,
    ) -> None:
        if token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 entry issuer is invalid")
        self._token = token
        self._cycle_ref = cycle_ref
        self._signal_fingerprint = signal_fingerprint
        self._preflight_digest = preflight_digest
        self._consumed = False

    def __repr__(self) -> str:
        return "_V4VerifiedEntryPreflightAuthorization(<redacted-one-use>)"

    def __bool__(self) -> bool:
        return False


class V4GmoActualCoordinatorStore:
    """Dedicated exact-once ledger; separate from fake runtime state."""

    def __init__(self, path: Path) -> None:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise V4GmoActualCoordinatorError("v4 coordinator path is invalid")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cycles(
                    cycle_ref TEXT PRIMARY KEY,
                    signal_fingerprint TEXT NOT NULL UNIQUE,
                    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
                    requested_size INTEGER NOT NULL,
                    frozen_atr_24 TEXT NOT NULL,
                    frozen_atr_digest TEXT NOT NULL,
                    probability_up TEXT NOT NULL,
                    planned_loss_bound_jpy INTEGER NOT NULL,
                    signal_valid_until_utc TEXT NOT NULL,
                    instruction_bid TEXT,
                    instruction_ask TEXT,
                    entry_average_fill_price TEXT,
                    entry_spread_pips TEXT,
                    entry_slippage_pips TEXT,
                    realized_pnl_jpy INTEGER,
                    net_pips TEXT,
                    trade_won INTEGER CHECK(trade_won IN (0, 1)),
                    protection_plan_digest TEXT,
                    protection_plan_json TEXT,
                    settlement_expected_size INTEGER,
                    market_attempted_at_utc TEXT,
                    market_attempted_monotonic REAL,
                    entry_preflight_json TEXT,
                    entry_preflight_digest TEXT,
                    entry_preflight_at_utc TEXT,
                    entry_preflight_monotonic REAL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts(
                    cycle_ref TEXT NOT NULL,
                    action TEXT NOT NULL,
                    attempted_at_utc TEXT NOT NULL,
                    plan_digest TEXT NOT NULL,
                    reconciliation_digest TEXT,
                    PRIMARY KEY(cycle_ref, action),
                    FOREIGN KEY(cycle_ref) REFERENCES cycles(cycle_ref)
                );
                """
            )
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.executemany(
                    "INSERT INTO metadata(key,value) VALUES(?,?)",
                    (
                        ("schema_version", V4_GMO_ACTUAL_COORDINATOR_SCHEMA),
                        ("actual_post_allowed", "false"),
                    ),
                )
            elif row["value"] != V4_GMO_ACTUAL_COORDINATOR_SCHEMA:
                raise V4GmoActualCoordinatorError("v4 coordinator schema mismatch")
            pending = connection.execute(
                "SELECT value FROM metadata WHERE key='pending_transport_attempt'"
            ).fetchone()
            if pending is not None:
                connection.execute(
                    "INSERT INTO metadata(key,value) VALUES('unknown_halt_latched','true') "
                    "ON CONFLICT(key) DO UPDATE SET value='true'"
                )

    def bind_generation(self, generation: V4GmoFrozenGeneration) -> None:
        values = {
            "generation_digest": generation.digest,
            "generation_manifest": generation.canonical_json,
            "implementation_digest": generation.implementation_digest,
            "operator_selection_digest": generation.operator_selection_digest,
            "policy_config_hash": generation.policy_config_hash,
            "risk_policy_digest": generation.risk_policy_digest,
            "dead_man_policy_digest": generation.dead_man_policy_digest,
        }
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT key,value FROM metadata WHERE key IN "
                "('generation_digest','generation_manifest','implementation_digest',"
                "'operator_selection_digest','policy_config_hash','risk_policy_digest',"
                "'dead_man_policy_digest')"
            ).fetchall()
            if not existing:
                connection.executemany(
                    "INSERT INTO metadata(key,value) VALUES(?,?)", values.items()
                )
            elif dict(existing) != values:
                raise V4GmoActualCoordinatorError("v4 generation binding mismatch")

    def prepare_entry_intent(
        self,
        *,
        generation: V4GmoFrozenGeneration,
        signal: FormalSignal,
        policy: V4GmoExecutionPolicy,
        frozen_atr_24: Decimal,
        now_utc: datetime,
    ) -> V4FrozenSignalRisk:
        self.bind_generation(generation)
        if self.unknown_halt_latched():
            raise V4GmoActualCoordinatorError("v4 unknown halt is latched")
        if now_utc.tzinfo is None or now_utc >= signal.valid_until_utc:
            raise V4GmoActualCoordinatorError("v4 signal time is invalid")
        if not policy.accepts(signal):
            raise V4GmoActualCoordinatorError("v4 signal contract mismatch")
        if policy.config_hash != generation.policy_config_hash:
            raise V4GmoActualCoordinatorError("v4 policy generation mismatch")
        if signal.decision not in (SignalDecision.BUY, SignalDecision.SELL):
            raise V4GmoActualCoordinatorError("v4 directional signal required")
        risk = calculate_v4_planned_loss(
            signal_fingerprint=signal.fingerprint,
            frozen_atr_24=frozen_atr_24,
            quantity_units=policy.requested_size,
            adverse_slippage_allowance_pips=Decimal(
                generation.adverse_slippage_allowance_pips
            ),
        )
        if risk.planned_loss_bound_jpy > policy.max_loss_per_trade_yen:
            raise V4GmoActualCoordinatorError("v4 planned loss exceeds operator limit")
        cycle_ref = _cycle_ref(generation.digest, signal.fingerprint)
        timestamp = _timestamp(now_utc)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM cycles LIMIT 1").fetchone() is not None:
                    raise V4GmoActualCoordinatorError(
                        "v4 initial canary already has a cycle"
                    )
                connection.execute(
                    """
                    INSERT INTO cycles(
                        cycle_ref,signal_fingerprint,side,requested_size,
                        frozen_atr_24,frozen_atr_digest,probability_up,
                        planned_loss_bound_jpy,signal_valid_until_utc,created_at_utc
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        cycle_ref,
                        signal.fingerprint,
                        signal.decision.value,
                        policy.requested_size,
                        risk.atr_24,
                        risk.atr_digest,
                        format(signal.probability_up.normalize(), "f"),
                        risk.planned_loss_bound_jpy,
                        _timestamp(signal.valid_until_utc),
                        timestamp,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise V4GmoActualCoordinatorError("duplicate v4 entry intent refused") from error
        return risk

    def _record_entry_preflight_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        evidence: V4CanaryEntryPreflightEvidence,
        snapshot: V4GmoBrokerSnapshot,
        position_bundle_present: bool,
        average_fill_price_present: bool,
        instruction_bid: Decimal,
        instruction_ask: Decimal,
        authoritative_reconciliation_digest: str,
        now_utc: datetime,
        now_monotonic: float,
    ) -> _V4VerifiedEntryPreflightAuthorization:
        """Persist exact flat/account facts for the current canary generation."""

        if issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 entry issuer is invalid")
        _require_monotonic(now_monotonic)
        if (
            not isinstance(instruction_bid, Decimal)
            or not isinstance(instruction_ask, Decimal)
            or not instruction_bid.is_finite()
            or not instruction_ask.is_finite()
            or instruction_bid <= 0
            or instruction_ask < instruction_bid
        ):
            raise V4GmoActualCoordinatorError(
                "v4 entry reference quote is invalid"
            )
        timestamp = _timestamp(now_utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            generation = connection.execute(
                "SELECT value FROM metadata WHERE key='generation_digest'"
            ).fetchone()
            row = connection.execute(
                "SELECT cycle_ref,signal_fingerprint,signal_valid_until_utc "
                "FROM cycles WHERE cycle_ref=?",
                (evidence.cycle_ref,),
            ).fetchone()
            valid = (
                generation is not None
                and row is not None
                and generation["value"] == evidence.generation_digest
                and row["signal_fingerprint"] == evidence.signal_fingerprint
                and now_utc.astimezone(UTC)
                < datetime.fromisoformat(str(row["signal_valid_until_utc"])).astimezone(UTC)
                and snapshot.fresh is True
                and snapshot.result_known is True
                and snapshot.position_count == 0
                and snapshot.position_side is None
                and snapshot.filled_size == 0
                and snapshot.pending_entry_size == 0
                and snapshot.protection_size == 0
                and snapshot.entry_status is V4GmoEntryStatus.NONE
                and snapshot.protection_status is V4GmoProtectionStatus.NONE
                and position_bundle_present is False
                and average_fill_price_present is False
                and evidence.clock_status_label == V4_CLOCK_STATUS_REQUIRED
                and evidence.notification_status_label
                == V4_NOTIFICATION_STATUS_REQUIRED
                and evidence.account_exclusivity_label
                == V4_ACCOUNT_EXCLUSIVITY_REQUIRED
                and evidence.unowned_position_count == 0
                and evidence.active_order_count == 0
                and evidence.unowned_active_order_count == 0
                and _valid_digest(authoritative_reconciliation_digest)
            )
            if not valid:
                raise V4GmoActualCoordinatorError("v4 entry preflight mismatch")
            payload = {
                "account_exclusivity_label": evidence.account_exclusivity_label,
                "clock_status_label": evidence.clock_status_label,
                "cycle_ref": evidence.cycle_ref,
                "generation_digest": evidence.generation_digest,
                "instruction_ask": format(instruction_ask.normalize(), "f"),
                "instruction_bid": format(instruction_bid.normalize(), "f"),
                "notification_status_label": evidence.notification_status_label,
                "signal_fingerprint": evidence.signal_fingerprint,
                "snapshot": {
                    "entry_status": snapshot.entry_status.value,
                    "filled_size": snapshot.filled_size,
                    "pending_entry_size": snapshot.pending_entry_size,
                    "position_count": snapshot.position_count,
                    "protection_size": snapshot.protection_size,
                    "protection_status": snapshot.protection_status.value,
                    "result_known": snapshot.result_known,
                },
                "unowned_position_count": evidence.unowned_position_count,
                "active_order_count": evidence.active_order_count,
                "unowned_active_order_count": evidence.unowned_active_order_count,
                "authoritative_reconciliation_digest": (
                    authoritative_reconciliation_digest
                ),
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
            cursor = connection.execute(
                "UPDATE cycles SET entry_preflight_json=?,entry_preflight_digest=?,"
                "entry_preflight_at_utc=?,entry_preflight_monotonic=?,"
                "instruction_bid=?,instruction_ask=? "
                "WHERE cycle_ref=? AND entry_preflight_digest IS NULL "
                "AND market_attempted_at_utc IS NULL",
                (
                    canonical,
                    digest,
                    timestamp,
                    now_monotonic,
                    format(instruction_bid.normalize(), "f"),
                    format(instruction_ask.normalize(), "f"),
                    evidence.cycle_ref,
                ),
            )
            if cursor.rowcount != 1:
                raise V4GmoActualCoordinatorError("second v4 entry preflight refused")
        return _V4VerifiedEntryPreflightAuthorization(
            token=_ENTRY_PREFLIGHT_ISSUER_TOKEN,
            cycle_ref=evidence.cycle_ref,
            signal_fingerprint=evidence.signal_fingerprint,
            preflight_digest=digest,
        )

    def _record_market_attempt_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        entry_authorization: _V4VerifiedEntryPreflightAuthorization,
        signal_fingerprint: str,
        plan: V4GmoActionPlan,
        now_utc: datetime,
        now_monotonic: float,
    ) -> V4PreparedAttempt:
        if (
            issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN
            or type(entry_authorization)
            is not _V4VerifiedEntryPreflightAuthorization
            or entry_authorization._token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN
            or entry_authorization._consumed
            or entry_authorization._signal_fingerprint != signal_fingerprint
        ):
            raise V4GmoActualCoordinatorError("v4 entry issuer is invalid")
        if self.unknown_halt_latched():
            raise V4GmoActualCoordinatorError("v4 unknown halt is latched")
        _require_monotonic(now_monotonic)
        timestamp = _timestamp(now_utc)
        plan_digest = persisted_plan_digest(plan)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT cycle_ref,side,requested_size,signal_valid_until_utc,"
                    "entry_preflight_digest,entry_preflight_monotonic "
                    "FROM cycles WHERE signal_fingerprint=?",
                    (signal_fingerprint,),
                ).fetchone()
                if row is None:
                    raise V4GmoActualCoordinatorError("v4 entry intent is missing")
                cycle_ref = str(row["cycle_ref"])
                valid_until = datetime.fromisoformat(
                    str(row["signal_valid_until_utc"])
                )
                if (
                    plan.action is not V4GmoAction.MARKET_ENTRY
                    or plan.cycle_ref != cycle_ref
                    or plan.side.value != row["side"]
                    or plan.requested_size != row["requested_size"]
                    or now_utc.astimezone(UTC) >= valid_until.astimezone(UTC)
                    or row["entry_preflight_digest"] is None
                    or row["entry_preflight_digest"]
                    != entry_authorization._preflight_digest
                    or cycle_ref != entry_authorization._cycle_ref
                    or row["entry_preflight_monotonic"] is None
                    or not 0
                    <= now_monotonic - float(row["entry_preflight_monotonic"])
                    <= V4_ENTRY_PREFLIGHT_MAX_AGE_SECONDS
                ):
                    raise V4GmoActualCoordinatorError(
                        "v4 MARKET plan does not match persisted intent"
                    )
                connection.execute(
                    "INSERT INTO attempts(cycle_ref,action,attempted_at_utc,plan_digest) "
                    "VALUES(?, 'MARKET_ENTRY', ?, ?)",
                    (cycle_ref, timestamp, plan_digest),
                )
                self._mark_transport_pending(
                    connection,
                    cycle_ref=cycle_ref,
                    action=V4GmoAction.MARKET_ENTRY,
                )
                connection.execute(
                    "UPDATE cycles SET market_attempted_at_utc=?,"
                    "market_attempted_monotonic=? WHERE cycle_ref=?",
                    (timestamp, now_monotonic, cycle_ref),
                )
                entry_authorization._consumed = True
        except sqlite3.IntegrityError as error:
            raise V4GmoActualCoordinatorError(
                "second v4 MARKET attempt refused"
            ) from error
        return V4PreparedAttempt(
            cycle_ref=cycle_ref,
            action="MARKET_ENTRY",
            attempted_at_utc=timestamp,
            authorization=_issue_persisted_action_authorization(
                plan=plan,
                protection_plan_digest=None,
                reconciliation_digest=None,
                deadline_monotonic=None,
                verify_committed=self._committed_attempt_verifier(
                    cycle_ref=cycle_ref,
                    action=V4GmoAction.MARKET_ENTRY,
                    plan_digest=plan_digest,
                ),
            ),
        )

    def load_single_signal_fingerprint_internal(self) -> str:
        """Return the sole local signal hash for the finite KILL rehearsal."""

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT signal_fingerprint FROM cycles ORDER BY created_at_utc"
            ).fetchall()
        if len(rows) != 1:
            raise V4GmoActualCoordinatorError("v4 rehearsal cycle count mismatch")
        return str(rows[0]["signal_fingerprint"])

    def record_kill_rehearsal_pending_no_transport(self, *, cycle_ref: str) -> None:
        """Persist only a crash marker; never mint a transport authorization."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT 1 FROM cycles WHERE cycle_ref=?", (cycle_ref,)
            ).fetchone()
            halt = connection.execute(
                "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
            ).fetchone()
            if row is None or (halt is not None and halt["value"] == "true"):
                raise V4GmoActualCoordinatorError(
                    "v4 KILL rehearsal state mismatch"
                )
            self._mark_transport_pending(
                connection,
                cycle_ref=cycle_ref,
                action=V4GmoAction.MARKET_ENTRY,
            )

    def cycle_ref_for_signal_internal(self, signal_fingerprint: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cycle_ref FROM cycles WHERE signal_fingerprint=?",
                (signal_fingerprint,),
            ).fetchone()
        if row is None:
            raise V4GmoActualCoordinatorError("v4 entry intent is missing")
        return str(row["cycle_ref"])

    def side_for_signal_internal(self, signal_fingerprint: str) -> SignalDecision:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT side FROM cycles WHERE signal_fingerprint=?",
                (signal_fingerprint,),
            ).fetchone()
        if row is None:
            raise V4GmoActualCoordinatorError("v4 entry intent is missing")
        return SignalDecision(str(row["side"]))

    def expected_closed_size_for_signal_internal(
        self, signal_fingerprint: str
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT protection_plan_json,settlement_expected_size "
                "FROM cycles WHERE signal_fingerprint=?",
                (signal_fingerprint,),
            ).fetchone()
        if row is None:
            raise V4GmoActualCoordinatorError("v4 entry intent is missing")
        explicit = row["settlement_expected_size"]
        if explicit is not None:
            size = int(explicit)
        else:
            try:
                payload = json.loads(str(row["protection_plan_json"]))
                size = int(payload["exact_filled_size"])
            except (TypeError, KeyError, ValueError, json.JSONDecodeError) as error:
                raise V4GmoActualCoordinatorError(
                    "v4 settlement size is unavailable"
                ) from error
        if not 0 < size <= 10_000:
            raise V4GmoActualCoordinatorError("v4 settlement size is invalid")
        return size

    def _persist_exact_protection_plan_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        signal_fingerprint: str,
        reconciled_average_fill_price: Decimal,
        reconciled_filled_size: int,
        now_utc: datetime,
        now_monotonic: float,
    ) -> V4GmoExactProtectionPlan:
        if issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 protection issuer is invalid")
        _require_monotonic(now_monotonic)
        _timestamp(now_utc)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cycles WHERE signal_fingerprint=?",
                (signal_fingerprint,),
            ).fetchone()
        if row is None or row["market_attempted_at_utc"] is None:
            raise V4GmoActualCoordinatorError("v4 MARKET attempt is not persisted")
        attempted_monotonic = row["market_attempted_monotonic"]
        if attempted_monotonic is None:
            raise V4GmoActualCoordinatorError("v4 MARKET attempt is not persisted")
        elapsed = now_monotonic - float(attempted_monotonic)
        if not 0 <= elapsed <= 15:
            raise V4GmoActualCoordinatorError("v4 protection deadline exceeded")
        try:
            atr = Decimal(str(row["frozen_atr_24"]))
        except InvalidOperation as error:
            raise V4GmoActualCoordinatorError("v4 frozen ATR is invalid") from error
        expected_atr_digest = _atr_digest(
            signal_fingerprint=signal_fingerprint,
            canonical_atr=format(atr.normalize(), "f"),
        )
        if row["frozen_atr_digest"] != expected_atr_digest:
            raise V4GmoActualCoordinatorError("v4 frozen ATR digest mismatch")
        try:
            instruction_bid = Decimal(str(row["instruction_bid"]))
            instruction_ask = Decimal(str(row["instruction_ask"]))
        except (InvalidOperation, TypeError) as error:
            raise V4GmoActualCoordinatorError(
                "v4 entry reference quote is missing"
            ) from error
        if (
            not reconciled_average_fill_price.is_finite()
            or not instruction_bid.is_finite()
            or not instruction_ask.is_finite()
            or instruction_bid <= 0
            or instruction_ask < instruction_bid
        ):
            raise V4GmoActualCoordinatorError(
                "v4 entry execution metrics are invalid"
            )
        entry_spread_pips = (instruction_ask - instruction_bid) / Decimal("0.01")
        if SignalDecision(str(row["side"])) is SignalDecision.BUY:
            entry_slippage_pips = (
                reconciled_average_fill_price - instruction_ask
            ) / Decimal("0.01")
        else:
            entry_slippage_pips = (
                instruction_bid - reconciled_average_fill_price
            ) / Decimal("0.01")
        plan = build_exact_fill_oco_plan_no_post(
            position_side=SignalDecision(str(row["side"])),
            reconciled_average_fill_price=reconciled_average_fill_price,
            frozen_signal_atr_24=atr,
            reconciled_filled_size=reconciled_filled_size,
        )
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "UPDATE cycles SET protection_plan_digest=?, protection_plan_json=?,"
                    "entry_average_fill_price=?,entry_spread_pips=?,"
                    "entry_slippage_pips=? "
                    "WHERE cycle_ref=? AND protection_plan_digest IS NULL",
                    (
                        "sha256:" + plan.plan_digest,
                        plan.canonical_json,
                        format(reconciled_average_fill_price.normalize(), "f"),
                        format(entry_spread_pips.normalize(), "f"),
                        format(entry_slippage_pips.normalize(), "f"),
                        str(row["cycle_ref"]),
                    ),
                )
                if cursor.rowcount != 1:
                    raise V4GmoActualCoordinatorError(
                        "second v4 protection plan refused"
                    )
        except sqlite3.IntegrityError as error:
            raise V4GmoActualCoordinatorError(
                "second v4 protection plan refused"
            ) from error
        return plan

    def record_closed_metrics_once_internal(
        self,
        *,
        cycle_ref: str,
        realized_pnl_jpy: int,
    ) -> bool:
        """Persist sanitized trade-result metrics without exposing identifiers."""

        if type(realized_pnl_jpy) is not int:  # noqa: E721
            raise V4GmoActualCoordinatorError(
                "v4 realized pnl metric is invalid"
            )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT requested_size,realized_pnl_jpy,net_pips,trade_won "
                "FROM cycles WHERE cycle_ref=?",
                (cycle_ref,),
            ).fetchone()
            if row is None:
                raise V4GmoActualCoordinatorError("v4 cycle is unknown")
            requested_size = int(row["requested_size"])
            net_pips = Decimal(realized_pnl_jpy) / (
                Decimal(requested_size) * Decimal("0.01")
            )
            expected = (
                realized_pnl_jpy,
                format(net_pips.normalize(), "f"),
                int(realized_pnl_jpy > 0),
            )
            existing = (
                row["realized_pnl_jpy"],
                row["net_pips"],
                row["trade_won"],
            )
            if existing == expected:
                return False
            if existing != (None, None, None):
                raise V4GmoActualCoordinatorError(
                    "v4 closed metric mismatch"
                )
            cursor = connection.execute(
                "UPDATE cycles SET realized_pnl_jpy=?,net_pips=?,trade_won=? "
                "WHERE cycle_ref=? AND realized_pnl_jpy IS NULL",
                (*expected, cycle_ref),
            )
            if cursor.rowcount != 1:
                raise V4GmoActualCoordinatorError(
                    "v4 closed metric update refused"
                )
        return True

    def _record_exact_protection_attempt_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        signal_fingerprint: str,
        plan: V4GmoActionPlan,
        protection_plan: V4GmoExactProtectionPlan,
        reconciliation_digest: str,
        now_utc: datetime,
        now_monotonic: float,
    ) -> V4PreparedAttempt:
        if issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 protection issuer is invalid")
        timestamp = _timestamp(now_utc)
        _require_monotonic(now_monotonic)
        expected_digest = "sha256:" + protection_plan.plan_digest
        action_plan_digest = persisted_plan_digest(plan)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                halt = connection.execute(
                    "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
                ).fetchone()
                if (
                    halt is not None
                    and halt["value"] == "true"
                    and not self._recovery_allows_action(
                        connection,
                        cycle_ref=plan.cycle_ref,
                        action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
                    )
                ):
                    raise V4GmoActualCoordinatorError("v4 unknown halt is latched")
                row = connection.execute(
                    "SELECT cycle_ref,side,requested_size,protection_plan_digest,"
                    "protection_plan_json,"
                    "market_attempted_monotonic "
                    "FROM cycles "
                    "WHERE signal_fingerprint=?",
                    (signal_fingerprint,),
                ).fetchone()
                if (
                    row is None
                    or row["protection_plan_digest"] != expected_digest
                    or row["protection_plan_json"] != protection_plan.canonical_json
                    or plan.action is not V4GmoAction.EXACT_SIZE_OCO_PROTECTION
                    or plan.cycle_ref != row["cycle_ref"]
                    or plan.side.value != row["side"]
                    or plan.requested_size != protection_plan.exact_filled_size
                    or not 0 < plan.requested_size <= row["requested_size"]
                    or plan.protection_contract_hash != protection_plan.contract_hash
                    or not _valid_digest(reconciliation_digest)
                ):
                    raise V4GmoActualCoordinatorError(
                        "v4 persisted protection plan mismatch"
                    )
                market_attempted_monotonic = row["market_attempted_monotonic"]
                if market_attempted_monotonic is None:
                    raise V4GmoActualCoordinatorError(
                        "v4 MARKET attempt is not persisted"
                    )
                elapsed = now_monotonic - float(market_attempted_monotonic)
                if not 0 <= elapsed <= 15:
                    raise V4GmoActualCoordinatorError(
                        "v4 protection deadline exceeded"
                    )
                cycle_ref = str(row["cycle_ref"])
                connection.execute(
                    "INSERT INTO attempts(cycle_ref,action,attempted_at_utc,plan_digest,"
                    "reconciliation_digest) VALUES(?, 'EXACT_SIZE_OCO_PROTECTION', ?, ?, ?)",
                    (cycle_ref, timestamp, action_plan_digest, reconciliation_digest),
                )
                self._mark_transport_pending(
                    connection,
                    cycle_ref=cycle_ref,
                    action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
                )
        except sqlite3.IntegrityError as error:
            raise V4GmoActualCoordinatorError(
                "second v4 protection attempt refused"
            ) from error
        return V4PreparedAttempt(
            cycle_ref=cycle_ref,
            action="EXACT_SIZE_OCO_PROTECTION",
            attempted_at_utc=timestamp,
            authorization=_issue_persisted_action_authorization(
                plan=plan,
                protection_plan_digest=expected_digest,
                reconciliation_digest=reconciliation_digest,
                deadline_monotonic=float(market_attempted_monotonic) + 15.0,
                verify_committed=self._committed_attempt_verifier(
                    cycle_ref=cycle_ref,
                    action=V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
                    plan_digest=action_plan_digest,
                    protection_plan_digest=expected_digest,
                    reconciliation_digest=reconciliation_digest,
                ),
            ),
        )

    def _record_risk_reducing_attempt_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        signal_fingerprint: str,
        plan: V4GmoActionPlan,
        snapshot: V4GmoBrokerSnapshot,
        position_bundle_total: int | None,
        authoritative_reconciliation_digest: str,
        now_utc: datetime,
    ) -> V4PreparedAttempt:
        """Persist one cancel/emergency-exit action before future transport."""

        if issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 risk action issuer is invalid")

        action = plan.action
        if action not in {
            V4GmoAction.CANCEL_ENTRY_REMAINDER,
            V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
            V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
            V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
        }:
            raise V4GmoActualCoordinatorError(
                "v4 risk-reducing action is invalid"
            )
        if snapshot.fresh is not True or snapshot.result_known is not True:
            raise V4GmoActualCoordinatorError("v4 risk-reducing state is unknown")
        timestamp = _timestamp(now_utc)
        plan_digest = persisted_plan_digest(plan)
        if not _valid_digest(authoritative_reconciliation_digest):
            raise V4GmoActualCoordinatorError(
                "v4 authoritative reconciliation digest is invalid"
            )
        reconciliation_digest = authoritative_reconciliation_digest
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT cycle_ref,side,market_attempted_at_utc FROM cycles "
                    "WHERE signal_fingerprint=?",
                    (signal_fingerprint,),
                ).fetchone()
                if row is None or row["market_attempted_at_utc"] is None:
                    raise V4GmoActualCoordinatorError(
                        "v4 MARKET attempt is not persisted"
                    )
                cycle_ref = str(row["cycle_ref"])
                if plan.cycle_ref != cycle_ref or plan.side.value != row["side"]:
                    raise V4GmoActualCoordinatorError(
                        "v4 risk-reducing plan mismatch"
                    )
                halt = connection.execute(
                    "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
                ).fetchone()
                if (
                    halt is not None
                    and halt["value"] == "true"
                    and not self._recovery_allows_action(
                        connection,
                        cycle_ref=cycle_ref,
                        action=action,
                    )
                ):
                    raise V4GmoActualCoordinatorError(
                        "v4 unknown halt risk action mismatch"
                    )
                if action is V4GmoAction.CANCEL_ENTRY_REMAINDER:
                    valid_state = (
                        snapshot.pending_entry_size > 0
                        and snapshot.position_count <= 1
                        and plan.requested_size == snapshot.pending_entry_size
                    )
                elif action is V4GmoAction.CANCEL_MISMATCHED_PROTECTION:
                    valid_state = (
                        snapshot.position_count == 1
                        and snapshot.filled_size > 0
                        and snapshot.protection_size > 0
                        and snapshot.protection_status
                        in {
                            V4GmoProtectionStatus.UNDERSIZED,
                            V4GmoProtectionStatus.OVERSIZED,
                        }
                        and plan.requested_size == snapshot.protection_size
                    )
                elif action in {
                    V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
                    V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
                }:
                    valid_state = (
                        snapshot.position_count == 1
                        and snapshot.position_side is SignalDecision(str(row["side"]))
                        and snapshot.filled_size > 0
                        and snapshot.pending_entry_size == 0
                        and snapshot.entry_status is V4GmoEntryStatus.FILLED
                        and snapshot.protection_size == 0
                        and position_bundle_total == snapshot.filled_size
                        and plan.requested_size == snapshot.filled_size
                    )
                else:
                    valid_state = (
                        snapshot.position_count == 1
                        and snapshot.position_side is SignalDecision(str(row["side"]))
                        and snapshot.filled_size > 0
                        and snapshot.pending_entry_size == 0
                        and snapshot.entry_status is V4GmoEntryStatus.FILLED
                        and snapshot.protection_size == snapshot.filled_size
                        and snapshot.protection_status
                        is V4GmoProtectionStatus.EXACT_MATCH
                        and position_bundle_total == snapshot.filled_size
                        and plan.requested_size == snapshot.protection_size
                    )
                if action in {
                    V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
                    V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
                }:
                    attempted_at = datetime.fromisoformat(
                        str(row["market_attempted_at_utc"])
                    ).astimezone(UTC)
                    scheduled_exit = v4_gmo_scheduled_time_exit_at(
                        entry_time_utc=attempted_at
                    )
                    if (
                        scheduled_exit is None
                        or now_utc.astimezone(UTC) < scheduled_exit
                    ):
                        valid_state = False
                if not valid_state:
                    raise V4GmoActualCoordinatorError(
                        "v4 risk-reducing state mismatch"
                    )
                if action in {
                    V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
                    V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
                }:
                    cursor = connection.execute(
                        "UPDATE cycles SET settlement_expected_size=? "
                        "WHERE cycle_ref=? AND "
                        "(settlement_expected_size IS NULL OR "
                        "settlement_expected_size=?)",
                        (plan.requested_size, cycle_ref, plan.requested_size),
                    )
                    if cursor.rowcount != 1:
                        raise V4GmoActualCoordinatorError(
                            "v4 settlement size mismatch"
                        )
                connection.execute(
                    "INSERT INTO attempts(cycle_ref,action,attempted_at_utc,"
                    "plan_digest,reconciliation_digest) VALUES(?,?,?,?,?)",
                    (
                        cycle_ref,
                        action.value,
                        timestamp,
                        plan_digest,
                        reconciliation_digest,
                    ),
                )
                self._mark_transport_pending(
                    connection,
                    cycle_ref=cycle_ref,
                    action=action,
                )
        except sqlite3.IntegrityError as error:
            raise V4GmoActualCoordinatorError(
                "second v4 risk-reducing attempt refused"
            ) from error
        return V4PreparedAttempt(
            cycle_ref=cycle_ref,
            action=action.value,
            attempted_at_utc=timestamp,
            authorization=_issue_persisted_action_authorization(
                plan=plan,
                protection_plan_digest=None,
                reconciliation_digest=reconciliation_digest,
                deadline_monotonic=None,
                verify_committed=self._committed_attempt_verifier(
                    cycle_ref=cycle_ref,
                    action=action,
                    plan_digest=plan_digest,
                    reconciliation_digest=reconciliation_digest,
                ),
            ),
        )

    def _committed_attempt_verifier(
        self,
        *,
        cycle_ref: str,
        action: V4GmoAction,
        plan_digest: str,
        protection_plan_digest: str | None = None,
        reconciliation_digest: str | None = None,
    ) -> Callable[[], bool]:
        """Build a one-purpose verifier that re-reads the committed DB row."""

        database_path = self.path
        with self._connect() as connection:
            generation_row = connection.execute(
                "SELECT value FROM metadata WHERE key='generation_digest'"
            ).fetchone()
        if generation_row is None:
            raise V4GmoActualCoordinatorError("v4 generation binding is missing")
        expected_generation_digest = str(generation_row["value"])

        def verify() -> bool:
            try:
                with sqlite3.connect(database_path, timeout=5.0) as connection:
                    connection.row_factory = sqlite3.Row
                    row = connection.execute(
                        "SELECT plan_digest,reconciliation_digest FROM attempts "
                        "WHERE cycle_ref=? AND action=?",
                        (cycle_ref, action.value),
                    ).fetchone()
                    cycle = connection.execute(
                        "SELECT protection_plan_digest,entry_preflight_digest "
                        "FROM cycles WHERE cycle_ref=?",
                        (cycle_ref,),
                    ).fetchone()
                    generation = connection.execute(
                        "SELECT value FROM metadata WHERE key='generation_digest'"
                    ).fetchone()
                    halt = connection.execute(
                        "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
                    ).fetchone()
                    pending = connection.execute(
                        "SELECT value FROM metadata "
                        "WHERE key='pending_transport_attempt'"
                    ).fetchone()
                    recovery = connection.execute(
                        "SELECT value FROM metadata "
                        "WHERE key='pending_transport_resolution'"
                    ).fetchone()
            except sqlite3.Error:
                return False
            if (
                row is None
                or row["plan_digest"] != plan_digest
                or row["reconciliation_digest"] != reconciliation_digest
                or generation is None
                or generation["value"] != expected_generation_digest
                or pending is None
                or pending["value"]
                != json.dumps(
                    {"action": action.value, "cycle_ref": cycle_ref},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ):
                return False
            if halt is not None and halt["value"] == "true":
                if action is V4GmoAction.MARKET_ENTRY:
                    return False
                if recovery is None or not self._recovery_value_allows_action(
                    str(recovery["value"]),
                    cycle_ref=cycle_ref,
                    action=action,
                ):
                    return False
            if action is V4GmoAction.MARKET_ENTRY and (
                cycle is None or cycle["entry_preflight_digest"] is None
            ):
                return False
            if protection_plan_digest is not None:
                return (
                    cycle is not None
                    and cycle["protection_plan_digest"] == protection_plan_digest
                )
            return cycle is not None

        return verify

    @staticmethod
    def _recovery_allows_action(
        connection: sqlite3.Connection,
        *,
        cycle_ref: str,
        action: V4GmoAction,
    ) -> bool:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key='pending_transport_resolution'"
        ).fetchone()
        if row is None:
            return False
        return V4GmoActualCoordinatorStore._recovery_value_allows_action(
            str(row["value"]),
            cycle_ref=cycle_ref,
            action=action,
        )

    @staticmethod
    def _recovery_value_allows_action(
        value: str,
        *,
        cycle_ref: str,
        action: V4GmoAction,
    ) -> bool:
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return False
        if not isinstance(payload, dict) or payload.get("cycle_ref") != cycle_ref:
            return False
        classification = payload.get("classification")
        allowed = {
            "MARKET_PARTIAL_PENDING": {
                V4GmoAction.CANCEL_ENTRY_REMAINDER,
            },
            "FILLED_UNPROTECTED": {
                V4GmoAction.EXACT_SIZE_OCO_PROTECTION,
                V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
                V4GmoAction.POSITION_SPECIFIC_TIME_EXIT,
            },
            "FILLED_PROTECTION_MISMATCHED": {
                V4GmoAction.CANCEL_MISMATCHED_PROTECTION,
                V4GmoAction.POSITION_SPECIFIC_EMERGENCY_EXIT,
            },
            "FILLED_PROTECTED": {
                V4GmoAction.CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT,
            },
        }
        return action in allowed.get(str(classification), set())

    @staticmethod
    def _mark_transport_pending(
        connection: sqlite3.Connection,
        *,
        cycle_ref: str,
        action: V4GmoAction,
    ) -> None:
        payload = json.dumps(
            {"action": action.value, "cycle_ref": cycle_ref},
            sort_keys=True,
            separators=(",", ":"),
        )
        existing = connection.execute(
            "SELECT 1 FROM metadata WHERE key='pending_transport_attempt'"
        ).fetchone()
        if existing is not None:
            raise V4GmoActualCoordinatorError(
                "v4 pending transport requires operator review"
            )
        connection.execute(
            "INSERT INTO metadata(key,value) VALUES('pending_transport_attempt',?)",
            (payload,),
        )

    def _record_transport_outcome_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        cycle_ref: str,
        action: V4GmoAction,
        outcome_label: str,
    ) -> None:
        if issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 outcome issuer is invalid")
        if outcome_label not in {
            "ACCEPTED_SANITIZED",
            "REJECTED_SANITIZED",
            "UNKNOWN_SANITIZED",
        }:
            raise V4GmoActualCoordinatorError("v4 transport outcome is invalid")
        expected = json.dumps(
            {"action": action.value, "cycle_ref": cycle_ref},
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='pending_transport_attempt'"
            ).fetchone()
            if row is None or row["value"] != expected:
                raise V4GmoActualCoordinatorError(
                    "v4 pending transport state mismatch"
                )
            if outcome_label == "REJECTED_SANITIZED":
                connection.execute(
                    "DELETE FROM metadata WHERE key='pending_transport_attempt'"
                )
            else:
                # ACCEPTED still requires fresh authoritative reconciliation;
                # UNKNOWN is likewise unresolved.  Keep the exact pending
                # marker for crash recovery and block MARKET reauthorization.
                connection.execute(
                    "INSERT INTO metadata(key,value) VALUES('unknown_halt_latched','true') "
                    "ON CONFLICT(key) DO UPDATE SET value='true'"
                )

    def _resolve_pending_transport_from_coordinated_path(
        self,
        *,
        issuer_token: object,
        cycle_ref: str,
        snapshot: V4GmoBrokerSnapshot,
        position_bundle_total: int | None,
        authoritative_reconciliation_digest: str,
        now_utc: datetime,
    ) -> V4PendingTransportRecovery:
        """Resolve one crashed transport marker from a fresh exact snapshot.

        The old attempt row is never removed, MARKET is never re-authorized,
        HALT remains latched, and an indeterminate snapshot leaves the pending
        marker untouched.
        """

        if issuer_token is not _ENTRY_PREFLIGHT_ISSUER_TOKEN:
            raise V4GmoActualCoordinatorError("v4 recovery issuer is invalid")
        if (
            snapshot.fresh is not True
            or snapshot.result_known is not True
            or not _valid_digest(authoritative_reconciliation_digest)
        ):
            raise V4GmoActualCoordinatorError(
                "v4 pending transport recovery remains unknown"
            )
        timestamp = _timestamp(now_utc)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending_row = connection.execute(
                "SELECT value FROM metadata WHERE key='pending_transport_attempt'"
            ).fetchone()
            halt = connection.execute(
                "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
            ).fetchone()
            cycle = connection.execute(
                "SELECT side FROM cycles WHERE cycle_ref=?", (cycle_ref,)
            ).fetchone()
            if pending_row is None or halt is None or halt["value"] != "true" or cycle is None:
                raise V4GmoActualCoordinatorError(
                    "v4 pending transport recovery state mismatch"
                )
            try:
                pending = json.loads(str(pending_row["value"]))
            except json.JSONDecodeError as error:
                raise V4GmoActualCoordinatorError(
                    "v4 pending transport recovery state mismatch"
                ) from error
            if (
                not isinstance(pending, dict)
                or pending.get("cycle_ref") != cycle_ref
                or pending.get("action") not in {action.value for action in V4GmoAction}
            ):
                raise V4GmoActualCoordinatorError(
                    "v4 pending transport recovery state mismatch"
                )
            classification = _classify_pending_transport_recovery(
                previous_action=str(pending["action"]),
                expected_side=SignalDecision(str(cycle["side"])),
                snapshot=snapshot,
                position_bundle_total=position_bundle_total,
            )
            if classification is None:
                raise V4GmoActualCoordinatorError(
                    "v4 pending transport recovery remains unknown"
                )
            resolution = json.dumps(
                {
                    "classification": classification,
                    "cycle_ref": cycle_ref,
                    "generation_digest": self._metadata_value(
                        connection, "generation_digest"
                    ),
                    "previous_action": pending["action"],
                    "reconciliation_digest": authoritative_reconciliation_digest,
                    "resolved_at_utc": timestamp,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            connection.execute(
                "INSERT INTO metadata(key,value) VALUES('pending_transport_resolution',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (resolution,),
            )
            connection.execute(
                "DELETE FROM metadata WHERE key='pending_transport_attempt'"
            )
        return V4PendingTransportRecovery(
            cycle_ref=cycle_ref,
            previous_action=str(pending["action"]),
            classification=classification,
            reconciliation_digest=authoritative_reconciliation_digest,
            pending_marker_cleared=True,
        )

    @staticmethod
    def _metadata_value(connection: sqlite3.Connection, key: str) -> str:
        row = connection.execute(
            "SELECT value FROM metadata WHERE key=?", (key,)
        ).fetchone()
        if row is None:
            raise V4GmoActualCoordinatorError("v4 generation binding is missing")
        return str(row["value"])

    def engage_unknown_halt(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO metadata(key,value) VALUES('unknown_halt_latched','true') "
                "ON CONFLICT(key) DO UPDATE SET value='true'"
            )

    def unknown_halt_latched(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
            ).fetchone()
        return row is not None and row["value"] == "true"

    def confirm_exact_protection_within_deadline(
        self,
        *,
        signal_fingerprint: str,
        confirmed_protection_size: int,
        now_utc: datetime,
        now_monotonic: float,
    ) -> None:
        timestamp = _timestamp(now_utc)
        _require_monotonic(now_monotonic)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT market_attempted_monotonic,protection_plan_json "
                "FROM cycles WHERE signal_fingerprint=?",
                (signal_fingerprint,),
            ).fetchone()
            if row is None or row["protection_plan_json"] is None:
                raise V4GmoActualCoordinatorError(
                    "v4 persisted protection plan mismatch"
                )
            attempted_monotonic = row["market_attempted_monotonic"]
            if attempted_monotonic is None:
                raise V4GmoActualCoordinatorError(
                    "v4 MARKET attempt is not persisted"
                )
            elapsed = now_monotonic - float(attempted_monotonic)
            try:
                plan_payload = json.loads(str(row["protection_plan_json"]))
            except json.JSONDecodeError as error:
                raise V4GmoActualCoordinatorError(
                    "v4 persisted protection plan mismatch"
                ) from error
            if (
                not 0 <= elapsed <= 15
                or not isinstance(plan_payload, dict)
                or plan_payload.get("exact_filled_size") != confirmed_protection_size
            ):
                raise V4GmoActualCoordinatorError(
                    "v4 exact protection confirmation failed"
                )
            connection.execute(
                "INSERT INTO metadata(key,value) "
                "VALUES('protection_confirmed_at_utc',?)",
                (timestamp,),
            )


def calculate_v4_planned_loss(
    *,
    signal_fingerprint: str,
    frozen_atr_24: Decimal,
    quantity_units: int,
    adverse_slippage_allowance_pips: Decimal,
) -> V4FrozenSignalRisk:
    """Conservative planning gate, not a guarantee against unbounded gaps."""

    if (
        len(signal_fingerprint) != 64
        or frozen_atr_24 <= 0
        or quantity_units != 10_000
        or adverse_slippage_allowance_pips < 0
    ):
        raise V4GmoActualCoordinatorError("v4 frozen risk input is invalid")
    canonical_atr = format(frozen_atr_24.normalize(), "f")
    atr_digest = _atr_digest(
        signal_fingerprint=signal_fingerprint,
        canonical_atr=canonical_atr,
    )
    stop_width_pips = frozen_atr_24 * Decimal("1.5") / Decimal("0.01")
    stop_tick_rounding_allowance_pips = Decimal("0.1")
    yen_per_pip = Decimal(quantity_units) * Decimal("0.01")
    planned = (
        stop_width_pips
        + stop_tick_rounding_allowance_pips
        + adverse_slippage_allowance_pips
    ) * yen_per_pip
    planned_int = int(planned.to_integral_value(rounding=ROUND_CEILING))
    return V4FrozenSignalRisk(
        signal_fingerprint=signal_fingerprint,
        atr_24=canonical_atr,
        atr_digest=atr_digest,
        adverse_slippage_allowance_pips=format(
            adverse_slippage_allowance_pips.normalize(), "f"
        ),
        planned_loss_bound_jpy=planned_int,
    )


def _cycle_ref(generation_digest: str, signal_fingerprint: str) -> str:
    return hashlib.sha256(f"{generation_digest}:{signal_fingerprint}".encode()).hexdigest()


def _atr_digest(*, signal_fingerprint: str, canonical_atr: str) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(
            {
                "atr_24": canonical_atr,
                "signal_fingerprint": signal_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _snapshot_digest(
    *, snapshot: V4GmoBrokerSnapshot, position_bundle_total: int | None
) -> str:
    payload = {
        "entry_status": snapshot.entry_status.value,
        "filled_size": snapshot.filled_size,
        "pending_entry_size": snapshot.pending_entry_size,
        "position_bundle_total": position_bundle_total,
        "position_count": snapshot.position_count,
        "position_side": (
            snapshot.position_side.value if snapshot.position_side is not None else None
        ),
        "protection_size": snapshot.protection_size,
        "protection_status": snapshot.protection_status.value,
        "result_known": snapshot.result_known,
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _classify_pending_transport_recovery(
    *,
    previous_action: str,
    expected_side: SignalDecision,
    snapshot: V4GmoBrokerSnapshot,
    position_bundle_total: int | None,
) -> str | None:
    flat = (
        snapshot.position_count == 0
        and snapshot.position_side is None
        and snapshot.filled_size == 0
        and snapshot.pending_entry_size == 0
        and snapshot.protection_size == 0
        and snapshot.entry_status in {V4GmoEntryStatus.NONE, V4GmoEntryStatus.REJECTED}
        and snapshot.protection_status is V4GmoProtectionStatus.NONE
        and position_bundle_total is None
    )
    if flat:
        return "FLAT_OR_REJECTED"
    ownership_exact = (
        snapshot.position_count == 1
        and snapshot.position_side is expected_side
        and snapshot.filled_size > 0
        and position_bundle_total == snapshot.filled_size
    )
    partial_pending = (
        previous_action == V4GmoAction.MARKET_ENTRY.value
        and snapshot.entry_status in {V4GmoEntryStatus.PENDING, V4GmoEntryStatus.PARTIAL}
        and snapshot.pending_entry_size > 0
        and snapshot.protection_size == 0
        and snapshot.protection_status is V4GmoProtectionStatus.NONE
        and (
            (
                snapshot.position_count == 0
                and snapshot.position_side is None
                and snapshot.filled_size == 0
                and position_bundle_total is None
            )
            or ownership_exact
        )
    )
    if partial_pending:
        return "MARKET_PARTIAL_PENDING"
    if (
        ownership_exact
        and snapshot.entry_status is V4GmoEntryStatus.FILLED
        and snapshot.pending_entry_size == 0
        and snapshot.protection_size == 0
        and snapshot.protection_status is V4GmoProtectionStatus.NONE
    ):
        return "FILLED_UNPROTECTED"
    if (
        ownership_exact
        and snapshot.entry_status is V4GmoEntryStatus.FILLED
        and snapshot.pending_entry_size == 0
        and snapshot.protection_size == snapshot.filled_size
        and snapshot.protection_status is V4GmoProtectionStatus.EXACT_MATCH
    ):
        return "FILLED_PROTECTED"
    if (
        ownership_exact
        and snapshot.entry_status is V4GmoEntryStatus.FILLED
        and snapshot.pending_entry_size == 0
        and snapshot.protection_size > 0
        and snapshot.protection_status
        in {
            V4GmoProtectionStatus.UNDERSIZED,
            V4GmoProtectionStatus.OVERSIZED,
        }
    ):
        return "FILLED_PROTECTION_MISMATCHED"
    return None


def _valid_digest(value: str) -> bool:
    prefix = "sha256:"
    normalized = value.removeprefix(prefix) if isinstance(value, str) else ""
    return (
        isinstance(value, str)
        and value.startswith(prefix)
        and len(normalized) == 64
        and all(character in "0123456789abcdef" for character in normalized)
    )


def _require_monotonic(value: float) -> None:
    if not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
        raise V4GmoActualCoordinatorError("v4 monotonic time is invalid")


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise V4GmoActualCoordinatorError("v4 coordinator time must be timezone-aware")
    return value.astimezone(UTC).isoformat()
