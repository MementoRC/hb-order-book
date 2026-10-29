"""Contract edges shared with hummingbot core: duplicates, NaN, truncation ties, empty sides."""

import math

import pytest

from order_book.core import OrderBook, OrderBookRow

R = OrderBookRow


def test_snapshot_duplicate_price_first_wins() -> None:
    # core: std::set::insert is a no-op when the price is already present.
    book = OrderBook()
    book.apply_snapshot(
        [R(10, 1, 1), R(9, 2, 1), R(10, 5, 2)],
        [R(11, 1, 1), R(12, 2, 1), R(11, 7, 3)],
        7,
    )
    assert list(book.bid_entries()) == [R(10, 1, 1), R(9, 2, 1)]
    assert list(book.ask_entries()) == [R(11, 1, 1), R(12, 2, 1)]
    assert book.get_price(False) == 10
    assert book.get_price(True) == 11


def test_snapshot_best_price_tracking_sees_duplicates() -> None:
    # core updates the best price from every row, duplicates included.
    book = OrderBook()
    book.apply_snapshot([R(10, 1, 1), R(10, 5, 2)], [R(11, 1, 1), R(11, 5, 2)], 1)
    assert book.get_price(False) == 10
    assert book.get_price(True) == 11


def test_diff_duplicate_price_last_wins() -> None:
    # core erases then inserts for each diff row, so the last row stays.
    book = OrderBook()
    book.apply_diffs([R(10, 1, 1), R(10, 5, 2)], [R(11, 1, 1), R(11, 7, 3)], 3)
    assert list(book.bid_entries()) == [R(10, 5, 2)]
    assert list(book.ask_entries()) == [R(11, 7, 3)]


def test_negative_zero_and_zero_are_one_level() -> None:
    book = OrderBook()
    book.apply_snapshot([R(0.0, 1, 1), R(-0.0, 5, 2)], [], 1)
    assert list(book.bid_entries()) == [R(0.0, 1, 1)]
    book.apply_diffs([R(-0.0, 0, 3)], [], 2)
    assert list(book.bid_entries()) == []


def test_nan_price_rejected_in_snapshot_and_diffs() -> None:
    nan = float("nan")
    book = OrderBook()
    with pytest.raises(ValueError, match="NaN"):
        book.apply_snapshot([R(nan, 1, 1)], [], 1)
    with pytest.raises(ValueError, match="NaN"):
        book.apply_snapshot([], [R(nan, 1, 1)], 1)
    with pytest.raises(ValueError, match="NaN"):
        book.apply_diffs([R(nan, 1, 1)], [], 1)
    with pytest.raises(ValueError, match="NaN"):
        book.apply_diffs([], [R(nan, 1, 1)], 1)


def test_nan_price_rejected_in_numpy_paths() -> None:
    np = pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    nan_rows = np.array([[float("nan"), 1.0, 1.0]])
    no_rows = np.empty((0, 3))
    book = OrderBook()
    with pytest.raises(ValueError, match="NaN"):
        book.apply_numpy_snapshot(nan_rows, no_rows)
    with pytest.raises(ValueError, match="NaN"):
        book.apply_numpy_diffs(no_rows, nan_rows)


def test_vwap_for_zero_volume() -> None:
    # Core's Cython (no cdivision directive) divides 0.0 / 0.0 and raises ZeroDivisionError;
    # the package matches. An empty side never reaches the division and returns NaN.
    book = OrderBook()
    book.apply_snapshot([R(10, 1, 1)], [R(11, 1, 1)], 1)
    with pytest.raises(ZeroDivisionError):
        book.get_vwap_for_volume(True, 0)
    with pytest.raises(ZeroDivisionError):
        book.get_vwap_for_volume(False, 0)
    assert math.isnan(OrderBook().get_vwap_for_volume(True, 0).result_price)


def test_diff_cex_tie_erases_bid() -> None:
    # Crossed with equal update_id: bid.update_id > ask.update_id is False, so the bid goes.
    book = OrderBook()
    book.apply_snapshot([R(5, 1, 1), R(3, 1, 1)], [R(11, 1, 1)], 1)
    book.apply_diffs([], [R(4, 1, 1)], 2)
    assert list(book.bid_entries()) == [R(3, 1, 1)]
    assert list(book.ask_entries()) == [R(4, 1, 1), R(11, 1, 1)]
    assert book.get_price(False) == 3


def test_diff_dex_tie_erases_bid() -> None:
    book = OrderBook(dex=True)
    book.apply_snapshot([R(5, 2, 1), R(3, 1, 1)], [R(11, 1, 1)], 1)
    book.apply_diffs([], [R(5, 2, 1)], 2)  # notional 10 == 10
    assert list(book.bid_entries()) == [R(3, 1, 1)]
    assert list(book.ask_entries()) == [R(5, 2, 1), R(11, 1, 1)]


def test_truncation_emptying_a_side_keeps_cached_best_price() -> None:
    # core's apply_diffs only refreshes the best price of a non-empty side.
    book = OrderBook()
    book.apply_snapshot([R(5, 1, 1)], [R(11, 1, 1)], 1)
    book.apply_diffs([], [R(4, 1, 1)], 2)
    assert list(book.bid_entries()) == []
    assert book._best_bid == 5
    assert book.get_price(True) == 4
    with pytest.raises(OSError, match="empty"):
        book.get_price(False)
