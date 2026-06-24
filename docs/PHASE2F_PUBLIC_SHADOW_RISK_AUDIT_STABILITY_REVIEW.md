# Phase 2F: Public shadow risk/audit 安定性レビュー

Phase 2Fでは、Phase 2E-5までに実施したPublic APIのみのshadow risk/audit runをレビューし、
Phase 3B Private API read-onlyへ進む前の安全状態を確認する。

今回は **レビュー・docs化のみ** である。gmo-public再実行、コード修正、テスト追加、Phase 3B実装、
Private API接続、APIキー入力、broker、実注文、実資金、自動売買、本番公開API追加には進まない。

## 1. 目的

- Public shadow risk/auditの短期安定性を評価する。
- Phase 3B read-onlyへ進む前の安全レビューとして、Public側の境界が崩れていないことを確認する。
- 実行・実装ではなく、既存runと既存docsに基づくdocs-onlyレビューに限定する。
- Private API、APIキー、broker、注文API、実注文、実資金には進まない。
- Phase 3B前に追加で挟むべきオフライン監査の要否を判断する。

## 2. レビュー対象

Phase 2E-5短期3回確認として、以下のmanual runを対象にした。

| run | run_id | date | source | symbol | interval | steps | risk/audit |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 1回目 | `20260622_103430_shadow_USD_JPY_gmo-public` | `20260622` | `gmo-public` | `USD_JPY` | `M1` | 5 | enabled |
| 2回目 | `20260623_000652_shadow_USD_JPY_gmo-public` | `20260623` | `gmo-public` | `USD_JPY` | `M1` | 5 | enabled |
| 3回目 | `20260624_001906_shadow_USD_JPY_gmo-public` | `20260624` | `gmo-public` | `USD_JPY` | `M1` | 5 | enabled |

実行条件はいずれも `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk`、manual onlyである。

## 3. Phase 2E-5短期3回確認の要約

3回合計:

```text
candidate_count: 5
risk_allow_count: 3
risk_reject_count: 2
virtual_orders_count: 3
real_public_bid_ask_count: 5
ticker_kline_skew_reject_count: 7
public_ticker_fetch_error_count: 0
safety_violation_count: 0
raw_response_saved: false
Private API / APIキー / broker / 実注文: なし
```

run別:

| 指標 | 1回目 | 2回目 | 3回目 |
| --- | ---: | ---: | ---: |
| `exit_code` | 0 | 0 | 0 |
| `halted` | false | false | false |
| `candidate_count` | 2 | 1 | 2 |
| `risk_allow_count` | 1 | 1 | 1 |
| `risk_reject_count` | 1 | 0 | 1 |
| `virtual_orders_count` | 1 | 1 | 1 |
| `real_public_bid_ask_count` | 2 | 1 | 2 |
| `ticker_kline_skew_reject_count` | 2 | 3 | 2 |
| `public_ticker_fetch_error_count` | 0 | 0 | 0 |
| `safety_violation_count` | 0 | 0 | 0 |
| `raw_response_saved` | false | false | false |

## 4. Public shadow risk/audit安定性評価

安定性評価:

- 3回すべてで `exit_code=0`。
- 3回すべてで `halted=false`。
- 3回すべてで `REAL_PUBLIC_BID_ASK` を確認した。
- 3回すべてでcandidate生成を確認した。
- 3回すべてで `ALLOW_SHADOW` を確認した。
- 1回目と3回目で `REJECT_SHADOW` を確認した。
- ALLOW時のみvirtual resultが生成された。
- REJECT時にはvirtual resultが生成されていない。
- `safety_violation_count=0`。
- `broken/skipped=0`。
- `invalid_risk_row_count=0`。
- `kill_switch_count=0`、`kill_switch_active=false`。
- raw response保存なし。
- Private API、APIキー、broker、実注文、実資金はなし。

評価:

- Public shadow risk/auditの短期3runとして、基本的な安全契約、ログ相関、summary互換は安定している。
- REJECTが発生したrunでも、理由は `cooldown_active` として説明可能であり、virtual result抑止も維持された。
- 現時点で、Phase 3B準備へ進む前にPublic runを追加することは必須ではない。
- ただし、Private APIやAPIキーを扱う前に、Public側のSTOP / audit failure / duplicate / cooldown / run_id衝突を
  オフラインで最終確認する価値がある。

## 5. REAL_PUBLIC_BID_ASK評価

確認結果:

- 3回すべてで `REAL_PUBLIC_BID_ASK` を確認した。
- 3回合計の `real_public_bid_ask_count` は5件。
- candidate 5件すべての `spread_provenance` は `REAL_PUBLIC_BID_ASK`。
- 3run内の `synthetic_spread_reject_count` は0。
- `public_ticker_fetch_error_count` は0。
- `raw_response_saved=false` を維持した。
- Public APIのみであり、Private APIやAPIキーへfallbackしていない。

評価:

- GMO Public ticker由来bid/askが、3回連続でrisk/audit candidateへ到達した。
- kline-only synthetic spreadを使ってALLOW/REJECTを代替する挙動は、対象3runでは発生していない。
- `REAL_PUBLIC_BID_ASK` provenanceは、Phase 3B準備へ進む前のPublic側確認として合格扱いにできる。

## 6. ALLOW / REJECT / virtual result相関

1回目:

- BUY candidate `cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a` は `ALLOW_SHADOW`。
- 対応decisionは `risk_cand_20260622_103430_shadow_USD_JPY_gmo-public_3_buy_8c5a5b19351a_a2da9feb8233`。
- 同じcandidate_id / decision_idでvirtual resultが生成された。
- SELL candidate `cand_20260622_103430_shadow_USD_JPY_gmo-public_4_sell_b09947dad955` は
  `cooldown_active` により `REJECT_SHADOW`。
- REJECT candidateにvirtual resultは生成されていない。

2回目:

- BUY candidate `cand_20260623_000652_shadow_USD_JPY_gmo-public_4_buy_266813a7cb33` は `ALLOW_SHADOW`。
- 対応decisionは `risk_cand_20260623_000652_shadow_USD_JPY_gmo-public_4_buy_266813a7cb33_cdbebd4a075f`。
- 同じcandidate_id / decision_idでvirtual resultが生成された。
- REJECT candidateは発生していない。

3回目:

- BUY candidate `cand_20260624_001906_shadow_USD_JPY_gmo-public_3_buy_031170be866a` は `ALLOW_SHADOW`。
- 対応decisionは `risk_cand_20260624_001906_shadow_USD_JPY_gmo-public_3_buy_031170be866a_f9fbe9c76ab3`。
- 同じcandidate_id / decision_idでvirtual resultが生成された。
- BUY candidate `cand_20260624_001906_shadow_USD_JPY_gmo-public_4_buy_2571a53a70dc` は
  `cooldown_active` により `REJECT_SHADOW`。
- REJECT candidateにvirtual resultは生成されていない。

評価:

- ALLOW時だけvirtual resultが生成される契約は安定している。
- REJECT時にvirtual resultが生成されない契約は安定している。
- candidate_id / decision_id / virtual result相関は維持された。
- `cooldown_active` は期待どおり、連続candidateを抑制するrisk/audit制約として働いた。

## 7. skew / stale_data / NO_TRADE評価

確認結果:

- 1回目: `ticker_kline_skew_reject_count=2`。step 1/2 が `stale_data` で `NO_TRADE`。
- 2回目: `ticker_kline_skew_reject_count=3`。step 1/2/3 が `stale_data` で `NO_TRADE`。
- 3回目: `ticker_kline_skew_reject_count=2`。step 1/2 が `stale_data` で `NO_TRADE`。
- 3回合計の `ticker_kline_skew_reject_count` は7件。

評価:

- skew / stale_dataは3回すべてで発生したが、失敗ではない。
- 古いklineと現在tickerを混ぜない制約として機能し、candidate生成前に `NO_TRADE` へ安全fail closedした。
- skew発生stepではvirtual resultへ進んでいない。
- Public ticker fetch errorではなく、timestamp整合性の安全制約として説明できる。
- 現時点でskew閾値緩和はしない。閾値緩和は古いklineと現在tickerの混用を許しやすくし、
  provenanceの意味を弱める。
- Phase 3Bへ進む前に修正必須ではない。
- 将来の運用設計では、「最新足のみ利用」または「最新足だけをrisk/audit候補にする」設計レビューは検討余地がある。

## 8. safety評価

3runとaggregateで、次を確認した。

```text
real_order: false
private_api_used: false
api_key_used: false
no_order_execution: true
live_trading_environment_enabled: false
gmo_order_enabled: false
safety_violation_count: 0
invalid_risk_row_count: 0
kill_switch_count: 0
kill_switch_active: false
raw_response_saved: false
```

確認結果:

- Private API接続なし。
- APIキー入力・表示・保存なし。
- brokerなし。
- 実注文なし。
- 実資金なし。
- raw API response、headers、authorization header、secret、token、private key、`.env` は保存されていない。
- `backend/shadow_exports/` はgitignore対象で、tracked fileはない。

## 9. summarize結果

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

補足:

- aggregate全体でも broken/skipped、safety violation、invalid risk row、halted runsは0。
- `real_public_bid_ask_count=6` は、Phase 2E-4R以降の実run確認分を含む。
- `synthetic_spread_reject_count=12` は過去runを含むaggregate値であり、Phase 2E-5短期3run内では0だった。
- PnLは収益性判断に使わない。Phase 2Fの評価対象は安全性、相関、fail closed、summary互換である。

## 10. 合格判定

判定: **A: Public shadow risk/auditはPhase 3B準備へ進める水準**

理由:

- 3回すべてで `exit_code=0`、`halted=false`。
- 3回すべてで `REAL_PUBLIC_BID_ASK` を確認した。
- 3回すべてでcandidateと `ALLOW_SHADOW` を確認した。
- 1回目と3回目で説明可能な `cooldown_active` REJECTを確認した。
- ALLOW時のみvirtual resultが生成された。
- REJECT時にはvirtual resultが生成されていない。
- candidate / decision / virtual result相関が維持された。
- skew / stale_dataは `NO_TRADE` へ安全fail closedした。
- safety violation、broken/skipped、invalid risk row、kill switch active、raw response保存は0。
- Private API、APIキー、broker、実注文、実資金はない。

ただし、A判定はPhase 3B実装へ即進むという意味ではない。次はPhase 3B実装ではなく、
Phase 3B read-only公式仕様確認・実装設計、またはPhase 2Gオフライン最終デバッグ監査を別タスクで扱う。

## 11. Phase 3B前に挟むべき作業

推奨: **Phase 3B実装の前に、Phase 2G: Public shadow risk/audit オフライン最終デバッグ監査を半日程度で挟む。**

理由:

- Private API/APIキーを入れる前に、既存Public shadow risk/auditの境界を確認できる。
- STOP、audit failure、safety violation、duplicate、cooldown、run_id衝突をオフラインで確認できる。
- 秘密情報や実注文に触れずに問題を潰せる。
- Phase 3B read-only実装時に、Public側の未解決問題とPrivate API側の新規問題を混ぜずに済む。
- `shadow_exports/` tracking混入やraw response保存禁止など、生成物境界を再確認できる。

Phase 2Gで扱ってよい候補:

- STOPファイル / pre-gateの再確認。
- audit log write failure時のfail closed設計確認。
- duplicate candidate / duplicate decision / duplicate virtual resultの検出確認。
- `cooldown_active` の境界確認。
- run_id衝突・既存run directoryの扱い確認。
- summary / metadata / summarize互換確認。
- `shadow_exports/` / `analysis_exports/` tracking境界確認。
- 禁止import / 危険参照のread-only再監査。

Phase 2Gでも扱わないもの:

- gmo-public再実行。
- Private API接続。
- APIキー入力。
- `.env`表示・変更。
- broker。
- 注文API。
- 実注文。
- 実資金。

## 12. Phase 3Bへ進む前の条件

Phase 3B read-only公式仕様確認・実装設計へ進む前に、次を満たすことを推奨する。

```text
Phase 2Fレビュー完了
Phase 2Gオフライン最終デバッグ監査完了
Phase 3Aロードマップのread-only境界維持
公式仕様でread-only endpoint / 禁止endpointを確認
APIキー / secret管理手順のレビュー完了
注文系endpoint、broker、OrderRequest変換を範囲外に固定
backend公開API / frontend / main_readonly変更なしの方針維持
raw response / headers / credential保存なしの方針維持
```

## 13. まだ進まない範囲

```text
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
Live Verification Mode実装
本番公開API追加
frontend変更
DB本番化
認証
M5や他通貨への拡張
cron / schedule / 常駐bot
```

## 14. 結論

Phase 2Fの結論は次のとおり。

- Public shadow risk/auditは、Phase 3B準備へ進める水準にある。
- `REAL_PUBLIC_BID_ASK`、ALLOW、REJECT、virtual result相関、安全fail closed、summary互換は短期3回で安定している。
- skew / stale_dataは修正必須ではなく、古いklineと現在tickerを混ぜない安全制約として許容する。
- ただし、Phase 3B実装へ即進むのではなく、先にPhase 2Gオフライン最終デバッグ監査を挟むことを推奨する。
- 本レビューでは、Phase 3B、Private API、APIキー、broker、実注文、実資金には進まない。
