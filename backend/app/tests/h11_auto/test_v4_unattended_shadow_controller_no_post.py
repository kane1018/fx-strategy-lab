from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto import v4_unattended_shadow_controller as subject
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.v4_gmo_contracts import (
    V4GmoExecutionPolicy,
    V4GmoPreflightSnapshot,
)
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH


@pytest.fixture(autouse=True)
def _isolated_shadow_export_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subject,
        "_SHADOW_EXPORT_ROOT",
        tmp_path / "backend" / "shadow_exports",
    )


def _shadow_path(tmp_path: Path, name: str) -> Path:
    return tmp_path / "backend" / "shadow_exports" / name


def _policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash=subject.V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
        selected_horizon=FormalHorizon.MINUTES_30,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _now() -> datetime:
    return datetime(2026, 7, 20, 1, 0, tzinfo=UTC)


def _signal(
    *,
    decision: SignalDecision = SignalDecision.BUY,
    observed_at_utc: datetime | None = None,
    probability_up: Decimal = Decimal("0.61"),
    strategy_version: str = "SHORT_V1",
    horizon: FormalHorizon = FormalHorizon.MINUTES_30,
    signal_config_hash: str = subject.V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
) -> FormalSignal:
    observed = observed_at_utc or (_now() - timedelta(seconds=30))
    return FormalSignal(
        strategy_version=strategy_version,
        signal_config_hash=signal_config_hash,
        horizon=horizon,
        observed_at_utc=observed,
        valid_until_utc=observed + timedelta(minutes=30),
        decision=decision,
        probability_up=probability_up,
    )


def _preflight(**overrides: object) -> V4GmoPreflightSnapshot:
    values: dict[str, object] = {
        "boot_reconciled": True,
        "process_lock_held": True,
        "data_fresh": True,
        "clock_synchronized": True,
        "notification_path_ready": True,
        "broker_snapshot_fresh": True,
        "position_count": 0,
        "active_order_count": 0,
        "entries_today": 0,
        "daily_stop_clear": True,
        "monthly_stop_clear": True,
        "consecutive_loss_stop_clear": True,
        "operator_halt_clear": True,
    }
    values.update(overrides)
    return V4GmoPreflightSnapshot(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> subject.V4UnattendedShadowSnapshot:
    values: dict[str, object] = {
        "preflight": _preflight(),
        "market_open": True,
        "quote_age_seconds": Decimal("1"),
        "spread_pips": Decimal("0.5"),
        "reference_deviation_pips": Decimal("1.0"),
        "frozen_atr_24": Decimal("0.09"),
        "planned_loss_bound_jpy": 188,
    }
    values.update(overrides)
    return subject.V4UnattendedShadowSnapshot(**values)  # type: ignore[arg-type]


def _run(
    tmp_path: Path,
    *,
    signal: FormalSignal | None = None,
    snapshot: subject.V4UnattendedShadowSnapshot | None = None,
    store: subject.V4UnattendedShadowStore | None = None,
    policy: V4GmoExecutionPolicy | None = None,
    now_utc: datetime | None = None,
) -> subject.V4ShadowControllerReport:
    resolved_store = store or subject.V4UnattendedShadowStore(
        _shadow_path(tmp_path, "shadow.sqlite3")
    )
    return subject.run_v4_unattended_shadow_cycle_once(
        signal=signal or _signal(),
        policy=policy or _policy(),
        snapshot=snapshot or _snapshot(),
        store=resolved_store,
        lock_path=_shadow_path(tmp_path, "shadow.lock"),
        now_utc=now_utc or _now(),
    )


def test_clear_snapshot_creates_non_authorizing_shadow_intent(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
    assert result.shadow_intent is not None
    assert result.shadow_intent.side is SignalDecision.BUY
    assert result.shadow_intent.size == 1_000
    assert result.shadow_intent.broker_post_authorized is False
    assert result.to_safe_dict() == {
        "status": "SHADOW_WOULD_ENTER_NON_AUTHORIZING",
        "blocked_reasons": [],
        "recorded": True,
        "shadow_intent_created": True,
        "broker_post_authorized": False,
        "actual_post_count": 0,
        "broker_read_performed": False,
        "broker_write_performed": False,
        "credential_read_performed": False,
        "network_access_performed": False,
        "live_ready": False,
        "unattended_live_supported": False,
    }


def test_stay_is_recorded_without_an_intent(tmp_path: Path) -> None:
    result = _run(tmp_path, signal=_signal(decision=SignalDecision.STAY))
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_NO_ACTION_STAY
    assert result.shadow_intent is None


def test_stay_still_evaluates_safety_gates(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        signal=_signal(decision=SignalDecision.STAY),
        snapshot=_snapshot(market_open=False),
    )
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert "MARKET_NOT_OPEN" in result.blocked_reasons
    assert result.shadow_intent is None


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    (
        (_snapshot(market_open=False), "MARKET_NOT_OPEN"),
        (_snapshot(spread_pips=Decimal("2.1")), "SPREAD_LIMIT_EXCEEDED"),
        (
            _snapshot(reference_deviation_pips=Decimal("5.1")),
            "REFERENCE_DEVIATION_LIMIT_EXCEEDED",
        ),
        (_snapshot(preflight=_preflight(position_count=1)), "POSITION_NOT_FLAT"),
        (
            _snapshot(preflight=_preflight(active_order_count=1)),
            "ACTIVE_ORDER_EXISTS",
        ),
        (
            _snapshot(preflight=_preflight(operator_halt_clear=False)),
            "OPERATOR_HALT_LATCHED",
        ),
    ),
)
def test_entry_gate_is_fail_closed(
    tmp_path: Path,
    snapshot: subject.V4UnattendedShadowSnapshot,
    reason: str,
) -> None:
    result = _run(tmp_path, snapshot=snapshot)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert reason in result.blocked_reasons
    assert result.shadow_intent is None


def test_duplicate_signal_is_refused_without_a_second_record(tmp_path: Path) -> None:
    store = subject.V4UnattendedShadowStore(_shadow_path(tmp_path, "shadow.sqlite3"))
    first = _run(tmp_path, store=store)
    second = _run(tmp_path, store=store)
    assert first.recorded is True
    assert second.status is subject.V4ShadowDecisionStatus.SHADOW_DUPLICATE_SIGNAL_REFUSED
    assert second.recorded is False
    assert second.shadow_intent is None


def test_second_actionable_signal_on_same_jst_day_is_blocked(tmp_path: Path) -> None:
    store = subject.V4UnattendedShadowStore(_shadow_path(tmp_path, "shadow.sqlite3"))
    first = _run(tmp_path, store=store)
    second_signal = _signal(
        observed_at_utc=_now() - timedelta(seconds=20),
        probability_up=Decimal("0.62"),
    )
    second = _run(tmp_path, store=store, signal=second_signal)
    assert first.status is subject.V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
    assert second.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert second.blocked_reasons == ("SHADOW_DAILY_ENTRY_CAP_REACHED",)
    assert second.shadow_intent is None


def test_sticky_halt_has_no_clear_path(tmp_path: Path) -> None:
    store = subject.V4UnattendedShadowStore(_shadow_path(tmp_path, "shadow.sqlite3"))
    store.latch_halt(reason="OPERATOR_KILL")
    result = _run(tmp_path, store=store)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_HALTED
    assert result.blocked_reasons == ("STICKY_HALT_OPERATOR_KILL",)
    assert not hasattr(store, "clear_halt")
    assert not hasattr(store, "reset")


def test_report_cannot_claim_live_activity(tmp_path: Path) -> None:
    result = _run(tmp_path)
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_REPORT_CANNOT_CLAIM_LIVE_ACTIVITY",
    ):
        replace(result, broker_post_authorized=True)
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_REPORT_CANNOT_CLAIM_LIVE_ACTIVITY",
    ):
        replace(result, actual_post_count=False)


def test_intent_requires_integer_zero_post_count(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.shadow_intent is not None
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_INTENT_CANNOT_AUTHORIZE_POST",
    ):
        replace(result.shadow_intent, actual_post_count=False)


def test_intent_rejects_malformed_typed_state(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.shadow_intent is not None
    mutations: tuple[dict[str, object], ...] = (
        {"cycle_ref": 1},
        {"policy_config_hash": 1},
        {"side": "BUY"},
        {"frozen_atr_24": Decimal("NaN")},
        {"planned_loss_bound_jpy": False},
    )
    for mutation in mutations:
        with pytest.raises(subject.V4UnattendedShadowError):
            replace(result.shadow_intent, **mutation)


def test_report_rejects_malformed_or_inconsistent_state(tmp_path: Path) -> None:
    result = _run(tmp_path)
    mutations: tuple[dict[str, object], ...] = (
        {"status": "SHADOW_WOULD_ENTER_NON_AUTHORIZING"},
        {"cycle_ref": "bad"},
        {"blocked_reasons": ["BAD"]},
        {"recorded": 1},
        {"shadow_intent": None},
        {"status": subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE},
    )
    for mutation in mutations:
        with pytest.raises(subject.V4UnattendedShadowError):
            replace(result, **mutation)


@pytest.mark.parametrize(
    ("policy", "signal"),
    (
        (
            replace(_policy(), strategy_version="OTHER"),
            _signal(strategy_version="OTHER"),
        ),
        (
            replace(_policy(), selected_horizon=FormalHorizon.MINUTES_10),
            _signal(horizon=FormalHorizon.MINUTES_10),
        ),
    ),
)
def test_non_frozen_policy_is_always_blocked(
    tmp_path: Path,
    policy: V4GmoExecutionPolicy,
    signal: FormalSignal,
) -> None:
    result = _run(tmp_path, policy=policy, signal=signal)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert "CONTROLLER_POLICY_NOT_FROZEN" in result.blocked_reasons
    assert result.shadow_intent is None


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("protection_contract_hash", "sha256:" + ("0" * 64)),
        ("max_loss_per_trade_yen", 5_001),
    ),
)
def test_mutated_frozen_risk_contract_is_blocked(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    policy = _policy()
    object.__setattr__(policy, field, value)
    result = _run(tmp_path, policy=policy)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert "CONTROLLER_POLICY_NOT_FROZEN" in result.blocked_reasons
    assert result.shadow_intent is None


def test_matching_forged_signal_config_pair_is_blocked(tmp_path: Path) -> None:
    forged_hash = "sha256:" + ("0" * 64)
    policy = replace(_policy(), signal_config_hash=forged_hash)
    signal = _signal(signal_config_hash=forged_hash)
    result = _run(tmp_path, policy=policy, signal=signal)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert "CONTROLLER_POLICY_NOT_FROZEN" in result.blocked_reasons
    assert result.shadow_intent is None


@pytest.mark.parametrize("field", ("signal", "policy", "snapshot", "store"))
def test_runner_rejects_duck_typed_inputs(tmp_path: Path, field: str) -> None:
    values: dict[str, object] = {
        "signal": _signal(),
        "policy": _policy(),
        "snapshot": _snapshot(),
        "store": subject.V4UnattendedShadowStore(
            _shadow_path(tmp_path, "shadow.sqlite3")
        ),
    }
    values[field] = object()
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_INPUT_TYPE_INVALID",
    ):
        subject.run_v4_unattended_shadow_cycle_once(
            signal=values["signal"],  # type: ignore[arg-type]
            policy=values["policy"],  # type: ignore[arg-type]
            snapshot=values["snapshot"],  # type: ignore[arg-type]
            store=values["store"],  # type: ignore[arg-type]
            lock_path=_shadow_path(tmp_path, "shadow.lock"),
            now_utc=_now(),
        )


@pytest.mark.parametrize(
    ("signal", "reason"),
    (
        (
            _signal(observed_at_utc=_now() - timedelta(seconds=121)),
            "SIGNAL_AGE_OUT_OF_RANGE",
        ),
        (
            _signal(observed_at_utc=_now() + timedelta(seconds=6)),
            "SIGNAL_AGE_OUT_OF_RANGE",
        ),
        (
            _signal(observed_at_utc=_now() - timedelta(minutes=31)),
            "SIGNAL_EXPIRED",
        ),
    ),
)
def test_signal_time_contract_is_fail_closed(
    tmp_path: Path,
    signal: FormalSignal,
    reason: str,
) -> None:
    result = _run(tmp_path, signal=signal)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert reason in result.blocked_reasons


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    (
        (_snapshot(quote_age_seconds=Decimal("5.1")), "QUOTE_AGE_OUT_OF_RANGE"),
        (_snapshot(quote_age_seconds=Decimal("-5.1")), "QUOTE_AGE_OUT_OF_RANGE"),
        (
            _snapshot(planned_loss_bound_jpy=5_001),
            "PLANNED_LOSS_LIMIT_EXCEEDED",
        ),
    ),
)
def test_quote_and_loss_contract_is_fail_closed(
    tmp_path: Path,
    snapshot: subject.V4UnattendedShadowSnapshot,
    reason: str,
) -> None:
    result = _run(tmp_path, snapshot=snapshot)
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert reason in result.blocked_reasons


def test_snapshot_rejects_preflight_subclass() -> None:
    class UnsafePreflight(V4GmoPreflightSnapshot):
        def blocked_reasons(self) -> tuple[str, ...]:
            return ()

    unsafe = UnsafePreflight(**vars(_preflight()))
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_PREFLIGHT_INVALID",
    ):
        _snapshot(preflight=unsafe)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("boot_reconciled", False),
        ("process_lock_held", False),
        ("data_fresh", False),
        ("clock_synchronized", False),
        ("notification_path_ready", False),
        ("broker_snapshot_fresh", False),
        ("entries_today", 1),
        ("daily_stop_clear", False),
        ("monthly_stop_clear", False),
        ("consecutive_loss_stop_clear", False),
    ),
)
def test_every_preflight_safety_gate_blocks(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    result = _run(
        tmp_path,
        snapshot=_snapshot(preflight=_preflight(**{field: value})),
    )
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert result.blocked_reasons
    assert result.shadow_intent is None


def test_entry_window_is_enforced(tmp_path: Path) -> None:
    policy = _policy()
    candidates = (
        _now().replace(hour=hour, minute=0, second=0)
        for hour in range(24)
    )
    blocked_now = next(
        candidate
        for candidate in candidates
        if not policy.entry_time_allowed(now_utc=candidate)
    )
    signal = _signal(observed_at_utc=blocked_now - timedelta(seconds=30))
    result = _run(
        tmp_path,
        policy=policy,
        signal=signal,
        now_utc=blocked_now,
    )
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert "ENTRY_TIME_NOT_ALLOWED" in result.blocked_reasons


def test_store_refuses_path_outside_shadow_exports(tmp_path: Path) -> None:
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_LEDGER_PATH_OUTSIDE_EXPORT_ROOT",
    ):
        subject.V4UnattendedShadowStore(tmp_path / "outside.sqlite3")


def test_store_rechecks_path_confinement_before_each_connection(
    tmp_path: Path,
) -> None:
    store = subject.V4UnattendedShadowStore(
        _shadow_path(tmp_path, "shadow.sqlite3")
    )
    with pytest.raises(AttributeError):
        store.path = tmp_path / "outside.sqlite3"  # type: ignore[misc]
    object.__setattr__(store, "_path", tmp_path / "outside.sqlite3")
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_LEDGER_PATH_OUTSIDE_EXPORT_ROOT",
    ):
        store.halt_reason()


def test_sqlite_connection_uses_no_follow_uri() -> None:
    source = inspect.getsource(subject.V4UnattendedShadowStore._connect)
    assert "nofollow=1" in source
    assert "uri=True" in source


def test_runner_refuses_lock_path_outside_shadow_exports(tmp_path: Path) -> None:
    store = subject.V4UnattendedShadowStore(
        _shadow_path(tmp_path, "shadow.sqlite3")
    )
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_LOCK_PATH_OUTSIDE_EXPORT_ROOT",
    ):
        subject.run_v4_unattended_shadow_cycle_once(
            signal=_signal(),
            policy=_policy(),
            snapshot=_snapshot(),
            store=store,
            lock_path=tmp_path / "outside.lock",
            now_utc=_now(),
        )


def test_record_once_rechecks_controller_digest_binding(tmp_path: Path) -> None:
    store = subject.V4UnattendedShadowStore(
        _shadow_path(tmp_path, "shadow.sqlite3")
    )
    store.bind_controller(controller_digest="sha256:bound")
    with pytest.raises(
        subject.V4UnattendedShadowError,
        match="SHADOW_CONTROLLER_BINDING_MISMATCH",
    ):
        store.record_once(
            signal_fingerprint="a" * 64,
            cycle_ref="b" * 64,
            controller_digest="sha256:different",
            trading_day_jst="2026-07-20",
            proposed_status=(
                subject.V4ShadowDecisionStatus.SHADOW_NO_ACTION_STAY
            ),
            intent_digest=None,
            blocked_reasons=(),
            recorded_at_utc=_now(),
        )


def test_record_once_applies_sticky_halt_inside_transaction(tmp_path: Path) -> None:
    store = subject.V4UnattendedShadowStore(
        _shadow_path(tmp_path, "shadow.sqlite3")
    )
    digest = "sha256:bound"
    store.bind_controller(controller_digest=digest)
    store.latch_halt(reason="OPERATOR_KILL")
    stored = store.record_once(
        signal_fingerprint="a" * 64,
        cycle_ref="b" * 64,
        controller_digest=digest,
        trading_day_jst="2026-07-20",
        proposed_status=(
            subject.V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING
        ),
        intent_digest="c" * 64,
        blocked_reasons=(),
        recorded_at_utc=_now(),
    )
    assert stored.status is subject.V4ShadowDecisionStatus.SHADOW_HALTED
    assert stored.blocked_reasons == ("STICKY_HALT_OPERATOR_KILL",)
    assert stored.recorded is True


def test_lock_contention_returns_safe_unrecorded_report(tmp_path: Path) -> None:
    lock = H11AutoProcessLock(_shadow_path(tmp_path, "shadow.lock"))
    assert lock.acquire() is True
    try:
        result = _run(tmp_path)
    finally:
        lock.release()
    assert result.status is subject.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    assert result.blocked_reasons == ("SHADOW_PROCESS_LOCK_HELD",)
    assert result.recorded is False
    assert result.shadow_intent is None


def test_module_has_no_live_or_external_dependency() -> None:
    source = inspect.getsource(subject)
    parsed = ast.parse(source)
    imported_app_modules = {
        node.module
        for node in ast.walk(parsed)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("app.")
    }
    assert imported_app_modules == {
        "app.h11_auto.contracts",
        "app.h11_auto.persistence",
        "app.h11_auto.v4_gmo_contracts",
        "app.h11_auto.v4_gmo_protection",
    }
    reachable_sources = _reachable_app_sources(
        root_module="app.h11_auto.v4_unattended_shadow_controller",
        app_root=Path(subject.__file__).parents[1],
    )
    for forbidden in (
        "app.private_api",
        "app.security.real_broker_post_hard_guard",
        "h11_v4_gmo_actual_transport",
        "h11_v4_gmo_actual_adapter",
        "h11_v4_gmo_actual_coordinator",
        "Keychain",
        "Pushover",
        "SMTP",
        "cancelOrders",
        "closeOrder",
        "/private/v1/order",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "scheduler",
        "polling",
        "LaunchAgent",
        "launchctl",
        "cron",
    ):
        for module_name, module_source in reachable_sources.items():
            assert forbidden not in module_source, module_name


def _reachable_app_sources(
    *,
    root_module: str,
    app_root: Path,
) -> dict[str, str]:
    pending = [root_module]
    visited: dict[str, str] = {}
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        module_path = _app_module_path(
            module_name=module_name,
            app_root=app_root,
        )
        module_source = module_path.read_text(encoding="utf-8")
        visited[module_name] = module_source
        tree = ast.parse(module_source, filename=str(module_path))
        _assert_static_safe_imports(tree=tree, module_name=module_name)
        module_parts = module_name.split(".")
        for length in range(1, len(module_parts)):
            package_name = ".".join(module_parts[:length])
            package_path = _optional_app_module_path(
                module_name=package_name,
                app_root=app_root,
            )
            if (
                package_path is not None
                and package_path.name == "__init__.py"
                and package_name not in visited
            ):
                pending.append(package_name)
        for imported_name in _local_app_imports(
            tree=tree,
            current_module=module_name,
            current_is_package=module_path.name == "__init__.py",
            app_root=app_root,
        ):
            if imported_name not in visited:
                pending.append(imported_name)
    return visited


def _local_app_imports(
    *,
    tree: ast.AST,
    current_module: str,
    current_is_package: bool,
    app_root: Path,
) -> set[str]:
    imported: set[str] = set()
    current_package = (
        current_module if current_is_package else current_module.rpartition(".")[0]
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(
                alias.name
                for alias in node.names
                if alias.name == "app" or alias.name.startswith("app.")
            )
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            package_parts = current_package.split(".")
            keep = len(package_parts) - node.level + 1
            base_parts = package_parts[:keep]
            if node.module:
                base_parts.extend(node.module.split("."))
            base = ".".join(base_parts)
        else:
            base = node.module or ""
        if base != "app" and not base.startswith("app."):
            continue
        imported.add(base)
        base_path = _optional_app_module_path(
            module_name=base,
            app_root=app_root,
        )
        if base_path is None:
            raise AssertionError(f"unresolved local import: {base}")
        defined_names = _defined_module_names(base_path)
        for alias in node.names:
            if alias.name == "*":
                raise AssertionError(f"wildcard local import from {base}")
            candidate = f"{base}.{alias.name}"
            if _optional_app_module_path(
                module_name=candidate,
                app_root=app_root,
            ) is not None:
                imported.add(candidate)
            elif alias.name not in defined_names:
                raise AssertionError(
                    f"unresolved local import symbol: {base}.{alias.name}"
                )
    return imported


def _app_module_path(*, module_name: str, app_root: Path) -> Path:
    path = _optional_app_module_path(module_name=module_name, app_root=app_root)
    if path is None:
        raise AssertionError(f"unresolved local import: {module_name}")
    return path


def _optional_app_module_path(
    *,
    module_name: str,
    app_root: Path,
) -> Path | None:
    relative_parts = module_name.split(".")[1:]
    if not relative_parts:
        candidates = (app_root / "__init__.py",)
    else:
        base = app_root.joinpath(*relative_parts)
        candidates = (base.with_suffix(".py"), base / "__init__.py")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _assert_static_safe_imports(*, tree: ast.AST, module_name: str) -> None:
    allowed_stdlib_roots = {
        "__future__",
        "contextlib",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fcntl",
        "hashlib",
        "json",
        "pathlib",
        "sqlite3",
        "typing",
        "zoneinfo",
    }
    forbidden_dynamic_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "exec_module",
        "find_spec",
        "import_module",
        "load_module",
        "load_source",
        "module_from_spec",
        "run_module",
        "run_path",
        "spec_from_file_location",
    }
    forbidden_dynamic_names = {
        "__builtins__",
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
        "vars",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden_dynamic_names, (
                f"dynamic namespace access {node.id!r} reachable from {module_name}"
            )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in forbidden_dynamic_names, (
                f"dynamic namespace token {node.value!r} reachable from {module_name}"
            )
        imported_names: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            imported_names = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported_names = (node.module,)
        for imported_name in imported_names:
            root = imported_name.split(".", 1)[0]
            assert root == "app" or root in allowed_stdlib_roots, (
                f"unsafe import root {root!r} reachable from {module_name}"
            )
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr
        else:
            continue
        assert called_name not in forbidden_dynamic_calls, (
            f"dynamic code/import call {called_name!r} reachable from {module_name}"
        )


def _defined_module_names(module_path: Path) -> set[str]:
    tree = ast.parse(
        module_path.read_text(encoding="utf-8"),
        filename=str(module_path),
    )
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names
