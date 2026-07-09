# API Capability Sheet（sanitized / unknown-default / no-POST）

Date: 2026-07-10

Owner: operator

Initial status: `UNFILLED_UNKNOWN_DEFAULT`

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
| sheet status | `UNFILLED_UNKNOWN_DEFAULT` |
| operator reviewed | `false` |
| official specification reviewed | `false` |
| review date | `UNKNOWN` |
| reviewer safe label | `OPERATOR_NOT_RECORDED` |
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
| client order ID or idempotency key | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| position-specific close route | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| server-side SL/TP attached to entry | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| partial-fill semantics | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| supported order types | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| order-state query | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| position query | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| maintenance windows | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| public/private rate limits | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| minimum lot and increments | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| account mode: netting / hedging | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| terms-of-service automation policy | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |

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
api_capability_sheet_status: UNFILLED_UNKNOWN_DEFAULT
operator_reviewed: false
official_specification_reviewed: false
all_required_items_answered: false
idempotency_or_client_order_id: UNKNOWN
position_specific_close_route: UNKNOWN
server_side_sl_tp_attached_to_entry: UNKNOWN
partial_fill_semantics: UNKNOWN
order_types_supported: UNKNOWN
order_state_query: UNKNOWN
position_query: UNKNOWN
maintenance_windows: UNKNOWN
rate_limits: UNKNOWN
min_lot_and_increments: UNKNOWN
account_mode: UNKNOWN
tos_automation_policy: UNKNOWN
credential_value_recorded: false
real_id_value_recorded: false
raw_request_response_recorded: false
actual_api_call_performed: false
actual_post_permission: false
e1_gate_passed: false
e2_allowed: false
e3_allowed: false
```
