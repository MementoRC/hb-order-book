from collections.abc import Iterator
from enum import Enum
from typing import Any

from order_book.core import (
    EventPort,
    OrderBook,
    OrderBookProtocol,
    OrderBookQueryResult,
    OrderBookRow,
)


class _GoodHub:
    def add_listener(self, event_tag: Enum, listener: Any) -> None: ...
    def remove_listener(self, event_tag: Enum, listener: Any) -> None: ...
    def get_listeners(self, event_tag: Enum) -> list[Any]:
        return []

    def trigger_event(self, event_tag: Enum, message: Any) -> None: ...


class _PartialHub:
    def add_listener(self, event_tag: Enum, listener: Any) -> None: ...


def test_event_port_runtime_check() -> None:
    assert isinstance(_GoodHub(), EventPort)
    assert not isinstance(_PartialHub(), EventPort)
    assert not isinstance(object(), EventPort)


def test_order_book_protocol_runtime_check() -> None:
    assert isinstance(OrderBook(), OrderBookProtocol)
    assert isinstance(OrderBook(), EventPort)
    assert not isinstance(_GoodHub(), OrderBookProtocol)


class _FullBook(_GoodHub):
    snapshot_uid = 0
    last_diff_uid = 0
    last_applied_trade = 0.0
    last_trade_price = 0.0
    last_trade_price_rest_updated = 0.0

    def apply_snapshot(self, bids: Any, asks: Any, update_id: int) -> None: ...
    def apply_diffs(self, bids: Any, asks: Any, update_id: int) -> None: ...
    def apply_trade(self, trade: Any) -> None: ...
    def restore_from_snapshot_and_diffs(self, snapshot: Any, diffs: Any) -> None: ...
    def bid_entries(self) -> Iterator[OrderBookRow]:
        return iter(())

    def ask_entries(self) -> Iterator[OrderBookRow]:
        return iter(())

    def get_price(self, is_buy: bool) -> float:
        return 0.0

    def simulate_buy(self, amount: float) -> list[OrderBookRow]:
        return []

    def simulate_sell(self, amount: float) -> list[OrderBookRow]:
        return []

    def _q(self) -> OrderBookQueryResult:
        return OrderBookQueryResult(0.0, 0.0, 0.0, 0.0)

    def get_price_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult:
        return self._q()

    def get_vwap_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult:
        return self._q()

    def get_price_for_quote_volume(self, is_buy: bool, quote_volume: float) -> OrderBookQueryResult:
        return self._q()

    def get_quote_volume_for_base_amount(
        self, is_buy: bool, base_amount: float
    ) -> OrderBookQueryResult:
        return self._q()

    def get_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult:
        return self._q()

    def get_quote_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult:
        return self._q()


def test_conforming_dummy_book_passes() -> None:
    assert isinstance(_FullBook(), OrderBookProtocol)
