# FX Strategy Lab

個人用のFX戦略検証・ペーパートレード・シグナル監視・デモ注文基盤です。

実資金取引はデフォルトで無効です。このMVPには実資金ブローカー実装を含めず、
ライブ注文要求は安全条件に関係なく最終的に拒否されます。

## セットアップ

```bash
cp .env.example .env

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

別のターミナルで:

```bash
cd frontend
npm install
npm run dev
```

ブラウザで `http://localhost:3000` を開きます。APIドキュメントは
`http://localhost:8000/docs` です。

## Structure

- `frontend/`: Next.js dashboard
- `backend/`: FastAPI, strategy engine, risk controls, SQLite persistence
- `docs/`: architecture, safety, and API notes

詳しい手順は [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) と
[docs/SAFETY.md](docs/SAFETY.md) を参照してください。

## 現在の接続範囲

- 市場データ: バックテスト等は再現可能な合成OHLC、Phase 4はOANDA practice価格
- ブローカー: ローカルデモブローカーとOANDA practice
- OANDA: practice限定で価格・残高・確定足・注文・約定・ポジション・決済に対応
- 通知: 画面表示とSQLite保存
- DB: SQLite標準。`DATABASE_URL`でPostgreSQL系へ変更可能

OANDA practiceを使う場合は、`.env`へ以下を設定します。

```dotenv
OANDA_ENV=practice
OANDA_API_URL=https://api-fxpractice.oanda.com
OANDA_API_TOKEN=
OANDA_ACCOUNT_ID=
ENABLE_LIVE_TRADING=false
```

トークンまたは口座IDが未設定の場合、practice接続と自動売買開始は明示的に拒否されます。
UIのPhase 4で接続テスト後に自動売買をONにすると、30秒周期の監視を開始します。

OANDA側のSL/TPで決済された場合は、Trade詳細と`closingTransactionIDs`を取得し、
OrderFill Transactionの損益・金利・手数料を照合します。照合できない場合は
`close_unconfirmed`としてBotを停止し、成功扱いにはしません。

現在は`Base.metadata.create_all()`を利用しています。既存DBへ列変更や制約変更を行う段階では、
自動作成へ依存せずAlembicを導入し、practice DBのバックアップとdry-run後に適用してください。

## practice E2E（市場稼働時）

平日の市場稼働時間中に、小数量のpractice注文〜決済を確認する手順は
[docs/SAFETY.md](docs/SAFETY.md) の「市場開始後の practice E2E 手順」を参照してください。
補助スクリプト `backend/scripts/practice_e2e.py` は practice 専用で、`preflight`（読み取り専用）
→ `order`（`--confirm`・1〜10 units・SL/TP必須・tradeable時のみ）→ `status` → `close` の順に
使います。live broker は生成されず、すべての注文は RiskManager を通ります。

```bash
cd backend
.venv/bin/python -m scripts.practice_e2e preflight --symbol USD_JPY
```

バックテスト結果は将来の利益を保証しません。
