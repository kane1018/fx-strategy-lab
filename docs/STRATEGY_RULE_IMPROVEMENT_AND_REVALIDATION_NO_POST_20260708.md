# Strategy Rule Improvement & Revalidation（no-POST・2026-07-08）

Step: `STRATEGY_BACKTEST_RESULT_REVIEW_RULE_IMPROVEMENT_AND_REVALIDATION_NO_POST`（revalidation部）
実装: `backend/app/services/gmo_strategy_rule_revalidation.py`

**重要: aggregate/sign-onlyの探索結果であり、performance proofではない
（performance_proof_status=false / live_ready=false）。raw price/spread/PnLは扱わない。
OOSは freeze後に最大1回のみ使用し、OOSを見た後の再調整はしない。**

## 1. 改善仮説（<=3系統 + 小規模combo・candidate-only）

- **A: entry momentum strict** — momentumが厳密にsideと一致する時のみentry
  （neutral momentum entryを除外）
- **B: opposite-signal debounce** — opposite trendが連続3barで初めてexit
  （即時flipを抑制。SL/max holdは優先）
- **C: tight exit profile** — TP/SL/max holdを `CANDIDATE_SMALL_TIGHT` に変更
- **A+B combo**

これらは **backtest-level の knob**（`run_synthetic_backtest` の
`entry_momentum_strict` / `opposite_signal_debounce_bars` / exit policy key）であり、
**deterministic signal engine（rulebook）は無変更**。`officially_adopted=True` は
構築時に例外で拒否。

## 2. train/validation 比較（validation slice・aggregate/sign only）

- split: chronological（no shuffle）train 60% / validation 20% / OOS 20%
- parameter_search_count: 4（baseline除く）/ selected_using: TRAIN_VALIDATION_ONLY /
  oos_not_seen_before_freeze: true

| candidate | validation trades | PF | win | expectancy | max consec losses | spread cost |
|---|---|---|---|---|---|---|
| BASELINE | 653 | 0.545 | 0.27 | NEGATIVE | 19 | POSITIVE |
| A entry strict | 637 | 0.539 | 0.27 | NEGATIVE | 18 | POSITIVE |
| B opposite debounce | 351 | 0.618 | 0.29 | NEGATIVE | 21 | POSITIVE |
| C tight exit | 665 | 0.552 | 0.26 | NEGATIVE | 19 | POSITIVE |
| A+B combo | 346 | 0.631 | 0.28 | NEGATIVE | 21 | POSITIVE |

## 3. 選定ルールと結果

選定条件（validation only・全て満たす候補のみ freeze 資格）:
- trade_count >= 30
- PF > baseline PF × 1.05
- max_consecutive_losses <= baseline
- spread_cost_ratio <= baseline × 1.10
- expectancy が baseline から負へ反転しない

結果: **NO_CANDIDATE_SELECTED**
（selection_reason: `NO_CANDIDATE_MEETS_SELECTION_CRITERIA`）。
PFを改善したB / A+Bは **max_consecutive_losses が悪化（21 > 19）** し、
保守guardで却下。A / C はPF改善が閾値未満。全候補 expectancy NEGATIVE。

## 4. candidate freeze / OOS

- candidate freeze: **なし**（freeze候補が選定されなかった）
- OOS: **未実行**（`OOS_NOT_RUN_NO_CANDIDATE`。freeze前にOOSを見ない原則を維持）
- **OOSを最適化に使っていない・OOSを見た後の再調整もしていない**

## 5. overfitting controls / limitations

- 未来データ不使用 / chronological split / lead-inはindicator warmupのみ（leakageなし）
- OOSは freeze後1回限定（今回は候補なしで未実行）
- parameter探索は5構成（baseline+4）に制限、count記録
- 単一3ヶ月sample・bar-level spread近似・単一symbol/timeframe
- overfitting_status: single-sample real-data（保守）

## 6. 判定・next Step

- CASE: **STRATEGY_REVIEW_DONE_NO_CANDIDATE_SELECTED_NO_POST**
- 結論: 現engine+候補knobでは spread込みで edge を確立できない。
  incremental tweak（A/B/C）は不十分。
- recommended next Step: **STRATEGY_RULE_REDESIGN_NO_POST**
  （trend/momentum flip 依存からの再設計・exit/entryの根本見直し・
  spread前提の設計）。必要なら
  `EXPAND_HISTORICAL_DATA_RANGE_OR_TIMEFRAME_NO_POST`。
- live移行は不可（performance未証明・OOS未確認・paper forward未実施・operator判断要）。
