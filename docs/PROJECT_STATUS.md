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
  Phase 2FとPhase 2Gは完了したが、Phase 3Bはまずread-only公式仕様確認・実装設計を別タスクで行う。
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
