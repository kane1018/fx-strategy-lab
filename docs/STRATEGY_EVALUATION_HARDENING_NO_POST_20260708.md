# Strategy Evaluation Hardening（no-POST・2026-07-08）

Step: `STRATEGY_EVALUATION_HARDENING_NO_POST`
実装: `backend/app/services/gmo_strategy_evaluation_hardening.py`

**重要: これは「結論の信頼度」を上げる評価基盤であり、performance proofではない
（performance_proof_status=false / live_ready=false）。raw price/spread/PnLは扱わない。**

## 1. 背景と目的

前Stepの単発 freeze→OOS は、validationでPF>1だった候補（mean-reversion/ride）を
freeze したがOOSで却下した。**単発OOSは1回の運任せで偽陽性を出しやすい**。
本Stepは単発OOSを、時間・コスト・ベンチマークにわたる頑健性検証に置き換える。

## 2. no-POST安全境界

実POST / broker write / real HTTP / download / public kline export再実行 /
private API / runtime private GET / credential / env read はゼロ。operator提供の
local CSV を read-only 再利用。deterministic signal engine は無変更。追加は
backtest runner への後方互換 `spread_cost_multiplier`（既定1.0）のみ。

## 3. 導入した検証（4本立て）

1. **ウォークフォワード（rolling OOS）**: 固定候補を連続する複数OOS窓で評価し、
   「一度勝ったか」ではなく「edgeが時間的に持続するか」を pass率で測る
2. **コスト感度**: spread cost 乗数 1.0 / 1.5 / 2.0 で再評価。実edgeは高コストでも生存
3. **ランダムentryベンチマーク**: 同一exitで決定論的LCG（`random`モジュール不使用）の
   ランダムentryを通し、entryが情報を持つかを分離
4. **候補別の総合頑健性判定**（walk-forward robust ∧ cost robust ∧ beats random）

## 4. 実データ結果（USD_JPY M5・safe aggregate）

- rolling OOS 窓: **9窓 × 2,000 bars（≈1週間/窓）**、indicator lead-in 40（warmupのみ）
- baseline base-cost pass率: **0.22**（9窓中2窓のみPF>1）
- random benchmark median PF（base cost）: **0.63**

| candidate | 判定 | base pass率 | base median PF | stress(1.5x) pass率 | beats random |
|---|---|---|---|---|---|
| TREND_CONTINUATION TIGHT | NOT_ROBUST | 0.17 | 0.89 | 0.00 | yes |
| TREND_CONTINUATION RIDE | NOT_ROBUST | 0.25 | 0.81 | 0.25 | yes |
| BREAKOUT TIGHT | NOT_ROBUST | 0.00 | 0.73 | 0.00 | yes |
| BREAKOUT RIDE | NOT_ROBUST | 0.00 | 0.64 | 0.00 | no |
| MEAN_REVERSION_RANGE TIGHT | NOT_ROBUST | 0.33 | 0.78 | 0.22 | yes |
| **MEAN_REVERSION_RANGE RIDE** (前回freeze候補) | **NOT_ROBUST** | 0.44 | 0.91 | 0.44 | yes |
| DUAL_CONFIRMATION TIGHT | NOT_ROBUST | 0.33 | 0.96 | 0.33 | yes |
| DUAL_CONFIRMATION RIDE | INSUFFICIENT_WINDOWS | 0.00 | 0.37 | 0.00 | no |

- any_robust_candidate: **false**
- overall_conclusion: **NO_ROBUST_EDGE_ACROSS_WALK_FORWARD_AND_COST_STRESS**

## 5. 解釈（正直に）

- 前回の単発OOSで freeze された候補は、**9窓中4窓しかPF>1を満たさず**（median PF 0.91<1）、
  頑健性閾値（pass率0.60）に届かない。**新枠組みが偽陽性を明確に却下**した
- 多くの候補は **beats_random=yes**（median PFがランダム0.63を上回る）＝
  entryルールは限界的な情報を持つが、**spread込みでPF>1を持続的に超えるには不足**
- baseline自身も pass率0.22 で非頑健。**M5テクニカルはコスト差引後に持続edgeなし**が
  再現性を持って確認された

## 6. 本Stepの本質的成果

「精度」を上げたのは strategy ではなく **評価の信頼度**である。単発OOSの偽陽性リスクを、
時間×コスト×ベンチマークの多面検証で構造的に低減し、意思決定を誤らせない基盤を得た。

## 7. limitations / next Step

- 単一3ヶ月・単一symbol/timeframe・bar-level spread近似（依然）
- 次の実質的向上は **より長期・複数期間・別時間足（H1/H4等）でのwalk-forward再評価**
  または **テクニカル以外のシグナル源の導入**
- recommended next Step: `EXPAND_HISTORICAL_DATA_RANGE_OR_TIMEFRAME_NO_POST`
  （データ拡張＋本hardening再適用）または `STRATEGY_HYPOTHESIS_REBUILD_NO_POST`
- live移行は不可（robust edge未確認・operator判断・paper forward要）

report詳細: [STRATEGY_EVALUATION_HARDENING_REPORT_NO_POST_20260708.md](STRATEGY_EVALUATION_HARDENING_REPORT_NO_POST_20260708.md)
