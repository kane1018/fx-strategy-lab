# Strategy Backtest Dataset Requirements（no-POST・将来仕様）

Step: `STRATEGY_BACKTEST_AND_EVALUATION_READINESS_NO_POST`
Date: 2026-07-08
実装: `backend/app/services/gmo_strategy_backtest_dataset.py`

本書は「実データを投入して検証できる準備」のための dataset 要件である。
**このStepでは実データ取得・broker接続・外部API・web取得は行っていない**
(synthetic fixtureのみ)。

## 1. 対象

- 通貨ペア候補: `USD_JPY`(初期対象。追加はschema拡張で対応)
- 時間足候補: `M1 / M5 / M15 / H1`(初期backtestはM5想定)

## 2. 必須項目

### candle(`BacktestCandleRecord`)
- timestamp(単調増加・重複禁止。実データではUTC基準のepochまたはISO+TZ必須。
  synthetic fixtureでは単調tick)
- symbol / timeframe safe label、OHLC、volume(optional)、source_label、
  synthetic_fixture flag

### spread(`BacktestSpreadRecord`)
- candleと同一timestampで**全bar必須**(欠損は `DATASET_SPREAD_RECORD_MISSING` でblock)
- spread_category(NORMAL / WIDE / UNKNOWN)+ spread_value
  (categoryがUNKNOWN以外なら必須。欠損は `DATASET_SPREAD_VALUE_MISSING` でblock)
- 実データではbroker生値そのものをdocs/reportへ出さない(集計のみ)

### session(`BacktestSessionRecord`)
- 全bar必須。SESSION_ALLOWED / SESSION_BLOCKED / SESSION_UNKNOWN
- 実データではJST時間帯(スプレッド拡大帯5:00-9:00等)からの生成interfaceを想定

### strategy signal input(`StrategySignalSafeInput`・既存engine入力)
- trend / momentum / volatility / spread / ticker / market / session / guard /
  position context — **safe labelのみ**。candleからの変換は
  `gmo_strategy_backtest_engine.convert_bar_to_signal_input`
  (算術のみ・LLM判断なし)が唯一の境界

## 3. データ品質ルール(fail-closed・実装済み)

- timestamp: 単調増加必須・重複禁止
- 欠損値: candle必須field欠損 / spread欠損 / session欠損 → dataset invalid
- 異常値: high < low → invalid
- warmup: 既定3bar(trend導出lookback)。warmup >= 総bar数 → invalid
- 実データ投入は将来の専用adapter Step経由のみ。本phaseでは
  `synthetic_fixture=false` のdatasetをvalidationがblockする

## 4. 分割形式

`split_backtest_dataset_chronologically` — warmup → train → validation → OOS
の時系列分割のみ(`CHRONOLOGICAL_NO_SHUFFLE`)。random shuffle・OOSの
parameter選定利用は `assert_no_lookahead_leakage` が例外でblock。

## 5. 実データadapter(設計のみ・fail-closed)

- `HistoricalDataAdapter` protocol: `load_dataset() -> BacktestDataset`
- `SyntheticHistoricalDataAdapter`: 本phase唯一の動作adapter
- `FutureCsvHistoricalDataAdapter`: local CSVのみ(download surfaceなし)。
  必須列 = timestamp(TZ明示)/ OHLC / spread / session。未実装のため
  `DATA_ADAPTER_NOT_CONFIGURED` でfail-closed
- `FutureBrokerExportHistoricalDataAdapter`: operatorがexportしたファイル限定
  (このコード経路からのbroker接続は永久に行わない)。同じくfail-closed

## 6. 取得候補(次Step `HISTORICAL_DATA_SOURCE_SELECTION_NO_POST` で選定)

- GMO公式のヒストリカルデータ(operator手動export)
- 既存repoのpublic klines取得スクリプト(`fetch_gmo_public_market_data.py`)の
  出力をローカルCSV化(取得自体は別Stepでoperator承認のうえ実施)
- spread実記録は live 時間帯での public ticker 記録が別途必要
