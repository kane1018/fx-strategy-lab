# Phase 3D-13: 署名 / headers / request body 実装前レビュー

Phase 3D-13では、Phase 3D-12で `GMO_FX_API_KEY` / `GMO_FX_API_SECRET` の存在が
`set` とだけ確認済みであることを前提に、署名、headers、request bodyを実装する前の責務境界を整理する。

今回は **実装ではない**。署名生成、headers生成、request body生成、HTTP request、HTTP POST、
Private API接続、broker、`OrderRequest`、real order API client、実注文、実資金検証には進まない。

## 1. Phase 3D-13の目的

目的:

- 署名 / headers / request body 実装前レビューを行う。
- APIキー存在確認後に、実値を扱う前の責務境界を固定する。
- 実署名、実headers、実request bodyを作る前に、作ってよいplanと作ってはいけない実体を分離する。
- HTTP POST実装前の停止条件を整理する。
- credential値、`.env`、raw request、raw response、headers、signatureを保存しない境界を固定する。
- 100通貨、`USD_JPY`、1回限定、manual onlyを維持する。

今回の扱い:

- 今回は実装ではない。
- 今回はHTTP request実装ではない。
- 今回は署名実装ではない。
- 今回はheaders生成ではない。
- 今回はrequest body生成ではない。
- 今回はAPIキー確認ではない。
- 今回はPrivate API接続ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. 現在の状態

Phase 3D-12で確認済み:

```text
GMO_FX_API_KEY: set
GMO_FX_API_SECRET: set
```

これは存在有無だけの確認であり、APIキー値、secret値、`.env`内容、環境変数一覧は表示していない。

現在のno-network chain:

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

現在まだ進んでいない範囲:

```text
-/-> actual signature
-/-> actual headers
-/-> actual request body
-/-> real HTTP request
-/-> API-KEY / API-SIGN / API-TIMESTAMP 実値
-/-> POST /private/v1/order
-/-> broker
-/-> OrderRequest
-/-> 実注文
```

Phase 3D-10Bまでの安全到達点:

- `DisabledHttpRequestClientSkeletonPlan` は no-network / no-secret / no-order guard済み。
- `disabled_by_default=true`。
- `network_enabled=false`。
- `credential_access_enabled=false`。
- `http_client_enabled=false`。
- `http_post_enabled=false`。
- `headers_created=false`。
- `request_body_created=false`。
- `actual_signature_created=false`。
- `raw_request_created=false`。
- `raw_response_saved=false`。
- `api_key_used=false`。
- `api_secret_used=false`。
- `hmac_used=false`。
- `real_order_attempted=false`。

## 3. 署名責務の整理

将来の署名責務は、仕様上は次の材料から署名候補を作る責務である。

```text
timestamp + method + path + body + API secret -> signature candidate
```

ただしPhase 3D-13では、これは仕様上の責務整理に留める。

Phase 3D-13で行わないこと:

- HMAC処理を実装しない。
- signature値を作らない。
- API secret値を扱わない。
- API secret値を表示しない。
- `.env`を読まない。
- signatureを保存しない。
- signatureをログ、docs、stdout、Git diffに出さない。

将来の署名層が満たすべき条件:

- 入力は明示的に渡された値だけに限定する。
- 値をログ出力しない。
- raw signing sourceを保存しない。
- signature値を保存しない。
- HTTP POSTとは別層に分離する。
- fail closed時にHTTP requestへ進まない。

## 4. headers責務の整理

将来のheaders候補は、仕様上は次の要素を持つ可能性がある。

```text
API-KEY
API-TIMESTAMP
API-SIGN
```

ただしPhase 3D-13では、headersを生成しない。実値も保持しない。

Phase 3D-13で行わないこと:

- headers dictを作らない。
- `API-KEY` 実値を保持しない。
- `API-TIMESTAMP` 実値を生成しない。
- `API-SIGN` 実値を生成しない。
- headersをログ、docs、stdout、Git diffに出さない。
- response headersを保存しない。

将来のheaders層が満たすべき条件:

- headers生成は署名生成後の別責務に限定する。
- headersをraw artifactとして保存しない。
- headers値をテストfixture化しない。
- headers生成に失敗した場合、HTTP requestへ進まない。

## 5. request body責務の整理

将来のrequest body候補は、100通貨・`USD_JPY`・1回限定・manual onlyの最小注文条件に必要な形だけを扱う。

将来候補として追加レビューが必要なbody項目:

- `symbol`
- `side`
- `size`
- `executionType`
- `timeInForce`
- `settleType`

Phase 3D-13で行わないこと:

- request body dictを作らない。
- JSON bodyを作らない。
- raw requestを作らない。
- raw requestを保存しない。
- `POST /private/v1/order` に渡せる形へ変換しない。
- `MockedOrderPayloadCandidate` を送信用payloadに変換しない。

将来のrequest body層が満たすべき条件:

- `symbol=USD_JPY` のみ。
- `size=100` のみ。
- `executionType=MARKET` 候補は追加レビュー後に限定。
- `timeInForce=FAK` 候補は追加レビュー後に限定。
- `settleType=OPEN` 候補は追加レビュー後に限定。
- body生成に失敗した場合、署名、headers、HTTP requestへ進まない。

## 6. 責務分離方針

Phase 3D-13時点では、以下の責務を混ぜない。

```text
MockedOrderPayloadCandidate:
  local-only候補。送信用bodyではない。

DisabledOrderClientPlan:
  no-network / disabled-by-default のclient計画。HTTP情報を持たない。

SignatureHttpRequestDesignModel:
  署名・HTTP request形状のdesign-only model。実署名、headers、bodyを持たない。

DisabledHttpRequestClientSkeletonPlan:
  HTTP request client直前のdisabled skeleton。HTTP client、POST、headers、bodyを持たない。

future signature / headers / body plan:
  将来の責務境界だけを表すplan。実値は持たない。

future request body builder:
  将来の送信用bodyを作る責務。まだ未実装。

future signer:
  将来のsignature候補を作る責務。まだ未実装。

future headers builder:
  将来のheaders候補を作る責務。まだ未実装。

future HTTP client:
  将来POSTする責務。まだ未実装。
```

Phase 3D-13では、上記のうち `future signature / headers / body plan` の設計境界までを整理する。
実builder、実signer、実headers builder、実HTTP clientは作らない。

## 7. Phase 3D-14で作ってよい候補

Phase 3D-14に進む場合でも、作ってよいのは **plan-only** の候補に限定する。

候補:

```text
SignatureHeadersBodyPlan
```

候補フィールド:

```text
plan_id
verification_run_id
skeleton_id
body_plan_created
headers_plan_created
signature_plan_created
actual_body_created
actual_headers_created
actual_signature_created
http_post_enabled
credential_values_exposed
raw_request_saved
raw_response_saved
fail_reasons
```

必須条件:

```text
body_plan_created=true
headers_plan_created=true
signature_plan_created=true
actual_body_created=false
actual_headers_created=false
actual_signature_created=false
http_post_enabled=false
credential_values_exposed=false
raw_request_saved=false
raw_response_saved=false
```

Phase 3D-14のplanが許可すること:

- 実装前の責務境界をコード上のlocal-only planとして表現する。
- `DisabledHttpRequestClientSkeletonPlan` からID相関を保持する。
- no-network / no-secret / no-order flagを持つ。
- fail closed理由を保持する。

Phase 3D-14のplanが許可しないこと:

- actual body生成。
- actual headers生成。
- actual signature生成。
- API key / secret値の保持。
- HTTP POST。
- HTTP client import。
- `POST /private/v1/order` 実行可能コード。

## 8. Phase 3D-14でもまだ作らないもの

Phase 3D-14でも次は作らない。

- actual signature value。
- actual headers。
- actual request body。
- raw request。
- raw response。
- HTTP request。
- HTTP client import。
- HTTP POST。
- HMAC処理。
- API key値の表示または保持。
- API secret値の表示または保持。
- `.env`参照。
- broker。
- `OrderRequest`。
- real order API client。
- 注文API client。
- 実注文。
- 実資金検証。

## 9. fail closed条件

次のいずれかに該当する場合は停止する。

- APIキー値を表示した。
- API secret値を表示した。
- `.env`を表示した。
- actual headersを生成した。
- actual signatureを生成した。
- actual request bodyを生成した。
- raw requestを保存した。
- raw responseを保存した。
- headersを保存した。
- signatureを保存した。
- HTTP client importが混入した。
- HTTP POSTが混入した。
- `POST /private/v1/order` が実行可能コードに混入した。
- brokerが混入した。
- `OrderRequest`が混入した。
- `symbol` が `USD_JPY` 以外。
- `size` が100以外。
- 1回限定ではない。
- manual onlyではない。
- retryまたはloopの可能性がある。
- backend testsが失敗した。
- live_verification testsが失敗した。
- ruffが失敗した。
- Gitがdirty。
- `shadow_exports/` または `analysis_exports/` がtracked。
- ユーザー明示承認なしに実注文へ進もうとした。

## 10. Phase 3D-14以降の分割案

### Phase 3D-14: signature / headers / request body plan実装

目的:

- 実body、実headers、実signatureを作る前に、plan-only objectを実装する。

作るもの:

- `SignatureHeadersBodyPlan`。
- plan-only build function。
- no-secret / no-network / no-order tests。

作らないもの:

- actual body。
- actual headers。
- actual signature。
- HTTP client。
- HTTP POST。
- API key / secret値参照。
- 実注文。

検証方法:

- focused tests。
- live_verification tests。
- backend全体tests。
- ruff。
- no-order / no-secret / no-network guard。

成功条件:

- plan-onlyでID相関を保持する。
- actual body / headers / signatureがない。
- HTTP POSTがない。
- credential値がない。

停止条件:

- 実値、実body、実headers、実signature、HTTP client、HTTP POSTが混入した場合。

### Phase 3D-14B: no-secret guard hardening

目的:

- Phase 3D-14のplanがsecret、headers、body、signature、HTTPに変質しないことを強化する。

作るもの:

- fail closed tests。
- 禁止field / 禁止import / 禁止文字列 guard。

作らないもの:

- actual signature。
- actual headers。
- actual body。
- HTTP POST。
- 実注文。

検証方法:

- focused tests。
- no-order / no-secret / no-network guard。
- 危険語scan。

成功条件:

- unsafe flagや禁止fieldが必ずfail closedする。

停止条件:

- credential値、HTTP送信、実request artifactが混入した場合。

### Phase 3D-15: actual body / headers / signature最小実装前レビュー

目的:

- actual body、headers、signatureを最小実装する前の最終レビューを行う。

作るもの:

- docs-onlyレビュー。
- まだ実装しない。

作らないもの:

- actual body。
- actual headers。
- actual signature。
- HTTP POST。
- 実注文。

検証方法:

- 既存tests。
- ruff。
- no-secret / no-order guard確認。

成功条件:

- 実装範囲と停止条件が明確。

停止条件:

- レビューなしに実装へ進む場合。

### Phase 3D-16: actual body / headers / signature最小実装

目的:

- HTTP POSTなしで、最小のbody / headers / signature生成をlocal-onlyに実装する。

作るもの:

- local-only body builder。
- local-only signer。
- local-only headers builder。

作らないもの:

- HTTP client。
- HTTP POST。
- raw request保存。
- raw response保存。
- 実注文。

検証方法:

- unit tests。
- no-log / no-save / no-network guard。
- secret値非表示確認。

成功条件:

- 実HTTP送信なし。
- 値を保存しない。
- secretを表示しない。

停止条件:

- HTTP POST、raw artifact保存、credential表示が発生した場合。

### Phase 3D-17: HTTP POST実装前レビュー

目的:

- HTTP POSTを作る前に、最終的な送信責務と停止条件をdocs-onlyで確認する。

作るもの:

- docs-onlyレビュー。

作らないもの:

- HTTP POST。
- 実注文。

検証方法:

- existing tests。
- no-order guard。
- Git / secret scan。

成功条件:

- POST解禁条件と実注文停止条件が明確。

停止条件:

- 明示承認なしに送信可能コードへ進む場合。

### Phase 3D-18: 100通貨・1回限定・manual only実注文最終レビュー

目的:

- 実注文直前に、技術状態、口座状態、注文条件、ユーザー承認を最終確認する。

作るもの:

- docs-only最終レビュー。
- 実行チェックリスト。

作らないもの:

- 実注文。
- 追加注文。
- retry。
- loop。

検証方法:

- 直前read-only precheck。
- backend tests。
- ruff。
- Git clean。
- no-secret / no-order scan。

成功条件:

- 既存建玉なし。
- 未約定注文なし。
- `USD_JPY` / 100通貨 / 1回限定 / manual only。
- ユーザー明示承認あり。

停止条件:

- 1項目でも条件未充足の場合。

### Phase 3D-19: 100通貨・1回限定・手動承認つき実注文

目的:

- 明示承認後に、100通貨・1回限定・手動承認つきで極小実注文を行う。

作るもの:

- この段階でのみ、承認済みの実行手順に従う。

作らないもの:

- retry。
- loop。
- 追加注文。
- 自動売買。
- frontend実行画面。
- 本番公開API。

検証方法:

- 直前read-only precheck。
- 実行後read-only確認。
- sanitized summaryのみ。

成功条件:

- 1回だけ実行し、即停止する。
- raw response、headers、signatureを保存しない。
- 実データをcommitしない。

停止条件:

- ユーザー明示承認なし。
- 既存建玉あり。
- 未約定注文あり。
- 複数注文の可能性。
- retry / loopの可能性。

## 11. 今回まだ進まない範囲

Phase 3D-13では次へ進まない。

- 署名生成実装。
- HMAC処理実装。
- timestamp生成実装。
- headers生成。
- request body生成。
- HTTP request実装。
- HTTP client import。
- HTTP POST。
- APIキー確認。
- API key値表示。
- API secret値表示。
- `.env`確認。
- `.env`表示。
- Private API接続。
- broker実装。
- `OrderRequest`実装。
- real order API client実装。
- 注文API client実装。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend変更。
- 本番公開API追加。

## 12. 結論

Phase 3D-13では、Phase 3D-12でAPIキー環境変数が `set` と確認済みであることを前提に、
署名、headers、request bodyの実装前境界をdocs-onlyで整理した。

判定:

```text
A: Phase 3D-14 signature / headers / request body plan実装へ進んでよい
```

ただし、Phase 3D-14でも作ってよいのはplan-only objectまでである。actual body、actual headers、
actual signature、HTTP request、HTTP POST、Private API接続、broker、`OrderRequest`、実注文、
実資金検証には進まない。

## 13. Phase 3D-14実装結果メモ

Phase 3D-14では、Phase 3D-13の設計に基づき、`DisabledHttpRequestClientSkeletonPlan` の後段に
`SignatureHeadersBodyPlan` を追加した。

実装内容:

- `backend/app/live_verification/signature_headers_body_plan.py` を追加。
- `SignatureHeadersBodyPlan` を追加。
- `build_signature_headers_body_plan()` を追加。
- `signature_headers_body_plan_id` を決定論的に生成。
- `body_plan_created=true`、`headers_plan_created=true`、`signature_plan_created=true` をplan-only markerとして固定。
- actual body、actual headers、actual signature、HTTP POST、credential exposure、raw request /
  raw response、headers / signature保存、HMAC、real order attemptはfalseで固定。
- unsafe skeletonまたはplan flagは `plan_passed=false` と `fail_reasons` でfail closed。
- `backend/app/tests/test_live_verification_signature_headers_body_plan.py` を追加。

維持した境界:

- APIキー値表示なし。
- secret値表示なし。
- `.env`確認なし。
- 実署名生成なし。
- HMAC処理なし。
- headers生成なし。
- request body生成なし。
- HTTP request実装なし。
- HTTP client importなし。
- HTTP POSTなし。
- brokerなし。
- `OrderRequest`なし。
- real order API clientなし。
- 実注文なし。
- 実資金検証なし。

次候補:

- Phase 3D-14B no-secret guard hardening。
- ただしPhase 3D-14Bでも、実署名、headers生成、request body生成、HTTP request、実注文、実資金検証には進まない。
