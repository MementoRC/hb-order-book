from decimal import Decimal

from data_type_primitives import TradeType

from order_book import OrderBookEvent, OrderBookTradeEvent


def test_order_book_event_values() -> None:
    assert OrderBookEvent.TradeEvent == 901
    assert OrderBookEvent.OrderBookDataSourceUpdateEvent == 904
    assert isinstance(OrderBookEvent.TradeEvent, int)


def test_trade_event_defaults() -> None:
    ev = OrderBookTradeEvent("BTC-USDT", 1.0, TradeType.BUY, Decimal("1"), Decimal("2"))
    assert ev.trade_id is None
    assert ev.is_taker is True
    assert ev._fields == (
        "trading_pair",
        "timestamp",
        "type",
        "price",
        "amount",
        "trade_id",
        "is_taker",
    )


def test_trade_event_explicit_fields() -> None:
    ev = OrderBookTradeEvent(
        "ETH-USDT", 2.0, TradeType.SELL, Decimal("3"), Decimal("4"), "t1", False
    )
    assert ev.type is TradeType.SELL
    assert ev.trade_id == "t1"
    assert ev.is_taker is False
