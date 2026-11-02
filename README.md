# hb-order-book

Hummingbot OrderBook extracted as a standalone L2 domain sub-package
(import name `order_book`).

## Installation / extras

```bash
pip install hb-order-book             # core book, no numpy/pandas
pip install 'hb-order-book[frames]'   # adds snapshot, apply_pandas_diffs, apply_numpy_diffs, apply_numpy_snapshot
```

Without the `frames` extra those four members raise `ImportError` naming the extra.
Currently numpy and pandas arrive transitively through `hb-data-type-primitives`, so the extra is declarative until that changes.

## Usage

```python
from order_book import OrderBook, OrderBookEvent, OrderBookRow

book = OrderBook()
book.add_listener(OrderBookEvent.TradeEvent, lambda event: print(event))  # held weakly: keep a reference
book.apply_snapshot([OrderBookRow(99.0, 1.0, 1)], [OrderBookRow(101.0, 2.0, 1)], update_id=1)
book.get_price(is_buy=True)  # 101.0
```

## Layer

L2 (see ADR 0001). Layout:

- `order_book.core` - pure domain logic: `OrderBook`, `CompositeOrderBook`, `OrderBookMessage`,
  `OrderBookEntry`/price levels, `OrderBookProtocol`, and its own `EventHub` (`core/_hub.py`)
- `order_book.adapters` - concrete adapters
- `order_book.hb_compat` - drop-in compatibility layer for hummingbot; never imports hummingbot
- `frames` extra - numpy/pandas-backed `snapshot` and diff helpers

Intentional divergences from hummingbot core are listed in docs/divergences.md.

## Dependency rule

The only runtime dependency is `hb-data-type-primitives` (git tag `v0.4.0`).
The six order-book value types (`OrderBookRow`, `ClientOrderBookRow`, `OrderBookQueryResult`, `ClientOrderBookQueryResult`, `OrderBookMessageType`, `OrderBookMessage`) are defined in `data_type_primitives` and re-exported here.
Never imports `hummingbot` (enforced by import-linter via `pixi run lint-imports`).

## API stability

The public API is:

- `order_book.hb_compat`: the only path hummingbot may import from. Module and class names
  mirror `hummingbot.core.data_type.*` (`order_book`, `composite_order_book`,
  `order_book_row`, `order_book_query_result`, `order_book_message`) and the
  `OrderBookEvent` / `OrderBookTradeEvent` events. Signatures match core.
- The names in `order_book.__all__`, for direct (non-hummingbot) consumers.

Everything else (`order_book.core.*` internals, `order_book.adapters`, underscore names) is
private and may change without notice.

Versioning follows SemVer. While on `0.x`, a breaking change to the public API bumps the minor
version and is listed in `CHANGELOG.md`; a behaviour change relative to hummingbot core is
also recorded in docs/divergences.md with a `@pytest.mark.divergence` test. Releases are
signed `vX.Y.Z` tags on `development`; consumers pin a tag, never a branch head.

Out of scope: `order_book_tracker`, `order_book_tracker_entry`,
`order_book_tracker_data_source` and the API data sources stay in hummingbot core and use
the `hb_compat` `OrderBook`.

## Ownership

Implementation is owned by the hb-order-book session.

## Development

```bash
pixi run test      # pytest with coverage (fail_under=100)
pixi run lint      # ruff check
pixi run format    # ruff format
pixi run typecheck # mypy
pixi run lint-imports  # import-linter contracts
pixi run check     # lint + format-check + typecheck + lint-imports + coverage
```

Work in `.worktrees/<branch>` cut from `origin/development`; open PRs against `development`.
`development` is the default branch; `main` only receives PRs from `development`.
Both are protected and require the `CI Success` check. Commits are GPG-signed.

## License

Apache-2.0
