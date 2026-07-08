# Unattended Monitoring Runbook（no-POST・paper soak用）

Step: `UNATTENDED_MONITORING_GUARD_AND_PAPER_SOAK_READINESS_NO_POST`
Date: 2026-07-08

本書は paper/fake/synthetic の soak 運用手順である。**live 運用手順ではない**。
報告はすべて safe label / safe category / safe count のみで行い、raw ID /
数量 / 価格 / 損益 / credential / header / signature / broker response本文を
出力・保存・報告してはならない。

## 1. paper soak開始前チェック

- [ ] branch=main / HEAD==origin/main==remote main / working tree clean
- [ ] 対象テスト green(unattended 3ファイル + paper runner + preview)
- [ ] `run_paper_soak_readiness_suite()` が `PAPER_SOAK_READINESS_PASSED`
- [ ] transportがすべて `FakePaperCycleTransport`(is_real_transport=false)
- [ ] kill switch状態が明示的に `false`(不明はhaltが正しい挙動)
- [ ] credential / `.env` / private GET を使う工程がゼロであること

## 2. halt事象別の対応

| 事象 | 意味 | 対応 |
|---|---|---|
| GUARD_HALT_KILL_SWITCH | kill switch作動または状態不明 | soak停止。**解除はoperator確認必須**(自動解除禁止)。原因記録後、operator判断で再開 |
| GUARD_HALT_SPREAD_OUT_OF_LIMIT | spread safe labelが上限外/不明 | 待機。RiskPolicy数値の緩和は禁止。labelがWITHINに戻ってからfreshに再開 |
| GUARD_HALT_TICKER_STALE | ticker stale/不明 | データ供給を確認。復旧までsoak再開しない |
| GUARD_HALT_MARKET_UNSAFE | market unsafe/不明 | 市場時間帯・状態の確認まで待機 |
| GUARD_HALT_MAX_HOLD_EXCEEDED | 保有時間上限超過/不明 | シナリオ・上限設定をreview。上限緩和は operator 判断事項 |
| GUARD_HALT_MAX_LOSS_EXCEEDED | 損失safe category上限超過/不明 | soak停止のうえ operator review。raw PnLは参照しない(safe categoryのみ) |
| GUARD_HALT_ACTIVE_PENDING_PRESENT | active/pending あり/不明 | 状態解消の確認まで再開しない |
| GUARD_HALT_POSITION_COUNT_MISMATCH | 建玉状態/件数の不整合・不明 | **手動確認必須**。state と snapshot の整合を取り直すまで再開禁止 |
| SCENARIO_HALTED_NO_RETRY_SAFE | rejected/timeout/unknown | **再試行しない**。原因分類(safe categoryのみ)→ 新しいfresh cycleとしてのみ再開可 |
| SCENARIO_DUPLICATE_BLOCKED_SAFE | duplicate attempt検出 | 設計どおりのblock。発生経路をreviewし、修正まで再開しない |
| notifier failure | 必須通知の失敗 | safe halt。通知経路復旧まで soak 再開しない |

## 3. safe halt後の再開条件

1. halt原因が safe label で特定・記録済み
2. 原因が解消済み(または synthetic シナリオとして意図どおり)
3. state machine は**新しいinstance**で開始(HALTEDはterminal・再利用禁止)
4. lockを新規取得し、attempt ledgerも新規(countの持ち越し禁止)
5. guard snapshotをfreshに取り直し `GUARD_PASS` を確認

## 4. manual interventionが必要な場合

- kill switch の解除
- position count mismatch / state inconsistent の解消確認
- max loss / max hold 上限の変更(RiskPolicy変更は別途明示Step)
- 通知経路の復旧確認

## 5. live移行の禁止条件（現時点ではすべて該当）

以下がすべて解消されるまで、live(実broker)への移行は禁止:

- operator current-turn confirmation の設計が維持されていること
  (削除・自動生成・bankingはコードでは扱わず、operatorの明示的方針Stepのみ)
- broker write リスクの受容は常に operator 専権
- live用 kill switch / max hold / max loss の**実runtime接続**が未実装
  (本Stepの guard は safe label 入力のみで、live raw adapter は対象外)
- `actual_entry_POST_allowed=false` / `actual_settlement_POST_allowed=false` は不変

**unattended live remains unsupported / unattended full auto completed=false。**

## 6. 報告形式

- CASE / guard decision / scenario outcome / safe count / halt reason safe label のみ
- raw ID・数量・価格・損益・credential・signature・header・broker response本文は禁止
- 「unattended live completed」と記載してはならない
