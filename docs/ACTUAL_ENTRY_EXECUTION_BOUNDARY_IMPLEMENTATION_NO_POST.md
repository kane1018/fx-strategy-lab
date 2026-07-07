# Actual Entry Execution Boundary — no-POST 実装記録

Step: `STEP_6G_PC_OX_R_ACTUAL_ENTRY_EXECUTION_BOUNDARY_IMPLEMENTATION_NO_POST_C`
（2026-07-07）

本書は no-POST 実装記録である。**本Stepで actual POST / entry POST は実行していない**。
`actual_entry_POST_allowed=false` は不変。実送信は、次回の別Step（actual gate）で、
fresh repo / fresh runtime read / fresh final preflight / current-turn operator input /
one-use activation / hard guard reviewed call site / **実 sender の injection** が
すべて揃った場合にのみ、entry POST 最大1回として可能になる。

## 1. review-first 分類

| 対象 | 分類 | 根拠 |
|---|---|---|
| entry-only request plan（`build_gmo_fx_entry_request_plan`） | `IMPLEMENTABLE_NO_POST_WITH_FAIL_CLOSED_TESTS` | 既存。path=`/private/v1/order` 固定。generic/settlement と分離済み |
| activation boundary | `IMPLEMENTABLE_NO_POST_WITH_FAIL_CLOSED_TESTS` | fail-closed factory。operator current-turn 入力必須 |
| single reviewed call site（send） | `REQUIRES_ACTUAL_POST_STEP_TO_EXECUTE` | 実送信は injected sender が必要。本Stepでは fake/refusing のみ |
| sealed credential unseal | `REQUIRES_ACTUAL_POST_STEP_TO_EXECUTE` | 実 unseal は injected 実 sender 内部でのみ。本Stepでは実値未読 |
| hard guard allow 供給 | `REQUIRES_OPERATOR_CURRENT_TURN_GATE` | `allow` は `activation.granted` から導出。単一 call site のみ |
| fresh runtime read | `REQUIRES_FRESH_RUNTIME_READ_GATE` | actual gate で fresh 実行必須 |
| generic order / settlement / close 流用 | `MUST_NOT_SHARE_GENERIC_ORDER_PATH` / `MUST_NOT_USE_SETTLEMENT_OR_CLOSE_PATH` | 本 boundary は entry-only。`market_order`/`live_order_once`/`closeOrder`/`settlePosition` を一切使わない |

review-first の9問への回答: (1) yes（`order_builders` の entry-only plan と `auth.py` の
injected 署名部品）(2) entry-only dedicated plan を直接使用し `GmoFxBroker.market_order`
は使わない (3) `live_order_once`/generic executor は import しない（source-scan で固定）
(4) hard guard は send の単一 call site で1回だけ (5) unseal は injected 実 sender 内部のみ
(6) yes（sender が sanitized outcome のみ返すため raw を境界外に出さない）(7) yes
（`EntryPostSafeOutcome` のみ）(8) yes（send に retry 分岐が存在しない・sender は2回目で例外）
(9) yes（refusing sender と injection 必須構造をテストで固定）。

## 2. 実装（injection-gated・fail-closed）

追加: `backend/app/services/gmo_live_actual_entry_execution_boundary.py`

- `ActualEntryOperatorCurrentTurnInput` + `verify_actual_entry_operator_input`
  - operator 4項目の完全一致のみ受理。`HOLD`・未知ラベルは `OPERATOR_SIGNAL_NOT_EXECUTABLE`
  - AI は side を判断しない（`ENTRY_BUY→ENTRY_OPEN_BUY` / `ENTRY_SELL→ENTRY_OPEN_SELL` の機械写像のみ）
- `ActualEntryExecutionActivation` + `build_actual_entry_execution_activation`
  - 9 gate（final preflight / fresh runtime / signoff / paper / anomaly / permit /
    hard guard supply / sanitized preview / credential presence）すべて満たす場合のみ `granted=true`
  - entry-only / one-use / settlement・close・generic・retry・repost・second POST すべて False 固定
  - `grants_hard_guard_allow` は `granted` から導出（literal True なし・banking 不可）
  - `__bool__=False`、repr/str は `<sanitized>`（action label・secret・ID を含めない）
- `ActualEntryOneShotSender`（Protocol・injection 点）
  - 実装は actual step で caller が注入。内部で credential unseal → auth header → 1回 POST →
    sanitized outcome のみ返す（raw/ID/value/credential を境界外に出さない）
- `FakeActualEntryOneShotSender`（テスト専用・network なし・2回目呼び出しで例外）
- `RefusingActualEntryOneShotSender`（既定状態が送信不能であることの証明・常時 raise）
- `send_actual_entry_post_once`（**単一 reviewed call site**）
  - granted / entry-only / 非 forbidden scope / entry plan であることを検証
  - `assert_real_broker_post_allowed(allow=activation.grants_hard_guard_allow)` を1回だけ
  - sender を**ちょうど1回**呼ぶ。**retry / repost / second POST 分岐は関数内に存在しない**
  - 結果は `ActualEntryExecutionResult`（sanitized outcome category のみ）

追加テスト: `backend/app/tests/test_gmo_live_actual_entry_execution_boundary_no_post.py`
（operator 一致/不一致・全 gate 個別 deny・HOLD 非実行・refusing sender・settlement plan 拒否・
1回のみ送信で再送なし・raw/ID/value/credential 非露出・source-scan で
live_verification/closeOrder/settlePosition/httpx/os.environ 不在と allow literal 恒久化なしを固定）。

## 3. 追加実装: Real Sender no-POST 対応（本Step）

STEP: `STEP_6G_PC_OX_R_REAL_ENTRY_SENDER_INJECTION_IMPLEMENTATION_NO_POST_C`
本Stepで `backend/app/services/gmo_live_actual_entry_sender.py` を追加し、`ActualEntryOneShotSender`
向けの実運用 sender を no-POST で実装した。既定で実 HTTP は走らず、呼び出し元が
`ActualEntrySenderHttpClient` / sealed credential を注入した場合のみ、entry plan を1回のみ
送信できる構造になっている（実際の送信タイミングは次の actual gate）。

- `GmoActualEntryOneShotHttpSender`
  - one-shot one-attempt（2回目送信は boundary error）
  - `build_auth_headers` を内部でのみ利用、ヘッダ/署名/資格情報を境界外に保持しない
  - 状態は `EntryPostSafeOutcome` の safe category のみ
- `map_entry_post_response_to_safe_outcome` / `map_entry_post_exception_to_safe_outcome`
  の追加
  - status と exception を safe outcome に即時変換
  - raw body / error body / ID の外部露出なし
- no-POST tests: `backend/app/tests/test_gmo_live_actual_entry_sender_no_post.py`
  - status/例外 mapping
  - one-shot / no retry / no repost / no second send
  - `live_order_once` / `closeOrder` / `settlePosition` / `httpx` source-scan

この Step 後、次 actual entry gate は "実 sender 注入 + fresh gates" でコード変更なし進行可とする。

## 4. final preflight 接続

`gmo_live_entry_final_preflight.py` 最小更新:

- 入力: `actual_entry_execution_boundary_implemented`（default false）
- status: `READY_FOR_ENTRY_POST_GATE_WITH_CURRENT_TURN_CONFIRMATION` 追加
  - signoff 記録済み＋boundary 実装済みで到達
  - **「READY」は実行許可ではない**。`actual_entry_POST_allowed=false`・`__bool__=false`・
    entry signal / exact confirmation 入力field不在（banking 不能）は不変

## 5. 本Step後の状態

- activation_boundary_status: `IMPLEMENTED_FAIL_CLOSED_ONE_USE_ENTRY_ONLY`
- sealed_credential_actual_boundary_status:
  `UNSEAL_INSIDE_INJECTED_SENDER_ONLY_NO_VALUE_EXPOSURE_THIS_STEP`
- production_entry_transport_status:
  `SINGLE_REVIEWED_CALL_SITE_IMPLEMENTED_SENDER_INJECTION_REQUIRED_NO_NETWORK_THIS_STEP`
- hard_guard_controlled_supply_status:
  `ALLOW_DERIVED_FROM_GRANTED_ACTIVATION_SINGLE_CALL_SITE_DEFAULT_DENY_NO_BRIDGE`
- final_preflight_status: `READY_FOR_ENTRY_POST_GATE_WITH_CURRENT_TURN_CONFIRMATION`
- actual_entry_POST_allowed: `false`
- retry / repost / second POST: 構造的に不可能
- settlement / close / generic route: 分離維持（本 boundary は entry-only）

## 6. 次回 actual gate で必要なもの（本Stepでは扱わない）

1. fresh workspace / HEAD==remote main / clean
2. fresh read-only runtime safe read（NO_POSITION / count 0 / active-pending clear / credential presence）
3. fresh final preflight 再評価
4. operator current-turn 4項目（`ENTRY_BUY`/`ENTRY_SELL` + exact confirmation 群・banking 無効）
5. **実 `ActualEntryOneShotSender` の injection**（credential unseal + auth header + 1回 POST を内部実行）
6. one-use permit 消費・hard guard 単一 call site 通過
7. 実行制約: 最大1回・no retry / no repost / no second POST・settlement/close/generic 禁止・
   result は sanitized category のみ・POST後は即停止（post-entry read-only confirmation は別Step）
