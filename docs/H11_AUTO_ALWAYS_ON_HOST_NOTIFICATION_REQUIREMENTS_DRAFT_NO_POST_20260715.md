# H-11 Auto Always-on Host and Notification Requirements（draft / no-POST）

Date: 2026-07-15

Status: `FAKE_ONLY_PREPARATION_IMPLEMENTED_NO_RESIDENT_PROCESS`

## 1. Purpose

完全自動売買を動かすhost、supervisor、clock、notificationの最低条件をbroker profileと独立して固定する。
本書は常駐process、launchd、cron、credential、network送信、liveを実装・有効化しない。承認済みの
current Mac有限rehearsal、disabled launchd template renderer、clock評価、fake通知二経路だけを実装した。

## 2. Host baseline

必須:

- 専用hostまたは他用途processとresource競合しないhost
- sleep / hibernation無効
- stable power。可能ならUPS
- full-disk encryption
- OS security update手順
- auto engine専用OS user
- repository、state、logsへの最小filesystem permission
- UTC/JST変換はtimezone-aware。system clock syncを監視
- disk free、SQLite write、filesystem durabilityを監視
- operatorが物理またはremoteでKILLできる

MacBookの画面が開いていること、operatorが目視していること、ブラウザUIが表示されていることを成立条件に
しない。

## 3. Process separation

```text
manual_ui_process != auto_process
manual_port != auto_status_surface
manual_state != auto_state
manual_keychain_service != auto_keychain_service
manual_broker_session != auto_broker_session
```

auto processは1instanceだけ。process lockが取れない場合、既存processをkillして奪わず開始を拒否する。

## 4. Supervisor contract

supervisorの仕事はprocessを起動することだけであり、trade stateを修復・resetしない。

Allowed future behavior:

- OS bootまたはoperator指定時に1processを起動
- unexpected exitを記録
- bounded backoff後にprocessを再起動し、必ずBOOT_RECONCILINGへ入れる
- process lock競合時は追加起動を停止

Forbidden:

- HALT row削除
- attempt count reset
- old checkpoint resume
- unknown entry / exitの再送
- config、generation、risk値の自動変更
- `actual_post_allowed`生成
- loss後の自動再開

現在の実装は`Disabled=true`、`RunAtLoad=false`、`KeepAlive=false`のlaunchd plistをmemory上へ生成するだけで、
`~/Library/LaunchAgents`へ書かず、`launchctl`も呼ばない。actual supervisorは未導入である。

process再起動とtrading再開は同じ意味ではない。再起動後にreconciliationがclearしなければ
`HALTED_OPERATOR_REVIEW_REQUIRED`を維持する。

## 5. Clock contract

future runtimeで監視するsafe values:

```text
clock_source_status
clock_skew_bucket
last_monotonic_progress_age
last_market_timestamp_age
last_formal_signal_age
```

wall clock backward、future heartbeat、formal signal timestamp future、market timestamp stale、clock sync不明は新規entryを
停止する。OS時刻の急な補正を、そのままsignal validity延長に使わない。

activation preparation contractでは、clock sync knownを要求し、absolute skew上限を5秒に固定した。wall clock backward、
monotonic clock停止、skew unknown/超過はHALTする。これは注入clockによるfake検証であり、OS/NTP実測証拠ではない。

## 6. Notification contract

通知対象:

- runtime heartbeat loss
- process restart
- boot reconciliation result
- entry confirmed
- protection confirmed / missing / size mismatch
- exit confirmed
- result unknown
- risk stop / KILL
- journal invalid
- external/manual position conflict

最低2経路を推奨する。

```text
primary=PUSHOVER
secondary=EMAIL
```

新規entry前にはprimary delivery path readyを要求する。通知失敗時にentryを続け、後からoperatorが気付く設計は
採用しない。ただしserver-side protection済みpositionを、通知失敗だけで無保護なgeneric closeへ変換しない。

Pushover primaryはcritical eventをemergency priority、receipt/ack必須、provider retry=60秒、expire=3600秒として
組み立てる。application側のsendは各route最大1回であり、broker actionのretry/repostとは独立しても再送loopを
持たない。email secondaryとともにrefusing default + fake transportだけを実装済みで、実token、宛先、SMTP、HTTPは
未接続である。

## 7. Credential availability after reboot

sealed credentialが「保存されている」だけではunattended成立を証明しない。次を別gateで確認する。

- auto専用credential item
- minimum API permission
- OS userとprocess identityのaccess control
- reboot / login / Keychain lock後のavailability
- secret値、length、hash、fingerprintをlogへ出さない
- supervisorがcredential failure時にloopしない
- credential unavailableはPOSTせずHALT

現在はcredential presence checkも実行せず、loader bindingもしない。

## 8. Host-level acceptance tests

actual activation前に専用hostで行う。

1. process SIGKILL
2. OS reboot
3. sleep attempt
4. network disconnect / reconnect
5. DNS failure
6. clock skew forward / backward
7. disk fullまたはSQLite write failure
8. notification primary failure
9. primary + secondary failure
10. Keychain locked / credential unavailable
11. duplicate supervisor launch
12. active protected position中のprocess restart
13. unknown entry / exit中のrestart

各scenarioで確認する。

```text
duplicate_attempt=false
retry=false
repost=false
unprotected_position_created=false
halt_persists=true_when_required
supervisor_does_not_reset_state=true
raw_or_secret_exposure=false
```

## 9. Deployment stages

```text
HOST_SPEC_DRAFT
-> HOST_SELECTED
-> FAKE_ONLY_SUPERVISED_REHEARSAL
-> READ_ONLY_RECONCILIATION_REHEARSAL
-> DISABLED_ACTUAL_ADAPTER_REHEARSAL
-> SEPARATE_ACTUAL_ACTIVATION_REVIEW
```

現在位置は`FAKE_ONLY_SUPERVISED_REHEARSAL_IMPLEMENTED`。current Macで有限CLIを実行できるが、host選定完了、
resident process、launchd install、actual notification、actual clock sync proofを意味しない。

2026-07-15T14:20:21Z開始の15秒rehearsalは15.0068秒で完走し、fake pipeline 0.00009秒、clock assessment
59回、Pushover/email fake二経路ready、actual network/credential/broker/POST/resident/launchd/cronは全て0または
falseだった。これはhost-local fake proofであり、actual broker通信の15秒証拠ではない。

## 10. Current safety state

```text
resident_process_added=false
launchd_added=false
cron=false
external_notification_send=false
pushover_actual_delivery=false
email_actual_delivery=false
credential_read=false
broker_read=false
broker_write=false
actual_post=false
live_ready=false
unattended_live_supported=false
```
