# Phase 2E-5: gmo-public risk/audit 短期3回確認レビュー

Phase 2E-5継続確認計画に基づき実施した `gmo-public / USD_JPY / M1 / steps 5 /
--enable-shadow-risk` manual run 3回分をレビューし、Public shadow risk/auditとしてPhase 2Fへ進めるかを判断する。

今回は **レビュー・docs化のみ** であり、gmo-public再実行、コード修正、テスト追加、Phase 2F実行、
Phase 3B実装、Private API接続、APIキー入力、broker、実注文、実資金、自動売買、本番公開API追加には進まない。

## 1. レビュー対象

| run | run_id | date | source | symbol | interval | steps | risk/audit |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 1回目 | `20260622_103430_shadow_USD_JPY_gmo-public` | `20260622` | `gmo-public` | `USD_JPY` | `M1` | 5 | enabled |
| 2回目 | `20260623_000652_shadow_USD_JPY_gmo-public` | `20260623` | `gmo-public` | `USD_JPY` | `M1` | 5 | enabled |
| 3回目 | `20260624_001906_shadow_USD_JPY_gmo-public` | `20260624` | `gmo-public` | `USD_JPY` | `M1` | 5 | enabled |

各runはmanual onlyで実行され、1日1回ルールを維持した。3回目完了後も、本レビューではPhase 2F実行へは進まない。

## 2. 3回分の比較

| 指標 | 1回目 | 2回目 | 3回目 | 3回合計 |
| --- | ---: | ---: | ---: | ---: |
| `exit_code` | 0 | 0 | 0 | - |
| `halted` | false | false | false | - |
| `candidate_count` | 2 | 1 | 2 | 5 |
| `risk_allow_count` | 1 | 1 | 1 | 3 |
| `risk_reject_count` | 1 | 0 | 1 | 2 |
| `virtual_orders_count` | 1 | 1 | 1 | 3 |
| `ticker_bid_ask_used_count` | 2 | 1 | 2 | 5 |
| `real_public_bid_ask_count` | 2 | 1 | 2 | 5 |
| `ticker_kline_skew_reject_count` | 2 | 3 | 2 | 7 |
| `public_ticker_fetch_error_count` | 0 | 0 | 0 | 0 |
| `safety_violation_count` | 0 | 0 | 0 | 0 |
| `raw_response_saved` | false | false | false | - |

3回とも `exit_code=0`、`halted=false`、`safety_violation_count=0`、`raw_response_saved=false` を維持した。
candidate、ALLOW、virtual resultは3回すべてで確認できた。REJECTは1回目と3回目で確認できた。

## 3. REAL_PUBLIC_BID_ASK確認

確認結果:

- 3回すべてで `REAL_PUBLIC_BID_ASK` が確認できた。
- 3回合計の `real_public_bid_ask_count` は5件。
- candidate 5件すべての `spread_provenance` は `REAL_PUBLIC_BID_ASK`。
- 3回の実runでは `synthetic_spread_reject_count=0` を維持した。
- `public_ticker_fetch_error_count=0` を維持した。
- `raw_response_saved=false` を維持し、raw responseやheadersは保存していない。

評価:

- GMO Public ticker由来bid/askが、3日連続のmanual runでrisk/audit candidateへ到達した。
- kline-only synthetic spreadに倒れてALLOW/REJECT判定を代替する挙動は、対象3runでは発生していない。
- Public ticker bid/ask provenanceの継続確認として、短期確認の最低条件は満たした。

## 4. ALLOW / REJECT / virtual result確認

### 1回目

- BUY candidate `cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a`
  は `ALLOW_SHADOW`。
- decision_idは `risk_cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a_a2da9feb8233`。
- 同じcandidate_id / decision_idでvirtual resultが生成された。
- SELL candidate `cand_20260622_103430_shadow_USD_JPY_gmo-public_4_sell_b09947dad955`
  は `cooldown_active` により `REJECT_SHADOW`。
- REJECT candidateにvirtual resultは生成されていない。

### 2回目

- BUY candidate `cand_20260623_000652_shadow_USD_JPY_gmo-public_4_buy_266813a7cb33`
  は `ALLOW_SHADOW`。
- decision_idは `risk_cand_20260623_000652_shadow_USD_JPY_gmo-public_4_buy_266813a7cb33_cdbebd4a075f`。
- 同じcandidate_id / decision_idでvirtual resultが生成された。
- REJECT candidateは発生しなかった。

### 3回目

- BUY candidate `cand_20260624_001906_shadow_USD_JPY_gmo-public_3_buy_031170be866a`
  は `ALLOW_SHADOW`。
- decision_idは `risk_cand_20260624_001906_shadow_USD_JPY_gmo-public_3_buy_031170be866a_f9fbe9c76ab3`。
- 同じcandidate_id / decision_idでvirtual resultが生成された。
- BUY candidate `cand_20260624_001906_shadow_USD_JPY_gmo-public_4_buy_2571a53a70dc`
  は `cooldown_active` により `REJECT_SHADOW`。
- REJECT candidateにvirtual resultは生成されていない。

評価:

- 3回すべてで `ALLOW_SHADOW` が確認できた。
- REJECTは1回目と3回目で確認でき、理由はいずれも `cooldown_active`。
- ALLOW時のみvirtual resultが生成された。
- REJECT時にはvirtual resultが生成されていない。
- candidate_id / decision_id相関は3回すべてで維持された。
- `cooldown_active` REJECTは失敗ではなく、risk/auditの抑制が機能した結果である。

## 5. ticker/kline skew評価

確認結果:

- 1回目: `ticker_kline_skew_reject_count=2`。step 1/2 が `stale_data` で `NO_TRADE`。
- 2回目: `ticker_kline_skew_reject_count=3`。step 1/2/3 が `stale_data` で `NO_TRADE`。
- 3回目: `ticker_kline_skew_reject_count=2`。step 1/2 が `stale_data` で `NO_TRADE`。
- 3回合計の `ticker_kline_skew_reject_count` は7件。

評価:

- skew / stale_dataは3回とも発生したが、失敗ではない。
- 古いklineと現在tickerを混ぜない安全制約として機能し、candidate生成前に `NO_TRADE` へ倒れた。
- skewが発生したstepではvirtual resultへ進んでいない。
- `public_ticker_fetch_error_count=0` であり、Public ticker取得失敗とは区別できる。
- 現時点でskew閾値緩和はしない。閾値緩和は古いklineと現在tickerの混用を許しやすくし、provenanceの意味を弱める。
- Phase 2Fでは、最新足だけを使う設計レビューが必要かを検討対象にする。

## 6. safety評価

3回分の確認結果:

- `safety_violation_count=0`。
- `broken/skipped=0`。
- `invalid_risk_row_count=0`。
- `halted=false`。
- `kill_switch_count=0`。
- `kill_switch_active=false`。
- `raw_response_saved=false`。
- `private_api_used=false`。
- `api_key_used=false`。
- `real_order=false`。
- `no_order_execution=true`。
- `live_trading_environment_enabled=false`。
- `gmo_order_enabled=false`。
- Private API / APIキー / broker / 実注文 / 実資金はなし。
- `backend/shadow_exports/` はgitignore対象。
- `git ls-files | grep shadow_exports` は出力なし。

保存ファイル:

- 各runの保存ファイルは `events.jsonl`、`summary.json`、`metadata.json`、
  `signal_decision_log.jsonl`、`candidate_log.jsonl`、`risk_decision_log.jsonl`、`virtual_result_log.jsonl`。
- `kill_switch_log.jsonl` は3runとも未生成。summary上の `kill_switch_count=0` と整合する。
- raw API response、response headers、authorization header、API key、secret、token、private key、`.env` は保存されていない。

## 7. summarize結果

レビュー時点のaggregate:

```text
runs_count: 25
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
candidate_count: 26
risk_allow_count: 4
risk_reject_count: 22
virtual_result_count: 4
kill_switch_count: 0
kill_switch_active_runs_count: 0
ticker_bid_ask_used_count: 6
real_public_bid_ask_count: 6
synthetic_spread_reject_count: 12
ticker_kline_skew_reject_count: 12
public_ticker_fetch_error_count: 0
spread_too_wide_count: 0
```

評価:

- aggregate全体でも broken/skipped、safety violation、invalid risk row、kill switch activeは0。
- `real_public_bid_ask_count` は、Phase 2E-4R以降の実run確認分を含めて6件。
- `synthetic_spread_reject_count=12` は過去runを含むaggregate値であり、Phase 2E-5短期3run内では0だった。
- PnLは収益性評価に使わない。Phase 2E-5の評価対象は安全性、相関、fail closed、summary互換である。

## 8. Phase 2E-5短期確認の判定

判定: **A: Phase 2Fへ進んでよい**

理由:

- 3回すべてで `REAL_PUBLIC_BID_ASK` を確認できた。
- 3回すべてでcandidate生成を確認できた。
- 3回すべてで `ALLOW_SHADOW` を確認できた。
- 1回目と3回目で `REJECT_SHADOW` を確認できた。
- REJECT理由は `cooldown_active` として説明可能。
- ALLOW時のみvirtual resultが生成された。
- REJECT時にvirtual resultが生成されていない。
- candidate / decision / virtual result相関が壊れていない。
- ticker/kline skewはcandidate生成前の `NO_TRADE` に安全fail closedした。
- safety violation、broken/skipped、invalid risk row、kill switch activeは0。
- raw response保存、Private API、APIキー、broker、実注文、実資金はなし。
- `shadow_exports/` のgit tracking混入はない。

ただし、この判定は **Phase 2Fレビューへ進む許可** であり、Phase 2F実行そのものではない。本タスクではPhase 2Fへ進まない。

## 9. Phase 2Fで扱うべき論点

Phase 2Fは、Private APIではなく **Public shadow risk/auditのレビュー・安定性評価・運用計画** として扱う。

Phase 2Fで扱うべき論点:

- Phase 2E-5短期3runの安定性評価。
- skew / stale_data / `NO_TRADE` の扱い。
- `REAL_PUBLIC_BID_ASK` の継続確認条件。
- ALLOW / REJECT / virtual result相関の受け入れ条件。
- Public shadow risk/auditとしての合格条件。
- 追加Public runが必要か、中期5〜10回確認へ進むか。
- Phase 3B Private API read-onlyへ進む前の残課題。
- Phase 3Aロードマップとの接続条件。
- まだPrivate API、APIキー、broker、実注文、実資金へ進まない根拠。

Phase 2Fでも扱わないもの:

- Private API接続。
- APIキー入力・表示・保存。
- broker。
- 注文API。
- 実注文。
- 実資金。
- 自動売買。
- Live Verification Mode実装。
- 本番公開API追加。

## 10. まだ進まない範囲

```text
Phase 2F実行
Phase 3B実装
Private API接続
APIキー入力・表示・保存
.env表示・変更
.env.example変更
broker
注文API
実注文
実資金
自動売買
cron / schedule / 常駐bot
本番公開API追加
frontend変更
DB本番化
認証
M5や他通貨への拡張
```

## 11. 結論

Phase 2E-5短期3回確認は、Public shadow risk/auditの短期安定性確認として成功した。

結論:

- `REAL_PUBLIC_BID_ASK`、candidate、ALLOW、REJECT、virtual result相関は短期3回で確認できた。
- skew / stale_dataは安全fail closedとして機能した。
- safety violation、broken/skipped、invalid risk row、kill switch active、raw response保存、Private/APIキー/broker/実注文はない。
- 判定は **A: Phase 2Fへ進んでよい**。
- 次に行うべき作業は、別タスクでPhase 2F Public shadow risk/audit安定性レビューを作成すること。
- 本レビューではPhase 2F実行、Phase 3B、Private API、実注文には進まない。

## 12. Phase 2Fレビュー結果

その後、Phase 2F Public shadow risk/audit安定性レビューをdocs化した。

詳細は [PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md](PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md)。

Phase 2Fの判定は **A: Public shadow risk/auditはPhase 3B準備へ進める水準**。ただし、Phase 3B実装へ即進まず、
先にPhase 2G Public shadow risk/auditオフライン最終デバッグ監査を半日程度で挟むことを推奨する。
Private API、APIキー、broker、実注文、実資金へは進まない。
