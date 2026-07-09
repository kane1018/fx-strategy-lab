# Operator Pre-Trade Briefing — read-only 使い方 runbook（no-POST）

設計基準: [OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST_20260709.md](OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST_20260709.md)

**本 briefing は判断材料の提示のみ。売買推奨でも自動売買でも edge 証明でも permission でもない。
read-only・safe-aggregate・no runtime private GET・no fetch・no-POST・SERE 非起動。
`performance_proof_status=false` / `live_ready=false` / `unattended_live_supported=false`（不変）。**

## 1. パイプライン（read-only・純粋関数）

```
SafeLabelSupplyRequest        ← caller が INTERNAL safe state から SAFE ラベルを詰める（取得しない）
      │
      ▼  operator_briefing_safe_label_supply.build_briefing_inputs (fail-closed 正規化)
BriefingInputs (+ supply_cautions)
      │
      ▼  operator_pre_trade_caution_briefing.generate_caution_briefing (warning-first / NO_ACTION default)
CautionBriefing
      │
      ▼  operator_pre_trade_briefing_service.render_operator_pre_trade_briefing (combined warning-first text)
rendered text
```

## 2. API

- `operator_pre_trade_briefing_service.produce_operator_pre_trade_briefing(request) -> OperatorPreTradeBriefingBundle`
  （`input_completeness` / `supply_cautions` / `briefing` / `briefing_text`・never truthy）。
- `operator_pre_trade_briefing_service.render_operator_pre_trade_briefing(request) -> str`
  （[0]入力データ品質cautions → [1..9] warning-first briefing。禁止フラグメント guard 付き）。

### 使用例（read-only・PULL 式）

```python
from app.services.operator_briefing_safe_label_supply import SafeLabelSupplyRequest
from app.services.operator_pre_trade_briefing_service import (
    render_operator_pre_trade_briefing,
)

# operator が売買を検討し始めた時"だけ"（PULL）呼ぶ。system は好機を PUSH しない。
request = SafeLabelSupplyRequest(
    exposure_status="FLAT",                 # INTERNAL safe label（broker 照会ではない）
    pending_order_safe_count=0,
    risk_budget_status="WITHIN_BUDGET",
    execution_readiness="READY",
    trend_range="RANGING",                  # 記述のみ・方向なし
    volatility="NORMAL", spread_condition="NORMAL", liquidity="NORMAL",
    time_of_day="TOKYO", event_proximity="NONE", uncertainty="NORMAL",
    intended_context_labels=("VOL_REGIME_CONDITIONAL_BREAKOUT",),  # 任意・照合用
)
print(render_operator_pre_trade_briefing(request))   # warning-first テキスト（read-only）
```

## 3. SAFE ラベルの供給元（重要な境界）

- `SafeLabelSupplyRequest` に詰めるのは **caller が既に保持する INTERNAL safe 状態**の SAFE ラベルのみ。
  **broker 照会（runtime private GET）はこのパイプラインでは行わない**（規律）。
- **未提供/unknown は fail-closed**：`*_UNKNOWN` に正規化され、supply caution が付き、briefing 側で
  exposure/execution/event/budget 不明 → **hard-stop（NO_ACTION 強調）**。
- **真の broker 照合が必要な場合は、この briefing の"外"の別 operator-gated read-only Step**に分離する
  （それ自体も no-private-GET 規律の下でのみ）。ここには実装しない。

## 4. 不変の境界（このパイプラインが「しない」こと）

- 売買推奨・方向（上下/売買）・confidence/alpha/expected-profit/win-rate を**出さない**。
- `ENTRY_BUY / ENTRY_SELL / HOLD` を**生成しない**（operator safe label のまま）。
- rejected-ledger 照合は **caution のみ**（RESEMBLES_REJECTED / OUTSIDE_TESTED_SCOPE / NOT_ASSESSED・
  **"非棄却＝許可"ではない**・signal でも方向でもない）。
- **no-flag ≠ permission**（警告ゼロでも GO ではない）を毎回明示。
- **SERE を起動しない・briefing は執行しない**。
- fetch / public GET / private API / broker write / credential / env read を**行わない**。

## 5. 運用フロー（PULL・warning-first）と実 POST の分離

1. operator が検討を始めた時だけ **PULL** で briefing を要求。
2. INTERNAL safe state → `SafeLabelSupplyRequest` を組む（取得しない）。
3. `render_operator_pre_trade_briefing` で warning-first テキストを見る。
4. NO_ACTION / hard-stop / tested-scope 照合 / risk・exposure・budget を確認。
5. **operator が自分で ENTRY_BUY / ENTRY_SELL / HOLD を判断し、理由を記録**。
6. 実 POST が必要なら **別 Step で current-turn exact confirmation → max one POST → no retry / no repost →
   post-trade read-only confirmation**（briefing から直行動線は作らない）。

## 6. DEFER（validated edge ＋ operator 承認まで作らない）

`AUTO_PREVIEW_SIGNAL_BUY/SELL` / confidence・uncertainty スコア / live research budget / auto-trade /
regime を live 判断入力にすること。有効化には **validated edge（標準 gate 合格）＋ operator 明示承認**の両方が必要。

## 7. 状態
research_phase=CLOSED_OUT / current_strategy_status=NO_ROBUST_EDGE_FOUND_IN_TESTED_SCOPE /
performance_proof_status=false / live_ready=false / unattended_live_supported=false（すべて不変）。
