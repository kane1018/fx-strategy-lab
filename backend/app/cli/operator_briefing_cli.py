"""Read-only CLI for the operator pre-trade caution briefing (no-POST).

Run: ``python -m app.cli.operator_briefing_cli [flags]``

Local I/O only (args in, warning-first text out). NO network / trading-venue /
fetch / private data read / env / secret access, NO POST, NO execution, never
triggers a Safe Execution & Risk Engine. It only wraps the existing read-only
pure functions and prints their safe text.

The system NEVER decides: ``--decision`` records the OPERATOR's OWN decision
(with ``--reason``); it is not a recommendation. No direction / confidence /
alpha / expected-profit / win-rate is produced. ``performance_proof_status`` /
``live_ready`` stay false.
"""

from __future__ import annotations

import argparse

from app.services.operator_briefing_safe_label_supply import SafeLabelSupplyRequest
from app.services.operator_briefing_session import (
    OperatorDecisionLabel,
    record_operator_decision,
    render_operator_briefing_session,
    start_operator_briefing_session,
)

# Operator-supplied decision (short flag value) -> operator-recorded label.
_DECISION_MAP: dict[str, OperatorDecisionLabel] = {
    "BUY": OperatorDecisionLabel.OPERATOR_DECIDED_ENTRY_BUY,
    "SELL": OperatorDecisionLabel.OPERATOR_DECIDED_ENTRY_SELL,
    "HOLD": OperatorDecisionLabel.OPERATOR_DECIDED_HOLD,
    "NO_ACTION": OperatorDecisionLabel.OPERATOR_DECIDED_NO_ACTION,
}

_BANNER = (
    "(read-only tool; not advice; the system does not decide; "
    "no-flag != permission; no validated edge)"
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="operator-briefing",
        description=(
            "Read-only operator pre-trade caution briefing. NOT advice, NOT a "
            "recommendation, NOT execution. The operator makes the decision."
        ),
    )
    # SAFE labels only (from the operator's INTERNAL state; never fetched).
    p.add_argument("--exposure")
    p.add_argument("--pending-count", type=int)
    p.add_argument("--pending-status")
    p.add_argument("--risk-budget")
    p.add_argument("--execution-readiness")
    p.add_argument("--trend")
    p.add_argument("--volatility")
    p.add_argument("--spread")
    p.add_argument("--liquidity")
    p.add_argument("--time-of-day")
    p.add_argument("--event")
    p.add_argument("--uncertainty")
    p.add_argument(
        "--context", action="append", default=[],
        help="intended-context label for rejected-ledger caution (repeatable)",
    )
    p.add_argument("--session-label", default="")
    # The operator's OWN decision to record (never produced by the system).
    p.add_argument("--decision", choices=sorted(_DECISION_MAP))
    p.add_argument("--reason", help="operator's reason (required with --decision)")
    return p


def _build_request(args: argparse.Namespace) -> SafeLabelSupplyRequest:
    return SafeLabelSupplyRequest(
        exposure_status=args.exposure,
        pending_order_status=args.pending_status,
        pending_order_safe_count=args.pending_count,
        risk_budget_status=args.risk_budget,
        execution_readiness=args.execution_readiness,
        trend_range=args.trend,
        volatility=args.volatility,
        spread_condition=args.spread,
        liquidity=args.liquidity,
        time_of_day=args.time_of_day,
        event_proximity=args.event,
        uncertainty=args.uncertainty,
        intended_context_labels=tuple(args.context),
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    session = start_operator_briefing_session(
        _build_request(args), session_label=args.session_label
    )
    if args.decision is not None:
        if not args.reason or not args.reason.strip():
            parser.error("--reason is required when --decision is given")
        session = record_operator_decision(
            session, _DECISION_MAP[args.decision], args.reason
        )
    print(_BANNER)
    print(render_operator_briefing_session(session))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
