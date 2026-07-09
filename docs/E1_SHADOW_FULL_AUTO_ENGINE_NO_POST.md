# E1 Shadow Full-Auto Engine 設計契約（no-POST）

Date: 2026-07-10

Step: `E1_SHADOW_FULL_AUTO_ENGINE_NO_POST`

Case: `TWO_TRACK_MODEL_INFRA_VALIDATION_FIRST`

Current status: `E1_IMPLEMENTED_NOT_GATE_PASSED`

## 1. 一言結論

E1 は、仮説の収益性を証明する場ではなく、**offline の virtual venue 上で実行基盤の
安全契約を検証する local-only の有限 full-auto shadow engine** である。

`E1_IMPLEMENTED_NOT_GATE_PASSED` は「E1 用の実装境界が用意された」ことだけを示す。
E1→E2 ゲートの稼働期間・イベント数・フォールト注入証拠は未充足であり、
E2 / E3 / live / performance への進行資格や許可を意味しない。

## 2. 二軌道モデル上の位置づけ

### インフラ軌道

- E1: shadow full-auto（本 Step）
- E2: paper / fake transport の実行経路検証（**E1 ゲート通過後の別 Step**）
- E3: execution validation 専用の supervised live research（**本 Step の対象外**）

### 仮説軌道

- すべての仮説は事前登録し、E1 / E2 のみで評価する。
- E1 の完了や結果から、edge、performance proof、live readiness を導出しない。
- 新しい仮説は常に E1 から開始し、稼働中の spec を変更しない。

## 3. 安全状態の固定

| 項目 | E1 での固定値 |
| --- | --- |
| actual POST permission | `false` |
| entry POST / settlement POST | `false / false` |
| HTTP / network | 使用しない |
| Public API / Private API | 使用しない |
| broker / live transport | 使用しない |
| credential / env / `.env` | 読まない・要求しない |
| real balance / position / order / execution | 取得しない |
| `app.main_readonly:app` / public UI | 変更・公開しない |
| performance proof | `false` |
| live ready | `false` |
| unattended live supported | `false` |
| E2 / E3 promotion | `false` |

## 4. 実装境界

E1 専用コードは `backend/app/shadow/e1/` に隔離する。内訳は
`contracts.py`（frozen registry / policy / label / token）、
`persistence.py`（intent journal / virtual venue state）、
`engine.py`（risk gate / executor / kill / dead-man / reconcile）、
`qualification.py`（固定 E1 gate / multi-run evidence bundle）である。既存の
`ShadowTrader` / `VirtualPosition.apply_fill()` / `run_shadow_session()` はそのまま保ち、
E1 executor として再利用しない。

E1 package は次を import または呼び出さない。

- `app.live_verification` / `live_order_once`
- `app.brokers`
- `app.security.real_broker_post_hard_guard`
- `app.shadow.gmo_public`
- HTTP / socket / HMAC / signing library
- environment / dotenv / settings loader
- subprocess / daemon / scheduler / background thread

`backend/app/shadow/e1/` に実 POST 可能経路を import しないことは、専用の
source/import isolation test で固定する。`threading.RLock` は同一 process 内の mutex としてのみ
使用し、`Thread` / `Timer` / worker の生成は isolation test で禁止する。stdlib import も
明示 allowlist 方式とし、別の network client が紛れ込まないようにする。

## 5. 全体フロー

```text
FrozenHypothesisRegistry
        |
        v
HYPOTHESIS_* decision (data only, zero permission)
        |
        v
ENGINE_* candidate (still zero permission)
        |
        v
fixed risk gate + stage/prospective-budget/kill checks
        |
        v
intent-digest-bound / single-use TTL ShadowGateToken
        |
        v
append intent -> flush -> fsync
        |
        v
position-specific virtual venue operation
        |
        v
separate persistent virtual venue state
        |
        v
typed safe audit + reconciliation + gate evidence
```

ラベルはデータであり、権限ではない。executor は label / string / hypothesis decision /
risk decision を直接受け取らず、適法な `ShadowGateToken` のみを受理する。

## 6. 凍結 label namespace

### Hypothesis labels

- `HYPOTHESIS_BUY_CANDIDATE`
- `HYPOTHESIS_SELL_CANDIDATE`
- `HYPOTHESIS_HOLD_CANDIDATE`
- `HYPOTHESIS_NO_ACTION`

### Engine labels

- `ENGINE_ENTRY_BUY_CANDIDATE`
- `ENGINE_ENTRY_SELL_CANDIDATE`
- `ENGINE_EXIT_CANDIDATE`
- `ENGINE_SETTLEMENT_CANDIDATE`
- `ENGINE_NO_ACTION`

`ENTRY_BUY` / `ENTRY_SELL` / `HOLD` などの operator 向け safe label は E1 入力に使用しない。
`HYPOTHESIS_NO_ACTION` / `ENGINE_NO_ACTION` は記録のみで終端し、token を発行しない。

## 7. Frozen registry / policy / spec hash

- `FrozenHypothesisRegistry`、risk policy、label schema、engine contract version を
  canonical serialization する。
- canonical bytes から `E1Policy.config_hash`（frozen spec hash）を作り、token / intent /
  venue state / audit / gate evidence の
  全イベントに刻印する。
- run 開始後の policy / spec 変更は許可しない。hash 不一致は sticky halt とする。
- spec 変更は別 run / 別 review window とし、旧証拠と合算しない。
- config 値はコード上の frozen policy か明示的な local test fixture だけから供給し、
  env で解除・緩和しない。

## 8. ShadowGateToken

`ShadowGateToken` は E1 virtual execution 専用の capability であり、少なくとも次に結び付く。

- run reference
- candidate / intent correlation reference
- `config_hash`（registry / policy / label schema / engine contract versionを含む）
- canonical `intent_digest`
- exact engine action
- issue time / expiry time
- single-use token reference
- E1 stage marker

契約:

1. public API は `build_e1_shadow_engine(...)` → risk gate の1経路だけで token を発行する。
2. token の TTL は frozen policy で固定し、synthetic market timestamp とは分離した
   trusted/injected clock で検証する。expiry exact boundary でも失効する。
3. expired / reused / wrong-run / wrong-action / wrong-spec token は virtual state 変更前に拒否する。
4. token は exact `intent_digest` に束縛し、risk check 後のunits/side/stop等の差し替えを拒否する。
5. token 消費は durable intent と1対1で相関させる。
6. token から real broker hard guard の `allow` を生成する bridge は作らない。
7. token は live / paper / broker executor と互換にしない。

## 9. Virtual venue 制約

- 同時 virtual position は最大1。
- flat の場合だけ entry できる。
- 同方向の追加、反対方向への flip、hedge、マーチンゲール、grid、ナンピンを拒否する。
- settlement は E1 内部の virtual position reference を指定する経路だけを持つ。
- venue mutation method は public API に出さず、executor 内部の mutation capability が必須。
- generic close / opposite order close の public method を作らない。「使わない」ではなく
  「存在しない」ことを test で固定する。
- virtual position reference は E1 内部の相関用であり、broker / order / execution /
  account ID ではない。
- executor は hypothesis を再計算せず、token に結び付いた exact action だけを実行する。

## 10. Intent journal と virtual venue state

### Intent journal

- append-only の typed record とする。
- trusted output root 配下だけへ書き込む。path traversal / symlink escape を拒否する。
- public factory は safe local run id を path 構築前に検証し、resolved run root が
  `shadow_exports/e1` 直下であることを確認する。
- virtual venue の state mutation **前**に intent を appendし、flush + `fsync` 完了を確認する。
- single-writer file lock、同一process mutex、disk snapshot vs in-memory snapshot の一致確認を
  毎appendで行う。初回file作成時は親directoryも`fsync`する。
- append / flush / fsync 失敗は、virtual effect を発生させず sticky halt にする。
- 既存 record の上書き、削除、reset、自動修復を行わない。

### Persistent virtual venue state

- journal とは別ファイル / 別責務で永続化する。
- journal を venue state の代わりにせず、boot reconcile で両方を照合する。
- state の永続化失敗は outcome を推測せず、unknown / reconcile-required で停止する。
- venue state も single-writer lock を使い、temporary path のsymlinkを拒否する。
- temporary file はfile `fsync`後にatomic replaceし、親directoryを`fsync`してから
  in-memory stateを更新する。

### 生成物の配置

E1 の journal、venue state、audit、gate evidence はすべて次の trusted root 配下に置く。

```text
backend/shadow_exports/e1/<run-reference>/
```

`backend/shadow_exports/` は local 生成物用であり、journal / state / JSONL / summary /
gate evidence を **git add / commit / push しない**。

## 11. Boot reconcile-first / restart protocol

restart は resume ではない。新しい process / engine instance は必ず次の順で進む。

1. 新規 entry を禁止した boot-blocked 状態で起動する。
2. frozen registry / policy / `config_hash` を確認する。
3. intent journal / intent digest / consumed token evidence / persistent virtual venue state /
   audit を照合する。
4. corrupt / truncated / duplicate / missing terminal outcome / state mismatch を検出する。
5. 不一致なら sticky halt + safe escalation とし、自動修復・自動再送しない。
6. 完全一致でも自動再開せず、その reconcile generation に対する明示的な
   local restart acknowledgement を必須とする。
7. acknowledgement 検証後にのみ新規 entry を再許可する。

restart acknowledgement は E1 内の local lifecycle 確認であり、live approval、POST permission、
hard guard allow ではない。過去 run の acknowledgement は再利用できない。

## 12. Sticky kill / dead-man semantics

kill と dead-man は sticky であり、同一 run 内に reset 経路を持たない。

### Flat の場合

1. 新規 entry を即時禁止する。
2. halt し、以後の virtual execution を受理しない。

### Virtual position が1件ある場合

1. 新規 entry を即時禁止する。
2. position-specific virtual settlement を **1回だけ** 試行する。
3. 成功なら flat を永続化し、完全 halt する。
4. rejected / timeout / unknown / persistence failure なら再試行せず、safe critical event を記録して
   完全 halt する。

KILL中のcrashからrestartした場合も再settlementしない。reconcile後にpositionが残る場合は
safe critical escalationを追記し、position有りのままでもdurableなsticky haltを確定する。
すでにhalt済みのrunでは、後発のkill/dead-manが追加試行を発生させない。

dead-man は injected clock と explicit heartbeat event で検証する。E1 で background timer、
sleep loop、external notifier を実装しない。通知は safe in-memory / local audit event のみとする。

## 13. Fixed risk policy

E1 では少なくとも次を fail-closed で固定する。

- maximum concurrent positions: 1
- protective stop から算出した prospective per-trade / daily / weekly virtual loss
- maximum entry attempts per cycle: 1
- maximum settlement attempts per position: 1
- retry / repost / second attempt: false
- scale-in / flip / hedge: false
- martingale / grid / nanpin: false
- generic close / generic opposite close: unavailable
- unknown market / data / spread / event / budget / lifecycle state: no action or halt
- kill active / dead-man expired / reconcile incomplete: entry forbidden
- spec hash mismatch: halt
- journal or venue-state durability failure: halt
- budget reload / same-run reset / win-based size-up: unavailable

E1 の「budget」は virtual safety counter であり、実資金の損失許容や live budget ではない。

## 14. Bounded fault injection

フォールト注入は deterministic fixture + injected clock / injected failure point で行う。
実 network 障害を発生させず、無限 loop / sleep / daemon / cron を使用しない。

| E1 fault category | 最低回数 | 必須期待結果 |
| --- | ---: | --- |
| timeout | 5 | no retry、pending/unknown のまま entry block、reconcile required |
| unknown result | 5 | outcome を推測せず halt、duplicate effect 0 |
| synthetic network-error category | 5 | network は使わず同等の failure contract を検証 |
| crash after durable intent / before virtual apply | 5 | journal の pending intent を boot reconcile が検出 |
| crash after virtual apply / before terminal outcome | 5 | venue state から effect を照合し、再実行しない |
| restart reconcile | 5 | matchでも explicit ack まで entry block、mismatch は halt |

旧 gate 文言の `crash-mid-POST` は E1 では POST を意味しない。上記の
`crash after durable intent` / `crash after virtual apply` を E1 対応の検証とし、
`actual_post_count=0` を独立に固定する。

kill switch と dead-man はそれぞれ最低3回発火させ、全件が one-shot flatten / halt 契約に
従うことを確認する。

## 15. Audit cardinality / safe schema

E1 監査は「消費」「durable intent」「試行」「state effect」を区別する。

```text
consumed_token_count
  = durable_intent_count
  = virtual_execution_attempt_count

virtual_state_effect_count
  <= virtual_execution_attempt_count

actual_POST_count
  = 0
```

資格判定は record 数だけでなく、run / intent / intent_digest / token / action / before-state /
planned-state を lifecycle 単位で完全照合する。duplicate/fabricated terminal row は件数に加えず、
cardinality violation とする。accepted baseline event では intent / attempt / effect / terminal outcome が
1対1である。fault 注入時の
pending / unknown を無理に accepted と数えず、reconcile-required として別集計する。
`FAULT_HANDLED` は単独行を数えず、同じintent/tokenに対する
prepared→started→uncertain/crash→reconcile→handledの一意な順序付き証拠だけを数える。
`ENGINE_NO_ACTION_TERMINAL` もfrozen hypothesis identityとcanonical decision digestが一致する行だけを
数え、任意のラベル行による件数水増しをgate evidenceにしない。

audit / render / gate evidence に次を含めない。

- credential / secret / token value / header / signature
- raw request / raw response / broker response / error body
- account / broker order / execution / position ID
- real balance / quantity / price / PnL
- hard guard allow または live permission と読める field

## 16. E1→E2 stage gate

ゲートは review window でのみ判定し、前倒し昇格・自動昇格しない。threshold はコード上で固定し、
caller による緩和引数を持たない。sticky kill / dead-man演習は、同一`config_hash`かつ一意なrun idの
複数journalと同じ frozen `E1Policy` を `summarize_e1_bundle` で集約する。policy は
NO_ACTION evidence の hypothesis identity が frozen registry に登録済みであることも検証する。

| 条件 | 必須基準 |
| --- | --- |
| 最低稼働 | 2週間 **かつ** 10営業日以上 |
| virtual entry | 100件以上 |
| virtual settlement | 100件以上 |
| NO_ACTION | 300件以上 |
| reconcile mismatch | 0件 |
| fault injection | 必須 category ごとに5回以上、全件規定通り |
| kill / dead-man | 各3回以上、全件成功 |
| safety violation | 0件 |
| incident | High=0、Medium≤2かつ全件 post-mortem 完了 |

日数はcaller入力やsynthetic market timestampではなく、journalがappend時に自動記録する
`recorded_at`の最初/最後と、実際にeventが記録された平日数から算出する。
単体 test、加速時計、synthetic batch を「2週間 / 10営業日」の代替にしない。
kill / dead-man のgate件数には、position有り→position-specific settlement 1回→直接成功→flat→haltの
完全なexerciseだけを算入する。flat発火、unknown、crash/reconcile recoveryは安全経路の試験には使えるが、
成功flatten件数には算入しない。
現在は validation / operational evidence 蓄積前のため、状態は必ず
`E1_IMPLEMENTED_NOT_GATE_PASSED` とする。

## 17. 自動降格・停止

次のいずれか1件で gate evidence は fail とし、原因の post-mortem と review window まで
再判定しない。

- reconcile mismatch
- virtual budget breach（上限到達は正常停止、超過が breach）
- safety flag violation
- retry / second-attempt / token reuse
- spec hash drift
- journal-before-effect 違反
- restart acknowledgement なしの resume
- forbidden import / network / env / broker / POST 経路の検出

## 18. この Step が証明しないこと

- 仮説の edge / 収益性 / 統計的優位性
- live execution quality
- broker の idempotency / settlement / partial fill / server-side SL 能力
- credential / permission / IP binding / account mode
- E2 / E3 readiness
- unattended live safety
- actual POST permission

API 能力は
[`API_CAPABILITY_SHEET_SANITIZED_NO_POST.md`](API_CAPABILITY_SHEET_SANITIZED_NO_POST.md)
へ operator が別途記入する。E1 engine はその sheet を読み込まず、実行許可に使わない。

## 19. 最終 safe summary

```yaml
step: E1_SHADOW_FULL_AUTO_ENGINE_NO_POST
status: E1_IMPLEMENTED_NOT_GATE_PASSED
purpose: execution_infrastructure_validation_only
data_source: synthetic_or_existing_local_only
network_used: false
public_api_used: false
private_api_used: false
credential_env_read: false
actual_post_permission: false
entry_post: false
settlement_post: false
actual_post_count: 0
performance_proof_status: false
live_ready: false
unattended_live_supported: false
e2_allowed: false
e3_allowed: false
generated_artifacts_commit_allowed: false
```
