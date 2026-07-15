# H-11 v4 GMO Operator Runbook（fake-only / no-POST）

Date: 2026-07-15

Status: `FAKE_RUNTIME_PLUS_ACTIVATION_PREPARATION_IMPLEMENTED_NOT_ACTIVATED`

## 1. Boundary

このrunbookのCLIはlocal sanitized fileとfake brokerだけを使用する。GMOへのGET/POST、credential読取、
署名、実口座照会、常駐process、cronを行わない。

```text
actual_post=false
broker_read=false
broker_write=false
credential_read=false
network_access=false
resident_process=false
cron=false
```

## 2. One finite signal run

入力はformal signal snapshot 1件だけのUTF-8 JSONLとする。rolling estimate、24時間方向、replay、
non-PROSPECTIVE、追加field、2件以上を拒否する。

```bash
cd "/Users/naoikansui/Desktop/トレード/backend"
python3 -m scripts.h11_auto_v4_gmo_no_post_run \
  --mode signal \
  --signals /ABSOLUTE/PATH/formal_signal.jsonl \
  --state-dir /ABSOLUTE/PATH/v4-local-state \
  --strategy-version SHORT_V1 \
  --signal-config-hash sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d \
  --horizon 30m \
  --generation-label H11_AUTO_30M_20260715_G001 \
  --scenario FULL_FILL_PROTECTED
```

利用できるnew-cycle fake scenario:

```text
FULL_FILL_PROTECTED
PARTIAL_REMAINDER_CANCEL_THEN_PROTECT
ENTRY_RECONCILIATION_UNKNOWN_HALT
PROTECTION_MISSING_EMERGENCY_FLAT
```

このscenario指定はfake fault injectionであり、actual broker結果を選択・予測するものではない。

## 3. Restart reconciliation

active cycleが残った場合、signalを再入力せず、同じstate-dirとgenerationでresumeする。現在のCLIは
`RESUME_EXACT_PROTECTED`というfake snapshotだけを提供する。実broker snapshotには接続しない。

```bash
python3 -m scripts.h11_auto_v4_gmo_no_post_run \
  --mode resume \
  --state-dir /ABSOLUTE/PATH/v4-local-state \
  --strategy-version SHORT_V1 \
  --signal-config-hash sha256:ca08df187ae11b89192f1bbb4f77adc712ad41dc07d06d85bd67c9c7bcf6135d \
  --horizon 30m \
  --generation-label H11_AUTO_30M_20260715_G001 \
  --scenario RESUME_EXACT_PROTECTED
```

resumeはpersist済みcycleのsideを使用し、新しいentry intentやrisk entry countを作らない。

## 4. Safe report

SQLiteはread-only URIで開き、generation digest、journal hash chain、action outcome cross-linkを再検証する。

```bash
python3 -m scripts.h11_auto_v4_gmo_safe_report \
  --state /ABSOLUTE/PATH/v4-local-state/v4_state.sqlite3 \
  --format markdown
```

## 5. Operator HALT reload（fake-only）

reloadはexact phraseとfresh fake flat snapshotを同時に要求する。

```bash
python3 -m scripts.h11_auto_v4_gmo_operator_reload_no_post \
  --state /ABSOLUTE/PATH/v4-local-state/v4_state.sqlite3 \
  --lock /ABSOLUTE/PATH/v4-local-state/v4_runtime.lock \
  --confirmation H11_V4_GMO_OPERATOR_RELOAD_NO_POST \
  --synthetic-snapshot FLAT
```

`NONFLAT`は解除を拒否する。解除操作自体はentry、cancel、protection、exitを一切実行せず、自動resumeもしない。

## 6. Fault soak

```bash
python3 -m scripts.h11_auto_v4_gmo_soak --cycles 100
```

合格条件:

```text
status=PASSED_SYNTHETIC_NO_POST
matched_cycle_count=100
max_same_action_attempts_observed=1
journal_verification_failures=0
actual_post_count=0
broker_write_performed=false
credential_read_performed=false
network_access_performed=false
```

## 7. Finite current-Mac host rehearsal

Pushover/emailはfake transport、clock sync/skewも注入したsafe値だけを使う。broker、Keychain、外部networkへ
接続せず、15秒で必ず終了する。常駐化、launchd install、cron登録は行わない。

```bash
python3 -m scripts.h11_auto_v4_host_rehearsal --duration-seconds 15
```

合格表示は`PASSED_FAKE_ONLY_NOT_ACTIVATED`。これはcurrent Mac上で有限timer、clock評価、二経路fake通知が
動くことだけを示し、actual notification delivery、sleep/reboot耐性、broker通信15秒以内を証明しない。

`render_disabled_launchd_template`は`Disabled=true`、`RunAtLoad=false`、`KeepAlive=false`のreview用plistを
memory上へ生成する。ファイル配置や`launchctl`は別Stepまで禁止する。

## 8. Actual boundary

actual adapter、official endpoint mapping、HMAC signing、sealed Keychain loader、3 GET reconciliationは
fake clientで実装・検証済みである。ただし、このrunbookを完走してもactual接続は開かない。
activation permitは現在生成不能であり、実Keychain itemを読まず、Private GET/POSTを送らない。

actual runtime binding、実credential provisioning、外部通知、supervisor install、major-incident resume発効、
activationは、別の明示授権と独立レビューを必要とする。
