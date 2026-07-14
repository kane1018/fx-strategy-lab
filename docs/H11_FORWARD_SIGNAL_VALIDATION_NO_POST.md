# H-11 Forward Signal Validation Contract（no-POST）

Status: `ACTIVE_FOR_LOCAL_SIGNAL_SCOREKEEPING`

## 評価対象

方向確率そのものを評価し、実売買損益と混同しない。10分、30分、24時間は別horizonとして
分離し、主指標はBrier score、確認指標はLog lossとする。方向精度は補助指標に留める。

`見送り`を都合よく除外せず、記録された全確率予測を同じ分母で採点する。`判定不可`は確率予測が
成立していないため台帳へforecastとして保存しない。

## 時点固定

forecast keyは `horizon + origin_time_utc + model_config_hash` から決定し、同じ予測を重複登録しない。
結果は対象horizonの将来barが到着した後に別tableへappendする。既存forecastの確率、方向、理由、
config hashは更新しない。

起動が遅く対象horizonの結果が既に存在する予測は `REPLAYED_AFTER_MATURITY`、結果到着前に記録した
予測は `PROSPECTIVE` と明示する。この2つを同じ意味のforward evidenceとして扱わない。

## 現時点の意味

UIの検証画面は `FORWARD_SIGNAL_SCORE_ONLY_NOT_EDGE_VALIDATION` である。resolved n、Brier、Log loss、
方向精度の蓄積は比較材料だが、`VALIDATED`、`LIVE_READY`、収益性、将来利益を意味しない。

Tradable edgeを評価する場合は、別versionでbid/ask、spread、slippage、entry/exit rule、coverageを
事前固定する。手動売買の結果だけから予測モデルを場当たり的に再学習しない。

## 確率帯・閾値診断

検証画面は `PROSPECTIVE` の確定結果だけを対象に、5 percentage-pointの予測確率帯ごとに
平均予測確率、実現上昇率、calibration gapを表示する。さらに買い/売り対称閾値
52/48、54/46、56/44、58/42、60/40、62/38、65/35についてcoverageと方向精度を比較する。

各horizonのraw全件に加え、10分・30分・24時間ごとにlabel overlapを避ける簡易decimationを行った
non-overlapping件数・精度・Wilson 95%区間を併記する。これは軽量診断であり、独立性や頑健性の証明ではない。
現行58/42は `SHORT_V1_FIXED_58_42` のまま固定し、画面結果から自動変更しない。変更候補は新versionとして
別の事前登録・未閲覧期間・operator承認を必要とする。

手動出口計画と損益履歴は、方向確率のBrier / Log loss scoreから分離する。entry、stop、take、
手動終了理由は売買運用の記録であり、forecastを採点する分母の選別や閾値の事後調整には使わない。

保有建玉向け出口シグナルもforecast scoreから分離する。モデル由来の `警戒 / 損切り候補` は、
正式予測の別用途への事前固定mappingであり、予測自体の正解labelではない。反対正式基準2回連続という
確認条件、固定SL / TP / time exitの優先順位を結果確認後に場当たり的に変更しない。出口成績を評価する
場合はentry・exit・costを固定した別のTradable Edge contractを必要とする。

## 毎秒リアルタイム推定の分離

`M1_BOOTSTRAP_ROLLING_60S` と `TICK_NATIVE_ROLLING_60S` は、現時点では
`REALTIME_ESTIMATE_NOT_FORMAL` である。既存の毎分forecast key、正式台帳、上記scoreへ混入させない。
UIでは4つ目の独立カードとして表示し、確率チャートは現在のbrowser sessionだけを保持する。
保存する1秒Public ticker sampleから後日再現・label生成できるが、強いoverlapを持つため、raw秒数を
独立標本数として扱わない。別の凍結validation contractとoperator承認なしに正式シグナルへ昇格しない。

## 毎秒ローリング検証（別台帳）

10分・30分の各推定を1秒ごとに `realtime_rolling_forecasts` へ保存し、正式forecast tableとは
物理的に分離する。origin時点のPublic BIDと、originから正確に10分または30分後のPublic BIDを比較する。
対象時刻から15秒以内に観測したBIDだけをlabelに採用し、15秒を超えてから再開した場合は
`TARGET_PRICE_MISSING`として不可逆に確定する。後から取得できた都合のよい価格で補完しない。

検証画面はhorizon別にforecast数、resolved数、対象価格欠測数、解決coverage、Brier、Log loss、
方向精度、確率帯、閾値診断を表示する。rawの毎秒行は独立標本ではないため、horizon間隔で抽出した
non-overlapping指標を併記する。これは簡易診断であり、purge / embargoを含む正式検証ではない。
推定mode別件数も保持し、M1併用期間と1秒native期間の混在を隠さない。

結果が良くても、正式シグナルへの自動昇格、閾値自動変更、出口シグナルへの接続は行わない。
昇格には別versionの凍結contract、欠損・flicker・mode分離を含む正式評価、operator承認を必要とする。
