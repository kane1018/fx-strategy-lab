# Historical Data Source Selection（no-POST・no-download）

Step: `HISTORICAL_DATA_SOURCE_SELECTION_NO_POST`
Date: 2026-07-08
実装: `backend/app/services/gmo_historical_data_source_selection.py`

## 1. 目的・対象範囲・対象外

実データbacktestに使うヒストリカルデータソースの調査・比較・選定。
**このStepでは実データ取得・download・broker接続・API接続・credential使用・
real HTTP・private GETを一切行っていない**(分類モデルとdocsのみ)。
source選定はperformance proofではない
(performance_proof_status=false / live_ready=false)。

## 2. repo内データ資産棚卸し(safe category)

- `DATA_ASSET_PUBLIC_KLINE_SCRIPT_PRESENT`:
  `backend/scripts/fetch_gmo_public_market_data.py` +
  `app/shadow/gmo_public.GmoPublicMarketDataClient` — GMO Public API klines、
  **price_type BID / ASK 両対応**、openTime=ms epoch(UTC変換済み)、認証不要、
  stdout出力のみ(保存なし)
- `DATA_ASSET_SPREAD_MISSING`(単一series)/ ただし **BID+ASK両series export で
  bar-level spread導出可能**
- `DATA_ASSET_SESSION_LABEL_PRESENT`: JST時間帯policy(5:00-9:00拡大帯等)は
  runbook/dataset要件に既定。生成interfaceは設計済み
- `DATA_ASSET_ADAPTER_DESIGNED_NOT_CONFIGURED`:
  `FutureCsvHistoricalDataAdapter` / `FutureBrokerExportHistoricalDataAdapter`
  は fail-closed 設計のみ
- `DATA_ASSET_SYNTHETIC_ONLY`(backtest層)/ `DATA_ASSET_REAL_IMPORT_NOT_READY`
- 実データファイルはrepo内に存在しない(shadow_exportsはcommit禁止policy)

## 3. Candidate matrix

| candidate | 取得方法 | 本Step自動化 | credential | real HTTP(投入時) | spread | session | TZ | broker整合 | 分類 |
|---|---|---|---|---|---|---|---|---|---|
| A: GMO Public klines BID+ASK → local CSV | operator承認の別Stepでpublic GETスクリプト実行→CSV化 | 不可(本Stepはdownloadなし) | 不要 | 不要(intakeはlocal file) | **bid/ask両OHLCから導出可** | TZから導出可 | 明確(UTC epoch) | GMO自身のレート | **OFFICIAL候補**(条件付き) |
| B: GMO会員画面 手動export | operator手動 | 不可 | 不要(operator画面操作) | 不要 | export内容依存(通常spread列なし) | 導出可 | 要確認 | GMO | **REFERENCE-ONLY**(spread列が確認できればofficial昇格をoperatorが判断) |
| C: 他broker export CSV | operator手動 | 不可 | 不要 | 不要 | bid/askあり得る | 導出可 | 明確 | **GMOと乖離** | official条件を満たしてもCAUTION付き(実行環境差)。原則reference扱い推奨 |
| D: synthetic fixture | in-process | 可 | 不要 | 不要 | synthetic | synthetic | synthetic | なし | DEVELOPMENT-ONLY(性能評価不可) |
| E: credential/API必須source | — | 不可 | 必要 | 必要 | — | — | — | — | **BLOCKED** |

分類はテストで固定(`classify_historical_data_source`)。

## 4. 分類ルール(実装済み・fail-closed)

- BLOCKED: credential必要 / broker API必要 / intakeにreal HTTP必要 /
  forbidden columns / local CSV化不可 / TZ不明
- DEVELOPMENT_ONLY: synthetic(performance proof永久不可)
- OFFICIAL_EVALUATION_CANDIDATE: OHLC + (spread列 or bid/ask) + TZ + session導出可
  - bid/ask由来の場合は
    `OFFICIAL_CONDITION_SPREAD_FROM_BID_ASK_BAR_APPROXIMATION` を条件として付記
    (bar-level近似であり、tick-level spreadより保守的な取り扱いが必要)
  - GMO非整合brokerは `CAUTION_BROKER_ENVIRONMENT_DIFFERS_FROM_GMO` 付記
- REFERENCE_ONLY_CANDIDATE: OHLCのみ(spreadデータなし)
- **spreadなしのデータはofficial evaluation不可 / spread excludedはREFERENCE_ONLY /
  syntheticはperformance proof不可**

## 5. 推奨route(decision・実装済み)

- **Primary: `GMO_PUBLIC_KLINES_BID_ASK_LOCAL_CSV`** — GMO自身の公開レートで
  broker整合・credential不要・TZ明確。BID/ASK両seriesを取得しbar-level spreadを
  導出(取得実行はoperator承認の次Step以降。**このStepでは未取得**)
- Secondary: `GMO_MEMBER_SITE_MANUAL_EXPORT_CSV`(operatorがspread列有無を確認)
- Development-only: synthetic fixture継続
- Blocked: credential/API/real HTTP必須のsource一切

## 6. operatorが準備・判断すべきもの(次Step前)

1. symbol(推奨: USD_JPY)と timeframe(推奨: M5)の確定
2. date range(train/validation/OOSを賄う期間。目安: 最低3ヶ月以上を推奨、最終はoperator判断)
3. public kline export 実行の承認(BID と ASK の両方・別Stepで実行)
4. local CSV file path の提供
5. データソース利用条件がローカル分析用途を許容することの確認
   (Codexは法的判断を断定しない)

## 7. 次Step

- `HISTORICAL_DATA_IMPORT_ADAPTER_NO_POST` — local CSV adapter実装
  (intake spec: [HISTORICAL_DATA_LOCAL_CSV_INTAKE_SPEC_NO_POST.md](HISTORICAL_DATA_LOCAL_CSV_INTAKE_SPEC_NO_POST.md))
- データ投入後: `STRATEGY_BACKTEST_WITH_REAL_DATA_NO_POST`
