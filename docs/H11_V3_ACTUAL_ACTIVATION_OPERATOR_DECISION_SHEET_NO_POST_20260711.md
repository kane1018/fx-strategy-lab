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
sender_contract_and_injection_point=true
default_refusing_sender=true
fake_credential_and_fake_http_client_binding=true
actual_post_allowed_structurally_false=true
private_ws_token_and_reconnect_design=true
fake_external_notifier_binding=true
heartbeat_dead_man_entry_settlement_notification_tests=true
agents_md_v3_exception_draft=true
major_incident_resume_declaration_draft=true
synthetic_fault_soak=100_of_100_matched
wall_clock_24h_fake_soak=RUNNING_UNTIL_2026-07-12T13:45:56+09:00
backend_full_tests=7522_passed
backend_ruff=passed
actual_post=false
```

上記のsender/notification項目は設計・fake実装がclearであることだけを意味する。production
sender、actual WebSocket、外部送信、activation tokenは存在しない。

## 2. Operator / actual account専任の未決定

| 項目 | 現在値 | 推奨値・停止規則 |
|---|---|---|
| broker-native pending expiry | `FIELD_PRESENT_DURATION_UNCONFIRMED` | `CONFIRMED`必須。ifoOrder requestから期限指定不可。規則不明のままならv3 activation拒否、cancel追加はv4 |
| actual account capability profile | `UNKNOWN` | account mode、1position/netting/hedging、10,000 units eligibility、API permission、IP bindingをoperatorがactual accountで確認。raw値は記録しない |
| actual partial-fill semantics | `SPEC_ONLY_UNCONFIRMED_ON_ACCOUNT` | actual account/vendorで観測可能性を確認。partial/unknownはHALT、追加POST禁止 |
| ToS / fee / responsibility acceptance | `PENDING_OPERATOR` | actual account契約、API手数料、自動化条件、責任条項をoperatorが記名確認 |
| notification destination and owner | `PENDING_OPERATOR` | メール/Webhook等のactual宛先、所有者、障害時手順をoperatorが選定。credential値は文書化しない |
| execution host / observation window | `PENDING_OPERATOR` | host、sleep抑止、時計同期、初期目視時間帯、再起動時reconcile-firstをoperatorが固定 |
| bounded background authority | `false` | 24h fake soakを除くactual運用プロセス権限は別途明示。cron導入は別判断 |
| sealed credential provision | `PENDING_OPERATOR` | actual hostへの値非露出・ログ非保存・Git非保存の提供方式をoperatorが承認 |
| v3 major-incident resume declaration | `DRAFT_NOT_EFFECTIVE` | v3限定でoperatorが記名発効。generic allow bridgeは禁止 |
| actual activation authorization | `false` | 上記完了後も別current-turnの専用activation承認が必須 |

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
phase_A=operator_and_actual_account_decisions
phase_B=operator_signed_v3_resume_and_complete_diff_review
phase_C=fresh_sanitized_preflight
phase_D=separate_current-turn first-live activation
```

fake transport/notification実装と24h soakの完了は、上記phaseのpermissionを自動発生させない。
actual live開始時は、dirty tree、
HEAD不一致、test失敗、能力UNKNOWN、position/order不一致のいずれかで停止する。

## 5. 安全状態

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
credential_read=false
resident_process=false
cron=false
raw_id_value_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
