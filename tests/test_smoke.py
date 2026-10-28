import importlib

import order_book
from order_book.__about__ import __version__


def test_version_is_str() -> None:
    assert isinstance(order_book.__version__, str)


def test_version_matches_about() -> None:
    assert order_book.__version__ == __version__


def test_subpackages_import() -> None:
    for name in ("core", "adapters", "hb_compat"):
        assert importlib.import_module(f"order_book.{name}") is not None
