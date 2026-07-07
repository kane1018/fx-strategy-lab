# Codex 引き継ぎ（CODEX_HANDOFF）

Codex が新しいタスクを安全に開始するための要約済み文脈。詳細な現在地は
[PROJECT_STATUS.md](PROJECT_STATUS.md)、固定ルールは [`../AGENTS.md`](../AGENTS.md) を参照する。

## 1. 目的と現在地

FX Strategy Lab は、FX の検証、ペーパートレード、通知、将来の少額自動売買へ安全に段階移行するための
検証基盤である。現時点では実注文・実資金・注文API・broker・本番公開 API 追加を扱わない
（ただし下記インシデント記録の例外を参照）。

- repository: `https://github.com/kane1018/fx-strategy-lab.git`
- branch: `main`
- frontend production: `https://fx-strategy-lab.vercel.app`
- backend production: `https://fx-strategy-lab.onrender.com`
- production entrypoint: `app.main_readonly:app`

### 【重大インシデント記録 2026-07-06】Claude Codeによる実POST能力監査・fresh retry/entry/settlement作業停止

運営者からの指示で、Claude Code（本ドキュメントを含むリポジトリのコード）を fresh に監査した結果、
以下が判明した。運営者はこれを重大インシデントとして扱い、fresh retry・entry gate・settlement gate・
実POST系の作業をすべて停止し、以後は no-POST の安全境界修正のみを行う方針とした。

- 本ファイル内の "Step 6G-PC-OX-R-..." という一連の記録（entry POST accepted、settlement POST
  rejected、runtime safe read の position count、credential presence safe boolean 等）は、
  その大半が `backend/app/live_verification/` 配下の"controlled"系モジュールの**dataclass固定
  デフォルト値によるシミュレーション**から生成されたものであり、実ブローカーへの実HTTP接続・
  実credential使用の結果ではない。読者はこれらの記録を「実ブローカー検証済みの事実」ではなく
  「simulation / docs claim / unknown」として扱うこと。
- 一方で、以下は**実際にGMO FX本番Private APIへ実HMAC-SHA256署名付きHTTP POSTを送信できる、
  実装済みの実コード**であり、シミュレーションではない。
  - `backend/app/live_verification/live_order_once.py`
    （`execute_one_shot_live_order` / `post_live_order_with_httpx`。
    エンドポイント `https://forex-api.coin.z.com/private/v1/order`）
  - `backend/app/live_verification/live_order_real_official_settlement_actual_transport_no_post_controlled.py`
    （`OfficialSettlementActualTransportHttpxClient.send_official_settlement`）
  - `backend/app/live_verification/live_order_real_one_shot_post_real_delegate_controlled.py`
    （`make_live_order_real_one_shot_post_real_delegate` が上記の実POST関数を解決・呼び出す橋渡し。
    `os.environ` から `GMO_FX_API_KEY` / `GMO_FX_API_SECRET` を読む設計）
  - これらのファイル名にある `_no_post_controlled` / `controlled` は「実行不可能」を意味しない。
    「このモジュール自身の他の関数がこれを呼んでいない」という意味に過ぎない。
- ローカルに `~/.local/state/fx-strategy-lab/live-order-attempts/2026-06-25.json` と
  `2026-06-26.json` が実在する（ファイル名の日付のみ確認、中身は未読・ID等は非露出）。これは
  `live_order_once.py` の台帳機能が、単体テストのfakeパスではなく実際のデフォルト台帳パスに
  対して過去に呼び出されたことを示す一次証拠であり、「Step 6G記録が完全な絵空事」とは断定できない
  一方、「実際にブローカーへPOSTが届き何が返ったか」もコード監査だけでは確認できない
  （レスポンス非保存設計のため）。
- 対応として `backend/app/tests/test_live_verification_real_post_capability_isolation.py` を追加し、
  Step 6G "controlled/safe" 系モジュールの既定（zero-arg）エントリポイントから上記3つの実POST可能
  コードへ到達できないこと、および実POST可能な関数・クラスが明示的な transport・実credential・
  `allow_live_http_post=True` 相当を要求すること、GMO_FX_API_KEY/SECRET 未設定時は実delegateが
  ネットワークに触れず安全に失敗することを回帰テストで固定した（実POST・credential使用・.env読取・
  ledger中身閲覧はいずれも行っていない）。
- 次にやるべきは、ブローカー側（GMOコイン管理画面）で実際の建玉・注文履歴を運営者自身が一次確認
  すること。コード監査だけでは実POSTの成否は再現できない。
- **追記（Step 6G-PC-OX-R-REAL-POST-HARD-GUARD-MINIMAL-NO-POST-C 完了）**: 上記3経路それぞれの
  実送信直前に、共通のdefault-denyハードガード `real_broker_post_hard_guard.py`
  （`assert_real_broker_post_allowed`）を追加した。明示的な`allow=True`以外（False/None/未設定/
  その他truthy値）はすべて拒否し、env/`.env`による解除経路はない。既存の個別フラグに加える形の
  多層防御で、read-onlyのsafe read経路（`check_private_readonly_connection.py`等）は変更していない。
  詳細は `AGENTS.md` の同Step追記、テストは
  `backend/app/tests/test_live_verification_real_post_capability_isolation.py`。
- **追記（Step 6G-PC-OX-R-POST-INCIDENT-LIVE-ALLOW-BRIDGE-NO-POST-C: allow bridge実装を却下）**:
  hard guardの`allow`を複数のsafe boolean/labelから自動算出する「allow bridge」（再利用可能な
  許可判定関数）の実装依頼があったが、no-POST設計であっても却下した。理由は、これが将来hard guard
  を機械的に解除する唯一の欠けていた接続点になり得るためで、重大インシデント直後の安全方針に反する。
  hard guardはdefault-denyのまま維持する。live再開の可否は、boolean判定器ではなく運営者による
  明示的な重大インシデント解除宣言と、その時点のfresh gate（新しいruntime読み取り・新しい6行
  confirmation）でのみ扱う。previous confirmationや過去のsafe labelは再利用しない。実POST再開の
  是非は、別途専用の再開方針Stepでのみ判断する。新しいエージェント/セッションは同種のallow bridge
  を再提案・再実装しないこと。コード変更なし。
- **追記（Step 6G-PC-OX-R-REAL-BROKER-HARD-GUARD-RELOCATION-NO-POST-C 完了）**:
  `real_broker_post_hard_guard.py`を`app.live_verification`から`app.security`へ移設した
  （挙動・default-denyは無変更）。目的は、production broker/service経路が
  `app.live_verification`を一切importしないという分離原則（
  `test_gmo_fx_broker_live_verification_isolation.py`）を保ちながら、将来の`GmoFxBroker`実装が
  このハードガードを参照できるようにするため。実POST可能3経路(`live_order_once.py`等)は新しい
  import pathを参照するよう更新し、旧モジュールは削除（互換shimなし）。詳細は`AGENTS.md`の同Step
  追記、テストは`backend/app/tests/test_gmo_fx_broker_live_verification_isolation.py`。

- 現在のフェーズ:
  **Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECT-ROOT-CAUSE-HARDENING-NO-POST-C
  official settlement reject root-cause hardening ready / no-POST**。
  official settlement rejected loopの再発リスクを下げるため、
  `backend/app/live_verification/live_order_real_official_settlement_reject_root_cause_hardening_no_post_controlled.py`
  と対応テストを追加した。hardening summaryは official settlement route、size-based target consistency、
  side provenance、real-network client binding、safe rejection reporting をsafe label/booleanだけで束ねる。
  `safe_error_code_capture_status=SAFE_ERROR_CODE_CAPTURE_READY_ALLOWLIST_ONLY` とし、
  safe HTTP status label、safe API status label、safe broker error code label、safe broker error code family、
  operator UI safe labelだけを allowlist で分類する。raw response、broker response本文、error message本文、
  account/order/position/trade ID、数量、価格、credential、signature、headers、`.env` は扱わない。
  GMO FX公式docsのerror code familyは、決済数量・target mismatch、建玉なし、active order conflict、
  session/market、permission/account、rate limit/temporary、parameter/request shapeへsafe分類するための
  label familyとしてのみ扱う。position-specific settlementは
  `position_specific_safe_identifier_handling_ready=false`、
  `position_specific_actual_path_allowed=false` のまま、将来使う場合はopaque handle設計が必要。
  size-based settlementは `request_uses_size_only=true`、
  `request_includes_settlePosition=false`、
  `size_and_settlePosition_mutually_exclusive=true` をsafe labelで確認する。
  `operator_size_only_closeOrder_dual_position_targeting=SETTLE_POSITION_REQUIRED_FOR_DUAL_OR_MULTIPLE_POSITIONS`
  は、両建て/複数建玉時に size-only を official settlement 候補化しない policy として保持する。
  operator UIからは本文・ID・数量・価格を受け取らず、
  `UI_SAFE_REASON_PERMISSION`、`UI_SAFE_REASON_SIZE_OR_TARGET`、
  `UI_SAFE_REASON_POSITION_NOT_FOUND`、`UI_SAFE_REASON_ACTIVE_ORDER_CONFLICT`、
  `UI_SAFE_REASON_MARKET_OR_SESSION`、`UI_SAFE_REASON_RATE_LIMIT_OR_TEMPORARY`、
  `UI_SAFE_REASON_UNKNOWN`、`UI_SAFE_REASON_NOT_DISPLAYED` のみを受け取る。
  現在のmanual close後safe stateが `NO_POSITION/count=0` かつ active/pending clear であれば、
  `fresh_retry_readiness=READY_WITH_FRESH_GATES_REQUIRED` として扱い、次は
  **Step 6G-PC-OX-R-FRESH-ENTRY-SIGNAL-SAFE-LABEL-CONFIRMATION-NO-POST-C**。
- 直前関連フェーズ:
  **Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECTION-SAFE-CATEGORY-REPORTING-HANDOFF-NO-POST-C
  safe rejection category reporting / handoff ready / no-POST**。
  前Stepで統合した safe rejection category capture 結果を、final report と
  ChatGPT一括引き継ぎ要約へ安全に出力する no-POST reporting/handoff adapter を追加した。
  `backend/app/live_verification/live_order_real_official_settlement_rejection_safe_category_reporting_handoff_no_post_controlled.py`
  は integration result から `safe_rejection_category`、`safe_rejection_kind`、
  `safe_rejection_source`、`safe_rejection_confidence`、
  `safe_rejection_reason_available`、`safe_rejection_reason_unavailable`、
  `safe_rejection_requires_raw_response`、
  `safe_rejection_requires_operator_ui_safe_label` を safe label / boolean のみで
  final report fragment と ChatGPT handoff summary に出力する。
  default rejected-only result は
  `SAFE_REJECTION_CATEGORY_UNKNOWN` /
  `SAFE_REJECTION_KIND_BROKER_REJECTED_REASON_UNAVAILABLE` /
  `SAFE_REJECTION_SOURCE_SANITIZED_RESULT_ONLY` に落ち、
  `safe_rejection_reason_available=false`、`safe_rejection_reason_unavailable=true`、
  `safe_rejection_requires_raw_response=true`、
  `safe_rejection_requires_operator_ui_safe_label=true` として扱う。
  safe broker code label、safe HTTP status label、operator UI safe label、
  official docs comparison safe result がある場合だけ category/kind/source/confidence を具体化する。
  actual settlement POST、entry POST、retry/repost、second settlement POST、generic close、
  ledger/receipt、transport/HTTP call、position-specific pathはすべて0/falseにsanitizeされる。
  sentinel testsで raw response、broker response、error message、account/order/position/trade ID、
  数量、価格、credential、signature、headers が asdict/render/final report/ChatGPT summary に
  出ないことを確認した。このStepでも `Level_5_full_auto_cycle_completed=false` は維持する。
  次の推奨Stepは
  **Step 6G-PC-OX-R-FRESH-ENTRY-SIGNAL-SAFE-LABEL-CONFIRMATION-NO-POST-C**。
- 直前関連フェーズ:
  **Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-REJECTION-SAFE-CATEGORY-CAPTURE-INTEGRATION-NO-POST-C
  safe rejection category capture integrated / no-POST**。
  前Stepで追加した safe rejection category capture 境界を、official settlement rejected result handling 用の
  no-POST adapterへ接続した。
  `backend/app/live_verification/live_order_real_official_settlement_rejection_safe_category_capture_integration_no_post_controlled.py`
  は official settlement の `RESULT_REJECTED_SANITIZED` を safe capture に渡し、final report / handoff 用に
  `safe_rejection_category`、`safe_rejection_kind`、`safe_rejection_source`、
  `safe_rejection_confidence`、`safe_rejection_reason_available`、
  `safe_rejection_reason_unavailable` を safe label / boolean のみで返す。
  default rejected-only result は
  `SAFE_REJECTION_CATEGORY_UNKNOWN` /
  `SAFE_REJECTION_KIND_BROKER_REJECTED_REASON_UNAVAILABLE` /
  `SAFE_REJECTION_SOURCE_SANITIZED_RESULT_ONLY` に落ち、
  `safe_rejection_reason_available=false`、`safe_rejection_reason_unavailable=true`、
  `safe_rejection_requires_raw_response=true` として扱う。safe broker code label、safe HTTP status label、
  operator UI safe label、official docs comparison safe result がある場合だけ、より具体的な
  category/kind/sourceへ分類する。
  actual settlement POST、entry POST、retry/repost、second settlement POST、generic close、
  ledger/receipt、transport/HTTP call、position-specific pathはすべて0/falseにsanitizeされる。
  sentinel testsで raw response、broker response、error message、account/order/position/trade ID、
  数量、価格、credential、signature、headers が asdict/render に出ないことを確認した。
  このStepでも `Level_5_full_auto_cycle_completed=false` は維持する。
- 直前関連フェーズ:
  **Step 6G-PC-OX-R-API-PERMISSION-UPDATE-RECORD-NO-POST-C API permission update safe declaration recorded / no-POST**。
  直近のLevel 5再挑戦サイクルでは、previous entry POSTはsafe summary上1回のみで
  `RESULT_ACCEPTED_SANITIZED`、official settlement POSTも1回のみ実行され
  `RESULT_REJECTED_SANITIZED` だった。retry/repost/second settlement POST、entry POST after reject、
  generic close、ledger/receipt、raw/ID/value exposure は行っていない。その後operator manual interventionにより
  cycle closeout は `MANUAL_INTERVENTION_INCLUDED_CLOSEOUT` として扱う。read-only safe confirmationでは
  `runtime_position_after_manual_action=NO_POSITION`、`position_count_safe_after_manual_action=0`、
  `active_order_status_safe=NO_ACTIVE_ORDERS_SAFE`、`pending_order_status_safe=NO_PENDING_ORDER_SAFE` を確認した。
  manual intervention included のため `Level_5_full_auto_cycle_completed=false` は固定で、前サイクルを
  full auto成功として扱わない。fresh retry readinessは `fresh_cycle_required=true`、
  `previous_cycle_closed=true`、`known_code_blocker_remaining=false`。次にLevel 5を狙う場合は別fresh cycleとして
  Fresh entry gate → post-entry ONE_POSITION_OPEN/count=1 confirmation → official settlement execution gate →
  post-settlement NO_POSITION/count=0 confirmation の順に進む。次回settlement前には official settlement route、
  actual transport、real-network client binding、settlement side provenance、operator readiness、
  settlement-specific confirmation、retry/repost/second POST禁止をfreshに再確認する。
  追加記録として、operator safe declaration により
  `api_permission_update_recorded=true`、
  `operator_enabled_api_permission_settlement_order=true`、
  `operator_enabled_api_permission_execution_info=true`、
  `api_permission_update_source=OPERATOR_SAFE_DECLARATION` を記録した。これはCodexがAPIキー画面、
  秘密情報、raw権限画面値、API key、API secretを取得して確認したものではない。
  `api_permission_raw_screen_value_exposed=false`、`api_key_value_exposed=false`、
  `api_secret_value_exposed=false`、`credential_metadata_exposed=false`。
  previous settlement rejectionについては
  `suspected_rejection_cause=API_PERMISSION_SETTLEMENT_ORDER_OR_EXECUTION_INFO_DISABLED_POSSIBLE` を
  仮説として扱い、`rejection_cause_confirmed=false`、`raw_response_inspected=false`、
  `broker_response_exposed=false` を維持する。
  `next_fresh_cycle_note=settlement_permission_and_execution_info_permission_updated_before_next_attempt`。
- 直前関連フェーズ:
  **Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-ROUTE-NO-POST-IMPLEMENTATION-C official settlement route no-POST preview / CASE 1**。
  直前 GMO official settlement route review はCASE 1で、
  `official_settlement_route_confirmed=true`、
  `official_settlement_route_confirmation_basis=OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST`、
  `generic_opposite_order_as_close_forbidden=true`、
  `generic_close_primitive_revoked=true`、`actual_close_post_allowed_now=false` だった。
  今回
  `backend/app/live_verification/live_order_real_official_settlement_route_no_post_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_official_settlement_route_no_post_controlled.py`、
  [STEP6G_OFFICIAL_SETTLEMENT_ROUTE_NO_POST_IMPLEMENTATION.md](STEP6G_OFFICIAL_SETTLEMENT_ROUTE_NO_POST_IMPLEMENTATION.md)
  を追加した。safe previewは
  `official_settlement_no_post_preview_ready=true`、
  `settlement_route_kind=OFFICIAL_SIZE_BASED_SETTLEMENT`、
  `settlement_route_is_generic_order=false`、
  `settlement_route_is_dedicated=true`、
  `settlement_route_invocation_deferred=true`、
  `actual_settlement_post_allowed_now=false`、
  `actual_close_post_allowed_now=false`、
  `symbol_safe_label=USD_JPY`、`settlement_size_safe_label=100`、
  `settlement_order_type_safe_label=MARKET`。position-specific pathは
  `position_specific_identifier_safe_handling_ready=false` のため
  `position_specific_preview_allowed=false`、
  `position_specific_execution_blocked_reason=SAFE_IDENTIFIER_HANDLING_NOT_READY`。
  Level 5は `OFFICIAL_SETTLEMENT_PREVIEW_READY_NO_POST` までで停止する。
  actual entry POST、actual close POST、actual settlement POST、retry/repost、
  second close、ledger update、receipt handoff、raw request/response、raw endpoint、
  broker/API response、account/order/transaction/position ID、actual price/PnL、
  credential/signature/header値、`.env` は扱っていない。
  次の推奨Stepは **Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C**。
- 直前フェーズ:
  **Step 6G-PC-OX-R-GMO-OFFICIAL-SETTLEMENT-ROUTE-REVIEW-C GMO official settlement route review / no-POST / CASE 1**。
  GMO FX操作マニュアル、取引ルール、公式API docs、repo内docs/codeを照合し、UI決済フロー、
  buy/sell非ネット、API新規注文最小数量、決済数量下限なし、両建て可能、
  専用settlement route/parameterを no-POST で確認した。
  詳細は [STEP6G_GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW.md](STEP6G_GMO_OFFICIAL_SETTLEMENT_ROUTE_REVIEW.md)。
- 直前フェーズ:
  **Step 6G-PC-OX-R-CLOSE-ORDER-ACTUAL-EXECUTOR-COMPATIBILITY-NO-POST-C close actual executor compatibility foundation / no actual close POST / CASE 1**。
  直前 close execution gate retry はCASE 2で、close executable previewは
  `SELL / USD_JPY / 100 / MARKET` までreadyだったが、既存 one-shot executor preview が
  generic entry用のBUY固定guardで `SELL` を拒否したため、actual close POSTには進まなかった。
  今回
  `backend/app/live_verification/live_order_real_close_actual_executor_compatibility_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_close_actual_executor_compatibility_controlled.py`、
  [STEP6G_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_CONTROLLED.md](STEP6G_CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_CONTROLLED.md)
  を追加した。既存 generic entry BUY guardは維持し、generic entry `SELL` は引き続きblockする。
  後続manual risk gateにより、approved guarded generic close primitive はactual settlement用として撤回済み。
  現在は official GMO settlement route が確認されるまで
  `CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_BLOCKED_OFFICIAL_SETTLEMENT_ROUTE` としてfail-closedに扱う。
  Level 5 foundation still carries `close_actual_executor_compatibility`, but generic opposite orderでは
  `CLOSE_ACTUAL_EXECUTOR_COMPATIBILITY_READY_NO_POST` に進めない。
  actual close POST / entry POST / retry/repost / second close POST / ledger / receipt /
  raw/ID/value exposure は未実行。
  次の推奨Stepは
  **Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C**。
- 直前フェーズ:
  **Step 6G-PC-OX-R-FRESH-POSITION-OPEN-SAFE-HANDOFF-GATE-C confirmed fresh open position handed off to close execution gate / planning-only / no close POST / CASE 1**。
  直前のfresh cycle entry gateはCASE 1で、fresh entry POSTはsafe summary上
  `fresh_entry_http_post_executed=true`、`fresh_entry_post_execution_count=1`、
  `fresh_entry_sanitized_result_category=RESULT_ACCEPTED_SANITIZED`、
  `fresh_entry_safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF`、
  `fresh_entry_retry_attempted=false`、`fresh_entry_repost_attempted=false`、
  `fresh_entry_second_post_attempted=false`、`close_post_executed=false`、
  `ledger/receipt=false`、`raw/ID/value exposure=false` として扱う。
  直前のfresh post-entry confirmation gateはCASE 1で、read-only runtime position checkにより
  `position_status=ONE_POSITION_OPEN`、`position_count_safe=1`、
  `has_exactly_one_position=true`、`fresh_entry_effect_confirmed_by_position=true`、
  `next_cycle_state=FRESH_POSITION_OPEN_SAFE` を確認済み。
  今回のfresh position open safe handoff gateではcredential presenceをsafe booleanで再確認し、
  read-only runtime position checkを1回だけ再実行した。safe status/countは
  `runtime_position_status=ONE_POSITION_OPEN`、`runtime_position_count_safe=1`、
  `has_exactly_one_position=true`。判定は
  `handoff_gate_ready=true`、
  `fresh_position_open_safe_handoff_ready=true`、
  `next_cycle_state=FRESH_POSITION_OPEN_SAFE_HANDOFF_READY`、
  `close_route_ready=true`、`close_planning_allowed=true`、
  `close_execution_gate_may_be_planned=true`、
  `close_execution_allowed_now=false`、`retry_allowed=false`、
  `repost_allowed=false`、`second_entry_allowed=false`、
  `close_post_allowed_now=false`、`level5_full_auto_cycle_completed=false`。
  このStepではfresh entry POST再実行、retry/repost、second POST、actual close POST、
  ledger update、receipt handoff、raw request/response、broker/API response、
  account/order/transaction/position ID、actual price/PnL、credential/signature/header値、
  `.env` は扱っていない。詳細は
  [STEP6G_FRESH_POSITION_OPEN_SAFE_HANDOFF_GATE.md](STEP6G_FRESH_POSITION_OPEN_SAFE_HANDOFF_GATE.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-CLOSE-ORDER-EXECUTION-GATE-C**。次Stepでは新しいruntime position read、
  operator readiness、sanitized close preview、close-specific confirmationが必須で、このStepのentry confirmationは再利用不可。
- 直前フェーズ:
  **Step 6G-PC-OX-R-FRESH-POST-ENTRY-POSITION-CONFIRMATION-GATE-C fresh accepted entry effect confirmed by runtime ONE_POSITION_OPEN / no retry / no close POST**。
  直前のfresh cycle entry gateはCASE 1で、fresh entry POSTはsafe summary上
  `fresh_entry_http_post_executed=true`、`fresh_entry_post_execution_count=1`、
  `fresh_entry_sanitized_result_category=RESULT_ACCEPTED_SANITIZED`、
  `fresh_entry_safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF`、
  `fresh_entry_retry_attempted=false`、`fresh_entry_repost_attempted=false`、
  `fresh_entry_second_post_attempted=false`、`close_post_executed=false`、
  `ledger/receipt=false`、`raw/ID/value exposure=false` として扱う。
  今回のfresh post-entry confirmation gateではcredential presenceをsafe booleanで再確認し、
  read-only runtime position checkを1回だけ実行した。safe status/countは
  `position_status=ONE_POSITION_OPEN`、`position_count_safe=1`、
  `has_exactly_one_position=true`。判定は
  `fresh_entry_effect_confirmed_by_position=true`、
  `fresh_position_confirmation_status=FRESH_ENTRY_EFFECT_CONFIRMED_POSITION_OPEN_SAFE`、
  `next_cycle_state=FRESH_POSITION_OPEN_SAFE`、
  `close_execution_gate_may_be_planned=true`、
  `close_execution_allowed_now=false`、`retry_allowed=false`、
  `repost_allowed=false`、`second_entry_allowed=false`、
  `close_post_allowed_now=false`、`level5_full_auto_cycle_completed=false`。
  このStepではfresh entry POST再実行、retry/repost、second POST、actual close POST、
  ledger update、receipt handoff、raw request/response、broker/API response、
  account/order/transaction/position ID、actual price/PnL、credential/signature/header値、
  `.env` は扱っていない。詳細は
  [STEP6G_FRESH_POST_ENTRY_POSITION_CONFIRMATION_GATE.md](STEP6G_FRESH_POST_ENTRY_POSITION_CONFIRMATION_GATE.md)。
- 直前フェーズ:
  **Step 6G-PC-OX-R-ENTRY-UNKNOWN-NO-POSITION-CLOSEOUT-GATE-C entry unknown/no-position closeout gate / safe state transition only / no retry / no close POST**。
  `backend/app/live_verification/live_order_real_entry_unknown_no_position_closeout_gate_controlled.py` は、
  previous entry POST safe summary（1回のみ、retry=false、second=false、close=false、unknown/blocked）と
  runtime position safe status/countを使い、`NO_POSITION` / count `0` の場合だけ
  `ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT` へ進めるsafe gateを提供する。fresh cycle may be planned は
  このStepでの実POST許可ではなく、別Stepで current position read / new signal / new operator readiness /
  new confirmation を取り直す条件を意味する。Level 5 state machineには
  `UNKNOWN_RESULT_SAFE_STOP -> ENTRY_UNKNOWN_NO_POSITION_CLOSED_OUT` を追加した。
  今回の実行ではruntime safe readが `UNKNOWN_FAIL_CLOSED` になったため、live closeout decisionはfail-closed。
  actual entry POST、retry/repost、second entry POST、actual close POST、ledger update、receipt handoff、
  raw request/response、broker/API response、account/order/transaction/position ID、credential/signature/header値は扱っていない。
  詳細は [STEP6G_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT_GATE.md](STEP6G_ENTRY_UNKNOWN_NO_POSITION_CLOSEOUT_GATE.md)。
- 直前フェーズ:
  **Step 6G-PC-OX-R-POST-ENTRY-POSITION-CONFIRMATION-GATE-C post-entry position confirmation / read-only runtime position safe read / no retry / no close POST**。
  直前のentry execution Stepは `CASE 3` で、safe summary上は
  `entry_http_post_executed=true`、`entry_post_execution_count=1`、
  `entry_retry_attempted=false`、`entry_second_post_attempted=false`、
  `close_post_executed=false`、`ledger_updated=false`、`receipt_handoff_executed=false`、
  `entry_sanitized_result_category=unknown/blocked` として扱う。今回のgateではcontrolled credential presenceが
  safe boolean上presentで、runtime position safe readを1回だけ実行し、safe status/countは
  `position_status=NO_POSITION`、`position_count_safe=0`。したがって
  `entry_effect_confirmed_by_position=false`、`position_confirmation_status=NO_POSITION_AFTER_ENTRY_POST`、
  `next_cycle_state=UNKNOWN_RESULT_SAFE_STOP`、`retry_allowed=false`、
  `second_entry_allowed=false`、`close_post_allowed_now=false`。actual entry POST再実行、retry/repost、second POST、
  actual close POST、ledger update、receipt handoff、raw request/response、broker/API response、
  account/order/transaction/position ID、credential/signature/header値は扱っていない。詳細は
  [STEP6G_POST_ENTRY_POSITION_CONFIRMATION_GATE.md](STEP6G_POST_ENTRY_POSITION_CONFIRMATION_GATE.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-ENTRY-UNKNOWN-NO-POSITION-CLOSEOUT-GATE-C**。
- 直前フェーズ:
  **Step 6G-PC-OX-R-LEVEL5-SIGNAL-ENTRY-CYCLE-GATE-C signal entry cycle gate / planning-only / no actual POST / no close POST**。
  runtime safe readで `NO_POSITION` / safe count `0` が確認済みの前提を受け、
  `backend/app/live_verification/live_order_real_step6g_level5_fast_mvp_controlled.py` に safe label input のsignal MVPと
  entry planning gateを接続した。`NO_POSITION + UPTREND + NORMAL spread + OK market` は `ENTRY_BUY`、
  `NO_POSITION + DOWNTREND + NORMAL spread + OK market` は `ENTRY_SELL`、`FLAT` は `HOLD`、unknown/wide/blockedや
  建玉あり/unknown/multipleではfail-closed。entry planningは固定safe labels `USD_JPY`、`100`、`MARKET`、
  `BUY/SELL`のみを返し、`entry_execution_allowed_now=false` を維持する。Level 5 cycleは
  `IDLE + NO_POSITION + ENTRY` を planning-only の `ENTRY_READY` へ進めるが、`ENTRY_SENT` には進まない。
  actual entry POST、close POST、retry/repost、second POST、ledger update、receipt handoff、raw market data、actual
  market value、raw request/response、broker/API response、account/order/transaction/position ID、credential/signature/header値は扱わない。
  詳細は [STEP6G_LEVEL5_SIGNAL_ENTRY_CYCLE_GATE.md](STEP6G_LEVEL5_SIGNAL_ENTRY_CYCLE_GATE.md)。
- 直前フェーズ:
  **Step 6G-PC-OX-R-LEVEL5-FAST-TRACK-MVP-FOUNDATION-C Level 5 fast-track MVP foundation / no actual POST / no close POST**。
  ledger/receipt planning CASE 1の後続として、Level 5最小MVPの土台を1つのsafe contract moduleへまとめた。
  `backend/app/live_verification/live_order_real_step6g_level5_fast_mvp_controlled.py` は、safe sanitized
  ledger-like record、review-only receipt summary、position read-only status、close route foundation、cycle state
  machine、signal MVP、fast-track configを扱う。実行対象ではなく、actual HTTP POST、close POST、order endpoint、
  `live_order_once`、retry/repost、second POST、ledger update、attempt counter persistence、actual receipt handoff、
  raw/ID/value取得、credential/signature/headers値取得は行わない。固定制約は `USD_JPY`、100 units、
  max open positions 1、entry/close各1回、human monitoring required、operator confirmation required、
  time/market gate required、kill switch required。position real sourceは未接続で、次Stepは
  **Step 6G-PC-OX-R-POSITION-READ-ONLY-ROUTE-WIRING-C**。
- 直前フェーズ:
  **Step 6G-PC-OX-R-LEDGER-RECEIPT-PLANNING-AND-SAFE-HANDOFF-SPRINT-C ledger/receipt planning + safe handoff**。
  直前の POST result reconciliation gate は CASE 1。one-shot POST は直前の実行Stepで最大1回だけ実行済みで、
  `post_execution_count=1`、`retry_attempted=false`、`second_post_attempted=false`、
  `sanitized_result_category=RESULT_ACCEPTED_SANITIZED`、
  `safe_reconciliation_status=RECONCILIATION_READY_NO_RECEIPT_HANDOFF` としてsafe summaryに閉じている。
  このplanning Stepではactual HTTP POST、retry/repost、second POST、ledger update、attempt counter persistence、
  actual receipt handoff、raw/ID/value取得・表示は行っていない。safe summaryだけを扱うledger相当の記録計画と
  review-only receipt summary計画は可能だが、実broker receiptやID付きreceiptが必要な処理はCodexでは取得せず
  manual broker UI checkへ切り離す。詳細は
  [STEP6G_POST_RESULT_RECONCILIATION_GATE.md](STEP6G_POST_RESULT_RECONCILIATION_GATE.md) と
  [STEP6G_LEDGER_RECEIPT_PLANNING_GATE.md](STEP6G_LEDGER_RECEIPT_PLANNING_GATE.md)。
  次の推奨Stepは
  **Step 6G-PC-OX-R-SAFE-SANITIZED-LEDGER-RECEIPT-EXECUTION-GATE**。次Stepでもretry/repost/second POSTは永久禁止で、
  raw/ID/valueが必要になった時点で停止する。
- 直前フェーズ: **Step 6G-PC-OX-R-SEALED-CREDENTIAL-SIGNING-PROVIDER-C sealed credential/signing/headers provider foundation / no actual HTTP POST**。
  SEALED-REQUEST-BODY-RESULT-MAPPER-C CASE 1（sealed request model、sealed body builder、source-owned client order id
  strategy skeleton、safe result mapper実装済み）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_sealed_credential_signing_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_sealed_credential_signing_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_SEALED_CREDENTIAL_SIGNING_CONTROLLED.md` を追加した。sealed credential/signing provider foundationは、
  sealed credential provider safe summary、sealed signing provider safe summary、sealed headers object、provider readiness
  summary、sealed request/body foundation connectionを提供する。新規moduleは `live_order_once`、broker/private API、
  HTTP client、env reader、credential reader、real signing helper、real header builder、ledger writer、receipt handoffを
  import/callしない。testsではsentinelを使ってrepr/asdict/rendererがcredential値、credential length/hash/fingerprint/
  metadata、signature値、signature length/hash/fingerprint、headers値、headers metadata/count、raw body、raw response、
  broker/API response、IDを出さないこと、missing sealed request/body、missing credential presence、unsafe exposure、
  execution/lifecycle attemptsをfail-closedにすることを確認する。このStepではactual HTTP POST、order endpoint、
  `live_order_once`、POST-specific confirmation取得、actual source callable、ledger-free source factory、ledger update、
  attempt counter persistence、actual receipt handoff、retry/repostには進んでいない。`approved_primitive_actual_source_available`
  はfalseのまま。次の推奨Stepは **Step 6G-PC-OX-R-LEDGER-FREE-POST-ONLY-SOURCE-FACTORY-C**。次Stepでもactual POST、
  POST-specific confirmation取得、credential/signature/header値表示、raw/ID/value露出、ledger/receipt/retry/repostは禁止。
- 直前フェーズ: **Step 6G-PC-OX-R-SEALED-REQUEST-BODY-RESULT-MAPPER-C sealed request/body/result mapper foundation / no actual HTTP POST**。
  POST-ONLY-SOURCE-REFACTOR-C CASE 2（一度にledger-free POST-only sourceを実装するには責務分離が大きすぎる）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_sealed_request_result_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_sealed_request_result_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_SEALED_REQUEST_RESULT_CONTROLLED.md` を追加した。sealed request/body/result foundationは、
  sealed request model、sealed body builder、sealed endpoint label、source-owned client order id strategy skeleton、
  safe result mapperを提供する。新規moduleは `live_order_once`、broker/private API、HTTP client、env reader、
  credential reader、signing/header provider、ledger writer、receipt handoffをimport/callしない。
  testsではsentinelを使ってrepr/asdict/rendererがraw body、endpoint actual value、headers/signature/credential value、
  raw response、broker/API response、IDを出さないこと、accepted/rejected/failed/timeout/unknown/unavailable mapping、
  no retry、no ledger、no receiptを確認する。このStepではactual HTTP POST、order endpoint、`live_order_once`、
  POST-specific confirmation取得、credential/signing/header生成、ledger update、attempt counter persistence、
  actual receipt handoff、retry/repostには進んでいない。`approved_primitive_actual_source_available` はfalseのまま。
- 直前フェーズ: **Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-ACTUAL-SOURCE-SUPPLY-C approved primitive actual source callable boundary implementation / no actual HTTP POST**。
  ONE-SHOT-POST-EXECUTION-GATE-RETRY-5 CASE 2（credential presence、safe route、sanitized preview、approved primitive
  boundary、approved primitive source boundary、controlled binding/executorは確認済み。ただしactual POSTに渡せる
  approved primitive actual source callable本体が未供給で停止）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_approved_primitive_actual_source_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_approved_primitive_actual_source_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_APPROVED_PRIMITIVE_ACTUAL_SOURCE_CONTROLLED.md` を追加した。actual source boundaryは
  availability safe summary、default/import/summary/construct no-execution guard、actual-source-to-approved-source
  adapter、approved primitive source/approved primitive/controlled binding/executor compatibilityを提供する。
- 直前フェーズ: **Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-SOURCE-SUPPLY-C approved primitive source supply boundary implementation / no actual HTTP POST**。
  ONE-SHOT-POST-EXECUTION-GATE-RETRY-4 CASE 2（POST-specific confirmationは取得できたが再利用不可、credential presence、
  safe route、sanitized preview、approved primitive boundary、controlled binding/executorは確認済み。ただしactual POSTに渡せる
  approved primitive source本体が未供給で停止）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_approved_primitive_source_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_approved_primitive_source_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_APPROVED_PRIMITIVE_SOURCE_CONTROLLED.md` を追加した。source boundaryはavailability safe summary、
  default/import/summary/construct no-execution guard、source-to-approved-primitive adapter、controlled binding/executor compatibilityを提供する。
  新規moduleは `live_order_once`、broker/private API、HTTP client、env reader、ledger writer、receipt handoffをimport/callしない。
  testsではfake/monkeypatch sourceのみを使い、approved primitive boundary、controlled real transport binding、controlled executorへの接続、
  one POST max、no retry、timeout fail-closed、ledger/receipt分離、raw/ID/value非露出を確認する。このStepではactual HTTP POST、
  order endpoint、`live_order_once`、POST-specific confirmation取得、直前POST-specific confirmation再利用、ledger update、
  attempt counter persistence、actual receipt handoff、retry/repost、fresh preflight再実行、final confirmation再取得には進んでいない。
  次の推奨Stepは **Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-5**。次Stepでも最初からPOSTしてはならず、
  safe preview提示後、このCodexセッション内の新しいPOST-specific confirmationを取得してから、条件が揃う場合だけ
  最大1回のHTTP POSTを検討する。RETRY-4のPOST-specific confirmationは再利用不可で、ledger/receipt/retry/repostは引き続き分離必須。
- 直前フェーズ: **Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-RESOLUTION-C approved primitive boundary implementation / no actual HTTP POST**。
  ONE-SHOT-POST-EXECUTION-GATE-RETRY-3 CASE 2（credential presence、safe route、sanitized preview、controlled real transport
  bindingは確認済みだが、current/default bindingが `approved_primitive_missing` で停止）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_approved_primitive_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_approved_primitive_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_APPROVED_PRIMITIVE_CONTROLLED.md` を追加した。approved primitive boundaryはavailability safe summary、
  default/import/summary/construct no-execution guard、controlled callable interface、sanitized primitive outcome mappingを提供する。
- 直前フェーズ: **Step 6G-PC-OX-R-ONE-SHOT-POST-REAL-TRANSPORT-BINDING-C controlled real transport binding implementation / no actual HTTP POST**。
  ONE-SHOT-POST-EXECUTION-GATE-RETRY CASE 2（safe route と sanitized previewは確認済みだが、actual HTTP POST用の
  承認済みreal transport bindingをrepo内で安全に確認できなかった）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_real_transport_binding_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_real_transport_binding_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_REAL_TRANSPORT_BINDING_CONTROLLED.md` を追加した。bindingはavailability safe summary、
  default/import/summary/construct no-execution guard、controlled executorに渡すtransport callable wrapper、
  sanitized transport outcome mappingを提供する。
- 直前フェーズ: **Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-RUNTIME-C safe one-shot POST execution route implementation / no actual HTTP POST**。
  ONE-SHOT-POST-EXECUTION-GATE CASE 2（safe one-shot POST execution route と executable sanitized order previewが未確認）を受けて、
  `backend/app/live_verification/live_order_real_one_shot_post_execution_controlled.py` と
  `backend/app/tests/test_live_verification_live_order_real_one_shot_post_execution_controlled.py`、
  `docs/STEP6G_ONE_SHOT_POST_EXECUTION_CONTROLLED.md` を追加した。実装したrouteは、sanitized executable order
  preview、POST-specific confirmation safe validator、transport注入型one-shot controlled executorの3層で構成する。
  このroute ready状態はPOST許可ではなく、actual transport bindingと新しいPOST-specific confirmationが別途必要。
- 直前フェーズ: **Step 6G-PC-OX-R-ONE-SHOT-POST-READY-GATE implementation / final ready gate before real one-shot POST / no HTTP POST**。
  FRESH-PREFLIGHT-CHECK-RETRY-3 CASE 1 PASS（fresh preflight executed exactly once / PASS / current=true / new=true /
  reused=false / stale=false / safe summary only）と FINAL-CONFIRMATION-GATE-RETRY CASE 1 PASS（final confirmation
  received=true / current-turn=true / new=true / one-time=true / reused=false / actual value stored=false / reported=false /
  logged=false）を前提に、POST直前の最終ready判定をsafe summaryへ閉じる独立gateを追加した。
  `backend/app/live_verification/live_order_real_one_shot_post_ready_gate_controlled.py` は
  `ONE_SHOT_POST_READY_GATE_CONTROLLED_NO_POST`、固定safe ready gate label、
  `ONE_SHOT_POST_READY_GATE_PASSED_NO_POST`、`ready_gate_passed`、
  `one_shot_post_execution_step_may_be_planned` を扱う。passingでも
  `actual_post_permitted_now=false`、`post_allowed_this_step=false`、`http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false`、`ledger_updated=false`、
  `attempt_counter_persisted=false`、`actual_receipt_handoff_executed=false` を維持する。
  missing fresh preflight PASS、missing current-turn/new/one-time final confirmation、confirmation reuse、
  post guard/final readiness/final exec stack/sanitized result missing、retry allowed、timeout fail-closed missing、
  POST/order endpoint/`live_order_once`、ledger/attempt counter、actual receipt/handoff、raw/ID/value exposureは
  fail-closed。詳細は [STEP6G_ONE_SHOT_POST_READY_GATE_CONTROLLED.md](STEP6G_ONE_SHOT_POST_READY_GATE_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE dedicated real POST step /
  requires new explicit POST-specific confirmation first**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-FINAL-CONFIRMATION-GATE-RETRY final confirmation acquisition / no HTTP POST**。
  fresh preflight PASS後、safe final confirmation gateを使ってcurrent-turn / new / one-time / non-reused final confirmationを
  safe boolean/statusだけで成立確認した。confirmation phrase actual valueは保存・表示・報告・ログ出力していない。
  `post_allowed_this_step=false`、`http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false`、
  `ledger_updated=false`、`attempt_counter_persisted=false`、`actual_receipt_handoff_executed=false` を維持した。
  final confirmation成立も同Step内のPOST許可ではない。
- 直前フェーズ: **Step 6G-PC-OX-R-FRESH-PREFLIGHT-EXECUTION-RUNTIME-E actual safe fresh preflight execution mode implementation完了 / execute mode implemented / no actual fresh preflight run / no HTTP POST / no final confirmation**。
  FRESH-PREFLIGHT-CHECK-RETRY-2 CASE 3の原因（CLIがadapter summary onlyで、fresh preflightをnew/current/non-reusedとして実行するsafe execution modeが未整備）を受けて、
  `backend/app/live_verification/live_order_real_fresh_preflight_execution_controlled.py` と
  `backend/app/live_verification/run_fresh_preflight_execution_controlled.py` を更新した。default / adapter-summary CLIは引き続き
  `cd backend && python3 -m app.live_verification.run_fresh_preflight_execution_controlled --adapter-summary-only`。
  次Step用の明示実行CLIは
  `cd backend && python3 -m app.live_verification.run_fresh_preflight_execution_controlled --execute-once --safe-summary-only`。
  このStepではexecute modeを実環境で実行していない。adapter/execute modeはconsolidated fresh preflight runtime resultに接続し、
  safe label / safe status / safe boolean / safe count / blocked reason labelsだけを出力する。
  `fresh_preflight_execute_mode_available=true` は、次Stepでsafe execute-once commandを使えることだけを意味し、
  fresh preflight実行済み、POST許可、final confirmation済み、ledger更新済み、actual receipt handoff済み、
  実資金Step 6G再試行可を意味しない。IWにも `fresh_preflight_execution_adapter_ready` gateを維持し、
  missing runtime / missing mapping / unsafe renderer / unknown / failed / timeout / unavailable / stale / reused /
  retry allowed / POST/order endpoint/`live_order_once` / final confirmation / ledger / actual receipt / raw/ID/value
  exposureをfail-closedにする。詳細は
  [STEP6G_FRESH_PREFLIGHT_EXECUTION_CONTROLLED.md](STEP6G_FRESH_PREFLIGHT_EXECUTION_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-FRESH-PREFLIGHT-CHECK-RETRY-3 fresh preflight execution with actual safe execute mode /
  no POST / no final confirmation**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-FRESH-PREFLIGHT-RUNTIME-C consolidated safe fresh preflight runtime implementation完了 / runtime route implementation only / no fresh preflight execution / no HTTP POST / no final confirmation**。
  FRESH-PREFLIGHT-CHECK CASE 3の原因（complete safe fresh preflight runtime route未整備）を受けて、
  public market / private read-only / local-static checks、final exec stack readiness、POST guard、no-order guardを
  safe label / safe status / safe boolean / safe count / blocked reason labelsだけへ統合するruntime contractを追加した。
  `backend/app/live_verification/live_order_real_fresh_preflight_runtime_controlled.py` は
  `FRESH_PREFLIGHT_RUNTIME_CONTROLLED_IMPLEMENTATION_ONLY`、
  `FRESH_PREFLIGHT_RUNTIME_READY_NO_EXECUTION`、`fresh_preflight_runtime_ready`、
  safe route labels、safe account/open-position/active-order countsを扱うが、fresh preflight executionそのものは行わない。
  IWにも `fresh_preflight_runtime_ready` gateを最小連携し、public/private/local/final exec stack/post guard/no-order guard missing、
  unknown / failed / timeout / unavailable / stale / reused、POST/order endpoint/`live_order_once`、final confirmation、ledger、
  actual receipt/handoff、raw/broker/API/ID/value exposureをfail-closedにする。
  詳細は [STEP6G_FRESH_PREFLIGHT_RUNTIME_CONTROLLED.md](STEP6G_FRESH_PREFLIGHT_RUNTIME_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-FRESH-PREFLIGHT-CHECK-RETRY fresh preflight execution with consolidated runtime /
  no POST / no final confirmation execution**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-FINAL-EXEC-STACK-C dry-run only one-shot execution stack implementation完了 / dry-run only / fake no-network transport / no API call / no POST / no live_order_once / no real transport**。
  FINAL-READINESS-V CASE 1 PASSの判断後、final readiness / POST guard / sanitized resultがsafe boundaryとして成立している前提で、
  dry-run one-shot execution orchestrator、fake/no-network transport path、dry-run one-shot decision、dry-run sanitized result /
  reconciliation path、dry-run receipt handoff preview、dry-run ledger / attempt counter previewを1つのfinal exec stack controlled
  contractへ統合した。FINAL-EXEC-STACK-Cでは
  `backend/app/live_verification/live_order_real_final_exec_stack_controlled.py` を追加し、
  `FINAL_EXEC_STACK_DRY_RUN_ONLY`、固定safe dry-run stack label、
  `FINAL_EXEC_STACK_READY_DRY_RUN_ONLY`、`dry_run_stack_ready`、`dry_run_mode=true`、
  `fake_transport_used=true`、`network_transport_used=false`、`real_transport_used=false`、
  `one_shot_post_allowed=false`、safe dry-run preview labels、safe blocked reasonsだけを扱う。
  このStepはdry-run only implementationであり、API call、HTTP POST、order endpoint、`live_order_once`、
  real transport、network I/O、fresh preflight execution、final confirmation execution、ledger更新、attempt counter永続化、
  actual result receipt、actual receipt handoff、実資金Step 6G再試行には進まない。credential値、signature値、headers値、
  raw request、raw response、broker/API response実体、endpoint actual value、real ID、account ID、order ID、transaction ID、
  confirmation phrase actual value、Step 4 approval phrase actual value、ledger state actual value、approval command actual valueは
  result / renderer / asdict / docsに含めない。dry-run stack readyでもPOST、API、order endpoint、`live_order_once`、
  fresh preflight済み、final confirmation済み、ledger更新済み、actual receipt handoff済み、実資金Step 6G再試行可にはならない。
  Step 6G-IWにも `final_exec_stack_dry_run_ready` gateを最小連携し、final readiness missing、one-shot POST allowed、
  network/real transport、API/POST/order endpoint/`live_order_once`、fresh/final execution、ledger/attempt persistence、
  actual receipt/handoff、raw/broker/API/ID/value exposureをfail-closedで検査する。
  詳細は [STEP6G_FINAL_EXEC_STACK_CONTROLLED.md](STEP6G_FINAL_EXEC_STACK_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-FINAL-EXEC-STACK-V dry-run one-shot execution stack boundary review /
  no API call / no POST / no code change**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-FINAL-READINESS-C consolidated final readiness contract implementation完了 / contract implementation only / no API call / no POST / no fresh preflight execution / no final confirmation execution**。
  FINAL-GATE CASE 1の判断後、POST guard resultとsanitized result / reconciliation resultを前提に、
  fresh preflight required、final confirmation required、ledger / attempt counter required、actual receipt handoff
  required、one-shot POST readiness blockedを1つのfinal readiness controlled contractへ統合した。
  FINAL-READINESS-Cでは `backend/app/live_verification/live_order_real_final_readiness_controlled.py` を追加し、
  `FINAL_READINESS_CONTROLLED_IMPLEMENTATION_ONLY`、固定safe final readiness label、
  `FINAL_READINESS_READY_NO_POST`、final readiness controlled ready boolean、safe blocked reasonsだけを扱う。
  fresh preflightはrequiredだが未実行、final confirmationはrequiredだが未取得、ledger / attempt counterはrequired
  だが更新・永続化しない、actual receipt handoffはrequiredだが未実行、`one_shot_post_allowed=false`を固定する。
  このStepはcontract implementationであり、API call、HTTP POST、order endpoint、`live_order_once`、
  fresh preflight execution、final confirmation execution、ledger更新、attempt counter永続化、actual result receipt、
  actual receipt handoff、実資金Step 6G再試行には進まない。credential値、signature値、headers値、raw request、
  raw response、broker/API response実体、endpoint actual value、real ID、account ID、order ID、transaction ID、
  confirmation phrase actual value、Step 4 approval phrase actual value、ledger state actual value、approval command
  actual valueはresult / renderer / asdict / docsに含めない。final readiness readyでもPOST、API、order endpoint、
  `live_order_once`、fresh preflight済み、final confirmation済み、ledger更新済み、actual receipt handoff済み、
  実資金Step 6G再試行可にはならない。Step 6G-IWにも `final_readiness_controlled_ready` gateを最小連携し、
  missing / unknown / failed / unavailable / timeout / stale / previous-turn / reused / fresh preflight missing or executed /
  final confirmation missing or executed / ledger update / attempt counter persistence / actual receipt handoff / API / POST /
  order endpoint / `live_order_once` / unsafe exposureをfail-closedで検査する。
  詳細は [STEP6G_FINAL_READINESS_CONTROLLED.md](STEP6G_FINAL_READINESS_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-FINAL-READINESS-V final readiness contract boundary review /
  no API call / no POST / no code change**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-RESULT-C sanitized POST result / reconciliation contract implementation完了 / contract implementation only / no API call / no POST / no live_order_once**。
  POST-GUARD-V CASE 1の判断後、controlled POST guard resultを前提に、将来POST result / reconciliationを
  safe label / safe status / safe boolean / sanitized categoryだけへ閉じるcontract implementationを追加した。
  RESULT-Cでは `backend/app/live_verification/live_order_real_sanitized_post_result.py` を追加し、
  `SANITIZED_POST_RESULT_CONTRACT_ONLY`、固定safe POST result label、固定safe reconciliation label、
  `SANITIZED_RESULT_READY_NO_RECEIPT`、safe result category、safe reconciliation status、
  sanitized result ready boolean、reconciliation ready boolean、safe blocked reasonsだけを扱う。このStepの
  sanitized result / reconciliationはPOST実行後の実レスポンス処理ではなく、将来の結果境界contractであり、
  API call、HTTP POST、order endpoint、`live_order_once`、raw request generation、raw response receipt、
  broker/API response parsing、fresh preflight execution、final confirmation execution、actual result receipt、
  actual receipt handoff、ledger更新、attempt counter永続化、実資金Step 6G再試行には進まない。credential値、
  signature値、headers値、raw request、raw response、request body、response body、broker/API response実体、
  endpoint actual value、real ID、account ID、order ID、transaction ID、confirmation phrase actual value、
  ledger state actual valueはresult / renderer / asdict / docsに含めない。sanitized result readyでもPOST、
  API、order endpoint、`live_order_once`、fresh preflight、final confirmation、ledger更新、actual receipt
  handoff、実資金Step 6G再試行には進めない。Step 6G-IWにも `sanitized_post_result_ready` gateを最小連携し、
  unknown / failed / unavailable / timeout / rejected / partial / ambiguous / unmatched / stale / previous-turn /
  reused / raw response exposure / broker API response exposure / ID exposure / ledger update / actual receipt /
  API / POST / order endpoint / `live_order_once` をfail-closedで検査する。
  詳細は [STEP6G_SANITIZED_POST_RESULT.md](STEP6G_SANITIZED_POST_RESULT.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-RESULT-V sanitized POST result / reconciliation contract boundary review /
  no API call / no POST / no code change**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-POST-GUARD-C one POST max / no retry / timeout fail-closed guard implementation完了 / guard implementation only / no API call / no POST / no live_order_once**。
  TRANSPORT-V CASE 1の判断後、controlled transport resultを前提に、POST前guard readinessを
  safe label / safe status / safe booleanだけへ閉じるcontrolled implementationを追加した。POST-GUARD-Cでは
  `backend/app/live_verification/live_order_real_post_guard_controlled.py` を追加し、
  `POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY`、固定safe POST guard label、
  `POST_GUARD_READY_NO_POST`、post guard ready boolean、safe blocked reasons、one POST max enforced /
  no retry enforced / timeout fail-closed enforced / fresh preflight required / final confirmation required /
  sanitized result required booleansだけを扱う。このStepのPOST guardはPOST実行前の安全契約であり、
  API call、HTTP POST、order endpoint、`live_order_once`、raw request generation、raw response receipt、
  fresh preflight execution、final confirmation execution、actual checker execution、actual result receipt、
  actual receipt handoff、ledger更新、実資金Step 6G再試行には進まない。credential値、signature値、
  headers値、raw request、raw response、request body、response body、endpoint actual value、order endpoint
  actual value、real ID、account ID、order ID、broker/API response、confirmation phrase actual value、
  ledger state actual valueはresult / renderer / asdict / docsに含めない。post guard readyでもPOST、
  API、order endpoint、`live_order_once`、fresh preflight、final confirmation、実資金Step 6G再試行には
  進めない。Step 6G-IWにも `post_guard_controlled_ready` gateを最小連携し、unknown / failed /
  unavailable / timeout / rejected / stale / previous-turn / reused / retry attempted / second POST attempted /
  multiple POST attempts / API / POST / order endpoint / `live_order_once` をfail-closedで検査する。
  詳細は [STEP6G_POST_GUARD_CONTROLLED.md](STEP6G_POST_GUARD_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-POST-GUARD-V one POST max / no retry / timeout fail-closed guard
  boundary review / no API call / no POST / no code change**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-TRANSPORT-C transport controlled implementation完了 / safe label-status-boolean only / no API call / no POST / no live_order_once**。
  TRANSPORT-GATE CASE 1の判断後、controlled signing/headers resultを前提に、transport readinessを
  safe label / safe status / safe booleanだけへ閉じるcontrolled implementationを追加した。TRANSPORT-Cでは
  `backend/app/live_verification/live_order_real_transport_controlled.py` を追加し、
  `TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY`、固定safe transport label、
  `TRANSPORT_READY_NO_API_NO_POST`、transport controlled ready boolean、safe blocked reasons、one POST max /
  no retry / fresh preflight / final confirmation / sanitized result required booleansだけを扱う。このStepの
  transportはAPI/POST用の実transportではない。credential値、signature値、headers値、raw request、raw response、
  request body、response body、endpoint actual value、order endpoint actual value、real ID、account ID、order ID、
  broker/API responseはresult / renderer / asdict / docsに含めない。transport readyでもPOST、API、
  order endpoint、`live_order_once`、actual checker execution、actual result receipt、actual receipt handoff、
  fresh preflight、final confirmation、実資金Step 6G再試行には進めない。Step 6G-IWにも
  `transport_controlled_ready` gateを最小連携し、missing / unknown / failed / unavailable / timeout /
  unsafe exposure / credential or signature or headers or raw request or raw response exposure / API / POST /
  order endpoint / `live_order_once` をfail-closedで検査する。詳細は
  [STEP6G_TRANSPORT_CONTROLLED.md](STEP6G_TRANSPORT_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-TRANSPORT-V transport controlled implementation boundary review /
  no API call / no POST / no code change**。実資金Step 6G再試行はまだ不可。
- 直前フェーズ: **Step 6G-PC-OX-R-SIGN-C signing and headers controlled implementation完了 / safe label-status-boolean only / no signature value exposure / no headers value exposure / no API / no POST**。
  SIGN-GATE CASE 1の判断後、controlled credential injection resultを前提に、signing / headers readinessを
  safe label / safe status / safe booleanだけへ閉じるcontrolled implementationを追加した。SIGN-Cでは
  `backend/app/live_verification/live_order_real_signing_headers_controlled.py` を追加し、
  `SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY`、固定safe signing label、固定safe headers label、
  `SIGNING_HEADERS_READY_NO_TRANSPORT`、signing/headers controlled ready booleans、safe blocked reasonsだけを扱う。
  このStepのsigning / headersはAPI/POST用の実署名値生成・実headers値生成ではない。credential値、
  raw handle実体、credential length/hash/fingerprint、credential metadata実体、env actual name、signature値、
  headers値、signature length/hash/fingerprint、headers metadata実体、raw request、raw response、real IDは
  result / renderer / asdict / docsに含めない。signing readyでもPOST、API、real transport、order endpoint、
  `live_order_once`、actual checker execution、actual result receipt、actual receipt handoff、fresh preflight、
  final confirmation、実資金Step 6G再試行には進めない。Step 6G-IWにも
  `signing_headers_controlled_ready` gateを最小連携し、missing / unknown / failed / unavailable / timeout /
  unsafe exposure / credential or signature or headers exposure / transport or API / POST or order / `live_order_once`
  をfail-closedで検査する。詳細は
  [STEP6G_SIGNING_HEADERS_CONTROLLED.md](STEP6G_SIGNING_HEADERS_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-SIGN-V signing and headers controlled implementation boundary review /
  no signature value exposure / no API / no POST / no code change**。
- 直前フェーズ: **Step 6G-PC-OX-R-CRED-I-C credential injection controlled implementation完了 / opaque handle only / no signing / no API / no POST**。
  CRED-I-GATE CASE 1の判断後、credential injectionをsafe boundary内で扱うcontrolled implementationを追加した。
  CRED-I-Cでは `backend/app/live_verification/live_order_real_credential_injection_controlled.py` を追加し、
  `CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY`、固定safe handle label、
  `CREDENTIAL_INJECTION_READY_NO_SIGNING`、credential injection ready boolean、safe blocked reasonsだけを扱う。
  このStepのinjectionはreal signing用のcredential値注入ではない。credential値、raw handle実体、length、hash、
  fingerprint、metadata実体、env actual name、headers、signature、raw request、raw response、real IDは
  result / renderer / asdict / docsに含めない。injection readyでもPOST、signing、headers generation、API、
  `live_order_once`、actual checker execution、actual result receipt、actual receipt handoff、fresh preflight、
  final confirmation、実資金Step 6G再試行には進めない。Step 6G-IWにも
  `credential_injection_controlled_ready` gateを最小連携し、missing / unknown / failed / unavailable / timeout /
  unsafe exposure / value or raw handle or metadata exposure / signing or headers / API or POST / `live_order_once`
  をfail-closedで検査する。詳細は
  [STEP6G_CREDENTIAL_INJECTION_CONTROLLED.md](STEP6G_CREDENTIAL_INJECTION_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-CRED-I-V credential injection controlled implementation boundary review /
  no credential value exposure / no signing / no API / no POST / no code change**。
- 直前フェーズ: **Step 6G-PC-OX-R-CRED-P-C credential presence check controlled implementation完了 / env access only for presence / no value exposure / no API / no POST**。
  ENV-GATE CASE 1の判断後、credential presenceをsafe booleanへ変換するcontrolled implementationを追加した。
  CRED-P-Cでは `backend/app/live_verification/live_order_real_credential_presence_controlled.py` を追加し、
  `CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY`、required credential safe labels、
  per-safe-label present boolean、all required present boolean、safe status、blocked reasonsだけを扱う。
  このStepで許可したenv accessはprocess envのpresence判定のみで、`.env` / `.env.example` は読まない。
  credential値、length、hash、fingerprint、metadata実体、env actual name、headers、signature、raw request、
  raw response、real IDはresult / renderer / asdict / docsに含めない。presence trueでもPOST、signing、API、
  `live_order_once`、actual checker execution beyond presence、actual result receipt、actual receipt handoff、
  fresh preflight、final confirmation、実資金Step 6G再試行には進めない。Step 6G-IWにも
  `credential_presence_controlled_ready` gateを最小連携し、missing / unknown / failed / unavailable / timeout /
  unsafe exposure / API or POST / signing or transportをfail-closedで検査する。詳細は
  [STEP6G_CREDENTIAL_PRESENCE_CONTROLLED.md](STEP6G_CREDENTIAL_PRESENCE_CONTROLLED.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-CRED-P-V credential presence controlled implementation boundary review /
  no credential value exposure / no API / no POST / no code change**。
- 直前フェーズ: **Step 6G-PC-OX-R-RH-C receipt handoff non-execution boundary consolidation完了 / shortest safe route / no env / no actual receipt / no API / no POST**。
  Step 6G-PC-OX-R-AL完了後の最短安全ルートとして、receipt skeleton / policy hardening / lifecycle contractの
  ready状態を統合するnon-execution boundary contractを追加した。RH-Cでは
  `backend/app/live_verification/live_order_real_operator_result_handoff_non_execution_boundary.py` を追加し、
  `OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY_SKELETON_ONLY`、boundary declared、
  receipt/policy/lifecycle contract ready、receipt/policy/lifecycle ready、actual handoff prohibited、
  actual receipt prohibited、actual checker execution prohibited、env access prohibited、credential read/injection
  prohibited、API/POST/live_order_once prohibited、fresh preflight/final confirmation prohibited、safe category only、
  raw/detail/identifier prohibited、ready flags are not POST permission、ready flags are not actual handoff permission
  だけを扱う。Step 6G-IWにも `operator_result_handoff_non_execution_boundary_ready` gateを最小連携し、
  receipt/policy/lifecycle readyがtrueでもactual receipt handoff、actual result receipt、checker execution、
  env access、credential read/injection、API、POST、order endpoint、`live_order_once`、real signing、real transport、
  fresh preflight、final confirmation、実資金Step 6G再試行には進めないことをfail-closedで検査する。
  このStepはsafe pace-up policy上の低リスクcontract/docs/tests領域として、独立review-only Stepを挟まず、
  実装・自己境界レビュー・検証・次Step提案を1Step内で完了した。詳細は
  [STEP6G_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY.md](STEP6G_OPERATOR_RESULT_HANDOFF_NON_EXECUTION_BOUNDARY.md)。
  次の推奨Stepは **Step 6G-PC-OX-R-ENV-GATE env access decision gate / review-only / no env read /
  no credential read / no API / no POST**。この次Stepでもまだenv / `.env` を読まない。
- 直前フェーズ: **Step 6G-PC-OX-R-AL actual receipt lifecycle contract skeleton完了 / still no env / no actual receipt / no API / no POST**。
  Step 6G-PC-OX-R-AH-VのCASE 1 PASS後の次Stepとして、将来のoperator result handoff receiptを扱う前の
  lifecycle state / event / transition policyをsafe enum / dataclass / pure functionとして追加した。
  R-ALでは `backend/app/live_verification/live_order_real_operator_result_handoff_lifecycle.py` を追加し、
  `OPERATOR_RESULT_HANDOFF_LIFECYCLE_SKELETON_ONLY`、lifecycle declared、transition policy declared、
  one-time/fresh/current-turn/non-reuse/previous-turn prohibited、stale/timeout/expired prohibited、
  non-raw/non-detail/non-identifier、safe category only、`READY_CONFIRMED` is not POST permission、
  `NOT_PROVIDED` is not actual result receipt、actual receipt handoff executed=false、actual result receipt
  received=false、actual checker execution performed=false、final confirmation received=false、fresh preflight
  executed=false、env access=false、credential read=false、API/POST/live_order_once flags=falseだけを扱う。
  Step 6G-IWにも `operator_result_handoff_lifecycle_ready` gateを最小連携し、receipt gateの前に
  fail-closedで検査する。このStepでもactual receipt handoff、actual result receipt、actual checker execution、
  env / `.env` access、credential read/injection、API、read-only API、public API、Private API、HTTP POST、
  order endpoint、`live_order_once`、real signing、real transport、fresh preflight、final confirmation、
  実資金Step 6G再試行には進んでいない。詳細は
  [STEP6G_OPERATOR_RESULT_HANDOFF_LIFECYCLE.md](STEP6G_OPERATOR_RESULT_HANDOFF_LIFECYCLE.md)。
  Step 6G-PC-OX-R-AH-VはCASE 1 PASSで完了し、次StepとしてStep 6G-PC-OX-R-ALへ進んだ。
- 直前フェーズ: **Step 6G-PC-OX-R-AH actual receipt handoff policy hardening完了 / still no env / no actual execution / no API / no POST**。
  Step 6G-SPP-Dで固定した [STEP6G_SAFE_PACE_POLICY.md](STEP6G_SAFE_PACE_POLICY.md) を前提に、将来の
  actual receipt handoffへ進む前のpolicy / lifecycle / freshness / non-reuse / current-turn / no-raw /
  no-detail / no-identifier boundaryをpure contractとして追加した。R-AHでは
  `backend/app/live_verification/live_order_real_operator_result_handoff_policy.py` を追加し、
  `OPERATOR_RESULT_HANDOFF_POLICY_SKELETON_ONLY`、policy declared、receipt lifecycle policy declared、
  freshness/one-time/non-reuse/current-turn/previous-turn prohibited、non-raw/non-detail/non-identifier、
  safe category only、`READY_CONFIRMED` is not POST permission、`NOT_PROVIDED` is not actual receipt、
  actual receipt handoff executed=false、actual result receipt received=false、actual checker execution performed=false、
  env access=false、credential read=false、API/POST/live_order_once flags=falseだけを扱う。Step 6G-IWにも
  `operator_result_handoff_policy_ready` gateを最小連携し、receipt gateの前にfail-closedで検査する。
  このStepでもactual receipt handoff、actual result receipt、actual checker execution、env / `.env` access、
  credential read/injection、API、read-only API、public API、Private API、HTTP POST、order endpoint、
  `live_order_once`、real signing、real transport、fresh preflight、final confirmation、実資金Step 6G再試行には
  進んでいない。詳細は [STEP6G_OPERATOR_RESULT_HANDOFF_POLICY.md](STEP6G_OPERATOR_RESULT_HANDOFF_POLICY.md)。
  Step 6G-PC-OX-R-AH-VはCASE 1 PASSで完了し、次StepとしてStep 6G-PC-OX-R-ALへ進んだ。
- 直前フェーズ: **Step 6G-SPP-D safe pace-up policy documentation完了 / docs only / no env / no API / no POST**。
  Step 6G-PC-OX-R-A-VはCASE 1 PASSで、operator result handoff receipt skeletonはreceipt-only /
  skeleton-only / no env / no credential / no actual execution / no API / no POSTとして安全に閉じている。
  Step 6G-SPP-Dでは [STEP6G_SAFE_PACE_POLICY.md](STEP6G_SAFE_PACE_POLICY.md) を追加し、今後のCodex
  作業でsafe pace-up policyをrepo docs参照にできるよう固定した。safe pace-up policyは重複調査、
  過剰レビュー、細かすぎるStep分割を減らすための方針であり、未レビュー領域へ進む許可ではない。
  env / `.env` access、credential read/injection、actual checker execution、actual result receipt、API、
  read-only API、public API、Private API、HTTP POST、order endpoint、`live_order_once`、real signing、
  real transport、fresh preflight、final confirmation、実資金Step 6G再試行に近づく場合は停止する。
  `READY_CONFIRMED`はPOST許可・final confirmation・fresh preflight済みを意味せず、`NOT_PROVIDED`は
  actual result receiptではない。今後の最終報告には、次Step案とChatGPTへ貼れる一括引き継ぎ要約を含める。
- 直前フェーズ: **Step 6G-PC-OX-R-A operator result handoff artifact / receipt skeleton完了 / no env / no actual execution / no API / no POST**。
  Step 6G-PC-OX-R-C-VのCASE 2結論後の次Stepとして、operator側で将来確認したsafe categoryを
  Codexへ渡すためのone-time / fresh / non-reuse / non-raw / non-detail receipt contractを追加した。
  Step 6G-PC-OX-R-Aでは
  `backend/app/live_verification/live_order_real_operator_result_handoff_receipt.py` を追加し、
  `OPERATOR_RESULT_HANDOFF_RECEIPT_SKELETON_ONLY`、receipt contract/boundary declared、receipt one-time/fresh/
  non-reuse/non-raw/non-detail required、operator execution result category contract ready、operator executed
  execution boundary ready、operator result handoff safe、safe category label/allowed、receipt current turn/fresh、
  receipt stale/reused/previous-turn/expired/timeout/unknown/failed/unavailable=false、receipt raw/detail=false、
  receipt id/token/nonce/hash/fingerprint/length=false、actual execution/Codex execution=false、env access/credential
  read=false、real signature / real headers / HTTP POST capability=false flagsだけを扱う。ready not providedでは
  `OPERATOR_RESULT_HANDOFF_RECEIPT_READY_NOT_PROVIDED`、`operator_result_category=NOT_PROVIDED`、
  `receipt_provided=false`、`receipt_category_confirmed=false`、`post_allowed_this_step=false`、
  `post_executed=false` を維持する。ready confirmedでは
  `OPERATOR_RESULT_HANDOFF_RECEIPT_READY_CONFIRMED_NO_POST` だが、READY_CONFIRMED receiptはPOST許可ではなく、
  `can_generate_real_signature=false`、`can_generate_real_headers=false`、`can_execute_http_post=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。unknown / failed / unavailable / stale /
  timeout / reused / previous-turn receiptは必ずblockする。Step 6G-IWにも最小連携し、
  `operator_result_handoff_receipt_ready` gateをready条件に加えた。このStepでは実API、read-only API、
  public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、実credential値取得、credential presence実環境確認、env / `.env` access、checker execution、
  operator actual result受信処理、receipt raw/id/token/nonce/hash/fingerprint/length保存・表示、operator result
  detail/raw保存・表示、checker result detail保存・表示、env variable names保存・表示、credential metadata取得・表示、
  実credential injection、実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。
  future actual receipt handoff / checker execution / env access / real credential injection / real signing /
  real transportは別Stepで、新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_OPERATOR_RESULT_HANDOFF_RECEIPT.md](STEP6G_OPERATOR_RESULT_HANDOFF_RECEIPT.md)。
- 直前フェーズ: **Step 6G-PC-OX-R-C operator-side execution result category contract完了 / no env / no actual execution / no API / no POST**。
  Step 6G-PC-OX-E-B-VのCASE 2結論後の次Stepとして、operator側で将来実行したchecker resultを
  Codexへ渡す際のsafe categoryだけをpure contractとして追加した。Step 6G-PC-OX-R-Cでは
  `backend/app/live_verification/live_order_real_operator_execution_result_category_contract.py` を追加し、
  `OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY`、allowed category set declared、operator executed execution
  boundary ready、operator result handoff safe、operator checker workflow ready、safe enum labels
  `NOT_PROVIDED` / `READY_CONFIRMED` / `BLOCKED_UNKNOWN` / `BLOCKED_FAILED` / `BLOCKED_UNAVAILABLE` /
  `BLOCKED_STALE` / `BLOCKED_TIMEOUT` / `BLOCKED_REUSED` / `BLOCKED_PREVIOUS_TURN` /
  `BLOCKED_UNSAFE_DETAIL` / `BLOCKED_UNSUPPORTED` だけを扱う。ready no resultでは
  `OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_NO_RESULT`、`operator_result_category=NOT_PROVIDED`、
  `operator_result_provided=false`、`operator_result_ready_confirmed=false`、`post_allowed_this_step=false`、
  `post_executed=false` を維持する。ready confirmedでは
  `OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_READY_CONFIRMED_NO_POST` だが、READY_CONFIRMEDはPOST許可ではなく、
  `can_generate_real_signature=false`、`can_generate_real_headers=false`、`can_execute_http_post=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。unknown / failed / unavailable / stale /
  timeout / reused / previous-turn categoriesは必ずblockする。Step 6G-IWにも最小連携し、
  `operator_execution_result_category_contract_ready` gateをready条件に加えた。このStepでは実API、read-only API、
  public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、実credential値取得、credential presence実環境確認、env / `.env` access、checker execution、
  operator actual result受信処理、operator result detail/raw保存・表示、checker result detail保存・表示、
  env variable names保存・表示、credential metadata取得・表示、実credential injection、実署名値生成、
  実headers値生成、raw request/response表示・保存、real ID表示を行わない。future actual checker execution /
  env access / real credential injection / real signing / real transportは別Stepで、新しいfinal confirmationと
  fresh preflightが必要。詳細は
  [STEP6G_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT.md](STEP6G_OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT.md)。
- 直前フェーズ: **Step 6G-PC-OX-E-B operator-executed execution boundary formalization完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-X-P-RのCASE 2結論後の次Stepとして、operator側の将来actual checker executionと
  Codex側safe boolean/category handoffの正式境界をpure skeletonとして追加した。Step 6G-PC-OX-E-Bでは
  `backend/app/live_verification/live_order_real_operator_executed_execution_boundary.py` を追加し、
  `OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY`、boundary declared、operator execution boundary
  declared、operator execution must be outside Codex、Codex execution forbidden、checker execution implementation
  skeleton ready、checker execution contract ready、operator result handoff safe、operator checker workflow ready、
  operator execution performed=false、Codex execution performed=false、env access requested=false、Codex env access
  requested=false、actual environment presence check performed=false、credential read performed=false、credential
  values/metadata present=false、operator result provided=false、operator result safe boolean/category only=true、
  operator result detail/raw=false、operator result unknown/failed/unavailable/stale/timeout=false、operator result
  reused/previous-turn=false、checker result detail=false、env variable names=false、sentinel value=false、real signature /
  real headers / HTTP POST capability=false flagsだけを扱う。readyでは
  `OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK`、
  `operator_executed_execution_boundary_ready=true`、`operator_execution_must_be_outside_codex=true`,
  `codex_execution_forbidden=true`、`operator_execution_performed=false`、`codex_execution_performed=false`、
  `env_access_requested=false`、`actual_environment_presence_check_performed=false`、
  `credential_read_performed=false`、`operator_result_provided=false`、`operator_result_raw_value_present=false`、
  `operator_result_timeout=false`、`post_allowed_this_step=false`、`post_executed=false` を維持する。unknown /
  failed / unavailable / stale / timeout / reused / previous-turnは必ずblockする。Step 6G-IWにも最小連携し、
  operator executed execution boundary readyをready条件に加えた。このStepでは実API、read-only API、public API、
  Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、
  実credential値取得、credential presence実環境確認、env / `.env` access、checker execution、operator result
  detail/raw保存・表示、checker result detail保存・表示、env variable names保存・表示、credential metadata取得・表示、
  実credential injection、実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。
  future actual checker execution / env access / real credential injection / real signing / real transportは別Stepで、
  新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_OPERATOR_EXECUTED_EXECUTION_BOUNDARY.md](STEP6G_OPERATOR_EXECUTED_EXECUTION_BOUNDARY.md)。
- 直前フェーズ: **Step 6G-PC-X-I-S checker execution implementation skeleton完了 / no env / no actual credential / no actual check / no API / no POST**。
  Step 6G-PC-OX-H-VのCASE 2結論後の次Stepとして、checker executionのimplementation interface /
  lifecycle / result mapping / stop condition hooksだけをskeletonとして追加した。Step 6G-PC-X-I-Sでは
  `backend/app/live_verification/live_order_real_credential_presence_checker_execution_implementation.py` を追加し、
  `CHECKER_EXECUTION_IMPLEMENTATION_SKELETON_ONLY`、checker execution contract ready、checker
  implementation skeleton ready、operator result handoff safe、operator checker workflow ready、
  execution implementation/interface/lifecycle/result mapping/stop conditions declared、execution deferred to future
  step、execution performed=false、execution performed by Codex/operator=false、env access requested=false、
  Codex env access requested=false、actual environment presence check performed=false、credential read performed=false、
  credential values/metadata present=false、checker result available/detail=false、checker result
  unknown/failed/unavailable/stale/timeout=false、operator result detail/raw/reused/previous-turn/timeout=false、
  real signature / real headers / HTTP POST capability=false flagsだけを扱う。readyでは
  `CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_READY_NO_ENV_NO_CHECK`、
  `checker_execution_implementation_skeleton_ready=true`、`execution_deferred_to_future_step=true`、
  `execution_performed=false`、`execution_performed_by_codex=false`、
  `execution_performed_by_operator=false`、`env_access_requested=false`、
  `codex_env_access_requested=false`、`actual_environment_presence_check_performed=false`、
  `credential_read_performed=false`、`checker_result_available=false`、`checker_result_timeout=false`、
  `operator_result_raw_value_present=false`、`post_allowed_this_step=false`、`post_executed=false` を維持する。
  unknown / failed / unavailable / stale / timeoutは必ずblockする。Step 6G-IWにも最小連携し、
  checker execution implementation skeleton readyをready条件に加えた。このStepでは実API、read-only API、
  public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、実credential値取得、credential presence実環境確認、env / `.env` access、checker execution、
  checker result detail保存・表示、operator result detail/raw保存・表示、env variable names保存・表示、
  credential metadata取得・表示、実credential injection、実署名値生成、実headers値生成、raw request/response表示・保存、
  real ID表示を行わない。future checker execution / env access / real credential injection / real signing /
  real transportは別Stepで、新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_SKELETON.md](STEP6G_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_IMPLEMENTATION_SKELETON.md)。
- 直前フェーズ: **Step 6G-PC-OX-H operator result handoff hardening完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-X-C-VのCASE 2結論後の次Stepとして、operator-executed checker workflowの結果受け渡しを
  safe boolean/categoryだけに限定するhardeningを追加した。Step 6G-PC-OX-Hでは
  `backend/app/live_verification/live_order_real_operator_executed_checker_workflow.py` とStep 6G-IWに
  `operator_result_handoff_declared=true`、`operator_result_handoff_safe=true`、
  `operator_result_category_only=true`、`operator_result_is_boolean_only=true`、
  `operator_result_raw_value_present=false`、`operator_result_raw_value_saved=false`、
  `operator_result_raw_value_displayed=false`、`operator_result_previous_turn=false`、
  `operator_result_reused=false`、`operator_result_stale=false`、
  `operator_result_timeout=false`、`operator_result_unknown=false`、
  `operator_result_failed=false`、`operator_result_unavailable=false`、
  `operator_result_saved=false`、`operator_result_displayed=false`、
  `operator_result_broadly_propagated=false` を追加・固定した。raw operator result value、
  operator result detail、credential metadata、env variable names、sentinel value、previous-turn、
  reused、stale、unknown、failed、unavailable、timeout はblockする。readyでも
  `post_allowed_this_step=false`、`post_executed=false`、`http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false` を維持する。このStepでは実API、
  read-only API、public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、
  `live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、
  env / `.env` access、checker execution、real credential injection、実署名値生成、実headers値生成、
  raw request/response表示・保存、real ID表示を行わない。future checker execution / env access /
  real credential injection / real signing / real transportは別Stepで、新しいfinal confirmationと
  fresh preflightが必要。詳細は
  [STEP6G_OPERATOR_EXECUTED_CHECKER_WORKFLOW.md](STEP6G_OPERATOR_EXECUTED_CHECKER_WORKFLOW.md)。
- 直前フェーズ: **Step 6G-PC-X-C checker execution contract skeleton完了 / no env / no actual credential / no actual check / no API / no POST**。
  Step 6G-PC-X-RのCASE 2結論後の次Stepとして、checker executionの入力・出力・停止条件だけを
  pure contract skeletonとして追加した。Step 6G-PC-X-Cでは
  `backend/app/live_verification/live_order_real_credential_presence_checker_execution_contract.py` を追加し、
  `CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY`、checker implementation skeleton ready、
  operator checker workflow ready、checker contract ready、execution contract/input/output/stop conditions declared、
  execution deferred to future step、execution performed=false、execution performed by Codex/operator=false、
  Codex env access requested=false、actual environment presence check performed=false、
  credential read performed=false、credential values/metadata present=false、checker result available/detail=false、
  checker result unknown/failed/unavailable/stale/timeout=false、operator workflow preserved=true、
  real signature / real headers / HTTP POST capability=false flagsだけを扱う。readyでは
  `CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK`、
  `checker_execution_contract_ready=true`、`execution_deferred_to_future_step=true`、
  `execution_performed=false`、`execution_performed_by_codex=false`、
  `execution_performed_by_operator=false`、`codex_env_access_requested=false`、
  `actual_environment_presence_check_performed=false`、`credential_read_performed=false`,
  `checker_result_available=false`、`checker_result_timeout=false`、`post_allowed_this_step=false`、
  `post_executed=false` を維持する。unknown / failed / unavailable / stale / timeoutは必ずblockする。
  Step 6G-IWにも最小連携し、checker execution contract readyをready条件に加えた。
  このStepでは実API、read-only API、public API、Private API、broker、fresh preflight、HTTP POST、
  order endpoint、`live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、
  env / `.env` access、checker execution、checker result detail保存・表示、operator result detail保存・表示、
  env variable names保存・表示、credential metadata取得・表示、実credential injection、実署名値生成、
  実headers値生成、raw request/response表示・保存、real ID表示を行わない。future checker execution /
  real credential injection / real signing / real transportは別Stepで、新しいfinal confirmationと
  fresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT.md](STEP6G_CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT.md)。
- 直前フェーズ: **Step 6G-PC-I-S real credential presence checker implementation skeleton完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-OX-V後の次Stepとして、将来のreal credential presence checkerのimplementation
  interface / lifecycle / stop conditionsだけをskeletonとして追加した。Step 6G-PC-I-Sでは
  `backend/app/live_verification/live_order_real_credential_presence_checker_implementation.py` を追加し、
  `CHECKER_IMPLEMENTATION_SKELETON_ONLY`、checker contract ready、operator checker workflow ready、
  credential presence adapter/check ready、implementation interface/lifecycle declared、
  execution deferred to future step、execution performed=false、Codex env access requested=false、
  actual environment presence check performed=false、env access capability=false、credential read capability=false、
  credential values/metadata=false、checker result available/detail=false、unknown/failed/unavailable/stale=false、
  operator workflow supported/preserved=true、real signature / real headers / POST capability=false flagsだけを扱う。
  readyでは `CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK`、
  `checker_implementation_skeleton_ready=true`、`execution_deferred_to_future_step=true`、
  `execution_performed=false`、`codex_env_access_requested=false`、
  `actual_environment_presence_check_performed=false`、`checker_result_available=false`、
  `operator_workflow_preserved=true`、`http_post_executed=false`、`order_endpoint_called=false`,
  `live_order_once_called=false`、`post_allowed_this_step=false`、`post_executed=false` を維持する。
  Step 6G-IWにも最小連携し、checker implementation skeleton readyをready条件に加えた。
  このStepでは実API、read-only API、public API、Private API、broker、fresh preflight、HTTP POST、
  order endpoint、`live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、
  env / `.env` access、checker execution、checker result detail保存・表示、operator result detail保存・表示、
  env variable names保存・表示、credential metadata取得・表示、実credential injection、実署名値生成、
  実headers値生成、raw request/response表示・保存、real ID表示を行わない。future checker execution /
  real credential injection / real signing / real transportは別Stepで、新しいfinal confirmationと
  fresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_SKELETON.md](STEP6G_CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_SKELETON.md)。
- 直前フェーズ: **Step 6G-PC-OX operator-executed checker workflow skeleton完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-I-R後の次Stepとして、operatorが別途credential presenceを確認し、Codexにはsafe
  boolean/categoryだけを渡すworkflow skeletonを追加した。Step 6G-PC-OXでは
  `backend/app/live_verification/live_order_real_operator_executed_checker_workflow.py` を追加し、
  `OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY`、credential presence checker contract / adapter /
  check ready、operator execution outside Codex、Codex execution/env access/actual environment check=false、
  operator result provided/boolean-only/fresh、unknown/failed/unavailable/stale/reused/previous-turn=false、
  operator result save/display/broad propagation/detail=false、credential values/metadata=false、
  env variable names=false、sentinel value=false、checker result detail=false、real signature / real headers /
  POST capability=false flagsだけを扱う。readyでは
  `OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST`、
  `operator_checker_workflow_ready=true`、`operator_execution_performed_outside_codex=true`、
  `codex_execution_performed=false`、`codex_env_access_requested=false`、
  `actual_environment_presence_check_performed_by_codex=false`、`operator_result_unknown=false`、
  `operator_result_failed=false`、`operator_result_unavailable=false`、
  `http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。unknown / failed / unavailable /
  stale / reused / previous-turn result は必ずblockする。Step 6G-IWにも最小連携し、
  operator checker workflow readyをready条件に加えた。このStepでは実API、read-only API、public API、
  Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、実credential値取得、credential presence実環境確認、env / `.env` access、
  real checker attachment/execution、operator result detail保存・表示、env variable names保存・表示、
  credential metadata取得・表示、実credential injection、実署名値生成、実headers値生成、
  raw request/response表示・保存、real ID表示を行わない。future real checker implementation /
  execution、real credential injection、real signing、real transportは別Stepで、新しいfinal confirmationと
  fresh preflightが必要。詳細は
  [STEP6G_OPERATOR_EXECUTED_CHECKER_WORKFLOW.md](STEP6G_OPERATOR_EXECUTED_CHECKER_WORKFLOW.md)。
- 直前フェーズ: **Step 6G-PC-C-H checker contract hardening完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-C-V後の次Stepとして、PC-C checker contractのunsupported input echoを補強した。
  unsupported `checker_contract_mode` は raw inputをresult / renderer / asdictへ残さず、
  safe canonical label `UNSUPPORTED_REDACTED` と
  `unsupported_checker_contract_mode_present=true` のboolean/categoryだけに正規化する。
  `raw_checker_contract_mode_displayed=false`、`raw_checker_contract_mode_saved=false` を固定し、
  Step 6G-IWの返却snapshotでもPC-C result由来のsafe modeだけを保持する。今回も実API、
  read-only API、public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、
  `live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、
  env / `.env` access、real checker attachment/execution、checker result detail保存・表示、
  credential metadata取得・表示、実credential injection、実署名値生成、実headers値生成、
  raw request/response表示・保存、real ID表示を行わない。future real checker implementationは別Stepで、
  新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_REAL_CREDENTIAL_PRESENCE_CHECKER_CONTRACT.md](STEP6G_REAL_CREDENTIAL_PRESENCE_CHECKER_CONTRACT.md)。
- 直前フェーズ: **Step 6G-PC-C real credential presence checker contract完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-A-V後の次Stepとして、将来のreal credential presence checker implementationへ進む前に、
  入力・出力・停止条件だけをcontract-onlyで定義した。Step 6G-PC-Cでは
  `backend/app/live_verification/live_order_real_credential_presence_checker_contract.py` を追加し、metadataとして
  `CHECKER_CONTRACT_ONLY`、credential presence adapter / presence check / boundary / handle / injection ready、
  checker contract requested、checker contract ready requested、real checker implementation present=false、
  real checker attached/executed=false、actual environment presence check performed=false、env access required=true
  かつ allowed/requested=false、credential values available/read/displayed/saved=false、credential metadata
  available/displayed/saved=false、checker result available/saved/displayed/broad propagation=false、
  checker result boolean-only、checker result unknown/failed=false、real signature / real headers / POST capability=false
  flagsだけを扱う。readyでは
  `CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK`、
  `credential_presence_checker_contract_ready=true`、`real_checker_implementation_present=false`、
  `real_checker_attached=false`、`real_checker_executed=false`、
  `actual_environment_presence_check_performed=false`、`env_access_allowed=false`、
  `env_access_requested=false`、`credential_values_available=false`、`credential_values_read=false`、
  `credential_metadata_available=false`、`checker_result_available=false`、`checker_result_saved=false`、
  `checker_result_displayed=false`、`checker_result_unknown=false`、`checker_result_failed=false`、
  `can_generate_real_signature=false`、`can_generate_real_headers=false`、`can_execute_http_post=false`、
  `http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。Step 6G-IWにも最小連携し、
  credential presence checker contract readyをready条件に加えた。このStepでは実API、read-only API、
  public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、実credential値取得、credential presence実環境確認、env / `.env` access、real checker
  attachment/execution、checker result detail保存・表示、credential metadata取得・表示、実credential injection、
  実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。future real
  credential presence check implementation / real credential injection / real signing / real transportは別Stepで、
  新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_REAL_CREDENTIAL_PRESENCE_CHECKER_CONTRACT.md](STEP6G_REAL_CREDENTIAL_PRESENCE_CHECKER_CONTRACT.md)。
- 直前フェーズ: **Step 6G-PC-A credential presence adapter skeleton完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-V後の次Stepとして、operator-provided presence resultを将来のreal credential presence checkerと
  分離するadapter boundary skeletonを追加した。Step 6G-PC-Aでは
  `backend/app/live_verification/live_order_real_credential_presence_adapter.py` を追加し、metadataとして
  `PRESENCE_ADAPTER_SKELETON_ONLY`、credential presence check / boundary / handle / injection ready、
  operator-provided presence result、boolean-only、fresh、reused/stale/previous turn false、presence result
  adapted、presence result display/save/broad propagation false、sentinel value/hash/fingerprint/length
  present/displayed/saved false、credential values/metadata present false、actual environment presence check=false、
  env / `.env` / printenv access=false、real checker attached/executed=false、real signature / real headers /
  POST capability=false flagsだけを扱う。readyでは
  `CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK`、`credential_presence_adapter_ready=true`、
  `operator_provided_presence_result=true`、`operator_presence_result_fresh=true`、
  `operator_presence_result_reused=false`、`operator_presence_result_stale=false`、
  `presence_result_adapted=true`、`actual_environment_presence_check_performed=false`、
  `env_access_requested=false`、`real_checker_attached=false`、`real_checker_executed=false`、
  `sentinel_value_present=false`、`credential_values_present=false`、`credential_metadata_present=false`、
  `can_generate_real_signature=false`、`can_generate_real_headers=false`、`can_execute_http_post=false`、
  `http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。Step 6G-IWにも最小連携し、
  credential presence adapter readyをready条件に加えた。このStepでは実API、read-only API、public API、
  Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、
  実credential値取得、credential presence実環境確認、env / `.env` access、real checker attachment/execution、
  sentinel文字列保存・表示、sentinel hash/fingerprint/length取得・表示、credential metadata取得・表示、
  実credential injection、実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。
  future real credential presence check / real credential injection / real signing / real transportは別Stepで、
  新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_PRESENCE_ADAPTER_SKELETON.md](STEP6G_CREDENTIAL_PRESENCE_ADAPTER_SKELETON.md)。
- 直前フェーズ: **Step 6G-PC credential presence check skeleton完了 / no env / no actual credential / no API / no POST**。
  Step 6G-PC-R後の次Stepとして、operator-provided boolean / sentinel方式のcredential presence check skeletonを
  追加した。Step 6G-PCでは
  `backend/app/live_verification/live_order_real_credential_presence_check.py` を追加し、metadataとして
  `OPERATOR_PROVIDED_SENTINEL_ONLY`、credential boundary / handle / injection ready、operator assertion
  provided、operator assertion boolean-only、operator sentinel received/fresh、stale/reused/previous turn sentinel
  false、sentinel value/hash/fingerprint/length present/displayed/saved false、credential values/metadata present false、
  credential presence実環境確認=false、env / `.env` / printenv access=false、presence result broad propagation/save=false、
  real signature / real headers / POST capability=false flagsだけを扱う。readyでは
  `CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV`、`credential_presence_check_ready=true`、
  `operator_assertion_provided=true`、`operator_sentinel_fresh=true`、`operator_sentinel_reused=false`、
  `operator_sentinel_stale=false`、`sentinel_value_present=false`、`credential_values_present=false`、
  `credential_metadata_present=false`、`credential_presence_checked_against_environment=false`、
  `env_access_requested=false`、`can_generate_real_signature=false`、`can_generate_real_headers=false`、
  `can_execute_http_post=false`、`http_post_executed=false`、`order_endpoint_called=false`、
  `live_order_once_called=false`、`post_allowed_this_step=false`、`post_executed=false` を維持する。
  Step 6G-IWにも最小連携し、credential presence check readyをready条件に加えた。このStepでは実API、
  read-only API、public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、
  `live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、env / `.env`
  access、sentinel文字列保存・表示、sentinel hash/fingerprint/length取得・表示、credential metadata取得・表示、
  実credential injection、実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。
  future real credential presence check / real credential injection / real signing / real transportは別Stepで、
  新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_PRESENCE_CHECK_PLAN.md](STEP6G_CREDENTIAL_PRESENCE_CHECK_PLAN.md)。
- 直前フェーズ: **Step 6G-CI credential injection skeleton完了 / no real credential / no env / no API / no POST**。
  Step 6G-CH後の次Stepとして、将来のreal credential injectionへ進む前に、credential値を注入しない
  credential injection skeletonを追加した。Step 6G-CIでは
  `backend/app/live_verification/live_order_real_credential_injection.py` を追加し、metadataとして
  `INJECTION_SKELETON_ONLY`、credential boundary ready、credential handle ready、injection requested、
  injection performed=false、real credential values available/injected=false、credential values provided/loaded=false、
  credential metadata available=false、handle created/value/identifier=false、env / `.env` access=false、
  credential presence実環境確認=false、real signature / real headers / POST capability=false flagsだけを扱う。
  readyでは `CREDENTIAL_INJECTION_READY_NO_VALUE_NO_ENV`、`credential_injection_ready=true`、
  `injection_requested=true`、`injection_performed=false`、`real_credential_values_available=false`、
  `real_credential_values_injected=false`、`credential_values_provided=false`、`credential_values_loaded=false`、
  `credential_metadata_available=false`、`handle_created=false`、`handle_contains_value=false`、
  `handle_contains_identifier=false`、`env_access_requested=false`、`can_generate_real_signature=false`、
  `can_generate_real_headers=false`、`can_execute_http_post=false`、`http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false`、`post_allowed_this_step=false`、
  `post_executed=false` を維持する。Step 6G-IWにも最小連携し、credential injection readyをready条件に加えた。
  このStepでは実API、read-only API、public API、Private API、broker、fresh preflight、HTTP POST、
  order endpoint、`live_order_once`、実注文、ledger操作、実credential値取得、実credential injection、
  credential presence実環境確認、実handle作成、handle id/token/secret/key material、credential長さ/hash/
  fingerprint/preview/prefix/suffix取得・表示、実署名値生成、実headers値生成、raw request/response表示・保存、
  real ID表示を行わない。future real credential injection / real signing / real transportは別Stepで、
  新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_INJECTION_SKELETON.md](STEP6G_CREDENTIAL_INJECTION_SKELETON.md)。
- 直前フェーズ: **Step 6G-CH credential handle contract完了 / no real credential / no env / no API / no POST**。
  Step 6G-CB後の次Stepとして、将来のreal credential injectionに進む前にcredential値を持たない
  credential handle contractを追加した。Step 6G-CHでは
  `backend/app/live_verification/live_order_real_credential_handle.py` を追加し、metadataとして
  `HANDLE_CONTRACT_ONLY`、credential boundary ready、handle requested、handle created/value/secret/token/
  key material/identifier/metadata exposure false flags、env / `.env` access false flags、credential values
  provided/loaded false flags、real signature / real headers / POST capability false flagsだけを扱う。readyでは
  `CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV`、`credential_handle_ready=true`、`handle_requested=true`、
  `handle_created=false`、`handle_contains_value=false`、`handle_contains_identifier=false`、
  `handle_metadata_exposed=false`、`credential_values_provided=false`、`credential_values_loaded=false`、
  `env_access_requested=false`、`can_generate_real_signature=false`、`can_generate_real_headers=false`、
  `can_execute_http_post=false`、`http_post_executed=false`、`order_endpoint_called=false`、
  `live_order_once_called=false`、`post_allowed_this_step=false`、`post_executed=false` を維持する。
  Step 6G-IWにも最小連携し、credential handle readyをready条件に加えた。このStepでは実API、
  read-only API、public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、
  `live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、実handle作成、
  handle id/token/secret/key material、credential長さ/hash/fingerprint/preview/prefix/suffix取得・表示、
  実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。future real
  credential injection / real signing / real transportは別Stepで、新しいfinal confirmationとfresh preflightが必要。
  詳細は [STEP6G_CREDENTIAL_HANDLE_CONTRACT.md](STEP6G_CREDENTIAL_HANDLE_CONTRACT.md)。
- 直前フェーズ: **Step 6G-CB credential boundary skeleton完了 / no real credential / no API / no POST**。
  Step 6G-HT後の次Stepとして、将来のreal signing実装前にcredential境界のcontract-only skeletonを追加した。
  Step 6G-CBでは `backend/app/live_verification/live_order_real_credential_boundary.py` を追加し、
  metadataとして `BOUNDARY_ONLY`、credential request/value/load/env/presence/metadata exposure false flags、
  signing contract / dummy signing / HTTP transport interface readiness、real signature / real headers / POST capability
  false flagsだけを扱う。readyでは `CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV`、
  `real_credentials_requested=false`、`credential_values_provided=false`、`credential_values_loaded=false`、
  `credential_presence_checked_against_environment=false`、`env_access_requested=false`、
  `credential_metadata_exposed=false`、`can_generate_real_signature=false`、`can_generate_real_headers=false`、
  `can_execute_http_post=false`、`http_post_executed=false`、`order_endpoint_called=false`、
  `live_order_once_called=false`、`post_allowed_this_step=false`、`post_executed=false` を維持する。
  Step 6G-IWにも最小連携し、credential boundary readyをready条件に加えた。このStepでは実API、
  read-only API、public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、
  `live_order_once`、実注文、ledger操作、実credential値取得、credential presence実環境確認、
  credential長さ/hash/fingerprint/preview/prefix/suffix取得・表示、実署名値生成、実headers値生成、
  raw request/response表示・保存、real ID表示を行わない。future real credential injection / real signing /
  real transportは別Stepで、新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_CREDENTIAL_BOUNDARY_SKELETON.md](STEP6G_CREDENTIAL_BOUNDARY_SKELETON.md)。
- 直前フェーズ: **Step 6G-HT HTTP transport interface skeleton完了 / no API / no POST**。
  Step 6G-DS後の次Stepとして、将来のreal transport実装前にinterface-onlyのHTTP transport boundaryを追加した。
  Step 6G-HTでは `backend/app/live_verification/live_order_real_http_transport_interface.py` を追加し、
  metadataとして `INTERFACE_ONLY`、method/path、endpoint/body/serialization/signing/dummy signing/private
  transport readiness、one-shot/no-retry attempt state、HTTP client / POST / order endpoint / `live_order_once`
  capability false flagsだけを扱う。readyでは
  `HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST`、`http_client_present=false`、
  `can_execute_http_post=false`、`can_call_order_endpoint=false`、`can_call_live_order_once=false`、
  `credential_values_provided=false`、`signature_value_generated=false`、`header_values_present=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。Step 6G-IWにも最小連携し、
  HTTP transport interface readyをready条件に加えた。このStepでは実API、read-only API、public API、
  Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、
  credential値取得、実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。
  future real transportは別Stepで、新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_HTTP_TRANSPORT_INTERFACE_SKELETON.md](STEP6G_HTTP_TRANSPORT_INTERFACE_SKELETON.md)。
- 直前フェーズ: **Step 6G-DS dummy signing implementation完了 / no API / no POST / no real credential**。
  Step 6G-IW後の次Stepとして、実署名・実POSTに進む前にdummy signingの入力形とredaction境界を確認した。
  Step 6G-DSでは `backend/app/live_verification/live_order_real_dummy_signing.py` を追加し、dummy-only
  metadataとして method/path、body contract ready、stable serialization ready、dummy timestamp/key/secret
  material labels、algorithm label、header-name labelsのみを扱う。valid inputでは
  `DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED` となるが、実credentialを扱わず、実署名値を生成せず、
  実headers値を生成せず、signature value / header values / credential valuesをresult・renderer・asdictに保持しない。
  Step 6G-IWにも最小連携し、dummy signing ready / dummy signature check passedをready条件に加えた。readyでも
  `http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false`、
  `post_allowed_this_step=false`、`post_executed=false` を維持する。このStepでは実API、read-only API、
  public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、credential値取得、実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を
  行わない。future real signingは別Stepで、新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_DUMMY_SIGNING_PLAN.md](STEP6G_DUMMY_SIGNING_PLAN.md)。
- 直前フェーズ: **Step 6G-IW internal wiring dry-run完了 / no API / no POST**。
  Step 6G-IRはCASE 2として、PB / EB / AD / RA / TC / STの個別部品は安全境界を維持している一方、
  同一fake/sanitized snapshotで一気通貫させる内部E2E dry-run wiringが未実装であると判定した。
  Step 6G-IWでは `backend/app/live_verification/live_order_real_step6g_internal_wiring.py` を追加し、
  Step 6G-PB post route bridge、Step 6G-EB fake runtime bridge、Step 6G-AD controlled adapter、
  Step 6G-RA real adapter contract、Step 6G-TC low-level transport core、Step 6G-ST signing / private
  transport contractsをfake/sanitizedで接続する。readyでも `http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false`、`credential_values_provided=false`、
  `signature_value_generated=false`、`header_values_present=false`、`post_allowed_this_step=false`、
  `post_executed=false` を維持する。このStepでは実API、read-only API、public API、Private API、broker、
  fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、credential値取得、
  実署名値生成、実headers値生成、raw request/response表示・保存、real ID表示を行わない。fake final
  confirmation / fake preflightは実承認・実preflightではなく、future real executionには別Stepで新しい
  final confirmationとfresh preflightが必要。詳細は
  [STEP6G_INTERNAL_WIRING_DRY_RUN.md](STEP6G_INTERNAL_WIRING_DRY_RUN.md)。
- 直前フェーズ: **Step 6G-ST real signing / private order transport contract完了 / no API / no POST / no credential value**。
  Step 6G-SRはCASE 2として、既存 `live_order_once.py` のStep 4入口をそのままStep 6Gから使わず、
  Step 4 approval phrase / ledger stateを偽装・強制変換しないまま、署名・headers・transport分類の
  低レベル概念だけをStep 4非依存contractへ分離する方針を確認した。Step 6G-STでは
  `backend/app/live_verification/live_order_real_signing_contract.py` と
  `backend/app/live_verification/live_order_real_private_order_transport.py` を追加し、real signing contractは
  method/path、stable body contract、timestamp required、credential presence required、非秘密algorithm label、
  header-name labels、redacted header contractだけを扱う。private order transport contractは実HTTP clientを持たず、
  sanitized result categoryだけを扱い、unknown / timeout / rejectedでもretryしない。ready / classified resultでも
  `credential_values_provided=false`、`signature_value_generated=false`、`http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false`、`post_allowed_this_step=false`、
  `post_executed=false` を維持する。このStepでは実API、read-only API、public API、Private API、broker、
  fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、実署名値生成、
  credential値取得、実headers値生成、raw request/response表示・保存、real ID表示を行わない。future real signing /
  real transport は別Stepで、新しいfinal confirmationとfresh preflightが必要。詳細は
  [STEP6G_REAL_SIGNING_TRANSPORT_CONTRACT.md](STEP6G_REAL_SIGNING_TRANSPORT_CONTRACT.md)。
- 直前フェーズ: **Step 6G-TC low-level transport core完了 / pure-fake / no API / no POST**。
  Step 6G-LTはCASE 2として、既存 `live_order_once.py` のStep 4入口をそのままStep 6Gから使わず、
  Step 4 approval phrase / ledger `PREPARED` stateに依存しない低レベルtransport coreだけを抽出する方針を
  確認した。Step 6G-TCでは
  `backend/app/live_verification/live_order_real_order_transport_core.py` を追加し、Step 6G専用real adapterが
  将来利用できるpure/fake coreとして、order body allowlist、stable JSON serialization、method/path contract、
  redacted header-name contract、fake/sanitized transport result classification、one-shot/no-retry contract、
  raw/secret/real ID exposure blockersを実装した。ready / classified resultでも `http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false`、`post_allowed_this_step=false`、
  `post_executed=false`、retry/loop/追加/変更/取消/決済禁止を維持する。このStepでは実API、read-only API、
  public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、
  ledger操作、実署名値生成、実credentials利用、headers値表示・保存、raw request/response表示・保存、
  real ID表示を行わない。future real signing / real transport は別Stepで、新しいfinal confirmationと
  fresh preflightが必要。詳細は [STEP6G_LOW_LEVEL_TRANSPORT_CORE_PLAN.md](STEP6G_LOW_LEVEL_TRANSPORT_CORE_PLAN.md)。
- 直前フェーズ: **Step 6G-RA real adapter contract完了 / stub transport only / no API / no POST**。
  Step 6G-RTはCASE 2として、既存 `live_order_once.py` のStep 4入口をそのままStep 6Gから使わず、
  Step 4 approval phrase / ledger `PREPARED` stateを偽装・強制変換しない方針を確認した。
  Step 6G-RAでは `backend/app/live_verification/live_order_real_step6g_real_adapter.py` を追加し、
  Step 6G-PBのroute bridge、Step 6G-EBのfake runtime bridge、Step 6G-ADのcontrolled adapterを入力にする
  real adapter contract / stub transport modelを実装した。このStepでは `STUB_ONLY` transportのみを許可し、
  real transport、HTTP POST可能transport、order endpoint / `live_order_once` / broker / Private API /
  HTTP client importをfail-closedでblockする。stub accepted / rejected / unknown / timeoutを区別するが、
  実POST結果としては扱わない。ready / stub completedでも `allowed_for_live=false`、
  `post_allowed_this_step=false`、`post_executed=false`、`real_http_post_executed=false`、
  `order_endpoint_called=false`、`live_order_once_called=false` を維持する。stubでもattemptは最大1回で、
  retry/loop/追加/変更/取消/決済、raw/secret/ID露出、Step 4 approval phrase偽装、ledger state強制変更を
  fail-closedでblockする。Step 6G-RAは実API、read-only API、public API、Private API、broker、
  fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、final confirmation再利用を
  行わない。将来のreal transport実装は別Stepで、新しいfinal confirmationとfresh preflightが必要。
  詳細は [STEP6G_REAL_ADAPTER_CONTRACT.md](STEP6G_REAL_ADAPTER_CONTRACT.md)。
- 直前フェーズ: **Step 6G-AD controlled adapter fake transport完了 / no API / no POST**。
  Step 6G-PBのpure route bridgeとStep 6G-EBのfake runtime bridgeを入力に、将来の実POST実行器へ渡す
  controlled adapter skeletonとして `backend/app/live_verification/live_order_real_step6g_controlled_adapter.py`
  を追加した。このStepでは `FAKE_ONLY` transport contractのみを許可し、real transport、HTTP POST可能transport、
  order endpoint / `live_order_once` / broker / Private API / HTTP client importをfail-closedでblockする。
  fake accepted / rejected / unknown / timeoutを区別するが、実POST結果としては扱わない。ready / fake completedでも
  `allowed_for_live=false`、`post_allowed_this_step=false`、`post_executed=false`、
  `real_http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false` を維持する。
  fakeでもattemptは最大1回で、retry/loop/追加/変更/取消/決済、raw/secret/ID露出、Step 4 approval phrase偽装、
  ledger state強制変更をfail-closedでblockする。Step 6G-ADは実API、read-only API、public API、
  Private API、broker、fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、
  final confirmation再利用を行わない。将来の実行には別Stepで新しいfinal confirmation、fresh preflight、
  reviewed real adapter contractが必要。詳細は [STEP6G_CONTROLLED_ADAPTER_PLAN.md](STEP6G_CONTROLLED_ADAPTER_PLAN.md)。
- 直前フェーズ: **Step 6G-EB runtime bridge fake executor完了 / no API / no POST**。
  Step 6G-PBのPOST route bridge pure model ready resultを受け取り、将来の実POST実行器へ渡す前段として
  `backend/app/live_verification/live_order_real_step6g_runtime_bridge.py` を追加した。これはfake-only runtime
  bridgeであり、fake accepted / rejected / unknown / timeoutを区別しつつ、実POST結果としては扱わない。
  ready / fake completedでも `allowed_for_live=false`、`post_allowed_this_step=false`、`post_executed=false`、
  `real_http_post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false`、
  `broker_order_path_called=false` を維持する。fakeでもattemptは最大1回で、retry/loop/追加/変更/取消/決済、
  raw/secret/ID露出、Step 4 approval phrase偽装、ledger state強制変更をfail-closedでblockする。
  Step 6G-EBは実API、read-only API、public API、Private API、broker、fresh preflight、HTTP POST、
  order endpoint、`live_order_once`、実注文、ledger操作、final confirmation再利用を行わない。将来の実行には
  別Stepで新しいfinal confirmationとfresh preflight、実adapter reviewが必要。詳細は
  [STEP6G_RUNTIME_BRIDGE_PLAN.md](STEP6G_RUNTIME_BRIDGE_PLAN.md)。
- 直前フェーズ: **Step 6G-PB POST route bridge pure model完了 / no API / no POST**。
  Step 6G-F2はfinal confirmation、approval artifact再生成、fingerprint/sha256 prefix一致、POST直前fresh
  preflight、order intent exact matchまでは通過したが、既存POST経路との安全接続が確認できず
  `BLOCKED_STEP6GF2_ROUTE_UNSAFE` で停止した。既存 `live_order_once.py` はStep 4専用approval phraseと
  ledger `PREPARED` stateを要求し、Step 6G final confirmation / Step 6B-6C artifactとはそのまま互換ではない。
  Step 6G-PBでは、Step 6G order intent、approval artifact、fresh preflight、attempt state、route safetyを
  接続するpure modelを追加した。readyでも `allowed_for_live=false`、`post_allowed_this_step=false`、
  `post_executed=false`、`order_endpoint_called=false`、`live_order_once_called=false` を維持し、Step 4
  approval phrase偽装、Step 4 ledger state強制変更、raw/secret/ID露出、retry/loop/追加/変更/取消/決済を
  fail-closedでblockする。Step 6G-PBは実API、read-only API、public API、Private API、broker、
  fresh preflight、HTTP POST、order endpoint、`live_order_once`、実注文、ledger操作、final confirmation再利用を
  行わない。詳細は [STEP6G_POST_ROUTE_BRIDGE_PLAN.md](STEP6G_POST_ROUTE_BRIDGE_PLAN.md)。
- 直前フェーズ: **Step 6G-TF ticker age sanitizer fix完了 / no API / no POST**。
  Step 6G-Fはfinal confirmation phrase受領後、approval artifact再生成とfingerprint一致までは成功したが、
  POST直前fresh preflightのsanitized処理で `Ticker object has no attribute timestamp` が発生し、
  fail-closedで停止した。HTTP POST、order endpoint、`live_order_once`、実注文は未実行で、
  `post_attempt_count=0`、raw/secret/ID露出なし。原因は
  `GmoPublicMarketDataClient.fetch_ticker()` が返す normalized `Ticker` の時刻fieldが `time` であるのに、
  Step 6G-Fのsanitized ticker age算出が `.timestamp` 固定参照だったこと。Step 6G-TFでは実API、
  read-only API、public API、Private API、broker、fresh preflight、HTTP POST、order endpoint、
  `live_order_once`、実注文、final confirmation再利用を行わず、ticker age算出を `time` primaryの
  fail-closed sanitizerへ限定修正する。修正後も過去final confirmation phraseは失効扱いで、
  次のStep 6Gは別タスクとして最初から再実行し、新しいfinal confirmation gateを通す必要がある。詳細は
  [STEP6G_TICKER_AGE_SANITIZER_FIX.md](STEP6G_TICKER_AGE_SANITIZER_FIX.md)。
- 直前フェーズ: **Step 6F Real post-readiness planning完了 / planning-only / no POST**。
  Step 6E-R2のsanitized runtime result
  `REAL_API_PREFLIGHT_PASSED_NO_POST` をGitに保存せずsnapshot入力として受け取り、
  `backend/app/live_verification/live_order_real_post_readiness_plan.py` を追加した。
  ready Step 6Fでは `POST_READINESS_PLANNED_NO_POST`、`plan_ready=true`、
  `eligible_for_step6g_one_shot_post_request=true` になるが、これは将来のStep 6G明示依頼を待てる
  planning evidenceという意味だけで、`allowed_for_live=false`、`post_authorized_this_step=false`、
  `post_allowed_this_step=false`、`post_attempt_limit=1`、`post_executed=false`、
  `order_endpoint_called=false`、`order_payload_generated=false`、`order_payload_sent=false`、
  `live_order_once_called=false`、broker order path false、retry/loop/追加/変更/取消/決済禁止を維持する。
  Step 6Fは実API、read-only API、public API、Private API、broker、order endpoint、
  `live_order_once`、HTTP POST、実注文、raw request/response表示・保存、
  headers/signature/credentials/real ID表示・保存、ledger操作を行わない。
  Step 6Gへ進むには別の明示依頼と直前fresh real API preflight再確認が必要。詳細は
  [STEP6F_REAL_POST_READINESS_PLAN.md](STEP6F_REAL_POST_READINESS_PLAN.md)。
- 直前フェーズ: **Step 6E-S Sunday offline preparation完了 / no API / no POST**。
  2026-06-28 JSTが日曜で市場外停止条件に該当するため、Step 6E real API preflightは未実行だった。
  市場時間内に別タスクとして1回だけread-only/preflight確認を再試行するため、
  [STEP6E_R_MARKET_OPEN_RETRY_RUNBOOK.md](STEP6E_R_MARKET_OPEN_RETRY_RUNBOOK.md) を追加した。
- 直前フェーズ: **Step 6E Real API preflight execution model完了 / read-only-preflight result model / no POST**。
  `backend/app/live_verification/live_order_real_api_preflight_execution.py` を追加し、Step 6Dの
  `LiveOrderRealApiPreflightPlan`、明示的なStep 6E request acknowledgement snapshot、
  environment/safe-route check、sanitized preflight resultを入力に、real API preflight結果を
  fail-closedで評価できるようにした。ready resultでは
  `REAL_API_PREFLIGHT_PASSED_NO_POST`、`execution_ready=true`、
  `api_preflight_executed=true`、`api_preflight_passed=true`、
  `eligible_for_step6f_post_readiness_planning=true` になるが、これはsanitized read-only/preflight evidenceを
  Step 6Fの別タスクへ渡せるという意味だけで、Step 6Eでも `allowed_for_live=false`、
  `post_allowed_this_step=false`、`post_executed=false`、`order_endpoint_called=false`、
  `order_payload_generated=false`、`order_payload_sent=false`、`live_order_once_called=false`、
  retry/loop/追加/変更/取消/決済禁止、raw request/response/headers/signature表示・保存禁止を維持する。
  2026-06-28 JSTは日曜のため、今回の作業では実API preflightは実行せず、model/tests/docsのみ完了した。
  詳細は [STEP6E_REAL_API_PREFLIGHT_EXECUTION.md](STEP6E_REAL_API_PREFLIGHT_EXECUTION.md)。
  実API preflightは未実行のため、Step 6Fへ進む前にfreshなStep 6E-R market-open retryが必要。
- 直前フェーズ: **Step 6D Real API preflight plan完了 / planning-only / no real API / no POST**。
  `backend/app/live_verification/live_order_real_api_preflight_plan.py` を追加し、Step 6Cの
  `LiveOrderRealApprovalArtifactValidation`、明示的なStep 6D request acknowledgement snapshot、
  sanitized safety snapshotを入力に、将来のStep 6E real API preflight executionで確認する予定項目、
  data handling policy、go/no-go/stop条件、future Step 6E handoff/blockersをfail-closedで整理した。
  ready planでは `API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST`、`plan_ready=true`、
  `eligible_for_step6e_real_api_preflight_execution=true`、`approval_gate_enabled=true`、
  `approval_artifact_validated=true`、`api_preflight_planned=true` になるが、これはStep 6E以降の
  real API preflight executionを別タスクとして計画できるという意味だけで、Step 6Dでは
  `allowed_for_live=false`、`api_preflight_executed=false`、`real_api_execution_deferred_to_step6e=true`、
  `read_only_api_called=false`、`public_api_called=false`、`private_api_called=false`、
  `broker_called=false`、`live_order_once_called=false`、`post_allowed_this_step=false`、
  `post_attempt_limit=1`、`post_executed=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  Planned checksはmarket-hours/session、account/assets、open positions、active orders、instrument rules、
  ticker spread/age、permission scope、IP/account binding、previous result unknown、raw response handlingを
  **将来Step 6E or later** の確認予定として定義するだけで、Step 6Dではread-only API、public API、
  Private API、broker、`live_order_once`、ledger、HTTP POST、実注文、approval gate発行、approval command生成・
  表示・copyable化・pbcopy・保存、raw request/response/headers/signature表示・保存には接続していない。
  詳細は [STEP6D_REAL_API_PREFLIGHT_PLAN.md](STEP6D_REAL_API_PREFLIGHT_PLAN.md)。
  次は別StepのStep 6E real API preflight execution request。
- 直前フェーズ: **Step 6C Real approval artifact validation完了 / validation-only / no API / no POST / no copyable command**。
  `backend/app/live_verification/live_order_real_approval_artifact_validation.py` を追加し、Step 6Bの
  `LiveOrderRealApprovalArtifact`、明示的なStep 6C request acknowledgement snapshot、
  provided command snapshot、sanitized validation safety snapshotを入力に、approval artifactの整合性を
  fail-closedで検証できるようにした。safe artifact + explicit request + exact provided command + safe snapshotでは
  `APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST`、`validation_ready=true`、
  `approval_artifact_validated=true`、`approval_command_exact_match_validated=true`、
  `approval_command_ttl_validated=true`、`approval_command_same_session_validated=true`、
  `eligible_for_step6d_api_preflight_planning=true`、`approval_gate_enabled=true` になるが、
  `approval_gate_enabled=true` はStep 6A由来のstate-only enablementがStep 6B artifact経由で
  Step 6C validationまで維持されたという意味だけで、live POST許可、実approval gate発行、
  実注文許可、copyable承認文ではない。Step 6Cはmodel内部validationだけで、
  `allowed_for_live=false`、`approval_gate_issued=false`、`approval_command_copyable=false`、
  `approval_command_displayed=false`、`approval_command_display_mode=redacted_only_in_step6c`、
  `approval_command_persisted=false`、`approval_command_copied_to_clipboard=false`、
  `approval_command_executable=false`、`post_allowed_this_step=false`、`post_attempt_limit=1`、
  `post_executed=false`、`live_order_once_called=false`、`private_api_called=false`、
  `broker_called=false`、`read_only_api_called=false`、`public_api_called=false`、
  retry/loop/追加/変更/取消/決済禁止を維持する。Step 6Cはgenerated/provided approval command全文を
  Markdown表示せず、copyableにせず、pbcopyせず、ファイル保存せず、HTTP POST、実注文、read-only API、
  public API、Private API、broker、live_order_once、ledgerには接続していない。rendererは
  `provided_command_sha256`、fingerprint、redacted representationのみを出す。詳細は
  [STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md](STEP6C_REAL_APPROVAL_ARTIFACT_VALIDATION.md)。
  ready validationはlive POST許可でも実approval gate発行でもcopyable承認文でもない。次は別Stepの
  Step 6D API preflight planning。
- 直前フェーズ: **Step 6B Real approval artifact generation完了 / artifact-only / no API / no POST / no copyable command**。
  `backend/app/live_verification/live_order_real_approval_artifact_generation.py` を追加し、Step 6Aの
  `LiveOrderRealApprovalGateEnablementState`、明示的なStep 6B request acknowledgement snapshot、
  sanitized artifact-generation safety snapshotを入力に、将来のStep 6C approval artifact validationへ渡す
  内部artifactをfail-closedで生成できるようにした。safe source + explicit request + safe snapshotでは
  `APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST`、`artifact_ready=true`、
  `eligible_for_step6c_validation=true`、`approval_id_generated=true`、
  `approval_command_generated=true`、`approval_artifact_generated=true` になるが、これはmodel内部artifactだけで、
  `allowed_for_live=false`、`approval_gate_issued=false`、`approval_command_copyable=false`、
  `approval_command_displayed=false`、`approval_command_display_mode=redacted_only_in_step6b`、
  `approval_command_persisted=false`、`approval_command_copied_to_clipboard=false`、
  `approval_command_executable=false`、`real_approval_artifacts_available=false`、
  `post_allowed_this_step=false`、`post_attempt_limit=1`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、`public_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  Step 6Bはapproval command全文をMarkdown表示せず、copyableにせず、pbcopyせず、ファイル保存せず、
  HTTP POST、実注文、read-only API、public API、Private API、broker、live_order_once、ledgerには接続していない。
  rendererは `approval_command_sha256`、fingerprint、redacted representationのみを出す。詳細は
  [STEP6B_REAL_APPROVAL_ARTIFACT_GENERATION.md](STEP6B_REAL_APPROVAL_ARTIFACT_GENERATION.md)。
  ready artifactはlive POST許可でも実approval gate発行でもcopyable承認文でもない。次は別Stepの
  Step 6C approval artifact validation。
- 直前フェーズ: **Step 6A Real approval gate enablement state完了 / state-only / no approval artifacts / no API / no POST**。
  `backend/app/live_verification/live_order_real_approval_gate_enablement_state.py` を追加し、Step 5Y-Zの
  `LiveOrderRealApprovalEnablementDryRunPlan`、明示的なStep 6A request acknowledgement snapshot、
  sanitized safety snapshotを入力に、将来のStep 6B approval artifact generation reviewへ進める状態かを
  fail-closedで整理した。safe plan + explicit request + safe snapshotでは
  `REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS`、`enablement_state_ready=true`、
  `eligible_for_future_step6b_approval_artifact_generation=true`、`approval_gate_enabled=true` になるが、
  これはsanitized model outputだけで、`approval_gate_enablement_scope=future_approval_artifact_generation_review_only`、
  `allowed_for_live=false`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_copyable=false`、
  `approval_command_executable=false`、`usable_approval_artifacts_generated=false`、
  `real_approval_artifacts_available=false`、`post_allowed_this_step=false`、`post_attempt_limit=1`、
  `post_executed=false`、`live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、`public_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  Step 6AはHTTP POST、実注文、read-only API、public API、Private API、broker、live_order_once、ledger、
  real approval gate発行、real approval id生成、real approval command生成、copyable approval text生成、
  pbcopy、approval text保存には接続していない。詳細は
  [STEP6A_REAL_APPROVAL_GATE_ENABLEMENT_STATE.md](STEP6A_REAL_APPROVAL_GATE_ENABLEMENT_STATE.md)。
  ready stateはlive POST許可でもapproval gate発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5Y-Z Real approval enablement dry-run plan完了 / dry-run only / market-hours snapshot blocker / no API / no POST / no real approval artifacts**。
  `backend/app/live_verification/live_order_real_approval_enablement_dry_run_plan.py` を追加し、Step 5Xの
  `LiveOrderRealApprovalEnablementCriteria` と sanitized market-hours snapshot を入力に、将来のStep 6A
  planningへ進めるかどうかをpre-enable go/no-goとしてfail-closedで整理した。safe criteria + safe snapshotでは
  `READY_FOR_PRE_ENABLE_GO_NO_GO_REVIEW`、`GO_FOR_FUTURE_STEP6A_PLANNING_ONLY`、
  `plan_ready=true`、`eligible_for_future_step6a_enablement_planning=true` になるが、これは将来の別Stepで
  Step 6A planningを検討するためのevidenceという意味だけで、`approval_gate_enabled=false`、
  `allowed_for_live=false`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_copyable=false`、
  `approval_command_executable=false`、`usable_approval_artifacts_generated=false`、
  `real_approval_artifacts_available=false`、`post_attempt_limit=1`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、`public_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  Step 5Y-Zはsanitized snapshotのみでweekend/market-hours/maintenance/holiday/stale/unknownをblockし、
  HTTP POST、実注文、read-only API、public API、Private API、broker、live_order_once、ledger、
  real approval gate有効化/発行、real approval id生成、real approval command生成、copyable approval text生成、
  pbcopy、approval text保存には接続していない。詳細は
  [STEP5Y_Z_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN.md](STEP5Y_Z_REAL_APPROVAL_ENABLEMENT_DRY_RUN_PLAN.md)。
  ready planはlive POST許可でもapproval gate enablement/発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5X Real approval enablement criteria完了 / dry-run only / no API / no POST / no real enablement**。
  `backend/app/live_verification/live_order_real_approval_enablement_criteria.py` を追加し、Step 5Wの
  `LiveOrderRealApprovalDisabledScaffold` を入力に、将来どの条件を満たせばreal approval gateの
  enablement検討へ進めるかをsanitized criteriaとしてfail-closedで固定した。safe disabled scaffoldでは
  `READY_FOR_REAL_APPROVAL_ENABLEMENT_CRITERIA_REVIEW`、`criteria_ready=true`、
  `eligible_for_future_real_approval_gate_enablement_planning=true` になるが、これは将来の別Stepで
  enablement criteriaをレビューするためのevidenceという意味だけで、`approval_gate_enabled=false`、
  `allowed_for_live=false`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_copyable=false`、
  `approval_command_executable=false`、`usable_approval_artifacts_generated=false`、
  `real_approval_artifacts_available=false`、`post_attempt_limit=1`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、`public_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  Step 5XはHTTP POST、実注文、read-only API、public API、Private API、broker、live_order_once、ledger、
  real approval gate有効化/発行、real approval id生成、real approval command生成、copyable approval text生成、
  pbcopy、approval text保存には接続していない。詳細は
  [STEP5X_REAL_APPROVAL_ENABLEMENT_CRITERIA.md](STEP5X_REAL_APPROVAL_ENABLEMENT_CRITERIA.md)。
  ready criteriaはlive POST許可でもapproval gate enablement/発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5W Real approval disabled scaffold完了 / dry-run only / no usable approval artifacts / no API / no POST**。
  `backend/app/live_verification/live_order_real_approval_disabled_scaffold.py` を追加し、Step 5Vの
  `LiveOrderRealApprovalImplementationReadinessReview` をsanitized evidenceとして、将来のreal approval gate
  implementationに必要な型・表示項目・検証項目を、あえて無効化されたscaffoldとしてfail-closedで整理した。
  safe readiness reviewでは `READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW`、
  `scaffold_ready=true`、`eligible_for_future_enablement_planning=true` になるが、これは将来の別Stepで
  enablement planningを検討するためのdisabled scaffold evidenceという意味だけで、`allowed_for_live=false`、
  `approval_gate_enabled=false`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_copyable=false`、`approval_command_executable=false`、
  `usable_approval_artifacts_generated=false`、`real_approval_artifacts_available=false`、
  `post_attempt_limit=1`、`post_executed=false`、`live_order_once_called=false`、
  `private_api_called=false`、`broker_called=false`、`read_only_api_called=false`、
  `public_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。Step 5WはHTTP POST、実注文、
  real approval gate発行、real approval id生成、real approval command生成、copyable approval text生成、
  pbcopy、approval text保存、final dynamic preflight実行、post reconciliation実行、read-only API、
  public API、Private API、broker、ledgerには接続していない。詳細は
  [STEP5W_REAL_APPROVAL_DISABLED_SCAFFOLD.md](STEP5W_REAL_APPROVAL_DISABLED_SCAFFOLD.md)。
  ready scaffoldはlive POST許可でもapproval gate enablement/発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5V Real approval implementation readiness review完了 / dry-run only / no API / no POST**。
  `backend/app/live_verification/live_order_real_approval_implementation_readiness.py` を追加し、Step 5Uの
  `LiveOrderRealApprovalPreImplementationAudit` をsanitized evidenceとして、将来のreal approval gate
  implementation stepへ進む前のreadiness reviewをfail-closedで作るmodelを実装した。safe auditでは
  `READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW`、`readiness_ready=true`、
  `eligible_for_future_real_approval_gate_implementation_step=true` になるが、これは将来の別Stepで
  実承認ゲート実装を検討するためのreview evidenceという意味だけで、`allowed_for_live=false`、
  `approval_gate_issued=false`、`approval_id_generated=false`、`approval_command_generated=false`、
  `approval_command_copyable=false`、`post_attempt_limit=1`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、`public_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  Step 5VはHTTP POST、実注文、real approval gate実装/発行、real approval id生成、
  real approval command生成、final dynamic preflight実行、post reconciliation実行、read-only API、
  public API、Private API、broker、ledgerには接続していない。詳細は
  [STEP5V_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW.md](STEP5V_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW.md)。
  ready reviewはlive POST許可でもapproval gate実装/発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5Q Real approval readiness checkpoint完了 / dry-run only / no API / no POST**。
  `backend/app/live_verification/live_order_real_approval_readiness.py` を追加し、Step 5Pの
  `LiveOrderE2EDryRunChainReview` をsanitized evidenceとして、将来のreal approval gate planningへ進む前の
  readiness checkpointをfail-closedで作るmodelを実装した。ready chainに加えて、operator reviewed full chain、
  real-money risk理解、no auto-post理解、future steps separation理解、unknown means stop理解を必須にする。
  safe checkpointでは `READY_FOR_REAL_APPROVAL_READINESS_REVIEW`、`readiness_ready=true`、
  `eligible_for_future_real_approval_gate_planning=true` になるが、これは将来の別Stepで実承認設計を
  検討するためのreadiness evidenceという意味だけで、`allowed_for_live=false`、
  `approval_gate_issued=false`、`approval_id_generated=false`、`approval_command_generated=false`、
  `approval_command_copyable=false`、`post_attempt_limit=1`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。go/no-go/stop conditionsと
  readiness check resultsをsanitizedに整理する。Step 5QはHTTP POST、実注文、real approval gate発行、
  real approval id生成、real approval command生成、final dynamic preflight実行、post reconciliation実行、
  read-only API、public API、Private API、broker、ledgerには接続していない。詳細は
  [STEP5Q_REAL_APPROVAL_READINESS_CHECKPOINT.md](STEP5Q_REAL_APPROVAL_READINESS_CHECKPOINT.md)。
  ready checkpointはlive POST許可でもapproval gate発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5P E2E dry-run chain review完了 / dry-run only / no API / no POST**。
  `backend/app/live_verification/live_order_e2e_dry_run_chain.py` を追加し、Step 5B〜5Oで作成した
  `LiveOrderCandidate`、`RiskDecision`、`TraceRecord`、review report、session policy、bundle、
  operator review、approval handoff、fake approval design/preview/validation、final dynamic preflight、
  one-shot boundary、execution runbookを1本のfake/sanitized chainとして検査するmodelを実装した。
  safe chainでは `READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW`、`chain_ready=true`、
  `eligible_for_future_real_approval_planning=true` になるが、これは将来の別Stepでreal approval planningを
  検討するためのreview evidenceという意味だけで、`allowed_for_live=false`、`approval_gate_issued=false`、
  `approval_id_generated=false`、`approval_command_generated=false`、`approval_command_copyable=false`、
  `post_attempt_limit=1`、`post_executed=false`、`live_order_once_called=false`、
  `private_api_called=false`、`broker_called=false`、`read_only_api_called=false`、retry/loop/追加/変更/取消/決済禁止、
  `post_reconciliation_required=true` を維持する。stage consistency、ID consistency、symbol/side/size/
  execution_type consistency、安全flag consistency、one-shot constraintsをsanitized check resultsとして出す。
  Step 5PはHTTP POST、実注文、approval gate発行、approval id生成、approval command生成、final dynamic
  preflight実実行、post reconciliation実実行、read-only API、public API、Private API、broker、ledgerには
  接続していない。詳細は [STEP5P_E2E_DRY_RUN_CHAIN_REVIEW.md](STEP5P_E2E_DRY_RUN_CHAIN_REVIEW.md)。
  ready chainはlive POST許可でもapproval gate発行許可でもapproval command生成許可でもない。
- 直前フェーズ: **Step 5O One-shot execution runbook完了 / dry-run only / no API / no POST**。
  `backend/app/live_verification/live_order_execution_runbook.py` を追加し、Step 5Nの
  `LiveOrderOneShotBoundaryDecision` から、将来のreal approval gate、fresh final dynamic preflight、
  one-shot HTTP POST、post reconciliation、final report and stopを分離したdry-run execution runbookを作る
  modelを実装した。ready runbookはlive POST許可でもapproval gate発行許可でもない。詳細は
  [STEP5O_ONE_SHOT_EXECUTION_RUNBOOK.md](STEP5O_ONE_SHOT_EXECUTION_RUNBOOK.md)。
- 直前フェーズ: **Step 5N One-shot live boundary完了 / dry-run only / no API / no POST**。
  `backend/app/live_verification/live_order_one_shot_boundary.py` を追加し、Step 5Mの
  `LiveOrderFinalDynamicPreflightDecision` から、将来のone-shot live order boundaryをfail-closedで評価する
  dry-run modelを実装した。safeなStep 5M decisionとsafe boundary inputでは
  `READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW`、`boundary_passed=true`、
  `eligible_for_future_one_shot_live_review=true` になるが、これは将来の別Stepでreal approval gateまたは
  one-shot execution planを設計する候補という意味だけで、`allowed_for_live=false`、
  `requires_human_approval=true`、`approval_gate_required=true`、`approval_gate_issued=false`,
  `approval_id_generated=false`、`approval_command_generated=false`、`approval_command_template_only=true`、
  `approval_command_copyable=false`、`final_dynamic_preflight_required=true`、`dry_run_only=true`、
  `post_attempt_limit=1`、`post_executed=false`、`live_order_once_called=false`、
  `private_api_called=false`、`broker_called=false`、`read_only_api_called=false` を維持する。
  retry/loop/追加/変更/取消/決済禁止、body field allowlist、request body/signing body一致、
  post reconciliation planをsanitized inputとして評価する。Markdown renderingには
  `This one-shot live boundary model is dry-run only.`、`This model does not call read-only API.`、
  `This model does not call Private API.`、`This model does not call live_order_once.`、
  `This model does not execute HTTP POST.`、`This model does not authorize live POST.`、
  `allowed_for_live=false.` の警告を含める。Step 5NはHTTP POST、実注文、approval gate発行、approval id生成、
  approval command生成、final dynamic preflight実行、read-only API、Private API、public API、broker、ledgerには
  接続していない。詳細は [STEP5N_ONE_SHOT_LIVE_BOUNDARY.md](STEP5N_ONE_SHOT_LIVE_BOUNDARY.md)。
  passed boundaryはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も別Step・別承認で扱う。
- 直前フェーズ: **Step 5M Final dynamic preflight完了 / dry-run only / no API / no POST**。
  `backend/app/live_verification/live_order_final_dynamic_preflight.py` を追加し、Step 5Lの
  `LiveOrderApprovalValidationSimulation` とsanitizedな `LiveOrderFinalDynamicPreflightSnapshot` から
  fail-closedな `LiveOrderFinalDynamicPreflightDecision` を作るfinal dynamic preflight dry-run modelを実装した。
  account/assets status、open positions / active orders count、USD_JPY min order size / size step、ticker availability、
  spread、ticker age、market window、maintenance、important event、ledger unused、session attempt、daily size、
  previous result、result unknown、Git/tests/ruff/secret scan、raw response saved/displayed、outbound body allowlist、
  request body/signing body一致、final preflight ageをsanitized inputとして評価する。safe snapshotでは
  `READY_FOR_FINAL_DYNAMIC_PREFLIGHT_REVIEW`、`preflight_passed=true`、
  `eligible_for_future_one_shot_review=true` になるが、これは将来のone-shot boundary review候補という意味だけで、
  `allowed_for_live=false`、`requires_human_approval=true`、`approval_gate_required=true`、
  `approval_gate_issued=false`、`approval_id_generated=false`、`approval_command_generated=false`、
  `approval_command_template_only=true`、`approval_command_copyable=false`、
  `final_dynamic_preflight_required=true`、`dry_run_only=true` を維持する。blocked simulation、unsafe flags、
  unsupported order shape、API/preflight入力のmissing/unsafe/staleは `BLOCKED_FINAL_DYNAMIC_PREFLIGHT` として
  blocked reasonsを保持する。Markdown renderingには `This final dynamic preflight model is dry-run only.`、
  `This model does not call read-only API.`、`This model does not call Private API.`、
  `This model does not execute final dynamic preflight.`、`This model does not authorize live POST.`、
  `allowed_for_live=false.` の警告を含める。Step 5MはHTTP POST、実注文、approval gate発行、approval id生成、
  approval command生成、final dynamic preflight実行、read-only API、Private API、public API、broker、ledgerには
  接続していない。詳細は [STEP5M_FINAL_DYNAMIC_PREFLIGHT.md](STEP5M_FINAL_DYNAMIC_PREFLIGHT.md)。
  passed decisionはlive POST許可でもapproval gate発行許可でもfinal dynamic preflight実行許可でもない。
  次フェーズを行う場合も別Step・別承認で扱う。
- 直前フェーズ: **Step 5L Approval validation simulator完了 / fake validation only / no order / no POST**。
  `backend/app/live_verification/live_order_approval_validation_simulator.py` を追加し、Step 5Kの
  `LiveOrderApprovalGatePreview` とfake/template-only command入力からsanitizedな
  `LiveOrderApprovalValidationSimulation` と `LiveOrderApprovalValidationRuleResult` を作る
  approval validation simulator modelを実装した。fake templateの完全一致、TTL 300秒、同一セッション、
  未使用、ACK token、余分なtoken/改行/空白なし、placeholder-only、fake prefixをfail-closedで評価する。
  pass時は `SIMULATED_APPROVAL_VALIDATION_PASSED` になるが、これはfake validation simulationが通った
  という意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、
  `approval_gate_required=true`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_template_only=true`、
  `approval_command_copyable=false`、`final_dynamic_preflight_required=true`、`dry_run_only=true` を維持する。
  blocked preview、mismatch、TTL超過、別セッション、使用済み、ACK不足/重複、extra token、改行/余分な空白、
  real approval shape、placeholder欠落では `BLOCKED_APPROVAL_VALIDATION_SIMULATION` となり、blocked reasonsを
  保持する。Markdown renderingには `This approval validation simulation is dry-run only.`、
  `This simulation is not a real approval gate.`、`This simulation does not generate a real approval_id.`、
  `This simulation does not generate a real approval command.`、
  `This simulation does not authorize final dynamic preflight.`、
  `This simulation does not authorize live POST.`、`allowed_for_live=false.` の警告を含める。
  Step 5Lは real approval id / real approval command生成、approval gate発行、clipboard/file出力、
  final dynamic preflight、`live_order_once`、Private API、broker、HTTP client、read-only API、ledgerには
  接続していない。詳細は [STEP5L_APPROVAL_VALIDATION_SIMULATOR.md](STEP5L_APPROVAL_VALIDATION_SIMULATOR.md)。
  passed simulationはlive POST許可でもapproval gate発行許可でもfinal dynamic preflight許可でもない。
  次フェーズを行う場合も別Step・別承認で扱う。
- 直前フェーズ: **Step 5K Approval gate preview完了 / validation dry-run / no order / no POST**。
  `backend/app/live_verification/live_order_approval_gate_preview.py` を追加し、Step 5Jの
  `LiveOrderApprovalGateDesign` からsanitizedな `LiveOrderApprovalGatePreview` と
  `LiveOrderApprovalGatePreviewValidationRule` を作るapproval gate preview modelを実装した。
  ready designでは `READY_FOR_APPROVAL_GATE_PREVIEW_REVIEW` になるが、これは将来のreal approval gate前に読む
  dry-run previewという意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、
  `approval_gate_required=true`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_template_only=true`、
  `approval_command_copyable=false`、`ttl_seconds=300`、`exact_match_required=true`、
  `same_session_required=true`、`final_dynamic_preflight_required=true`、`dry_run_only=true` を維持する。
  approval idは `<APPROVAL_ID_FROM_FUTURE_STEP>` placeholderのみ、approval commandは
  `STEP_APPROVAL_TEMPLATE ...` のfake template previewのみで、実approval id、実approval command、
  copyable command、approval gate発行、pbcopy、ファイル保存は行わない。blocked designやunsafe inputでは
  `BLOCKED_APPROVAL_GATE_PREVIEW` となり、blocked reasonsを保持する。Markdown renderingには
  `This approval gate preview is dry-run only.`、`This preview is not a real approval gate.`、
  `This preview does not generate a real approval_id.`、
  `This preview does not generate a real approval command.`、
  `This preview is not copyable approval text.`、
  `This preview does not authorize live POST.`、`allowed_for_live=false.` の警告を含める。
  Step 5Kは `approval_id` / real approval command生成、approval gate発行、clipboard/file出力、
  `live_order_once`、Private API、broker、HTTP client、read-only API、ledgerには接続していない。
  詳細は [STEP5K_APPROVAL_GATE_PREVIEW.md](STEP5K_APPROVAL_GATE_PREVIEW.md)。
  ready previewはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5J Approval gate design完了 / fake approval only / no order / no POST**。
  `backend/app/live_verification/live_order_approval_gate_design.py` を追加し、Step 5Iの
  `LiveOrderApprovalHandoffPackage` からsanitizedな `LiveOrderApprovalGateDesign` と
  `LiveOrderApprovalCommandTemplate` を作るfake approval gate design modelを実装した。
  ready handoffでは `READY_FOR_APPROVAL_GATE_DESIGN_REVIEW` になるが、これは将来のreal approval gate前に読む
  dry-run設計資料という意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、
  `approval_gate_required=true`、`approval_gate_issued=false`、`approval_id_generated=false`、
  `approval_command_generated=false`、`approval_command_template_only=true`、
  `approval_command_copyable=false`、`ttl_seconds=300`、`exact_match_required=true`、
  `same_session_required=true`、`final_dynamic_preflight_required=true`、`dry_run_only=true` を維持する。
  approval idは `<APPROVAL_ID_FROM_FUTURE_STEP>` placeholderのみ、approval commandは
  `STEP_APPROVAL_TEMPLATE ...` のfake templateのみで、実approval id、実approval command、
  copyable command、approval gate発行、pbcopy、ファイル保存は行わない。blocked handoffやunsafe inputでは
  `BLOCKED_APPROVAL_GATE_DESIGN` となり、blocked reasonsを保持する。Markdown renderingには
  `This approval gate design is dry-run only.`、`This design is not an approval gate.`、
  `This design does not generate a real approval_id.`、
  `This design does not generate a real approval command.`、
  `This design does not authorize live POST.`、`allowed_for_live=false.` の警告を含める。
  Step 5Jは `approval_id` / real approval command生成、approval gate発行、`live_order_once`、
  Private API、broker、HTTP client、read-only API、ledgerには接続していない。詳細は
  [STEP5J_APPROVAL_GATE_DESIGN.md](STEP5J_APPROVAL_GATE_DESIGN.md)。
  ready designはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5I Approval handoff package完了 / no order / no POST**。
  `backend/app/live_verification/live_order_approval_handoff.py` を追加し、Step 5Hの
  `LiveOrderOperatorReviewProcedure` からsanitizedな `LiveOrderApprovalHandoffPackage` を作る
  approval handoff modelを実装した。ready operator reviewでは
  `READY_FOR_APPROVAL_HANDOFF_REVIEW` になるが、これは将来のapproval gate前に読むdry-run handoff資料という
  意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、
  `approval_gate_required=true`、`approval_gate_issued=false`、`approval_command_generated=false`、
  `final_dynamic_preflight_required=true`、`dry_run_only=true` を維持する。
  display allowed fields、display forbidden fields、future final dynamic preflight itemsを固定した。
  blocked operator reviewやunsafe inputでは `BLOCKED_HANDOFF` となり、blocked reasonsを保持する。
  Markdown renderingには `This approval handoff is dry-run only.`、
  `This handoff is not an approval gate.`、
  `This handoff does not generate approval_id or approval command.`、
  `This handoff does not authorize live POST.`、`allowed_for_live=false.` の警告を含める。
  Step 5Iは `approval_id` / approval command生成、approval gate発行、`live_order_once`、Private API、
  broker、HTTP client、read-only API、ledgerには接続していない。詳細は
  [STEP5I_APPROVAL_HANDOFF_PACKAGE.md](STEP5I_APPROVAL_HANDOFF_PACKAGE.md)。
  ready handoffはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5H Operator review procedure完了 / no order / no POST**。
  `backend/app/live_verification/live_order_operator_review.py` を追加し、Step 5Gの
  `ReviewGatedSessionBundle` からsanitizedな `LiveOrderOperatorReviewProcedure` と
  checklist itemsを作るoperator review procedure modelを実装した。
  ready bundleでは `READY_FOR_OPERATOR_CHECKLIST` になるが、これは人間が読むdry-run確認手順という
  意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、
  `approval_gate_required=true`、`dry_run_only=true` を維持する。READY checklistにはdry-run確認、
  approval gateではないこと、live POSTを許可しないこと、candidate条件、risk gate、session policy、
  残りセッション枠、残り通貨枠、future approval gate / final dynamic preflightが別Stepであることを含める。
  blocked bundleやunsafe inputでは `BLOCKED_OPERATOR_REVIEW` となり、blocked reasonsを保持し、
  `Do not proceed to approval gate` / `Do not proceed to live POST` のchecklistを出す。
  Markdown renderingには `This operator review is dry-run only.`、
  `This review is not an approval gate.`、`This review does not authorize live POST.`、
  `allowed_for_live=false.` の警告を含める。Step 5Hは `live_order_once`、Private API、broker、
  HTTP client、read-only API、ledger、approval gateには接続していない。詳細は
  [STEP5H_OPERATOR_REVIEW_PROCEDURE.md](STEP5H_OPERATOR_REVIEW_PROCEDURE.md)。
  ready operator reviewはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5G Review-gated session bundle完了 / no order / no POST**。
  `backend/app/live_verification/live_order_review_session_bundle.py` を追加し、Step 5Eの
  `LiveOrderCandidateReviewReport` とStep 5Fの `ReviewGatedSessionPolicyDecision` から
  sanitizedな `ReviewGatedSessionBundle` を作るoperation bundle modelを実装した。
  ready review + passed session policyでは `READY_FOR_OPERATOR_REVIEW` になるが、
  これは人間が読むdry-run運用判断レポート候補という意味だけで、`allowed_for_live=false`、
  `requires_human_approval=true`、`approval_gate_required=true`、`dry_run_only=true` を維持する。
  review / policy / bundle-levelの `blocked_reasons` を統合し、`remaining_sessions_today` と
  `remaining_daily_size` をsanitizedに計算する。capacityがmissing/unknown/negativeの場合はfail closedで
  `BLOCKED_BUNDLE` になる。Markdown renderingには `This operation bundle is dry-run only.`、
  `This bundle is not an approval gate.`、`This bundle does not authorize live POST.`、
  `allowed_for_live=false.` の警告を含める。Step 5Gは `live_order_once`、Private API、broker、
  HTTP client、read-only API、ledger、approval gateには接続していない。詳細は
  [STEP5G_REVIEW_GATED_SESSION_BUNDLE.md](STEP5G_REVIEW_GATED_SESSION_BUNDLE.md)。
  ready bundleはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5F Review-gated session policy完了 / no order / no POST**。
  `backend/app/live_verification/live_order_session_policy.py` を追加し、Step 5Eの
  `LiveOrderCandidateReviewReport` とsanitizedな `ReviewGatedSessionPolicySnapshot` から
  fail-closedな `ReviewGatedSessionPolicyDecision` を作るsession policy modelを実装した。
  初回micro-live完了、前回結果確定、結果不明なし、`open_positions_count=0`、
  `active_orders_count=0`、1日最大2セッション、セッション間120分以上、1セッション100通貨、
  1日合計200通貨以下、Git/tests/ruff/secret scan正常、raw response未保存・未表示、
  market window allowed、maintenance false、important event window confirmedを評価する。
  safe snapshotでは `policy_passed=true`、`eligible_for_review_session=true` になるが、
  `allowed_for_live=false`、`requires_human_approval=true`、`approval_gate_required=true`、
  `dry_run_only=true` を維持する。unknown / missing / unsafe inputは `BLOCKED` となり、
  複数の `blocked_reasons` を返す。Step 5Fは `live_order_once`、Private API、broker、
  HTTP client、read-only API、ledger、approval gateには接続していない。詳細は
  [STEP5F_REVIEW_GATED_SESSION_POLICY.md](STEP5F_REVIEW_GATED_SESSION_POLICY.md)。
  policy passはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も
  別Step・別承認で扱う。
- 直前フェーズ: **Step 5E Candidate review report完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate_review.py` を追加し、Step 5Bの
  `LiveOrderCandidate`、Step 5Cの `LiveOrderCandidateRiskDecision`、Step 5Dの
  `LiveOrderCandidateTraceRecord` からsanitizedな `LiveOrderCandidateReviewReport` を作る
  review/reporting modelを実装した。`READY_FOR_HUMAN_REVIEW` は人間が読むdry-run report候補という
  意味だけで、`allowed_for_live=false`、`requires_human_approval=true`、`approval_gate_required=true`、
  `dry_run_only=true` を維持する。risk decisionやtraceがblockedの場合は `BLOCKED_REVIEW` として
  blocked reasonsを統合し、`fix_blocked_reasons_no_post` を返す。Markdown renderingには
  `This review report is dry-run only.`、`This report is not an approval gate.`、
  `This report does not authorize live POST.`、`allowed_for_live=false.` の警告を含める。
  Step 5Eは `live_order_once`、Private API、broker、HTTP client、read-only API、ledger、approval gateには
  接続していない。詳細は [STEP5E_CANDIDATE_REVIEW_REPORT.md](STEP5E_CANDIDATE_REVIEW_REPORT.md)。
  次フェーズを行う場合も、approval gateやlive POSTへ直接進まず、別Step・別承認で扱う。
- 直前フェーズ: **Step 5D Candidate trace record完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate_trace.py` を追加し、Step 5Bの
  `LiveOrderCandidate` とStep 5Cの `LiveOrderCandidateRiskDecision` を、sanitizedな
  `source_signal_id` / `paper_trade_ref` / `shadow_run_ref` / optional decision refsへ紐付ける
  `LiveOrderCandidateTraceRecord` を実装した。`candidate_id` と `risk_decision.candidate_id` の不一致、
  `allowed_for_live=true`、dry-run / human approval / approval gate条件の欠落、source signal欠落、
  paper/shadow参照欠落、unsupported symbol/side/size/execution_typeはfail closedで `BLOCKED` になる。
  risk decisionがblockedの場合も監査用に `BLOCKED_TRACE_RECORDED` を作れるが、
  `eligible_for_human_review=false`、`allowed_for_live=false` を維持する。`READY_FOR_REVIEW` は
  review/reporting候補という意味だけで、approval gateやlive POST許可ではない。Step 5Dは
  `live_order_once`、Private API、broker、HTTP client、ledger、approval gateには接続していない。
  詳細は [STEP5D_CANDIDATE_TRACE_RECORD.md](STEP5D_CANDIDATE_TRACE_RECORD.md)。
  推奨次フェーズはStep 5E candidate review/reportingであり、引き続きno POSTとする。
- 直前フェーズ: **Step 5C Live order candidate risk gate完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate_risk_gate.py` を追加し、Step 5Bの
  `LiveOrderCandidate` とsanitizedな `LiveOrderCandidateRiskSnapshot` からfail-closedな
  `LiveOrderCandidateRiskDecision` を作るrisk gateを実装した。safe snapshotでは
  `risk_gate_passed=true`、`eligible_for_human_review=true` になるが、`allowed_for_live=false`、
  `requires_human_approval=true`、`approval_gate_required=true`、`dry_run_only=true` を維持する。
  unsafe / unknown / missing inputは `BLOCKED` となり、複数の `blocked_reasons` を返す。Step 5Cは
  risk gate passをlive POST許可とは扱わず、candidate review候補へ進めるだけで停止する。
  `live_order_once`、Private API、broker、HTTP client、ledger、approval gateには接続していない。
  詳細は [STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md](STEP5C_LIVE_ORDER_CANDIDATE_RISK_GATE.md)。
  推奨次フェーズはStep 5D/5E candidate review/reportingであり、引き続きno POSTとする。
- 直前フェーズ: **Step 5B Live order candidate dry-run model完了 / no order / no POST**。
  `backend/app/live_verification/live_order_candidate.py` を追加し、sanitizedな `StrategySignalInput` から
  非実行の `LiveOrderCandidate` またはblocked resultを作るdry-runモデルを実装した。BUY / SELL signalは
  `USD_JPY`、`size=100`、`execution_type=MARKET`、`status=REVIEW_REQUIRED` のcandidateになるが、
  `allowed_for_live=false`、`requires_human_approval=true`、`risk_gate_required=true`、
  `approval_gate_required=true`、`dry_run_only=true` を固定する。`NO_TRADE` / `hold`、unsupported symbol、
  invalid confidence、missing rationaleはcandidateなしの `BLOCKED` resultへfail closedする。
  candidate idは `LOCAND-` prefixのdeterministic dry-run IDで、order id、execution id、position id、
  client order idではない。`live_order_once`、Private API、broker、HTTP client、ledger、approval gateには
  接続していない。詳細は [STEP5B_LIVE_ORDER_CANDIDATE_DRY_RUN.md](STEP5B_LIVE_ORDER_CANDIDATE_DRY_RUN.md)。
  推奨次フェーズはStep 5C candidate risk gate implementationであり、Step 5Cもno POSTとする。
- 直前フェーズ: **Step 5A Paper / Shadow / Live接続設計レビュー完了 / no order / no POST**。
  Step 4 micro-live完了後の次フェーズとして、paper trading、shadow run、live verificationの役割分担と
  安全な接続設計を [STEP5A_PAPER_SHADOW_LIVE_CONNECTION_REVIEW.md](STEP5A_PAPER_SHADOW_LIVE_CONNECTION_REVIEW.md)
  にdocs-onlyで整理した。提案フローは `Market data -> Strategy signal -> Paper / Shadow decision record ->
  Live order candidate -> Risk gate -> Human approval gate -> Final dynamic preflight -> One-shot live POST ->
  Read-only reconciliation -> Stop`。Paperは仮想取引・仮想P/L・研究用、Shadowはpublic market data由来の
  candidate/risk/audit記録、Liveは人間承認・final preflight・one-shot ledger後にのみ扱う分離を明文化した。
  Live order candidate schema draftとrisk gate必須項目を定義したが、実装、HTTP POST、実注文、決済、取消、
  注文変更、approval id発行、approval gate、BUY/SELL live判断、Private API接続、API key / secret確認、
  ledger変更は行っていない。推奨次フェーズはStep 5B strategy signal -> live order candidate dry-run model
  であり、Step 5Bもno POSTとする。
- 直前フェーズ: **Step 4H micro-live検証完了レビュー完了 / no order / no close / no POST**。
  Step 4B〜Step 4G-Cのmicro-live検証を
  [STEP4_MICRO_LIVE_COMPLETION_REVIEW.md](STEP4_MICRO_LIVE_COMPLETION_REVIEW.md)
  に総括した。到達点は「新規注文API成功 -> ユーザー手動決済 -> read-onlyで建玉0・有効注文0確認」。
  確認できたこと、未検証範囲、安全境界、次フェーズ候補、次にlive POSTへ進む条件をdocs化した。
  BUYはユーザー指定であり、戦略システムが自動判断したものではない。決済はユーザーがGMO Web画面で
  手動実施し、Codexは決済APIを実行していない。今回のStep 4HではHTTP POST、新規注文、追加注文、
  決済注文、取消、注文変更、approval id発行、approval gate、approval command表示、ledger reset、
  credential / headers / signature / raw request / raw response / order id / execution id / position idの
  表示・保存は未実行。推奨次フェーズは、候補A paper/shadow-to-live接続設計レビュー、候補B
  戦略シグナルdry-run、候補C close API仕様調査とfake transportの順であり、候補D/Eへ直接進まない。
- 直前フェーズ: **Step 4G-C 手動決済後read-only確認完了 / MANUAL_SETTLEMENT_CONFIRMED / no order / no close**。
  ユーザー報告として、GMO Web画面から前回の `USD_JPY BUY 100通貨` 建玉を手動決済済みで、
  建玉サマリー・建玉一覧に対象取引なしと表示されている。Codex側では2026-06-26にread-only確認のみを実施し、
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認した。ledgerは
  `POST_COMPLETED`、`attempt_count=1`、`result_category=success` のままsanitized確認し、
  ledger reset / delete / edit / overwriteは行っていない。既存read-only runnerで
  `account/assets=success`、`open_positions_count=0`、`active_orders_count=0`、raw response保存なし、
  headers保存なし、credential表示なしを確認した。manual settlement API confirmationは `true`、
  position statusは `closed`、active order statusは `none`。Step 4G-CではHTTP POST、新規注文、
  追加注文、決済注文、取消、注文変更、approval id発行、approval gate、approval command表示は未実行。
  raw request / raw response、order id、execution id、position id、open price、execution price、
  timestamp、詳細損益、残高詳細、建玉詳細は表示・保存していない。今回のmicro-live検証は
  「新規注文API成功 -> ユーザー手動決済 -> read-onlyで建玉0・有効注文0確認」まで到達した。
- 直前フェーズ: **Step 4G-A 建玉read-only確認完了 / POSITION_CONFIRMED / no close / no order**。
  Step 4F-B後のOPEN建玉確認として、2026-06-26にread-only確認のみを実施した。
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認し、ledgerは
  `POST_COMPLETED`、`attempt_count=1`、`result_category=success` のままsanitized確認した。
  既存read-only runnerで `account/assets=success`、`open_positions_count=1`、
  `active_orders_count=0`、raw response保存なし、headers保存なし、credential表示なしを確認した。
  openPositionsのsanitized summaryは `position_count=1`、`symbol=USD_JPY`、`side=BUY`、
  `size_total=100`。建玉ID、注文ID、約定ID、position ID、open price、execution price、
  timestamp、詳細損益、残高詳細、建玉詳細、raw responseは表示・保存していない。public tickerは
  `bid=161.804`、`ask=161.809`、`spread_jpy=0.005`、`ticker_age_seconds=0.236`。
  判定は **POSITION_CONFIRMED**。USD/JPY 100通貨では、1円変動で概算約100円、0.1円変動で
  概算約10円の損益変動があり得る。Step 4G-AではHTTP POST、新規注文、追加注文、決済、
  取消、注文変更、approval id発行、approval gate、ledger resetは未実行。決済する場合は
  Step 4G-Bとして別タスク・別承認で扱う。
- 直前フェーズ: **Step 4F-B one-shot retry with approval gate 完了 / live order success、OPEN建玉あり**。
  `dd705dd` 対応後、2026-06-26 11:09 JSTに `STEP4F-` approval gateを発行し、
  ユーザーが同じCodexセッションで短い1行approval commandを完全一致入力した。承認後再preflightでは
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set`、`account/assets=success`、
  `open_positions_count_before=0`、`active_orders_count_before=0`、当日one-shot ledger
  `PREPARED` / `attempt_count=0`、Git clean、market window allowed、maintenance false、
  `bid=161.8`、`ask=161.805`、`spread_jpy=0.005` を確認した。HTTP POSTは承認後に1回だけ実行し、
  sanitized結果は `transport_result=success`、`api_status_success=true`、`result_unknown=false`。
  実行後read-only照合では `account/assets=success`、`open_positions_count_after=1`、
  `active_orders_count_after=0`。raw request / raw response / headers / signature / credential値 /
  order ID / execution IDは表示・保存していない。ledgerは `POST_COMPLETED`、`attempt_count=1`、
  `result_category=success`。retry、loop、追加注文、注文変更、取消、決済、自動クローズは行っていない。
  OPEN建玉が残っている可能性があるため、以後の操作は別タスク・別承認で扱う。
- 直前フェーズ: **Step 4F-APPROVAL修正完了 / runner approval仕様をStep 4F-Bへ整合**。
  Step 4F-B実行前コード確認で、Step 4F-Bプロンプトが要求する `STEP4F-` approval id prefix、
  `ACK_ORDER_PERMISSION=YES`、`ACK_IP_ACCOUNT_CHECK=YES` と既存runnerの旧Step 4 compact
  approval仕様が一致していないため、安全停止した。runner側はStep 4F-B用approval idを
  `STEP4F-` prefixに統一し、Step 4F-B用approval commandでは `ACK_ORDER_PERMISSION=YES` と
  `ACK_IP_ACCOUNT_CHECK=YES` を必須ACKとして扱う。旧compact command（追加ACKなし）と `STEP4-`
  prefixはStep 4F-B用としてfail closedする。approval TTL 300秒、承認後再preflight必須、
  最終動的preflightからPOSTまで30秒以内、HTTP POST最大1回、retry / loop禁止は維持する。
  この修正ではHTTP POST、実注文、approval id発行、approval gate発行、fresh preflight、read-only接続、
  ledger reset / delete / edit / overwrite、credential / headers / signature / raw response表示・保存は未実行。
  次回Step 4F-Bは別タスクとしてfresh preflightから再実行し、approval gateで必ず停止する。
- 直前フェーズ: **Step 4F-A sanitized retry preflight / no POST完了、READY_FOR_LATER_4F_B、
  本日再POST不可**。ユーザー報告として、GMO外国為替FX APIキー設定で「トレード > 注文」権限に
  チェックを入れた後、Codex環境では `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認した。
  read-only Private APIはsanitized出力で `account/assets=success`、`open_positions_count=0`、
  `active_orders_count=0`。public rulesはUSD_JPY `minOpenOrderSize=100` / `sizeStep=1`、
  `maxOrderSize=500000`、TRY_JPY / ZAR_JPY / MXN_JPY例外にUSD_JPYは含まれないことを確認した。
  public tickerは `bid=161.789`、`ask=161.794`、`spread_jpy=0.005`、`ticker_age_seconds=0.650`、
  service status `OPEN`、maintenance false。ただし確認時刻は `2026-06-25T14:54:16+0900 JST` で、
  初回retry候補の10:00-14:30 JST枠外。ledgerはsanitized確認のみで `POST_COMPLETED`、
  `attempt_count=1`、`result_category=api_rejected` のままなので、本日再POST不可を維持する。
  read-only successは注文権限成功を意味しない。Step 4F-Bへ進めるのは別日または明示された新ledger方針があり、
  ユーザー側permission/IP/account確認が完了し、fresh preflightが全て通る場合のみ。Step 4F-Bでも
  approval gateで停止し、即POSTしない。Step 4F-AではHTTP POST、実注文、approval id発行、approval gate、
  retry、loop、追加注文、注文変更、取消、決済、ledger reset / delete / edit / overwrite、raw response表示・保存は未実行。
- 直前フェーズ: **Step 4E GMO FX API注文権限追加後no POST確認完了 / same-day retry禁止維持**。
  ユーザー報告として、GMO外国為替FX APIキー設定で「トレード > 注文」権限にチェックを入れたことを
  `docs/STEP4_API_REJECT_REVIEW.md` に追記した。これはユーザー報告の記録であり、CodexがGMO管理画面を
  直接確認したものではなく、API上で注文権限が有効化されたことを確定確認したものでもない。
  Step 4E自体ではAPI key / secretがmissingだったためread-only確認は未実行だったが、Step 4F-Aでset環境の
  read-only no-POST preflightを実施した。
- 直前フェーズ: **Step 4D sanitized reject classification + API権限チェックリスト整備完了 / REJECT_CAUSE_PARTIAL**。
  `backend/app/live_verification/live_order_reject_classification.py` と
  `backend/app/tests/test_live_verification_live_order_reject_classification.py`、
  `docs/STEP4_API_REJECT_REVIEW.md` を追加し、前回Step 4B-Bの
  `transport_result=api_rejected` をraw responseなしで分類するlocal-only sanitized modelを整備した。
  ledgerは読み取りのみで `POST_COMPLETED`、`attempt_count=1`、
  `result_category=api_rejected` をsanitized確認し、ledger reset / delete / edit / overwriteは行っていない。
  raw error codeがないため判定は **REJECT_CAUSE_PARTIAL**。候補はAPI key scope、order permission、
  IP restriction、account procedure、account state、margin、signing、timestamp、body、size等に分け、
  user-side checklistとしてdocs化した。HTTP POST、実注文、retry、loop、追加注文、注文変更、取消、
  決済、approval id発行、BUY/SELL選択、API key / secret確認、read-only接続、raw response表示・保存は未実行。
  次候補はStep 4E user-side API permission/account/IP/settings checklist confirmationであり、
  Step 4D自体は再注文を許可しない。
- 直前実装フェーズ: **Step 4B-APPROVAL修正 短い1行approval command化完了 / Step 4B実行は未実行**。
  `backend/app/live_verification/live_order_once.py` と
  `backend/app/tests/test_live_verification_live_order_once.py` を追加し、live outbound bodyのfield allowlist、
  approval commandのexact match、300秒expiry（elapsed seconds <= 300は有効、> 300は失効）、
  persistent one-shot ledger、POST直前の`POST_STARTED`記録、
  fake transportでの1回限定実行、timeout時`RESULT_UNKNOWN`、no-retry / no-loop / no-leak guardを実装した。
  Step 4B-TTL修正では、以前の120秒固定を廃止し、実装・テスト・docsを300秒へ統一した。
  Step 4B-APPROVAL修正では、長い日本語承認文を廃止/非推奨化し、`STEP4_APPROVE <approval_id>
  SIDE=BUY|SELL SYMBOL=USD_JPY SIZE=100 ACK_...=YES` の短い1行ASCII command形式へ変更した。
  実資金損失、OPEN建玉、API scope、重要経済指標、retry / loop / 追加注文 / 注文変更 /
  取消 / 決済禁止、結果不明時停止はACK tokenで明示し、欠落、`YES`以外、余分なtoken、
  改行、余分な空白、旧日本語長文承認文はfail closedする。
  ただし承認後再preflightは引き続き必須であり、最終動的preflightからPOSTまで30秒以内の条件も緩めない。
  送信bodyは `symbol=USD_JPY`、`side=BUY|SELL`、`size="100"`、`clientOrderId`、
  `executionType=MARKET` のみで、`timeInForce` / `settleType` / price系 / internal metadataは
  live outbound bodyへ含めない。実HTTP transport関数は明示実行関数からしか使えず、API key / secretは
  関数引数のみで扱い、`.env`や環境変数は読まない。APPROVAL修正ではHTTP POST、実注文、
  approval_id発行、API key / secret確認、read-only接続、BUY/SELL選択、注文取消、決済、
  追加注文、実資金検証は未実行。Step 4B実注文は別タスク・別承認で扱う。
- 直前フェーズ: **Step 4-SPEC USD_JPY最小注文数量 仕様差異解消完了 / READY_FOR_STEP4_RETRY**。
  `docs/STEP4_SYMBOL_RULES_RECONCILIATION.md` を作成し、live public API
  `GET /public/v1/symbols`、公式商品ページ、2025-04-04お知らせ、2025-09-25お知らせ、
  API docs response exampleを照合した。live public APIではUSD_JPY
  `minOpenOrderSize=100` / `sizeStep=1`、TRY_JPY / ZAR_JPY / MXN_JPYは
  `minOpenOrderSize=10000`。公式商品ページと2025-09-25お知らせもUSD_JPYを100通貨対象に含め、
  TRY/JPY・ZAR/JPY・MXN/JPYだけを10,000通貨例外としている。API docsのUSD_JPY
  `minOpenOrderSize=10000` は `responsetime=2022-12-15` の古いresponse exampleであり、
  2025年以降の公式通知と現在のlive public APIより現行値ではないと分類した。判定は
  **READY_FOR_STEP4_RETRY**。ただしStep 4 retry、approval id、HTTP POST、実注文、
  Private API注文系接続、BUY/SELL選択、10000通貨への変更は未実行。次に進む場合も
  Step 4A retryとしてpreflightを再実行し、exact approval gateで停止すること。
  Step 3では `LiveOrderPreflightSnapshot` / `LiveOrderPreflightDecision` /
  `evaluate_live_order_preflight` をlocal-onlyで追加し、API key / secretはpresence flagのみ、
  read-only checks、open positions count、active orders count、known previous result、
  Step 2 skeleton / mock submission、tests / ruff / git、market / maintenance / event window、
  attempt count、retry / loop、kill switch、HTTP POST / real order attemptを監査対象にした。
  Step 3実装時のCodex実行環境では `GMO_FX_API_KEY: missing` /
  `GMO_FX_API_SECRET: missing` だったため、既存read-only接続手順は実行せず、Step 3判定は
  **NO_GO**。HTTP POST、実注文、実資金検証、Private API書き込み、broker、`OrderRequest`、
  real order API client、本番公開API追加には進んでいない。
  Phase 2E-4Rでは直近kline条件の
  `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk` run
  `20260622_100540_shadow_USD_JPY_gmo-public` をレビューし、実runで `REAL_PUBLIC_BID_ASK` candidate、
  `ALLOW_SHADOW` decision、対応するvirtual result、candidate/decision/virtual resultのID相関を確認した。
  古い3 stepはticker/kline skewによりcandidate生成前の`NO_TRADE`へ安全に倒れた。safety violation 0、
  broken 0、raw response保存なし、Private API/APIキー/broker/実注文なし。詳細は
  [PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md](PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md)。
  Phase 2E-5では、今後のgmo-public risk/audit継続確認をmanual only、`USD_JPY / M1 / steps 5`、
  1日1回まで、短期3回・中期5〜10回を目安に進める計画を定義した。成功/保留/停止条件、ticker/kline skew評価、
  Phase 2Fへ進む条件は
  [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。
  Phase 2E-5 1回目run `20260622_103430_shadow_USD_JPY_gmo-public` では `REAL_PUBLIC_BID_ASK` 2件、
  candidate 2件、`ALLOW_SHADOW` 1件、`REJECT_SHADOW` 1件、ALLOW時のみvirtual result、REJECT時virtual resultなし、
  `cooldown_active` reject、ticker/kline skew 2件の安全`NO_TRADE`を確認した。同日2回目は1日1回ルールにより
  未実行で停止した。詳細は
  [PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md](PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md)。
  Phase 2E-5短期3回確認レビューでは、
  `20260622_103430_shadow_USD_JPY_gmo-public`、`20260623_000652_shadow_USD_JPY_gmo-public`、
  `20260624_001906_shadow_USD_JPY_gmo-public` の3runを整理し、3回すべてで`REAL_PUBLIC_BID_ASK`、
  candidate、`ALLOW_SHADOW`、ALLOW時のみvirtual resultを確認した。1回目と3回目では`cooldown_active`による
  `REJECT_SHADOW`とREJECT時virtual resultなしを確認した。ticker/kline skewは`stale_data` / `NO_TRADE`へ
  安全fail closedし、safety violation、broken、invalid risk row、kill switch active、raw response保存、
  Private API/APIキー/broker/実注文はなし。判定は **A: Phase 2Fへ進んでよい**。ただしPhase 2F実行は
  別タスクであり、Private API、APIキー、broker、実注文、実資金、自動売買、本番公開API追加には進まない。
  詳細は [PHASE2E5_SHORT_RUNS_REVIEW.md](PHASE2E5_SHORT_RUNS_REVIEW.md)。
  Phase 3A準備では、将来のPrivate API read-only、APIキー / secret管理、Live Verification Mode、
  100通貨・1回だけの極小実資金検証までのロードマップをdocs-onlyで整理した。これは実装ではなく、
  Private API接続、APIキー入力・表示・保存、`.env`変更、broker、注文API、実注文、実資金検証には進んでいない。
  詳細は [PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md](PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md)。
  Phase 2FではPublic shadow risk/audit安定性レビューを完了し、3runすべての`REAL_PUBLIC_BID_ASK`、
  ALLOW、ALLOW時virtual result、1回目/3回目の`cooldown_active` REJECT、REJECT時virtual resultなし、
  skew / stale_dataの安全`NO_TRADE`を確認した。判定は **A: Public shadow risk/auditはPhase 3B準備へ進める水準**。
  ただしPhase 3B実装へ即進まず、先にPhase 2G Public shadow risk/auditオフライン最終デバッグ監査を
  半日程度で挟むことを推奨する。詳細は
  [PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md](PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md)。
  Phase 2Gではgmo-public再実行やコード修正を行わず、既存テスト、focused test、offline mock run、summarize、
  禁止参照確認でPublic shadow risk/auditの最終デバッグ監査を完了した。`python3 -m pytest -q` は354 passed、
  `ruff check .` はclean、focused testは177 passed。mock run
  `20260624_005528_shadow_USD_JPY_mock` ではsynthetic spreadがfail closedでREJECTされ、virtual resultは0、
  safety violation / invalid risk row / raw response保存は0だった。判定は
  **A: Phase 3B read-only公式仕様確認・実装設計へ進んでよい**。詳細は
  [PHASE2G_PUBLIC_SHADOW_RISK_AUDIT_OFFLINE_DEBUG_AUDIT.md](PHASE2G_PUBLIC_SHADOW_RISK_AUDIT_OFFLINE_DEBUG_AUDIT.md)。
  Phase 3B-0ではGMOコイン外国為替FXの公式API docsを確認し、Private REST APIのread-only候補GET endpoint、
  禁止する注文・変更・取消・決済系POST endpoint、認証・署名仕様、APIキー / secret管理、Phase 3B分割案を
  docs-onlyで整理した。Private API接続、APIキー入力、`.env`変更、backend実装、broker、注文API、実注文、
  実資金には進んでいない。詳細は
  [PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md](PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md)。
  Phase 3B-1では `backend/app/private_api/` に実接続なし・APIキー環境読込なし・`.env`読込なしの
  read-only skeleton、auth/signing helper、sanitized schemas、errors、forbidden endpoint guardを追加し、
  mocked testsとno-order-import guardを整備した。GET read-only候補だけをwhitelistし、POST/PUT/DELETEの
  注文・変更・取消・決済系endpointは例外で拒否する。Private API実接続、APIキー入力、`.env`変更、broker、
  注文API、実注文、実資金には進んでいない。
  Phase 3B-2ではread-only endpointごとのmocked tests、sanitizer、error handlingを拡張した。GET候補7件の
  mocked provider変換、sanitized `PrivateApiError`、error時no-retry、forbidden endpoint guardを確認した。
  実HTTP接続、APIキー入力、`.env`読込・変更、broker、注文API、実注文、実資金には進んでいない。次に進む場合は
  Phase 3B-3としてローカル接続前レビュー、APIキー管理手順レビュー、実接続しない運用設計確認を別タスクで扱う。
  Phase 3B-3ではPrivate API read-onlyローカル接続前レビューとして、APIキー / secret管理手順、
  read-only権限分離、`.env`安全手順、Phase 3B-4初回接続endpoint、禁止endpoint、接続前後チェックリスト、
  停止条件をdocs化した。判定は **A: Phase 3B-4 read-onlyローカル接続確認へ進んでよい**。ただしPhase 3B-4は
  別タスクであり、Phase 3B-3ではPrivate API実接続、APIキー入力、`.env`変更、broker、注文API、実注文、
  実資金には進んでいない。詳細は
  [PHASE3B3_PRIVATE_READONLY_PRECONNECT_REVIEW.md](PHASE3B3_PRIVATE_READONLY_PRECONNECT_REVIEW.md)。
  Phase 3B-4では `account/assets`、`openPositions`、`activeOrders` の3 endpointについて、
  Private API read-onlyローカル接続確認結果を総合レビューした。最終結果は3 endpoint successで、
  raw response、headers、signature、credentialsの保存・表示なし、broker、OrderRequest、注文API、
  実注文、実資金検証なしを確認した。判定は **A: Phase 3B-4 read-onlyローカル接続確認は完了**、
  **A: Phase 3C Live Verification Mode設計へ進んでよい**。ただし次タスクでも、まず設計レビューとして扱い、
  Live Verification Mode実装、broker、注文API、実注文、実資金検証へは進まない。詳細は
  [PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md](PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md)。
  Phase 3CではLive Verification Modeの定義、許可範囲、禁止範囲、注文前read-onlyチェック、risk decision /
  candidate / order intent相関、order intent設計、kill switch / STOP / fail closed条件、実注文前後の
  チェックリスト、Phase 3Dへ進む条件をdocs-onlyで整理した。Live Verification Mode実装、order intent実装、
  broker、OrderRequest、注文API、実注文、実資金検証には進んでいない。詳細は
  [PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md](PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md)。
  Phase 3C実装設計レビューでは、実装をPhase 3C-1 mocked core、Phase 3C-2 ID相関テスト、
  Phase 3C-3 dry-run統合、Phase 3D前 broker / order API実装前レビューへ分割した。order intent、
  read-only precheck、live verification state、ID相関、テスト方針をdocs-onlyで整理した。Live Verification Mode実装、
  order intent実装、broker、OrderRequest、注文API、実注文、実資金検証には進んでいない。詳細は
  [PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md](PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md)。
  Phase 3C-1では `backend/app/live_verification/` に、order intent、read-only precheck result、
  live verification state、errorsのpure mocked coreとmocked unit tests / no-order-import guardを追加した。
  `USD_JPY`、100通貨、ALLOW相当、read-only precheck passed、manual confirmation必須の条件を満たす場合だけ
  order intentを作れる。READY_FOR_ORDER_REVIEWまでで停止し、broker、OrderRequest、注文API、実注文、
  実資金検証、Private API追加接続、APIキー確認、`.env`確認には進んでいない。次に進む場合は
  Phase 3C-2 ID相関テストを別タスクで扱う。
  Phase 3C-2では `backend/app/live_verification/correlation.py` と
  `backend/app/tests/test_live_verification_id_correlation.py` を追加し、signal、candidate、risk decision、
  readonly precheck、order intent、verification runのID相関をpure mocked helperとtestsで固定した。
  必須ID欠損、verification_run_id不整合、ALLOW系以外、precheck failed、同一run内の2件目intentを
  fail closedし、READY_FOR_ORDER_REVIEWまでで停止することを確認した。broker、OrderRequest、注文API、
  実注文、実資金検証、Private API追加接続、APIキー確認、`.env`確認には進んでいない。次に進む場合は
  Phase 3C-3 dry-run統合テストを別タスクで扱う。
  Phase 3C-3では `backend/app/live_verification/dry_run.py` と
  `backend/app/tests/test_live_verification_dry_run.py` を追加し、read-only precheck、risk decision、
  ID correlation、order intent、state transition、no-order guardを1本のpure mocked dry-run flowとして接続した。
  成功系はREADY_FOR_ORDER_REVIEWまで到達し、precheck failed、ALLOW系以外、ID不整合、同一run内2件目intent、
  unsupported symbol / units、manual confirmationなし、open position / active orderあり、raw response /
  headers / credentials保存・表示フラグありはfail closedする。broker、OrderRequest、注文API、実注文、
  実資金検証、Private API追加接続、APIキー確認、`.env`確認には進んでいない。次に進む場合も、
  Phase 3D前 broker / order API実装前レビューを別タスクで行う。
  Phase 3D前レビューでは、broker / order API実装へ進む前の安全条件、禁止境界、分割計画、
  実注文前の明示承認条件をdocs-onlyで整理した。判定は
  **A: Phase 3D-0 公式仕様・危険endpoint再レビューへ進んでよい**。ただしPhase 3D前レビューでは
  broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次に進む場合も、まず
  [PHASE3D_PRE_ORDER_API_REVIEW.md](PHASE3D_PRE_ORDER_API_REVIEW.md) に従って
  Phase 3D-0 docsレビューだけを別タスクで扱う。
  Phase 3D-0では、GMOコイン外国為替FXの公式API docsと既存Phase 3B / 3C / 3D前docsに基づき、
  read-only endpointと注文系endpointを分離し、`order`、`speedOrder`、IFD / IFDOCO、change、cancel、
  `closeOrder`、`ws-auth` 系endpointをHigh risk / forbidden now / review onlyとして整理した。判定は
  **A: Phase 3D-1 order review model / final checklist mocked設計・実装へ進んでよい**。ただしPhase 3D-0でも、
  broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。詳細は
  [PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md](PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md)。
  Phase 3D-1では `backend/app/live_verification/order_review.py` と
  `backend/app/tests/test_live_verification_order_review.py` を追加し、`OrderIntent` からreview-only
  `OrderReview` を生成するpure functionと、実注文前の `FinalOrderChecklist` 評価を実装した。
  checklistは全必須項目がtrueの場合だけpassedとなり、false項目を `fail_reasons` に保持する。
  これは注文payloadではなく、broker、OrderRequest、注文API client、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次に進む場合はPhase 3D-2
  broker boundary / no-network adapter mocked設計を別タスクで扱う。
  Phase 3D-2では `docs/PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md` を作成し、
  `OrderReview` / `FinalOrderChecklist` の先に置くbroker boundary、no-network adapterの責務、
  `NoNetworkBrokerBoundaryResult` 候補、fail closed条件、no-order guard policy、Phase 3D-2A以降の分割案を
  docs-onlyで整理した。no-network adapter実装、broker、OrderRequest、注文API client、注文payload builder、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次に進む場合は
  Phase 3D-2A no-network broker boundary adapter mocked実装を別タスクで扱う。
  Phase 3D-2Aでは `backend/app/live_verification/broker_boundary.py` と
  `backend/app/tests/test_live_verification_broker_boundary.py` を追加し、
  `NoNetworkBrokerBoundaryResult` と `evaluate_no_network_broker_boundary()` をpure mocked / no-networkで実装した。
  checklist未pass、READY_FOR_ORDER_REVIEW以外、network/API key/payload/broker/real order flags、
  `USD_JPY` / 100通貨 / `live_verification` 逸脱、ID不整合は `boundary_passed=false` でfail closedする。
  broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次に進む場合はPhase 3D-2B
  fail closed / no-order guard hardeningを別タスクで扱う。
  Phase 3D-2Bでは `backend/app/tests/test_live_verification_broker_boundary.py` と
  `backend/app/tests/test_live_verification_no_order_imports.py` を強化し、複数fail closed理由の同時検出、
  no-network flag横断、ID不整合 / checklist failure / state failureの蓄積、payload / transport / credential
  フィールド非保持、HTTP client import、GMO FX env名、注文endpoint文字列、注文送信状態名、payload field名の
  実装コード混入検出を追加した。broker、OrderRequest、注文API client、注文payload builder、HTTP POST、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次に進む場合は
  Phase 3D-3 order payload builder実装前レビューを別タスクで扱う。
  Phase 3D-3では `docs/PHASE3D3_ORDER_PAYLOAD_BUILDER_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  将来のmocked order payload builderの責務、Phase 3D-4で扱ってよい候補field、
  Phase 3D-4でも扱わない注文種別、`OrderReview` / `FinalOrderChecklist` /
  `NoNetworkBrokerBoundaryResult` との関係、mocked payload candidate候補データ、fail closed条件、
  broker / API client / HTTP POSTとの分離、Phase 3D-4以降の分割案、no-order guard方針をdocs-onlyで整理した。
  order payload builder実装、order payload model実装、broker、OrderRequest、注文API client、HTTP POST、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次に進む場合は
  Phase 3D-4 mocked order payload builder実装を別タスクで扱う。
  Phase 3D-4では `backend/app/live_verification/payload_candidate.py` と
  `backend/app/tests/test_live_verification_payload_candidate.py` を追加し、`MockedOrderPayloadCandidate` と
  `build_mocked_order_payload_candidate()` をpure mocked / local-onlyで実装した。`OrderReview` /
  `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` がpassしている場合だけcandidateを生成し、
  endpoint、method、URL、request body、raw response、headers、signature、credentialは保持しない。
  broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。次に進む場合はPhase 3D-4B mocked payload builder
  fail closed / no-network guard hardeningを別タスクで扱う。
  Phase 3D-4Bでは `test_live_verification_payload_candidate.py` と
  `test_live_verification_no_order_imports.py` を強化し、candidateのfail closed、許可値固定、
  非送信・非payload本体、HTTP / credential / endpoint / env / broker混入禁止を追加で固定した。
  `payload_candidate.py` 本体は送信不能なlocal-only candidateのまま維持し、broker、OrderRequest、
  注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には
  進んでいない。次候補はPhase 3D-5 real order API client実装前レビューである。
  Phase 3D-5では `docs/PHASE3D5_REAL_ORDER_API_CLIENT_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  real order API client実装前の安全条件、まだ作らない範囲、将来扱う可能性がある最小endpoint候補、
  APIキー / secret / `.env` の扱い、実HTTP POST禁止方針、Phase 3D-6以降の推奨分割、
  実装前・実注文前の明示承認条件をdocs-onlyで整理した。判定は
  **A: Phase 3D-6 real order API client no-network skeleton / disabled-by-default設計・mock実装へ進んでよい**。
  ただしreal order API client、broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
  Phase 2E-1Hでは`app/shadow/`内の
  OrderCandidate、pure risk評価、sticky Kill switch、deterministic ID、local JSONL writer、legacy互換summarizeに
  対し、Phase 2E-1.5監査のD-1〜D-4を修正した。spread provenanceのfail closed化、malformed inputの
  reason付きreject、typed audit schema/root containment、unsafe risk rowのsummary検出を実装済みである。
  再監査では統合前必須修正なし、Phase 2E-2の設計着手可と判定した。Phase 2E-2設計では、run単位の
  KillSwitchState ownership、pre-gate、AuditLogWriteError時のexit code 2、STOPファイル、candidate/decision/
  virtual result相関、summary互換、統合test方針を整理した。実装では`--enable-shadow-risk`の明示フラグ時のみ
  STOP pre-gate、candidate生成、pure `evaluate()`、typed audit JSONL、REJECT時virtual result抑止、audit失敗時
  fail closed/exit code 2、summary/metadataのrisk情報を接続した。デフォルトrunはlegacy互換を維持する。
  Phase 2E-2.5監査では修正必須事項なし、Phase 2E-3設計へ進行可と判定した。詳細は
  [PHASE2E2_INTEGRATION_AUDIT.md](PHASE2E2_INTEGRATION_AUDIT.md)。Public ticker bid/ask連携実装、
  Private API、broker、実注文へは明示承認なしに進まない。設計は
  [PHASE2E2_SESSION_INTEGRATION_DESIGN.md](PHASE2E2_SESSION_INTEGRATION_DESIGN.md)、再監査結果は
  [PHASE2E1H_REAUDIT.md](PHASE2E1H_REAUDIT.md)、初回監査と修正追記は
  [PHASE2E1_SAFETY_AUDIT.md](PHASE2E1_SAFETY_AUDIT.md)、設計は
  [PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md) と
  [PHASE2E0_5_SAFETY_REVIEW.md](PHASE2E0_5_SAFETY_REVIEW.md) を参照する。
  Private API、APIキー、実注文、本番公開には進まない。

## 2. 完了済みフェーズ

- **v0.1 read-only reports 公開版**: `/`、`/reports`、`/reports/[run_id]`。backend は `/health` と
  `/api/reports*` の GET のみ。orders / paper / automation は公開していない。
- **Production Smoke**: `npm run e2e:prod`、7 tests passed の実績あり。
- **Phase 2A**: `backend/app/shadow/` に local-only / no-network / no-order の shadow 検証土台を実装。
- **Phase 2B**: GMO Public API read-only adapter と local CLI を実装。Public API のみで APIキー・注文なし。
- **Phase 2C**: local shadow run、demo 用 `momentum_signal`、`events.jsonl` / `summary.json` /
  `metadata.json`、仮想 PnL 集計を実装。出力は `shadow_exports/`。
- **Phase 2D**: 複数 run の集計 CLI、Markdown / CSV 出力、safety 違反検出を実装。
- **Phase 2E-3.5**: Public ticker bid/ask provenance連携監査を完了。B判定で、修正必須事項なし。
  Phase 2E-4設計または実行指示作成へ進めるが、実runやPrivate/APIキー/broker/実注文には別承認が必要。
- **Phase 2E-4.5**: gmo-public risk/audit結果レビューを完了。`ticker_kline_skew_reject_count=2` は
  安全fail closed。実runでの`REAL_PUBLIC_BID_ASK` candidate/ALLOWは未確認。
- **Phase 2E-4R**: 直近kline条件のgmo-public再確認レビューを完了。実runで`REAL_PUBLIC_BID_ASK`
  candidate、`ALLOW_SHADOW`、virtual result相関を確認。Phase 2E-5設計へ進める。
- **Phase 2E-5**: gmo-public risk/audit継続確認計画を設計。manual only、1日1回まで、
  `USD_JPY / M1 / steps 5 / --enable-shadow-risk`、短期3回・中期5〜10回、成功/保留/停止条件、
  Phase 2Fへ進む条件を定義。実行、コード変更、Private API、broker、実注文には進んでいない。
- **Phase 2E-5 1回目レビュー**: run `20260622_103430_shadow_USD_JPY_gmo-public` をレビューし、
  `REAL_PUBLIC_BID_ASK` 2件、ALLOW 1件、REJECT 1件、ALLOW時のみvirtual result、REJECT時virtual resultなし、
  1日1回ルールによる同日2回目未実行停止を確認。次は別日に2回目を1回だけ実行する。
- **Phase 2E-5短期3回確認レビュー**: 3runすべてで`REAL_PUBLIC_BID_ASK` / candidate / ALLOW /
  virtual resultを確認し、1回目と3回目で`cooldown_active` REJECTとREJECT時virtual resultなしを確認。
  safety violation、broken、invalid risk row、raw response保存、Private API/APIキー/broker/実注文はなし。
  判定はAで、Phase 2Fレビュー着手可とした。その後Phase 2Fレビューは完了済み。
- **Phase 2F Public shadow risk/audit安定性レビュー**: Phase 2E-5短期3runを安定性レビューし、
  Public shadow risk/auditはPhase 3B準備へ進める水準と判定。Phase 3B実装へ即進まず、先にPhase 2G
  オフライン最終デバッグ監査を挟むことを推奨。Private API、APIキー、broker、実注文、実資金には進んでいない。
- **Phase 2G Public shadow risk/auditオフライン最終デバッグ監査**: gmo-publicを再実行せず、既存テスト、
  focused test、offline mock run、summarize、禁止参照確認でSTOP / kill switch / audit failure /
  safety violation / duplicate / cooldown / 相関検出を監査。判定はAで、Phase 3B read-only公式仕様確認・
  実装設計へ進んでよい。ただしPrivate API接続、APIキー入力、broker、注文API、実注文、実資金には進んでいない。
- **Phase 3B-0 Private API read-only公式仕様確認・実装設計**: 公式API docsに基づき、REST GETのread-only候補、
  POSTの注文・変更・取消・決済系禁止endpoint、認証・署名、APIキー / secret管理、Phase 3B分割案を整理。
  実装・接続・APIキー入力・`.env`変更・broker・実注文はなし。
- **Phase 3B-1 mocked private readonly skeleton**: `backend/app/private_api/` のauth helper、
  readonly client skeleton、schemas、errors、mocked tests、no-order-import guardを追加。実HTTP接続、
  APIキー入力、`.env`読込、broker、注文API、実注文はなし。
- **Phase 3B-2 mocked private readonly endpoints**: GET read-only候補7件のmocked tests、
  sanitizer、sanitized error handling、forbidden endpoint guard拡張を追加。実HTTP接続、APIキー入力、
  `.env`読込・変更、broker、注文API、実注文はなし。
- **Phase 3B-3 private readonly preconnect review**: APIキー / secret管理、read-only権限分離、
  `.env`安全手順、Phase 3B-4初回endpoint、禁止endpoint、接続前後チェックリスト、停止条件をdocs化。
  判定はAだが、実接続、APIキー入力、`.env`変更、broker、注文API、実注文はなし。
- **Phase 3A準備ロードマップ設計**: Private API read-only、APIキー / secret管理、read-only境界、
  Live Verification Mode、Phase 3D極小実資金検証条件をdocs-onlyで整理。実装、接続、`.env`変更、broker、
  注文API、実注文はなし。Phase 3BへはPhase 2E-5短期確認、Phase 2Fレビュー、Phase 2G監査の完了後に、
  read-only公式仕様確認・実装設計を別タスクで扱う。
- 直近確認実績: backend 354 passed、`ruff check .` OK、production smoke 7 passed。

実績値はスナップショットであり、作業時は利用可能なコマンドで再確認する。

## 3. 安全制約と公開境界

### 公開してよい範囲

- 無害な `e2e_*` サンプルによる read-only reports と、その加工済みメタ情報。
- 実取引、実資金、APIキー、個人情報を含まない Markdown 概要。
- CSV 本文を含まないファイルメタ情報。

### 公開・実装してはいけない範囲

- Private API、APIキー、secret、`.env`、実資金、実注文。
- 残高、建玉、注文履歴、約定の取得、および注文・変更・取消。
- 実 API レスポンス、実取引由来レポート、実データ CSV、本番 DB の内容。
- paper / shadow の実行情報、シグナル、ポジション、設定・管理・実行画面の本番公開。
- 本番公開 API の追加、`backend/app/main_readonly.py` の変更、`ENABLE_LIVE_TRADING=true`。
- Render / Vercel 設定変更、DB 本番化、認証実装。
- `shadow_exports/`、集計出力、実データ入り `analysis_exports/` の commit。

公開判断の詳細は [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) を単一参照点とする。

## 4. Codex 中心運用と役割分担

- 基本運用は Codex で、指定タスクの実装・検証・commit・push を行う。ただし commit / push は依頼された場合のみ行う。
- ChatGPT は次タスクの整理、Codex 用プロンプト作成、最終報告レビューに使う。
- Claude Code は大きめの既存設計確認、安全レビュー、複数ファイルにまたがる慎重な改修時に補助的に使う。
- 重要フェーズは ChatGPT または Claude Code で設計確認してから進める。
- Private API、APIキー、実資金、実注文、本番公開 API 追加、DB、認証に近づく場合は必ず事前レビューを挟む。

## 5. 変更境界

タスクごとに、変更してよいファイルを明示して最小限に編集する。shadow 運用タスクの通常範囲は
local-only の `backend/app/shadow/`、関連する `backend/scripts/`、offline tests、関連 docs である。

明示承認なしに変更しない範囲:

- `backend/app/main_readonly.py`、`backend/app/main.py`、backend 公開 API。
- frontend 本番 UI、production smoke、Render / Vercel 設定。
- `.env`、`.env.example`、APIキー、secret、DB、broker、注文・RiskManager 経路。

## 6. 検証コマンド候補

必ず `backend/pyproject.toml` と `frontend/package.json` を先に確認し、変更範囲に必要なコマンドだけを実行する。

```bash
# backend（ローカル・offline）
cd backend
.venv/bin/pytest
.venv/bin/ruff check .

# frontend
cd frontend
npm run lint
npm run test
npm run build
npm run e2e

# production read-only smoke（非破壊。依頼・必要性がある場合のみ）
cd frontend
npm run e2e:prod
```

文書だけの変更では、リンク・記述・diff・禁止対象が未変更であることの確認を優先し、無関係な全テストを
機械的に実行しない。ネットワークを使う GMO Public CLI は自動検証に含めない。

## 7. 生成物を git add しない確認

```bash
git status --short
git status --ignored --short -- shadow_exports backend/shadow_exports analysis_exports
git diff --cached --name-only
git diff --cached --name-only | grep -E '(^|/)(shadow_exports|analysis_exports)/' && exit 1 || true
```

実 API レスポンスや集計出力が別名・別パスにないかも確認する。生成物が見つかった場合は add せず、
ユーザーの既存ファイルを勝手に削除しない。

## 8. 次タスクの始め方

1. `AGENTS.md` と本書を読む。
2. `PROJECT_STATUS.md` とタスクに関係する runbook / policy / plan を読む。
3. `git status --short --branch`、`git log -1 --oneline`、既存コードとテストを確認する。
4. 変更対象、触らない箇所、検証方法を整理する。
5. 最小変更を実装し、最大5回まで修正・再検証する。
6. 成功したら停止し、次フェーズへ自動的に進まない。

Phase 2D-2 を始める場合も、まず [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md) に沿って注文なし・local-only・
上限付き run であることを確認し、運用手順と蓄積確認だけを一つの明確なタスクとして切り出す。

## 9. 最終報告テンプレート

```markdown
# 作業報告

## 結果
- 完了 / 未完了と、その理由

## 変更内容
- 変更ファイル: `path`
- 要点

## 検証
- `実行コマンド`: 成功 / 失敗（件数や要点）
- 未実行項目と理由

## 安全確認
- Private API / APIキー / 実注文 / 実資金: なし
- 本番公開 API・設定変更: なし
- 生成物の commit: なし

## Git
- branch / commit / push の状態

## 次の候補
- 明示依頼があるまで着手しない次タスク
```

## Step 5S Follow-up

Step 5S adds a pre-approval fresh preflight dry-run model. It consumes the Step
5R real approval gate plan plus sanitized snapshot fields for account/assets,
open positions, active orders, instrument rules, ticker/spread/age,
market/maintenance/event, API scope/order permission/IP account, previous
result, session/daily limits, Git/tests/ruff/secret scan, raw response flags,
outbound body allowlist, request/signing body equality, and pre-approval
freshness.

A ready Step 5S decision keeps `allowed_for_live=false` and is only evidence for
a future separate real approval gate generation step. Step 5S does not call APIs,
issue approval, generate real approval ids or commands, make approval text
copyable, call `live_order_once`, read/write ledgers, or execute POST.

## Step 5T Follow-up

Step 5T is complete as a dry-run-only real approval gate generation package.
`backend/app/live_verification/live_order_real_approval_gate_generation_package.py`
adds `LiveOrderRealApprovalGateGenerationPackage` and builder/renderer helpers.
It consumes the Step 5S pre-approval fresh preflight decision, preserves blocked
reasons when Step 5S is blocked, and otherwise produces
`READY_FOR_REAL_APPROVAL_GATE_GENERATION_PACKAGE_REVIEW`.

Important boundary: a ready Step 5T package is review evidence only. It is not
permission to issue a real approval gate, generate a real approval id, generate
a real approval command, copy approval text, run final dynamic preflight, call
`live_order_once`, or execute POST. It keeps `allowed_for_live=false`,
`approval_gate_issued=false`, `approval_id_generated=false`,
`approval_command_generated=false`, `approval_command_copyable=false`,
`ttl_seconds=300`, `exact_match_required=true`, and
`same_session_required=true`. See
[STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md](STEP5T_REAL_APPROVAL_GATE_GENERATION_PACKAGE.md).

## Step 5U Follow-up

Step 5U is complete as a dry-run-only real approval pre-implementation safety
audit. `backend/app/live_verification/live_order_real_approval_pre_implementation_audit.py`
adds `LiveOrderRealApprovalPreImplementationAudit` and builder/renderer
helpers. It consumes the Step 5T generation package, preserves blocked reasons
when Step 5T is blocked, and otherwise produces
`READY_FOR_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT_REVIEW`.

Important boundary: a ready Step 5U audit is review evidence only. It is not
permission to issue a real approval gate, generate a real approval id, generate
a real approval command, copy approval text, run final dynamic preflight, call
`live_order_once`, or execute POST. It keeps `allowed_for_live=false`,
`approval_gate_issued=false`, `approval_id_generated=false`,
`approval_command_generated=false`, `approval_command_copyable=false`,
`post_attempt_limit=1`, `post_executed=false`, `live_order_once_called=false`,
and `retry_allowed=false` / `loop_allowed=false`.

Step 5U records residual risks, manual confirmation items, implementation
blockers, and required safety checks for TTL 300, exact match, same session,
ACK tokens, display forbidden fields, no API/broker calls, no POST, and
one-shot constraints. See
[STEP5U_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT.md](STEP5U_REAL_APPROVAL_PRE_IMPLEMENTATION_AUDIT.md).

## Step 5V Follow-up

Step 5V is complete as a dry-run-only real approval implementation readiness
review. `backend/app/live_verification/live_order_real_approval_implementation_readiness.py`
adds `LiveOrderRealApprovalImplementationReadinessReview` and builder/renderer
helpers. It consumes the Step 5U pre-implementation audit, preserves blocked
reasons when Step 5U is blocked, and otherwise produces
`READY_FOR_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW`.

Important boundary: a ready Step 5V review is review evidence only. It is not
permission to implement or issue a real approval gate, generate a real approval
id, generate a real approval command, copy approval text, run final dynamic
preflight, call `live_order_once`, or execute POST. It keeps
`allowed_for_live=false`, `approval_gate_issued=false`,
`approval_id_generated=false`, `approval_command_generated=false`,
`approval_command_copyable=false`, `post_attempt_limit=1`,
`post_executed=false`, `live_order_once_called=false`, and
`retry_allowed=false` / `loop_allowed=false`.

Step 5V records residual risks, manual confirmation items, Step 5U
implementation blockers, future implementation readiness blockers, and required
safety checks for prompt truncation review, Step 5U test/docs review, TTL 300,
exact match, same session, ACK tokens, display forbidden fields, no API/broker
calls, no POST, and one-shot constraints. See
[STEP5V_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW.md](STEP5V_REAL_APPROVAL_IMPLEMENTATION_READINESS_REVIEW.md).

## Step 5W Follow-up

Step 5W adds a disabled real approval gate scaffold dry-run model. It consumes
the Step 5V `LiveOrderRealApprovalImplementationReadinessReview` and creates
`LiveOrderRealApprovalDisabledScaffold` as sanitized review evidence for a
future separate enablement planning step.

Ready scaffolds use
`READY_FOR_DISABLED_REAL_APPROVAL_GATE_SCAFFOLD_REVIEW`,
`scaffold_ready=true`, and `eligible_for_future_enablement_planning=true`, but
this is not live execution permission and not approval gate enablement. Step 5W
keeps `allowed_for_live=false`, `approval_gate_enabled=false`,
`approval_gate_issued=false`, `approval_id_generated=false`,
`approval_command_generated=false`, `approval_command_copyable=false`,
`approval_command_executable=false`, `usable_approval_artifacts_generated=false`,
`real_approval_artifacts_available=false`, `post_attempt_limit=1`,
`post_executed=false`, and `live_order_once_called=false`.

Step 5W records future enablement requirements, disabled reasons, and check
results for disabled gate state, deferred approval id/command generation, TTL
300, exact match, same session, ACK tokens, display forbidden fields, no
API/broker calls, no POST, and one-shot constraints. It does not call read-only
API, public API, Private API, broker, `live_order_once`, ledgers, clipboard, or
POST, and it does not generate usable approval artifacts. Details:
[STEP5W_REAL_APPROVAL_DISABLED_SCAFFOLD.md](STEP5W_REAL_APPROVAL_DISABLED_SCAFFOLD.md).

## Step 6E-RR Follow-up

Step 6E-RR is complete as an offline/static route review. It adds
`LiveOrderRealApiPreflightSafeRouteReview` in
`backend/app/live_verification/live_order_real_api_preflight_safe_route_review.py`
and documents the existing route candidates, coverage matrix, gaps, and data
handling policy.

Key result: existing candidates are safe-looking but incomplete. The private
readonly script covers account/assets, open positions, and active orders; the
public market-data adapter covers public status/ticker source data. Missing
coverage remains for market-window/maintenance/holiday unknowns, instrument
rules, ticker spread/age pass status, permission scope, IP/account binding, and
previous-result-unknown state.

The review status is
`READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION`, not Step 6E-R2
execution readiness. The next task should implement a safe consolidated route or
wrapper without API execution unless separately scoped. Step 6E-RR itself did
not call API, broker, order endpoints, or `live_order_once`; did not execute
POST; did not display raw request/response, headers, signatures, credentials,
or real IDs; and keeps `allowed_for_live=false`.

## Step 6E-SC Follow-up

Step 6E-SC is complete as a no-API/no-POST safe route consolidation model.
`backend/app/live_verification/live_order_real_api_preflight_safe_route_consolidation.py`
defines sanitized private read-only input, public market input, local/static
input, data policy, consolidated sanitized result, and fail-closed status
handling.

Ready consolidation means only that a future explicit Step 6E-R2 retry can use
the consolidated safe route surface. It is not Step 6F readiness and not live
execution permission. The model keeps `allowed_for_live=false`, all API-called
flags false, `order_endpoint_called_this_step=false`,
`live_order_once_called_this_step=false`, and `post_executed_this_step=false`.
It stores no raw request/response, headers, signatures, credentials, or real
IDs.

## Step 6G Real Delegate Connection Follow-up

Step 6G-PC-OX-R-REAL-POST-DELEGATE-CONNECTION-C adds a controlled real POST
delegate connection boundary for the ledger-free source factory. The current
default approved primitive actual source route is now delegate-backed and no
longer fails solely because the delegate is missing.

This state is not POST permission. The delegate connection keeps
`actual_post_allowed=false` before a later POST-specific confirmation,
`actual_http_post_executed=false`, `post_execution_count=0`,
`retry_attempted=false`, `second_post_attempted=false`, `ledger_updated=false`,
and `actual_receipt_handoff_executed=false`.

The delegate boundary references the existing `post_live_order_with_httpx`
primitive only as a non-executing function reference. Import, construction,
summary, delegate supply, factory construction, and source callable
construction do not call it. Fake/monkeypatch tests verify exactly-once
controlled executor compatibility and safe accepted/rejected/fail-closed result
mapping without raw request/response, broker/API response, credential,
signature, header, or ID exposure.

Recommended next step:

```text
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-8
```

That later step must still show the sanitized preview and obtain a new
POST-specific explicit confirmation in the current Codex session before any
HTTP POST can be considered. Retry/repost, ledger update, attempt counter
persistence, and actual receipt handoff remain forbidden.

## Step 6G Real Delegate Runner Materialization Follow-up

Step 6G-PC-OX-R-REAL-POST-DELEGATE-RUNNER-MATERIALIZATION-C materializes the
current/default real delegate runner behind the same no-execution boundary.
The route now reports `real_post_delegate_runner_materialized=true`,
`real_post_delegate_runner_supplied=true`, `delegate_runner_missing=false`, and
`source_callable_unavailable_due_missing_runner=false`.

This is still not POST permission. Import, construction, summary rendering,
runner materialization, delegate supply, factory construction, and source
callable construction do not call the post primitive. The runner is only
reachable through the existing execution controller after a later
POST-specific confirmation, and `actual_post_allowed=false` remains the
pre-confirmation state.

Recommended next step:

```text
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-9
```

That later step must confirm repository state, prerequisites, time/trading
window, maintenance status, user monitoring availability, and absence of
important event risk before requesting a new POST-specific confirmation.
Unknown time or market state remains a CASE 2 stop.

## Step 6G Position Read-Only Source Connection Follow-up

Step 6G-PC-OX-R-POSITION-READ-ONLY-SOURCE-CONNECTION-C connects the Level 5
position route to a controlled sanitized source summary. The current/default
route no longer remains `SOURCE_MISSING_BLOCKED`; it can consume safe
`position_count_safe` and `position_status` from
`live_order_real_position_read_only_source_controlled.py`.
Without an explicit checked source summary, the default remains
`UNKNOWN_FAIL_CLOSED` and blocks entry and close planning.

Existing real read-only candidates remain
`backend/scripts/check_private_readonly_connection.py` and
`backend/app/private_api/readonly_client.py`, but the Level 5 route does not
import them directly because they sit at the credential/signing/HTTP/schema
boundary. The connected source summary is status/count only and keeps
raw position objects, broker/API responses, position/account/order/transaction
IDs, actual price/PnL values, credential values, signature values, and header
values out of route output.

This is still not POST permission and not close execution permission:
`actual_http_post_executed=false`, `close_post_executed=false`,
`retry_attempted=false`, `second_post_attempted=false`,
`ledger_updated=false`, and `receipt_handoff_executed=false`.

Recommended next step:

```text
Step 6G-PC-OX-R-CLOSE-ORDER-ROUTE-IMPLEMENTATION-C
```

## Step 6G Close Order Route Controlled Follow-up

Step 6G-PC-OX-R-CLOSE-ORDER-ROUTE-IMPLEMENTATION-C adds the planning-only close
route foundation in
`backend/app/live_verification/live_order_real_close_order_route_controlled.py`.

Close planning is allowed only for a safe `ONE_POSITION_OPEN` result with
`position_status_checked=true` and `position_count_safe=1`. Default
`UNKNOWN_FAIL_CLOSED`, no position, multiple positions, source missing, and
raw/ID/value/credential exposure blocked statuses all block close planning.

The sealed close instruction is safe-label only: `USD_JPY`, fixed `100`,
`MARKET`, and `OPPOSITE_OF_SAFE_POSITION_SIDE`. It does not contain position
ID, order ID, transaction ID, account ID, client order ID actual value, raw
position, raw request/response, broker/API response, credential value,
signature value, or header value.

This is not close execution permission. `close_execution_allowed_now=false`,
`close_post_executed=false`, `close_post_count=0`, `close_retry_allowed=false`,
`close_repost_allowed=false`, `close_second_post_allowed=false`,
`ledger_updated=false`, and `receipt_handoff_executed=false`.

Recommended next step:

```text
Step 6G-PC-OX-R-POSITION-RUNTIME-SAFE-READ-CHECK-C
```

## Step 6G Position Runtime Safe Read Check Follow-up

Step 6G-PC-OX-R-POSITION-RUNTIME-SAFE-READ-CHECK-C completed a runtime
read-only position check through safe status/count only:

```text
credential_presence_checked=true
credential_presence_available=true
runtime_read_executed=true
position_source_checked=true
position_status_checked=true
position_status=NO_POSITION
position_count_safe=0
has_open_position=false
new_entry_allowed=true
close_planning_allowed=false
close_execution_allowed_now=false
```

The safe mapper added in
`backend/app/live_verification/live_order_real_position_runtime_safe_read_controlled.py`
connects runtime safe count/status into the position route, close route, and
Level 5 contracts without importing broker, Private API, HTTP, env, order,
ledger, receipt, or `live_order_once` dependencies.

No raw response, broker/API response, raw position object, position ID, account
ID, order ID, transaction ID, trade ID, price value, PnL value, credential
value, signature value, or header value was displayed, saved, or returned.

Recommended next step:

```text
Step 6G-PC-OX-R-LEVEL5-SIGNAL-ENTRY-CYCLE-GATE-C
```

## Step 6G Manual Position Risk Check Follow-up

Step 6G-PC-OX-R-MANUAL-POSITION-RISK-CHECK-GATE-C confirms the current manual
risk state with safe fields only:

```text
position_status=MULTIPLE_POSITIONS_BLOCKED
position_count_safe=2
has_multiple_positions=true
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
```

The previous generic opposite-order close primitive is revoked for actual
settlement:

```text
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
actual_close_post_allowed_now=false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
```

GMO FX official manual/rules are now the authoritative basis for settlement
behavior. Buy and sell positions can coexist, so Codex must not treat a generic
opposite order as close settlement or net multiple positions into flat status.

Recommended next step:

```text
Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C
```

That step is read-only after operator manual flattening. No entry POST, close
POST, retry/repost, second close, ledger update, receipt handoff, raw response,
broker/API response, ID, credential, signature, header, price, PnL, or `.env`
exposure is allowed.

## Step 6G Manual Flatten Runtime Flat Reconciliation

Step 6G-PC-OX-R-MANUAL-FLATTEN-THEN-RUNTIME-FLAT-RECONCILIATION-C records the
operator manual flatten result and confirms runtime flat status with safe
status/count only:

```text
operator_manual_flatten_completed=true
position_status=NO_POSITION
position_count_safe=0
manual_flatten_reconciled=true
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
fresh_cycle_allowed=false
official_settlement_route_required=true
```

This removes the current position risk but does not complete a full auto Level
5 cycle. The generic opposite-order close primitive remains revoked and future
actual close POST remains forbidden until official settlement route review.

Recommended next step:

```text
Step 6G-PC-OX-R-GMO-OFFICIAL-SETTLEMENT-ROUTE-REVIEW-C
```

## Step 6G Fable5 Accelerated Pre-Actual Entry Self-Drive (no-POST)

STEP_6G_PC_OX_R_FABLE5_ACCELERATED_PRE_ACTUAL_ENTRY_SELF_DRIVE_NO_POST_C
(2026-07-07) は no-POST 準備Stepであり、実POST許可ではない:

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
runtime_private_GET_executed=false
read_only_runtime_confirmation_status=WAITING_FOR_OPERATOR_CURRENT_TURN_CONFIRMATION
paper_trade_evidence_status=PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY
anomaly_evidence_status=SYNTHETIC_ONLY_NOT_SUFFICIENT
local_tracking_sync_status=SYNCED_AFTER_NO_WRITE_FETCH_HEAD
actual_entry_POST_allowed=false
level5_full_auto_cycle_completed=false
```

追加: `backend/app/services/gmo_live_entry_final_preflight.py`（final preflight
package model と、残code blocker 4件の fail-closed design skeleton。default-deny・
POST不能・値露出不能・allow解決不能）、
`backend/app/tests/test_gmo_live_entry_final_preflight_no_post.py`、
`docs/ENTRY_ACTUAL_FINAL_PREFLIGHT_NO_POST_CHECKLIST.md`、
`docs/ACCELERATED_PRE_ACTUAL_ENTRY_PATH_NO_POST.md`。

次に必要なのは operator の read-only runtime confirmation 5項目
（`docs/ACCELERATED_PRE_ACTUAL_ENTRY_PATH_NO_POST.md` §7。actual POST許可入力ではない）。
actual entry POST は別Stepでのみ、current-turn exact confirmation 下で最大1回。

### Continuation: read-only runtime safe confirmation executed (no-POST)

同Step内で operator が read-only 用5項目を current-turn 完全一致で提示したため、
Phase B/C/E を実行した（実POST許可ではない）:

```text
runtime_private_GET_executed=true_read_only_once_operator_confirmed
runtime_read_result_category=READ_CONFIRMED_SAFE
credential_presence_safe_boolean=true
runtime_position_safe_status=NO_POSITION
position_count_safe=0
active_pending_order_safe_status=NO_ACTIVE_PENDING_ORDERS
active_pending_order_count_safe=0
raw_id_value_credential_exposure=false
anomaly_evidence_status=KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED
final_preflight_status=READY_FOR_OPERATOR_ENTRY_CURRENT_TURN_CONFIRMATION
actual_entry_POST_allowed=false
level5_full_auto_cycle_completed=false
```

次は別Stepでの actual entry POST 用 current-turn 入力
（RESUME_DESIGN §15.1: operator_signal_type ほか exact confirmation 群）と、
残 code blocker（production real entry transport 実装等）の解消。
詳細: `docs/ACCELERATED_PRE_ACTUAL_ENTRY_PATH_NO_POST.md` §9。

## Step 6G Production Entry Code Blockers Review-First Implementation (no-POST)

STEP_6G_PC_OX_R_PRODUCTION_ENTRY_CODE_BLOCKERS_REVIEW_FIRST_IMPLEMENTATION_NO_POST_C
(2026-07-07) は、残っていた4つの code blocker を review-first で分類し、
no-POST 範囲を fail-closed で実装した（実POST許可ではない）:

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
runtime_private_GET_execution=false
production_real_entry_transport_status=IMPLEMENTED_DISABLED_FAIL_CLOSED_NO_SEND_PATH
sealed_credential_real_operation_status=BOUNDARY_IMPLEMENTED_NO_VALUE_EXPOSURE_UNSEAL_FORBIDDEN
runtime_safe_read_real_connection_status=ADAPTER_WIRED_NO_NETWORK_FRESH_READ_REQUIRES_OPERATOR_GATE
hard_guard_allow_controlled_supply_status=DEFAULT_DENY_SUPPLY_IMPLEMENTED_NO_ALLOW_BRIDGE
final_preflight_status=WAITING_FOR_ACTUAL_ENTRY_SIGNOFF
actual_entry_POST_allowed=false
level5_full_auto_cycle_completed=false
```

追加: `backend/app/services/gmo_live_production_entry_boundary.py`、
`backend/app/tests/test_gmo_live_production_entry_boundary_no_post.py`、
`docs/PRODUCTION_ENTRY_CODE_BLOCKERS_NO_POST_REVIEW.md`。
`gmo_live_entry_final_preflight.py` は status 3種を追加する最小更新。

次に必要なのは operator の actual entry 書面 sign-off。その後、別Stepで
fresh final preflight + operator current-turn 入力（RESUME_DESIGN §15.1）が揃った
場合のみ actual entry POST を最大1回（no retry / no repost / no second POST）。

## Step 6G Actual Entry Sign-off Record (no-POST)

STEP_6G_PC_OX_R_ACTUAL_ENTRY_SIGNOFF_RECORD_NO_POST_C (2026-07-07) は
operator 書面 sign-off を no-POST で記録した（docs-only・コード変更なし）:

```text
operator_actual_entry_written_signoff_status=RECORDED_NO_POST
signoff_is_actual_post_permission=false
signoff_banks_entry_signal=false
signoff_banks_actual_post_confirmation=false
final_preflight_status=READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST
actual_entry_POST_allowed=false
actual_post=false
entry_post=false
settlement_post=false
post_count=0
level5_full_auto_cycle_completed=false
```

「READY」は実行許可ではない。actual entry POST Step では fresh workspace /
fresh runtime read / fresh final preflight / operator current-turn 入力
（RESUME_DESIGN §15.1）/ activation の reviewed 構築 / hard guard への明示 literal
供給がすべて別途必須で、最大1回・no retry / no repost / no second POST。
詳細: `docs/ACTUAL_ENTRY_SIGNOFF_RECORD_NO_POST.md`

## Step 6G Actual Entry Execution Boundary Implementation (no-POST)

STEP_6G_PC_OX_R_ACTUAL_ENTRY_EXECUTION_BOUNDARY_IMPLEMENTATION_NO_POST_C
(2026-07-07) は、直前 actual gate の BLOCKED_BEFORE_POST（送信経路ゼロ）を受け、
実送信境界を no-POST・injection-gated・fail-closed で実装した（POST 未実行）:

```text
actual_post=false
entry_post=false
post_count=0
runtime_private_GET_execution=false
credential_value_read=false
activation_boundary_status=IMPLEMENTED_FAIL_CLOSED_ONE_USE_ENTRY_ONLY
sealed_credential_actual_boundary_status=UNSEAL_INSIDE_INJECTED_SENDER_ONLY_NO_VALUE_EXPOSURE_THIS_STEP
production_entry_transport_status=SINGLE_REVIEWED_CALL_SITE_IMPLEMENTED_SENDER_INJECTION_REQUIRED_NO_NETWORK_THIS_STEP
hard_guard_controlled_supply_status=ALLOW_DERIVED_FROM_GRANTED_ACTIVATION_SINGLE_CALL_SITE_DEFAULT_DENY_NO_BRIDGE
final_preflight_status=READY_FOR_ENTRY_POST_GATE_WITH_CURRENT_TURN_CONFIRMATION
actual_entry_POST_allowed=false
level5_full_auto_cycle_completed=false
```

追加: `backend/app/services/gmo_live_actual_entry_execution_boundary.py`、
`backend/app/tests/test_gmo_live_actual_entry_execution_boundary_no_post.py`、
`docs/ACTUAL_ENTRY_EXECUTION_BOUNDARY_IMPLEMENTATION_NO_POST.md`。
`gmo_live_entry_final_preflight.py` は入力1件と status 1件を追加する最小更新。

実 HTTP 送信 / credential unseal / auth header はすべて injected sender 内部に閉じ、
本モジュールは network/credential/raw に触れない。既定 refusing sender は送信不能。
次 actual gate は「実 sender の injection + operator current-turn 入力 + fresh gate 全通過」で
entry POST 最大1回（no retry / no repost / no second POST）。コード変更なしで gate 実行に進める。
