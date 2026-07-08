# Hypothesis Registry（仮説台帳）— no-POST・safe aggregate

研究統治の一部。全仮説の状態を一元管理する。**新仮説は必ず mechanism-first で事前登録し、
標準 gate で1回採点してから本表を更新する**（[runbook](RESEARCH_RUNBOOK_NO_POST.md)）。
raw price/spread/PnL/CSV row/ID/credential は載せない。performance_proof_status=false / live_ready=false。

## 状態凡例
- **REJECTED**: 標準 gate で採点し robust edge なし（棄却）。
- **FROZEN_UNEXECUTED**: 事前登録は凍結済だが未採点（データ未入手等）。将来データがあれば契約通り1回採点可。
- **DEFERRED**: 事前登録前。データ/prior 上 near-term 非推奨。
- **BLOCKED_DATA**: 要求データが no-credential で入手困難。
- ※ **REJECTED のみ多重検定 null にカウント**。FROZEN/DEFERRED/BLOCKED は未カウント。

## 台帳

| ID | 機構 / family | scope / data | 状態 | verdict（safe） | 主因（safe） | 記録 |
|---|---|---|---|---|---|---|
| H-01 | M5 technical（trend/breakout/mean-rev/dual ×2 exit） | M5 | REJECTED | NO_ROBUST_EDGE | 全候補 NOT_ROBUST（コスト後 edge なし） | [redesign](STRATEGY_RULE_REDESIGN_NO_POST_20260708.md) / [hardening](STRATEGY_EVALUATION_HARDENING_NO_POST_20260708.md) |
| H-02 | H1 trend continuation / ATR ride | H1 ~15ヶ月 | REJECTED | NOT_ROBUST_UNDER_EXECUTION_FRICTION | 0.5pip/side で breakeven 化・多解像度不一致 | [execution-realism](STRATEGY_EXECUTION_REALISM_HARDENING_NO_POST_20260708.md) / [gate-correction](STRATEGY_GATE_CORRECTION_AND_SESSION_HYPOTHESIS_NO_POST_20260708.md) |
| H-03 | SESSION_MOMENTUM（session-open continuation） | H1 | REJECTED | DIRECTION_RULE_NOT_BEATING_SIGN_PERMUTATION | 方向ルールが符号置換 p90 に負け・非 unanimous | [gate-correction](STRATEGY_GATE_CORRECTION_AND_SESSION_HYPOTHESIS_NO_POST_20260708.md) |
| H-04 | GOTOBI_FIX_DRIFT（仲値ドリフト） | M5 2.7年・166件 | REJECTED | REJECTED_ON_MULTI_YEAR_M5 | PF≈1.00・2.0×コスト負・符号置換負け・非持続。16件 PF5.38 は小標本の偶然 | [preregistration](STRATEGY_GOTOBI_FIX_DRIFT_PREREGISTRATION_NO_POST_20260708.md) / [retest](STRATEGY_GOTOBI_MULTI_YEAR_M5_RETEST_NO_POST_20260708.md) |
| H-05 | VOL_REGIME_CONDITIONAL_BREAKOUT | M5 2.7年 primary / H1 参照 | REJECTED | NOT_ROBUST | 高vol化で改善方向は確認(H1 0.80→0.94)だが PF<1・符号置換未達・コスト非生存 | [retest](STRATEGY_VOL_REGIME_CONDITIONAL_BREAKOUT_RETEST_NO_POST_20260708.md) |
| H-06 | RATE_DIFFERENTIAL_DAILY（US–JP 10y 差の変化→USD/JPY） | 日次 2005–2026 | FROZEN_UNEXECUTED | （未採点） | データが当 sandbox から不達（FRED/MOF）・operator は closeout 選択。契約は凍結・将来採点可 | [preregistration](STRATEGY_RATE_DIFFERENTIAL_DAILY_PREREGISTRATION_NO_POST_20260709.md) |
| H-07 | FX_RELATIVE_VALUE_TRIANGULAR（非方向） | 多ペア（要取得） | DEFERRED | — | 文献上 小口三角裁定は "mirage"（3-leg コスト）・prior 低 | [inventory](STRATEGY_HYPOTHESIS_INVENTORY_AND_PREREGISTRATION_NO_POST_20260708.md) / [feasibility](STRATEGY_MECHANISM_TIMESCALE_DATA_FEASIBILITY_NO_POST_20260709.md) |
| H-08 | CROSS_ASSET_RATES_LEADLAG（intraday 金利→USD/JPY） | intraday（M5 整合金利） | BLOCKED_DATA | — | 無認証で清潔な分足金利が困難 | [cross-asset preregistration](STRATEGY_CROSS_ASSET_RATES_LEADLAG_PREREGISTRATION_NO_POST_20260709.md) |
| H-09 | MONTH_END_FIX_REBALANCING | 月次イベント | DEFERRED | — | 標本過少（≈12/年）＋方向に株式データ要 | [feasibility](STRATEGY_MECHANISM_TIMESCALE_DATA_FEASIBILITY_NO_POST_20260709.md) |
| H-10 | EVENT_DRIFT（BOJ/FOMC/NFP/CPI） | イベント前後 | DEFERRED | — | 方向 drift は 2015 後減衰・確実なのは非方向 vol・外部カレンダー要 | [feasibility](STRATEGY_MECHANISM_TIMESCALE_DATA_FEASIBILITY_NO_POST_20260709.md) |

## 多重検定台帳（cumulative trial budget）

- 採点済み candidate-config: 概数 ~20（M5 technical ~8・H1 technical ~8・SESSION ~2・GOTOBI primary+secondary ~2）＝**全 REJECT**。
- **pre-registered null カウント: #1/3**（H-05 VOL_REGIME）。H-06 は FROZEN_UNEXECUTED のため**未カウント**。
- **escalation 則**: pre-registered 新仮説が **さらに K=3 連続 REJECT** で `RESEARCH_PLATFORM_CLOSEOUT` へ
  （operator 判断で前倒し可。今回発動済み）。
- 合格は常に **unanimous 多対照 × multi-resolution**（単一指標超えでは合格にしない）。**post-OOS retuning 禁止**。

## 現在の集約状態

- current_strategy_status: **NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE**
- research_phase: **CLOSED_OUT**（operator 判断で再開可）
- performance_proof_status=false / live_ready=false / unattended_live_supported=false（不変）

## 新仮説の追加手順（要約）

1. **mechanism-first** で機構＋発動条件を凍結（データを見る前・data-dredging 禁止）。
2. 要求データを特定（no-credential で入手できなければ BLOCKED として記録・代替に流さない）。
3. 標準 gate で **1回採点**（条件変更なし）。
4. 本表を更新（REJECTED は null +1）。null なら closeout 維持。
