"""Shared definitions for the GMO Public read-only paper 15-window evaluations.

Single home for the things every 15-window runner must agree on: the standard
window set, the fixed config (M5 / current_cost / SL30 / TP60 / 4 JPY pairs), the
read-only safety metadata, run-id naming, and the 3-way classification verdict.

Runners import from here so a new strategy/timeframe can be evaluated under the
exact same protocol (see docs/fx_strategy_evaluation_protocol.md). This module is
library-only: it performs NO network or broker I/O.

No real orders, no Private API, no API key/secret.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.trading import ExecutionConfig  # noqa: E402

# Re-exported from the original helper module so runners can import everything
# they need from one place. (robustness_windows holds the per-trade summarizers.)
from scripts.robustness_windows import (  # noqa: E402,F401
    _FORCED,
    _OPP,
    _SL,
    _STAT_FIELDS,
    _exit_category,
    _mem,
    _summarize,
    _weekdays,
    robustness_summary,
)

EXPORT_ROOT = Path(__file__).resolve().parent.parent.parent / "analysis_exports"

# --- standard fixed config (M5 / current_cost; never tuned per the protocol) ---
SYMBOLS = ["USD_JPY", "EUR_JPY", "GBP_JPY", "AUD_JPY"]
TIMEFRAME = "M5"
SPREAD, SLIP = ExecutionConfig().spread_pips, ExecutionConfig().slippage_pips
STOP_LOSS_PIPS = ExecutionConfig().stop_loss_pips
TAKE_PROFIT_PIPS = ExecutionConfig().take_profit_pips
EXIT_POLICY = "baseline"
DATA_SOURCE = "GMO Public API klines (BID), read-only"

# (label, start, end, group) — 10 prior independent weeks + 5 OOS weeks.
WINDOWS = [
    ("window_1", "20260504", "20260515", "prior10"),
    ("window_2", "20260420", "20260501", "prior10"),
    ("window_3", "20260406", "20260417", "prior10"),
    ("window_4", "20260323", "20260403", "prior10"),
    ("window_5", "20260309", "20260320", "prior10"),
    ("window_6", "20260223", "20260306", "prior10"),
    ("window_7", "20260209", "20260220", "prior10"),
    ("window_8", "20260126", "20260206", "prior10"),
    ("window_9", "20260112", "20260123", "prior10"),
    ("window_10", "20251229", "20260109", "prior10"),
    ("oos_window_1", "20251215", "20251226", "oos5"),
    ("oos_window_2", "20251201", "20251212", "oos5"),
    ("oos_window_3", "20251117", "20251128", "oos5"),
    ("oos_window_4", "20251103", "20251114", "oos5"),
    ("oos_window_5", "20251020", "20251031", "oos5"),
]


def window_groups() -> dict[str, str]:
    """Map each window label to its group ('prior10' / 'oos5')."""
    return {label: group for label, _s, _e, group in WINDOWS}


def group_labels(group: str) -> list[str]:
    return [label for label, _s, _e, g in WINDOWS if g == group]


def run_id(kind: str) -> str:
    """Timestamped run id, e.g. '20260616_120000_gmo_public_paper_<kind>'."""
    return datetime.now().strftime("%Y%m%d_%H%M%S") + f"_gmo_public_paper_{kind}"


def fixed_config(**overrides: object) -> dict:
    """Standard fixed-config block for manifest.json / warnings.json."""
    config = {
        "data_source": DATA_SOURCE,
        "mode": "read-only paper",
        "timeframe": TIMEFRAME,
        "cost_scenario": "current_cost",
        "spread_pips": SPREAD,
        "slippage_pips": SLIP,
        "stop_loss_pips": STOP_LOSS_PIPS,
        "take_profit_pips": TAKE_PROFIT_PIPS,
        "exit_policy": EXIT_POLICY,
        "symbols": SYMBOLS,
        "continuous_replay": True,
    }
    config.update(overrides)
    return config


def safety_metadata() -> dict:
    """Read-only safety flags asserted by every paper run (no live access)."""
    return {
        "real_order": False,
        "private_api_used": False,
        "api_key_used": False,
        "no_order_execution": True,
        "gmo_readonly": True,
        "gmo_order_enabled": False,
    }


def classify_strategy(
    *,
    median_exp: float,
    median_pf: float,
    positive_windows: int,
    n_windows: int,
    edge_windows: int,
    total_pnl: float,
    prior_median_exp: float,
    oos_median_exp: float,
    symbol_concentrated: bool,
) -> tuple[str, list[str]]:
    """Pure 3-way verdict: 継続検証候補 / 研究用ベースライン / 撤退.

    継続: robustly positive across the whole independent set AND both sub-periods.
    撤退: net non-positive overall (median<=0 or total<=0 or positive windows <=half).
    研究用ベースライン: overall mildly positive but fails robustness (period sign
    flip, OOS negative, PF<=1, or concentration) -> keep only as reference.
    """
    reasons: list[str] = []
    majority = n_windows / 2
    sign_flip = (prior_median_exp > 0) != (oos_median_exp > 0)

    strong_keep = (
        median_exp > 0
        and median_pf > 1
        and positive_windows > majority
        and edge_windows > majority
        and total_pnl > 0
        and prior_median_exp > 0
        and oos_median_exp > 0
        and not symbol_concentrated
    )
    if strong_keep:
        return "継続検証候補", ["全window横断で頑健に正(両期間ともプラス)"]

    retire = median_exp <= 0 or total_pnl <= 0 or positive_windows <= majority
    if median_exp <= 0:
        reasons.append(f"期待値中央値 {median_exp} ≤ 0")
    if median_pf <= 1:
        reasons.append(f"PF中央値 {median_pf} ≤ 1")
    if total_pnl <= 0:
        reasons.append(f"合計損益 {total_pnl} ≤ 0")
    if positive_windows <= majority:
        reasons.append(f"プラスwindow {positive_windows}/{n_windows} が過半未満")
    if sign_flip:
        reasons.append("前10窓とOOS5窓で期待値中央値の符号が反転(期間依存)")
    if oos_median_exp <= 0:
        reasons.append(f"OOS5窓の期待値中央値 {oos_median_exp} ≤ 0")
    if symbol_concentrated:
        reasons.append("損益が単一通貨ペアに偏重")

    if retire:
        return "撤退", reasons
    return "研究用ベースライン", reasons
