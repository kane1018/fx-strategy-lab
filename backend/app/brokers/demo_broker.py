from uuid import uuid4

from app.brokers.base import Broker, BrokerResult
from app.schemas.trading import OrderRequest
from app.services.market_data_service import pip_size


class DemoBroker(Broker):
    def connection_test(self) -> bool:
        return True

    def market_order(self, request: OrderRequest) -> BrokerResult:
        pip = pip_size(request.symbol)
        slippage = pip * 0.1
        fill = (
            request.current_price + slippage
            if request.side.value == "buy"
            else request.current_price - slippage
        )
        return BrokerResult(
            broker_order_id=f"DEMO-{uuid4().hex[:12].upper()}",
            status="filled",
            filled_price=fill,
        )
