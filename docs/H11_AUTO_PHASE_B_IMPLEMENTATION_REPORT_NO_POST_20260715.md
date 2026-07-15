# H-11 Auto Parallel Phase B Implementation Report（fake-only / no-POST）

Date: 2026-07-15

Status: `IMPLEMENTED_AND_24H_SOAK_RUNNING_FAKE_ONLY`

## 1. Implemented

### Bounded paper runner

- local sanitized formal signal JSONLだけを読む
- maximum record count / maximum wall secondsを強制
- strategy version / config hash / selected horizonを完全一致
- generation / strategy / config / horizon / risk / dead-manをSQLite metadataへ初回digest固定
- canonical generation manifestとdigestをread時にも再検証し、metadata tamperを拒否
- 同じstate directoryを別policyで再利用する操作をfail-closedで拒否
- auto専用SQLiteとprocess lockを使用
- state pathとlock pathの同一指定およびsymlinkを拒否
- fake protected entry / fake position-specific exitだけ
- protected position作成後は、明示的synthetic auto-flatなしでは停止
- network、broker、credential、POSTなし

### Process crash / restart

- 別Python processでintentとentry attemptをcommit
- process自身をSIGKILL
- OSがprocess lockを解放することを確認
- restart後も`PROTECTED_ENTRY_PENDING / attempt_count=1`を保持
- recovery actionは`OBSERVE_PENDING_NO_RESEND`
- entry / exit resendはfalse

### Safe aggregate / status

- SQLiteを`mode=ro`で開く
- schema versionを完全一致で確認
- journal hash chainを全期間で検証
- 日付指定時のcycle / journal件数を同じcycle集合で集計
- intent ID、signal fingerprint、価格、数量、raw値を出力しない
- generation / strategy / horizon / risk / dead-manは登録済みsafe labelだけを出力
- statusはone-shot CLI。HTTP server、port、resident processを追加しない

### Wall-clock fake soak

- 最大86400秒の有限run
- 100-cycle fault batchを固定間隔で反復
- checkpoint heartbeatをatomic replaceで更新
- checkpointとlockの同一pathを拒否
- 既存checkpointは上書き・resumeしない
- observation gap超過を成功時間へ算入せずfail
- checkpoint inspectorはPOST/non-fake markerをfail-closedで拒否
- auto package全Python sourceのSHA-256を開始時に固定
- checkpointのsource digestが現在のコードと違う場合、status commandをnon-clearにする

### Persistent risk / dead-man foundation

- v3 moduleをimportせず、新auto専用契約として実装
- policy digest不一致を拒否
- per-trade / daily / monthly / consecutive-loss stop
- maximum entries/dayは1から変更不可
- monthly / consecutive / KILLは自動resumeなし
- terminal stopを後続resultで上書きしない
- dead-man missing / corrupt / stale / future / time reversalをHALT判定
- heartbeat fileのpolicy上書きを拒否
- bounded paper runnerへpersistent risk / dead-manを必須注入
- entry attemptより先にpersistent risk attemptを保存し、crash後の過少計上を防止
- fake notification heartbeatを各signal cycle前に要求し、失敗時はentry attempt前にHALT
- actual notification destination、network送信、credentialは未実装

H-11 v2 Stage 1でoperator承認済みの損失上限値は既存証拠として確認した。ただし、本auto trackは
10分/30分の別signal contractであるため、自動継承やactive defaultにはしていない。CLIで明示した
policy labelと数値をdigest固定し、異なる値で既存stateを開くと拒否する。

## 2. Commands

```bash
cd backend

python3 -m scripts.h11_auto_phase_b_paper_run \
  --signals /absolute/path/to/sanitized_signals.jsonl \
  --state-dir market_data/h11_auto_phase_b \
  --strategy-version SHORT_V1 \
  --signal-config-hash '<operator-frozen hash>' \
  --horizon 10m \
  --generation-label '<new immutable generation label>' \
  --risk-policy-label '<operator-approved auto policy label>' \
  --per-trade-loss-bound-jpy '<operator-approved integer>' \
  --daily-loss-limit-jpy '<operator-approved integer>' \
  --monthly-loss-limit-jpy '<operator-approved integer>' \
  --maximum-consecutive-losses '<operator-approved integer>' \
  --dead-man-policy-label '<operator-approved dead-man label>' \
  --dead-man-maximum-age-seconds '<operator-approved integer>'

python3 -m scripts.h11_auto_safe_report \
  --state market_data/h11_auto_phase_b/auto_state.sqlite3

python3 -m scripts.h11_auto_status \
  --state market_data/h11_auto_phase_b/auto_state.sqlite3

# operator起動の日次または週次safe aggregate（自動scheduleなし）
python3 -m scripts.h11_auto_safe_report \
  --state market_data/h11_auto_phase_b/auto_state.sqlite3 \
  --since-jst YYYY-MM-DD \
  --until-jst YYYY-MM-DD \
  --format markdown
```

## 3. 24h soak runtime

```text
previous_runs=STOPPED_OR_SUPERSEDED_BY_CODE_CHANGE
interrupted_run=soak_20260715T152821JST_final_code_bound
interrupted_run_reason=PROCESS_MISSING_HEARTBEAT_STALE_NOT_CLEAR
started_at_jst=2026-07-15T16:21:33+09:00
expected_completion_jst=2026-07-16T16:21:33+09:00
duration_seconds=86400
batch_interval_seconds=60
maximum_gap_seconds=180
checkpoint_schema=H11_AUTO_PHASE_B_SOAK_V2_CODE_BOUND
implementation_digest=4ac717f0e2a7d329f529c9f27de814f64f32ae56562cda2e32d20557c0508846
checkpoint=backend/market_data/h11_auto_phase_b/soak_20260715T162050JST_independent_terminal.json
lock=backend/market_data/h11_auto_phase_b/soak_20260715T162050JST_independent_terminal.lock
log=backend/market_data/h11_auto_phase_b/soak_20260715T162050JST_independent_terminal.log
launch_mode=INDEPENDENT_TERMINAL_FINITE_CAFFEINATE
cron=false
launchd=false
resident_service=false
```

Completion / heartbeat check:

```bash
cd backend
python3 -m scripts.h11_auto_wall_clock_soak_status \
  --checkpoint market_data/h11_auto_phase_b/soak_20260715T162050JST_independent_terminal.json \
  --maximum-heartbeat-age-seconds 180
```

Start confirmation:

```text
status=RUNNING_FAKE_ONLY
batch_count>=1
synthetic_cycle_count>=100
heartbeat_fresh=true
implementation_matches_current_code=true
actual_post_count=0
broker_write_performed=false
network_access_performed=false
credential_read_performed=false
```

Mac sleep、power off、process停止等でheartbeat gapが180秒を超えた場合、
`FAILED_OBSERVATION_GAP`として停止する。古いcheckpointから自動再開しない。

## 4. Verification

```text
h11_auto focused including offline tooling=249 passed
generation manifest validator focused=40 passed
GMO profile acceptance validator focused=30 passed
execution profile freeze validator focused=22 passed
frozen artifact bundle verifier focused=11 passed
wall-clock checkpoint inspector focused=8 passed (included above)
manual + auto related=281 passed
v3 selected no-POST safety regression (Keychain integration excluded)=95 passed
Ruff=passed
git diff --check=passed
danger scan=0 matches
short code-bound real-clock CLI soak=PASSED_FAKE_ONLY / 100 cycles / POST 0
short soak implementation_matches_current_code=true
bounded runner CLI smoke=COMPLETED_FAKE_ONLY / Stay 1 / heartbeat 1 / POST 0
safe report/status smoke=IDLE_FAKE_ONLY / generation labels verified / broker read-write false
generation manifest CLI=draft/frozen split / canonical SHA-256 / no runtime binding
execution profile freeze CLI=accepted evidence exact binding / canonical SHA-256 / review only
artifact bundle verifier=evidence/profile/manifest exact cross-binding / no activation
```

## 5. Safety state

```text
actual_post=false
broker_read=false
broker_write=false
network_access=false
credential_read=false
env_read=false
raw_id_value_exposure=false
resident_service=false
cron=false
live_ready=false
unattended_live_supported=false
```

## 6. Remaining broker-independent work

- 24h soak完走確認
- reviewed localhost producer contractを別授権後に実装すること
- actual notification destinationを使わないfake-only health evidenceの継続
- auto track専用risk数値とdead-man値のoperator freeze
- selected formal horizonと新run generation labelのoperator freeze

sanitized mapping契約、persistent risk/dead-man binding、fake notification heartbeat、HALT review / reload
草案は実装・文書化済み。実localhost binding、actual notification、reload commandは安全レビュー・
別授権まで未実装のまま維持する。

operator/broker残件の記入欄は
`docs/H11_AUTO_OPERATOR_DECISION_SHEET_NO_POST_20260715.md`へ分離した。
localhost bindingの独立reviewは
`docs/H11_AUTO_FORMAL_SIGNAL_LOCALHOST_BINDING_REVIEW_NO_POST_20260715.md`へ記録した。
Phase Bの日次・週次集計、停止、HALT review、24h soak確認手順は
`docs/H11_AUTO_PHASE_B_OPERATOR_RUNBOOK_NO_POST_20260715.md`へ固定した。
完全自動売買の完成条件10項目の達成状況は
`docs/H11_AUTO_COMPLETION_AUDIT_NO_POST_20260715.md`を正とする。

Actual adapter、broker read/write、credential binding、POSTはexecution profile選定と別授権まで開始しない。
