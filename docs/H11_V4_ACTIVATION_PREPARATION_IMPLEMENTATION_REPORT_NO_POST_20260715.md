# H-11 v4 Activation Preparation Implementation Report（no-POST）

Date: 2026-07-15

Status: `IMPLEMENTED_FAKE_ONLY_ACTIVATION_BLOCKED`

## 1. Scope and decision

operatorが承認した次をv4専用のdisabled preparation contractへ固定した。

```text
formal_horizon=30m
strategy_version=SHORT_V1
signal_config_hash=sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d
risk=5000_per_trade/10000_daily/50000_monthly/5_losses/1_entry_daily
heartbeat_interval_seconds=15
maximum_heartbeat_age_seconds=60
account_ownership=EXCLUSIVE_DURING_AUTO
first_host=CURRENT_MAC_SUPERVISED_FAKE_REHEARSAL
clock_skew_limit_seconds=5
primary_notification=PUSHOVER
secondary_notification=EMAIL
actual_activation_allowed=false
approved_operator_selection_digest=sha256:249be96c69cf71747f4ebdae0191cc298cd92f3a682838685df27e1ae43e6f96
```

同一口座を手動とautoで同時利用しない。auto有効中のmanual trade、別Private API client、unowned position、
unowned active orderはHALT条件である。同時運用が必要になった場合は別口座または別brokerへ再設計する。

## 2. Implemented code

```text
backend/app/h11_auto/v4_activation_preparation.py
backend/app/h11_auto/v4_host_rehearsal.py
backend/app/services/h11_v4_notification_binding_no_post.py
backend/app/services/h11_v4_gmo_actual_transport.py
backend/scripts/h11_auto_v4_host_rehearsal.py
backend/app/tests/h11_auto/test_v4_activation_preparation_no_post.py
backend/app/tests/h11_auto/test_v4_notification_binding_fake_only.py
backend/app/tests/h11_auto/test_v4_host_rehearsal_no_post.py
backend/app/tests/h11_auto/test_v4_gmo_actual_adapter_fake_only.py
```

Implemented:

- 承認値のimmutable dataclassとcanonical SHA-256 digest。
- account exclusivityのsanitized fail-closed gate。
- Private GET最短0.25秒（最大4回/秒）、Private POST最短1.10秒のaccount-wide cadence gate。
- actual-shaped transportのsigning/credential/networkより前にcadence gateを配置。超過時はsleep、queue、retryせず拒否。
- reconciliation 3 GETのoffsetを0.00/0.25/0.50秒へ固定。
- clock sync unknown、skew unknown/5秒超、wall clock backward、monotonic停止をHALTするpure monitor。
- Pushover primary + email secondaryのsafe-label-only interface。
- critical Pushover eventのemergency receipt/ack契約。application sendは各route最大1回。
- refusing default transportとfake transport。HTTP、SMTP、Keychain、credential、envを不使用。
- disabled launchd plist renderer。`Disabled=true` / `RunAtLoad=false` / `KeepAlive=false`固定。
- 0.1〜60秒で必ず終了するcurrent-Mac fake-only host rehearsal CLI。

## 3. Deliberately not implemented or activated

```text
actual broker GET=false
actual broker POST=false
actual Keychain read=false
actual Pushover send=false
actual email send=false
launchd install=false
launchctl invocation=false
resident process=false
cron=false
activation permit=false
allow bridge=false
```

signal config hashは既存ignored local artifactを`ShortModelArtifact.load`で整合検証し、再学習せず固定した。
actual destination/credential、actual account OCO representation、actual host fault proofは推測せずpendingに残した。

## 4. Verification

```text
new_focused_tests=11 passed
v4_actual_adapter_plus_preparation_tests=26 passed
h11_auto_tests=323 passed
h11_auto_plus_real_post_isolation_tests=342 passed
backend_except_prohibited_v3_keychain_write_tests=7911 passed
unfiltered_backend_note=7915 passed_plus_2_OS_denied_v3_test_keychain_write_errors
ruff=passed
git_diff_check=passed
danger_scan=passed_only_permit_constructor_reference_is_negative_test_expect_raise
finite_15_second_host_rehearsal=PASSED_FAKE_ONLY_NOT_ACTIVATED
host_rehearsal_started_at_utc=2026-07-15T14:20:21.268638+00:00
host_rehearsal_finished_at_utc=2026-07-15T14:20:36.276214+00:00
host_rehearsal_elapsed_seconds=15.006820580922067
host_rehearsal_fake_pipeline_seconds=0.0000894197728484869
actual_network_call=0
actual_keychain_read=0
actual_post_count=0
```

## 5. Remaining activation blockers

1. remaining PENDING fieldsを含まない完全generation manifest作成。
2. v4専用minimum-permission Keychain credentialの別Step provisioning/read proof。
3. actual Pushover delivery/receipt/ackとemail secondary delivery proof。
4. actual read-only GET rehearsalによるOCO activeOrders rowsのsanitized証拠。
5. actual runtime schedulerへの0.00/0.25/0.50 GET cadenceと1.10秒POST cadence結線。
6. sleep/reboot/network/DNS/clock/disk/Keychain lock/duplicate supervisorのhost fault rehearsal。
7. operator KILL access実証。
8. 完全差分の独立安全レビュー。
9. major-incident resume宣言のoperator承認・発効。
10. 別Stepのactual activation reviewとactivation permit判断。

## 6. Safety state

```text
actual_post=false
broker_read=false
broker_write=false
credential_read=false
external_notification_send=false
resident_process_added=false
launchd_installed=false
cron=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
commit_performed=false
push_performed=false
```
