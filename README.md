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

The only runtime dependency is `hb-data-type-primitives` (git tag `v0.1.0`).
Never imports `hummingbot` (enforced by import-linter via `pixi run lint-imports`).

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
