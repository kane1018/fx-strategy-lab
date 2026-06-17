# 本番 smoke テスト（PRODUCTION_SMOKE_TEST）

デプロイ済みの read-only MVP（公開 URL）が壊れていないかを自動確認する Playwright smoke test。
**read-only のみ**（GET 中心。書き込みは `POST /api/reports` の 405 確認だけ）。secret 不要・実注文/
Private API には触れない。通常のローカル E2E（`npm run e2e`）とは**分離**している。

## 何を確認するか

- backend（Render, `app.main_readonly:app`）:
  - `GET /health` → 200（`status=ok` / `mode=read-only` / `live_trading_environment_enabled=false` /
    `live_broker_implemented=false`）
  - `GET /api/reports` → 200（`count=4`、`e2e_normal_run` を含む）
  - `GET /api/reports/e2e_normal_run` → 200（safety 全フラグ read-only）
  - `GET /api/orders` / `/api/paper/sessions` / `/api/automation/status` → 404、`POST /api/reports` → 405
- frontend（Vercel）:
  - `/` が read-only ランディング（scope 文・「レポート一覧を見る」CTA・未公開機能の明示、旧ダッシュボード非表示、
    `Failed to fetch` なし）
  - `/reports` が `Reports: 4` と `e2e_normal_run` を表示、一覧 Markdown コピー成功
  - `/reports/e2e_normal_run` が 7 セクション（Overview/Safety/Metrics/Cost/Files/Summary/Final Decision）と
    「Read-only確認済み」バッジを表示、詳細 Markdown コピー成功

## 実行コマンド

```bash
cd frontend
npm run e2e:prod
# 対象URLを差し替える場合（既定は下記）:
PRODUCTION_FRONTEND_URL=https://fx-strategy-lab.vercel.app \
PRODUCTION_BACKEND_URL=https://fx-strategy-lab.onrender.com \
  npm run e2e:prod
```

- 実装: `frontend/e2e/production-smoke.spec.ts` ＋ `frontend/playwright.prod.config.ts`（webServer なし）。
- 通常 E2E（`npm run e2e`）は本 spec を `testIgnore` で除外（ローカル E2E と混ざらない）。
- 既定の対象 URL: frontend `https://fx-strategy-lab.vercel.app` / backend `https://fx-strategy-lab.onrender.com`。

## Render sleep（cold start）について

- Render free instance は無操作で sleep する。spec は最初に `/health` を**最大6回 / 3秒間隔でリトライ**して
  ウォームアップしてから検証する（無限リトライはしない）。
- それでも起動しない場合は「Render free instance may be sleeping / cold start, or backend down」を含む
  エラーで失敗する。

## GitHub Actions（手動実行のみ）

- `.github/workflows/production-smoke.yml`（`workflow_dispatch` のみ。push/PR では走らない）。
- inputs で `frontend_url` / `backend_url` を上書き可能。secrets 不要。失敗時のみ artifacts を upload。

## 失敗時に見るポイント

- **Vercel 未反映**: `/` が旧ダッシュボードに戻っている → 最新 Deployment を確認（再デプロイ）。
- **Render sleep / cold start**: warmup で失敗 → 少し待って再実行、または Render の稼働状態を確認。
- **CORS**: backend `FRONTEND_ORIGIN` が Vercel URL と完全一致しているか。
- **API base URL**: frontend `NEXT_PUBLIC_API_BASE_URL` が backend URL になっているか（変更時は再ビルド）。
- **reports API 不調**: `/api/reports` の count や detail を直接 curl で確認。
- **safety フラグ変化 / 危険API公開**: PSMOKE-03/04 が落ちたら、backend が `app.main_readonly:app` のままか、
  公開面が広がっていないかを確認（[PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) §2）。
- **セレクタ不備**: UI 文言/`data-testid` を変更した場合は spec 側を更新。

## やらないこと

- 実注文・Private API・APIキー/secret・live trading・DB 本番化には触れない。GET 中心の read-only 確認のみ。
