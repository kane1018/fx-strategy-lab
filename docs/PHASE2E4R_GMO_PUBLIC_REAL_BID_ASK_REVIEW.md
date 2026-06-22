# Phase 2E-4R: GMO Public REAL_PUBLIC_BID_ASK runレビュー

Phase 2E-4Rで実施した直近kline条件の `gmo-public / USD_JPY / M1 / steps 5 /
--enable-shadow-risk` 再確認結果をレビューし、実runで `REAL_PUBLIC_BID_ASK`、`ALLOW_SHADOW`、
virtual result相関が確認できたことを整理する。

今回はレビュー・docs化のみであり、gmo-public再実行、コード修正、テスト追加、Phase 2E-5実装、
Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進んでいない。

## 1. 対象run

```text
run_id: 20260622_100540_shadow_USD_JPY_gmo-public
source: gmo-public
symbol: USD_JPY
interval: M1
date: 20260622
steps: 5
risk/audit: enabled
created_at: 2026-06-22T10:05:40.354320+00:00
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

## 2. run結果評価

結果は **成功** と評価する。

```text
exit_code: 0
steps_executed: 5
halted: false
virtual_orders_count: 1
candidate_count: 1
risk_allow_count: 1
risk_reject_count: 0
kill_switch_count: 0
kill_switch_active: false
safety_violation_count: 0
ticker_bid_ask_used_count: 1
real_public_bid_ask_count: 1
ticker_kline_skew_reject_count: 3
public_ticker_fetch_error_count: 0
raw_response_saved: false
```

Phase 2E-4で未確認だった実runの `REAL_PUBLIC_BID_ASK` candidate、`ALLOW_SHADOW` decision、
virtual result相関が確認できた。

## 3. REAL_PUBLIC_BID_ASK確認

`candidate_log.jsonl` に1件のcandidateが生成された。

```text
candidate_id: cand_20260622_100540_shadow_USD_JPY_gmo-public_4_sell_ced876962cec
step_index: 4
side: SELL
spread_provenance: REAL_PUBLIC_BID_ASK
spread_pips: 0.5
entry_reference_price: 161.738
market_data_timestamp: 2026-06-22T10:05:39.953048Z
real_order: false
private_api_used: false
api_key_used: false
no_order_execution: true
live_trading_environment_enabled: false
gmo_order_enabled: false
```

確認結果:

- 実runで `REAL_PUBLIC_BID_ASK` が付与された。
- Public ticker由来bid/askがrisk/audit candidateへ到達した。
- raw response、headers、secret、Private情報は保存されていない。
- `spread_pips=0.5` は初期policyの `max_spread_pips=0.5` 境界内で、ALLOW判定へ進めた。

## 4. ALLOW_SHADOW / virtual result確認

`risk_decision_log.jsonl` に1件の `ALLOW_SHADOW` decisionが生成された。

```text
decision_id: risk_cand_20260622_100540_shadow_USD_JPY_gmo-public_4_sell_ced876962cec_54b63e1c364f
candidate_id: cand_20260622_100540_shadow_USD_JPY_gmo-public_4_sell_ced876962cec
status: ALLOW_SHADOW
reasons: []
real_order: false
private_api_used: false
api_key_used: false
no_order_execution: true
```

`virtual_result_log.jsonl` に、同じcandidate/decisionに対応する1件のvirtual resultが生成された。

```text
candidate_id: cand_20260622_100540_shadow_USD_JPY_gmo-public_4_sell_ced876962cec
decision_id: risk_cand_20260622_100540_shadow_USD_JPY_gmo-public_4_sell_ced876962cec_54b63e1c364f
status: VIRTUAL_RESULT
position_side: short
units: 1
```

確認結果:

- ALLOW時のみvirtual resultが生成された。
- candidate / decision / virtual result のID相関が成立している。
- `risk_reject_count=0` で、REJECTに対応するvirtual resultは存在しない。
- `virtual_orders_count=1` と `virtual_result_log` 1件が対応する。

## 5. ticker/kline skew NO_TRADE確認

古い3 stepは `ticker_kline_skew_reject_count=3` としてcandidate生成前に `NO_TRADE` へ倒れた。

```text
step 1: BUY / NO_TRADE / reason_codes=["stale_data"]
step 2: BUY / NO_TRADE / reason_codes=["stale_data"]
step 3: BUY / NO_TRADE / reason_codes=["stale_data"]
```

これはPhase 2E-4.5で整理したとおり、現在tickerと古いklineを混ぜないための安全fail closedである。
今回はstep 4の直近SELLで `REAL_PUBLIC_BID_ASK` candidateが生成されたため、skew制約を維持したまま
実runのALLOW経路を確認できた。

## 6. safety確認

summary / metadata / audit logsで以下を確認した。

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

Private API、APIキー、broker、実注文、実資金は使われていない。

## 7. summarize確認

Phase 2E-4R後のaggregate:

```text
runs_count: 22
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
candidate_count: 21
risk_allow_count: 1
risk_reject_count: 20
virtual_result_count: 1
kill_switch_count: 0
ticker_bid_ask_used_count: 1
real_public_bid_ask_count: 1
synthetic_spread_reject_count: 12
ticker_kline_skew_reject_count: 5
public_ticker_fetch_error_count: 0
spread_too_wide_count: 0
```

集計は成功し、壊れsummaryやsafety violationは検出されていない。

## 8. Phase 2E-5前判断

判定: **Phase 2E-5設計へ進める**

理由:

- Phase 2E-3で設計した `REAL_PUBLIC_BID_ASK` provenanceが実runで確認できた。
- 実runでcandidateが生成された。
- 実runで `ALLOW_SHADOW` が生成された。
- ALLOWに対応するvirtual resultが生成された。
- candidate / decision / virtual result のID相関が確認できた。
- 古いklineはskewにより安全に `NO_TRADE` へ倒れた。
- safety violation、broken summary、raw response保存、Private/APIキー/broker/実注文がない。

ただし、進めるのは **Phase 2E-5設計** までであり、Phase 2E-5実装/実行、Private API、APIキー、
broker、実注文、実資金、自動売買、本番公開API追加へは進まない。

## 9. 追加確認の要否

Phase 2E-5設計前に必須のgmo-public再確認は不要と判断する。

任意で行う場合も、目的はPublic risk/audit経路の再現性確認に限定し、1回ずつ手動・local-only・生成物commit禁止で行う。
ただし、同じ到達点は今回すでに確認できているため、追加runよりもPhase 2E-5設計で次の安全境界を整理する方が優先度は高い。

## 10. Phase 2E-5設計で扱うべき論点

Phase 2E-5設計で検討してよい候補:

- Public risk/audit確認の受け入れ条件を文書化する。
- `REAL_PUBLIC_BID_ASK` candidate/ALLOW/virtual result相関の継続確認方法を整理する。
- ticker/kline skewが出たstepの扱いをrunbookへ明記し続ける。
- 実run生成物をcommitしない運用を継続する。
- Phase 2E-5でもPublic/local-only境界を維持する。

Phase 2E-5設計でまだ扱わないもの:

- Private API
- APIキー
- broker接続
- 実注文
- 実資金
- 自動売買
- 本番公開API追加
- frontend / reports公開
- cron / schedule / 常駐bot

## 10.1 Phase 2E-5設計結果

Phase 2E-5では、gmo-public risk/audit継続確認計画をdocs化した。

要点:

- 初期条件は `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk`。
- manual only、1日1回まで。
- 短期3回・中期5〜10回を目安に、安全性、ログ品質、相関、fail closed、summary互換を確認する。
- HOLD、ticker/kline skew、spread too wide、ticker stale、fetch error fail closedは保留/追加観察として扱う。
- safety violation、broken summary、raw response保存、Private/APIキー/broker/実注文痕跡、相関不整合は停止条件とする。
- Phase 2FはPublic shadow risk/auditのレビュー・安定性評価・運用計画であり、Private APIや実注文ではない。

詳細は [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。

## 11. Git / 生成物境界

- `backend/shadow_exports/` はgitignore対象。
- `git ls-files | grep shadow_exports` は出力なし。
- Phase 2E-4Rの実run生成物はcommitしない。
- raw API response、secret、APIキー、Private情報は保存しない。
