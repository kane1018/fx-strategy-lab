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

- settlement_side_official_docs_semantics_confirmed: `true`
- settlement_side_rule_status: `OFFICIAL_DOCS_SAFE_SUMMARY_CONFIRMED_OPPOSITE_SIDE`
- live settlement: `blocked`（docs確認済みだが、position-specific条件・運用者確認/credential未成立で継続）
- max_consecutive_losses_selected: `2`
- max_consecutive_losses_decision: `MINIMAL_START_MAX_CONSECUTIVE_LOSSES_2`
- service_wiring_policy: `DESIGN_FIRST_NO_CODE`（no-POST hook実配線済み）
- closeOrder docs review result: `SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE`
- closeOrder endpoint: confirmed（`/private/v1/closeOrder`）
- settlement_side_confirmation: `confirmed`（公式docs safe summary: entry反対side）

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
   このStep完了時点ではGMO公式closeOrder docsとの整合を人手で未確認だったため
   `settlement_side_official_docs_semantics_confirmed=false`だった（その後、§9.1の
   2026-07-07公式docs確認により現在は`true`。冒頭「現在のステータス」参照）。実送信直前で
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
- service wiringは`DESIGN_FIRST_NO_CODE`継続。設計readinessは以下を新たに固定:
  - `size-only settlement` は `open_positions_count == 1` 且つ `active/pending=0` の場合のみ候補化
  - `multiple/dual position` の場合は候補扱いをブロックしたまま維持
  - `position_specific_actual_path_enabled=False`（実装は現時点で未接続）
  - `actual_settlement_POST_allowed=False`
  - `full_cycle_design_ready_no_post` と `full_cycle_actual_ready` を分離し、前者は候補条件で成立し得る設計ready、
    後者は別Stepの実POST承認前提のため常時false
- 次Step候補は **`NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_NO_POST_OR_OPERATOR_CONFIRMATION_DESIGN`** に
  絞る（credential不足時のみ `NEXT_STEP_CREDENTIAL_ACTUAL_USE_POLICY_DECISION`）。

## 13. 次に実装する最小Step

- no-POST hook配線は完了。次Stepは entry/settlement actual gate 前提の分離Stepへ進む。
  - 推奨: `NEXT_STEP_ENTRY_ACTUAL_GATE_PRECHECK_NO_POST_OR_OPERATOR_CONFIRMATION_DESIGN`
    （§14でno-POST precheck実装済み。次は `ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION`
    の指示設計へ進めるが、これは実POST許可ではない）
  - credential不足時のみ: `NEXT_STEP_CREDENTIAL_ACTUAL_USE_POLICY_DECISION`
- 実POST系 (`allow_bridge`, `allow_real_broker_post=True`, `allow_live_http_post=True`,
  `GmoFxBroker.market_order`/`official_settlement_order` 直接起動) は次Step以降。

## 14. entry actual gate precheck（no-POST・実装済み）

- `backend/app/services/gmo_live_entry_actual_gate_precheck.py` を追加。
  entry実POST直前のprecheckを、safe boolean / safe count / safe labelのみで
  fail-closed分類する（default入力はすべてblocked）。
- precheck結果は**実行許可ではない**ことを構造で固定:
  - `actual_entry_POST_allowed=False` ハードコード（source-scanテストで`=True`不在も固定）
  - summaryの`__bool__`は常にFalse（allow-bridge化防止）
  - `entry_post_execution_gate_is_separate_step=True`
  - readyでも status は `ENTRY_PRECHECK_READY_NO_POST_OPERATOR_CURRENT_TURN_GATE_REQUIRED`
- operator current-turn exact confirmation は**入力fieldとして存在しない**
  （precheckで取得・保存・再利用（banking）できない設計。
  `operator_current_turn_exact_confirmation_still_required=True`固定）。
  confirmationの取り扱いは別Step `ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION` 専用。
- 売買判断はAIが行わない: entry sideは operator safe label
  （`ENTRY_BUY`/`ENTRY_SELL`/`HOLD`）のみ。`HOLD`は候補化せずblock、
  未知テキストは `OPERATOR_SIGNAL_UNSAFE_RAW_TEXT_PROVIDED` としてblock。
  `ai_trade_decision_performed=False`固定。
- precheck gate項目: HEAD==origin/main / working tree clean / credential presence safe boolean /
  credential boundary ready / credential actual use operator承認 / runtime safe read実施・fresh /
  open_positions_count==0（None含む不明はblock）/ active-pending conflict==0（同）/
  fresh entry signal存在・fresh / operator readiness / one entry POST max（1以外block）/
  retry・repost・second POST要求のblock / settlement POST・generic close混入のblock。
- テスト: `backend/app/tests/test_gmo_live_entry_actual_gate_precheck_no_post.py`
  （default fail-closed、全gate個別block、HOLD非候補化、raw text拒否、
  next step分類、confirmation field不在のdataclassスキャン、env/network/live_verification不在、
  fail-closedフィールドのsource-scan固定）。
- 併せて `GmoLiveActualEntryGateReadinessSummary` に `actual_entry_POST_allowed=False`
  ハードコードfieldを追加（settlement summaryの`actual_settlement_POST_allowed=False`との対称化）。
- このStepは実POST許可Stepではない。credential実運用承認・operator confirmationは
  引き続き未成立のblockerとして残る。

## 15. entry POST gate 設計（ENTRY_POST_GATE_WITH_OPERATOR_CURRENT_TURN_CONFIRMATION・未実行）

本節は entry POST gate の**設計語彙の記録のみ**であり、実行許可ではない。
本節の記載を operator confirmation の代わりに読み取ることは**できない**:
current-turn confirmation は実行タスクのそのターン内で operator が直接入力した場合のみ有効で、
本docs・過去ログ・ファイル・前回報告からの再利用（banking）は無効とする
（§14 precheck が構造的に confirmation 入力fieldを持たないのと同じ原則）。

### 15.1 current-turn operator必須入力（許可値・完全一致のみ）

- `operator_signal_type`: `ENTRY_BUY` / `ENTRY_SELL` / `HOLD`
  （HOLDはno-POST停止。AI/Codex/Fable5/ChatGPTによる代入・推測は禁止）
- `operator_current_turn_exact_confirmation`:
  `CONFIRM_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST_NO_SETTLEMENT`
- `operator_readiness`:
  `OPERATOR_READY_FOR_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST`
- `operator_understands_risk`:
  `OPERATOR_ACKNOWLEDGES_ACTUAL_BROKER_WRITE_RISK`
- 4つすべてがcurrent-turnで明示され、1文字でも不一致なら停止。

### 15.2 POST前必須gate（すべてfail-closed）

fresh repo check（main / HEAD==origin/main / clean / 期待commit）、
credential presence safe boolean、credential actual use boundary ready、
runtime safe read 実施・fresh、`NO_POSITION`/count=0、active/pending clear、
fresh operator signal、one entry POST max、retry/repost/second POST禁止、
settlement POST禁止、generic close禁止、raw/ID/value/credential非露出、
result は sanitized category のみ。

### 15.3 実行時制約と結果分岐

- entry order POST のみ・最大1回。timeout/unknown/rejected/network/client/server error
  いずれでも再送しない。POST後は即停止。
- `RESULT_ACCEPTED_SANITIZED` → 停止。次Step: `POST_ENTRY_READ_ONLY_CONFIRMATION_NO_POST`
- `RESULT_REJECTED_SANITIZED` → 停止・再送なし。次Step: `REJECTED_SAFE_REVIEW_NO_POST`
- `RESULT_UNKNOWN_SANITIZED` → 停止・再送なし。次Step: `UNKNOWN_RESULT_SAFE_REVIEW_NO_POST`
- `HOLD` / precheck blocked → no-POSTで停止。

### 15.4 現在の状態

- 状態: `READY_FOR_OPERATOR_CURRENT_TURN_CONFIRMATION`（operator入力待ち・未実行）
- 実行用Codex指示書はFable5最終報告（actual POST doorstep package）に含まれる。
- 実行にはさらに、実transport実装・hard guard通過設計・credential sealed provider等の
  未実装事項の解決と運営者の明示承認が別途必要（§1の必須条件は不変）。

## 16. entry actual POST 到達不能の原因分析と no-POST安全基盤（実装済み）

### 16.1 原因（operator入力ではなくinfra未整備）

operatorが current-turn で `ENTRY_SELL` を含む5項目を完全一致で入力し、operator入力gateは
PASSした。それでも entry POST が実行されなかった理由は、operator入力の不足ではなく、
repo側の実POST基盤が未整備だったためである。判明した一次blocker:

- `ENTRY_POST_BLOCKED_PRODUCTION_TRANSPORT_NOT_IMPLEMENTED`:
  `GmoFxBroker.market_order()` は transport未実装で必ず例外。
- `ENTRY_POST_BLOCKED_APPROVED_TRANSPORT_REQUIRES_FORBIDDEN_OPERATIONS`:
  実POST可能な唯一の経路（`app.live_verification`内 one-shot）は env credential読取・
  hard guard `allow=True`・real HTTP を要し、no-POST安全境界（`.env`読取禁止・
  hard guard改変禁止・新規POST経路作成禁止）と両立しない。
- `ENTRY_POST_BLOCKED_CREDENTIAL_ACTUAL_USE_BOUNDARY_NOT_READY`:
  `credential_boundary_ready_for_actual_post` は構造上常に false。
- `ENTRY_POST_BLOCKED_RUNTIME_SAFE_READ_REQUIRES_AUTHENTICATED_CONNECTION`:
  NO_POSITION/count=0 確認に認証接続（credential実使用）が必要。

### 16.2 no-POSTで整備した安全基盤（fake-only・default fail-closed）

- `gmo_live_sealed_credential_provider.py`: presence safe boolean のみを答える
  sealed provider境界。値・長さ・hash・fingerprint・prefix/suffix を扱うfieldが構造上存在せず、
  env読取surfaceも無い。`credential_actual_use_ready` は current-turn 認可がある場合のみ true、
  既定 false。
- `gmo_live_entry_post_permit.py`: ephemeral・single-use・entry専用 permit。one POST max、
  保存不可・再利用不可、settlement/close/cancel/change には使用不可（scope拒否）、
  retry/repost context では不許可、`hard_guard_allow_resolved` は常に false（`allow=True`を
  導出しない＝hard guard default-deny維持）。
- `gmo_live_runtime_safe_read.py`: fake read-only client のみ。safe status/safe count だけを返し、
  raw payload・positionId・size・price・PnL・timestamp を保持するfieldが構造上存在しない。
  gate は performed/fresh/NO_POSITION/count=0/active-pending clear/market open/ticker fresh/
  spread within limit の全成立時のみ ready、unknown/stale/非0は block。
- `gmo_live_entry_transport.py`: entry専用 transport interface と fake transport、
  「production real transport未実装」を明示する fail-closed transport、fake-only 状態機械。
  結果は sanitized category（ACCEPTED/REJECTED/UNKNOWN）のみで、raw/response/ID/生値の
  field無し。real transport は状態機械が拒否、いかなる結果でも再送（retry/repost/second POST）
  なし。
- `gmo_live_entry_actual_post_gate_readiness.py`: 上記4境界を統合。**全fakeが揃っても
  `actual_entry_POST_allowed` は常に false**、`entry_post_execution_gate_is_separate_step=True`、
  `production_real_transport_implemented=False`、`PRODUCTION_REAL_ENTRY_TRANSPORT_NOT_IMPLEMENTED`
  を常時 blocked_reason に含める。`__bool__` も false。

### 16.3 まだ actual POST 許可ではない

本Stepは no-POST安全基盤の整備のみで、実POST解禁ではない。実POSTに進むには以下が別途必要
（本Stepでは扱わない・偽装しない）:

- production real entry transport の実装（`auth.py`署名再利用、no-POSTスケルトン解消）
- credential sealed provider の実実装と、安全境界内での実運用承認
- runtime safe read の実 read-only client 接続
- RESUME_DESIGN §1 の未達条件（paper実績・kill switch全異常系実テスト・運営者書面sign-off記録）
- 2026-07-06 インシデントの正式remediation宣言
- hard guard への `allow` 供給を「allow bridge を作らずに」operator gate から渡す controlled設計

### 16.4 STEP_6G_PC_OX_R_RESUME_DESIGN_OPERATOR_CONDITIONS_RECORD_SAFE_LABELS_NO_POST_C

本セクションは **no-POST記録**。実POST許可ではない。

- actual POST許可: `false`（`actual_post_permission_this_step`）
- entry POST許可: `false`（`entry_post_permission_this_step`）
- settlement POST許可: `false`（`settlement_post_permission_this_step`）
- POST count: `0`
- no-POST基盤状況: 運用側条件を除き整備済み。`actual_entry_POST_allowed` は既定 `false` 維持
- Level 5 full auto cycle completed: `false`
- RESUME_DESIGN §1 operator condition status: `NOT_COMPLETE`
- operator_actual_post_intent_status: `OPERATOR_INTENDS_TO_PROCEED_TO_ACTUAL_ENTRY_POST_AFTER_ALL_REQUIRED_GATES`
- operator_acknowledges_actual_broker_write_risk: `true`
- operator_acknowledges_one_post_max_no_retry_no_repost: `true`
- operator_acknowledges_raw_id_value_credential_non_exposure: `true`
- operator_acknowledges_no_generic_close: `true`
- operator_acknowledges_no_settlement_post_in_entry_step: `true`
- operator_acknowledges_incident_history: `true`
- operator_acknowledges_resume_conditions_not_equal_actual_post_permission: `true`
- operator_approves_objective_paper_and_anomaly_audit: `true`
- operator_approves_no_post_safe_infra_work: `true`
- operator_approves_sealed_credential_provider_design_no_value_exposure: `true`
- operator_approves_controlled_hard_guard_permit_design_no_allow_bridge: `true`
- no-post objective evidence audit:
  - paper trade evidence: `PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY`
    - paper evidence criteria status: `PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY`
    - paper trade evidence safe summary: `docs/STEP6G_PC_OX_R_PAPER_SHADOW_SAFE_REPORT_AND_ANOMALY_EVIDENCE_EXPANSION_NO_POST_C.md`
    - `paper_trade_evidence_criteria` は no-POST で safe label のみで判定可能な条件を明文化済み（本Step）
      - evidence source exists
      - evidence location safe label exists
      - period / run count / result category safe label exists
      - reproducible or checked-in report / deterministic test / documented runbook
      - no raw P/L / trade ID / order ID / position ID / price/size exposure
      - relevance to GMO live entry readiness and no implication to actual POST permission
    - `paper_trade_source_exists=true`, `paper_trade_period_safe_label=LEVEL5_FAKE_CYCLE_SYNTHETIC_WINDOW_V1`, `paper_trade_run_count_safe_label=RUN_COUNT_SAFE_FIXTURE_SCENARIOS`, `paper_trade_result_category=NO_POST_ENTRY_EXECUTION_PATH`, `performance_report_location_safe_label=docs/REPRODUCIBLE_NO_POST_PAPER_SHADOW_EVIDENCE_SUMMARY.md`
    - `raw_profit_loss_values_exposed=false`, `raw_trade_ids_exposed=false`, `raw_order_ids_exposed=false`, `raw_position_ids_exposed=false`, `raw_price_or_size_values_exposed=false`
    - 次手順（no-POST）: 上記安全 summary の充足条件を満たす `PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY` エビデンスに更新
  - kill switch / settlement anomaly audit: `SYNTHETIC_ONLY_NOT_SUFFICIENT`
    - kill switch and anomaly evidence criteria status: `SYNTHETIC_ONLY_NOT_SUFFICIENT`
    - criteriaは以下を no-POST で満たすことを定義:
      - kill switch failure modes safe label
      - settlement reconciliation failure modes safe label
      - retry / repost / second POST block coverage
      - raw/ID/value exposure block
      - settlement POST-in-entry block
      - generic close / active-pending conflict block
      - position count nonzero block
      - stale / unknown runtime read block
      - missing credential boundary block
      - unknown / rejected / timeout result no-retry block
      - synthetic only coverage indicator
      - deterministic replay / fake runtime evidence indicator
      - real_broker_write_used=false, raw_response_exposed=false, raw_ids_exposed=false
    - `kill_switch_test_scope_safe_label=SYNTHETIC_TESTS_ONLY`, `settlement_reconciliation_test_scope_safe_label=SYNTHETIC_TESTS_ONLY`, `tested_failure_modes_safe_labels=SYNTHETIC_ONLY_SCOPE_NOT_SUFFICIENT_FOR_ACTUAL_POST_RESUME`, `synthetic_only=true`, `real_broker_write_used=false`
    - `anomaly_deterministic_or_replay_coverage_safe_label=DETERMINISTIC_REPLAY_FIXTURES_BASED`
    - `anomaly_evidence_sources= test_gmo_kill_switch_no_post.py, test_gmo_settlement_reconciliation_no_post.py, test_gmo_level5_fake_cycle_no_post.py, test_gmo_level5_integrated_fake_cycle_no_post.py`
    - `anomaly_replay_evidence_source=backend/app/tests/fixtures/no_post_evidence/anomaly_replay_safe_evidence_no_post.json`
    - 次手順（no-POST）: synthetic外の evidence / テストを追加し `KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED` を更新
- actual_post_permission_this_step: `false`（本Stepは actual POST 許可ではない）
- entry_post_permission_this_step: `false`（本Stepは entry POST 許可ではない）
- settlement_post_permission_this_step: `false`（本Stepは settlement POST 許可ではない）
- current-turn entry POST exact confirmation: `false`（別ターンで operator_signal_type と exact confirmation を再入力）
- paper trade evidence status: `PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY`（`paper_trade_source_exists=true`, `paper_trade_period_safe_label=LEVEL5_FAKE_CYCLE_SYNTHETIC_WINDOW_V1`, `paper_trade_run_count_safe_label=RUN_COUNT_SAFE_FIXTURE_SCENARIOS`, `paper_trade_result_category=NO_POST_ENTRY_EXECUTION_PATH`, `performance_report_location_safe_label=docs/REPRODUCIBLE_NO_POST_PAPER_SHADOW_EVIDENCE_SUMMARY.md`）
- kill switch / settlement anomaly tests: `SYNTHETIC_ONLY_NOT_SUFFICIENT`（`kill_switch_test_scope_safe_label=SYNTHETIC_TESTS_ONLY`, `settlement_reconciliation_test_scope_safe_label=SYNTHETIC_TESTS_ONLY`, `tested_failure_modes_safe_labels=SYNTHETIC_ONLY_SCOPE_NOT_SUFFICIENT_FOR_ACTUAL_POST_RESUME`, `synthetic_only=true`, `real_broker_write_used=false`）
- operator sign-off: `OPERATOR_SIGNOFF_RECORDED_FOR_NO_POST_NEXT_GATE_DESIGN`
- incident remediation: `OPERATOR_DECLARES_2026_07_06_INCIDENT_REMEDIATED_FOR_NO_POST_RESUME_DESIGN`
- operator UI no-position/no-active-pending check: `OPERATOR_UI_CONFIRMED_NO_POSITION_AND_NO_ACTIVE_PENDING_ORDER`
- UI check time safe label: `CURRENT_OPERATOR_UI_CHECK_COMPLETED`
- position status safe label: `NO_POSITION_CONFIRMED_BY_OPERATOR_UI`
- active/pending order safe label: `NO_ACTIVE_PENDING_ORDER_CONFIRMED_BY_OPERATOR_UI`
- credential actual use policy: `OPERATOR_APPROVES_DESIGN_OF_SEALED_CREDENTIAL_PROVIDER_NO_VALUE_EXPOSURE`
- raw/ID/value exposure: `false`（raw報告/生報告/credential/値の実露出なし）
- operator_acknowledges_actual_broker_write_risk: `true`
- operator_acknowledges_one_post_max_no_retry_no_repost: `true`
- operator_acknowledges_raw_id_value_credential_non_exposure: `true`
- operator_acknowledges_no_generic_close: `true`
- operator_acknowledges_no_settlement_post_in_entry_step: `true`
- operator_acknowledges_incident_history: `true`
- operator_acknowledges_resume_conditions_not_equal_actual_post_permission: `true`
- remaining operator blockers:
  - kill switch / settlement anomaly tests beyond synthetic-only
- remaining code blockers:
  - production real entry transport
  - credential sealed provider real operation
  - runtime safe read real connection
  - hard guard allow controlled供給設計
- next recommended step:
  - operatorがsafe summaryを提示するまで、RESUME_DESIGN §1 は未完了
  - code 側で進める場合は、real HTTPなしの production signed POST interface no-POST設計に限定
  - actual POST gate へは進まない

### 16.5 STEP_6G_PC_OX_R_ENTRY_SIGNED_POST_INTERFACE_NO_POST_C

このセクションは、`signed`インターフェースを含む entry actual POST 進入口の
no-POST境界を明示し、実行可否ではなく**設計状態**を記録する。

- no-POSTステータス: `NOT_COMPLETE`（運営者条件は未完）
- 本Stepの結論: `actual_post_permission_this_step=false`、`entry_post_permission_this_step=false`、`settlement_post_permission_this_step=false`
- production signed POST transport（entry専用）は未実装（`real transport`未接続）
- `app/private_api/auth.py` / `app/private_api/order_builders.py` の署名部品は設計準拠で既に存在
  - 実シグネチャ送出は行わない（`raw signature / header / credential`は送出・保持しない）
  - request planは `method/path/body_json` のsafe modelで保持（実値非露出）
- `backend/app/services/gmo_live_entry_transport.py` は引き続き no-POST専用:
  - fake transportは `entry_only / one-post / no-retry / no-repost / no-second-post`
  - real transportは `ProductionEntryTransportNotImplemented` で `fail-closed`
  - 結果カテゴリは sanitized のみ
- `backend/app/services/gmo_live_entry_actual_post_gate_readiness.py` と no-POST test群は
  `actual_entry_POST_allowed=false` を固定し、allow直書きを許容しない
- `entry` と `official settlement` の境界は維持（closeOrder / settlePosition / generic close へは流用不可）
- remaining operator blockers:
  - kill switch / settlement anomaly tests beyond synthetic-only
  - kill switch / settlement anomaly tests beyond synthetic-only
- remaining code blockers:
  - production real entry transport actual 実装
  - credential sealed provider real operation
  - runtime safe read real 接続
  - hard guard allow-controlled供給
- 次 step 推奨:
  - RESUME_DESIGN §1 を実行条件として未完扱いのまま維持し、実POSTに進まず運営者条件の提示を待つ
  - production signed POST境界は引き続き no-POST（fake / fail-closed）で固定

### 16.6 Level 5 full auto cycle

`Level_5_full_auto_cycle_completed=false`（不変）。entry POST自体が未到達のため、
post-entry read-only confirmation・settlement・full cycle はいずれも未着手。

## 9. 運営者向け公式docs確認チェックリスト（no-POST）

- `POST /private/v1/closeOrder` の `side` 定義（`BUY`/`SELL` の意味）をGMO公式記載で直接確認済みか
- entryの反対側に `side` を送ったときの決済挙動を確認済みか（運営者safe summary）
- `closeOrder` 既定の `size` 指定動作とエラーケースを運営者が認識しているか
- `settlement_side_official_docs_semantics_confirmed` が確認済みで、
  `live settlement` が side docs由来でブロックしない状態になったかを確認する

### 9.1 公式docs確認結果（2026-07-07）

- `closeOrder` endpoint: `POST /private/v1/closeOrder` の存在を公式docsで確認（`/private`）
- `side`: `BUY` / `SELL` の列挙確認（必須パラメータ）
- `size` / `settlePosition`: 「どちらか1つ必須、同時指定不可」の仕様を確認
- 決済対象ポジション側への `side` マッピング（`buy sideが買建玉決済側か / 売り建玉決済側か`）は
  GMO FX公式IFDOCO例で `OPEN BUY` 対して `CLOSE SELL`、`OPEN SELL` 対して `CLOSE BUY` を確認済み（`OPPOSITE_SIDE`）
- 両建て時に size-only closeOrder を送った場合にどの建玉が対象かについて、公式docs本文で確認不可
- `operator_size_only_closeOrder_dual_position_targeting=SETTLE_POSITION_REQUIRED_FOR_DUAL_OR_MULTIPLE_POSITIONS`
  を、両建て/複数建玉時のsafe policyとして確定扱いする。
- 判定: `SIDE_SEMANTICS_CONFIRMED_OPPOSITE_SIDE`（entry `BUY`=SELL決済、`SELL`=BUY決済）
- 判定結果: `settlement_side_official_docs_semantics_confirmed = true`、`live settlement` は
  `size-only closeOrder` の両建て対象未確認のため block維持（position-specific path/actual gate未整備）
- 次Step: size-only closeOrder の両建て時対象選択（position指定なしでのどちら決済）が未確認なため、その扱いをblockedとして維持しつつ
  position-specific actual path/実POST条件の設計を保留

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
