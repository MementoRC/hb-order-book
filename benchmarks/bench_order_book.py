"""Stdlib timeit benchmarks for OrderBook (run: ``python benchmarks/bench_order_book.py``).

Final result vs the pre-optimisation code (ms, 1e4-level book, bids best-first):

    case                              before    after
    apply_snapshot 1e3/side             2.03     1.4
    apply_snapshot 1e4/side            45.1     14
    apply_snapshot 5e4/side           848       90
    10k apply_diffs                    57.9     41
    10k diff + 1 ask query             8524     66
    (a) 10k diff + 1 bid query         8357    347
    (b) 10k diff + 5 bid queries      38584    437

Trade-off: the parallel sorted-entries list makes apply_diffs about 25% slower
than the dict-rebuild variant (~31 ms), in exchange for ~14x faster same-side
queries (a, b), whose cache rebuild is a plain tuple copy.
"""

import sys
from pathlib import Path
from timeit import timeit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from order_book.core.order_book import OrderBook  # noqa: E402
from order_book.core.types import OrderBookRow  # noqa: E402

DIFFS = 10_000
BOOK_SIZE = 10_000


def _side(n: int, start: float, step: float) -> list[OrderBookRow]:
    return [OrderBookRow(start + i * step, 1.0 + i % 7, i) for i in range(n)]


def _book(n: int) -> OrderBook:
    book = OrderBook()
    book.apply_snapshot(_side(n, 1000.0, -0.01), _side(n, 1001.0, 0.01), 1)
    return book


def _diff_rows() -> list[list[OrderBookRow]]:
    return [[OrderBookRow(990.0 - (i % 500) * 0.01, 1.0 + i % 5, i)] for i in range(DIFFS)]


def bench_snapshot(n: int) -> float:
    bids = _side(n, 1000.0, -0.01)  # best-first (descending)
    asks = _side(n, 1001.0, 0.01)
    book = OrderBook()
    return timeit(lambda: book.apply_snapshot(bids, asks, 1), number=3) / 3


def bench_diffs(queries: int = 0, is_buy: bool = False) -> float:
    """10k one-row bid diffs; ``queries`` get_price_for_volume calls after each diff."""
    book = _book(BOOK_SIZE)
    rows = _diff_rows()

    def run() -> None:
        for i, row in enumerate(rows):
            book.apply_diffs(row, [], i)
            for _ in range(queries):
                book.get_price_for_volume(is_buy, 5.0)

    return timeit(run, number=1)


def main() -> None:
    for n in (1_000, 10_000, 50_000):
        print(f"apply_snapshot n={n:>6}/side: {bench_snapshot(n) * 1000:10.2f} ms")
    cases = (
        ("10k apply_diffs on 1e4 book", 0, False),
        ("10k diff + 1 ask query (other side)", 1, True),
        ("(a) 10k diff + 1 bid query", 1, False),
        ("(b) 10k diff + 5 bid queries", 5, False),
    )
    for label, queries, is_buy in cases:
        print(f"{label}: {bench_diffs(queries, is_buy) * 1000:10.2f} ms")


if __name__ == "__main__":
    main()
