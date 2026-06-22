# Phase 2E-5: gmo-public risk/audit継続確認1回目レビュー / 2回目実行前整理

Phase 2E-5継続確認計画に基づき、1回目の `gmo-public / USD_JPY / M1 / steps 5 /
--enable-shadow-risk` runをレビューし、2回目を別日に安全に実行するための条件を整理する。

今回は **レビュー・docs整理のみ** であり、本日追加のgmo-public run、コード修正、テスト追加、Phase 2F、
Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進まない。

## 1. 対象run

```text
run_id: 20260622_103430_shadow_USD_JPY_gmo-public
source: gmo-public
symbol: USD_JPY
interval: M1
date: 20260622
steps: 5
risk/audit: enabled
created_at: 2026-06-22T10:34:30.010073+00:00
```

対象runに存在した主要ファイル:

```text
events.jsonl
metadata.json
signal_decision_log.jsonl
candidate_log.jsonl
risk_decision_log.jsonl
virtual_result_log.jsonl
summary.json
```

`kill_switch_log.jsonl` は生成されていない。

## 2. 1回目run結果

判定: **成功**

```text
exit_code: 0
steps_executed: 5
halted: false
virtual_orders_count: 1
candidate_count: 2
risk_allow_count: 1
risk_reject_count: 1
kill_switch_count: 0
kill_switch_active: false
safety_violation_count: 0
invalid_risk_row_count: 0
audit_log_write_error_count: 0
```

Public ticker bid/ask:

```text
ticker_bid_ask_used_count: 2
real_public_bid_ask_count: 2
synthetic_spread_reject_count: 0
ticker_missing_count: 0
ticker_stale_count: 0
ticker_invalid_count: 0
ticker_kline_skew_reject_count: 2
public_ticker_fetch_error_count: 0
spread_too_wide_count: 0
raw_response_saved: false
```

確認結果:

- `REAL_PUBLIC_BID_ASK` が2件確認できた。
- candidateが2件生成された。
- `ALLOW_SHADOW` と `REJECT_SHADOW` の両方が確認できた。
- ALLOW時だけvirtual resultが生成された。
- REJECT時にはvirtual resultが生成されなかった。
- safety violation、broken/skipped、invalid risk rowは0。
- raw response保存なし。
- Private API、APIキー、broker、実注文なし。

## 3. ALLOW / REJECT / virtual result確認

### 3.1 BUY candidate: ALLOW_SHADOW

```text
step_index: 3
side: BUY
candidate_id: cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a
spread_provenance: REAL_PUBLIC_BID_ASK
spread_pips: 0.5
entry_reference_price: 161.72
decision_id: risk_cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a_a2da9feb8233
risk status: ALLOW_SHADOW
reasons: []
```

対応するvirtual result:

```text
candidate_id: cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a
decision_id: risk_cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a_a2da9feb8233
status: VIRTUAL_RESULT
position_side: long
units: 1
```

評価:

- ALLOW candidateとrisk decisionのID相関が成立している。
- ALLOW時のみvirtual resultが生成された。
- virtual resultはvirtual-onlyであり、実注文ではない。

### 3.2 SELL candidate: REJECT_SHADOW

```text
step_index: 4
side: SELL
candidate_id: cand_20260622_103430_shadow_USD_JPY_gmo-public_4_sell_b09947dad955
spread_provenance: REAL_PUBLIC_BID_ASK
spread_pips: 0.5
entry_reference_price: 161.715
decision_id: risk_cand_20260622_103430_shadow_USD_JPY_gmo-public_4_sell_b09947dad955_c7a758ef8945
risk status: REJECT_SHADOW
reasons: ["cooldown_active"]
```

評価:

- SELL candidateは `cooldown_active` で正常にREJECTされた。
- REJECT時のvirtual resultは生成されていない。
- REJECTが出たこと自体は失敗ではなく、risk/auditが意図どおりfail closedした結果である。

## 4. ticker/kline skew確認

`ticker_kline_skew_reject_count=2`。

signal log上の該当step:

```text
step 1: BUY / NO_TRADE / reason_codes=["stale_data"]
step 2: BUY / NO_TRADE / reason_codes=["stale_data"]
```

評価:

- 古いklineと現在tickerを混ぜない安全制約により、candidate生成前に `NO_TRADE` へ倒れた。
- これは失敗ではなく、Phase 2E-3以降の設計どおりのfail closedである。
- `public_ticker_fetch_error_count=0` であり、Public ticker fetch failureではない。
- 現時点でskew閾値緩和やticker timestamp基準candidate化などの設計変更は行わない。

## 5. 1日1回ルール確認

Phase 2E-5計画では、gmo-public risk/audit manual runは **1日1回まで** と定義している。

同日2回目の確認:

```text
当日: 20260622
同日実行済みrun: 20260622_103430_shadow_USD_JPY_gmo-public
判断: 1日1回ルールにより、Phase 2E-5 2回目の新規runは未実行で停止
```

評価:

- 同日2回目を実行しなかったことは失敗ではない。
- 継続確認計画どおりの安全停止である。
- 次回のPhase 2E-5 2回目runは別日に1回だけ実行する。

## 6. Phase 2E-5短期確認の進捗

短期確認計画:

```text
3回の gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk manual run
manual only
1日1回まで
```

現在の進捗:

```text
1回目: 完了
2回目: 同日1日1回ルールにより未実行で停止
3回目: 未実行
```

評価:

- 実runとしては短期3回中1回目が完了した状態。
- 2回目として数える実runはまだ未実施である。
- 次は別日に2回目を1回だけ実行する。

## 7. safety / raw response確認

summary / metadata / audit logsで次を確認した。

```text
real_order: false
private_api_used: false
api_key_used: false
no_order_execution: true
live_trading_environment_enabled: false
gmo_order_enabled: false
raw_response_saved: false
safety_violation_count: 0
kill_switch_count: 0
halted: false
```

確認結果:

- Private API、APIキー、broker、実注文、実資金は使われていない。
- raw API response、headers、secret、Private情報は保存されていない。
- run生成物は `backend/shadow_exports/` 配下のみで、commit対象外である。

## 8. summarize確認

Phase 2E-5 1回目後のaggregate:

```text
runs_count: 23
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
candidate_count: 23
risk_allow_count: 2
risk_reject_count: 21
virtual_result_count: 2
kill_switch_count: 0
ticker_bid_ask_used_count: 3
real_public_bid_ask_count: 3
synthetic_spread_reject_count: 12
ticker_kline_skew_reject_count: 7
public_ticker_fetch_error_count: 0
spread_too_wide_count: 0
```

集計は成功し、壊れsummary、safety violation、invalid risk rowは検出されていない。

## 9. 次回2回目runの条件

次回のPhase 2E-5 2回目runは、別日に以下の条件で1回だけ実行する。

```text
source = gmo-public
symbol = USD_JPY
interval = M1
steps = 5
risk/audit = enabled
execution = manual only
frequency = 1日1回まで
commit/push = なし
```

実行前に必ず確認すること:

- 当日の日付。
- 同日すでにPhase 2E-5 gmo-public risk/audit runが存在しないこと。
- `git status --short --branch` が意図しない差分を示さないこと。
- `backend/shadow_exports/` がgitignore対象であること。
- `git ls-files | grep shadow_exports` が出力なしであること。

実行後に必ず確認すること:

- summary / metadata / signal / candidate / risk / virtual result / kill switch logs。
- `REAL_PUBLIC_BID_ASK`、ALLOW、REJECT、virtual result、ticker/kline skew、fetch error、safety。
- REJECT時にvirtual resultが生成されていないこと。
- raw response保存なし。
- Private API、APIキー、broker、実注文なし。
- `shadow_exports/` をcommitしないこと。

## 10. まだ進まない範囲

Phase 2E-5 1回目レビュー後も、次へは進まない。

```text
Phase 2F
Private API
APIキー
broker
実注文
実資金
自動売買
本番公開API追加
frontend変更
DB本番化
認証
M5や他通貨への拡張
cron / schedule / 常駐bot
```

## 11. 結論

Phase 2E-5 1回目は、継続確認として良い結果だった。

- `REAL_PUBLIC_BID_ASK` が複数件確認できた。
- ALLOW / REJECT の両方を実runで確認できた。
- ALLOW時のみvirtual resultが生成された。
- REJECT時virtual resultなしを確認できた。
- `cooldown_active` によるREJECTが正常に働いた。
- skewは `NO_TRADE` へ安全に倒れた。
- safety violation、broken/skipped、invalid risk row、raw response保存、Private/APIキー/broker/実注文はなし。
- 同日2回目は1日1回ルールにより未実行で停止し、計画どおりの運用判断だった。

次は別日にPhase 2E-5 2回目を1回だけ実行する。
