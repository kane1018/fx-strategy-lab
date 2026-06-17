# プロジェクト現在地（PROJECT_STATUS）

FX Strategy Lab / FX read-only レポート閲覧プロジェクトの現在地まとめ。Codex / Claude Code /
ChatGPT を横断して開発するための「現在何が完了し、次に何をすべきか」の単一参照点。
本書は事実ベースのスナップショットであり、実装の置き換えではない。

## 1. メタ情報

- リポジトリ: `https://github.com/kane1018/fx-strategy-lab.git`
- branch: `main`
- 最新コミット（本書作成時点の直近）: `4f0c3b8 ci: opt FX report E2E actions into node24 runtime`
- GitHub Actions: `FX Report E2E` 成功実績あり（`workflow_dispatch` / `pull_request`）

## 2. 完了済み検証（ローカル直近）

- backend: `pytest` 211 passed / `ruff check .` clean
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
- **read-only レポート UI**（`frontend/app/reports/`）: `/reports` 一覧（safety バッジ / ERROR 行 /
  状態表示 / Markdown コピー）、`/reports/[run_id]` 詳細（7セクション + Markdown コピー、aria-live 通知・自動消去）。
- **E2E**: Playwright（Chromium）E2E-01〜10、fixture は `create_e2e_report_fixtures.py` で生成
  （実 analysis_exports 非使用）。**CI**: GitHub Actions で backend/frontend/E2E を実行。

## 5. 未実装 / 次フェーズ候補

- レポート閲覧 UI の拡張: CSV プレビュー / CSV ダウンロード（別 endpoint 設計が必要）。
- 認証 / アクセス制御（現状ローカル read-only 前提、認証なし）。
- CI 最適化: 複数ブラウザ / matrix / sharding / Playwright browser cache / `push` トリガ拡張。
- 本番デプロイ: **初回デプロイ方針は確定済み**（read-only レポート閲覧に限定、frontend=Vercel /
  backend=Render。[DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md) §0）。**実デプロイは未実施**。
- 戦略・検証の新フェーズ（標準化基盤の上での再設計。単純テクニカル単一構造は終了済み）。
- 通知 / paper forward / 実 broker 連携（OANDA practice 以外）は明示承認が前提。

## 6. 既知の注意点

- DB は `Base.metadata.create_all()` 依存。スキーマ変更時は Alembic 導入＋バックアップ＋dry-run が必要。
- レポート API/UI/E2E は **read-only 前提**。書き込み・注文・Private API・APIキー導線は置かない。
- `analysis_exports/` は生成物で gitignore。CI/E2E は実 analysis_exports を読まず fixture を使う。
- GMO 外国為替FX は**本番のみ・デモ環境なし**のため、実注文は別フェーズで明示許可があるまで無効。
- `.env` は非コミット。`.env.example` はダミー値テンプレート。

## 7. 次回 Codex / Claude Code に渡す作業候補（1つを選ぶ）

- **初回デプロイ（手元操作）**: [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) に Vercel/Render の
  具体設定・env・サンプル配置・疎通確認・トラブルシュート・チェックリストを整備済み。次は利用者が手元で
  Render→Vercel の順にデプロイし、CORS/base URL を設定して疎通確認する（実反映は手元）。
- レポート閲覧 UI の CSV プレビュー（read-only・先頭N行・別 endpoint、安全制約厳守）。
- CI の `push`(main) トリガ追加 or browser cache 最適化（workflow のみ変更）。

## 8. 安全制約（全フェーズ共通）

実注文・GMO Private API・APIキー/secret 表示・`.env` 変更・OANDA 経路変更・RiskManager 変更・
注文系変更・DB コミット・実 analysis_exports 読込（テスト/CI）・新戦略追加・追加バックテスト・
本番デプロイは、明示承認なしに行わない。
