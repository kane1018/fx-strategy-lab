# E1 Shadow Full-Auto Engine Runbook（no-POST）

Date: 2026-07-10

Applies to: `backend/app/shadow/e1/`

Status: `E1_IMPLEMENTED_NOT_GATE_PASSED`

本書は E1 の local-only / offline / bounded 検証手順である。
**live、paper broker、Public API、Private API、credential、HTTP POST の運用手順ではない。**

E1 にはユーザー向け CLI、daemon、cron、scheduler、常駐 process を用意しない。
「full-auto」は、明示的に起動された1回の有限 offline run 内で、decision→risk gate→
virtual entry→virtual settlement→reconcile→audit が人手の per-event 承認なしに進むことを意味する。

## 1. 運用者が守る境界

- synthetic fixture または既存 local data のみを使う。
- Public / Private API、broker、HTTP、socket、credential、env に切り替えない。
- E1 の失敗を `.env`、API key、live transport、retry で回避しない。
- `backend/shadow_exports/` 配下の journal / state / audit / evidence を commit しない。
- `analysis_exports/` へ変換・コピーしない。
- E1 結果を performance proof、live readiness、E2/E3 permission と表現しない。
- halt した run を再利用しない。自動 reset / journal reset / state rewrite は禁止する。

## 2. 開始前確認

repo ルートで次を確認する。

```bash
cd /Users/naoikansui/Desktop/トレード
git branch --show-current
git status --short
git check-ignore backend/shadow_exports
git ls-files backend/shadow_exports
```

確認項目:

- [ ] branch / HEAD / working tree の状態を把握した
- [ ] `backend/shadow_exports/` が ignore 対象である
- [ ] `backend/shadow_exports/` 配下の tracked file がない
- [ ] E1 focused tests が green
- [ ] E1 import/source isolation test が green
- [ ] `FrozenHypothesisRegistry` と `E1Policy.config_hash` が新規 run 用に確定している
- [ ] 入力が synthetic または既存 local data である
- [ ] 出力 root が `backend/shadow_exports/e1/` 配下である
- [ ] 前 run の acknowledgement / token / halt state を再利用していない

credential presence や env 一覧は E1 の開始条件ではない。`env` / `printenv` /
`.env` 表示は行わない。

## 3. 有限 run の起動モデル

E1 は Python library / test harness から明示的に1回ずつ呼び出す。
シェルから engine を常駐起動する command は持たない。

1回の run で事前に固定するもの:

- run reference
- frozen hypothesis spec
- frozen risk policy
- canonical `config_hash`（registry / policy / labels / engine contractを含む）
- bounded event list / maximum event count
- injected clock
- fault injection plan（必要な場合のみ）
- trusted output root

run 開始後に spec、policy、event limit、fault plan を書き換えない。

## 4. 正常 lifecycle

### 4.1 Boot

1. entry forbidden で起動する。
2. output root の containment を確認する。
3. frozen registry / policy / `config_hash` を確認する。
4. journal / persistent venue state / audit を reconcile する。
5. fresh run の空状態、または restart run の完全一致を確認する。
6. restart の場合は explicit acknowledgement 完了まで entry forbidden を維持する。

### 4.2 Decision / risk gate

1. hypothesis event を `HYPOTHESIS_*` として記録する。
2. `HYPOTHESIS_NO_ACTION` は記録のみで終了する。
3. engine candidate はそれ自体で execution permission を持たない。
4. risk gate が position / lifecycle / protective-stop由来prospective budget / kill /
   dead-man / config hash を検証する。
5. 全条件を満たす場合だけ single-use TTL `ShadowGateToken` を発行する。

### 4.3 Virtual execution

1. executor は `ShadowGateToken` 以外の入力を拒否する。
2. token の run / action / config / `intent_digest` / TTL / unused を検証する。
3. intent journal へ typed intent を append する。
4. flush + `fsync` 完了後にのみ token を消費し virtual venue を変更する。
5. venue state を journal と別に永続化する。
6. terminal outcome と safe audit event を append する。
7. entry / settlement のどちらも retry しない。

### 4.4 Settlement

- virtual position に対応する internal reference を exact match する。
- position-specific settlement のみを1回試行する。
- generic close、反対方向 entry、position 無指定の close は使えない。
- accepted なら flat state と outcome を永続化する。
- rejected / timeout / unknown なら再試行せず halt / reconcile-required にする。

### 4.5 Normal completion

- bounded event list の終了後、journal / venue state / audit を最終 reconcile する。
- pending intent、position mismatch、spec drift、cardinality violation がないことを確認する。
- run summary と gate evidence は safe count / safe category / boolean のみで作る。
- normal completion でも E2 へ自動昇格しない。

## 5. Halt 事象と対応

| 事象 | 即時動作 | 再開条件 |
| --- | --- | --- |
| token expired / reused / mismatch | virtual effect 前に拒否、sticky halt | 原因修正後の新 run + review |
| spec hash mismatch | entry禁止、sticky halt | 新 spec の別 run、旧証拠と分離 |
| journal append / fsync failure | effect 0、sticky halt | storage 原因解消後の新 run |
| venue state persistence failure | unknown + reconcile-required + halt | boot reconcile + explicit ack（match時のみ） |
| reconcile mismatch | entry禁止、safe escalation、halt | 自動修復禁止、post-mortem + review |
| kill / dead-man | one-shot virtual flatten attempt → halt | 同 run は再開不可 |
| flatten rejected / timeout / unknown | retryせず halt | 新 run 前に post-mortem |
| safety / budget breach | 新規 entry禁止、halt | review window まで gate fail |
| forbidden path / import / network surface | 実行しない | 実装修正 + isolation test |

halted instance に reset method を追加しない。run directory の削除や journal 編集で
「直った」ことにしない。

## 6. Restart / recovery 手順

1. 元 process を resume させず、新 engine instance を boot-blocked で構築する。
2. 対象 run の frozen `config_hash` を渡す。
3. journal / venue state / audit を read-only reconcile する。
4. pending intent の効果を「未実行」と推測して再実行しない。
5. match した場合は reconcile generation に対する new acknowledgement を明示的に作る。
6. acknowledgement 完全一致後にのみ lifecycle を再開可能にする。
7. mismatch / corrupt / truncated / duplicate は halt のまま post-mortem へ回す。

acknowledgement は current reconcile generation 専用で、banking / reuse しない。

## 7. Kill / dead-man 演習

### Kill exercise

- flat 状態で発火: entry 0、settlement 0、halt 1。
- one-position 状態で発火: position-specific settlement attempt 1、その後 halt。
- settlement unknown で発火: attempt 1、retry 0、halt。
- unresolved / reconcile-required 中に発火: settlement 0のまま activation / alert / halt を
  durable記録し、restart後もresumeしない。

ゲート証拠の成功件数に算入するのは、one-position→position-specific settlement 1回→
直接成功→flat→haltの完全なexerciseだけである。flat / unknown / crash recovery は安全経路の
test coverageには含めるが、成功flatten件数には含めない。

### Dead-man exercise

- injected clock を heartbeat deadline まで進める。sleep は使わない。
- deadline 前は発火せず、deadline 到達 / 超過で fail-closed 発火すること。
- one-position なら one-shot position-specific virtual settlement 後に halt すること。
- acknowledgement の無い heartbeat 復帰で自動 resume しないこと。

ゲート証拠に算入するには、上記と同じ成功flatten契約を満たすdead-man exerciseを3回以上行う。

## 8. Fault injection 運用

次の category を deterministic にそれぞれ5回以上実行する。

- timeout
- unknown result
- synthetic network-error category
- crash after durable intent / before virtual apply
- crash after virtual apply / before terminal outcome
- restart reconcile

各 injection で次を確認する。

- [ ] retry / repost / second attempt = 0
- [ ] duplicate virtual effect = 0
- [ ] pending / unknown 時の新規 entry = blocked
- [ ] journal は virtual effect 前に durable
- [ ] consumed token / durable intent / execution attempt の cardinality が一致
- [ ] restart は reconcile-first
- [ ] match でも explicit ack 前の resume = blocked
- [ ] actual POST / network / credential / env read = 0

fault suite の batch size は事前固定し、failure を取り消すための自動再実行を行わない。

## 9. E1 gate evidence の蓄積

E1 実装検証と E1→E2 運用ゲートは別物である。

### 実装検証で確認するもの

- contract / isolation / token / journal / venue / reconcile / kill / dead-man / fault の test
- bounded synthetic scenarios
- no-POST と cardinality invariants

### 運用ゲートで追加で必要なもの

- journal `recorded_at` 実績で2週間かつ、event記録のある営業日10日以上
- virtual entry 100件以上
- virtual settlement 100件以上
- NO_ACTION 300件以上
- reconcile mismatch 0
- fault category ごと5回以上全件成功
- kill / dead-man 各3回以上全件成功
- safety violation 0
- High incident 0 / Medium incident 2件以下かつ全件 post-mortem 完了

加速 clock、unit test 実行日、1日内の大量 synthetic event を稼働期間の代替にしない。
NO_ACTION は frozen `E1Policy` / registry と canonical decision digest が一致する行だけを数える。
fault 件数も prepared→started→uncertain/crash→reconcile→handled の一意な対応がある行だけを数える。
現状は `E1_IMPLEMENTED_NOT_GATE_PASSED` であり、ゲート証拠が揃うまで E2 に進まない。

## 10. 生成物の確認

E1 が生成するすべての永続物は次の下に置く。

```text
backend/shadow_exports/e1/<run-reference>/
```

含まれ得る artifact role:

- frozen manifest / config hash record
- append-only intent journal
- persistent virtual venue state
- typed safe audit log
- reconciliation report
- gate evidence summary

ファイル名や配置をテストで固定する場合も、trusted root から外へ書かない。

run 後の確認:

```bash
cd /Users/naoikansui/Desktop/トレード
git status --short
git check-ignore backend/shadow_exports
git ls-files backend/shadow_exports
```

`git ls-files backend/shadow_exports` は空であること。生成物を `git add -f` しない。

## 11. 実装後の focused validation

`backend` で、実在する test file を確認してから次を実行する。

```bash
cd /Users/naoikansui/Desktop/トレード/backend
python3 -m pytest -q app/tests/test_e1_shadow_*_no_post.py
python3 -m pytest -q \
  app/tests/test_shadow_risk.py \
  app/tests/test_shadow_audit.py \
  app/tests/test_shadow_session.py \
  app/tests/test_shadow_session_risk_integration.py \
  app/tests/test_shadow_trading.py \
  app/tests/test_shadow_summary.py \
  app/tests/test_gmo_fx_broker_live_verification_isolation.py
python3 -m ruff check .
```

repo ルートで最後に次を確認する。

```bash
cd /Users/naoikansui/Desktop/トレード
git diff --check
git status --short
```

テストが green でも、経過期間を含む E1→E2 gate 通過として報告しない。

## 12. 報告テンプレート

```yaml
case: E1_SHADOW_FULL_AUTO_ENGINE_NO_POST
status: E1_IMPLEMENTED_NOT_GATE_PASSED
purpose: execution_infrastructure_validation_only
config_hash_match: true_or_false
boot_reconcile_status: SAFE_LABEL_ONLY
restart_ack_status: SAFE_LABEL_ONLY
virtual_entry_count: SAFE_COUNT_ONLY
virtual_settlement_count: SAFE_COUNT_ONLY
no_action_count: SAFE_COUNT_ONLY
reconcile_mismatch_count: SAFE_COUNT_ONLY
kill_exercise_count: SAFE_COUNT_ONLY
deadman_exercise_count: SAFE_COUNT_ONLY
fault_matrix_status: SAFE_LABEL_ONLY
safety_violation_count: SAFE_COUNT_ONLY
actual_post_permission: false
actual_post_count: 0
network_used: false
credential_env_read: false
performance_proof_status: false
live_ready: false
e2_allowed: false
e3_allowed: false
generated_artifacts_committed: false
```

## 13. 停止条件

以下のいずれかで当該 run を終了し、自動再開しない。

- reconcile mismatch 1件
- safety violation 1件
- spec hash mismatch 1件
- token reuse / duplicate effect 1件
- retry / second attempt 1件
- journal-before-effect 違反 1件
- restart acknowledgement なしの resume 1件
- output root escape / unsafe field 1件
- network / API / broker / credential / env / POST surface の検出
- 少しでも E1 no-POST 境界を保証できない場合

停止後は E2 / E3 へ進まず、原因・影響・修正方針を別の review で扱う。
