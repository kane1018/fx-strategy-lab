"""CLI for the Step 6G controlled fresh preflight execution adapter.

The CLI renders only the adapter safe summary. It does not execute fresh
preflight, HTTP POST, order endpoints, live_order_once, final confirmation,
ledger updates, attempt persistence, actual result receipt, or receipt handoff.
"""

from __future__ import annotations

import sys

from app.live_verification.live_order_real_fresh_preflight_execution_controlled import (
    LiveOrderRealFreshPreflightExecutionControlledInput,
    build_live_order_real_fresh_preflight_execution_controlled,
    render_live_order_real_fresh_preflight_execution_controlled_markdown,
)
from app.live_verification.live_order_real_fresh_preflight_runtime_controlled import (
    LiveOrderRealFreshPreflightRuntimeControlledInput,
    build_live_order_real_fresh_preflight_runtime_controlled,
)

SAFE_USAGE = (
    "usage: python3 -m app.live_verification."
    "run_fresh_preflight_execution_controlled [--adapter-summary-only | "
    "--simulate-runtime-not-ready]"
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in ([], ["--adapter-summary-only"], ["--no-execution"]):
        result = build_live_order_real_fresh_preflight_execution_controlled()
        print(render_live_order_real_fresh_preflight_execution_controlled_markdown(result))
        return 0 if result.fresh_preflight_execution_allowed_next_step else 2
    if args == ["--simulate-runtime-not-ready"]:
        runtime_result = build_live_order_real_fresh_preflight_runtime_controlled(
            input_snapshot=LiveOrderRealFreshPreflightRuntimeControlledInput(
                fresh_preflight_runtime_requested=False,
            ),
        )
        result = build_live_order_real_fresh_preflight_execution_controlled(
            input_snapshot=LiveOrderRealFreshPreflightExecutionControlledInput(),
            runtime_result=runtime_result,
        )
        print(render_live_order_real_fresh_preflight_execution_controlled_markdown(result))
        return 2

    sys.stderr.write(SAFE_USAGE + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
