"""Pure-Python L2 order book (contract port of ``hummingbot.core.data_type.order_book``)."""

import logging
import time
from bisect import bisect_right
from collections.abc import Iterator
from enum import Enum
from typing import Any

from order_book.core._hub import EventHub
from order_book.core.entry import OrderBookEntry, PriceLevels, truncate_overlap_entries
from order_book.core.events import OrderBookEvent, OrderBookTradeEvent
from order_book.core.message import OrderBookMessage
from order_book.core.ports import EventPort, EventSubscriber
from order_book.core.types import OrderBookQueryResult, OrderBookRow

NaN = float("nan")


def _entries(rows: list[OrderBookRow]) -> list[OrderBookEntry]:
    return [OrderBookEntry(row.price, row.amount, row.update_id) for row in rows]


def _row(entry: OrderBookEntry) -> OrderBookRow:
    return OrderBookRow(entry.price, entry.amount, entry.update_id)


class OrderBook:
    ORDER_BOOK_TRADE_EVENT_TAG = OrderBookEvent.TradeEvent.value

    @classmethod
    def logger(cls) -> logging.Logger:
        return logging.getLogger(__name__)

    def __init__(self, dex: bool = False, *, event_hub: EventPort | None = None) -> None:
        self._hub: EventPort = event_hub if event_hub is not None else EventHub()
        self._bid_book = PriceLevels()
        self._ask_book = PriceLevels()
        self._snapshot_uid = 0
        self._last_diff_uid = 0
        self._best_bid = self._best_ask = NaN
        self._last_trade_price = NaN
        self._last_applied_trade = -1000.0
        self._last_trade_price_rest_updated: float = -1000
        self._dex = dex

    # -- EventPort delegation -------------------------------------------------
    def add_listener(self, event_tag: Enum, listener: EventSubscriber) -> None:
        self._hub.add_listener(event_tag, listener)

    def remove_listener(self, event_tag: Enum, listener: EventSubscriber) -> None:
        self._hub.remove_listener(event_tag, listener)

    def get_listeners(self, event_tag: Enum) -> list[EventSubscriber]:
        return self._hub.get_listeners(event_tag)

    def trigger_event(self, event_tag: Enum, message: Any) -> None:
        self._hub.trigger_event(event_tag, message)

    # -- state properties -----------------------------------------------------
    @property
    def last_trade_price(self) -> float:
        return self._last_trade_price

    @last_trade_price.setter
    def last_trade_price(self, value: float) -> None:
        self._last_trade_price = value

    @property
    def last_applied_trade(self) -> float:
        return self._last_applied_trade

    @property
    def last_trade_price_rest_updated(self) -> float:
        return self._last_trade_price_rest_updated

    @last_trade_price_rest_updated.setter
    def last_trade_price_rest_updated(self, value: float) -> None:
        self._last_trade_price_rest_updated = value

    @property
    def snapshot_uid(self) -> int:
        return self._snapshot_uid

    @property
    def last_diff_uid(self) -> int:
        return self._last_diff_uid

    # -- mutation -------------------------------------------------------------
    def apply_snapshot(
        self, bids: list[OrderBookRow], asks: list[OrderBookRow], update_id: int
    ) -> None:
        best_bid = best_ask = NaN
        self._bid_book.clear()
        self._ask_book.clear()
        for bid in _entries(bids):
            self._bid_book.insert(bid)
            if not (bid.price <= best_bid):
                best_bid = bid.price
        for ask in _entries(asks):
            self._ask_book.insert(ask)
            if not (ask.price >= best_ask):
                best_ask = ask.price

        if self._dex:
            truncate_overlap_entries(self._bid_book, self._ask_book, self._dex)
            if self._bid_book:
                best_bid = self._bid_book.max().price
            if self._ask_book:
                best_ask = self._ask_book.min().price

        self._best_bid = best_bid
        self._best_ask = best_ask
        self._snapshot_uid = update_id

    def apply_diffs(
        self, bids: list[OrderBookRow], asks: list[OrderBookRow], update_id: int
    ) -> None:
        # Diffs with 0 amounts mean deletion.
        for bid in _entries(bids):
            self._bid_book.remove(bid.price)
            if bid.amount > 0:
                self._bid_book.insert(bid)
        for ask in _entries(asks):
            self._ask_book.remove(ask.price)
            if ask.amount > 0:
                self._ask_book.insert(ask)

        truncate_overlap_entries(self._bid_book, self._ask_book, self._dex)

        if self._bid_book:
            self._best_bid = self._bid_book.max().price
        if self._ask_book:
            self._best_ask = self._ask_book.min().price

        self._last_diff_uid = update_id

    def apply_trade(self, trade: OrderBookTradeEvent) -> None:
        self._last_trade_price = trade.price  # type: ignore[assignment]
        self._last_applied_trade = time.perf_counter()
        self._hub.trigger_event(OrderBookEvent.TradeEvent, trade)

    def restore_from_snapshot_and_diffs(
        self, snapshot: OrderBookMessage, diffs: list[OrderBookMessage]
    ) -> None:
        replay_position = bisect_right(diffs, snapshot)
        replay_diffs = diffs[replay_position:]
        self.apply_snapshot(snapshot.bids, snapshot.asks, snapshot.update_id)
        for diff in replay_diffs:
            self.apply_diffs(diff.bids, diff.asks, diff.update_id)

    # -- iteration and simulation --------------------------------------------
    def bid_entries(self) -> Iterator[OrderBookRow]:
        return (_row(entry) for entry in self._bid_book.descending())

    def ask_entries(self) -> Iterator[OrderBookRow]:
        return (_row(entry) for entry in self._ask_book.ascending())

    @staticmethod
    def _simulate(rows: Iterator[OrderBookRow], amount: float) -> list[OrderBookRow]:
        amount_left = amount
        result: list[OrderBookRow] = []
        for row in rows:
            if row.amount < amount_left:
                result.append(row)
                amount_left -= row.amount
            else:
                result.append(OrderBookRow(row.price, amount_left, row.update_id))
                break
        return result

    def simulate_buy(self, amount: float) -> list[OrderBookRow]:
        return self._simulate(self.ask_entries(), amount)

    def simulate_sell(self, amount: float) -> list[OrderBookRow]:
        return self._simulate(self.bid_entries(), amount)

    # -- queries --------------------------------------------------------------
    def _side(self, is_buy: bool) -> Iterator[OrderBookRow]:
        return self.ask_entries() if is_buy else self.bid_entries()

    def get_price(self, is_buy: bool) -> float:
        book = self._ask_book if is_buy else self._bid_book
        if len(book) < 1:
            raise OSError("Order book is empty - no price quote is possible.")
        return self._best_ask if is_buy else self._best_bid

    def get_price_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult:
        cumulative = 0.0
        result_price = NaN
        for row in self._side(is_buy):
            cumulative += row.amount
            if cumulative >= volume:
                result_price = row.price
                break
        return OrderBookQueryResult(NaN, volume, result_price, min(cumulative, volume))

    def get_vwap_for_volume(self, is_buy: bool, volume: float) -> OrderBookQueryResult:
        total_cost = 0.0
        total_volume = 0.0
        result_vwap = NaN
        for row in self._side(is_buy):
            total_cost += row.amount * row.price
            total_volume += row.amount
            if total_volume >= volume:
                total_cost -= row.amount * row.price
                total_volume -= row.amount
                incremental_amount = volume - total_volume
                total_cost += incremental_amount * row.price
                total_volume += incremental_amount
                result_vwap = total_cost / total_volume
                break
        return OrderBookQueryResult(NaN, volume, result_vwap, min(total_volume, volume))

    def get_price_for_quote_volume(self, is_buy: bool, quote_volume: float) -> OrderBookQueryResult:
        cumulative = 0.0
        result_price = NaN
        for row in self._side(is_buy):
            cumulative += row.amount * row.price
            if cumulative >= quote_volume:
                result_price = row.price
                break
        return OrderBookQueryResult(NaN, quote_volume, result_price, min(cumulative, quote_volume))

    def get_quote_volume_for_base_amount(
        self, is_buy: bool, base_amount: float
    ) -> OrderBookQueryResult:
        cumulative_volume = 0.0
        cumulative_base = 0.0
        for row in self._side(is_buy):
            row_amount = row.amount
            if row_amount + cumulative_base >= base_amount:
                row_amount = base_amount - cumulative_base
            cumulative_base += row_amount
            cumulative_volume += row_amount * row.price
            if cumulative_base >= base_amount:
                break
        return OrderBookQueryResult(NaN, base_amount, NaN, cumulative_volume)

    def get_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult:
        cumulative = 0.0
        result_price = NaN
        for row in self._side(is_buy):
            if (row.price > price) if is_buy else (row.price < price):
                break
            cumulative += row.amount
            result_price = row.price
        return OrderBookQueryResult(price, NaN, result_price, cumulative)

    def get_quote_volume_for_price(self, is_buy: bool, price: float) -> OrderBookQueryResult:
        cumulative = 0.0
        result_price = NaN
        for row in self._side(is_buy):
            if (row.price > price) if is_buy else (row.price < price):
                break
            cumulative += row.amount * row.price
            result_price = row.price
        return OrderBookQueryResult(price, NaN, result_price, cumulative)
