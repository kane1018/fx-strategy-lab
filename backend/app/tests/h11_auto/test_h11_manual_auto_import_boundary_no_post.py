"""Exact import boundary between the manual UI and H-11 automation."""

import ast
from pathlib import Path

ALLOWED_AUTO_IMPORTS = frozenset(
    {
        ("app.h11_auto.runtime_safety", "H11AutoRuntimeSafetyError"),
        ("app.h11_auto.runtime_safety", "PhaseBRiskStore"),
        (
            "app.h11_auto.v4_actual_preparation_guard",
            "V4ActualPreparationGuardError",
        ),
        ("app.h11_auto.v4_actual_preparation_guard", "require_clean_main"),
        (
            "app.h11_auto.v4_gmo_actual_coordinator",
            "V4GmoActualCoordinatorError",
        ),
        (
            "app.h11_auto.v4_gmo_actual_coordinator",
            "V4GmoActualCoordinatorStore",
        ),
        ("app.h11_auto.v4_gmo_generation", "V4GmoFrozenGeneration"),
        ("app.h11_auto.v4_gmo_generation", "V4GmoGenerationError"),
        (
            "app.h11_auto.v4_gmo_generation",
            "load_v4_gmo_frozen_generation",
        ),
        ("app.h11_auto.v4_gmo_generation", "v4_gmo_risk_policy"),
        (
            "app.h11_auto.v4_gmo_runtime_paths",
            "v4_gmo_runtime_state_root",
        ),
    }
)


def test_manual_ui_auto_imports_are_an_exact_reviewed_allowlist() -> None:
    app_root = Path(__file__).resolve().parents[2]
    observed: set[tuple[str, str]] = set()

    for path in sorted((app_root / "h11_manual").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app.h11_auto" or alias.name.startswith(
                        "app.h11_auto."
                    ):
                        observed.add((alias.name, "*"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "app.h11_auto" or module.startswith(
                    "app.h11_auto."
                ):
                    observed.update((module, alias.name) for alias in node.names)

    assert observed <= ALLOWED_AUTO_IMPORTS, (
        "manual UI added an unreviewed automation import: "
        f"{sorted(observed - ALLOWED_AUTO_IMPORTS)}"
    )
