"""Tests for OrderBookEntry, PriceLevels and truncate_overlap_entries."""

import dataclasses

import pytest

from order_book.core.entry import OrderBookEntry, PriceLevels, truncate_overlap_entries


def levels(*rows: tuple[float, float, int]) -> PriceLevels:
    result = PriceLevels()
    for price, amount, update_id in rows:
        result.insert(OrderBookEntry(price, amount, update_id))
    return result


def rows(side: PriceLevels) -> list[tuple[float, float, int]]:
    return [(e.price, e.amount, e.update_id) for e in side.ascending()]


class TestEntry:
    def test_ordering_by_price_only(self) -> None:
        a = OrderBookEntry(1.0, 100.0, 9)
        b = OrderBookEntry(2.0, 1.0, 1)
        assert a < b
        assert a <= b
        assert b > a
        assert b >= a
        assert not b < a
        assert not b <= a
        assert not a > b
        assert not a >= b

    def test_same_price_orders_equivalent_but_not_equal(self) -> None:
        a = OrderBookEntry(1.0, 1.0, 1)
        b = OrderBookEntry(1.0, 2.0, 2)
        assert a <= b
        assert a >= b
        assert not a < b
        assert not a > b
        assert a != b
        assert a == OrderBookEntry(1.0, 1.0, 1)

    def test_comparison_with_other_type_unsupported(self) -> None:
        a = OrderBookEntry(1.0, 1.0, 1)
        with pytest.raises(TypeError):
            _ = a < 1  # type: ignore[operator]
        with pytest.raises(TypeError):
            _ = a <= 1  # type: ignore[operator]
        with pytest.raises(TypeError):
            _ = a > 1  # type: ignore[operator]
        with pytest.raises(TypeError):
            _ = a >= 1  # type: ignore[operator]

    def test_frozen(self) -> None:
        a = OrderBookEntry(1.0, 1.0, 1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.price = 2.0  # type: ignore[misc]


class TestPriceLevels:
    def test_empty(self) -> None:
        p = PriceLevels()
        assert len(p) == 0
        assert not p
        assert 1.0 not in p
        assert p.get(1.0) is None
        assert list(p.ascending()) == []
        assert list(p.descending()) == []
        with pytest.raises(ValueError, match="empty"):
            p.min()
        with pytest.raises(ValueError, match="empty"):
            p.max()

    def test_insert_sorted_and_min_max(self) -> None:
        p = levels((3.0, 1.0, 1), (1.0, 1.0, 2), (2.0, 1.0, 3))
        assert len(p) == 3
        assert p
        assert [e.price for e in p.ascending()] == [1.0, 2.0, 3.0]
        assert [e.price for e in p.descending()] == [3.0, 2.0, 1.0]
        assert p.min().price == 1.0
        assert p.max().price == 3.0
        assert 2.0 in p
        assert p.get(2.0) == OrderBookEntry(2.0, 1.0, 3)

    def test_insert_replaces_same_price(self) -> None:
        p = levels((1.0, 1.0, 1), (2.0, 1.0, 2))
        p.insert(OrderBookEntry(1.0, 5.0, 7))
        assert len(p) == 2
        assert rows(p) == [(1.0, 5.0, 7), (2.0, 1.0, 2)]

    def test_remove(self) -> None:
        p = levels((1.0, 1.0, 1), (2.0, 1.0, 2))
        assert p.remove(1.0) is True
        assert rows(p) == [(2.0, 1.0, 2)]
        assert 1.0 not in p

    def test_remove_missing(self) -> None:
        p = levels((1.0, 1.0, 1))
        assert p.remove(9.0) is False
        assert len(p) == 1

    def test_clear(self) -> None:
        p = levels((1.0, 1.0, 1))
        p.clear()
        assert len(p) == 0
        assert not p
        assert 1.0 not in p

    def test_replace_all(self) -> None:
        p = levels((9.0, 1.0, 1))
        p.replace_all(
            [
                OrderBookEntry(2.0, 1.0, 1),
                OrderBookEntry(1.0, 1.0, 1),
                OrderBookEntry(2.0, 3.0, 2),
            ]
        )
        assert rows(p) == [(1.0, 1.0, 1), (2.0, 3.0, 2)]
        assert 9.0 not in p

    def test_iteration_tolerates_mutation(self) -> None:
        p = levels((1.0, 1.0, 1), (2.0, 1.0, 2), (3.0, 1.0, 3))
        seen = []
        for e in p.descending():
            seen.append(e.price)
            p.remove(e.price)
        assert seen == [3.0, 2.0, 1.0]
        assert not p


class TestTruncate:
    def test_no_overlap_noop(self) -> None:
        bids = levels((1.0, 1.0, 1), (2.0, 1.0, 2))
        asks = levels((3.0, 1.0, 1))
        for dex in (False, True):
            truncate_overlap_entries(bids, asks, dex)
        assert len(bids) == 2
        assert len(asks) == 1

    def test_empty_sides(self) -> None:
        bids = levels((1.0, 1.0, 1))
        asks = PriceLevels()
        truncate_overlap_entries(bids, asks, False)
        truncate_overlap_entries(asks, bids, True)
        truncate_overlap_entries(PriceLevels(), PriceLevels(), True)
        assert len(bids) == 1

    def test_cex_bid_newer_removes_ask(self) -> None:
        bids = levels((5.0, 1.0, 3))
        asks = levels((4.0, 1.0, 2), (6.0, 1.0, 1))
        truncate_overlap_entries(bids, asks, False)
        assert len(bids) == 1
        assert rows(asks) == [(6.0, 1.0, 1)]

    def test_cex_ask_newer_removes_bid(self) -> None:
        bids = levels((5.0, 1.0, 1), (3.0, 1.0, 1))
        asks = levels((4.0, 1.0, 2))
        truncate_overlap_entries(bids, asks, False)
        assert rows(bids) == [(3.0, 1.0, 1)]
        assert len(asks) == 1

    def test_cex_tie_removes_bid(self) -> None:
        bids = levels((5.0, 1.0, 2), (3.0, 1.0, 1))
        asks = levels((4.0, 1.0, 2))
        truncate_overlap_entries(bids, asks, False)
        assert rows(bids) == [(3.0, 1.0, 1)]
        assert len(asks) == 1

    def test_cex_equal_price_crosses(self) -> None:
        bids = levels((4.0, 1.0, 2))
        asks = levels((4.0, 1.0, 2))
        truncate_overlap_entries(bids, asks, False)
        assert not bids
        assert len(asks) == 1

    def test_dex_larger_notional_wins(self) -> None:
        bids = levels((5.0, 1.0, 1))
        asks = levels((4.0, 1.0, 9))
        truncate_overlap_entries(bids, asks, True)
        assert len(bids) == 1
        assert not asks

    def test_dex_smaller_notional_loses(self) -> None:
        bids = levels((5.0, 0.1, 9), (3.0, 1.0, 9))
        asks = levels((4.0, 1.0, 1))
        truncate_overlap_entries(bids, asks, True)
        assert rows(bids) == [(3.0, 1.0, 9)]
        assert len(asks) == 1

    def test_dex_tie_removes_bid(self) -> None:
        bids = levels((4.0, 2.0, 9))
        asks = levels((4.0, 2.0, 1))
        truncate_overlap_entries(bids, asks, True)
        assert not bids
        assert len(asks) == 1

    def test_multi_level_cascade(self) -> None:
        bids = levels((100.0, 1.0, 1), (99.0, 1.0, 5), (90.0, 1.0, 1))
        asks = levels((98.0, 1.0, 4), (99.5, 1.0, 2), (120.0, 1.0, 1))
        truncate_overlap_entries(bids, asks, False)
        # bid100(1) vs ask98(4): bid removed; bid99(5) vs ask98(4): ask removed;
        # bid99(5) vs ask99.5: no cross.
        assert rows(bids) == [(90.0, 1.0, 1), (99.0, 1.0, 5)]
        assert rows(asks) == [(99.5, 1.0, 2), (120.0, 1.0, 1)]

    def test_core_scenario_cex(self) -> None:
        bids = levels((1.0, 1.0, 1), (2.0, 1.0, 2), (3.0, 1.0, 3))
        asks = levels((4.0, 1.0, 1), (5.0, 1.0, 2), (6.0, 1.0, 3), (7.0, 1.0, 4))
        truncate_overlap_entries(bids, asks, False)
        assert bids.max() == OrderBookEntry(3.0, 1.0, 3)
        assert asks.min() == OrderBookEntry(4.0, 1.0, 1)

        asks.insert(OrderBookEntry(2.0, 0.1, 5))
        bids.insert(OrderBookEntry(50.0, 0.01, 6))
        truncate_overlap_entries(bids, asks, False)
        assert bids.max() == OrderBookEntry(50.0, 0.01, 6)
        assert len(asks) == 0

    def test_core_scenario_dex(self) -> None:
        bids = levels((1.0, 1.0, 1), (2.0, 1.0, 2), (3.0, 1.0, 3), (50.0, 0.01, 4))
        asks = levels((4.0, 1.0, 1), (5.0, 1.0, 2), (6.0, 1.0, 3), (7.0, 1.0, 4))
        truncate_overlap_entries(bids, asks, True)
        assert bids.max() == OrderBookEntry(3.0, 1.0, 3)
        assert asks.min() == OrderBookEntry(4.0, 1.0, 1)

        asks.insert(OrderBookEntry(2.0, 0.1, 5))
        bids.insert(OrderBookEntry(3.5, 1.0, 5))
        truncate_overlap_entries(bids, asks, True)
        assert bids.max() == OrderBookEntry(3.5, 1.0, 5)
        assert asks.min() == OrderBookEntry(4.0, 1.0, 1)

    def test_cpp_testoverlappingorderbooks(self) -> None:
        bids = PriceLevels()
        asks = PriceLevels()
        for p, a, u in [(100.0, 1.0, 1), (99.9, 2.0, 1), (99.8, 4.0, 1)]:
            bids.insert(OrderBookEntry(p, a, u))
        truncate_overlap_entries(bids, asks, False)
        assert bids.max().price == 100.0
        assert not asks

        for p, a, u in [(100.0, 4.0, 2), (100.1, 2.0, 2), (100.9, 1.5, 2), (101.0, 0.1, 2)]:
            bids.insert(OrderBookEntry(p, a, u))
        for p, a, u in [
            (105.0, 100.0, 2),
            (104.0, 50.0, 2),
            (103.0, 20.0, 3),
            (102.0, 10.0, 3),
            (100.91, 1.0, 3),
        ]:
            asks.insert(OrderBookEntry(p, a, u))
        truncate_overlap_entries(bids, asks, False)
        # bid101(2) loses to ask100.91(3); bid100.9 < 100.91 ends the cascade.
        assert bids.max().price == 100.9
        assert asks.min().price == 100.91

        bids.insert(OrderBookEntry(100.91, 3.0, 3))
        for p, a, u in [(100.89, 1.0, 4), (100.88, 0.8, 4), (100.86, 0.7, 4)]:
            asks.insert(OrderBookEntry(p, a, u))
        bids.insert(OrderBookEntry(100.87, 1.1, 5))
        truncate_overlap_entries(bids, asks, False)
        assert bids.max().price < asks.min().price
