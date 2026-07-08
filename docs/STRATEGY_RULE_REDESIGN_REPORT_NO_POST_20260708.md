# Strategy Rule Redesign Report（no-POST・2026-07-08）

Step: `STRATEGY_RULE_REDESIGN_NO_POST`（report部）

**aggregate metrics / safe counts / sign labels のみ。raw price/spread/PnL/
per-trade値・sample rows・ID・credentialは含まない。performance proofではない。**

## 1. candidate comparison（validation・aggregate/sign only）

| candidate | val trades | PF | win | expectancy | max consec losses | spread cost |
|---|---|---|---|---|---|---|
| BASELINE | 653 | 0.545 | 0.27 | NEGATIVE | 19 | POSITIVE |
| TREND_CONTINUATION EXIT_TIGHT | 27 | 0.674 | 0.44 | NEGATIVE | 5 | POSITIVE |
| TREND_CONTINUATION EXIT_RIDE | 20 | 0.654 | 0.25 | NEGATIVE | 7 | POSITIVE |
| BREAKOUT EXIT_TIGHT | 215 | 0.560 | 0.45 | NEGATIVE | 8 | POSITIVE |
| BREAKOUT EXIT_RIDE | 177 | 0.595 | 0.24 | NEGATIVE | 16 | POSITIVE |
| MEAN_REVERSION_RANGE EXIT_TIGHT | 192 | 0.787 | 0.55 | NEGATIVE | 5 | POSITIVE |
| **MEAN_REVERSION_RANGE EXIT_RIDE (frozen)** | 170 | **1.107** | 0.39 | **POSITIVE** | 10 | POSITIVE |
| DUAL_CONFIRMATION EXIT_TIGHT | 7 | 0.345 | 0.29 | NEGATIVE | 5 | POSITIVE |
| DUAL_CONFIRMATION EXIT_RIDE | 7 | 0.518 | 0.14 | NEGATIVE | 5 | POSITIVE |

## 2. selection / freeze

- selection: validation PF > 1.0 かつ expectancy 非negative かつ trade>=30 かつ
  max_consec_losses <= baseline を全て満たす候補のみ資格
- frozen: MEAN_REVERSION_RANGE__EXIT_RIDE_ATR / selected_using TRAIN_VALIDATION_ONLY /
  parameter_search_count 8 / oos_not_seen_before_freeze true

## 3. OOS one-time（frozen候補のみ・aggregate/sign）

- result: **OOS_DEGRADED_REJECT_CANDIDATE**
- OOS: trades 164 / PF 0.643 / win 0.26 / expectancy NEGATIVE / max_consec_losses 11
- OOS exit reason distribution: SL 119 / TP 37 / opposite 6 / max_hold 2
- signal(entry side) distribution は entry rule 由来の safe label のみ

## 4. overfitting checks / flags

- 未来データ不使用・chronological・lead-inはindicator warmupのみ（leakageなし）
- OOSは freeze後1回・最適化未使用・OOS後の再調整なし
- parameter_search_count 8（<=30）
- performance_proof_status=false / live_ready=false / real_data_used=true /
  synthetic_fixture_only=false / CSV commit=false / public kline export再実行=false
- 過大表現（profitable/winning/edge proven）なし

## 5. 結論

exit構造（ATR相対TP/SL）は baseline から明確に改善（opposite依存の解消）したが、
**OOSで持続する優位性は確認できず**、frozen候補はOOSで却下。次は仮説の再構築、
またはデータ期間/時間足の拡張。
