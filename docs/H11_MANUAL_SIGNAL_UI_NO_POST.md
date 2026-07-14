# H-11 Manual Signal UI（local-only / no-POST）

Status: `IMPLEMENTED_LOCAL_ONLY`

## 1. 目的

H-11を自動売買へ接続せず、ユーザーが短期売買の参考にする方向確率を、直感的な
デスクトップ画面で表示する。画面名は **「シグナル」** とし、旧案の「今の判断」は使用しない。

本UIは売買注文を作成・送信せず、broker、Private API、credential、envを扱わない。

## 2. 表示時間軸

- `10分`: 新しいM1低容量logisticモデル。初期選択として大きく表示。
- `30分`: 同じM1特徴量契約を使う別horizonモデル。
- `24時間`: 既存H-11 v2 TREND単独expertを、H1の長期方向コンテキストとして維持。
- `毎秒ローリング`: 10分方向を直近60秒のPublic tickerから毎秒再推定する、非正式・検証前の独立表示。

大きなカードは常に1枚で、残り3シグナルを右側の小カードに表示する。小カードをクリックすると
4つのどれでも大きなカードと入れ替わる。方向表示は `買い / 売り / 見送り / 判定不可` の4種類とする。
毎秒ローリングはformal forecastではなく、正式な10分シグナルとも別の表示・記録種別である。

各カード内にそのシグナル自身の `p_up` 履歴チャートを表示する。10分・30分・24時間は
`PROSPECTIVE` forecast台帳から最大120点を読む。毎秒ローリングは画面を開いている現在sessionの
最大120点だけを描画し、正式forecast tableへ保存しない。チャートの58%・50%・42%線は表示補助で、
履歴を見た後に閾値を自動変更しない。

```text
買い     p_up >= 0.58
売り     p_up <= 0.42
見送り   0.42 < p_up < 0.58
判定不可 モデル・データ・特徴量のいずれかが不成立
```

## 3. 短期モデル

短期モデルはM1 BID candleだけを使用し、時刻tまでの情報から10本後・30本後の方向確率を別々に
推定する。低容量のL2 logistic regressionであり、初回データ準備時に時系列の先頭70%だけで
学習する。最大horizon分をpurgeし、生成したartifactはlocal-onlyで凍結する。

初回学習後に画面のデータ更新を行っても再学習しない。artifactの削除・置換やmodel version変更は、
別研究versionとして明示的に扱う。

短期モデルの結果はedge証明ではない。未初期化時に仮の確率やモック方向を表示せず、
`判定不可`へfail closedする。

## 4. データと記録

- Market data: GMO外国為替FX Public `GET /v1/klines` のBID candleのみ。
- Live quote: GMO外国為替FX Public WebSocket tickerのBID / ASK。認証・API keyなし。
- 価格・チャート描画: 画面を開いている間、受信済みlatest tickを1秒間隔で描画。
- 正式シグナル更新: 毎分の境界から3秒後にPublic M1確定足を更新し、10分・30分を再計算。
- リアルタイム推定: latest Public tickerをlocalhost内で1秒に1サンプルへ正規化し、直近60秒を
  ローリング足として10分・30分を毎秒再推定する。正式シグナル、正式forecast台帳、24時間モデルは
  変更しない。
- 蓄積初期（約31分未満）は凍結M1履歴と直近60秒を併用する
  `M1_BOOTSTRAP_ROLLING_60S`、31個の十分に密な60秒窓が揃った後は1秒サンプルだけの
  `TICK_NATIVE_ROLLING_60S` と表示する。どちらも非正式・検証前である。
- 24時間シグナル: 新しいcompleted H1を取得したときに再計算（同一H1は重複登録しない）。
- 手動更新: 「データを更新」は初期化・復旧用。通常は毎分schedulerが自動更新する。
- 常駐: browser pageと手動起動local serverの稼働中だけ。launchd / cron / OS常駐なし。
- 保存先: `backend/market_data/h11_manual/`（gitignore済み、commit禁止）。
- 台帳: `signal_ledger.sqlite3`。正式予測、結果、ユーザーの `取引した / 見送った / 保留` と、
  1秒Public ticker sampleを別tableに分離して記録。リアルタイム推定は正式forecast tableへ記録しない。
- 出口計画: 10分・30分の正式forecastを根拠に、operatorが入力したentry / stop / take / time exitを
  local tableへ記録する。到達表示と手動終了記録だけで、自動決済・broker建玉確認は行わない。
- raw response、credential、broker ID、注文情報は保存しない。

Public GETはread-onlyで認証不要だが、レート制限へ配慮して日付単位の要求間に0.15秒を置く。
エラー時の自動retryは行わない。

Public WebSocketは1接続・1回のsubscribeを使用し、価格変動messageを受信する。切断時の再接続は
5〜30秒のbounded backoffとし、注文POSTのretry/repostとは無関係なPublic read-only再接続である。

## 5. UI面

初期approved mock（実装版はこの構成にリアルタイムチャートを追加）:

![H-11 manual signal UI](assets/h11_manual_signal_ui_desktop.png)

主画面に売買判断へ必要な情報を集約し、研究指標は「検証」へ分離する。

- シグナル: 正式3時間軸と毎秒ローリングの4枠。方向・確率・理由・観測時刻・確率履歴を表示。
- 毎秒ローリング: 独立カードとして10分方向の毎秒確率と蓄積modeを明示。
- リアルタイムチャート: 実BID candle、live BID / ASK、spread、1分・10分・30分・1時間切替。
- 履歴: 固定済み予測と結果。
- 注文計算: 手入力条件によるSL/TP・損益目安。注文送信なし。
- 出口管理: 固定した損切り・利益確定・予測対象時刻の到達確認と手動終了記録。自動決済なし。
- 手動記録: ユーザー選択の履歴。
- 検証: Brier / Log loss / 方向精度 / resolved nに加え、確率帯別実現率と閾値別診断。

デスクトップ幅では、左に価格チャート、右に4シグナル（大1＋右側の小3）を同じdashboard rowで配置し、
標準的な画面高ではスクロールせずに同時確認できる。狭い画面では可読性を優先して縦積みに戻す。

## 5.1 保有建玉を前提とした出口シグナル

broker建玉は参照しない。「出口管理」でoperatorが開始したOPENの手動出口計画だけを保有状態として扱い、
主画面と出口管理画面の両方へ次の優先順位で出口シグナルを表示する。

```text
1. 固定損切り価格到達                    -> 損切り
2. 固定利益確定価格到達                  -> 利益確定
3. 事前固定した予測対象時刻到達          -> 時間切れ
4. 15秒以内のPublic価格を確認できない     -> 判定不可
5. 反対方向の正式基準を2回連続で満たす    -> 損切り候補
6. 正式確率が50%中立線を不利側へ越える    -> 警戒
7. 上記以外                              -> 継続
```

買い建玉の反対方向正式基準は `p_up <= 0.42`、売り建玉は `p_up >= 0.58`。10分建玉は10分正式予測、
30分建玉は30分正式予測だけを使用し、毎秒ローリングは出口モデル判定へ使用しない。
`損切り候補`を含むすべての表示はoperator向け情報であり、自動決済、注文命令、broker状態確認ではない。
固定SL / TP / time exitをモデルより優先し、反対シグナル1回だけで損切り候補へ切り替えない。

## 5.2 正式な毎秒シグナルへの昇格条件

現在のリアルタイム推定は自動昇格しない。少なくとも次を別Stepで満たし、operatorが明示承認した後に
新versionとして扱う。

- 十分な期間の1秒sampleが保存され、欠損・停止・再接続区間を識別できる。
- 10分・30分の将来labelを1秒時点ごとに作り、強いoverlapを考慮したpurge / embargoで評価する。
- 現行の毎分正式シグナル、単純baselineとの比較、Brier / Log loss / calibrationを凍結条件で行う。
- 1秒ごとのsignal flicker、coverage、データ遅延時のfail-closed条件を事前固定する。
- 正式forecast ledger、UI名称、validation contractを別versionとしてレビューする。

## 6. 安全境界

専用entrypoint `app.main_h11_manual:app` を使い、`app.main`、`app.main_readonly`、broker、
`app.live_verification`、H-11 v3 transportをimportしない。hostはlocalhostだけを許可し、
launcherも `127.0.0.1` に固定する。

```text
actual_post=false
broker_read=false
broker_write=false
private_api=false
credential_read=false
env_read=false
automatic_trade_authority=false
```

このUIをpublic deploymentへ追加してはならない。`backend/app/main_readonly.py`は変更しない。

## 7. 毎秒ローリング検証UI（2026-07-15追加）

検証画面に「毎秒ローリング検証」を正式検証と分けて表示する。10分・30分を切り替え、raw件数、
horizon間隔の非重複N、対象価格欠測、解決coverage、Brier / Log loss / calibration / 閾値診断、
推定mode内訳を確認できる。

毎秒推定は別tableへ保存し、10分・30分後の対象BIDを15秒以内に観測できた場合だけ解決する。
超過時は `TARGET_PRICE_MISSING` に固定する。この表示は正式化条件の材料を集めるだけで、正式シグナル、
出口シグナル、売買権限、閾値を変更しない。

## 8. ワンクリック出口開始（2026-07-15追加）

選択中の正式10分・30分シグナルが `買い` または `売り` で、15秒以内のPublic tickerを確認できる場合、
主画面の `取引した＋出口開始` 1回で取引記録とローカル出口計画を開始する。買いは最新ASK、売りは
最新BIDを参考entryとして使用し、既存presetの固定SL 15pips、固定TP 22.5pips、予測対象時刻の
time exitを設定する。二重クリック中はボタンを無効化し、OPEN計画は同時に1件だけとする。

これはbroker約定確認ではなく、Public価格を使った迅速な参考設定である。実約定価格が異なる、価格が
15秒超、見送り・判定不可、24時間、毎秒ローリングの場合はワンクリック開始せず、従来の出口フォームで
実約定価格を確認して開始する。broker read/write、自動決済、注文送信は行わない。
