# H-11 Auto Formal Data and Clock Contract（draft / no-fetch）

Date: 2026-07-15

Status: `CLOCK_SKEW_BOUND_IMPLEMENTED_OTHER_FRESHNESS_PENDING_NO_SCHEDULER`

## 1. Purpose

10m/30m正式シグナルを毎秒rolling estimateと混同せず、M1確定、data freshness、clock、poll cadenceを
auto executionから独立した契約として固定する。

```text
data_fetch_performed=false
public_get_added=false
private_get=false
websocket_added=false
scheduler_added=false
cron=false
resident_process=false
```

## 2. Data roles

```text
Public price/ticker:
  purpose=display_and_future_position_monitoring
  cadence=potentially_subminute
  formal_signal_authority=false

Finalized M1 candles:
  purpose=10m_and_30m_formal_signal_input
  cadence=once_per_finalized_minute
  formal_signal_authority=true

Rolling one-second estimate:
  purpose=manual_reference_and_separate_validation
  formal_signal_authority=false
  auto_entry_authority=false

H1/24h model:
  purpose=manual_directional_reference
  auto_entry_authority=false
```

## 3. Finalized M1 definition

M1 rowを正式入力へ使える条件:

- candle open timeがUTC aware
- expected one-minute bucketへ整列
- 次bucket開始後である
- OHLCが有限値で整合
- duplicate timestampなし
- required lookbackに欠損なし、またはfrozen model contractが許容する明示処理
- source freshness上限内
- current partial candleを含めない

broker/public sourceがfinal flagを提供しない場合の確定待ちmarginをoperator configとして事前固定する。

## 4. Formal evaluation cadence

```text
target cadence=each finalized M1 at most once
consumer poll upper bound=once per minute
entry evaluation per formal fingerprint=once
missed minute behavior=no backlog trading
```

process停止後に複数の古いformal signalsを順番にentry候補へしない。restart時は最新の未期限formal signalだけを
評価し、既にexpiryまたはreplayedならno actionとする。

## 5. Clock requirements

必須時刻:

```text
system_utc_now
monotonic_runtime_clock
market_event_time_utc
m1_open_time_utc
formal_observed_at_utc
formal_valid_until_utc
last_reconciliation_at_utc
last_heartbeat_at_utc
```

wall clockとmonotonic clockの用途を分ける。

- validity / market timestamp比較はUTC wall clock
- process elapsed / timeout / backoffはmonotonic clock
- wall clock backward/future timestampはHALT
- sleep gapはelapsed成功時間へ算入しない

## 6. Freshness gates

maximum clock skewだけはoperator承認済みpreparation contractへ固定した。他のfreshness値は未承認のため
発効しない。

```yaml
maximum_m1_age_seconds: PENDING_OPERATOR_FREEZE
finalization_margin_seconds: PENDING_OPERATOR_FREEZE
maximum_ticker_age_seconds: PENDING_OPERATOR_FREEZE
maximum_clock_skew_seconds: 5
maximum_reconciliation_age_seconds: PENDING_EXECUTION_PROFILE
```

いずれかがunknown、negative、future、staleなら新規entryを作らない。

## 7. Producer / consumer separation

Producer responsibilities:

- Public data取得とM1確定
- frozen modelで10m/30m probabilitiesを計算
- config hash、origin、recorded modeを付与
- exact sanitized localhost schemaを返す

Consumer responsibilities:

- frozen horizon/config exact match
- schema / freshness / expiry検証
- deterministic fingerprint重複拒否
- persistent risk / process / reconciliation gates
- entry intent persist

consumerがdata不足時にmodel training、threshold変更、Public refreshを自動実行しない。

## 8. Failure behavior

```text
missing M1=NO_ENTRY
partial current candle=NO_ENTRY
duplicate candle=HALT_OR_SAFE_BLOCK
clock future/backward=HALT
producer timeout=NO_ENTRY_NO_RETRY_WITHIN_SAME_CYCLE
schema drift=HALT
config mismatch=HALT
replayed forecast=NO_ENTRY
expired forecast=NO_ENTRY
backlog after downtime=DROP_OLD_SIGNALS
```

別horizonやrolling estimateへ自動fallbackしない。

## 9. Verification before implementation activation

- boundary minute前後のM1確定
- DSTの影響を受けずUTC→JST day budgetが正しい
- missing / duplicate / out-of-order candle
- process sleep / wake gap
- wall clock forward / backward
- delayed producer response
- same M1 snapshot repeated
- restart後のold backlog
- 10mと30mが同じoriginでもfrozen horizonだけ採用
- rolling / 24hが0 entry attempts
- no implicit training / threshold change / data fetch by consumer

## 10. Current boundary

現在のmanual producerはPublic refreshとmodel初期化を持つが、auto consumerへ直接bindingしない。
専用sanitized route reviewは`H11_AUTO_FORMAL_SIGNAL_LOCALHOST_BINDING_REVIEW_NO_POST_20260715.md`を正とする。

本draftはdata fetch、WebSocket、scheduler、resident process、broker access、credential、POSTを許可しない。
