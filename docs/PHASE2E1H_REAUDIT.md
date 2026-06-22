# Phase 2E-1H: local-only safety hardening 再監査

## 1. 目的と結論

本書は、Phase 2E-1H commit `9784486` で実施した corrective hardening が、
Phase 2E-1.5監査で見つかったD-1〜D-4を塞げているかを再監査した記録である。

今回の作業は再監査・検証・docs化のみであり、backend code、tests、frontend、公開API、broker、Private API、
実注文、実資金、session統合は変更していない。

総合判定は **B: 軽微な改善候補はあるが、Phase 2E-2設計へ進める** とする。
D-1〜D-4の再現入力は、既存adversarial testsと追加offline probeで安全側に倒れることを確認した。

ただし、次に進めるのは **Phase 2E-2設計** であり、いきなりsession統合実装へ進まない。
Phase 2E-2実装は、設計レビューと明示承認後に別タスクとして扱う。

## 2. 監査対象

対象commit:

```text
9784486 fix: harden local shadow safety contracts
```

対象コード・テスト:

- `backend/app/shadow/risk.py`
- `backend/app/shadow/audit.py`
- `backend/app/shadow/audit_schema.py`
- `backend/app/shadow/aggregate.py`
- `backend/scripts/summarize_shadow_runs.py`
- `backend/app/tests/test_shadow_risk.py`
- `backend/app/tests/test_shadow_audit.py`
- `backend/app/tests/test_shadow_summary.py`

参照した設計・監査文書:

- `docs/PHASE2E0_SAFETY_DESIGN.md`
- `docs/PHASE2E0_5_SAFETY_REVIEW.md`
- `docs/PHASE2E1_SAFETY_AUDIT.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`
- `docs/CODEX_HANDOFF.md`
- `docs/PROJECT_STATUS.md`

## 3. 方法

- Phase 2E-1.5監査のD-1〜D-4とPhase 2E-1H修正内容を突合した。
- `risk.py`、`audit.py`、`audit_schema.py`、`aggregate.py`の実装をレビューした。
- `test_shadow_risk.py`、`test_shadow_audit.py`、`test_shadow_summary.py`でadversarial caseの固定状況を確認した。
- repository外の一時ディレクトリだけを使う追加offline probeを実行した。
- import / dependency / dangerous referenceを静的検索した。
- targeted tests、backend全体test、ruff、legacy summarizeを実行した。

## 4. D-1 spread provenance再監査

判定: **A**

確認結果:

- `SpreadProvenance` enumがあり、値は `REAL_PUBLIC_BID_ASK`、`SYNTHETIC_ZERO`、
  `CANDLE_DERIVED`、`UNKNOWN` に限定されている。
- `OrderCandidate.spread_provenance` と `RiskContext.spread_provenance` が明示fieldになっている。
- `RiskContext.spread_provenance` のdefaultは `UNKNOWN` であり、callerが指定を忘れてもallowされない。
- `evaluate()` はcandidate/context両方のprovenanceを検査し、`REAL_PUBLIC_BID_ASK`以外をrejectする。
- `SYNTHETIC_ZERO` と `CANDLE_DERIVED` は `synthetic_spread_not_allowed` でrejectする。
- `UNKNOWN` は `invalid_data` でrejectする。
- malformed provenance型はconstructorまたは`evaluate()`でfail closedになる。
- zero spreadであってもprovenanceが欠損/default `UNKNOWN`ならrejectされ、数値だけでreal Public spreadとは推測しない。
- `RiskPolicy.allow_synthetic_zero_spread=True` はconstructor invariantで拒否されるため、安全契約をpolicyで緩和できない。

追加probe:

```text
provenance未指定zero spread: REJECT_SHADOW / invalid_data
malformed provenance: REJECT_SHADOW / unknown_state
```

確認した既存test:

- `test_spread_provenance_is_required_and_fail_closed`
- `test_malformed_spread_provenance_rejects_or_constructor_fails`
- `test_risk_reject_boundaries`

## 5. D-2 malformed input fail closed再監査

判定: **A**

確認結果:

- `RiskPolicy.__post_init__` がpolicy ID、allowed symbols/intervals、上限値、finite spread、
  fixed safety booleansを検証する。
- `RiskContext.__post_init__` がtimezone-aware evaluation time、provenance、counts、existing IDs、
  market_closed、kill_switch型を検証する。
- `KillSwitchState.__post_init__` がactive/inactive invariantを検証する。
- `RiskDecision.__post_init__` がstatus/reason/safety flag invariantを検証する。
- `evaluate()` はpolicy検証をcandidate field参照より前に行い、malformed policyを`REJECT_SHADOW`へ倒す。
- `_decision()` はcandidate_id、run_id、step_index、policy_id、timestampのfallbackを持ち、
  decision生成中の例外でも`REJECT_SHADOW / unknown_state`を返す。
- malformed candidate/context/policyは例外を外へ漏らさず、reason付きrejectになる。

追加probe:

```text
malformed policy: REJECT_SHADOW / unknown_state
```

確認した既存test:

- `test_risk_policy_constructor_rejects_invalid_invariants`
- `test_malformed_candidate_rejects_without_escaping`
- `test_malformed_context_rejects_without_escaping`
- `test_missing_safety_and_unknown_states_fail_closed`

## 6. D-3 audit schema / root containment再監査

判定: **A**

確認結果:

- `audit_schema.py` が追加され、writerとsummarizerが同じversioned schema validatorを使う。
- writerはarbitrary dictを拒否し、typed dataclassだけを受け付ける。
- event別にrequired field / allowed fieldが定義され、unknown fieldを拒否する。
- `safety_snapshot`のnested unknown fieldも拒否する。
- safety flagは全eventで固定値を検証する。
- forbidden field名は正規化して検査され、`api_key`、`secret`、`token`、`password`、
  `private_key`、`authorization`、`account_id`、`broker_order_id`、`raw_response`、
  request/response headers/body系、`credentials`を拒否する。
- writerは`trusted_root + run_id + event_type`から固定ファイル名を構築し、任意ファイルパスを直接受け取らない。
- invalid run_id、absolute path、`..` traversal、run directory symlink、event file symlinkを拒否する。
- write/fsync failureは`AuditLogWriteError`になる。

追加probe:

```text
real_order=true audit row: AuditLogWriteError
root外/traversal保存: AuditLogWriteError
```

確認した既存test:

- `test_audit_writer_rejects_arbitrary_dict`
- `test_audit_writer_rejects_unsafe_safety_flags`
- `test_audit_writer_rejects_unknown_and_nested_unknown_fields`
- `test_audit_writer_rejects_credentials_and_raw_response_fields`
- `test_audit_writer_rejects_invalid_run_id_and_path_injection`
- `test_audit_writer_rejects_symlink_escape`
- `test_audit_writer_rejects_event_file_symlink`
- `test_audit_writer_write_and_fsync_failures_are_fail_closed`

## 7. D-4 unsafe risk row summarize再監査

判定: **A**

確認結果:

- `_load_risk_pipeline()` は各risk JSONL rowを `validate_audit_row()` に通す。
- invalid/unsafe rowはcandidate/allow/reject通常件数に含めない。
- invalid/unsafe rowは`log_errors`へ記録され、`safety_violations`へ反映される。
- `invalid_risk_row_count` が追加され、invalid row数を明示できる。
- `candidate_id`、`decision_id`、run_id、step_indexの相関を検証する。
- duplicate candidate/decision、decision without candidate、candidate without decisionを検出する。
- risk logがないlegacy runは従来どおりbroken扱いにならず、candidate/risk/kill countは0のまま維持される。

追加probe:

```text
unsafe risk row summarize:
  broken: []
  candidate_count: 0
  safety_violation_runs_count: 1
  invalid_risk_row_count: 1
```

確認した既存test:

- `test_unsafe_candidate_risk_row_is_violation_and_not_counted`
- `test_invalid_risk_row_schema_is_violation_and_not_counted`
- `test_decision_without_candidate_is_violation_and_not_counted`
- `test_candidate_without_decision_is_violation_and_not_counted`
- `test_duplicate_decision_is_violation_and_not_counted`
- `test_phase2e_risk_logs_are_aggregated_without_breaking_legacy`
- `test_invalid_new_schema_is_safety_violation_not_broken_legacy`

## 8. KillSwitchState invariant再監査

判定: **B**

確認結果:

- `active=True`の場合、`reasons`と`activated_at`が必須である。
- `active=False`の場合、`reasons`、`activated_at`、`safety_snapshot`のようなactive専用fieldは拒否される。
- `deactivate` / `reset` methodは存在しない。
- `record_api_result(success=True)`はactive stateを復帰させず、同じactive objectを返す。
- active stateはcandidate生成、risk allow、virtual result処理を止める。

残る課題:

- 同一runで新しいinactive `KillSwitchState()` を作り直さない保証は、value object単体ではなく
  Phase 2E-2 orchestrationのstate所有責務として残る。

この残課題はPhase 2E-1.5監査時点のC-1と同じ性質であり、今回のD-1〜D-4修正のblockerではない。
Phase 2E-2設計でrun lifecycleがKillSwitchStateを唯一所有し、停止済みrunをresumeしない構造を定義する必要がある。

## 9. import / dependency監査

判定: **A**

禁止参照検索:

```text
OrderRequest|risk_service|app\.brokers|dotenv|os\.environ|getenv: 一致なし
def (submit|send|place|cancel|amend): 一致なし
```

広めの依存検索では以下を確認したが、禁止経路ではない。

- `backend/app/shadow/gmo_public.py` の `httpx`: Phase 2B既存のGMO Public read-only adapter。
  Private API、APIキー、注文送信ではない。
- `backend/app/tests/test_shadow_session.py` の `httpx.MockTransport`: offline test用。
- `backend/app/shadow/audit.py` の `os.fsync`: local JSONL durable write用。環境変数読込ではない。
- `backend/app/shadow/session.py` / `aggregate.py` の `Path`: local `shadow_exports` file I/O用。
- `backend/app/shadow/__init__.py` / `gmo_public.py` のFastAPI表記: docs文字列上の「未公開」説明でありroute登録ではない。

確認結果:

- GMO/OANDA Private API importなし。
- broker importなし。
- OrderRequest変換なし。
- 既存live RiskManager importなし。
- `.env` / dotenv / `os.environ` / `getenv`なし。
- DB接続なし。
- frontend / reports接続なし。
- submit/send/place/cancel/amend系関数なし。

## 10. summarize後方互換

判定: **A**

実行結果:

```text
runs_count: 11
broken/skipped: 0
safety_violation_runs_count: 0
candidate_count: 0
risk_allow_count: 0
risk_reject_count: 0
kill_switch_count: 0
invalid_risk_row_count: 0
shadow_risk_schema_versions: -
```

legacy risk logなしrunは壊れておらず、Phase 2Dまでのsummary集計との後方互換を維持している。

## 11. tests確認

実行結果:

```text
python3 -m pytest -q app/tests/test_shadow_audit.py app/tests/test_shadow_risk.py app/tests/test_shadow_summary.py
83 passed

python3 -m pytest -q
327 passed

python3 -m ruff check .
All checks passed
```

tests評価:

- D-1〜D-4の主要adversarial inputsは既存testで固定されている。
- writer/summarizerの共有schema、unsafe flags、unknown fields、credentials/raw response、path traversal、
  symlink、write/fsync failure、risk row相関不整合がtestされている。
- Phase 2E-2 orchestrationで必要になるKillSwitchState同一run所有、log write failure時のCLI exit 2接続、
  session統合後のstate lifecycleは、今後の設計・統合test対象として残る。

## 12. レビュー判定

```text
判定: B（軽微な改善候補はあるが、Phase 2E-2設計へ進める）
Phase 2E-2設計へ進めるか: はい
Phase 2E-2実装へ進めるか: まだ進まない
修正必須事項: なし
修正推奨事項: Phase 2E-2設計でKillSwitchState所有、log failure exit 2、session統合境界を明文化する
追加テスト要否: Phase 2E-2設計後、session統合testとして追加が必要
```

B判定の理由:

- Phase 2E-1.5のD-1〜D-4は、コードレビュー、既存adversarial tests、追加probeで修正確認できた。
- local-only境界、no Private/no broker/no orderの構造は維持されている。
- legacy summarize互換も維持されている。
- 残る課題はPhase 2E-2 orchestration設計に属するstate ownership / CLI接続 / integration testであり、
  現local-only部品のD判定を継続するものではない。

## 13. 今回作成・更新したファイル

作成:

- `docs/PHASE2E1H_REAUDIT.md`

更新:

- `docs/CODEX_HANDOFF.md`
- `docs/PROJECT_STATUS.md`
- `docs/PHASE2E1_SAFETY_AUDIT.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`

コード・テストは変更していない。

## 14. 安全確認

- Private API: なし
- APIキー / secret / `.env`: 読込・表示・変更なし
- broker: 変更なし
- 実注文 / 実資金: なし
- `backend/app/main.py`: 変更なし
- `backend/app/main_readonly.py`: 変更なし
- backend公開API: 変更なし
- frontend: 変更なし
- Render / Vercel設定: 変更なし
- DB / 認証: 変更なし
- session統合: 未実施
- `shadow_exports/` / `analysis_exports/` 生成物: commit対象外

## 15. 次の作業

次は **Phase 2E-2設計** を別タスクとして行う。

Phase 2E-2設計で扱うべき論点:

- 既存shadow sessionへcandidate/risk/audit境界をどこで差し込むか。
- Public ticker由来の `REAL_PUBLIC_BID_ASK` provenanceをどう保証するか。
- KillSwitchStateをrun lifecycleが唯一所有し、停止済みrunをresumeしない構造。
- audit writer failureをKill switch / CLI exit code 2 / summaryへどう接続するか。
- session統合後のcandidate/decision/virtual result 1:1相関test。
- legacy run互換を保ったまま新risk JSONLを保存する運用境界。

Phase 2E-2実装、Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加にはまだ進まない。

## 16. Phase 2E-2設計結果

Phase 2E-2のsession統合前安全接続設計を
[PHASE2E2_SESSION_INTEGRATION_DESIGN.md](PHASE2E2_SESSION_INTEGRATION_DESIGN.md) に整理した。

設計で確定した境界:

- KillSwitchStateはrun lifecycle orchestratorがrun単位で1つだけ所有する。
- STOPファイル、audit log write failure、safety violationはkill switch activeとCLI exit code 2へ接続する。
- candidate、RiskDecision、virtual resultはrun_id / step_index / candidate_id / decision_idで相関させる。
- risk JSONLがないlegacy runは引き続き壊さない。
- Phase 2E-2実装は、設計レビューと明示承認後に別タスクとして行う。

この追記時点では、既存shadow session、backend code、tests、frontend、公開API、Private API、broker、実注文には
接続していない。
