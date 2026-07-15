# H-11 GMO relaxed v4 Actual Adapter Implementation Report（no activation）

Date: 2026-07-15

Status: `ACTIVATION_PREPARATION_EXTENDED_FAKE_REVIEWED_ACTIVATION_BLOCKED`

## 1. Scope and verdict

operatorが承認したv4実装限定例外の範囲で、GMO FX Private API adapterを実装した。
実GMO endpoint、実Keychain item、実credential、実口座にはアクセスしていない。

```text
typed_private_get_post_adapter=implemented
order_cancel_oco_position_specific_close=implemented
latest_executions_open_positions_active_orders=implemented
sealed_keychain_loader=implemented_not_invoked
hmac_signing=implemented_fake_secret_verified
actual_reconciliation=implemented_fake_raw_envelopes
actual_http_transport_shape=implemented_request_boundary_hard_disabled
runtime_binding=false
actual_activation=false
actual_post=false
broker_read=false
broker_write=false
credential_read=false
```

## 2. Implemented files

```text
AGENTS.md
backend/app/services/h11_v4_gmo_actual_adapter.py
backend/app/services/h11_v4_gmo_actual_transport.py
backend/app/tests/h11_auto/test_v4_gmo_actual_adapter_fake_only.py
docs/H11_V4_GMO_RELAXED_EXECUTION_PROFILE_NO_POST_20260715.md
docs/H11_V4_GMO_OPERATOR_RUNBOOK_NO_POST_20260715.md
docs/H11_AUTO_COMPLETION_AUDIT_NO_POST_20260715.md
docs/H11_AUTO_OPERATOR_DECISION_SHEET_NO_POST_20260715.md
docs/H11_AUTO_DISABLED_ADAPTER_INTERFACE_DRAFT_NO_POST_20260715.md
docs/H11_V4_GMO_ACTUAL_ADAPTER_IMPLEMENTATION_REPORT_NO_POST_20260715.md
```

既存`app.h11_auto`はHTTP、credential、Private API非依存のfake-only coreとして変更していない。
actual-capableコードは`app.services`のv4専用2モジュールへ隔離した。`main_readonly.py`、v3、手動UIの
既存差分には触れていない。

## 3. Official request mapping

正とした公開仕様: [GMOコイン 外国為替FX API](https://api.coin.z.com/fxdocs/)

| v4 action/read | HTTP path | signing path | ownership/size source |
|---|---|---|---|
| MARKET entry | `POST /private/v1/order` | `/v1/order` | frozen cycle clientOrderId / requested size |
| cancel entry remainder | `POST /private/v1/cancelOrders` | `/v1/cancelOrders` | entry clientOrderId |
| exact OCO protection | `POST /private/v1/closeOrder` | `/v1/closeOrder` | reconciled positionId bundle / exact current size |
| cancel mismatched OCO | `POST /private/v1/cancelOrders` | `/v1/cancelOrders` | protection clientOrderId |
| emergency exit | `POST /private/v1/closeOrder` | `/v1/closeOrder` | reconciled positionId bundle / current size |
| executions | `GET /private/v1/latestExecutions` | `/v1/latestExecutions` | cycle clientOrderId→positionId linkage |
| positions | `GET /private/v1/openPositions` | `/v1/openPositions` | current position rows |
| orders | `GET /private/v1/activeOrders` | `/v1/activeOrders` | entry/protection clientOrderId |

request contractは余分なfield、別symbol、別executionType、別clientOrderId prefix、10,000超数量、
10件超のsettlePositionを拒否する。署名はqueryを含めず、POST bodyはcanonical JSONとし、署名した文字列と
送る文字列を同一に固定する。

## 4. Ownership and identifier handling

```text
clientOrderId=cycle_refから決定論的に生成する36桁以内のv4専用英数字
entry ownership=latestExecutions.clientOrderIdからpositionIdへ連結
openPositions ownership=上記positionIdとの完全一致を要求
partial fills=同じentryに属する最大10 positionIdを1 logical positionへ集約
protection ownership=protection専用clientOrderId
unowned open position=UNKNOWN/HALT projection
unowned active order=UNKNOWN/HALT projection
```

HTTP JSON envelopeは受信直後にredacted `V4GmoPrivateEnvelope`へ封入し、raw mappingをadapter公開resultへ返さない。positionIdはredacted in-memory bundle内だけで扱い、safe snapshot、repr、exception、SQLite、docsへ出さない。
再起動時はraw IDを永続化せず、deterministic clientOrderIdとfresh 3-GETから再構成する。

## 5. Fail-closed behavior

- activation permitは現buildでは生成不能。
- actual httpx transportはpermitなしでconstructできない。
- 低レベルにtransport instanceを作っても`request()`自体が常時拒否し、credential/networkへ到達しない。
- POST分岐のcommon hard guardは`allow=False`で残し、将来のactivation変更でも削除しない。
- fake transportだけでadapterを実行した。
- 同じ`(cycle_ref, action)`の2回目はadapterでも拒否する。
- timeout、network error、不正response envelopeは`UNKNOWN_SANITIZED`とし、再送しない。
- GET schema不一致、ownership不一致、混在active orderは`result_known=false`へ落とす。
- raw response、headers、signature、credential、identifierをlog/printするコードを持たない。
- `.env`、process env、`live_verification`、`main_readonly.py`へ接続しない。

## 6. Verification

```text
actual_adapter_fake_focused=15 passed
h11_auto=323 passed
historical_related_isolation_and_builder_tests=67 passed
latest_h11_auto_plus_real_post_isolation=342 passed
historical_combined_adapter_and_related=378 passed
ruff=passed
git_diff_check=passed
actual_network_call=0
actual_keychain_read=0
actual_post_count=0
```

fake focused coverage:

- activation permit生成拒否
- official signing pathとHMAC digest
- fake Keychain reader injectionとsecret repr redaction
- MARKET entry、entry cancel、protection cancel
- partial-fill 2 positionIdの所有権集約
- exact-size OCOとposition-specific MARKET close
- BUY/SELL entry sideと反対決済sideの固定mapping
- OCO二脚を合算せず1 protection sizeとして照合
- unowned positionのUNKNOWN化
- unrelated manual execution historyをownershipに使用しない
- malformed response / timeout後のno-resend
- extra/wrong request field拒否
- logging/env/runtime binding danger scan
- actual transport constructorおよびrequestの二重常時拒否
- 別経路のread-only preparation GETでの0.25秒cadenceとno-retry固定

## 7. Remaining activation blockers

```text
operator API permission confirmation=pending
actual GET/POST rate/cadence contract=fixed_GET_0.25s_max4_per_second_POST_1.10s_transport_enforced_no_sleep
actual activeOrders OCO row/size semantics=fake_two_leg_verified_actual_account_proof_pending
dedicated v4 Keychain credential provisioning=pending
actual runtime-to-adapter binding=pending
actual notification delivery/ack=pushover_plus_email_fake_interface_ready_actual_proof_pending
always-on host/supervisor/clock monitor=disabled_template_and_fake_clock_ready_actual_host_proof_pending
15-second unprotected-window host rehearsal=finite_fake_current_mac_cli_implemented_actual_broker_proof_pending
dedicated account or exclusive-operation rule=EXCLUSIVE_DURING_AUTO_contract_implemented
independent full-diff safety review=pending
major-incident resume declaration=draft_inactive
operator actual activation approval=pending
```

これらが完了するまで、adapter実装済みを`live_ready`または`unattended_live_supported`へ読み替えない。

追加実装はcadence超過時にsleep/queue/retryせず`V4_GMO_CADENCE_BLOCKED_NO_RETRY`で拒否する。actual
reconciliationの3 GETは0.00/0.25/0.50秒offsetへ固定したが、actual runtime schedulerとの結線はactivation前の
別review対象である。Pushover/email、clock、launchdはfake/refusing/disabledのみで、credentialやnetworkを扱わない。

## 8. Safety state

```text
actual_post=false
entry_post=false
settlement_post=false
cancel_post=false
post_count=0
broker_read=false
broker_write=false
credential_read=false
raw_response_exposure=false
real_identifier_exposure=false
resident_process_added=false
cron=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
commit_performed=false
push_performed=false
```
