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

## 市場開始後の practice E2E 手順（runbook）

実資金は対象外です。live注文は実行しません。FXは週末休場のため、平日の市場稼働時間中
（おおむね日本時間で月曜早朝〜土曜早朝）に実施します。すべての注文は必ず
`broker_service.place_order` → `risk_service`（RiskManager）を通ります。

補助スクリプト: `backend/scripts/practice_e2e.py`（practice専用。live broker は生成しない）。

### 0. 実行前チェック
- `OANDA_ENV=practice` / `ENABLE_LIVE_TRADING=false` を確認
- `.env` がGit追跡対象外（`git status` に現れない）であることを確認
- APIキーは画面・ログ・チャットに出さない（スクリプトは秘密情報を出力しません）

### 1. `.env` 設定
```bash
cp .env.example .env
# .env を編集し、practice の値を設定（live は使用しない）:
#   OANDA_API_TOKEN=<practiceトークン>
#   OANDA_ACCOUNT_ID=<practice口座ID>
#   OANDA_ENV=practice
#   OANDA_API_URL=https://api-fxpractice.oanda.com
#   ENABLE_LIVE_TRADING=false
#   AUTO_TRADE_DEFAULT_ENABLED=false
```

### 2. 起動 / 事前確認（読み取り専用）
```bash
cd backend
.venv/bin/python -m scripts.practice_e2e preflight --symbol USD_JPY
```
このコマンドで以下を確認します:
- account summary 取得 / 残高・通貨・建玉数
- 直近ローソク足（M5×5）取得
- 既存ポジション取得
- 価格取得・スプレッド・価格鮮度
- `tradeable` 判定（休場時は `NOT_TRADEABLE` と表示し、注文へ進みません）
- 末尾の VERDICT が `READY` のときのみ次へ進む

（API経由で確認したい場合: `POST /api/broker/connection-test?mode=practice` → ok:true、
`POST /api/automation/start` は監視スレッドを伴うため、単発E2Eではスクリプトを推奨）

### 3. 小数量 practice 注文（SL/TP付き・1〜10 units）
```bash
.venv/bin/python -m scripts.practice_e2e order --symbol USD_JPY --units 1 --side buy --confirm
```
- `--confirm` 必須。`tradeable` でなければ自動的に中止
- SL/TP は自動付与（既定 SL20 / TP40 pips、`--stop-pips` / `--tp-pips` で調整可）
- RiskManager 通過時のみ発注。注文IDと約定結果を表示

### 4. 約定照合 / ポジション確認
```bash
.venv/bin/python -m scripts.practice_e2e status
```
- 直近 OrderLog の `status=filled` / 約定価格 / 注文ID を確認
- 約定が確認できない場合は成功扱いせず Bot は停止します

### 5. 決済 / 確定損益
```bash
.venv/bin/python -m scripts.practice_e2e close --symbol USD_JPY --confirm
```
- ポジションを決済し、確定損益（realized PnL）を OrderLog に照合保存
- 決済失敗時は成功扱いせず、ErrorLog 保存・Bot停止
- 完了後 `status` で確定損益を確認し、**OANDA practice 画面の取引履歴／残高と突合**

### 6. 異常時の停止確認
- 価格鮮度切れ・スプレッド超過・約定/決済確認失敗・429/timeout/通信断 →
  Bot は `error_stopped` / `risk_stopped` になり、停止理由は BotLog / ErrorLog と
  `GET /api/automation/status` で確認できます

### 7. 実行後に確認するログ
- `OrderLog`: 注文ID・約定価格・確定損益・risk_check_json
- `BotLog`: 状態遷移と停止理由
- `ErrorLog`: 失敗内容（Authorization ヘッダや token は含まれません）

### 注意
- APIキー・Authorization ヘッダは決して出力しない（コード上も非出力）
- `OANDA_ENV=practice` 以外、または `tradeable=false` のときは注文しない
- 長時間の無人稼働はしない。1回ずつ結果を確認する

## GMO コイン外国為替FX 対応方針（段階導入）

OANDA REST の条件が重いため、GMO コイン外国為替FX API を追加 broker 候補として段階導入します。
**重要: GMO 外国為替FX にはデモ/practice 環境が無く、API は本番（実資金）のみ**です。30日間の
無料トライアルは「API経由注文の手数料無料」であって、デモ取引ではありません。よって実注文は
明示許可のある後続フェーズまで無効に保ちます。

- 認証（Private 用・本フェーズ未使用）: ヘッダ `API-KEY` / `API-TIMESTAMP` / `API-SIGN`。
  署名は `timestamp + method + path + body` を APIシークレットで HMAC-SHA256。
  **APIキー・シークレット・署名文字列はログ・画面・チャット・Git に出さない。**
- Public 応答エンベロープ: `{"status":0,"data":...}`。`status!=0` は `messages[].message_code`
  （例 `ERR-5003`=レート制限）。HTTP 429 とあわせて失敗扱いで停止します。
- レート制限: Public/Private WS は 1req/秒/IP、Private GET 6req/秒、Private POST 1req/秒（口座毎）。
- 最小注文数量: `GET /public/v1/symbols` の `minOpenOrderSize` が正。主要ペア（USD_JPY 等）は
  1通貨から可能（一部エキゾチックは 10/100/100,000 通貨）。**実注文前に必ず symbols で検証**。

### フェーズ
- **G1（実装済み）Public read-only**: `GmoFxBroker`（`app/brokers/gmo_fx_broker.py`）。
  `service_status` / `current_price`（ticker）/ `candles`（klines）/ スプレッド算出 /
  symbol 正規化 / timeout / 429・エラーエンベロープ停止。`market_order` は無効化（例外）。
  既定 `GMO_FX_READONLY=true` / `GMO_FX_ORDER_ENABLED=false`。
- **G2（設計のみ）Private read-only**: 残高 `/v1/account/assets`、建玉 `/v1/openPositions`、
  注文情報 `/v1/orders`・`/v1/activeOrders`、約定 `/v1/latestExecutions`。実接続は後続。
- **G3（設計のみ）dry-run order**: `gmo_dry_run_order()` が共通 RiskManager を通し、
  `build_gmo_order_payload()` で注文ボディを生成するが**送信しない**。SL/TP は OrderRequest
  スキーマで必須。OrderLog には `dry_run` として保存できる設計。
- **G4（未実装）100通貨実E2E**: 口座開設・APIキー発行・明示許可がある場合のみ別タスクで実施。

### 禁止（GMO）
- 実注文 / 実決済 / Private API 実接続 / `GMO_FX_ORDER_ENABLED=true` 化（明示許可前）
- APIキー・シークレットの出力・Git 追跡・ログ出力
- RiskManager・live注文ブロック・OANDA 既存経路の弱体化
