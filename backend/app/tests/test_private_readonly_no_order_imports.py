import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "private_api"


def _source_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*.py"))


def test_private_api_package_avoids_blocked_imports_and_config_reads() -> None:
    blocked_module = "app." + "brokers"
    blocked_dot_module = "dot" + "env"
    blocked_order_schema = "Order" + "Request"
    blocked_attr = "en" + "viron"
    blocked_getter = "get" + "env"
    blocked_flag = "ENABLE_" + "LIVE_TRADING"

    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                assert blocked_dot_module not in names
                assert all(not name.startswith(blocked_module) for name in names)
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module != blocked_dot_module
                assert not module.startswith(blocked_module)
            if isinstance(node, ast.Name):
                assert node.id != blocked_order_schema
                assert node.id != blocked_getter
                assert node.id != blocked_flag
            if isinstance(node, ast.Attribute):
                assert node.attr != blocked_attr
                assert node.attr != blocked_getter


def test_private_api_package_has_no_execution_function_defs() -> None:
    blocked_names = {"sub" + "mit", "se" + "nd", "pl" + "ace", "can" + "cel", "am" + "end"}

    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        assert function_names.isdisjoint(blocked_names)


def test_private_api_package_does_not_reference_dot_env_files() -> None:
    marker = "." + "env"
    for path in _source_files():
        assert marker not in path.read_text(encoding="utf-8")
