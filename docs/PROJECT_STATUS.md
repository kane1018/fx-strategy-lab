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

- backend: `pytest` 253 passed / `ruff check .` clean
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

- **優先候補: Phase 2D-2** — gmo-public shadow run の注文なし・local-only 運用手順と蓄積確認。
  実行上限を設け、生成物は `shadow_exports/` から git add しない。収益性判断や次フェーズ移行は含めない。

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
