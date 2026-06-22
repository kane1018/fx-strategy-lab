# Phase 2E-4.5: gmo-public risk/audit結果レビュー

Phase 2E-4で実施した `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk` の
手動確認結果をレビューし、`ticker_kline_skew_reject_count=2` の原因候補と次に取るべき安全な方針を整理する。

今回はレビュー・原因整理・docs化のみであり、gmo-public再実行、コード修正、テスト追加、Private API、
APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進んでいない。

## 1. 対象run

```text
run_id: 20260622_094837_shadow_USD_JPY_gmo-public
source: gmo-public
symbol: USD_JPY
interval: M1
date: 20260622
steps: 5
risk/audit: enabled
created_at: 2026-06-22T09:48:37.851387+00:00
```

対象runに存在したファイル:

```text
events.jsonl
metadata.json
signal_decision_log.jsonl
summary.json
```

`candidate_log.jsonl`、`risk_decision_log.jsonl`、`virtual_result_log.jsonl`、`kill_switch_log.jsonl` は生成されていない。

## 2. Phase 2E-4結果評価

結果は **正常終了かつ安全なfail closed** と評価する。

```text
exit_code: 0
steps_executed: 5
halted: false
candidate_count: 0
risk_allow_count: 0
risk_reject_count: 0
virtual_orders_count: 0
ticker_kline_skew_reject_count: 2
public_ticker_fetch_error_count: 0
safety_violation_count: 0
raw_response_saved: false
```

重要な確認:

- Public ticker取得失敗ではない。
- BUY/SELL signalは出たが、ticker/kline skewによりcandidate生成前に`NO_TRADE`へ倒れた。
- candidateが作られていないため、risk decisionとvirtual resultも作られていない。
- kill switch、halt、safety violationは発生していない。
- Private API、APIキー、broker、実注文、実資金には進んでいない。

## 3. signal logの観察

`signal_decision_log.jsonl` は5行だった。

| step | kline timestamp | signal | disposition | reason_codes |
| ---: | --- | --- | --- | --- |
| 0 | `2026-06-22T09:44:00.000000Z` | HOLD | NO_TRADE | `[]` |
| 1 | `2026-06-22T09:45:00.000000Z` | HOLD | NO_TRADE | `[]` |
| 2 | `2026-06-22T09:46:00.000000Z` | BUY | NO_TRADE | `["stale_data"]` |
| 3 | `2026-06-22T09:47:00.000000Z` | SELL | NO_TRADE | `["stale_data"]` |
| 4 | `2026-06-22T09:48:00.000000Z` | HOLD | NO_TRADE | `[]` |

BUY/SELLだったstep 2/3だけでPublic snapshot validationが行われ、`ticker_kline_skew_reject_count` が増えた。
step 4は直近足だがHOLDだったためcandidate生成条件に入らず、`REAL_PUBLIC_BID_ASK`確認には至らなかった。

## 4. ticker/kline skewの原因候補

最も可能性が高い原因は、**CLIがrun開始前にPublic tickerを1回だけ取得し、その同じticker timestampを各BUY/SELL
stepのkline timestampと比較する設計**である。

実装上の流れ:

1. `run_shadow_session.py` が `fetch_candles(..., limit=5, date=20260622)` を実行する。
2. `--enable-shadow-risk` のため `fetch_ticker(USD_JPY)` を1回実行する。
3. そのtickerを閉じ込めた `public_risk_snapshot()` をsessionへ渡す。
4. sessionはBUY/SELL stepでのみ `create_public_market_snapshot()` を呼ぶ。
5. `create_public_market_snapshot()` は `abs(ticker_time - kline_time) > 90秒` なら
   `ticker_kline_skew_reject_count` と `stale_data` でfail closedする。

今回のrunでは、取得した5本のM1 klineは09:44〜09:48だった。BUY/SELLが出たのは09:46と09:47であり、
run作成時刻は09:48:37だった。ticker timestampはログに保存しない設計のため実値は残っていないが、tickerが
run時点の現在値に近い場合、09:46/09:47のklineとは90秒を超える可能性がある。

そのため、`ticker_kline_skew_reject_count=2` は、過去klineと現在tickerを混ぜないための安全制約が働いた結果と見る。

## 5. stale / skew / future判定の確認

現在の主な閾値:

```text
max_ticker_age_seconds: 30
max_ticker_kline_skew_seconds: 90
max_future_skew_seconds: 5
RiskPolicy.max_data_age_seconds: 180
```

今回該当した条件:

- `ticker_stale_count=0` なので、tickerそのものが評価時刻から30秒超古かったわけではない。
- `ticker_invalid_count=0` なので、future timestamp、不正timestamp、bid/ask不正ではない。
- `ticker_kline_skew_reject_count=2` なので、ticker timestampとBUY/SELL kline timestampの差が90秒を超えた。

`create_public_market_snapshot()` はticker/kline skew超過を `RejectReason.STALE_DATA` として返す。
signal logの `reason_codes=["stale_data"]` はこの設計に沿う。これはsafety violationではなく、通常の
`NO_TRADE` / fail closedとして扱ってよい。

## 6. 安全fail closed判定

判定: **安全fail closed**

理由:

- exit code 0で正常終了している。
- halt / kill switch / safety violationがない。
- Public ticker fetch errorではない。
- candidate生成前に止まり、risk decision / virtual resultへ進んでいない。
- virtual orderは0で、positionもflatのまま。
- raw response保存なし。
- Private API、APIキー、broker、実注文、実資金に接続していない。

この結果は、Phase 2E-3の設計「ticker/kline skew超過はfail closed」に一致する。したがって、Phase 2E-4を
危険な失敗として扱う必要はない。

## 7. REAL_PUBLIC_BID_ASK未確認事項

今回まだ確認できていないこと:

- 実runで `REAL_PUBLIC_BID_ASK` が付与されること。
- 実runでcandidateが生成されること。
- 実runで `risk_allow_count > 0` になること。
- 実runでALLOW時のみ `virtual_result_log` が生成されること。
- 実runでcandidate / decision / virtual resultが相関すること。

offline testsではこれらのALLOW経路は確認済みだが、実gmo-public runではまだ未確認である。

## 8. 次回REAL_PUBLIC_BID_ASK確認の選択肢

### A. 当日・直近klineで再実行する

推奨。現在の安全設計を維持したまま、tickerとklineのskewが小さいタイミングを狙える。
ただし、直近足がHOLDなら今回同様candidateは作られない。市場時間、API状態、signal結果に依存する。

### B. 最新足だけを使う設計にする

候補。`--enable-shadow-risk` のgmo-public確認時に、古いklineを除外し最新足中心に評価する設計は
`REAL_PUBLIC_BID_ASK`確認には有効になり得る。ただしコード修正が必要なので、別タスクで設計レビューしてから行う。

### C. ticker/kline skew上限を緩める

現時点では非推奨。古いklineと現在tickerの混用を許しやすくなり、`REAL_PUBLIC_BID_ASK` の意味が弱くなる。
初期安全フェーズでは、90秒上限を安易に緩めない方がよい。

### D. kline timestampではなくticker timestamp基準のcandidateにする

現時点では早い。candidateの市場時刻、signal生成対象、audit相関の意味が変わるため、設計変更の影響が大きい。

## 9. 推奨方針

次は **A: 当日・直近klineでの1回限定再確認** を第一候補にする。

条件:

- 別タスクで明示承認を得る。
- `USD_JPY / M1 / steps 5 / --enable-shadow-risk` を維持する。
- 生成物は `backend/shadow_exports/` のみ、commit禁止。
- `ticker_kline_skew_reject_count` が出ても安全fail closedとして扱う。
- `REAL_PUBLIC_BID_ASK`が確認できなかった場合も、Private API、APIキー、broker、実注文へ進まない。

もし同様のskewが繰り返され、実runで`REAL_PUBLIC_BID_ASK`候補がまったく確認できない場合のみ、Bの
「最新足だけを使う設計」を別レビューする。C/Dは初期段階では採用しない。

## 10. Phase 2E-5へ進む条件

Phase 2E-5へ進む前に必要なこと:

- 少なくとももう一度、Phase 2E-4相当のgmo-public risk/audit確認結果をレビューする。
- 実runで `REAL_PUBLIC_BID_ASK` candidate/decision/virtual result相関を確認できるか、または確認できない理由を
  安全設計として明文化する。
- 設計変更が必要なら、実装前に別docsで設計レビューする。
- safety violation、broken summary、raw response保存、Private/APIキー/broker接続がないことを継続確認する。

今回のレビューだけでは、Phase 2E-5へは進まない。

## 11. summarize確認

Phase 2E-4 run後のaggregate:

```text
runs_count: 21
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
candidate_count: 20
risk_allow_count: 0
risk_reject_count: 20
kill_switch_count: 0
ticker_kline_skew_reject_count: 2
real_public_bid_ask_count: 0
public_ticker_fetch_error_count: 0
```

集計は成功し、壊れsummaryやsafety violationは検出されていない。

## 12. Git / 生成物境界

- `backend/shadow_exports/` はgitignore対象。
- `git ls-files | grep shadow_exports` は出力なし。
- Phase 2E-4の実run生成物はcommitしない。
- raw API response、secret、APIキー、Private情報は保存しない。
