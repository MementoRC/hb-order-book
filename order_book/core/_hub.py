"""Default synchronous, weak-reference event hub (satisfies ``EventPort``)."""

import logging
import weakref
from enum import Enum
from inspect import ismethod
from typing import Any

from order_book.core.ports import EventSubscriber

_logger = logging.getLogger(__name__)

_Ref = weakref.ReferenceType[Any] | weakref.WeakMethod[Any]


def _make_ref(listener: EventSubscriber) -> _Ref:
    if ismethod(listener):
        return weakref.WeakMethod(listener)
    return weakref.ref(listener)


def _same(a: _Ref, b: _Ref) -> bool:
    # A WeakMethod's referent is the bound object itself, so a bare object and one of its
    # bound methods would otherwise compare equal.
    return type(a) is type(b) and a == b


class EventHub:
    """Weakly-referencing publish/subscribe hub keyed by event tag."""

    def __init__(self) -> None:
        self._listeners: dict[Enum, list[_Ref]] = {}

    def _live(self, event_tag: Enum) -> list[tuple[_Ref, EventSubscriber]]:
        """Return live ``(ref, listener)`` pairs for ``event_tag``, pruning dead refs."""
        refs = self._listeners.get(event_tag)
        if refs is None:
            return []
        live = [(ref, listener) for ref in refs if (listener := ref()) is not None]
        if live:
            self._listeners[event_tag] = [ref for ref, _ in live]
        else:
            del self._listeners[event_tag]
        return live

    def add_listener(self, event_tag: Enum, listener: EventSubscriber) -> None:
        new_ref = _make_ref(listener)
        live = self._live(event_tag)
        if any(_same(ref, new_ref) for ref, _ in live):
            return
        self._listeners.setdefault(event_tag, []).append(new_ref)

    def remove_listener(self, event_tag: Enum, listener: EventSubscriber) -> None:
        old_ref = _make_ref(listener)
        live = self._live(event_tag)
        kept = [ref for ref, _ in live if not _same(ref, old_ref)]
        if kept:
            self._listeners[event_tag] = kept
        else:
            self._listeners.pop(event_tag, None)

    def get_listeners(self, event_tag: Enum) -> list[EventSubscriber]:
        return [listener for _, listener in self._live(event_tag)]

    def trigger_event(self, event_tag: Enum, message: Any) -> None:
        # Iterate a copy: listeners may add/remove listeners during dispatch.
        for _, listener in self._live(event_tag):
            try:
                listener(message)
            except Exception:
                _logger.exception("Unexpected error while processing event %s.", event_tag)
