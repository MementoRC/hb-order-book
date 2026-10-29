# Intentional divergences from hummingbot core

Rule: contract parity, not defect parity. The package matches core's observable contract
and deliberately does not reproduce core defects. Tests asserting a divergence carry
`@pytest.mark.divergence`, so a run against core can deselect or xfail them
(`-m "not divergence"`). Paths are relative to `hummingbot/core/data_type/`.

Note on items 1-2: since #12 the `OrderBookMessage` class is defined in `data_type_primitives`
(hb-data-type-primitives v0.4.0, `data_type_primitives/order_book.py`) carrying the same
semantics. hb-order-book re-exports it, and its `@pytest.mark.divergence` tests remain the guard.

| # | Divergence | Core location | Rationale |
|---|---|---|---|
| 1 | `OrderBookMessage.__hash__` hashes the tuple `(type, id)` | `order_book_message.py:82` | Core calls `hash(a, b, c)`, which always raises `TypeError`. |
| 2 | `OrderBookMessage.__lt__` / `__eq__` are strict (irreflexive, consistent) | `order_book_message.py:75-79`, `:84-93` | In `__lt__` the trailing `or self.has_update_id` sits outside the equal-timestamp branch, so a snapshot or diff is `<` anything. `restore_from_snapshot_and_diffs` (`order_book.pyx:479`) then gets `bisect_right == 0` and replays stale diffs. `__eq__` falls through to `trade_id` (-1 == -1), so DIFFs with different `update_id` compare equal. |
| 3 | `TradeType` is matched by `.name` in `CompositeOrderBook.record_filled_order` | `composite_order_book.pyx:44`, `:59` | Core uses identity (`is TradeType.BUY`); the package must not import hummingbot, so any enum with the same member names works. |
| 4 | `CompositeOrderBook.get_price` raises `OSError` when every level is netted away | `composite_order_book.pyx:184-194` | Core leaks `StopIteration` from `next()` on an exhausted generator. |
| 5 | NaN prices are rejected with `ValueError` in `PriceLevels.insert` | `order_book.pyx:111-118`, `OrderBookEntry.cpp` | A NaN breaks `std::set` ordering; behaviour in core is undefined. |

## Draft core bug report (not filed)

Three defects in `hummingbot/core/data_type/order_book_message.py`.

```python
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

def diff(uid, ts):
    return OrderBookMessage(OrderBookMessageType.DIFF, {"update_id": uid}, ts)

def snap(uid, ts):
    return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {"update_id": uid}, ts)

# 1. __lt__: a snapshot/diff is less than everything, including itself and older messages.
assert snap(10, 1.0) < diff(9, 0.5)      # passes, expected False (id 10 > 9, older ts)
assert diff(1, 1.0) < diff(1, 1.0)       # passes, expected False

# 1b. Consequence: OrderBook.restore_from_snapshot_and_diffs uses bisect_right(diffs, snapshot).
#     Since diff < snapshot is always True... and snapshot < diff is also True, the
#     bisect result is 0, so diffs with update_id <= snapshot.update_id are replayed.

# 2. __eq__: for non-trade messages the trade_id fall-through (-1 == -1) makes
#    DIFFs with different update_id equal.
assert diff(1, 1.0) == diff(2, 1.0)      # passes, expected False

# 3. __hash__: hash() takes one argument.
hash(diff(1, 1.0))                       # TypeError: hash() takes exactly one argument (3 given)
```

Suggested fix: move `or self.has_update_id` inside the equal-timestamp branch of `__lt__`,
guard the `trade_id` branch of `__eq__` with `not self.has_update_id`, and use
`hash((self.type, self.update_id, self.trade_id))`.
