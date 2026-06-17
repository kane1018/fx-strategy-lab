# 初回デプロイ結果（DEPLOYMENT_RESULT）

FX Strategy Lab の **初回デプロイは完了済み**。本書は as-deployed の事実記録（公開URL・使用した設定値・
疎通確認・安全確認・残課題）。手順は [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md)、方針は
[DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md)。

- 公開対象: **read-only レポート閲覧のみ**（実注文・実資金・Private API は未使用）。
- backend: Render `https://fx-strategy-lab.onrender.com`（entrypoint `app.main_readonly:app`）。
- frontend: Vercel `https://fx-strategy-lab.vercel.app`。
- 公開しているのは Build 生成の無害な E2E サンプルレポートのみ（実データ・個人情報なし）。

## 1. Render backend（実績）

| 項目 | 値 |
| --- | --- |
| URL | `https://fx-strategy-lab.onrender.com` |
| Service | Render Web Service |
| Runtime | Python 3（`PYTHON_VERSION=3.11`） |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt && python -m scripts.create_e2e_report_fixtures --output-root analysis_exports` |
| Start Command | `uvicorn app.main_readonly:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

設定済み環境変数（実値の secret は無し）:
```text
ANALYSIS_EXPORTS_ROOT=analysis_exports
ENABLE_LIVE_TRADING=false
LOG_LEVEL=INFO
PYTHON_VERSION=3.11
FRONTEND_ORIGIN=https://fx-strategy-lab.vercel.app
```

- `app.main:app` ではなく **`app.main_readonly:app`** を使用：初回公開面を `/health` と `/api/reports*`（GET）に
  限定し、注文/paper/signals/bot/automation/broker/backtests を外部公開しないため。
- Build でサンプルを `backend/analysis_exports/` に生成（`ANALYSIS_EXPORTS_ROOT=analysis_exports` が指す先）。

## 2. Vercel frontend（実績）

| 項目 | 値 |
| --- | --- |
| URL | `https://fx-strategy-lab.vercel.app` |
| Root Directory | `frontend` |
| Framework | Next.js |
| Environment Variable | `NEXT_PUBLIC_API_BASE_URL=https://fx-strategy-lab.onrender.com` |

- `NEXT_PUBLIC_API_BASE_URL` は **ビルド時 inline**。値変更時は Vercel 再デプロイが必要。

## 3. CORS（実績）

- Render `FRONTEND_ORIGIN=https://fx-strategy-lab.vercel.app`（**末尾スラッシュなし・Vercel オリジンと完全一致**）。
- `FRONTEND_ORIGIN` 変更時は Render 再デプロイが必要。

## 4. 疎通確認結果（実施済み・成功）

backend:
- `GET /health` → 200（`status=ok` / `mode=read-only` / `live_trading_environment_enabled=false` /
  `live_broker_implemented=false`）
- `GET /api/reports` → 200（`count: 4`）
- `GET /api/reports/e2e_normal_run` → 200（詳細JSON取得）

frontend:
- `/reports` → 表示成功（`Reports: 4`）
- `/reports/e2e_normal_run` → 詳細表示成功（Overview / Safety / Metrics Summary / Cost / Execution /
  Files / Summary Markdown / Final Decision の7セクション）
- 一覧 Markdown コピー → 成功（「一覧Markdownをコピーしました」）
- 詳細 Markdown コピー → 成功（「Markdownをコピーしました」）

## 5. 安全確認結果（実施済み）

公開面の限定（未登録/メソッド制限）:
- `GET /api/orders` → **404**（`{"detail":"Not Found"}`）
- `GET /api/paper/sessions` → **404**
- `GET /api/automation/status` → **404**
- `POST /api/reports` → **405**（`{"detail":"Method Not Allowed"}`）

read-only / no-order を示すフラグ:
- health: `mode=read-only` / `live_trading_environment_enabled=false` / `live_broker_implemented=false`
- detail Safety: `real_order=false` / `private_api_used=false` / `api_key_used=false` /
  `gmo_readonly=true` / `gmo_order_enabled=false` / `no_order_execution=true`

## 5b. 公開 UI（read-only 版に整合）

- トップ `/` は **read-only 案内ランディング**（公開範囲の明示 ＋ `/reports` への誘導）。フル
  TradingDashboard（バックテスト/ペーパー/シグナル/デモ注文）は **公開 UI に表示しない**ため、
  read-only backend に無い API を叩いて `Failed to fetch` になる導線が無い。
- `TradingDashboard` コンポーネント自体はローカル開発/将来用に残置（公開トップからは未参照）。
- reports 機能（`/reports`・`/reports/[run_id]`・Markdown コピー）は従来どおり動作。E2E は landing 確認の
  E2E-11 を追加し、計 **11 passed**。

## 6. 残課題

- Render free instance は inactivity で **sleep** → 初回アクセスがコールドスタートで遅い可能性。
- 公開中は **無害な E2E サンプルレポートのみ**。実データ・個人情報・実取引由来レポートは公開しない。
- **認証は未実装**。一般公開範囲として問題ないかは今後判断（read-only だが内容露出の是非）。
- CSV 本文返却 / CSV ダウンロードは未実装（初回範囲外）。
- 独自ドメイン未設定。本番 DB 化は未実施（reports は DB 不使用、Alembic 未導入）。
- 実注文・実資金・GMO Private API・OANDA 実接続は **引き続き禁止**。

## 7. 再デプロイ時の注意（実績ベース）

- Render Start は必ず `app.main_readonly:app`（`app.main:app` にしない）。
- `FRONTEND_ORIGIN`（Render）/ `NEXT_PUBLIC_API_BASE_URL`（Vercel）を変えたら、それぞれ再デプロイ/再ビルド。
- Build のサンプル生成（`create_e2e_report_fixtures --output-root analysis_exports`）を外すと `/api/reports` が
  空（count 0）になり得る。
- 再デプロイ後は §4・§5 を再確認（特に §5 の 404/405）。
