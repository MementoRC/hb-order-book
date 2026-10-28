"""Order book that nets recorded fills off the live book (port of ``CompositeOrderBook``)."""

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from order_book.core.entry import OrderBookEntry
from order_book.core.order_book import OrderBook
from order_book.core.ports import EventPort
from order_book.core.types import OrderBookRow


@runtime_checkable
class _Named(Protocol):
    @property
    def name(self) -> str: ...


@runtime_checkable
class OrderFillLike(Protocol):
    """Structural view of an order-fill event (no hummingbot import).

    ``trade_type`` only needs a ``name`` of ``"BUY"`` or ``"SELL"``, so any
    ``TradeType`` enum works.
    """

    @property
    def price(self) -> float: ...
    @property
    def amount(self) -> float: ...
    @property
    def timestamp(self) -> float: ...
    @property
    def trade_type(self) -> _Named: ...


class CompositeOrderBook(OrderBook):
    """Records fills and exposes the book with those fills netted off.

    Bid/ask entries are generators; as in the core, the traded book is pruned
    only when the generator is run to exhaustion (a partially consumed
    generator, e.g. via ``next()``, leaves the traded book untouched).
    """

    def __init__(
        self, order_book: OrderBook | None = None, *, event_hub: EventPort | None = None
    ) -> None:
        # ``order_book`` is accepted for signature parity with the core and ignored.
        super().__init__(event_hub=event_hub)
        self._traded_order_book = OrderBook()

    @property
    def traded_order_book(self) -> OrderBook:
        return self._traded_order_book

    def clear_traded_order_book(self) -> None:
        self._traded_order_book._bid_book.clear()
        self._traded_order_book._ask_book.clear()

    def record_filled_order(self, order_fill_event: OrderFillLike) -> None:
        price = float(order_fill_event.price)
        amount = float(order_fill_event.amount)
        update_id = int(order_fill_event.timestamp)
        side = order_fill_event.trade_type.name
        bids: list[OrderBookRow] = []
        asks: list[OrderBookRow] = []

        if side == "BUY":
            existing = self._traded_order_book._ask_book.get(price)
            if existing is not None:
                amount += existing.amount
            asks.append(OrderBookRow(price, amount, update_id))
        elif side == "SELL":
            existing = self._traded_order_book._bid_book.get(price)
            if existing is not None:
                amount += existing.amount
            bids.append(OrderBookRow(price, amount, update_id))

        self._traded_order_book.apply_diffs(bids, asks, update_id)

    def original_bid_entries(self) -> Iterator[OrderBookRow]:
        return super().bid_entries()

    def original_ask_entries(self) -> Iterator[OrderBookRow]:
        return super().ask_entries()

    def bid_entries(self) -> Iterator[OrderBookRow]:
        originals = list(self._bid_book.descending())
        traded = list(self._traded_order_book._bid_book.descending())
        changes: list[OrderBookRow] = []
        idx = 0
        for original in originals:
            while idx < len(traded):
                entry = traded[idx]
                if entry.price == original.price:
                    yield from self._netted(original, entry, changes)
                    idx += 1
                    break
                if entry.price > original.price:
                    changes.append(OrderBookRow(entry.price, 0, entry.update_id))
                    idx += 1
                else:
                    yield OrderBookRow(original.price, original.amount, original.update_id)
                    break
            else:
                yield OrderBookRow(original.price, original.amount, original.update_id)
        self._traded_order_book.apply_diffs(changes, [], self._last_diff_uid)

    def ask_entries(self) -> Iterator[OrderBookRow]:
        originals = list(self._ask_book.ascending())
        traded = list(self._traded_order_book._ask_book.ascending())
        changes: list[OrderBookRow] = []
        idx = 0
        for original in originals:
            while idx < len(traded):
                entry = traded[idx]
                if entry.price == original.price:
                    yield from self._netted(original, entry, changes)
                    idx += 1
                    break
                if entry.price > original.price:
                    yield OrderBookRow(original.price, original.amount, original.update_id)
                    break
                changes.append(OrderBookRow(entry.price, 0, entry.update_id))
                idx += 1
            else:
                yield OrderBookRow(original.price, original.amount, original.update_id)
        self._traded_order_book.apply_diffs([], changes, self._last_diff_uid)

    @staticmethod
    def _netted(
        original: OrderBookEntry, traded: OrderBookEntry, changes: list[OrderBookRow]
    ) -> Iterator[OrderBookRow]:
        composite = original.amount - traded.amount
        if composite > 0:
            yield OrderBookRow(original.price, composite, original.update_id)
        else:
            changes.append(
                OrderBookRow(original.price, min(original.amount, traded.amount), traded.update_id)
            )

    def get_price(self, is_buy: bool) -> float:
        book = self._ask_book if is_buy else self._bid_book
        if len(book) < 1:
            raise OSError("Order book is empty - no price quote is possible.")
        # Deviation: the core leaks StopIteration when every level is netted away.
        first = next(self._side(is_buy), None)
        if first is None:
            raise OSError("Order book is fully consumed - no price quote is possible.")
        return first.price
