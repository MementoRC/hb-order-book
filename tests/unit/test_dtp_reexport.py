import importlib

import data_type_primitives
import pytest

import order_book.core

_ROW_MODULES = [
    "order_book",
    "order_book.core",
    "order_book.core.types",
    "order_book.hb_compat",
    "order_book.hb_compat.order_book_row",
]
_QUERY_MODULES = [
    "order_book",
    "order_book.core",
    "order_book.core.types",
    "order_book.hb_compat",
    "order_book.hb_compat.order_book_query_result",
]
_MESSAGE_MODULES = [
    "order_book",
    "order_book.core",
    "order_book.core.message",
    "order_book.hb_compat",
    "order_book.hb_compat.order_book_message",
]

_CASES = (
    [(m, n) for m in _ROW_MODULES for n in ("OrderBookRow", "ClientOrderBookRow")]
    + [
        (m, n)
        for m in _QUERY_MODULES
        for n in ("OrderBookQueryResult", "ClientOrderBookQueryResult")
    ]
    + [(m, n) for m in _MESSAGE_MODULES for n in ("OrderBookMessage", "OrderBookMessageType")]
)


@pytest.mark.parametrize(("module_name", "name"), _CASES)
def test_type_is_reexported_from_dtp(module_name: str, name: str) -> None:
    module = importlib.import_module(module_name)
    assert getattr(module, name) is getattr(data_type_primitives, name)


def test_order_book_entry_is_not_dtp_entry() -> None:
    assert order_book.core.OrderBookEntry is not data_type_primitives.OrderBookEntry
