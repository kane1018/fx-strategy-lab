# Phase 3D-15: actual body / headers / signature 最小実装前レビュー

Phase 3D-15では、Phase 3D-14Bまでで強化した `SignatureHeadersBodyPlan` の
no-secret / no-network / no-order guardを前提に、actual request body、actual headers、
actual signatureの最小実装へ進む前の責務分離と安全境界をdocs-onlyで整理する。

今回は **設計レビュー・docs化のみ** である。actual request body生成、actual headers生成、
actual signature生成、HMAC処理、HTTP request実装、HTTP client import、HTTP POST、
Private API追加接続、broker、`OrderRequest`、real order API client、実注文、実資金検証には進まない。

## 1. Phase 3D-15の目的

目的:

- actual body / headers / signature 最小実装前レビューを行う。
- 実request body生成前の責務を整理する。
- 実headers生成前の責務を整理する。
- 実signature生成前の責務を整理する。
- HTTP POST実装前の境界を整理する。
- APIキー / secret値を表示しない実装・運用条件を固定する。
- raw request / raw response / headers / signatureを保存しない条件を固定する。
- Phase 3D-16以降の分割案を明確にする。

今回の扱い:

- 今回は実装ではない。
- 今回はPrivate API接続ではない。
- 今回はHTTP request実装ではない。
- 今回はHMAC処理実装ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. 現在の到達点

Phase 3D-12で確認済みの環境変数存在状態:

```text
GMO_FX_API_KEY: set
GMO_FX_API_SECRET: set
```

ただし、これは存在有無だけの確認である。

維持している境界:

- APIキー値表示なし。
- secret値表示なし。
- `.env`表示なし。
- `.env`変更なし。
- HTTP request実装なし。
- HTTP client importなし。
- HTTP POSTなし。
- 署名実装なし。
- actual body生成なし。
- actual headers生成なし。
- actual signature生成なし。
- HMAC処理なし。
- brokerなし。
- `OrderRequest`なし。
- real order API clientなし。
- 実注文なし。
- 実資金検証なし。

現在の no-network / no-secret / no-order chain:

```text
OrderIntent
-> OrderReview
-> FinalOrderChecklist
-> NoNetworkBrokerBoundaryResult
-> MockedOrderPayloadCandidate
-> DisabledOrderClientPlan
-> SignatureHttpRequestDesignModel
-> DisabledHttpRequestClientSkeletonPlan
-> SignatureHeadersBodyPlan
```

まだ進まない導線:

```text
SignatureHeadersBodyPlan
-/-> actual request body
-/-> actual headers
-/-> actual signature
-/-> HMAC
-/-> HTTP request
-/-> HTTP POST
-/-> POST /private/v1/order
-/-> broker
-/-> OrderRequest
-/-> real order API client
-/-> 実注文
```

## 3. actual request body生成の責務整理

将来の actual request body 最小候補は、GMO FX注文仕様上の送信用bodyを作る責務を持つ。
Phase 3D-15では、次の項目を候補として整理するだけで、生成しない。

将来候補:

```text
symbol
side
size
executionType
timeInForce
settleType
```

Phase 3D-15で行わないこと:

- actual request bodyを生成しない。
- dict化しない。
- JSON化しない。
- raw requestとして保存しない。
- HTTP POSTへ渡さない。
- brokerへ渡さない。
- real order API clientへ渡さない。

Phase 3D-16で作る場合の最小条件:

- `symbol=USD_JPY` のみ。
- `size=100` のみ。
- `executionType=MARKET` のみ。
- `timeInForce=FAK` のみ。
- `settleType=OPEN` のみ。
- sideは明示値のみ。
- manual only。
- 1 verification runにつき1回限定。
- retryなし。
- loopなし。
- 追加注文なし。

Phase 3D-16でactual request bodyを作るとしても、HTTP POSTはまだ禁止する。

## 4. actual headers生成の責務整理

将来の actual headers 最小候補は、GMO Private REST APIの認証headersを作る責務を持つ。
Phase 3D-15では、次の項目を候補として整理するだけで、生成しない。

将来候補:

```text
API-KEY
API-TIMESTAMP
API-SIGN
```

Phase 3D-15で行わないこと:

- actual headersを生成しない。
- header値を保持しない。
- dict化しない。
- stdoutへ出さない。
- logsへ出さない。
- docsへ値を書かない。
- Git diffへ値を入れない。
- raw requestとして保存しない。
- HTTP POSTへ渡さない。

Phase 3D-16で作る場合の必須条件:

- header値をstdoutへ出さない。
- header値をlogsへ出さない。
- header値をdocsへ書かない。
- header値をGit diffへ入れない。
- header値をtest fixture化しない。
- raw request / raw response / response headersを保存しない。
- 実credential値はcommit対象にしない。

## 5. actual signature生成の責務整理

将来の actual signature 最小候補は、GMO Private REST API仕様に基づき、署名対象文字列とAPI secretから
signature値を作る責務を持つ。

将来候補の署名材料:

```text
timestamp + method + path + body + API secret
```

Phase 3D-15で行わないこと:

- HMAC処理しない。
- actual signature値を作らない。
- signature値を保存しない。
- signature値をstdoutへ出さない。
- signature値をlogsへ出さない。
- signature値をdocsへ書かない。
- signature値をGit diffへ入れない。
- API secret値を表示しない。
- API secret値を保存しない。
- HTTP POSTへ渡さない。

Phase 3D-16で作る場合の必須条件:

- signature値を保存しない。
- signature値を表示しない。
- signature値をlogsへ出さない。
- signature値をdocsへ書かない。
- signature値をGit diffへ入れない。
- API secret値をstdout / logs / docs / Git diffへ出さない。
- raw request / raw responseを保存しない。

## 6. actual body / headers / signature の分離方針

将来の責務分離:

```text
body builder:
actual request bodyだけを作る責務。

signer:
API secretを使ってsignatureだけを作る責務。

headers builder:
API-KEY / API-TIMESTAMP / API-SIGN headersだけを作る責務。

HTTP client:
headers + body をPOSTする責務。まだ未実装。
```

分離ルール:

- body builderはAPI key / secretを扱わない。
- body builderはheaders / signatureを作らない。
- signerはHTTP POSTしない。
- signerはraw request / raw responseを保存しない。
- headers builderはHTTP POSTしない。
- HTTP clientはPhase 3D-15でもPhase 3D-16でも未実装のままにする。
- どの層でもcredential値を表示・保存・commitしない。

Phase 3D-15では、上記は設計整理のみであり、どのbuilderも実装しない。

## 7. Phase 3D-16で作ってよい候補

Phase 3D-16に進む場合、作ってよい候補は次のような最小bundleに限定する。

```text
ActualBodyHeadersSignatureBundle:
- bundle_id
- verification_run_id
- signature_headers_body_plan_id
- body_created
- headers_created
- signature_created
- http_post_enabled
- raw_request_saved
- raw_response_saved
- credential_values_logged
- body_fields_summary
- headers_fields_summary
```

Phase 3D-16で許可し得る状態:

```text
body_created=true
headers_created=true
signature_created=true
```

ただし、Phase 3D-16でも必須でfalseにする状態:

```text
http_post_enabled=false
raw_request_saved=false
raw_response_saved=false
credential_values_logged=false
```

Phase 3D-16の最小実装候補に含めるべき安全設計:

- `body_fields_summary` はfield名や固定条件のsummaryに限定し、raw body値やraw JSONを保存しない。
- `headers_fields_summary` はheader名の存在summaryに限定し、header値を保存しない。
- signature値そのものをmodel fieldに持たせない。
- actual body / headers / signatureを作ってもHTTP POSTには渡さない。
- 実注文endpointの送信関数を作らない。
- APIキー / secret値をstdout / logs / docs / Git diffへ出さない。

## 8. Phase 3D-16でもまだ作らないもの

Phase 3D-16でも、次は作らない。

- HTTP request送信。
- HTTP POST。
- HTTP client import。
- broker。
- `OrderRequest`。
- real order API client。
- retry。
- loop。
- 複数注文。
- raw request保存。
- raw response保存。
- headers保存。
- signature保存。
- credential値のログ出力。
- APIキー値表示。
- secret値表示。
- `.env`表示。
- frontend実行画面。
- 本番公開API追加。
- 実注文。
- 実資金検証。

## 9. fail closed条件

次のいずれかに該当する場合は停止する。

- APIキー値が表示された。
- secret値が表示された。
- `.env`が表示された。
- actual headersがログ出力された。
- actual signatureがログ出力された。
- raw requestが保存された。
- raw responseが保存された。
- response headersが保存された。
- signature値が保存された。
- HTTP POSTが混入した。
- HTTP client importが混入した。
- brokerが混入した。
- `OrderRequest`が混入した。
- real order API clientが混入した。
- `POST /private/v1/order` が実行可能コードに混入した。
- `symbol != USD_JPY`。
- `size != 100`。
- 1回限定でない。
- manual onlyでない。
- retry / loop / 複数注文の可能性がある。
- backend tests failure。
- ruff failure。
- `git diff --check` failure。
- Git dirtyのまま実注文系フェーズへ進もうとしている。
- ユーザーの明示承認なしに実注文へ進もうとしている。

fail closed時の扱い:

- 実送信しない。
- credential値を読まない、または表示しない。
- raw artifactを保存しない。
- commitしない。
- 原因をdocsまたは最終報告にsanitized summaryで残す。

## 10. Phase 3D-16以降の分割案

### Phase 3D-16: actual body / headers / signature 最小実装

目的:

- `SignatureHeadersBodyPlan` の後段に、actual body / headers / signatureの最小bundleを追加する。

作るもの:

- `ActualBodyHeadersSignatureBundle`。
- body / headers / signature作成成功を示す安全summary。
- no-log / no-save / no-POSTのguard。

作らないもの:

- HTTP POST。
- HTTP client。
- broker。
- `OrderRequest`。
- raw request / raw response保存。
- headers / signature保存。
- credential値ログ出力。
- 実注文。

検証方法:

- focused tests。
- no-secret / no-order / no-network guard。
- backend全体tests。
- ruff。
- secret混入確認。

成功条件:

- `body_created=true`、`headers_created=true`、`signature_created=true`。
- `http_post_enabled=false`。
- raw artifact保存なし。
- credential値表示なし。

停止条件:

- credential値表示。
- raw artifact保存。
- HTTP POST混入。
- symbol / size / manual only / 1回限定逸脱。

### Phase 3D-16B: actual body / headers / signature no-leak hardening

目的:

- Phase 3D-16のbundleがcredential値、headers値、signature値、raw bodyを漏らさないことを強化する。

作るもの:

- no-leak tests。
- no-order guard強化。
- no-secret guard強化。

作らないもの:

- HTTP POST。
- HTTP client。
- broker。
- 実注文。

検証方法:

- adversarial tests。
- AST guard。
- danger word scan。
- secret scan。

成功条件:

- 値表示・保存・commitがない。
- unsafe flagsがfail closedする。

停止条件:

- header値 / signature値 / API key / secretが出力または保存された。

### Phase 3D-17: HTTP POST実装前レビュー

目的:

- HTTP POST実装へ進む前に、送信責務、禁止endpoint、実注文停止条件を再確認する。

作るもの:

- docs-onlyレビュー。

作らないもの:

- HTTP POST。
- HTTP client。
- 実注文。

検証方法:

- docs-only diff確認。
- existing tests / ruff。
- no-order / no-secret scan。

成功条件:

- HTTP POST解禁前条件と停止条件が明文化されている。

停止条件:

- HTTP送信実装に進もうとしている。

### Phase 3D-18: real HTTP POST disabled-by-default skeleton

目的:

- 将来のHTTP POST境界をdisabled-by-defaultで表現する。

作るもの:

- disabled-by-default skeleton。
- no-send guard。

作らないもの:

- 実送信。
- 実注文。
- retry / loop。

検証方法:

- no-network tests。
- no-order tests。
- backend全体tests。
- ruff。

成功条件:

- HTTP POST実行不能。
- credential値非表示。
- 実注文なし。

停止条件:

- 送信可能コードが混入した。

### Phase 3D-19: 実注文最終レビュー

目的:

- 100通貨 / 1回限定 / manual only の最終確認を行う。

作るもの:

- docs-only最終レビュー。
- 実行条件と停止条件の最終固定。

作らないもの:

- まだ実注文しない。
- 追加注文導線。
- 自動売買導線。

検証方法:

- Git clean。
- backend tests / ruff。
- read-only precheck summary。
- no-secret / no-order scan。

成功条件:

- 実注文可能条件が完全に揃い、ユーザーの明示承認形式が固定されている。

停止条件:

- 既存建玉あり。
- 未約定注文あり。
- Git dirty。
- tests / ruff failure。
- 明示承認なし。

### Phase 3D-20: 100通貨・1回限定・手動承認つき実注文

目的:

- ユーザー明示承認のもと、100通貨・1回限定・manual onlyで極小実注文を検証する。

作るもの:

- 実行時のsanitized summary。

作らないもの:

- 追加注文。
- retry。
- loop。
- 自動売買。
- raw response保存。
- headers / signature保存。

検証方法:

- 直前read-only precheck。
- 実行後read-only確認。
- sanitized summaryのみ。

成功条件:

- 1回だけ実行し、即停止する。
- 追加注文しない。
- 結果をsanitized summaryで確認する。

停止条件:

- 承認文言不備。
- 既存建玉あり。
- 未約定注文あり。
- API / HTTP / order条件の不一致。
- 予期しないレスポンスまたは実行失敗。

## 11. 今回まだ進まない範囲

Phase 3D-15では次に進まない。

- actual request body生成。
- actual headers生成。
- actual signature生成。
- HMAC処理。
- HTTP request実装。
- HTTP client import。
- HTTP POST。
- broker実装。
- `OrderRequest`実装。
- real order API client実装。
- Private API追加接続。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend変更。
- 本番公開API追加。

## 12. 結論

Phase 3D-15では、Phase 3D-16でactual body / headers / signatureの最小実装に進む前の責務分離、
禁止境界、fail closed条件、以降の分割案をdocs-onlyで整理した。

判定:

```text
A: Phase 3D-16 actual body / headers / signature 最小実装へ進んでよい
```

ただし、Phase 3D-16でもHTTP POST、HTTP request送信、Private API追加接続、broker、`OrderRequest`、
real order API client、実注文、実資金検証には進まない。Phase 3D-16は別タスクであり、今回このまま
実装へ進まない。

## 13. Phase 3D-16A actual request body最小実装結果メモ

Phase 3D-16Aでは、Phase 3D-15で整理した責務分離に基づき、actual body / headers / signature のうち
actual request body modelだけを最小実装した。

追加したもの:

- `backend/app/live_verification/actual_order_body.py`
- `ActualOrderRequestBody`
- `build_actual_order_request_body()`
- `make_actual_order_body_id()`
- `backend/app/tests/test_live_verification_actual_order_body.py`

固定した条件:

- `symbol=USD_JPY`
- `side=BUY|SELL`
- `size=100`
- `executionType=MARKET`
- `timeInForce=FAK`
- `settleType=OPEN`
- `body_created=true`
- `http_post_enabled=false`
- `headers_created=false`
- `signature_created=false`
- `raw_request_saved=false`
- `raw_response_saved=false`
- `credential_values_logged=false`
- `real_order_attempted=false`

維持した境界:

- actual headers生成なし。
- actual signature生成なし。
- HMAC処理なし。
- HTTP request実装なし。
- HTTP client importなし。
- HTTP POSTなし。
- APIキー値表示なし。
- secret値表示なし。
- `.env`確認なし。
- Private API追加接続なし。
- brokerなし。
- `OrderRequest`なし。
- real order API clientなし。
- 注文API clientなし。
- 実注文なし。
- 実資金検証なし。

次候補:

- Phase 3D-16B actual body no-leak hardening。
- ただしPhase 3D-16Bでも、actual headers生成、actual signature生成、HTTP request実装、HTTP POST、
  実注文、実資金検証には進まない。

## 14. Phase 3D-16B actual body no-leak hardening結果メモ

Phase 3D-16Bでは、Phase 3D-16Aで追加した `ActualOrderRequestBody` の no-leak / no-secret /
no-network / no-order guardを強化した。

強化した内容:

- unsafeな `SignatureHeadersBodyPlan` flagを複数同時に指定してもfail closedすることを確認。
- actual body側の複数unsafe flag同時指定をfail closedで拒否することを確認。
- `ActualOrderRequestBody` がactual headers、actual signature、credential値、raw request、
  raw response、HTTP client、endpoint、responseを保持しないことを確認。
- `to_json`、`to_http_payload`、`to_request_body` など、HTTP payload化の導線を持たないことを確認。
- no-order / no-secret / no-network guardで、実装コードにHTTP client、credential参照、
  order endpoint、raw request / raw response fieldが混入しないことを確認。

変更しなかった境界:

- `actual_order_body.py` 本体は変更していない。
- actual headers生成なし。
- actual signature生成なし。
- HMAC処理なし。
- HTTP request実装なし。
- HTTP client importなし。
- HTTP POSTなし。
- APIキー値表示なし。
- secret値表示なし。
- `.env`確認なし。
- Private API追加接続なし。
- brokerなし。
- `OrderRequest`なし。
- real order API clientなし。
- 注文API clientなし。
- 実注文なし。
- 実資金検証なし。

次候補:

- Phase 3D-16C actual headers / signature最小実装前レビュー。
- ただしPhase 3D-16Cでも、HTTP request実装、HTTP POST、実注文、実資金検証には進まない。
