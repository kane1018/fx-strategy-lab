# Phase 2E-1.5: local-only safety contract監査

## 1. 目的と結論

本書は、Phase 2E-1 commit `67ae2f1`で追加されたlocal-only安全基盤を、
[PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md) と
[PHASE2E0_5_SAFETY_REVIEW.md](PHASE2E0_5_SAFETY_REVIEW.md) に照らして監査した記録である。
コード・test・API・UIは変更していない。

総合判定は **D: Phase 2E-2前に修正必須** とする。Private API、broker、live RiskManager、OrderRequest、
`.env`への接続はなく、既存sessionにも未統合のため、現時点で実注文へ到達する経路はない。一方、統合後の
safety contractを破り得る入力検証と監査ログ検証の不足をoffline実証したため、現状のままPhase 2E-2へ進まない。

## 2. 監査対象と方法

対象:

- `backend/app/shadow/risk.py`
- `backend/app/shadow/audit.py`
- `backend/app/shadow/aggregate.py`
- `backend/app/tests/test_shadow_risk.py`
- `backend/app/tests/test_shadow_summary.py`
- `backend/scripts/summarize_shadow_runs.py`

方法:

- 設計文書とのfield、policy、reason、境界条件の突合。
- import、I/O、network、DB、broker、環境変数、注文変換の静的検索。
- 既存test、ruff、legacy summarizeの再実行。
- repository外の一時ディレクトリだけを使うadversarial offline probe。
- 問題の実装修正やtest追加は行わず、再現結果と修正方針のみを記録。

分類:

- A: 問題なし
- B: 軽微な改善候補
- C: Phase 2E-2前に修正推奨
- D: Phase 2E-2前に修正必須
- E: 危険。統合へ進めない

## 3. import / dependency監査 — A

次のimport・参照・呼出しは対象コードに存在しないことを確認した。

- GMO/OANDA Private API。
- `app.brokers`およびbroker送信関数。
- `OrderRequest`および注文変換adapter。
- `app.services.risk_service`。
- `.env`、dotenv、`os.environ`、`getenv`。
- requests/httpx等のnetwork client。
- DB/SQLAlchemy。
- frontend、reports、FastAPI route。

`audit.py`の`os` importは`fsync`だけに使用され、環境変数を読まない。`main.py`、`main_readonly.py`、
router、frontendからPhase 2E-1 risk/audit/aggregateへの参照もない。

## 4. OrderCandidate監査

### 4.1 確認できた事項 — A

- frozen dataclassであり、通常の代入は拒否される。
- constructor/`dataclasses.replace`で`real_order`、`private_api_used`、`api_key_used`をtrueにすると拒否される。
- BUY/SELLだけを生成し、HOLDおよび渡されたKill switchがactiveの場合は生成しない。
- BUYはask、SELLはbidを参照価格に使う。
- broker送信、変更、取消、OrderRequest変換メソッドを持たない。
- secret、APIキー値、account ID、broker order IDのfieldを持たない。
- candidate payloadとdeterministic IDの不一致はrisk rejectされる。

### 4.2 synthetic provenanceが必須でない — D-1

`create_order_candidate()`はbid/askからspreadを計算するが、spreadのprovenanceをcandidateへ保持しない。
`RiskContext.synthetic_spread`のdefaultはfalseであり、callerが明示し忘れるとbid=askのzero spreadが
`ALLOW_SHADOW`になることをoffline probeで確認した。

```text
zero_spread = 0.0
default_context_status = ALLOW_SHADOW
```

これは「synthetic zero spreadをrisk通過に使わない」「provenance欠損はinvalid_data」という設計に反する。

推奨修正:

- market data provenanceをrequired enumとしてcandidateまたは必須contextへ持たせる。
- defaultを安全側の`UNKNOWN`にし、`REAL_PUBLIC_BID_ASK`以外はrejectする。
- provenance欠損、unknown、candle-derived、synthetic zeroを個別testする。
- Phase 2E-2 callerのboolean自己申告だけに依存しない。

## 5. RiskPolicy / evaluate監査

### 5.1 確認できた事項 — A

- `evaluate()`自体はfile、network、DB、broker、環境変数を呼ばない。
- 正常なtyped inputに対する評価は決定論的である。
- unsupported symbol/interval、quantity、spread、freshness、future skew、count、duplicate、cooldown、
  Kill switch、required field、安全flagを評価する。
- 通常のrejectでは1件以上のreasonを返し、`ALLOW_SHADOW`はvirtual継続だけを意味する。
- RiskDecision constructorはunsafe flagとreason/status不整合を拒否する。

### 5.2 malformed policyで例外が外へ漏れる — D-2

RiskPolicyはfrozenだがruntime validationを持たず、型・範囲の異なる値をconstructできる。
`evaluate()`内のcatch後に `_decision()` がpolicy値をdeterministic IDへ使用するため、malformed policyでは
reject decisionではなく例外がcallerへ漏れる場合がある。

offline probeでは `RiskPolicy(policy_id=object())` により次を確認した。

```text
malformed_policy_escaped = TypeError
```

これは「不明・欠損・例外はfail closed」「RiskManager reject reason必須」を満たさない。

推奨修正:

- RiskPolicyに`__post_init__`を設け、policy ID、型、有限値、正の閾値、固定false契約をconstructorで検証する。
- policy validationをcandidate field参照より前に行う。
- `_decision()`を含む全decision生成経路をfail-closed境界内に置く。
- malformed candidate/context/policyの代表例で、例外ではなく`REJECT_SHADOW + unknown_state/policy_mismatch`を確認する。

## 6. KillSwitchState監査

### 6.1 確認できた事項 — A

- `activate()`はactive stateに対してselfを返し、method経由ではstickyである。
- deactivate/reset methodはない。
- active stateを渡したcandidate factoryはcandidateを生成しない。
- active stateを渡したrisk評価は`kill_switch_active`でrejectする。
- `can_process_virtual_result()`はactive時にfalseを返す。
- Public errorは3回目で`repeated_api_errors`を発火し、active後のsuccessでも復帰しない。
- `manual_stop_file_exists` reasonを保持できる。

### 6.2 state invariantとrun継続性 — C-1

`KillSwitchState(active=True)`をreason/activated_atなしで直接constructできる。逆に、active後もcallerが新しい
`KillSwitchState()`を作ればinactive stateを得られる。immutable value objectだけでは「同一runで復帰しない」を
保証できず、Phase 2E-2 orchestrationに状態所有責務が残る。

推奨修正:

- `__post_init__`でactive/reasons/activated_at/snapshot/counterのinvariantを検証する。
- active stateをrun lifecycleが唯一所有し、同じrun_idでは再初期化しない構造にする。
- direct invalid construction、state replacement、同一run再開を拒否するtestを追加する。

## 7. JSONL audit writer監査

### 7.1 確認できた事項 — A

- event typeを固定一覧へ制限する。
- schema versionとevent typeのoverrideを拒否する。
- run_idとtimestampを要求する。
- exact forbidden keyとして`api_key`、`secret`、`token`、`password`、`account_id`、
  `broker_order_id`を再帰確認する。
- open/write/flush/fsync失敗を`AuditLogWriteError`へ変換し、成功扱いしない。
- DB、reports、frontendへ接続しない。

### 7.2 unsafe payloadと任意保存先を許容する — D-3

writerはevent別schemaやsafety snapshotを検証せず、任意dictを受け取る。offline probeで次の1行が例外なく
保存されることを確認した。

```text
write_succeeded = true
outside_shadow_exports = true
real_order = true
note_accepted = true
```

`note`にはダミー機密markerを入れた。exact forbidden key以外のfield/value、生responseを示すfield、
`real_order=true`、`private_api_used=true`等を拒否できない。また`run_dir`は任意Pathで、
`shadow_exports/<run_id>/`配下という保存境界を強制しない。

推奨修正:

- arbitrary dictではなくevent別typed recordだけを受け付ける。
- eventごとのfield allowlist、型、required field、reason code、ID相関、固定safety snapshotを検証する。
- `real_order=false`等の6安全flagをすべての該当eventで強制する。
- raw response/header/body、authorization、credential、account/broker identifiersを構造的に保持できなくする。
- writerへtrusted output rootを渡し、resolve後のpathが`shadow_exports`配下であることを検証する。
- path traversalとsymlink escapeも拒否する。
- exact forbidden keyだけでなく、event schemaに存在しないfieldを拒否する。

### 7.3 CLI exit code 2 — C-2

writerは失敗時に例外を返すためlocal fail closedの土台はあるが、sessionへ未統合のためCLI exit code 2、
Kill switch log、失敗summaryの一貫した扱いはまだ検証できない。修正後のPhase 2E-2設計で必須とする。

## 8. summarize監査

### 8.1 legacy互換 — A

- risk logがない11 legacy runをbrokenにせず集計できる。
- current runはruns 11、broken/skipped 0、safety violation 0を維持した。
- candidate/risk/kill countsはrisk logがない場合0となる。
- schema version欠損risk rowはrisk pipeline error/safety violationになる。
- 既存runs/group CSV fieldは変更されていない。

### 8.2 unsafe risk rowをsafety violationとして検出しない — D-4

summarizerはrisk rowのschema version、event type、risk statusを一部確認するが、row内のsafety flag、
required field、run/candidate/decision相関、reason code型を検証しない。

有効なschema/event typeを持ち、`real_order=true`を含むcandidate logを一時runへ置いたoffline probe結果:

```text
candidate_count = 1
safety_violation_runs_count = 0
safety_violations = []
```

unsafe rowを件数へ含めながら安全違反0と表示できるため、Phase 2E-2統合前に修正必須である。

推奨修正:

- writerと共有するversioned event schema validatorをsummarizerでも使用する。
- safety flag、required ID、run_id一致、candidate/decision 1対1、reason code、kill state invariantを検証する。
- invalid rowは通常件数へ含めず、run safety violationとして明示する。
- unknown field、unsafe flag、相関不一致、invalid reason、invalid active stateのtestを追加する。

## 9. tests監査

### 9.1 現在カバーされる事項 — A

- OrderCandidateのBUY/SELL/HOLD、immutability、固定false。
- deterministic candidate/decision ID。
- 主要reject条件、unknown candidate、policy safety flag。
- Kill switch method経由のsticky behavior、3連続API error。
- JSONL基本field、exact forbidden key、filesystem write failure。
- risk集計、legacy互換、invalid schema detection。

### 9.2 追加必須test — D/C

次のtestが不足しており、今回のprobeで実際に抜けを確認した。

- D: provenance欠損/unknown/synthetic zeroが必ずrejectされること。
- D: arbitrary dictのunsafe flag、unknown field、nested dummy credential、raw response fieldをwriterが拒否すること。
- D: writerが許可root外、`..`、symlink escapeを拒否すること。
- D: unsafe risk rowをsummarizerがsafety violationにすること。
- D: malformed policy/context/candidateの全経路が例外を漏らさずrejectすること。
- C: KillSwitchStateのinvalid direct constructionと同一run再初期化を拒否すること。
- C: log failureをKill switch active、exit code 2、非成功summaryへ接続するintegration test。
- C: UTC日界、上限直前/ちょうど/超過、cooldown 59/60秒の境界test。
- C: JSONL candidate/decision 1対1相関とduplicate ID検出。

既存testがすべて成功することは確認したが、上記adversarial contractを保証するものではない。

## 10. 検証結果

```text
関連test: 28 passed
backend全体: 272 passed
ruff: All checks passed
summarize: runs 11 / broken 0 / safety violation 0
```

禁止import/危険参照の静的検索は0件だった。probeはすべて`tempfile.TemporaryDirectory`配下で実行し、
repository、`shadow_exports/`、外部serviceへ書込み・通信していない。

## 11. 最終判定

```text
判定: D（Phase 2E-2前に修正必須）
Phase 2E-2へ進めるか: いいえ
修正プロンプト: 必要
追加test: 必要
現状のまま統合: 危険
```

E判定としない理由は、Phase 2E-1部品が既存session、本番API/UI、broker、Private API、実注文へ未接続で、
現時点のrunへ影響していないためである。D-1〜D-4を修正・再監査するまで統合許可は出さない。

## 12. 修正タスクの最小範囲

次のタスクはPhase 2E-2統合ではなく、Phase 2E-1のlocal-only hardeningに限定する。

1. required provenance modelとfail-closed spread判定。
2. RiskPolicy/KillSwitchStateのruntime invariant validation。
3. malformed inputでも例外を漏らさないdecision生成境界。
4. typed/versioned audit event schemaと固定safety contract。
5. `shadow_exports` root containment/path traversal対策。
6. writerとsummarizerの共有validator。
7. D/C項目のadversarial offline tests。

修正後に全test、ruff、legacy summarizeを再実行し、同じprobeがすべて拒否/safety violationになることを確認する。
Private API、APIキー、broker、実注文、session統合、本番公開は修正タスクにも含めない。

## 13. ChatGPTへの引き継ぎ要約

Phase 2E-1.5監査の総合判定はD。import/dependency境界、通常のOrderCandidate固定false、pure I/O境界、
legacy summarize互換は確認できた。一方、synthetic provenance未指定でzero spreadがALLOW、malformed policyで
TypeErrorが外へ漏れる、audit writerがunsafe arbitrary dictとroot外保存を許す、summarizerが
`real_order=true` risk rowをsafety violation 0とする問題をoffline実証した。

Phase 2E-2へ進まず、まずlocal-only corrective hardening promptを作成する。D-1〜D-4と不足testを修正し、
再監査でAまたは許容可能なB/Cになるまでsession統合を禁止する。

## 14. Phase 2E-1H corrective hardening結果

2026-06-22に、Phase 2E-2統合へ進まず、`backend/app/shadow/`内のlocal-only安全基盤に限定して
D-1〜D-4のcorrective hardeningを実施した。

修正内容:

- D-1: `SpreadProvenance` enumを追加し、candidate/contextのprovenanceが
  `REAL_PUBLIC_BID_ASK`で明示されない限り`ALLOW_SHADOW`にならないようfail closed化した。
  `UNKNOWN`、`SYNTHETIC_ZERO`、`CANDLE_DERIVED`、malformed型、zero spread + provenance欠損をrejectする。
- D-2: `RiskPolicy`、`RiskContext`、`KillSwitchState`、`RiskDecision`のruntime invariantを追加し、
  `evaluate()`入口とdecision生成fallbackをfail closed化した。malformed candidate/context/policyでも例外を外へ漏らさず、
  reason付き`REJECT_SHADOW`へ倒す。
- D-3: `audit_schema.py`を追加し、event別required/allowed field、reason code、safety flags、secret/raw field禁止、
  run_id/timestamp/ID形式を検証するversioned schema validatorをwriterへ接続した。writerはtyped dataclassだけを受け付け、
  `trusted_root + run_id + event_type`から固定ファイル名で保存し、path traversal、absolute run_id、symlink escape、
  write/fsync failureを`AuditLogWriteError`にする。
- D-4: summarizerがwriterと同じschema validatorを使い、unsafe/malformed/correlation不整合のrisk rowを
  通常candidate/allow/reject件数に含めず、`safety_violations`と`invalid_risk_row_count`へ反映するようにした。
  duplicate candidate/decision、decision without candidate、candidate without decision、run_id/ID不整合も検出する。
- C-1の一部: KillSwitchStateのactive/inactive invariantをconstructorで検証する。active後のsuccessで復帰しない
  sticky behaviorは維持した。同一runでのstate所有・再初期化防止は引き続きPhase 2E-2 orchestration側の責務である。

追加検証:

```text
targeted shadow safety tests: 83 passed
backend全体: 327 passed
ruff: All checks passed
summarize: runs 11 / broken 0 / safety violation 0 / invalid risk row 0
```

今回も既存shadow session、本番API/UI、broker、Private API、APIキー、実注文、実資金には接続していない。
Phase 2E-2へは、このcorrective hardeningの再監査と明示承認まで進まない。

## 15. Phase 2E-1H再監査結果

2026-06-22の再監査ではD-1〜D-4の修正をadversarial probe、targeted test、backend全test、ruff、
legacy summarizeで確認し、総合 **B判定** とした。統合前必須修正はなく、Phase 2E-2の設計着手は可。

ただしPhase 2E-2実装は未許可である。KillSwitchStateのsession ownership、監査ログ失敗時exit 2、
session統合境界とintegration testを設計レビューし、明示承認を得るまで既存shadow sessionへ統合しない。
再監査の詳細とChatGPT引き継ぎ要約は [PHASE2E1H_REAUDIT.md](PHASE2E1H_REAUDIT.md) を参照する。
