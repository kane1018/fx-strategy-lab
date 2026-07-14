"""Append-only local SQLite ledger for forecasts and operator decisions."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.h11_manual.contracts import (
    Direction,
    Horizon,
    ManualExitReason,
    OperatorDecision,
    SignalView,
)

CALIBRATION_BIN_WIDTH = 0.05
THRESHOLD_CANDIDATES = (0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.65)


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
                CREATE TABLE IF NOT EXISTS operator_decisions (
                    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forecast_id TEXT,
                    horizon TEXT NOT NULL,
                    decision TEXT NOT NULL,
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
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_manual_trade_plan
                ON manual_trade_plans(status) WHERE status = 'OPEN';
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

    def record_operator_decision(
        self,
        *,
        forecast_id: str | None,
        horizon: Horizon,
        decision: OperatorDecision,
        note: str = "",
        recorded_at: datetime | None = None,
    ) -> int:
        now = (recorded_at or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO operator_decisions
                (forecast_id, horizon, decision, note, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?)""",
                (forecast_id, horizon.value, decision.value, note[:500], now),
            )
            return int(cursor.lastrowid)

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

    def latest_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM operator_decisions ORDER BY decision_id DESC LIMIT ?",
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
            raise ValueError("an open manual trade plan already exists") from error

    def active_manual_trade_plan(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM manual_trade_plans WHERE status = 'OPEN' LIMIT 1"
            ).fetchone()
        return None if row is None else dict(row)

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
        result: dict[str, Any] = {
            "scope": "PROSPECTIVE_ONLY",
            "threshold_version": "SHORT_V1_FIXED_58_42",
            "threshold_auto_change_allowed": False,
            "overall": self._metrics(None),
            "horizons": {},
            "diagnostics": {},
        }
        for horizon in Horizon:
            result["horizons"][horizon.value] = self._metrics(horizon)
            rows = self._resolved_rows(horizon)
            independent = self._non_overlapping_rows(rows, horizon)
            result["diagnostics"][horizon.value] = {
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
