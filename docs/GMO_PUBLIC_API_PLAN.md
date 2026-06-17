# GMO 外国為替FX Public API メモ（Phase 2B）

shadow 検証用の **Public（認証不要）read-only** market data 取得についての仕様メモと安全制約。
adapter は `backend/app/shadow/gmo_public.py`、CLI は `backend/scripts/fetch_gmo_public_market_data.py`。
Public のみ・APIキー不要・注文なし・本番公開なし・local CLI 限定。

## 1. Phase 2B の範囲

- GMO Public API 仕様の確認（下記）。
- Public/read-only adapter（`GmoPublicMarketDataClient`、shadow `MarketDataClient` Protocol を実装）。
- local CLI（status / ticker / klines の GET 確認、保存なし）。
- mock(httpx MockTransport) parser/adapter テスト（pytest はネットワーク非依存）。
- 実 API 取得結果は **repo に保存しない**。本番公開 API には追加しない。

## 2. Public API 仕様メモ（参照元・確認内容）

- **参照元**: GMO コイン 外国為替FX 公式 API ドキュメント（Public API）。本リポジトリの既存実装
  `backend/app/brokers/gmo_fx_broker.py`（公式仕様に基づき構築済み）と同一のendpoint/レスポンス形状を踏襲。
  本タスクでも live CLI で `status`(=OPEN) と `ticker`(USD_JPY) の応答を実際に確認済み。
- **base URL**: `https://forex-api.coin.z.com/public`
- **共通エンベロープ**: `{"status": 0, "data": ..., "responsetime": "..."}`。
  `status != 0` は `messages[].message_code`（例 `ERR-5003` = レート制限）を伴う。
- **確認した endpoint / データ種別**:
  - `GET /v1/status` → `data.status`（`OPEN` / `CLOSE` / `MAINTENANCE`）。
  - `GET /v1/ticker` → `data` = `[{symbol, bid, ask, timestamp, status}]`（全銘柄。symbol で抽出）。
  - `GET /v1/klines?symbol&priceType&interval&date` →
    `data` = `[{openTime, open, high, low, close}]`。
- **symbol**: `BASE_QUOTE` 形式（例 `USD_JPY`）。内部表記＝GMO 表記（そのまま）。
- **interval**: GMO 文字列（`1min`/`5min`/`15min`/`30min`/`1hour`/`4hour`/`1day` など）。
  adapter は内部 timeframe（`M1`/`M5`/…）も GMO interval にマップ（`GMO_INTERVALS`）。
- **date**: klines は `YYYYMMDD`（UTC 基準。未指定時は当日 UTC）。
- **response の主項目 / 型・時刻**:
  - 数値（bid/ask/open/high/low/close）は **文字列で返る** → `Decimal(str(x))` で安全に検証して `float` 化。
  - ticker `timestamp` は ISO 文字列（末尾 `Z`）。内部 `Ticker.time` に文字列のまま保持。
  - klines `openTime` は **ミリ秒 epoch（文字列）** → `datetime.fromtimestamp(ms/1000, UTC).isoformat()` で
    内部 `Candle.time`（ISO 文字列）に正規化。volume は Public klines に含まれないため `None`。
- **制限・注意点**: レート制限あり（`ERR-5003` / HTTP 429）。GMO 外国為替FX は**デモ環境なし・本番のみ**
  （ただし Public はマーケットデータのみで認証不要・注文不可）。市場クローズ時は ticker `status != OPEN`。
- **不明点 / 今後確認**: 全 interval の網羅、過去日 klines の取得可能範囲、レート制限の具体閾値、
  板情報(orderbooks)の要否（現状は ticker/klines のみ対象）。

## 3. 内部正規化（→ shadow models）

- `/v1/ticker` 行 → `Ticker(symbol, bid, ask, time)`（`mid` は (bid+ask)/2）。
- `/v1/klines` 行 → `Candle(time=ISO(openTime), open, high, low, close, volume=None)`。
- 数値は `_num()`＝`float(Decimal(str(x)))`（不正値は `GmoPublicError`）。

## 4. 安全制約（Phase 2B）

- **Public API のみ**。認証ヘッダ・APIキー・secret・`.env` を一切使わない/送らない（テストで no-auth を検証）。
- **Private API 禁止**（残高/建玉/注文/約定/変更/取消は実装しない）。
- 実注文・実資金なし。注文送信関数なし（adapter は GET のみ）。
- 本番公開 API（`app.main_readonly:app`）に **追加しない**。Render/Vercel 設定・DB・認証は変更しない。
- **local CLI 限定**。取得結果は stdout のみ・保存なし。実 API レスポンスを repo にコミットしない。
- 失敗時: 例外を握りつぶさず `GmoPublicError("Public API取得失敗: ...")`。Private へフォールバックしない。
  timeout 10s。無限 retry なし（本実装は retry なし＝1 回 GET）。

## 5. local CLI

```bash
cd backend
python -m scripts.fetch_gmo_public_market_data --kind status
python -m scripts.fetch_gmo_public_market_data --kind ticker --symbol USD_JPY
python -m scripts.fetch_gmo_public_market_data --kind candles --symbol USD_JPY \
    --interval 1min --date 20260618 --limit 5
```

GET のみ・APIキー不要・保存なし。`status` は OPEN/CLOSE/MAINTENANCE を表示。

## 6. 次フェーズ

- **Phase 2C**: Public 取得 → `SignalFn` → `ShadowTrader.step` を local 実行し、shadow log 保存・仮想損益の
  蓄積（1〜2 週間の注文なし運用ログ）。reports 化は安全レビュー後に検討。
- **Phase 3**: Private API の **read-only** 設計（残高/建玉の参照のみ・まだ注文なし）。APIキーの扱いは
  [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) の基準と明示承認のうえで別フェーズ管理。
