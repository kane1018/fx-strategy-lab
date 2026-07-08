# Strategy Backtest Report Format（no-POST）

Step: `STRATEGY_BACKTEST_AND_EVALUATION_READINESS_NO_POST`
Date: 2026-07-08
実装: `backend/app/services/gmo_strategy_backtest_report.py`

## 1. Report sections（固定・実装済み）

1. dataset summary(symbol / timeframe / bar count / warmup / synthetic flag)
2. split summary(method=CHRONOLOGICAL_NO_SHUFFLE / train / validation / OOS bar数)
3. strategy configuration(TP/SL/max hold **candidate** profiles・candidate_only固定)
4. signal distribution(safe counts)
5. trade summary(件数)
6. exit reason summary(TP / SL / max hold / opposite / end-of-window counts)
7. spread inclusion status(excludedは**reference only**・official評価不可)
8. metrics summary(status / win_rate / profit_factor / expectancy)
9. drawdown summary(max_drawdown / max_consecutive_losses)
10. guard/block summary(block reason distribution)
11. overfitting checks(status / OOS status / parameter_search_count)
12. limitations(SYNTHETIC_FIXTURE_ONLY_NOT_REAL_DATA_NOT_PERFORMANCE_PROOF)
13. performance proof status(**false固定**)
14. recommended next Step

## 2. Report flags（固定）

actual_post=false / broker_write=false / real_http=false / credential_read=false /
env_read=false / synthetic_fixture_only=true / real_data_used=false /
spread_included=true|false / oos_evaluated=false(本phaseではtrue構築不可・例外)/
performance_proof_status=false / live_ready=false /
operator_confirmation_required=true

## 3. 禁止事項（実装で強制）

- raw broker trade/order/account/position ID・broker response・credential:
  **fieldが構造的に不存在**
- per-bar価格リスト: report surfaceに存在しない(集計のみ)
- 過大表現(profitable / winning strategy / edge proven / performance proven):
  rendererが検出した場合は例外(`GmoBacktestReportError`)

## 4. 評価指標定義（`gmo_strategy_backtest_metrics.py`）

trade_count / win_rate / profit_factor / average_win / average_loss /
expectancy / max_drawdown / max_consecutive_losses / average・median hold /
exposure_time_ratio / spread_cost_ratio / signal_count / HOLD_rate /
UNKNOWN_BLOCKED_rate / guard_block_rate / TP・SL・max hold・opposite・EOW exit counts /
no_trade。

判定原則: **「計算できること」ではなく「データ漏洩なく・spread込みで・
過大解釈なしにreportできること」を合格条件とする**。
- 最小trade数(30)未満 → `EVALUATION_WITHHELD_INSUFFICIENT_TRADES`
- spread excluded → `METRICS_BLOCKED_SPREAD_EXCLUDED`(official評価不可)
- 既定 overfitting status: `OVERFITTING_RISK_UNKNOWN_NO_REAL_DATA` /
  `OOS_NOT_EVALUATED`

## 5. spread込み評価方針

- spread included evaluationは**必須**。excludedは参考のみ
- spread欠損・不明はdataset invalid / engine blockでfail-closed
- entry時にspread costを計上する設計(synthetic実装済み。実データでは
  bid/ask由来のside別costへ拡張)
- **spread込みで崩れる戦略はlive検討不可**。短期売買ほどspread影響が大きい
- RiskPolicy(max_spread_pips=0.5等)は変更しない

## 6. TP/SL/max hold候補policy（candidate-only）

TAKE_PROFIT_PROFILE_SMALL/MEDIUM/LARGE、STOP_LOSS_PROFILE_SMALL/MEDIUM/LARGE、
MAX_HOLD_PROFILE_SHORT/MEDIUM/LONG、EXIT_ON_OPPOSITE_SIGNAL、
EXIT_ON_END_OF_WINDOW。数値はsynthetic test-onlyで、
`officially_adopted=True` は**構築時例外で拒否**。
**採用決定には実データbacktest + OOS評価 + operator判断が必須**で、
live適用には別Stepが必要。max loss guard(監視側)とは別概念。
settlement route・live settlement permissionとは無関係。

## 7. overfitting防止ルール

- 未来データ不使用(chronological split + leakage assert)
- OOSは最終確認まで不使用・最適化利用禁止(flagで例外)
- parameter探索回数をreportに記録(`parameter_search_count`)
- 最小trade数未満は評価保留 / 低trade数の高PFを過信しない
- validationで良くてもOOSで崩れたら不採用 / OOS悪化時はliveに進まない
- ルール変更はbatch単位(1回の勝敗で変更しない)
- 複数候補比較では選択バイアスを明記
- performance claimは実データ・OOS・paper forward後まで禁止
- live移行にはoperator判断が必要
