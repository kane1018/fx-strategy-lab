# H-11 Auto Phase B Operator Runbook（fake-only / no-POST）

Date: 2026-07-15

Status: `ACTIVE_FOR_PHASE_B_FAKE_ONLY`

## 1. Scope

このrunbookはH-11 auto Phase Bのlocal fake/paper検証だけを扱う。

```text
actual_post=false
broker_read=false
broker_write=false
credential_read=false
public_data_fetch_added=false
resident_service=false
cron=false
live_ready=false
unattended_live_supported=false
```

actual transport、broker reconciliation、credential、notification送信、live activationには使用しない。

## 2. Pre-run checks

```bash
cd "/Users/naoikansui/Desktop/トレード/backend"

python3 -m pytest -q app/tests/h11_auto
python3 -m ruff check app/h11_auto app/tests/h11_auto \
  scripts/h11_auto_phase_a_soak.py \
  scripts/h11_auto_phase_b_paper_run.py \
  scripts/h11_auto_runtime_status.py \
  scripts/h11_auto_safe_report.py \
  scripts/h11_auto_status.py \
  scripts/h11_auto_wall_clock_soak.py \
  scripts/h11_auto_wall_clock_soak_status.py \
  scripts/h11_auto_generation_manifest.py \
  scripts/h11_auto_profile_acceptance.py \
  scripts/h11_auto_profile_freeze.py \
  scripts/h11_auto_artifact_bundle_verify.py
```

次を確認する。

- auto専用の新しいstate directoryを使用する。
- generation labelを再利用しない。
- strategy / config / horizon / risk / dead-manのoperator-frozen値を入力する。
- manual UIのSQLite、Keychain service、port、processを指定しない。
- signal JSONLはregular non-symlink fileであり、sanitized formal schemaだけを含む。

## 3. One bounded paper run

```bash
python3 -m scripts.h11_auto_phase_b_paper_run \
  --signals /absolute/path/to/sanitized_signals.jsonl \
  --state-dir market_data/h11_auto_phase_b/<new_generation_directory> \
  --strategy-version '<operator-frozen strategy>' \
  --signal-config-hash '<operator-frozen exact hash>' \
  --horizon '<10m-or-30m>' \
  --generation-label '<new immutable generation label>' \
  --risk-policy-label '<operator-approved label>' \
  --per-trade-loss-bound-jpy '<operator-approved integer>' \
  --daily-loss-limit-jpy '<operator-approved integer>' \
  --monthly-loss-limit-jpy '<operator-approved integer>' \
  --maximum-consecutive-losses '<operator-approved integer>' \
  --dead-man-policy-label '<operator-approved label>' \
  --dead-man-maximum-age-seconds '<operator-approved integer>'
```

`synthetic-auto-flat`はテスト専用であり、通常runでは付けない。protected position作成後に停止するのが
正常である。

## 4. One-shot status

```bash
python3 -m scripts.h11_auto_status \
  --state market_data/h11_auto_phase_b/<generation>/auto_state.sqlite3
```

safe statusで確認する項目:

```text
generation_label
strategy_version
selected_horizon
risk_policy_label
dead_man_policy_label
state
active_cycles
entry_attempts
exit_attempts
halt_latched
journal_valid
actual_post_allowed=false
broker_read_allowed=false
broker_write_allowed=false
credential_read_allowed=false
```

## 5. Risk / dead-man status

```bash
python3 -m scripts.h11_auto_runtime_status \
  --state-dir market_data/h11_auto_phase_b/<generation> \
  --cycle-day-jst YYYY-MM-DD \
  --risk-policy-label '<same label>' \
  --per-trade-loss-bound-jpy '<same integer>' \
  --daily-loss-limit-jpy '<same integer>' \
  --monthly-loss-limit-jpy '<same integer>' \
  --maximum-consecutive-losses '<same integer>' \
  --dead-man-policy-label '<same label>' \
  --dead-man-maximum-age-seconds '<same integer>'
```

bounded process終了後にdead-manがstaleになることは正常なfail-closed結果である。staleを自動復帰させたり、
古いheartbeatを更新してactiveに見せたりしない。

## 6. Daily / weekly safe aggregate

日次:

```bash
python3 -m scripts.h11_auto_safe_report \
  --state market_data/h11_auto_phase_b/<generation>/auto_state.sqlite3 \
  --since-jst YYYY-MM-DD \
  --until-jst YYYY-MM-DD \
  --format markdown
```

週次はMondayからSundayまでを同じ引数で指定する。出力をdocsへ転記する場合も、ID、price、quantity、raw、
credential、actual broker値を追加しない。自動schedule、cron、launchdは設定しない。

## 7. 24h soak monitoring

現在のrun:

```bash
python3 -m scripts.h11_auto_wall_clock_soak_status \
  --checkpoint market_data/h11_auto_phase_b/soak_20260715T162050JST_independent_terminal.json \
  --maximum-heartbeat-age-seconds 180
```

直前の`soak_20260715T152821JST_final_code_bound.json`はprocess消失・heartbeat staleのため不採用。
checkpointをresumeせず、新しい独立Terminalの有限`caffeinate` runを最初から開始した。Terminal windowとMacを
終了しない。これはlaunchd / cron / resident serviceではなく、24時間で自己終了する検証processである。

clear条件:

```text
status=PASSED_FAKE_ONLY
target_duration_seconds=86400
observed_elapsed_seconds>=86400
heartbeat_fresh=true at final inspection where applicable
checkpoint_schema_version=H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND
implementation_matches_current_code=true
actual_post_count=0
broker_write_performed=false
network_access_performed=false
credential_read_performed=false
raw_id_value_exposure=false
```

`implementation_matches_current_code=false`、gap超過、process停止、checkpoint不正のrunは成功扱いしない。
checkpointを変更、削除、resumeせず、新しいpathと新しいgenerationで最初から実行する。

## 8. Stop and review rules

以下は新規runを開始せずoperator reviewへ送る。

- `HALTED_OPERATOR_REVIEW_REQUIRED`
- journal invalid
- persistent risk stop
- stale / corrupt / future dead-man
- duplicate process lock
- generation/policy digest mismatch
- entryまたはexit attemptが1を超える疑い
- signal schema drift、replay、expiry、config mismatch
- notifier failure
- actual POST / broker / network / credential markerがnon-zeroまたはtrue

HALT row、attempt count、checkpoint、SQLiteをreset/delete/updateしない。再開は
`H11_AUTO_OPERATOR_HALT_REVIEW_RELOAD_DRAFT_NO_POST_20260715.md`に従い、別承認後に新generationを作る。

## 9. Handoff fields

Phase Bの引き継ぎでは最低限、次だけを共有する。

```text
run_started_at_jst
generation_label
selected_horizon
safe_state_label
entry_attempt_count
exit_attempt_count
halt_latched
journal_valid
risk_stop_state
dead_man_reason
soak_checkpoint_path
soak_implementation_matches_current_code
actual_post_count
broker_write_performed
network_access_performed
credential_read_performed
```

actual ID、raw response、credential、price、quantityは共有しない。
