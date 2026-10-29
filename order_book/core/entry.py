"""Order book entry, sorted price-level container and crossed-book truncation."""

from bisect import bisect_left
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
    Iteration reuses an immutable sorted tuple that every mutation invalidates.
    """

    __slots__ = ("_cache", "_entries", "_prices", "_sorted_entries")

    def __init__(self) -> None:
        self._entries: dict[float, OrderBookEntry] = {}
        self._prices: list[float] = []
        self._sorted_entries: list[OrderBookEntry] = []  # parallel to ``_prices``
        self._cache: tuple[OrderBookEntry, ...] | None = None

    def insert(self, entry: OrderBookEntry) -> None:
        """Insert ``entry``, replacing any existing entry at the same price.

        Raises ValueError for a NaN price (it breaks the bisect/dict pairing; core is undefined).
        """
        if isnan(entry.price):
            raise ValueError("NaN price is not allowed in PriceLevels")
        index = bisect_left(self._prices, entry.price)
        if entry.price in self._entries:
            self._sorted_entries[index] = entry
        else:
            self._prices.insert(index, entry.price)
            self._sorted_entries.insert(index, entry)
        self._entries[entry.price] = entry
        self._cache = None

    def insert_if_absent(self, entry: OrderBookEntry) -> None:
        """Insert ``entry`` unless its price is already present (``std::set::insert``)."""
        if entry.price not in self._entries:
            self.insert(entry)

    def remove(self, price: float) -> bool:
        """Remove the entry at ``price``; return False if there was none."""
        if price not in self._entries:
            return False
        del self._entries[price]
        index = bisect_left(self._prices, price)
        del self._prices[index]
        del self._sorted_entries[index]
        self._cache = None
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
        self._sorted_entries.clear()
        self._cache = None

    def min(self) -> OrderBookEntry:
        """Entry with the lowest price (best ask). Raises ValueError when empty."""
        if not self._prices:
            raise ValueError("PriceLevels is empty")
        return self._sorted_entries[0]

    def max(self) -> OrderBookEntry:
        """Entry with the highest price (best bid). Raises ValueError when empty."""
        if not self._prices:
            raise ValueError("PriceLevels is empty")
        return self._sorted_entries[-1]

    def _sorted(self) -> tuple[OrderBookEntry, ...]:
        """Immutable ascending entries, rebuilt lazily after a mutation."""
        if self._cache is None:
            self._cache = tuple(self._sorted_entries)
        return self._cache

    def ascending(self) -> Iterator[OrderBookEntry]:
        """Iterate entries from lowest to highest price (snapshot of current entries)."""
        return iter(self._sorted())

    def descending(self) -> Iterator[OrderBookEntry]:
        """Iterate entries from highest to lowest price (snapshot of current entries)."""
        return reversed(self._sorted())

    def replace_all(self, entries: Iterable[OrderBookEntry]) -> None:
        """Replace the whole content with ``entries`` (first duplicate wins, like a set).

        Built in bulk (dedupe, then one sort). Raises ValueError for a NaN price.
        """
        unique: dict[float, OrderBookEntry] = {}
        for entry in entries:
            if isnan(entry.price):
                raise ValueError("NaN price is not allowed in PriceLevels")
            if entry.price not in unique:
                unique[entry.price] = entry
        self._entries = unique
        self._prices = sorted(unique)
        self._sorted_entries = list(map(unique.__getitem__, self._prices))
        self._cache = None


def truncate_overlap_entries(bids: PriceLevels, asks: PriceLevels, dex: bool) -> None:
    """Resolve a crossed book (top bid >= top ask) in place, mirroring the C++ core.

    Centralised (``dex=False``): the entry with the larger ``update_id`` wins;
    ties (``bid.update_id <= ask.update_id``) erase the bid.
    DEX (``dex=True``): the entry with the larger notional (``amount * price``)
    wins; ties erase the bid.
    """
    bid_prices = bids._prices
    ask_prices = asks._prices
    if not bid_prices or not ask_prices or bid_prices[-1] < ask_prices[0]:
        return  # not crossed: nothing to do
    bid_entries = bids._sorted_entries
    ask_entries = asks._sorted_entries
    ask_cut = 0  # asks erased from the front; removed from the lists in one slice
    while bid_prices and ask_cut < len(ask_prices):
        top_bid = bid_entries[-1]
        top_ask = ask_entries[ask_cut]
        if top_bid.price < top_ask.price:
            break
        if dex:
            bid_wins = top_bid.amount * top_bid.price > top_ask.amount * top_ask.price
        else:
            bid_wins = top_bid.update_id > top_ask.update_id
        if bid_wins:
            del asks._entries[top_ask.price]
            ask_cut += 1
        else:
            del bids._entries[top_bid.price]
            bid_prices.pop()
            bid_entries.pop()
            bids._cache = None
    if ask_cut:
        del ask_prices[:ask_cut]
        del ask_entries[:ask_cut]
        asks._cache = None
