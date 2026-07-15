# H-11 Auto GMO Response Acceptance Template（docs-only / no-POST）

Date: 2026-07-15

Status: `RESPONSE_RECEIVED_RELAXED_V4_SELECTED_NO_POST`

## 1. Purpose

GMOの追加回答を受領した際、文章の印象ではなくexecution profileの必須条件ごとに判定する。
回答を転記してもactual adapter、broker access、credential、POSTは許可されない。

## 2. Source record

```yaml
response_received_at_jst: 2026-07-15_OPERATOR_PRESENTED
official_sender: GMO_COIN_SUPPORT_OPERATOR_RELAY
official_document_url_or_title: GMO_FOREIGN_EXCHANGE_FX_API_DOCUMENTATION
operator_preserved_original: UNKNOWN
account_specific_information_included: false
credential_or_real_id_included: false
```

原文に口座情報、API key、注文ID等がある場合はdocsへ貼らず、safe summaryだけを作る。

## 3. Capability matrix

値は`CONFIRMED_YES / CONFIRMED_NO / AMBIGUOUS / NOT_ANSWERED`のいずれかに限定する。

```yaml
pending_expiry:
  per_order_short_expiry: NOT_ANSWERED
  tif_ioc: NOT_ANSWERED
  tif_fok: NOT_ANSWERED
  tif_day: NOT_ANSWERED
  official_endpoint_or_field: ""

fill_atomicity:
  full_fill_or_none_supported: NOT_ANSWERED
  supported_for_usdjpy: NOT_ANSWERED
  supported_for_protected_entry: NOT_ANSWERED
  official_endpoint_or_field: ""

protection:
  server_side_stop_loss: NOT_ANSWERED
  server_side_take_profit: NOT_ANSWERED
  protection_created_atomically_with_entry: NOT_ANSWERED
  protection_size_matches_actual_fill: NOT_ANSWERED
  partial_fill_auto_adjusts_protection: NOT_ANSWERED
  official_order_type_or_endpoint: ""

excess_protection_behavior:
  excess_size_rejected: NOT_ANSWERED
  excess_size_cancelled: NOT_ANSWERED
  excess_size_can_reverse_position: NOT_ANSWERED
  behavior_with_hedging_disabled: NOT_ANSWERED
  behavior_with_hedging_enabled: NOT_ANSWERED

partial_fill_remediation:
  partial_fill_detectable: NOT_ANSWERED
  official_executed_size_field: ""
  protection_size_change_supported: NOT_ANSWERED
  protection_cancel_replace_supported: NOT_ANSWERED
  position_specific_close_supported: NOT_ANSWERED
  unknown_result_official_guidance: ""

reconciliation:
  open_positions_read: NOT_ANSWERED
  active_orders_read: NOT_ANSWERED
  latest_executions_read: NOT_ANSWERED
  pending_order_state_read: NOT_ANSWERED
  protected_order_size_read: NOT_ANSWERED
  read_after_timeout_is_authoritative: NOT_ANSWERED

permissions_and_limits:
  read_only_key_possible: NOT_ANSWERED
  order_only_minimum_permission_possible: NOT_ANSWERED
  private_get_rate_limit: NOT_ANSWERED
  private_post_rate_limit: NOT_ANSWERED
  websocket_reconnect_rule: NOT_ANSWERED
  tos_automatic_trading_allowed: NOT_ANSWERED

cost:
  api_order_fee: NOT_ANSWERED
  spread_contract: NOT_ANSWERED
  holding_cost_contract: NOT_ANSWERED
```

## 4. Existing confirmed constraints

過去のoperator提示回答から確認済みのsafe summary:

```text
ifoOrder_expiry=30 trading days fixed
per_order_short_expiry_field=not provided for ifoOrder
second_oco_size=uses originally requested size
second_oco_size_auto_adjust_to_actual_fill=false
partial_fill_detectable_via_orderExecutedSize=true
```

上記だけでは現在のIFDOCO profileをactual autoへ採用できない。特にpartial fill時の過大保護と短期signal expiryが
未解決である。

## 5. Acceptance rules

Candidate profileを`ACCEPT_FOR_DISABLED_ADAPTER_DESIGN`にできるのは、次を全て公式回答で確認した場合だけ。

```text
short_pending_expiry_or_no_pending_entry
AND full_fill_or_none_or_atomic_protection_size_match
AND server_side_loss_limit
AND position_specific_settlement
AND authoritative_read_after_unknown
AND permission_and_rate_limit_known
AND no_excess_order_can_create_opposite_position
```

1つでも`CONFIRMED_NO / AMBIGUOUS / NOT_ANSWERED`ならactual profileとしてはclearしない。

## 6. Verdict form

```yaml
candidate_profile_name: PENDING
verdict: WAITING  # ACCEPT_FOR_DISABLED_ADAPTER_DESIGN | REJECT | NEEDS_FOLLOWUP
blocking_fields: []
safe_rationale: ""
strategy_contract_change_required: false
broker_change_required: false
actual_adapter_authorized: false
actual_activation_authorized: false
actual_post_authorized: false
```

`ACCEPT_FOR_DISABLED_ADAPTER_DESIGN`はfake credential / fake HTTPによる型・mapping実装の検討資格だけを表す。
actual bindingやlive資格ではない。

## 7. Follow-up question rule

曖昧な回答へ推測を追加しない。follow-upは未回答fieldだけを対象にし、口座情報、注文情報、API key、実IDを
要求しない。回答が得られないfieldは`UNKNOWN`ではなくacceptance上のblockerとして維持する。

## 8. Safety state after review

```text
actual_post=false
broker_read=false
broker_write=false
credential_read=false
actual_adapter_present=false
live_ready=false
unattended_live_supported=false
```

## 9. Offline capability verdict CLI（implemented no-POST）

公式回答をsafe capability recordへ手動転記した後、次で機械判定する。

```bash
cd backend
python3 -m scripts.h11_auto_profile_acceptance \
  --evidence /absolute/path/to/sanitized-profile-evidence.json
```

入力schema:

```json
{
  "schema": "H11_AUTO_EXECUTION_PROFILE_EVIDENCE_V1",
  "profile_label": "CANDIDATE_PROFILE_LABEL",
  "capabilities": {
    "short_pending_expiry": "NOT_ANSWERED",
    "no_pending_entry": "NOT_ANSWERED",
    "full_fill_or_none": "NOT_ANSWERED",
    "atomic_protection_with_entry": "NOT_ANSWERED",
    "protection_size_matches_actual_fill": "NOT_ANSWERED",
    "server_side_stop_loss": "NOT_ANSWERED",
    "server_side_take_profit": "NOT_ANSWERED",
    "position_specific_settlement": "NOT_ANSWERED",
    "authoritative_read_after_unknown": "NOT_ANSWERED",
    "broker_state_readable": "NOT_ANSWERED",
    "protected_size_readable": "NOT_ANSWERED",
    "excess_size_can_reverse_position": "NOT_ANSWERED",
    "minimum_permission_known": "NOT_ANSWERED",
    "private_get_rate_limit_known": "NOT_ANSWERED",
    "private_post_rate_limit_known": "NOT_ANSWERED",
    "tos_automatic_trading_allowed": "NOT_ANSWERED",
    "fee_model_known": "NOT_ANSWERED",
    "ownership_isolation_supported": "NOT_ANSWERED"
  },
  "official_evidence_refs": []
}
```

capability値は`CONFIRMED_YES / CONFIRMED_NO / AMBIGUOUS / NOT_ANSWERED`だけを許す。入力はUTF-8 JSON、
regular non-symlink、最大128 KiB。raw support回答、口座情報、実ID、credentialは入力しない。

判定:

```text
exit 0 = ACCEPT_FOR_DISABLED_ADAPTER_DESIGN
exit 3 = NEEDS_FOLLOWUP または REJECT
exit 2 = schema / file / enum invalid
```

alternative gate:

```text
short_pending_expiry OR no_pending_entry
full_fill_or_none OR (atomic_protection_with_entry AND protection_size_matches_actual_fill)
```

direct gateではserver-side SL/TP、position-specific settlement、authoritative read-after-unknown、broker state、
protected size、permission/rate/ToS/fee、ownership isolationを全て`CONFIRMED_YES`、
`excess_size_can_reverse_position`を`CONFIRMED_NO`と要求する。official evidence refが0件ならfollow-upとする。

```text
implementation=backend/scripts/h11_auto_profile_acceptance.py
focused_tests=30 passed
network_import=false
credential_import=false
broker_read=false
broker_write=false
actual_post=false
```

`ACCEPT_FOR_DISABLED_ADAPTER_DESIGN`もactual adapter実装、credential、broker access、activation、POSTを
許可しない。outputの全permission flagはfalse固定である。

## 10. Received response safe verdict（2026-07-15）

厳格profileに対する判定:

```yaml
pending_expiry:
  per_order_short_expiry: CONFIRMED_NO
  tif_ioc: CONFIRMED_NO
  tif_fok: CONFIRMED_NO
  tif_day: CONFIRMED_NO
fill_atomicity:
  full_fill_or_none_supported: CONFIRMED_NO
  supported_for_usdjpy: CONFIRMED_NO
  supported_for_protected_entry: CONFIRMED_NO
protection:
  protection_created_atomically_with_entry: CONFIRMED_NO
  protection_size_matches_actual_fill: CONFIRMED_NO
  partial_fill_auto_adjusts_protection: CONFIRMED_NO
partial_fill_remediation:
  partial_fill_detectable: CONFIRMED_YES
  official_executed_size_field: orderExecutedSize
  protection_size_change_supported: CONFIRMED_NO
  protection_cancel_replace_supported: CONFIRMED_YES
reconciliation:
  open_positions_read: CONFIRMED_YES
  latest_executions_read: CONFIRMED_YES
identification:
  client_order_id_on_order_and_execution_records: CONFIRMED_YES_WHEN_SET
  open_positions_client_order_id: CONFIRMED_NO
  position_linkage_via_execution_record: CONFIRMED_YES
excess_protection_behavior:
  guaranteed_safe_excess_behavior: NOT_ANSWERED
  broker_guidance: UNEXPECTED_OPERATION_CANCEL_AND_REPLACE_STRONGLY_RECOMMENDED
strict_profile_verdict: REJECT
```

strict判定が`REJECT`である事実は変えない。operatorは「同等の原子的安全性を必須にしない」方針を別途
選択したため、次のrelaxed profileだけをfake-only実装対象として選定した。

```yaml
candidate_profile_name: H11_V4_GMO_MARKET_THEN_EXACT_OCO_NO_POST_V1
verdict: ACCEPT_FOR_RELAXED_FAKE_ONLY_IMPLEMENTATION
temporary_unprotected_gap_accepted: true
maximum_unprotected_seconds: 15
same_action_retry: false
same_action_repost: false
actual_adapter_authorized: false
actual_activation_authorized: false
actual_post_authorized: false
canonical_profile_doc: H11_V4_GMO_RELAXED_EXECUTION_PROFILE_NO_POST_20260715.md
```
