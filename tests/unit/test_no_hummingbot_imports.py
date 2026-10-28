import ast
from pathlib import Path

import order_book

PACKAGE_DIR = Path(order_book.__file__).parent


def _offending_imports(path: Path) -> list[str]:
    bad: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            bad += [a.name for a in node.names if a.name.split(".")[0] == "hummingbot"]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "hummingbot":
            bad.append(node.module or "")
    return bad


def test_no_hummingbot_imports() -> None:
    files = sorted(PACKAGE_DIR.rglob("*.py"))
    assert files
    offenders = {str(f): _offending_imports(f) for f in files if _offending_imports(f)}
    assert not offenders


def test_scanner_detects_hummingbot_imports(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text("import hummingbot.core\nfrom hummingbot.x import y\nimport os\n")
    assert _offending_imports(sample) == ["hummingbot.core", "hummingbot.x"]
