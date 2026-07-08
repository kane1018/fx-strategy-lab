# Strategy Backtest Result Review（no-POST・2026-07-08）

Step: `STRATEGY_BACKTEST_RESULT_REVIEW_RULE_IMPROVEMENT_AND_REVALIDATION_NO_POST`（review部）

**重要: 本書は初回real-data backtestの aggregate review であり、strategyの勝率・
収益性・期待値の証明でも否定でもない（performance_proof_status=false /
live_ready=false）。raw price / raw spread / per-trade PnL は扱わない。**

## 1. baseline summary（初回・full dataset・aggregate）

- dataset: GMO public kline BID/ASK local CSV / USD_JPY M5 / 19,992 bars
- signal: BUY 1,649 / SELL 1,547 / HOLD 13,601 / UNKNOWN_BLOCKED 3,192
- trade_count 3,196 / win_rate ≈0.29 / profit_factor ≈0.83 / expectancy NEGATIVE
- exit: opposite_signal 3,168 / TP 22 / SL 6 / max_hold 0 / EOW 0
- max_consecutive_losses 23 / avg_hold ≈3.87 bars / exposure ≈0.62 /
  spread_cost_ratio POSITIVE

## 2. failure factor classification（safe category）

| factor | 根拠（aggregate） | 効きそうな lever か |
|---|---|---|
| EXIT_TOO_REACTIVE_TO_OPPOSITE_SIGNAL | opposite exitが3,168/3,196でほぼ全て | 主因候補。ただし debounce の naive適用は drawdown 悪化 |
| TP_TOO_RARE / SL_TOO_RARE_OR_TOO_LOOSE | TP 22・SL 6のみ。TP/SL距離(候補0.5/0.4)がM5に対し過大でほぼ未到達 | 距離見直しは必要だが単独では不十分 |
| SPREAD_COST_TOO_HIGH | spread_cost_ratio POSITIVE・短保有・低勝率でspreadがedgeを侵食 | 重要。短期売買ほど致命的 |
| TRADE_FREQUENCY_TOO_HIGH / AVG_HOLD_TOO_SHORT | 3,196 trades・avg hold ≈3.87 bars | 頻度過多 |
| TREND_CONFIRMATION_WEAK / MOMENTUM_CONFIRMATION_WEAK | strict entry(候補A)で殆ど不変(0.545→0.539) | entry filterは主因ではない |
| DATA_PERIOD_SINGLE_SAMPLE_LIMITATION | 3ヶ月単一sample | 汎化未検証 |
| LABELING_NEEDS_REAL_DATA_REFINEMENT | metrics/report label が real dataでも保守ラベル | 本Stepで一部精緻化(下記) |
| OOS_NOT_EVALUATED | freeze候補なしのためOOS未実行 | 正しいfail-closed |

## 3. label精緻化（本Stepで実施）

- report: real local CSV datasetは
  `REPORT_OPERATOR_LOCAL_CSV_SPREAD_INCLUDED` /
  `REPORT_OPERATOR_LOCAL_CSV_REFERENCE_ONLY`（保守ラベル）
- metrics: real single-sample時は
  `OVERFITTING_RISK_UNKNOWN_SINGLE_SAMPLE_REAL_DATA`
- engine: `real_data_used` / `synthetic_fixture_only` を dataset由来で正確化
- **いずれも performance proof には一切ならない**

## 4. 総括

baseline（M5のtrend/momentum flip・過大なTP/SL・即時opposite exit）は
**spread込みで net edge の根拠がない**。詳細な改善候補比較とOOS判断は
[STRATEGY_RULE_IMPROVEMENT_AND_REVALIDATION_NO_POST_20260708.md](STRATEGY_RULE_IMPROVEMENT_AND_REVALIDATION_NO_POST_20260708.md)。
