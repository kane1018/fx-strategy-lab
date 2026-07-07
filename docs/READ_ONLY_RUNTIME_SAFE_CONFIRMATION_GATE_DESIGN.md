# Read-only Runtime Safe Confirmation Gate Design (No-POST)

- step_name: `STEP_6G_PC_OX_R_READ_ONLY_RUNTIME_SAFE_CONFIRMATION_GATE_DESIGN_NO_POST_C`
- scope: `no-POST`
- actual_post_this_step: `false`
- entry_post_this_step: `false`
- settlement_post_this_step: `false`
- post_count_this_step: `0`
- runtime_private_GET_executed_this_step: `false`
- raw_or_credential_exposure_this_step: `false`
- actual_POST_permission_inference: `false`

## 1) 目的（Design-only）

このStepは、将来のno-POST前提の runtime private GET 確認を安全に実行できるための
設計・条件・ゲートを定義する。実際のネットワーク／実API呼び出し／credential実読取は実施しない。

## 2) このStepで確定した最終方針

- `anomaly_evidence_status` は引き続き `SYNTHETIC_ONLY_NOT_SUFFICIENT`。
- `paper_trade_evidence_status` は `PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY` を保持。
- `actual_entry_POST_allowed`: `false`
- `actual_settlement_POST_allowed`: `false`
- `read_only_runtime_private_confirmation_gate` は設計のみ追加。

## 3) repository gate（再評価時の前提）

以下を満たすことを再評価Stepで確認。

- branch = `main`
- `HEAD == origin/main`
- `working tree clean`
- `ahead/behind == 0/0`
- no merge / no rebase / no stash / no git clean / no force push

## 4) operator current-turn confirmation（次Step）

次Stepで必須とする exact confirmation:

- `OPERATOR_READY_FOR_READ_ONLY_RUNTIME_SAFE_CONFIRMATION_NO_POST`
- `CONFIRM_READ_ONLY_RUNTIME_SAFE_CONFIRMATION_NO_POST_NO_RAW_NO_ID_NO_VALUE`
- `OPERATOR_ACKNOWLEDGES_PRIVATE_READ_WITH_CREDENTIAL_PRESENCE_ONLY_AND_NO_RAW_EXPOSURE`
- `OPERATOR_ACKNOWLEDGES_NO_POST_NO_RETRY_NO_REPOST_NO_SETTLEMENT`
- `OPERATOR_ACKNOWLEDGES_NOT_ACTUAL_POST_PERMISSION`

本Stepでは上記を要求しない（設計のみ）。

## 5) credential safe handling

- 許可する扱い: `credential_presence_safe_boolean` のみ（`true/false`）
- 追加で保存・評価する safe label: `credential_source_safe_label`
- 禁止固定値: `credential_value_exposed=false`, `credential_length_exposed=false`,
  `credential_hash_exposed=false`, `credential_fingerprint_exposed=false`,
  `credential_prefix_suffix_exposed=false`, `env_value_exposed=false`
- API key / API secret / signature / header 値は保存・表示しない。

## 6) runtime read safe output design（公開するsafe label）

- `runtime_position_safe_status`
  - `NO_POSITION`
  - `ONE_POSITION_OPEN`
  - `MULTIPLE_POSITIONS_OPEN`
  - `UNKNOWN`
  - `READ_FAILED_SAFE`
- `position_count_safe`
  - `COUNT_ZERO`
  - `COUNT_ONE`
  - `COUNT_MULTIPLE`
  - `COUNT_UNKNOWN`
- `active_pending_order_safe_status`
  - `NO_ACTIVE_PENDING_ORDERS`
  - `ACTIVE_OR_PENDING_ORDERS_PRESENT`
  - `UNKNOWN`
- `active_pending_order_count_safe`
  - `COUNT_ZERO`
  - `COUNT_NONZERO`
  - `COUNT_UNKNOWN`
- `runtime_read_result_category`
  - `READ_CONFIRMED_SAFE`
  - `READ_FAILED_SAFE`
  - `READ_TIMEOUT_SAFE`
  - `READ_UNKNOWN_SAFE`
  - `READ_REJECTED_SAFE`

raw response/ID/価格/PnL/取引数量/アカウント系IDは保存・表示しない。

## 7) stopping conditions（fail-closed）

以下のいずれかならnext-step readinessは成立しない。

- repository条件不備
- operator current-turn confirmation不備
- credential safe boolean不成立／credential source欠落
- runtime read failed / timeout / unknown / rejected
- `NO_POSITION` かつ `count 0` の安全確認が取得できない
- active/pending が clear でない、または `COUNT_NONZERO`
- multiple position / non-zero count
- anomaly evidence が synthetic-onlyのみ
- generic close 検出
- retry / repost / second post 要求
- settlement POST in entry step 要求

`raw_response_exposed` / `raw_ids_exposed` / `raw_price_or_size_values_exposed` が起きる場合は即ブロック。

## 8) service design（追加分）

新規追加:

- `backend/app/services/gmo_live_runtime_safe_confirmation_gate.py`
  - fail-closed model/result
  - `__bool__` 常に `False`
  - `actual/entry/settlement POST` 固定 `false`
  - `runtime_private_GET_executed` 固定 `false`
  - `future_operator_confirmation_required=true` を出力
  - `future_private_read_step_required=true` を出力
  - `anomaly_evidence_non_synthetic` 条件を入力として持つ

テスト追加:

- `backend/app/tests/test_gmo_live_runtime_safe_confirmation_gate_no_post.py`
  - default fail-closed
  - repository/operator/credential/runtime/anomaly/raw block
  - retry/repost/second/settlement/generic close block
  - no network string scan

## 9) next-step criteria（for anomaly）

`KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED` へ進むのは次Stepの実runtime確認で、
以下を満たした時点のみ：

- read-only runtime結果が safe label/count で取得済み
- credential presence は safe boolean のみ
- raw/ID/value/credential実露出なし
- no POST / no retry / no repost / no second
- active/pending clear と NO_POSITION 0件確認
- anomaly failure modes が live read + settlement + kill-switch 側で保全
- 実POST許可は別 step/別条件の current-turn confirmation を通過

