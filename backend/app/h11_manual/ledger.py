"""Append-only local SQLite ledger for forecasts and operator decisions."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.h11_manual.contracts import (
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    Direction,
    Horizon,
    ManualExitReason,
    SignalAction,
    SignalView,
)

CALIBRATION_BIN_WIDTH = 0.05
THRESHOLD_CANDIDATES = (0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.65)


def _parse_broker_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid sanitized broker execution timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("sanitized broker execution timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _decimal_text(value: float) -> str:
    return format(value, ".12g")


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


class SignalLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    horizon TEXT NOT NULL,
                    origin_time_utc TEXT NOT NULL,
                    p_up REAL NOT NULL CHECK (p_up >= 0 AND p_up <= 1),
                    direction TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    model_config_hash TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL,
                    recorded_mode TEXT NOT NULL,
                    UNIQUE(horizon, origin_time_utc, model_config_hash)
                );
                CREATE TABLE IF NOT EXISTS resolutions (
                    forecast_id TEXT PRIMARY KEY REFERENCES forecasts(forecast_id),
                    outcome_up INTEGER NOT NULL CHECK (outcome_up IN (0, 1)),
                    target_time_utc TEXT NOT NULL,
                    resolved_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signal_actions (
                    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forecast_id TEXT NOT NULL UNIQUE REFERENCES forecasts(forecast_id),
                    horizon TEXT NOT NULL CHECK (horizon IN ('10m', '30m')),
                    action TEXT NOT NULL CHECK (action IN ('TRADE_STARTED', 'NO_ACTION')),
                    note TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS realtime_tick_samples (
                    sample_time_utc TEXT PRIMARY KEY,
                    market_time_utc TEXT NOT NULL,
                    bid REAL NOT NULL CHECK (bid > 0),
                    ask REAL NOT NULL CHECK (ask >= bid),
                    source TEXT NOT NULL CHECK (source = 'GMO_PUBLIC_WS')
                );
                CREATE TABLE IF NOT EXISTS realtime_rolling_forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    horizon TEXT NOT NULL CHECK (horizon IN ('10m', '30m')),
                    origin_time_utc TEXT NOT NULL,
                    target_time_utc TEXT NOT NULL,
                    p_up REAL NOT NULL CHECK (p_up >= 0 AND p_up <= 1),
                    direction TEXT NOT NULL,
                    origin_bid REAL NOT NULL CHECK (origin_bid > 0),
                    estimate_mode TEXT NOT NULL,
                    model_config_hash TEXT NOT NULL,
                    tick_native_window_ready INTEGER NOT NULL CHECK (
                        tick_native_window_ready IN (0, 1)
                    ),
                    recorded_at_utc TEXT NOT NULL,
                    UNIQUE(horizon, origin_time_utc, model_config_hash)
                );
                CREATE TABLE IF NOT EXISTS realtime_rolling_resolutions (
                    forecast_id TEXT PRIMARY KEY
                        REFERENCES realtime_rolling_forecasts(forecast_id),
                    resolution_status TEXT NOT NULL CHECK (
                        resolution_status IN ('RESOLVED', 'TARGET_PRICE_MISSING')
                    ),
                    outcome_up INTEGER CHECK (outcome_up IN (0, 1)),
                    target_bid REAL,
                    target_observed_time_utc TEXT NOT NULL,
                    target_delay_seconds REAL NOT NULL CHECK (target_delay_seconds >= 0),
                    resolved_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS realtime_rolling_forecast_target
                ON realtime_rolling_forecasts(target_time_utc);
                CREATE TABLE IF NOT EXISTS manual_trade_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forecast_id TEXT NOT NULL REFERENCES forecasts(forecast_id),
                    horizon TEXT NOT NULL CHECK (horizon IN ('10m', '30m')),
                    direction TEXT NOT NULL CHECK (direction IN ('買い', '売り')),
                    signal_origin_utc TEXT NOT NULL,
                    target_time_utc TEXT NOT NULL,
                    entry_time_utc TEXT NOT NULL,
                    entry_price REAL NOT NULL CHECK (entry_price > 0),
                    stop_loss_price REAL NOT NULL CHECK (stop_loss_price > 0),
                    take_profit_price REAL NOT NULL CHECK (take_profit_price > 0),
                    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
                    exit_time_utc TEXT,
                    exit_price REAL,
                    exit_reason TEXT
                );
                DROP INDEX IF EXISTS one_open_manual_trade_plan;
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_manual_trade_plan_per_horizon
                ON manual_trade_plans(horizon) WHERE status = 'OPEN';
                CREATE TABLE IF NOT EXISTS manual_trade_plan_quick_starts (
                    plan_id INTEGER PRIMARY KEY REFERENCES manual_trade_plans(plan_id),
                    reference_entry_price REAL NOT NULL CHECK (reference_entry_price > 0),
                    started_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_trade_plan_fill_corrections (
                    correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL REFERENCES manual_trade_plans(plan_id),
                    corrected_at_utc TEXT NOT NULL,
                    previous_entry_price REAL NOT NULL CHECK (previous_entry_price > 0),
                    corrected_entry_price REAL NOT NULL CHECK (corrected_entry_price > 0),
                    previous_stop_loss_price REAL NOT NULL CHECK (previous_stop_loss_price > 0),
                    corrected_stop_loss_price REAL NOT NULL CHECK (corrected_stop_loss_price > 0),
                    previous_take_profit_price REAL NOT NULL CHECK (previous_take_profit_price > 0),
                    corrected_take_profit_price REAL NOT NULL CHECK (
                        corrected_take_profit_price > 0
                    )
                );
                CREATE TABLE IF NOT EXISTS manual_broker_plan_links (
                    plan_id INTEGER PRIMARY KEY REFERENCES manual_trade_plans(plan_id),
                    position_ref TEXT UNIQUE,
                    entry_execution_ref TEXT UNIQUE,
                    entry_size TEXT,
                    closed_size TEXT NOT NULL DEFAULT '0',
                    close_value TEXT NOT NULL DEFAULT '0',
                    remaining_size TEXT,
                    sync_state TEXT NOT NULL CHECK (sync_state IN (
                        'WAITING_FOR_OPEN', 'AMBIGUOUS_OPEN', 'LINKED',
                        'PARTIALLY_CLOSED', 'RECHECK_REQUIRED', 'CLOSED'
                    )),
                    linked_at_utc TEXT,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_broker_execution_receipts (
                    execution_ref TEXT PRIMARY KEY,
                    position_ref TEXT NOT NULL,
                    settle_type TEXT NOT NULL CHECK (settle_type IN ('OPEN', 'CLOSE')),
                    symbol TEXT NOT NULL CHECK (symbol = 'USD_JPY'),
                    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
                    size TEXT NOT NULL,
                    price TEXT NOT NULL,
                    executed_at_utc TEXT NOT NULL,
                    applied_plan_id INTEGER REFERENCES manual_trade_plans(plan_id),
                    recorded_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_broker_positions (
                    position_ref TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL CHECK (symbol = 'USD_JPY'),
                    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
                    opened_at_utc TEXT NOT NULL,
                    opened_at_source TEXT NOT NULL CHECK (
                        opened_at_source IN ('OPEN_EXECUTION', 'FIRST_OPEN_SNAPSHOT')
                    ),
                    entry_size TEXT NOT NULL,
                    average_entry_price TEXT,
                    remaining_size TEXT NOT NULL,
                    closed_size TEXT NOT NULL DEFAULT '0',
                    close_value TEXT NOT NULL DEFAULT '0',
                    average_close_price TEXT,
                    closed_at_utc TEXT,
                    status TEXT NOT NULL CHECK (status IN (
                        'OPEN', 'PARTIALLY_CLOSED', 'CLOSED', 'RECHECK_REQUIRED'
                    )),
                    first_seen_at_utc TEXT NOT NULL,
                    last_seen_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_broker_sync_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    status TEXT NOT NULL,
                    safe_error_code TEXT,
                    source TEXT NOT NULL,
                    open_position_count INTEGER,
                    last_attempt_at_utc TEXT NOT NULL,
                    last_success_at_utc TEXT
                );
                INSERT INTO signal_actions
                    (forecast_id, horizon, action, note, recorded_at_utc)
                SELECT p.forecast_id, p.horizon, 'TRADE_STARTED',
                       '既存quick-start監査から移行', q.started_at_utc
                FROM manual_trade_plan_quick_starts q
                JOIN manual_trade_plans p USING(plan_id)
                WHERE 1
                ON CONFLICT(forecast_id) DO UPDATE SET
                    action = 'TRADE_STARTED',
                    note = '既存quick-start監査から移行',
                    recorded_at_utc = excluded.recorded_at_utc
                WHERE signal_actions.action = 'NO_ACTION';
                """
            )

    def record_realtime_tick(
        self,
        *,
        bid: float,
        ask: float,
        market_time_utc: str,
        sampled_at: datetime | None = None,
    ) -> bool:
        sample_time = (sampled_at or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
        with self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO realtime_tick_samples
                (sample_time_utc, market_time_utc, bid, ask, source)
                VALUES (?, ?, ?, ?, 'GMO_PUBLIC_WS')""",
                (sample_time.isoformat(), market_time_utc, bid, ask),
            )
            return cursor.rowcount == 1

    def recent_realtime_ticks(self, limit: int = 2_400) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 10_000))
        with self._connect() as db:
            rows = db.execute(
                """SELECT sample_time_utc, market_time_utc, bid, ask
                FROM realtime_tick_samples ORDER BY sample_time_utc DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def realtime_tick_count(self) -> int:
        with self._connect() as db:
            row = db.execute("SELECT COUNT(*) AS count FROM realtime_tick_samples").fetchone()
        return int(row["count"])

    def latest_realtime_tick(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT sample_time_utc, market_time_utc, bid, ask
                FROM realtime_tick_samples ORDER BY sample_time_utc DESC LIMIT 1"""
            ).fetchone()
        return None if row is None else dict(row)

    def record_realtime_rolling_forecast(
        self,
        *,
        forecast_id: str,
        horizon: Horizon,
        origin_time_utc: str,
        p_up: float,
        direction: Direction,
        origin_bid: float,
        estimate_mode: str,
        model_config_hash: str,
        tick_native_window_ready: bool,
        recorded_at: datetime | None = None,
    ) -> bool:
        if horizon not in (Horizon.MINUTES_10, Horizon.MINUTES_30):
            raise ValueError("realtime rolling validation supports only 10m and 30m")
        origin = datetime.fromisoformat(origin_time_utc).astimezone(UTC)
        target = origin + timedelta(minutes=horizon.bars)
        now = (recorded_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO realtime_rolling_forecasts
                (forecast_id, horizon, origin_time_utc, target_time_utc, p_up, direction,
                 origin_bid, estimate_mode, model_config_hash, tick_native_window_ready,
                 recorded_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    forecast_id,
                    horizon.value,
                    origin.isoformat(),
                    target.isoformat(),
                    p_up,
                    direction.value,
                    origin_bid,
                    estimate_mode,
                    model_config_hash,
                    int(tick_native_window_ready),
                    now,
                ),
            )
            return cursor.rowcount == 1

    def resolve_due_realtime_rolling_forecasts(
        self,
        *,
        observed_at: datetime,
        bid: float,
        max_target_delay_seconds: int = 15,
        limit: int = 10_000,
    ) -> dict[str, int]:
        observed = observed_at.astimezone(UTC).replace(microsecond=0)
        safe_limit = max(1, min(limit, 50_000))
        with self._connect() as db:
            rows = db.execute(
                """SELECT f.forecast_id, f.target_time_utc, f.origin_bid
                FROM realtime_rolling_forecasts f
                LEFT JOIN realtime_rolling_resolutions r USING(forecast_id)
                WHERE r.forecast_id IS NULL AND f.target_time_utc <= ?
                ORDER BY f.target_time_utc LIMIT ?""",
                (observed.isoformat(), safe_limit),
            ).fetchall()
            resolutions: list[tuple[Any, ...]] = []
            resolved_n = 0
            missing_n = 0
            for row in rows:
                target = datetime.fromisoformat(row["target_time_utc"]).astimezone(UTC)
                delay = max(0.0, (observed - target).total_seconds())
                if delay <= max_target_delay_seconds:
                    status = "RESOLVED"
                    outcome_up: int | None = int(bid > float(row["origin_bid"]))
                    target_bid: float | None = bid
                    resolved_n += 1
                else:
                    status = "TARGET_PRICE_MISSING"
                    outcome_up = None
                    target_bid = None
                    missing_n += 1
                resolutions.append(
                    (
                        row["forecast_id"],
                        status,
                        outcome_up,
                        target_bid,
                        observed.isoformat(),
                        delay,
                        observed.isoformat(),
                    )
                )
            db.executemany(
                """INSERT OR IGNORE INTO realtime_rolling_resolutions
                (forecast_id, resolution_status, outcome_up, target_bid,
                 target_observed_time_utc, target_delay_seconds, resolved_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                resolutions,
            )
        return {"resolved_n": resolved_n, "target_price_missing_n": missing_n}

    def realtime_rolling_forecast_count(self) -> int:
        with self._connect() as db:
            row = db.execute("SELECT COUNT(*) AS count FROM realtime_rolling_forecasts").fetchone()
        return int(row["count"])

    def record_forecast(self, signal: SignalView, *, recorded_at: datetime | None = None) -> bool:
        if signal.forecast_id is None or signal.p_up is None or signal.origin_time_utc is None:
            return False
        now = (recorded_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO forecasts
                (forecast_id, horizon, origin_time_utc, p_up, direction, reason,
                 model_config_hash, recorded_at_utc, recorded_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.forecast_id,
                    signal.horizon.value,
                    signal.origin_time_utc,
                    signal.p_up,
                    signal.direction.value,
                    signal.reason,
                    signal.model_config_hash,
                    now,
                    signal.recorded_mode or "PROSPECTIVE",
                ),
            )
            return cursor.rowcount == 1

    def resolve(
        self,
        forecast_id: str,
        *,
        outcome_up: bool,
        target_time_utc: str,
        resolved_at: datetime | None = None,
    ) -> bool:
        now = (resolved_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO resolutions
                (forecast_id, outcome_up, target_time_utc, resolved_at_utc)
                VALUES (?, ?, ?, ?)""",
                (forecast_id, int(outcome_up), target_time_utc, now),
            )
            return cursor.rowcount == 1

    def record_due_no_actions(self, *, now: datetime | None = None) -> int:
        """Record objective expiry without inferring that an operator deliberately skipped."""

        current = (now or datetime.now(UTC)).astimezone(UTC)
        recorded_at = current.isoformat(timespec="seconds")
        with self._connect() as db:
            rows = db.execute(
                """SELECT f.forecast_id, f.horizon, f.origin_time_utc
                FROM forecasts f
                LEFT JOIN signal_actions a USING(forecast_id)
                WHERE f.recorded_mode = 'PROSPECTIVE'
                  AND f.horizon IN ('10m', '30m')
                  AND a.forecast_id IS NULL
                ORDER BY f.origin_time_utc"""
            ).fetchall()
            due = []
            for row in rows:
                horizon = Horizon(row["horizon"])
                origin = datetime.fromisoformat(row["origin_time_utc"]).astimezone(UTC)
                if current >= origin + timedelta(minutes=horizon.bars):
                    due.append(
                        (
                            row["forecast_id"],
                            horizon.value,
                            SignalAction.NO_ACTION.value,
                            "取引開始記録なし",
                            recorded_at,
                        )
                    )
            if not due:
                return 0
            before = db.total_changes
            db.executemany(
                """INSERT OR IGNORE INTO signal_actions
                (forecast_id, horizon, action, note, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?)""",
                due,
            )
            return db.total_changes - before

    def latest_forecasts(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as db:
            rows = db.execute(
                """SELECT f.*, r.outcome_up, r.target_time_utc
                FROM forecasts f LEFT JOIN resolutions r USING(forecast_id)
                ORDER BY f.origin_time_utc DESC, f.horizon ASC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_prospective_forecasts(
        self,
        horizon: Horizon,
        *,
        since_utc: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 100))
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM forecasts
                WHERE horizon = ? AND recorded_mode = 'PROSPECTIVE'
                  AND origin_time_utc >= ?
                ORDER BY origin_time_utc DESC LIMIT ?""",
                (horizon.value, since_utc, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def signal_probability_series(self, limit: int = 120) -> dict[str, list[dict[str, Any]]]:
        safe_limit = max(10, min(limit, 500))
        result: dict[str, list[dict[str, Any]]] = {}
        with self._connect() as db:
            for horizon in Horizon:
                rows = db.execute(
                    """SELECT origin_time_utc AS time_utc, p_up
                    FROM forecasts
                    WHERE horizon = ? AND recorded_mode = 'PROSPECTIVE'
                    ORDER BY origin_time_utc DESC LIMIT ?""",
                    (horizon.value, safe_limit),
                ).fetchall()
                result[horizon.value] = [dict(row) for row in reversed(rows)]
        return result

    def latest_signal_actions(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM signal_actions ORDER BY action_id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def forecast(self, forecast_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM forecasts WHERE forecast_id = ?", (forecast_id,)
            ).fetchone()
        return None if row is None else dict(row)

    def open_manual_trade_plan(
        self,
        *,
        forecast_id: str,
        horizon: Horizon,
        direction: Direction,
        signal_origin_utc: str,
        target_time_utc: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        opened_at: datetime | None = None,
    ) -> int:
        now = (opened_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        try:
            with self._connect() as db:
                cursor = db.execute(
                    """INSERT INTO manual_trade_plans
                    (forecast_id, horizon, direction, signal_origin_utc, target_time_utc,
                     entry_time_utc, entry_price, stop_loss_price, take_profit_price, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
                    (
                        forecast_id,
                        horizon.value,
                        direction.value,
                        signal_origin_utc,
                        target_time_utc,
                        now,
                        entry_price,
                        stop_loss_price,
                        take_profit_price,
                    ),
                )
                return int(cursor.lastrowid)
        except sqlite3.IntegrityError as error:
            raise ValueError("an open manual trade plan already exists for this horizon") from error

    def active_manual_trade_plans(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM manual_trade_plans WHERE status = 'OPEN'
                ORDER BY CASE horizon WHEN '10m' THEN 1 ELSE 2 END, plan_id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def active_manual_trade_plan(
        self,
        *,
        plan_id: int | None = None,
        horizon: Horizon | None = None,
    ) -> dict[str, Any] | None:
        clauses = ["status = 'OPEN'"]
        parameters: list[Any] = []
        if plan_id is not None:
            clauses.append("plan_id = ?")
            parameters.append(plan_id)
        if horizon is not None:
            clauses.append("horizon = ?")
            parameters.append(horizon.value)
        with self._connect() as db:
            row = db.execute(
                f"SELECT * FROM manual_trade_plans WHERE {' AND '.join(clauses)} LIMIT 1",
                parameters,
            ).fetchone()
        return None if row is None else dict(row)

    def record_manual_trade_quick_start(
        self,
        *,
        plan_id: int,
        forecast_id: str,
        horizon: Horizon,
        reference_entry_price: float,
        started_at: datetime | None = None,
    ) -> bool:
        now = (started_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO manual_trade_plan_quick_starts
                (plan_id, reference_entry_price, started_at_utc) VALUES (?, ?, ?)""",
                (plan_id, reference_entry_price, now),
            )
            if cursor.rowcount != 1:
                return False
            db.execute(
                """INSERT OR IGNORE INTO manual_broker_plan_links
                (plan_id, sync_state, updated_at_utc)
                VALUES (?, 'WAITING_FOR_OPEN', ?)""",
                (plan_id, now),
            )
            action = db.execute(
                """INSERT OR IGNORE INTO signal_actions
                (forecast_id, horizon, action, note, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    forecast_id,
                    horizon.value,
                    SignalAction.TRADE_STARTED.value,
                    "カード内の取引開始からlocal出口計画を開始",
                    now,
                ),
            )
            return action.rowcount == 1

    def record_broker_sync_failure(
        self,
        *,
        status: str,
        safe_error_code: str,
        source: str,
        attempted_at: datetime | None = None,
    ) -> None:
        now = (attempted_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            previous = db.execute(
                "SELECT last_success_at_utc FROM manual_broker_sync_state WHERE singleton = 1"
            ).fetchone()
            last_success = None if previous is None else previous["last_success_at_utc"]
            db.execute(
                """INSERT INTO manual_broker_sync_state
                (singleton, status, safe_error_code, source, open_position_count,
                 last_attempt_at_utc, last_success_at_utc)
                VALUES (1, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    status = excluded.status,
                    safe_error_code = excluded.safe_error_code,
                    source = excluded.source,
                    open_position_count = NULL,
                    last_attempt_at_utc = excluded.last_attempt_at_utc,
                    last_success_at_utc = excluded.last_success_at_utc""",
                (status, safe_error_code, source, now, last_success),
            )

    def apply_broker_sync_snapshot(
        self,
        *,
        executions: list[dict[str, Any]],
        open_positions: list[dict[str, Any]],
        source: str,
        synced_at: datetime | None = None,
        match_window_seconds: int = 120,
        stop_pips: float = 15.0,
        take_pips: float = 22.5,
        pip_size: float = 0.01,
    ) -> dict[str, Any]:
        """Atomically apply sanitized receipts; no raw broker identifier enters SQLite."""

        now_dt = (synced_at or datetime.now(UTC)).astimezone(UTC)
        now = now_dt.isoformat(timespec="seconds")
        events: list[dict[str, Any]] = []
        with self._connect() as db:
            for execution in executions:
                db.execute(
                    """INSERT OR IGNORE INTO manual_broker_execution_receipts
                    (execution_ref, position_ref, settle_type, symbol, side, size, price,
                     executed_at_utc, applied_plan_id, recorded_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
                    (
                        execution["execution_ref"],
                        execution["position_ref"],
                        execution["settle_type"],
                        execution["symbol"],
                        execution["side"],
                        execution["size"],
                        execution["price"],
                        execution["executed_at_utc"],
                        now,
                    ),
                )

            open_by_ref = {row["position_ref"]: row for row in open_positions}
            for position_ref, position in open_by_ref.items():
                previous = db.execute(
                    "SELECT * FROM manual_broker_positions WHERE position_ref = ?",
                    (position_ref,),
                ).fetchone()
                open_rows = db.execute(
                    """SELECT size, price, executed_at_utc
                    FROM manual_broker_execution_receipts
                    WHERE position_ref = ? AND settle_type = 'OPEN'
                    ORDER BY executed_at_utc, execution_ref""",
                    (position_ref,),
                ).fetchall()
                close_rows_for_position = db.execute(
                    """SELECT size, price, executed_at_utc
                    FROM manual_broker_execution_receipts
                    WHERE position_ref = ? AND settle_type = 'CLOSE'
                    ORDER BY executed_at_utc, execution_ref""",
                    (position_ref,),
                ).fetchall()
                open_size = sum(float(row["size"]) for row in open_rows)
                close_size = sum(float(row["size"]) for row in close_rows_for_position)
                close_value = sum(
                    float(row["size"]) * float(row["price"])
                    for row in close_rows_for_position
                )
                remaining = float(position["size"])
                previous_entry_size = 0.0 if previous is None else float(previous["entry_size"])
                entry_size = max(open_size, previous_entry_size, remaining + close_size)
                if open_rows and open_size > 0:
                    average_entry = sum(
                        float(row["size"]) * float(row["price"]) for row in open_rows
                    ) / open_size
                    opened_at = open_rows[0]["executed_at_utc"]
                    opened_at_source = "OPEN_EXECUTION"
                else:
                    average_entry = _float_or_none(position.get("average_price"))
                    if average_entry is None and previous is not None:
                        average_entry = _float_or_none(previous["average_entry_price"])
                    opened_at = now if previous is None else previous["opened_at_utc"]
                    opened_at_source = (
                        "FIRST_OPEN_SNAPSHOT"
                        if previous is None
                        else previous["opened_at_source"]
                    )
                average_close = None if close_size <= 0 else close_value / close_size
                status = (
                    "PARTIALLY_CLOSED"
                    if close_size > 0 or remaining + 1e-9 < entry_size
                    else "OPEN"
                )
                first_seen = now if previous is None else previous["first_seen_at_utc"]
                db.execute(
                    """INSERT INTO manual_broker_positions
                    (position_ref, symbol, side, opened_at_utc, opened_at_source,
                     entry_size, average_entry_price, remaining_size, closed_size,
                     close_value, average_close_price, closed_at_utc, status,
                     first_seen_at_utc, last_seen_at_utc, updated_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                    ON CONFLICT(position_ref) DO UPDATE SET
                        symbol = excluded.symbol,
                        side = excluded.side,
                        opened_at_utc = excluded.opened_at_utc,
                        opened_at_source = excluded.opened_at_source,
                        entry_size = excluded.entry_size,
                        average_entry_price = excluded.average_entry_price,
                        remaining_size = excluded.remaining_size,
                        closed_size = excluded.closed_size,
                        close_value = excluded.close_value,
                        average_close_price = excluded.average_close_price,
                        closed_at_utc = NULL,
                        status = excluded.status,
                        last_seen_at_utc = excluded.last_seen_at_utc,
                        updated_at_utc = excluded.updated_at_utc""",
                    (
                        position_ref,
                        position["symbol"],
                        position["side"],
                        opened_at,
                        opened_at_source,
                        _decimal_text(entry_size),
                        None if average_entry is None else _decimal_text(average_entry),
                        _decimal_text(remaining),
                        _decimal_text(close_size),
                        _decimal_text(close_value),
                        None if average_close is None else _decimal_text(average_close),
                        status,
                        first_seen,
                        now,
                        now,
                    ),
                )

            tracked_positions = db.execute(
                "SELECT * FROM manual_broker_positions WHERE status != 'CLOSED'"
            ).fetchall()
            for tracked in tracked_positions:
                if tracked["position_ref"] in open_by_ref:
                    continue
                close_rows_for_position = db.execute(
                    """SELECT size, price, executed_at_utc
                    FROM manual_broker_execution_receipts
                    WHERE position_ref = ? AND settle_type = 'CLOSE'
                    ORDER BY executed_at_utc, execution_ref""",
                    (tracked["position_ref"],),
                ).fetchall()
                close_size = sum(float(row["size"]) for row in close_rows_for_position)
                close_value = sum(
                    float(row["size"]) * float(row["price"])
                    for row in close_rows_for_position
                )
                entry_size = float(tracked["entry_size"])
                fully_closed = close_size > 0 and close_size + 1e-9 >= entry_size
                closed_at = (
                    close_rows_for_position[-1]["executed_at_utc"]
                    if fully_closed
                    else None
                )
                db.execute(
                    """UPDATE manual_broker_positions
                    SET remaining_size = ?, closed_size = ?, close_value = ?,
                        average_close_price = ?, closed_at_utc = ?, status = ?,
                        updated_at_utc = ? WHERE position_ref = ?""",
                    (
                        "0" if fully_closed else tracked["remaining_size"],
                        _decimal_text(close_size),
                        _decimal_text(close_value),
                        None if close_size <= 0 else _decimal_text(close_value / close_size),
                        closed_at,
                        "CLOSED" if fully_closed else "RECHECK_REQUIRED",
                        now,
                        tracked["position_ref"],
                    ),
                )

            active = db.execute(
                """SELECT p.*, l.sync_state, l.position_ref, l.entry_size
                FROM manual_trade_plans p
                JOIN manual_broker_plan_links l USING(plan_id)
                WHERE p.status = 'OPEN'
                ORDER BY p.plan_id"""
            ).fetchall()
            unmatched_open = db.execute(
                """SELECT * FROM manual_broker_execution_receipts
                WHERE settle_type = 'OPEN' AND applied_plan_id IS NULL
                ORDER BY executed_at_utc, execution_ref"""
            ).fetchall()

            candidate_map: dict[int, list[sqlite3.Row]] = {}
            execution_use_count: dict[str, int] = {}
            for plan in active:
                if plan["position_ref"]:
                    continue
                entry_time = datetime.fromisoformat(plan["entry_time_utc"]).astimezone(UTC)
                expected_side = "BUY" if plan["direction"] == Direction.BUY.value else "SELL"
                candidates: list[sqlite3.Row] = []
                for execution in unmatched_open:
                    executed_at = _parse_broker_datetime(execution["executed_at_utc"])
                    if (
                        execution["side"] == expected_side
                        and abs((executed_at - entry_time).total_seconds()) <= match_window_seconds
                    ):
                        candidates.append(execution)
                        execution_use_count[execution["execution_ref"]] = (
                            execution_use_count.get(execution["execution_ref"], 0) + 1
                        )
                candidate_map[int(plan["plan_id"])] = candidates

            for plan in active:
                plan_id = int(plan["plan_id"])
                if plan["position_ref"]:
                    continue
                candidates = candidate_map.get(plan_id, [])
                unique = [
                    row
                    for row in candidates
                    if execution_use_count.get(row["execution_ref"], 0) == 1
                ]
                if len(candidates) != 1 or len(unique) != 1:
                    state = "AMBIGUOUS_OPEN" if candidates else "WAITING_FOR_OPEN"
                    db.execute(
                        """UPDATE manual_broker_plan_links
                        SET sync_state = ?, updated_at_utc = ? WHERE plan_id = ?""",
                        (state, now, plan_id),
                    )
                    continue
                execution = unique[0]
                entry_price = float(execution["price"])
                sign = 1 if plan["direction"] == Direction.BUY.value else -1
                stop_price = round(entry_price - sign * stop_pips * pip_size, 6)
                take_price = round(entry_price + sign * take_pips * pip_size, 6)
                db.execute(
                    """UPDATE manual_trade_plans
                    SET entry_price = ?, stop_loss_price = ?, take_profit_price = ?
                    WHERE plan_id = ? AND status = 'OPEN'""",
                    (entry_price, stop_price, take_price, plan_id),
                )
                db.execute(
                    """INSERT INTO manual_trade_plan_fill_corrections
                    (plan_id, corrected_at_utc, previous_entry_price, corrected_entry_price,
                     previous_stop_loss_price, corrected_stop_loss_price,
                     previous_take_profit_price, corrected_take_profit_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        plan_id,
                        now,
                        plan["entry_price"],
                        entry_price,
                        plan["stop_loss_price"],
                        stop_price,
                        plan["take_profit_price"],
                        take_price,
                    ),
                )
                db.execute(
                    """UPDATE manual_broker_plan_links
                    SET position_ref = ?, entry_execution_ref = ?, entry_size = ?,
                        remaining_size = ?, sync_state = 'LINKED', linked_at_utc = ?,
                        updated_at_utc = ?
                    WHERE plan_id = ?""",
                    (
                        execution["position_ref"],
                        execution["execution_ref"],
                        execution["size"],
                        execution["size"],
                        execution["executed_at_utc"],
                        now,
                        plan_id,
                    ),
                )
                db.execute(
                    """UPDATE manual_broker_execution_receipts SET applied_plan_id = ?
                    WHERE execution_ref = ?""",
                    (plan_id, execution["execution_ref"]),
                )
                events.append({"type": "OPEN_LINKED", "plan_id": plan_id})

            close_rows = db.execute(
                """SELECT * FROM manual_broker_execution_receipts
                WHERE settle_type = 'CLOSE' AND applied_plan_id IS NULL
                ORDER BY executed_at_utc, execution_ref"""
            ).fetchall()
            for execution in close_rows:
                link = db.execute(
                    """SELECT l.*, p.status, p.horizon
                    FROM manual_broker_plan_links l JOIN manual_trade_plans p USING(plan_id)
                    WHERE l.position_ref = ?""",
                    (execution["position_ref"],),
                ).fetchone()
                if link is None:
                    continue
                plan_id = int(link["plan_id"])
                closed_size = float(link["closed_size"]) + float(execution["size"])
                close_value = float(link["close_value"]) + (
                    float(execution["size"]) * float(execution["price"])
                )
                entry_size = float(link["entry_size"])
                state = "CLOSED" if closed_size + 1e-9 >= entry_size else "PARTIALLY_CLOSED"
                remaining_size = max(0.0, entry_size - closed_size)
                db.execute(
                    """UPDATE manual_broker_plan_links
                    SET closed_size = ?, close_value = ?, remaining_size = ?,
                        sync_state = ?, updated_at_utc = ? WHERE plan_id = ?""",
                    (
                        _decimal_text(closed_size),
                        _decimal_text(close_value),
                        _decimal_text(remaining_size),
                        state,
                        now,
                        plan_id,
                    ),
                )
                db.execute(
                    """UPDATE manual_broker_execution_receipts SET applied_plan_id = ?
                    WHERE execution_ref = ?""",
                    (plan_id, execution["execution_ref"]),
                )
                if state == "CLOSED" and link["status"] == "OPEN":
                    average_exit = close_value / closed_size
                    db.execute(
                        """UPDATE manual_trade_plans SET status = 'CLOSED', exit_time_utc = ?,
                        exit_price = ?, exit_reason = ?
                        WHERE plan_id = ? AND status = 'OPEN'""",
                        (
                            execution["executed_at_utc"],
                            average_exit,
                            ManualExitReason.BROKER_SYNC.value,
                            plan_id,
                        ),
                    )
                    events.append({"type": "CLOSE_APPLIED", "plan_id": plan_id})
                else:
                    events.append({"type": "PARTIAL_CLOSE_APPLIED", "plan_id": plan_id})

            linked_open = db.execute(
                """SELECT l.*, p.status FROM manual_broker_plan_links l
                JOIN manual_trade_plans p USING(plan_id)
                WHERE p.status = 'OPEN' AND l.position_ref IS NOT NULL"""
            ).fetchall()
            for link in linked_open:
                position = open_by_ref.get(link["position_ref"])
                if position is None:
                    db.execute(
                        """UPDATE manual_broker_plan_links
                        SET sync_state = 'RECHECK_REQUIRED', updated_at_utc = ?
                        WHERE plan_id = ?""",
                        (now, link["plan_id"]),
                    )
                    continue
                remaining = float(position["size"])
                entry_size = float(link["entry_size"])
                state = "PARTIALLY_CLOSED" if remaining + 1e-9 < entry_size else "LINKED"
                db.execute(
                    """UPDATE manual_broker_plan_links
                    SET remaining_size = ?, sync_state = ?, updated_at_utc = ?
                    WHERE plan_id = ?""",
                    (_decimal_text(remaining), state, now, link["plan_id"]),
                )

            db.execute(
                """INSERT INTO manual_broker_sync_state
                (singleton, status, safe_error_code, source, open_position_count,
                 last_attempt_at_utc, last_success_at_utc)
                VALUES (1, 'SYNCED', NULL, ?, ?, ?, ?)
                ON CONFLICT(singleton) DO UPDATE SET
                    status = 'SYNCED', safe_error_code = NULL, source = excluded.source,
                    open_position_count = excluded.open_position_count,
                    last_attempt_at_utc = excluded.last_attempt_at_utc,
                    last_success_at_utc = excluded.last_success_at_utc""",
                (source, len(open_positions), now, now),
            )
        return {"events": events, **self.broker_sync_overview()}

    def broker_position_history(
        self,
        *,
        limit: int = 100,
        include_private_ref: bool = False,
    ) -> list[dict[str, Any]]:
        """Return sanitized local position facts; broker identifiers stay internal by default."""

        safe_limit = max(1, min(limit, 500))
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM manual_broker_positions
                ORDER BY opened_at_utc DESC, first_seen_at_utc DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if not include_private_ref:
                item.pop("position_ref", None)
            for key in (
                "entry_size",
                "average_entry_price",
                "remaining_size",
                "closed_size",
                "average_close_price",
            ):
                item[key] = _float_or_none(item[key])
            item.pop("close_value", None)
            result.append(item)
        return result

    def active_broker_positions(self) -> list[dict[str, Any]]:
        return [
            row
            for row in self.broker_position_history(limit=500, include_private_ref=True)
            if row["status"] in {"OPEN", "PARTIALLY_CLOSED"}
        ]

    def broker_plan_sync_status(self, plan_id: int) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                """SELECT sync_state, entry_size, closed_size, remaining_size,
                linked_at_utc, updated_at_utc FROM manual_broker_plan_links
                WHERE plan_id = ?""",
                (plan_id,),
            ).fetchone()
        if row is None:
            return {
                "state": "NOT_TRACKED",
                "entry_size": None,
                "closed_size": None,
                "remaining_size": None,
                "linked_at_utc": None,
                "updated_at_utc": None,
            }
        return {
            "state": row["sync_state"],
            "entry_size": _float_or_none(row["entry_size"]),
            "closed_size": _float_or_none(row["closed_size"]),
            "remaining_size": _float_or_none(row["remaining_size"]),
            "linked_at_utc": row["linked_at_utc"],
            "updated_at_utc": row["updated_at_utc"],
        }

    def broker_sync_overview(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM manual_broker_sync_state WHERE singleton = 1"
            ).fetchone()
        if row is None:
            return {
                "status": "NOT_CONFIGURED",
                "safe_error_code": None,
                "source": "DISABLED",
                "open_position_count": None,
                "last_attempt_at_utc": None,
                "last_success_at_utc": None,
            }
        result = dict(row)
        result.pop("singleton", None)
        return result

    def is_manual_trade_quick_start(self, plan_id: int) -> bool:
        with self._connect() as db:
            row = db.execute(
                "SELECT 1 FROM manual_trade_plan_quick_starts WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        return row is not None

    def correct_active_manual_trade_fill(
        self,
        *,
        plan_id: int,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        corrected_at: datetime | None = None,
    ) -> bool:
        now = (corrected_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            previous = db.execute(
                "SELECT * FROM manual_trade_plans WHERE plan_id = ? AND status = 'OPEN'",
                (plan_id,),
            ).fetchone()
            if previous is None:
                return False
            cursor = db.execute(
                """UPDATE manual_trade_plans
                SET entry_price = ?, stop_loss_price = ?, take_profit_price = ?
                WHERE plan_id = ? AND status = 'OPEN'""",
                (entry_price, stop_loss_price, take_profit_price, plan_id),
            )
            if cursor.rowcount != 1:
                return False
            db.execute(
                """INSERT INTO manual_trade_plan_fill_corrections
                (plan_id, corrected_at_utc, previous_entry_price, corrected_entry_price,
                 previous_stop_loss_price, corrected_stop_loss_price,
                 previous_take_profit_price, corrected_take_profit_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    plan_id,
                    now,
                    previous["entry_price"],
                    entry_price,
                    previous["stop_loss_price"],
                    stop_loss_price,
                    previous["take_profit_price"],
                    take_profit_price,
                ),
            )
            return True

    def manual_trade_fill_correction_summary(self, plan_id: int) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS correction_count, MAX(corrected_at_utc) AS corrected_at_utc
                FROM manual_trade_plan_fill_corrections WHERE plan_id = ?""",
                (plan_id,),
            ).fetchone()
        return dict(row)

    def close_manual_trade_plan(
        self,
        *,
        plan_id: int,
        reason: ManualExitReason,
        exit_price: float,
        closed_at: datetime | None = None,
    ) -> bool:
        now = (closed_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE manual_trade_plans
                SET status = 'CLOSED', exit_time_utc = ?, exit_price = ?, exit_reason = ?
                WHERE plan_id = ? AND status = 'OPEN'""",
                (now, exit_price, reason.value, plan_id),
            )
            return cursor.rowcount == 1

    def manual_trade_history(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM manual_trade_plans
                ORDER BY plan_id DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def unresolved(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT f.* FROM forecasts f LEFT JOIN resolutions r USING(forecast_id)
                WHERE r.forecast_id IS NULL ORDER BY f.origin_time_utc"""
            ).fetchall()
        return [dict(row) for row in rows]

    def validation_summary(self) -> dict[str, Any]:
        overall_rows = self._resolved_rows(None)
        overall_actions = self._action_breakdown(overall_rows, [])
        overall_actions["confidence_interval_basis"] = "NOT_AVAILABLE_MIXED_HORIZONS"
        overall_actions["mixed_horizon_aggregate"] = True
        overall_calibration = self._calibration_bands(overall_rows, [])
        overall_thresholds = self._threshold_curve(overall_rows, [])
        for row in overall_calibration:
            row["non_overlapping_n"] = None
        for row in overall_thresholds:
            row["non_overlapping_n"] = None
        result: dict[str, Any] = {
            "scope": "PROSPECTIVE_ONLY",
            "threshold_version": "SHORT_V1_FIXED_58_42",
            "threshold_auto_change_allowed": False,
            "overall": self._metrics(None),
            "horizons": {},
            "diagnostics": {
                "overall": {
                    "action_breakdown": overall_actions,
                    "calibration_bands": overall_calibration,
                    "threshold_curve": overall_thresholds,
                    "raw_resolved_n": len(overall_rows),
                    "non_overlapping_n": None,
                    "overlap_note": "MIXED_HORIZONS_NO_SINGLE_NON_OVERLAPPING_SAMPLE",
                }
            },
        }
        for horizon in Horizon:
            result["horizons"][horizon.value] = self._metrics(horizon)
            rows = self._resolved_rows(horizon)
            independent = self._non_overlapping_rows(rows, horizon)
            result["diagnostics"][horizon.value] = {
                "action_breakdown": self._action_breakdown(rows, independent),
                "calibration_bands": self._calibration_bands(rows, independent),
                "threshold_curve": self._threshold_curve(rows, independent),
                "raw_resolved_n": len(rows),
                "non_overlapping_n": len(independent),
                "overlap_note": "RAW_ROWS_ARE_NOT_INDEPENDENT",
            }
        return result

    def realtime_rolling_validation_summary(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "COLLECTING_NOT_FORMAL",
            "scope": "REALTIME_ROLLING_SEPARATE_LEDGER",
            "formal_signal": False,
            "promotion_eligible": False,
            "target_price_max_delay_seconds": 15,
            "raw_rows_are_independent": False,
            "threshold_auto_change_allowed": False,
            "horizons": {},
        }
        total_resolved = 0
        for horizon in (Horizon.MINUTES_10, Horizon.MINUTES_30):
            counts = self._realtime_rolling_counts(horizon)
            rows = self._realtime_rolling_resolved_rows(horizon)
            independent = self._non_overlapping_rows(rows, horizon)
            raw_metrics = self._metrics_from_rows(rows)
            non_overlapping_metrics = self._metrics_from_rows(independent)
            for metrics in (raw_metrics, non_overlapping_metrics):
                metrics["brier_improvement_vs_0_5"] = (
                    None if metrics["brier"] is None else round(0.25 - metrics["brier"], 6)
                )
                metrics["log_loss_improvement_vs_0_5"] = (
                    None
                    if metrics["log_loss"] is None
                    else round(math.log(2) - metrics["log_loss"], 6)
                )
            matured_n = counts["resolved_n"] + counts["target_price_missing_n"]
            result["horizons"][horizon.value] = {
                **counts,
                "pending_n": max(0, counts["forecast_n"] - matured_n),
                "target_resolution_coverage": (
                    None if matured_n == 0 else round(counts["resolved_n"] / matured_n, 6)
                ),
                "raw_metrics": raw_metrics,
                "non_overlapping_metrics": non_overlapping_metrics,
                "calibration_bands": self._calibration_bands(rows, independent),
                "threshold_curve": self._threshold_curve(rows, independent),
                "estimate_modes": self._realtime_rolling_mode_counts(horizon),
            }
            total_resolved += counts["resolved_n"]
        if total_resolved:
            result["status"] = "EVALUATING_NOT_FORMAL"
        return result

    def _realtime_rolling_counts(self, horizon: Horizon) -> dict[str, int]:
        with self._connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS forecast_n,
                SUM(CASE WHEN r.resolution_status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_n,
                SUM(CASE WHEN r.resolution_status = 'TARGET_PRICE_MISSING' THEN 1 ELSE 0 END)
                    AS target_price_missing_n
                FROM realtime_rolling_forecasts f
                LEFT JOIN realtime_rolling_resolutions r USING(forecast_id)
                WHERE f.horizon = ?""",
                (horizon.value,),
            ).fetchone()
        return {
            "forecast_n": int(row["forecast_n"] or 0),
            "resolved_n": int(row["resolved_n"] or 0),
            "target_price_missing_n": int(row["target_price_missing_n"] or 0),
        }

    def _realtime_rolling_resolved_rows(self, horizon: Horizon) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT f.origin_time_utc, f.p_up, r.outcome_up
                FROM realtime_rolling_forecasts f
                JOIN realtime_rolling_resolutions r USING(forecast_id)
                WHERE f.horizon = ? AND r.resolution_status = 'RESOLVED'
                ORDER BY f.origin_time_utc""",
                (horizon.value,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _realtime_rolling_mode_counts(self, horizon: Horizon) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT f.estimate_mode, COUNT(*) AS forecast_n,
                SUM(CASE WHEN r.resolution_status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_n
                FROM realtime_rolling_forecasts f
                LEFT JOIN realtime_rolling_resolutions r USING(forecast_id)
                WHERE f.horizon = ?
                GROUP BY f.estimate_mode ORDER BY f.estimate_mode""",
                (horizon.value,),
            ).fetchall()
        return [
            {
                "estimate_mode": row["estimate_mode"],
                "forecast_n": int(row["forecast_n"] or 0),
                "resolved_n": int(row["resolved_n"] or 0),
            }
            for row in rows
        ]

    def _metrics(self, horizon: Horizon | None) -> dict[str, Any]:
        rows = self._resolved_rows(horizon)
        return self._metrics_from_rows(rows)

    @staticmethod
    def _metrics_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"resolved_n": 0, "brier": None, "log_loss": None, "accuracy": None}
        probabilities = [float(row["p_up"]) for row in rows]
        outcomes = [int(row["outcome_up"]) for row in rows]
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes, strict=True)) / len(rows)
        log_loss = -sum(
            y * math.log(max(p, 1e-12)) + (1 - y) * math.log(max(1 - p, 1e-12))
            for p, y in zip(probabilities, outcomes, strict=True)
        ) / len(rows)
        accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(probabilities, outcomes, strict=True))
        return {
            "resolved_n": len(rows),
            "brier": round(brier, 6),
            "log_loss": round(log_loss, 6),
            "accuracy": round(accuracy / len(rows), 6),
        }

    def _resolved_rows(self, horizon: Horizon | None) -> list[dict[str, Any]]:
        where = "AND f.horizon = ?" if horizon is not None else ""
        parameters: tuple[str, ...] = () if horizon is None else (horizon.value,)
        with self._connect() as db:
            rows = db.execute(
                f"""SELECT f.origin_time_utc, f.p_up, r.outcome_up
                FROM forecasts f JOIN resolutions r USING(forecast_id)
                WHERE f.recorded_mode = 'PROSPECTIVE' {where}
                ORDER BY f.origin_time_utc""",  # noqa: S608
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _non_overlapping_rows(rows: list[dict[str, Any]], horizon: Horizon) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        last_time: datetime | None = None
        spacing = (
            timedelta(hours=horizon.bars)
            if horizon.interval == "H1"
            else timedelta(minutes=horizon.bars)
        )
        for row in rows:
            origin = datetime.fromisoformat(str(row["origin_time_utc"])).astimezone(UTC)
            if last_time is None or origin - last_time >= spacing:
                selected.append(row)
                last_time = origin
        return selected

    @staticmethod
    def _calibration_bands(
        rows: list[dict[str, Any]], independent: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for index in range(int(1 / CALIBRATION_BIN_WIDTH)):
            lower = round(index * CALIBRATION_BIN_WIDTH, 2)
            upper = round((index + 1) * CALIBRATION_BIN_WIDTH, 2)
            band = [
                row
                for row in rows
                if lower <= float(row["p_up"]) < upper
                or (upper == 1.0 and float(row["p_up"]) == 1.0)
            ]
            if not band:
                continue
            independent_n = sum(
                lower <= float(row["p_up"]) < upper or (upper == 1.0 and float(row["p_up"]) == 1.0)
                for row in independent
            )
            mean_probability = sum(float(row["p_up"]) for row in band) / len(band)
            realized_up = sum(int(row["outcome_up"]) for row in band) / len(band)
            result.append(
                {
                    "lower": lower,
                    "upper": upper,
                    "label": f"{int(lower * 100)}–{int(upper * 100)}%",
                    "sample_n": len(band),
                    "non_overlapping_n": independent_n,
                    "mean_p_up": round(mean_probability, 6),
                    "realized_up_rate": round(realized_up, 6),
                    "calibration_gap": round(realized_up - mean_probability, 6),
                }
            )
        return result

    @classmethod
    def _threshold_curve(
        cls, rows: list[dict[str, Any]], independent: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for threshold in THRESHOLD_CANDIDATES:
            selected = cls._rows_at_threshold(rows, threshold)
            independent_selected = cls._rows_at_threshold(independent, threshold)
            correct = cls._direction_correct_count(selected, threshold)
            independent_correct = cls._direction_correct_count(independent_selected, threshold)
            lower, upper = cls._wilson_interval(independent_correct, len(independent_selected))
            result.append(
                {
                    "buy_threshold": threshold,
                    "sell_threshold": round(1 - threshold, 2),
                    "sample_n": len(selected),
                    "non_overlapping_n": len(independent_selected),
                    "coverage": None if not rows else round(len(selected) / len(rows), 6),
                    "direction_accuracy": None
                    if not selected
                    else round(correct / len(selected), 6),
                    "non_overlapping_accuracy": None
                    if not independent_selected
                    else round(independent_correct / len(independent_selected), 6),
                    "wilson_low": lower,
                    "wilson_high": upper,
                    "is_current_v1": threshold == 0.58,
                }
            )
        return result

    @classmethod
    def _action_breakdown(
        cls, rows: list[dict[str, Any]], independent: list[dict[str, Any]]
    ) -> dict[str, Any]:
        def selected(source: list[dict[str, Any]], action: str) -> list[dict[str, Any]]:
            if action == "buy":
                return [row for row in source if float(row["p_up"]) >= BUY_THRESHOLD]
            if action == "sell":
                return [row for row in source if float(row["p_up"]) <= SELL_THRESHOLD]
            return [
                row
                for row in source
                if SELL_THRESHOLD < float(row["p_up"]) < BUY_THRESHOLD
            ]

        items: dict[str, Any] = {}
        for action in ("buy", "sell", "stay"):
            action_rows = selected(rows, action)
            independent_rows = selected(independent, action)
            up_count = sum(int(row["outcome_up"]) for row in action_rows)
            down_count = len(action_rows) - up_count
            independent_up = sum(int(row["outcome_up"]) for row in independent_rows)
            independent_down = len(independent_rows) - independent_up
            up_low, up_high = cls._wilson_interval(independent_up, len(independent_rows))
            down_low, down_high = cls._wilson_interval(
                independent_down, len(independent_rows)
            )
            direction_correct = up_count if action == "buy" else down_count
            independent_correct = independent_up if action == "buy" else independent_down
            direction_low, direction_high = (
                (None, None)
                if action == "stay"
                else cls._wilson_interval(independent_correct, len(independent_rows))
            )
            items[action] = {
                "sample_n": len(action_rows),
                "coverage": None
                if not rows
                else round(len(action_rows) / len(rows), 6),
                "direction_accuracy": None
                if action == "stay" or not action_rows
                else round(direction_correct / len(action_rows), 6),
                "realized_up_rate": None
                if not action_rows
                else round(up_count / len(action_rows), 6),
                "realized_down_rate": None
                if not action_rows
                else round(down_count / len(action_rows), 6),
                "non_overlapping_n": len(independent_rows),
                "non_overlapping_direction_accuracy": None
                if action == "stay" or not independent_rows
                else round(independent_correct / len(independent_rows), 6),
                "non_overlapping_realized_up_rate": None
                if not independent_rows
                else round(independent_up / len(independent_rows), 6),
                "non_overlapping_realized_down_rate": None
                if not independent_rows
                else round(independent_down / len(independent_rows), 6),
                "wilson_low": direction_low,
                "wilson_high": direction_high,
                "up_wilson_low": up_low,
                "up_wilson_high": up_high,
                "down_wilson_low": down_low,
                "down_wilson_high": down_high,
            }
        return {
            "buy_threshold": BUY_THRESHOLD,
            "sell_threshold": SELL_THRESHOLD,
            "total_resolved_n": len(rows),
            "items": items,
            "confidence_interval_basis": "NON_OVERLAPPING_WILSON_95",
            "cost_adjusted_stay_fit_available": False,
        }

    @staticmethod
    def _rows_at_threshold(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if float(row["p_up"]) >= threshold or float(row["p_up"]) <= 1 - threshold
        ]

    @staticmethod
    def _direction_correct_count(rows: list[dict[str, Any]], threshold: float) -> int:
        return sum(
            (float(row["p_up"]) >= threshold and int(row["outcome_up"]) == 1)
            or (float(row["p_up"]) <= 1 - threshold and int(row["outcome_up"]) == 0)
            for row in rows
        )

    @staticmethod
    def _wilson_interval(correct: int, total: int) -> tuple[float | None, float | None]:
        if total == 0:
            return None, None
        z = 1.959963984540054
        proportion = correct / total
        denominator = 1 + z * z / total
        center = (proportion + z * z / (2 * total)) / denominator
        margin = (
            z
            * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
            / denominator
        )
        return round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)

    def export_safe_json(self) -> str:
        return json.dumps(self.validation_summary(), ensure_ascii=False, sort_keys=True)
