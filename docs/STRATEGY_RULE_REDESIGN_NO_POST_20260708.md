# Strategy Rule Redesign（no-POST・2026-07-08）

Step: `STRATEGY_RULE_REDESIGN_NO_POST`
実装: `backend/app/services/gmo_strategy_redesign.py`

**重要: aggregate/sign-onlyの探索であり、performance proofではない
（performance_proof_status=false / live_ready=false）。raw price/spread/PnLは扱わない。
OOSは freeze後1回のみ使用し、OOS結果を見た後の再調整はしていない。**

## 1. no-POST安全境界

実POST / broker write / real HTTP / download / public kline export再実行 /
private API / runtime private GET / credential / env read はゼロ。
operator提供 local CSV を read-only 再利用。deterministic signal engine
（rulebook）は**無変更**。redesignは backtest-only の別runnerで実施。

## 2. baseline failure summary（前Step)

trade 3,196 / PF≈0.83 / expectancy NEGATIVE / win≈0.29 / opposite exit 3,168 /
TP 22・SL 6・max_hold 0 / max_consec_losses 23。主因: 即時opposite-signal exit依存 +
過大な固定TP/SL（M5に対し数十pips）でTP/SLが機能せず、spread込みで edge が消失。

## 3. redesign requirements

spread込み成立 / entry頻度低下 / 弱いtrend/momentum entry削減 / opposite即時exit依存の
低減 / TP・SL・max holdを実際に効かせる / max_consec_lossesを悪化させない / HOLD・
UNKNOWN_BLOCKED適正増 / session・spreadを尊重 / deterministic・safe-label-only /
actual flags false / preview非permission / operator signalではない。

## 4. candidate families（<=4・candidate-only）

- **TREND_CONTINUATION**: SMA-trendとmomentum厳密一致時のみentry
- **BREAKOUT**: 直近N barのhigh/low を close がbreakした時のみentry（trend逆行時は除外）
- **MEAN_REVERSION_RANGE**: RANGE regime かつ ATR基準の overextension 時のみ逆張り
- **DUAL_CONFIRMATION**: trend と breakout が一致時のみentry

各familyに **ATR相対exit** 2種（EXIT_TIGHT: TP=1.0×ATR/SL=1.0×ATR/max_hold12/debounce2、
EXIT_RIDE: TP=2.5×ATR/SL=1.0×ATR/max_hold48/debounce3）。
= 8 candidates。固定TP/SLの主因を ATR相対で解消。

## 5. implementation summary

- 算術feature converter（SMA-trend / momentum / breakout / mean-reversion
  overextension / ATR）。**safe labelのみ出力、ATRは内部でexit距離算定にのみ使用、
  raw値は非露出**
- backtest-only redesign runner（独自loop・同時1トレード・retryなし・
  `BacktestRunResult` を返し既存metrics/reportを再利用）
- chronological split（redesign用40 bar indicator lead-in＝warmupのみ・leakageなし）
- 候補比較・freeze・OOS 1回。`officially_adopted=True` は構築時例外で拒否

## 6. train/validation comparison（validation・aggregate/sign only）

- baseline validation: PF 0.545 / maxcl 19 / expectancy NEGATIVE
- parameter_search_count: 8 / selected_using: TRAIN_VALIDATION_ONLY /
  oos_not_seen_before_freeze: true

主な validation 結果:
- MEAN_REVERSION_RANGE__EXIT_RIDE_ATR: trades 170 / **PF 1.107** /
  **expectancy POSITIVE** / maxcl 10（<baseline 19）← 選定基準を満たす唯一の候補
- MEAN_REVERSION_RANGE__EXIT_TIGHT: PF 0.787 / TREND_CONTINUATION系 PF 0.65–0.67 /
  BREAKOUT系 PF 0.56–0.60 / DUAL_CONFIRMATION系 PF 0.34–0.52（全てPF<1・expectancy NEGATIVE）

## 7. candidate freeze

- freeze: **MEAN_REVERSION_RANGE__EXIT_RIDE_ATR**
  （validation PF>1.0・expectancy非negative・maxcl<=baseline・trade数十分）
- selection_reason: VALIDATION_PROFIT_FACTOR_ABOVE_ONE_WITHOUT_WORSE_RISK
- **OOSは freeze後に初めて確認**

## 8. OOS one-time evaluation

- 結果: **OOS_DEGRADED_REJECT_CANDIDATE**
- OOS: trades 164 / PF 0.643 / expectancy NEGATIVE / maxcl 11
- OOS exit分布: SL 119 / TP 37 / opposite 6 / max_hold 2
  （**ATR相対exitが実際に機能**＝baselineの opposite依存3,168からの構造改善。
  ただしnetでは edge が続かず）
- **OOSを見た後の再調整はしていない**

## 9. limitations / overfitting controls

- validationで良好でもOOSで崩れる典型（selection→freeze→OOSのガードが正しく機能）
- 単一3ヶ月sample・単一symbol/timeframe・bar-level spread近似
- feature/exitパラメータは固定既定（無制限探索なし・count=8記録）
- overfitting_status: single-sample real-data（保守）

## 10. 判定・next Step

- CASE: **STRATEGY_RULE_REDESIGN_OOS_REJECTED_NO_POST**
- 結論: ATR相対exitで exit構造は改善したが、OOSで持続する edge は確認できず。
  validation上の優位性はperiod artifactの可能性が高い。
- recommended next Step: **STRATEGY_HYPOTHESIS_REBUILD_NO_POST**
  （仮説の再構築）または `EXPAND_HISTORICAL_DATA_RANGE_OR_TIMEFRAME_NO_POST`
  （より長期・複数期間・別時間足での再評価）。
- live移行は不可（performance未証明・OOS reject・paper forward未実施・operator判断要）。

report詳細: [STRATEGY_RULE_REDESIGN_REPORT_NO_POST_20260708.md](STRATEGY_RULE_REDESIGN_REPORT_NO_POST_20260708.md)
