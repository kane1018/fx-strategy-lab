# Historical Data Local CSV Intake Spec（no-POST・local fileのみ）

Step: `HISTORICAL_DATA_SOURCE_SELECTION_NO_POST`
Date: 2026-07-08
実装: `gmo_historical_data_source_selection.build_local_csv_intake_requirements`

本仕様は次Step `HISTORICAL_DATA_IMPORT_ADAPTER_NO_POST` の受入契約である。
adapterは **local fileのみ** を読み、download・real HTTP・credentialを持たない。

## 1. 必須columns

`timestamp` / `symbol` / `timeframe` / `open` / `high` / `low` / `close` /
`source_label`

さらに official evaluation には以下の**いずれか1グループ**が必須:

- `spread`
- `bid_open, bid_high, bid_low, bid_close, ask_open, ask_high, ask_low, ask_close`
  (BID/ASK両OHLC → bar-level spread導出)
- `bid, ask`(bar代表値)

## 2. 任意columns

`volume` / `market_status` / `ticker_fresh_status` / `spread_status` /
`session_label` / `notes_safe_category`

## 3. 禁止columns(検出時は intake block)

`account_id` / `order_id` / `position_id` / `trade_id` / `transaction_id` /
`api_key` / `api_secret` / `signature` / `header` / `credential` /
`raw_response` / `broker_response`(自由記述のraw broker response列も禁止)

## 4. validation rules(実装labelで固定)

- timestamp必須・**UTC epochまたはTZ明示ISO**(`UTC_EPOCH_OR_ISO_WITH_EXPLICIT_TZ`)
- timestamp単調増加・重複block・欠損candle block
- symbol / timeframe / source_label 必須
- OHLC必須・数値・high >= low
- **spreadまたはbid/askがofficialに必須**。欠損時は
  `CSV_INTAKE_BLOCKED_MISSING_SPREAD`(official)/ 最良でもreference-only
- sessionはTZから導出または提供。unknownは blocked or reference-only
- 実データは `synthetic_fixture=false` で投入(backtest dataset側の
  本phase synthetic-only blockは import adapter Stepで解除方針を定義)

## 5. intake result categories

`CSV_INTAKE_READY_OFFICIAL_EVALUATION` / `CSV_INTAKE_READY_REFERENCE_ONLY` /
`CSV_INTAKE_BLOCKED_MISSING_SPREAD` / `CSV_INTAKE_BLOCKED_MISSING_TIMESTAMP_TZ` /
`CSV_INTAKE_BLOCKED_INVALID_COLUMNS` / `CSV_INTAKE_BLOCKED_FORBIDDEN_COLUMNS` /
`CSV_INTAKE_NOT_PROVIDED`

## 6. header例(placeholderのみ・実データ値は書かない)

```
timestamp,symbol,timeframe,open,high,low,close,bid_close,ask_close,source_label
<UTC_EPOCH_MS>,USD_JPY,M5,<OHLC_PLACEHOLDER>,...,<SOURCE_LABEL>
```

実データ値・実spread値・broker生値は本docs以下すべてのdocsに記載禁止。

## 7. spread / timezone policy

- spread policy: `SPREAD_OR_BID_ASK_REQUIRED_FOR_OFFICIAL_EXCLUDED_IS_REFERENCE_ONLY`
- bid/ask由来spreadは bar-level 近似であることをreportに明記
  (official条件label: `OFFICIAL_CONDITION_SPREAD_FROM_BID_ASK_BAR_APPROXIMATION`)
- timezone policy: UTC基準。JST session labelはUTC timestampから導出
