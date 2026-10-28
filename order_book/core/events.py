"""Order book events."""

from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from data_type_primitives import TradeType


class OrderBookEvent(int, Enum):
    TradeEvent = 901
    OrderBookDataSourceUpdateEvent = 904


class OrderBookTradeEvent(NamedTuple):
    trading_pair: str
    timestamp: float
    type: TradeType
    price: Decimal
    amount: Decimal
    trade_id: str | None = None
    is_taker: bool = True  # CEXs deliver trade events from the taker's perspective
