# Timeframe/Range Expansion (H1) + Evaluation Hardening（no-POST・2026-07-08）

Step: `EXPAND_HISTORICAL_DATA_RANGE_OR_TIMEFRAME_NO_POST`
実装: 既存 `gmo_strategy_evaluation_hardening.py` を**そのまま再適用**（コード変更なし）

**重要: これは candidate 探索の結果であり、performance proof ではない
（performance_proof_status=false / live_ready=false）。raw price/spread/PnL は扱わない。
「robust candidate」= paper-forward へ進める候補であって、edge の証明ではない。**

## 1. 目的と背景

M5 では、walk-forward + コスト感度 + ランダムベンチマークで**全候補が非頑健**
（NO_ROBUST_EDGE）だった。主因の一つは「M5 は spread が値幅に対して大きく、
コスト差引後に edge が残りにくい」こと。そこで **より長期・より高い時間足(H1)** で
データを揃え、同じ hardening 基盤を再適用した。

## 2. no-POST安全境界 / データ準備

- 実POST / broker write / private API / runtime private GET / credential / env read はゼロ
- GMO **Public** klines を **public GET のみ**で取得（認証不要）。H4("4hour")は公開APIが
  非対応のため H1 を採用
- 出力は repo外 gitignored ディレクトリ・**CSV は commit しない**
- H1 dataset: USD_JPY / **7,828 bars / ~15ヶ月（2025-04-01〜2026-07-07）** /
  BID/ASK 完全alignment・monotonic・負spread 0 / official evaluation candidate /
  spread は bar-level 近似（NOT_TICK_LEVEL）

## 3. hardening 再適用結果（H1・safe aggregate）

- rolling OOS 窓: **8窓 × 900 bars（≈5-6週/窓）**、cost 乗数 1.0/1.5/2.0、
  ランダムベンチマーク（決定論的LCG）
- baseline base-cost pass率: **0.375**（M5 の 0.22 より改善）
- random benchmark median PF（base）: 0.93

| candidate | 判定 | base pass率 | base median PF | stress(1.5x) pass率 | beats random |
|---|---|---|---|---|---|
| **TREND_CONTINUATION RIDE** | **ROBUST_FOR_PAPER_FORWARD** | **0.625** | **1.060** | **0.625** | **yes** |
| TREND_CONTINUATION TIGHT | NOT_ROBUST | 0.50 | 1.010 | 0.50 | yes |
| DUAL_CONFIRMATION TIGHT | NOT_ROBUST | 0.375 | 0.926 | 0.375 | no |
| BREAKOUT TIGHT | NOT_ROBUST | 0.375 | 0.968 | 0.375 | no |
| MEAN_REVERSION_RANGE TIGHT | NOT_ROBUST | 0.40 | 0.846 | 0.40 | no |
| DUAL_CONFIRMATION RIDE | NOT_ROBUST | 0.50 | 0.867 | 0.375 | no |
| BREAKOUT RIDE | NOT_ROBUST | 0.375 | 0.716 | 0.375 | no |
| MEAN_REVERSION_RANGE RIDE | NOT_ROBUST | 0.00 | 0.767 | 0.00 | no |

- any_robust_candidate: **true** / overall_conclusion: **ROBUST_CANDIDATE_FOUND_PAPER_FORWARD_NEXT**

## 4. 解釈（正直に・過大評価しない）

- **時間足を H1 に上げると結論が変わった**: M5 で全滅だった中、H1 では
  **trend-continuation × wide ATR ride exit** が 8窓中5窓でPF>1（median 1.06）、
  1.5×コストでも同pass率、ランダム超過 → 頑健性バーを通過。
  **spread比が下がると trend continuation が成立し得る**という仮説と整合。
- ただし **これは edge の証明ではない**。留意点:
  1. **多重検定**: 8候補を試して1つ通過。現在のバー（pass率>=0.60・8窓のみ）は
     厳しくなく、偶然の通過が混じり得る。通算試行数を踏まえた**より厳しいバー**での
     再検証が必須
  2. **exit依存**: 同family の TIGHT exit は 0.50 で不通過。exit設定に敏感
  3. **pass率 0.625 は marginal**（3窓は不合格）。安定edgeとは呼べない
  4. 単一symbol・単一期間帯・bar-level spread近似（tick spreadより楽観的な可能性）

## 5. 本Stepの成果

- 「精度=結論の信頼度」の観点で、**データ拡張により hardening 基盤が
  “有望候補”を初めて surface** した（枠組みの ROBUST 分岐が実データで機能）
- 同時に、**多重検定・marginal性のため、まだ live でも proof でもない**ことを明示

## 6. recommended next Step

1. **PAPER_FORWARD_TEST_DESIGN_NO_POST** — TREND_CONTINUATION_RIDE を対象に、
   完全に未使用の将来データ（forward）での検証設計。ただし**多重検定補正**
   （通算試行数に対する Bonferroni 相当の厳格化）と、より多窓・複数期間での
   再現確認をセットにする
2. 並行して **さらなるデータ拡張**（別年・別pair・H1の期間延長）で
   同候補が再現するかを見る
- live移行は不可（proof未確立・operator判断・paper forward要）
