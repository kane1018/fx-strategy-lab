# H-11 Auto Phase C/D Pre-implementation Design（docs-only / no-POST）

Date: 2026-07-15

Status: `SUPERSEDED_BY_RELAXED_V4_FAKE_ONLY_IMPLEMENTATION`

> 2026-07-15 update: profile未選定を前提とする本書はhistorical designとなった。operator選択済みの
> relaxed GMO v4と実装状態は
> `H11_V4_GMO_RELAXED_EXECUTION_PROFILE_NO_POST_20260715.md`を正とする。actual bindingは未授権。

## 1. Purpose

GMOの最終回答を待つ間に、execution profile選定後すぐ実装レビューへ入れるよう、profileに依存しない
reconciliation、unknown handling、disabled actual adapterの境界を先に固定する。

本書はPrivate API接続、credential、署名、HTTP request、actual transport、POST、resident processを
実装・許可しない。現在稼働中のcode-bound 24h fake soakのsource digestも変更しない。

契約の分担は次のとおり。

- entry / exit request-result interface: `H11_AUTO_DISABLED_ADAPTER_INTERFACE_DRAFT_NO_POST_20260715.md`
- formal M1 / freshness / clock: `H11_AUTO_FORMAL_DATA_CLOCK_CONTRACT_DRAFT_NO_POST_20260715.md`
- profile acceptance / reconciliation / unknown / implementation allowlist: 本書
- broker回答の判定表: `H11_AUTO_GMO_RESPONSE_ACCEPTANCE_TEMPLATE_NO_POST_20260715.md`

```text
phase_c_profile_selected=true_relaxed_v4
phase_d_adapter_implemented=false
fake_only_v4_state_machine_implemented=true
broker_read=false
broker_write=false
credential_read=false
actual_post=false
live_ready=false
unattended_live_supported=false
```

## 2. Phase C output contract

Phase Cの成果物は、GMO回答の文章そのものではなく、次の全fieldを埋めた1つのimmutable profileである。

```yaml
profile_schema: H11_AUTO_EXECUTION_PROFILE_V1
profile_status: OPERATOR_FROZEN_NOT_ACTIVATED
profile_label: ""
broker_label: ""
entry_mode: PENDING | IMMEDIATE
pending_expiry_contract: ""
fill_atomicity_contract: ""
protection_creation_contract: ""
protection_size_contract: ""
server_side_stop_loss: false
server_side_take_profit: false
position_specific_settlement: false
authoritative_read_after_unknown: false
ownership_contract: DEDICATED_ACCOUNT | OFFICIAL_UNIQUE_OWNERSHIP
minimum_permission_contract: ""
rate_limit_contract: ""
fee_and_holding_cost_contract: ""
official_evidence_refs: []
accepted_evidence_digest: ""
operator_approval_ref: ""
safety:
  actual_adapter_authorized: false
  broker_read_authorized: false
  broker_write_authorized: false
  credential_read_authorized: false
  actual_post_authorized: false
  live_ready: false
  unattended_live_supported: false
profile_hash: RUNNER_GENERATED_NOT_HAND_ENTERED
```

1 fieldでも空、曖昧、推測、非公式情報のみなら`PROFILE_REJECTED_OR_INCOMPLETE`とする。profile hashは
canonical serializationからtoolが生成し、operatorが手入力しない。

Implemented offline command:

```bash
cd backend

# broker/operator未決定の構造確認。profile digestは出力しない
python3 -m scripts.h11_auto_profile_freeze \
  --profile ../docs/templates/h11_auto_execution_profile.draft.json \
  --evidence ../docs/templates/h11_auto_execution_profile_evidence.draft.json \
  --mode draft

# accepted evidenceとの完全一致を要求し、review専用profile digestを生成
python3 -m scripts.h11_auto_profile_freeze \
  --profile /absolute/path/to/frozen-profile.json \
  --evidence /absolute/path/to/accepted-evidence.json \
  --mode frozen
```

`frozen`成功もadapter実装、broker read/write、credential、POST、activation、live readinessを許可しない。
生成されたprofile digestはgeneration manifestの`entry.execution_profile_hash`へ完全一致で固定する。

3成果物を個別に検証した後、相互の取り違えを次のoffline commandで拒否する。

```bash
cd backend
python3 -m scripts.h11_auto_artifact_bundle_verify \
  --manifest /absolute/path/to/frozen-generation-manifest.json \
  --profile /absolute/path/to/frozen-execution-profile.json \
  --evidence /absolute/path/to/accepted-evidence.json
```

bundle verifierはprofile label、profile digest、entry mode、専用口座ownership、evidence digestを完全一致確認し、
一致時も`BUNDLE_COHERENT_NOT_ACTIVATED`だけを返す。bundle digestは承認・レビュー対象の識別子であり、
adapter permission、POST permission、live readinessを生成しない。

## 3. Non-negotiable profile gate

```text
(short_pending_expiry OR no_pending_entry)
AND (full_fill_or_none OR protection_size_atomically_matches_actual_fill)
AND server_side_stop_loss
AND position_specific_settlement
AND authoritative_read_after_unknown
AND no_excess_order_can_reverse_position
AND ownership_isolation
```

次は代替として認めない。

- 30取引日注文をclient timerで後からcancelする
- 約定後に別POSTでstopを置き、一時的な未保護建玉を許容する
- 部分約定を検知してから保護数量を追従させる
- 反対方向の新規注文をgeneric closeとして使う
- timeout後に同一注文を再送する
- operatorの目視をatomic protectionの代わりにする

## 4. Future package boundary

profile選定・別授権後の候補構成。現在は作成しない。

```text
app/h11_auto/
  actual_boundary/
    contracts.py                  # pure typed contracts only
    broker_snapshot.py            # sanitized read model
    reconciler.py                 # pure decision function
    disabled_adapter.py           # always refusing; no network
    profile.py                    # immutable selected profile
    result_projection.py          # safe labels only
```

Phase Dでは`httpx`、Keychain、GMO client、HMAC signing、実endpoint定数をこのpackageへimportしない。
profile-specific request mappingやfake HTTP clientを追加する場合も、別のPhase D実装授権とsource isolation reviewを
必要とする。

`app.live_verification`のStep 6G actual POST capable modulesをimportしない。既存の実POST関数へのbridge、
delegate、factory、generic allow booleanを作らない。

## 5. Sanitized broker snapshot contract

将来のreconcilerへ渡してよいのは、transport内でsanitize済みの次の情報だけとする。

```yaml
observed_at_utc: ""
snapshot_fresh: false
account_scope: DEDICATED_AUTO_ACCOUNT | EXCLUSIVE_AUTO_WINDOW
open_position_count: 0
active_order_count: 0
owned_position_state: NONE | EXACTLY_ONE | AMBIGUOUS | FOREIGN_PRESENT
owned_entry_state: NONE | PENDING | PARTIAL | FILLED | UNKNOWN
protection_state: NONE | EXACT_MATCH | MISSING | UNDERSIZED | OVERSIZED | UNKNOWN
settlement_state: NONE | PENDING | FILLED | UNKNOWN
ownership_ref_present: false
```

通常log、safe report、UIへ出さないもの:

```text
raw response
raw order / execution / position ID
API key / secret / signature / headers
price / quantity
request body
credential metadata
```

transport内部でownership照合に必要な実IDは、local専用keyでopaque refへ変換してから境界を越える。
専用口座profileでは、外部建玉または外部注文が1件でもあれば`FOREIGN_PRESENT`として扱う。

## 6. Pure reconciliation decision

reconcilerはbroker readを行わず、local stateとsanitized snapshotを受け取って次のsafe decisionだけを返す。

```text
ARMED_FLAT
OBSERVE_ENTRY_PENDING_NO_RESEND
POSITION_PROTECTED_CONFIRMED
OBSERVE_EXIT_PENDING_NO_RESEND
FLAT_RECONCILED
HALT_STALE_READ
HALT_FOREIGN_STATE
HALT_ACTIVE_ORDER_CONFLICT
HALT_PARTIAL_FILL
HALT_PROTECTION_MISSING
HALT_PROTECTION_UNDERSIZED
HALT_PROTECTION_OVERSIZED
HALT_OWNERSHIP_AMBIGUOUS
HALT_RESULT_UNKNOWN
HALT_LOCAL_BROKER_MISMATCH
```

reconcilerのreturn値に`actual_post_allowed`、`retry_allowed`、`can_resume`を持たせない。write可否は
reconciliation単体から生成せず、fresh runtime gate全体と別current-turn activation境界で扱う。

## 7. Reconciliation timing

actual候補では次の各点でfresh snapshotを要求する。

1. process boot
2. ARMED遷移前
3. entry intent作成直前
4. entry attempt直後
5. protected position監視中の固定間隔
6. Private event stream再接続後
7. exit intent作成直前
8. exit attempt直後
9. process restart後

read-only GETの一時的失敗にbounded read retryを設けるかは、rate limitと公式guidance確認後に別policyで固定する。
ただしread retryはwrite retryではない。fresh snapshotを得られない間、新規writeは0件とする。

## 8. Unknown result table

| Situation | Required action | Forbidden action |
| --- | --- | --- |
| entry送信前にlocal failure | attempt未開始ならHALT/abort | profileやsignalを変えて続行 |
| entry attempt後にtimeout/connection loss | intentをUNKNOWNとして永続化しfresh readへ | entry repost |
| broker readでpending entry一致 | observe only | duplicate entry |
| broker readでprotected position一致 | position監視へ | protection再作成 |
| broker readでflat | 当日attempt消化済みでHALT/終了 | 同日再entry |
| partial fill | protectionがatomic exactでない限りHALT | client追従POSTで穴埋め |
| exit attempt後にunknown、position残存 | server protectionを維持してHALT | exit repost / generic opposite |
| exit attempt後にflat確認 | FLAT_RECONCILEDとして終了 | second settlement |
| snapshot stale / ambiguous | HALT | 成功・失敗の推定 |

unknownが後からbroker eventで解消しても、すでに消費したattemptを戻さない。late eventはstate説明には使えるが、
新しいwrite permissionを生成しない。

## 9. Disabled adapter contract

Phase D最初のadapterは常にrefusingである。

```text
entry_send_available=false
settlement_send_available=false
cancel_available=false
change_available=false
credential_source_bound=false
network_client_bound=false
actual_post_count=0
```

将来のpure mapping testはfake credential labelとfake clientだけを使い、実credential presenceや実Keychain itemを
参照しない。refusing adapterをproduction adapterへ切り替えるconstructor flag、env、config、CLI optionは
追加しない。

## 10. Intent-first persistence order

```text
1. generation/profile/policy digest確認
2. fresh reconciliation確認
3. risk/dead-man/notification gate確認
4. intent INSERT
5. attempt CAS 0 -> 1
6. sender call
7. sanitized result state INSERT
8. fresh reconciliation
9. state transitionまたはpersistent HALT
```

sender callより前にintentとattemptをdurable commitする。process crashでbroker側結果が不明でも、restart後に
attemptを0へ戻さない。

## 11. Required fake-only tests after authorization

### Contract tests

- exact selected profile hash and immutable metadata
- unknown / extra field rejection
- bool-as-int、NaN、Inf、negative count、future timestamp rejection
- raw ID、price、quantity、credential field rejection
- symlink / non-regular state path rejection

### Reconciliation matrix

- local flat + broker flat
- local flat + foreign position/order
- entry pending + broker pending/protected/flat/unknown
- protected local position + missing/under/over/exact protection
- exit pending + position present/flat/unknown
- stale snapshot、clock skew、ownership ambiguity

### Process fault tests

- crash before intent
- crash after intent before attempt
- crash after attempt before result
- crash after protected confirmation
- crash after exit attempt
- delayed result and late event
- duplicate supervisor launch
- notification acknowledgement loss

### Isolation tests

```text
network_call_count=0
credential_read_count=0
actual_post_count=0
broker_write_count=0
live_verification_import_count=0
generic_allow_bridge_count=0
```

## 12. Implementation allowlist for a future Phase D task

別授権時も最初に触れてよい範囲を限定する。

```text
backend/app/h11_auto/actual_boundary/**
backend/app/tests/h11_auto/test_actual_boundary_*.py
docs/H11_AUTO_PHASE_D_*_NO_POST_*.md
```

触らない範囲:

```text
AGENTS.md
backend/app/main_readonly.py
backend/app/live_verification/**
backend/app/brokers/** actual transport
manual UI ledger / settlement sync
Keychain credential modules
production process/supervisor config
```

## 13. Phase D acceptance gate

次をすべて満たした場合だけ、`DISABLED_ADAPTER_IMPLEMENTED_NO_POST`と表現できる。

```text
official_profile_complete=true
profile_hash_frozen=true
refusing_default=true
network_client_bound=false
credential_source_bound=false
actual_transport_bound=false
actual_post_count=0
broker_read_count=0
broker_write_count=0
source_isolation_tests=passed
fault_matrix=passed
ruff=passed
git_diff_check=passed
independent_safety_review=clear
```

このgateを通過してもactual readiness、live readiness、unattended support、POST permissionはfalseのままである。

## 14. Current next action

現在は次だけを行う。

1. code-bound 24h fake soakを完走させる。
2. operator decision sheetのformal horizon / risk / dead-man / account / host項目を検討する。
3. GMO回答をsafe JSONへ転記し、`scripts.h11_auto_profile_acceptance`と
   `H11_AUTO_GMO_RESPONSE_ACCEPTANCE_TEMPLATE_NO_POST_20260715.md`で判定する。
4. clearしたevidenceとoperator承認済みprofileを`scripts.h11_auto_profile_freeze`で完全一致固定する。
5. frozen generation manifestを作成し、`scripts.h11_auto_artifact_bundle_verify`で3成果物の整合を確認する。
6. bundleがclearした場合だけ、別Phase D実装授権を依頼する。

profileがclearしない場合はGMO向けadapterを作らず、注文方式・strategy contract・brokerのいずれを変更するかを
別Stepで選択する。

## 15. Safety restatement

```text
actual_post=false
broker_read=false
broker_write=false
credential_read=false
network_access_added=false
resident_process_added=false
cron=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
