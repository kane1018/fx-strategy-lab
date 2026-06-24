# Phase 3D-7: 署名・HTTP request設計レビュー

Phase 3D-7では、GMO Private API注文系に進む前に、署名・HTTP requestの責務境界をdocs-onlyで整理する。

今回は **設計レビュー・docs化のみ** である。署名生成実装、HMAC処理実装、timestamp生成実装、
HTTP request builder実装、HTTP client実装、APIキー確認、`.env`確認、実注文、実資金検証には進まない。

## 1. Phase 3D-7の目的

目的:

- 署名・HTTP request設計レビューを行う。
- real order API client実装前の安全境界を整理する。
- APIキー / secret取り扱いの設計を固定する。
- HTTP POST実装前のレビューを行う。
- request body生成と署名対象文字列の関係を整理する。
- no-network skeletonと将来のreal order clientを混同しない境界を固定する。

今回の扱い:

- 今回は実装ではない。
- 今回はPrivate API接続ではない。
- 今回はAPIキー確認ではない。
- 今回は`.env`確認ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. GMO Private API署名仕様の整理

公式docsおよび既存Phase 3B / Phase 3D-0 docsで確認済みの仕様整理:

```text
Private REST base URL:
https://forex-api.coin.z.com/private

version:
v1

headers:
API-KEY
API-TIMESTAMP
API-SIGN

signature:
HMAC-SHA256 hex

timestamp:
milliseconds epoch

GET signature source:
<TIMESTAMP> + <METHOD> + <PATH>

POST signature source:
<TIMESTAMP> + <METHOD> + <PATH> + <BODY>
```

重要な注意:

- 今回は仕様整理のみ。
- 署名生成関数は作らない。
- HMAC処理は新規実装しない。
- timestamp生成処理は新規実装しない。
- API secretは扱わない。
- APIキーの存在確認もしない。
- `.env`は読まない。
- raw request、headers、signatureを保存しない。

署名対象pathの注意:

- 既存read-only確認では、公式docsの例に合わせ、署名対象pathは `/v1/...` 形式として扱う設計が確認済み。
- 外向きのendpoint表記は `/private/v1/...` だが、署名対象pathとbase URL結合後の実URL表現を混同しない。
- Phase 3D-7では、この差分をdocs上の注意点として残すだけで、署名実装には進まない。

## 3. 注文系POSTの扱い方

将来対象候補:

```text
POST /private/v1/order
```

ただしPhase 3D-7では、次をすべて禁止する。

- 実装しない。
- 接続しない。
- request bodyを作らない。
- 署名しない。
- HTTP POSTしない。
- APIキーを確認しない。
- secretを確認しない。
- `.env`を確認しない。
- 実注文しない。

引き続き対象外:

- `speedOrder`
- `changeOrder`
- `cancelOrders`
- `closeOrder`
- IFD / IFO / OCO
- Private WebSocket / `ws-auth`

理由:

- 初回の100通貨・1回限定・manual onlyの検証候補に不要である。
- 注文変更、注文取消、決済、WebSocket token管理は、初回注文疎通よりも危険度と状態管理が高い。
- `POST /private/v1/order` であっても、Phase 3D-7では仕様整理の対象であり、実装対象ではない。

## 4. 署名責務の分離

責務分離:

```text
payload candidate:
local-onlyの候補。送信用bodyではない。

disabled order client plan:
no-network / disabled-by-default の計画。HTTP情報を持たない。

future request body builder:
将来の送信用body候補を作る責務。まだ未実装。

future signer:
timestamp + method + path + body から署名候補を作る責務。まだ未実装。

future HTTP client:
POSTする責務。まだ未実装。
```

現在の到達点:

- `MockedOrderPayloadCandidate` はlocal-onlyであり、endpoint、method、path、url、request body、headers、
  signature、credentialを保持しない。
- `DisabledOrderClientPlan` はno-network / disabled-by-defaultであり、HTTP request情報を保持しない。
- 既存のPrivate API read-only auth helperは、mocked read-only tests用に値を注入して使う境界であり、
  Phase 3D-7で注文系へ流用しない。

将来の分離条件:

- request body builderは、署名処理から分離する。
- signerは、API secretを受け取る境界として別レビュー後に限定する。
- HTTP clientは、signerとrequest body builderの後段に置くが、network-enabled化はさらに別レビュー後にする。
- どの層も、stdout、logs、docs、fixtures、Git diffにcredentialや署名値を出してはいけない。

## 5. APIキー / secretの扱い

Phase 3D-7では、APIキーもsecretも扱わない。

禁止:

- APIキー存在確認なし。
- secret存在確認なし。
- APIキー値を要求しない。
- secret値を要求しない。
- `.env`を読まない。
- `.env.example`を変更しない。
- docsに実credentialを書かない。
- test fixtureに実credentialを書かない。
- stdout / logs / commitにcredentialを出さない。

将来扱う場合の条件:

- 実装前レビューが完了していること。
- local-onlyであること。
- ユーザーが明示承認していること。
- APIキー / secret値をstdout、logs、docs、fixtures、Git diffに出さないこと。
- raw request、headers、signatureを保存しないこと。
- `.env`内容を表示しないこと。
- read-only用キーと注文用キーの権限分離を再確認すること。

1項目でも満たせない場合は停止する。

## 6. HTTP request設計の境界

Phase 3D-7ではHTTP requestを作らない。

禁止:

- HTTP method、endpoint、headers、bodyを持つ実装objectを作らない。
- `requests` / `httpx` / `aiohttp` / `urllib` / `urllib3` をimportしない。
- POST送信関数を作らない。
- request builderを作らない。
- request body builderを作らない。
- HTTP client classを作らない。
- network-enabled flagをtrueにしない。

設計上の境界:

- Phase 3D-7は、将来どこでHTTP requestを作るべきかをdocsで整理するだけで停止する。
- Phase 3D-8以降でmocked modelを作る場合も、まずno-secret / no-network / no-sendを維持する。
- HTTP POSTを含む実装は、Phase 3D-7の範囲外であり、検出された場合は即停止条件とする。

## 7. 署名・HTTP request実装前のfail closed条件

将来の実装前レビューで、次のいずれかに該当した場合は停止する。

- APIキー / secretを表示した。
- `.env`を表示した。
- headersを保存した。
- signatureを保存した。
- raw requestを保存した。
- raw responseを保存した。
- HTTP POSTが実装に混入した。
- brokerが混入した。
- `OrderRequest`が混入した。
- 注文API endpointが実行可能コードに混入した。
- 100通貨 / `USD_JPY` / manual only / 1回限定から逸脱した。
- `FinalOrderChecklist`が未pass。
- `DisabledOrderClientPlan`がdisabledでない。
- `network_enabled=false` が維持されていない。
- `credential_access_enabled=false` が維持されていない。
- 本番公開API、frontend、cron、schedule、常駐botから到達できる導線が混入した。

fail closed時の扱い:

- 追加接続しない。
- retryしない。
- loopしない。
- 修正前に原因を分類する。
- raw request / raw response / headers / signature / credentialを保存しない。

## 8. Phase 3D-8以降の分割案

### Phase 3D-8: signature / request design model mocked実装

目的:

- 署名・HTTP requestに進む前のmocked design modelを作る。
- 実署名、APIキー、HTTPなしで、責務分離だけをコードで固定する。

作るもの:

- no-secret signature design model。
- no-network request design model。
- `DisabledOrderClientPlan` から先へ進む場合のmocked validation。

作らないもの:

- 実署名。
- APIキー参照。
- API secret参照。
- HTTP client。
- HTTP POST。
- request body送信用object。

検証方法:

- mocked unit tests。
- no-order / no-secret guard。
- forbidden field guard。
- backend全体tests / ruff。

成功条件:

- 実credentialなしで責務境界を検証できる。
- HTTP送信できない。
- headers、signature、raw requestを保持しない。

停止条件:

- HMAC処理、API secret参照、HTTP送信、実endpointが実行可能コードに混入した。

### Phase 3D-8B: signature / request model no-secret guard hardening

目的:

- Phase 3D-8のmocked modelに対してno-secret / no-send guardを強化する。

作るもの:

- 禁止field検出。
- 禁止import検出。
- forbidden endpoint文字列の実装コード混入検出。
- fail closed tests。

作らないもの:

- 実署名。
- APIキー確認。
- `.env`確認。
- HTTP request builder。
- HTTP client。

検証方法:

- AST-based guard。
- `rg`による危険語確認。
- backend全体tests / ruff。

成功条件:

- 実装コードにcredential / HTTP / order endpoint導線がないことを確認できる。

停止条件:

- 実行可能コードにHTTP送信、credential access、署名生成が混入した。

### Phase 3D-9: HTTP request client skeleton disabled-by-default設計レビュー

目的:

- HTTP request client skeletonを作る前に、disabled-by-defaultの設計をレビューする。

作るもの:

- docsレビュー。
- 作るもの / 作らないもの / 検証方法 / 停止条件の整理。

作らないもの:

- HTTP client。
- HTTP POST。
- APIキー確認。
- `.env`確認。
- 実注文。

検証方法:

- docs差分確認。
- 危険語分類。
- secret混入確認。

成功条件:

- 次に作る skeleton がno-network / disabled-by-defaultであることが明確。

停止条件:

- 実送信やcredential accessを設計レビューなしに許可する記述が入った。

### Phase 3D-10: HTTP request client skeleton no-network実装

目的:

- HTTP request clientに近い境界をno-networkでmock実装する。

作るもの:

- no-network HTTP client skeleton。
- disabled-by-default validation。
- no-send tests。

作らないもの:

- 実HTTP POST。
- network-enabled client。
- APIキー参照。
- HMAC署名。
- 実注文。

検証方法:

- mocked tests。
- no-order / no-secret guard。
- backend全体tests / ruff。

成功条件:

- client skeletonが存在しても送信できない。
- credential accessが無効。

停止条件:

- network-enabled、HTTP POST、credential access、実endpoint実行が混入した。

### Phase 3D-11: 実注文直前preflightレビュー

目的:

- 実注文に近づく前の最終preflight条件をレビューする。

作るもの:

- docsレビュー。
- 実行直前checklist。

作らないもの:

- 新しい実装。
- 実注文。
- APIキー表示。
- `.env`表示。

検証方法:

- read-only precheck直前成功確認。
- 既存建玉なし。
- 未約定注文なし。
- tests / ruff / Git clean / secret scan。

成功条件:

- 実注文前の明示承認に必要な条件がすべて明文化されている。

停止条件:

- 1項目でも未確認またはNG。

### Phase 3D-12: 100通貨・1回限定・手動承認つき実注文最終レビュー

目的:

- 100通貨、1回限定、manual onlyの実注文検証を行うか最終判断する。

作るもの:

- 最終レビューdocs。
- 実行手順の明示確認。

作らないもの:

- 自動売買。
- retry。
- loop。
- cron / schedule / 常駐bot。
- frontend実行画面。

検証方法:

- ユーザー明示承認。
- 直前read-only precheck。
- `FinalOrderChecklist` pass。
- no-send guard確認。
- tests / ruff / Git clean / secret scan。

成功条件:

- 実行内容、最大損失、停止条件をユーザーが理解し、明示承認している。

停止条件:

- 明示承認なし。
- 既存建玉あり。
- 未約定注文あり。
- Git dirty。
- secret混入。
- 100通貨 / `USD_JPY` / 1回限定 / manual onlyから逸脱。

## 9. no-order / no-secret guard方針

Phase 3D-7以降も、次のguard方針を維持する。

- `API-KEY` / `API-SIGN` / `API-TIMESTAMP` を実値として扱わない。
- API secretを扱わない。
- `.env`を読まない。
- HTTP client import禁止。
- POST送信禁止。
- broker import禁止。
- `OrderRequest`禁止。
- raw request保存禁止。
- raw response保存禁止。
- headers保存禁止。
- signature保存禁止。
- order endpointの実行可能コード混入禁止。
- 本番公開API、frontend、cron、schedule、常駐botからの実行導線禁止。

確認方法:

- AST-based no-order-import guard。
- `rg`による危険語スキャン。
- `git diff --cached` のsecret scan。
- `.env` / `.env.example` 差分なし確認。
- `shadow_exports/` / `analysis_exports` trackedなし確認。

## 10. 今回まだ進まない範囲

Phase 3D-7では、次へ進まない。

- 署名生成実装。
- HMAC処理実装。
- timestamp生成実装。
- HTTP request builder実装。
- HTTP client実装。
- `POST /private/v1/order` 実装。
- request body builder実装。
- APIキー確認。
- `.env`確認。
- secret確認。
- broker実装。
- `OrderRequest`実装。
- 注文API client実装。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend変更。
- 本番公開API追加。

Phase 3D-7は、署名・HTTP request設計レビューdocsで停止する。

## 11. Phase 3D-8実装結果メモ

Phase 3D-8では、Phase 3D-7の設計レビューに基づき、署名・HTTP requestへ進む前の
mocked design modelだけを実装した。

実装したもの:

- `SignatureHttpRequestDesignModel`。
- `build_signature_http_request_design_model()`。
- `DisabledOrderClientPlan` と `MockedOrderPayloadCandidate` のID・run・安全flag相関確認。
- `ORDER_CREATE_METHOD_LABEL` / `ORDER_CREATE_PATH_LABEL` /
  `ORDER_CREATE_BODY_SHAPE_LABEL` / `TIMESTAMP_PLACEHOLDER` のdesign-only許可値。
- placeholder-onlyの `signing_source_candidate`。
- fail closed tests。
- 非secret / 非HTTP / 非署名実値のtests。

実装していないもの:

- 実署名生成。
- HMAC処理。
- hmac/hashlib import。
- API-KEY / API-SIGN / API-TIMESTAMP生成。
- APIキー確認。
- API secret参照。
- `.env`確認。
- HTTP request builder。
- HTTP client。
- headers生成。
- request body生成。
- HTTP POST。
- broker。
- `OrderRequest`。
- 注文API client。
- 実注文。
- 実資金検証。

次候補はPhase 3D-8B no-secret / no-network guard hardeningである。ただし、Phase 3D-8Bでも
実署名、APIキー確認、`.env`確認、HTTP request、HTTP POST、実注文、実資金検証には進まない。

## 12. Phase 3D-8B実装結果メモ

Phase 3D-8Bでは、Phase 3D-8の `SignatureHttpRequestDesignModel` が no-secret / no-network /
design-only の境界を維持することを追加テストで固定した。

強化したもの:

- `signing_source_candidate` が `TIMESTAMP_PLACEHOLDER`、`ORDER_CREATE_METHOD_LABEL`、
  `ORDER_CREATE_PATH_LABEL`、`ORDER_CREATE_BODY_SHAPE_LABEL` の4 tokenだけで構成されること。
- modelのstring値に実HTTP method、実endpoint、API header名、secret、request body、raw request /
  raw responseが混入しないこと。
- model field一覧が許可済みの安全fieldだけであること。
- safety flagがboolであり、不正値やtrue化を拒否すること。
- plan / candidateのID相関不整合を拒否すること。
- `signature_request_design.py` に `hmac` / `hashlib` / HTTP client importがないこと。

実装していないもの:

- 実署名生成。
- HMAC処理。
- API-KEY / API-SIGN / API-TIMESTAMP生成。
- APIキー確認。
- API secret参照。
- `.env`確認。
- HTTP request builder。
- HTTP client。
- headers生成。
- request body生成。
- HTTP POST。
- broker。
- `OrderRequest`。
- 注文API client。
- 実注文。
- 実資金検証。

次候補はPhase 3D-9 HTTP request client skeleton disabled-by-default設計レビューである。ただし、
Phase 3D-9でも実署名、APIキー確認、`.env`確認、HTTP request実装、HTTP POST、実注文、
実資金検証には進まない。
