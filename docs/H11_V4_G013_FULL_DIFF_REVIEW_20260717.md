# H-11 v4 G013 フルdiff独立レビュー記録（no-POST）

Date: 2026-07-17
Reviewer: Claude（Codex実装分に対して独立。自身のサイズ改定分は機械検証で客観化）
Scope: 作業ツリー全差分（Codex G013 VETO解消実装＋no-poll driver修正＋数量10,000→1,000改定＋hash再凍結）

## 判定: **REVIEW_CLEAR**（重大指摘1件は本レビュー内で修正済み）

## 発見と処置

| # | 深刻度 | 内容 | 処置 |
|---|---|---|---|
| 1 | HIGH | AGENTS.md G013例外が「10,000通貨に限定」のまま、凍結世代(1,000通貨)と矛盾。authorization文言と実行コードの不一致 | 修正済み（operator改定注記付きで1,000通貨へ。PROJECT_STATUS §0AG・G013報告のfrozen contractも同時修正） |
| 2 | 期待動作 | AGENTS.md改定によりimplementation_digest不一致（設計どおりの再凍結要求） | digest再焼成: reviewed_files=sha256:7dda0da4…・世代digest=sha256:b9324e1a…・両テンプレート更新・load再検証OK |

## 観点別結果

### ① 安全不変条件（POST表面）— CLEAR
- canary_activation: intentにexact_order_sheet_digestを結合（provenance強化）・1,000固定・challenge文言G013化
- actual_transport: order/settle合計の上限1,000へ整合
- exit_dispatcher: reconciliation持ち回り方式へ変更（Private GET削減）＋分類ゲート追加（FILLED_UNPROTECTED/FLAT_OR_REJECTED以外は即エラー）— fail-closed強化
- coordinated_actual_path: 新規3メソッドとも evidence一回消費・15秒age上限・逸脱で即unknown halt
- g013_canary: session一回消費→exact binding再検証→permit直前clean-main再確認→resume+current-turn proof→permit→try/finally binding close。entry/cancel/OCO各1 attempt・分類ゲート・結果はsafe labelのみ。secret入力はgetpass（echoなし）
- runtime_driver: 保護確認後はheartbeat＋ローカルsnapshot＋exit marker監視のみ（Private GET 0回、テストで固定済み）
- preparation_guard: PUBLIC_GETを順序付き準備操作として追加（count==2・raw非保持・POST 0を証明要求）。reviewed対象にG013新規ファイル・報告doc・AGENTS.mdを包含
- danger scan: 禁止パターン検出0

### ② サイズ/ハッシュ整合 — CLEAR
- サイズ意味の10_000残存: 0件（paper_runnerの記録件数上限のみ・非該当）
- protection hash: ピン留め==再計算 一致（sha256:2b2a5d86…）
- policy config hash: sha256:58a9a63e…（requested_size=1000をhash対象に反映済み）
- テンプレート2件: quantity_units=1000・全hashフィールド整合・load関数で往復検証OK

### ③ テスト完全性 — CLEAR
- JPY予算（5,000/10,000/50,000円）: 無変更
- 境界テスト: UNDERSIZED=800 / OVERSIZED=1,200（1,000の±20%境界として有効）
- planned loss: ATR0.20→351円（式検算一致）・ATR4.00→上限5,000円超過rejectテスト健在（非空洞化）
- EUR_USD unowned検出行: 無傷
- 削除されたテスト・コメントアウトされたassertion: なし

## 検証サマリ

```text
h11_auto: 475 passed / full backend: 8,063 passed（Keychain統合testは境界どおり除外）
ruff: passed / git diff --check: passed / danger scan: clear
generation: H11_AUTO_30M_20260717_G013 / quantity_units=1000
reviewed_files_digest=sha256:7dda0da4176673619320a…
generation_digest=sha256:b9324e1a141d310cb0aa3…
actual_post=0 / broker_read=0 / credential_read=0（本レビューを通じて）
```

## 残作業（レビュー外・operator側）

- commit後のpush（G013契約はHEAD==origin/mainを要求。pushはoperator承認事項）
- 外部準備（Keychain/notification/host/exclusivity/Public/Private GET/LaunchAgentのfresh G013 operation）
- actual canary当日のfresh resume phrase＋current-turn challenge入力（operator専任）
