# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `OrderBookEntry`, `PriceLevels` and truncation of price levels (#4).
- `OrderBook`, the package-local `EventHub` and `OrderBookProtocol` (#5).
- `CompositeOrderBook` (#6).
- `frames` extra: `snapshot`, `apply_pandas_diffs`, `apply_numpy_diffs`,
  `apply_numpy_snapshot` (numpy/pandas, lazily imported) (#7).
- `order_book.hb_compat` drop-in surface for hummingbot (#8).

### Removed

- The `frames` pip extra (`hb-order-book[frames]`). hb-* packages are conda-only: install `pandas` and `numpy` from conda-forge to use the DataFrame helpers. (#19)

### Changed

- The six order-book value types are now re-exported from hb-data-type-primitives v0.4.0 instead of defined locally (#12).
