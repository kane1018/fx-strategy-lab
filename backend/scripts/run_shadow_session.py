"""Local CLI: run a bounded, no-order shadow session and save events + summary.

source=mock  : deterministic offline candles (no network).
source=gmo-public : fetch candles from the GMO **Public** API (read-only, no auth).
NO orders, NO Private API, NO API key / secret / .env. Output goes under
`shadow_exports/<run_id>/` (gitignored) and is NEVER committed. Bounded by --steps.

Usage:
    python -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 20
    python -m scripts.run_shadow_session --source gmo-public --symbol USD_JPY \
        --interval M1 --date 20260618 --steps 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.shadow.gmo_public import GmoPublicError, GmoPublicMarketDataClient
from app.shadow.risk import RiskPolicy
from app.shadow.session import make_mock_candles, run_shadow_session


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a local no-order shadow session (mock or GMO Public read-only)."
    )
    parser.add_argument("--source", choices=["mock", "gmo-public"], default="mock")
    parser.add_argument("--symbol", default="USD_JPY", help="BASE_QUOTE, e.g. USD_JPY")
    parser.add_argument("--interval", default="M1", help="internal TF (M1/M5..) or GMO interval")
    parser.add_argument("--date", default=None, help="YYYYMMDD (gmo-public klines; default today)")
    parser.add_argument("--steps", type=int, default=20, help="max steps (bounded; no loop)")
    parser.add_argument("--units", type=int, default=1)
    parser.add_argument("--max-units", type=int, default=100)
    parser.add_argument("--out-root", default="shadow_exports", help="output dir (gitignored)")
    parser.add_argument(
        "--enable-shadow-risk",
        action="store_true",
        help="enable local-only Phase 2E risk/audit JSONL integration",
    )
    args = parser.parse_args()

    if args.steps <= 0:
        print("ERROR: --steps must be positive")
        return 1

    if args.enable_shadow_risk:
        policy = RiskPolicy()
        if args.symbol not in policy.allowed_symbols:
            print(f"ERROR: --enable-shadow-risk supports symbols: {policy.allowed_symbols}")
            return 1
        if args.interval not in policy.allowed_intervals:
            print(f"ERROR: --enable-shadow-risk supports intervals: {policy.allowed_intervals}")
            return 1
        stop_path = Path(args.out_root) / "STOP"
        if stop_path.exists():
            summary = run_shadow_session(
                symbol=args.symbol,
                interval=args.interval,
                source=args.source,
                candles=[],
                out_root=args.out_root,
                steps=args.steps,
                units=args.units,
                max_units=args.max_units,
                enable_shadow_risk=True,
            )
            print(f"run_id: {summary['run_id']}")
            print(f"output: {args.out_root}/{summary['run_id']}/")
            print("files: events.jsonl, summary.json, metadata.json, risk/audit JSONL")
            print(f"halted={summary['halted']} halt_reason={summary['halt_reason']}")
            return int(summary["exit_code"])

    if args.source == "mock":
        candles = make_mock_candles(args.steps)
    else:
        try:
            client = GmoPublicMarketDataClient()
            candles = client.fetch_candles(
                args.symbol, args.interval, limit=args.steps, date=args.date
            )
        except GmoPublicError as error:
            # Do not fall back to any authenticated/Private path.
            print(f"ERROR: {error}")
            return 1

    summary = run_shadow_session(
        symbol=args.symbol,
        interval=args.interval,
        source=args.source,
        candles=candles,
        out_root=args.out_root,
        steps=args.steps,
        units=args.units,
        max_units=args.max_units,
        enable_shadow_risk=args.enable_shadow_risk,
    )
    print(f"run_id: {summary['run_id']}")
    print(f"output: {args.out_root}/{summary['run_id']}/")
    if args.enable_shadow_risk:
        print("files: events.jsonl, summary.json, metadata.json, risk/audit JSONL")
    else:
        print("files: events.jsonl, summary.json, metadata.json")
    print(
        f"steps_executed={summary['steps_executed']} orders={summary['virtual_orders_count']} "
        f"final_position={summary['final_position_side']}:{summary['final_position_units']} "
        f"pnl={summary['final_unrealized_pnl']:.5f} halted={summary['halted']}"
    )
    if args.enable_shadow_risk:
        print(
            f"shadow_risk candidates={summary['candidate_count']} "
            f"allow={summary['risk_allow_count']} reject={summary['risk_reject_count']} "
            f"kill_switch={summary['kill_switch_active']} exit_code={summary['exit_code']}"
        )
    print(f"safety.real_order={summary['safety']['real_order']} (no-order shadow run)")
    return int(summary.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
