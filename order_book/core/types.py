"""Order book value types: rows and query results."""

from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple


class OrderBookRow(NamedTuple):
    """Change applied to an OrderBook. Uses float internally for performance."""

    price: float
    amount: float
    update_id: int


class ClientOrderBookRow(NamedTuple):
    """Row used in market classes where OrderBook values are converted to Decimal."""

    price: Decimal
    amount: Decimal
    update_id: int


@dataclass(slots=True)
class OrderBookQueryResult:
    """Result of an OrderBook volume/price query (float values)."""

    query_price: float
    query_volume: float
    result_price: float
    result_volume: float


@dataclass(slots=True)
class ClientOrderBookQueryResult:
    """Result of an OrderBook volume/price query (Decimal values)."""

    query_price: Decimal
    query_volume: Decimal
    result_price: Decimal
    result_volume: Decimal
