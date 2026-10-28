"""Drop-in surface for hummingbot's order book modules.

hummingbot reaches this package only through ``order_book.hb_compat``. Each submodule mirrors
one superseded core module and re-exports the classes under core's names:

- ``order_book_row``: ``hummingbot.core.data_type.order_book_row``
- ``order_book_query_result``: ``hummingbot.core.data_type.order_book_query_result``
- ``order_book_message``: ``hummingbot.core.data_type.order_book_message``
- ``order_book``: ``hummingbot.core.data_type.order_book``
- ``composite_order_book``: ``hummingbot.core.data_type.composite_order_book``
- ``events``: ``OrderBookEvent`` and ``OrderBookTradeEvent`` from ``hummingbot.core.event.events``
"""

from order_book.hb_compat.composite_order_book import CompositeOrderBook
from order_book.hb_compat.events import OrderBookEvent, OrderBookTradeEvent
from order_book.hb_compat.order_book import OrderBook
from order_book.hb_compat.order_book_message import OrderBookMessage, OrderBookMessageType
from order_book.hb_compat.order_book_query_result import (
    ClientOrderBookQueryResult,
    OrderBookQueryResult,
)
from order_book.hb_compat.order_book_row import ClientOrderBookRow, OrderBookRow

__all__ = [
    "ClientOrderBookQueryResult",
    "ClientOrderBookRow",
    "CompositeOrderBook",
    "OrderBook",
    "OrderBookEvent",
    "OrderBookMessage",
    "OrderBookMessageType",
    "OrderBookQueryResult",
    "OrderBookRow",
    "OrderBookTradeEvent",
]
