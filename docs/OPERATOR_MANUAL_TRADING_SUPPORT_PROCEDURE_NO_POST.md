# Operator 手動運用支援 手順（read-only・no-POST）

対象: operator が**自分の外部トレード環境で裁量トレードする際**に、この repo の read-only ツールを
**判断材料・規律・記録**として併用するための手順。
関連: [briefing 使い方](OPERATOR_PRE_TRADE_BRIEFING_READONLY_USAGE_NO_POST.md) /
[設計](OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST_20260709.md)

**このツール群は判断材料の提示と記録のみ。売買推奨でも自動売買でも edge 証明でも permission でもない。
read-only・safe-aggregate・no runtime private GET・no fetch・no-POST・no credential・SERE 非起動。
実際の発注は operator が自分の外部環境（または別の operator-gated one-POST Step）で行う。
`performance_proof_status=false` / `live_ready=false` / `unattended_live_supported=false`（不変）。
これは"利益装置"ではなく、過信・後付け最適化・過剰売買を抑える"規律・摩擦・記録"の道具。
検証済み edge は無い（NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE）。あなたの裁量にも検証済み優位性は無い。**

## 1. 使うモジュール（read-only）

- `operator_briefing_safe_label_supply`（SAFE ラベル正規化）
- `operator_pre_trade_briefing_service`（briefing 生成 + render）
- `operator_briefing_session`（session 起票・**operator の決定の記録**・render）

## 2. 手動運用フロー（PULL・warning-first）

1. **PULL**: あなたが売買を検討し始めた時"だけ" briefing を起票する（system は好機を通知しない）。
2. **SAFE ラベルを組む**: あなたが**内部で把握している**状態を SAFE ラベルとして `SafeLabelSupplyRequest` に入れる
   （exposure/orders/budget/execution readiness/market-state カテゴリ/event/uncertainty）。
   **broker 照会（runtime private GET）はしない**。不明は空欄でよい（fail-closed で caution 化）。
3. **session 起票**: `start_operator_briefing_session(request, session_label=...)`。
4. **briefing を読む**: `render_operator_briefing_session(session)`（warning-first）。
   NO_ACTION / hard-stop / tested-scope 照合 / risk・exposure・budget / uncertainty を確認。
   **警告ゼロでも GO ではない（no-flag != permission）**。
5. **あなたが判断**: ENTRY_BUY / ENTRY_SELL / HOLD / NO_ACTION を**あなた自身が決める**（system は決めない）。
6. **記録**: `record_operator_decision(session, OperatorDecisionLabel.OPERATOR_DECIDED_*, reason)`。
   理由は必須（後日レビューで後付け合理化を検出するため）。
7. **発注が必要なら**: あなたの**外部トレード環境**で執行する。
   この repo 経由で実弾を出す場合のみ、**別 Step の operator-gated one-POST**
   （current-turn exact confirmation → max one POST → no retry / no repost → post-trade read-only confirmation）。
   briefing/session から発注への"直行動線"は無い（あなたが必ず挟まる）。

### コード例（read-only）
```python
from app.services.operator_briefing_safe_label_supply import SafeLabelSupplyRequest
from app.services.operator_briefing_session import (
    start_operator_briefing_session, record_operator_decision,
    render_operator_briefing_session, OperatorDecisionLabel,
)

req = SafeLabelSupplyRequest(
    exposure_status="FLAT", risk_budget_status="WITHIN_BUDGET",
    execution_readiness="READY", trend_range="RANGING", volatility="NORMAL",
    spread_condition="NORMAL", liquidity="NORMAL", time_of_day="TOKYO",
    event_proximity="NONE", uncertainty="NORMAL",
    intended_context_labels=("VOL_REGIME_CONDITIONAL_BREAKOUT",),  # 任意（照合用）
)
session = start_operator_briefing_session(req, session_label="2026-07-09-am")
print(render_operator_briefing_session(session))       # warning-first を読む

# ↓ あなた自身の判断を"記録"（system は決めない）
session = record_operator_decision(
    session, OperatorDecisionLabel.OPERATOR_DECIDED_HOLD, "spread 拡大・様子見")
print(render_operator_briefing_session(session))       # session log（監査用）
```

## 3. あなたが見るべき点（チェックリスト）

- disclaimer（no edge / not advice / no-flag != permission）を読んだ。
- NO_ACTION の該当理由・hard-stop を確認した。
- tested-scope 照合（この状況は棄却済に類似か・未検証領域か）を確認した。
- risk budget / exposure が上限内。
- **この判断は自分の裁量であり、system の検証済み優位性に基づかない**。
- 決定理由を記録した。

## 4. 境界（このツールが「しない」こと）

- 方向（上下/売買）・confidence/alpha/expected-profit/win-rate を**出さない**。
- `ENTRY_BUY / ENTRY_SELL / HOLD` を**生成しない**（あなたが決め、system は記録するだけ）。
- fetch / public GET / private API / broker 照会 / credential / env read / actual POST を**行わない**。
- SERE を起動しない・実弾を動かさない。

## 5. DEFER（validated edge ＋ operator 承認まで作らない）
`AUTO_PREVIEW_SIGNAL_BUY/SELL` / confidence スコア / live research budget / auto-trade /
regime を live 判断入力にすること。

## 6. 正直な運用上の注意
- **edge 不在のまま実弾に進むと期待値はマイナス**。このツールは規律・記録であって収益を生まない。
- 実弾は「損を上限管理する研究費」としてのみ、かつ**あなたの明示的な判断・per-POST 確認**で。
- 勝っても**ロットを上げない**／負けても**条件を変えない**（後付け最適化の禁止）。
