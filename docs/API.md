# API

FastAPI起動後、完全なOpenAPI仕様は `/docs` で確認できます。

## Backtest

- `POST /api/backtests`

## Paper trading

- `POST /api/paper/sessions`
- `GET /api/paper/sessions/{id}`
- `POST /api/paper/sessions/{id}/tick`
- `POST /api/paper/sessions/{id}/stop`

## Signals

- `POST /api/signals/monitors`
- `POST /api/signals/monitors/{id}/evaluate`
- `POST /api/signals/monitors/{id}/stop`
- `GET /api/signals`

## Bot and broker

- `POST /api/broker/connection-test?mode=demo`
- `POST /api/broker/connection-test?mode=practice`
- `GET /api/bot/status`
- `POST /api/bot/start`
- `POST /api/bot/stop`
- `POST /api/orders`
- `POST /api/orders/{id}/close`
- `GET /api/orders`

`POST /api/orders`は`request`と`risk`を持つJSONを受け取ります。ライブ注文は固定ガードで
拒否されます。

## OANDA practice automation

- `GET /api/automation/status`
- `POST /api/automation/start`
- `POST /api/automation/cycle`
- `POST /api/automation/stop`

`POST /api/automation/start`は`symbol`、`timeframe`、`strategy`、`execution`、`risk`、
`interval_seconds`を受け取ります。開始時に残高・価格・確定足・ポジションを確認し、
いずれかが失敗した場合はBotを`error_stopped`にします。live環境へのルートはありません。
