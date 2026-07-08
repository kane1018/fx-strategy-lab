# Initial Real-Data Backtest（operator CSV・no-POST・2026-07-08）

Step: `HISTORICAL_DATA_IMPORT_DRY_RUN_AND_BACKTEST_WITH_OPERATOR_CSV_NO_POST`（backtest部）

**重要: これは初回の探索的評価であり、strategyの勝率・収益性・期待値の証明ではない
（performance_proof_status=false / live_ready=false）。以下の数値は候補policy1本を
過去1データセットに適用した aggregate であり、むしろ「現状のbaselineには edge の
根拠がない」ことを示す方向の結果である。過大解釈しないこと。**

## 1. dataset summary

- source: GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV / type: VALIDATED_OPERATOR_LOCAL_CSV
- symbol USD_JPY / timeframe M5 / bar_count 19,992
- date range: JST 2026-04-01 00:00〜2026-07-07 23:55
- spread included: true / derivation: BAR_LEVEL_APPROXIMATION_NOT_TICK_LEVEL

## 2. split summary（chronological・no shuffle）

- train 11,993 bars / validation 3,997 bars / OOS 3,999 bars（warmup除外）
- OOSは最適化に未使用（このStepはparameter選定・grid search・OOS使い回しを行わない）

## 3. strategy configuration / candidate policy

- engine: 既存 deterministic strategy signal engine（rulebook準拠）
- candidate policy: `CANDIDATE_MEDIUM_BALANCED`（TP/SL/max hold は **candidate-only**・
  synthetic test-only距離・official採用値ではない）
- exit: opposite signal / TP / SL / max hold / end-of-window

## 4. signal distribution（safe counts）

BUY 1,649 / SELL 1,547 / HOLD 13,601 / UNKNOWN_BLOCKED 3,192。
category: SETTLEMENT_PREVIEW_CONTEXT_ONLY 12,186（建玉保有中）/
ENTRY_PREVIEW_PROPOSED 3,196 / HOLD_NO_ORDER 1,415 / BLOCKED_FAIL_CLOSED 3,192。
block理由: SESSION_NOT_ALLOWED 3,192（JSTスプレッド拡大帯）/
ENTRY_PREVIEW_BLOCKED_POSITION_ALREADY_OPEN 12,186。

## 5. trade / exit summary（aggregate・safe counts）

- trade_count 3,196 / metrics_status: METRICS_COMPUTED_SYNTHETIC
- exit: opposite_signal 3,168 / TP 22 / SL 6 / max_hold 0 / end_of_window 0
- average_hold_duration ≈ 3.87 bars / exposure_time_ratio ≈ 0.62

## 6. metrics summary（aggregate only・proofではない）

- win_rate ≈ 0.29 / profit_factor ≈ 0.83（**<1.0**）/ expectancy: **NEGATIVE**
- max_consecutive_losses 23 / spread_cost_ratio: POSITIVE（spread costが効いている）
- hold_rate ≈ 0.68 / unknown_blocked_rate ≈ 0.16

**解釈**: この候補policy＋現engineは、spread込みのこの期間では
**期待値マイナス**（profit factor < 1）。頻繁なopposite-signal flipで
ほぼ全トレードが反転exitしており、baselineとして edge を示していない。
これは「戦略が悪い」の断定でも「勝てる」の断定でもなく、
**初回探索の観察**として扱う。

## 7. guard/block・overfitting・limitations

- overfitting_status: OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA（module既定ラベル）/
  oos_status: OOS_NOT_EVALUATED / parameter_search_count 0
- **既知のラベル限界**: metrics/report module の一部ラベルは "SYNTHETIC" /
  "NO_REAL_DATA" の語を含む（これはreal dataでも保守的に「未証明」側へ倒す
  固定ラベルであり、危険側ではない）。real-data用ラベルの精緻化は将来Stepの
  候補（`STRATEGY_BACKTEST_RESULT_REVIEW_NO_POST`）
- limitations: SYNTHETIC_FIXTURE_ONLY_NOT_REAL_DATA_NOT_PERFORMANCE_PROOF
  相当（bar-level spread近似・単一期間・単一候補policy・OOS未評価）

## 8. 判定・next Step

- 結果判定: **BACKTEST_REAL_DATA_INITIAL_COMPLETED_UNPROVEN**
- recommended next Step: `STRATEGY_BACKTEST_RESULT_REVIEW_NO_POST`
  （結果レビュー・engine/policy改善候補の整理・real-dataラベル精緻化）。
  baselineに edge が見えないため、改善またはstrategy再設計の検討が必要。
  live移行は不可（operator判断・OOS評価・paper forward後まで禁止）。
