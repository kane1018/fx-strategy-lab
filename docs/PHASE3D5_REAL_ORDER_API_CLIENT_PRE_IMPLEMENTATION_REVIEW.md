# Phase 3D-5: real order API client実装前レビュー

## 1. Phase 3D-5の目的

Phase 3D-5は、real order API clientを実装する前の安全レビューである。

目的:

- real order API client実装前レビューを行う。
- 実注文可能コードを作る前の最終境界を確認する。
- `MockedOrderPayloadCandidate` からreal order clientへ進む前の安全条件を整理する。
- 何を作ってよいか、何をまだ作らないか、どの条件を満たすまで実装禁止かを固定する。
- 100通貨、`USD_JPY`、1回限定、manual onlyの制約を維持する。

今回の範囲外:

- 今回は実装ではない。
- 今回はPrivate API接続ではない。
- 今回はAPIキー確認ではない。
- 今回は`.env`確認ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. 現在の安全到達点

Phase 3D-4Bまでで、次を確認済みである。

- `READY_FOR_ORDER_REVIEW` までのdry-run flowを確認済み。
- `OrderReview` / `FinalOrderChecklist` をreview-only objectとして確認済み。
- `NoNetworkBrokerBoundaryResult` / no-network adapterを確認済み。
- `MockedOrderPayloadCandidate` をlocal-only / no-send candidateとして確認済み。
- no-send / fail-closed hardening済み。
- candidateは `endpoint` / `method` / `path` / `url` / `request_body` / `payload` を保持しない。
- candidateは `headers` / `signature` / `api_key` / `secret` / `authorization` / `timestamp` / `sign` を保持しない。
- `execution_type=MARKET`、`time_in_force=FAK`、`settle_type=OPEN` のlocal-only値に固定済み。
- 表記揺れや不許可値は拒否する。
- brokerなし。
- `OrderRequest` なし。
- 注文API clientなし。
- HTTP POSTなし。
- HTTP PUTなし。
- HTTP DELETEなし。
- 実注文なし。
- 実資金検証なし。

この到達点は、実注文可能状態ではない。あくまで実注文可能コードを作る前にレビューできる状態である。

## 3. real order API client実装前の必須条件

real order API client関連の実装へ進む前に、最低限すべて満たす必要がある。

- backend全体tests pass。
- ruff pass。
- live_verification focused tests pass。
- no-order-import guard pass。
- payload candidate no-send guard pass。
- Git clean。
- secret混入なし。
- `.env` / `.env.example` 変更なし。
- `shadow_exports/` / 実データ commitなし。
- Phase 3D-5レビューdocs完了。
- real order API client実装前のユーザー明示承認。
- 実注文前の別途ユーザー明示承認。

1項目でも未確認またはNGなら、real order API client実装へ進まない。

## 4. 今回まだ作ってはいけない範囲

Phase 3D-5では次を作らない。

- real order API client。
- broker。
- `OrderRequest`。
- 注文API client。
- 注文payload builder。
- HTTP POST。
- HTTP PUT。
- HTTP DELETE。
- `API-KEY` / `API-TIMESTAMP` / `API-SIGN` 生成。
- 署名付き注文request。
- 注文変更API。
- 注文取消API。
- 決済API。
- `speedOrder`。
- `ws-auth`。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend実行画面。
- 本番公開API。
- retry注文。
- loop注文。
- cron / schedule / 常駐bot。

## 5. 将来のreal order API clientで扱う可能性がある最小範囲

将来扱うとしても、初回候補は次に限定する。

- endpoint候補は `POST /private/v1/order` のみ。
- `symbol=USD_JPY` のみ。
- `units=100` のみ。
- `execution_type=MARKET` のみ。
- `time_in_force=FAK` のみ。
- `settle_type=OPEN` のみ。
- 1 `verification_run_id` につき1回のみ。
- manual confirmation必須。
- read-only precheck直前成功必須。
- 既存建玉なし。
- 未約定注文なし。
- retryなし。
- loopなし。
- cronなし。

ただし、Phase 3D-5ではこのclientを作らない。上記は将来レビュー対象の候補範囲であり、実装許可ではない。

## 6. 絶対に使わない / 今は使わないendpoint

### 絶対に今は使わないendpoint

- `POST /private/v1/speedOrder`
- `POST /private/v1/ifdOrder`
- `POST /private/v1/ifoOrder`
- `POST /private/v1/changeOrder`
- `POST /private/v1/changeOcoOrder`
- `POST /private/v1/changeIfdOrder`
- `POST /private/v1/changeIfoOrder`
- `POST /private/v1/cancelOrders`
- `POST /private/v1/cancelBulkOrder`
- `POST /private/v1/closeOrder`
- `POST /private/v1/ws-auth`
- `PUT /private/v1/ws-auth`
- `DELETE /private/v1/ws-auth`

### 今回も次フェーズでも禁止する領域

- `speedOrder`
- IFD / IFO / OCO
- change
- cancel
- close
- `ws-auth`
- WebSocket private auth

これらは初回の100通貨・1回限定・manual onlyの疎通確認には不要であり、実注文・変更・取消・決済・認証token発行に直結するため、別レビューなしに扱わない。

## 7. APIキー / secret / .env の扱い

Phase 3D-5ではAPIキー、secret、`.env` を扱わない。

方針:

- APIキー確認なし。
- `.env`確認なし。
- secret表示なし。
- APIキー値を要求しない。
- secret値を要求しない。
- 実装コード内で `os.environ` / `getenv` を使わない。
- docs、commit、test fixtureにAPIキー・secretを含めない。
- ChatGPT / Codex / docs / commit にAPIキー・secretを貼らない。
- 将来APIキーを扱う場合も、人間がローカル環境で管理する。
- 将来のAPIキー権限は最小化し、read-only権限との分離を再確認する。

APIキー / secret / `.env` を扱う必要が出た場合は、Phase 3D-5の範囲を超えるため停止する。

## 8. 実HTTP POST禁止方針

Phase 3D-5ではHTTP POSTは禁止する。

方針:

- Phase 3D-5ではHTTP POST / PUT / DELETE禁止。
- 次の実装フェーズでも、まずno-network skeleton / disabled-by-defaultから始める。
- network-enabled clientはさらに別レビュー後に限定する。
- 実注文前には別途明示承認を必須にする。
- retryによる再注文は禁止。
- loopは禁止。
- cron / schedule / 常駐botは禁止。

HTTP POSTを作る必要が出た場合は、Phase 3D-5の範囲を超えるため停止する。

## 9. Phase 3D-6以降の推奨分割

今後進む場合は、次のように細分化する。

### Phase 3D-6: real order API client no-network skeleton / disabled-by-default設計・mock実装

目的:

- real order API clientの形だけをno-network / disabled-by-defaultで定義する。
- 送信関数、HTTP client、署名、APIキー参照はまだ作らない。

作るもの:

- no-network skeleton。
- disabled-by-default設定。
- 実送信不能を確認するtests。

作らないもの:

- HTTP POST。
- APIキー参照。
- 署名付きrequest。
- broker。
- 実注文。

### Phase 3D-7: 署名・HTTP request設計レビュー。ただし実送信なし

目的:

- 署名、method、path、bodyの設計だけをレビューする。
- まだ送信コードを作らない。

作るもの:

- docsレビュー。
- mock-only設計メモ。

作らないもの:

- 実HTTP request。
- APIキー参照。
- 実署名生成。
- 実注文。

### Phase 3D-8: network disabled integration tests / no-send verification

目的:

- network disabled状態で、誤送信できないことをテストで確認する。

作るもの:

- network disabled tests。
- no-send verification。

作らないもの:

- network-enabled client。
- 実HTTP POST。
- 実注文。

### Phase 3D-9: 実注文前最終レビュー

目的:

- 実注文へ進むかを最終判断する。

確認するもの:

- read-only precheck直前成功。
- 既存建玉なし。
- 未約定注文なし。
- backend tests / ruff pass。
- Git clean。
- secret混入なし。
- ユーザー明示承認。

作らないもの:

- 新しい実装。
- 実注文。

### Phase 3D-10: 100通貨・1回限定・手動承認つき極小実注文検証

目的:

- 100通貨、`USD_JPY`、1回限定、manual onlyの極小疎通を検証する。

前提:

- Phase 3D-9までの全条件を満たす。
- ユーザーがChatGPT上で明示承認する。

禁止:

- retry。
- loop。
- cron。
- 自動売買。
- 追加注文。

Phase 3D-5では、これらの後続フェーズを実行しない。

## 10. real order API client実装前の明示承認条件

real order API client実装へ進む前に、最低限次をすべて満たす必要がある。

- ユーザーがreal order API clientの実装開始を明示承認する。
- 実装範囲がno-network / disabled-by-defaultである。
- HTTP POSTはまだ作らない。
- APIキー確認はまだしない。
- `.env`確認はまだしない。
- brokerはまだ作らない。
- `OrderRequest`はまだ作らない。
- 実注文はまだしない。
- backend tests pass。
- ruff pass。
- Git clean。
- secret混入なし。

## 11. 実注文前の明示承認条件

実注文前には、最低限次をすべて満たす必要がある。

- ユーザーが100通貨・1回限定の実注文検証をChatGPT上で明示承認する。
- 直前read-only precheck成功。
- 既存建玉なし。
- 未約定注文なし。
- risk decision `ALLOW`。
- `READY_FOR_ORDER_REVIEW` 到達。
- `OrderReview` / `FinalChecklist` pass。
- payload candidate pass。
- no-send guard確認。
- backend tests pass。
- ruff pass。
- Git clean。
- secret混入なし。
- 実行内容、最大損失、停止条件をユーザーが理解している。

1項目でも未確認またはNGなら、実注文には進まない。

## 12. Phase 3D-6へ進めるかの判定

判定:

**A: Phase 3D-6 real order API client no-network skeleton / disabled-by-default設計・mock実装へ進んでよい。**

理由:

- Phase 3D-4Bまででno-send / fail-closed / no-order guardが確認済み。
- backend tests / ruff / live_verification focused testsが直近で通過済み。
- `MockedOrderPayloadCandidate` は送信不能なlocal-only candidateのまま維持されている。
- broker、`OrderRequest`、注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証は未実装である。

ただし、Phase 3D-5ではPhase 3D-6を実行しない。次候補として提案するだけで停止する。

## 13. まだ進まない範囲

Phase 3D-5では次へ進まない。

- Phase 3D-6の実行。
- real order API client実装。
- broker実装。
- `OrderRequest`実装。
- 注文API実装。
- HTTP POST。
- HTTP PUT。
- HTTP DELETE。
- 署名付き注文request。
- APIキー確認。
- `.env`確認。
- 実注文。
- 実資金検証。
- 自動売買。
- frontend変更。
- 本番公開API追加。

Phase 3D-5は、real order API client実装前のレビューdocsで停止する。
