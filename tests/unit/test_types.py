from decimal import Decimal

import pytest

from order_book.core.types import (
    ClientOrderBookQueryResult,
    ClientOrderBookRow,
    OrderBookQueryResult,
    OrderBookRow,
)


def test_order_book_row_fields() -> None:
    row = OrderBookRow(1.5, 2.5, 3)
    assert row._fields == ("price", "amount", "update_id")
    assert tuple(row) == (1.5, 2.5, 3)


def test_client_order_book_row_fields() -> None:
    row = ClientOrderBookRow(Decimal("1.5"), Decimal("2.5"), 3)
    assert row._fields == ("price", "amount", "update_id")
    assert row.price == Decimal("1.5")
    assert row.update_id == 3


def test_query_result_positional_construction() -> None:
    res = OrderBookQueryResult(1.0, 2.0, 3.0, 4.0)
    assert (res.query_price, res.query_volume, res.result_price, res.result_volume) == (
        1.0,
        2.0,
        3.0,
        4.0,
    )


def test_client_query_result_positional_construction() -> None:
    d = [Decimal(i) for i in range(4)]
    res = ClientOrderBookQueryResult(*d)
    assert (res.query_price, res.query_volume, res.result_price, res.result_volume) == tuple(d)


def test_query_results_use_slots() -> None:
    res = OrderBookQueryResult(1.0, 2.0, 3.0, 4.0)
    with pytest.raises(AttributeError):
        res.extra = 1  # type: ignore[attr-defined]
    res.result_price = 9.0
    assert res.result_price == 9.0
