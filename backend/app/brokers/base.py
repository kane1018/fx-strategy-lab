from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.schemas.trading import OrderRequest


@dataclass(frozen=True)
class BrokerResult:
    broker_order_id: str
    status: str
    filled_price: float
    fill_transaction_id: str | None = None
    trade_id: str | None = None
    fill_time: datetime | None = None
    filled_units: float | None = None
    realized_pnl: float | None = None
    financing: float = 0
    commission: float = 0
    guaranteed_execution_fee: float = 0
    half_spread_cost: float = 0
    closed_trade_ids: tuple[str, ...] = ()


class Broker(ABC):
    @abstractmethod
    def connection_test(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def market_order(self, request: OrderRequest) -> BrokerResult:
        raise NotImplementedError
