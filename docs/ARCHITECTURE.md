# Architecture

## 方針

単一利用者向けのMVPです。戦略判定を `backend/app/strategies/` に集約し、
バックテスト、ペーパートレード、シグナル監視から同じ関数を利用します。

## 構成

```text
frontend/
  app/                 Next.js App Router
  components/          4 Phase共通ダッシュボード
  lib/                 API client、入力検証
  types/               API型
backend/
  app/
    models/            SQLAlchemyモデル
    schemas/           Pydantic API schema
    strategies/        MA、RSI、breakout
    services/          backtest、paper、signal、risk、broker、bot、automation
    brokers/           broker interface、local demo、OANDA practice
    tests/             unit/service tests
```

## データ

標準DBはSQLiteです。`DATABASE_URL`をPostgreSQL URLへ変更できます。スキーマ変更の
マイグレーション基盤はまだ導入していないため、共有・本番DBへ移行する前にAlembicを
追加してください。

## Phase

1. バックテスト: 確定足で判定し、次足始値で約定。コストと資金上限を反映。
2. ペーパー: DB永続セッションと仮想ポジション。価格は合成tick。
3. シグナル: 画面通知とDB履歴。注文サービスは呼び出さない。
4. デモ注文: ローカルデモに加え、OANDA practice限定で価格取得、戦略判定、Signal保存、
   リスク判定、数量計算、SL/TP付き注文、約定照合、ポジション監視、反対シグナル決済。

## 未接続

- 実際のヒストリカル／リアルタイム価格
- OANDA live API
- 経済指標カレンダー
- Discord、メール、LINE系通知

OANDA practiceは接続実装済みですが、実資格情報を使ったエンドツーエンド試験は環境依存の
ため未実施です。バックテスト、ペーパー、半自動シグナルの価格は引き続き合成データです。
