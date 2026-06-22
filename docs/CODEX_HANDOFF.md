# Codex 引き継ぎ（CODEX_HANDOFF）

Codex が新しいタスクを安全に開始するための要約済み文脈。詳細な現在地は
[PROJECT_STATUS.md](PROJECT_STATUS.md)、固定ルールは [`../AGENTS.md`](../AGENTS.md) を参照する。

## 1. 目的と現在地

FX Strategy Lab は、FX の検証、ペーパートレード、通知、将来の少額自動売買へ安全に段階移行するための
検証基盤である。現時点では実注文・実資金・Private API・APIキー・本番公開 API 追加を扱わない。

- repository: `https://github.com/kane1018/fx-strategy-lab.git`
- branch: `main`
- frontend production: `https://fx-strategy-lab.vercel.app`
- backend production: `https://fx-strategy-lab.onrender.com`
- production entrypoint: `app.main_readonly:app`
- 現在のフェーズ: **Phase 3A準備ロードマップ設計完了 / Phase 2E-5継続確認は1回目レビュー完了**。Phase 2E-4Rでは直近kline条件の
  `gmo-public / USD_JPY / M1 / steps 5 / --enable-shadow-risk` run
  `20260622_100540_shadow_USD_JPY_gmo-public` をレビューし、実runで `REAL_PUBLIC_BID_ASK` candidate、
  `ALLOW_SHADOW` decision、対応するvirtual result、candidate/decision/virtual resultのID相関を確認した。
  古い3 stepはticker/kline skewによりcandidate生成前の`NO_TRADE`へ安全に倒れた。safety violation 0、
  broken 0、raw response保存なし、Private API/APIキー/broker/実注文なし。詳細は
  [PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md](PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md)。
  Phase 2E-5では、今後のgmo-public risk/audit継続確認をmanual only、`USD_JPY / M1 / steps 5`、
  1日1回まで、短期3回・中期5〜10回を目安に進める計画を定義した。成功/保留/停止条件、ticker/kline skew評価、
  Phase 2Fへ進む条件は
  [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。
  Phase 2E-5 1回目run `20260622_103430_shadow_USD_JPY_gmo-public` では `REAL_PUBLIC_BID_ASK` 2件、
  candidate 2件、`ALLOW_SHADOW` 1件、`REJECT_SHADOW` 1件、ALLOW時のみvirtual result、REJECT時virtual resultなし、
  `cooldown_active` reject、ticker/kline skew 2件の安全`NO_TRADE`を確認した。同日2回目は1日1回ルールにより
  未実行で停止した。詳細は
  [PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md](PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md)。
  次に行えるのは別日のPhase 2E-5 2回目手動実行までであり、Private API、APIキー、broker、実注文、実資金、
  自動売買、本番公開API追加には進まない。
  Phase 3A準備では、将来のPrivate API read-only、APIキー / secret管理、Live Verification Mode、
  100通貨・1回だけの極小実資金検証までのロードマップをdocs-onlyで整理した。これは実装ではなく、
  Private API接続、APIキー入力・表示・保存、`.env`変更、broker、注文API、実注文、実資金検証には進んでいない。
  詳細は [PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md](PHASE3A_PRIVATE_API_READONLY_AND_LIVE_VERIFICATION_ROADMAP.md)。
  Phase 3B read-only実装は、Phase 2E-5短期確認、Phase 2F Public shadow risk/audit安定性レビュー、
  Phase 3Aレビュー完了後の別タスクに限定する。
  Phase 2E-1Hでは`app/shadow/`内の
  OrderCandidate、pure risk評価、sticky Kill switch、deterministic ID、local JSONL writer、legacy互換summarizeに
  対し、Phase 2E-1.5監査のD-1〜D-4を修正した。spread provenanceのfail closed化、malformed inputの
  reason付きreject、typed audit schema/root containment、unsafe risk rowのsummary検出を実装済みである。
  再監査では統合前必須修正なし、Phase 2E-2の設計着手可と判定した。Phase 2E-2設計では、run単位の
  KillSwitchState ownership、pre-gate、AuditLogWriteError時のexit code 2、STOPファイル、candidate/decision/
  virtual result相関、summary互換、統合test方針を整理した。実装では`--enable-shadow-risk`の明示フラグ時のみ
  STOP pre-gate、candidate生成、pure `evaluate()`、typed audit JSONL、REJECT時virtual result抑止、audit失敗時
  fail closed/exit code 2、summary/metadataのrisk情報を接続した。デフォルトrunはlegacy互換を維持する。
  Phase 2E-2.5監査では修正必須事項なし、Phase 2E-3設計へ進行可と判定した。詳細は
  [PHASE2E2_INTEGRATION_AUDIT.md](PHASE2E2_INTEGRATION_AUDIT.md)。Public ticker bid/ask連携実装、
  Private API、broker、実注文へは明示承認なしに進まない。設計は
  [PHASE2E2_SESSION_INTEGRATION_DESIGN.md](PHASE2E2_SESSION_INTEGRATION_DESIGN.md)、再監査結果は
  [PHASE2E1H_REAUDIT.md](PHASE2E1H_REAUDIT.md)、初回監査と修正追記は
  [PHASE2E1_SAFETY_AUDIT.md](PHASE2E1_SAFETY_AUDIT.md)、設計は
  [PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md) と
  [PHASE2E0_5_SAFETY_REVIEW.md](PHASE2E0_5_SAFETY_REVIEW.md) を参照する。
  Private API、APIキー、実注文、本番公開には進まない。

## 2. 完了済みフェーズ

- **v0.1 read-only reports 公開版**: `/`、`/reports`、`/reports/[run_id]`。backend は `/health` と
  `/api/reports*` の GET のみ。orders / paper / automation は公開していない。
- **Production Smoke**: `npm run e2e:prod`、7 tests passed の実績あり。
- **Phase 2A**: `backend/app/shadow/` に local-only / no-network / no-order の shadow 検証土台を実装。
- **Phase 2B**: GMO Public API read-only adapter と local CLI を実装。Public API のみで APIキー・注文なし。
- **Phase 2C**: local shadow run、demo 用 `momentum_signal`、`events.jsonl` / `summary.json` /
  `metadata.json`、仮想 PnL 集計を実装。出力は `shadow_exports/`。
- **Phase 2D**: 複数 run の集計 CLI、Markdown / CSV 出力、safety 違反検出を実装。
- **Phase 2E-3.5**: Public ticker bid/ask provenance連携監査を完了。B判定で、修正必須事項なし。
  Phase 2E-4設計または実行指示作成へ進めるが、実runやPrivate/APIキー/broker/実注文には別承認が必要。
- **Phase 2E-4.5**: gmo-public risk/audit結果レビューを完了。`ticker_kline_skew_reject_count=2` は
  安全fail closed。実runでの`REAL_PUBLIC_BID_ASK` candidate/ALLOWは未確認。
- **Phase 2E-4R**: 直近kline条件のgmo-public再確認レビューを完了。実runで`REAL_PUBLIC_BID_ASK`
  candidate、`ALLOW_SHADOW`、virtual result相関を確認。Phase 2E-5設計へ進める。
- **Phase 2E-5**: gmo-public risk/audit継続確認計画を設計。manual only、1日1回まで、
  `USD_JPY / M1 / steps 5 / --enable-shadow-risk`、短期3回・中期5〜10回、成功/保留/停止条件、
  Phase 2Fへ進む条件を定義。実行、コード変更、Private API、broker、実注文には進んでいない。
- **Phase 2E-5 1回目レビュー**: run `20260622_103430_shadow_USD_JPY_gmo-public` をレビューし、
  `REAL_PUBLIC_BID_ASK` 2件、ALLOW 1件、REJECT 1件、ALLOW時のみvirtual result、REJECT時virtual resultなし、
  1日1回ルールによる同日2回目未実行停止を確認。次は別日に2回目を1回だけ実行する。
- **Phase 3A準備ロードマップ設計**: Private API read-only、APIキー / secret管理、read-only境界、
  Live Verification Mode、Phase 3D極小実資金検証条件をdocs-onlyで整理。実装、接続、`.env`変更、broker、
  注文API、実注文はなし。Phase 3BへはPhase 2E-5短期確認とPhase 2Fレビュー完了後に別タスクで進む。
- 直近確認実績: backend 354 passed、`ruff check .` OK、production smoke 7 passed。

実績値はスナップショットであり、作業時は利用可能なコマンドで再確認する。

## 3. 安全制約と公開境界

### 公開してよい範囲

- 無害な `e2e_*` サンプルによる read-only reports と、その加工済みメタ情報。
- 実取引、実資金、APIキー、個人情報を含まない Markdown 概要。
- CSV 本文を含まないファイルメタ情報。

### 公開・実装してはいけない範囲

- Private API、APIキー、secret、`.env`、実資金、実注文。
- 残高、建玉、注文履歴、約定の取得、および注文・変更・取消。
- 実 API レスポンス、実取引由来レポート、実データ CSV、本番 DB の内容。
- paper / shadow の実行情報、シグナル、ポジション、設定・管理・実行画面の本番公開。
- 本番公開 API の追加、`backend/app/main_readonly.py` の変更、`ENABLE_LIVE_TRADING=true`。
- Render / Vercel 設定変更、DB 本番化、認証実装。
- `shadow_exports/`、集計出力、実データ入り `analysis_exports/` の commit。

公開判断の詳細は [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) を単一参照点とする。

## 4. Codex 中心運用と役割分担

- 基本運用は Codex で、指定タスクの実装・検証・commit・push を行う。ただし commit / push は依頼された場合のみ行う。
- ChatGPT は次タスクの整理、Codex 用プロンプト作成、最終報告レビューに使う。
- Claude Code は大きめの既存設計確認、安全レビュー、複数ファイルにまたがる慎重な改修時に補助的に使う。
- 重要フェーズは ChatGPT または Claude Code で設計確認してから進める。
- Private API、APIキー、実資金、実注文、本番公開 API 追加、DB、認証に近づく場合は必ず事前レビューを挟む。

## 5. 変更境界

タスクごとに、変更してよいファイルを明示して最小限に編集する。shadow 運用タスクの通常範囲は
local-only の `backend/app/shadow/`、関連する `backend/scripts/`、offline tests、関連 docs である。

明示承認なしに変更しない範囲:

- `backend/app/main_readonly.py`、`backend/app/main.py`、backend 公開 API。
- frontend 本番 UI、production smoke、Render / Vercel 設定。
- `.env`、`.env.example`、APIキー、secret、DB、broker、注文・RiskManager 経路。

## 6. 検証コマンド候補

必ず `backend/pyproject.toml` と `frontend/package.json` を先に確認し、変更範囲に必要なコマンドだけを実行する。

```bash
# backend（ローカル・offline）
cd backend
.venv/bin/pytest
.venv/bin/ruff check .

# frontend
cd frontend
npm run lint
npm run test
npm run build
npm run e2e

# production read-only smoke（非破壊。依頼・必要性がある場合のみ）
cd frontend
npm run e2e:prod
```

文書だけの変更では、リンク・記述・diff・禁止対象が未変更であることの確認を優先し、無関係な全テストを
機械的に実行しない。ネットワークを使う GMO Public CLI は自動検証に含めない。

## 7. 生成物を git add しない確認

```bash
git status --short
git status --ignored --short -- shadow_exports backend/shadow_exports analysis_exports
git diff --cached --name-only
git diff --cached --name-only | grep -E '(^|/)(shadow_exports|analysis_exports)/' && exit 1 || true
```

実 API レスポンスや集計出力が別名・別パスにないかも確認する。生成物が見つかった場合は add せず、
ユーザーの既存ファイルを勝手に削除しない。

## 8. 次タスクの始め方

1. `AGENTS.md` と本書を読む。
2. `PROJECT_STATUS.md` とタスクに関係する runbook / policy / plan を読む。
3. `git status --short --branch`、`git log -1 --oneline`、既存コードとテストを確認する。
4. 変更対象、触らない箇所、検証方法を整理する。
5. 最小変更を実装し、最大5回まで修正・再検証する。
6. 成功したら停止し、次フェーズへ自動的に進まない。

Phase 2D-2 を始める場合も、まず [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md) に沿って注文なし・local-only・
上限付き run であることを確認し、運用手順と蓄積確認だけを一つの明確なタスクとして切り出す。

## 9. 最終報告テンプレート

```markdown
# 作業報告

## 結果
- 完了 / 未完了と、その理由

## 変更内容
- 変更ファイル: `path`
- 要点

## 検証
- `実行コマンド`: 成功 / 失敗（件数や要点）
- 未実行項目と理由

## 安全確認
- Private API / APIキー / 実注文 / 実資金: なし
- 本番公開 API・設定変更: なし
- 生成物の commit: なし

## Git
- branch / commit / push の状態

## 次の候補
- 明示依頼があるまで着手しない次タスク
```
