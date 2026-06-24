# Phase 3B-3: Private API read-only ローカル接続前レビュー

Phase 3B-3では、Phase 3B-4で将来1回だけPrivate API read-onlyローカル接続確認を行う前に、
APIキー / secret管理、read-only権限分離、`.env`安全手順、接続前後チェックリスト、停止条件を整理する。

今回は **レビュー・docs化のみ** である。Private API実接続、APIキー入力・表示、secret入力・表示、
`.env`読込・表示・変更、`.env.example`変更、backendコード変更、broker、注文API、実注文、実資金、
自動売買、本番公開API追加、frontend変更には進まない。

## 1. Phase 3B-3の目的

- Private API read-onlyローカル接続前の安全レビューを行う。
- APIキー入力前に、キーとsecretをCodex / ChatGPT / Claude Codeへ見せない手順を固定する。
- `.env`変更前に、表示禁止・commit禁止・git管理確認の手順を固定する。
- 実接続前の合否判定を行い、Phase 3B-4へ進めるかを整理する。
- 今回はまだ実接続しない。
- 今回はまだAPIキーを扱わない。
- 今回はまだ実注文しない。

## 2. 現在の実装状況

確認対象:

- `backend/app/private_api/auth.py`
- `backend/app/private_api/readonly_client.py`
- `backend/app/private_api/schemas.py`
- `backend/app/private_api/errors.py`
- `backend/app/tests/test_private_readonly_*.py`

確認結果:

- `auth.py` は、呼び出し元から渡された値だけで署名文字列と認証headerを組み立てる。
- `auth.py` は、process config、local credential store、`.env`を読まない。
- `readonly_client.py` は、mocked `response_provider` を注入するread-only skeletonである。
- `readonly_client.py` は、providerなしの場合 `PrivateApiConnectionDisabledError` でfail closedする。
- `readonly_client.py` のread-only whitelistはGET候補7件に限定されている。
- `readonly_client.py` のforbidden listは注文・変更・取消・決済・Private WebSocket token系を拒否する。
- `schemas.py` は、sanitized schemaだけを保持し、raw response全体を保持しない。
- `schemas.py` は、`PrivateApiError` をerror code / message / status程度に制限する。
- `errors.py` は、mocked skeleton用の例外だけを持ち、brokerや注文経路へ進まない。
- private_readonly testsは、auth helper、read-only client、endpoint別mocked payload、sanitizer、
  error handling、forbidden endpoint guard、no-order-import guardを確認している。

現在の安全境界:

- 実HTTP接続なし。
- `.env`読込なし。
- broker importなし。
- `OrderRequest`なし。
- `submit/send/place/cancel/amend` 実行関数なし。
- backend公開API変更なし。
- `main_readonly.py`変更なし。
- frontend変更なし。

## 3. APIキー / secret管理手順

Phase 3B-4で接続する場合も、APIキーとsecretはユーザー自身がローカルで管理し、Codex / ChatGPT /
Claude Codeには値を見せない。

必須ルール:

- APIキーをChatGPT / Codex / Claude Codeに貼らない。
- APIキーをdocsに書かない。
- APIキーをcommitしない。
- secretをChatGPT / Codex / Claude Codeに貼らない。
- secretをdocsに書かない。
- secretをcommitしない。
- `.env`を表示しない。
- `.env`をgit管理しない。
- `.env.example`に実値を書かない。
- terminal出力にAPIキーやsecretを表示しない。
- screenshotsにAPIキーやsecretを写さない。
- request headers、署名対象文字列、raw response、error response、JSONL、summary、docsにsecretを出さない。
- 漏洩疑いがある場合は、Phase 3B-4以降を停止し、キー失効・再発行・ローテーションのレビューへ戻る。

Phase 3B-4で許されるキー扱い:

- ユーザーがローカル環境で値を設定する。
- Codexは値を見ない。
- Codexは値を要求しない。
- Codexは値を表示しない。
- Codexは値をcommitしない。

## 4. read-only権限分離の確認手順

GMO管理画面でAPIキーを作成・確認する場合は、具体的なUI名を断定せず、画面上で次を確認する。
公式UIの権限名や粒度は **要画面確認** とする。

確認項目:

- read-only / 照会系の権限だけにできるか。
- 注文系権限をOFFにできるか。
- 注文変更権限をOFFにできるか。
- 注文取消権限をOFFにできるか。
- 決済・close position系権限をOFFにできるか。
- 送金・資金移動系権限があればOFFにする。
- read-only専用キーとorder用キーを分離する。
- Phase 3Bではread-only専用キーだけを使う。
- order権限を持つキーはPhase 3D直前まで使わない。

停止条件:

- read-only専用権限を確認できない場合は、Phase 3B-4へ進まない。
- 注文権限OFFを確認できない場合は、Phase 3B-4へ進まない。
- 権限名が不明なまま接続しない。
- order権限付きキーをread-only確認に流用しない。

## 5. `.env`を将来使う場合の安全手順

今回は `.env` を読まない、表示しない、変更しない。`.env.example` も変更しない。

将来Phase 3B-4で接続する場合の安全手順:

- `.env`はローカルのみ。
- `.env`をcatしない。
- `.env`をChatGPT / Codex / Claude Codeに貼らない。
- `.env`をgit addしない。
- `.env`がgitignore対象か確認する。
- `git status --short --ignored -- .env` などで管理状態だけを確認する。
- `.env.example`にはplaceholderだけを書く。
- `.env.example`に実値は絶対に書かない。
- terminal outputにAPIキーやsecretを出さない。
- shell historyにsecretが残る入力方法を避ける。
- `.env`がtracking対象になった場合は即停止する。

Phase 3B-4指示では、`.env`の中身を表示するコマンドを含めない。

## 6. Phase 3B-4で接続してよいendpoint候補

Phase 3B-4で接続する場合も、初回は最小限にする。

初回候補:

```text
GET /private/v1/account/assets
GET /private/v1/openPositions
GET /private/v1/activeOrders
```

原則:

- 1回だけ。
- manual only。
- local only。
- read-only専用キーのみ。
- raw response保存なし。
- headers保存なし。
- signature保存なし。
- sanitized summaryのみ確認。
- 失敗時にretryしない。
- error時に注文系へ進まない。
- 接続後はPhase 3B-4内で停止し、レビューへ戻る。

初回で扱わないread-only候補:

- `/private/v1/orders`
- `/private/v1/executions`
- `/private/v1/latestExecutions`
- `/private/v1/positionSummary`

これらはmocked testsでは確認済みだが、初回実接続では広げない。

## 7. Phase 3B-4で絶対に呼ばないendpoint / 処理

禁止endpoint:

```text
POST /private/v1/speedOrder
POST /private/v1/order
POST /private/v1/ifdOrder
POST /private/v1/ifoOrder
POST /private/v1/changeOrder
POST /private/v1/changeOcoOrder
POST /private/v1/changeIfdOrder
POST /private/v1/changeIfoOrder
POST /private/v1/cancelOrders
POST /private/v1/cancelBulkOrder
POST /private/v1/closeOrder
POST /private/v1/ws-auth
PUT /private/v1/ws-auth
DELETE /private/v1/ws-auth
```

禁止する名前・処理:

```text
OrderRequest
broker
submit
send
place
cancel
amend
close position
live trading
ENABLE_LIVE_TRADING
cron
schedule
常駐bot
```

補足:

- forbidden list / test文字列としてのendpoint名は許容する。
- 実行可能なclient method、payload builder、broker adapterとして存在してはいけない。
- POST / PUT / DELETE経路が入った場合はPhase 3B-4へ進まない。

## 8. 実接続前チェックリスト

Phase 3B-4前に最低限確認する項目:

- git working tree clean。
- backend全体tests pass。
- `ruff check .` pass。
- private_readonly tests pass。
- no-order-import guard pass。
- forbidden endpoint guard pass。
- `.env`がgit管理対象でない。
- `.env.example`に実値がない。
- APIキーを画面・ログ・docs・terminal outputに表示していない。
- secretを画面・ログ・docs・terminal outputに表示していない。
- read-only専用キーである。
- 注文権限がOFFである。
- 変更・取消・決済系権限がOFFである。
- 接続先endpointがGET read-onlyだけ。
- 接続回数は1回だけ。
- raw response保存なし。
- headers保存なし。
- signature保存なし。
- error時retryなし。
- Private API接続後にPhase 3B-4で停止する。

## 9. 実接続後チェックリスト

Phase 3B-4で接続した後に確認すべき項目:

- 実行したendpoint。
- HTTP method。
- 成功/失敗。
- sanitized schema変換結果。
- raw response保存なし。
- headers保存なし。
- APIキー保存なし。
- secret保存なし。
- signature保存なし。
- Git差分にsecretなし。
- Git差分に実API responseなし。
- 注文系endpointを呼んでいない。
- broker importなし。
- `OrderRequest`なし。
- commit対象に実データなし。
- `shadow_exports/`や`analysis_exports/`をcommitしていない。
- 接続後に追加接続・retry・loopへ進んでいない。

## 10. 停止条件

次のいずれかが出た場合、Phase 3B-4へ進まない、または即停止する。

- read-only専用権限が確認できない。
- 注文権限OFFが確認できない。
- 変更・取消・決済系権限OFFが確認できない。
- APIキーやsecretが画面・ログ・docs・terminal outputに出た。
- `.env`がgit tracking対象になった。
- `.env.example`に実値が入った。
- backend testsが失敗。
- no-order-import guardが失敗。
- forbidden endpoint guardが失敗。
- Private API clientにPOST/PUT/DELETE経路が混入。
- broker importが混入。
- `OrderRequest`が混入。
- `submit/send/place/cancel/amend` 実行関数が混入。
- raw response保存設計になっている。
- headers保存設計になっている。
- 接続時にretryやloopが入っている。
- 実接続後にPhase 3B-4で停止せず、次フェーズへ進もうとしている。

停止時は、実接続や修正を急がず、docsレビュー、mocked tests、実装範囲の再確認へ戻る。

## 11. Phase 3B-4へ進めるかの判定

判定: **A: Phase 3B-4 read-onlyローカル接続確認へ進んでよい**

理由:

- Phase 3B-0でread-only候補と禁止endpointを整理済み。
- Phase 3B-1でmocked private readonly skeletonを実装済み。
- Phase 3B-2でGET read-only候補7件のmocked tests / sanitizer / error handlingを拡張済み。
- 現在の実装は実HTTP接続を持たず、providerなしではfail closedする。
- `.env`読込なし、broker importなし、注文APIなし、`OrderRequest`なしをguardしている。
- Phase 3B-4で接続する場合の初回endpointをGET 3件に限定した。
- APIキー / secretをCodex / ChatGPT / Claude Codeに見せない手順を定義した。

ただし、今回のタスクではPhase 3B-4へ進まない。Phase 3B-4は別タスクで、1回だけ、manual only、
local only、read-only専用キーのみ、raw response保存なしで実施する。

## 12. Phase 3B-4の次回指示に含めるべき内容

次回Phase 3B-4の指示文には、最低限次を含める。

- 1回だけread-only接続。
- 接続前にユーザーがローカルでAPIキーを設定する。
- APIキーをChatGPT / Codex / Claude Codeへ貼らない。
- secretをChatGPT / Codex / Claude Codeへ貼らない。
- `.env`を表示しない。
- `.env`をcommitしない。
- 接続endpointは `account/assets` / `openPositions` / `activeOrders` まで。
- HTTP methodはGETのみ。
- raw response保存なし。
- headers保存なし。
- signature保存なし。
- sanitized outputのみ。
- retryなし。
- loopなし。
- commit/pushなし。
- 実データcommit禁止。
- Private API接続後は停止。
- 注文系endpoint禁止。
- broker禁止。
- `OrderRequest`禁止。
- 実注文禁止。
- 実資金検証へ進まない。

## 13. 変更していない重要箇所

- Private API実接続: なし。
- APIキー入力: なし。
- secret入力: なし。
- `.env` / `.env.example`: 読込・表示・変更なし。
- backendコード: 変更なし。
- backend公開API: 変更なし。
- `main_readonly.py`: 変更なし。
- frontend: 変更なし。
- broker: 変更なし。
- 注文API: 変更なし。
- 実注文: なし。
- 実資金: なし。
- `shadow_exports/` / 実データ: commit対象外。

## 14. 結論

Phase 3B-3では、Private API read-onlyローカル接続前の安全手順を整理した。

結論:

- Phase 3B-4へ進む条件はdocs上で整理済みである。
- 初回接続はGET read-only 3 endpointに限定する。
- APIキー / secretはユーザー自身がローカルで管理し、Codex / ChatGPT / Claude Codeには見せない。
- `.env`を表示・commitしない。
- raw response、headers、signatureを保存しない。
- 注文系endpoint、broker、`OrderRequest`、実注文、実資金には進まない。
- 判定は **A: Phase 3B-4 read-onlyローカル接続確認へ進んでよい**。
- ただしPhase 3B-4は別タスクであり、今回のPhase 3B-3では実接続しない。
