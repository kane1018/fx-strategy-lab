# Strategy Signal Engine Supervised Evaluation — no-POST evidence（2026-07-08）

Step: `STRATEGY_SIGNAL_ENGINE_SUPERVISED_EVALUATION_NO_POST`
実装: `backend/app/services/gmo_strategy_signal_supervised_evaluation.py`
rulebook: [STRATEGY_SIGNAL_ENGINE_RULEBOOK_NO_POST.md](STRATEGY_SIGNAL_ENGINE_RULEBOOK_NO_POST.md)

## 1. 目的とno-POST安全境界

deterministic rule engine の**挙動評価**(behavior evaluation)。
利益・勝率・PF・PnLは評価対象外で、該当fieldは構造的に不存在。
actual POST / broker write / real HTTP / private GET / credential / `.env` /
外部データ取得はゼロ。**performance proof status = false**。

## 2. Evaluation plan

- required scenario families: 17(下記)+ deterministic grid 52行(>=50)
- すべてsynthetic safe labelのみ・sleep/外部取得なし・決定論的(同一入力=同一出力をテストで固定)

## 3. 実行結果（safe counts / categoriesのみ）

- status: **STRATEGY_EVALUATION_BEHAVIOR_PASSED**
- scenario families: **17/17 期待一致** — clear uptrend BUY / clear downtrend SELL /
  range HOLD / trend unknown・conflict block / momentum conflict HOLD /
  spread・ticker・market・session・volatility・guard block /
  no-position entry preview可 / one-position settlement context only /
  position unknown block / missing labels block / momentum unknown block
- grid: 52行。signal分布 BUY=3 / SELL=2 / HOLD=6 / UNKNOWN_BLOCKED=41
- category分布: ENTRY_PREVIEW_PROPOSED=5 / HOLD_NO_ORDER=5 /
  SETTLEMENT_PREVIEW_CONTEXT_ONLY=1 / **BLOCKED_FAIL_CLOSED=41**
- block reason分布: SPREAD=10 / TICKER=10 / TREND_UNKNOWN=4 / TREND_CONFLICT=4 /
  GUARD=3 / MOMENTUM_UNKNOWN=3 / MARKET=2 / SESSION=2 / VOLATILITY=2 /
  POSITION_UNKNOWN=1 / POSITION_ALREADY_OPEN=1
- rule coverage: **complete**(定義済みrule path 11種すべてgridで到達)
- fail-closed率: 41/52行がBLOCKED_FAIL_CLOSED(gridは劣化入力を意図的に多数含む)
- HOLD行の発注: **0**(HOLDはorderにならないことを確認)
- preview is permission: false / auto signal is operator signal: false

## 4. Supervised review placeholder

review record 17件を生成。`operator_acceptance_placeholder=NOT_PROVIDED`
(AIはoperator判断を埋めない・テストで固定)、
`excluded_from_performance_claim=true` 全件。

## 5. 改善候補（safe categoryのみ）

IMPROVE_TREND_CONFIRMATION / IMPROVE_RANGE_FILTER / IMPROVE_CONFLICT_HANDLING /
IMPROVE_SESSION_FILTER / IMPROVE_VOLATILITY_BLOCKER / IMPROVE_SETTLEMENT_RULES /
IMPROVE_HOLD_RULES / INTEGRATE_PREVIEW_MODULE_WITH_ENGINE /
NEEDS_BACKTEST_DATASET / NEEDS_OUT_OF_SAMPLE_EVALUATION /
NEEDS_OPERATOR_REVIEW_SAMPLES / NEEDS_PAPER_FORWARD_TEST

## 6. strategy quality status

**未証明**。本評価は「ルールが宣言どおり・fail-closedに・決定論的に動く」ことの
確認であり、勝てる・利益が出る・期待値があることの証明ではない。
品質評価には backtest dataset / out-of-sample / operator review /
paper forward test が別途必要。

## 7. 遵守記録

actual/entry/settlement/close POST=false / POST count=0 / broker write=false /
real HTTP=false / runtime private GET=false / credential・env read=false /
raw・ID・value露出=false / operator confirmation banking=false /
unattended live remains unsupported / unattended full auto completed=false。

## 8. recommended next Step

- 品質評価へ: `STRATEGY_BACKTEST_DATASET_REQUIREMENTS_NO_POST`
- operator review運用へ: `STRATEGY_SIGNAL_OPERATOR_REVIEW_WORKFLOW_NO_POST`
- live監視統合へ: `LIVE_RUNTIME_SAFE_LABEL_ADAPTER_DESIGN_NO_POST`
