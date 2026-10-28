"""Ports: the event-hub contract and the public OrderBook surface.

``EventPort`` semantics (mirrors the compiled ``PubSub``):

- Listeners are held weakly: a hub never keeps a listener alive.
- Subscribing the same listener twice is a no-op; it gets one delivery per event.
- Delivery is synchronous inside ``trigger_event``.
- A listener may add or remove listeners during dispatch; listeners added then are not
  called for that event.
- A raising listener is logged and the remaining listeners still run; ``trigger_event``
  never raises because of a listener.
- Delivery order is unspecified.
"""

from collections.abc import Callable, Iterator
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from order_book.core.events import OrderBookTradeEvent
from order_book.core.message import OrderBookMessage
from order_book.core.types import OrderBookQueryResult, OrderBookRow

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd

EventSubscriber = Callable[[Any], None]


@runtime_checkable
class EventPort(Protocol):
    def add_listener(self, event_tag: Enum, listener: EventSubscriber) -> None: ...

    def remove_listener(self, event_tag: Enum, listener: EventSubscriber) -> None: ...

    def get_listeners(self, event_tag: Enum) -> list[EventSubscriber]: ...

    def trigger_event(self, event_tag: Enum, message: Any) -> None: ...


@runtime_checkable
class OrderBookProtocol(Protocol):
    """Public surface of an order book (event port + book operations and queries)."""

    def add_listener(self, event_tag: Enum, listener: EventSubscriber) -> None: ...

    def remove_listener(self, event_tag: Enum, listener: EventSubscriber) -> None: ...

    def get_listeners(self, event_tag: Enum) -> list[EventSubscriber]: ...

    def trigger_event(self, event_tag: Enum, message: Any) -> None: ...

    @property
    def snapshot_uid(self) -> int: ...

    @property
    def last_diff_uid(self) -> int: ...

    @property
    def last_applied_trade(self) -> float: ...

    last_trade_price: float
    last_trade_price_rest_updated: float

    def apply_snapshot(
        self, bids: list[OrderBookRow], asks: list[OrderBookRow], update_id: int
    ) -> None: ...

    def apply_diffs(
        self, bids: list[OrderBookRow], asks: list[OrderBookRow], update_id: int
    ) -> None: ...

    def apply_trade(self, trade: OrderBookTradeEvent) -> None: ...

    def restore_from_snapshot_and_diffs(
        self, snapshot: OrderBookMessage, diffs: list[OrderBookMessage]
    ) -> None: ...

    def bid_entries(self) -> Iterator[OrderBookRow]: ...

    def ask_entries(self) -> Iterator[OrderBookRow]: ...

    def get_price(self, is_buy: bool) -> float: ...

    def simulate_buy(self, amount: float) -> list[OrderBookRow]: ...

    def simulate_sell(self, amount: float) -> list[OrderBookRow]: ...

    def get_price_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult: ...

    def get_vwap_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult: ...

    def get_price_for_quote_volume(
        self, is_buy: bool, quote_volume: float
    ) -> OrderBookQueryResult: ...

    def get_quote_volume_for_base_amount(
        self, is_buy: bool, base_amount: float
    ) -> OrderBookQueryResult: ...

    def get_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult: ...

    def get_quote_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult: ...


@runtime_checkable
class FramesOrderBookProtocol(OrderBookProtocol, Protocol):
    """``OrderBookProtocol`` plus the numpy/pandas surface (``hb-order-book[frames]``)."""

    @property
    def snapshot(self) -> "tuple[pd.DataFrame, pd.DataFrame]": ...

    def apply_pandas_diffs(self, bids_df: "pd.DataFrame", asks_df: "pd.DataFrame") -> None: ...

    def apply_numpy_diffs(
        self, bids_array: "np.ndarray[Any, Any]", asks_array: "np.ndarray[Any, Any]"
    ) -> None: ...

    def apply_numpy_snapshot(
        self, bids_array: "np.ndarray[Any, Any]", asks_array: "np.ndarray[Any, Any]"
    ) -> None: ...
