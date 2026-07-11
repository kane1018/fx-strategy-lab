# H-11 v3 Phase A–C Implementation Report（no-POST）

Date: 2026-07-11

Status: **PHASE_ABC_IMPLEMENTED_NO_POST_ACTIVATION_BLOCKED**

## 1. Scope

Operatorの長距離自走授権に基づき、actual activation前に可能な範囲を実装した。

- Phase A: 公開仕様のsanitized capability review
- Phase B: actual senderを持たないdisabled IFDOCO production boundary
- Phase C: persistent safety primitives＋bounded synthetic fault soak

実broker/API/env/credential、actual POST、resident process、cron、commit/pushは実行していない。

## 2. Implemented

### Execution contract

- H-11 v2 TREND previewからv3 IFDOCO protected planへの決定論変換
- STOP entry、同一sizeのOCO、価格bracketing、config hash固定
- USD_JPY / min 10000 / sizeStep 1 / tick 0.001をcapability contract hashで固定
- non-actionable signal / config mismatchはplanを生成しない

### Persistent safety

- non-blocking process lock
- intent / attempt stateの送信相当前atomic persistence
- append-only hash-linked safe journal
- journal chain・sequence・config hash検証
- 同日2回目entry拒否
- entry / settlement各最大1 attempt
- timeout / unknown / network / rejectでHALT
- crash/restart時に再送せずreconciliation要求

### Risk / stop

- monthly 50,000 JPY / daily 10,000 JPY / per-trade 5,000 JPY
- consecutive losses 5 / entries per day 1
- daily stopは翌日reset
- monthly/consecutive stopは14日cooling＋月跨ぎ＋postmortem＋reviewでのみreload
- per-trade bound違反はdiscipline violation＋KILLED
- operator killは自動再開しない

### Reconciliation / observation

- local stateとsanitized broker-cycle statusのstate-specific boot reconcile
- missing/stale/unknown/mismatchはfail-closed
- fake notifier boundary
- notification / dead-man / pending expiry / sealed credential reviewをpre-entry gate化
- persistent heartbeat dead-man（missing/stale/future heartbeatはHALT）
- partial/full/unknown fill、OCO子注文、pending expiryのsafe-label reconcile policy
- partial fill、子注文欠落、expiry unknownはretry/repostなしでHALT

### Disabled actual boundary

- IFDOCO kind/path/body shapeだけを受理するproduction review boundary
- actual activation tokenは構築不能
- sender / credential / HTTP / hard-guard allow / allow bridgeなし
- structural reviewがclearでも`actual_post_allowed=false`

## 3. Public specification review

Source: [GMOコイン 外国為替FX APIドキュメント](https://api.coin.z.com/fxdocs/) /
[API自動売買商品ページ](https://coin.z.com/jp/corp/product/info/fx/api/)

- IFDOCO: first LIMIT/STOP＋second LIMIT/STOPを同一親注文で表現
- USD/JPY public symbols example: minOpenOrderSize=10000、sizeStep=1、tickSize=0.001
- clientOrderId: 36文字以内の半角英数字
- order/execution Private WebSocket events: orderSize / orderExecutedSize / executionSizeあり
- expiry fieldとEXPIRED statusは存在
- ただし`ifoOrder` requestにexpiry指定項目はなく、broker-native期限決定規則を確定できない
- したがってpending expiryはactual activation blockerのまま

## 4. Synthetic soak result

Command:

```text
cd backend
.venv/bin/python -m scripts.h11_v3_fault_soak --cycles 100
```

Safe aggregate:

```text
status=PASSED_SYNTHETIC_NO_POST
synthetic_cycle_count=100
matched_cycle_count=100
final_flat=16
fail_closed_halted=84
journal_verification_failures=0
notification_failures=0
max_entry_attempts_observed=1
max_settlement_attempts_observed=1
duplicate_attempt_invariant_ok=true
no_retry_invariant_ok=true
actual_post_count=0
broker_read=false
credential_env_read=false
raw_id_value_exposure=false
wall_clock_24h_soak_completed=false
actual_activation_ready=false
```

## 5. Remaining blockers

1. broker-native pending expiry duration/rule confirmation
2. IFDOCO partial-fill and child-order activation semanticsのactual adapter確認
3. actual account IFDOCO permission・account mode
4. Private WebSocket token/reconnect or alternative notification design
5. external operator notification route
6. execution host / sleep / clock / process supervision
7. sealed credential actual provision review
8. actual IFDOCO sender binding review
9. major-incident v3 resume declaration
10. AGENTS.md actual automatic-execution exception
11. 24h wall-clock fake soak
12. clean tree / HEAD==origin/main / complete actual-activation review

## 5A. Verification

```text
Phase A-C focused/isolation=78 passed
final safety focused=48 passed
backend full regression=7503 passed
backend Ruff=passed
git diff --check=passed
```

## 6. Safety state

```text
current_stage=V3_BUILD_NO_POST_PHASE_ABC_COMPLETE
actual_transport_bound=false
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
credential_env_read=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
