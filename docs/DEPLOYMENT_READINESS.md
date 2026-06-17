# デプロイ前確認（DEPLOYMENT_READINESS）

FX Strategy Lab / read-only レポート閲覧プロジェクトを将来デプロイする前の確認事項・候補構成・手順。
**本書は計画と確認リストであり、本番デプロイは実行しない。** 現構成（FastAPI backend ＋ Next.js
frontend ＋ SQLite ＋ read-only レポート API/UI）に基づく現実的な整理に留める。

## 0. 初回デプロイ方針（確定）

初回公開は **read-only レポート閲覧に限定**する。実注文・実資金・broker 実接続を含む機能は公開しない。
以下を本プロジェクトの「初回デプロイ方針」として確定する（実デプロイはまだ行わない）。

### 0-1. 初回公開対象

- frontend: `/reports`（一覧）、`/reports/[run_id]`（詳細）、Markdown コピー導線。
- backend: GET 系 read-only API のみ
  （`GET /api/reports` / `GET /api/reports/{run_id}` / `GET /api/reports/markdown` /
  `GET /api/reports/{run_id}/markdown`）。
- 閲覧対象は `ANALYSIS_EXPORTS_ROOT` 配下の固定/サンプルレポート（実データ・個人情報は含めない）。

### 0-2. 初回公開対象外（明確に出さない）

実注文 / 実資金取引 / GMO Private API / OANDA 実接続 / broker 注文処理 / RiskManager 変更 /
新戦略追加 / 追加バックテスト / CSV 本文返却 / CSV ダウンロード / 認証機能 / DB 本番化 /
通知機能 / 自動売買 / paper forward / 本番データ運用。
（既存の paper/signals/automation 等の API もデプロイ上は公開導線を作らず、UI は `/reports` 系のみ前提）

### 0-3. 推奨ホスティング構成（1案に確定）

- **frontend = Vercel**。理由: Next.js 公式ホスティングで App Router をそのまま動かせ、最小設定で済む。
- **backend = Render（次点 Railway）**。理由: FastAPI/uvicorn の常駐プロセスを最小プランのコンテナ/PaaS で
  動かせる。Vercel は uvicorn 常駐に不向きなため frontend と backend は分離する。Cloud Run も技術的には可だが
  GCP 初期セットアップが重く、初回は Render を推奨。
- frontend と backend は **別ホスト**になるため CORS / `NEXT_PUBLIC_API_BASE_URL` の設定が必須
  （§0-4 と後述「analysis_exports の扱い」「CORS / API 接続」）。
- まだ決めきれない点: 独自ドメインの要否、Render 無料プランの sleep 挙動許容可否、レポート生成物の同期方法。
  これらは PoC で確認してから確定する。

### 0-4. 環境変数（初回 read-only 公開で必要なもの・機密値は書かない）

```text
# backend (Render 等)
FRONTEND_ORIGIN=        # Vercel の frontend URL（CORS 許可）
ANALYSIS_EXPORTS_ROOT=analysis_exports   # レポート配置先（サーバー固定）
ENABLE_LIVE_TRADING=false                # 維持
LOG_LEVEL=INFO
# DATABASE_URL は既定 SQLite のまま（reports は DB 不使用。§8 参照）

# frontend (Vercel)
NEXT_PUBLIC_API_BASE_URL=   # Render の backend 公開 URL（ビルド時に inline される）
```

OANDA/GMO 系の APIキー・secret・トークンは **初回公開では不要**。`.env`（非コミット）にのみ置き、
本書・リポジトリ・ホスティングの公開設定には実値を書かない。

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

> 具体的な Vercel/Render 設定値・root directory・build/start command・env・サンプル配置・疎通確認・
> トラブルシュート・手元操作チェックリストは [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) にまとめた
> （実デプロイ手前まで。実反映は手元で行う）。

## 9. analysis_exports の扱い（初回デプロイ）

- `analysis_exports/` は **生成物で gitignore** のため、リポジトリにもデプロイ成果物にも自動では含まれない。
- 初回は **固定/サンプルレポートを backend 側に明示配置**し、`ANALYSIS_EXPORTS_ROOT` でそこを指す方式を推奨。
  （例: デプロイ時に小さなサンプル run を同梱、または起動時に `create_e2e_report_fixtures` 相当で生成）。
- **実データ・個人情報・実取引由来のレポートは初回公開に含めない**（サンプル/無害なもののみ）。
- CSV 本文返却・CSV ダウンロードは初回範囲外（API が本文を返さない設計＝閲覧は name/kind/size_bytes のメタのみ）。
  理由: 巨大ファイルの自動展開・転送を避け、read-only 表示の安全性とシンプルさを優先するため。
- 将来運用: レポートが増える/共有する段階で、オブジェクトストレージ（S3 / GCS / R2 等）配置と
  read-only 取得への移行を検討（本書時点では未導入・候補のみ）。

## 10. SQLite / DB の扱い（初回デプロイ）

- **read-only レポート閲覧に DB は不要**: `/api/reports*` は `ANALYSIS_EXPORTS_ROOT` のファイルを読むだけで
  DB を使わない。
- ただし backend 起動時の lifespan が `Base.metadata.create_all()` と自動化リカバリを実行するため、
  起動時に SQLite ファイル自体は作成される。**揮発しても reports 閲覧には影響しない**（自動売買は自動起動しない）。
- 永続ボリュームの無い PaaS では SQLite は再起動で揮発し得る。初回は **永続化 DB を本格導入しない**
  （reports に不要なため）。`DATABASE_URL` は既定 SQLite のままでよい。
- 本格運用（paper/signals 等を永続化して公開する段階）で DB が必要になったら、永続ストレージ or
  PostgreSQL 系（`DATABASE_URL` 変更）を検討し、**Alembic 未導入**のため移行前にスキーマ管理を整備する。

## 11. CORS / API 接続

- frontend（Vercel）と backend（Render）は別オリジンになるため、backend の CORS で
  `FRONTEND_ORIGIN` に Vercel の URL を許可する（現状 backend は `FRONTEND_ORIGIN` を許可元に使用）。
- frontend は `NEXT_PUBLIC_API_BASE_URL` を backend 公開 URL に設定する。**ビルド時に inline される**ため、
  値を変えたら再ビルド/再デプロイが必要。
- 環境の考え方: local（既定 localhost）/ staging（プレビュー URL）/ production（本番 URL）で
  上記2変数を切り替える。secrets ではないがホスティングの env として設定する。

## 12. 次回 Codex へ渡す実デプロイ準備プロンプト案（たたき台）

> 注: 以下は **次フェーズ用のプロンプト下書き**。本タスクの Claude Code 自身はデプロイ操作をしない。

```text
FX Strategy Lab の初回デプロイ準備を行ってください。実デプロイ手前までで、外部サービスへの
ログイン・課金設定・本番反映は私が手元で行います。方針は docs/DEPLOYMENT_READINESS.md の確定案に従う。

対象: read-only レポート閲覧のみ
- frontend = Vercel（/reports, /reports/[run_id], Markdown コピー）
- backend = Render（GET 系 /api/reports* のみ）

やること:
1. frontend(Vercel) / backend(Render) のデプロイ設定ファイル/手順を最小で用意（実デプロイはしない）。
2. 必要 env を整理（FRONTEND_ORIGIN / NEXT_PUBLIC_API_BASE_URL / ANALYSIS_EXPORTS_ROOT=analysis_exports /
   ENABLE_LIVE_TRADING=false）。実値・APIキー・secret は書かない/表示しない。
3. analysis_exports に置く無害なサンプルレポートの配置方法を用意（実データは含めない）。
4. CORS（FRONTEND_ORIGIN）と NEXT_PUBLIC_API_BASE_URL の設定箇所を明記。
5. デプロイ後の疎通確認手順（/api/reports と /reports が表示されること、危険導線が無いこと）を用意。

禁止: 実注文 / 実資金 / ENABLE_LIVE_TRADING の true 化 / GMO Private API / OANDA 実接続 /
APIキー・secret の表示・コミット / .env の表示・変更・コミット / 認証の本格実装 / DB 本番化 /
CSV 本文返却・ダウンロード / 新戦略・追加バックテスト / 私の承認なしの本番反映。

問題があれば最小修正し、最後に変更点・必要な手動操作・残課題を報告してください。
```
