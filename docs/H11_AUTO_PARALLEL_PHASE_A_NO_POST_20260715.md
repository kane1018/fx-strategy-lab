# H-11 Auto Parallel Phase A（broker-independent / no-POST）

Date: 2026-07-15

Status: **IMPLEMENTED_FAKE_ONLY_NO_POST**

## 1. Purpose

手動シグナルUIを主運用として維持しつつ、将来の完全自動売買を別process・別state・別credential
境界で開発する。GMOの最終回答を待たずに進められるbroker非依存部分だけを実装した。

これはH-11 v3の解除・変更ではない。v3は引き続き
`FROZEN_AND_BLOCKED_BY_BROKER_CONSTRAINTS`であり、本Phaseは実broker profileを選定しない。

```text
project=H11_AUTO_PARALLEL_V1
phase=PHASE_A_BROKER_INDEPENDENT
actual_transport_present=false
actual_post=false
broker_read=false
broker_write=false
credential_read=false
resident_process=false
cron=false
live_ready=false
unattended_live_supported=false
```

## 2. Implemented boundary

### Formal signal contract

- finalized formal signalのみ受理
- horizonは10分または30分
- 毎秒rolling estimateは拒否
- strategy version / signal config hash / horizonをpolicyと完全一致させる
- `BUY` / `SELL`だけがfake intent候補
- `STAY`はintentを作らず`NO_ACTION_STAY`
- signal timestamp・validity・probabilityを検証
- deterministic signal fingerprint / intent ID
- localhostのsanitized formal response shapeからのread-only adapter
- adapterはmanual packageをimportせず、mappingとして渡された値だけを検証
- `BLOCKED` / replayed / 24h / rolling / malformed snapshotを拒否

10分・30分のどちらをactual候補へ使うかは未選定。現在の成績を見た後の都合のよい自動切替は
実装していない。

### Frozen Phase A invariants

```text
max_positions=1
max_entries_per_day=1
max_entry_attempts_per_intent=1
max_exit_attempts_per_intent=1
scale_in=false
hedging=false
opposite_signal_as_exit=false
retry=false
repost=false
broker_native_protected_entry_required=true
```

constructor引数からこれらを弱めることはできない。

### Persistent state

- local SQLite
- signal fingerprint重複拒否
- active cycleがある状態で別intentを拒否
- intentをattemptより先にcommit
- entry / exit attemptをcompare-and-setで0→1に限定
- entry attempt日をJSTで永続化し、engine起動時の引数ではなくSQLite実績から1日1回を強制
- HALTを永続ラッチし、HALT行が1件でも残る間は新しいintentを拒否
- hash-linked safe event journal
- journal改ざん検知
- non-blocking process lock
- broker ID、position ID、execution ID、request/response、credential、price、sizeを保存しない

runtime stateを将来置く場合はgitignore済み`backend/market_data/`または`*.sqlite3`を使用し、
commitしない。

### State machine

```text
OFF
→ BOOT_RECONCILING
→ ARMED
→ WAITING_SIGNAL
→ INTENT_PERSISTED
→ PROTECTED_ENTRY_PENDING
→ POSITION_PROTECTED
→ EXIT_PENDING
→ FLAT_RECONCILED
```

各active stateから`HALTED_OPERATOR_REVIEW_REQUIRED`へ遷移できる。HALTから自動復帰するtransitionは
存在しない。`INTENT_PERSISTED`から`POSITION_PROTECTED`へのshortcutも存在しない。

### Fake/refusing boundary

- defaultは`RefusingProtectedEntrySender` / `RefusingPositionExitSender`
- fake senderだけをテスト注入可能
- network client、URL、HMAC、credential、env、Private API importなし
- accepted / rejected / unknown / timeout / partial-fill-size-mismatchをsynthetic再現
- entry、exit、通知失敗はretryせずHALT
- generic close / opposite entry / cancel / change routeなし

### Crash/restart decision

- intent保存後・attempt開始前だけ、最初のsynthetic attemptへ進める
- entry attempt開始後は再送せず`OBSERVE_PENDING_NO_RESEND`
- protected positionは監視のみ継続
- exit attempt後も再送しない
- exit結果不明でpositionが残る場合はHALT
- flatをfresh readで確認した場合だけwriteなしでreconcile
- stale / unknown / manual conflictは常にHALT
- recovery decisionの`actual_post_allowed`は常にfalse

### Pure paper cost model

- USD/JPYのBID/ASKを明示入力
- BUYはASK entry / BID exit、SELLはBID entry / ASK exit
- entry/exitそれぞれへslippageを適用
- API約定手数料は0.002%（rate=`0.00002`）をentry/exit双方のJPY notionalへ適用
- holding costを別控除
- fee=0のablationも明示設定で可能
- quote取得、broker接続、注文、credential処理なし

### Pure position-specific exit policy

- server-side protection未確認またはstale dataは、保護を残したままHALT
- BUYはBID、SELLはASKでunrealized pipsを計算
- frozen stop-loss / take-profit / max-holdを評価
- formal edge消失はposition-specific exit候補として扱う
- Stayまたは反対signalを新規反対注文へ変換しない
- generic close / opposite entryは常にfalse
- actual POST permissionを生成しない

## 3. Boot and entry safety

fake cycleを進めるにも以下を要求する。

```text
boot_reconciled
AND process_lock_held
AND data_fresh
AND clock_synchronized
AND notification_path_ready
AND local_position_count == 0
AND active_intent_count == 0
AND persistent_entry_attempts_on_current_jst_day < 1
AND persistent_halt_latch == false
AND external_or_manual_position_detected == false
AND active_or_pending_order_conflict == false
AND kill_requested == false
```

GMO最終回答に依存するactual readinessは別reviewとして保持する。全条件をtrueにしたsynthetic testでも
`actual_transport_present=false`、`actual_post_allowed=false`、`broker_write_allowed=false`、
`credential_read_allowed=false`は変化しない。

## 4. Bounded fault soak

Command:

```bash
cd backend
python3 -m scripts.h11_auto_phase_a_soak --cycles 100
```

Covered scenarios:

- protected entry → position → exit → flat
- entry reject / unknown / timeout
- partial fill protection-size mismatch
- exit unknown / timeout
- external/manual position conflict
- active order conflict
- stale market data
- Stay no action
- notification failure

Result:

```text
status=PASSED_SYNTHETIC_NO_POST
synthetic_cycle_count=100
matched_cycle_count=100
max_entry_attempts_observed=1
max_exit_attempts_observed=1
duplicate_attempt_invariant_ok=true
no_retry_invariant_ok=true
journal_verification_failures=0
actual_post_count=0
broker_write_performed=false
network_access_performed=false
credential_read_performed=false
raw_id_value_exposure=false
actual_activation_ready=false
```

## 5. Isolation from manual UI

`app.h11_auto`と`app.h11_manual`は相互importしない。Phase Aは手動UIのSQLite、ledger、port、
Keychain service、read-only settlement syncを使用しない。`main_readonly.py`も変更・bindingしない。

将来自動liveを同一GMO口座で行う場合、手動建玉を安全に識別できないため、次のいずれかをactual前に
固定する。

1. 自動売買専用口座
2. 自動運転中の手動売買禁止＋外部建玉検知時HALT

推奨は専用口座だが、現在は未決定である。

## 6. Phase B continuation independent of GMO answer

次はGMO最終回答前にno-POSTで実装済み。

1. bounded paper clock runner（resident/cronではなく有限run）
2. kill -9相当のprocess-level fault tests
3. safe aggregate daily/weekly report
4. one-shot read-only status projection（手動UIとは別state、server/portなし）
5. code-bound 24h wall-clock fake soak（旧run中断後、2026-07-15 16:21:33 JSTに独立Terminalで再開始・完走待ち）

Phase Bの正本は
`docs/H11_AUTO_PARALLEL_DEVELOPMENT_DESIGN_NO_POST_20260715.md`を参照する。

## 7. Blocked until broker/operator decision

```text
broker-native atomic protection
short pending expiry
partial-fill protection-size safety
dedicated account or exclusive-account policy
operator-frozen loss limits and size
selected formal horizon
always-on execution host
actual notification destination
actual credential provision
actual transport implementation
AGENTS.md automatic-execution exception
separate actual activation authorization
```

Public docsまたはbroker回答が上3件を満たさない場合、GMO actual adapterは作らず、broker変更を
選定する。MARKET entry後にclient側からOCOを追加する方式や、長期pending IFDOCOをtimer cancelする
方式へ安全条件を下げない。

## 8. Files

```text
backend/app/h11_auto/contracts.py
backend/app/h11_auto/state_machine.py
backend/app/h11_auto/risk.py
backend/app/h11_auto/persistence.py
backend/app/h11_auto/paper.py
backend/app/h11_auto/boundary.py
backend/app/h11_auto/engine.py
backend/app/h11_auto/exit_policy.py
backend/app/h11_auto/signal_adapter.py
backend/app/h11_auto/recovery.py
backend/app/h11_auto/soak.py
backend/scripts/h11_auto_phase_a_soak.py
backend/app/tests/h11_auto/
```
