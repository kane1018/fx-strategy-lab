# デプロイ前確認（DEPLOYMENT_READINESS）

FX Strategy Lab / read-only レポート閲覧プロジェクトを将来デプロイする前の確認事項・候補構成・手順。
**本書は計画と確認リストであり、本番デプロイは実行しない。** 現構成（FastAPI backend ＋ Next.js
frontend ＋ SQLite ＋ read-only レポート API/UI）に基づく現実的な整理に留める。

## 1. 現時点でデプロイ可能性が高い部分

- **read-only レポート閲覧**（`/api/reports*` ＋ `/reports`・`/reports/[run_id]`）: GET のみ・
  書き込みなし・実注文/Private API/APIキー導線なし・CSV 本文非返却。最も安全にデプロイ候補にしやすい。
- backend は read-only API としてなら外部依存（OANDA/GMO 実接続）なしで起動可能
  （`ANALYSIS_EXPORTS_ROOT` のレポートを読むだけ）。

## 2. デプロイ前に確認すべきこと

- **公開範囲**: 個人用ツール。一般公開するなら認証/アクセス制御が未実装な点を要検討（現状は read-only だが
  レポート内容を不特定多数に晒さない設計判断が必要）。
- **CORS**: backend は `FRONTEND_ORIGIN` を許可。デプロイ先の frontend URL に合わせて設定する。
- **API base URL**: frontend は `NEXT_PUBLIC_API_BASE_URL`（既定 `http://localhost:8000`）。
  デプロイ先 backend の URL を設定する（ビルド時に inline される点に注意）。
- **exports_root**: `ANALYSIS_EXPORTS_ROOT`（既定 `analysis_exports`）。デプロイ環境にレポート生成物を
  どう配置/同期するか（生成物は gitignore のためデプロイ成果物に含まれない）を決める。
- **DB**: 既定 SQLite。永続ボリュームが無い PaaS では揮発する。レポート閲覧だけなら DB 不要寄りだが、
  既存 app（paper/signals 等）は SQLite を使う。スキーマ変更時は Alembic 導入＋バックアップ＋dry-run。
- **secrets**: レポート閲覧 read-only に APIキー/secret は不要。OANDA/GMO 実接続を含めない構成を維持する。
- **ライブ取引フラグ**: `ENABLE_LIVE_TRADING=false` を維持。ライブブローカー実装は含まれない。

## 3. frontend / backend の想定デプロイ先候補（断定しない）

- **frontend（Next.js）**: Vercel が素直な候補。コンテナ前提なら Cloud Run / Render / Railway でも可。
  `NEXT_PUBLIC_API_BASE_URL` を backend の公開 URL に設定する必要あり。
- **backend（FastAPI/uvicorn）**: Render / Railway / Fly.io / Cloud Run などのコンテナ/PaaS。
  read-only レポート用途なら最小構成で可。SQLite を使うなら永続ストレージ、使わない設計なら不要。
- いずれも MVP は **read-only・1 リージョン・最小プラン**から。スケール/CDN/複数リージョンは後日。
- 注: 上記は現構成からの一般的候補であり確定ではない。実際の選定は要件（永続化・コスト・運用）で決める。

## 4. 環境変数（`.env.example` 準拠・実値は設定しない）

- backend: `DATABASE_URL` / `FRONTEND_ORIGIN` / `LOG_LEVEL` / `ANALYSIS_EXPORTS_ROOT` /
  `ENABLE_LIVE_TRADING`(=false) ほか（OANDA/GMO 系はレポート閲覧では未設定でよい）。
- frontend: `NEXT_PUBLIC_API_BASE_URL`。
- 実 APIキー/secret/トークンは `.env`（非コミット）にのみ置き、本書やリポジトリに記載しない。

## 5. build / test / E2E の確認手順（デプロイ前にローカル/CIで緑を確認）

```bash
# backend
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check .

# frontend
cd ../frontend
npm ci
npm run lint
npm run test
npm run build
npm run e2e   # Playwright Chromium（fixture 自動生成・実 analysis_exports 非使用）
```

CI（`.github/workflows/fx-report-e2e.yml`）でも同等を実行（`workflow_dispatch` / `pull_request`）。

## 6. 本番デプロイ前に触ってはいけないもの

- 実注文 / 自動売買の有効化、`ENABLE_LIVE_TRADING` の true 化、`market_order` 有効化。
- GMO Private API 接続、APIキー/secret の埋め込み・表示・コミット、`.env` のコミット。
- OANDA 経路 / RiskManager / 注文系の挙動変更。
- 本番 DB への破壊的スキーマ変更（Alembic 未導入のままの `create_all` 依存変更）。

## 7. 今回は実行しないこと

- 本番デプロイ、deployment workflow 作成、ホスティング設定、ドメイン/DNS、secrets 登録。
- 外部 broker への実接続、実注文、追加バックテスト、新戦略追加。

## 8. 次にやるべき作業（デプロイへ進む場合の最小ステップ）

1. デプロイ対象を **read-only レポート閲覧（API＋UI）に限定**することを意思決定する。
2. frontend/backend のホスティング候補を1つずつ仮決め（例: frontend=Vercel、backend=Render）。
3. 必要 env（`NEXT_PUBLIC_API_BASE_URL` / `FRONTEND_ORIGIN` / `ANALYSIS_EXPORTS_ROOT`）と
   レポート生成物の配置方法を決める。
4. read-only である（注文/Private API/APIキー導線が無い）ことを再確認してから、最小 PoC をステージングで試す。
5. 本番化は、認証/アクセス制御・永続化・監視の要否を整理してから別途判断する。

いずれも明示承認のうえで進める。本書時点ではデプロイは未実施。
