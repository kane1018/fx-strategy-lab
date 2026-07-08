# Historical Data Import Dry-Run（operator CSV・no-POST・2026-07-08）

Step: `HISTORICAL_DATA_IMPORT_DRY_RUN_AND_BACKTEST_WITH_OPERATOR_CSV_NO_POST`（dry-run部）

## 1. 目的・no-POST安全境界

operator提供のGMO public kline BID/ASK local CSVを **read-only** で validate し、
official evaluation candidate 判定と backtest dataset化を行った。実POST /
broker write / real HTTP / download / public kline export再実行 / private API /
runtime private GET / credential・env read は**すべてなし**。

## 2. operator approval / CSV paths

- approval: `OPERATOR_APPROVES_LOCAL_CSV_READ_ONLY_DRY_RUN_AND_INITIAL_BACKTEST_NO_POST_NO_CREDENTIAL`
- bid_csv_path / ask_csv_path: repo外
  `~/Desktop/fx_strategy_lab_historical_data/USD_JPY_M5_{BID,ASK}_20260401_20260707.csv`
- mode: BID_ASK_PAIR_CSV / symbol=USD_JPY / timeframe=M5

## 3. dry-run validation結果（safe summaryのみ）

- intake category: **CSV_INTAKE_READY_OFFICIAL_EVALUATION**
- official_evaluation_eligible: true / spread_included: true
- spread derivation labels: `SPREAD_FROM_BID_ASK_BAR_APPROXIMATION` +
  `NOT_TICK_LEVEL_SPREAD`（**bar-level近似・tick-level実spreadではない**）
- session derivation: `SESSION_DERIVED_FROM_UTC_TIMESTAMP_JST_POLICY`
- bar_count: 19,992 / BID=ASK 完全alignment / duplicate・非単調なし / 負spread 0
- coverage: UTC 2026-03-31T15:00〜2026-07-07T14:55（= JST 指定範囲を完全カバー）
- forbidden columns: 不存在
- backtest dataset validation: **DATASET_VALID_OPERATOR_LOCAL_CSV**

## 4. synthetic-only制約解除review

最小コード変更で、**validation通過済みの operator local CSV dataset に限定**して
非synthetic datasetを許可した:

- `BacktestDataset.validated_operator_local_csv`（adapterがintake validation
  通過後にのみtrue）を追加
- `validate_backtest_dataset` は、非syntheticでも
  `validated_operator_local_csv=True` の場合のみ通過し、status
  `DATASET_VALID_OPERATOR_LOCAL_CSV` を返す
- **未validated real dataset / forged real dataset / remote pathは引き続き
  fail-closed**（回帰テスト
  `test_gmo_historical_data_dry_run_and_backtest_no_post.py` で固定）
- 既存 synthetic テストは status `DATASET_VALID_SYNTHETIC` のまま維持
- global bypassは存在しない

## 5. 遵守記録

actual/entry/settlement/close POST=false / POST count=0 / broker write=false /
real HTTP=false / download=false / public kline export再実行=false /
private API=false / runtime private GET=false / credential・env read=false /
raw CSV row・raw OHLC・raw BID/ASK・raw spread値の露出=false / CSV commit=false /
performance_proof_status=false / live_ready=false。

## 6. next Step

初回backtest結果は
[STRATEGY_BACKTEST_WITH_OPERATOR_CSV_INITIAL_NO_POST_20260708.md](STRATEGY_BACKTEST_WITH_OPERATOR_CSV_INITIAL_NO_POST_20260708.md)。
