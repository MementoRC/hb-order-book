from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

import pytest
from data_type_primitives import TradeType

from order_book.core import (
    CompositeOrderBook,
    EventHub,
    OrderBook,
    OrderBookEvent,
    OrderBookProtocol,
    OrderBookRow,
    OrderBookTradeEvent,
)
from order_book.core.composite_order_book import OrderFillLike

R = OrderBookRow


class LocalTradeType(Enum):
    BUY = 1
    SELL = 2
    OTHER = 3


LocalTradeType.__name__ = "TradeType"


@dataclass
class Fill:
    price: float
    amount: float
    timestamp: float
    trade_type: Any


def make_book() -> CompositeOrderBook:
    book = CompositeOrderBook()
    book.apply_snapshot(
        [R(10, 1, 1), R(9, 2, 1), R(8, 3, 1)],
        [R(11, 1, 1), R(12, 2, 1), R(13, 3, 1)],
        7,
    )
    return book


def buy(price: float, amount: float, ts: float = 100.0) -> Fill:
    return Fill(price, amount, ts, TradeType.BUY)


def sell(price: float, amount: float, ts: float = 100.0) -> Fill:
    return Fill(price, amount, ts, TradeType.SELL)


def traded_asks(book: CompositeOrderBook) -> list[OrderBookRow]:
    return list(book.traded_order_book.ask_entries())


def traded_bids(book: CompositeOrderBook) -> list[OrderBookRow]:
    return list(book.traded_order_book.bid_entries())


def test_constructor_ignores_order_book_and_is_protocol() -> None:
    other = make_book()
    book = CompositeOrderBook(other)
    assert list(book.bid_entries()) == []
    assert isinstance(book.traded_order_book, OrderBook)
    assert book.traded_order_book is not other
    assert isinstance(book, OrderBookProtocol)
    assert isinstance(buy(1, 1), OrderFillLike)


def test_record_buy_goes_to_traded_asks_and_accumulates() -> None:
    book = make_book()
    book.record_filled_order(buy(11, 0.25, 100.9))
    assert traded_asks(book) == [R(11, 0.25, 100)]
    assert traded_bids(book) == []
    book.record_filled_order(buy(11, Decimal("0.5"), 200.0))
    assert traded_asks(book) == [R(11, 0.75, 200)]
    assert book.traded_order_book.last_diff_uid == 200


def test_record_sell_goes_to_traded_bids_and_accumulates() -> None:
    book = make_book()
    book.record_filled_order(sell(10, 0.25))
    book.record_filled_order(sell(10, 0.25))
    book.record_filled_order(sell(9, 1))
    assert traded_bids(book) == [R(10, 0.5, 100), R(9, 1, 100)]
    assert traded_asks(book) == []


def test_unknown_trade_type_records_nothing() -> None:
    book = make_book()
    book.record_filled_order(Fill(11, 1, 5.0, LocalTradeType.OTHER))
    assert traded_asks(book) == []
    assert traded_bids(book) == []
    assert book.traded_order_book.last_diff_uid == 5


def test_local_trade_type_enum_is_supported() -> None:
    book = make_book()
    assert LocalTradeType.BUY.__class__ is not TradeType
    book.record_filled_order(Fill(11, 0.5, 1.0, LocalTradeType.BUY))
    book.record_filled_order(Fill(10, 0.5, 1.0, LocalTradeType.SELL))
    assert list(book.ask_entries())[0] == R(11, 0.5, 1)
    assert list(book.bid_entries())[0] == R(10, 0.5, 1)


def test_ask_netting_and_filtering() -> None:
    book = make_book()
    book.record_filled_order(buy(11, 0.25))
    book.record_filled_order(buy(12, 2))
    assert list(book.ask_entries()) == [R(11, 0.75, 1), R(13, 3, 1)]
    assert list(book.original_ask_entries()) == [R(11, 1, 1), R(12, 2, 1), R(13, 3, 1)]


def test_bid_netting_and_filtering() -> None:
    book = make_book()
    book.record_filled_order(sell(10, 0.25))
    book.record_filled_order(sell(9, 2))
    assert list(book.bid_entries()) == [R(10, 0.75, 1), R(8, 3, 1)]
    assert list(book.original_bid_entries()) == [R(10, 1, 1), R(9, 2, 1), R(8, 3, 1)]


def test_ask_pruning_after_exhaustion() -> None:
    book = make_book()
    book.record_filled_order(buy(10.5, 1, 1))  # below best ask: stale
    book.record_filled_order(buy(11, 5, 2))  # over-consumed: trimmed to original amount
    book.record_filled_order(buy(12.5, 1, 3))  # between 12 and 13: stale
    book.record_filled_order(buy(13.5, 1, 4))  # beyond the book: never reached (core parity)
    assert list(book.ask_entries()) == [R(12, 2, 1), R(13, 3, 1)]
    assert traded_asks(book) == [R(11, 1, 2), R(13.5, 1, 4)]


def test_bid_pruning_after_exhaustion() -> None:
    book = make_book()
    book.record_filled_order(sell(10.5, 1, 1))  # above best bid: stale
    book.record_filled_order(sell(10, 5, 2))  # over-consumed: trimmed to original amount
    book.record_filled_order(sell(9.5, 1, 3))  # between 10 and 9: stale
    book.record_filled_order(sell(7, 1, 4))  # beyond the book: never reached (core parity)
    assert list(book.bid_entries()) == [R(9, 2, 1), R(8, 3, 1)]
    assert traded_bids(book) == [R(10, 1, 2), R(7, 1, 4)]


def test_traded_level_below_best_bid_does_not_filter() -> None:
    book = make_book()
    book.record_filled_order(sell(9.5, 1))
    assert list(book.bid_entries()) == [R(10, 1, 1), R(9, 2, 1), R(8, 3, 1)]


def test_partial_consumption_does_not_prune() -> None:
    book = make_book()
    book.record_filled_order(buy(10.5, 1))
    book.record_filled_order(sell(10.4, 1))
    assert next(book.ask_entries()) == R(11, 1, 1)
    assert next(book.bid_entries()) == R(10, 1, 1)
    assert traded_asks(book) == [R(10.5, 1, 100)]
    assert traded_bids(book) == [R(10.4, 1, 100)]
    list(book.ask_entries())
    list(book.bid_entries())
    assert traded_asks(book) == []
    assert traded_bids(book) == []


def test_clear_traded_order_book() -> None:
    book = make_book()
    book.record_filled_order(buy(11, 1))
    book.record_filled_order(sell(10, 1))
    book.clear_traded_order_book()
    assert traded_asks(book) == []
    assert traded_bids(book) == []
    assert list(book.ask_entries())[0] == R(11, 1, 1)


def test_get_price_normal_and_netted_best() -> None:
    book = make_book()
    assert book.get_price(True) == 11
    assert book.get_price(False) == 10
    book.record_filled_order(buy(11, 1))
    book.record_filled_order(sell(10, 1))
    assert book.get_price(True) == 12
    assert book.get_price(False) == 9


def test_get_price_empty_side_raises() -> None:
    book = CompositeOrderBook()
    with pytest.raises(OSError, match="empty"):
        book.get_price(True)
    with pytest.raises(EnvironmentError, match="empty"):
        book.get_price(False)


def test_get_price_fully_netted_raises_os_error() -> None:
    book = CompositeOrderBook()
    book.apply_snapshot([R(10, 1, 1)], [R(11, 1, 1)], 1)
    book.record_filled_order(buy(11, 1))
    book.record_filled_order(sell(10, 1))
    with pytest.raises(OSError, match="consumed"):
        book.get_price(True)
    with pytest.raises(OSError, match="consumed"):
        book.get_price(False)


def test_inherited_queries_see_netted_levels() -> None:
    book = make_book()
    book.record_filled_order(buy(11, 1))
    book.record_filled_order(sell(10, 0.5))
    assert book.get_price_for_volume(True, 1).result_price == 12
    assert book.get_volume_for_price(True, 12).result_volume == 2
    assert book.get_volume_for_price(False, 9).result_volume == 2.5
    assert book.simulate_buy(1) == [R(12, 1, 1)]
    assert book.simulate_sell(0.5) == [R(10, 0.5, 1)]


def test_trade_events_still_emitted() -> None:
    book = make_book()
    received: list[Any] = []

    def listener(ev: Any) -> None:
        received.append(ev)

    book.add_listener(OrderBookEvent.TradeEvent, listener)
    trade = OrderBookTradeEvent("BTC-USDT", 1.0, TradeType.BUY, Decimal("100"), Decimal("1"))
    book.apply_trade(trade)
    assert received == [trade]
    assert book.last_trade_price == 100.0


def test_injected_event_hub_is_used() -> None:
    hub = EventHub()
    book = CompositeOrderBook(event_hub=hub)
    received: list[Any] = []

    def listener(ev: Any) -> None:
        received.append(ev)

    hub.add_listener(OrderBookEvent.TradeEvent, listener)
    book.apply_trade(OrderBookTradeEvent("X", 1.0, TradeType.SELL, Decimal("1"), Decimal("1")))
    assert len(received) == 1
