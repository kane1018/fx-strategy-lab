from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.brokers.base import Broker, BrokerResult
from app.config import Settings, get_settings
from app.schemas.trading import Candle, OrderRequest
from app.services.market_data_service import pip_size


class OandaBrokerError(RuntimeError):
    pass


@dataclass(frozen=True)
class OandaPrice:
    symbol: str
    bid: float
    ask: float
    midpoint: float
    spread_pips: float
    timestamp: datetime
    quote_home_conversion: float


@dataclass(frozen=True)
class OandaAccount:
    balance: float
    nav: float
    currency: str
    open_position_count: int


def _decimal(value: float) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")


def _price(value: float, symbol: str) -> str:
    precision = 3 if symbol.endswith("JPY") else 5
    return f"{value:.{precision}f}"


def _number(payload: dict[str, Any], key: str) -> float:
    return float(payload.get(key, 0) or 0)


def _fill_result(
    transaction: dict[str, Any],
    broker_order_id: str,
    status: str,
) -> BrokerResult:
    closed = list(transaction.get("tradesClosed") or [])
    reduced = transaction.get("tradeReduced")
    opened = transaction.get("tradeOpened")
    trade = opened or reduced or (closed[0] if closed else {})
    realized = _number(transaction, "pl")
    financing = _number(transaction, "financing")
    commission = _number(transaction, "commission")
    guaranteed_fee = _number(transaction, "guaranteedExecutionFee")
    net_pnl = realized + financing - commission - guaranteed_fee
    fill_price = (
        trade.get("price")
        or transaction.get("fullVWAP")
        or transaction.get("price")
    )
    if fill_price is None:
        raise OandaBrokerError("約定価格を確認できません")
    return BrokerResult(
        broker_order_id=broker_order_id,
        status=status,
        filled_price=float(fill_price),
        fill_transaction_id=str(transaction["id"]),
        trade_id=str(trade.get("tradeID")) if opened and trade.get("tradeID") else None,
        fill_time=datetime.fromisoformat(str(transaction["time"]).replace("Z", "+00:00")),
        filled_units=abs(_number(transaction, "units")),
        realized_pnl=net_pnl if closed or reduced else None,
        financing=financing,
        commission=commission,
        guaranteed_execution_fee=guaranteed_fee,
        half_spread_cost=_number(transaction, "halfSpreadCost"),
        closed_trade_ids=tuple(
            str(item["tradeID"])
            for item in [*closed, *([reduced] if reduced else [])]
            if item.get("tradeID")
        ),
    )


class OandaBroker(Broker):
    PRACTICE_API_URL = "https://api-fxpractice.oanda.com"

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._validate_config()
        self.client = client or httpx.Client(
            base_url=self.settings.oanda_api_url,
            headers={
                "Authorization": f"Bearer {self.settings.oanda_api_token}",
                "Content-Type": "application/json",
                "Accept-Datetime-Format": "RFC3339",
            },
            timeout=10,
        )

    def _validate_config(self) -> None:
        if self.settings.oanda_environment.lower() != "practice":
            raise OandaBrokerError("OANDA_ENV must be practice")
        if self.settings.oanda_api_url.rstrip("/") != self.PRACTICE_API_URL:
            raise OandaBrokerError("OANDA practice以外のAPI URLは使用できません")
        if not self.settings.oanda_api_token:
            raise OandaBrokerError("OANDA_API_TOKENが未設定です")
        if not self.settings.oanda_account_id:
            raise OandaBrokerError("OANDA_ACCOUNT_IDが未設定です")

    @property
    def account_id(self) -> str:
        account_id = self.settings.oanda_account_id
        if not account_id:
            raise OandaBrokerError("OANDA_ACCOUNT_IDが未設定です")
        return account_id

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.client.request(method, path, params=params, json=json)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            try:
                payload = error.response.json()
                message = payload.get("errorMessage") or payload.get("errorCode")
            except ValueError:
                message = None
            raise OandaBrokerError(
                f"OANDA API error ({error.response.status_code}): {message or 'request rejected'}"
            ) from error
        except (httpx.RequestError, ValueError) as error:
            raise OandaBrokerError("OANDA API connection error") from error

    def connection_test(self) -> bool:
        self.account_summary()
        return True

    def account_summary(self) -> OandaAccount:
        payload = self._request("GET", f"/v3/accounts/{self.account_id}/summary")
        account = payload["account"]
        return OandaAccount(
            balance=float(account["balance"]),
            nav=float(account["NAV"]),
            currency=str(account["currency"]),
            open_position_count=int(account["openPositionCount"]),
        )

    def current_price(self, symbol: str) -> OandaPrice:
        payload = self._request(
            "GET",
            f"/v3/accounts/{self.account_id}/pricing",
            params={"instruments": symbol, "includeHomeConversions": "true"},
        )
        prices = payload.get("prices", [])
        if not prices:
            raise OandaBrokerError(f"{symbol}の価格が取得できません")
        price = prices[0]
        if price.get("status") != "tradeable":
            raise OandaBrokerError(f"{symbol}は現在取引できません")
        bid = float(price["closeoutBid"])
        ask = float(price["closeoutAsk"])
        factors = price.get("quoteHomeConversionFactors") or {}
        conversions = [
            abs(float(value))
            for value in (factors.get("positiveUnits"), factors.get("negativeUnits"))
            if value is not None
        ]
        if not conversions:
            raise OandaBrokerError("quote-home conversion factorが取得できません")
        timestamp = datetime.fromisoformat(str(price["time"]).replace("Z", "+00:00"))
        return OandaPrice(
            symbol=symbol,
            bid=bid,
            ask=ask,
            midpoint=(bid + ask) / 2,
            spread_pips=(ask - bid) / pip_size(symbol),
            timestamp=timestamp,
            quote_home_conversion=max(conversions),
        )

    def candles(self, symbol: str, timeframe: str, count: int = 200) -> list[Candle]:
        payload = self._request(
            "GET",
            f"/v3/accounts/{self.account_id}/instruments/{symbol}/candles",
            params={
                "price": "M",
                "granularity": timeframe,
                "count": min(max(count, 10), 5000),
            },
        )
        candles: list[Candle] = []
        for item in payload.get("candles", []):
            if not item.get("complete"):
                continue
            midpoint = item["mid"]
            candles.append(
                Candle(
                    timestamp=datetime.fromisoformat(
                        str(item["time"]).replace("Z", "+00:00")
                    ),
                    open=float(midpoint["o"]),
                    high=float(midpoint["h"]),
                    low=float(midpoint["l"]),
                    close=float(midpoint["c"]),
                    volume=float(item.get("volume", 0)),
                )
            )
        if not candles:
            raise OandaBrokerError(f"{symbol}の確定足が取得できません")
        return candles

    def open_positions(self) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/v3/accounts/{self.account_id}/openPositions")
        return list(payload.get("positions", []))

    def confirm_fill(self, transaction_id: str) -> dict[str, Any]:
        payload = self._request(
            "GET",
            f"/v3/accounts/{self.account_id}/transactions/{transaction_id}",
        )
        transaction = payload.get("transaction", {})
        if transaction.get("type") != "ORDER_FILL":
            raise OandaBrokerError("約定Transactionを確認できません")
        return transaction

    def trade_details(self, trade_id: str) -> dict[str, Any]:
        payload = self._request(
            "GET",
            f"/v3/accounts/{self.account_id}/trades/{trade_id}",
        )
        trade = payload.get("trade")
        if not trade:
            raise OandaBrokerError("Trade詳細を確認できません")
        return dict(trade)

    def closed_trade_summary(self, trade_id: str) -> dict[str, Any]:
        trade = self.trade_details(trade_id)
        if trade.get("state") != "CLOSED":
            raise OandaBrokerError("Tradeが決済済みではありません")
        transaction_ids = list(trade.get("closingTransactionIDs") or [])
        if not transaction_ids:
            raise OandaBrokerError("決済Transaction IDを確認できません")
        transactions = [self.confirm_fill(str(item)) for item in transaction_ids]
        realized = sum(_number(item, "pl") for item in transactions)
        financing = sum(_number(item, "financing") for item in transactions)
        commission = sum(_number(item, "commission") for item in transactions)
        guaranteed_fee = sum(
            _number(item, "guaranteedExecutionFee") for item in transactions
        )
        return {
            "trade_id": trade_id,
            "status": "closed",
            "realized_pnl": realized + financing - commission - guaranteed_fee,
            "gross_pl": realized,
            "financing": financing,
            "commission": commission,
            "guaranteed_execution_fee": guaranteed_fee,
            "half_spread_cost": sum(
                _number(item, "halfSpreadCost") for item in transactions
            ),
            "average_close_price": float(trade["averageClosePrice"]),
            "closed_at": str(trade["closeTime"]),
            "closing_transaction_ids": [str(item) for item in transaction_ids],
        }

    def market_order(self, request: OrderRequest) -> BrokerResult:
        signed_units = request.units if request.side.value == "buy" else -request.units
        payload = self._request(
            "POST",
            f"/v3/accounts/{self.account_id}/orders",
            json={
                "order": {
                    "units": _decimal(signed_units),
                    "instrument": request.symbol,
                    "timeInForce": "FOK",
                    "type": "MARKET",
                    "positionFill": "DEFAULT",
                    "stopLossOnFill": {
                        "price": _price(request.stop_loss, request.symbol),
                        "timeInForce": "GTC",
                    },
                    "takeProfitOnFill": {
                        "price": _price(request.take_profit, request.symbol),
                    },
                }
            },
        )
        create = payload.get("orderCreateTransaction", {})
        fill = payload.get("orderFillTransaction")
        if not fill:
            raise OandaBrokerError("成行注文の即時約定を確認できません")
        confirmed = self.confirm_fill(str(fill["id"]))
        return _fill_result(
            confirmed,
            str(create.get("id") or fill.get("orderID")),
            "filled",
        )

    def close_position(self, symbol: str, side: str) -> BrokerResult:
        body = (
            {"longUnits": "ALL", "shortUnits": "NONE"}
            if side == "buy"
            else {"longUnits": "NONE", "shortUnits": "ALL"}
        )
        payload = self._request(
            "PUT",
            f"/v3/accounts/{self.account_id}/positions/{symbol}/close",
            json=body,
        )
        prefix = "long" if side == "buy" else "short"
        create = payload.get(f"{prefix}OrderCreateTransaction", {})
        fill = payload.get(f"{prefix}OrderFillTransaction")
        if not fill:
            raise OandaBrokerError("決済注文の約定を確認できません")
        confirmed = self.confirm_fill(str(fill["id"]))
        return _fill_result(
            confirmed,
            str(create.get("id") or fill.get("orderID")),
            "closed",
        )
