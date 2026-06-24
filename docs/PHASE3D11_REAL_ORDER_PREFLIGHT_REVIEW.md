# Phase 3D-11: 実注文直前preflightレビュー

Phase 3D-11では、Phase 3D-10Bまでで強化した no-network / no-secret / no-order chain を前提に、
実注文へ進む前のpreflight条件をdocs-onlyで整理する。

今回は **設計レビュー・docs化のみ** である。APIキー確認、`.env`確認、HTTP request実装、
HTTP client import、HTTP POST、headers生成、request body生成、actual signature生成、broker、
`OrderRequest`、real order API client、実注文、実資金検証には進まない。

## 1. Phase 3D-11の目的

目的:

- 実注文直前preflightレビューを行う。
- APIキー確認前の最終安全条件を整理する。
- HTTP request / 署名実装前の最終安全条件を整理する。
- 実注文最終承認前のチェックリストを作成する。
- 直前read-only precheck、技術状態、注文条件、ユーザー承認、停止条件を分離して明文化する。
- 100通貨、`USD_JPY`、1回限定、manual onlyの制約を実注文直前まで維持する。

今回の扱い:

- 今回は実装ではない。
- 今回はPrivate API接続ではない。
- 今回はAPIキー確認ではない。
- 今回は`.env`確認ではない。
- 今回はHTTP request実装ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. 実注文直前preflightの定義

preflightとは、実注文に進む前に、技術状態・安全条件・口座状態・注文条件・ユーザー承認・停止条件を
一括で確認する最終レビューである。

Phase 3D-11ではpreflight条件をdocs化するだけで停止する。

Phase 3D-11で行わないこと:

- HTTP request実装。
- 署名実装。
- APIキー確認。
- `.env`確認。
- Private API追加接続。
- 実注文。
- 実資金検証。

preflightは実注文実行の代替ではない。1項目でも未確認またはNGなら、次工程へ進まない。

## 3. 現在のno-network chain

現在の安全なno-network chain:

```text
OrderIntent
-> OrderReview
-> FinalOrderChecklist
-> NoNetworkBrokerBoundaryResult
-> MockedOrderPayloadCandidate
-> DisabledOrderClientPlan
-> SignatureHttpRequestDesignModel
-> DisabledHttpRequestClientSkeletonPlan
```

まだ進まない導線:

```text
DisabledHttpRequestClientSkeletonPlan
-/-> real HTTP request
-/-> API-KEY / API-SIGN / API-TIMESTAMP
-/-> headers
-/-> request body
-/-> actual signature
-/-> POST /private/v1/order
-/-> broker
-/-> OrderRequest
-/-> real order API client
-/-> 実注文
```

このchainは、実注文可能状態ではない。実注文前レビュー可能状態であり、実送信不能であることを安全性として扱う。

## 4. 直前read-only precheck条件

将来、実注文直前には、最低限次のread-only endpointを確認する。

```text
GET /private/v1/account/assets
GET /private/v1/openPositions
GET /private/v1/activeOrders
```

必須条件:

- `account/assets` が成功している。
- `openPositions` が成功している。
- `activeOrders` が成功している。
- 既存建玉なし。
- 未約定注文なし。
- read-only結果はsanitized summaryのみ。
- raw response保存なし。
- headers保存なし。
- signature保存なし。
- APIキー / secret表示なし。
- APIキー / secret値のログ出力なし。
- 実APIレスポンスのfixture化なし。

注意:

- Phase 3D-11では実接続しない。
- read-only precheckの実接続は、別タスク・明示承認後に限定する。
- precheck結果が1つでも失敗、未確認、または曖昧な場合は実注文へ進まない。

## 5. 実注文前の技術チェックリスト

実注文前には、最低限次をすべて確認する。

- `git status` がclean。
- local `HEAD` と `origin/main` が一致。
- backend全体tests pass。
- live_verification tests pass。
- `ruff check .` pass。
- `git diff --check` clean。
- no-order guard pass。
- no-secret guard pass。
- no-network guard pass。
- `shadow_exports/` trackedなし。
- `analysis_exports/` trackedなし。
- `.env` / `.env.example` 変更なし。
- staged diffにcredential混入なし。
- backend公開API追加なし。
- `backend/app/main_readonly.py` 変更なし。
- frontend変更なし。

1項目でも未確認またはNGなら停止する。

## 6. 実注文前の注文条件チェックリスト

実注文前には、最低限次をすべて満たす必要がある。

- `symbol=USD_JPY`。
- `units=100` / `size=100`。
- 1回限定。
- manual only。
- retryなし。
- loopなし。
- 追加注文なし。
- ナンピンなし。
- マーチンゲールなし。
- 損失回復目的の注文なし。
- 既存建玉なし。
- 未約定注文なし。
- `FinalOrderChecklist` pass。
- `DisabledHttpRequestClientSkeletonPlan` pass。
- `manual_confirmation_required=true`。
- 同一 `verification_run_id` で複数注文なし。
- 本番公開API、frontend、cron、schedule、常駐botから実行できない。

数量、通貨ペア、実行回数、manual onlyのいずれかが崩れた場合は停止する。

## 7. APIキー / secret / .env を扱う前の条件

Phase 3D-11ではAPIキー / secret / `.env` を扱わない。

将来扱う場合の必須条件:

- ユーザーの明示承認がある。
- そのタスクがAPIキー確認専用である。
- APIキー値をChatGPT / Codex / logs / docs / stdoutに出さない。
- secret値をChatGPT / Codex / logs / docs / stdoutに出さない。
- `.env` をcatしない。
- `.env` の内容を表示しない。
- `.env` をcommitしない。
- `.env.example` を変更しない。
- APIキー存在確認は `set` / `missing` のみ。
- secret存在確認も `set` / `missing` のみ。
- raw request、headers、signatureを保存しない。
- 実APIレスポンスをfixture化しない。

APIキー / secret / `.env` を扱う必要が出た場合は、Phase 3D-11の範囲外として停止する。

## 8. HTTP request / 署名実装へ進む前の条件

Phase 3D-11ではHTTP request / 署名を実装しない。

将来進む場合の必須条件:

- preflightレビューが完了している。
- APIキー確認前レビューが完了している。
- HTTP request実装前レビューが完了している。
- 署名実装前レビューが完了している。
- no-secret / no-network / no-order guardが維持されている。
- 実注文をまだ行わない範囲が明確である。
- 実HTTP POSTを作る前に別レビューがある。
- headers、request body、actual signatureの保存禁止が明文化されている。
- broker、`OrderRequest`、real order API clientへの接続境界が別レビューになっている。

HTTP requestや署名を実装する必要が出た場合は、Phase 3D-11の範囲外として停止する。

## 9. ユーザー明示承認の形式

実注文に進む前には、ユーザーが明示的に以下の趣旨を承認する必要がある。

承認文の例:

```text
USD_JPYを100通貨、1回だけ、手動承認で実注文してよい
```

曖昧な承認では進まない。

不十分な例:

- 進めて。
- お願い。
- そのまま。
- 実行して。
- OK。
- 任せます。

必要な承認項目:

- 通貨ペア。
- 数量。
- 1回限定。
- 手動実行。
- 実資金であることの理解。
- 実行後に追加注文しないこと。
- retry / loopしないこと。
- 停止条件を理解していること。

明示承認がない場合は実注文へ進まない。

## 10. 即停止条件

次のいずれかに該当した場合は即停止する。

- APIキー / secretを表示した。
- `.env`を表示した。
- raw responseを保存した。
- headersを保存した。
- signatureを保存した。
- raw requestを保存した。
- HTTP POSTが意図せず混入した。
- HTTP client importが混入した。
- broker / `OrderRequest` が混入した。
- real order API clientが混入した。
- `POST /private/v1/order` が実行可能コードに混入した。
- 既存建玉あり。
- 未約定注文あり。
- tests / ruff failure。
- `git status` dirty。
- `quantity` / `units` / `size` が100以外。
- `symbol` が `USD_JPY` 以外。
- 複数注文の可能性。
- retry / loopの可能性。
- cron / schedule / 常駐botからの実行可能性。
- frontendまたは本番公開APIからの実行可能性。
- ユーザー明示承認なし。

即停止時は、追加接続、再試行、補助的なcredential確認、実注文、実資金検証へ進まない。

## 11. 実注文後の停止・確認条件

将来、明示承認後に実注文を行う場合でも、注文を出したら即停止する。

実注文後の必須条件:

- 注文を出したら即停止。
- 追加注文しない。
- retryしない。
- loopしない。
- 自動売買へ進まない。
- read-onlyで約定 / 建玉 / 未約定注文を確認する。
- 結果はsanitized summaryのみ。
- raw response保存なし。
- headers保存なし。
- signature保存なし。
- raw request保存なし。
- 実データcommitなし。
- `shadow_exports/` / `analysis_exports/` に実データを混入しない。

約定・建玉・未約定注文確認もread-onlyであり、実データやcredentialを保存しない。

## 12. Phase 3D-12以降の分割案

### Phase 3D-12: APIキー確認専用レビュー

目的:

- APIキー / secretを扱う前に、確認方法と出力禁止範囲を最終レビューする。

作るもの:

- APIキー確認専用レビューdocs。
- `set` / `missing` だけを扱う確認方針。
- 値表示禁止、`.env`表示禁止、secret保存禁止の停止条件。

作らないもの:

- APIキー値表示。
- secret値表示。
- `.env`内容表示。
- HTTP request。
- 実注文。

検証方法:

- docs-only diff。
- secret混入確認。
- `.env` / `.env.example` 差分なし確認。

成功条件:

- 値を一切表示せず、存在確認だけを行う条件が明文化されている。

停止条件:

- 値表示、`.env`表示、credential保存に近づいた。

### Phase 3D-13: 署名 / headers / request body 実装前レビュー

目的:

- 署名、headers、request bodyを実装する前の責務境界を再確認する。

作るもの:

- 実装前レビューdocs。
- 署名対象、headers、bodyの責務分離。
- 値保存禁止と出力禁止の確認項目。

作らないもの:

- 署名実装。
- headers生成。
- request body生成。
- HTTP POST。
- 実注文。

検証方法:

- docs-only diff。
- 危険語分類。
- no-secret / no-network guard確認。

成功条件:

- 実装対象と禁止対象が明確で、まだ送信しない境界が保たれている。

停止条件:

- 実署名、headers、body、HTTP送信が混入した。

### Phase 3D-14: 署名 / headers / request body 最小実装

目的:

- 実HTTP送信なしで、最小の署名 / headers / request body構築を実装するかを検証する。

作るもの:

- 明示承認された最小実装。
- 値を保存しない設計。
- no-send tests。

作らないもの:

- HTTP POST。
- raw request保存。
- raw response保存。
- headers保存。
- signature保存。
- 実注文。

検証方法:

- focused tests。
- no-secret guard。
- Git / secret scan。
- backend全体tests / ruff。

成功条件:

- 送信せず、値を保存せず、guardを維持できる。

停止条件:

- HTTP POST、credential出力、headers/signature保存が混入した。

### Phase 3D-15: HTTP POST実装前レビュー

目的:

- HTTP POST実装に進む前に、送信解禁条件を別レビューする。

作るもの:

- HTTP POST実装前レビューdocs。
- 送信禁止 / 解禁条件。
- 実注文前の停止条件。

作らないもの:

- HTTP POST実装。
- 実送信。
- 実注文。

検証方法:

- docs-only diff。
- no-order / no-secret / no-network guard確認。
- tests / ruff。

成功条件:

- HTTP POSTを作る前に、必要条件と停止条件が明文化されている。

停止条件:

- レビューなしで送信可能コードが入った。

### Phase 3D-16: 実注文最終レビュー

目的:

- 100通貨、1回限定、manual onlyの実注文可否を最終レビューする。

作るもの:

- 実注文最終レビューdocs。
- 直前read-only precheck結果のsanitized summary。
- ユーザー明示承認の確認。

作らないもの:

- 実注文実行。
- 追加注文。
- retry。
- loop。

検証方法:

- 直前read-only precheck。
- backend tests / ruff。
- Git clean。
- secret scan。
- no-order guard。

成功条件:

- すべてのpreflight条件がOKで、ユーザー明示承認がある。

停止条件:

- 1項目でも未確認またはNG。

### Phase 3D-17: 100通貨・1回限定・手動承認つき実注文

目的:

- 明示承認済みの条件で、100通貨、1回限定、manual onlyの実注文を行う。

作るもの:

- 1回限りの手動実行。
- sanitized summary。
- 実行後read-only確認。

作らないもの:

- 自動売買。
- 追加注文。
- retry。
- loop。
- cron / schedule / 常駐bot。
- frontend実行画面。
- 本番公開API。

検証方法:

- 実行直前read-only precheck。
- 実行後read-only確認。
- raw response / headers / signature / credential保存なし確認。
- 実データcommitなし確認。

成功条件:

- 1回だけ実行して停止し、sanitized summaryのみで報告できる。

停止条件:

- 明示承認なし。
- 既存建玉あり。
- 未約定注文あり。
- 100通貨 / `USD_JPY` / 1回限定 / manual onlyから逸脱。
- credential、headers、signature、raw response、実データの保存が発生した。

## 13. 今回まだ進まない範囲

Phase 3D-11では次へ進まない。

- APIキー確認。
- `.env`確認。
- HTTP request実装。
- HTTP client import。
- HTTP POST。
- headers生成。
- request body生成。
- actual signature生成。
- HMAC処理。
- broker実装。
- `OrderRequest`実装。
- real order API client実装。
- 注文API client実装。
- `POST /private/v1/order` 実装。
- 実注文。
- 実資金検証。
- 自動売買。
- retry。
- loop。
- cron / schedule / 常駐bot。
- frontend変更。
- 本番公開API追加。

Phase 3D-11は、実注文直前preflightレビューdocsで停止する。
