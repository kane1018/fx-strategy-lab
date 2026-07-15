# H-11 Auto Formal Signal Localhost Binding Review（no-POST）

Date: 2026-07-15

Status: `REVIEW_COMPLETE_BINDING_NOT_AUTHORIZED`

## 1. Verdict

```text
technical_feasibility=FEASIBLE_WITH_A_DEDICATED_SANITIZED_ROUTE
current_manual_current_endpoint_direct_use=REJECTED
localhost_binding_implemented=false
public_data_refresh_added=false
network_access_performed=false
broker_read=false
broker_write=false
credential_read=false
actual_post=false
```

`GET /api/manual/current`をauto engineから直接pollしてはならない。現在のresponseから必要な正式シグナルだけを
抽出する、localhost専用・副作用なしの別routeまたは同等のproducer boundaryが必要である。

## 2. Current code facts

### Existing local application boundary

- manual UIは`app.main_h11_manual`だけで起動する。
- hostは`127.0.0.1 / localhost / ::1 / testserver`だけ許可する。
- `app.main_readonly`とは分離されている。
- order / cancel / change / settlement POST routeは持たない。

### Why `/api/manual/current` cannot be used directly

1. `ManualSignalService.current()`のdefaultは`record=True`であり、forecast記録、NO_ACTION記録、maturity
   resolutionを行う。GETだがSQLiteへ副作用がある。
2. top-levelには`screen / symbol / updated_at_utc / latest_market_time_utc / safety / signals`が含まれる。
   auto側のpure handoff contractはtop-levelを`signals`だけに限定している。
3. 各signalには`horizon_label / p_down / reason / forecast_id`等の表示・manual台帳用fieldが含まれる。
   auto側はこれらを受けず、未知fieldをfail-closedで拒否する。
4. 10m / 30mだけでなく24hも含む。24hはauto inputとして禁止済み。
5. current responseにはbroker syncを直接含めないが、manual UI全体にはbroker/exit/trade-plan routeがある。
   autoはmanual response全体を信頼境界へ入れてはならない。
6. `/api/manual/refresh`はPublic data fetchとmodel初期化を行い得る。formal signal readとdata refreshを同じ
   consumer actionにしてはならない。

## 3. Frozen handoff schema proposal

将来別授権で追加するproducer outputは、top-levelとrecord fieldを完全一致で次へ限定する。

```json
{
  "signals": [
    {
      "horizon": "10m",
      "direction": "BUY",
      "status": "OK",
      "p_up": 0.61,
      "origin_time_utc": "2026-07-15T00:00:00+00:00",
      "model_config_hash": "operator-frozen exact value",
      "recorded_mode": "PROSPECTIVE"
    },
    {
      "horizon": "30m",
      "direction": "STAY",
      "status": "OK",
      "p_up": 0.54,
      "origin_time_utc": "2026-07-15T00:00:00+00:00",
      "model_config_hash": "operator-frozen exact value",
      "recorded_mode": "PROSPECTIVE"
    }
  ]
}
```

例の値はschema説明用であり、actual signalやoperator選定値ではない。

Allowed record keys:

```text
horizon
direction
status
p_up
origin_time_utc
model_config_hash
recorded_mode
```

禁止field:

```text
24h
realtime / rolling estimate
forecast_id
horizon_label
reason
p_down
screen / symbol / safety
trade plan / exit plan
broker sync / position / execution / active order
price / quantity
raw response / ID / credential
```

## 4. Producer requirements

将来のproducer routeは最低限、次をすべて満たす。

1. `main_h11_manual`のlocalhost middleware内だけに置く。
2. `main_readonly.py`へ追加しない。
3. GET-onlyで、`service.current(record=False)`相当の副作用なし計算だけを使う。
4. `/refresh`、Public GET、Private GET、broker syncを暗黙に呼ばない。
5. 10mと30mだけを出力し、24hとrealtimeを除外する。
6. unknown keyを追加せず、上記schemaをexact matchで返す。
7. `BLOCKED / REPLAYED_AFTER_MATURITY / missing config`をactionableへ変換しない。
8. model config hashやhorizonをproducer側で推測・置換しない。
9. response、signal、時刻をlogへ全文保存しない。
10. route自身は注文権限、risk変更権限、actual permissionを一切持たない。

## 5. Consumer requirements

1. auto起動時にoperator-frozen horizon / strategy / config hashを固定する。
2. 1cycleにつき最大1回だけlocalhost snapshotを読む。
3. timeout、connection failure、invalid JSON、duplicate horizon、schema driftはentryを作らずHALTまたはsafe block。
4. formal signal validity内だけentry candidateを作る。
5. deterministic fingerprintとpersistent journalで同一signalの再処理を拒否する。
6. consumerは`app.h11_manual`をimportしない。
7. producerは`app.h11_auto`をimportしない。
8. localhost read failureをPublic refreshや別horizonへのfallbackで補わない。
9. query parameterやUI操作でrun中horizonを切り替えない。
10. bindingから`actual_post_allowed=true`を生成しない。

## 6. Polling and timing

正式10m/30m signalは確定M1を入力にする。毎秒rolling estimateではないため、auto consumerが毎秒pollする
必要はない。候補は確定M1更新後に1回、最大でも1分1回である。

```text
price/chart display cadence != formal auto signal cadence
formal signal source=M1 finalized snapshot
rolling estimate source=never used by auto
```

data refresh scheduler、market closure、clock alignment、M1 finalization判定は別契約として固定する。現在は
新しいdata fetch、scheduler、cron、resident processを追加しない。

## 7. Required tests before binding authorization

- route呼出前後でmanual ledger row countが不変
- exact top-level schemaとexact record keys
- 10m / 30mのみ、各1件
- 24h / realtime / broker / exit / trade-plan fieldが0
- `recorded_mode=PROSPECTIVE`以外をauto側が拒否
- blocked / missing / duplicate / malformed / unknown keyを拒否
- localhost以外を403
- producerとconsumerの相互importが0
- timeout / connection error後のentry attemptが0
- 同一signal反復取得後のentry attemptが最大1
- actual POST / broker read/write / credential readが0

## 8. Activation boundary

本reviewは実装授権ではない。次の順序を維持する。

1. 現在のcode-bound 24h soakを完走する。
2. operatorがformal horizon / config hash / generationを固定する。
3. localhost producer routeとrefusing-by-default consumer bindingを別Stepで明示授権する。
4. fake client testsと独立safety reviewを行う。
5. source codeが変わった場合は新しいimplementation digestで必要なsoakを再実行する。

このbindingが完成してもbroker profile、reconciliation、actual notification、sealed credential、actual transport、
actual activation、POSTは引き続き別gateである。
