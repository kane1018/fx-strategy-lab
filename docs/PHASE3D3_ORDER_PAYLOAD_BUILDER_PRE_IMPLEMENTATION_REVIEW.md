# Phase 3D-3: order payload builder実装前レビュー

Phase 3D-3では、Phase 3D-2Bまでで整備した `OrderReview` / `FinalOrderChecklist` /
`NoNetworkBrokerBoundaryResult` のreview-only / no-network境界を前提に、将来のmocked order payload
builderへ進む前の設計境界を整理する。

今回は **設計レビュー・docs化のみ** である。order payload builder実装、order payload model実装、
broker実装、OrderRequest実装、注文API client実装、HTTP POST、Private API追加接続、APIキー確認、
`.env`確認、実注文、実資金検証、自動売買、本番公開API追加には進まない。

## 1. Phase 3D-3の目的

目的:

- order payload builder実装前レビューを行う。
- 注文payload生成前の安全境界を整理する。
- broker / OrderRequest / 注文API client実装前のレビューを行う。
- 実HTTP POST前のレビューを行う。
- Phase 3D-4でmocked builderを実装する場合に、作ってよいものと作らないものを固定する。
- `USD_JPY`、100通貨、1回限定、manual only、no-networkの制約を再確認する。

今回の扱い:

- 今回は実装ではない。
- 今回はorder payload builder実装ではない。
- 今回はorder payload model実装ではない。
- 今回はPrivate API接続ではない。
- 今回はAPIキー確認ではない。
- 今回は`.env`確認ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. order payload builderの定義

order payload builderとは、`OrderReview` / `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` を
前提に、将来の注文API request body候補をmocked / local-onlyで組み立てる責務である。

ただし、Phase 3D-3では定義のみを行う。Phase 3D-4でmocked builderを実装する場合も、送信、broker、
HTTP POST、署名生成、APIキー参照、`.env`参照は行わない。

責務候補:

- review済みのID相関を保持する。
- `USD_JPY`、100通貨、`live_verification`、manual onlyの制約を再確認する。
- GMO FX注文API仕様で必要になり得るrequest body field名を、mocked candidateとして整理する。
- 実送信用ではなく、送信不可のcandidate objectとしてfail closed条件を検証する。

非責務:

- broker呼び出し。
- OrderRequest作成。
- 注文API client呼び出し。
- HTTP POST / PUT / DELETE。
- 署名生成。
- APIキー / secret参照。
- 実注文。
- 実資金検証。

## 3. Phase 3D-4 mocked builderで扱ってよい候補

Phase 3D-4でmocked builderを実装する場合、GMO FX注文API仕様レビューを踏まえ、
候補fieldとして扱ってよいものは次に限定する。

```text
symbol
side
size
executionType
timeInForce
settleType
```

Phase 3D-4で実装する場合も、値と運用は次に限定する。

```text
symbol=USD_JPY
size=100
mode=live_verification
manual only
1回限定
no network
no broker
no POST
```

補足:

- `side` は既存 `OrderIntentSide` の `BUY` / `SELL` を起点にする。
- `size` は既存 `units=100` から導出する候補名であり、Phase 3D-4では100以外を拒否する。
- `executionType`、`timeInForce`、`settleType` は候補field名として扱うだけで、Phase 3D-3では値を確定しない。
- Phase 3D-4で値を扱う場合も、初回はpriceを伴わない最小候補に限定し、limit / stop / OCO / IFD / IFOへ広げない。

## 4. Phase 3D-4でも扱わない候補

Phase 3D-4のmocked builderでも、次は扱わない。

```text
price
losscutPrice
limit order
stop order
OCO
IFD
IFO
settlement
close position
cancel order
change order
bulk order
speed order
WebSocket
```

理由:

- `price` / `losscutPrice` は、価格指定、ロスカット、注文有効性の追加レビューが必要である。
- limit / stop order は、成行相当の最小検証より条件が複雑であり、初回100通貨・1回限定の範囲を超える。
- OCO / IFD / IFO は複合注文であり、ID相関、取消、約定後状態のレビューが別途必要である。
- settlement / close position は既存建玉へ作用する可能性があり、初回の新規注文候補から分離する。
- cancel / change / bulk order は既存注文に作用するため、注文取消・変更レビューが先に必要である。
- speed order は実注文に直結しやすいため、初回候補から除外する。
- WebSocketはtoken管理、購読範囲、長時間接続、通知処理の追加レビューが必要である。

## 5. OrderReview / FinalOrderChecklist / NoNetworkBrokerBoundaryResultとの関係

許可される片方向の関係:

```text
OrderIntent
  -> OrderReview
  -> FinalOrderChecklist
  -> NoNetworkBrokerBoundaryResult
  -> MockedOrderPayloadCandidate
```

ただし、次へは進まない。

```text
MockedOrderPayloadCandidate -/-> broker
MockedOrderPayloadCandidate -/-> OrderRequest
MockedOrderPayloadCandidate -/-> POST /private/v1/order
MockedOrderPayloadCandidate -/-> 実注文
```

意味:

- `OrderIntent` は注文ではない。
- `OrderReview` は注文ではない。
- `FinalOrderChecklist` がpassedでも注文ではない。
- `NoNetworkBrokerBoundaryResult` がpassedでも注文ではない。
- 将来の `MockedOrderPayloadCandidate` も注文ではなく、送信不可のlocal-only候補である。

## 6. mocked payload candidateの候補データ

Phase 3D-4で検討する候補データ:

```text
mocked_payload_candidate_id
order_review_id
order_intent_id
verification_run_id
final_checklist_id
boundary_check_id
symbol
side
size
execution_type
time_in_force
settle_type
mode
manual_confirmation_required
network_used
api_key_used
broker_called
real_order_attempted
```

必須invariant:

```text
symbol=USD_JPY
size=100
mode=live_verification
manual_confirmation_required=true
network_used=false
api_key_used=false
broker_called=false
real_order_attempted=false
```

安全上の注意:

- 候補データは実注文payloadではない。
- 候補データはrequest bodyとして送信しない。
- 候補データは署名対象にしない。
- 候補データはAPIキー、secret、headers、signature、raw responseを保持しない。

## 7. fail closed条件

次の場合、mocked payload candidateを作らない方針にする。

```text
OrderReview invalid
FinalOrderChecklist failed
NoNetworkBrokerBoundaryResult failed
network_used=true
api_key_used=true
broker_called=true
real_order_attempted=true
symbol != USD_JPY
size != 100
manual_confirmation_required=false
mode != live_verification
verification_run_id不整合
```

追加で停止する条件:

- `order_review_id` / `order_intent_id` / `final_checklist_id` / `boundary_check_id` の相関が崩れている。
- `NoNetworkBrokerBoundaryResult.order_payload_created=true` が入力された。
- `READY_FOR_ORDER_REVIEW` 以外の状態から候補生成しようとした。
- `FinalOrderChecklist` の `broker_not_implemented` または `order_api_not_implemented` がfalseである。
- raw response、headers、signature、credentialsの保存・表示フラグがある。

fail closed時の扱い:

- brokerを呼ばない。
- OrderRequestを作らない。
- HTTP POSTしない。
- APIキー / secret / `.env` を読まない。
- 実注文へ進まない。
- fail reasonは安全なreason名だけに限定し、実データやcredential値を含めない。

## 8. 注文payload builderとbroker / API clientの分離

payload builder:

- request body候補をmocked / local-onlyで組み立てるだけ。
- 送信責務を持たない。
- API署名責務を持たない。
- APIキーやsecretを参照しない。
- HTTP method、URL、headers、raw responseを保持しない。

broker:

- payloadを送信する責務を持ち得る将来領域。
- まだ未実装。
- Phase 3D-4でも実装しない。

order API client:

- HTTP POSTを行う責務を持ち得る将来領域。
- まだ未実装。
- Phase 3D-4でも実装しない。

Phase 3D-4でも、broker / API client / HTTP POSTへ進まない。

## 9. Phase 3D-4以降の分割案

### Phase 3D-4: mocked order payload builder実装

目的:

- 実送信用ではないmocked payload候補を、review-only / no-network境界の先に作れるか検証する。

作るもの:

- `MockedOrderPayloadCandidate` 相当のlocal-only model。
- `OrderReview` / `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` からcandidateを作るpure function。
- fail closed validation。
- mocked tests。

作らないもの:

- broker。
- OrderRequest。
- 注文API client。
- HTTP POST。
- 署名つきrequest。
- APIキー / secret参照。
- 実注文。

検証方法:

- focused mocked tests。
- no-order guard。
- payload field guard。
- backend全体tests。
- `ruff check .`。
- 危険語 / secret / generated artifact確認。

成功条件:

- mocked payload候補は作れても、送信経路が存在しない。
- `USD_JPY`、100通貨、manual only、1回限定、no-networkが維持される。
- broker / API client / HTTP POST / APIキー参照がない。

停止条件:

- 送信関数、API client、署名、APIキー、`.env`が必要になる。
- limit / stop / OCO / IFD / IFO / close / cancel / changeを扱う必要が出る。

### Phase 3D-4B: mocked payload builder fail closed / no-network guard hardening

目的:

- mocked payload builderの異常系とno-network境界を強化する。

作るもの:

- 追加のfail closed tests。
- no-order / no-network / no-secret guard拡張。
- payload候補がtransport情報やcredentialを持たないことの検証。

作らないもの:

- broker。
- OrderRequest。
- 注文API client。
- HTTP POST。
- 実注文。

検証方法:

- AST-based guard。
- danger word grep。
- backend全体tests。
- ruff。

成功条件:

- 実行可能コードに送信、接続、env参照、credential保持が混入しない。

停止条件:

- 実送信に必要な関数や型を作り始める必要が出た場合。

### Phase 3D-5: real order API client実装前レビュー

目的:

- real order API clientを実装する前に、明示承認、endpoint、接続条件、実行方法、停止条件を再レビューする。

作るもの:

- docsレビュー。
- 実装前チェックリスト。
- 実HTTP接続前の承認条件。

作らないもの:

- real order API client。
- HTTP POST。
- broker。
- 実注文。

検証方法:

- docs-only差分確認。
- tests / ruff。
- secret混入確認。
- Git clean確認。

成功条件:

- real order API client実装に進むかどうかの判定ができる。

停止条件:

- ユーザー明示承認がない。
- read-only precheck直前成功がない。
- 既存建玉や未約定注文がある。
- 実行内容、最大損失、停止条件が未確認。

### Phase 3D-6: 100通貨・1回限定・手動承認つき実注文最終レビュー

目的:

- 100通貨・1回限定・manual onlyの極小実注文検証に進めるかを最終確認する。

作るもの:

- 最終レビューdocs。
- 実行前チェックリスト。

作らないもの:

- 自動売買。
- loop注文。
- retry注文。
- cron / schedule / 常駐bot。
- frontend実行画面。
- 本番公開API。

検証方法:

- read-only precheck直前成功。
- `FinalOrderChecklist` 全項目pass。
- Git clean。
- tests / ruff pass。
- secret混入なし。
- ユーザー明示承認。

成功条件:

- 実注文を行う場合でも、100通貨・1回限定・manual onlyに固定される。

停止条件:

- 明示承認がない。
- 既存建玉あり。
- 未約定注文あり。
- kill switch active。
- 実行内容、最大損失、停止条件が未確認。

## 10. no-order guard方針

Phase 3D-4でも、次を禁止する。

- broker import禁止。
- OrderRequest禁止。
- HTTP POST禁止。
- APIキー参照禁止。
- `.env`参照禁止。
- 実注文endpoint実行禁止。
- raw response保存禁止。
- headers保存禁止。
- signature保存禁止。
- `requests` / `httpx` / `aiohttp` / `urllib` / `urllib3` の注文送信用import禁止。
- `submit` / `send` / `place` / `cancel` / `amend` / `close` 相当の実行関数名禁止。
- `ORDER_SENT` / `BROKER_SUBMIT` / `PRIVATE_ORDER_API` / `LIVE_ORDER_PLACED` の状態名禁止。

docs上では禁止語として列挙してよい。ただし、実行可能コードやtest helperが実送信可能な形で持ってはいけない。

## 11. 今回まだ進まない範囲

今回のPhase 3D-3では、次へ進まない。

```text
order payload builder実装
order payload model実装
broker実装
OrderRequest実装
注文API client実装
HTTP POST
POST /private/v1/order
実注文
実資金検証
自動売買
frontend変更
本番公開API追加
Private API追加接続
APIキー確認
.env確認
raw response保存
headers保存
signature保存
```

## 12. Phase 3D-4へ進めるかの判定

判定:

```text
A: Phase 3D-4 mocked order payload builder実装へ進んでよい
```

理由:

- Phase 3D-1でreview-only `OrderReview` と `FinalOrderChecklist` が実装済みである。
- Phase 3D-2Aでpure mocked / no-networkの `NoNetworkBrokerBoundaryResult` が実装済みである。
- Phase 3D-2Bでfail closed / no-order guard hardeningが完了済みである。
- Phase 3D-3で、mocked builderが扱ってよい候補、扱わない候補、broker / API client / HTTP POSTとの分離を整理した。
- Phase 3D-4は、実注文可能コードではなく、送信不可のmocked / local-only payload candidateに限定できる。

ただし、今回のタスクではPhase 3D-4へ進まない。次候補として提案するだけで停止する。

## 13. 結論

Phase 3D-3では、order payload builder実装前の安全境界をdocs-onlyで整理した。

結論:

- mocked order payload builderは、送信用payload builderではなく、local-onlyの候補生成に限定する。
- Phase 3D-4で扱う場合も、`symbol` / `side` / `size` / `executionType` / `timeInForce` / `settleType`
  の候補fieldに限定し、`USD_JPY`、100通貨、manual only、1回限定、no-networkを維持する。
- price、losscutPrice、limit / stop、OCO / IFD / IFO、settlement、close / cancel / change、speed order、
  WebSocketは扱わない。
- `MockedOrderPayloadCandidate` からbroker、OrderRequest、`POST /private/v1/order`、実注文へ接続してはいけない。
- 実注文や実資金検証へ進むには、さらにPhase 3D-5以降のレビューとユーザー明示承認が必要である。

Phase 3D-4追記:

- Phase 3D-4 mocked order payload builder実装は後続タスクで完了した。
- `backend/app/live_verification/payload_candidate.py` に `MockedOrderPayloadCandidate` と
  `build_mocked_order_payload_candidate()` を追加した。
- candidateは `OrderReview` / `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` がpassしている場合だけ生成される。
- `symbol=USD_JPY`、`size=100`、`mode=live_verification`、`manual_confirmation_required=true`、
  network / API key / broker / real order flags falseを必須にした。
- endpoint、method、URL、request body、raw response、headers、signature、credentialは保持しない。
- broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-4B mocked payload builder fail closed / no-network guard hardeningである。

Phase 3D-4B追記:

- Phase 3D-4B mocked payload candidate no-send / fail-closed hardeningは後続タスクで完了した。
- `MockedOrderPayloadCandidate` のfail closedテスト、許可値固定テスト、非送信・非payload本体テストを強化した。
- no-order-import guardを強化し、実装コードにHTTP client import、env参照、Private order endpoint文字列、
  HTTP method / credential文字列、注文送信系関数名が混入しないことを確認する。
- `payload_candidate.py` は送信不能なlocal-only candidateのままで、endpoint、method、URL、request body、
  raw response、headers、signature、credentialを保持しない。
- broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-5 real order API client実装前レビューである。
