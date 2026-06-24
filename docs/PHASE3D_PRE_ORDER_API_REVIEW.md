# Phase 3D前: broker / order API実装前レビュー

Phase 3D前レビューでは、Phase 3C-1 / 3C-2 / 3C-3 で構築した Live Verification mocked / dry-run core を前提に、
broker / order API 実装へ進む前の安全条件、禁止境界、分割計画、レビュー条件、明示承認条件を固定する。

今回は **レビュー・docs化のみ** である。broker実装、OrderRequest実装、注文API client実装、
注文payload builder実装、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証、
自動売買、本番公開API追加には進まない。

## 1. Phase 3D前レビューの目的

目的:

- broker / order API実装前の安全レビューを行う。
- Phase 3C-3 dry-run完了後の現在地を整理する。
- 実注文可能なコードを作る前の境界を固定する。
- 100通貨、`USD_JPY`、1回限定、manual onlyを再確認する。
- 実注文前の明示承認条件を整理する。
- broker / order API実装を細かいレビュー段階へ分割する。
- 本番公開APIやfrontendに実注文導線を出さない境界を維持する。

今回の扱い:

- 今回は実装ではない。
- 今回は実注文ではない。
- 今回は実資金検証ではない。
- 今回はPrivate API追加接続ではない。
- 今回はAPIキー確認ではない。

## 2. 現在の安全到達点

Phase 3C-3までに確認済みの安全到達点:

- READY_FOR_ORDER_REVIEWまでのdry-run flow確認済み。
- read-only precheck、risk decision、ID correlation、order intent、state transitionを統合済み。
- precheck failedなら `FAILED`。
- ALLOW系以外なら `FAILED`。
- ID不整合なら `FAILED`。
- 同一 `verification_run_id` 内の2件目intent拒否。
- `USD_JPY`以外は拒否。
- 100通貨以外は拒否。
- manual confirmationなしは拒否。
- 既存建玉あり相当の入力は拒否。
- 未約定注文あり相当の入力は拒否。
- raw response / headers / credentials保存・表示フラグありは拒否。
- READY_FOR_ORDER_REVIEWで停止。

未実装・未実施:

- brokerなし。
- OrderRequestなし。
- 注文APIなし。
- 注文payload builderなし。
- 実注文なし。
- 実資金検証なし。
- Private API追加接続なし。
- APIキー確認なし。
- `.env`確認なし。
- frontend実行画面なし。
- 本番公開API追加なし。

## 3. broker / order API実装へ進む前の必須条件

broker / order API関連の実装へ進む前に、最低限すべて満たす必要がある。

検証条件:

- backend全体tests pass。
- `ruff check .` pass。
- live_verification focused tests pass。
- no-order-import guard pass。
- private_readonly tests pass。
- forbidden endpoint guard pass。
- Git working tree clean。
- Git staged diffにsecret混入なし。
- `.env` / `.env.example` 変更なし。
- `shadow_exports/` / 実データ commitなし。
- raw response / headers / signature / credentials保存なし。

レビュー条件:

- Phase 3D前レビューdocs完了。
- 実装前の明示承認あり。
- 実注文前の別途明示承認あり。
- 実装対象フェーズの目的、作るもの、作らないもの、成功条件、停止条件が明文化されている。
- 本番公開API、frontend、`backend/app/main_readonly.py` を変更しない方針が維持されている。

## 4. まだ実装してはいけない範囲

Phase 3D前レビュー時点で、まだ次を実装してはいけない。

```text
broker
OrderRequest
注文API client
注文payload builder
注文変更API
注文取消API
決済API
実注文
実資金検証
自動売買
frontend実行画面
本番公開API
cron / schedule / 常駐bot
DB本番化
認証追加
retry注文
loop注文
```

加えて、次も行わない。

- Private API追加接続。
- APIキー存在確認。
- APIキー値・secret値の要求、表示、保存。
- `.env` 表示、変更、commit。
- 実APIレスポンスfixture化。
- raw response、response headers、signature保存。

## 5. 100通貨・USD_JPY・1回限定・manual onlyの維持方針

初回の実注文に近づく場合も、次の固定条件を維持する。

- symbolは `USD_JPY` のみ。
- unitsは100のみ。
- 1 `verification_run_id` につき1 intentまで。
- `manual_confirmation_required=true`。
- READY_FOR_ORDER_REVIEWで停止。
- 実注文前に再度read-only precheckを行う。
- 既存建玉ありなら停止。
- 未約定注文ありなら停止。
- retry注文を行わない。
- loop注文を行わない。
- schedule / cron / botから実行しない。
- 本番公開APIやfrontendから実行しない。

運用上の含意:

- `order_intent` は実注文payloadではない。
- `order_intent` から `OrderRequest` への変換は、別フェーズの明示承認なしに作らない。
- 実注文前には、read-only precheckとユーザー明示承認を同じ実行直前文脈で再確認する。

## 6. 実装フェーズ分割案

Phase 3Dは、少なくとも次の小フェーズへ分割する。

```text
Phase 3D-0:
GMO FX order API公式仕様・危険endpoint再レビュー

Phase 3D-1:
order review model / final checklist のmocked設計・実装

Phase 3D-2:
broker boundary / no-network adapter 設計・mock実装

Phase 3D-3:
order payload builder 実装前レビュー

Phase 3D-4:
実注文前最終レビュー

Phase 3D-5:
100通貨・1回限定・手動承認つき極小実注文検証
```

今回これらは実装しない。

### Phase 3D-0: GMO FX order API公式仕様・危険endpoint再レビュー

目的:

- 注文系endpointの公式仕様を再確認する。
- order / cancel / change / close / speedOrder / ws-auth の危険性を整理する。
- read-only endpointとorder可能endpointの境界を再確認する。
- まだ実装しない。
- まだ接続しない。
- まだAPIキー確認しない。

作るもの:

- `docs/PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md`。
- 危険endpoint一覧。
- 実装前レビュー観点。

作らないもの:

- broker。
- OrderRequest。
- 注文API client。
- 注文payload builder。
- Private API接続。
- APIキー確認。
- 実注文。

検証方法:

- docs差分確認。
- 危険語分類。
- secret混入確認。
- tests / ruffは必要範囲で実行。

成功条件:

- 注文系endpointと禁止操作が明文化されている。
- 次フェーズへ進む前の停止条件が明文化されている。
- 実装や接続が一切追加されていない。

停止条件:

- broker / OrderRequest / 注文API実装が混入した。
- Private API接続やAPIキー確認に進んだ。
- `.env` やsecretへ触れた。

### Phase 3D-1: order review model / final checklist のmocked設計・実装

目的:

- 実注文payloadではない、最終レビュー用のmodelを設計する。
- READY_FOR_ORDER_REVIEW後に、人間が確認する項目を固定する。

作るもの:

- mocked order review model。
- final checklist。
- 100通貨、`USD_JPY`、1回限定、manual onlyのvalidation。

作らないもの:

- OrderRequest。
- 注文payload。
- broker adapter。
- 注文API client。
- 実注文可能な変換関数。

検証方法:

- mocked unit tests。
- no-order-import guard。
- forbidden word guard。

成功条件:

- final checklistが全項目OKの場合だけ「レビュー可能」になる。
- NG項目があればfail closed。
- 実注文payloadや注文IDを保持しない。

停止条件:

- order review modelが実注文payloadとして使える形になった。
- broker / order APIへ渡す導線が入った。

### Phase 3D-2: broker boundary / no-network adapter 設計・mock実装

目的:

- broker境界を実装前にmock / no-networkで定義する。
- 実注文可能なadapterではなく、境界の責務と禁止事項をテストで固定する。

作るもの:

- no-network adapter。
- dry-run専用の境界test。
- 「実送信不可」を保証するguard。

作らないもの:

- 実broker。
- 注文API client。
- network call。
- APIキー参照。
- 実注文送信関数。

検証方法:

- no-network tests。
- AST import guard。
- forbidden method name guard。

成功条件:

- adapterはnetwork I/Oを持たない。
- 実注文送信関数が存在しない。
- `submit` / `send` / `place` / `cancel` / `amend` 相当が実行可能導線として存在しない。

停止条件:

- network I/Oが入った。
- broker importが実送信可能な形で入った。
- APIキーや`.env`へ触れた。

### Phase 3D-3: order payload builder 実装前レビュー

目的:

- order payload builderを作る前に、payload化のリスクを別レビューで整理する。
- 注文可能なコードを作るかどうかを再判定する。

作るもの:

- docsレビュー。
- payload field候補と禁止field一覧。
- 実装する場合の承認条件。

作らないもの:

- payload builder本体。
- OrderRequest。
- 注文API client。
- 実注文。

検証方法:

- docs-only diff確認。
- secret混入確認。
- forbidden endpoint / forbidden action確認。

成功条件:

- payload builder実装の前提条件、停止条件、承認条件が明文化されている。
- まだ実装していない。

停止条件:

- payload builderやOrderRequestが作られた。
- 注文API endpointへ接続可能なコードが入った。

### Phase 3D-4: 実注文前最終レビュー

目的:

- 実注文可能コードが存在する場合でも、実行前に最終レビューで停止する。
- 100通貨・1回限定・manual onlyの実行条件を再確認する。

作るもの:

- 実注文前最終チェックリスト。
- 実行手順案。
- 停止条件。

作らないもの:

- 実注文実行。
- 自動売買。
- retry / loop。
- 本番公開API。
- frontend実行画面。

検証方法:

- backend tests。
- ruff。
- no-order / no-secret checks。
- Git clean確認。
- 直前read-only precheck結果確認。

成功条件:

- 実行条件がすべてOK。
- ユーザーが最大損失、停止条件、実行内容を理解している。
- 実行前に別途明示承認がある。

停止条件:

- 1項目でも未確認またはNG。
- 既存建玉あり。
- 未約定注文あり。
- Git差分やsecret混入あり。

### Phase 3D-5: 100通貨・1回限定・手動承認つき極小実注文検証

目的:

- 100通貨、`USD_JPY`、1回限定、manual onlyで実注文疎通を確認する。
- 収益性評価ではなく、発注・確認・停止手順の検証に限定する。

作るもの:

- 明示承認済みの手動実行手順。
- 実行前後チェックリスト。
- sanitized summary。

作らないもの:

- 自動売買。
- 複数回注文。
- retry注文。
- loop注文。
- 数量拡大。
- frontend実行画面。
- 本番公開API。

検証方法:

- 実行直前read-only precheck。
- 実行後read-only確認。
- raw response / headers / credentials保存なし確認。
- Git / secret / 実データ混入確認。

成功条件:

- 1回だけ実行して停止。
- 追加注文なし。
- retryなし。
- loopなし。
- sanitized summaryのみ。

停止条件:

- 明示承認がない。
- read-only precheckが失敗。
- 既存建玉または未約定注文あり。
- ユーザーがリスクを理解していない。
- secretや実データ混入。

## 7. Phase 3D-0の推奨内容

次に進むなら、まず **Phase 3D-0: GMO FX order API公式仕様・危険endpoint再レビュー** が自然である。

目的:

- 注文系endpointの公式仕様を再確認する。
- `order` / `cancel` / `change` / `close` / `speedOrder` / `ws-auth` の危険性を整理する。
- read-onlyからorder可能領域へ境界が移る点を明文化する。
- まだ実装しない。
- まだ接続しない。
- まだAPIキー確認しない。

成果物:

```text
docs/PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md
```

禁止:

- broker実装。
- OrderRequest実装。
- 注文API実装。
- 注文payload builder。
- Private API接続。
- APIキー確認。
- `.env`確認。
- 実注文。

## 8. 実注文前の明示承認条件

実注文前には、最低限次をすべて満たす必要がある。

- ChatGPT上でユーザーが明示的に100通貨・1回限定の実注文検証を承認すること。
- 実行内容、最大損失、停止条件をユーザーが理解していること。
- 直前read-only precheckが成功していること。
- 既存建玉なし。
- 未約定注文なし。
- `account/assets` 確認済み。
- `openPositions` 確認済み。
- `activeOrders` 確認済み。
- kill switch inactive。
- backend tests pass。
- ruff pass。
- live_verification focused tests pass。
- no-order / no-secret checks pass。
- Git clean。
- secret混入なし。
- `.env` / `.env.example` 変更なし。
- raw response / headers / signature保存なし。
- 実データ commitなし。
- 本番公開APIやfrontendから実行できないこと。

1項目でも未確認またはNGなら、実注文には進まない。

## 9. Phase 3Dへ進めるかの判定

判定:

```text
A: Phase 3D-0 公式仕様・危険endpoint再レビューへ進んでよい
```

理由:

- Phase 3C-3でREADY_FOR_ORDER_REVIEWまでのdry-run統合が完了している。
- precheck failed、ALLOW系以外、ID不整合、同一run内2件目intentがfail closedする。
- broker、OrderRequest、注文API、実注文、実資金検証はまだ未実装である。
- 次に進む場合も、いきなり実装ではなく公式仕様・危険endpoint再レビューから始めるのが安全である。

ただし、今回のタスクではPhase 3D-0へ進まない。次候補として提案するだけで停止する。

## 10. まだ進まない範囲

今回も次へ進まない。

```text
Phase 3D-0の実行
broker実装
OrderRequest実装
注文API実装
注文payload builder
注文変更API
注文取消API
決済API
実注文
実資金検証
自動売買
frontend変更
本番公開API追加
Private API追加接続
APIキー確認
.env確認
```

## 11. 結論

Phase 3D前レビューでは、broker / order API実装へ進む前の安全境界を整理した。

結論:

- Phase 3C-3までのmocked / dry-run coreは、READY_FOR_ORDER_REVIEWまで到達できる。
- READY_FOR_ORDER_REVIEWは実注文可能状態ではなく、実注文前レビュー可能状態である。
- broker / OrderRequest / 注文API / 注文payload builderは、まだ作らない。
- Phase 3Dへ進む場合も、まずPhase 3D-0公式仕様・危険endpoint再レビューから始める。
- Phase 3D-5相当の実注文検証には、別途、100通貨・1回限定・manual onlyの明示承認が必須である。

追記:

- Phase 3D-0公式仕様・危険endpoint再レビューは
  [PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md](PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md) として完了した。
- Phase 3D-0の判定は
  **A: Phase 3D-1 order review model / final checklist mocked設計・実装へ進んでよい**。
- ただし、Phase 3D-0でもbroker、OrderRequest、注文API client、注文payload builder、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- Phase 3D-1ではreview-only `OrderReview` と `FinalOrderChecklist` をmocked実装した。
  これらは実注文payloadではなく、broker、OrderRequest、注文API client、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- Phase 3D-2では
  [PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md](PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md)
  を作成し、broker boundary / no-network adapterの責務、`NoNetworkBrokerBoundaryResult` 候補、
  fail closed条件、no-order guard policy、Phase 3D-2A以降の分割案をdocs-onlyで整理した。
  no-network adapter実装、broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- Phase 3D-2Aでは `NoNetworkBrokerBoundaryResult` と `evaluate_no_network_broker_boundary()` を
  pure mocked / no-networkで実装した。これは境界確認結果であり、注文結果ではない。broker、OrderRequest、
  注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。
- Phase 3D-2Bでは fail closed / no-order guard hardening を完了し、複数失敗理由の蓄積、
  no-network flag横断、payload / transport / credential field非保持、HTTP client import / GMO FX env名 /
  注文endpoint文字列 / 注文送信状態名 / payload field名の実装コード混入検出をテストで強化した。
  broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。
