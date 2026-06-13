# Safety

## 実資金

`ENABLE_LIVE_TRADING`の既定値は`false`です。ライブ注文要求には以下を検査します。

- 環境変数が`true`
- 管理画面の明示ON
- 確認文言一致
- 最大数量と日次損失設定
- 手動停止機能
- API接続試験
- ログ保存

さらに、このMVPでは実資金ブローカー未実装ガードを必ず追加するため、全条件を
満たしても実資金注文は送信されません。

## デモ注文

- Botの既定状態は停止
- デモ接続試験後に明示的な開始操作が必要
- 注文前に`risk_service.evaluate_order_risk`を必ず実行
- 同一`client_order_id`をDBユニーク制約で拒否
- 最大数量、1回/1日損失、最大ポジション、連敗、スプレッド、重要指標を検査
- 約定処理例外時はBotを`error_stopped`へ変更
- 手動停止後の新規注文を拒否

## OANDA practice自動化

- `OANDA_ENV=practice`かつpractice API URLと完全一致する場合だけアダプターを生成
- 自動売買OFF、Bot停止中、資格情報未設定では注文しない
- 価格と残高を取得できたサイクルだけ戦略判定を行う
- 60秒より古い価格、取引不可価格、換算係数欠落では緊急停止
- 注文は必ず`broker_service.place_order`から`risk_service`を通す
- 損切り・利確をOANDA注文へ同時指定し、損切りなし注文をschemaで拒否
- 最大数量、取引損失、日次損失、ポジション数、連敗、スプレッドを注文前に検査
- 注文応答後にTransaction APIで`ORDER_FILL`を再確認
- 約定後にopenPositionsを再取得できなければ`error_stopped`
- 反対シグナルはreduce-onlyの安全確認後にposition close APIへ送信
- 決済失敗が2回連続した場合は`error_stopped`
- OANDA側SL/TP決済はTradeと決済Transactionを再取得し、純損益を照合
- 決済Trade ID、Transaction ID、確定損益を確認できない場合は成功扱いせず停止
- サイクルを排他実行し、手動サイクルと定期実行の競合による二重注文を防止
- プロセス再起動後は自動復帰せず、再度接続確認と開始操作が必要

## 秘密情報

APIトークンはバックエンド環境変数だけで読み込みます。`.env`はGit対象外です。
トークンをDBや注文ログへ保存する処理はありません。

## ログ

バックテスト、取引、シグナル、注文、エラーはSQLiteの各テーブルへ保存します。
標準のDBファイルはバックエンド起動ディレクトリの`fx_trading.db`です。

## 未完了の安全確認

OANDA通信はMockTransportで試験済みですが、実際のpractice資格情報を使った注文・SL/TP・
決済・通信断試験は未実施です。実資金APIは意図的に未実装です。経済指標カレンダーも
今回の対象外です。
