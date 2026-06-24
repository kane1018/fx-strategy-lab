# Phase 3D-0: GMO FX order API公式仕様・危険endpoint再レビュー

Phase 3D-0では、Phase 3C-3 dry-run統合とPhase 3D前レビュー完了後、broker / order API実装へ進む前に、
GMOコイン外国為替FXの注文系API仕様と危険endpointを公式情報ベースで再確認する。

今回は **レビュー・docs化のみ** である。broker実装、OrderRequest実装、注文API client実装、
注文payload builder実装、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証、
自動売買、本番公開API追加には進まない。

## 1. Phase 3D-0の目的

目的:

- GMO FX order API公式仕様・危険endpointを再レビューする。
- broker / order API実装前に、注文系endpointの危険度を分類する。
- 実注文可能コードを作る前に、read-only endpointとorder endpointの境界を固定する。
- 100通貨、`USD_JPY`、1回限定、manual onlyの前提で、将来必要になり得る最小要件を整理する。
- Phase 3D-1以降で扱ってよい範囲と、まだ扱ってはいけない範囲を分離する。
- 実注文前の追加レビュー条件と明示承認条件を再整理する。

今回の扱い:

- 今回は実装ではない。
- 今回はPrivate API接続ではない。
- 今回はAPIキー確認ではない。
- 今回は`.env`確認ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. 公式仕様確認の扱い

参照した公式docs:

- GMOコイン 外国為替FX APIドキュメント: <https://api.coin.z.com/fxdocs/>

参照した既存docs:

- [PHASE3D_PRE_ORDER_API_REVIEW.md](PHASE3D_PRE_ORDER_API_REVIEW.md)
- [PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md](PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md)
- [PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md](PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md)
- [PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md](PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md)
- [PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md](PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md)

公式ページ再確認:

- 2026-06-24に公開docsを再確認できた。
- 公式docs上で、Private API base URL、現行version、Private API rate limit、APIキー権限、
  Private API認証、read-only系GET endpoint、注文・変更・取消・決済系POST endpoint、
  Private WebSocket API用token endpointを確認した。
- 公式仕様確認のためのPrivate API接続は行っていない。
- APIキー存在確認、APIキー値表示、secret値表示、`.env`確認は行っていない。

既存docsに基づく前提:

- Phase 3B-4で `GET /private/v1/account/assets`、`GET /private/v1/openPositions`、
  `GET /private/v1/activeOrders` のread-only接続確認は完了済み。
- Phase 3C-3でREADY_FOR_ORDER_REVIEWまでのdry-run flowは確認済み。
- READY_FOR_ORDER_REVIEWは実注文可能状態ではなく、実注文前レビュー可能状態である。
- broker、OrderRequest、注文API、注文payload builderは未実装である。

今回のレビューで未確定の項目:

- 実注文用APIキー権限のUI上の正確な名称と、read-only権限との分離手順。
- 注文APIの全エラーコード、業務エラー、約定直後の状態遷移、取消不能状態の詳細分類。
- `executionType`、`price`、`upperBound`、`lowerBound`、有効期限、スリッページ相当値を将来どのように制限するか。
- 実注文前の最終payload reviewで、どの注文タイプだけを候補に残すか。

## 3. read-only endpointとorder endpointの分離

Phase 3B-4で確認済みのread-only endpoint:

| endpoint | method | 分類 | Phase 3D-0での扱い |
| --- | --- | --- | --- |
| `/private/v1/account/assets` | GET | read-only | Phase 3B-4で確認済み。今回は再接続しない。 |
| `/private/v1/openPositions` | GET | read-only | Phase 3B-4で確認済み。今回は再接続しない。 |
| `/private/v1/activeOrders` | GET | read-only | Phase 3B-4で確認済み。今回は再接続しない。 |

read-only endpointの位置づけ:

- 注文、注文変更、注文取消、決済とは明確に分離する。
- Phase 3Dでも、実注文直前のprecheck用途に限定する。
- 実注文前には、既存建玉なし、未約定注文なしを再確認する。
- raw response、headers、signature、credentialsは保存しない。

order endpointの位置づけ:

- POST / PUT / DELETEの注文系、変更系、取消系、決済系、ws-auth系はread-onlyではない。
- Phase 3D-0では公式仕様確認と危険分類のみを行う。
- Phase 3D-1でも実装対象にしない。
- Phase 3D-2でも実HTTP POSTは禁止する。

## 4. 危険endpoint一覧

| endpoint | 種別 | 危険度 | 今回の扱い | Phase 3D-1で扱うか | Phase 3D-2以降で扱うか | 実注文前に追加レビューが必要か |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /private/v1/order` | 新規注文 | High | Review only / forbidden now | 扱わない | Phase 3D-3以降のレビュー候補。実HTTP POSTは不可 | 必要 |
| `POST /private/v1/speedOrder` | スピード注文 | High | Review only / forbidden now | 扱わない | 原則扱わない。初回100通貨検証候補から除外 | 必要 |
| `POST /private/v1/ifdOrder` | IFD新規注文 | High | Review only / forbidden now | 扱わない | 原則扱わない。複合注文は初回対象外 | 必要 |
| `POST /private/v1/ifoOrder` | IFDOCO新規注文 | High | Review only / forbidden now | 扱わない | 原則扱わない。複合注文は初回対象外 | 必要 |
| `POST /private/v1/changeOrder` | 通常注文変更 | High | Review only / forbidden now | 扱わない | 初回実注文検証前後とも対象外 | 必要 |
| `POST /private/v1/changeOcoOrder` | OCO注文変更 | High | Review only / forbidden now | 扱わない | 対象外 | 必要 |
| `POST /private/v1/changeIfdOrder` | IFD注文変更 | High | Review only / forbidden now | 扱わない | 対象外 | 必要 |
| `POST /private/v1/changeIfoOrder` | IFDOCO注文変更 | High | Review only / forbidden now | 扱わない | 対象外 | 必要 |
| `POST /private/v1/cancelOrders` | 注文の複数キャンセル | High | Review only / forbidden now | 扱わない | 初回では実装しない。取消方針レビューが先 | 必要 |
| `POST /private/v1/cancelBulkOrder` | 注文の一括キャンセル | High | Review only / forbidden now | 扱わない | 対象外。広範囲取消のため特に危険 | 必要 |
| `POST /private/v1/closeOrder` | 決済注文 | High | Review only / forbidden now | 扱わない | 初回100通貨検証でも別レビュー必須 | 必要 |
| `POST /private/v1/ws-auth` | Private WebSocket token取得 | High | Review only / forbidden now | 扱わない | 初回実注文検証では対象外 | 必要 |
| `PUT /private/v1/ws-auth` | Private WebSocket token延長 | High | Review only / forbidden now | 扱わない | 対象外 | 必要 |
| `DELETE /private/v1/ws-auth` | Private WebSocket token削除 | High | Review only / forbidden now | 扱わない | 対象外 | 必要 |

補足:

- `POST /private/v1/order` は通常の新規注文であり、`symbol`、`side`、`size`、
  `executionType` などの注文成立に関わる入力を持つため、実注文可能コードに直結する。
- `POST /private/v1/speedOrder` は成行系のスピード注文として扱い、初回の安全検証候補から除外する。
- IFD / IFDOCOは複合注文であり、初回100通貨・1回限定の最小検証には過剰である。
- change / cancel / close系は、既存注文や建玉を変更・取消・決済できるため、初回実装候補から除外する。
- ws-auth系はPrivate WebSocket通知の入口であり、token管理と通知購読範囲の追加レビューが必要である。

## 5. endpoint危険度分類

High:

- 新規注文を出せるendpoint。
- 決済注文を出せるendpoint。
- 既存注文を変更できるendpoint。
- 既存注文を取消できるendpoint。
- Private WebSocket認証tokenを発行、延長、削除できるendpoint。

Forbidden now:

- Phase 3D-0では、全注文系endpointは実装しない。
- Phase 3D-1でも、全注文系endpointは実装しない。
- Phase 3D-2でも、実HTTP POST / PUT / DELETEは禁止する。
- broker、OrderRequest、注文API client、注文payload builderは作らない。

Review only:

- 公式仕様確認。
- endpoint名、method、種別、危険度、将来レビュー要否のdocs整理。
- 既存Live Verification dry-runの安全境界との照合。

## 6. 100通貨・USD_JPY・1回限定に必要な最小要件

将来、100通貨・`USD_JPY`・1回限定・manual onlyの実注文検証に近づく場合でも、最低限次を満たす。

- `symbol=USD_JPY` のみ。
- `units=100` のみ。
- `side` は明示する。
- `executionType` がある場合は、注文タイプごとに別レビューする。
- `price`、`limitPrice`、`stopPrice`、`upperBound`、`lowerBound`、time-in-force相当値は別レビューする。
- 1 `verification_run_id` につき1 intentのみ。
- `manual_confirmation_required=true`。
- READY_FOR_ORDER_REVIEWで停止する。
- 実注文前にread-only precheckを再実行する。
- 既存建玉なし。
- 未約定注文なし。
- kill switch inactive。
- retryなし。
- loopなし。
- cron / schedule / 常駐botなし。
- frontendや本番公開APIから実行できないこと。

現時点の重要な制限:

- `OrderIntent` は実注文payloadではない。
- order review modelも実注文payloadではない。
- `OrderIntent` から注文API payloadへ変換する実装は、Phase 3D-1では作らない。

## 7. Phase 3D-1で扱ってよい範囲

Phase 3D-1は、まだ注文API実装ではない。

扱ってよい候補:

- order review model。
- final checklist。
- order intentからorder reviewへの変換。
- 実注文payloadではないreview-only object。
- mocked tests。
- no-order-import guard強化。
- READY_FOR_ORDER_REVIEW後に、人間が確認する項目の整理。

扱ってはいけないもの:

- broker。
- OrderRequest。
- order API client。
- order payload builder。
- HTTP POST / PUT / DELETE。
- Private API接続。
- APIキー確認。
- `.env`確認。
- 実注文。
- 実資金検証。

## 8. Phase 3D-2以降に回す範囲

Phase 3D-2:

- broker boundary / no-network adapter 設計・mock実装。
- ただし実HTTP接続、実注文、APIキー確認はしない。
- brokerという名前を使う場合も、まずno-network / mocked boundaryに限定し、実送信関数は作らない。

Phase 3D-3:

- order payload builder実装前レビュー。
- 公式仕様、最小注文タイプ、payload field、署名対象、失敗時停止条件を再確認する。
- この段階でも、実payload builder実装に進む前に別レビューを必須にする。

Phase 3D-4:

- 実注文前最終レビュー。
- read-only precheck、既存建玉なし、未約定注文なし、kill switch、テスト、ruff、Git clean、
  secret混入なし、ユーザー明示承認を確認する。

Phase 3D-5:

- 100通貨・1回限定・手動承認つき極小実注文検証。
- これは自動売買開始ではない。
- 別タスクで、明示承認がある場合だけ検討する。

今回、これらは実行しない。

## 9. 実注文前の追加レビュー条件

実注文前には、最低限次をすべて満たす必要がある。

- 公式仕様再確認済み。
- 危険endpoint分類済み。
- read-only precheck直前成功。
- 既存建玉なし。
- 未約定注文なし。
- risk decision ALLOW。
- READY_FOR_ORDER_REVIEW到達。
- 1 `verification_run_id` につき1 intent。
- `USD_JPY`、100通貨、manual only。
- Git clean。
- backend tests pass。
- `ruff check .` pass。
- secret混入なし。
- `.env` / `.env.example` 変更なし。
- raw response、headers、signature、credentials保存なし。
- 本番公開API、frontend、cron、schedule、常駐botから実行できないこと。
- ユーザーが100通貨・1回限定の実注文検証をChatGPT上で明示承認していること。
- 実行内容、最大損失、停止条件をユーザーが理解していること。

1項目でも未確認またはNGなら、実注文には進まない。

## 10. Phase 3D-1へ進めるかの判定

判定:

```text
A: Phase 3D-1 order review model / final checklist mocked設計・実装へ進んでよい
```

理由:

- Phase 3C-3 dry-run統合はREADY_FOR_ORDER_REVIEWで停止する。
- Phase 3D前レビューは完了し、Phase 3D-0へ進んでよい判定だった。
- 公式docsで注文系、変更系、取消系、決済系、ws-auth系endpointを再確認できた。
- Phase 3D-1は注文API実装ではなく、review-only model / checklistに限定できる。
- broker、OrderRequest、注文API client、payload builder、実HTTP POSTは引き続き禁止できる。

ただし、今回のタスクではPhase 3D-1へ進まない。次候補として提案するだけで停止する。

## 11. まだ進まない範囲

今回も次へ進まない。

```text
Phase 3D-1の実行
broker実装
OrderRequest実装
注文API実装
注文payload builder
注文送信関数
注文変更API
注文取消API
決済API
speedOrder実装
ws-auth実装
Private API接続
APIキー確認
.env確認
実注文
実資金検証
自動売買
frontend変更
本番公開API追加
cron / schedule / 常駐bot
```

## 12. 結論

Phase 3D-0では、GMOコイン外国為替FXの公式API docsに基づき、注文系endpointと危険境界を再レビューした。

結論:

- Phase 3B-4で確認済みの3 endpointはread-onlyとして分離できる。
- `POST /private/v1/order`、`speedOrder`、IFD / IFDOCO、change、cancel、close、ws-auth系はHigh riskである。
- Phase 3D-1では、order review model / final checklist のmocked設計・実装までに限定する。
- Phase 3D-2でも実HTTP POST / PUT / DELETEは禁止する。
- 実注文に進むには、別フェーズでの公式仕様再確認、read-only precheck直前成功、明示承認が必須である。

Phase 3D-1追記:

- Phase 3D-1 order review model / final checklist mocked実装は完了した。
- 実装したのはreview-only objectとfinal checklist評価であり、注文payloadではない。
- broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-2 broker boundary / no-network adapter mocked設計である。

Phase 3D-2追記:

- Phase 3D-2 broker boundary / no-network adapter mocked設計は
  [PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md](PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md)
  として完了した。
- `OrderReview` / `FinalOrderChecklist` の先に置くno-network境界、`NoNetworkBrokerBoundaryResult` 候補、
  fail closed条件、no-order guard policyをdocs-onlyで整理した。
- no-network adapter実装、broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-2A no-network broker boundary adapter mocked実装である。

Phase 3D-3追記:

- Phase 3D-3 order payload builder実装前レビューは
  [PHASE3D3_ORDER_PAYLOAD_BUILDER_PRE_IMPLEMENTATION_REVIEW.md](PHASE3D3_ORDER_PAYLOAD_BUILDER_PRE_IMPLEMENTATION_REVIEW.md)
  として完了した。
- mocked builderで扱ってよい候補field、扱わない注文種別、`OrderReview` / `FinalOrderChecklist` /
  `NoNetworkBrokerBoundaryResult` との関係、fail closed条件、broker / API client / HTTP POSTとの分離を整理した。
- order payload builder実装、order payload model実装、broker、OrderRequest、注文API client、HTTP POST、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-4 mocked order payload builder実装である。
