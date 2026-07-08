# Strategy Signal Engine Rulebook（no-POST・deterministic・safe-label-only）

Step: `STRATEGY_SIGNAL_ENGINE_SUPERVISED_EVALUATION_NO_POST`
Date: 2026-07-08
実装: `backend/app/services/gmo_strategy_signal_engine.py`

## 1. 目的・対象範囲・対象外

暫定signal logicを明文化した deterministic / rule-based / safe-label-only の
signal engine。**LLMの自由判断は売買判断に一切使わない**(固定table lookupのみ)。

対象外: 実データ取得、raw price/spread/PnL、backtest、live性能評価、
operator判断の代行。**strategy品質(勝率・収益性)は未証明**。

既存logicとの関係: `gmo_supervised_auto_live_preview.derive_auto_preview_signal`
(UPTREND→BUY / DOWNTREND→SELL / FLAT→HOLD / gate不成立→UNKNOWN_BLOCKED)は
本engineの単純部分集合として存続。preview moduleのengine統合は改善候補
(`INTEGRATE_PREVIEW_MODULE_WITH_ENGINE`)であり未実施。

## 2. 入力safe labels(default全unknown=block)

trend(UPTREND/DOWNTREND/RANGE/TREND_UNKNOWN/TREND_CONFLICT)、
momentum(UP/DOWN/FLAT/UNKNOWN)、volatility(NORMAL/HIGH_BLOCKED/UNKNOWN)、
spread(WITHIN/OUT/UNKNOWN)、ticker(FRESH/STALE/UNKNOWN)、
market(SAFE/UNSAFE/UNKNOWN)、session(ALLOWED/BLOCKED/UNKNOWN)、
guard(GUARD_PASS/GUARD_HALT/GUARD_UNKNOWN)、
position context(NO_POSITION/ONE_POSITION/UNKNOWN)。
raw値のfieldは構造的に不存在。

## 3. 出力

- `AUTO_PREVIEW_SIGNAL_BUY / _SELL / _HOLD / _UNKNOWN_BLOCKED`
- `strategy_decision_category`: ENTRY_PREVIEW_PROPOSED / HOLD_NO_ORDER /
  SETTLEMENT_PREVIEW_CONTEXT_ONLY / BLOCKED_FAIL_CLOSED
- `rule_path_safe_label` / `block_reason_safe_label`
- BUY/SELL提案時のみ `required_future_gate_names` と
  `required_operator_input_names`(**名前のみ・値は構造的に保持不能**)
- `why_not_permission` 固定文言

## 4. 評価順序とルール

**評価順**: environment gates → position context → trend×momentum table。

### 4.1 environment gates(固定順・1つでも非safeで即block)

guard≠PASS → BLOCK_GUARD_NOT_PASS / market≠SAFE → BLOCK_MARKET_NOT_SAFE /
session≠ALLOWED → BLOCK_SESSION_NOT_ALLOWED / ticker≠FRESH →
BLOCK_TICKER_NOT_FRESH / spread≠WITHIN → BLOCK_SPREAD_NOT_WITHIN_LIMIT /
volatility≠NORMAL → BLOCK_VOLATILITY_NOT_NORMAL。
いずれも rule path は `RULE_ENVIRONMENT_GATE_BLOCKED`。

### 4.2 position context

- NO_POSITION_CONTEXT: entry preview評価に進む
- ONE_POSITION_CONTEXT: **entry preview禁止**。
  `SETTLEMENT_PREVIEW_CONTEXT_ONLY` + HOLD signal
  (settlement方向は本engineの判断ではなく、prior entryからの機械写像 —
  official settlement preflight の provenance を参照)
- UNKNOWN: block

### 4.3 trend × momentum table(NO_POSITION contextのみ)

| trend | momentum | signal | rule path |
|---|---|---|---|
| UPTREND | UP | BUY | RULE_UPTREND_MOMENTUM_ALIGNED_BUY |
| UPTREND | FLAT | BUY | RULE_UPTREND_MOMENTUM_NEUTRAL_BUY |
| UPTREND | DOWN | HOLD | RULE_TREND_MOMENTUM_CONFLICT_HOLD |
| DOWNTREND | DOWN | SELL | RULE_DOWNTREND_MOMENTUM_ALIGNED_SELL |
| DOWNTREND | FLAT | SELL | RULE_DOWNTREND_MOMENTUM_NEUTRAL_SELL |
| DOWNTREND | UP | HOLD | RULE_TREND_MOMENTUM_CONFLICT_HOLD |
| RANGE | UP/DOWN/FLAT | HOLD | RULE_RANGE_HOLD |
| TREND_UNKNOWN / TREND_CONFLICT | — | UNKNOWN_BLOCKED | RULE_TREND_NOT_DERIVABLE_BLOCKED |
| — | MOMENTUM_UNKNOWN | UNKNOWN_BLOCKED | RULE_MOMENTUM_UNKNOWN_BLOCKED |
| table未定義の組合せ | — | UNKNOWN_BLOCKED | fail-closed default |

## 5. fail-closed policy

UNKNOWN / CONFLICT / 未定義 / 非safe はすべて `AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED`。
HOLDは発注ではない(`order_attempt_created=false` 固定)。

## 6. previewがpermissionでない理由 / auto signalがoperator signalでない理由

- decisionは `actual_entry_POST_allowed=false` / `actual_settlement_POST_allowed=false`
  固定・非truthy。POSTに至る経路が構造的に存在しない
- `AUTO_PREVIEW_SIGNAL_*` は `operator_signal_type`(ENTRY_BUY/ENTRY_SELL/HOLD)と
  別名前空間であり、`auto_preview_signal_is_operator_signal=false` 固定。
  実POSTには常に別Stepで operator current-turn confirmation(完全一致・banking不可)
  と fresh gate 一式が必要

## 7. 今後の評価path

behavior評価(本Step)→ backtest dataset要件定義 → out-of-sample評価 →
operator review samples → paper forward test。**これらが済むまで performance は
主張しない**。evidence:
[STRATEGY_SIGNAL_ENGINE_SUPERVISED_EVALUATION_NO_POST_20260708.md](STRATEGY_SIGNAL_ENGINE_SUPERVISED_EVALUATION_NO_POST_20260708.md)
