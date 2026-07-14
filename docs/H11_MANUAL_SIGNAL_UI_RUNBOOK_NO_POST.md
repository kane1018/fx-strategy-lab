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
- ユーザーが押す記録操作は正式10分・30分カード内の `取引開始`だけ。押さなかったforecastは満期後に
  `NO_ACTION（取引開始記録なし）`として自動記録されるため、見送り・保留操作は不要。
- 必要なら独立した「注文計算」で、正式方向とPublic価格の自動入力、許容損失額からの数量逆算を行う。
  シグナル画面からの直接導線はなく、計算結果も注文ではない。
- 手動取引を記録した場合は、その10分・30分カード内で損切り・利益確定・予測対象時刻を確認する。
  brokerの手動OPEN/CLOSEはGET-only同期され、実約定価格・数量・部分決済・全決済をカードへ反映する。
  独立した出口管理画面、自動決済、broker writeはない。
- 各カードの「出口シグナル」は対応する手動登録建玉がないとき `建玉なし`。計画開始後は毎秒、
  `継続 / 警戒 / 損切り候補 / 損切り / 利益確定 / 時間切れ / 判定不可` のいずれかを表示する。
- `損切り候補`は保有時間軸の反対正式基準が2回連続した場合だけ。毎秒ローリングの瞬間的な反転や、
  反対正式シグナル1回だけでは発火しない。
- `損切り / 利益確定 / 時間切れ`が表示されても自動決済されない。operatorがbroker側で手動決済すると、
  CLOSE約定をread-only同期してlocal計画を終了する。
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
- 許可済み2 endpoint以外のPrivate API、broker write、注文送信が必要になった。
- model artifact hash不一致、データ不足、非有限特徴量、Public GETエラー。
- Public tickerの最終sampleが15秒を超えて更新されず、出口価格を安全に判定できない。
- Broker同期が `AMBIGUOUS_OPEN / RECHECK_REQUIRED / ERROR` になった。
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

1. 正式10分または30分カード内の取引開始ボタンを確認する。大きく表示していないサブカードからも開始できる。
2. Stay時は `取引開始（Stay）`、Unknownは `取引開始（判定待ち）`、価格条件不足は
   `取引開始（価格待ち）`として表示されるが押せない。方向がBuy・SellでPublic価格が15秒以内なら、
   `Buyで取引開始`または`Sellで取引開始`として押せる。
3. 1回押すと取引記録と、固定SL 15pips / 固定TP 22.5pips / time exitの出口計画が開始される。
   画面はシグナルのまま維持され、開始したカード内が監視表示へ切り替わる。
4. 買いはASK、売りはBIDを参考entryに使用する。実約定価格と数量は、OPEN約定が一意に照合できた時点で
   Private GETの値へ自動補正される。
5. 開始カードは `出口シグナル稼働中 / OPEN約定待ち`となる。10分・30分は各1件まで独立して開始できるが、
   同じ時間軸の二重開始は拒否される。画面上部はlocal `管理中` とPrivate GETの `Broker` 件数を分ける。
   24時間と毎秒ローリングは常に取引・出口対象外である。

価格が古い、正式シグナルと方向が一致しない、対象時刻経過、OPEN計画ありの場合はfail closedで拒否する。
条件不足時はカード内ボタンを無効化し、出口計画なしの取引記録や出口管理への自動遷移を行わない。
この操作はローカル記録だけで、broker注文や決済を送信しない。

## 手動OPEN/CLOSEのread-only同期

1. 専用read-only API credentialをmacOS Keychainへ登録し、local serverを再起動する。
2. 上部が `同期 <時刻>` になり、`Broker` 件数が数値になることを確認する。未設定・エラー時は
   `取引開始` がdisabledになる。
3. `取引開始`後にbrokerで手動OPENすると、カードが `OPEN約定待ち` から `OPEN照合済み`へ変わり、
   実約定価格・数量が自動反映される。
4. 部分決済は `部分決済` と残数量を表示する。全数量のCLOSE約定を確認したときだけlocal計画を閉じる。
5. `OPEN照合不明 / 同期要確認` は推測で解決せず停止する。broker画面とlocal履歴を確認する。

poll対象は `GET latestExecutions` と `GET openPositions` だけである。注文、取消、変更、決済、ws-authの
POST/PUT/DELETEは実装していない。Private WebSocketも使用しない。

## Keychain設定

GMO側で注文権限を無効化したread-only専用credentialを別途発行する。Keychain Access.appから
「新規パスワード項目」を2件作り、次のservice / accountだけを一致させる。値はchat、Terminal、docs、
`.env`へ貼らない。

```text
service: fx-strategy-lab-h11-manual-readonly
account: gmo-fx-api-key

service: fx-strategy-lab-h11-manual-readonly
account: gmo-fx-api-secret
```

local serverは初回service生成時だけKeychainを読む。追加・変更後はserverを再起動する。コードから
credentialのread-only権限そのものは証明できないため、GMO管理画面で注文権限が無効であることをoperatorが
確認する。Keychain値、長さ、hash、prefix/suffixは表示・ログ出力しない。
