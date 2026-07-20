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

## 追補: 独立3観点レビュー（architecture/safety/operations）

`docs/templates/h11_v4_actual_preparation_evidence.json` の外部準備ゲートは
`architecture_review_clear`/`safety_review_clear`/`operations_review_clear` を独立に要求する
（digestが変わるたびリセットされる設計）。commit `28fecc8..bef9db5` に対し、上記の全diffレビューとは
別に3系統を並行・独立実施した。

| 観点 | 判定 | 主な指摘 |
|---|---|---|
| Architecture | CONCERNS_FOUND（non-blockingのみ） | `h11_v4_gmo_public_preflight.py`の責務混在、G013スプレッド上限定数の配置、shadow/paper共有クライアントへの依存、`recover_pending_transport_once`の死んだ本番コード、1,000上限値の非単一情報源（いずれも修正不要・将来クリーンアップ候補） |
| Safety | **CLEAR**（blocking無し） | 1,000上限を8箇所で独立検証（exact-equality・型チェック含む）、no-retry/fail-closed分類を実コードで確認、driverのPrivate GET除去を確認、資格情報非露出を確認 |
| Operations | CONCERNS_FOUND → **修正済み** | **[blocking→解消]** `AGENTS.md:320`に旧数量「10,000」が残存し303-307行の改定注記と矛盾していたため`1,000`へ修正。non-blocking: preparation ledgerのstep 60（LaunchAgent）が`V4PreparationOperation` enumに存在せず完了evidenceが検証しない、途中失敗時の世代再起不能が明文化不足、`launchctl bootstrap`の冪等性、operatorスクリプトCLIエントリポイント自体のテスト不足 |

AGENTS.md修正により`reviewed_files_digest`・`generation_manifest_digest`を再焼成し、両テンプレートを更新した。
h11_auto 475 passed（re-run）・ruff clean・diff --check clean。architecture/safety/operations
review flagsをすべて`true`へ更新。

```text
reviewed_files_digest=sha256:7f76c7643a4f63d67779eef850d55cc292c8032385e94523ab08096652d9397b
generation_digest=sha256:c9d27bd1a7336868573ec2701f77a2aa13d525f340508060f682faa8eb806ff9
```

## 2026-07-20 host rehearsal corrective generation review

旧G013 generationの`30_host_kill`は`READ_ONLY_HOST_CHECK_FAILED`で停止し、旧state rootは
`30_host_kill.started.json`を含めて保持した。旧markerの削除、変更、reset、証拠流用は行っていない。
safe markerは失敗commandを永続化しないため一意の事後特定はできないが、個別read-only probeと実装契約から、
DNS/接続時間を含むSNTPが非管理者wrapperの固定5秒を一時的に超え得る点を最小corrective対象とした。

- 実装: `sntp -t 2 time.apple.com`のwrapper timeoutだけを有限15秒へ変更。
- 不変: `pmset`と直接`systemsetup`は5秒、管理者read-only fallbackは120秒。
- 不変: fail-closed safe label、same-generation no-retry、broker POST hard deny。
- focused host/network-time: 9 passed。
- h11_auto: 475 passed（pandas FutureWarning 2件は既存non-blocking）。
- full backend: 8,063 passed（既存v3 test-only Keychain統合testを境界どおり除外）。
- ruff、`git diff --check`、danger scan: clear。
- 独立read-only review: Architecture CLEAR / Safety CLEAR / Operations CLEAR。
- non-blocking LOW: direct `systemsetup`の5秒を専用assertしていないが、同じdefault branchの5秒はpmset testで固定。

```text
generation=H11_AUTO_30M_20260717_G013
reviewed_files_digest=sha256:1bbedc947856af6102c62a8fcc44176042fc51c8ccb509075ef6d8f366f34475
generation_digest=sha256:6adf77c70be1c4344eb5e2001f17f952f81552cbcfaaa9e9e3c20399934e3fda
actual_post=0 / broker_post_authorized=false / activation_permit_issued=false
```

同じG013 labelでもdigestで旧失敗generationと分離された新規generationである。外部準備はcommit/push後の
clean mainでpresenceから最初から行い、旧Keychain、通知、Public/Private GET、signal、quote、operator入力、
permit、preflight結果を流用しない。

non-blocking指摘は本レビューの対象外（operator側の任意クリーンアップ）として記録するのみとし、
G013の外部準備ゲートを止めるものではない。
