# プロジェクト現在地（PROJECT_STATUS）

FX Strategy Lab / FX read-only レポート閲覧プロジェクトの現在地まとめ。Codex / Claude Code /
ChatGPT を横断して開発するための「現在何が完了し、次に何をすべきか」の単一参照点。
本書は事実ベースのスナップショットであり、実装の置き換えではない。

今後の基本運用は Codex 中心とする。Codex は作業開始時に [`../AGENTS.md`](../AGENTS.md) と
[CODEX_HANDOFF.md](CODEX_HANDOFF.md) を読み、固定ルールと要約済み文脈を確認する。

## 1. メタ情報

- リポジトリ: `https://github.com/kane1018/fx-strategy-lab.git`
- branch: `main`
- GitHub Actions: `FX Report E2E` 成功実績あり（`workflow_dispatch` / `pull_request`）
- **初回デプロイ: 完了済み（read-only レポート閲覧のみ）**
  - backend (Render): `https://fx-strategy-lab.onrender.com`（entrypoint `app.main_readonly:app`）
  - frontend (Vercel): `https://fx-strategy-lab.vercel.app`
  - 実値・疎通/安全確認結果は [DEPLOYMENT_RESULT.md](DEPLOYMENT_RESULT.md)

## 2. 完了済み検証（ローカル直近）

- backend: `pytest` 354 passed / `ruff check .` clean
- frontend: `npm run lint` clean / `npm run test`（Vitest）36 passed / `npm run build` 成功
- E2E: `npm run e2e`（Playwright Chromium）E2E-01〜10 passed
- 注: 数値は直近ローカル実行時のもの。最新は各検証コマンドで再確認すること。

## 3. 技術構成

- backend: FastAPI（Python 3.11、`backend/.venv`）、SQLite（`Base.metadata.create_all`）、
  pytest + ruff、設定は pydantic-settings（`app/config.py` の `Settings` / `get_settings`）。
- frontend: Next.js 15（App Router）、React 18、TypeScript、Vitest、Playwright（Chromium）。
- 主要 backend ディレクトリ: `app/{brokers,models,schemas,services,strategies,routers,tests}`、
  研究・検証スクリプト群 `backend/scripts/`。
- CI: `.github/workflows/fx-report-e2e.yml`。

## 4. 実装済み機能（事実ベース）

- 戦略エンジン / リスク制御 / ペーパートレード / シグナル監視 / デモ注文基盤（README 参照）。
  実資金取引は既定無効、ライブブローカー実装は含まず、ライブ注文要求は最終的に拒否。
- broker: ローカルデモ＋OANDA practice（practice 限定）。GMO 外国為替FX は **Public read-only のみ**
  （実注文・Private API・APIキー送信なし、`market_order` 無効化）。
- 研究・検証スクリプト（read-only ペーパー）: `paper_trade_gmo` / `paper_trade_gmo_batch` /
  `paper_analyze_gmo` / `performance_report` / 15窓ランナー7本 / regime 診断 ほか。
- 単純テクニカル研究フェーズ: **正式クローズ済み**（`rsi_reversal M5` のみ研究用ベースライン保存）。
- レポート標準化基盤（`scripts/fx_eval_common.py`）: 共通 writer、summary presence-only schema、
  `report_index_entry` / `list_report_index` / `report_detail` / `validate_*` /
  `format_report_index_markdown` / `format_report_detail_markdown`。
- **read-only レポート API**（`app/routers/reports.py`、GET のみ）:
  `/api/reports`・`/api/reports/{run_id}`・`/api/reports/markdown`・`/api/reports/{run_id}/markdown`。
  `exports_root` はサーバー固定（`ANALYSIS_EXPORTS_ROOT`）、run_id 検証、CSV 本文非返却、
  503/400/404/422 のエラー方針。
- **初回デプロイ用 read-only entrypoint**（`app/main_readonly.py`）: `GET /health` ＋ `GET /api/reports*`
  のみを公開し、注文/paper/signals/bot/automation/broker は include しない（404）。CORS は GET/OPTIONS 限定。
  既存 `app.main:app` は無変更。Render Start は `uvicorn app.main_readonly:app`（[DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md)）。
- **read-only レポート UI**（`frontend/app/reports/`）: `/reports` 一覧（safety バッジ / ERROR 行 /
  状態表示 / Markdown コピー）、`/reports/[run_id]` 詳細（7セクション + Markdown コピー、aria-live 通知・自動消去）。
- **E2E**: Playwright（Chromium）E2E-01〜10、fixture は `create_e2e_report_fixtures.py` で生成
  （実 analysis_exports 非使用）。**CI**: GitHub Actions で backend/frontend/E2E を実行。

## 4b. Phase 2A（shadow 検証土台・local-only）

- `backend/app/shadow/`（models / market_data / service）と `app/tests/test_shadow_trading.py` を追加。
  Public 由来の market data 正規化 → signal → **virtual（never-sent）order** → virtual position/PnL →
  safety → ShadowEvent の純粋ロジック（ネットワーク/broker/Private API/APIキーなし、注文送信関数なし）。
- 本番 API（`app.main_readonly:app`）には未追加・公開 UI にも未露出（local-only）。
- 設計と次フェーズ（2C shadow log / 3 Private read-only）は
  [PHASE2_SHADOW_TRADING_PLAN.md](PHASE2_SHADOW_TRADING_PLAN.md)。
- **Phase 2B（実装済み・local-only）**: GMO Public read-only adapter `app/shadow/gmo_public.py`
  （`GmoPublicMarketDataClient`）＋ CLI `scripts/fetch_gmo_public_market_data.py`。
  base `forex-api.coin.z.com/public` の `/v1/status|ticker|klines` を GET し Ticker/Candle に正規化。
  APIキー不要・Private 禁止・注文なし・保存なし・本番未公開。仕様 [GMO_PUBLIC_API_PLAN.md](GMO_PUBLIC_API_PLAN.md)。
- **Phase 2C（実装済み・local-only）**: local shadow run runner（`app/shadow/signals.py` の `momentum_signal`
  ＝demo・収益性判断ではない / `app/shadow/session.py` の `run_shadow_session` / CLI
  `scripts/run_shadow_session.py` `--source mock|gmo-public --steps N`）。candles→signal→ShadowTrader→
  events.jsonl/summary.json/metadata.json を `shadow_exports/<run_id>/`（**gitignore・commit 禁止**）に保存。
  注文なし・Private/APIキー/.env 不要。手順 [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md)。
- **Phase 2D（実装済み・local-only）**: shadow run 集計 CLI（`app/shadow/aggregate.py` ＋
  `scripts/summarize_shadow_runs.py` `--input-root shadow_exports --format markdown|csv --out <dir>`）。
  複数 summary.json を合計/by_source・symbol・interval・date 集計し **safety 違反検出**（違反時 exit 2）。
  入出力とも `shadow_exports/`（gitignore・commit 禁止）。ネットワーク/APIキー不要。安全性の継続確認が主目的
  （収益性判断は未充足）。

## 5. 未実装 / 次フェーズ候補

- **Step 5R Real approval gate plan完了 / dry-run only / no API / no POST** —
  `backend/app/live_verification/live_order_real_approval_gate_plan.py` を追加し、Step 5Qの
  `LiveOrderRealApprovalReadinessCheckpoint` をsanitized evidenceとして、将来のreal approval gate stepに
  必要な計画パッケージをfail-closedで作るmodelを実装した。planはstop and request explicit user instruction、
  future fresh preflight before approval gate、future real approval gate generation、future approval command exact-match
  validation、future post-approval final dynamic preflight、future one-shot POST boundary、future post reconciliation、
  future final report and stopを分離して記録する。safe checkpointでは
  `READY_FOR_REAL_APPROVAL_GATE_PLAN_REVIEW`、`plan_ready=true`、
  `eligible_for_future_real_approval_gate_implementation=true` になるが、これは将来の別Stepで実承認ゲートを
  設計するためのplanning evidenceという意味だけで、`allowed_for_live=false`、
  `approval_gate_issued=false`、`approval_id_generated=false`、`approval_command_generated=false`、
  `approval_command_copyable=false`、`ttl_seconds=300`、`exact_match_required=true`、
  `same_session_required=true`、`post_attempt_limit=1`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。Step 5RはHTTP POST、実注文、
  real approval gate発行、real approval id生成、real approval command生成、final dynamic preflight実行、
  post reconciliation実行、read-only API、public API、Private API、broker、ledgerには接続していない。
  詳細は [STEP5R_REAL_APPROVAL_GATE_PLAN.md](STEP5R_REAL_APPROVAL_GATE_PLAN.md)。
  ready planはlive POST許可でもapproval gate発行許可でもapproval command生成許可でもない。
- **Step 5Q Real approval readiness checkpoint完了 / dry-run only / no API / no POST** —
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
- **Step 5P E2E dry-run chain review完了 / no API / no POST** —
  `backend/app/live_verification/live_order_e2e_dry_run_chain.py` を追加し、Step 5B〜5Oの
  `LiveOrderCandidate`、`RiskDecision`、`TraceRecord`、review report、session policy、bundle、
  operator review、approval handoff、fake approval design/preview/validation、final dynamic preflight、
  one-shot boundary、execution runbookを、1本のfake/sanitized chainとして整合確認できるmodelを実装した。
  safe chainでは `READY_FOR_E2E_DRY_RUN_CHAIN_REVIEW`、`chain_ready=true`、
  `eligible_for_future_real_approval_planning=true` になるが、これは将来の別Stepでreal approval planningを
  検討するためのreview evidenceという意味だけで、`allowed_for_live=false` を維持する。stage/status/ID、
  symbol/side/size/executionType、source signal、安全flag、one-shot constraints、post reconciliation requirementを
  fail-closedで確認する。Step 5PはHTTP POST、実注文、approval gate発行、approval id生成、approval command生成、
  final dynamic preflight実行、post reconciliation実行、read-only API、public API、Private API、broker、ledgerには
  接続していない。詳細は [STEP5P_E2E_DRY_RUN_CHAIN_REVIEW.md](STEP5P_E2E_DRY_RUN_CHAIN_REVIEW.md)。
  ready chainはlive POST許可でもapproval gate発行許可でもapproval command生成許可でもない。
- **Step 5O One-shot execution runbook完了 / dry-run only / no API / no POST** —
  `backend/app/live_verification/live_order_execution_runbook.py` を追加し、Step 5Nの
  `LiveOrderOneShotBoundaryDecision` から、将来のreal approval gate、fresh final dynamic preflight、
  one-shot HTTP POST、post reconciliation、final report and stopを分離したdry-run execution runbookを作る
  modelを実装した。safe boundary + safe runbook constraintsでは
  `READY_FOR_ONE_SHOT_EXECUTION_RUNBOOK_REVIEW`、`runbook_ready=true`、
  `eligible_for_future_execution_planning=true` になるが、これは将来の別Stepで実承認・実preflight・
  one-shot executionを設計する候補という意味だけで、`allowed_for_live=false`、
  `approval_gate_issued=false`、`approval_id_generated=false`、`approval_command_generated=false`、
  `approval_command_template_only=true`、`approval_command_copyable=false`、`post_attempt_limit=1`、
  `post_executed=false`、`live_order_once_called=false`、`private_api_called=false`、
  `broker_called=false`、`read_only_api_called=false`、retry/loop/追加/変更/取消/決済禁止を維持する。
  required phases、go/no-go/stop conditions、post reconciliation planをsanitizedに整理する。
  Step 5OはHTTP POST、実注文、approval gate発行、approval id生成、approval command生成、final dynamic
  preflight実行、post reconciliation実行、read-only API、Private API、public API、broker、ledgerには接続していない。
  詳細は [STEP5O_ONE_SHOT_EXECUTION_RUNBOOK.md](STEP5O_ONE_SHOT_EXECUTION_RUNBOOK.md)。
  ready runbookはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も別Step・別承認で扱う。
- **Step 5N One-shot live boundary完了 / dry-run only / no API / no POST** —
  `backend/app/live_verification/live_order_one_shot_boundary.py` を追加し、Step 5Mの
  `LiveOrderFinalDynamicPreflightDecision` から、将来のone-shot live orderに必要な境界条件を
  fail-closedで評価するdry-run modelを実装した。safeなStep 5M decisionとsafe boundary inputでは
  `READY_FOR_ONE_SHOT_LIVE_BOUNDARY_REVIEW`、`boundary_passed=true`、
  `eligible_for_future_one_shot_live_review=true` になるが、これは将来の別Stepでapproval/execution計画を
  検討できるという意味だけで、`allowed_for_live=false`、`approval_gate_issued=false`、
  `approval_id_generated=false`、`approval_command_generated=false`、`post_executed=false`、
  `live_order_once_called=false`、`private_api_called=false`、`broker_called=false`、
  `read_only_api_called=false` を維持する。`post_attempt_limit=1`、retry/loop/追加/変更/取消/決済禁止、
  body field allowlist、request body/signing body一致、post reconciliation planをsanitizedに確認する。
  Step 5NはHTTP POST、実注文、approval gate発行、approval id生成、approval command生成、final dynamic
  preflight実行、read-only API、Private API、public API、broker、ledgerには接続していない。詳細は
  [STEP5N_ONE_SHOT_LIVE_BOUNDARY.md](STEP5N_ONE_SHOT_LIVE_BOUNDARY.md)。
  passed boundaryはlive POST許可でもapproval gate発行許可でもない。次フェーズを行う場合も別Step・別承認で扱う。
- **Step 5M Final dynamic preflight完了 / dry-run only / no API / no POST** —
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
- **Step 5L Approval validation simulator完了 / fake validation only / no order / no POST** —
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
- **Step 5K Approval gate preview完了 / validation dry-run / no order / no POST** —
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
- **Step 5J Approval gate design完了 / fake approval only / no order / no POST** —
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
- **Step 5I Approval handoff package完了 / no order / no POST** —
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
- **Step 5H Operator review procedure完了 / no order / no POST** —
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
- **Step 5G Review-gated session bundle完了 / no order / no POST** —
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
- **Step 5F Review-gated session policy完了 / no order / no POST** —
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
- **Step 5E Candidate review report完了 / no order / no POST** —
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
- **Step 5D Candidate trace record完了 / no order / no POST** —
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
- **Step 5C Live order candidate risk gate完了 / no order / no POST** —
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
- **Step 5B Live order candidate dry-run model完了 / no order / no POST** —
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
- **Step 5A Paper / Shadow / Live接続設計レビュー完了 / no order / no POST** —
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
- **Step 4H micro-live検証完了レビュー完了 / no order / no close / no POST** —
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
- **Step 4G-C 手動決済後read-only確認完了 / MANUAL_SETTLEMENT_CONFIRMED / no order / no close** —
  ユーザー報告として、GMO Web画面から前回の `USD_JPY BUY 100通貨` 建玉を手動決済済みで、
  建玉サマリー・建玉一覧に対象取引なしと表示されていることを確認した。Codex側では2026-06-26に
  read-only確認のみを実施し、`GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認した。
  ledgerは `POST_COMPLETED`、`attempt_count=1`、`result_category=success` のままsanitized確認し、
  ledger reset / delete / edit / overwriteは行っていない。既存read-only runnerで
  `account/assets=success`、`open_positions_count=0`、`active_orders_count=0`、raw response保存なし、
  headers保存なし、credential表示なしを確認した。manual settlement API confirmationは `true`、
  position statusは `closed`、active order statusは `none`。Step 4G-CではHTTP POST、新規注文、
  追加注文、決済注文、取消、注文変更、approval id発行、approval gate、approval command表示は未実行。
  raw request / raw response、order id、execution id、position id、open price、execution price、
  timestamp、詳細損益、残高詳細、建玉詳細は表示・保存していない。今回のmicro-live検証は
  「新規注文API成功 -> ユーザー手動決済 -> read-onlyで建玉0・有効注文0確認」まで到達した。
- **Step 4G-A 建玉read-only確認完了 / POSITION_CONFIRMED / no close / no order** —
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
- **Step 4F-B one-shot retry with approval gate 完了 / live order success、OPEN建玉あり** —
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
- **Step 4F-APPROVAL修正完了 / Step 4F-B approval仕様をrunnerへ反映** —
  Step 4F-B実行前コード確認で、プロンプト要求の `STEP4F-` prefix、
  `ACK_ORDER_PERMISSION=YES`、`ACK_IP_ACCOUNT_CHECK=YES` と、既存runnerの旧Step 4 compact
  approval仕様が一致していないため安全停止した。今回の修正で、Step 4F-B用approval idは
  `STEP4F-` prefixに統一し、Step 4F-B用approval commandには
  `ACK_ORDER_PERMISSION=YES` と `ACK_IP_ACCOUNT_CHECK=YES` を必須化した。追加ACKなしの旧compact
  commandと `STEP4-` prefixはStep 4F-B用としてfail closedする。approval TTL 300秒、承認後再preflight必須、
  最終動的preflightからPOSTまで30秒以内、HTTP POST最大1回、retry / loop禁止は維持する。
  この修正ではHTTP POST、実注文、approval id発行、approval gate発行、fresh preflight、read-only接続、
  ledger reset / delete / edit / overwrite、credential / headers / signature / raw response表示・保存は未実行。
  次回Step 4F-Bは別タスクとしてfresh preflightから再実行し、approval gateで必ず停止する。
- **Step 4F-A sanitized retry preflight / no POST完了、READY_FOR_LATER_4F_B、本日再POST不可** —
  ユーザー報告としてGMO外国為替FX APIキーの「トレード > 注文」権限追加後、Codex環境で
  `GMO_FX_API_KEY: set` / `GMO_FX_API_SECRET: set` を値非表示で確認した。既存read-only runnerで
  `account/assets=success`、`open_positions_count=0`、`active_orders_count=0` をsanitized確認した。
  public rulesはUSD_JPY `minOpenOrderSize=100` / `sizeStep=1` / `maxOrderSize=500000`、
  USD_JPYはTRY_JPY / ZAR_JPY / MXN_JPYの10000通貨例外に含まれない。public tickerは
  `bid=161.789`、`ask=161.794`、`spread_jpy=0.005`、`ticker_age_seconds=0.650`、service status
  `OPEN`、maintenance false。ただし確認時刻 `2026-06-25T14:54:16+0900 JST` は10:00-14:30 JST枠外。
  ledgerは `POST_COMPLETED`、`attempt_count=1`、`result_category=api_rejected` のままなので本日再POST不可。
  read-only successは注文権限成功を意味しない。Step 4F-Bへ進めるのは別日または明示された新ledger方針があり、
  ユーザー側permission/IP/account確認が完了し、fresh preflightが全て通る場合のみ。Step 4F-Bでも
  approval gateで停止し、即POSTしない。Step 4F-AではHTTP POST、実注文、approval id発行、approval gate、
  retry、loop、追加注文、注文変更、取消、決済、ledger reset / delete / edit / overwrite、raw response表示・保存は未実行。
- **Step 4E GMO FX API注文権限追加後no POST確認完了 / same-day retry禁止維持** —
  ユーザー報告として、GMO外国為替FX APIキー設定で「トレード > 注文」権限にチェックを入れたことを
  `docs/STEP4_API_REJECT_REVIEW.md` に追記した。これはユーザー報告の記録であり、CodexがGMO管理画面を
  直接確認したものではなく、API上で注文権限が有効化されたことを確定確認したものでもない。Step 4E自体では
  `GMO_FX_API_KEY: missing` / `GMO_FX_API_SECRET: missing` だったためread-only確認は未実行で、
  Step 4F-Aがset環境でのno-POST preflightとして後続実施された。
- **Step 4D sanitized reject classification + API権限チェックリスト整備完了 / REJECT_CAUSE_PARTIAL** —
  `backend/app/live_verification/live_order_reject_classification.py` と
  `backend/app/tests/test_live_verification_live_order_reject_classification.py`、
  `docs/STEP4_API_REJECT_REVIEW.md` を追加し、前回Step 4B-Bの
  `transport_result=api_rejected` をraw responseなしで分類するlocal-only sanitized modelを整備した。
  ledgerは読み取りのみで `POST_COMPLETED`、`attempt_count=1`、
  `result_category=api_rejected` をsanitized確認し、ledger reset / delete / edit / overwriteは行っていない。
  raw error codeがないため判定は **REJECT_CAUSE_PARTIAL** とし、API key scope / order permission /
  IP restriction / account procedure / account state / margin / signing / timestamp / body / size等を候補群として
  user-side checklistに分離した。HTTP POST、実注文、retry、loop、追加注文、注文変更、取消、決済、
  approval id発行、BUY/SELL選択、API key / secret確認、read-only接続、raw response表示・保存は未実行。
  次候補はStep 4E user-side API permission/account/IP/settings checklist confirmationであり、
  Step 4D自体は再注文を許可しない。
- **Step 4B-APPROVAL修正 短い1行approval command化完了 / approval gate再発行可能** —
  `backend/app/live_verification/live_order_once.py` と
  `backend/app/tests/test_live_verification_live_order_once.py` を追加し、Step 4B用の
  one-shot live runner、live outbound body serializer、approval command exact match、300秒expiry、
  persistent one-shot ledger、fake transport検証、no-retry / no-loop / no-leak guardを実装した。
  Step 4B-TTL修正では以前の120秒固定を廃止し、`LIVE_ORDER_APPROVAL_TTL_SECONDS=300`、
  `elapsed_seconds <= 300` は有効、`elapsed_seconds > 300` は失効として実装・テスト・docsを統一した。
  Step 4B-APPROVAL修正では、長い日本語承認文を廃止/非推奨化し、`STEP4_APPROVE <approval_id>
  SIDE=BUY|SELL SYMBOL=USD_JPY SIZE=100 ACK_...=YES` の短い1行ASCII command形式へ変更した。
  `ACK_RISK` / `ACK_OPEN_POSITION` / `ACK_API_SCOPE` / `ACK_NO_EVENT` / retry・loop・追加注文・
  注文変更・取消・決済禁止 / 結果不明時停止のACK tokenをすべて必須とし、欠落、`YES`以外、
  余分なtoken、改行、余分な空白、旧日本語長文承認文はfail closedする。
  承認後再preflightは引き続き必須であり、最終動的preflightからPOSTまで30秒以内の条件も維持する。
  live outbound bodyは `symbol=USD_JPY`、`side=BUY|SELL`、`size="100"`、`clientOrderId`、
  `executionType=MARKET` のallowlistのみで、`timeInForce` / `settleType` / price系 /
  internal metadataは送信bodyに含めない。persistent ledgerはGit管理外の
  `~/.local/state/fx-strategy-lab/live-order-attempts/YYYY-MM-DD.json` を想定し、credential、
  headers、signature、raw request / raw response、口座詳細を保存しない。APPROVAL修正では
  HTTP POST、実注文、approval_id発行、API key / secret確認、read-only接続、BUY/SELL選択、
  注文取消、決済、追加注文、実資金検証は未実行。
  Step 4Bは別タスク・別承認で扱う。
- **Step 4-SPEC USD_JPY最小注文数量 仕様差異解消完了 / READY_FOR_STEP4_RETRY** —
  `docs/STEP4_SYMBOL_RULES_RECONCILIATION.md` を作成し、live public API
  `GET /public/v1/symbols`、公式商品ページ、2025-04-04お知らせ、2025-09-25お知らせ、
  API docs response exampleを照合した。live public APIではUSD_JPY
  `minOpenOrderSize=100` / `sizeStep=1`、TRY_JPY / ZAR_JPY / MXN_JPYは
  `minOpenOrderSize=10000`。公式商品ページと2025-09-25お知らせも、USD_JPYを
  100通貨対象に含め、TRY/JPY・ZAR/JPY・MXN/JPYだけを10,000通貨例外としている。
  API docsのUSD_JPY `minOpenOrderSize=10000` は `responsetime=2022-12-15` の
  古いresponse exampleであり、2025年以降の公式通知と現在のlive public APIより現行値ではないと分類した。
  判定は **READY_FOR_STEP4_RETRY**。ただしStep 4 retry、approval id、HTTP POST、実注文、
  Private API注文系接続、BUY/SELL選択、10000通貨への変更は未実行。
- **Step 3 独立した最終監査・preflight完了（今回実行はNO_GO）** —
  `backend/app/live_verification/live_order_preflight.py` と
  `backend/app/tests/test_live_verification_live_order_preflight.py`、
  `docs/STEP3_LIVE_ORDER_PREFLIGHT_REVIEW.md` を追加し、Step 4直前の
  `LiveOrderPreflightSnapshot` / `LiveOrderPreflightDecision` /
  `evaluate_live_order_preflight` をlocal-onlyで実装した。`api_key_present` /
  `api_secret_present` はset/missing相当のpresence flagのみを扱い、credential値、
  headers値、signature値、raw request、raw response、request URL、口座詳細、建玉詳細、
  注文詳細は保持しない。`live_order_allowed_now=false` と
  `requires_separate_user_approval=true` を固定し、Step 3中の
  `manual_approval_present_for_execution=true` はfail closedで拒否する。
  初回実注文前preflightとして `max_daily_attempts=1`、session/daily attempt 0、
  retry禁止、loop禁止、result unknown停止、open positions / active orders存在時停止を評価する。
  このCodex実行環境では `GMO_FX_API_KEY: missing` /
  `GMO_FX_API_SECRET: missing` だったため、既存read-only接続手順は実行せず、
  Step 3判定は **NO_GO**。HTTP POST、実注文、実資金検証、Private API書き込み、
  broker、`OrderRequest`、real order API client、本番公開API追加には進んでいない。
  Step 4へ進むには、別タスクでAPIキーpresenceがsetである環境からread-only preflightを再実行し、
  `READY_FOR_STEP4_PROMPT` を得たうえで、さらにユーザーの明示承認が必要。
- **Step 2 HTTP client / 注文送信skeleton + 安全機構統合完了** —
  `backend/app/live_verification/order_submission_skeleton.py` を追加し、
  `ActualHeadersSignatureBundle` の後段に `OrderSubmissionSafetyContext` /
  `OrderSubmissionSafetyDecision`、`DisabledOrderSubmissionSkeletonResult`、
  `MockOrderSubmissionSkeletonResult` をlocal-onlyで実装した。manual approval必須、
  open positionsなし、active ordersなし、previous result known、result unknown時停止、
  session attempt 0、daily attempt上限、retry禁止、loop禁止をfail closedで評価する。
  `/private/v1/order` と `POST` はallowlist metadataとしてのみ保持し、HTTP client import、
  HTTP POST、Private API追加接続、broker、`OrderRequest`、real order API client、注文API client、
  実注文、実資金検証には進んでいない。公開resultにはAPIキー値、secret値、signature値、
  headers値、raw request、raw response、status code、response bodyを保持しない。
  `backend/app/tests/test_live_verification_order_submission_skeleton.py` と
  `backend/app/tests/test_live_verification_no_order_imports.py` でno-leak / no-secret /
  no-network / no-order guardを追加・更新した。次候補はStep 3: 独立した最終監査・preflight。
- **Step 1統合 / Phase 3D-16D actual headers / signature + mock transport完了** —
  `backend/app/live_verification/actual_headers_signature.py` と
  `backend/app/live_verification/mock_signed_transport.py` を追加し、
  `ActualOrderRequestBody` の後段に `ActualHeadersSignatureBundle` と
  `MockSignedOrderTransportResult` をlocal-onlyで実装した。署名用body serializationは安定JSONとして
  メモリ上でのみ作成し、HMAC-SHA256 hex署名と認証headerは関数境界内の一時値とprivate redacted objectに
  閉じ込める。公開bundle / transport resultにはheader名、algorithm名、summary flagだけを保持し、
  APIキー値、secret値、signature値、headers値、raw request、raw responseは保持しない。
  `backend/app/tests/test_live_verification_actual_headers_signature.py`、
  `backend/app/tests/test_live_verification_mock_signed_transport.py`、
  `backend/app/tests/test_live_verification_no_order_imports.py` でno-leak / no-secret / no-network /
  no-order guardを追加・更新した。HTTP client import、HTTP POST、Private API追加接続、broker、
  `OrderRequest`、real order API client、注文API client、実注文、実資金検証には進んでいない。
  次候補はStep 2: HTTP client / 注文送信skeleton + 安全機構統合。ただしStep 2でもdisabled-by-default /
  mock検証中心とし、実HTTP POST、実注文、実資金検証には進まない。
- **Phase 3D-16C actual headers / signature 最小実装前レビュー完了** —
  `docs/PHASE3D16C_ACTUAL_HEADERS_SIGNATURE_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  Phase 3D-16Bまでで安全固定した `ActualOrderRequestBody` の後段として、actual headers生成、
  actual signature生成、API key / API secret取扱い、signer / headers builder / body modelの責務分離、
  headers値 / signature値 / credential値の非表示・非保存、HTTP POSTへ進まない境界、
  fail closed条件、Phase 3D-16D以降の分割案をdocs-onlyで整理した。actual headers生成、
  actual signature生成、HMAC処理、HTTP request実装、HTTP client import、HTTP POST、APIキー値確認、
  secret値確認、`.env`確認、Private API追加接続、broker、`OrderRequest`、real order API client、
  注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-16D actual headers / signature最小実装。ただしPhase 3D-16DでもHTTP POST、
  実注文、実資金検証には進まない。
- **Phase 3D-16B actual body no-leak hardening完了** —
  `backend/app/tests/test_live_verification_actual_order_body.py` と
  `backend/app/tests/test_live_verification_no_order_imports.py` を強化し、
  `ActualOrderRequestBody` がactual headers、actual signature、HTTP payload、raw request / raw response、
  credential値、HTTP client、endpoint、responseを保持しないことを追加確認した。unsafeな
  `SignatureHeadersBodyPlan` flagや、actual body側の複数unsafe flag同時指定はfail closedで拒否する。
  `actual_order_body.py` 本体は変更せず、local-only / no-HTTP / no-secret / no-orderの境界を維持した。
  actual headers生成、actual signature生成、HMAC処理、HTTP request実装、HTTP client import、HTTP POST、
  APIキー値表示、secret値表示、`.env`確認、Private API追加接続、broker、`OrderRequest`、
  real order API client、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-16C actual headers / signature最小実装前レビュー。ここでもHTTP POST、
  実注文、実資金検証には進まない。
- **Phase 3D-16A actual request body最小実装完了** —
  `backend/app/live_verification/actual_order_body.py` と
  `backend/app/tests/test_live_verification_actual_order_body.py` を追加し、
  `SignatureHeadersBodyPlan` の後段に送信しないlocal-onlyの `ActualOrderRequestBody` と
  `build_actual_order_request_body()` を実装した。`symbol=USD_JPY`、`size=100`、
  `executionType=MARKET`、`timeInForce=FAK`、`settleType=OPEN`、`side=BUY|SELL` のみを許可し、
  `body_created=true`、`http_post_enabled=false`、`headers_created=false`、
  `signature_created=false`、`raw_request_saved=false`、`raw_response_saved=false`、
  `credential_values_logged=false`、`real_order_attempted=false` を固定する。unsafe plan、
  unsupported body fields、安全flag逸脱、未知sideはfail closedで拒否する。actual headers生成、
  actual signature生成、HMAC処理、HTTP request実装、HTTP client import、HTTP POST、
  APIキー値表示、secret値表示、`.env`確認、Private API追加接続、broker、`OrderRequest`、
  real order API client、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-16B actual body no-leak hardening。ここでもactual headers生成、actual signature生成、
  HTTP request、HTTP POST、実注文、実資金検証には進まない。
- **Phase 3D-15 actual body / headers / signature 最小実装前レビュー完了** —
  `docs/PHASE3D15_ACTUAL_BODY_HEADERS_SIGNATURE_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  Phase 3D-14Bまでで強化した `SignatureHeadersBodyPlan` を前提に、actual request body生成、
  actual headers生成、actual signature生成の責務分離、APIキー / secret値非表示、raw request /
  raw response / headers / signature非保存、HTTP POSTへ進まない境界、fail closed条件、
  Phase 3D-16以降の分割案をdocs-onlyで整理した。Phase 3D-12で
  `GMO_FX_API_KEY: set`、`GMO_FX_API_SECRET: set` と確認済みだが、APIキー値、secret値、
  `.env`内容は表示していない。actual body生成、actual headers生成、actual signature生成、
  HMAC処理、HTTP request実装、HTTP client import、HTTP POST、Private API追加接続、broker、
  `OrderRequest`、real order API client、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-16 actual body / headers / signature 最小実装。Phase 3D-16でもHTTP POST、
  HTTP request送信、実注文、実資金検証には進まない。
- **Phase 3D-14B SignatureHeadersBodyPlan no-secret / no-network / no-order guard hardening完了** —
  `backend/app/tests/test_live_verification_signature_headers_body_plan.py` と
  `backend/app/tests/test_live_verification_no_order_imports.py` を強化し、
  `SignatureHeadersBodyPlan` がactual body、actual headers、actual signature、HTTP request、
  HTTP POST、credential値、raw request / raw response、headers / signature保存、broker、
  `OrderRequest`、real order API clientへ変質しないことを追加で固定した。
  credential / raw artifact系の複数unsafe flagは `plan_passed=false` と複数 `fail_reasons` で
  fail closedする。`signature_headers_body_plan.py` 本体は変更していない。
  実署名生成、HMAC処理、headers生成、request body生成、HTTP request実装、HTTP client import、
  HTTP POST、APIキー値表示、secret値表示、`.env`確認、broker、`OrderRequest`、real order API client、
  注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-15 actual body / headers / signature 最小実装前レビュー。ここでもまずdocs-onlyで扱い、
  実署名、headers生成、request body生成、HTTP request、HTTP POST、実注文には進まない。
- **Phase 3D-14 署名 / headers / request body plan実装完了** —
  `backend/app/live_verification/signature_headers_body_plan.py` と
  `backend/app/tests/test_live_verification_signature_headers_body_plan.py` を追加し、
  `DisabledHttpRequestClientSkeletonPlan` の後段に plan-only / local-only の
  `SignatureHeadersBodyPlan` と `build_signature_headers_body_plan()` を実装した。
  `body_plan_created=true`、`headers_plan_created=true`、`signature_plan_created=true` のplan markerだけを許可し、
  actual body、actual headers、actual signature、HTTP POST、credential value exposure、raw request /
  raw response、headers / signature保存、HMAC、real order attemptはすべてfalseで固定する。
  unsafe skeletonまたはplan flagは `plan_passed=false` と `fail_reasons` でfail closedする。
  APIキー値表示、secret値表示、`.env`確認、実署名生成、HMAC処理、headers生成、request body生成、
  HTTP request実装、HTTP client import、HTTP POST、broker、OrderRequest、real order API client、
  注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-14B no-secret guard hardening。ここでも実署名、headers生成、request body生成、
  HTTP request、実注文なしでguard強化として扱う。
- **Phase 3D-13 署名 / headers / request body 実装前レビュー完了** —
  `docs/PHASE3D13_SIGNATURE_HEADERS_BODY_PRE_IMPLEMENTATION_REVIEW.md` を作成し、
  Phase 3D-12でAPIキー環境変数が `set` とだけ確認済みであることを前提に、署名責務、
  headers責務、request body責務、責務分離、Phase 3D-14で作ってよいplan-only候補、
  Phase 3D-14でも作らないもの、fail closed条件、Phase 3D-14以降の分割案をdocs-onlyで整理した。
  署名生成、HMAC処理、headers生成、request body生成、HTTP request実装、HTTP client import、
  HTTP POST、Private API接続、APIキー値表示、API secret値表示、`.env`確認、broker、OrderRequest、
  real order API client、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-14 signature / headers / request body plan実装。ただしactual body、actual headers、
  actual signature、HTTP POST、実注文なしのplan-onlyとして扱う。
- **Phase 3D-12 APIキー確認専用レビュー完了** —
  `docs/PHASE3D12_API_KEY_PRESENCE_REVIEW.md` を作成し、`GMO_FX_API_KEY` と
  `GMO_FX_API_SECRET` の存在有無を `set` / `missing` だけで確認した。結果は
  `GMO_FX_API_KEY: set`、`GMO_FX_API_SECRET: set`。APIキー値、secret値、`.env`内容、
  環境変数一覧は表示していない。Private API接続、HTTP request実装、署名実装、headers生成、
  request body生成、HTTP POST、broker、OrderRequest、real order API client、実注文、実資金検証には
  進んでいない。
- **Phase 3D-11 実注文直前preflightレビュー完了** —
  `docs/PHASE3D11_REAL_ORDER_PREFLIGHT_REVIEW.md` を作成し、実注文に進む前のpreflight定義、
  現在のno-network chain、直前read-only precheck条件、技術チェックリスト、注文条件チェックリスト、
  APIキー / secret / `.env` を扱う前の条件、HTTP request / 署名実装へ進む前の条件、
  ユーザー明示承認の形式、即停止条件、実注文後の停止・確認条件、Phase 3D-12以降の分割案を
  docs-onlyで整理した。APIキー確認、`.env`確認、HTTP request実装、HTTP client import、HTTP POST、
  headers生成、request body生成、actual signature生成、broker、OrderRequest、real order API client、
  注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-12 APIキー確認専用レビュー。ここでも値表示や実注文ではなく、set / missingのみの
  レビューとして扱う。
- **Phase 3D-10B HTTP request skeleton no-network / no-secret guard hardening完了** —
  `backend/app/live_verification/http_request_skeleton.py` と
  `backend/app/tests/test_live_verification_http_request_skeleton.py` を更新し、
  unsafeな `SignatureHttpRequestDesignModel` またはskeleton flagを成功扱いせず、
  `skeleton_passed=false` と複数 `fail_reasons` でfail closedするよう強化した。
  `test_live_verification_no_order_imports.py` では実装コードに `hmac`、HTTP client import、
  実endpoint、credential参照、HTTP / response系fieldが混入しないguardを強化した。
  HTTP request実装、HTTP client import、HTTP POST、headers生成、request body生成、実署名生成、
  APIキー確認、API secret参照、`.env`確認、broker、OrderRequest、real order API client、注文API client、
  実注文、実資金検証には進んでいない。
  次候補はPhase 3D-11 実注文直前preflightレビュー。ここでも実注文実行ではなくレビューとして扱う。
- **Phase 3D-10 HTTP request client skeleton no-network実装完了** —
  `backend/app/live_verification/http_request_skeleton.py` と
  `backend/app/tests/test_live_verification_http_request_skeleton.py` を追加し、
  `SignatureHttpRequestDesignModel` の後段に `DisabledHttpRequestClientSkeletonPlan` と
  `build_disabled_http_request_client_skeleton_plan()` をpure mocked / no-network / disabled-by-defaultで実装した。
  `disabled_by_default=true`、`network_enabled=false`、`credential_access_enabled=false`、
  `http_client_enabled=false`、`http_post_enabled=false`、headers / request body / actual signature /
  raw request / raw response / credential / HMAC / real order flags falseだけを許可し、unsafe flagやID欠損は
  fail closedする。HTTP client import、HTTP POST、headers生成、request body生成、実署名生成、
  APIキー確認、API secret参照、`.env`確認、broker、OrderRequest、real order API client、注文API client、
  実注文、実資金検証には進んでいない。
  次候補はPhase 3D-10B HTTP request skeleton no-network / no-secret guard hardening。
- **Phase 3D-9 HTTP request client skeleton disabled-by-default設計レビュー完了** —
  `docs/PHASE3D9_HTTP_REQUEST_CLIENT_SKELETON_DESIGN_REVIEW.md` を作成し、
  HTTP request client skeletonの定義、disabled-by-default不変条件、既存modelとの関係、
  Phase 3D-10で作ってよい候補、Phase 3D-10でも作らないもの、fail closed条件、
  no-order / no-secret / no-network guard方針、Phase 3D-10以降の分割案をdocs-onlyで整理した。
  HTTP request client skeleton実装、HTTP client import、HTTP POST、headers生成、request body生成、
  実署名生成、APIキー確認、API secret参照、`.env`確認、broker、OrderRequest、real order API client、
  注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-10 HTTP request client skeleton no-network実装。ただしHTTP client import、POST、
  headers、request body、credential、実注文なし。
- **Phase 3D-8B no-secret / no-network guard hardening完了** —
  `backend/app/tests/test_live_verification_signature_request_design.py` と
  `backend/app/tests/test_live_verification_no_order_imports.py` を強化し、
  `SignatureHttpRequestDesignModel` が実署名・HMAC・credential・HTTP requestへ変質しないことを追加確認した。
  `signing_source_candidate` は4つのdesign-only tokenだけで構成され、実HTTP method、実endpoint、
  API header名、secret、request body、raw request / raw responseを含まない。`signature_request_design.py` 限定で
  `hmac` / `hashlib` / HTTP client importがないこともAST guardで固定した。実署名生成、HMAC処理、
  APIキー確認、API secret参照、`.env`確認、HTTP request builder、HTTP client、headers生成、
  request body生成、HTTP POST、broker、OrderRequest、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-9 HTTP request client skeleton disabled-by-default設計レビュー。
- **Phase 3D-8 signature / request design model mocked実装完了** —
  `backend/app/live_verification/signature_request_design.py` と
  `backend/app/tests/test_live_verification_signature_request_design.py` を追加し、
  `SignatureHttpRequestDesignModel` と `build_signature_http_request_design_model()` をpure mocked /
  design-onlyで実装した。`DisabledOrderClientPlan` と `MockedOrderPayloadCandidate` が安全条件を満たす場合だけ、
  `ORDER_CREATE_*_LABEL` と `TIMESTAMP_PLACEHOLDER` からplaceholder-onlyの
  `signing_source_candidate` を生成する。実署名生成、HMAC処理、hmac/hashlib import、APIキー確認、
  API secret参照、`.env`確認、HTTP request builder、HTTP client、headers生成、request body生成、
  HTTP POST、broker、OrderRequest、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-8B no-secret / no-network guard hardening。
- **Phase 3D-7 署名・HTTP request設計レビュー完了** —
  `docs/PHASE3D7_SIGNATURE_HTTP_REQUEST_DESIGN_REVIEW.md` を作成し、GMO Private APIの署名仕様、
  `API-KEY` / `API-TIMESTAMP` / `API-SIGN` の扱い、request bodyと署名対象文字列の関係、
  HTTP requestをまだ作らない境界、APIキー / secret / `.env` をまだ扱わない境界、fail closed条件、
  Phase 3D-8以降の分割案、no-order / no-secret guard方針をdocs-onlyで整理した。署名生成、HMAC処理、
  timestamp生成、HTTP request builder、HTTP client、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、broker、OrderRequest、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-8 signature / request design model mocked実装。ただし実署名・APIキー・HTTPなし。
- **Phase 3D-6 real order API client no-network skeleton / disabled-by-default mock実装完了** —
  `backend/app/live_verification/order_client_skeleton.py` と
  `backend/app/tests/test_live_verification_order_client_skeleton.py` を追加し、
  `DisabledOrderClientPlan` と `build_disabled_order_client_plan()` をpure mocked / local-onlyで実装した。
  `MockedOrderPayloadCandidate` がpass済みの場合だけ、`USD_JPY`、100通貨、`MARKET`、`FAK`、`OPEN`、
  `disabled_by_default=true`、`network_enabled=false`、`credential_access_enabled=false`、
  manual confirmation必須のno-network planを生成する。endpoint、method、path、url、request body、
  raw response、headers、signature、credentialは保持しない。HTTP client import、HTTP POST、
  APIキー確認、`.env`確認、broker、OrderRequest、注文API client、実注文、実資金検証には進んでいない。
  次候補はPhase 3D-7 署名・HTTP request設計レビュー。ただし実送信なし。
- **Phase 3D-5 real order API client実装前レビュー完了** —
  `docs/PHASE3D5_REAL_ORDER_API_CLIENT_PRE_IMPLEMENTATION_REVIEW.md` を作成し、real order API client
  実装前の安全条件、まだ作らない範囲、将来扱う可能性のある最小endpoint候補、APIキー / secret /
  `.env` の扱い、実HTTP POST禁止方針、Phase 3D-6以降の推奨分割、実装前・実注文前の明示承認条件を
  docs-onlyで整理した。判定は **A: Phase 3D-6 real order API client no-network skeleton /
  disabled-by-default設計・mock実装へ進んでよい**。ただしreal order API client、broker、OrderRequest、
  注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には
  進んでいない。
- **Phase 3D-4B mocked payload candidate no-send / fail-closed hardening完了** —
  `MockedOrderPayloadCandidate` のfail closed、許可値固定、非送信・非payload本体、
  no-order-import guardを追加強化した。`execution_type=MARKET`、`time_in_force=FAK`、
  `settle_type=OPEN` だけをlocal-only値として許可し、表記揺れや他値は拒否する。candidateは
  endpoint、method、URL、request body、raw response、headers、signature、credentialを保持しない。
  broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。次候補はPhase 3D-5 real order API client実装前レビュー。
- **Phase 3D-4 mocked order payload builder実装完了** —
  `backend/app/live_verification/payload_candidate.py` と
  `backend/app/tests/test_live_verification_payload_candidate.py` を追加し、`MockedOrderPayloadCandidate` と
  `build_mocked_order_payload_candidate()` をpure mocked / local-onlyで実装した。`OrderReview` /
  `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` がpassしている場合だけ、`USD_JPY`、100通貨、
  `live_verification`、manual only、no-network flags falseのcandidateを生成する。endpoint、method、URL、
  request body、raw response、headers、signature、credentialは保持しない。broker、OrderRequest、
  注文API client、HTTP POST、Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には
  進んでいない。次候補はPhase 3D-4B mocked payload builder fail closed / no-network guard hardening。
- **Phase 3D-3 order payload builder実装前レビュー完了** —
  `docs/PHASE3D3_ORDER_PAYLOAD_BUILDER_PRE_IMPLEMENTATION_REVIEW.md` を作成し、将来のmocked
  order payload builderの定義、Phase 3D-4で扱ってよい候補field、扱わない注文種別、
  `OrderReview` / `FinalOrderChecklist` / `NoNetworkBrokerBoundaryResult` との関係、
  mocked payload candidate候補データ、fail closed条件、broker / API client / HTTP POSTとの分離、
  Phase 3D-4以降の分割案、no-order guard方針をdocs-onlyで整理した。order payload builder実装、
  order payload model実装、broker、OrderRequest、注文API client、HTTP POST、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次候補は
  Phase 3D-4 mocked order payload builder実装。
- **Phase 3D-2B fail closed / no-order guard hardening完了** —
  `backend/app/tests/test_live_verification_broker_boundary.py` で複数fail closed理由の同時検出、
  no-network flag横断、ID不整合 + checklist failure + state failureの蓄積、payload / transport / credential
  フィールド非保持を追加確認した。`test_live_verification_no_order_imports.py` はHTTP client import、
  GMO FX env名、注文endpoint文字列、注文送信状態名、payload field名を実装コード側で検出するよう強化した。
  broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次候補は
  Phase 3D-3 order payload builder実装前レビュー。
- **Phase 3D-2A no-network broker boundary adapter mocked実装完了** —
  `backend/app/live_verification/broker_boundary.py` と
  `backend/app/tests/test_live_verification_broker_boundary.py` を追加し、
  `NoNetworkBrokerBoundaryResult` と `evaluate_no_network_broker_boundary()` をpure mocked / no-networkで実装した。
  `FinalOrderChecklist` 未pass、READY_FOR_ORDER_REVIEW以外、network/API key/payload/broker/real order flags、
  `USD_JPY` / 100通貨 / `live_verification` 逸脱、ID不整合は `boundary_passed=false` でfail closedする。
  broker、OrderRequest、注文API client、注文payload builder、HTTP POST、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次候補は
  Phase 3D-2B fail closed / no-order guard hardening。
- **Phase 3D-2 broker boundary / no-network adapter mocked設計完了** —
  `docs/PHASE3D2_BROKER_BOUNDARY_NO_NETWORK_ADAPTER_DESIGN.md` を作成し、
  `OrderReview` / `FinalOrderChecklist` の先に置くbroker boundary、no-network adapterの責務、
  `NoNetworkBrokerBoundaryResult` 候補、fail closed条件、no-order guard policy、Phase 3D-2A以降の分割案を
  docs-onlyで整理した。no-network adapter実装、broker、OrderRequest、注文API client、注文payload builder、
  Private API追加接続、APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。次候補は
  Phase 3D-2A no-network broker boundary adapter mocked実装。
- **Phase 3D-1 order review model / final checklist mocked実装完了** —
  `backend/app/live_verification/order_review.py` と
  `backend/app/tests/test_live_verification_order_review.py` を追加し、`OrderIntent` からreview-only
  `OrderReview` を生成するpure functionと、実注文前の `FinalOrderChecklist` 評価を実装した。
  final checklistは全必須項目がtrueの場合のみpassedとなり、false項目を `fail_reasons` に保持する。
  broker、OrderRequest、注文API client、注文payload builder、Private API追加接続、APIキー確認、
  `.env`確認、実注文、実資金検証には進んでいない。次候補は
  Phase 3D-2 broker boundary / no-network adapter mocked設計。
- **Phase 3D-0 GMO FX order API公式仕様・危険endpoint再レビュー完了** —
  `docs/PHASE3D0_ORDER_API_OFFICIAL_SPEC_REVIEW.md` を作成し、公式docsと既存Phase 3B / 3C / 3D前docsに基づいて、
  read-only endpointと注文系endpointを分離し、`order`、`speedOrder`、IFD / IFDOCO、change、cancel、
  `closeOrder`、`ws-auth` 系endpointをHigh risk / review only / forbidden nowとして整理した。判定は
  **A: Phase 3D-1 order review model / final checklist mocked設計・実装へ進んでよい**。ただし、
  Phase 3D-0ではbroker、OrderRequest、注文API client、注文payload builder、Private API追加接続、
  APIキー確認、`.env`確認、実注文、実資金検証には進んでいない。
- **Phase 3D前 broker / order API実装前レビュー完了** — `docs/PHASE3D_PRE_ORDER_API_REVIEW.md` を作成し、
  Phase 3C-3 dry-run統合後の現在地、broker / order API実装前の必須条件、禁止境界、
  100通貨・`USD_JPY`・1回限定・manual only維持方針、Phase 3D-0〜3D-5分割案、
  実注文前の明示承認条件をdocs-onlyで整理した。判定は
  **A: Phase 3D-0 公式仕様・危険endpoint再レビューへ進んでよい**。ただし、broker、
  OrderRequest、注文API、注文payload builder、Private API追加接続、APIキー確認、`.env`確認、
  実注文、実資金検証には進んでいない。
- **Phase 3C-3 Live Verification dry-run統合テスト完了** — `backend/app/live_verification/dry_run.py` と
  `backend/app/tests/test_live_verification_dry_run.py` を追加し、read-only precheck、risk decision、
  ID correlation、order intent、state transitionをpure mocked flowとして接続した。成功系は
  READY_FOR_ORDER_REVIEWまで到達し、precheck failed、ALLOW系以外、ID不整合、同一run内2件目intent、
  unsupported symbol / units、manual confirmationなし、安全フラグ違反はfail closedする。broker、
  OrderRequest、注文API、実注文、実資金検証、Private API追加接続、APIキー確認、`.env`確認には
  進んでいない。次候補はPhase 3D前 broker / order API実装前レビュー。
- **Phase 3C-2 Live Verification ID相関テスト完了** — `backend/app/live_verification/correlation.py` と
  `backend/app/tests/test_live_verification_id_correlation.py` を追加し、signal、candidate、risk decision、
  readonly precheck、order intent、verification runのID相関をpure mocked範囲で検証した。必須ID欠損、
  verification_run_id不整合、ALLOW系以外、precheck failed、同一run内の2件目intentはfail closedする。
  READY_FOR_ORDER_REVIEWまでで停止し、broker、OrderRequest、注文API、実注文、実資金検証、
  Private API追加接続、APIキー確認、`.env`確認には進んでいない。次候補はPhase 3C-3 dry-run統合テスト。
- **Phase 3C-1 Live Verification mocked core実装完了** — `backend/app/live_verification/` に
  order intent、read-only precheck result、live verification state、errorsのpure mocked / dry-run coreを追加し、
  mocked unit testsとno-order-import guardを整備した。`USD_JPY`、100通貨、ALLOW相当、precheck passed、
  manual confirmation必須の条件を満たす場合だけorder intentを作れる。READY_FOR_ORDER_REVIEWまでで停止し、
  broker、OrderRequest、注文API、実注文、実資金検証、Private API追加接続、APIキー確認、`.env`確認には
  進んでいない。次候補はPhase 3C-2 ID相関テスト。
- **Phase 3C Live Verification Mode実装設計レビュー完了** — Phase 3C設計を前提に、
  Phase 3C-1 mocked core、Phase 3C-2 ID相関テスト、Phase 3C-3 dry-run統合、Phase 3D前
  broker / order API実装前レビューへ分割した。order intent、read-only precheck、live verification state、
  ID相関、テスト方針、Phase 3D前レビュー条件をdocs-onlyで整理した。Live Verification Mode実装、
  order intent実装、broker、OrderRequest、注文API、実注文、実資金検証には進んでいない。詳細は
  [PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md](PHASE3C_IMPLEMENTATION_DESIGN_REVIEW.md)。
- **Phase 3C Live Verification Mode設計完了** — Phase 3D極小実資金検証前の安全設計として、
  Live Verification Modeの定義、許可範囲、禁止範囲、注文前read-onlyチェック、risk decision /
  candidate / order intent相関、order intent設計、kill switch / STOP / fail closed条件、実注文前後の
  チェックリスト、Phase 3Dへ進む条件をdocs-onlyで整理した。Phase 3CではLive Verification Mode実装、
  order intent実装、broker、OrderRequest、注文API、実注文、実資金検証には進んでいない。詳細は
  [PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md](PHASE3C_LIVE_VERIFICATION_MODE_DESIGN.md)。
- **Phase 3B-4 Private API read-onlyローカル接続確認 総合レビュー完了** — `account/assets`、
  `openPositions`、`activeOrders` の3 endpointについて、read-onlyローカル接続確認結果を総合レビューした。
  3 endpointはいずれも最終successで、raw response、headers、signature、credentialsの保存・表示なし、
  broker、OrderRequest、注文API、実注文、実資金検証なしを確認した。判定は
  **A: Phase 3B-4 read-onlyローカル接続確認は完了**、
  **A: Phase 3C Live Verification Mode設計へ進んでよい**。ただしPhase 3C実装、broker、注文API、
  実注文、実資金検証には進まない。詳細は
  [PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md](PHASE3B4_PRIVATE_READONLY_CONNECTION_REVIEW.md)。
- **Phase 3B-3 private readonly preconnect review完了** — Private API read-onlyローカル接続前レビューとして、
  APIキー / secret管理、read-only権限分離、`.env`安全手順、Phase 3B-4初回接続endpoint、
  禁止endpoint、接続前後チェックリスト、停止条件をdocs化した。判定は
  **A: Phase 3B-4 read-onlyローカル接続確認へ進んでよい**。ただしPhase 3B-3ではPrivate API実接続、
  APIキー入力、`.env`変更、broker、注文API、実注文、実資金には進んでいない。次に進む場合は
  Phase 3B-4として、別タスクで1回だけread-onlyローカル接続確認を扱う。
- **Phase 3B-2 mocked private readonly endpoints拡張完了** — `backend/app/private_api/` の
  mocked read-only client / schemas / errorsに、endpoint別mocked tests、error response sanitizer、
  forbidden endpoint guard拡張を追加した。対象は `account/assets`, `openPositions`, `activeOrders`,
  `orders`, `executions`, `latestExecutions`, `positionSummary` のGET候補のみ。実HTTP接続、APIキー入力、
  `.env`読込・変更、broker、注文API、実注文、実資金には進んでいない。次に進む場合はPhase 3B-3として
  ローカル接続前レビュー、APIキー管理手順レビュー、実接続しない運用設計確認を別タスクで扱う。
- **Phase 3B-1 mocked private readonly skeleton実装完了** — `backend/app/private_api/` に
  実接続なし・APIキー環境読込なし・`.env`読込なしのread-only skeleton、auth/signing helper、
  sanitized schemas、errors、forbidden endpoint guardを追加し、mocked testsを整備した。GET read-only候補だけを
  whitelistし、POST/PUT/DELETEの注文・変更・取消・決済系endpointは例外で拒否する。`app.brokers`、
  `OrderRequest`、`submit/send/place/cancel/amend`、`dotenv`、`os.environ`、`getenv`、`ENABLE_LIVE_TRADING`
  の混入をAST testで監視する。Private API実接続、APIキー入力、`.env`変更、broker、注文API、実注文、
  実資金には進んでいない。
- **Phase 3B-0 Private API read-only公式仕様確認・実装設計完了** — GMOコイン外国為替FXの公式API docs
  （`https://api.coin.z.com/fxdocs/`）を確認し、Private REST APIのread-only候補GET endpoint、禁止する
  注文・変更・取消・決済系POST endpoint、認証・署名仕様、APIキー / secret管理、Phase 3B分割案を
  docs-onlyで整理した。Private API接続、APIキー入力、`.env`変更、backend実装、broker、注文API、実注文、
  実資金には進んでいない。次に進む場合はPhase 3B-1としてmocked read-only skeleton / auth helper /
  schemas / no-order-import testsから開始する。詳細は
  [PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md](PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md)。
- **Phase 2G Public shadow risk/auditオフライン最終デバッグ監査完了** — gmo-publicは再実行せず、
  既存テスト、focused test、offline mock run、summarize、禁止参照確認でPublic shadow risk/auditの
  STOP / kill switch / audit failure / safety violation / duplicate / cooldown / candidate-decision-virtual result相関を
  監査した。`python3 -m pytest -q` は354 passed、`ruff check .` はclean、focused testは177 passed。
  mock run `20260624_005528_shadow_USD_JPY_mock` ではsynthetic spreadがfail closedでREJECTされ、
  virtual resultは生成されず、safety violation / invalid risk row / raw response保存は0だった。
  判定は **A: Phase 3B read-only公式仕様確認・実装設計へ進んでよい**。ただし、Phase 3B実装・Private API接続・
  APIキー入力・broker・注文API・実注文・実資金には進まない。詳細は
  [PHASE2G_PUBLIC_SHADOW_RISK_AUDIT_OFFLINE_DEBUG_AUDIT.md](PHASE2G_PUBLIC_SHADOW_RISK_AUDIT_OFFLINE_DEBUG_AUDIT.md)。
- **Phase 2F Public shadow risk/audit安定性レビュー完了** — Phase 2E-5短期3runをレビューし、
  Public shadow risk/auditは **A: Phase 3B準備へ進める水準** と判定した。3回すべてで`REAL_PUBLIC_BID_ASK`、
  candidate、`ALLOW_SHADOW`、ALLOW時のみvirtual resultを確認し、1回目と3回目では`cooldown_active` REJECTと
  REJECT時virtual resultなしを確認した。skew / stale_dataは`NO_TRADE`へ安全fail closedし、safety violation /
  broken / invalid risk row / raw response保存 / Private API / APIキー / broker / 実注文はなし。ただしPhase 3B実装へ
  即進まず、先に **Phase 2G Public shadow risk/audit オフライン最終デバッグ監査** を半日程度で挟むことを推奨する。
  詳細は [PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md](PHASE2F_PUBLIC_SHADOW_RISK_AUDIT_STABILITY_REVIEW.md)。
- **Phase 2E-5短期3回確認レビュー完了** — `20260622_103430_shadow_USD_JPY_gmo-public`、
  `20260623_000652_shadow_USD_JPY_gmo-public`、`20260624_001906_shadow_USD_JPY_gmo-public` をレビューし、
  3回すべてで`REAL_PUBLIC_BID_ASK`、candidate、`ALLOW_SHADOW`、ALLOW時のみvirtual resultを確認した。
  1回目と3回目では`cooldown_active`による`REJECT_SHADOW`とREJECT時virtual resultなしを確認した。
  ticker/kline skewは3回とも`stale_data` / `NO_TRADE`へ安全fail closedし、safety violation / broken /
  invalid risk row / kill switch active / raw response保存 / Private API / APIキー / broker / 実注文はなし。
  判定は **A: Phase 2Fへ進んでよい**。ただしPhase 2F実行は別タスクとし、Private APIや実注文には進まない。
  詳細は [PHASE2E5_SHORT_RUNS_REVIEW.md](PHASE2E5_SHORT_RUNS_REVIEW.md)。
- **Phase 3A準備ロードマップ設計完了** — Private API read-only、APIキー / secret管理、
  Live Verification Mode、極小実資金検証までの段階的ロードマップをdocs-onlyで整理した。これは実装ではなく、
  Private API接続、APIキー入力・表示・保存、`.env`変更、broker、注文API、実注文、実資金検証には進んでいない。
  Phase 2F、Phase 2G、Phase 3B-0は完了したが、Phase 3B実装はまだ行っていない。
  詳細は
  [PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md](PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md)。
- **Phase 2E-5 1回目レビュー / 2回目実行前整理完了** — run
  `20260622_103430_shadow_USD_JPY_gmo-public` をレビューし、`REAL_PUBLIC_BID_ASK` 2件、candidate 2件、
  `ALLOW_SHADOW` 1件、`REJECT_SHADOW` 1件、ALLOW時のみvirtual result、REJECT時virtual resultなしを確認した。
  REJECT理由は `cooldown_active`。ticker/kline skew 2件は`NO_TRADE`へ安全に倒れた。safety violation /
  broken / invalid risk row / raw response保存 / Private API / APIキー / broker / 実注文はなし。同日2回目は
  1日1回ルールにより未実行で停止し、次は別日に2回目を1回だけ行う。詳細は
  [PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md](PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md)。
- **Phase 2E-5 gmo-public risk/audit継続確認計画 設計完了** — Phase 2E-4Rで確認済みの
  `REAL_PUBLIC_BID_ASK` candidate、`ALLOW_SHADOW`、virtual result、ID相関を前提に、次回以降の
  gmo-public risk/audit runをmanual onlyで継続確認する計画を整理した。初期条件は
  `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk`、1日1回まで。短期3回・中期5〜10回を目安に、
  success / hold / stop条件、ticker/kline skew評価、評価指標、Phase 2Fへ進む条件を定義した。
  Phase 2FはPrivate APIではなくPublic shadow risk/auditのレビュー・安定性評価・運用計画として扱う。
  詳細は [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。
  今回は設計のみで、gmo-public再実行、コード変更、Private API、APIキー、broker、実注文には進んでいない。
- **Phase 2E-4R REAL_PUBLIC_BID_ASK runレビュー完了** — 直近kline条件の
  `20260622_100540_shadow_USD_JPY_gmo-public` をレビューし、実runで
  `REAL_PUBLIC_BID_ASK` candidate、`ALLOW_SHADOW` decision、対応するvirtual result、candidate/decision/
  virtual resultのID相関を確認した。古い3 stepはticker/kline skewにより安全に`NO_TRADE`へ倒れた。
  safety violation / broken / raw response保存 / Private API / APIキー / broker / 実注文はなし。
  これによりPhase 2E-5**設計**へ進める。ただしPhase 2E-5実装、Private API、実注文には進まない。
  詳細は [PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md](PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md)。
- **Phase 2E-4.5 gmo-public risk/audit結果レビュー完了** — Phase 2E-4の
  `20260622_094837_shadow_USD_JPY_gmo-public` をレビューし、`ticker_kline_skew_reject_count=2` は
  ticker/kline timestamp skewの安全fail closedであり、safety violationやPublic ticker fetch failureではないと整理した。
  実runでの`REAL_PUBLIC_BID_ASK` candidate/ALLOW/virtual result相関はまだ未確認。次は別タスクで、当日・直近klineの
  1回限定再確認を第一候補とし、skew閾値緩和や設計変更は急がない。詳細は
  [PHASE2E4_GMO_PUBLIC_RISK_AUDIT_REVIEW.md](PHASE2E4_GMO_PUBLIC_RISK_AUDIT_REVIEW.md)。
- **Phase 2E-3.5 Public ticker bid/ask provenance連携監査完了（B判定）** — Phase 2E-3実装を
  レビューし、GMO Public ticker由来bid/askだけが`REAL_PUBLIC_BID_ASK`になること、kline-onlyがsynthetic
  spread rejectを維持すること、invalid/missing/stale/future/skew tickerがfail closedになること、raw responseを
  保存しないこと、summary/metadata互換を壊していないことを確認した。修正必須事項はなく、Phase 2E-4設計または
  実行指示作成へ進める。ただし今回もGMO Public実run、Private API、APIキー、broker、実注文、本番公開API追加は
  行っていない。詳細は [PHASE2E3_PUBLIC_TICKER_BID_ASK_AUDIT.md](PHASE2E3_PUBLIC_TICKER_BID_ASK_AUDIT.md)。
- **Phase 2E-3 Public ticker bid/ask provenance連携実装完了（local-only）** — Phase 2E-2.5監査と
  Phase 2E-3設計に基づき、GMO Public `/v1/ticker`由来bid/askだけを`REAL_PUBLIC_BID_ASK`として扱う
  `MarketSnapshot` validationを追加し、`--enable-shadow-risk`経路へ最小接続した。kline-onlyはsynthetic
  spread rejectを維持し、missing/invalid/stale/future/skew tickerはfail closedに倒す。summary/metadataには
  ticker optional countsと`raw_response_saved=false`を追加し、legacy summary互換を維持した。今回の作業では
  GMO Public実run、Private API、APIキー、broker、実注文、本番公開API追加は行っていない。
  詳細は [PHASE2E3_PUBLIC_TICKER_BID_ASK_DESIGN.md](PHASE2E3_PUBLIC_TICKER_BID_ASK_DESIGN.md)。
- **Phase 2E-2.5 session統合監査完了（B判定）** — `app/shadow/`内にimmutable
  OrderCandidate、RiskPolicy、pure risk評価、sticky KillSwitchState、deterministic ID、fail-closed JSONL writerを
  追加した。Phase 2E-1.5監査のD-1〜D-4に対し、spread provenance必須化、malformed inputのfail closed、
  typed audit schema/root containment、unsafe risk row summary検出を実装した。集計はversioned schema validatorで
  `shadow-risk-v1`ログを検証し、validなcandidate/allow/reject/kill/reasonだけをlegacy互換で集計する。
  既存sessionには`--enable-shadow-risk`の明示フラグでのみ最小統合し、デフォルト挙動はlegacy互換を維持する。
  本番API/UI、broker、Private API、APIキー、実注文への接続はない。
  再監査では統合前必須修正なし、Phase 2E-2の設計着手可と判定した。Phase 2E-2設計では、KillSwitchStateの
  session ownership、pre-gate、監査ログ失敗時exit 2、STOPファイル、candidate/decision/virtual result相関、
  summary互換、integration test方針を整理した。実装ではSTOP pre-gate、BUY/SELL candidate、pure risk evaluate、
  typed audit JSONL、REJECT時virtual result抑止、audit失敗時exit code 2、summary/metadata risk fields、
  virtual_result_log相関集計を追加した。Phase 2E-2.5監査ではdefault legacy互換、risk有効run、STOP/audit failure、
  candidate/decision/virtual result相関、summarize互換、禁止import境界を確認し、修正必須事項なしと判定した。
  監査結果は [PHASE2E2_INTEGRATION_AUDIT.md](PHASE2E2_INTEGRATION_AUDIT.md)。設計は
  [PHASE2E2_SESSION_INTEGRATION_DESIGN.md](PHASE2E2_SESSION_INTEGRATION_DESIGN.md)、再監査結果は
  [PHASE2E1H_REAUDIT.md](PHASE2E1H_REAUDIT.md)。
  設計は [PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md) と
  [PHASE2E0_5_SAFETY_REVIEW.md](PHASE2E0_5_SAFETY_REVIEW.md) を参照する。
  初回監査とhardening追記は [PHASE2E1_SAFETY_AUDIT.md](PHASE2E1_SAFETY_AUDIT.md)。

- レポート閲覧 UI の拡張: CSV プレビュー / CSV ダウンロード（別 endpoint 設計が必要）。
- 認証 / アクセス制御（現状ローカル read-only 前提、認証なし）。
- CI 最適化: 複数ブラウザ / matrix / sharding / Playwright browser cache / `push` トリガ拡張。
- 本番デプロイ: **初回デプロイ完了済み**（read-only レポート閲覧のみ、frontend=Vercel / backend=Render）。
  実績は [DEPLOYMENT_RESULT.md](DEPLOYMENT_RESULT.md)。残課題: Render free sleep / 認証未実装 / 実データ非公開 /
  独自ドメイン未設定 / 本番DB未化。
- 戦略・検証の新フェーズ（標準化基盤の上での再設計。単純テクニカル単一構造は終了済み）。
- 通知 / paper forward / 実 broker 連携（OANDA practice 以外）は明示承認が前提。

## 6. 既知の注意点

- DB は `Base.metadata.create_all()` 依存。スキーマ変更時は Alembic 導入＋バックアップ＋dry-run が必要。
- レポート API/UI/E2E は **read-only 前提**。書き込み・注文・Private API・APIキー導線は置かない。
- `analysis_exports/` は生成物で gitignore。CI/E2E は実 analysis_exports を読まず fixture を使う。
- GMO 外国為替FX は**本番のみ・デモ環境なし**のため、実注文は別フェーズで明示許可があるまで無効。
- `.env` は非コミット。`.env.example` はダミー値テンプレート。

## 7. 次回 Codex / Claude Code に渡す作業候補（1つを選ぶ）

- **初回デプロイは完了済み**（[DEPLOYMENT_RESULT.md](DEPLOYMENT_RESULT.md)）。本番 read-only smoke は
  `npm run e2e:prod`（[PRODUCTION_SMOKE_TEST.md](PRODUCTION_SMOKE_TEST.md)、手動 workflow あり）で自動確認可能。
  次の運用候補: 認証/アクセス制御の要否判断、Render free sleep 対策、独自ドメイン、実レポートの安全な配置方法。
- レポート閲覧 UI の CSV プレビュー（read-only・先頭N行・別 endpoint、安全制約厳守）。
- CI の `push`(main) トリガ追加 or browser cache 最適化（workflow のみ変更）。

## 8. 安全制約（全フェーズ共通）

実注文・GMO Private API・APIキー/secret 表示・`.env` 変更・OANDA 経路変更・RiskManager 変更・
注文系変更・DB コミット・実 analysis_exports 読込（テスト/CI）・新戦略追加・追加バックテスト・
本番デプロイは、明示承認なしに行わない。

公開可否・認証要否・公開禁止情報の方針は [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) を単一参照点とする
（現状の read-only サンプル公開は暫定可。§2 の条件に触れる前＝実データ/実取引/Private API/設定画面の公開前に
認証/アクセス制御の必須化を再判断）。

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
