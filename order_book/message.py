"""OrderBookMessage and its type enum."""

from enum import Enum
from functools import total_ordering
from typing import Any, NamedTuple

from order_book.types import OrderBookRow


class OrderBookMessageType(Enum):
    SNAPSHOT = 1
    DIFF = 2
    TRADE = 3


class _OrderBookMessageBase(NamedTuple):
    type: OrderBookMessageType
    content: dict[str, Any]
    timestamp: float | None


@total_ordering
class OrderBookMessage(_OrderBookMessageBase):
    __slots__ = ()

    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: dict[str, Any],
        timestamp: float | None = None,
    ) -> "OrderBookMessage":
        return super().__new__(cls, message_type, content, timestamp)

    @property
    def update_id(self) -> int:
        if self.type in (OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT):
            return self.content["update_id"]  # type: ignore[no-any-return]
        return -1

    @property
    def first_update_id(self) -> int:
        if self.type is OrderBookMessageType.DIFF:
            return self.content.get("first_update_id", self.update_id)  # type: ignore[no-any-return]
        return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return self.content["trade_id"]  # type: ignore[no-any-return]
        return -1

    @property
    def trading_pair(self) -> str:
        return self.content["trading_pair"]  # type: ignore[no-any-return]

    @property
    def asks(self) -> list[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(amount), self.update_id)
            for price, amount, *_ in self.content["asks"]
        ]

    @property
    def bids(self) -> list[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(amount), self.update_id)
            for price, amount, *_ in self.content["bids"]
        ]

    @property
    def has_update_id(self) -> bool:
        return self.type in {OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT}

    @property
    def has_trade_id(self) -> bool:
        return self.type == OrderBookMessageType.TRADE

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OrderBookMessage):
            return NotImplemented
        return (self.type == other.type) and (
            (self.has_update_id and (self.update_id == other.update_id))
            or (self.trade_id == other.trade_id)
        )

    def __hash__(self) -> int:
        # Hash only what __eq__ compares: equal messages must hash equal.
        return hash((self.type, self.update_id, self.trade_id))

    def __lt__(self, other: "OrderBookMessage") -> bool:  # type: ignore[override]
        return bool(
            (self.has_update_id and other.has_update_id and self.update_id < other.update_id)
            or (self.has_trade_id and other.has_trade_id and self.trade_id < other.trade_id)
            or (
                ((self.timestamp != other.timestamp) and self.timestamp < other.timestamp)  # type: ignore[operator]
                or self.has_update_id  # same timestamp: order book messages < trade messages
            )
        )
