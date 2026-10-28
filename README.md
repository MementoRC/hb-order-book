# hb-order-book

Hummingbot OrderBook extracted as a standalone L2 domain sub-package
(import name `order_book`). This repository is currently a skeleton: no
OrderBook code has been extracted yet.

## Layer

L2 (see ADR 0001). Layout:

- `order_book.core` - pure domain logic
- `order_book.adapters` - concrete adapters
- `order_book.hb_compat` - drop-in compatibility layer for hummingbot; never imports hummingbot

## Dependency rule

May depend only on the L0 leaves `hb-data-type-primitives` and `hb-event-bus`.
Never imports `hummingbot`. No runtime dependencies are declared yet; conda-forge only, no PyPI deps.

## Ownership

Implementation is owned by the hb-order-book session.

## Development

```bash
pixi run test      # pytest with coverage (fail_under=100)
pixi run lint      # ruff check
pixi run format    # ruff format
pixi run typecheck # mypy
pixi run check     # lint + format-check + typecheck + coverage
```

Work in `.worktrees/<branch>` cut from `origin/development`; open PRs against `development`.

## License

Apache-2.0
