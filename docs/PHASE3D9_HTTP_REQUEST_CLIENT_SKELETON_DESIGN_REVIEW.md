# Phase 3D-9: HTTP request client skeleton disabled-by-default設計レビュー

Phase 3D-9では、Phase 3D-8Bで強化した `SignatureHttpRequestDesignModel` の
no-secret / no-network guardを前提に、将来のHTTP request client skeletonを実装する前の
安全境界をdocs-onlyで整理する。

今回は **設計レビュー・docs化のみ** である。HTTP request client skeleton実装、HTTP client import、
HTTP POST、headers生成、request body生成、実署名生成、APIキー確認、`.env`確認、broker、
`OrderRequest`、real order API client、実注文、実資金検証には進まない。

## 1. Phase 3D-9の目的

目的:

- HTTP request client skeleton disabled-by-default設計レビューを行う。
- real HTTP client実装前の安全境界を整理する。
- HTTP POST実装前のレビュー条件を固定する。
- APIキー / secret / `.env` を扱う前のレビュー条件を固定する。
- Phase 3D-10で作ってよいno-network skeleton候補と、まだ作らないものを分離する。
- 100通貨、`USD_JPY`、1回限定、manual onlyの制約を維持する。

今回の扱い:

- 今回は実装ではない。
- 今回はPrivate API接続ではない。
- 今回はAPIキー確認ではない。
- 今回は`.env`確認ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. HTTP request client skeletonの定義

HTTP request client skeletonとは、将来のreal order API clientに近い責務を、
disabled-by-default / no-network / no-credential / no-POST の状態で設計するための骨格である。

Phase 3D-9では定義のみを行う。Phase 3D-10で実装する場合も、以下はまだ禁止する。

- HTTP client import。
- HTTP POST / PUT / DELETE。
- APIキー参照。
- API secret参照。
- `.env`参照。
- headers生成。
- request body生成。
- actual signature生成。
- raw request保存。
- raw response保存。
- broker接続。
- `OrderRequest`生成。
- real order API client実装。

HTTP request client skeletonは、real HTTP clientではない。実送信可能なclientでもない。
Phase 3D-10で扱うとしても、送信前のdisabled planとして停止する。

## 3. disabled-by-defaultの不変条件

将来 `DisabledHttpRequestClientSkeletonPlan` を作る場合、少なくとも次の不変条件を必須とする。

```text
disabled_by_default=true
network_enabled=false
credential_access_enabled=false
http_client_enabled=false
http_post_enabled=false
headers_created=false
request_body_created=false
actual_signature_created=false
real_order_attempted=false
```

意味:

- `disabled_by_default=true`: 明示的に無効な計画として作る。
- `network_enabled=false`: network I/Oへ進めない。
- `credential_access_enabled=false`: APIキー / secret / `.env` に触れない。
- `http_client_enabled=false`: HTTP client importやclient生成を行わない。
- `http_post_enabled=false`: POST送信関数を作らない。
- `headers_created=false`: `API-KEY` / `API-TIMESTAMP` / `API-SIGN` を含むheadersを作らない。
- `request_body_created=false`: 注文送信用bodyを作らない。
- `actual_signature_created=false`: HMACや実署名値を作らない。
- `real_order_attempted=false`: 実注文を試行しない。

いずれか1つでも反転した場合はfail closedとする。

## 4. 既存modelとの関係

既存のsafe flow:

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

ただし、Phase 3D-9では `DisabledHttpRequestClientSkeletonPlan` を実装しない。

進んではいけない導線:

```text
DisabledHttpRequestClientSkeletonPlan
-/-> requests.post
-/-> httpx.post
-/-> aiohttp
-/-> urllib
-/-> headers
-/-> request_body
-/-> actual signature
-/-> API-SIGN
-/-> POST /private/v1/order
-/-> broker
-/-> OrderRequest
-/-> 実注文
```

既存modelの役割:

- `MockedOrderPayloadCandidate`: local-only候補。送信用payloadではない。
- `DisabledOrderClientPlan`: no-network / disabled-by-defaultのclient計画。HTTP情報を持たない。
- `SignatureHttpRequestDesignModel`: 署名・HTTP requestに関するdesign-only placeholder。実署名、
  headers、request body、HTTP requestを作らない。
- `DisabledHttpRequestClientSkeletonPlan`: 将来候補。HTTP clientに近い名前でも、no-network /
  disabled-by-defaultで停止する計画に限定する。

## 5. Phase 3D-10で作ってよい候補

Phase 3D-10で実装する場合、候補は `DisabledHttpRequestClientSkeletonPlan` に限定する。

候補field:

```text
http_client_skeleton_id
signature_request_design_id
order_client_plan_id
mocked_payload_candidate_id
verification_run_id
disabled_by_default
network_enabled
credential_access_enabled
http_client_enabled
http_post_enabled
headers_created
request_body_created
actual_signature_created
real_order_attempted
fail_reasons
```

Phase 3D-10でも必須:

```text
disabled_by_default=true
network_enabled=false
credential_access_enabled=false
http_client_enabled=false
http_post_enabled=false
headers_created=false
request_body_created=false
actual_signature_created=false
real_order_attempted=false
```

作ってよいものは、上記flagsがすべて安全側で固定されたlocal-only planと、そのfail closed testsだけである。
実HTTP request、実headers、実body、実署名、実credential accessは対象外である。

## 6. Phase 3D-10でも作らないもの

Phase 3D-10でも、次は作らない。

- `requests` / `httpx` / `aiohttp` / `urllib` / `urllib3` import。
- HTTP POST / PUT / DELETE。
- headers生成。
- request body生成。
- actual signature生成。
- HMAC処理。
- API key / secret参照。
- `.env`参照。
- `os.environ` / `getenv` 追加。
- broker。
- `OrderRequest`。
- real order API client。
- 注文API client。
- 実注文。
- 実資金検証。
- raw request保存。
- raw response保存。

Phase 3D-10は、HTTP request clientに近い命名の境界を作っても送信不能であることを固定するだけのフェーズにする。

## 7. fail closed条件

次のいずれかに該当した場合は停止・失敗扱いとする。

- `disabled_by_default=false`。
- `network_enabled=true`。
- `credential_access_enabled=true`。
- `http_client_enabled=true`。
- `http_post_enabled=true`。
- `headers_created=true`。
- `request_body_created=true`。
- `actual_signature_created=true`。
- `real_order_attempted=true`。
- APIキー / secret が表示された。
- `.env` が表示された。
- HTTP client import が混入した。
- POST送信関数が混入した。
- broker / `OrderRequest` が混入した。
- `POST /private/v1/order` が実行可能コードに混入した。
- 100通貨 / `USD_JPY` / manual only / 1回限定から逸脱した。
- `SignatureHttpRequestDesignModel` の no-secret / no-network条件が崩れた。
- `FinalOrderChecklist` または no-network boundary が未passのまま先へ進んだ。

fail closed時の扱い:

- 追加接続しない。
- retryしない。
- loopしない。
- raw request / raw response / headers / signature / credentialを保存しない。
- 原因を分類し、必要最小限の修正またはレビューで停止する。

## 8. no-order / no-secret / no-network guard方針

Phase 3D-9以降も、次をguardする。

- HTTP client import禁止。
- POST送信禁止。
- headers生成禁止。
- request body生成禁止。
- signature生成禁止。
- API key / secret参照禁止。
- `.env`参照禁止。
- broker import禁止。
- `OrderRequest`禁止。
- raw request / raw response保存禁止。
- 実注文endpoint実行禁止。
- 本番公開API、frontend、cron、schedule、常駐botからの実行導線禁止。

確認方針:

- AST-based no-order-import guard。
- `SignatureHttpRequestDesignModel` 周辺のno-secret / no-network tests。
- `rg`による危険語分類。
- `git diff --cached` のsecret scan。
- `.env` / `.env.example` 差分なし確認。
- `shadow_exports/` / `analysis_exports` trackedなし確認。

## 9. Phase 3D-10以降の分割案

### Phase 3D-10: HTTP request client skeleton no-network実装

目的:

- HTTP request clientに近い境界をno-network / disabled-by-defaultでmock実装する。

作るもの:

- `DisabledHttpRequestClientSkeletonPlan`。
- safety flags validation。
- `SignatureHttpRequestDesignModel` から先へ進むためのlocal-only plan。
- no HTTP / no credential / no send tests。

作らないもの:

- HTTP client import。
- HTTP POST。
- headers。
- request body。
- actual signature。
- API key / secret参照。
- broker。
- `OrderRequest`。
- 実注文。

検証方法:

- focused unit tests。
- no-order-import guard。
- 危険語スキャン。
- backend全体tests / ruff。

成功条件:

- skeletonが存在しても送信できない。
- disabled flagsがすべて安全側に固定されている。
- credential accessが無効である。

停止条件:

- network、HTTP client、headers、request body、signature、credential access、実endpointが混入した。

### Phase 3D-10B: HTTP request skeleton no-network / no-secret guard hardening

目的:

- Phase 3D-10のskeletonに対し、no-network / no-secret / no-order guardを強化する。

作るもの:

- forbidden field tests。
- forbidden import tests。
- fail closed tests。
- docsの最小追記。

作らないもの:

- HTTP client。
- HTTP POST。
- headers。
- request body。
- actual signature。
- API key / secret参照。
- `.env`確認。
- 実注文。

検証方法:

- focused guard tests。
- `rg`危険語分類。
- backend全体tests / ruff。

成功条件:

- 実行可能コードにHTTP / credential / order endpoint導線がない。

停止条件:

- 実装コードに送信、credential access、署名生成が混入した。

### Phase 3D-11: 実注文直前preflightレビュー

目的:

- 実注文可否判断の直前に、preflight条件をdocs-onlyで再確認する。

作るもの:

- preflight review docs。
- 実行直前checklist。

作らないもの:

- 新規実装。
- 実注文。
- APIキー表示。
- `.env`表示。
- HTTP POST実行。

検証方法:

- read-only precheck直前成功の確認。
- 既存建玉なし。
- 未約定注文なし。
- tests / ruff。
- Git clean。
- secret scan。

成功条件:

- 実注文最終レビューに必要な条件がすべて明文化されている。

停止条件:

- 1項目でも未確認またはNG。

### Phase 3D-12: 100通貨・1回限定・手動承認つき実注文最終レビュー

目的:

- 100通貨、1回限定、manual onlyの実注文検証を行うか最終判断する。

作るもの:

- 最終レビューdocs。
- 明示承認確認。
- sanitized summary方針。

作らないもの:

- 自動売買。
- retry。
- loop。
- cron / schedule / 常駐bot。
- frontend実行画面。
- 本番公開API。

検証方法:

- ユーザー明示承認。
- 直前read-only precheck。
- `FinalOrderChecklist` pass。
- no-send guard確認。
- tests / ruff。
- Git clean。
- secret scan。

成功条件:

- 実行内容、最大損失、停止条件をユーザーが理解し、明示承認している。

停止条件:

- 明示承認なし。
- 既存建玉あり。
- 未約定注文あり。
- Git dirty。
- secret混入。
- 100通貨 / `USD_JPY` / 1回限定 / manual onlyから逸脱。

## 10. 今回まだ進まない範囲

Phase 3D-9では次へ進まない。

- HTTP request client skeleton実装。
- HTTP client import。
- HTTP POST。
- headers生成。
- request body生成。
- actual signature生成。
- HMAC処理。
- APIキー確認。
- `.env`確認。
- API secret確認。
- broker実装。
- `OrderRequest`実装。
- real order API client実装。
- 注文API client実装。
- `POST /private/v1/order` 実装。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend変更。
- 本番公開API追加。

Phase 3D-9は、HTTP request client skeleton disabled-by-default設計レビューdocsで停止する。

## 11. Phase 3D-10実装結果メモ

Phase 3D-10では、Phase 3D-9の設計に基づき、`SignatureHttpRequestDesignModel` の後段に
`DisabledHttpRequestClientSkeletonPlan` を追加した。

実装内容:

- `backend/app/live_verification/http_request_skeleton.py` を追加。
- `DisabledHttpRequestClientSkeletonPlan` を追加。
- `build_disabled_http_request_client_skeleton_plan()` を追加。
- `SignatureHttpRequestDesignModel` のno-secret / no-network条件が崩れている場合はfail closed。
- skeleton側のunsafe flagが1つでも安全側から反転した場合はfail closed。
- `backend/app/tests/test_live_verification_http_request_skeleton.py` を追加。
- `test_live_verification_no_order_imports.py` で `hmac` importもpackage-wideに禁止。

維持した境界:

- HTTP client importなし。
- HTTP POSTなし。
- headers生成なし。
- request body生成なし。
- actual signature生成なし。
- raw request生成なし。
- raw response保存なし。
- APIキー確認なし。
- API secret参照なし。
- `.env`確認なし。
- brokerなし。
- `OrderRequest`なし。
- real order API clientなし。
- 注文API clientなし。
- 実注文なし。
- 実資金検証なし。

次候補:

- Phase 3D-10B HTTP request skeleton no-network / no-secret guard hardening。
- ただし、Phase 3D-10BでもHTTP request実装、実署名、APIキー確認、実注文、実資金検証には進まない。
