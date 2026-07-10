# H-11 Development Training Record（operator授権 public GET・no-POST）

Date: 2026-07-11
Applies to: `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY`
config_hash: `sha256:7bff1ee4b8427a67111f289211bca5d654f1ae38bc3670bd1592a3ba9790e4a1`
Scope: **DEVELOPMENT_VALIDATION_ONLY — formal test ではなく edge 証拠でもない**

```text
actual_post=false / entry_post=false / settlement_post=false / post_count=0
broker_read=false / broker_write=false / private_api=false / credential_read=false
public_get=true(operator授権 2026-07-11・klines READ のみ)
performance_proof_status=false / live_ready=false / unattended_live_supported=false
```

## 1. 授権記録

- operator は 2026-07-11 に development データ取得のための **public GET（GMO Public API
  klines・無認証・read-only）** を授権した。注文系・Private API・credential は対象外。
- 取得スクリプト: `backend/scripts/h11_train_development.py`（日次イテレーション・
  礼儀的 sleep・休場日 skip）。
- 生データは `backend/market_data/`（**gitignore 済み・コミット禁止**）にのみ保存。
  リポジトリ・doc への raw price 記載なし（本書は safe aggregate のみ）。

## 2. データと手続き（凍結仕様どおり）

- USD/JPY H1 BID、2024-01-01 〜 2026-07-10 JST 終了（**freeze cutoff 2026-07-11 00:00 JST
  以降のバーは除外**。forward formal test 期間は未接触のまま）。
- development bars: 15,578（取得 655 営業日・休場 267 日）
- 時系列 70/30 分割・purge 24 バー・embargo 24 バー。学習は training 区間のみ。
- 学習: 3 expert L2 ロジスティック → 線形 softmax router（決定論・固定 iteration）。
- 学習済みパラメータ: `backend/app/strategies/h11_parameters_v1.json`（safe aggregate、
  config_hash 刻印済み）。

## 3. Validation 結果（safe aggregate・development のみ）

| 指標 | 値 |
|---|---|
| validation_rows_scored | 4,624（coverage 1.0） |
| Brier MoE | 0.241212 |
| Brier equal-weight | 0.241293 |
| Brier baseline (p=0.5) | 0.25 |
| Brier expert TREND 単独 | 0.240766 |
| Brier expert MEAN_REV 単独 | 0.241340 |
| Brier expert BREAKOUT 単独 | 0.242383 |
| Log loss MoE / equal-weight | 0.675517 / 0.675681 |

## 4. 誠実な読み（scorekeeper 判定・development 段階）

1. **MoE の equal-weight に対する改善は +0.03%（相対）** — 凍結済み支持基準
   「**1% 以上の相対改善**」に対し **約30分の1** であり、development validation の時点で
   主仮説（router の追加予測力）を**支持する兆候は出ていない**。
2. 単独 TREND expert（0.240766）が MoE（0.241212）より**良い** — router の重み付けは
   development 区間では価値を追加していない。
3. 全モデルとも baseline 0.25 に対する改善は 3〜4% 程度であり、これは方向確率の
   クラス基準率への calibration でほぼ説明可能な水準。
4. 本結果は formal test ではない（formal test は forward 期間・未収集・1回限り）。
   ただし ACTIVE policy の誠実採点原則に基づき、この development 結果を弱めずに記録する。
5. **禁止事項の確認**: 本結果を見た後の feature / expert / threshold / hyperparameter
   変更は、同一 `config_hash` では**行わない**（変更は新 version・新 config_hash のみ）。

## 5. 次の停止点

- 配線（Stage 1 paper wiring）は技術的には継続可能。ただし operator は上記 §4 を踏まえ、
  (a) このまま Stage 1 配線・paper 稼働へ進む、(b) H-11 を諦め新 version / 別仮説を検討する、
  のいずれかを判断できる。本書はどちらも先取りしない。
- formal test（forward・1回限り）の収集・実行は別授権のまま。
