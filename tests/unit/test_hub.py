import gc
import logging
from enum import Enum
from typing import Any

import pytest

from order_book.core import EventHub, EventPort, OrderBookEvent


class _Tag(Enum):
    A = 1
    B = 2


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def on_event(self, message: Any) -> None:
        self.calls.append(message)

    def __call__(self, message: Any) -> None:
        self.calls.append(("call", message))


def test_hub_is_event_port() -> None:
    assert isinstance(EventHub(), EventPort)


def test_add_get_trigger_remove() -> None:
    hub = EventHub()
    seen: list[Any] = []

    def listener(msg: Any) -> None:
        seen.append(msg)

    hub.add_listener(_Tag.A, listener)
    assert hub.get_listeners(_Tag.A) == [listener]
    hub.trigger_event(_Tag.A, 1)
    assert seen == [1]
    hub.remove_listener(_Tag.A, listener)
    assert hub.get_listeners(_Tag.A) == []
    hub.trigger_event(_Tag.A, 2)
    assert seen == [1]


def test_get_listeners_unknown_tag_empty() -> None:
    assert EventHub().get_listeners(_Tag.A) == []
    EventHub().trigger_event(_Tag.A, 1)


def test_subscribe_twice_is_noop() -> None:
    hub = EventHub()
    rec = _Recorder()
    hub.add_listener(_Tag.A, rec.on_event)
    hub.add_listener(_Tag.A, rec.on_event)
    hub.add_listener(_Tag.A, rec)
    assert len(hub.get_listeners(_Tag.A)) == 2
    hub.trigger_event(_Tag.A, "x")
    assert rec.calls == ["x", ("call", "x")]


def test_remove_one_of_many_keeps_others() -> None:
    hub = EventHub()
    rec = _Recorder()
    hub.add_listener(_Tag.A, rec.on_event)
    hub.add_listener(_Tag.A, rec)
    hub.remove_listener(_Tag.A, rec.on_event)
    hub.trigger_event(_Tag.A, 1)
    assert rec.calls == [("call", 1)]


def test_remove_unknown_is_noop() -> None:
    hub = EventHub()
    rec = _Recorder()
    hub.remove_listener(_Tag.A, rec.on_event)
    hub.add_listener(_Tag.A, rec)
    hub.remove_listener(_Tag.A, rec.on_event)
    assert hub.get_listeners(_Tag.A) == [rec]


def test_weak_function_listener_dies() -> None:
    hub = EventHub()

    def listener(_: Any) -> None:
        pass

    hub.add_listener(_Tag.A, listener)
    del listener
    gc.collect()
    assert hub.get_listeners(_Tag.A) == []


def test_weak_bound_method_dies_with_owner() -> None:
    hub = EventHub()
    rec = _Recorder()
    hub.add_listener(_Tag.A, rec.on_event)
    assert len(hub.get_listeners(_Tag.A)) == 1
    del rec
    gc.collect()
    assert hub.get_listeners(_Tag.A) == []
    hub.trigger_event(_Tag.A, 1)


def test_dead_ref_pruned_when_other_alive() -> None:
    hub = EventHub()
    keep = _Recorder()
    dead = _Recorder()
    hub.add_listener(_Tag.A, keep.on_event)
    hub.add_listener(_Tag.A, dead.on_event)
    del dead
    gc.collect()
    hub.trigger_event(_Tag.A, 5)
    assert keep.calls == [5]
    assert len(hub.get_listeners(_Tag.A)) == 1


def test_synchronous_delivery() -> None:
    hub = EventHub()
    order: list[str] = []

    def listener(_: Any) -> None:
        order.append("listener")

    hub.add_listener(_Tag.A, listener)
    order.append("before")
    hub.trigger_event(_Tag.A, None)
    order.append("after")
    assert order == ["before", "listener", "after"]


def test_error_isolation(caplog: pytest.LogCaptureFixture) -> None:
    hub = EventHub()
    rec = _Recorder()

    def bad(_: Any) -> None:
        raise RuntimeError("boom")

    hub.add_listener(_Tag.A, bad)
    hub.add_listener(_Tag.A, rec.on_event)
    with caplog.at_level(logging.ERROR, logger="order_book.core._hub"):
        hub.trigger_event(_Tag.A, 1)
    assert rec.calls == [1]
    assert any("Unexpected error" in r.getMessage() and r.exc_info for r in caplog.records)


def test_per_tag_isolation() -> None:
    hub = EventHub()
    a, b = _Recorder(), _Recorder()
    hub.add_listener(_Tag.A, a.on_event)
    hub.add_listener(_Tag.B, b.on_event)
    hub.trigger_event(_Tag.A, 1)
    assert a.calls == [1]
    assert b.calls == []
    hub.remove_listener(_Tag.A, a.on_event)
    assert hub.get_listeners(_Tag.B) == [b.on_event]


def test_int_enum_tag() -> None:
    hub = EventHub()
    rec = _Recorder()
    hub.add_listener(OrderBookEvent.TradeEvent, rec.on_event)
    hub.trigger_event(OrderBookEvent.TradeEvent, "t")
    assert rec.calls == ["t"]


def test_equal_valued_tags_from_different_enums_meet() -> None:
    class Other(Enum):
        T = 1

    hub = EventHub()
    rec = _Recorder()
    hub.add_listener(Other.T, rec.on_event)
    hub.trigger_event(_Tag.A, "x")
    assert rec.calls == ["x"]
    assert hub.get_listeners(_Tag.A) == [rec.on_event]
    hub.remove_listener(_Tag.A, rec.on_event)
    assert hub.get_listeners(Other.T) == []


def test_listener_added_during_dispatch_not_called() -> None:
    hub = EventHub()
    late = _Recorder()

    def adder(_: Any) -> None:
        hub.add_listener(_Tag.A, late.on_event)

    hub.add_listener(_Tag.A, adder)
    hub.trigger_event(_Tag.A, 1)
    assert late.calls == []
    hub.trigger_event(_Tag.A, 2)
    assert late.calls == [2]
