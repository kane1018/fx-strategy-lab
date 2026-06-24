# Phase 3C: Live Verification Mode implementation design review

Phase 3C実装設計レビューでは、Live Verification Mode設計を前提に、将来の実装を安全な小フェーズへ分割する。

今回は **設計レビュー・docs化のみ** である。Live Verification Mode実装、order intent実装、broker実装、
OrderRequest実装、注文API実装、実注文、実資金検証、自動売買、本番公開API追加には進まない。

## 1. 目的

- Live Verification Mode実装前の設計レビューを行う。
- order intent実装前に責務と禁止境界を整理する。
- read-only precheck / risk decision / order intent の接続を設計する。
- brokerや注文APIを作る前の安全境界を固定する。
- Phase 3C実装をmock / dry-runだけで段階分割する。
- Phase 3Dへ進む前に必要なレビューを明確にする。

これは実装ではない。実注文ではない。実資金検証ではない。

## 2. 前提

完了済み:

- Phase 3B-4で `account/assets`、`openPositions`、`activeOrders` のread-only接続確認が完了。
- Phase 3CでLive Verification Modeの目的、許可範囲、禁止範囲、注文前read-onlyチェック、
  risk decision / candidate / order intent相関、kill switch / STOP条件をdocs化済み。
- Public shadow risk/auditでは、candidate、risk decision、virtual resultのID相関とfail closed集計が既にある。

今回のレビューで変えないもの:

- Private API connection script。
- private read-only client / schemas / errors。
- shadow risk / audit / aggregate実装。
- backend公開API。
- frontend。
- broker / OrderRequest / 注文API。

## 3. 実装フェーズ分割案

Phase 3C実装は、少なくとも次の4段階に分ける。

```text
Phase 3C-1:
order intent / readonly precheck / live verification state のmocked実装

Phase 3C-2:
candidate / risk decision / order intent のID相関テスト

Phase 3C-3:
Live Verification Mode dry-run統合テスト

Phase 3D前:
broker / 注文API実装前レビュー
```

この分割は、実装を進める場合でもbrokerや注文APIに直行しないための安全境界である。

追記:

- Phase 3C-1 mocked core、Phase 3C-2 ID相関テスト、Phase 3C-3 dry-run統合、
  Phase 3D前レビュー、Phase 3D-0公式仕様・危険endpoint再レビュー、Phase 3D-1 order review model /
  final checklist mocked実装は完了済みである。
- Phase 3D-1で追加した `OrderReview` と `FinalOrderChecklist` はreview-onlyであり、
  broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、実注文には進んでいない。

## 4. Phase 3C-1: mocked core implementation

目的:

- order intent、readonly precheck、live verification stateの純粋ドメイン実装をmocked / dry-run限定で作る。
- 実HTTP接続や実注文なしに、入力制約とfail closed条件を単体テストで固定する。

変更してよい範囲の候補:

```text
backend/app/live_verification/
backend/app/tests/test_live_verification_*.py
docs/PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md
docs/PROJECT_STATUS.md
docs/CODEX_HANDOFF.md
```

作るものの候補:

```text
backend/app/live_verification/
  __init__.py
  intent.py
  precheck.py
  state.py
  errors.py

backend/app/tests/test_live_verification_intent.py
backend/app/tests/test_live_verification_precheck.py
backend/app/tests/test_live_verification_state.py
backend/app/tests/test_live_verification_no_order_imports.py
```

作らないもの:

- broker。
- OrderRequest。
- 注文API client。
- 注文payload builder。
- 実HTTP POST。
- 実Private API接続追加。
- CLI。
- DB model。
- frontend。

検証方法:

- mocked unit testsのみ。
- `python3 -m pytest -q app/tests/test_live_verification_*.py`
- `python3 -m pytest -q app/tests -k "live_verification or private_readonly"`
- `ruff check .`
- no-order-import guard。
- forbidden word guard。

成功条件:

- `USD_JPY` と100通貨以外を拒否する。
- risk decisionがALLOW相当でない場合にorder intentを作らない。
- read-only precheck失敗時にorder intentを作らない。
- 既存建玉あり、未約定注文ありでfail closedする。
- raw response、headers、signature、credentialを保持しない。
- broker / OrderRequest / submit / send / place / cancel / amend が混入しない。

停止条件:

- 実HTTP接続が入った。
- broker、OrderRequest、注文payload builderが入った。
- APIキー / secret / `.env` を読む実装が入った。
- raw responseやheadersを保持する設計になった。
- 複数order intentを許容した。

## 5. Phase 3C-2: ID correlation tests

目的:

- candidate / risk decision / readonly precheck / order intent / verification run のID相関を壊さない。
- Phase 2Eのcandidate / decision相関を、実注文payloadではなくorder intentまでに接続する。

変更してよい範囲の候補:

```text
backend/app/live_verification/
backend/app/tests/test_live_verification_correlation.py
backend/app/tests/test_live_verification_no_order_imports.py
```

作るもの:

- `candidate_id` 必須チェック。
- `decision_id` 必須チェック。
- `readonly_precheck_id` 必須チェック。
- `verification_run_id` 一致チェック。
- 同一 `verification_run_id` 内のorder intent 1件制限。
- risk decision ALLOW以外の拒否。

作らないもの:

- 実注文API。
- broker adapter。
- 注文ID / 約定IDの取得。
- 実データfixture。
- Private API追加接続。

検証方法:

- mocked candidate / decision / precheck / intent fixtureだけを使う。
- REJECT decision、missing ID、mismatched run、duplicate intentをfail closedとして確認する。
- credentialやraw responseをfixture化しない。

成功条件:

- 1 candidateに対して1 decisionだけを許可する。
- 1 verification runに対して1 order intentだけを許可する。
- ID不整合は例外またはSTOP状態として扱う。
- ALLOW以外でintentを作れない。

停止条件:

- ID不整合が許容される。
- 複数intentが許容される。
- REJECT decisionからintentが作れる。
- OrderRequest変換が混入する。

## 6. Phase 3C-3: dry-run integration

目的:

- Live Verification Modeのdry-run統合フローを、実注文なしで検証する。
- READY_FOR_ORDER_REVIEWまで到達できるが、実注文状態へは進まないことを確認する。

変更してよい範囲の候補:

```text
backend/app/live_verification/
backend/app/tests/test_live_verification_dry_run.py
backend/scripts/check_live_verification_dry_run.py
```

scriptを作る場合の制限:

- local only。
- manual only。
- mocked input only。
- Private API追加接続なし。
- APIキー確認なし。
- `.env`確認なし。
- raw response保存なし。
- 実データ保存なし。
- brokerなし。
- 注文APIなし。

作るもの:

- dry-run用のin-memory input。
- state transition確認。
- sanitized stdout summary。
- READY_FOR_ORDER_REVIEWで停止する流れ。

作らないもの:

- 実HTTP POST。
- 実注文可能なclient。
- broker adapter。
- 注文payload builder。
- frontend操作画面。
- cron / schedule / 常駐bot。

検証方法:

- dry-run統合テスト。
- state transition test。
- no-order-import guard。
- forbidden endpoint guard。

成功条件:

- `INIT -> READONLY_PRECHECK -> RISK_DECISION_CONFIRMED -> ORDER_INTENT_CREATED -> MANUAL_CONFIRMATION_REQUIRED -> READY_FOR_ORDER_REVIEW` まで到達できる。
- READY_FOR_ORDER_REVIEWで停止する。
- 実注文状態が存在しない。
- retry / loop / automationがない。

停止条件:

- READY_FOR_ORDER_REVIEWを越える状態が入った。
- 実注文可能なpayloadやclientが入った。
- brokerまたは注文APIへのimportが入った。
- 実データやcredentialを保存する。

## 7. Phase 3D前: broker / order API実装前レビュー

目的:

- Phase 3C dry-run完了後も、すぐにbrokerや注文APIを作らない。
- 実注文可能な実装へ進む前に、別レビューでリスクと承認条件を確認する。

必須レビュー:

```text
Phase 3C-1実装レビュー
Phase 3C-2相関テストレビュー
Phase 3C-3dry-run統合レビュー
broker / order API実装前レビュー
100通貨・1回限定の明示承認
```

このレビューが完了するまでは、broker / OrderRequest / 注文APIを作らない。

## 8. order intent責務設計

order intentは、実注文リクエストではなく、注文直前の意思決定記録である。

含める候補:

```text
order_intent_id
candidate_id
decision_id
verification_run_id
symbol
side
units
mode
manual_confirmation_required
readonly_precheck_passed
risk_decision_status
created_at
expires_at
```

制約:

```text
unitsは100固定
symbolはUSD_JPYのみ
modeはlive_verificationのみ
risk_decision_statusはALLOW相当のみ
manual_confirmation_requiredはtrue固定
readonly_precheck_passedはtrue必須
expires_atを過ぎたintentは無効
```

保持してはいけないもの:

- APIキー。
- secret。
- signature。
- request headers。
- raw response。
- 注文ID。
- 約定ID。
- 残高金額詳細。
- 建玉詳細。
- 実注文payload。

送ってはいけない先:

- broker。
- Private API order endpoint。
- frontend。
- backend公開API。

保存方針:

- Phase 3C-1ではin-memoryまたはunit test fixtureのみ。
- 実データをcommitしない。
- JSONL / DB / file保存は別レビューまで行わない。
- 将来保存する場合も、sanitized summaryだけに限定し、raw responseやcredentialを含めない。

## 9. read-only precheck責務設計

Phase 3B-4で成功済みの3 endpointを、注文前precheckの入力にする。

対象:

```text
GET /private/v1/account/assets
GET /private/v1/openPositions
GET /private/v1/activeOrders
```

Phase 3C-1では実接続しない。mocked inputだけでprecheck判定を実装する。

入力候補:

```text
symbol
verification_run_id
expected_units
mode
account_assets_status
open_positions_status
active_orders_status
open_positions_count
active_orders_count
raw_response_saved
headers_saved
credentials_printed
retry_attempted
```

出力候補:

```text
readonly_precheck_id
verification_run_id
account_assets_ok
open_positions_ok
active_orders_ok
has_open_positions
has_active_orders
readonly_precheck_passed
fail_reason
```

停止条件:

```text
account/assets失敗
openPositions失敗
activeOrders失敗
既存建玉あり
未約定注文あり
raw response保存あり
headers保存あり
credentials表示あり
retry attempted
symbolがUSD_JPY以外
expected_unitsが100以外
modeがlive_verification以外
```

責務境界:

- precheckは注文を作らない。
- precheckはorder intentを直接送信しない。
- precheckはPrivate API clientを直接拡張しない。
- precheckはsanitized count / booleanだけを扱う。

## 10. live verification state設計

状態候補:

```text
INIT
READONLY_PRECHECK
RISK_DECISION_CONFIRMED
ORDER_INTENT_CREATED
MANUAL_CONFIRMATION_REQUIRED
READY_FOR_ORDER_REVIEW
STOPPED
FAILED
```

許可する遷移:

```text
INIT -> READONLY_PRECHECK
READONLY_PRECHECK -> RISK_DECISION_CONFIRMED
RISK_DECISION_CONFIRMED -> ORDER_INTENT_CREATED
ORDER_INTENT_CREATED -> MANUAL_CONFIRMATION_REQUIRED
MANUAL_CONFIRMATION_REQUIRED -> READY_FOR_ORDER_REVIEW
any state -> STOPPED
any state -> FAILED
```

禁止する遷移:

```text
READY_FOR_ORDER_REVIEW -> ORDER_SENT
READY_FOR_ORDER_REVIEW -> BROKER_SUBMIT
READY_FOR_ORDER_REVIEW -> PRIVATE_ORDER_API
FAILED -> READY_FOR_ORDER_REVIEW
STOPPED -> READY_FOR_ORDER_REVIEW
```

Phase 3C-1〜3C-3では、READY_FOR_ORDER_REVIEWまでで停止する。
実注文へ進む状態は作らない。

状態ごとの責務:

| state | 意味 | 次へ進む条件 | fail closed |
| --- | --- | --- | --- |
| `INIT` | dry-run開始前 | local / manual / mode検証OK | 不正mode |
| `READONLY_PRECHECK` | precheck検証中 | 3 endpoint相当のsanitized result OK | 建玉あり、未約定あり |
| `RISK_DECISION_CONFIRMED` | ALLOW decision確認済み | candidate / decision ID相関OK | ALLOW以外 |
| `ORDER_INTENT_CREATED` | intent作成済み | intent制約OK | 100通貨以外、USD_JPY以外 |
| `MANUAL_CONFIRMATION_REQUIRED` | 人間確認待ち | 明示確認あり | 確認なし |
| `READY_FOR_ORDER_REVIEW` | 実注文前レビュー可能 | ここで停止 | 次状態作成禁止 |
| `STOPPED` | 安全停止 | なし | 再開禁止 |
| `FAILED` | エラー停止 | なし | 再開禁止 |

## 11. ID相関設計

扱うID:

```text
signal_id
candidate_id
decision_id
readonly_precheck_id
order_intent_id
verification_run_id
```

必須条件:

```text
candidate_idがないorder intentは禁止
decision_idがないorder intentは禁止
readonly_precheck_idがないorder intentは禁止
risk decisionがALLOW以外ならorder intent作成禁止
read-only precheckが失敗ならorder intent作成禁止
同一verification_run内でorder intentは1件まで
```

相関ルール:

- `verification_run_id` は全レコードで一致する。
- `candidate_id` は `decision_id` と1対1で対応する。
- `decision_id` はALLOW相当でなければならない。
- `readonly_precheck_id` はorder intent作成前にpassしている。
- `order_intent_id` は `candidate_id`、`decision_id`、`readonly_precheck_id` を参照する。
- `signal_id` は任意だが、存在する場合は `candidate_id` の元signalとして相関できる必要がある。

不整合時:

- order intentを作らない。
- stateをFAILEDまたはSTOPPEDにする。
- 実注文系へ進まない。

## 12. Phase 3C-1で作ってよいもの

Phase 3C-1はmocked / dry-run限定にする。

作ってよい候補:

```text
backend/app/live_verification/
  __init__.py
  intent.py
  precheck.py
  state.py
  errors.py

backend/app/tests/test_live_verification_intent.py
backend/app/tests/test_live_verification_precheck.py
backend/app/tests/test_live_verification_state.py
backend/app/tests/test_live_verification_no_order_imports.py
```

作ってよい型の候補:

```text
OrderIntent
ReadonlyPrecheckResult
LiveVerificationState
LiveVerificationContext
LiveVerificationError
```

作ってよい関数の候補:

```text
build_order_intent_from_allowed_decision()
evaluate_readonly_precheck()
transition_live_verification_state()
assert_single_intent_per_run()
assert_no_order_capability()
```

すべてpure / mocked / dry-run限定とし、外部通信、file write、broker呼び出しを持たない。

## 13. Phase 3C-1で作らないもの

Phase 3C-1では次を作らない。

```text
broker
OrderRequest
注文API client
注文payload builder
close position
cancel order
実HTTP POST
実注文
実資金検証
frontend実行画面
cron / schedule / 常駐bot
```

追加で作らないもの:

- `.env` loader。
- APIキー存在確認。
- Private API追加接続。
- DB table。
- migration。
- production route。
- background worker。
- retry queue。

## 14. テスト方針

最低限必要なテスト:

```text
order intentは100通貨以外を拒否
USD_JPY以外を拒否
risk decisionがALLOW以外なら拒否
read-only precheck失敗なら拒否
既存建玉ありなら拒否
未約定注文ありなら拒否
同一verification_run内で複数intent拒否
credentials / raw response / headersを保持しない
broker importなし
OrderRequestなし
submit/send/place/cancel/amendなし
```

Phase 3C-1の追加テスト候補:

- `mode != live_verification` を拒否。
- `manual_confirmation_required is not True` を拒否。
- expired intentを拒否。
- `readonly_precheck_id` 欠損を拒否。
- `verification_run_id` 不一致を拒否。
- STOPPED / FAILED からREADY_FOR_ORDER_REVIEWへ戻れない。
- READY_FOR_ORDER_REVIEWの先にORDER_SENT相当の状態が存在しない。

使ってよいfixture:

- mocked candidate。
- mocked risk decision。
- mocked readonly precheck summary。
- dummy IDs。

使ってはいけないfixture:

- 実API response。
- raw response全体。
- request headers。
- signature。
- APIキー / secret。
- 注文ID / 約定IDの実値。

## 15. Phase 3D前レビュー条件

Phase 3Dへ進む前に、次のレビューを必須にする。

```text
Phase 3C-1実装レビュー
Phase 3C-2相関テストレビュー
Phase 3C-3dry-run統合レビュー
broker / order API実装前レビュー
100通貨・1回限定の明示承認
```

各レビューで確認すること:

- mocked / dry-run範囲を逸脱していない。
- READY_FOR_ORDER_REVIEWで停止している。
- 実注文状態が存在しない。
- broker / OrderRequest / 注文APIが未実装。
- read-only precheckが直前に成功している。
- Git差分にsecretや実データがない。
- `shadow_exports/` / `analysis_exports/` がtrackedされていない。

## 15a. Phase 3C-1実装結果

Phase 3C-1では、設計レビューで候補化したmocked coreを最小実装した。

追加した範囲:

```text
backend/app/live_verification/
backend/app/tests/test_live_verification_*.py
```

実装したもの:

- order intentの型、決定論的ID、生成関数、validation。
- read-only precheck resultの型、fail closed reason、validation。
- live verification stateの状態定義と遷移ルール。
- Live Verification用errors。
- no-order-import guard。

実装していないもの:

- broker。
- OrderRequest。
- 注文API。
- 注文payload builder。
- Private API追加接続。
- APIキー確認。
- `.env`確認。
- 実注文。
- 実資金検証。
- frontend。
- 本番公開API。

Phase 3C-1は、READY_FOR_ORDER_REVIEWまでのmocked coreで停止する。
Phase 3C-2、Phase 3C-3、Phase 3Dへは別タスクの明示指示なしに進まない。

## 15b. Phase 3C-2実装結果

Phase 3C-2では、Phase 3C-1のmocked coreを前提にID相関テストを追加した。

追加した範囲:

```text
backend/app/live_verification/correlation.py
backend/app/tests/test_live_verification_id_correlation.py
```

確認したもの:

- signal、candidate、risk decision、readonly precheck、order intent、verification runのID相関。
- 必須ID欠損時のfail closed。
- verification_run_id不整合時のfail closed。
- ALLOW系以外、precheck failed、USD_JPY以外、100通貨以外、manual confirmationなしの拒否。
- 同一verification_run_id内の2件目intent拒否と、別runでのintent生成許可。
- READY_FOR_ORDER_REVIEWまでで停止し、注文送信状態へ進まないこと。
- no-order-import guard。

実装していないもの:

- broker。
- OrderRequest。
- 注文API。
- Private API追加接続。
- APIキー確認。
- `.env`確認。
- 実注文。
- 実資金検証。
- frontend。
- 本番公開API。

Phase 3C-2は、ID相関のpure mocked testsで停止する。
Phase 3C-3、Phase 3D、broker、注文API、実注文、実資金検証へは別タスクの明示指示なしに進まない。

## 15c. Phase 3C-3実装結果

Phase 3C-3では、Phase 3C-1 / 3C-2のmocked coreを前提にdry-run統合テストを追加した。

追加した範囲:

```text
backend/app/live_verification/dry_run.py
backend/app/tests/test_live_verification_dry_run.py
```

確認したもの:

- read-only precheck、risk decision、ID correlation、order intent、state transitionの統合。
- `INIT -> READONLY_PRECHECK -> RISK_DECISION_CONFIRMED -> ORDER_INTENT_CREATED -> MANUAL_CONFIRMATION_REQUIRED -> READY_FOR_ORDER_REVIEW`。
- READY_FOR_ORDER_REVIEWで停止し、注文送信状態へ進まないこと。
- precheck failed、ALLOW系以外、verification_run_id不整合、同一run内2件目intentのfail closed。
- unsupported symbol / units、manual confirmationなし、open position / active orderあり、安全フラグ違反のfail closed。
- no-order-import guard。

実装していないもの:

- broker。
- OrderRequest。
- 注文API。
- 注文payload builder。
- Private API追加接続。
- APIキー確認。
- `.env`確認。
- 実注文。
- 実資金検証。
- frontend。
- 本番公開API。

Phase 3C-3は、READY_FOR_ORDER_REVIEWまでのpure mocked dry-run統合テストで停止する。
Phase 3D、broker、注文API、実注文、実資金検証へは別タスクの明示指示なしに進まない。

## 16. まだ進まない範囲

今回も次へ進まない。

```text
Live Verification Mode実装
order intent実装
broker実装
OrderRequest実装
注文API実装
注文変更API
注文取消API
決済API
実注文
実資金検証
自動売買
本番公開API
frontend変更
backend/app/main_readonly.py変更
DB本番化
認証実装
cron / schedule / 常駐bot
```

## 17. 結論

Phase 3C実装設計レビューでは、Live Verification Mode実装を3つのmock / dry-run段階とPhase 3D前レビューへ分割した。

結論:

- Phase 3C-1では、order intent / readonly precheck / live verification stateのpure mocked実装だけを候補にする。
- Phase 3C-2では、candidate / risk decision / readonly precheck / order intentのID相関テストだけを扱う。
- Phase 3C-3では、READY_FOR_ORDER_REVIEWまでのdry-run統合テストだけを扱う。
- Phase 3D前には、broker / order API実装前レビューと100通貨・1回限定の明示承認が必須である。
- このレビューでは、Live Verification Mode実装、order intent実装、broker、OrderRequest、注文API、実注文、
  実資金検証には進まない。

追記:

- Phase 3C-1 mocked core実装は後続タスクで完了済み。
- Phase 3C-2 ID相関テストも後続タスクで完了済み。
- Phase 3C-3 dry-run統合テストも後続タスクで完了済み。
- Phase 3D前 broker / order API実装前レビューも後続タスクで完了済み。判定は
  **A: Phase 3D-0 公式仕様・危険endpoint再レビューへ進んでよい**。
- ただし、Phase 3D-0、broker、OrderRequest、注文API、
  実注文、実資金検証には進んでいない。
