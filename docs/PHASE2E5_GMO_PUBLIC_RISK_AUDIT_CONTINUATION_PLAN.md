# Phase 2E-5: gmo-public risk/audit 継続確認計画

Phase 2E-5は、Phase 2E-4Rで実run上の `REAL_PUBLIC_BID_ASK`、`ALLOW_SHADOW`、virtual result、
candidate/decision/virtual result相関を確認できた後に、gmo-public risk/audit runを今後どの条件で
継続確認するかを定義する設計フェーズである。

今回は **設計docs作成のみ** であり、gmo-public再実行、コード修正、テスト追加、Phase 2E-5実行、
Phase 2F実行、Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進まない。

## 1. 目的

- gmo-public risk/audit runの継続確認計画を定義する。
- 実装ではなく、次回以降の手動確認の判断基準を整理する。
- 実資金検証ではなく、Public APIのみを使うlocal-only shadow risk/audit確認に限定する。
- Private API、APIキー、broker、実注文、実資金には進まない。
- Phase 2E-4Rで `REAL_PUBLIC_BID_ASK`、candidate、`ALLOW_SHADOW`、virtual result、ID相関を確認済みであることを前提にする。

## 2. 現在の到達点

Phase 2E-4Rレビューで確認済み:

```text
run_id: 20260622_100540_shadow_USD_JPY_gmo-public
source: gmo-public
symbol: USD_JPY
interval: M1
steps_executed: 5
exit_code: 0
halted: false
candidate_count: 1
risk_allow_count: 1
risk_reject_count: 0
virtual_orders_count: 1
ticker_bid_ask_used_count: 1
real_public_bid_ask_count: 1
ticker_kline_skew_reject_count: 3
safety_violation_count: 0
raw_response_saved: false
```

整理:

- 実runで `REAL_PUBLIC_BID_ASK` を確認済み。
- candidate生成を確認済み。
- `ALLOW_SHADOW` を確認済み。
- ALLOWに対応するvirtual resultを確認済み。
- candidate / decision / virtual resultのID相関を確認済み。
- safety violationは0。
- raw response保存なし。
- Private API / APIキー / broker / 実注文なし。
- 古い3 stepはticker/kline skewによりcandidate生成前の `NO_TRADE` へ安全に倒れた。

## 3. 継続確認の基本条件

初期条件は次に固定する。

```text
source = gmo-public
symbol = USD_JPY
interval = M1
steps = 5
risk/audit = enabled
execution = manual only
frequency = 1日1回まで
```

運用条件:

- 当日の日付を使う。
- 原則、市場時間中に実行する。
- 1回ごとに `summary.json`、`metadata.json`、audit logsを確認する。
- 1回ごとに `scripts.summarize_shadow_runs` でaggregateを確認する。
- 1回ごとにGit状態と `shadow_exports/` の追跡対象混入がないことを確認する。
- 生成物はcommitしない。
- raw responseは保存しない。
- ticker取得失敗、skew、stale、wide spreadをPrivate API、APIキー、brokerで補完しない。
- cron、schedule、常駐bot、自動再実行は使わない。

次回以降の手動実行指示に含めるコマンド候補:

```bash
cd /Users/naoikansui/Desktop/トレード
git status --short --branch
git check-ignore backend/shadow_exports || true
git ls-files | grep shadow_exports || true

cd /Users/naoikansui/Desktop/トレード/backend
python3 -m scripts.run_shadow_session \
  --source gmo-public \
  --symbol USD_JPY \
  --interval M1 \
  --date <YYYYMMDD> \
  --steps 5 \
  --enable-shadow-risk

python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
```

本書作成時点では上記を実行しない。

## 4. 成功条件

1回のgmo-public risk/audit確認を成功扱いにできる条件:

```text
exit_code = 0
halted = false
broken/skipped = 0
safety_violation_count = 0
invalid_risk_row_count = 0
raw_response_saved = false
private_api_used = false
api_key_used = false
broker / 実注文の痕跡なし
summary / metadata / audit logs が壊れない
ticker取得失敗なし、またはfail closedしてsummaryが壊れない
```

`REAL_PUBLIC_BID_ASK`が確認できるrunの成功条件:

- `real_public_bid_ask_count >= 1`
- `ticker_bid_ask_used_count >= 1`
- candidate / decision / virtual resultのID相関が確認できる。
- ALLOW時のみvirtual resultが出る。
- REJECT時にvirtual resultが出ない。
- `spread_provenance=REAL_PUBLIC_BID_ASK` がPublic ticker由来として記録される。
- safety flagsが全てno-order / readonlyである。

HOLD中心でcandidateが出ない場合:

- `exit_code=0`、`halted=false`、safety violation 0、summary正常であれば失敗にしない。
- そのrunは「観察完了 / candidate未発生」として扱う。
- 複数回連続でcandidateが出ない場合は、市場時間、直近kline、signal分布、steps条件をレビューする。
- candidateが出ないことを理由にPrivate API、APIキー、broker、実注文へ進まない。

PnLについて:

- virtual PnLは収益性判断に使わない。
- Phase 2E-5の評価対象は、安全性、ログ品質、相関、fail closed、summary互換である。

## 5. 保留条件

次は失敗ではなく、保留または追加観察として扱う。

```text
HOLD / NO_TRADE中心でcandidateが出ない
ticker/kline skewでNO_TRADEになる
spread_too_wideでREJECT
ticker staleでREJECTまたはNO_TRADE
ticker取得失敗だがsummaryが壊れずfail closedする
```

保留時に確認すること:

- run日時が市場時間中か。
- `--date` が当日であるか。
- BUY/SELL signalが出ていたか、HOLD中心だったか。
- `signal_decision_log.jsonl` の `reason_codes` が説明可能か。
- `ticker_kline_skew_reject_count`、`ticker_stale_count`、`public_ticker_fetch_error_count` がsummaryに反映されているか。
- REJECT時にvirtual resultが出ていないか。
- `raw_response_saved=false` とno-order safety flagsが維持されているか。

保留が続く場合:

- まず運用タイミングと直近kline条件を見直す。
- それでも `REAL_PUBLIC_BID_ASK` が複数回まったく確認できない場合だけ、「最新足だけを使う設計レビュー」へ戻る。
- skew閾値緩和やticker timestamp基準candidate化は、別設計なしに採用しない。

## 6. 停止条件

次のいずれかが出た場合は、gmo-public risk/audit継続確認を止めてレビューへ戻る。

```text
safety_violation_count > 0
broken/skipped > 0
invalid_risk_row_count > 0
raw_response_saved = true
Private API / APIキー / broker / 実注文の痕跡
exit_code = 2
kill_switch_active = true
summary破損
candidate / decision / virtual result相関不整合
REJECT時にvirtual resultが出る
ALLOW時のcandidate_id / decision_idが欠落または不一致
shadow_exports がgit tracking対象になる
```

停止時の扱い:

- 当日の追加runを行わない。
- 該当runを安全扱いに書き換えない。
- 生成物をcommitしない。
- 原因整理、docsレビュー、必要ならoffline test設計へ戻る。
- Private API、APIキー、broker、実注文で原因を回避しない。

## 7. ticker/kline skew評価方針

- ticker/kline skewは必ずしも失敗ではない。
- 現在tickerと古いklineを混ぜないための安全制約である。
- skewによりcandidate生成前の `NO_TRADE` へ倒れるのは、Phase 2E-3/2E-4.5/2E-4Rの設計に沿う。
- skewが多発して `REAL_PUBLIC_BID_ASK` candidateがほとんど確認できない場合は、「最新足だけを使う設計レビュー」へ戻る。
- skew閾値緩和は現時点では非推奨である。古いklineと現在tickerの混用を許しやすくなり、provenanceの意味が弱くなる。
- ticker timestamp基準candidateは、signal timestamp、audit相関、market_data_timestampの意味が変わるため、別設計が必要である。
- skewを理由にPrivate API、APIキー、broker、実注文へ進まない。

## 8. 評価指標

継続確認では最低限、次を毎回見る。

```text
runs_count
broken/skipped
candidate_count
risk_allow_count
risk_reject_count
virtual_orders_count
virtual_result_count
real_public_bid_ask_count
ticker_bid_ask_used_count
ticker_kline_skew_reject_count
ticker_missing_count
ticker_stale_count
ticker_invalid_count
synthetic_spread_reject_count
spread_too_wide_count
public_ticker_fetch_error_count
safety_violation_runs_count
invalid_risk_row_count
kill_switch_count
kill_switch_active_runs_count
raw_response_saved
```

REJECT理由の分布:

- `reject_reasons` を毎回確認し、`synthetic_spread_not_allowed`、`cooldown_active`、`spread_too_wide`、
  `stale_data`、`invalid_data` などが説明可能かを見る。
- REJECTが増えること自体は失敗ではないが、理由がsummary/audit logsで説明できない場合は保留または停止候補にする。
- REJECT時にvirtual resultが生成されていないことを必ず確認する。

評価軸:

- `REAL_PUBLIC_BID_ASK`: Public ticker由来bid/askだけが到達しているか、syntheticやunknownが混入していないか。
- ALLOW: `ALLOW_SHADOW`が出た場合、candidateとdecisionのIDが一致し、no-order safety flagsが維持されているか。
- REJECT: reasonが説明可能で、virtual resultを生成していないか。
- virtual result: ALLOW時だけ生成され、candidate/decisionと相関し、実注文ではなくvirtual-onlyであるか。

相関確認:

- `candidate_log.jsonl` の `candidate_id`
- `risk_decision_log.jsonl` の `candidate_id` / `decision_id`
- `virtual_result_log.jsonl` の `candidate_id` / `decision_id`
- summaryの `risk_allow_count` / `risk_reject_count` / `virtual_result_count`

PnL:

- `final_unrealized_pnl` やaggregateのpnlは、Phase 2E-5では収益性評価に使わない。
- PnLはvirtual fillの計算が壊れていないかを見る補助情報に留める。

## 9. 確認回数の設計

短期確認:

- 3回の `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk` manual run。
- 1日1回まで。
- 各run後にsummary、audit logs、Git境界を確認する。

中期確認:

- 5〜10回のmanual run。
- 連続実行ではなく、市場時間中の別タイミングで行う。
- skew、HOLD、ALLOW、REJECT、fetch errorの分布を観察する。

最低通過条件:

- 少なくとも3回連続で safety violation 0。
- 少なくとも3回連続で broken/skipped 0。
- 少なくとも3回連続で raw response保存なし。
- 少なくとも3回連続で Private API / APIキー / broker / 実注文なし。
- 3回のうち少なくとも1回以上、`REAL_PUBLIC_BID_ASK` candidateまたは説明可能なfail closedを確認する。

推奨判断:

- Phase 2E-4Rで1回のALLOW/virtual result相関は確認済みだが、安定性判断にはまだ少ない。
- Phase 2Fへ進む前に、短期3回を最低ライン、中期5〜10回をより望ましい観察範囲とする。
- 今回は実行しない。

## 10. Phase 2Fへ進む条件

Phase 2Fは、Private APIではなく **Public shadow risk/auditのレビュー・安定性評価・運用計画** として定義する。

Phase 2F設計へ進める条件:

```text
複数回のgmo-public risk/audit runで safety violation 0
broken/skipped 0
invalid_risk_row_count 0
raw_response_saved=false 維持
Private API / APIキー / broker / 実注文なし
REAL_PUBLIC_BID_ASKが複数回確認できる、または確認できない理由が安全に説明できる
ALLOW / REJECT / virtual resultの相関が壊れない
REJECT時にvirtual resultが出ない
STOP / audit failure / kill switchの設計が維持されている
summary / metadata / summarize互換が維持されている
shadow_exportsがgit tracking対象になっていない
```

Phase 2Fで扱ってよい候補:

- Public shadow risk/audit runのレビュー。
- 複数runの安定性評価。
- skew / reject / allow分布の整理。
- manual運用計画の更新。
- local-only生成物境界の再確認。

Phase 2Fでも扱わないもの:

- Private API。
- APIキー。
- broker。
- 実注文。
- 実資金。
- 自動売買。
- Live Verification Mode。

## 11. まだ進まない範囲

Phase 2E-5設計および次回実行指示では、次へ進まない。

```text
Private API
APIキー
broker
実注文
実資金
自動売買
Live Verification Mode
本番公開API追加
frontend変更
DB本番化
認証
M5や他通貨への拡張
cron / schedule / 常駐bot
Render / Vercel設定変更
```

## 12. 次の実行指示に含めるべき内容

Phase 2E-5実行指示を作る場合は、次を必ず含める。

- 1回だけ実行する。
- `USD_JPY / M1 / steps 5 / --enable-shadow-risk` に固定する。
- 当日の日付を使う。
- 原則、市場時間中に実行する。
- 実行前に `git status --short --branch`、`git check-ignore backend/shadow_exports`、
  `git ls-files | grep shadow_exports || true` を確認する。
- 実行後に `summary.json`、`metadata.json`、`signal_decision_log.jsonl`、candidate/risk/virtual logsを確認する。
- 実行後に `python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown` を確認する。
- `REAL_PUBLIC_BID_ASK`、ALLOW、REJECT、virtual result、skew、fetch error、safetyを報告する。
- Git管理確認を行う。
- `shadow_exports/`、aggregate出力、実APIレスポンスはcommitしない。
- commit/pushなし。
- Private API、APIキー、broker、実注文なし。
- ChatGPTへ貼れるMarkdown最終報告形式にする。

## 13. docs / Git境界

- 本計画はdocs-onlyである。
- backendコード、frontendコード、`backend/app/main.py`、`backend/app/main_readonly.py`は変更しない。
- `shadow_exports/` と `analysis_exports/` はcommitしない。
- 実run生成物、aggregate CSV/Markdown、raw API response、secret、APIキー、Private情報はcommitしない。
- secret grepで禁止語に一致した場合は、禁止語の説明、固定falseフラグ、設計上の禁止範囲だけであることを確認する。

## 14. Phase 2E-5設計の結論

Phase 2E-5では、gmo-public risk/audit runを闇雲に増やさず、次の方針で継続確認する。

- 初期条件は `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk`。
- manual only、1日1回まで。
- 短期3回、中期5〜10回を目安に安全性・ログ品質・相関・fail closedを確認する。
- HOLD、skew、wide spread、stale、fetch error fail closedは保留/追加観察に分類する。
- safety violation、broken summary、raw response保存、Private/APIキー/broker/実注文痕跡、相関不整合は停止条件にする。
- Phase 2FはPublic shadow risk/auditのレビュー・安定性評価・運用計画であり、Private APIや実注文ではない。
