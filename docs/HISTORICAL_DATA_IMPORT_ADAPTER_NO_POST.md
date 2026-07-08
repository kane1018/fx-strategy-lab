# Historical Data Import Adapter — no-POST実装記録（2026-07-08）

Step: `HISTORICAL_DATA_IMPORT_ADAPTER_NO_POST`
実装: `backend/app/services/gmo_historical_data_import_adapter.py`
受入契約: [HISTORICAL_DATA_LOCAL_CSV_INTAKE_SPEC_NO_POST.md](HISTORICAL_DATA_LOCAL_CSV_INTAKE_SPEC_NO_POST.md)

## 1. 目的・対象範囲・対象外

operator提供のlocal CSVを既存 `BacktestDataset` schema へ取り込む adapter を
fail-closed で実装した。**このStepでは実CSV pathは NOT_PROVIDED のため
実データを一切読んでいない**(検証はtests内のsynthetic temporary CSVのみ)。
対象外: 実データ取得 / download / public kline export実行 /
`fetch_gmo_public_market_data.py` の実行 / broker接続 / real HTTP /
credential・env read / 実backtest / performance評価。
**adapter readyはperformance proofではない
(performance_proof_status=false / live_ready=false)**。

## 2. adapter design

- 入力: `HistoricalCsvImportRequest`(symbol/timeframe/source route labels、
  `combined_csv_path` **または** `bid_csv_path`+`ask_csv_path`、
  official_evaluation_requested)。両mode同時指定はblock
- **local file only**: path未提供→`DATA_ADAPTER_NOT_CONFIGURED`。
  URL・`http(s):`・`s3:`・`gs:`・`ftp:`・`file:` 等のremote scheme→
  `CSV_INTAKE_BLOCKED_REMOTE_PATH`(**読取前にblock**)。directory→block
  (auto-discovery/glob表面なし)。`.csv`以外→block。存在しないpath→NOT_PROVIDED
- 出力: intake category + safe blocked reasons + `BacktestDataset` +
  metadata(official eligibility / spread included / derivation labels /
  session derivation / bar count。**raw値のfieldなし**)

## 3. validation(実装・テスト固定)

- columns: 必須8列(intake spec準拠)。**forbidden columns**(ID・credential・
  raw response系。大小文字・space/dash・camel squash差分も正規化検出)→
  値を読まずに `CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS`
- timestamp: UTC epoch(s/ms)またはTZ明示ISOのみ。naive ISO→
  `CSV_INTAKE_BLOCKED_MISSING_TIMESTAMP_TZ`。非単調・重複→block
- symbol / timeframe / source_label: 欠損・不一致→block
- OHLC: 欠損・非数値・high<low→block。空file/header-only→block
- session: CSV提供label優先。なければUTC timestampからJST policy
  (5:00-8:59 JST=SESSION_BLOCKED)で導出。synthetic tick indexは
  DEFAULT_ALLOWED label付き

## 4. spread policy / 分類

- combined mode: `spread`列(非負必須)または `bid`/`ask`列(ask>=bid)から取得
- **BID/ASK pair mode**: 両file必須。timestamp/行数完全一致必須(不一致→
  `CSV_INTAKE_BLOCKED_BID_ASK_MISMATCH`)。bar-level spread = ask_close − bid_close
  (負→derivation impossible block)。metadataに
  `SPREAD_FROM_BID_ASK_BAR_APPROXIMATION` + `NOT_TICK_LEVEL_SPREAD` を必ず付与
  (**tick-level実spreadではない**)
- 分類: spreadあり→`CSV_INTAKE_READY_OFFICIAL_EVALUATION` /
  OHLCのみ+official要求→`CSV_INTAKE_BLOCKED_MISSING_SPREAD` /
  OHLCのみ+reference要求→`CSV_INTAKE_READY_REFERENCE_ONLY`(official不可)

## 5. backtest datasetとの接続

adapter出力は既存 `BacktestCandleRecord/SpreadRecord/SessionRecord` を再利用し、
`validate_backtest_dataset` を通過する形で構築(テスト固定)。strategy engineへは
従来どおり safe label converter 経由のみ(raw CSV rowを直接渡す経路なし)。
本phaseは `treat_as_synthetic_fixture=true` 固定で、実データdry-run Stepが
operator入力の下で明示的にfalseへ切り替える(dataset validation側の
synthetic-only blockの解除もそのStepで扱う)。

## 6. synthetic fixture検証結果

tests 36件 green — NOT_CONFIGURED / remote path 3種 / directory / 非csv /
mode排他 / official・reference分類 / 必須列欠損 / forbidden列(通常+表記ゆれ) /
重複・非単調timestamp / naive ISO block / TZ付きISO受理 / high<low / 非数値OHLC /
symbol・timeframe・source_label / 空file / pair正常系(approximation labels) /
片side欠落 / 行数・timestamp不一致 / 負spread / pair側forbidden列 /
dataset validation通過 / session導出 / 固定false flags / module isolation。

## 7. 遵守記録

actual/entry/settlement/close POST=false / POST count=0 / broker write=false /
real HTTP=false / download=false / public kline export実行=false /
runtime private GET=false / credential・env read=false / real_data_fetch=false /
real CSV dry-run=false / raw・ID・value露出=false。

## 8. next Step

operator CSV準備後: `HISTORICAL_DATA_IMPORT_DRY_RUN_WITH_OPERATOR_CSV_NO_POST`
(手順: [HISTORICAL_DATA_IMPORT_DRY_RUN_INSTRUCTIONS_NO_POST.md](HISTORICAL_DATA_IMPORT_DRY_RUN_INSTRUCTIONS_NO_POST.md))。
未準備なら: `OPERATOR_PREPARE_GMO_PUBLIC_KLINE_BID_ASK_LOCAL_CSV`。
