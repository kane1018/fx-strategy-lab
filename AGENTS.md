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

## 重要な注意（2026-07-06 監査で確認・重大インシデント扱い）

`backend/app/live_verification/` 配下の "Step 6G-PC-OX-R-...controlled" 系モジュール
（130ファイル中ほぼ全て）は、dataclassの固定デフォルト値によるシミュレーションであり、
実ブローカー・実HTTP・実credentialとは接続されていない。一方で、以下は**実際にGMO FX本番
Private APIへ実HMAC署名付きHTTP POSTを送信できる実装済みコード**であり、シミュレーションでは
ない。

- `backend/app/live_verification/live_order_once.py`
  （`execute_one_shot_live_order` / `post_live_order_with_httpx`）
- `backend/app/live_verification/live_order_real_official_settlement_actual_transport_no_post_controlled.py`
  （`OfficialSettlementActualTransportHttpxClient`）
- `backend/app/live_verification/live_order_real_one_shot_post_real_delegate_controlled.py`
  （`make_live_order_real_one_shot_post_real_delegate` が上記の実POST関数を解決・呼び出す橋渡し）

これらは現状、明示的な `transport`・実credential・`allow_live_http_post=True` 等をすべて
呼び出し側が渡さない限り発火せず、Step 6G の "controlled/safe" 系モジュールの既定
（zero-arg）エントリポイントからは到達できないことを
`backend/app/tests/test_live_verification_real_post_capability_isolation.py` で固定している。
ただし「実POSTが不可能」であることを意味する命名（`_no_post_controlled` 等）は誤解を招くため、
このファイル名だけを根拠に安全と判断してはならない。新しい "controlled" モジュールを追加する際は、
上記3ファイルをimport・呼び出しに追加しないこと。追加した場合は
`test_live_verification_real_post_capability_isolation.py` が失敗する設計にしてある。

**追記（Step 6G-PC-OX-R-REAL-POST-HARD-GUARD-MINIMAL-NO-POST-C 完了）**: 上記3経路の実POST/実送信
直前に、共通の default-deny ハードガード `backend/app/live_verification/real_broker_post_hard_guard.py`
（`assert_real_broker_post_allowed(*, allow: bool)`）を追加した。`allow` に明示的な `True` を渡さない
限り（`False`/`None`/未設定/その他の truthy値いずれも）例外で拒否し、env/`.env`による解除経路は
存在しない。既存の `allow_live_http_post` 等の個別フラグと合わせた多層防御であり、
`test_live_verification_real_post_capability_isolation.py` にsource scanと専用回帰テストを追加済み。

docs/CODEX_HANDOFF.md の過去の "Step 6G" 記録（entry POST accepted、settlement POST rejected、
runtime safe read の position count 等）は、実ブローカー検証済みの事実ではなく、大半が
上記シミュレーション層の出力または運用者の申告（docs claim）であり、コード監査だけでは
真偽を確認できない。詳細は同ファイル冒頭のインシデント記録を参照。

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
