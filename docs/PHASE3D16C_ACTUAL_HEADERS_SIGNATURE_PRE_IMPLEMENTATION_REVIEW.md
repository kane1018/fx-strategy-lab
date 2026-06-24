# Phase 3D-16C: actual headers / signature 最小実装前レビュー

Phase 3D-16Cでは、Phase 3D-16Bまでで強化した `ActualOrderRequestBody` の
no-leak / no-secret / no-network / no-order guardを前提に、actual headers と actual signature の
最小実装へ進む前の責務分離と安全境界をdocs-onlyで整理する。

今回は **設計レビュー・docs化のみ** である。actual headers生成、actual signature生成、HMAC処理、
HTTP request実装、HTTP client import、HTTP POST、Private API追加接続、APIキー値確認、
secret値確認、`.env`確認、broker、`OrderRequest`、real order API client、実注文、実資金検証には進まない。

## 1. Phase 3D-16Cの目的

目的:

- actual headers / signature 最小実装前レビューを行う。
- 実headers生成前の責務を整理する。
- 実signature生成前の責務を整理する。
- API key / API secret取扱い前の境界を整理する。
- HMAC処理前の停止条件を整理する。
- HTTP POST実装前の境界を整理する。
- `ActualOrderRequestBody`、signer、headers builder、HTTP clientの責務を分離する。
- credential値、headers値、signature値、raw request、raw responseを保存・表示しない条件を固定する。
- Phase 3D-16D以降の分割案を明確にする。

今回の扱い:

- 今回は実装ではない。
- 今回はheaders生成ではない。
- 今回はsignature生成ではない。
- 今回はHMAC処理ではない。
- 今回はPrivate API接続ではない。
- 今回はHTTP request実装ではない。
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
- signature値表示なし。
- `.env`表示なし。
- `.env`変更なし。
- headers生成なし。
- signature生成なし。
- HMAC処理なし。
- HTTP request実装なし。
- HTTP client importなし。
- HTTP POSTなし。
- Private API追加接続なし。
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
-> ActualOrderRequestBody
```

まだ進まない導線:

```text
ActualOrderRequestBody
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

既存 `backend/app/private_api/auth.py` にはread-only mocked tests向けの署名helperがあるが、
Phase 3D-16Cでは読むだけに留める。注文系live verificationへ接続せず、注文用headers/signature実装にも進まない。

## 3. actual headers生成の責務整理

将来の actual headers 最小候補は、GMO Private REST APIの認証headersを作る責務を持つ可能性がある。
候補となるheader名は次の3つである。

```text
API-KEY
API-TIMESTAMP
API-SIGN
```

Phase 3D-16Cで行わないこと:

- actual headersを生成しない。
- headers dictを作らない。
- header値を保持しない。
- header値をstdoutへ出さない。
- header値をlogsへ出さない。
- header値をdocsへ書かない。
- header値をGit diffへ入れない。
- header値をtest fixture化しない。
- HTTP clientへ渡さない。
- raw requestとして保存しない。
- response headersを保存しない。

Phase 3D-16Dで作る場合の必須条件:

- headers値を保存しない。
- headers値を表示しない。
- headers値をlogs / stdout / docs / Git diffへ出さない。
- headers値をdataclass fieldに保持しない。
- headers値をtest fixture化しない。
- headers生成に失敗した場合、HTTP requestへ進まない。
- HTTP POSTはまだ禁止する。

headers builderは、signature生成後に認証headerを組み立てる責務だけを持つ。HTTP送信、retry、
実注文判定、raw artifact保存は持たない。

## 4. actual signature生成の責務整理

将来の actual signature 最小候補は、GMO Private REST API仕様に基づき、署名対象とAPI secretから
signature値を作る責務を持つ可能性がある。

将来候補の署名材料:

```text
timestamp + method + path + body + API secret
```

Phase 3D-16Cで行わないこと:

- HMAC処理しない。
- actual signature値を作らない。
- signature値を保存しない。
- signature値をログ出力しない。
- signature値をstdoutへ出さない。
- signature値をdocsへ書かない。
- signature値をGit diffへ入れない。
- API secret値を表示しない。
- API secret値をdocsへ書かない。
- API secret値をGit diffへ入れない。
- API secret値をtest fixture化しない。
- raw signing sourceを保存しない。
- HTTP POSTへ渡さない。

Phase 3D-16Dで作る場合の必須条件:

- signature値を保存しない。
- signature値を表示しない。
- signature値をlogs / stdout / docs / Git diffへ出さない。
- signature値をdataclass fieldに保持しない。
- API secret値を保存・表示・commitしない。
- raw signing sourceを保存しない。
- signerが失敗した場合、headers builderやHTTP requestへ進まない。
- HTTP POSTはまだ禁止する。

signerはsignatureだけを作る責務に限定する。headers作成、HTTP送信、実注文判定、retry、loopは持たない。

## 5. signer / headers builder / body model の分離方針

責務分離:

```text
ActualOrderRequestBody:
actual request bodyのみを保持する責務。
API key / API secret / headers / signature / HTTP情報を持たない。

signer:
timestamp + method + path + body + API secret からsignatureを作る責務。
headersを作らず、HTTP POSTしない。

headers builder:
API-KEY / API-TIMESTAMP / API-SIGN headersを作る責務。
HTTP POSTしない。headers値を保存しない。

HTTP client:
headers + body をPOSTする責務。まだ未実装。
```

Phase 3D-16Cでは、上記は設計整理のみである。

分離ルール:

- `ActualOrderRequestBody` はbody条件だけを保持し、credential値を扱わない。
- signerはAPI secretを扱う可能性があるため、将来も戻り値・logs・docs・Git diffに値を出さない。
- headers builderはAPI key / timestamp / signatureを扱う可能性があるため、将来も値を保存しない。
- HTTP clientはPhase 3D-16CでもPhase 3D-16Dでも未実装のままにする。
- signer / headers builder / HTTP clientを同じ関数にまとめない。
- fail closed時は次の責務へ進まない。

## 6. API key / API secret の扱い

Phase 3D-16CではAPI key / API secretの値を扱わない。

固定ルール:

- API key / API secret の値は表示しない。
- API key / API secret の値はdocsに書かない。
- API key / API secret の値はlogs / stdoutに出さない。
- API key / API secret の値はテストfixtureにしない。
- API key / API secret の値はGit diffに入れない。
- `.env`は表示しない。
- `.env`は変更しない。
- `.env.example`は変更しない。
- env一覧を表示しない。
- `echo`、`printenv`、`env`、`set` でcredential値や環境一覧を出さない。

Phase 3D-16Dで扱う場合の方針:

- API key / API secret は関数境界内の一時値に限定する。
- 戻り値、dataclass、logs、docs、Git diffに値を出さない。
- 値の存在確認はPhase 3D-12で完了済みとして扱い、Phase 3D-16Dで再表示しない。
- 値を扱う必要が出る場合は、Phase 3D-16Dの実装指示で明示承認とno-leak検証を必須にする。
- API key / API secret の値が出力された場合は即停止する。

## 7. Phase 3D-16Dで作ってよい候補

Phase 3D-16Dに進む場合、作ってよい候補はHTTP送信しない最小bundleに限定する。

候補名:

```text
ActualHeadersSignatureBundle
```

候補フィールド:

```text
bundle_id
actual_order_body_id
verification_run_id
headers_created
signature_created
hmac_used
http_post_enabled
raw_headers_saved
raw_signature_saved
raw_request_saved
raw_response_saved
credential_values_logged
header_names_summary
signature_algorithm_summary
```

Phase 3D-16Dで許可し得る状態:

```text
headers_created=true
signature_created=true
hmac_used=true
```

ただし、Phase 3D-16Dでも必須でfalseにする状態:

```text
http_post_enabled=false
raw_headers_saved=false
raw_signature_saved=false
raw_request_saved=false
raw_response_saved=false
credential_values_logged=false
```

Phase 3D-16Dで守るべき追加条件:

- `header_names_summary` はheader名のsummaryだけに限定し、header値を持たせない。
- `signature_algorithm_summary` はアルゴリズム名や実装状態のsummaryだけに限定し、signature値を持たせない。
- API key値、API secret値、signature値をmodel fieldに持たせない。
- raw headers、raw signature、raw request、raw responseを保存しない。
- HTTP POSTはまだ禁止する。
- real order API client、broker、`OrderRequest` へ渡さない。

## 8. Phase 3D-16Dでもまだ作らないもの

Phase 3D-16Dでも次は作らない。

- HTTP request送信。
- HTTP POST。
- HTTP client import。
- broker。
- `OrderRequest`。
- real order API client。
- 注文API client。
- retry。
- loop。
- 複数注文。
- raw request保存。
- raw response保存。
- headers値保存。
- signature値保存。
- API key値保存。
- API secret値保存。
- credential値のログ出力。
- frontend実行画面。
- 本番公開API追加。
- 実注文。
- 実資金検証。

## 9. fail closed条件

次のいずれかに該当する場合は停止する。

- APIキー値が表示された。
- secret値が表示された。
- signature値が表示された。
- `.env`が表示された。
- headers値がログ出力された。
- signature値がログ出力された。
- raw headersが保存された。
- raw signatureが保存された。
- raw requestが保存された。
- raw responseが保存された。
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
- live_verification tests failure。
- ruff failure。
- `git diff --check` failure。
- Git dirtyのまま次の実装系フェーズへ進もうとしている。
- docs-only範囲を超えた。

fail closed時の扱い:

- 実送信しない。
- credential値を表示しない。
- raw artifactを保存しない。
- 追加接続しない。
- 実注文しない。
- 原因をsanitized summaryで報告する。

## 10. Phase 3D-16D以降の分割案

### Phase 3D-16D: actual headers / signature 最小実装

目的:

- HTTP POSTなしで、actual headers / signature の最小bundleを実装する。

作るもの:

- `ActualHeadersSignatureBundle`。
- signerとheaders builderの分離実装。
- headers / signature作成成功を示す安全summary。
- no-log / no-save / no-POST guard。

作らないもの:

- HTTP POST。
- HTTP client。
- broker。
- `OrderRequest`。
- raw request / raw response保存。
- headers値 / signature値保存。
- credential値ログ出力。
- 実注文。

検証方法:

- focused tests。
- no-secret / no-order / no-network guard。
- danger word scan。
- secret scan。
- backend全体tests。
- ruff。

成功条件:

- `headers_created=true`。
- `signature_created=true`。
- `hmac_used=true`。
- `http_post_enabled=false`。
- raw artifact保存なし。
- credential値表示なし。

停止条件:

- credential値表示。
- headers値 / signature値保存。
- raw artifact保存。
- HTTP POST混入。
- `USD_JPY` / 100通貨 / 1回限定 / manual only逸脱。

### Phase 3D-16E: actual headers / signature no-leak hardening

目的:

- Phase 3D-16Dのbundleがcredential値、headers値、signature値、raw signing sourceを漏らさないことを強化する。

作るもの:

- no-leak tests。
- no-order guard強化。
- no-secret guard強化。
- fail closed tests。

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

- header値 / signature値 / API key / API secretが出力または保存された。

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
- read-only precheck sanitized summary。
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

- 1回限りの手動実行。
- sanitized summary。
- 実行後read-only確認。

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

Phase 3D-16Cでは次に進まない。

- actual headers生成。
- actual signature生成。
- HMAC処理。
- HTTP request実装。
- HTTP client import。
- HTTP POST。
- broker実装。
- `OrderRequest`実装。
- real order API client実装。
- 注文API client実装。
- Private API追加接続。
- APIキー値確認。
- secret値確認。
- `.env`確認。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend変更。
- 本番公開API追加。

## 12. 結論

Phase 3D-16Cでは、Phase 3D-16Dでactual headers / signatureの最小実装に進む前の責務分離、
禁止境界、fail closed条件、以降の分割案をdocs-onlyで整理した。

判定:

```text
A: Phase 3D-16D actual headers / signature 最小実装へ進んでよい
```

ただし、Phase 3D-16DでもHTTP POST、HTTP request送信、Private API追加接続、broker、`OrderRequest`、
real order API client、実注文、実資金検証には進まない。Phase 3D-16Dは別タスクであり、今回このまま
実装へ進まない。
