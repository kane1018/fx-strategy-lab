# H-11 Auto Disabled Adapter Interface Draft（docs-only / no-POST）

Date: 2026-07-15

Status: `SUPERSEDED_BY_GMO_V4_ACTUAL_ADAPTER_IMPLEMENTATION_NOT_ACTIVATED`

## 1. Purpose

GMO回答後にexecution profileを選定した際、strategyやpersistent safety coreをbroker payloadへ直接結合せず、
default-refusingのtyped adapter境界へ接続するためのprofile非依存契約を先に固定する。

```text
adapter_code_implemented=true_for_gmo_v4
actual_transport_present=true_but_activation_permit_unavailable
credential_loader_implemented=true_not_invoked
broker_read=false
broker_write=false
actual_post=false
```

## 2. Layering

```text
Formal Signal
-> Frozen Policy / Risk Gate
-> Persistent Intent
-> Profile-independent Execution Port
-> Default Refusing Adapter
-> [future profile-specific disabled adapter]
-> [future actual transport, separate authorization]
```

strategy layerはendpoint、HTTP method、signature、broker IDを知らない。profile-specific adapterは予測確率や
risk値を変更しない。

## 3. Entry request contract

```yaml
ProtectedEntryIntent:
  local_intent_ref: opaque_local_reference
  generation_label: safe_registered_label
  strategy_version: safe_registered_label
  signal_config_hash: exact_frozen_value
  signal_fingerprint: opaque_local_digest
  symbol: operator_frozen_symbol
  direction: BUY | SELL
  quantity_units: operator_frozen_integer
  entry_style: selected_profile_enum
  signal_valid_until_utc: timezone_aware_utc
  stop_loss_contract: profile_specific_frozen_value
  take_profit_contract: profile_specific_frozen_value
  maximum_entry_attempts: 1
```

Requestを作れるのはintent persist後だけ。adapterはdirection、quantity、SL/TPを推測・補正しない。

## 4. Entry result contract

```text
ACCEPTED_AND_PROTECTED
REJECTED_CONFIRMED
RESULT_UNKNOWN
TIMEOUT_UNKNOWN
PARTIAL_FILL_PROTECTION_MISMATCH
PROTECTION_MISSING
PROTECTION_EXCESS_SIZE
PROFILE_CONTRACT_VIOLATION
```

上位層へ返すのはstatus、safe reason code、sanitized counts/booleansだけ。order ID、execution ID、position ID、
raw response、header、signature、credentialを返さない。

`RESULT_UNKNOWN / TIMEOUT_UNKNOWN / mismatch / missing / excess`はretryせずHALTする。

## 5. Reconciliation contract

```yaml
ReconciliationSnapshot:
  observed_at_utc: timezone_aware_utc
  account_scope_matches: bool
  position_count: non_negative_integer
  active_order_count: non_negative_integer
  owned_position_match: bool
  expected_direction_match: bool
  expected_size_match: bool
  server_protection_present: bool
  server_protection_size_match: bool
  pending_entry_present: bool
  entry_result_known: bool
  exit_result_known: bool
  source_fresh: bool
```

このsnapshotはsafe projectionであり、実IDやraw responseを含めない。profile adapter内部で実IDを必要とする場合も
UI、journal、reportへ露出させず、sealed runtime scopeで扱う設計レビューが別途必要。

## 6. Exit request contract

```yaml
PositionSpecificExitIntent:
  local_intent_ref: opaque_local_reference
  local_position_ownership_ref: opaque_local_reference
  exit_reason: HARD_STOP | TAKE_PROFIT | TIME_EXIT | FORMAL_EDGE_LOST | RISK_STOP
  settlement_style: official_position_specific_route
  maximum_exit_attempts: 1
```

禁止:

- opposite entryを決済として送る
- generic close
- quantityをcurrent signalから再計算する
- unknown後のsecond attempt
- partial closeを暗黙にfull close扱いする

## 7. Exit result contract

```text
ACCEPTED_AND_FLAT_CONFIRMED
ACCEPTED_PENDING_RECONCILIATION
REJECTED_CONFIRMED
RESULT_UNKNOWN
TIMEOUT_UNKNOWN
PARTIAL_SETTLEMENT
POSITION_OWNERSHIP_MISMATCH
PROFILE_CONTRACT_VIOLATION
```

flatはfresh reconciliationでposition count、ownership、active order/protection状態が一致した場合だけ確定する。

## 8. Credential handle

future interfaceはsecret文字列ではなくopaque handleを受ける。

```text
CredentialHandle:
  provider_label
  permission_profile_label
  presence=true_or_false
```

値、length、hash、fingerprint、先頭末尾をrepr、exception、log、reportへ出さない。credential unavailableは
adapter call前にHALTし、fallback env / `.env`を読まない。

## 9. Default-refusing requirements

profile-specific adapterを登録していないruntimeは必ず次を返す。

```text
entry=PROFILE_NOT_BOUND_REFUSED
exit=PROFILE_NOT_BOUND_REFUSED
reconciliation=SOURCE_NOT_BOUND
actual_post_allowed=false
```

複数booleanをANDしてhard guardを解除するgeneric allow bridgeを作らない。

## 10. Fake-only implementation acceptance tests

別授権後にdisabled adapterを実装する場合、fake clientだけで次を証明する。

- request mapping exact match
- extra / missing field拒否
- direction / quantity / SL / TPをadapterが変更しない
- intent persist前send拒否
- maximum entry / exit attemptが各1
- timeout / unknown後send countが増えない
- partial fillとprotection mismatchを別statusへ分類
- excess protectionをaccepted扱いしない
- actual ID/raw/credentialがexception、repr、journalへ出ない
- default runtimeはrefusing
- real POST import isolation
- actual POST count 0

## 11. Profile-specific fields deferred

GMO回答まで値を確定しない。

```text
endpoint
executionType
time_in_force
pending_expiry
full_fill_or_none
atomic_protection_method
partial_fill_remediation
settlement_endpoint
read_after_unknown_fields
rate_limit
permission profile
fee model
```

曖昧なfieldを一般的なbroker慣行から推測しない。

## 12. Authorization boundary

本書のGMO v4 profile-specific部分は、後続のoperator授権によりコード化済みである。次は引き続き
許可しない。

- actual broker GET/POST execution
- real credential read/provisioning
- runtime binding
- activation permit issuance
- actual activation

実装の正は`h11_v4_gmo_actual_adapter.py`、`h11_v4_gmo_actual_transport.py`、
`test_v4_gmo_actual_adapter_fake_only.py`とし、本書は履歴上のprofile非依存設計として保持する。
