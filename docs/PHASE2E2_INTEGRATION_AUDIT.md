# Phase 2E-2.5: shadow session統合結果レビュー / safety audit

## 1. 目的と結論

本書は、Phase 2E-2 commit `a491d17` で実装した shadow session へのlocal-only risk/audit最小統合を、
Phase 2E-3へ進む前にレビュー・安全監査した記録である。

今回の作業はレビュー、検証、docs化のみであり、backend code、tests、frontend、公開API、broker、
Private API、APIキー、実注文、実資金、Public ticker bid/ask連携は変更していない。

総合判定は **B: 軽微な改善候補はあるが、Phase 2E-3設計へ進める** とする。

理由:

- default runはlegacy互換を維持し、risk/audit JSONLを生成しない。
- `--enable-shadow-risk`有効時だけrisk/audit JSONLを生成する。
- STOP、audit failureは既存integration testsでexit code 2とhaltを確認できる。
- kline-only mockはsynthetic spreadとしてREJECTになり、virtual resultへ進まない。
- 明示bid/askを渡したoffline testではALLOWとvirtual_result_log相関を確認できる。
- summarizeはlegacy runとrisk/audit runを同時に扱い、safety violation 0、invalid_risk_row_count 0を維持した。
- 変更対象のPhase 2E経路ではPrivate API、broker、OrderRequest、`.env`参照はない。

ただし、次に進めるのは **Phase 2E-3設計** であり、いきなりPublic ticker bid/ask連携実装、Private API、
broker、実注文へ進まない。

## 2. 監査対象

対象commit:

```text
a491d17 feat: integrate local shadow risk audit into session
```

対象コード・テスト:

- `backend/scripts/run_shadow_session.py`
- `backend/app/shadow/session.py`
- `backend/app/shadow/aggregate.py`
- `backend/app/shadow/risk.py`
- `backend/app/shadow/audit.py`
- `backend/app/shadow/audit_schema.py`
- `backend/app/tests/test_shadow_session.py`
- `backend/app/tests/test_shadow_session_risk_integration.py`
- `backend/app/tests/test_shadow_summary.py`
- `backend/app/tests/test_shadow_risk.py`
- `backend/app/tests/test_shadow_audit.py`

参照docs:

- `docs/PHASE2E2_SESSION_INTEGRATION_DESIGN.md`
- `docs/PHASE2E1H_REAUDIT.md`
- `docs/PHASE2E1_SAFETY_AUDIT.md`
- `docs/PHASE2E0_SAFETY_DESIGN.md`
- `docs/PHASE2E0_5_SAFETY_REVIEW.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`
- `docs/CODEX_HANDOFF.md`
- `docs/PROJECT_STATUS.md`

## 3. CLI / feature flag監査

判定: **A**

確認結果:

- `backend/scripts/run_shadow_session.py`に`--enable-shadow-risk`が存在する。
- defaultでは既存の`run_shadow_session()`呼び出しに`enable_shadow_risk=False`が渡り、risk/audit JSONLを生成しない。
- `--enable-shadow-risk`有効時だけ、risk/audit JSONLとsummaryのrisk fieldsが生成される。
- risk有効時も、Private API、broker、実注文、OrderRequestへの接続はない。
- 既存CLI引数の`--source mock|gmo-public`、`--symbol`、`--interval`、`--steps`、`--out-root`は維持されている。
- risk有効時は`RiskPolicy`により`USD_JPY / M1`へ限定され、対象外symbol/intervalは一般エラーとして終了する。

実行確認:

```text
python3 -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 5
  exit 0 / orders 4 / risk JSONLなし

python3 -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 5 --enable-shadow-risk
  exit 0 / candidates 4 / allow 0 / reject 4 / orders 0 / risk JSONLあり
```

## 4. legacy互換監査

判定: **A**

確認結果:

- `--enable-shadow-risk`なしのmock runは従来どおり`events.jsonl`、`summary.json`、`metadata.json`だけを生成した。
- default runでは`shadow_risk_enabled` fieldは追加されない。
- default runでは`signal_decision_log.jsonl`、`candidate_log.jsonl`、`risk_decision_log.jsonl`、
  `virtual_result_log.jsonl`、`kill_switch_log.jsonl`は生成されない。
- legacy summaryはbroken扱いにならず、risk logなしrunのcandidate/risk/kill countは0扱いのまま維持された。

最終summarize確認:

```text
runs_count: 15
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
```

## 5. KillSwitchState ownership監査

判定: **B**

確認結果:

- risk有効時に`run_shadow_session()`内で`kill_switch = KillSwitchState()`を1回だけ初期化する。
- step loop内では新しいinactive `KillSwitchState()`を作り直していない。
- STOPとaudit failure時は`activate_kill_switch()`を通じてactive化する。
- active化後はloop冒頭でbreakし、candidate生成、risk allow、virtual fillへ進まない。
- active後にsuccess eventでinactiveへ戻す経路はない。

軽微な改善候補:

- `KillSwitchState()`の生成回数を直接検証するtestはない。現行のSTOP/audit failure testで挙動は確認できるが、
  将来のリファクタ時にownershipをより強く固定するなら、state生成回数またはstate lifecycleの直接testを追加してよい。

## 6. STOP pre-gate監査

判定: **A**

確認結果:

- CLIは`--enable-shadow-risk`有効時に、Public取得前に`<out-root>/STOP`を確認する。
- sessionもrun開始時、各step前、virtual fill前にSTOPを確認する。
- STOP検知時は`manual_stop_file_exists`でkill switch active、halt、candidateなし、virtual resultなし、exit code 2になる。
- summary/metadataへ停止理由が反映され、可能な場合は`kill_switch_log.jsonl`にも記録される。

確認test:

- `test_stop_file_pre_gate_halts_with_exit_code_2`

## 7. AuditLogWriteError / exit code 2監査

判定: **A**

確認結果:

- audit writeは`write_required_audit()`で必須処理として扱われる。
- `AuditLogWriteError`発生時は`audit_log_write_error_count`が増え、`log_write_failed`でkill switch activeになる。
- signal/candidate/risk/virtual result log失敗時は、後続のvirtual fillへ進まない。
- retryなしでfail closedに倒す。
- summary/metadataにはhalt、kill_switch_reason、audit_log_write_error_count、exit_code 2が残る。

確認test:

- `test_audit_write_failure_halts_with_exit_code_2`

## 8. candidate / risk / virtual result監査

判定: **B**

確認結果:

- BUY/SELLのみ`OrderCandidate`を生成する。
- HOLD/NO_TRADEではcandidateを生成せず、signal logのみ残す。
- kline-only mockは`SpreadProvenance.SYNTHETIC_ZERO`としてrisk rejectになり、virtual resultへ進まない。
- 明示bid/askを渡すoffline `risk_ticker_fn` testでは`REAL_PUBLIC_BID_ASK`としてALLOWになり、virtual resultが生成される。
- REJECT時は`virtual_result_log.jsonl`が生成されない。
- ALLOW時のvirtual resultはcandidate_id / decision_idでcandidate/risk decisionと相関する。
- summarizeはvirtual result without allowをsafety violationとして検出する。

軽微な改善候補:

- `risk_ticker_fn`は内部hookとして明示bid/askを信頼する。CLIからは露出していないため現時点のblockerではないが、
  Phase 2E-3設計ではPublic ticker由来であることのprovenance境界を明文化し、実装時にテストで固定する必要がある。
- ALLOW経路では`ShadowTrader.step()`がsignalを再評価する。現行のdemo signalは純粋で問題ないが、将来のSignalFn拡張時は
  candidate生成時のsignalとvirtual fill時のsignalが一致することを明示的に固定するtestを追加してよい。

## 9. audit JSONL監査

判定: **A**

確認結果:

- risk有効mock runでは`signal_decision_log.jsonl`、`candidate_log.jsonl`、`risk_decision_log.jsonl`が生成された。
- synthetic spread rejectのため`virtual_result_log.jsonl`は生成されなかった。
- STOP時の`kill_switch_log.jsonl`生成はintegration testで確認されている。
- writerはtyped dataclassと既存schema validatorを使用する。
- audit rowにはschema_version / event_type / fixed safety flagsが入る。
- secret、APIキー、raw response、account ID、broker order IDは保存しないschemaになっている。
- 出力先は`trusted_root/run_id/<event>.jsonl`に固定され、`shadow_exports/<run_id>/`配下に閉じている。

実ファイル確認:

```text
signal_decision_log.jsonl: 5 rows
candidate_log.jsonl: 4 rows
risk_decision_log.jsonl: 4 rows
virtual_result_log.jsonl: 0 rows
```

## 10. summary / metadata監査

判定: **A**

確認結果:

- risk有効runのsummaryに次が記録された:
  - `shadow_risk_enabled`
  - `candidate_count`
  - `risk_allow_count`
  - `risk_reject_count`
  - `kill_switch_count`
  - `kill_switch_active`
  - `kill_switch_reason`
  - `invalid_risk_row_count`
  - `audit_log_write_error_count`
  - `safety_violation_count`
  - `exit_code`
- 既存summary keyは維持されている。
- Markdown summarizeは`virtual_result_count`を含むrisk pipeline sectionを表示し、CSV/Markdownの既存run互換を壊していない。

確認したrisk有効mock summary:

```text
shadow_risk_enabled: true
candidate_count: 4
risk_allow_count: 0
risk_reject_count: 4
kill_switch_active: false
audit_log_write_error_count: 0
safety_violation_count: 0
exit_code: 0
```

## 11. import / dependency監査

判定: **A**

広い検索結果:

- 指定どおり`backend/scripts`全体を検索すると、既存の研究・paper系スクリプトに`app.brokers` importが複数存在する。
- これはPhase 2E-2で追加・変更した経路ではなく、既存の別用途スクリプトである。
- `def (submit|send|place|cancel|amend)`検索は一致なし。

Phase 2E変更対象に絞った検索結果:

```text
OrderRequest|risk_service|app\.brokers|dotenv|os\.environ|getenv: 一致なし
def (submit|send|place|cancel|amend): 一致なし
```

確認結果:

- `backend/app/shadow/`、`run_shadow_session.py`、`summarize_shadow_runs.py`、Phase 2E関連testに
  Private API、broker、OrderRequest、`.env`、既存live RiskManager、DB、frontend/reports接続はない。

## 12. tests監査

判定: **B**

確認済みtest:

- legacy default run: あり
- risk/audit enabled run: あり
- synthetic spread reject: あり
- explicit bid/ask allow: あり
- HOLD no candidate: あり
- STOP exit code 2: あり
- AuditLogWriteError exit code 2: あり
- REJECT no virtual result: あり
- ALLOW virtual result相関: あり
- summarize legacy互換: あり
- unsafe row検出: あり
- virtual result without allow検出: あり

軽微な追加推奨:

- CLIプロセスとしてSTOP exit code 2を直接見るtest。
- `risk_ticker_fn`ではなく将来のPublic ticker adapter由来bid/askを使うPhase 2E-3 test。
- SignalFn再評価によるcandidate/virtual fill signal driftを防ぐtest。

これらはPhase 2E-3設計・実装時の推奨であり、Phase 2E-2.5時点の修正必須ではない。

## 13. 検証結果

実行結果:

```text
関連テスト:
python3 -m pytest -q app/tests/test_shadow_session.py app/tests/test_shadow_session_risk_integration.py app/tests/test_shadow_summary.py app/tests/test_shadow_risk.py app/tests/test_shadow_audit.py
97 passed

backend全体:
python3 -m pytest -q
334 passed

ruff:
python3 -m ruff check .
All checks passed

summarize:
python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
runs_count: 15
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
candidate_count: 8
risk_allow_count: 0
risk_reject_count: 8
virtual_result_count: 0
```

mock run確認:

```text
risk/audit無効:
run_id: 20260622_044346_shadow_USD_JPY_mock
exit: 0
steps_executed: 5
orders: 4
halted: false

risk/audit有効:
run_id: 20260622_044354_shadow_USD_JPY_mock
exit: 0
steps_executed: 5
orders: 0
candidate_count: 4
risk_allow_count: 0
risk_reject_count: 4
kill_switch_active: false
```

## 14. レビュー判定

```text
判定: B（軽微な改善候補はあるが、Phase 2E-3設計へ進める）
Phase 2E-3設計へ進めるか: はい
Phase 2E-3実装へ進めるか: まだ進まない
修正必須事項: なし
修正推奨事項: Phase 2E-3設計でPublic ticker bid/ask provenance、CLI STOP test、signal drift対策を明文化する
追加テスト要否: Phase 2E-3設計後に追加推奨
```

## 15. 安全確認

- Private API: なし
- APIキー / secret / `.env`: 読込・表示・変更なし
- broker: 変更対象経路では未接続
- OrderRequest変換: なし
- 実注文 / 実資金: なし
- backend公開API: 変更なし
- `backend/app/main_readonly.py`: 変更なし
- frontend: 変更なし
- Render / Vercel設定: 変更なし
- DB / 認証: 変更なし
- Public ticker bid/ask連携: 未実装
- `shadow_exports/` / `analysis_exports/` 生成物: commit対象外

## 16. 次の作業

次は **Phase 2E-3設計** を別タスクとして行う。

Phase 2E-3設計で扱うべき論点:

- GMO Public ticker由来bid/askをsessionへどう渡すか。
- `REAL_PUBLIC_BID_ASK` provenanceをどこで保証するか。
- candle-only/kline-only runを引き続きsynthetic spread rejectに倒す境界。
- CLI-level STOP exit code 2 test。
- candidate生成時signalとvirtual fill時signalのdrift防止。
- risk/audit runを引き続きlocal-only / no-order / no Privateに保つ検証。

Phase 2E-3実装、Public ticker bid/ask連携実装、Private API、APIキー、broker、実注文、実資金、自動売買、
本番公開API追加にはまだ進まない。
