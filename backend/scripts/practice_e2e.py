"""OANDA practice E2E helper (practice-only; never live).

Read-only by default. Placing a real practice order requires ALL of:
  - OANDA_ENV=practice and ENABLE_LIVE_TRADING=false
  - the instrument is currently tradeable (market open)
  - tiny size (1..10 units)
  - the explicit --confirm flag

Every order still flows through broker_service.place_order -> risk_service
(RiskManager). This script never constructs a live broker and never prints the
API token or account id.

Usage (run from the backend/ directory):
  .venv/bin/python -m scripts.practice_e2e preflight --symbol USD_JPY
  .venv/bin/python -m scripts.practice_e2e order   --symbol USD_JPY --units 1 --side buy --confirm
  .venv/bin/python -m scripts.practice_e2e close   --symbol USD_JPY --confirm
  .venv/bin/python -m scripts.practice_e2e status
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Allow running both as `python -m scripts.practice_e2e` and `python scripts/practice_e2e.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.brokers import OandaBroker, OandaBrokerError  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import OrderLog, Signal  # noqa: E402
from app.schemas.trading import (  # noqa: E402
    AutoTradeConfig,
    ExecutionConfig,
    RiskConfig,
    StrategyConfig,
)
from app.services.automation_service import (  # noqa: E402
    _assert_fresh_price,
    _build_order,
    _positions_snapshot,
    automation_snapshot,
    get_or_create_automation_state,
    stop_automation,
)
from app.services.bot_service import bot_snapshot, start_bot  # noqa: E402
from app.services.broker_service import place_order  # noqa: E402


def _hr(title: str) -> None:
    print("\n" + "=" * 68 + f"\n{title}\n" + "=" * 68)


def _guard_practice() -> None:
    s = get_settings()
    if s.oanda_environment.lower() != "practice":
        print(f"ABORT: OANDA_ENV is '{s.oanda_environment}', must be 'practice'.")
        raise SystemExit(2)
    if s.enable_live_trading:
        print("ABORT: ENABLE_LIVE_TRADING is true. This script is practice-only.")
        raise SystemExit(2)


def _broker() -> OandaBroker:
    try:
        return OandaBroker()
    except OandaBrokerError as error:
        print(f"ABORT: cannot build practice broker: {error}")
        raise SystemExit(2) from error


def _market_state(broker: OandaBroker, symbol: str) -> tuple[str, object]:
    """Return (state, price_or_message). state in tradeable|not_tradeable|error."""
    try:
        price = broker.current_price(symbol)
        return "tradeable", price
    except OandaBrokerError as error:
        msg = str(error)
        if "取引できません" in msg or "tradeable" in msg.lower():
            return "not_tradeable", msg
        return "error", msg


def cmd_preflight(args: argparse.Namespace) -> int:
    s = get_settings()
    _hr("0. Settings (secrets hidden)")
    print(f"OANDA_ENV               = {s.oanda_environment}")
    print(f"OANDA_API_URL           = {s.oanda_api_url}")
    print(f"ENABLE_LIVE_TRADING     = {s.enable_live_trading}")
    print(f"OANDA_API_TOKEN present  = {bool(s.oanda_api_token)}")
    print(f"OANDA_ACCOUNT_ID present = {bool(s.oanda_account_id)}")
    _guard_practice()
    broker = _broker()

    _hr("1. account summary / balance")
    account = broker.account_summary()
    print(
        f"balance={account.balance} {account.currency}  nav={account.nav}  "
        f"open_positions={account.open_position_count}"
    )

    _hr("2. recent candles (M5 x 5)")
    candles = broker.candles(args.symbol, "M5", 5)
    print(f"candles={len(candles)}  last_close={candles[-1].close}")

    _hr("3. open positions")
    positions = _positions_snapshot(broker.open_positions())
    print(positions or "(none)")

    _hr("4. price / tradeable / spread")
    state, payload = _market_state(broker, args.symbol)
    if state == "tradeable":
        price = payload
        age = (datetime.now(UTC) - price.timestamp).total_seconds()  # type: ignore[union-attr]
        print(
            f"TRADEABLE  bid={price.bid} ask={price.ask}  "  # type: ignore[union-attr]
            f"spread={price.spread_pips:.2f} pips  age={age:.1f}s"  # type: ignore[union-attr]
        )
    elif state == "not_tradeable":
        print(f"NOT_TRADEABLE (market likely closed): {payload}")
    else:
        print(f"PRICE ERROR: {payload}")

    _hr("VERDICT")
    if state == "tradeable":
        print("READY: market is open. You may run `order --confirm` for a tiny E2E order.")
        return 0
    print("NOT READY: market_closed / not_tradeable. Wait for market hours and re-run preflight.")
    return 0


def cmd_order(args: argparse.Namespace) -> int:
    _guard_practice()
    if not args.confirm:
        print("ABORT: refusing to place a real practice order without --confirm.")
        return 2
    if not (1 <= args.units <= 10):
        print(f"ABORT: units must be 1..10 for E2E (got {args.units}).")
        return 2
    if args.side not in {"buy", "sell"}:
        print("ABORT: --side must be buy or sell.")
        return 2

    broker = _broker()
    state, payload = _market_state(broker, args.symbol)
    if state != "tradeable":
        print(f"ABORT: market not tradeable ({state}): {payload}. Will not order.")
        return 2
    price = payload
    _assert_fresh_price(price.timestamp)  # type: ignore[union-attr]
    account = broker.account_summary()

    config = AutoTradeConfig(
        symbol=args.symbol,
        timeframe="M5",
        strategy=StrategyConfig(),
        execution=ExecutionConfig(
            fixed_units=float(args.units),
            stop_loss_pips=args.stop_pips,
            take_profit_pips=args.tp_pips,
        ),
        risk=RiskConfig(max_units=max(10, args.units), max_positions=1),
    )

    with SessionLocal() as db:
        # E2E signal, clearly labelled and practice-only.
        db.add(
            Signal(
                monitor_id="e2e",
                symbol=args.symbol,
                timeframe="M5",
                strategy_name="e2e_practice_test",
                side=args.side,
                price=price.midpoint,  # type: ignore[union-attr]
                stop_loss=0.0,
                take_profit=0.0,
                reason="e2e_practice_test: 接続確認用Signal（利益目的ではありません）",
                risk_percent=config.execution.risk_percent,
                notice="OANDA practice専用のE2E検証Signal。実資金注文には使用しません。",
            )
        )
        db.commit()

        # Bring the bot up in practice mode so place_order's practice gate passes.
        start_bot(db, "practice")
        state_row = get_or_create_automation_state(db)
        state_row.enabled = True
        state_row.environment = "practice"
        state_row.config_json = config.model_dump(mode="json")
        db.commit()

        entry = price.ask if args.side == "buy" else price.bid  # type: ignore[union-attr]
        order = _build_order(
            config,
            args.side,
            entry,
            account.balance,
            price.spread_pips,  # type: ignore[union-attr]
            price.quote_home_conversion,  # type: ignore[union-attr]
        )
        order.client_order_id = f"E2E-PRACTICE-{uuid4().hex[:18].upper()}"

        _hr("placing practice order via place_order (RiskManager enforced)")
        result = place_order(
            db,
            order,
            config.risk,
            broker=broker,
            open_positions_override=len(_positions_snapshot(broker.open_positions())),
        )
        print(
            f"side={args.side} units={order.units} entry={entry} "
            f"SL={order.stop_loss} TP={order.take_profit}"
        )
        print("result:", result)
        return 0 if result.get("accepted") else 1


def _reconcile_close(db, symbol: str, result) -> None:  # type: ignore[no-untyped-def]
    logs = db.scalars(
        select(OrderLog).where(
            OrderLog.mode == "practice",
            OrderLog.symbol == symbol,
            OrderLog.status == "filled",
        )
    ).all()
    for log in logs:
        trade_id = str(log.risk_check_json.get("trade_id") or "")
        if trade_id and trade_id in result.closed_trade_ids:
            log.status = "closed"
            log.realized_pnl = result.realized_pnl
            log.closed_at = datetime.utcnow()
            log.reason = "E2E practice決済を照合済み"
    db.commit()


def cmd_close(args: argparse.Namespace) -> int:
    _guard_practice()
    if not args.confirm:
        print("ABORT: refusing to close without --confirm.")
        return 2
    broker = _broker()
    positions = _positions_snapshot(broker.open_positions())
    target = next((p for p in positions if p["symbol"] == args.symbol), None)
    if not target:
        print(f"No open practice position for {args.symbol}. Nothing to close.")
        return 0
    _hr("closing practice position")
    try:
        result = broker.close_position(args.symbol, target["side"])
    except OandaBrokerError as error:
        print(f"CLOSE FAILED (not treated as success): {error}")
        return 1
    print(
        f"closed side={target['side']} fill={result.filled_price} "
        f"realized_pnl={result.realized_pnl} tx={result.fill_transaction_id}"
    )
    with SessionLocal() as db:
        _reconcile_close(db, args.symbol, result)
        stop_automation(db, "E2E完了による停止")
    print("bot + automation stopped.")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        _hr("bot status")
        print(bot_snapshot(db))
        _hr("automation snapshot")
        snap = automation_snapshot(db)
        for key in ("enabled", "environment", "last_order_id", "consecutive_failures"):
            print(f"{key} = {snap.get(key)}")
        _hr("recent order logs")
        logs = db.scalars(select(OrderLog).order_by(OrderLog.id.desc()).limit(5)).all()
        for log in logs:
            print(
                f"#{log.id} {log.mode} {log.symbol} {log.side} u={log.units} "
                f"{log.status} fill={log.filled_price} pnl={log.realized_pnl}"
            )
    return 0


def main() -> int:
    Base.metadata.create_all(bind=engine)
    parser = argparse.ArgumentParser(description="OANDA practice E2E helper (practice-only).")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("preflight", help="read-only connection + market check")
    p.add_argument("--symbol", default="USD_JPY")
    p.set_defaults(func=cmd_preflight)

    p = sub.add_parser("order", help="place ONE tiny practice order (needs --confirm)")
    p.add_argument("--symbol", default="USD_JPY")
    p.add_argument("--units", type=int, default=1)
    p.add_argument("--side", default="buy")
    p.add_argument("--stop-pips", dest="stop_pips", type=float, default=20.0)
    p.add_argument("--tp-pips", dest="tp_pips", type=float, default=40.0)
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(func=cmd_order)

    p = sub.add_parser("close", help="close the practice position (needs --confirm)")
    p.add_argument("--symbol", default="USD_JPY")
    p.add_argument("--confirm", action="store_true")
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("status", help="print bot/automation/order-log snapshot")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
