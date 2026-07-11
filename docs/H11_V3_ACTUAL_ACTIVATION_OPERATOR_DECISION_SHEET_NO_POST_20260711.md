# H-11 v3 Actual Activation — Operator Decision Sheet（no-POST）

Date: 2026-07-11

Status: **PENDING_OPERATOR_AND_CAPABILITY_CONFIRMATION**

Purpose: `H11_V3_ACTUAL_ACTIVATION_STEP`前の未決定事項を一箇所に固定する。

本書はactual activation、API、credential、broker read、POST、resident process、cronを許可しない。

## 1. 現在clearなもの

```text
v3_spec_frozen=true
config_hash=sha256:737765dcbed89befceef8660d2b362c834344cc7e36e139d2ff75984914c3262
capability_contract_hash=sha256:8dd4c936e6cde8b5b9ac132cf68e9a7f4eecea2224a87a0d3864cd4c95aa9d7e
pure_ifdoco_builder=true
automatic_preview_signal_adapter=true
persistent_process_lock=true
one_entry_attempt_cap=true
one_settlement_attempt_cap=true
unknown_result_halt=true
same_day_second_entry_block=true
fake_server_side_protection_reconcile=true
append_only_safe_journal=true
persistent_risk_stop=true
state_specific_boot_reconcile=true
persistent_dead_man=true
partial_fill_fail_closed_policy=true
protection_children_reconcile_policy=true
disabled_actual_boundary=true
synthetic_fault_soak=100_of_100_matched
backend_full_tests=7503_passed
backend_ruff=passed
actual_post=false
```

## 2. Operator / capability未決定

| 項目 | 現在値 | 推奨値・停止規則 |
|---|---|---|
| broker-native pending expiry | `FIELD_PRESENT_DURATION_UNCONFIRMED` | `CONFIRMED`必須。ifoOrder requestから期限指定不可。規則不明のままならv3 activation拒否、cancel追加はv4 |
| partial-fill semantics | `PARTIAL_OBSERVABILITY_SPEC_ONLY` | event fieldsは存在。partial/unknownはHALT、追加POST禁止 |
| minimum lot | `PUBLIC_SPEC_10000` | fresh public symbolsとactual accountの両方で10,000 units適合を確認 |
| price increment | `PUBLIC_SPEC_0.001` | fresh public symbolsでUSD/JPY tickSizeを照合し、不一致ならHALT |
| account mode | `UNKNOWN` | 1position制約とnetting/hedgingの整合確認 |
| API permission | `UNKNOWN` | 必要最小限。値や画面raw情報を記録しない |
| ToS automation policy | `SERVICE_SUPPORTS_API_AUTOMATION` | actual account契約、API手数料、責任条項はoperatorが確認 |
| notification route | `PRIVATE_WS_SPEC_EXISTS_NO_ACTUAL_BINDING` | orderEvents / executionEventsを候補とするがtoken API・再接続設計と外部通知先は未決定 |
| execution host | `UNKNOWN` | sleep抑止、時計同期、再起動時reconcile-first |
| observation window | `UNKNOWN` | 初期burn-inはoperatorが目視可能な固定時間帯 |
| resident-process authority | `false` | actual activation時に別途明示。cronは初期burn-in非推奨 |
| sealed credential provision | `UNKNOWN` | 値非露出・ログ非保存・Git非保存を確認 |
| actual transport binding | `false` | complete diff review後に別Stepでのみ実装 |
| major-incident resume declaration | `false` | v3限定条件を明示し、generic allow bridgeは作らない |

## 3. Activation前の必須実証

1. fresh boot reconciliationがposition/order unknownをHALTする。
2. IFDOCO acceptance後、entry legとOCO protectionの存在をsafe status/countで確認できる。
3. timeout後に追加entry、retry、repostが0件である。
4. process二重起動がlockで拒否される。
5. dead-man、kill、notification failureが新規entryを止める。
6. budget stop後に自動再開しない。
7. actual senderはIFDOCO route一つだけに固定し、generic order/close/cancel/changeへ到達しない。
8. credential、raw request/response、headers、signature、ID、price、PnLを出力しない。

## 4. 次Stepの推奨scope

```text
step=H11_V3_ACTUAL_ACTIVATION_STEP
phase_A=public_spec_completion_and_operator_decisions
phase_B=actual_transport_binding_no_send_review
phase_C=fake_transport_fault_injection_and_24h_soak
phase_D=fresh_sanitized_preflight
phase_E=separate_current-turn first-live activation
```

Phase A〜Cの完了はPhase D/Eのpermissionを自動発生させない。actual live開始時は、dirty tree、
HEAD不一致、test失敗、能力UNKNOWN、position/order不一致のいずれかで停止する。

## 5. 安全状態

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
credential_env_read=false
raw_id_value_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
