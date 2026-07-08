# 研究 runbook（安全な再開手順・no-POST）

戦略探索は [RESEARCH_PLATFORM_CLOSEOUT_AND_STATUS_RECORD_NO_POST_20260709.md](RESEARCH_PLATFORM_CLOSEOUT_AND_STATUS_RECORD_NO_POST_20260709.md)
で CLOSED_OUT。本 runbook は**将来、新仮説を安全に検証再開する際の固定手順**。
固定ルールは [`../AGENTS.md`](../AGENTS.md)、現在地は [PROJECT_STATUS.md](PROJECT_STATUS.md)。

## 0. 安全不変則（最初に確認・常時遵守）

- **no actual POST**（entry/settlement/order）・no broker write・no real broker HTTP・no private API・
  no runtime private GET・no credential/env 値読取。default-deny hard guard を弱めない。
- 新規データ取得は **operator 承認の public GET（認証なし）のみ**。CSV は **repo 外**
  (`~/Desktop/fx_strategy_lab_historical_data/`)・**非commit**・raw row 非公開。
- 報告は **safe aggregate のみ**（raw price/spread/PnL/CSV row/ID/credential を出さない）。
- **事前登録なしの探索禁止 / post-OOS retuning 禁止**。
- 各 Step: repo fresh 確認 → tests → ruff → `git diff --check` → danger scan → docs → ≤2 commit → ≤1 push。

## 1. 再開の全体フロー（この順のみ）

1. **仮説を事前登録（docs・凍結）**: [inventory](STRATEGY_HYPOTHESIS_INVENTORY_AND_PREREGISTRATION_NO_POST_20260708.md) と
   [gotobi preregistration](STRATEGY_GOTOBI_FIX_DRIFT_PREREGISTRATION_NO_POST_20260708.md) が雛形。§4 のチェックリストを埋めて commit（=契約凍結）。
2. **データ承認**（新規が要る場合）: symbol / timeframe / date range / BID+ASK / 取得可能最古日 を
   operator に確認。まず bounded プローブで最古日確認 → 本取得。既存データで足りるなら不要。
3. **凍結ルールを実装**（既存 runner/gate を再利用。frozen signal engine は触らない）。synthetic test のみで検証
   （実データは採点まで見ない＝no peeking）。
4. **標準 gate で1回だけ採点**（§3）。**結果を見て条件変更しない**。
5. **safe aggregate で正直に記録**（PASS=paper-forward候補どまり / NOT_ROBUST / INSUFFICIENT）。台帳 +1。

## 2. どこに何があるか

- backtest 基盤: `backend/app/services/gmo_strategy_backtest_{engine,metrics,report,dataset}.py`
- 評価 hardening / 標準 gate: `backend/app/services/gmo_strategy_evaluation_hardening.py`
  - `StandardEvaluationGate`（gate 定数）/ `evaluate_under_standard_gate(...)`（multi-resolution 判定）
  - `run_walk_forward_for_*` / `sign_permutation_median_pf_percentile` / `run_random_entry_backtest`
- 候補 runner / families: `backend/app/services/gmo_strategy_redesign.py`
  - `run_redesign_backtest(...)`（entry families・ATR exit・**vol_regime_mode** gate・sign-permutation override）
  - builders: `build_default_redesign_candidates` / `build_session_structural_candidates` /
    `build_vol_regime_conditional_candidate`
- gotobi（カレンダー時刻窓 hypothesis の雛形）: `backend/app/services/gmo_strategy_gotobi.py`
  - `effective_gotobi_dates` / `run_gotobi_backtest` / `evaluate_gotobi_effect`(4対照)
- data 取込: `backend/app/services/gmo_historical_data_import_adapter.py`
  （`import_historical_csv` / local-file-only / BID+ASK→spread）
- 公開GET client（取得時のみ・認証なし）: `backend/app/shadow/gmo_public.py`
  （`GmoPublicMarketDataClient.fetch_candles(symbol, "M5", price_type=..., date="YYYYMMDD", limit=0)`）

## 3. 標準 gate の回し方（安全・read-only）

```
from app.services.gmo_historical_data_import_adapter import (
    HistoricalCsvImportRequest, import_historical_csv)
from app.services.gmo_strategy_evaluation_hardening import evaluate_under_standard_gate

ds = import_historical_csv(HistoricalCsvImportRequest(
    symbol_safe_label="USD_JPY", timeframe_safe_label="M5",
    bid_csv_path=..., ask_csv_path=..., treat_as_synthetic_fixture=False)).dataset
# 注意: dataset は __bool__ が False。存在判定は `if ds is not None:`

rep = evaluate_under_standard_gate(
    ds, candidates=(my_frozen_candidate,),
    window_bars_resolutions=(12000, 16800),  # M5 用（H1 は既定 1000/1400）
    lead=250)  # regime/indicator lead-in を包含
# rep.any_robust_candidate / rep.verdicts[*].robust_all_resolutions を確認
# 合格でも perf_proof/live は false。
```

- gotobi 型（時刻窓×カレンダー）は `evaluate_gotobi_effect(ds)`（非ゴトー対照/曜日層化置換/符号置換/Nブロック）。
- 採点は **1回**。窓/閾値/定義を変えて再走しない。

## 4. 事前登録チェックリスト（データ取得前に凍結）

- [ ] hypothesis と mechanism（動機であり証明対象でない旨）
- [ ] symbol / timeframe（primary/参照）・M1/他ペアの要否
- [ ] entry / exit ルール（単一 primary・secondary は厳格閾値＋台帳）
- [ ] 約定モデル（leg別spread・0.5pip/side・2.0×cost）
- [ ] 対照群（非条件対照・sign-permutation・（カレンダー系は）層化置換・Nブロック安定）
- [ ] 最小標本 / 最小 qualifying windows（未達は INSUFFICIENT）
- [ ] 合格基準（unanimous 多対照）と verdict ラベル
- [ ] 多重検定台帳 +1 / post-OOS retuning 禁止の明記
- [ ] 必要 operator 承認（public GET・range・保存先）

## 5. 多重検定台帳 & エスカレーション

- 累計 ~20 trial（全 REJECT）＋ pre-registered null #1/3。
- **さらに K=3 連続 NOT_ROBUST** で `RESEARCH_PLATFORM_CLOSEOUT` へ（operator 判断で前倒し可＝今回発動）。
- 単一 benchmark 超えでは合格にしない（常に unanimous 多対照 × multi-resolution）。

## 6. live へ進む条件（現状すべて未達）

robust edge（本 gate 合格）→ paper-forward soak → operator review → 明示承認、の**全て**が揃うまで
live 不可。現状 `live_ready=false` / `unattended_live_supported=false`。
