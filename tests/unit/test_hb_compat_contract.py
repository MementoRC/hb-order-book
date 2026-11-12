import importlib

import pytest

import order_book.core
import order_book.hb_compat

# hb_compat submodule -> names it must define, matching the superseded hummingbot module.
MODULES = {
    "order_book.hb_compat.order_book_row": {"OrderBookRow", "ClientOrderBookRow"},
    "order_book.hb_compat.order_book_query_result": {
        "OrderBookQueryResult",
        "ClientOrderBookQueryResult",
    },
    "order_book.hb_compat.order_book_message": {"OrderBookMessage", "OrderBookMessageType"},
    "order_book.hb_compat.order_book": {"OrderBook"},
    "order_book.hb_compat.composite_order_book": {"CompositeOrderBook"},
    "order_book.hb_compat.events": {"OrderBookEvent", "OrderBookTradeEvent"},
}
PUBLIC_NAMES = set().union(*MODULES.values())


@pytest.mark.parametrize(("module_name", "names"), sorted(MODULES.items()))
def test_submodule_defines_and_exports_core_names(module_name: str, names: set[str]) -> None:
    module = importlib.import_module(module_name)
    assert set(module.__all__) == names
    for name in names:
        assert getattr(module, name) is getattr(order_book.core, name)


def test_package_reexports_every_public_name() -> None:
    assert set(order_book.hb_compat.__all__) == PUBLIC_NAMES
    for name in PUBLIC_NAMES:
        assert getattr(order_book.hb_compat, name) is getattr(order_book.core, name)


@pytest.mark.xfail(
    strict=True,
    reason="hb-order-book#23: re-export event_bus.OrderBookEvent once hb-event-bus#42 is released",
)
def test_order_book_event_is_canonical_event_bus_class() -> None:
    from event_bus import OrderBookEvent

    from order_book.hb_compat import OrderBookEvent as HbCompatOrderBookEvent

    assert HbCompatOrderBookEvent is OrderBookEvent
    assert order_book.core.events.OrderBookEvent is OrderBookEvent
