# 初回デプロイ Runbook（DEPLOYMENT_RUNBOOK）

FX Strategy Lab の **初回デプロイ手前まで**の具体手順。方針は
[DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md)（§0 確定方針）に従う。
**本書は手元操作のための手順書であり、Claude Code/Codex 自身は実デプロイ・外部サービス設定・
secrets 登録・課金設定を行わない。** 実際の Vercel/Render 画面操作は利用者が手元で行う。

- 初回公開対象: **read-only レポート閲覧のみ**（frontend `/reports`・`/reports/[run_id]`＋
  Markdown コピー、backend GET 系 `/api/reports*`）。
- 公開対象外: 実注文 / 実資金 / GMO Private API / OANDA 実接続 / 注文系 / 認証 / DB 本番化 /
  CSV 本文・ダウンロード / 自動売買 / paper forward（[DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md) §0-2）。
- 構成: frontend = **Vercel**、backend = **Render**（別ホスト → CORS / base URL 設定が必須）。

確認済みの事実（リポジトリ由来）:
- frontend `frontend/package.json` scripts: `build=next build` / `start=next start`（Next.js 15 App Router）。
- backend `backend/app/main.py`: `app = FastAPI(...)`、`GET /health` あり。依存は `backend/requirements.txt`
  （`fastapi` / `uvicorn[standard]`）。`requires-python` ピンは無し（ローカルは Python 3.11）。
- backend 設定 `backend/app/config.py`（pydantic-settings、env で上書き）: `frontend_origin`（既定
  `http://localhost:3000`）/ `analysis_exports_root`（既定 `analysis_exports`）/ `enable_live_trading`（既定
  False）/ `log_level`（既定 INFO）。
- `analysis_exports/` は **gitignore**（生成物。リポジトリ/デプロイ成果物に自動では含まれない）。

---

## 1. Vercel（frontend）設定案

| 項目 | 値 |
| --- | --- |
| Framework Preset | Next.js（自動検出） |
| Root Directory | `frontend` |
| Install Command | 既定（`npm install`／lock があるため `npm ci` 相当。明示するなら `npm ci`） |
| Build Command | 既定（`next build`）。`frontend/package.json` の `build` を使用 |
| Output | 既定（Next.js）。`output` の手動指定は不要 |
| Node.js Version | 20 を推奨（CI と揃える。Project Settings → Node.js Version） |
| 環境変数 | `NEXT_PUBLIC_API_BASE_URL` = Render の backend 公開 URL |

注意点:
- `NEXT_PUBLIC_API_BASE_URL` は **ビルド時に inline** される。値を変えたら **再ビルド/再デプロイ**が必要。
- Production と Preview で backend URL が異なる場合、環境ごとに `NEXT_PUBLIC_API_BASE_URL` を設定する
  （Preview を使わないなら Production のみでよい）。
- 初回は backend URL が確定してから frontend をデプロイする（§4 デプロイ順序）。

---

## 2. Render（backend）設定案

| 項目 | 値 |
| --- | --- |
| Service type | Web Service |
| Root Directory | `backend` |
| Runtime | Python |
| Python Version | 3.11 系（ローカルと揃える。Render の env `PYTHON_VERSION=3.11.x`、または将来 `backend/runtime.txt`） |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |
| 環境変数 | §3 を参照 |

注意点:
- Start は Root Directory=`backend` 基準。`app.main:app` と `scripts.*` は `backend/` 直下のパッケージのため、
  この working dir でのみ正しく解決する。
- Render は `$PORT` を注入する。uvicorn は必ず `--host 0.0.0.0 --port $PORT` で待ち受ける。
- **Render 無料プランは無操作で sleep** し、次アクセス時にコールドスタートで初回応答が遅い。許容できなければ
  有料プラン/別サービスを検討（方針 §0-3 の未確定事項）。
- SQLite は §6 参照（reports 閲覧には不要だが起動時にファイル生成される）。

---

## 3. 必要な環境変数（機密値は書かない・実値は手元で設定）

```text
# backend (Render)
FRONTEND_ORIGIN=            # Vercel の frontend 公開 URL（CORS 許可元）
ANALYSIS_EXPORTS_ROOT=analysis_exports   # レポート配置先（サーバー固定。Root=backend 基準で backend/analysis_exports）
ENABLE_LIVE_TRADING=false   # 維持（true 化しない）
LOG_LEVEL=INFO
PYTHON_VERSION=3.11         # ローカルと揃える（Render の Python バージョン指定方法に従う）
# DATABASE_URL は設定不要（既定 SQLite のまま。reports は DB 不使用。§6）
# OANDA_* / GMO_FX_* / APIキー・secret は初回 read-only 公開では不要（設定しない）

# frontend (Vercel)
NEXT_PUBLIC_API_BASE_URL=   # Render の backend 公開 URL（例: https://<service>.onrender.com）
```

- 実 APIキー/secret/トークンは **ホスティングの env にも本書にも実値を書かない**。read-only 公開では不要。
- `.env`（ローカル非コミット）の実値は表示・コミットしない。

---

## 4. デプロイ順序（推奨：URL の相互依存を解消）

frontend は backend URL を、backend は frontend URL（CORS）を必要とするため、次の順で回す:

1. **backend を Render にデプロイ**（`FRONTEND_ORIGIN` は仮に空/後で更新でも起動はする）→ backend 公開 URL を取得。
2. Vercel の `NEXT_PUBLIC_API_BASE_URL` に backend URL を設定 → **frontend をデプロイ** → frontend 公開 URL を取得。
3. Render の `FRONTEND_ORIGIN` に frontend URL を設定 → **backend を再デプロイ/再起動**（CORS 反映）。
4. §5 の疎通確認。

---

## 5. analysis_exports / サンプルレポート配置方針

- `analysis_exports/` は gitignore のため **デプロイ成果物に自動では含まれない**。初回はサンプルを用意する。
- **推奨（無害なサンプルを起動環境に用意）**: backend の Build Command に fixture 生成を追加して
  `ANALYSIS_EXPORTS_ROOT` 配下を populate する。例:
  ```text
  Build Command: pip install -r requirements.txt && python -m scripts.create_e2e_report_fixtures --output-root analysis_exports
  ```
  これで `backend/analysis_exports/` に無害なサンプル run（`e2e_normal_run` ほか）が生成され、
  `ANALYSIS_EXPORTS_ROOT=analysis_exports` から読める。実データ・個人情報は一切含まない。
- 代替: 小さな無害サンプル run を **リポジトリの gitignore 外パス**に置き、起動時に `ANALYSIS_EXPORTS_ROOT` で
  そこを指す（本書ではファイル追加はしない。配置方針のみ）。
- **実データ・実取引由来・個人情報を含むレポートは初回公開に含めない**。
- CSV 本文返却・ダウンロードは初回範囲外（API は name/kind/size_bytes のメタのみ返す設計）。
- 将来: レポート増加/共有時にオブジェクトストレージ（S3 / GCS / R2）配置＋read-only 取得へ移行を検討（未導入）。

---

## 6. SQLite / DB の扱い

- **read-only レポート閲覧に DB は不要**（`/api/reports*` はファイルを読むだけ）。
- backend 起動時 lifespan が `Base.metadata.create_all()` を実行するため SQLite ファイルは作られるが、
  揮発しても reports 閲覧に影響なし（自動売買は自動起動しない）。
- 無料/エフェメラル環境では SQLite は再起動で揮発し得る。初回は **永続化 DB を導入しない**
  （`DATABASE_URL` 既定のまま）。本格運用で必要になったら永続ストレージ or PostgreSQL を検討
  （**Alembic 未導入**のため移行前にスキーマ管理整備）。

---

## 7. CORS / API 接続

- frontend（Vercel）と backend（Render）は別オリジン。backend の CORS 許可元は `FRONTEND_ORIGIN`
  （Vercel の URL を設定）。
- frontend の API 先は `NEXT_PUBLIC_API_BASE_URL`（Render の URL）。**ビルド時 inline** のため変更時は再ビルド。
- 環境の考え方: local（既定 localhost）/ preview（プレビュー URL）/ production（本番 URL）で 2 変数を切替。
- CORS で詰まったら: backend の `FRONTEND_ORIGIN` が **実際の frontend オリジンと完全一致**しているか
  （`https://`・末尾スラッシュ・サブドメイン差異）を確認。設定変更後は backend 再デプロイが必要。

---

## 8. デプロイ後の疎通確認手順

1. **backend health**: `GET https://<backend>/health` → 200・`{"status":"ok", ...}`。
2. **reports API**: `GET https://<backend>/api/reports` → 200・`{"items":[...],"count":N}`
   （サンプル run が見える）。`GET https://<backend>/api/reports/<run_id>` → 詳細 JSON。
3. **frontend 一覧**: `https://<frontend>/reports` を開く → 一覧表・件数・safety バッジが表示される。
4. **frontend 詳細**: 一覧の run_id クリック → `/reports/<run_id>` で 7 セクション表示。
5. **Markdown コピー**: 「Markdownをコピー」「一覧Markdownをコピー」→ 成功メッセージ表示。
6. **ブラウザ DevTools**: Console に CORS / fetch エラーが無いこと。Network タブで `/api/reports*` が 200。
7. **安全確認**: 画面・レスポンスに実注文/Private API/APIキー/secret/`.env` 値・CSV 本文が出ていないこと。
   注文/決済/自動売買などの危険導線が無いこと。

---

## 9. トラブルシュート

| 症状 | 確認ポイント |
| --- | --- |
| frontend build 失敗 | Vercel Root Directory=`frontend` か。Node 20 か。ローカル `npm run build` が通るか |
| backend が起動しない | Render Root Directory=`backend` / Start=`uvicorn app.main:app --host 0.0.0.0 --port $PORT` か |
| backend build 失敗 | `pip install -r requirements.txt`。Python 3.11 になっているか |
| Node version 不一致 | Vercel の Node.js Version を 20 に |
| CORS エラー | backend `FRONTEND_ORIGIN` が frontend オリジンと完全一致か。変更後に backend 再デプロイしたか |
| API に繋がらない | frontend `NEXT_PUBLIC_API_BASE_URL` 未設定/誤り。設定後に **再ビルド**したか |
| `/api/reports` が空（count 0） | `analysis_exports` が空。Build でサンプル生成したか（§5）。`ANALYSIS_EXPORTS_ROOT` の指す先を確認 |
| 初回応答が遅い/落ちる | Render 無料プランの sleep / コールドスタート。プラン見直し |
| データが消える | SQLite/ファイルが揮発（エフェメラル）。reports はサンプル再生成で対応（§5/§6） |
| 404 | URL/ルート誤り。frontend は `/reports`、backend は `/api/reports`・`/health` |
| 500 | backend ログ確認。`report_detail` の対象 run の構造（summary 0/複数）や JSON 破損 → 422/500 |

---

## 10. 手元操作チェックリスト（Vercel / Render 画面）

**共通（事前）**
- [ ] ローカルで緑: backend `pytest`/`ruff`、frontend `lint`/`test`/`build`/`e2e`（[DEPLOYMENT_READINESS.md](DEPLOYMENT_READINESS.md) §5）。
- [ ] 公開するサンプルレポートが無害（実データ・個人情報・実取引由来でない）こと。

**Render（backend）**
- [ ] GitHub repo `kane1018/fx-strategy-lab` を選択。
- [ ] Root Directory = `backend`。
- [ ] Build Command = `pip install -r requirements.txt`（＋必要ならサンプル生成、§5）。
- [ ] Start Command = `uvicorn app.main:app --host 0.0.0.0 --port $PORT`。
- [ ] Health Check Path = `/health`。
- [ ] Env: `FRONTEND_ORIGIN`（後で frontend URL）/ `ANALYSIS_EXPORTS_ROOT=analysis_exports` /
      `ENABLE_LIVE_TRADING=false` / `LOG_LEVEL=INFO` / `PYTHON_VERSION=3.11`。
- [ ] deploy 後: `/health` と `/api/reports` を確認。

**Vercel（frontend）**
- [ ] 同 GitHub repo を選択、Root Directory = `frontend`。
- [ ] Framework=Next.js（自動）、Build=既定、Node.js Version=20。
- [ ] Env: `NEXT_PUBLIC_API_BASE_URL` = Render の backend URL。
- [ ] deploy 後: `/reports` 表示・詳細遷移・Markdown コピー・Console/Network 確認。

**仕上げ**
- [ ] Render の `FRONTEND_ORIGIN` を Vercel URL に更新 → backend 再デプロイ（CORS 反映）。
- [ ] §8 疎通確認をすべて実施。

**rollback / 停止判断**
- [ ] 異常時は Vercel/Render の前デプロイへ rollback、または Service を一時停止。
- [ ] 危険導線（注文/secret 露出）を少しでも疑ったら **即停止**し、原因特定まで再公開しない。

---

## 11. 危険領域（初回デプロイで絶対に触らない）

実注文 / 自動売買 / `ENABLE_LIVE_TRADING` の true 化 / `market_order` 有効化 / GMO Private API 接続 /
OANDA 実接続 / RiskManager・注文系の変更 / APIキー・secret の登録・表示・コミット / `.env` のコミット /
DB 本番化（破壊的スキーマ変更）/ 認証の本格実装 / CSV 本文返却・ダウンロード / 新戦略・追加バックテスト。

## 12. 本書の範囲（今回やらないこと）

- 実デプロイ実行、外部サービスへのログイン、Vercel/Render の設定の実反映、secrets 登録、課金設定。
- backend/frontend 実装・テスト・CI・config の変更、実データの追加。
- これらは利用者が手元で（または別フェーズで明示承認のうえ）実施する。
