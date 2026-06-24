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
