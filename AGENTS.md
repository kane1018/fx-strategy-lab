# FX Strategy Lab — Codex 作業ルール

このリポジトリでは、目的達成に必要な最小限の変更だけを行う。

## 作業手順

1. 作業前に既存コード、関連 docs、テスト、`git status`、最新 commit を確認する。
2. 変更対象と触らない箇所を整理する。不要な機能追加や大規模リファクタリングはしない。
3. `package.json`、`pyproject.toml`、`requirements*.txt` 等を確認し、実在する検証コマンドだけを実行する。
4. エラー時は根本原因を特定して最小限に修正する。修正と再検証は最大5回までとする。
5. 指定された検証に成功したら停止し、明示依頼なしに次フェーズへ進まない。
6. 最終報告は ChatGPT へそのまま貼れる Markdown 形式で出力する。

## 絶対に行わないこと

- Private API、APIキー、実注文、実資金を扱わない。
- 残高、建玉、注文履歴、約定を取得しない。注文、注文変更、注文取消を行わない。
- `.env` / secret を表示、変更、commit しない。`ENABLE_LIVE_TRADING=true` にしない。
- 本番公開 API を追加せず、`backend/app/main_readonly.py` を変更しない。
- Render / Vercel の設定変更、DB 本番化、認証実装を行わない。
- `shadow_exports/`、実 API レスポンス、集計出力を commit しない。
- `analysis_exports/` に実データを混入させず、生成物を commit しない。

上記に近づく変更は、実装前に必ず ChatGPT または Claude Code を含む事前レビューを行い、明示承認を得る。

## Step 6G Controlled one-shot POST 限定例外

通常作業では、Private API、APIキー、実注文、実資金、残高・建玉・注文照会、HTTP POST、broker/order endpoint、`live_order_once` は引き続き禁止する。

ただし、ユーザーが明示的に `Step 6G Controlled one-shot POST` または同等のStep 6G実行タスクを依頼した場合に限り、以下の限定例外を認める。この例外はStep 6G専用であり、他の通常作業・調査・実装・docs更新には適用しない。

### Step 6Gで限定的に許可すること

- credential presenceを `PRESENT` / `MISSING` のみで確認する。
- credential値、長さ、hash、fingerprint、先頭末尾、headers、signature、token、secretは表示しない。
- `.env` は表示・変更しない。env一覧表示や `printenv` は行わない。
- Step 6Gのfresh preflight目的に限り、public status/ticker GETを実行してよい。
- Step 6Gのfresh preflight目的に限り、Private API read-only GETで以下だけをsanitized取得してよい。
  - `account/assets`: account status / account asset check pass flag
  - `openPositions`: open positions count / pass flag
  - `activeOrders`: active orders count / pass flag
- fresh read-only preflightは、final confirmation前に最大1回、final confirmation後のPOST直前に最大1回だけ許可する。
- final confirmation gateでは、非秘密・非rawのgo/no-go checklistのみ表示してよい。
- ユーザーがCodex画面で指定されたfinal confirmation phraseを完全一致入力した場合に限り、既存の承認済みone-shot経路で最大1回だけHTTP POSTしてよい。
- POST後は、sanitized fieldsだけのread-only reconciliationを最大1回行ってよい。
- Step 6G中も永続設定としての `allowed_for_live=true` 保存は禁止する。最終状態は `allowed_for_live=false` とする。

### Step 6Gでも禁止し続けること

- final confirmation前のHTTP POST。
- HTTP POSTを2回以上実行すること。
- retry、loop、追加注文、決済注文、取消、注文変更。
- `closeOrder`、`cancelOrders`、`changeOrder`。
- 新しいorder endpoint経路の作成、新しいpayload組み立てロジックの作成。
- CodexによるBUY/SELL、symbol、size、executionTypeの推測または変更。
- order payload全文の表示・保存。
- raw request / raw response の表示・保存。
- headers値、signature値、API key値、secret値、token値、credentials値の表示・保存。
- credentialの長さ、hash、fingerprint、先頭末尾の表示。
- `.env`表示・変更、env一覧表示、`printenv`。
- order ID、execution ID、position ID、clientOrderIdの表示。
- approval command全文表示、copyable approval command表示、pbcopy、approval commandファイル保存。
- ledger reset、ledger削除、ledger変更。
- 実API結果、raw request、raw response、headers、signature、credential、real ID、approval command全文のGit保存。
- commit / push。ただし別タスクでAGENTS.md変更自体を明示依頼された場合を除く。

### Step 6Gの停止条件

以下のいずれかに該当する場合、CodexはHTTP POSTせず停止する。

- working treeがdirty。
- HEADがorigin/mainと一致しない。
- credential presenceが不足。
- tests / ruff / danger scanが失敗。
- approval artifact / exact validation / order intent exact matchが確認できない。
- fresh preflightが失敗。
- market closed / unknown、broker maintenance、holiday / special close。
- open positions countが0ではない。
- active orders countが0ではない。
- ticker stale、spread上限超過。
- permission / IP binding / previous result checkが不明または失敗。
- raw/secret/ID非表示を保証できない。
- final confirmation phraseが完全一致しない。
- 少しでも安全に判断できない。

この限定例外は、Codexに投資判断を委ねるものではない。Codexは注文方向、数量、銘柄、executionTypeを推測せず、既存の承認済みartifactおよびユーザーの明示入力と完全一致する場合だけ処理を続行する。

## 最初に読む文書

- `docs/CODEX_HANDOFF.md`
- `docs/PROJECT_STATUS.md`
- `docs/SHADOW_RUNBOOK.md`
- `docs/PUBLICATION_POLICY.md`
- `docs/GMO_PUBLIC_API_PLAN.md`
- `docs/PHASE2_SHADOW_TRADING_PLAN.md`
