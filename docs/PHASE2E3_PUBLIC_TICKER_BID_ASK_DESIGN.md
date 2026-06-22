# Phase 2E-3: Public ticker bid/ask provenance連携設計

## 1. 目的と結論

本書は、既存の shadow session `--enable-shadow-risk` 経路へ、GMO Public ticker由来の
bid/askを安全に渡すための設計である。

今回は **設計のみ** であり、backend code、tests、frontend、公開API、broker、Private API、APIキー、
実注文、実資金、自動売買、GMO Public実行は変更・実行しない。

結論:

- `REAL_PUBLIC_BID_ASK` は、GMO Public `/v1/ticker` 由来で、bid/ask、symbol、timestamp、freshness、
  spread、safety flagsを検証できた場合だけ付与する。
- kline-only runは引き続きsynthetic spreadとしてfail closedに倒し、`REAL_PUBLIC_BID_ASK`を付与しない。
- ticker取得失敗、timestamp不正、stale、symbol mismatch、ask < bid、spread上限超過はfail closedに倒す。
- raw Public API responseは保存せず、sessionへ渡すのはsanitizedな`MarketSnapshot`または同等のlocal-only値に限定する。
- session本体はnetworkを行わず、broker、Private API、APIキー、注文系へ接続しない。

## 2. 現在地

- Phase 2E-2.5監査はB判定で、Phase 2E-3設計へ進める。
- `--enable-shadow-risk`は明示フラグでのみ有効になる。
- default runはlegacy互換で、risk/audit JSONLを生成しない。
- 現行のrisk有効mock/kline-only経路は`SYNTHETIC_ZERO`としてrejectされ、virtual resultへ進まない。
- Phase 2E-2.5確認時のmock kline-only risk runはcandidate 4、reject 4、orders 0だった。
- offline testでは明示bid/ask hookにより`REAL_PUBLIC_BID_ASK` allow経路を確認済み。
- 実際のGMO Public ticker bid/askをsessionへ渡す接続は未実装。
- Private API、broker、OrderRequest、`.env`、実注文は未接続である。

## 3. 範囲

Phase 2E-3実装タスクで扱ってよい候補:

- `backend/app/shadow/gmo_public.py`
- `backend/scripts/run_shadow_session.py`
- `backend/app/shadow/session.py`
- `backend/app/shadow/risk.py`
- `backend/app/shadow/audit_schema.py`
- `backend/app/shadow/aggregate.py`
- `backend/app/tests/test_shadow_*.py`
- 関連docs

ただし、本書作成時点では上記コードを変更しない。

Phase 2E-3で扱わないもの:

- `backend/app/main.py`
- `backend/app/main_readonly.py`
- backend公開API router
- frontend
- Render / Vercel設定
- `.env`、APIキー、secret
- GMO/OANDA Private API
- `backend/app/brokers/`
- live RiskManager、OrderRequest、注文・注文変更・注文取消
- DB、認証、本番公開機能
- `shadow_exports/`、`analysis_exports/`生成物のcommit

## 4. データ責務

### 4.1 Public adapter

GMO Public ticker取得は、既存の`backend/app/shadow/gmo_public.py`の
`GmoPublicMarketDataClient.fetch_ticker()`を第一候補にする。

理由:

- 既にPublic endpointのみを扱うshadow配下のadapterである。
- APIキー、Private API、注文系に接続していない。
- raw responseを保存しない。
- `Ticker(symbol, bid, ask, time)`へ正規化する責務が既にある。

将来`backend/app/integrations/`等へ移す場合は別レビューとし、Phase 2E-3の最小実装では新しいintegration層を
増やさない。

### 4.2 CLI / orchestrator

`backend/scripts/run_shadow_session.py`は、`--source gmo-public`かつ`--enable-shadow-risk`のときだけ、
Public klinesに加えてPublic tickerを取得する。

責務:

- Public adapterからcandlesとtickerを取得する。
- raw responseではなく、正規化済みtickerからsanitized snapshotを作る。
- `REAL_PUBLIC_BID_ASK`を名乗れるかをsession/riskへ判定可能な形で渡す。
- STOP file pre-gate、steps上限、local-only出力境界を維持する。

### 4.3 session

`backend/app/shadow/session.py`はnetworkを行わない。

責務:

- candle、signal、snapshot/ticker providerを受け取る。
- BUY/SELL時だけcandidateを作る。
- snapshotが有効な場合だけ`REAL_PUBLIC_BID_ASK`候補を作る。
- snapshotがない、または不正な場合はfail closedに倒す。
- REJECT時はvirtual resultを生成しない。
- audit write failure時は既存どおりkill switch active / exit code 2に倒す。

sessionへ渡す値はsanitized済みで、secret、account、raw response、header、request metadataを含めない。

## 5. MarketSnapshot案

Phase 2E-3実装では、`MarketSnapshot`または同等のimmutable DTOを追加する。

候補field:

```text
schema_version: "market-snapshot-v1"
source: "gmo-public"
symbol: "USD_JPY"
interval: "M1"
kline_timestamp: datetime
ticker_timestamp: datetime
bid: Decimal
ask: Decimal
mid: Decimal
spread_pips: Decimal
spread_provenance: "REAL_PUBLIC_BID_ASK" | "SYNTHETIC_ZERO" | "UNKNOWN"
private_api_used: false
api_key_used: false
raw_response_saved: false
validation_status: "valid" | "invalid"
reject_reason: str | null
```

禁止field:

- raw JSON response
- request/response headers
- APIキー、secret、token
- account ID、position、balance、order ID、execution ID
- broker名を実注文経路として識別できる情報
- `.env`由来値

## 6. REAL_PUBLIC_BID_ASK付与条件

`REAL_PUBLIC_BID_ASK`は、次の条件を全て満たす場合だけ付与する。

- sourceはGMO Public `/v1/ticker`である。
- Private APIを使っていない。
- APIキー、secret、tokenを使っていない。
- broker、OrderRequest、注文系を使っていない。
- raw responseを保存していない。
- ticker symbolがsession symbolと完全一致する。
- bidとaskが存在する。
- bidとaskがDecimal変換できる。
- bidとaskがfiniteである。
- bid > 0、ask > 0である。
- ask >= bidである。
- ticker timestampが存在する。
- ticker timestampがtimezone-awareまたは明確にUTCへ正規化できる。
- ticker timestampが現在時刻より`max_future_skew_seconds`を超えて未来ではない。
- ticker timestampが`max_ticker_age_seconds`以内である。
- ticker timestampとkline timestampの差が`max_ticker_kline_skew_seconds`以内である。
- spread_pipsがfiniteで、0以上である。

spread上限判定:

- `spread_pips <= RiskPolicy.max_spread_pips`なら通常のrisk評価へ進める。
- `spread_pips > RiskPolicy.max_spread_pips`なら`spread_too_wide`等の通常REJECTにする。
- spread上限超過は安全違反ではなく、取引しない正常なfail closedである。

## 7. timestamp / freshness方針

初期値案:

```text
max_ticker_age_seconds: 30
max_ticker_kline_skew_seconds: 90
max_future_skew_seconds: 5
RiskPolicy.max_data_age_seconds: 180
```

方針:

- `REAL_PUBLIC_BID_ASK` candidateの`market_data_timestamp`はticker timestampを使う。
- kline timestampは`MarketSnapshot.kline_timestamp`に保持し、ticker/kline skew判定に使う。
- ticker timestampのstale/future/skew不正はfail closedに倒す。
- stale/future/skew不正は通常REJECTまたはNO_TRADE扱いであり、Private API使用やraw保存のようなsafety violationとは区別する。

## 8. spread_pips計算方針

USD/JPY初期設計:

```text
spread_pips = (ask - bid) / Decimal("0.01")
```

方針:

- Decimalで計算し、audit/summaryへ保存する直前に必要最小限でfloat化する。
- ask < bidはinvalid dataとしてfail closed。
- spread_pips < 0はinvalid dataとしてfail closed。
- spread_pips == 0はPublic ticker由来として条件を満たす場合のみ許容する。
- kline-only synthetic zeroは引き続き`SYNTHETIC_ZERO`でrejectする。

## 9. fail closed設計

| ケース | 期待挙動 |
| --- | --- |
| kline-only / tickerなし | `SYNTHETIC_ZERO`としてREJECT、またはcandidateなし。初期実装は既存互換のREJECT優先 |
| ticker fetch failure | NO_TRADEまたはcandidateなし。summaryへfetch error countを記録 |
| ticker symbol mismatch | invalid dataとしてREJECT、virtual resultなし |
| bid/ask missing | invalid dataとしてREJECT、virtual resultなし |
| bid <= 0 / ask <= 0 | invalid dataとしてREJECT、virtual resultなし |
| ask < bid | invalid dataとしてREJECT、virtual resultなし |
| stale ticker | stale dataとしてREJECT、virtual resultなし |
| ticker too far future | invalid/stale dataとしてREJECT、virtual resultなし |
| ticker/kline skew超過 | stale/skew reject、virtual resultなし |
| spread上限超過 | spread_too_wide REJECT、virtual resultなし |
| raw response保存検知 | safety violation扱いで停止候補 |
| Private/APIキー/broker使用検知 | safety violation扱いで停止 |

初期実装では、観測性を維持するため、BUY/SELL signalがありsnapshot不正を説明できる場合はcandidate + REJECTを優先する。
ticker fetch failureなどcandidate価格を安全に作れない場合はsignal logのみでNO_TRADEに倒してよい。

## 10. audit log設計

初期実装で保存してよいsanitized情報:

- candidate_id
- decision_id
- symbol
- interval
- side
- units
- entry_reference_price
- market_data_timestamp
- spread_pips
- spread_provenance
- reject reason
- fixed safety flags

保存しない情報:

- raw Public API response
- request/response headers
- APIキー、secret、token
- account、balance、position、order、execution
- broker private response

新しい`market_snapshot_log.jsonl`は初期実装では必須にしない。追加する場合はschema reviewを行い、raw responseが
入らないこと、typed validatorで壊れrowを検出できること、legacy summarize互換を壊さないことを受け入れ条件に含める。

## 11. summary / metadata案

将来追加してよいsummary/metadata key:

```text
ticker_bid_ask_used_count
real_public_bid_ask_count
synthetic_spread_reject_count
ticker_missing_count
ticker_invalid_count
ticker_stale_count
ticker_kline_skew_reject_count
public_ticker_fetch_error_count
spread_too_wide_count
raw_response_saved: false
private_api_used: false
api_key_used: false
```

方針:

- 既存summary keyを削除・改名しない。
- legacy runでは新規keyがなくても集計できる。
- risk有効runでは新規keyがあっても既存summarizeが壊れない。
- `raw_response_saved`、`private_api_used`、`api_key_used`は固定falseを基本にする。

## 12. GMO Public run計画

Phase 2E-3実装後の手動確認候補:

```bash
cd /Users/naoikansui/Desktop/トレード/backend
python3 -m scripts.run_shadow_session \
  --source gmo-public \
  --symbol USD_JPY \
  --interval M1 \
  --date <YYYYMMDD> \
  --steps 10 \
  --enable-shadow-risk
python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
```

本書作成時点では上記を実行しない。

実行時の確認:

- APIキーなしでPublicだけを使う。
- `.env`を読まない。
- Private APIへ接続しない。
- brokerへ接続しない。
- 実注文、注文変更、注文取消を行わない。
- raw responseを保存しない。
- `shadow_exports/`をcommitしない。

## 13. テスト方針

Phase 2E-3実装時に追加するoffline tests:

- valid Public tickerで`REAL_PUBLIC_BID_ASK` candidateが作られる。
- valid Public tickerでALLOWならvirtual resultがcandidate/decisionと相関する。
- kline-only mockはsynthetic spread rejectを維持する。
- missing bid/askはfail closed。
- bid <= 0、ask <= 0はfail closed。
- ask < bidはfail closed。
- non-finite bid/askはfail closed。
- stale tickerはfail closed。
- future tickerはfail closed。
- ticker/kline skew超過はfail closed。
- symbol mismatchはfail closed。
- fetch_ticker exceptionはfail closed。
- spread_too_wideはREJECT。
- Public ticker由来のzero spreadは条件付きで許容される。
- synthetic zero spreadはrejectされる。
- raw responseを保存しない。
- `.env`、Private API、broker、OrderRequestへのimport/接続がない。
- CLI-level STOP file pre-gateがexit code 2を返す。
- candidate生成時signalとvirtual fill時signalのdriftを防ぐ。
- summarizeはlegacy runとticker bid/ask runを同時に扱う。

## 14. acceptance criteria

Phase 2E-3実装を完了と判定する条件:

- `REAL_PUBLIC_BID_ASK`がPublic ticker由来であることをtestで固定している。
- kline-only経路は`REAL_PUBLIC_BID_ASK`にならない。
- 不正ticker、stale、skew、spread上限超過はfail closedになる。
- REJECT時にvirtual resultが生成されない。
- ALLOW時だけcandidate/decision/virtual resultが相関する。
- raw responseを保存しない。
- Private API、APIキー、broker、OrderRequest、実注文経路に接続しない。
- backend公開API、`main_readonly.py`、frontend、Render/Vercel設定を変更しない。
- `shadow_exports/`、`analysis_exports/`生成物をcommitしない。
- offline pytest/ruffが通る。
- 手動GMO Public runを行う場合は、local-only、steps上限付き、注文なしで実施し、生成物をcommitしない。

## 15. リスクと緩和策

| リスク | 緩和策 |
| --- | --- |
| kline-only価格をreal bid/askと誤認する | `spread_provenance`必須、syntheticはreject |
| raw responseを保存する | DTOにraw fieldを持たせず、testsとsecret grepで確認 |
| stale tickerを使う | `max_ticker_age_seconds`とfuture/skew checks |
| tickerとklineの時刻がずれる | `max_ticker_kline_skew_seconds` |
| spread異常でALLOWする | Decimal計算、ask >= bid、max_spread_pips |
| Public ticker endpoint障害 | Private/APIキーへfallbackせず、NO_TRADEまたはREJECT |
| 市場時間外でticker/klinesが不足する | 失敗を正常なfail closedとして扱い、実行時間を前提にしない |
| ALLOW増加によりvirtual resultを収益性と誤解する | summary/docsでlocal-only検証値と明記し、実資金評価に使わない |
| sessionがnetwork責務を持つ | CLI/orchestratorで取得し、sessionはsanitized値だけ受け取る |
| Private/broker経路へ近づく | import grep、触らないファイル境界、レビュー必須 |
| summary互換を壊す | key追加のみ、legacy missing key許容 |

## 16. 次に進む条件

Phase 2E-4以降のgmo-public risk/audit確認や追加拡張へ進むには、Phase 2E-3実装結果のレビュー後に
明示承認を得る。

承認前に進まないもの:

- GMO Public run
- Private API
- APIキー
- broker
- 実注文
- 実資金
- 自動売買
- 本番公開API追加

## 17. 実装結果

Phase 2E-3実装では、設計に基づいてlocal-onlyの最小接続を完了した。

実装済み:

- `MarketSnapshot` validationを追加し、GMO Public ticker由来で厳格条件を満たすbid/askだけを
  `REAL_PUBLIC_BID_ASK`として扱う。
- `max_ticker_age_seconds=30`、`max_ticker_kline_skew_seconds=90`、`max_future_skew_seconds=5`で
  timestamp/freshness/skewを確認する。
- spreadはDecimalで`(ask - bid) / Decimal("0.01")`として計算する。
- `--source gmo-public --enable-shadow-risk`時のみ、CLIがPublic tickerを取得してsanitized snapshot providerを
  sessionへ渡す。session本体はnetworkを行わない。
- kline-onlyは既存どおりsynthetic spread rejectを維持する。
- missing/invalid/stale/future/skew tickerはfail closedに倒し、REJECT/NO_TRADE時はvirtual resultを作らない。
- summary/metadataへticker optional countsと`raw_response_saved=false`を追加した。
- legacy summary、risk log schema、backend公開API、`main_readonly.py`、frontendは変更していない。

今回もGMO Public実run、Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進んでいない。
