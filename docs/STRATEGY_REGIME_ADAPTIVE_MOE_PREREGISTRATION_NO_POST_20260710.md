# H-11 Regime-Adaptive Mixture of Experts Directional Probability — Preregistration Draft (no-POST)

Date: 2026-07-10
Hypothesis ID: `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY`
Status: `SPEC_FROZEN`（2026-07-11 operator 承認・[freeze doc](STRATEGY_H11_SPEC_FREEZE_DRAFT_NO_POST_20260711.md)）
Registry status: `OPERATOR_SELECTED_UNPROVEN`
Operator selected: 2026-07-10
Selected despite rejected: `false`

```text
frozen_spec=true
config_hash=sha256:7bff1ee4b8427a67111f289211bca5d654f1ae38bc3670bd1592a3ba9790e4a1
formal_test=RESERVED_FORWARD_FROM_2026-07-11_NOT_COLLECTED
current_stage=SPEC_FROZEN_PRE_STAGE1
stage1_wiring_allowed=true   # 2026-07-11 operator 授権（STAGE1_PAPER_WIRING_STEP・no-POST）
stage1_execution_allowed=false  # 配線・発火テスト完了後の operator 確認待ち
paper_execution_allowed=false
stage2_allowed=false
stage3_allowed=false
live_allowed=false
actual_post=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```

全 `PENDING_OPERATOR_DECISION` 項目は [spec freeze doc](STRATEGY_H11_SPEC_FREEZE_DRAFT_NO_POST_20260711.md)
で凍結された（§8 の項目リストの正は同 doc §1〜§5）。
本書は live、broker/API、credential/env 読取、POST、forward データ取得を許可しない。

## 1. 検証対象と反証可能な主仮説

時刻 `t` までに利用可能な情報だけを使う低容量soft routerが、相互に異なる3つの方向expertへ
非負かつ総和1の重みを与える。

\[
\hat P(r_{t,h}>0 \mid x_t)
=
\sum_{i=1}^{3}w_i(x_t)\hat P_i(r_{t,h}>0 \mid x_t),
\qquad
w_i(x_t)\geq0,
\qquad
\sum_{i=1}^{3}w_i(x_t)=1
\]

主仮説は、同じeligible timestamp集合で採点した状況依存Mixture of Experts（MoE）の
方向確率が、equal-weight ensembleよりfrozen formal testのBrier scoreを改善することである。

帰無仮説は、動的重みがequal-weightへ追加予測力を持たず、formal out-of-sampleで改善しないことである。
equal-weightを上回らなければrouterの複雑化根拠はなく、H-11を支持しない。

本仮説が扱うのは**方向確率予測**だけである。売買収益、注文方向、取引適格性、執行品質、live readinessは
本仮説の支持条件に含めず、予測性能からそれらを推論しない。

## 2. 初期モデル境界（固定予定・追加禁止）

### 2.1 Directional experts: exactly 3

1. `TREND_CONTINUATION`: 直近方向・トレンド構造の継続確率を推定する。
2. `MEAN_REVERSION`: 価格乖離・レンジ内位置から反転確率を推定する。
3. `BREAKOUT_CONTINUATION`: 収縮後または境界突破後の継続確率を推定する。

`session/time-of-day` はexpertではなくrouter入力、unconditional baselineは比較対象である。
類似indicatorをexpertとして追加しない。第4expertを追加する場合は本H-11を変更せず、新version・新契約として扱う。

### 2.2 Regime/router axes: at most 5

1. `TREND_RANGE_STATE`
2. `VOLATILITY_STATE`
3. `BREAKOUT_TRANSITION_STATE`
4. `SESSION_STATE`
5. `LIQUIDITY_COST_STATE`

各軸の具体的な特徴量、lookback、正規化、欠損処理は未決定であり、formal test前に凍結する。
初期版へevent/news、金利差、cross-asset、risk-on/off、自由文、裁量ラベルを追加しない。

### 2.3 Router

- routerは**1個の低容量soft router**に限定する。
- 重みは時刻 `t` までの情報だけから決める。
- session別・regime別に複数routerを作らない。
- 初期版ではonline update、HMM、LightGBM、LLM、end-to-end高容量モデルを使わない。
- formal test期間を見た後のfeature、expert、weight、hyperparameter、calibration変更は禁止する。

## 3. 出力契約

研究層が出力できるのは次だけである。

```text
p_up
p_down
expert_probabilities
expert_weights
model_uncertainty
prediction_status
block_reasons
```

`prediction_status` は計算可否・データ品質状態であり、取引判断ではない。
本研究層は `BUY_CANDIDATE`、`SELL_CANDIDATE`、`ENTRY_BUY`、`ENTRY_SELL`、`HOLD` を生成しない。
出力から実POSTへの直接接続も作らない。

確率・重みのcoherenceは次を必須とする。

- `p_up`と`p_down`はfiniteかつ`[0,1]`で、和が凍結済みの決定論的tolerance内で1であること。
- 各expert probabilityはfiniteかつ`[0,1]`であること。
- 各expert weightはfiniteかつ非負で、和が同じ凍結済みtolerance内で1であること。
- NaN、Inf、範囲外、normalization failureは`prediction_status=BLOCKED`とsafeな`block_reason`を返し、
  prediction eligibleとして扱わない。
- toleranceは`probability_normalization_tolerance=PENDING_OPERATOR_DECISION`であり、仕様凍結前に決める。

将来のpreview写像は
[staged live policy §2](REGIME_ADAPTIVE_MOE_STAGED_LIVE_POLICY_NO_POST_20260710.md)の構造だけを予定する。
threshold、eligibility、abstention/disagreement/uncertainty定義は
`stage1_prediction_to_preview_mapping=PENDING_OPERATOR_DECISION`の一部であり、現時点では未確定・未実装である。

## 4. 比較対象と採点母集団

最低限の比較対象は次とする。

- `p_up=0.5` の無条件baseline
- 単純な方向継続モデル
- 単純な方向反転モデル
- 3 expertそれぞれの単独モデル
- expertのequal-weight ensemble
- development/validationだけで固定したfixed-weight ensemble
- 状況依存MoE
- 同じ特徴量を用いる単一の直接予測モデル（採用可否は凍結前に決定）

主比較は `状況依存MoE vs equal-weight ensemble`。primary metricはBrier score、
confirmatory metricはLog lossとする。

**全eligible timestampを同一分母で採点する。** `NO_TRADE`、confidence threshold、regime uncertainty、
expert disagreement等を理由にprimary scoringから都合よくtimestampを除外してはならない。
欠損・計算不能は事前固定したfail-closed規則で扱い、coverageも必ず報告する。
将来、NO_TRADEを定義しても、それはprimary予測スコアとは別のsecondary analysisであり、
主比較の母集団を変更しない。

## 5. 評価契約

- primary: `Brier score`
- confirmatory: `Log loss`
- secondary: calibration、balanced/directional accuracy、確率帯別実現率、regime別性能、
  expert別寄与、expert間相関、router ablation、coverage
- horizonごとに独立採点し、異なるhorizonを混ぜない。
- overlapping labelを考慮したpurged walk-forwardとembargoを用いる。
- training、validation、formal testを分離する。
- best single expertやfixed weightsはtraining/validationだけで固定し、formal testで再選択しない。
- 不確実性評価は時系列依存を考慮したblock bootstrapを使用する予定とし、block length等は事前固定する。
- 最低効果量、confidence rule、支持・棄却・insufficient条件はformal test前に凍結する。

## 6. Formal testと反復禁止

- 既に参照・利用されたM5/H1期間はすべて**development-only**であり、untouched formal testとはみなさない。
- formal testには、仕様・実装・synthetic検証を凍結した後のforward期間、または仮説設計に未使用の
  truly untouched期間をoperatorが別途予約する。
- formal testは `NOT_RESERVED`。期間・データ出所・利用可否を現時点で推測しない。
- frozen `config_hash`ごとにformal test採点は1回だけとする。
- 結果を見てから同じtestへ再適合、再実行、optional stopping、別program IDでの同等再試験をしない。
- 再検証は独立した新規データ、事前記録したcorrective rationale、新version、新`config_hash`を必要とする。
- program-level campaign historyへ成功・失敗・insufficientをすべて残す。

## 7. 既存棄却証拠との関係

H-11は過去の棄却を消去・再包装しない。特に次をrelated rejected evidenceとして保持する。

- H-01: M5 technical（trend/breakout/mean-reversionを含む）がコスト後robust edgeを示さなかった。
- H-02: H1 trend continuationがexecution friction下でrobustでなかった。
- H-03: session momentumがsign-permutation対照を上回らなかった。
- H-05: volatility-regime conditional breakoutが改善方向でもrobustでなかった。

H-11の異なる主張は「個々の売買ルールの収益性」ではなく「事前情報による低容量routerの方向確率への
追加価値」である。したがって `selected_despite_rejected=false` とする一方、上記棄却事実を弱めない。
研究トラックは `CLOSED_OUT` のままで、本選定は多重検定null、escalation則、過去verdictを変更しない。

## 8. 未決定項目（2026-07-11 全項目凍結済み）

以下の全項目は [spec freeze doc](STRATEGY_H11_SPEC_FREEZE_DRAFT_NO_POST_20260711.md) §1〜§5 の値で
凍結された。以下のリストは選定時点の履歴として保持する（値の正は freeze doc）。

```text
symbol=PENDING_OPERATOR_DECISION
timeframe=PENDING_OPERATOR_DECISION
prediction_horizon=PENDING_OPERATOR_DECISION
return_and_tie_label_definition=PENDING_OPERATOR_DECISION
eligible_timestamp_definition=PENDING_OPERATOR_DECISION
expert_feature_equations=PENDING_OPERATOR_DECISION
feature_lookbacks_and_normalization=PENDING_OPERATOR_DECISION
expert_model_forms_and_capacity=PENDING_OPERATOR_DECISION
probability_calibration_method=PENDING_OPERATOR_DECISION
router_equation_capacity_and_regularization=PENDING_OPERATOR_DECISION
router_retraining_cadence=PENDING_OPERATOR_DECISION
missing_and_out_of_domain_policy=PENDING_OPERATOR_DECISION
training_validation_split=PENDING_OPERATOR_DECISION
purge_and_embargo_lengths=PENDING_OPERATOR_DECISION
formal_test_source_and_period=PENDING_OPERATOR_DECISION
formal_test_minimum_sample=PENDING_OPERATOR_DECISION
formal_test_independent_subperiods=PENDING_OPERATOR_DECISION
minimum_effect_size=PENDING_OPERATOR_DECISION
minimum_primary_coverage=PENDING_OPERATOR_DECISION
log_loss_degradation_tolerance=PENDING_OPERATOR_DECISION
calibration_degradation_tolerance=PENDING_OPERATOR_DECISION
probability_normalization_tolerance=PENDING_OPERATOR_DECISION
block_bootstrap_and_statistical_rule=PENDING_OPERATOR_DECISION
support_reject_insufficient_rules=PENDING_OPERATOR_DECISION
direct_model_comparator_inclusion=PENDING_OPERATOR_DECISION
stage1_prediction_to_preview_mapping=PENDING_OPERATOR_DECISION
entry_probability_thresholds=PENDING_OPERATOR_DECISION
no_trade_thresholds=PENDING_OPERATOR_DECISION
maximum_expert_disagreement=PENDING_OPERATOR_DECISION
unknown_regime_and_transition_definition=PENDING_OPERATOR_DECISION
expected_move_or_magnitude_model=PENDING_OPERATOR_DECISION
transaction_cost_and_uncertainty_buffer_rule=PENDING_OPERATOR_DECISION
allowed_trading_hours=PENDING_OPERATOR_DECISION
expected_trade_frequency=PENDING_OPERATOR_DECISION
maximum_spread=PENDING_OPERATOR_DECISION
event_exclusion_window=PENDING_OPERATOR_DECISION
position_size=PENDING_OPERATOR_DECISION
stop_loss_rule=PENDING_OPERATOR_DECISION
take_profit_rule=PENDING_OPERATOR_DECISION
maximum_holding_time=PENDING_OPERATOR_DECISION
model_health_window_and_stop_rule=PENDING_OPERATOR_DECISION
restart_rule=PENDING_OPERATOR_DECISION
stage1_exit_and_risk_contract=PENDING_OPERATOR_DECISION
budget_compatibility_reconfirmation=PENDING_OPERATOR_DECISION
```

## 9. 現在の停止点

operatorによるH-11選定は記録するが、上記仕様未決定のため本書は凍結済み事前登録ではない。
次に可能なのは、operatorが未決定項目を確定する別docs-only spec-freeze Stepだけである。
実装、データ閲覧・取得、backtest、Stage 1配線・実行、paper、live、API/broker、credential/env、POSTは停止する。

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
private_api=false
public_api=false
public_get=false
data_fetch=false
credential_read=false
env_read=false
raw_request_response_access=false
raw_id_value_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
automatic_trade_authority=false
```
