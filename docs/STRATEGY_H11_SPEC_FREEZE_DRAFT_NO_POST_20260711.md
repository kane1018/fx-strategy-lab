# H-11 Spec Freeze Draft — 全未決定項目のドラフト値（no-POST）

Date: 2026-07-11
Applies to: `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY`
Status: **FROZEN**（operator 承認: 2026-07-11 05:30 JST）

本書は [H-11 preregistration draft §8](STRATEGY_REGIME_ADAPTIVE_MOE_PREREGISTRATION_NO_POST_20260710.md)
の全 `PENDING_OPERATOR_DECISION` 項目の凍結値である。operator は 2026-07-11 に全項目を
無修正で承認した（`H11_SPEC_FREEZE_STEP`）。

```text
frozen_spec=true
config_hash=sha256:7bff1ee4b8427a67111f289211bca5d654f1ae38bc3670bd1592a3ba9790e4a1
config_hash_basis=git blob at commit d7cf8c3 (docs/STRATEGY_H11_SPEC_FREEZE_DRAFT_NO_POST_20260711.md)
formal_test=RESERVED_FORWARD_FROM_2026-07-11_NOT_COLLECTED
current_stage=SPEC_FROZEN_PRE_STAGE1
actual_post=false / entry_post=false / settlement_post=false / post_count=0
data_fetch=false / broker_read=false / credential_read=false
performance_proof_status=false / live_ready=false / unattended_live_supported=false
```

**変更禁止**: 本書の §1〜§5 の値の変更は禁止する。変更は review window でのみ可能で、
新 version・新 `config_hash` としての再登録（=別実験）を要する（ACTIVE policy §4）。
`config_hash` は commit `d7cf8c3` 時点の本書全文の SHA-256 であり、本 freeze 追記自体は
hash 対象に含まれない（承認前ドラフト全文が凍結対象）。

数値はすべて sanitized（円建て上限・pip 基準・バー数）。raw price/spread/PnL/ID は含まない。

---

## 1. 対象・ラベル・母集団

| 項目 | ドラフト値 | 根拠 |
|---|---|---|
| symbol | USD/JPY | 既存 development データ・実行境界・live 実績が全て USD/JPY |
| timeframe | H1 | M5 は H-01 で系統的に棄却済み。低頻度は Stage 2 per-trade confirmation と整合 |
| prediction_horizon | 24 H1 バー（約1営業日） | 予算の max 1 trade/day と整合。overlap は purge で処理 |
| return_and_tie_label_definition | label = 1 if close(t+24) > close(t) else 0。完全一致（tie）は eligible から除外し coverage に計上 | 決定論・fail-closed |
| eligible_timestamp_definition | 月〜金の完結済み H1 バーで、全特徴量 lookback（最大120バー）が欠損なく揃う時刻。取引時間帯フィルタは**執行側のみ**に適用し、採点母集団からは除外しない | preregistration §4「NO_TRADE で primary scoring を filter しない」に整合 |

## 2. Expert・特徴量・モデル容量

| 項目 | ドラフト値 |
|---|---|
| expert_feature_equations | **TREND**: ret_24 / ret_120 / (close−SMA120)のz。**MEAN_REV**: (close−SMA24)のz / RSI(14) / Bollinger(20,2)内位置。**BREAKOUT**: ATR(14)/ATR(96)比 / 24バー高値・安値ブレイク距離 / ブレイク後経過バー数。各expert 3特徴量固定・追加禁止 |
| feature_lookbacks_and_normalization | 最大 lookback 120 バー。rolling z-score（窓500バー）、±4でクリップ。クリップ超過は out-of-domain |
| expert_model_forms_and_capacity | 各 expert = L2正則化ロジスティック回帰（切片込み4パラメータ以下）。木・NN・boosting 禁止 |
| probability_calibration_method | 追加 calibration なし（ロジスティック出力をそのまま使用）。isotonic 等の柔軟な後処理は初期版で禁止 |
| router_equation_capacity_and_regularization | 5 regime 軸入力の線形 softmax router（3 expert × 6 パラメータ = 18 以下）、L2正則化 |
| router_retraining_cadence | online update なし。training 期間で1回のみ fit。再学習は新 version・新 `config_hash` としてのみ |
| missing_and_out_of_domain_policy | NaN / lookback 不足 / クリップ超過 / 正規化失敗 → `prediction_status=BLOCKED` + safe block_reason。補間・前値埋め禁止 |

regime 軸の具体化（router 入力・各1特徴量に限定）:
TREND_RANGE_STATE=|close−SMA120|のz、VOLATILITY_STATE=ATR(24)のz、
BREAKOUT_TRANSITION_STATE=ATR(14)/ATR(96)比、SESSION_STATE=東京/欧州/NYの3値one-hot、
LIQUIDITY_COST_STATE=時間帯別スプレッド階級（sanitized 2値: 通常/広）。

## 3. 学習・検証・formal test

| 項目 | ドラフト値 |
|---|---|
| training_validation_split | development データを時系列で前 70% / 後 30% に分割 |
| purge_and_embargo_lengths | purge = 24 バー（= horizon）、embargo = 24 バー |
| formal_test_source_and_period | **freeze 日以降の forward 期間**（別授権の取得 Step で収集）。過去の参照済み期間は使用不可 |
| formal_test_minimum_sample | 26週以上 かつ eligible 2,500 timestamp 以上 |
| formal_test_independent_subperiods | 前半・後半の 2 subperiod で改善方向の符号が一致すること |
| minimum_effect_size | MoE の Brier が equal-weight 比 **1% 以上相対改善**、かつ block bootstrap 90% CI が 0 改善を除外 |
| minimum_primary_coverage | eligible の 95% 以上を採点（coverage 必須報告） |
| log_loss_degradation_tolerance | equal-weight 比 相対 +0.5% 以内（悪化がこれを超えたら支持しない） |
| calibration_degradation_tolerance | ECE 絶対 +0.01 以内 |
| probability_normalization_tolerance | 1e-6 |
| block_bootstrap_and_statistical_rule | circular block bootstrap、block 長 120 バー（≈1週）、10,000 リサンプル、90% CI |
| support_reject_insufficient_rules | **SUPPORT**: 効果量達成 ∧ CI が 0 を除外 ∧ 両 subperiod 符号一致 ∧ confirmatory/calibration が許容内。**REJECT**: CI が改善を除外 or 符号逆転。**INSUFFICIENT**: それ以外（サンプル不足・coverage 未達含む） |
| direct_model_comparator_inclusion | **採用**（全9特徴量の単一 L2 ロジスティック）。MoE が直接モデルにも劣るなら構造の複雑化根拠なし |

## 4. Preview 写像・執行境界（Stage 1 paper / 将来 Stage 2 共通契約）

| 項目 | ドラフト値 |
|---|---|
| stage1_prediction_to_preview_mapping | [staged live policy §2](REGIME_ADAPTIVE_MOE_STAGED_LIVE_POLICY_NO_POST_20260710.md) の優先順（安全block→abstention→threshold）どおり。下記 threshold を使用 |
| entry_probability_thresholds | BUY: p_up ≥ 0.58 / SELL: p_up ≤ 0.42 |
| no_trade_thresholds | 0.42 < p_up < 0.58 → `AUTO_PREVIEW_SIGNAL_HOLD` |
| maximum_expert_disagreement | expert 間確率の最大ペア差 > 0.40 → abstention（HOLD） |
| unknown_regime_and_transition_definition | いずれかの regime 軸が out-of-domain（クリップ超過・欠損）→ `AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED` |
| expected_move_or_magnitude_model | 初期版は**なし**。SL/TP は ATR ベースの執行側規則のみ（magnitude 予測モデルを追加しない） |
| transaction_cost_and_uncertainty_buffer_rule | threshold margin 0.08（0.5±0.08）を摩擦バッファとして固定。加えて model_uncertainty（weight加重 expert 分散）> 0.15 → HOLD |
| allowed_trading_hours | 新規 entry は 9:00〜翌5:00 JST（スプレッド提示時間内）かつ月〜金。**金曜 21:00 JST 以降の新規 entry 禁止**（週末キャリー回避） |
| expected_trade_frequency | 上限 1/日（予算と同値）。想定 2〜4/週 |
| maximum_spread | 通常時スプレッド階級「広」判定時は entry しない（sanitized 階級判定。実数値は API 能力表確定時に凍結） |
| event_exclusion_window | FOMC/BOJ/NFP/US CPI の予定時刻 ±60分は新規 entry 禁止（operator 手動管理カレンダー。外部 fetch なし） |

## 5. リスク・停止・再起動

| 項目 | ドラフト値 |
|---|---|
| position_size | 固定 10,000 通貨（増減・複利なし）。構造上界: size × SL幅 ≤ ¥5,000 を violate する SL は entry 不可 |
| stop_loss_rule | 1.5 × ATR(24)。server-side 付帯可否は API 能力表確定待ち（「無」なら Stage 2 手順側で対応を再設計） |
| take_profit_rule | SL 幅 × 1.5（R:R = 1:1.5） |
| maximum_holding_time | 24時間で強制決済（別 settlement task・官式ルートのみ） |
| model_health_window_and_stop_rule | 直近 20 予測の rolling Brier が 0.30 超（無情報 0.25 比 +20%）→ `BLOCKED` + review window まで停止 |
| restart_rule | boot 時 reconcile-first。BLOCKED 状態は永続化し、operator の review window 承認まで自動解除しない |
| stage1_exit_and_risk_contract | paper 決済は SL/TP/24h timeout の3経路のみ。予算定数（月50,000/日10,000/1トレード5,000/5連敗/1日1回）をコード定数で強制。違反は discipline violation として記録 |
| budget_compatibility_reconfirmation | **確認済み**: H1・最大1/日・per-trade ¥5,000 は日次 ¥10,000・月次 ¥50,000 と整合（月10トレードの余地あり） |

---

## 6. 承認記録

1. operator は 2026-07-11 に本書の全項目を無修正で承認した。
2. `H11_SPEC_FREEZE_STEP` により Status を `FROZEN` に変更し、`config_hash`
   （commit `d7cf8c3` 時点の本書 SHA-256）を発行、preregistration draft と registry を更新した。
3. freeze 後の変更は新 version・新 `config_hash` としてのみ可能（ACTIVE policy §4）。
4. operator は同承認で `STAGE1_PAPER_WIRING_STEP`（モデル実装＋paper 配線、no-POST・
   fake-transport-only）への着手を授権した。Stage 1 の**実稼働開始**は配線・発火テスト完了後の
   operator 確認を別途要する。

本書は live、broker/API、credential、POST のいずれも許可しない。formal test 用 forward データの
取得は別授権 Step を要する。
