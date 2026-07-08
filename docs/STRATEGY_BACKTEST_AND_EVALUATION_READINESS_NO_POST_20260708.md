# Strategy Backtest & Evaluation Readiness — no-POST evidence（2026-07-08）

Step: `STRATEGY_BACKTEST_AND_EVALUATION_READINESS_NO_POST`

関連docs:
[STRATEGY_BACKTEST_DATASET_REQUIREMENTS_NO_POST.md](STRATEGY_BACKTEST_DATASET_REQUIREMENTS_NO_POST.md) /
[STRATEGY_BACKTEST_REPORT_FORMAT_NO_POST.md](STRATEGY_BACKTEST_REPORT_FORMAT_NO_POST.md) /
[STRATEGY_SIGNAL_ENGINE_RULEBOOK_NO_POST.md](STRATEGY_SIGNAL_ENGINE_RULEBOOK_NO_POST.md)

## 1. 到達点

**「実データを投入して検証できる準備が整った」まで**。実データ取得・broker接続・
実POST・real HTTP・credential・`.env`・外部API・webはゼロ。
**synthetic fixture結果はlive性能・収益性の証明ではない
(performance proof status=false / live_ready=false)**。

## 2. 実装（4 modules + 4 test files・標準ライブラリのみ・新規依存なし）

| module | 内容 |
|---|---|
| `gmo_strategy_backtest_dataset.py` | candle/spread/session schema、fail-closed validation(単調timestamp・重複禁止・spread/session全bar必須・非synthetic block)、chronological split + leakage assert、adapter設計(synthetic動作 / CSV・broker export はDATA_ADAPTER_NOT_CONFIGUREDでfail-closed)、決定論的trend fixture builder |
| `gmo_strategy_backtest_engine.py` | 変換境界(candle→safe labels・算術のみ・LLMなし)、既存strategy engineの時系列適用、paper entry/exit skeleton(同時1トレードのみ・retry/duplicateなし)、exit分類(TP/SL/max hold/opposite/end-of-window)、spread cost計上、TP/SL/max hold **candidate** policy(officially_adopted=Trueは構築時例外) |
| `gmo_strategy_backtest_metrics.py` | 21指標のpipeline、最小trade数(30)未満は評価保留、spread excludedはofficial評価block、overfitting status既定=RISK_UNKNOWN_NO_REAL_DATA / OOS_NOT_EVALUATED |
| `gmo_strategy_backtest_report.py` | 14 section固定report、集計のみ(per-bar価格・ID・credentialのfield不存在)、過大表現をrendererが例外で拒否、spread excludedはREFERENCE_ONLY、OOS_EVALUATEDの構築はこのphaseでは例外 |

## 3. synthetic fixture検証結果（tests 58件 green・safe summary）

- uptrend→BUY→TP exit / reversal→SL exit / downtrend→SELL→TP・SL exit
- range→HOLDのみ・トレードなし / trend unknown・conflict→block・トレードなし
- spread wide / ticker stale / market unsafe / session blocked /
  high volatility / guard halt → **entry前block**
- max hold exit / end-of-window exit
- 欠損field・非単調timestamp・重複timestamp・spread欠損 → dataset invalid block
- chronological split: no shuffle・no leakage・OOS温存(違反flagは例外)
- spread included/excluded: cost計上差をreport statusで区別
  (excluded=REFERENCE_ONLY・official不可)
- 60bar+のfixture・複数trade event・raw非露出・過大表現拒否を確認

## 4. 遵守記録

actual/entry/settlement/close POST=false / POST count=0 / broker write=false /
real HTTP=false / runtime private GET=false / credential・env read=false /
real data fetch=false / raw・ID・value露出=false /
AUTO_PREVIEW_SIGNAL_*のoperator signal化なし / RiskPolicy変更なし /
unattended live remains unsupported / unattended full auto completed=false。

## 5. recommended next Step

1. `HISTORICAL_DATA_SOURCE_SELECTION_NO_POST` — データソース選定
   (GMO公式ヒストリカル / public klines のローカルCSV化方針。operator判断)
2. `HISTORICAL_DATA_IMPORT_ADAPTER_NO_POST` — CSV adapter実装
   (local fileのみ・downloadなし)
3. データ投入後: `STRATEGY_BACKTEST_WITH_REAL_DATA_NO_POST`
   (spread込み・chronological split・OOS温存で実行)
