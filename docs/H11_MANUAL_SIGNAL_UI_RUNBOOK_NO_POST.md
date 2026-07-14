# H-11 Manual Signal UI Runbook（local-only / no-POST）

## 起動

```bash
cd /Users/naoikansui/Desktop/トレード/backend
python3 -m scripts.h11_manual_ui
```

ブラウザで次を開く。

```text
http://127.0.0.1:8765/
```

停止は起動Terminalで `Ctrl+C`。常駐サービス、launchd、cronは作成しない。

## 初回

1. 「シグナル」画面を開く。
2. Public tickerが接続され、BID / ASK / spreadとチャートが1秒間隔で描画される。
3. 10分・30分が `判定不可` の場合、初回schedulerがPublic M1 BID cacheを準備し、必要行数を
   満たせば短期model artifactを1回だけ生成する。
4. 自動初期化が失敗した場合だけ「データを更新」を1回押す。
5. 更新失敗時は連打せず、画面の理由を確認して停止する。

24時間は既存H1 cacheとH-11 v2 parameterを使用する。H1の最新barが不足すれば判定不可となる。

## 日常利用

- 10分、30分、24時間、毎秒ローリングの4カードをクリックして主表示を入れ替える。
- 各カード内の小チャートで、そのシグナルの上昇確率推移を確認する。正式3枠は前向きforecast履歴、
  毎秒ローリングは現在の画面session履歴である。
- 価格・価格チャート・独立した「毎秒ローリング」は画面を開いている間1秒更新する。
- 「正式シグナル」は従来どおりM1確定後（毎分+3秒）だけ再計算される。
- 最初の約31分は `M1履歴を併用・蓄積中`、十分な連続sample後は
  `1秒データのみで計算` と表示する。どちらも `非正式・検証前` であり、自動昇格しない。
- チャートは1分・10分・30分・1時間を切り替えられる。
- 実際の対応を `取引した / 見送った / 保留` から記録する。
- 必要なら「注文計算」で手入力計算を行う。計算結果は注文ではない。
- 手動取引を記録した場合は「出口管理」で損切り・利益確定・予測対象時刻を固定し、到達後に
  operator自身が終了理由と価格を記録する。自動決済やbroker照会はない。
- 主画面の「出口シグナル」は手動登録建玉がないとき `建玉なし`。計画開始後は毎秒、
  `継続 / 警戒 / 損切り候補 / 損切り / 利益確定 / 時間切れ / 判定不可` のいずれかを表示する。
- `損切り候補`は保有時間軸の反対正式基準が2回連続した場合だけ。毎秒ローリングの瞬間的な反転や、
  反対正式シグナル1回だけでは発火しない。
- `損切り / 利益確定 / 時間切れ`が表示されても自動決済されない。operatorが実際の手動取引を確認し、
  出口管理から対応する終了理由と価格を記録する。
- 「履歴」と「検証」で予測時点固定・結果確定状況、確率帯・閾値別の診断を確認する。

## ローカルartifact

```text
backend/market_data/h11_manual/usdjpy_m1_bid.csv
backend/market_data/h11_manual/usdjpy_h1_bid.csv
backend/market_data/h11_manual/short_model_artifact.json
backend/market_data/h11_manual/signal_ledger.sqlite3
```

1秒sampleは上記SQLiteの `realtime_tick_samples` tableに保存される。正式forecast tableとは分離され、
raw broker response、ID、credentialは含まない。ブラウザまたはMacを停止していた区間は収集されない。

すべてgitignore対象であり、commit、chat貼付、public deploymentへの同梱を行わない。

## 停止条件

- localhost以外へbindする必要が生じた。
- Private API、credential、broker read/write、注文送信が必要になった。
- model artifact hash不一致、データ不足、非有限特徴量、Public GETエラー。
- Public tickerの最終sampleが15秒を超えて更新されず、出口価格を安全に判定できない。
- 予測値を確認した後に同じartifactを上書き学習する必要が生じた。

これらはUIから回避せず、`判定不可`またはエラーで停止する。

## 毎秒ローリング検証の確認

- 「検証」の「毎秒ローリング検証」で10分・30分を切り替える。
- raw件数は毎秒行であり独立標本数ではない。判断にはhorizon間隔の非重複Nも併用する。
- 対象時刻+15秒以内のBIDだけが解決対象。Mac、server、Public ticker受信の停止で対象時刻を逃した予測は
  `TARGET_PRICE_MISSING`となり、後から補完されない。
- 毎秒推定は `realtime_rolling_forecasts`、結果は `realtime_rolling_resolutions` に保存される。
- 検証収集にはMac、ローカルUI server、シグナル画面のPublic ticker受信が必要。
- 結果から正式シグナルへの自動昇格、閾値変更、出口接続は行われない。

## ワンクリック出口開始

1. 正式10分または30分シグナルを大きく表示する。
2. 方向が買い・売りでPublic価格が15秒以内なら、ボタンが `取引した＋出口開始` に変わる。
3. 1回押すと取引記録と、固定SL 15pips / 固定TP 22.5pips / time exitの出口計画が開始される。
4. 買いはASK、売りはBIDを参考entryに使用する。実約定価格と違う場合はワンクリックを使わず、
   「出口管理」の従来フォームへ実約定価格を入力する。
5. `出口管理中`表示では追加開始しない。終了理由を記録してから次の計画を開始する。

価格が古い、正式シグナルと方向が一致しない、対象時刻経過、OPEN計画ありの場合はfail closedで拒否する。
この操作はローカル記録だけで、broker注文や決済を送信しない。
