import logging
import math
import time
from decimal import Decimal
from enum import Enum
from typing import Any

import pytest
from data_type_primitives import TradeType

from order_book.core import (
    EventHub,
    EventPort,
    OrderBook,
    OrderBookEvent,
    OrderBookMessage,
    OrderBookMessageType,
    OrderBookProtocol,
    OrderBookRow,
    OrderBookTradeEvent,
)

R = OrderBookRow


def make_book(dex: bool = False) -> OrderBook:
    book = OrderBook(dex=dex)
    book.apply_snapshot(
        [R(10, 1, 1), R(9, 2, 1), R(8, 3, 1)],
        [R(11, 1, 1), R(12, 2, 1), R(13, 3, 1)],
        7,
    )
    return book


def test_initial_state() -> None:
    book = OrderBook()
    assert book.snapshot_uid == 0
    assert book.last_diff_uid == 0
    assert math.isnan(book.last_trade_price)
    assert book.last_applied_trade == -1000.0
    assert book.last_trade_price_rest_updated == -1000
    assert list(book.bid_entries()) == []
    assert list(book.ask_entries()) == []
    assert OrderBook.ORDER_BOOK_TRADE_EVENT_TAG == 901
    assert OrderBook.logger() is logging.getLogger("order_book.core.order_book")


def test_protocol_conformance() -> None:
    book = OrderBook()
    assert isinstance(book, OrderBookProtocol)
    assert isinstance(book, EventPort)


def test_setters() -> None:
    book = OrderBook()
    book.last_trade_price = 5.5
    book.last_trade_price_rest_updated = 12.0
    assert book.last_trade_price == 5.5
    assert book.last_trade_price_rest_updated == 12.0


def test_snapshot_entries_ordering_and_uid() -> None:
    book = make_book()
    assert book.snapshot_uid == 7
    assert list(book.bid_entries()) == [R(10, 1, 1), R(9, 2, 1), R(8, 3, 1)]
    assert list(book.ask_entries()) == [R(11, 1, 1), R(12, 2, 1), R(13, 3, 1)]


def test_snapshot_replaces_previous_and_keeps_zero_amounts() -> None:
    book = make_book()
    book.apply_snapshot([R(1, 0, 2)], [R(2, 0, 2)], 8)
    assert list(book.bid_entries()) == [R(1, 0, 2)]
    assert list(book.ask_entries()) == [R(2, 0, 2)]
    assert book.get_price(False) == 1
    assert book.get_price(True) == 2


def test_snapshot_best_prices_unsorted_input() -> None:
    book = OrderBook()
    book.apply_snapshot(
        [R(1, 1, 1), R(3, 1, 1), R(2, 1, 1)], [R(6, 1, 1), R(4, 1, 1), R(5, 1, 1)], 1
    )
    assert book.get_price(False) == 3
    assert book.get_price(True) == 4


def test_empty_snapshot_clears() -> None:
    book = make_book()
    book.apply_snapshot([], [], 9)
    assert list(book.bid_entries()) == []
    with pytest.raises(EnvironmentError, match="empty"):
        book.get_price(True)
    with pytest.raises(EnvironmentError):
        book.get_price(False)


def test_get_price() -> None:
    book = make_book()
    assert book.get_price(True) == 11
    assert book.get_price(False) == 10


def test_get_price_raises_when_one_side_empty() -> None:
    book = OrderBook()
    book.apply_snapshot([R(1, 1, 1)], [], 1)
    assert book.get_price(False) == 1
    with pytest.raises(EnvironmentError):
        book.get_price(True)


def test_cex_snapshot_not_truncated() -> None:
    book = OrderBook(dex=False)
    book.apply_snapshot([R(10, 1, 1)], [R(9, 1, 1)], 1)
    assert list(book.bid_entries()) == [R(10, 1, 1)]
    assert list(book.ask_entries()) == [R(9, 1, 1)]
    assert book.get_price(False) == 10
    assert book.get_price(True) == 9


def test_truncate_overlap_entries_dex() -> None:
    book = OrderBook(dex=True)
    bids = [R(1, 1, 1), R(2, 1, 2), R(3, 1, 3), R(50, 0.01, 4)]
    asks = [R(4, 1, 1), R(5, 1, 2), R(6, 1, 3), R(7, 1, 4)]
    book.apply_snapshot(bids, asks, 4)
    assert next(book.bid_entries()) == R(3, 1, 3)
    assert next(book.ask_entries()) == R(4, 1, 1)
    assert book.get_price(False) == 3
    assert book.get_price(True) == 4

    book.apply_diffs([R(3.5, 1, 5)], [R(2, 0.1, 5)], 5)
    assert next(book.bid_entries()) == R(3.5, 1, 5)
    assert next(book.ask_entries()) == R(4, 1, 1)
    assert book.get_price(False) == 3.5
    assert book.get_price(True) == 4


def test_truncate_overlap_entries_cex() -> None:
    book = OrderBook(dex=False)
    bids = [R(1, 1, 1), R(2, 1, 2), R(3, 1, 3)]
    asks = [R(4, 1, 1), R(5, 1, 2), R(6, 1, 3), R(7, 1, 4)]
    book.apply_snapshot(bids, asks, 4)
    assert next(book.bid_entries()) == R(3, 1, 3)
    assert next(book.ask_entries()) == R(4, 1, 1)

    book.apply_diffs([R(50, 0.01, 6)], [R(2, 0.1, 5)], 6)
    assert next(book.bid_entries()) == R(50, 0.01, 6)
    assert list(book.ask_entries()) == []
    assert book.last_diff_uid == 6


def test_diffs_update_insert_delete() -> None:
    book = make_book()
    book.apply_diffs([R(10, 5, 8), R(9, 0, 8), R(7, 1, 8)], [R(11, 0, 8), R(14, 2, 8)], 8)
    assert list(book.bid_entries()) == [R(10, 5, 8), R(8, 3, 1), R(7, 1, 8)]
    assert list(book.ask_entries()) == [R(12, 2, 1), R(13, 3, 1), R(14, 2, 8)]
    assert book.last_diff_uid == 8
    assert book.snapshot_uid == 7
    assert book.get_price(True) == 12
    assert book.get_price(False) == 10


def test_diff_zero_amount_on_missing_level_is_noop() -> None:
    book = make_book()
    book.apply_diffs([R(1, 0, 8)], [R(99, 0, 8)], 8)
    assert len(list(book.bid_entries())) == 3
    assert len(list(book.ask_entries())) == 3


def test_diffs_on_empty_sides_keep_best() -> None:
    book = make_book()
    book.apply_diffs([], [], 9)
    assert book.last_diff_uid == 9
    assert book.get_price(True) == 11
    book.apply_diffs([R(10, 0, 10), R(9, 0, 10), R(8, 0, 10)], [], 10)
    assert list(book.bid_entries()) == []
    with pytest.raises(EnvironmentError):
        book.get_price(False)
    assert book.get_price(True) == 11


def test_apply_trade_sets_price_and_notifies() -> None:
    book = make_book()
    received: list[OrderBookTradeEvent] = []

    def listener(ev: Any) -> None:
        received.append(ev)

    book.add_listener(OrderBookEvent.TradeEvent, listener)
    assert book.get_listeners(OrderBookEvent.TradeEvent) == [listener]
    before_bids = list(book.bid_entries())
    before = time.perf_counter()
    trade = OrderBookTradeEvent("BTC-USDT", 1.0, TradeType.BUY, Decimal("100"), Decimal("1"))
    book.apply_trade(trade)
    assert received == [trade]
    assert book.last_trade_price == 100.0
    assert type(book.last_trade_price) is float
    assert book.last_applied_trade >= before
    assert list(book.bid_entries()) == before_bids

    book.remove_listener(OrderBookEvent.TradeEvent, listener)
    book.apply_trade(trade)
    assert received == [trade]


def test_apply_trade_without_listeners() -> None:
    book = OrderBook()
    book.apply_trade(OrderBookTradeEvent("X", 1.0, TradeType.SELL, Decimal("1"), Decimal("1")))
    assert book.last_trade_price == Decimal("1")


def test_trigger_event_delegates() -> None:
    book = OrderBook()
    got: list[Any] = []

    def listener(msg: Any) -> None:
        got.append(msg)

    book.add_listener(OrderBookEvent.OrderBookDataSourceUpdateEvent, listener)
    book.trigger_event(OrderBookEvent.OrderBookDataSourceUpdateEvent, "hi")
    assert got == ["hi"]


class _SpyHub:
    def __init__(self) -> None:
        self.log: list[tuple[str, Any]] = []

    def add_listener(self, event_tag: Enum, listener: Any) -> None:
        self.log.append(("add", event_tag))

    def remove_listener(self, event_tag: Enum, listener: Any) -> None:
        self.log.append(("remove", event_tag))

    def get_listeners(self, event_tag: Enum) -> list[Any]:
        self.log.append(("get", event_tag))
        return []

    def trigger_event(self, event_tag: Enum, message: Any) -> None:
        self.log.append(("trigger", message))


def test_injected_hub_is_used() -> None:
    hub = _SpyHub()
    book = OrderBook(event_hub=hub)

    def listener(_: Any) -> None:
        pass

    book.add_listener(OrderBookEvent.TradeEvent, listener)
    book.remove_listener(OrderBookEvent.TradeEvent, listener)
    assert book.get_listeners(OrderBookEvent.TradeEvent) == []
    trade = OrderBookTradeEvent("X", 1.0, TradeType.BUY, Decimal("2"), Decimal("1"))
    book.apply_trade(trade)
    assert hub.log == [
        ("add", OrderBookEvent.TradeEvent),
        ("remove", OrderBookEvent.TradeEvent),
        ("get", OrderBookEvent.TradeEvent),
        ("trigger", trade),
    ]


def test_books_do_not_share_default_hub() -> None:
    a, b = OrderBook(), OrderBook()
    got: list[Any] = []

    def listener(msg: Any) -> None:
        got.append(msg)

    a.add_listener(OrderBookEvent.TradeEvent, listener)
    b.apply_trade(OrderBookTradeEvent("X", 1.0, TradeType.BUY, Decimal("2"), Decimal("1")))
    assert got == []


def test_shared_hub_instance() -> None:
    hub = EventHub()
    a, b = OrderBook(event_hub=hub), OrderBook(event_hub=hub)
    got: list[Any] = []

    def listener(msg: Any) -> None:
        got.append(msg)

    a.add_listener(OrderBookEvent.TradeEvent, listener)
    trade = OrderBookTradeEvent("X", 1.0, TradeType.BUY, Decimal("2"), Decimal("1"))
    b.apply_trade(trade)
    assert got == [trade]


# -- simulate -----------------------------------------------------------------
def test_simulate_buy_partial_and_full() -> None:
    book = make_book()
    assert book.simulate_buy(2.5) == [R(11, 1, 1), R(12, 1.5, 1)]
    assert book.simulate_buy(1) == [R(11, 1.0, 1)]
    assert book.simulate_buy(100) == [R(11, 1, 1), R(12, 2, 1), R(13, 3, 1)]
    assert OrderBook().simulate_buy(1) == []


def test_simulate_sell_partial_and_full() -> None:
    book = make_book()
    assert book.simulate_sell(2.5) == [R(10, 1, 1), R(9, 1.5, 1)]
    assert book.simulate_sell(100) == [R(10, 1, 1), R(9, 2, 1), R(8, 3, 1)]
    assert OrderBook().simulate_sell(1) == []


# -- queries ------------------------------------------------------------------
def test_get_price_for_volume() -> None:
    book = make_book()
    res = book.get_price_for_volume(True, 2.5)
    assert math.isnan(res.query_price)
    assert (res.query_volume, res.result_price, res.result_volume) == (2.5, 12, 2.5)
    res = book.get_price_for_volume(False, 2.5)
    assert (res.result_price, res.result_volume) == (9, 2.5)
    res = book.get_price_for_volume(True, 100)
    assert math.isnan(res.result_price)
    assert res.result_volume == 6
    assert res.query_volume == 100


def test_get_vwap_for_volume() -> None:
    book = make_book()
    res = book.get_vwap_for_volume(True, 2)
    assert math.isnan(res.query_price)
    assert (res.query_volume, res.result_price, res.result_volume) == (2, 11.5, 2)
    res = book.get_vwap_for_volume(False, 2)
    assert (res.result_price, res.result_volume) == (9.5, 2)
    res = book.get_vwap_for_volume(True, 100)
    assert math.isnan(res.result_price)
    assert res.result_volume == 6


def test_get_price_for_quote_volume() -> None:
    book = make_book()
    res = book.get_price_for_quote_volume(True, 20)
    assert math.isnan(res.query_price)
    assert (res.query_volume, res.result_price, res.result_volume) == (20, 12, 20)
    res = book.get_price_for_quote_volume(False, 15)
    assert (res.result_price, res.result_volume) == (9, 15)
    res = book.get_price_for_quote_volume(True, 1000)
    assert math.isnan(res.result_price)
    assert res.result_volume == 74


def test_get_quote_volume_for_base_amount() -> None:
    book = make_book()
    res = book.get_quote_volume_for_base_amount(True, 2)
    assert math.isnan(res.query_price)
    assert math.isnan(res.result_price)
    assert (res.query_volume, res.result_volume) == (2, 23)
    assert book.get_quote_volume_for_base_amount(False, 2).result_volume == 19
    assert book.get_quote_volume_for_base_amount(True, 100).result_volume == 74
    assert OrderBook().get_quote_volume_for_base_amount(True, 1).result_volume == 0


def test_get_volume_for_price() -> None:
    book = make_book()
    res = book.get_volume_for_price(True, 12)
    assert math.isnan(res.query_volume)
    assert (res.query_price, res.result_price, res.result_volume) == (12, 12, 3)
    res = book.get_volume_for_price(True, 10)
    assert math.isnan(res.result_price)
    assert res.result_volume == 0
    res = book.get_volume_for_price(False, 9)
    assert (res.result_price, res.result_volume) == (9, 3)
    res = book.get_volume_for_price(False, 11)
    assert math.isnan(res.result_price)
    assert res.result_volume == 0


def test_get_quote_volume_for_price() -> None:
    book = make_book()
    res = book.get_quote_volume_for_price(True, 12)
    assert math.isnan(res.query_volume)
    assert (res.query_price, res.result_price, res.result_volume) == (12, 12, 35)
    res = book.get_quote_volume_for_price(False, 9)
    assert (res.result_price, res.result_volume) == (9, 28)
    res = book.get_quote_volume_for_price(True, 1)
    assert math.isnan(res.result_price)
    assert res.result_volume == 0
    assert book.get_quote_volume_for_price(False, 100).result_volume == 0


def test_price_queries_consuming_whole_side() -> None:
    book = make_book()
    assert book.get_volume_for_price(True, 100).result_volume == 6
    assert book.get_volume_for_price(False, 0).result_volume == 6
    assert book.get_quote_volume_for_price(True, 100).result_volume == 74
    assert (
        book.get_quote_volume_for_price(False, 0).result_volume == 74 - 11 - 24 - 39 + 10 + 18 + 24
    )


def test_dex_snapshot_with_one_empty_side() -> None:
    book = OrderBook(dex=True)
    book.apply_snapshot([R(1, 1, 1)], [], 1)
    assert book.get_price(False) == 1
    with pytest.raises(EnvironmentError):
        book.get_price(True)
    book.apply_snapshot([], [R(2, 1, 1)], 2)
    assert book.get_price(True) == 2
    with pytest.raises(EnvironmentError):
        book.get_price(False)


# -- restore ------------------------------------------------------------------
def _msg(kind: OrderBookMessageType, uid: int, bids: Any, asks: Any, ts: float) -> OrderBookMessage:
    content = {"trading_pair": "BTC-USDT", "update_id": uid, "bids": bids, "asks": asks}
    return OrderBookMessage(kind, content, ts)


@pytest.mark.divergence  # core's __lt__ puts every snapshot/diff first, so it replays stale diffs
def test_restore_from_snapshot_and_diffs() -> None:
    snap = _msg(OrderBookMessageType.SNAPSHOT, 10, [["10", "1"], ["9", "2"]], [["11", "1"]], 1.0)
    diffs = [
        _msg(OrderBookMessageType.DIFF, 9, [["9", "0"]], [["11", "5"]], 0.5),  # stale
        _msg(OrderBookMessageType.DIFF, 10, [["10", "7"]], [], 1.0),  # stale (<=)
        _msg(OrderBookMessageType.DIFF, 11, [["10", "0"]], [["12", "4"]], 2.0),
        _msg(OrderBookMessageType.DIFF, 12, [["8", "1"]], [["11", "0"]], 3.0),
    ]
    book = OrderBook()
    book.restore_from_snapshot_and_diffs(snap, diffs)
    assert book.snapshot_uid == 10
    assert book.last_diff_uid == 12
    assert list(book.bid_entries()) == [R(9, 2, 10), R(8, 1, 12)]
    assert list(book.ask_entries()) == [R(12, 4, 11)]


def test_restore_without_diffs() -> None:
    snap = _msg(OrderBookMessageType.SNAPSHOT, 10, [["10", "1"]], [["11", "1"]], 1.0)
    book = OrderBook()
    book.restore_from_snapshot_and_diffs(snap, [])
    assert book.snapshot_uid == 10
    assert book.last_diff_uid == 0
    assert list(book.bid_entries()) == [R(10, 1, 10)]
