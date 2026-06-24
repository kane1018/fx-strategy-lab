# Phase 3B-0: Private API read-only 公式仕様確認・実装設計

Phase 3B-0では、GMOコイン外国為替FX Private APIを将来read-only用途で扱う前に、公式仕様ベースで
read-only候補、禁止endpoint、認証・署名、APIキー / secret管理、実装分割方針を整理する。

今回は **調査・設計・docs化のみ** である。Private API接続、APIキー入力、`.env`変更、backend実装、
broker実装、注文API実装、実注文、実資金、自動売買、本番公開API追加、frontend変更には進まない。

## 1. Phase 3B-0の目的

- Private API read-only実装前に、公式仕様でendpointと認証境界を確認する。
- APIキー入力前に、secret管理、署名、ログ禁止事項を設計として固定する。
- 実装前に、read-only候補と注文・変更・取消・決済系の禁止境界を分離する。
- Phase 3Bを一括実装せず、mocked unit testから始める小さいタスクへ分割する。
- Phase 3B-0では接続しない、APIキーを扱わない、実注文しない。

## 2. 公式仕様確認結果

確認日: 2026-06-24

公式参照:

- GMOコイン 外国為替FX APIドキュメント: <https://api.coin.z.com/fxdocs/>

確認できたこと:

- 外国為替FX APIはPublic APIと、APIキー認証が必要なPrivate APIを提供している。
- base URLは `https://forex-api.coin.z.com/private`、versionは `v1`。
- APIキーは会員ページで作成し、機能ごとにパーミッションを設定できる。
- Private REST APIの制限は、同一アカウントでGETが1秒6回、POSTが1秒1回。
- Private API request headerは `API-KEY`、`API-TIMESTAMP`、`API-SIGN`。
- GET系read-only候補として、資産残高、注文情報、有効注文、約定、最新約定、建玉、建玉サマリーを確認した。
- 注文、変更、取消、決済、Private WebSocket token系のPOST/PUT/DELETE endpointを確認した。

要公式仕様確認として残すこと:

- APIキー権限画面で「read-only専用」権限をどの粒度で分離できるか。
- 実際のAPIキー発行UIの権限名、order可能権限との分離手順。
- error response bodyの全schemaと、status/error codeごとのretry可否。
- Phase 3B実接続前のIP制限利用可否と、ローカル実行時の運用手順。
- Private WebSocketをread-only通知として使うかどうか。Phase 3B初期実装では対象外。

## 3. read-only候補endpoint

Phase 3B-0で公式確認できたREST GET候補は次のとおり。Phase 3B初期実装では、mocked unit testから始め、
実接続はさらに後続タスクへ分離する。

| endpoint | method | read-onlyか | 取得する情報 | 注文・変更・取消に該当しないか | Phase 3B初期対象 | 未確定事項 |
| --- | --- | --- | --- | --- | --- | --- |
| `/private/v1/account/assets` | GET | 候補 | 時価評価総額、取引余力、現金残高、拘束証拠金、証拠金維持率、評価損益など | 該当しない | 最優先候補 | APIキー権限名、response sanitizer詳細 |
| `/private/v1/orders` | GET | 候補 | 指定した注文ID / 親注文IDの注文情報 | 取得のみ。注文作成ではない | 候補 | ID指定が必要。実接続前に取得対象IDの扱いを設計 |
| `/private/v1/activeOrders` | GET | 候補 | 有効注文一覧 | 取得のみ。取消ではない | 候補 | `count`上限、pagination扱い、既存注文あり時の停止方針 |
| `/private/v1/executions` | GET | 候補 | 指定した注文ID / 約定IDの約定情報 | 取得のみ | 候補 | ID指定が必要。テストではmocked responseのみ |
| `/private/v1/latestExecutions` | GET | 候補 | 銘柄別の最新約定一覧 | 取得のみ | 候補 | `symbol`必須。Phase 3Bでは`USD_JPY`から開始候補 |
| `/private/v1/openPositions` | GET | 候補 | 建玉一覧 | 取得のみ。建玉決済ではない | 候補 | 既存建玉あり時の停止条件とsanitized schema |
| `/private/v1/positionSummary` | GET | 候補 | 建玉サマリー | 取得のみ。建玉決済ではない | 候補 | `symbol`省略時の全銘柄取得を初期実装で許すか |

Phase 3B初期の推奨順:

1. `/private/v1/account/assets`
2. `/private/v1/openPositions`
3. `/private/v1/activeOrders`
4. `/private/v1/orders` / `/private/v1/executions` / `/private/v1/latestExecutions`
5. `/private/v1/positionSummary`

Public status確認:

- APIステータス確認はPublic API側の `/public/v1/status` で確認済みの領域であり、Private read-only初期実装に含めない。
- Private APIの疎通・認証確認をstatus代わりに行う場合も、Phase 3B-4以降の別タスクに限定する。

## 4. 禁止endpoint

公式docsで確認できた次のendpointは、Phase 3Bでは実装対象外とする。

| endpoint / 処理 | method | 禁止理由 |
| --- | --- | --- |
| `/private/v1/speedOrder` | POST | スピード注文。新規注文に該当する。 |
| `/private/v1/order` | POST | 注文。成行、指値、逆指値などの発注に該当する。 |
| `/private/v1/ifdOrder` | POST | IFD注文。発注に該当する。 |
| `/private/v1/ifoOrder` | POST | IFDOCO注文。発注に該当する。 |
| `/private/v1/changeOrder` | POST | 注文変更に該当する。 |
| `/private/v1/changeOcoOrder` | POST | OCO注文変更に該当する。 |
| `/private/v1/changeIfdOrder` | POST | IFD注文変更に該当する。 |
| `/private/v1/changeIfoOrder` | POST | IFDOCO注文変更に該当する。 |
| `/private/v1/cancelOrders` | POST | 注文の複数キャンセルに該当する。 |
| `/private/v1/cancelBulkOrder` | POST | 注文の一括キャンセルに該当する。 |
| `/private/v1/closeOrder` | POST | 決済注文、建玉決済に該当する。 |
| `/private/v1/ws-auth` | POST / PUT / DELETE | Private WebSocket token作成・延長・削除。Phase 3B初期対象外。 |
| broker `submit/send/place/cancel/amend` | n/a | broker送信関数はread-onlyではない。 |
| `OrderCandidate -> OrderRequest`変換 | n/a | 実注文導線に近づくため禁止。 |

公式docs上で見つからないが、将来見つかった場合も禁止するもの:

- レバレッジ変更。
- 設定変更。
- 資金移動。
- 口座振替。
- 注文権限の有効化。
- Live trading flag。
- cron / schedule / 常駐bot。

## 5. 認証・署名仕様

公式docsで確認できた範囲:

- Private APIはAPIキーによる認証が必要。
- required headers:
  - `API-KEY: <API_KEY>`
  - `API-TIMESTAMP: <TIMESTAMP>`
  - `API-SIGN: <SIGNATURE>`
- signatureはHMAC-SHA256のhex digestとして示されている。
- timestampはmilliseconds epoch文字列として示されている。
- REST GETの公式例では、署名対象は `<TIMESTAMP> + <METHOD> + <PATH>`。
- REST POSTの公式例では、署名対象は `<TIMESTAMP> + <METHOD> + <PATH> + <REQUEST_BODY>`。
- GET query parametersはURLに付与するが、公式GET例の署名対象にはquery stringを含めていない。
- Private REST API rate limitはGET 6 req/s、POST 1 req/s。
- error code例として、rate limit、timestamp不整合、signature不正、API key未設定、API key認証エラーなどが定義されている。

Phase 3B実装前に再確認すること:

- GET query parametersを署名対象に含めない扱いが、全GET endpointで一貫しているか。
- PUT / DELETEをPhase 3Bで使わない方針。将来使う場合はendpointごとの署名対象を再確認する。
- HTTP status code、API status code、error codeのresponse schema。
- timestamp clock skew許容幅。
- retryしてよいerrorと、即停止すべきerrorの分類。

今回のdocsには実APIキー・secret・signatureを書かない。例示はplaceholderだけに限定する。

```text
<API_KEY>
<API_SECRET>
<TIMESTAMP>
<SIGNATURE>
```

## 6. APIキー / secret管理方針

- APIキーはChatGPT / Codex / Claude Codeに貼らない。
- APIキーをdocsに書かない。
- APIキーをcommitしない。
- secretをdocsに書かない。
- `.env`を表示しない。
- `.env`を読まない。
- `.env`をgit管理しない。
- `.env.example`にも実値を書かない。Phase 3B-0では`.env.example`も変更しない。
- read-only権限とorder権限を分けられる場合は必ず分離する。
- order権限はPhase 3D直前まで使わない。
- Phase 3Bではread-only専用キーのみを想定する。
- request headers、署名対象文字列、raw payload、error response、terminal output、JSONL、summary、docsにsecretを出さない。
- APIキー管理手順は、Phase 3B-3で別途レビューし、実接続はPhase 3B-4以降に分ける。

漏洩疑いがある場合:

- その場でPhase 3B以降を停止する。
- commitしない。
- terminal / git diff / staged diff / logs / generated filesを確認する。
- キー失効・再発行・ローテーション手順のレビューへ戻る。

## 7. Phase 3B read-only実装スコープ案

Phase 3Bで実装してよい最小範囲:

- private read-only client skeleton。
- authentication helper設計。
- request signing helper設計。
- typed sanitized response schema。
- mocked responseのみのunit tests。
- raw responseを保存しない設計。
- account assets inquiry。
- open positions inquiry。
- active orders inquiry。
- order / execution history inquiry。
- no-order-import guard tests。

Phase 3Bで実装しないもの:

- order client。
- broker adapter。
- `OrderRequest`。
- `submit/send/place/cancel/amend`。
- live trading flag。
- cron / schedule / 常駐bot。
- frontend公開。
- `backend/app/main_readonly.py`変更。
- 本番公開API追加。
- Private WebSocket。
- 実接続。実接続はPhase 3B-4以降の別タスク。

## 8. ファイル構成案

将来のPhase 3B実装候補。Phase 3B-0では作成しない。

```text
backend/app/private_api/
  __init__.py
  readonly_client.py
  auth.py
  schemas.py
  errors.py

backend/app/tests/
  test_private_readonly_auth.py
  test_private_readonly_client.py
  test_private_readonly_schemas.py
  test_private_readonly_no_order_imports.py
  test_private_readonly_no_env_read.py
```

設計上の分離:

- `private_api.readonly_client` はGET inquiryだけを持つ。
- `auth.py` は署名文字列作成とheaders組み立てだけを持つ。
- `schemas.py` はsanitized responseだけを持ち、raw response保存を持たない。
- `errors.py` はsafe error分類のみを持つ。
- broker、orders、shadow candidate、RiskManagerとはimportしない。

## 9. テスト方針

Phase 3B実装時の最低限:

- APIキーやsecretの実値を使わない。
- mocked responseのみでunit testを開始する。
- HTTP clientはMockTransport等で差し替え、Private API実接続しない。
- raw responseを保存しないことを確認する。
- order endpointがimportされないことを確認する。
- `submit/send/place/cancel/amend` が存在しないことを確認する。
- `.env`を読まないことを確認する。
- response sanitizer testを追加する。
- error response handling testを追加する。
- timestamp / signature helperはplaceholderで検証する。
- GET signingではquery有無、path、methodをfixture化し、公式仕様との差分をレビューする。
- forbidden endpoint listをテストに入れ、client methodとして露出しないことを確認する。

テストで禁止するもの:

- 実APIキー。
- 実secret。
- `.env`読込。
- 実Private API接続。
- 実APIレスポンスfixture保存。
- broker import。
- 注文API payload builder。

## 10. Phase 3B分割案

Phase 3B-1:

- read-only client skeleton。
- auth helper。
- schemas。
- mocked unit tests。
- no-order-import guard。
- 実接続なし。
- 追記: Phase 3B-1は完了済み。`backend/app/private_api/` と `backend/app/tests/test_private_readonly_*.py` に、
  mocked skeleton、auth/signing helper、sanitized schemas、errors、forbidden endpoint guard、
  no-order-import guardを追加した。Private API実接続、APIキー入力、`.env`読込、broker、注文API、実注文はなし。

Phase 3B-2:

- 公式仕様に基づくread-only endpointごとのmocked tests。
- account assets / open positions / active orders / executions系response sanitizer。
- error handling test。
- 実接続なし。
- 追記: Phase 3B-2は完了済み。GET read-only候補7件のmocked provider変換、空配列・任意項目欠損、
  sanitized `PrivateApiError`、error時no-retry、forbidden endpoint guard拡張をテストした。Private API実接続、
  APIキー入力、`.env`読込・変更、broker、注文API、実注文、実資金はなし。

Phase 3B-3:

- ローカル接続前レビュー。
- APIキー管理手順レビュー。
- `.env`を使うか、OS環境変数を使うかの運用設計。
- APIキー権限分離の確認。
- 実接続なし。
- 追記: Phase 3B-3は完了済み。APIキー / secret管理、read-only権限分離、`.env`安全手順、
  Phase 3B-4初回接続endpoint、禁止endpoint、接続前後チェックリスト、停止条件をdocs化した。
  判定はAだが、Private API実接続、APIキー入力、`.env`変更、broker、注文API、実注文、実資金はなし。

Phase 3B-4:

- read-onlyローカル接続確認。
- 1回だけ、manual only。
- raw response保存なし。
- 接続後即停止してレビュー。
- 注文系endpoint、broker、実注文なし。

## 11. Phase 3Bへ進む条件

- Phase 3B-0 docs完了。
- 公式仕様でread-only endpointが確認済み。
- 禁止endpointが明確。
- APIキー / secret管理方針が明確。
- 実装範囲がread-onlyに限定されている。
- order関連名、broker関連名、OrderRequest変換を禁止している。
- mocked testsから開始する。
- 実接続はさらに別フェーズへ分離している。
- `.env` / `.env.example`を変更しない方針が維持されている。
- backend公開API / frontend / `main_readonly.py`を変更しない方針が維持されている。

Phase 3Bへ進まない条件:

- 公式仕様が確認できない。
- read-only権限とorder権限を分離できない。
- 実装対象にPOST/PUT/DELETE endpointが混入している。
- APIキー管理手順が未整理。
- secretを出さないログ・error handling方針が未整理。
- 実接続をPhase 3B-1/3B-2へ前倒ししようとしている。

## 12. run_id同秒衝突リスクの扱い

Phase 2Gで確認したrun_id同秒衝突リスクは、現在はmanual onlyのためPhase 3B-0 / 3B-1のブロッカーではない。

扱い:

- Phase 3B-0はdocs-onlyであり、run_id生成を触らない。
- Phase 3B-1はmocked unit tests中心であり、shadow runの連続実行を前提にしない。
- cron / parallel / automation化前には対応候補とする。
- unique run_id化、microseconds追加、または既存run_dir検出fail closedを将来検討する。

## 13. まだ進まない範囲

```text
Phase 3B実装
Private API実接続
APIキー入力
.env変更
.env.example変更
broker
注文API
注文変更
注文取消
決済注文
実注文
実資金
自動売買
Live Verification Mode実装
本番公開API
frontend変更
DB本番化
認証
M5や他通貨への拡張
cron / schedule / 常駐bot
```

## 14. 結論

Phase 3B-0では、GMOコイン外国為替FXの公式API docsに基づき、Private API read-only候補と禁止endpointを
整理した。

結論:

- REST GETのread-only候補は、Phase 3Bのmocked設計対象にできる。
- POSTの注文、注文変更、注文取消、決済系endpointはPhase 3B対象外として固定する。
- Private WebSocket token系は初期Phase 3B対象外とする。
- 認証・署名はplaceholder設計までに限定し、実APIキー・secretは扱わない。
- 次に進む場合は、Phase 3B-1としてmocked read-only skeleton / auth helper / schemas / no-order-import testsから始める。
