"""Ported from hummingbot core test_order_book_message.py, plus __hash__ contract."""

import time

import pytest

from order_book.core.message import OrderBookMessage, OrderBookMessageType
from order_book.core.types import OrderBookRow


def _msg(kind: OrderBookMessageType, content: dict, ts: float | None = None) -> OrderBookMessage:
    return OrderBookMessage(
        message_type=kind, content=content, timestamp=time.time() if ts is None else ts
    )


def test_update_id() -> None:
    update_id = "someId"
    assert _msg(OrderBookMessageType.SNAPSHOT, {"update_id": update_id}).update_id == update_id
    assert _msg(OrderBookMessageType.DIFF, {"update_id": update_id}).update_id == update_id
    assert _msg(OrderBookMessageType.TRADE, {"someKey": "someValue"}).update_id == -1


def test_first_update_id() -> None:
    assert _msg(OrderBookMessageType.SNAPSHOT, {"someKey": "v"}).first_update_id == -1
    msg = _msg(
        OrderBookMessageType.DIFF, {"update_id": "someId", "first_update_id": "firstUpdateId"}
    )
    assert msg.first_update_id == "firstUpdateId"
    assert _msg(OrderBookMessageType.TRADE, {"someKey": "v"}).first_update_id == -1


def test_trade_id() -> None:
    assert _msg(OrderBookMessageType.SNAPSHOT, {"someKey": "v"}).trade_id == -1
    assert _msg(OrderBookMessageType.DIFF, {"someKey": "v"}).trade_id == -1
    assert _msg(OrderBookMessageType.TRADE, {"trade_id": "someTradeId"}).trade_id == "someTradeId"


def test_trading_pair() -> None:
    msg = _msg(OrderBookMessageType.SNAPSHOT, {"trading_pair": "BTC-USDT"})
    assert msg.trading_pair == "BTC-USDT"


def test_bids_and_asks() -> None:
    update_id = "someId"
    msg = _msg(
        OrderBookMessageType.SNAPSHOT,
        {"update_id": update_id, "asks": [(1, 2), (3, 4)], "bids": [(5, 6), (7, 8)]},
    )
    asks = msg.asks
    assert len(asks) == 2
    assert isinstance(asks[0], OrderBookRow)
    assert (asks[0].price, asks[0].amount, asks[0].update_id) == (1, 2, update_id)

    bids = msg.bids
    assert len(bids) == 2
    assert isinstance(bids[0], OrderBookRow)
    assert (bids[0].price, bids[0].amount, bids[0].update_id) == (5, 6, update_id)


def test_has_update_id() -> None:
    assert _msg(OrderBookMessageType.SNAPSHOT, {"update_id": "x"}).has_update_id
    assert _msg(OrderBookMessageType.DIFF, {"update_id": "x"}).has_update_id
    assert not _msg(OrderBookMessageType.TRADE, {"someKey": "v"}).has_update_id


def test_has_trade_id() -> None:
    assert not _msg(OrderBookMessageType.SNAPSHOT, {"someKey": "v"}).has_trade_id
    assert not _msg(OrderBookMessageType.DIFF, {"someKey": "v"}).has_trade_id
    assert _msg(OrderBookMessageType.TRADE, {"trade_id": "t"}).has_trade_id


def test_equality() -> None:
    upd = {"update_id": "someId"}
    trd = {"trade_id": "someTradeId"}
    snapshot1 = _msg(OrderBookMessageType.SNAPSHOT, upd)
    snapshot2 = _msg(OrderBookMessageType.SNAPSHOT, upd)
    diff1 = _msg(OrderBookMessageType.DIFF, upd)
    diff2 = _msg(OrderBookMessageType.DIFF, upd)
    trade1 = _msg(OrderBookMessageType.TRADE, trd)
    trade2 = _msg(OrderBookMessageType.TRADE, trd)

    assert snapshot1 != diff1
    assert snapshot1 != trade1
    assert diff1 != trade1
    assert snapshot1 == snapshot2
    assert diff1 == diff2
    assert trade1 == trade2


def test_equality_with_foreign_type() -> None:
    msg = _msg(OrderBookMessageType.DIFF, {"update_id": 1})
    assert msg != "not a message"
    assert msg.__eq__(object()) is NotImplemented


def test_larger_than() -> None:
    t = time.time()
    trade1 = _msg(OrderBookMessageType.TRADE, {"trade_id": 5}, t)
    trade2 = _msg(OrderBookMessageType.TRADE, {"trade_id": 6}, time.time() + 1)
    snapshot1 = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 1}, time.time() + 2)
    snapshot2 = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 3}, time.time() + 3)
    diff1 = _msg(OrderBookMessageType.DIFF, {"update_id": 2}, time.time() + 4)
    diff2 = _msg(OrderBookMessageType.DIFF, {"update_id": 2}, t)

    assert trade1 < trade2  # based on id
    assert snapshot1 < snapshot2  # based on id
    assert snapshot1 < diff1  # based on id
    assert diff1 < snapshot2  # based on id
    assert trade1 < snapshot1  # based on timestamp
    assert diff2 < trade1  # if same ts, ob messages < trade messages


@pytest.mark.divergence  # core __eq__ falls through to trade_id (-1 == -1) and __hash__ raises
def test_diffs_with_different_update_id_are_unequal() -> None:
    d1 = _msg(OrderBookMessageType.DIFF, {"update_id": 1}, 1.0)
    d2 = _msg(OrderBookMessageType.DIFF, {"update_id": 2}, 1.0)
    assert d1 != d2
    assert hash(d1) != hash(d2)
    assert len({d1, d2}) == 2
    t1 = _msg(OrderBookMessageType.TRADE, {"trade_id": 1}, 1.0)
    t2 = _msg(OrderBookMessageType.TRADE, {"trade_id": 2}, 1.0)
    assert t1 != t2


def test_ne_follows_eq_not_tuple_comparison() -> None:
    s1 = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 7, "x": 1}, 1.0)
    s2 = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 7}, 2.0)
    assert s1 == s2
    assert s1.__ne__(s2) is False
    assert s1 != _msg(OrderBookMessageType.DIFF, {"update_id": 7}, 1.0)
    assert s1.__ne__(object()) is NotImplemented


@pytest.mark.divergence  # core __lt__: a snapshot/diff is < anything, even itself
def test_strict_order() -> None:
    msgs = [
        _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 1}, 1.0),
        _msg(OrderBookMessageType.DIFF, {"update_id": 2}, 2.0),
        _msg(OrderBookMessageType.DIFF, {"update_id": 2}, 2.0),
        _msg(OrderBookMessageType.TRADE, {"trade_id": 1}, 1.0),
        _msg(OrderBookMessageType.TRADE, {"trade_id": 2}, 2.0),
        _msg(OrderBookMessageType.TRADE, {"trade_id": 3}, 3.0),
    ]
    for a in msgs:
        assert not a < a
        for b in msgs:
            assert not (a < b and b < a)


def test_mixed_kind_order() -> None:
    diff = _msg(OrderBookMessageType.DIFF, {"update_id": 1}, 5.0)
    trade_same_ts = _msg(OrderBookMessageType.TRADE, {"trade_id": 1}, 5.0)
    assert diff < trade_same_ts
    assert not trade_same_ts < diff
    trade_earlier = _msg(OrderBookMessageType.TRADE, {"trade_id": 1}, 4.0)
    assert trade_earlier < diff
    assert not diff < trade_earlier


def test_derived_comparisons_between_diffs() -> None:
    # The message is a tuple subclass, so tuple's own >, <= and >= are inherited and
    # total_ordering (which only fills missing methods) never replaces them; they compare the
    # content dicts and raise TypeError. Core's namedtuple base behaves the same.
    d1 = _msg(OrderBookMessageType.DIFF, {"update_id": 1}, 1.0)
    d2 = _msg(OrderBookMessageType.DIFF, {"update_id": 2}, 2.0)
    with pytest.raises(TypeError):
        _ = d2 > d1
    with pytest.raises(TypeError):
        _ = d1 <= d2
    with pytest.raises(TypeError):
        _ = d2 >= d1


def test_derived_comparisons_between_diff_and_trade() -> None:
    diff = _msg(OrderBookMessageType.DIFF, {"update_id": 1}, 1.0)
    trade = _msg(OrderBookMessageType.TRADE, {"trade_id": 1}, 2.0)
    assert diff < trade  # only __lt__ is custom
    with pytest.raises(TypeError):
        _ = trade > diff
    with pytest.raises(TypeError):
        _ = diff <= trade
    with pytest.raises(TypeError):
        _ = trade >= diff


def test_sort_mixed_list() -> None:
    snap = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 1}, 1.0)
    d2 = _msg(OrderBookMessageType.DIFF, {"update_id": 2}, 2.0)
    d3 = _msg(OrderBookMessageType.DIFF, {"update_id": 3}, 3.0)
    tr = _msg(OrderBookMessageType.TRADE, {"trade_id": 1}, 3.0)
    assert sorted([tr, d3, snap, d2]) == [snap, d2, d3, tr]
    assert sorted([tr, d3, snap, d2])[-1] is tr


@pytest.mark.divergence  # core __hash__ calls hash(a, b, c), which always raises TypeError
def test_hash_is_consistent_with_equality() -> None:
    snapshot1 = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 7}, 1.0)
    snapshot2 = _msg(OrderBookMessageType.SNAPSHOT, {"update_id": 7, "x": 1}, 2.0)
    diff = _msg(OrderBookMessageType.DIFF, {"update_id": 7})
    trade1 = _msg(OrderBookMessageType.TRADE, {"trade_id": 9})
    trade2 = _msg(OrderBookMessageType.TRADE, {"trade_id": 9}, 5.0)

    assert snapshot1 == snapshot2
    assert hash(snapshot1) == hash(snapshot2)
    assert hash(trade1) == hash(trade2)
    assert len({snapshot1, snapshot2, diff, trade1, trade2}) == 3
    assert {trade1: "a"}[trade2] == "a"
