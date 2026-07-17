# H-11 v4 — GMO Relaxed Execution Profile（implemented / no-POST）

Date: 2026-07-15

Status: `ACTUAL_ADAPTER_IMPLEMENTED_FAKE_REVIEWED_NOT_ACTIVATED`

## 1. Decision

GMO FXが短期expiry、AON/FOK、実約定量へ原子的に追随する保護注文を提供しないことを前提に、
H-11 v3とは別versionとして次を採用する。

```text
profile=H11_V4_GMO_MARKET_THEN_EXACT_OCO_FRIDAY_LIMITED_NO_POST_V2
broker_capability_evidence_hash=sha256:33cb3ab46256b3feaaa191d7578ea8dd7e1388e4ac349363554504c13b3a54ab
v3_modified=false
entry=MARKET
entry_pending_expiry_dependency=false
partial_fill=detect_then_cancel_remainder_once
protection=actual_filled_size_exact_OCO_after_reconciliation
temporary_unprotected_gap=accepted_up_to_15_seconds
same_action_retry=false
same_action_repost=false
unknown_result=reconcile_then_halt_if_not_authoritatively_known
maximum_positions=1
maximum_entries_per_day=1
scale_in=false
hedging=false
generic_opposite_close=false
friday_entry_window_jst=09:00_inclusive_to_21:00_exclusive
friday_weekend_flat_target_jst=Saturday_04:00
friday_exit_sequence_start_jst=Saturday_03:45
normal_maximum_hold_seconds=82800
actual_post=false
```

これはv3と同等の原子的安全性を主張しない。MARKET約定からOCO確認までの間に価格急変、通信断、
process停止が起きると、最大損失をserver-sideで直ちに拘束できない時間が存在する。この残余リスクを
明示的に受容する代わりに、GMOの公式仕様で実現可能な操作へ限定する。

## 2. Official broker facts used

operatorが2026-07-15に提示したGMOサポート回答を、値・ID・口座情報を含まないsafe summaryとして採用した。

```text
per_order_expiry_or_tif=false
all_or_none_or_fok=false
atomic_actual_fill_sized_protection=false
ifdoco_second_size_auto_adjust=false
partial_fill_detection=orderExecutedSize_plus_openPositions
order_size_change=false
official_partial_fill_remediation=cancel_oversized_protection_then_reconcile_then_replace_exact_size
client_order_id_available_on_order_and_execution_records_when_set=true
open_positions_has_position_id_only=true
position_linkage=execution_records_to_position_id
```

過大保護注文の余剰分がどう処理されるかは「想定外運用」とされ、保証されなかった。したがってv4は、
過大・過小OCOを正常状態として許容しない。

## 3. Frozen execution and risk contract

```yaml
symbol: USD_JPY
position_size_units: 10000
max_positions: 1
max_entries_per_day: 1
max_unprotected_seconds: 15
per_trade_loss_bound_jpy: 5000
daily_loss_limit_jpy: 10000
monthly_loss_limit_jpy: 50000
maximum_consecutive_losses: 5
same_action_max_attempts: 1
same_action_retry: false
same_action_repost: false
scale_in: false
hedging: false
generic_opposite_close: false
temporary_unprotected_gap_accepted: true
broker_native_atomic_protection_required: false
friday_entry_start_hour_jst: 9
friday_entry_cutoff_hour_jst: 21
friday_weekend_flat_weekday_jst: Saturday
friday_weekend_flat_hour_jst: 4
friday_exit_sequence_start_hour_jst: 3
friday_exit_sequence_start_minute_jst: 45
normal_maximum_hold_seconds: 82800
```

`15秒`は実接続前のv4 no-POST契約として固定した上限である。timerは実約定確認時ではなく、より保守的に
MARKET action attemptを永続化した時刻から開始する。注入clockで16秒経過を再現したtestではOCO作成へ
進まずposition-specific emergency exitへ切り替わる。実host・実通信で15秒以内を継続的に満たせる証拠が
なければactivationしない。

## 4. Operation sequence

### Normal full fill

```text
1. persist MARKET_ENTRY intent
2. one synthetic/actual attempt
3. executions/openPositions/activeOrders reconciliation
4. actual filled sizeを確定
5. actual average fill priceとsignal時点で凍結したATRからOCO価格を計算
6. persist EXACT_SIZE_OCO_PROTECTION intent
7. filled sizeと同量のOCOをone attempt
8. position size == OCO protection sizeを再照合
9. POSITION_PROTECTED
```

### Partial fill

```text
1. orderExecutedSizeとposition集計でpartialを検知
2. persist CANCEL_ENTRY_REMAINDER intent
3. 未約定残だけをone attemptで取消
4. pending=0を再照合
5. 最終actual filled sizeだけを保護
```

取消結果が不明、または取消後もpendingが残る場合、同じ取消を再送せずHALTする。

### Protection mismatch

```text
1. OCO size不足・超過を検知
2. persist CANCEL_MISMATCHED_PROTECTION intent
3. 不一致OCOをone attemptで取消
4. protection size=0を再照合
5. persist POSITION_SPECIFIC_EMERGENCY_EXIT intent
6. position指定routeでone attempt決済
7. flatを再照合
```

OCO存在自体が不明な場合は、OCOを残したまま決済して反対建玉を作る危険があるため、追加操作せずHALTする。

### Friday-limited weekend flat

金曜は09:00 JST以上21:00 JST未満だけ新規entryを許可する。金曜entryのexit-sequence startは、通常のentryから
82,800秒後と土曜03:45 JSTの早い方を固定期限とし、土曜04:00 JSTをflat目標とする。開始期限到達後は、既存の
`CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT` → fresh reconciliation →
`POSITION_SPECIFIC_TIME_EXIT`の単発順序だけを使用する。

土曜03:45より前のweekend time exit、金曜21:00以降のentry、土曜・日曜entryは拒否する。OCO取消前と
position-specific close前には、それぞれ別の2秒以内の公式public status `OPEN` evidenceを要求する。
結果不明時のretry/repost、自動resume、generic opposite closeは引き続き禁止する。04:00時点でflatを
確認できなければpersistent HALTし、OCOを維持できる場合は維持する。broker障害やmarket CLOSED/UNKNOWN時まで
flat完了を保証する契約ではない。03:45自動dispatcherと04:00 target monitorはactivation前の凍結必須要件で、
本refreeze時点では未発効である。

## 5. Exact protection calculation

v3の予測モデルとrisk幅を維持し、pending STOP entryだけをMARKET entryへ変更する。

```text
stop distance = 1.50 * ATR(24) frozen at formal signal
take profit distance = 1.50R
price origin = reconciled actual average fill price
protection size = reconciled actual filled size
tick = 0.001
protection_contract_hash = sha256:48344aeb590a4b024879e34de5a8897a74d2d301b542b032407776c6ffa1e0d7
```

BUY建玉はSELL決済OCO、SELL建玉はBUY決済OCOに固定する。計算はpure functionであり、HTTP、credential、
署名、broker IDを扱わない。

## 6. Persistent state and crash recovery

v4は既存Phase A/v3と別SQLite schemaを使用する。

```text
schema=H11_V4_GMO_RELAXED_STATE_V1
intent_persisted_before_each_action=true
unique_attempt_key=(cycle_ref, action_kind)
hash_linked_safe_journal=true
raw_response_persisted=false
broker_id_persisted=false
credential_persisted=false
```

processがaction開始記録後に停止した場合、再起動後は同じactionを再送しない。fresh reconciliationで
結果を確定し、必要なら次の異なるactionへ進む。確定できなければoperator review HALTを永続化する。

local operational runtimeは、次も実装済みである。

```text
immutable_generation_binding=true
process_lock=true
boot_flat_reconciliation=true
active_cycle_restart_reconciliation=true
protected_position_restart_reconciliation=true
persistent_risk_policy_binding=true
persistent_dead_man_binding=true
fake_notification_heartbeat=true
operator_reload_exact_phrase=H11_V4_GMO_OPERATOR_RELOAD_NO_POST
operator_reload_requires_fresh_flat=true
operator_reload_automatic_resume=false
safe_aggregate_read_only_sqlite=true
```

HALT解除は履歴を削除・resetせず、元cycleを`OPERATOR_RELOAD_CLEARED`へ遷移させる。解除後も同じ呼出しで
entryやresumeを行わず、次のruntime実行を別操作として要求する。

## 7. Implemented files

```text
backend/app/h11_auto/v4_gmo_contracts.py
backend/app/h11_auto/v4_gmo_evidence.py
backend/app/h11_auto/v4_gmo_protection.py
backend/app/h11_auto/v4_gmo_boundary.py
backend/app/h11_auto/v4_gmo_persistence.py
backend/app/h11_auto/v4_gmo_engine.py
backend/app/h11_auto/v4_gmo_runtime.py
backend/app/h11_auto/v4_gmo_report.py
backend/app/h11_auto/v4_gmo_soak.py
backend/app/services/h11_v4_gmo_actual_adapter.py
backend/app/services/h11_v4_gmo_actual_transport.py
backend/app/tests/h11_auto/test_v4_gmo_relaxed_no_post.py
backend/app/tests/h11_auto/test_v4_gmo_runtime_no_post.py
backend/app/tests/h11_auto/test_v4_gmo_report_and_recovery_no_post.py
backend/app/tests/h11_auto/test_v4_gmo_soak_no_post.py
backend/app/tests/h11_auto/test_v4_gmo_cli_no_post.py
backend/app/tests/h11_auto/test_v4_gmo_actual_adapter_fake_only.py
backend/scripts/h11_auto_v4_gmo_no_post_run.py
backend/scripts/h11_auto_v4_gmo_safe_report.py
backend/scripts/h11_auto_v4_gmo_operator_reload_no_post.py
backend/scripts/h11_auto_v4_gmo_soak.py
```

実装済み:

- relaxed policyとconfig hash
- broker capability safe factsのcanonical JSON / SHA-256固定とpolicy binding
- pure exact-fill OCO calculation
- full fill / partial fill / cancel / protection / mismatch cancel / emergency exit状態機械
- action種類ごとの永続one-attempt制約
- restart時no-resend reconciliation
- protected positionのrestart時fresh reconciliation
- SQLite hash-linked safe journalとtamper detection
- immutable generation / risk / dead-man policy binding
- process二重起動拒否、boot flat確認、persistent HALT
- exact phrase＋fresh flatを要求するno-POST operator reload
- read-only SQLite safe aggregate
- sanitized formal signal JSONLを1件だけ受けるfinite fake-only CLI
- 14-scenario / 100-cycle GMO v4 fault soak
- refusing default boundaryとexact fake boundary
- actual POST、credential、networkを構造的にfalse固定するresult
- official pathを固定したPrivate GET/POST request mapping
- transport path（`/private/v1/...`）と署名path（`/v1/...`）の型分離
- order / cancelOrders / closeOrder OCO / position-specific MARKET close builder
- latestExecutions / openPositions / activeOrders actual reconciliation
- deterministic clientOrderIdとexecution→positionIdによるin-memory ownership linkage
- 複数partial-fill positionIdを1 logical positionとして最大10件まで集約
- raw JSON mappingを上位へ返さないredacted response envelope
- sealed Keychain loaderとHMAC signed-request factory（実credential未読）
- unconstructible activation permitによるactual httpx transportのdefault拒否

Current verification snapshot:

```text
v4_focused_tests=62 passed
h11_auto_tests=311 passed
actual_adapter_fake_tests=15 passed
adapter_plus_isolation_related_tests=378 passed
activation_preparation_new_tests=11 passed
h11_auto_current_tests=323 passed
latest_h11_auto_plus_real_post_isolation=342 passed
v4_fault_soak=100/100 passed
v4_fault_scenarios=14
max_same_action_attempts=1
slow_reconciliation_over_15_seconds_forces_emergency_exit=true
actual_post_count=0
network_access=false
credential_read=false
broker_write=false
```

2026-07-15 activation preparation追加後も、historical 378-test snapshotは当時のsuiteとして保持する。最新の
h11_auto + real POST isolationは342件で成功し、15秒current-Mac fake rehearsalも
`PASSED_FAKE_ONLY_NOT_ACTIVATED`だった。actual broker、credential、external notificationは不使用。

operator CLIは
`H11_V4_GMO_OPERATOR_RUNBOOK_NO_POST_20260715.md`を正とする。

## 8. Implemented but not activated

operatorが承認した`AGENTS.md`のv4実装限定例外により、次はコード化・fake検証まで完了した。

```text
actual HTTP transport shape=implemented_activation_permit_unavailable
HMAC signing=implemented_fake_secret_verified
sealed Keychain loading=implemented_not_invoked
Private GET mapping=implemented_fake_client_verified
Private POST mapping=implemented_fake_client_verified
actual broker reconciliation=implemented_against_fake_raw_envelopes
raw_response_retention=false
real_identifier_persistence=false
same_action_second_attempt=false
actual_post=false
broker_read=false
credential_read=false
```

次は依然として未実装または未発効である。

```text
actual activation permit issuance
actual runtime-to-adapter binding
real credential provisioning/read
real Private GET/POST execution
actual notification delivery
resident supervisor
major incident resume activation
actual live activation
```

したがって`ACTUAL_ADAPTER_IMPLEMENTED_FAKE_REVIEWED_NOT_ACTIVATED`は、actual auto完成やlive-readyを
意味しない。request mapping完成と、実口座へ接続・送信するactivationを分離して扱う。

## 9. Residual risks accepted by this profile

- MARKET約定からOCO確認までの一時的な無保護価格変動
- crash/network partition時に15秒以内の保護を保証できない可能性
- cancel/protection/exitが別操作であり、操作間に状態変化が起こる可能性
- broker read反映遅延によりauthoritative reconciliationが成立しない可能性
- 急変時のslippageでper-trade budgetを超える可能性
- OCO取消後からposition-specific emergency exitまでの無保護時間

次は受容しない。

- 同一actionのretry/repost
- OCO存在不明のままの決済
- generic opposite orderによる決済
- 複数建玉、買い増し、両建て
- 実約定量を超えるOCOを正常状態として維持
- unknown状態からの自動再開

## 10. Activation blockers

実装済みno-POST profileをactualへ接続するには、別の明示授権と少なくとも次が必要である。

1. v4専用API権限: order、cancel、OCO、position-specific close、required GETのoperator確認。
2. Private GET/POST rate limit内のpoll・reconcile cadence固定。
3. v4専用credentialの実Keychain provisioningと最小権限確認。
4. actual hostで15秒上限を満たすfault rehearsal。
5. actual notification、dead-man、supervisor、clock monitor。
6. 専用口座またはauto稼働中のmanual取引禁止。
7. actual runtime bindingを含む完全差分の独立safety review。
8. major incident resume宣言とoperatorによる別activation承認。

## 11. Safety state

```text
actual_post=false
entry_post=false
settlement_post=false
cancel_post=false
post_count=0
broker_read=false
broker_write=false
credential_read=false
network_access=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
