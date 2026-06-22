"""Local shadow-session runner: candles -> SignalFn -> ShadowTrader -> log + summary.

Pure/local: takes an already-fetched candle series, runs no-order shadow steps, writes
events.jsonl + summary.json + metadata.json under <out_root>/<run_id>/, and returns the
summary dict. No network here (the caller fetches candles), no orders, no Private API,
no secret. Output dirs (shadow_exports/) are gitignored and must never be committed.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.shadow.audit import AuditLogWriteError, write_audit_event
from app.shadow.audit_schema import (
    KillSwitchAuditRecord,
    SignalDecisionAuditRecord,
    VirtualResultAuditRecord,
)
from app.shadow.models import Candle, ShadowEvent, Signal, Ticker, shadow_safety
from app.shadow.risk import (
    Disposition,
    KillSwitchReason,
    KillSwitchState,
    RiskContext,
    RiskPolicy,
    RiskStatus,
    SignalLabel,
    SpreadProvenance,
    can_process_virtual_result,
    canonical_timestamp,
    create_order_candidate,
    evaluate,
    signal_label_from_side,
)
from app.shadow.service import ShadowTrader, SignalFn
from app.shadow.signals import momentum_signal

RiskTickerFn = Callable[[Candle], Ticker]


def make_mock_candles(count: int, *, start: float = 150.0, step: float = 0.1) -> list[Candle]:
    """Deterministic zig-zag candles for offline/mock shadow runs (no network)."""
    candles: list[Candle] = []
    price = start
    for i in range(count):
        delta = step if i % 2 == 0 else -step
        open_ = price
        close = round(price + delta, 5)
        candles.append(
            Candle(
                time=f"t{i:04d}",
                open=open_,
                high=round(max(open_, close) + 0.05, 5),
                low=round(min(open_, close) - 0.05, 5),
                close=close,
            )
        )
        price = close
    return candles


def _ticker_from_candle(symbol: str, candle: Candle) -> Ticker:
    # Shadow uses the candle close as both bid/ask (zero synthetic spread) for fill/PnL.
    return Ticker(symbol=symbol, bid=candle.close, ask=candle.close, time=candle.time)


def _canonical_or_fallback(value: str, fallback: datetime) -> str:
    try:
        return canonical_timestamp(value)
    except (TypeError, ValueError):
        return canonical_timestamp(fallback)


def _event_without_order(
    trader: ShadowTrader,
    *,
    signal: Signal,
    ticker: Ticker,
    halted: bool | None = None,
    halt_reason: str | None = None,
) -> ShadowEvent:
    event = ShadowEvent(
        time=ticker.time,
        symbol=trader.symbol,
        signal=signal,
        virtual_order=None,
        position_side=trader.position.side,
        position_units=trader.position.units,
        position_avg_price=trader.position.avg_price,
        virtual_pnl=trader.position.unrealized_pnl(ticker.mid),
        halted=trader.halted if halted is None else halted,
        halt_reason=trader.halt_reason if halt_reason is None else halt_reason,
        safety=shadow_safety(),
    )
    trader.events.append(event)
    return event


def run_shadow_session(
    *,
    symbol: str,
    interval: str,
    source: str,
    candles: list[Candle],
    out_root: str | Path,
    steps: int,
    run_id: str | None = None,
    units: int = 1,
    max_units: int = 100,
    signal_fn: SignalFn = momentum_signal,
    enable_shadow_risk: bool = False,
    risk_ticker_fn: RiskTickerFn | None = None,
    stop_file: str | Path | None = None,
) -> dict:
    """Run a bounded, no-order shadow session and persist events + summary. Returns summary."""
    created_at_dt = datetime.now(UTC)
    created_at = created_at_dt.isoformat()
    run_id = run_id or (
        f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_shadow_{symbol}_{source}"
    )
    steps_requested = steps
    usable = candles[: max(0, steps)]
    trader = ShadowTrader(symbol, signal_fn, units=units, max_units=max_units)

    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    buy = sell = flat = 0
    orders = 0
    max_abs_units = 0
    last_price = None
    event_rows: list[dict] = []
    exit_code = 0
    risk_summary: dict[str, object] = {}

    if not enable_shadow_risk:
        for i in range(len(usable)):
            candle = usable[i]
            ticker = _ticker_from_candle(symbol, candle)
            event = trader.step(usable[: i + 1], ticker)
            last_price = candle.close
            if event.signal.side == "buy":
                buy += 1
            elif event.signal.side == "sell":
                sell += 1
            else:
                flat += 1
            if event.virtual_order is not None:
                orders += 1
            max_abs_units = max(max_abs_units, event.position_units)
            row = {
                "run_id": run_id,
                "source": source,
                "interval": interval,
                **asdict(event),
            }
            event_rows.append(row)
    else:
        policy = RiskPolicy()
        kill_switch = KillSwitchState()
        stop_path = Path(stop_file) if stop_file is not None else Path(out_root) / "STOP"
        candidate_count = 0
        risk_allow_count = 0
        risk_reject_count = 0
        kill_switch_count = 0
        audit_log_write_error_count = 0
        existing_candidate_ids: set[str] = set()
        last_candidate_timestamp: str | None = None
        kill_switch_reason = ""

        def write_required_audit(event_type: str, payload: object) -> bool:
            nonlocal audit_log_write_error_count
            try:
                write_audit_event(
                    run_dir.parent,
                    run_id=run_id,
                    event_type=event_type,
                    payload=payload,
                )
                return True
            except AuditLogWriteError:
                audit_log_write_error_count += 1
                return False

        def activate_kill_switch(
            reason: KillSwitchReason,
            *,
            timestamp: str,
            trigger: str,
            write_log: bool = True,
        ) -> None:
            nonlocal exit_code, kill_switch, kill_switch_count, kill_switch_reason
            if not kill_switch.active:
                kill_switch = kill_switch.activate(
                    reason,
                    timestamp=timestamp,
                    safety_snapshot={
                        key: value
                        for key, value in shadow_safety().items()
                        if key != "gmo_readonly"
                    },
                )
                kill_switch_count += 1
                kill_switch_reason = reason.value
            trader.halted = True
            trader.halt_reason = reason.value
            exit_code = 2
            if write_log:
                record = KillSwitchAuditRecord(
                    run_id=run_id,
                    timestamp=timestamp,
                    active=True,
                    reasons=kill_switch.reasons,
                    activated_at=kill_switch.activated_at,
                    trigger=trigger,
                )
                write_required_audit("kill_switch_log", record)

        def stop_requested() -> bool:
            return stop_path.exists()

        if stop_requested():
            activate_kill_switch(
                KillSwitchReason.MANUAL_STOP_FILE_EXISTS,
                timestamp=canonical_timestamp(created_at_dt),
                trigger="manual_stop_file_exists",
            )

        for i in range(len(usable)):
            if kill_switch.active:
                break
            candle = usable[i]
            fallback_time = created_at_dt
            market_timestamp = _canonical_or_fallback(candle.time, fallback_time)
            ticker = _ticker_from_candle(symbol, candle)
            ticker = Ticker(
                symbol=ticker.symbol,
                bid=ticker.bid,
                ask=ticker.ask,
                time=market_timestamp,
            )
            last_price = candle.close

            if stop_requested():
                activate_kill_switch(
                    KillSwitchReason.MANUAL_STOP_FILE_EXISTS,
                    timestamp=market_timestamp,
                    trigger="manual_stop_file_exists",
                )
                break

            signal = signal_fn(usable[: i + 1])
            signal_label = signal_label_from_side(signal.side)
            if signal.side == "buy":
                buy += 1
            elif signal.side == "sell":
                sell += 1
            else:
                flat += 1

            disposition = (
                Disposition.NO_TRADE
                if signal_label is SignalLabel.HOLD
                else Disposition.CANDIDATE_CREATED
            )
            signal_record = SignalDecisionAuditRecord(
                run_id=run_id,
                timestamp=market_timestamp,
                step_index=i,
                signal_label=signal_label,
                disposition=disposition,
                reason_codes=(),
                market_data_timestamp=market_timestamp,
                source=source,
                symbol=symbol,
                interval=interval,
                signal_name=getattr(signal_fn, "__name__", "signal_fn"),
            )
            if not write_required_audit("signal_decision_log", signal_record):
                activate_kill_switch(
                    KillSwitchReason.LOG_WRITE_FAILED,
                    timestamp=market_timestamp,
                    trigger="signal_decision_log",
                    write_log=False,
                )
                break

            if signal_label is SignalLabel.HOLD:
                event = _event_without_order(trader, signal=signal, ticker=ticker)
                max_abs_units = max(max_abs_units, event.position_units)
                event_rows.append({
                    "run_id": run_id,
                    "source": source,
                    "interval": interval,
                    **asdict(event),
                })
                continue

            risk_ticker = risk_ticker_fn(candle) if risk_ticker_fn is not None else ticker
            risk_market_timestamp = _canonical_or_fallback(risk_ticker.time, fallback_time)
            spread_provenance = (
                SpreadProvenance.REAL_PUBLIC_BID_ASK
                if risk_ticker_fn is not None
                else SpreadProvenance.SYNTHETIC_ZERO
            )
            candidate = create_order_candidate(
                signal_label=signal_label,
                run_id=run_id,
                step_index=i,
                timestamp=market_timestamp,
                market_data_timestamp=risk_market_timestamp,
                source=source,
                symbol=symbol,
                interval=interval,
                quantity=units,
                bid=risk_ticker.bid,
                ask=risk_ticker.ask,
                spread_provenance=spread_provenance,
                signal_name=getattr(signal_fn, "__name__", "signal_fn"),
                signal_reason=signal.reason or "signal",
                confidence=0.5,
                kill_switch=kill_switch,
            )
            if candidate is None:
                event = _event_without_order(trader, signal=signal, ticker=ticker)
                max_abs_units = max(max_abs_units, event.position_units)
                event_rows.append({
                    "run_id": run_id,
                    "source": source,
                    "interval": interval,
                    **asdict(event),
                })
                continue

            if not write_required_audit("candidate_log", candidate):
                activate_kill_switch(
                    KillSwitchReason.LOG_WRITE_FAILED,
                    timestamp=market_timestamp,
                    trigger="candidate_log",
                    write_log=False,
                )
                break
            candidate_count += 1

            context = RiskContext(
                evaluation_time=datetime.fromisoformat(
                    market_timestamp.replace("Z", "+00:00")
                ).astimezone(UTC),
                spread_provenance=spread_provenance,
                candidates_in_run=candidate_count - 1,
                candidates_today=candidate_count - 1,
                existing_candidate_ids=frozenset(existing_candidate_ids),
                last_candidate_timestamp=last_candidate_timestamp,
                market_closed=False,
                kill_switch=kill_switch,
            )
            decision = evaluate(candidate, context, policy)
            if not write_required_audit("risk_decision_log", decision):
                activate_kill_switch(
                    KillSwitchReason.LOG_WRITE_FAILED,
                    timestamp=market_timestamp,
                    trigger="risk_decision_log",
                    write_log=False,
                )
                break
            existing_candidate_ids.add(candidate.candidate_id)
            last_candidate_timestamp = candidate.market_data_timestamp

            if decision.status is RiskStatus.REJECT_SHADOW:
                risk_reject_count += 1
                event = _event_without_order(trader, signal=signal, ticker=ticker)
                max_abs_units = max(max_abs_units, event.position_units)
                event_rows.append({
                    "run_id": run_id,
                    "source": source,
                    "interval": interval,
                    **asdict(event),
                })
                continue

            risk_allow_count += 1
            if stop_requested():
                activate_kill_switch(
                    KillSwitchReason.MANUAL_STOP_FILE_EXISTS,
                    timestamp=market_timestamp,
                    trigger="manual_stop_file_exists",
                )
                break
            if not can_process_virtual_result(kill_switch, decision):
                event = _event_without_order(trader, signal=signal, ticker=ticker)
                max_abs_units = max(max_abs_units, event.position_units)
                event_rows.append({
                    "run_id": run_id,
                    "source": source,
                    "interval": interval,
                    **asdict(event),
                })
                continue

            fill_ticker = Ticker(
                symbol=symbol,
                bid=risk_ticker.bid,
                ask=risk_ticker.ask,
                time=risk_market_timestamp,
            )
            event = trader.step(usable[: i + 1], fill_ticker)
            if event.virtual_order is not None:
                orders += 1
            max_abs_units = max(max_abs_units, event.position_units)
            virtual_result = VirtualResultAuditRecord(
                run_id=run_id,
                timestamp=risk_market_timestamp,
                candidate_id=candidate.candidate_id,
                decision_id=decision.decision_id,
                status="HALTED" if event.halted else "VIRTUAL_RESULT",
                position_side=event.position_side,
                units=event.position_units,
                unrealized_pnl=event.virtual_pnl,
            )
            if not write_required_audit("virtual_result_log", virtual_result):
                activate_kill_switch(
                    KillSwitchReason.LOG_WRITE_FAILED,
                    timestamp=market_timestamp,
                    trigger="virtual_result_log",
                    write_log=False,
                )
                break
            event_rows.append({
                "run_id": run_id,
                "source": source,
                "interval": interval,
                **asdict(event),
            })

        risk_summary = {
            "shadow_risk_enabled": True,
            "candidate_count": candidate_count,
            "risk_allow_count": risk_allow_count,
            "risk_reject_count": risk_reject_count,
            "kill_switch_count": kill_switch_count,
            "kill_switch_active": kill_switch.active,
            "kill_switch_reason": kill_switch_reason,
            "invalid_risk_row_count": 0,
            "audit_log_write_error_count": audit_log_write_error_count,
            "safety_violation_count": 1 if exit_code == 2 else 0,
            "exit_code": exit_code,
        }

    with (run_dir / "events.jsonl").open("w") as fh:
        for row in event_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "run_id": run_id,
        "source": source,
        "symbol": symbol,
        "interval": interval,
        "steps_requested": steps_requested,
        "steps_executed": len(event_rows),
        "events_count": len(event_rows),
        "virtual_orders_count": orders,
        "buy_count": buy,
        "sell_count": sell,
        "flat_count": flat,
        "max_abs_units": max_abs_units,
        "final_position_side": trader.position.side,
        "final_position_units": trader.position.units,
        "final_average_price": trader.position.avg_price,
        "final_unrealized_pnl": (
            trader.position.unrealized_pnl(last_price) if last_price is not None else 0.0
        ),
        "last_price": last_price,
        "data_points": len(candles),
        "halted": trader.halted,
        "halt_reason": trader.halt_reason,
        "safety": shadow_safety(),
        "created_at": created_at,
    }
    summary.update(risk_summary)
    with (run_dir / "summary.json").open("w") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    metadata = {
        "run_id": run_id,
        "source": source,
        "symbol": symbol,
        "interval": interval,
        "steps_requested": steps_requested,
        "units": units,
        "max_units": max_units,
        "signal": "momentum_signal (demo only; NOT a profitability claim)",
        "created_at": created_at,
        "safety": shadow_safety(),
        "note": "Local shadow run. No real order / Private API / API key. Do not commit outputs.",
    }
    if risk_summary:
        metadata.update({
            "shadow_risk_enabled": True,
            "exit_code": exit_code,
            "halt_reason": summary["halt_reason"],
        })
    with (run_dir / "metadata.json").open("w") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)

    return summary
