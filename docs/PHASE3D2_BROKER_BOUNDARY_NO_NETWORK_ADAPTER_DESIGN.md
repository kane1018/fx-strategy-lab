# Phase 3D-2 broker boundary / no-network adapter mocked design

FX Strategy Lab の Phase 3D-2 として、broker boundary / no-network adapter の設計を整理する。

この文書はレビュー・設計のみであり、実装ではない。broker、OrderRequest、注文API client、
注文payload builder、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証、
自動売買、本番公開API追加には進まない。

## 1. Phase 3D-2の目的

Phase 3D-2の目的は、Phase 3D-1で実装済みの `OrderReview` / `FinalOrderChecklist` から、
将来のbroker実装領域へ進む直前の境界を定義することである。

整理する境界:

- broker実装前の安全境界。
- 注文payload builder実装前の安全境界。
- HTTP POST実装前の安全境界。
- review-only object と実注文可能なorder requestを混同しないための境界。
- mocked / no-network / real broker を段階分離するための境界。

今回の位置づけ:

- 今回は設計docsのみ。
- 今回はno-network adapterを実装しない。
- 今回はbrokerを実装しない。
- 今回はOrderRequestを作らない。
- 今回は注文API clientを作らない。
- 今回は注文payload builderを作らない。
- 今回はPrivate APIへ接続しない。
- 今回はAPIキー確認をしない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。

## 2. broker boundaryの定義

broker boundary は、`OrderReview` / `FinalOrderChecklist` の先に存在するが、
実注文可能コードへ入る前に必ず通過する安全境界である。

この境界の責務:

- `OrderIntent` / `OrderReview` / `FinalOrderChecklist` が実注文payloadではないことを固定する。
- `FinalOrderChecklist` が未通過なら次段階へ進めない。
- `READY_FOR_ORDER_REVIEW` より先の注文送信状態を作らない。
- no-network / mocked adapter と real broker adapter を分離する。
- real broker adapter へ進むには、別フェーズの公式仕様レビュー、実装レビュー、明示承認を必須にする。

この境界の非責務:

- broker送信。
- 注文payload生成。
- Private API接続。
- API署名。
- HTTP POST / PUT / DELETE。
- 注文変更、注文取消、決済。
- 実注文。

境界上の安全原則:

- `OrderReview` はreview-only objectであり、注文payloadではない。
- `FinalOrderChecklist` は人間が実注文前に確認するためのchecklistであり、注文実行トリガではない。
- no-network adapterの戻り値も実注文結果ではなく、境界確認結果である。
- `READY_FOR_ORDER_REVIEW` は「レビュー準備完了」であり、「注文送信許可」ではない。

## 3. no-network adapterの定義

no-network adapter は、将来Phase 3D-2Aで実装する可能性があるmocked adapterである。

入力候補:

- `OrderReview`
- `FinalOrderChecklist`

出力候補:

- `NoNetworkBrokerBoundaryResult`

許可される処理:

- ID相関の確認。
- `FinalOrderChecklist.final_checklist_passed` の確認。
- `USD_JPY` / 100通貨 / `live_verification` / manual only の確認。
- `READY_FOR_ORDER_REVIEW` で止まっていることの確認。
- no-network / no-payload / no-broker / no-real-order flagsの確認。
- fail closedの理由を `fail_reasons` に記録すること。

禁止される処理:

- broker import。
- OrderRequest作成。
- 注文payload作成。
- 注文API client呼び出し。
- HTTP POST / PUT / DELETE。
- Private API接続。
- APIキー確認。
- `.env`確認。
- 署名生成。
- 実注文。

no-network adapterの戻り値は「送信結果」ではない。戻り値は、no-network境界を越えていないことを
確認するためのmocked resultに限定する。

## 4. OrderReview / FinalOrderChecklist / no-network adapterの関係

許可される片方向の関係:

```text
OrderIntent
  -> OrderReview
  -> FinalOrderChecklist
  -> NoNetworkBrokerBoundaryResult
```

明示的な非接続:

```text
NoNetworkBrokerBoundaryResult -/-> OrderRequest
NoNetworkBrokerBoundaryResult -/-> broker
NoNetworkBrokerBoundaryResult -/-> POST /private/v1/order
NoNetworkBrokerBoundaryResult -/-> 注文payload
NoNetworkBrokerBoundaryResult -/-> 実注文
```

意味:

- `OrderIntent` はまだ注文ではない。
- `OrderReview` はまだ注文ではない。
- `FinalOrderChecklist` がpassedでも、まだ注文ではない。
- `NoNetworkBrokerBoundaryResult` がpassedでも、まだ注文ではない。
- 実注文へ進むには、Phase 3D-3以降の追加レビューとユーザー明示承認が必要である。

## 5. candidate data model

将来のno-network adapterで検討する候補モデル:

```text
NoNetworkBrokerBoundaryResult:
  boundary_check_id: str
  order_review_id: str
  order_intent_id: str
  verification_run_id: str
  final_checklist_id: str
  boundary_passed: bool
  final_state: str
  network_used: bool
  api_key_used: bool
  order_payload_created: bool
  broker_called: bool
  real_order_attempted: bool
  fail_reasons: tuple[str, ...]
```

必須invariant:

```text
network_used = false
api_key_used = false
order_payload_created = false
broker_called = false
real_order_attempted = false
final_state = READY_FOR_ORDER_REVIEW
```

`boundary_passed=true` の意味:

- no-network境界の安全条件を満たした。
- 実注文は試行していない。
- brokerは呼んでいない。
- payloadは作っていない。
- APIキーは使っていない。
- ネットワークは使っていない。

`boundary_passed=true` は、注文API実装や実注文の承認ではない。

## 6. fail closed条件

no-network adapterは、以下のいずれかに該当する場合にfail closedする。

- `OrderReview` がinvalid。
- `FinalOrderChecklist` がinvalid。
- `FinalOrderChecklist.final_checklist_passed=false`。
- `final_state != READY_FOR_ORDER_REVIEW`。
- `network_used=true`。
- `api_key_used=true`。
- `order_payload_created=true`。
- `broker_called=true`。
- `real_order_attempted=true`。
- `symbol != USD_JPY`。
- `units != 100`。
- `mode != live_verification`。
- `manual_confirmation_required=false`。
- `readonly_precheck_passed=false`。
- `risk_decision_status` がALLOW系ではない。
- `order_review_id` / `order_intent_id` / `verification_run_id` / `final_checklist_id` の相関が崩れている。

fail closed時の扱い:

- 実注文へ進まない。
- payloadを作らない。
- brokerを呼ばない。
- APIキーを読まない。
- `.env`を読まない。
- network I/Oを行わない。
- `fail_reasons` に安全な理由名だけを保持する。

## 7. Phase 3D-2A以降の分割案

### Phase 3D-2A: no-network broker boundary adapter mocked実装

目的:

- この文書で定義した `NoNetworkBrokerBoundaryResult` をpure mockedで実装する。

作るもの:

- no-network boundary result model。
- `OrderReview` + `FinalOrderChecklist` からboundary resultへ変換するpure function。
- mocked tests。
- no-order guard強化。

作らないもの:

- broker。
- OrderRequest。
- 注文payload。
- 注文API client。
- HTTP POST。
- Private API接続。
- 実注文。

検証方法:

- focused unit tests。
- live_verification focused tests。
- backend全体tests。
- ruff。
- 禁止語 / secret / generated artifact確認。

成功条件:

- `boundary_passed=true` でもnetwork / APIキー / payload / broker / real order flagsがすべてfalse。
- checklist failedや状態不整合はfail closed。
- no-order guardが通る。

停止条件:

- brokerや注文payloadが必要になる。
- HTTP POSTやPrivate API接続が必要になる。
- APIキーや`.env`が必要になる。

### Phase 3D-2B: no-network adapter fail closed / no-order guard hardening

目的:

- no-network adapterの異常系、禁止語、境界逸脱検出を強化する。

作るもの:

- 追加のmocked fail closed tests。
- no-order-import guardの拡張。
- endpoint literal / HTTP client / env access禁止検査。

作らないもの:

- broker。
- OrderRequest。
- 注文payload。
- order client。
- 実HTTP接続。
- 実注文。

検証方法:

- AST-based no-order guard。
- danger word grep。
- backend全体tests。
- ruff。

成功条件:

- 実行可能コードに注文送信・接続・env参照が混入しない。

停止条件:

- 実送信に必要な関数や型を作り始める必要が出た場合。

### Phase 3D-3: order payload builder実装前レビュー

目的:

- payload builderを実装する前に、公式仕様、最小注文タイプ、必須field、禁止field、
  署名対象、停止条件を再確認する。

作るもの:

- docsレビュー。
- payload builderの設計境界。

作らないもの:

- payload builder実装。
- broker。
- order client。
- HTTP POST。
- 実注文。

検証方法:

- docs-only差分確認。
- existing tests / ruff。
- secret / generated artifact確認。

成功条件:

- まだpayload builderを作らず、実装条件が明確になる。

停止条件:

- 公式仕様や実注文前承認条件に不明点が残る。

### Phase 3D-4: mocked order payload builder実装

目的:

- 実送信用ではないmocked payload候補を、公式仕様に沿って安全に組み立てられるか検証する。

作るもの:

- mocked payload model。
- validation。
- tests。

作らないもの:

- broker。
- order client。
- HTTP POST。
- 署名つきrequest。
- 実注文。

検証方法:

- mocked unit tests。
- no-network guard。
- no-order guard。
- backend全体tests。
- ruff。

成功条件:

- payload候補は作れても送信経路が存在しない。

停止条件:

- 送信関数、API client、APIキー、署名が必要になる。

### Phase 3D-5: real order API client実装前レビュー

目的:

- real order API clientを実装する前に、明示承認、接続条件、endpoint、実行方法、停止条件を再レビューする。

作るもの:

- docsレビュー。
- 実装前チェックリスト。

作らないもの:

- real order API client。
- HTTP POST。
- 実注文。

検証方法:

- docs-only差分確認。
- tests / ruff。
- secret混入確認。

成功条件:

- real order API client実装に進むかどうかの判定ができる。

停止条件:

- ユーザーの明示承認がない。
- read-only precheck直前成功がない。
- 既存建玉や未約定注文がある。

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
- FinalOrderChecklist全項目pass。
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

## 8. no-order guard policy

live verification / order review / no-network adapter領域では、以下を実行可能コードに含めない。

- broker import。
- OrderRequest。
- order payload。
- HTTP POST / PUT / DELETE。
- `/private/v1/order` literal。
- `speedOrder`。
- cancel / close / change系処理。
- `os.environ`。
- `getenv`。
- `dotenv`。
- `ENABLE_LIVE_TRADING`。
- submit / send / place / cancel / amend相当の関数名。
- 実APIレスポンスfixture。
- raw response / headers / signature保存。

docs上では禁止語として列挙してよい。ただし、実行可能コードやtest helperが実送信可能な形で持ってはいけない。

## 9. 実資金検証前の再レビュー条件

実資金検証に進むには、少なくとも以下の別フェーズが完了している必要がある。

- Phase 3D-2 broker boundary / no-network adapter design完了。
- Phase 3D-2A no-network boundary adapter mocked実装完了。
- Phase 3D-2B fail closed / no-order guard hardening完了。
- Phase 3D-3 order payload builder実装前レビュー完了。
- Phase 3D-4 mocked order payload builder実装完了。
- Phase 3D-5 real order API client実装前レビュー完了。
- 直前read-only precheck成功。
- `FinalOrderChecklist` 全項目pass。
- 既存建玉なし。
- 未約定注文なし。
- Git clean。
- backend tests pass。
- ruff pass。
- secret混入なし。
- `.env` / `.env.example` 変更なし。
- 100通貨・1回限定・manual onlyについて、ユーザーがChatGPT上で明示承認。
- 実行内容、最大損失、停止条件をユーザーが理解している。

1項目でも未確認またはNGなら、実資金検証には進まない。

## 10. まだ進まない範囲

今回も次へ進まない。

```text
Phase 3D-2Aの実行
no-network adapter実装
broker実装
OrderRequest実装
注文API client実装
注文payload builder実装
注文送信関数
注文変更API
注文取消API
決済API
speedOrder実装
ws-auth実装
HTTP POST / PUT / DELETE
POST /private/v1/order
Private API追加接続
APIキー確認
.env確認
実注文
実資金検証
自動売買
frontend変更
本番公開API追加
cron / schedule / 常駐bot
```

## 11. Phase 3D-2Aへ進めるかの判定

判定:

```text
A: Phase 3D-2A no-network broker boundary adapter mocked実装へ進んでよい
```

理由:

- Phase 3C-3でREADY_FOR_ORDER_REVIEWまでのdry-run統合が完了している。
- Phase 3D-1でreview-only `OrderReview` と `FinalOrderChecklist` が実装済みである。
- Phase 3D-2でbroker boundary / no-network adapterの設計境界を文書化した。
- Phase 3D-2Aは、実注文可能コードではなくpure mocked no-network boundary resultに限定できる。

ただし、今回のタスクではPhase 3D-2Aへ進まない。次候補として提案するだけで停止する。

## 12. 結論

Phase 3D-2では、broker実装前に必要なno-network境界をdocs-onlyで設計した。

結論:

- `OrderIntent -> OrderReview -> FinalOrderChecklist -> NoNetworkBrokerBoundaryResult` までは、
  将来のmocked no-network pathとして扱える。
- `NoNetworkBrokerBoundaryResult` は実注文結果ではなく、境界確認結果である。
- no-network resultからOrderRequest、broker、注文payload、HTTP POST、実注文へ接続してはいけない。
- Phase 3D-2Aに進む場合も、実装はpure mocked / no-networkに限定する。
- 実注文や実資金検証へ進むには、さらに複数のレビューとユーザー明示承認が必要である。

Phase 3D-2A追記:

- Phase 3D-2A no-network broker boundary adapter mocked実装は後続タスクで完了した。
- `NoNetworkBrokerBoundaryResult` と `evaluate_no_network_broker_boundary()` を
  `backend/app/live_verification/broker_boundary.py` に追加した。
- `OrderReview` + `FinalOrderChecklist` + `READY_FOR_ORDER_REVIEW` が安全条件を満たす場合だけ
  `boundary_passed=true` になる。
- checklist未pass、READY_FOR_ORDER_REVIEW以外、network/API key/payload/broker/real order flags、
  `USD_JPY` / 100通貨 / `live_verification` 逸脱、ID不整合は `boundary_passed=false` でfail closedする。
- broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-2B fail closed / no-order guard hardeningである。

Phase 3D-2B追記:

- Phase 3D-2B fail closed / no-order guard hardeningは後続タスクで完了した。
- `test_live_verification_broker_boundary.py` で、複数fail closed理由が同時に保持されること、network / API key /
  order payload / broker / real order flagsがすべてfail closedになること、ID不整合・checklist failure・state
  failureをまとめて拒否できることを確認した。
- `NoNetworkBrokerBoundaryResult` がprice、executionType、timeInForce、endpoint、request body、raw response、
  headers、signature、API key / secret / tokenなどのpayload / transport / credential fieldを持たないことを確認した。
- `test_live_verification_no_order_imports.py` を強化し、HTTP client import、GMO FX env名、注文endpoint文字列、
  注文送信状態名、payload field名を実装コード側で検出する。
- `broker_boundary.py` の境界実装はpure mocked / no-networkのまま維持した。
- broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。
- 次候補はPhase 3D-3 order payload builder実装前レビューである。
