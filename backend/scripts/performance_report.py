"""Read-only virtual-trading performance report.

Prints aggregated backtest / paper / operational stats from the local DB. Never
calls a broker, never connects to any API, never writes to the DB.

Run from the backend/ directory:
  .venv/bin/python -m scripts.performance_report
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.performance_service import performance_report  # noqa: E402


def _hr(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def _print_stats(stats: dict) -> None:
    if stats["completed_trades"] == 0:
        print("  完了取引なし — 集計対象データがありません")
        return
    flag = "  (参考値: 取引数が少ない)" if stats["reference_only"] else ""
    print(f"  完了取引数      : {stats['completed_trades']}{flag}")
    print(f"  勝ち / 負け / 引分: {stats['wins']} / {stats['losses']} / {stats['breakeven']}")
    print(f"  勝率            : {stats['win_rate']}%")
    print(f"  総損益          : {stats['total_pnl']}")
    print(f"  平均利益        : {stats['avg_win']}")
    print(f"  平均損失(絶対値) : {stats['avg_loss']}")
    print(f"  期待値          : {stats['expectancy']}")
    print(f"  1取引平均損益    : {stats['avg_pnl_per_trade']}  (期待値と一致するはず)")
    print(f"  プロフィットファクター: {stats['profit_factor']}")
    print(f"  最大利益 / 最大損失: {stats['max_profit']} / {stats['max_loss']}")
    print(f"  最大ドローダウン  : {stats['max_drawdown']}")


def main() -> int:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        report = performance_report(db)

    bt = report["backtest"]
    _hr("1. バックテスト成績 (手数料・スプレッド込み)")
    print(f"run数={bt['run_count']}  通貨={bt['symbols']}  戦略={bt['strategies']}")
    print(f"単一runの最大DD(最悪): {bt['worst_single_run_drawdown']}")
    _print_stats(bt["overall"])
    if bt["by_strategy"]:
        print("\n-- 戦略別 --")
        for name, stats in bt["by_strategy"].items():
            print(f"[{name}] 取引={stats['completed_trades']} 勝率={stats['win_rate']}% "
                  f"期待値={stats['expectancy']} PF={stats['profit_factor']}")
    if bt["by_symbol"]:
        print("\n-- 通貨ペア別 --")
        for name, stats in bt["by_symbol"].items():
            print(f"[{name}] 取引={stats['completed_trades']} 勝率={stats['win_rate']}% "
                  f"期待値={stats['expectancy']} PF={stats['profit_factor']}")

    paper = report["paper"]
    _hr("2. ペーパートレード成績")
    print(f"セッション数={paper['session_count']}  "
          f"未決済={paper['open_position_count']}  含み損益={paper['unrealized_pnl']}")
    _print_stats(paper["overall"])
    if paper.get("by_symbol"):
        print("\n-- 通貨ペア別 --")
        for name, stats in paper["by_symbol"].items():
            flag = " (参考値)" if stats["reference_only"] else ""
            print(f"[{name}] 取引={stats['completed_trades']} 勝率={stats['win_rate']}% "
                  f"総損益={stats['total_pnl']} 期待値={stats['expectancy']} "
                  f"PF={stats['profit_factor']}{flag}")
    if paper.get("by_strategy"):
        print("\n-- 戦略別 --")
        for name, stats in paper["by_strategy"].items():
            flag = " (参考値)" if stats["reference_only"] else ""
            print(f"[{name}] 取引={stats['completed_trades']} 勝率={stats['win_rate']}% "
                  f"総損益={stats['total_pnl']} 期待値={stats['expectancy']} "
                  f"PF={stats['profit_factor']}{flag}")

    op = report["operational"]
    _hr("3. mock E2E / dry-run (動作確認 — 戦略成績に含めない)")
    print(f"mock注文={op['mock_order_count']}  mock約定={op['mock_fill_count']}  "
          f"mock決済={op['mock_close_count']}")
    print(f"practice注文={op['practice_order_count']}  dry_run注文={op['dry_run_count']}  "
          f"エラー注文={op['error_order_count']}")
    print(f"戦略成績から除外: {op['excluded_from_strategy_performance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
