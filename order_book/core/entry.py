"""Order book entry, sorted price-level container and crossed-book truncation."""

from bisect import bisect_left, insort
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import isnan
from typing import Any


@dataclass(frozen=True, slots=True, order=False)
class OrderBookEntry:
    """A single price level.

    Ordering compares ``price`` only (mirrors the C++ ``operator<``), so book
    equivalence is by price. Equality (``==``) still compares all fields.
    """

    price: float
    amount: float
    update_id: int

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, OrderBookEntry):
            return NotImplemented
        return self.price < other.price

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, OrderBookEntry):
            return NotImplemented
        return self.price <= other.price

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, OrderBookEntry):
            return NotImplemented
        return self.price > other.price

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, OrderBookEntry):
            return NotImplemented
        return self.price >= other.price


class PriceLevels:
    """Sorted ``price -> OrderBookEntry`` container (replaces ``std::set<OrderBookEntry>``).

    Prices are matched by exact float equality. Position lookup is O(log n).
    """

    __slots__ = ("_entries", "_prices")

    def __init__(self) -> None:
        self._entries: dict[float, OrderBookEntry] = {}
        self._prices: list[float] = []

    def insert(self, entry: OrderBookEntry) -> None:
        """Insert ``entry``, replacing any existing entry at the same price.

        Raises ValueError for a NaN price (it breaks the bisect/dict pairing; core is undefined).
        """
        if isnan(entry.price):
            raise ValueError("NaN price is not allowed in PriceLevels")
        if entry.price not in self._entries:
            insort(self._prices, entry.price)
        self._entries[entry.price] = entry

    def insert_if_absent(self, entry: OrderBookEntry) -> None:
        """Insert ``entry`` unless its price is already present (``std::set::insert``)."""
        if entry.price not in self._entries:
            self.insert(entry)

    def remove(self, price: float) -> bool:
        """Remove the entry at ``price``; return False if there was none."""
        if price not in self._entries:
            return False
        del self._entries[price]
        del self._prices[bisect_left(self._prices, price)]
        return True

    def get(self, price: float) -> OrderBookEntry | None:
        return self._entries.get(price)

    def __contains__(self, price: object) -> bool:
        return price in self._entries

    def __len__(self) -> int:
        return len(self._prices)

    def __bool__(self) -> bool:
        return bool(self._prices)

    def clear(self) -> None:
        self._entries.clear()
        self._prices.clear()

    def min(self) -> OrderBookEntry:
        """Entry with the lowest price (best ask). Raises ValueError when empty."""
        if not self._prices:
            raise ValueError("PriceLevels is empty")
        return self._entries[self._prices[0]]

    def max(self) -> OrderBookEntry:
        """Entry with the highest price (best bid). Raises ValueError when empty."""
        if not self._prices:
            raise ValueError("PriceLevels is empty")
        return self._entries[self._prices[-1]]

    def ascending(self) -> Iterator[OrderBookEntry]:
        """Iterate entries from lowest to highest price (snapshot of current prices)."""
        return iter(tuple(self._entries[p] for p in self._prices))

    def descending(self) -> Iterator[OrderBookEntry]:
        """Iterate entries from highest to lowest price (snapshot of current entries)."""
        return iter(tuple(self._entries[p] for p in reversed(self._prices)))

    def replace_all(self, entries: Iterable[OrderBookEntry]) -> None:
        """Replace the whole content with ``entries`` (first duplicate wins, like a set)."""
        self.clear()
        for entry in entries:
            self.insert_if_absent(entry)


def truncate_overlap_entries(bids: PriceLevels, asks: PriceLevels, dex: bool) -> None:
    """Resolve a crossed book (top bid >= top ask) in place, mirroring the C++ core.

    Centralised (``dex=False``): the entry with the larger ``update_id`` wins;
    ties (``bid.update_id <= ask.update_id``) erase the bid.
    DEX (``dex=True``): the entry with the larger notional (``amount * price``)
    wins; ties erase the bid.
    """
    while bids and asks:
        top_bid = bids.max()
        top_ask = asks.min()
        if top_bid.price < top_ask.price:
            break
        if dex:
            bid_wins = top_bid.amount * top_bid.price > top_ask.amount * top_ask.price
        else:
            bid_wins = top_bid.update_id > top_ask.update_id
        if bid_wins:
            asks.remove(top_ask.price)
        else:
            bids.remove(top_bid.price)
