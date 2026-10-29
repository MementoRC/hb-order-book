import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import order_book
from order_book import CompositeOrderBook, FramesOrderBookProtocol, OrderBook, OrderBookRow

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")


def _arrays() -> tuple["np.ndarray[Any, Any]", "np.ndarray[Any, Any]"]:
    bids = np.array([[1, 1, 1], [2, 1, 2], [3, 1, 3]], dtype=np.float64)
    asks = np.array([[4, 1, 1], [5, 1, 2], [6, 1, 3], [7, 1, 4]], dtype=np.float64)
    return bids, asks


def test_truncate_overlap_entries_dex() -> None:
    book = OrderBook(dex=True)
    bids_array = np.array([[1, 1, 1], [2, 1, 2], [3, 1, 3], [50, 0.01, 4]], dtype=np.float64)
    asks_array = np.array([[4, 1, 1], [5, 1, 2], [6, 1, 3], [7, 1, 4]], dtype=np.float64)
    book.apply_numpy_snapshot(bids_array, asks_array)
    bids, asks = book.snapshot
    assert bids.iloc[0].tolist() == [3.0, 1.0, 3.0]
    assert asks.iloc[0].tolist() == [4.0, 1.0, 1.0]

    book.apply_numpy_diffs(np.array([[3.5, 1, 5]]), np.array([[2, 0.1, 5]]))
    bids, asks = book.snapshot
    assert bids.iloc[0].tolist() == [3.5, 1.0, 5.0]
    assert asks.iloc[0].tolist() == [4.0, 1.0, 1.0]


def test_truncate_overlap_entries_cex() -> None:
    book = OrderBook(dex=False)
    bids_array, asks_array = _arrays()
    book.apply_numpy_snapshot(bids_array, asks_array)
    bids, asks = book.snapshot
    assert bids.iloc[0].tolist() == [3.0, 1.0, 3.0]
    assert asks.iloc[0].tolist() == [4.0, 1.0, 1.0]

    book.apply_numpy_diffs(np.array([[50, 0.01, 6]]), np.array([[2, 0.1, 5]]))
    bids, asks = book.snapshot
    assert (len(bids) and bids.iloc[0].tolist()) == [50.0, 0.01, 6.0]
    assert (len(asks) and asks.iloc[0].tolist()) == 0


def test_snapshot_columns_dtypes_and_order() -> None:
    book = OrderBook()
    bids_array, asks_array = _arrays()
    book.apply_numpy_snapshot(bids_array, asks_array)
    bids, asks = book.snapshot
    assert list(bids.columns) == ["price", "amount", "update_id"]
    assert list(asks.columns) == ["price", "amount", "update_id"]
    assert set(bids.dtypes) == {np.dtype("float64")}
    assert bids["price"].tolist() == [3.0, 2.0, 1.0]  # bids descending
    assert asks["price"].tolist() == [4.0, 5.0, 6.0, 7.0]  # asks ascending
    assert isinstance(bids.index, pd.RangeIndex)


def test_empty_snapshot_has_columns_and_dtypes() -> None:
    bids, asks = OrderBook().snapshot
    assert bids.empty
    assert asks.empty
    assert list(bids.columns) == ["price", "amount", "update_id"]
    assert set(asks.dtypes) == {np.dtype("float64")}


def test_numpy_update_id_is_max_row_id() -> None:
    book = OrderBook()
    bids_array, asks_array = _arrays()
    book.apply_numpy_snapshot(bids_array, asks_array)
    assert book.snapshot_uid == 4
    book.apply_numpy_diffs(np.array([[3.0, 2.0, 9.7]]), np.array([[4.0, 0.0, 7]]))
    assert book.last_diff_uid == 9  # row[2] is cast to int
    assert next(book.bid_entries()) == OrderBookRow(3.0, 2.0, 9)


def test_numpy_empty_arrays_update_id_zero() -> None:
    book = OrderBook()
    empty = np.empty((0, 3), dtype=np.float64)
    book.apply_numpy_snapshot(empty, empty)
    assert book.snapshot_uid == 0
    book.apply_numpy_diffs(empty, empty)
    assert book.last_diff_uid == 0


def test_apply_pandas_diffs() -> None:
    book = OrderBook()
    bids_array, asks_array = _arrays()
    book.apply_numpy_snapshot(bids_array, asks_array)
    columns = ["price", "amount", "update_id"]
    bids_df = pd.DataFrame([[3.0, 0.0, 8.0], [2.5, 4.0, 6.0]], columns=columns)
    asks_df = pd.DataFrame([[4.0, 3.0, 5.0]], columns=columns)
    book.apply_pandas_diffs(bids_df, asks_df)
    bids, asks = book.snapshot
    assert bids["price"].tolist() == [2.5, 2.0, 1.0]
    assert asks.iloc[0].tolist() == [4.0, 3.0, 5.0]
    assert book.last_diff_uid == 8


def test_composite_snapshot_uses_netted_entries() -> None:
    book = CompositeOrderBook()
    bids_array, asks_array = _arrays()
    book.apply_numpy_snapshot(bids_array, asks_array)
    buy = SimpleNamespace(
        price=4.0, amount=0.4, timestamp=10, trade_type=SimpleNamespace(name="BUY")
    )
    book.record_filled_order(buy)
    _, asks = book.snapshot
    assert asks.iloc[0].tolist() == [4.0, pytest.approx(0.6), 1.0]
    raw_asks = [row.amount for row in book.original_ask_entries()]
    assert raw_asks[0] == 1.0  # the raw container is untouched


def test_frames_protocol_runtime_check() -> None:
    assert isinstance(OrderBook(), FramesOrderBookProtocol)
    assert isinstance(CompositeOrderBook(), FramesOrderBookProtocol)
    assert not isinstance(object(), FramesOrderBookProtocol)


@pytest.mark.parametrize(
    "member",
    ["snapshot", "apply_pandas_diffs", "apply_numpy_diffs", "apply_numpy_snapshot"],
)
@pytest.mark.parametrize("blocked", ["numpy", "pandas"])
def test_missing_extra_raises_import_error(
    member: str, blocked: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    book = OrderBook()
    empty = np.empty((0, 3), dtype=np.float64)
    frame = pd.DataFrame(empty, columns=["price", "amount", "update_id"])
    monkeypatch.setitem(sys.modules, blocked, None)
    with pytest.raises(ImportError) as info:
        if member == "snapshot":
            _ = book.snapshot
        elif member == "apply_pandas_diffs":
            book.apply_pandas_diffs(frame, frame)
        elif member == "apply_numpy_diffs":
            book.apply_numpy_diffs(empty, empty)
        else:
            book.apply_numpy_snapshot(empty, empty)
    assert str(info.value) == (
        f"hb-order-book[frames] is required for {member}: pip install 'hb-order-book[frames]'"
    )
    assert info.value.__cause__ is not None


def test_package_has_no_module_level_numpy_or_pandas_import() -> None:
    # A subprocess import check is not possible: hb-data-type-primitives itself imports
    # pandas. Instead assert that order_book never imports them at module level.
    root = Path(order_book.__file__).parent
    offenders = []
    for path in root.rglob("*.py"):
        for node in ast.parse(path.read_text()).body:
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            if any(name.split(".")[0] in {"numpy", "pandas"} for name in names):
                offenders.append(str(path))
    assert offenders == []
