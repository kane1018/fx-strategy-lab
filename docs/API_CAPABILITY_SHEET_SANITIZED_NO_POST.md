# API Capability Sheet（sanitized / unknown-default / no-POST）

Date: 2026-07-10

Owner: operator

Current status: `PARTIAL_PUBLIC_SPEC_REVIEW_NO_ACTUAL_CHECK`

E1 dependency: `false`

## 1. 目的

将来の E2→E3 review に必要な broker API 能力を、**仕様レベルの sanitized 情報だけ**で
整理する operator 記入用テンプレート。

現在はすべて `UNKNOWN` であり、本 sheet の作成・記入・完了は次のいずれも意味しない。

- credential / permission の確認済み
- actual account での利用可能性
- E1 / E2 gate 通過
- E3 / live readiness
- actual POST permission
- unattended live permission

E1 engine は本 sheet を読み込まず、risk gate、`ShadowGateToken`、hard guard allow の
入力に使用しない。

## 2. Sanitization rules

### 記入してよいもの

- `YES` / `NO` / `UNKNOWN`
- 公式仕様の種別や概要
- 公式ドキュメントの公開ページ名 / 参照日
- 仕様上の order type 名、account mode 名、通知方式の種別
- rate-limit や maintenance window の公開仕様概要

### 記入してはいけないもの

- API key / secret / token / password / signature / header
- credential の値、長さ、hash、fingerprint、先頭末尾
- account / order / execution / position / client order ID の実値
- actual request / response / error body / screenshot の raw 値
- actual balance / position / order / execution / quantity / price / PnL
- `.env` の内容、env 一覧、permission 画面の raw 値
- actual endpoint への接続結果や「試しに POST した」結果

不明な項目は推測せず `UNKNOWN` のままにする。コード上の実装存在や過去 docs claim を
API 仕様の `YES` 根拠にしない。

## 3. Review metadata（初期値）

| Field | Value |
| --- | --- |
| sheet status | `PARTIAL_PUBLIC_SPEC_REVIEW_NO_ACTUAL_CHECK` |
| operator reviewed | `false` |
| official specification reviewed | `true`（H-11 v3に直接必要な公開項目のみ） |
| review date | `2026-07-11` |
| reviewer safe label | `CODEX_PUBLIC_SPEC_ONLY` |
| actual credential checked | `false` |
| actual account setting checked by Codex | `false` |
| actual API call performed for this sheet | `false` |
| POST performed for this sheet | `false` |
| E2 allowed | `false` |
| E3 allowed | `false` |
| actual POST permission | `false` |

## 4. Capability checklist（operator 記入欄）

| Capability | Current value | Sanitized specification note | Public source title / review date |
| --- | --- | --- | --- |
| client order ID or idempotency key | `YES_CLIENT_ORDER_ID` | 36文字以内の半角英数字。idempotency保証・actual account利用可否は未確認 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| position-specific close route | `YES_SPEC_ONLY` | `closeOrder`の`settlePosition`でposition ID＋sizeを指定可能。v3 actual pathではID安全処理未完成のため未使用 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| server-side SL/TP attached to entry | `YES_IFDOCO_CONDITIONAL` | `ifoOrder`は一次LIMIT/STOPと二次LIMIT＋STOPを同一親注文で表現。通常MARKET entryへの直接付帯ではない | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| partial-fill semantics | `PARTIAL_OBSERVABILITY_SPEC_ONLY` | executionEventsに`executionSize` / `orderExecutedSize` / `orderSize`あり。partial発生条件・IFDOCO子注文連動・REST反映遅延は未確定 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| supported order types | `PARTIAL_YES` | 公開仕様: NORMAL / OCO / IFD / IFDOCO / LOSSCUT、MARKET / LIMIT / STOP。actual account可否は未確認 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| order-state query | `YES_SPEC_ONLY` | orders / activeOrdersの公開仕様あり。反映遅延・unknown解消能力は未確認 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| position query | `YES_SPEC_ONLY` | openPositionsの公開仕様あり。actual account・反映遅延は未確認 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| pending order expiry | `FIELD_PRESENT_DURATION_UNCONFIRMED` | order/activeOrders/IFDOCO responseに`expiry`と`EXPIRED`あり。ただしifoOrder requestにexpiry指定項目がなく、有効期限決定規則を公開仕様から確定できない | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| private order/execution notification | `YES_SPEC_ONLY` | Private WebSocketにorderEvents / executionEventsあり。token取得・延長はPrivate APIを要するためactual確認なし | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| maintenance windows | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| public/private rate limits | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| minimum lot and increments | `YES_PUBLIC_SPEC_USD_JPY` | 公開symbols仕様例: minOpenOrderSize=10000、sizeStep=1、tickSize=0.001。actual activation時はfresh public rule照合必須 | GMOコイン 外国為替FX APIドキュメント / 2026-07-11 |
| account mode: netting / hedging | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| terms-of-service automation policy | `SERVICE_SUPPORTS_API_AUTOMATION` | GMO公式商品ページが外国為替FX APIによる自動売買を案内。actual account契約・API手数料・責任条項のoperator確認は別途必要 | GMOコイン API（外国為替FXの自動売買） / 2026-07-11 |

公開仕様レビュー元: [GMOコイン 外国為替FX APIドキュメント](https://api.coin.z.com/fxdocs/)。
これは公開ページの文書確認だけであり、actual account、permission、credential、API接続、POSTの確認ではない。

## 5. 項目ごとの記入ガイド

### client order ID or idempotency key

- `YES / NO / UNKNOWN` と、仕様上の適用範囲だけを記入する。
- actual key / ID を記入しない。
- settlement で同一 key を使う場合の仕様が不明なら `UNKNOWN`。

### position-specific close route

- position の指定方式が仕様上存在するかだけを記入する。
- actual position ID、request body、endpoint 呼び出し結果は記入しない。
- generic close のみで position-specific route が無い場合は `NO`。

### server-side SL/TP attached to entry

- entry と同時に broker-side protection を指定できるかを記入する。
- client-side の監視ロジックは `YES` の根拠にしない。
- SL と TP の能力が異なる場合は note で分離する。

### partial-fill semantics

- partial fill の有無、状態遷移、通知 / query 方式の種別を sanitized に記入する。
- actual fill / execution ID や actual response を記入しない。

### supported order types

- 公開仕様の名称のみを列挙する。
- actual account で利用可能であることは別問題として扱う。

### order-state query / position query

- query 粒度、反映遅延、完了 / unknown の区別可能性を記入する。
- 信頼性が不明なら `UNKNOWN`。
- actual account を照会しない。

### maintenance windows / rate limits

- 公開仕様の定期メンテナンス、週末、ロールオーバー、rate-limit 区分を記入する。
- actual header / actual error response を記入しない。

### minimum lot and increments / account mode

- 公式仕様の数値 / mode と、actual account の設定を混同しない。
- 数値を記入する場合は「公開仕様値」と明記する。

### terms-of-service automation policy

- operator が公開されている利用規約を確認する責任を負う。
- Codex は actual account の契約状態や例外許可を推測しない。

## 6. Fail-closed decision rules

本 sheet を将来 review に使う場合も、次を fail-closed とする。

- 一項目でも未記入 / 矛盾 / 根拠不明なら `UNKNOWN`。
- idempotency も reliable state query も無い / 不明な場合、full automation は E2 で停止。
- server-side SL が無い / 不明な場合、E3 は開かない。
- position-specific close route が無い / 不明な場合、E3 kill auto-flatten は開かない。
- partial fill / order state / position state の reconcile 方法が不明なら E3 は開かない。
- `YES` が記入されても、stage gate、budget、runbook、operator review、他の fresh gate を
  代替しない。

これらは将来の review 条件であり、E2 / E3 の開始を許可する文言ではない。

## 7. Operator completion block（初期値）

```yaml
api_capability_sheet_status: PARTIAL_PUBLIC_SPEC_REVIEW_NO_ACTUAL_CHECK
operator_reviewed: false
official_specification_reviewed: true
all_required_items_answered: false
idempotency_or_client_order_id: YES_CLIENT_ORDER_ID_SPEC_ONLY
position_specific_close_route: YES_SPEC_ONLY_NOT_ENABLED
server_side_sl_tp_attached_to_entry: YES_IFDOCO_CONDITIONAL
partial_fill_semantics: PARTIAL_OBSERVABILITY_SPEC_ONLY
order_types_supported: PARTIAL_YES_SPEC_ONLY
order_state_query: YES_SPEC_ONLY
position_query: YES_SPEC_ONLY
maintenance_windows: UNKNOWN
rate_limits: UNKNOWN
pending_order_expiry: FIELD_PRESENT_DURATION_UNCONFIRMED
private_order_execution_notification: YES_SPEC_ONLY
min_lot_and_increments: YES_PUBLIC_SPEC_USD_JPY_REQUIRES_FRESH_CHECK
account_mode: UNKNOWN
tos_automation_policy: SERVICE_SUPPORTS_API_AUTOMATION_OPERATOR_CONFIRMATION_PENDING
credential_value_recorded: false
real_id_value_recorded: false
raw_request_response_recorded: false
actual_api_call_performed: false
actual_post_permission: false
e1_gate_passed: false
e2_allowed: false
e3_allowed: false
```
