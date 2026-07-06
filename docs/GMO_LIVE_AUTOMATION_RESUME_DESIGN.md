# GMO FX 実資金自動売買 再開設計（ドラフト・未実装）

本書は Step 6G-PC-OX-R 系インシデント（`live_order_once.py` 等の実POST可能経路と、
Step 6G "controlled/safe" simulation 系の混在）を踏まえ、GMO FX 実資金自動売買を
**将来安全に再開するための設計**をまとめたものである。本書自体はコード実装を含まない。
数値（リスク上限の具体的な金額・数量）は本書では決め切らず、設定項目と判定構造のみを固める。

関連: [`../AGENTS.md`](../AGENTS.md)、[`CODEX_HANDOFF.md`](CODEX_HANDOFF.md)（インシデント記録）、
`backend/app/security/real_broker_post_hard_guard.py`（既存hard guard。当初
`app/live_verification/`にあったが、production broker/service経路との分離のため
`app/security/`へ移設済み）。

## 現在のステータス（このStepでの反映）

- settlement_side_official_docs_semantics_confirmed: `false`
- settlement_side_rule_status: `NEEDS_OFFICIAL_DOCS_REVIEW`
- live settlement: `blocked`（docs確認まで継続）
- max_consecutive_losses_selected: `2`
- max_consecutive_losses_decision: `MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2`
- service_wiring_policy: `DESIGN_FIRST_NO_CODE`（no-POST hook実配線済み）
- closeOrder docs review result: `SIDE_DOCS_STILL_UNCONFIRMED`
- closeOrder endpoint: confirmed（`/private/v1/closeOrder`）
- settlement_side_confirmation: `pending`（公式docsだけでは決済方向を確定不能）

## 1. GMO live自動売買再開の必須条件

以下がすべて満たされるまで、GMO実資金自動売買は有効化しない。

1. `GmoFxBroker.market_order()` / official settlement dedicated path が実装・テスト・レビュー済みで、
   `OandaBroker`と同じく `risk_service` / `AutomationRunner` / `bot_service` 経由に統合されている。
2. `backend/app/live_verification/`（Step 6G controlled/simulation系、および `live_order_once.py`）は
   自動売買経路から**一切import/呼び出しされない**ことがテストで固定されている。
3. `real_broker_post_hard_guard.py` の default-deny は維持され、統合後の経路でも実送信直前で
   引き続き呼ばれる（統合＝ガード撤去ではない）。
4. allow bridge（複数booleanから許可を自動算出する再利用可能な判定器）は作らない。
5. `GMO_FX_ORDER_ENABLED` 相当のenable設定は既定OFFで、プロセス再起動後も自動でOFFに戻る。
6. 十分なpaper trade実績（`paper_trade_gmo` / `performance_report`）が存在する。
7. 運営者による明示的な書面上の承認（sign-off）が記録されている。
8. Kill switch・settlement照合ロジックが実装され、synthetic fixtureで全異常系がテスト済み。
9. repo clean、HEAD==origin/main、全テスト green、ruff clean。
10. `service_wiring_policy` が `DESIGN_FIRST_NO_CODE`（`bot_service`/`automation_service`は
    no-POST hook 配線済み、実POST配線未実装）。

## 2. GmoFxBrokerの統合位置

- `backend/app/brokers/gmo_fx_broker.py` の `market_order()`（現状は無条件raise）を実装し、
  `OandaBroker`と同一の `Broker` インターフェースを満たす形にする。
- 署名・認証は `app/private_api/auth.py` の `build_auth_headers`（既存の実装・監査済み）を
  再利用し、`live_order_once.py`内の独自署名ロジックは使わない。
- 決済は専用の official settlement dedicated route を呼ぶ専用メソッド（例:
  `GmoFxBroker.close_position()`）とし、generic opposite order（両建てクローズ）は使わない。
- **アーキテクチャ上の硬い境界**: `gmo_fx_broker.py` は `app.live_verification.*` を
  import しない。これをsource-scanテストで固定する（既存の
  `test_live_verification_real_post_capability_isolation.py` と同じパターン）。
- 統合後も、`market_order()` / `close_position()` の実送信直前で
  `real_broker_post_hard_guard.assert_real_broker_post_allowed(allow=...)` を呼ぶ。
  `allow` は `bot_service`/`AutomationRunner` 側の既存enableチェック（`GMO_FX_ORDER_ENABLED`
  ＋`admin_live_enabled`＋confirmation phrase一致等、OANDAのlive-mode gateと同型）から
  渡される値のみとし、専用の「許可判定器（allow bridge）」は作らない。

## 3. risk_serviceとの接続設計

- `evaluate_order_risk()` の構造はそのまま再利用する。
- 現行の「`mode=="live"`なら無条件で`実資金ブローカーアダプターが未実装`を追加」という
  ブロックは、`GmoFxBroker`実装完了後に、具体的なGMO live gate群（
  `enable_live_trading`、`admin_live_enabled`、confirmation phrase一致、
  `api_connection_ok`、risk config妥当性、**加えてGMO固有の**
  paper実績フラグ・kill switch armedフラグ・settlement route確認済みフラグ）
  へ置き換える。「未実装」という文言のまま実装済みにはしない。
- `bot_service.start_bot()` は、既存の demo/practice以外を`risk_stopped`にする
  二重ガードと同型で、GMO live専用の起動前チェック（下記kill switch条件）を
  start時に一括評価する。

## 4. kill switch条件

| 条件 | 挙動 |
|---|---|
| 起動時 | 必ずOFF（自動復帰しない。プロセス再起動後も同様） |
| manual stop | 最優先。毎サイクルの最初にチェックし、trueなら即停止 |
| stale price | 既存 `_assert_fresh_price` と同型で停止 |
| risk_service rejected | GMO live経路では即bot停止（demo/paperのような「このシグナルだけskip」ではなく停止） |
| settlement rejected | 停止。retry/repostしない |
| settlement unknown/timeout | fail-closedで停止（成功扱いにしない） |
| active/pending order conflict | entry試行前に検出したら停止（自動キャンセルしない） |
| multiple positions検出 | 本来起きないはずの異常として即停止 |
| 連敗上限到達 | 停止 |
| 日次損失上限到達 | 停止 |
| 最大entry回数(`max_entries_per_day`)到達 | 停止 |
| kill switch作動中 | entry・settlementいずれの新規POSTも行わない（単一の`status`フラグで一元管理） |

## 5. 最小RiskConfig案（項目のみ、数値は保留）

既存`RiskConfig`（`max_daily_loss` / `max_loss_per_trade` / `max_positions` /
`max_units` / `max_consecutive_losses` / `max_spread_pips` / `avoid_news_minutes`）に加え、
GMO live専用として以下のフィールドを新設する。数値は次の議論で決める。

- `max_positions`: 1（構造上も1に固定）
- `max_entries_per_day`: 1から開始（候補）
- `max_settlements_per_position`: 1（同一ポジションへの決済試行は1回のみ）
- `max_consecutive_losses`: `MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2`（2）で先行確定
- `order_size_safe_label`: GMOの最小許容単位に固定。引き上げには設定ファイル変更＋
  再デプロイ＋レビューを必須とし、実行時にコードから変更不可にする。
- `official_settlement_route_required`: True（固定・configで変更不可）
- `generic_close_allowed`: False（固定・configで変更不可。テストで固定）

## 6. settlement照合設計

1. official settlement dedicated routeのみを使う（generic opposite order禁止、テストで固定）。
2. settlement POSTがsanitized acceptedを返しても、その場では「決済完了」扱いにしない。
3. 続けてread-onlyのsafe confirmation（openPositions count）を取得し、
   `NO_POSITION`/`count=0`を確認できた時点で初めて「決済完了」とする
   （OANDAの`close_unconfirmed`と同じ思想）。
4. rejected/unknown/timeoutの場合は停止し、retry/repostしない。運営者の手動対応に委ねる。
5. `max_settlements_per_position=1`をポジション単位の状態（DB）でも構造的に強制する
   （risk_serviceのチェックだけに依存しない）。

## 7. Level 5 full auto completed=true の条件

以下の**すべて**が、1つのfresh cycle内でmanual interventionなしに成立した場合のみtrue。

1. entry POSTがちょうど1回実行され、結果がaccepted(sanitized)
2. entry後のread-only確認で`ONE_POSITION_OPEN`/`count=1`を確認
3. official settlement POSTがちょうど1回実行され、結果がaccepted(sanitized)
4. settlement後のread-only確認で`NO_POSITION`/`count=0`を確認
5. retry/repost/second POSTが一度も発生していない
6. manual stop・manual close・manual overrideなどの人手介入が一切なかった
7. kill switchが一度も作動していない

上記のいずれかが未達・不明・timeoutの場合は`Level_5_full_auto_cycle_completed=false`とする
（これはCODEX_HANDOFF.mdの過去記録で既に踏襲されているルールと同じ）。

## 8. no-POSTで先に実装すべきStep一覧

1. 本設計書のリスク上限数値・段階的ロールアウト期間の確定（別途議論）
2. ✅ **完了**: `gmo_fx_broker.py`が`app.live_verification.*`を一切importしないことを固定する
   source-scan/isolationテスト追加（`test_gmo_fx_broker_live_verification_isolation.py`）。
   同Stepで`real_broker_post_hard_guard.py`を`app.security`へ移設済み。
3. ✅ **完了**: `app/private_api/order_builders.py`に、entry注文用・official settlement用の
   pure body/signing-ready request plan builderを追加（実送信なし、`auth.py`は呼ばない設計、
   fake fixtureのみでテスト・`test_private_api_order_builders.py`）。settlementは
   `/private/v1/closeOrder`専用route固定、size-based以外（position-specific）は
   構造上サポートせず明示的に拒否する。
4. ✅ **完了（no-POSTスケルトンのみ）**: `GmoFxBroker.market_order()`をentry専用skeletonとして
   実装。上記builderで作った`GmoFxPrivateRequestPlan`を使い、`real_broker_post_hard_guard`を
   実送信直前に必ず呼ぶ。production側で`allow_real_broker_post`をTrueにする配線は一切なく、
   実HTTP transportも未実装のため常に例外で停止する（`test_gmo_fx_broker_market_order_no_post.py`）。
   settlement・risk_service接続・kill switch・paper実績チェックはこのStepでは未実装。
5. ✅ **完了（no-POSTスケルトンのみ）**: `GmoFxBroker.official_settlement_order()`を
   size-based専用skeletonとして実装。`market_order()`とは別メソッドで、generic opposite orderは
   使わず、entry builderではなく`build_gmo_fx_official_settlement_request_plan`のみを使う。
   settlement side（決済方向）は`entry_side_safe_label`（`ENTRY_BUY`/`ENTRY_SELL`のみ）から
   `derive_settlement_side_from_entry_side_safe_label`で機械的に導出し、side provenanceが
   ready でない限りrequest planを作らずに停止する。導出ルール（entryの反対sideで決済）自体は
   GMO公式closeOrder docsとの整合を人手でまだ確認していないため、
   `settlement_side_official_docs_semantics_confirmed=false`のまま。実送信直前で
   `real_broker_post_hard_guard`を必ず呼び、production側で許可配線はなく、実HTTP transportも
   未実装のため常に例外で停止する（`test_gmo_fx_broker_official_settlement_no_post.py`）。
   position-specific settlement・risk_service接続・kill switch・paper実績チェックは未実装。
6. ✅ **完了（構造のみ、risk_service未接続）**: `app/services/gmo_live_safety_policy.py`に
   `GmoLiveRiskConfig`（`max_positions`/`max_entries_per_day`/`max_settlements_per_position`等、
   `generic_close_allowed`/`opposite_order_as_close_allowed`/`position_specific_actual_path_enabled`
   はFalse固定で構築時に検証）、kill switch（`GmoLiveKillSwitchState`/
   `evaluate_gmo_live_kill_switch`、15種のtriggerでentry/settlementを止め、retry/repost/generic
   closeは常にFalse固定）、live enable policy（`GmoLiveEnablePolicyInput`/
   `evaluate_gmo_live_enable_policy`、16項目全部trueでのみready）を追加した。
   **`risk_service.evaluate_order_risk`・`bot_service`・`automation_service`へはまだ接続していない**
   （既存の無条件live拒否ブロックは意図的にそのまま維持）。テストは
   `test_gmo_live_policy_no_post.py`・`test_gmo_kill_switch_no_post.py`。
7. ✅ **完了（shadow gate / adapter skeletonのみ、実自動売買ループは未変更）**:
   `risk_service.py`に`evaluate_gmo_live_readiness_shadow`を追加（`evaluate_order_risk`は完全に
   無変更・呼び出しなし。既存の無条件live拒否もそのまま）。`bot_service.start_bot`は
   demo/practice以外を`risk_stopped`にする既存ガードがあり、`automation_service.AutomationRunner`は
   `OandaBroker`・SQLAlchemy DBモデルに強く結合しているため、これらのファイル自体は変更せず、
   独立したadapter `app/services/gmo_live_runner_boundary.py`
   （`build_gmo_live_runner_boundary_summary`）を追加した。起動時OFF・kill switch・live enable
   policyを合成してentry/settlement開始可否のみを計算し、`bot_service`/`automation_service`から
   importされない（実配線は別Step）。テストは`test_gmo_live_risk_service_integration_no_post.py`・
   `test_gmo_live_runner_boundary_no_post.py`。
8. ✅ **完了（skeletonのみ、実read-only API接続なし）**:
   `app/services/gmo_settlement_reconciliation.py`に`evaluate_gmo_settlement_reconciliation`を
   追加。OANDAの`close_unconfirmed`と同じ思想で、settlement acceptedでも
   `NO_POSITION`/`count=0`のsynthetic safe読み取りが揃うまで`reconciled=true`にしない。
   `ONE_POSITION_OPEN`は未決済、`MULTIPLE_POSITIONS`は危険停止、読み取り不可/不明は
   unknown停止。retry/repostは常にfalse。実read-only API接続は未実装（`app/private_api/`の
   既存read-onlyクライアントとの接続は別Step）。テストは
   `test_gmo_settlement_reconciliation_no_post.py`。
9. ✅ **完了（純粋な状態機械シミュレーションのみ）**:
   `app/services/gmo_level5_fake_cycle.py`に`simulate_gmo_level5_fake_cycle`を追加。
   `GmoFxBroker`の実transportが未実装のため、実際にbroker経由でfake cycleを流すことはできず、
   entry/position/settlement/position確認の各段階をsafe label入力として与える純粋な状態機械で
   代替した。成功時のみ`level5_full_auto_cycle_completed=true`、rejected/unknown/timeout・
   manual intervention・retry/repost/generic close・kill switch発火のいずれでもfalseになることを
   `test_gmo_level5_fake_cycle_no_post.py`で確認。
10. ✅ **完了（統合fake cycle。実transport未実装のため常にfail-closed）**:
    `app/services/gmo_level5_integrated_fake_cycle.py`に
    `run_gmo_level5_integrated_fake_cycle`を追加。前項9の純粋シミュレーションと異なり、
    kill switch・live enable policyが**両方とも完全に許可的な**synthetic fixtureであっても、
    実際の`GmoFxBroker.market_order()`（refusing fake HTTP client注入）を呼び出し、
    実transport未実装のため必ず例外で止まることを確認する（＝上流ゲートの寛容さに関わらず、
    現行アーキテクチャではLevel5成功に絶対到達できないことを実証する統合テスト）。
    万一将来`market_order()`が例外を投げなくなった場合に備え、`AssertionError`で大声を上げる
    フェイルセーフも入れた（`test_gmo_level5_integrated_fake_cycle_no_post.py`のmonkeypatchテストで確認）。

    **追記（Step 6G-PC-OX-R-GMO-LIVE-RUNTIME-PIPELINE-INTEGRATION-NO-POST-SPRINT-C 完了）**:
    - `gmo_live_runner_boundary.py`に`risk_config.gmo_live_enabled`ゲートと
      `settlement_side_docs_status_classified`（settlement専用ブロック）を追加。
      `bot_service.py`/`automation_service.py`は引き続き変更・import なし
      （既存自動売買ループがOANDA/SQLAlchemyに強く結合しているため、実配線は別Stepへ延期）。
    - `gmo_settlement_reconciliation.py`に`GmoSettlementSafeReadSnapshot`と
      `build_gmo_settlement_reconciliation_input_from_safe_snapshot`を追加。将来
      `app/private_api`の実read-onlyクライアントが返すsafe snapshotを reconciliation input へ
      変換する境界を用意（実read-only API接続はまだ行っていない）。`active_or_pending_order_conflict`
      ゲートも追加。
    - `risk_service.py`に`GmoLiveShadowBlockReason`（structured safe label enum）を追加し、
      `evaluate_gmo_live_readiness_shadow`が`risk_config.gmo_live_enabled`も見るよう拡張。
      `evaluate_order_risk`は完全に無変更（既存の無条件live拒否は維持）。
    - `gmo_level5_integrated_fake_cycle.py`をrunner boundary・risk shadow gate・settlement
      reconciliationを通す形に強化。実broker skeleton経由のdefaultパスは、上流ゲートが完全に
      許可的でも必ずfail-closedになることを維持しつつ、`simulate_accepted_transport_for_state_
      machine_test_only`（実broker/hard guardには一切触れないテスト専用スイッチ、production
      コードでは常にFalseであることをテストで固定）を有効にし、かつsettlement reconciliationが
      `NO_POSITION`/`count=0`を確認した場合のみLevel5=trueに到達する設計とした。

    **追記（Step 6G-PC-OX-R-GMO-LIVE-SERVICE-WIRING-READONLY-SNAPSHOT-NO-POST-SPRINT-C 完了）**:
    - `gmo_live_runner_boundary.py`に`build_gmo_live_service_boundary_summary`（`GmoLiveServiceBoundarySummary`）
      を追加。`bot_service.start_bot`/`AutomationRunner`が将来呼ぶことを想定した名前付きフック。
      `service_hook_wired=false`固定で、`bot_service.py`/`automation_service.py`は今回も未変更・未import
      （理由は前Stepと同じくOANDA/SQLAlchemyへの強結合）。
    - `gmo_settlement_reconciliation.py`に`build_gmo_settlement_safe_read_snapshot_from_private_api_safe_result`
      を追加。引数は`open_positions_count: int`・`active_orders_count: int`・`read_succeeded: bool`のみで、
      raw response・ID・数量・価格を構造的に受け取れない設計。将来`app/private_api`の実read-onlyクライアントが
      返す`OpenPosition`/`ActiveOrder`リストの`len()`を渡す形を想定（実接続はまだ行っていない）。
    - `risk_service.py`に`classify_gmo_live_unconditional_rejection_replacement_readiness`を追加。
      無条件拒否を置換するかどうかの判断はこのStepでも行わず、safe labelで分類するのみ
      （`evaluate_order_risk`は無変更）。
    - `gmo_live_safety_policy.py`に`classify_max_consecutive_losses_decision_status`を更新し、
      `max_consecutive_losses_selected=2`を本Stepで先行確定（`MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2`）した。
      `2 / 3`候補外は引き続き例外。
    - `gmo_level5_integrated_fake_cycle.py`が上記service boundary・counts-basedスナップショットアダプタを
      通る形に更新。
    - **運営者向け注記**: GMO live自動化のno-POST基盤構築は本Stepまでで複数Sprintにわたり積み上がっている
      （RiskConfig・kill switch・live enable policy・runner/service boundary・settlement reconciliation・
      risk shadow gate・integrated fake cycle）。未解決のまま残っている決定事項は (a)
      settlement side導出ルールのGMO公式closeOrder docsとの整合確認、(b) リスク上限の具体的数値、(c)
      `bot_service`/`automation_service`への実配線タイミング。これらはコードの追加では解決できない
      運営者判断/外部確認が必要な項目のため、次にno-POST scaffoldingをさらに積み上げる前に、
      一度これらの意思決定を行うことを推奨する。
11. `live_order_once.py`と Step 6G "controlled" simulation系（約130ファイル）の
    廃止・隔離（自動売買から使われないことを明示するマーカー追加、またはディレクトリ移動）
12. 運営者レビュー・sign-offチェックリスト文書化
13. `GMO_FX_ORDER_ENABLED`を本番で手動ONにする（上記すべて完了後、十分なpaper実績確認後のみ）

## 12. pre-actual readiness convergence（no-POST）

- `backend/app/services/gmo_live_pre_actual_readiness.py` を追加し、GMO live実POST前の収束用サマリーを safe boolean / safe label だけで評価できるようにした。
- `backend/app/tests/test_gmo_live_pre_actual_readiness_no_post.py` を追加し、以下を検証:
  - default で未ready
  - side docs未確認/支持回答未取得時の settlement block
  - support safe label 受領時の導出（position/opposite/ambiguous/raw分類）
  - max_consecutive_losses=2/3反映と候補外拒否
  - credential境界がfalseならactual entry gate / settlement gate不可
  - `support_answer_safe_label_capture_ready` と next step の判定
- support回答は本文ではなく safe label で扱う前提（`SUPPORT_ANSWER_*`）に統一し、raw本文保存・表示は行わない。
- service wiringは`DESIGN_FIRST_NO_CODE`継続。次Step候補は
  **`NEXT_STEP_CREDENTIAL_BOUNDARY_DESIGN`** を1本に絞る。

## 13. 次に実装する最小Step

- no-POST hook配線は完了。次Stepは credential境界 / 実POST readiness 確認の分離 Step に進む。
- 実POST系 (`allow_bridge`, `allow_real_broker_post=True`, `allow_live_http_post=True`,
  `GmoFxBroker.market_order`/`official_settlement_order` 直接起動) は次Step以降。

## 9. 運営者向け公式docs確認チェックリスト（no-POST）

- `POST /private/v1/closeOrder` の `side` 定義（`BUY`/`SELL` の意味）をGMO公式記載で直接確認済みか
- entryの反対側に `side` を送ったときの決済挙動を少なくとも2ケースで確認済みか（両建て含む）
- `closeOrder` 既定の `size` 指定動作とエラーケースを運営者が認識しているか
- `settlement_side_official_docs_semantics_confirmed=false` が外部確認完了まで
  `live settlement` blockの要件に残ることを維持しているか

### 9.1 公式docs確認結果（2026-07-07）

- `closeOrder` endpoint: `POST /private/v1/closeOrder` の存在を公式docsで確認（`/private`）
- `side`: `BUY` / `SELL` の列挙確認（必須パラメータ）
- `size` / `settlePosition`: 「どちらか1つ必須、同時指定不可」の仕様を確認
- 決済対象ポジション側への `side` マッピング（`buy sideが買建玉決済側か / 売り建玉決済側か`）は
  公式docs本文で断定する文言を確認できず
- 両建て時に size-only closeOrder を送った場合にどの建玉が対象かについて、公式docs本文で確認不可
- 判定: `SIDE_DOCS_STILL_UNCONFIRMED`（`closeOrder` 決済方向は未確定）
- 判定結果: `settlement_side_official_docs_semantics_confirmed = false` 維持、`live settlement` はblock維持
- 次Step: GMOサポートへ確認依頼を発出（本ドキュメント末尾に文面追加）

### 9.2 GMOサポート確認文（公開情報外・実値非表示）

> GMOコイン外国為替FX API の `POST /private/v1/closeOrder` について、以下をご教示ください。
> 1. `side` が決済対象建玉の「同一side」を意味するか、反対売買側を意味するか。
> 2. 買建玉を決済する場合は `BUY` か `SELL` か。
> 3. 売建玉を決済する場合は `SELL` か `BUY` か。
> 4. `size` 指定と `settlePosition` 指定（positionId複数含む）で `side` の意味が変わるか。
> 5. 同一銘柄で買建玉・売建玉が同時保有（両建て）されている場合、`size-only` closeOrder の `side` はどちらを対象にするか。
> 実注文ID／建玉ID／数量／価格／損益等の実値は共有しません。仕様意味の確認のみご回答ください。

## 10. service wiring design note（DESIGN_FIRST_NO_CODE）

- `bot_service.start_bot` / `automation_service`（`run_automation_cycle` / `AutomationRunner`）へ
  `build_gmo_live_service_no_post_hook_summary` を no-POST フックとして実配線済み。
- 実POSTメソッド呼び出し（`GmoFxBroker.market_order` / `official_settlement_order`）は未実装。
- 既存の OANDA / SQLAlchemy 結合は維持し、無変更。
- `risk_service` の実注文連携は未変更。`evaluate_gmo_live_readiness_shadow` は
  サービス hook summary の shadow 判定として参照する形のみに留めている。
- `app.live_verification` / `live_order_once` は触らない。

## 11. 確認事項

本書作成にあたり、実POST・credential使用・.env読取・raw response/broker response本文・
ID・数量・価格・損益の表示は一切行っていない。no-POST条件に従い、本文/API生レスポンスや
生パラメータの保存・表示は行わない。
