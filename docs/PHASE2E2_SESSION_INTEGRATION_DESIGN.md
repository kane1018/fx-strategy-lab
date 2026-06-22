# Phase 2E-2: shadow session統合前の安全接続設計

## 1. 目的

本書は、Phase 2E-1Hでhardening済みのlocal-only安全基盤を、既存shadow sessionへ段階的に接続するための設計である。

今回の範囲は設計のみであり、`run_shadow_session.py`、`app/shadow/`コード、tests、公開API、frontendは変更しない。
Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加にも進まない。

Phase 2E-2実装時の目的は次の5点である。

- 既存Public shadow runの挙動を壊さず、risk/audit境界を最小接続する。
- `KillSwitchState`をrun lifecycleで一貫して所有する。
- STOPファイル、audit log write failure、safety violationを安全停止へ接続する。
- candidate、RiskDecision、virtual result、kill switch logの相関を保つ。
- legacy summaryとの後方互換を維持する。

## 2. 現在の前提

- Phase 2E-1H再監査はB判定である。
- D-1 spread provenance、D-2 malformed input fail closed、D-3 audit schema/root containment、D-4 unsafe risk row summarizeの必須修正は解消済みである。
- `KillSwitchState`のvalue object invariantは強化済みだが、同一run内で再初期化しない保証はPhase 2E-2のorchestration設計課題である。
- `AuditLogWriteError`はlocal JSONL writerでfail closedに発生するが、現行session/CLIのexit code 2へは未接続である。
- 既存runは `events.jsonl`、`summary.json`、`metadata.json` を生成するが、candidate/risk/kill JSONLはまだ生成しない。
- `scripts.summarize_shadow_runs`はrisk JSONLがある場合だけ検証し、ないlegacy runは壊さない。
- 実注文、Private API、APIキー、broker、OrderRequest、本番公開API、frontendへは未接続である。

## 3. 既存session lifecycle

現行の流れは次の通りである。

1. `scripts/run_shadow_session.py`でCLI argsをparseする。
2. `--source mock`ならdeterministic candlesを生成する。
3. `--source gmo-public`ならGMO Public read-only adapterでcandlesを取得する。
4. `app.shadow.session.run_shadow_session()`へcandlesとrun parametersを渡す。
5. `run_shadow_session()`がrun_idを決め、`ShadowTrader`を作成する。
6. 各stepでcandleからsynthetic zero spreadのTickerを作る。
7. `ShadowTrader.step()`がsignal、virtual order、position、PnL、safety、haltを含むeventを返す。
8. `events.jsonl`、`summary.json`、`metadata.json`を`shadow_exports/<run_id>/`へ保存する。
9. CLIがsummaryを表示し、通常はexit code 0を返す。

Phase 2E-2実装では、この構造を大きく分解せず、CLIと`run_shadow_session()`の境界に最小限のrisk/audit orchestrationを追加する。

## 4. Phase 2E-2 run lifecycle設計

Phase 2E-2実装時の理想フローは次の通り。

1. CLI args parse
   - `steps > 0`、source、symbol、interval、out_rootを検証する。
   - Private API、APIキー、`.env`、broker設定は要求しない。

2. output root / run_id決定
   - `out_root`は既定`shadow_exports`を維持する。
   - run_idは既存形式を維持し、audit schemaのsafe run_id制約へ合わせる。
   - `shadow_exports/`がgitignore対象であることは運用確認で扱い、実行時に追跡状態を変更しない。

3. `KillSwitchState`初期化
   - run lifecycle orchestratorがrun単位で1つだけ生成して所有する。
   - stepごと、candidateごと、logごとに再生成しない。

4. STOPファイルrun pre-gate
   - 既定`backend/shadow_exports/STOP`を確認する。
   - 存在する場合はkill switchをactiveにし、candidate生成、risk allow、virtual fill、Public追加取得へ進まない。

5. Public data取得前gate
   - kill switch inactiveを確認する。
   - STOPファイルを再確認する。
   - symbol/intervalがrisk policyで許可された範囲か確認する。
   - GMO Public read-only以外へfallbackしない。

6. Public data取得
   - 成功時は必要なcandlesだけをsessionへ渡す。
   - 失敗時は無限retryしない。Phase 2E-2で連続API errorを扱う場合はrun-local `KillSwitchState.record_api_result()`で管理する。

7. 各step開始
   - step pre-gateでkill switch inactive、STOPファイル、candidate count、consecutive API errorsを確認する。
   - gateに失敗した場合は通常step処理へ進まず、kill switch logとsummaryへ停止理由を残す。

8. signal decision
   - 既存`momentum_signal`を維持し、収益性判断や戦略変更はしない。
   - BUY/SELL/HOLDをPhase 2Eの`SignalLabel`へ明示変換する。
   - signal decision logを書けない場合はfail closedで停止する。

9. candidate factory
   - HOLD/NO_TRADEではcandidateを作らない。
   - BUY/SELLのみ`OrderCandidate`を作る。
   - Phase 2E-2初期では、real Public bid/askを保証できるsourceだけ`REAL_PUBLIC_BID_ASK`にする。
   - candle close由来のsynthetic zero spreadは`SYNTHETIC_ZERO`またはcandidate生成なしとして扱い、ALLOWへ進めない。

10. risk evaluate
    - `RiskContext`をrun stateから構築する。
    - data freshness、spread provenance、cooldown、duplicate、daily count、kill switch state、安全flagsを検査する。
    - candidate 1件に対してRiskDecision 1件を必ず作る。

11. audit logs
    - candidate_log、risk_decision_log、必要に応じてkill_switch_logを書く。
    - `AuditLogWriteError`が1回でも起きたらkill switch active、current run halt、exit code 2へ倒す。

12. virtual result
    - `RiskDecision.status == ALLOW_SHADOW`かつkill switch inactiveかつaudit log成功時だけ進む。
    - virtual resultはcandidate_idとdecision_idを保持する。
    - REJECT時はvirtual resultを作らない。

13. summary / metadata
    - 既存summary keyを維持する。
    - risk/audit追加情報は後方互換を壊さない追加keyとして記録する。
    - halt、kill switch、audit failure、exit codeを明示する。

14. summarize確認
    - `scripts.summarize_shadow_runs`はrisk JSONLがあるrunだけ追加検証する。
    - safety violationがあればexit code 2を維持する。

## 5. KillSwitchState ownership設計

`KillSwitchState`はrun単位で1つだけ存在し、run lifecycle orchestratorが唯一所有する。

要件:

- `run_shadow_session()`開始時に1回だけ初期化する。
- step loop内で新しいinactive stateを作って置き換えない。
- success eventでinactiveへ戻さない。
- STOP削除後も同一runでは復帰しない。
- 復帰はSTOPを削除したうえで、新しいrun_idで手動再開する。
- active中はPublic追加取得、candidate生成、risk allow、virtual fill、audit以外の通常処理を止める。
- active中に許可する処理は、停止理由のsummary/metadata反映と可能な範囲のkill_switch_logだけに限定する。

Phase 2E-2実装時の推奨構造:

- `SessionSafetyState`のようなrun-local orchestration stateを導入する場合も、保持する`KillSwitchState`は1つだけにする。
- state更新は`kill_switch = kill_switch.activate(...)`のように明示代入し、関数内localで握りつぶさない。
- integration testで`KillSwitchState()` constructorの呼び出し回数、またはrun内state objectの継続性を検証する。

## 6. pre-gate設計

### run開始前

- STOPファイル存在確認。
- output rootが意図したlocal pathであることを確認。
- `shadow_exports/`がcommit対象外である運用前提を確認。
- safety flagsの初期値が固定false/true契約を満たすことを確認。

### Public API取得前

- kill switch inactive確認。
- STOPファイル再確認。
- allowed symbol / interval確認。
- Private API、APIキー、認証header、broker fallbackが不要であることを確認。
- sourceが`gmo-public`でもPublic endpointのみに限定する。

### 各step前

- kill switch inactive確認。
- STOPファイル再確認。
- candidates_in_runがpolicy上限未満であることを確認。
- consecutive API errorsがpolicy上限未満であることを確認。
- 失敗時はcandidate生成前に停止する。

### candidate生成前

- signal labelがBUY/SELL/HOLDの既知値であることを確認。
- HOLD/NO_TRADE時はcandidate生成なし。
- market data timestampが存在し、timezone-aware timestampへ正規化できることを確認。
- spread provenanceを明示する。
- `REAL_PUBLIC_BID_ASK`を名乗れるのはbid/askがPublic ticker等から明示取得できた場合だけにする。

### risk allow前

- `RiskContext`をrun stateから構築する。
- data freshness、future skew、spread、cooldown、duplicate、daily/run candidate countを評価する。
- safety flagsが固定契約を満たすことを確認する。
- kill switch activeなら必ず`REJECT_SHADOW`にする。

### virtual fill前

- `RiskDecision.status == ALLOW_SHADOW`を確認。
- kill switch inactiveを確認。
- candidate_logとrisk_decision_logが成功していることを確認。
- candidate_id / decision_id / run_id / step_index相関を確認。
- 条件を満たさない場合はvirtual fillへ進まない。

## 7. AuditLogWriteError設計

audit log失敗は成功扱いしない。初期設計ではretryなしでfail closedにする。

`AuditLogWriteError`発生時の処理:

1. 例外を握りつぶさない。
2. `KillSwitchState.activate(KillSwitchReason.LOG_WRITE_FAILED, ...)`でkill switch activeにする。
3. current runをhalt扱いにする。
4. candidate生成、risk allow、virtual fill、以後のPublic追加取得を止める。
5. summary/metadataへ`halted=true`、`halt_reason=log_write_failed`、`audit_log_write_error_count`、`exit_code=2`を記録する。
6. kill_switch_logの書き込みも失敗した場合は、summary/metadataへの停止理由記録を優先する。
7. partial logsがあるrunは安全側に倒し、summarizeでsafety violationとして検出できる状態にする。

retry方針:

- Phase 2E-2初期はretryなし。
- durable write失敗のretryは、二重書き・相関崩れ・partial outputを増やすため、別設計レビューなしに追加しない。

## 8. CLI exit code設計

Phase 2E-2でのexit code方針:

```text
0: 正常終了
1: 一般エラー、入力不正、Public取得失敗など
2: safety violation / kill switch / STOP / audit log failure
```

最低限、次はexit code 2へ接続する。

- STOPファイル検知。
- kill switch active。
- audit log write failure。
- safety flag violation。
- summarizeで検出されるrisk JSONL schema/correlation violation。

現行のPublic取得失敗は一般エラーとしてexit code 1を維持してよい。ただし連続API errorをrun内で扱う設計にする場合、
policy上限到達はkill switch activeとしてexit code 2にする。

## 9. STOPファイル設計

既定パス:

```text
backend/shadow_exports/STOP
```

実装上は、backendディレクトリからの既定`out_root=shadow_exports`に対して`<out_root>/STOP`を確認する。
repository rootからの運用確認では`backend/shadow_exports/STOP`として扱う。

検知タイミング:

- run開始前。
- Public API取得前。
- 各step前。
- virtual fill前の最終gate。

STOP検知時の処理:

- kill switch active。
- reasonは`manual_stop_file_exists`。
- candidate生成なし。
- risk allowなし。
- virtual fillなし。
- summary/metadataへ停止理由を記録。
- 可能ならkill_switch_logを書く。
- CLI exit code 2。

STOP削除後の扱い:

- 同一runでは復帰しない。
- 再開はSTOP削除後、新しいrun_idで手動実行する。
- partial runを安全な正常runとして書き換えない。

## 10. candidate / decision / virtual result相関設計

相関ルール:

- BUY/SELLのみcandidateを生成する。
- HOLD/NO_TRADEはsignal_decision_logのみで、candidate_logを書かない。
- candidate 1件に対してRiskDecision 1件を必ず書く。
- REJECT時はvirtual resultを生成しない。
- ALLOW時のみvirtual result候補へ進む。
- virtual resultはcandidate_idとdecision_idを必ず保持する。
- decision without candidateは禁止。
- virtual result without allowは禁止。
- duplicate candidate/decisionは禁止。
- run_id不一致は禁止。
- step_index不一致は禁止。

ID設計:

- candidate_idは`make_candidate_id()`で決定的に生成する。
- decision_idは`make_decision_id(candidate_id, policy_id)`で決定的に生成する。
- virtual resultは独自IDを持つ場合でもcandidate_id/decision_idを主相関キーにする。

summarize連携:

- risk JSONL validatorでcandidate/decision相関を検出する。
- Phase 2E-2実装ではvirtual_result_logの相関検証も追加する。
- unsafe rowや相関不整合は通常件数へ含めず、safety violationにする。

## 11. audit log出力設計

Phase 2E-2統合時の出力対象:

```text
signal_decision_log.jsonl
candidate_log.jsonl
risk_decision_log.jsonl
virtual_result_log.jsonl
kill_switch_log.jsonl
```

出力タイミング:

- `signal_decision_log`: signal評価直後。HOLD/NO_TRADEも記録する。
- `candidate_log`: BUY/SELLでcandidate生成に成功した直後。
- `risk_decision_log`: risk evaluate直後。ALLOW/REJECTどちらも記録する。
- `virtual_result_log`: ALLOWかつvirtual fill/PnL更新に進んだ後。
- `kill_switch_log`: STOP、audit failure、safety violation、repeated API errors等でkill switch activeになった時。

失敗時の扱い:

- どのaudit logでも書けなければ`AuditLogWriteError`としてkill switch activeにする。
- signal logが書けない場合はcandidate生成へ進まない。
- candidate_logが書けない場合はrisk evaluateへ進まない。
- risk_decision_logが書けない場合はvirtual fillへ進まない。
- virtual_result_logが書けない場合はrunをhalt扱いにし、summaryで安全停止を示す。
- kill_switch_logも書けない場合はsummary/metadataへ停止理由を残し、exit code 2にする。

禁止事項:

- 生APIレスポンスを保存しない。
- secret、APIキー、account ID、authorization header、request/response bodyを含めない。
- broker order IDや実注文IDに見えるfieldを含めない。

## 12. summary / metadata設計

既存summary keyは維持する。Phase 2E-2では追加keyとして次を検討する。

```text
candidate_count
risk_allow_count
risk_reject_count
kill_switch_count
kill_switch_active
kill_switch_reason
invalid_risk_row_count
audit_log_write_error_count
safety_violation_count
exit_code
shadow_risk_schema_versions
```

要件:

- legacy summary互換を維持する。
- risk logがない既存runを壊さない。
- Markdown/CSV出力の既存列を壊さない。
- 追加列は後方互換のある形でappendする。
- unsafe rowは通常candidate/allow/reject件数に含めない。
- safety violationとして集計する。
- `summary.json`とrisk JSONLの値が矛盾する場合はrisk JSONL validatorの結果を優先して安全側に倒す。

metadataには次を追加候補とする。

- `phase`: `2E-2`
- `risk_policy_id`
- `stop_file_path`
- `audit_log_enabled`
- `exit_code`
- `halt_reason`

## 13. Phase 2E-2実装で触ってよい範囲

次フェーズ実装指示時に最終確定するが、候補は以下に限定する。

- `backend/scripts/run_shadow_session.py`
- `backend/scripts/summarize_shadow_runs.py`
- `backend/app/shadow/session.py`
- `backend/app/shadow/risk.py`
- `backend/app/shadow/audit.py`
- `backend/app/shadow/audit_schema.py`
- `backend/app/shadow/aggregate.py`
- `backend/app/tests/test_shadow_session.py`
- `backend/app/tests/test_shadow_summary.py`
- `backend/app/tests/test_shadow_risk.py`
- `backend/app/tests/test_shadow_audit.py`
- `backend/app/tests/test_shadow_session_risk_integration.py`
- `docs/PROJECT_STATUS.md`
- `docs/CODEX_HANDOFF.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`
- `docs/PHASE2E2_SESSION_INTEGRATION_DESIGN.md`

実装時も、既存sessionの公開surfaceを広げず、local-only/offline tests中心に進める。

## 14. Phase 2E-2実装でまだ触らない範囲

- `backend/app/main.py`
- `backend/app/main_readonly.py`
- frontend全体
- backend公開API
- Render / Vercel設定
- `.env`
- `.env.example`
- GMO Private API
- OANDA Private API
- `backend/app/brokers/**`
- 既存live RiskManager
- `OrderRequest` / 注文系API
- DB
- 認証
- reports公開
- `analysis_exports`実データ
- `shadow_exports/`生成物のcommit

## 15. Phase 2E-2統合テスト設計

Phase 2E-2実装時に必要なtest:

- normal shadow runでsignal/candidate/risk/virtual logsが生成される。
- HOLD/NO_TRADEでcandidateが生成されない。
- risk reject時にvirtual resultが生成されない。
- audit log failureでkill switch active、halt、exit code 2になる。
- STOPファイル検知でkill switch active、halt、exit code 2になる。
- `KillSwitchState`がrun内で再初期化されない。
- candidate / decision / virtual resultが1:1で相関する。
- decision without candidate、virtual result without allow、duplicate decisionをsummaryが検出する。
- unsafe risk rowをsummaryが検出する。
- legacy run summaryが壊れない。
- Private API / broker / OrderRequest importがない。
- `.env` / APIキーを読まない。
- `shadow_exports/`が未追跡である。

推奨testファイル:

- `backend/app/tests/test_shadow_session_risk_integration.py`
- 既存`test_shadow_session.py`への最小追加
- 既存`test_shadow_summary.py`への相関検証追加

## 16. 受け入れ条件

Phase 2E-2実装時の受け入れ条件:

- Public shadow runの既存挙動を壊さない。
- `USD_JPY / M1 / steps 10` が引き続き実行できる。
- risk/audit統合後も`real_order=false`。
- `private_api_used=false`。
- `api_key_used=false`。
- `no_order_execution=true`。
- `live_trading_environment_enabled=false`。
- `gmo_order_enabled=false`。
- broker送信なし。
- Private API importなし。
- OrderRequest変換なし。
- STOP時はexit code 2。
- audit failure時はexit code 2。
- safety violation時はexit code 2。
- candidate/decision/virtual result相関不整合をsummaryが検出する。
- backend全体テストが通る。
- ruffが通る。
- summarizeが通る。
- frontend、公開API、`main_readonly.py`に変更なし。
- `shadow_exports/`や実データをcommitしない。

## 17. 設計上のリスクと軽減策

### 既存runのデフォルト挙動を変えすぎるリスク

軽減策:

- Phase 2E-2初期は既存`events.jsonl`、`summary.json`、`metadata.json`を維持する。
- risk/audit情報は追加JSONLと追加summary keyに閉じる。
- legacy runを壊さないtestを先に固定する。

### log write失敗でrunが止まりやすくなるリスク

軽減策:

- これは安全側の意図した停止として扱う。
- exit code 2とsummary reasonを明確にし、原因調査しやすくする。
- retryは初期実装に入れない。

### risk rejectが増えvirtual ordersが減るリスク

軽減策:

- reject理由をsummaryとrisk_decision_logに明示する。
- PnLやvirtual order数を収益性評価に使わない前提を維持する。
- spread provenanceが不十分なsourceではALLOWしないことを安全仕様として受け入れる。

### summary互換性を壊すリスク

軽減策:

- 既存keyを削除・renameしない。
- 新規keyはoptionalにする。
- aggregatorはrisk JSONLなしrunをlegacyとして扱い続ける。

### Kill switch active時のpartial output扱い

軽減策:

- partial outputを正常runとして書き換えない。
- `halted=true`、`halt_reason`、`exit_code=2`、kill switch reasonを記録する。
- summarizeでhalted/safety violationとして見えるようにする。

### sessionが長くなりテストが複雑化するリスク

軽減策:

- orchestratorのgate処理を小さなpure helperへ分離する。
- Public APIはMockTransportまたはmock candlesでoffline testに限定する。
- integration testはsteps 2から3程度の短いrunで相関だけを見る。

## 18. 次フェーズへの引き継ぎ

次はPhase 2E-2実装プロンプトを別タスクとして作成する。

実装プロンプトでは、まずoffline integration testで受け入れ条件を固定し、その後にsession最小接続を行う。
Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進まない。
