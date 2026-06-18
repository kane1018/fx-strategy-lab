# FX Strategy Lab

個人用のFX戦略検証・ペーパートレード・シグナル監視・デモ注文基盤です。

実資金取引はデフォルトで無効です。このMVPには実資金ブローカー実装を含めず、
ライブ注文要求は安全条件に関係なく最終的に拒否されます。

## セットアップ

```bash
cp .env.example .env

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

別のターミナルで:

```bash
cd frontend
npm install
npm run dev
```

ブラウザで `http://localhost:3000` を開きます。APIドキュメントは
`http://localhost:8000/docs` です。

## Structure

- `frontend/`: Next.js dashboard
- `backend/`: FastAPI, strategy engine, risk controls, SQLite persistence
- `docs/`: architecture, safety, and API notes

詳しい手順は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) と
[docs/SAFETY.md](docs/SAFETY.md) を参照してください。

## Codexで作業する場合

固定ルールの [AGENTS.md](AGENTS.md) と、現在の引き継ぎ
[docs/CODEX_HANDOFF.md](docs/CODEX_HANDOFF.md) を最初に確認してください。現在地と安全な運用の詳細は以下です。

- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)
- [docs/SHADOW_RUNBOOK.md](docs/SHADOW_RUNBOOK.md)
- [docs/PUBLICATION_POLICY.md](docs/PUBLICATION_POLICY.md)
- [docs/GMO_PUBLIC_API_PLAN.md](docs/GMO_PUBLIC_API_PLAN.md)
- [docs/PHASE2_SHADOW_TRADING_PLAN.md](docs/PHASE2_SHADOW_TRADING_PLAN.md)

## 現在の接続範囲

- 市場データ: バックテスト等は再現可能な合成OHLC、Phase 4はOANDA practice価格
- ブローカー: ローカルデモブローカーとOANDA practice
- OANDA: practice限定で価格・残高・確定足・注文・約定・ポジション・決済に対応
- 通知: 画面表示とSQLite保存
- DB: SQLite標準。`DATABASE_URL`でPostgreSQL系へ変更可能

OANDA practiceを使う場合は、`.env`へ以下を設定します。

```dotenv
OANDA_ENV=practice
OANDA_API_URL=https://api-fxpractice.oanda.com
OANDA_API_TOKEN=
OANDA_ACCOUNT_ID=
ENABLE_LIVE_TRADING=false
```

トークンまたは口座IDが未設定の場合、practice接続と自動売買開始は明示的に拒否されます。
UIのPhase 4で接続テスト後に自動売買をONにすると、30秒周期の監視を開始します。

OANDA側のSL/TPで決済された場合は、Trade詳細と`closingTransactionIDs`を取得し、
OrderFill Transactionの損益・金利・手数料を照合します。照合できない場合は
`close_unconfirmed`としてBotを停止し、成功扱いにはしません。

現在は`Base.metadata.create_all()`を利用しています。既存DBへ列変更や制約変更を行う段階では、
自動作成へ依存せずAlembicを導入し、practice DBのバックアップとdry-run後に適用してください。

## practice E2E（市場稼働時）

平日の市場稼働時間中に、小数量のpractice注文〜決済を確認する手順は
[docs/SAFETY.md](docs/SAFETY.md) の「市場開始後の practice E2E 手順」を参照してください。
補助スクリプト `backend/scripts/practice_e2e.py` は practice 専用で、`preflight`（読み取り専用）
→ `order`（`--confirm`・1〜10 units・SL/TP必須・tradeable時のみ）→ `status` → `close` の順に
使います。live broker は生成されず、すべての注文は RiskManager を通ります。

```bash
cd backend
.venv/bin/python -m scripts.practice_e2e preflight --symbol USD_JPY
```

## 成績集計（仮想取引・読み取り専用）

バックテスト / ペーパートレード / mock E2E を**カテゴリ別に分離**して損益・勝率・期待値を
集計します（`app/services/performance_service.py`）。勝率・期待値は**完了取引のみ**を対象とし、
未決済は含み損益として別表示。mock E2E・dry-run は動作確認用として戦略成績から除外します。
読み取り専用で、ブローカー接続もDB書き込みも行いません。

```bash
cd backend
.venv/bin/python -m scripts.performance_report
```

期待値 = 勝率 × 平均利益 − 負率 × 平均損失（定義上、`総損益 ÷ 完了取引数` と一致します）。
完了取引が30件未満の集計は「参考値」として扱ってください。

## GMO コイン外国為替FX（追加broker・準備中）

OANDA に加えて、GMO コイン外国為替FX API を追加 broker として扱う土台を用意しています。
現状は **Public read-only のみ**（最新レート・Kline・スプレッド算出）で、実注文・Private API
接続・APIキー送信は行いません。詳細と段階計画は [docs/SAFETY.md](docs/SAFETY.md) を参照。

- `app/brokers/gmo_fx_broker.py`: `GmoFxBroker`（Public read-only）。`market_order` は無効化済み。
- 設定: `BROKER_PROVIDER`（既定 `oanda`）、`GMO_FX_*`（既定 `READONLY=true` / `ORDER_ENABLED=false`）。
- GMO 外国為替FX には**デモ環境がなく本番のみ**のため、実注文は別フェーズで明示許可があるまで無効です。

### GMO Public データでのペーパートレード（実注文なし）

GMO Public API の Kline を読み取り、既存戦略で**仮想**の建玉・決済を行い PaperTrade として
保存します（実注文・Private API・APIキーは一切使いません）。結果は `performance_report` で確認。

```bash
cd backend
.venv/bin/python -m scripts.paper_trade_gmo --symbol USD_JPY --interval 1min --limit 100
.venv/bin/python -m scripts.performance_report
```

複数通貨ペア×複数戦略をまとめてリプレイするバッチも利用できます（`--date` で過去の取引日を指定）。
`performance_report` の「ペーパートレード成績」は通貨ペア別・戦略別の内訳（`by_symbol`/`by_strategy`）も表示します。

```bash
# 単一日
.venv/bin/python -m scripts.paper_trade_gmo_batch --date 20260612
# 複数営業日（再現性確認用。日別×戦略のロールアップも表示）
.venv/bin/python -m scripts.paper_trade_gmo_batch --dates 20260608,20260609,20260610,20260611,20260612
.venv/bin/python -m scripts.performance_report
```

`performance_report` は通貨ペア別・戦略別・通貨ペア×戦略の内訳（30件未満は「参考値」）を表示します。

蓄積したペーパー取引を、時間帯・相場環境（ADX/ATR/MA傾き/レンジ）・保有時間で分解する読み取り専用
分析は `scripts.paper_analyze_gmo` で行います。結果は `analysis_exports/<run_id>/`（gitignore・ローカル
生成）へ CSV / JSON / `summary.md` / `filter_candidates.md` として保存します。実価格はGMO Public APIの
再取得klineから相場環境を再計算するもので、実注文・Private API・APIキーは使いません。

```bash
.venv/bin/python -m scripts.paper_analyze_gmo
```

## FX 単純テクニカル研究フェーズ（正式クローズ済み）

GMO Public API の **read-only ペーパー検証**（実注文・Private API・APIキーなし）で、M5/M15 の
単純テクニカル戦略を 15窓プロトコル（IS 10窓 + OOS 5窓）で評価しました。rsi_reversal / ADX30 /
breakout / Bollinger / market-structure（M5）、rsi_reversal M15（baseline / SL50・TP100 scaled）、
さらに regime予測可能性診断まで一巡した結果、**単純単一構造＋regimeフィルタ路線に頑健な正エッジは
確認できず**、本研究フェーズを **正式にクローズ**しました。`rsi_reversal M5` のみ研究用ベースライン
として保存。次フェーズは戦略追加ではなく、**検証基盤・レポート標準化**へ移ります。

- 総括（最終判断・やらないこと・次フェーズ）: [docs/fx_research_m5_summary.md](docs/fx_research_m5_summary.md)
- 標準評価手順（15窓プロトコル）: [docs/fx_strategy_evaluation_protocol.md](docs/fx_strategy_evaluation_protocol.md)
- 次フェーズ設計（レポート標準化・E2E導入タイミング）: [docs/fx_report_standardization_plan.md](docs/fx_report_standardization_plan.md)

これらは検証基盤・分析用で、実注文機能ではありません。Private API / APIキーは使いません。

## レポート閲覧 UI / read-only API（実装済み・初回デプロイ済み）

標準化された `analysis_exports/<run_id>/` のレポートを **read-only** で閲覧する API と UI を実装済みです
（実注文・Private API・APIキー・CSV 本文展開なし。設計は
[docs/fx_report_standardization_plan.md](docs/fx_report_standardization_plan.md) §11〜§16）。

**初回デプロイ済み（read-only レポート閲覧のみ）**:
- frontend (Vercel): `https://fx-strategy-lab.vercel.app`（トップ `/` は read-only 案内 → `/reports` へ誘導。
  `/reports`・`/reports/[run_id]`。バックテスト/ペーパー/通知/注文系は公開版では未提供＝公開UIに導線なし）
- backend (Render): `https://fx-strategy-lab.onrender.com`（entrypoint **`app.main_readonly:app`**、
  `/health` ＋ `/api/reports*` の GET のみ公開。注文系など他 API は非公開）
- 実値・使用設定・疎通/安全確認結果は [docs/DEPLOYMENT_RESULT.md](docs/DEPLOYMENT_RESULT.md)。
  手順は [docs/DEPLOYMENT_RUNBOOK.md](docs/DEPLOYMENT_RUNBOOK.md)。実データ・個人情報は公開していません。

- backend API（GET のみ、`app/routers/reports.py`）:
  - `GET /api/reports` … run 一覧（壊れた run は error 行として返す）
  - `GET /api/reports/{run_id}` … 1 run の詳細（manifest/warnings/summary/files メタ。CSV 本文は返さない）
  - `GET /api/reports/markdown` / `GET /api/reports/{run_id}/markdown` … ChatGPT 貼り付け用 Markdown
  - `exports_root` はサーバー固定（`ANALYSIS_EXPORTS_ROOT`、既定 `analysis_exports`）。呼び出し側からの任意指定不可。
- frontend UI（`frontend/app/reports/`）:
  - `/reports` … 一覧（safety バッジ / ERROR 行 / 状態表示 / 一覧 Markdown コピー）
  - `/reports/[run_id]` … 詳細（Overview / Safety / Metrics / Cost / Files / Summary / Final Decision ＋ Markdown コピー）
- read-only ヘルパ純関数は `backend/scripts/fx_eval_common.py`（`list_report_index` / `report_detail` /
  `format_report_index_markdown` / `format_report_detail_markdown` / 各 `validate_*`）。
- 初回デプロイは **read-only 専用 entrypoint `app.main_readonly:app`**（`/health` ＋ `/api/reports*` のみ公開、
  CORS は GET/OPTIONS 限定）を使う。注文系など `app.main:app` の他 API は公開しない。詳細は
  [docs/DEPLOYMENT_RUNBOOK.md](docs/DEPLOYMENT_RUNBOOK.md)。ローカル開発は従来どおり `app.main:app`。

## フロントエンド検証 / CI

```bash
cd frontend
npm ci
npm run lint
npm run test     # Vitest（lib のユニットテスト。e2e/ は除外）
npm run build
npm run e2e       # Playwright（Chromium）E2E-01〜10。fixture 自動生成・実 analysis_exports 非使用
```

E2E は `backend/scripts/create_e2e_report_fixtures.py` が生成する固定 fixture を使い、
`ANALYSIS_EXPORTS_ROOT` を fixture へ向けて backend(uvicorn) と Next dev を起動します（`playwright.config.ts`）。
GitHub Actions の `FX Report E2E`（`.github/workflows/fx-report-e2e.yml`、trigger: `workflow_dispatch` /
`pull_request`）が backend pytest+ruff / frontend lint+test+build / Playwright E2E を実行します。
secrets 不使用・本番デプロイなし・実 analysis_exports 非接触。

デプロイ済みの公開 URL に対する read-only smoke 確認は `cd frontend && npm run e2e:prod`
（手動 workflow `production-smoke.yml` あり）。詳細は [docs/PRODUCTION_SMOKE_TEST.md](docs/PRODUCTION_SMOKE_TEST.md)。

現在地・デプロイ前確認は [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) と
[docs/DEPLOYMENT_READINESS.md](docs/DEPLOYMENT_READINESS.md) を参照してください。
公開可否・認証要否・公開禁止情報の方針は [docs/PUBLICATION_POLICY.md](docs/PUBLICATION_POLICY.md)
（現状の read-only サンプル公開は暫定可。実データ・実取引・Private API・設定画面へ進む前に認証要否を再判断）。

バックテスト結果は将来の利益を保証しません。
