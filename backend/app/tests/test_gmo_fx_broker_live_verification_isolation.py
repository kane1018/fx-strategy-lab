"""No-POST isolation guard: production code must stay separated from the
Step 6G controlled/simulation family.

Context: an incident audit found that a small number of modules under
`app.live_verification` (including `live_order_once`) contain genuine
httpx-based HTTP POST capability toward real GMO FX endpoints, guarded by a
shared default-deny hard guard now living at
`app.security.real_broker_post_hard_guard` (relocated out of
`app.live_verification` specifically so production broker code can depend on
it). The design for a future real `GmoFxBroker` order-write path
(`docs/GMO_LIVE_AUTOMATION_RESUME_DESIGN.md`) requires that production broker/
service code never import the `app.live_verification` simulation family or
`live_order_once`, and never wire `allow_real_broker_post=True` /
`allow_live_http_post=True` directly. This is a source-scan test, not an
import-time check, so it also catches files that do not exist yet being added
later without ever needing to import them at collection time.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

APP_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_DIR_NAMES = {"live_verification", "tests", "__pycache__"}

_ALLOW_TRUE_PATTERNS = (
    "allow_real_broker_post=True",
    "allow_real_broker_post = True",
    "allow_live_http_post=True",
    "allow_live_http_post = True",
)


def _production_python_files() -> list[pathlib.Path]:
    files = []
    for path in APP_ROOT.rglob("*.py"):
        relative_parts = path.relative_to(APP_ROOT).parts
        if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
            continue
        files.append(path)
    return sorted(files)


def _imported_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_production_files_discovered_for_scan() -> None:
    files = _production_python_files()
    assert len(files) > 20, "expected the production app/ tree to be scanned, not an empty set"
    assert not any("live_verification" in path.parts for path in files)
    assert not any("tests" in path.parts for path in files)


def test_production_code_does_not_import_live_verification() -> None:
    offenders = []
    for path in _production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = _imported_module_names(tree)
        if any(
            module == "app.live_verification" or module.startswith("app.live_verification.")
            for module in modules
        ):
            offenders.append(str(path.relative_to(APP_ROOT)))
    assert offenders == [], (
        f"production files import app.live_verification (Step 6G simulation family): {offenders}"
    )


def test_production_code_does_not_reference_live_order_once() -> None:
    offenders = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        if "live_order_once" in text:
            offenders.append(str(path.relative_to(APP_ROOT)))
    assert offenders == [], f"production files reference live_order_once: {offenders}"


def test_gmo_or_oanda_named_broker_files_have_no_live_verification_reference() -> None:
    """Source-scan any *gmo*broker*.py / *oanda*broker*.py file, present or future.

    This does not require the file to exist yet — glob simply returns an empty
    list if no such file exists, and the assertion still holds trivially. When
    a real GmoFxBroker order-write path is added, this test starts actually
    checking it without any test-file change required.
    """
    offenders = []
    for path in sorted(APP_ROOT.rglob("*broker*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        name = path.name.lower()
        if "gmo" not in name and "oanda" not in name:
            continue
        text = path.read_text(encoding="utf-8")
        if "live_verification" in text:
            offenders.append(str(path.relative_to(APP_ROOT)))
    assert offenders == [], f"broker files reference live_verification: {offenders}"


def test_no_production_allow_true_wiring() -> None:
    offenders = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        collapsed = text.replace(" ", "")
        if any(pattern.replace(" ", "") in collapsed for pattern in _ALLOW_TRUE_PATTERNS):
            offenders.append(str(path.relative_to(APP_ROOT)))
    assert offenders == [], (
        f"production files wire allow_real_broker_post/allow_live_http_post=True: {offenders}"
    )


@pytest.mark.parametrize(
    "candidate_relative_path",
    [
        "brokers/gmo_fx_broker.py",
        "services/bot_service.py",
        "services/automation_service.py",
        "services/broker_service.py",
        "services/risk_service.py",
    ],
)
def test_known_broker_and_service_files_are_covered_by_the_scan(
    candidate_relative_path: str,
) -> None:
    """Pin that the files most likely to host the future GmoFxBroker
    integration are actually inside the scanned production set (not silently
    excluded by directory-name overlap or similar path-matching mistakes).
    """
    path = APP_ROOT / candidate_relative_path
    assert path.exists(), f"expected file missing, scan assumptions may be stale: {path}"
    assert path in _production_python_files()


def test_hard_guard_lives_outside_live_verification() -> None:
    """The shared real-broker-post hard guard must be importable from a
    production-safe location, and must no longer exist inside
    `app.live_verification`.
    """
    from app.security.real_broker_post_hard_guard import (
        RealBrokerPostHardGuardError,
        assert_real_broker_post_allowed,
    )

    assert callable(assert_real_broker_post_allowed)
    assert issubclass(RealBrokerPostHardGuardError, RuntimeError)

    with pytest.raises(ModuleNotFoundError):
        __import__("app.live_verification.real_broker_post_hard_guard")

    old_path = APP_ROOT / "live_verification" / "real_broker_post_hard_guard.py"
    assert not old_path.exists(), "old hard guard location must be removed, not just unused"


def test_app_security_package_is_covered_by_the_production_scan() -> None:
    """app/security must be scanned as production code (not silently excluded),
    so it stays subject to the same live_verification-import ban as brokers.
    """
    security_dir = APP_ROOT / "security"
    assert security_dir.exists()
    scanned = _production_python_files()
    assert any(path.parts[len(APP_ROOT.parts) :][0] == "security" for path in scanned)


def test_real_post_capable_files_reference_the_new_hard_guard_location() -> None:
    """The three known real-POST-capable live_verification modules must import
    the guard from its new location, not the removed old one.
    """
    real_post_capable_files = (
        "live_verification/live_order_once.py",
        "live_verification/live_order_real_official_settlement_actual_transport_no_post_controlled.py",  # noqa: E501
        "live_verification/live_order_real_one_shot_post_real_delegate_controlled.py",
    )
    for relative_path in real_post_capable_files:
        path = APP_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        assert "app.security.real_broker_post_hard_guard" in text, (
            f"{relative_path} does not reference the relocated hard guard"
        )
        assert "app.live_verification.real_broker_post_hard_guard" not in text, (
            f"{relative_path} still references the removed old hard guard location"
        )
