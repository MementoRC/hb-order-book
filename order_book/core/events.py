"""Order book events."""

from decimal import Decimal
from typing import NamedTuple

from data_type_primitives import TradeType
from event_bus import OrderBookEvent

__all__ = ["OrderBookEvent", "OrderBookTradeEvent"]


class OrderBookTradeEvent(NamedTuple):
    trading_pair: str
    timestamp: float
    type: TradeType
    price: Decimal
    amount: Decimal
    trade_id: str | None = None
    is_taker: bool = True  # CEXs deliver trade events from the taker's perspective
