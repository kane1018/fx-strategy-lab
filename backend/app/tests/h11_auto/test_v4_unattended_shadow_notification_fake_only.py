from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.h11_auto import v4_unattended_shadow_controller as controller
from app.h11_auto.contracts import FormalHorizon, FormalSignal, SignalDecision
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy, V4GmoPreflightSnapshot
from app.h11_auto.v4_gmo_protection import H11_V4_GMO_PROTECTION_CONTRACT_HASH
from app.services import h11_v4_notification_binding_no_post as binding
from app.services import h11_v4_unattended_shadow_notification as subject


@pytest.fixture(autouse=True)
def _isolated_shadow_export_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(controller, "_SHADOW_EXPORT_ROOT", tmp_path / "backend" / "shadow_exports")


def _shadow_path(tmp_path: Path, name: str) -> Path:
    return tmp_path / "backend" / "shadow_exports" / name


def _policy() -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version="SHORT_V1",
        signal_config_hash=controller.V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
        selected_horizon=FormalHorizon.MINUTES_30,
        protection_contract_hash=H11_V4_GMO_PROTECTION_CONTRACT_HASH,
    )


def _now() -> datetime:
    return datetime(2026, 7, 24, 1, 0, tzinfo=UTC)


def _signal(*, decision: SignalDecision = SignalDecision.BUY) -> FormalSignal:
    observed = _now() - timedelta(seconds=30)
    return FormalSignal(
        strategy_version="SHORT_V1",
        signal_config_hash=controller.V4_UNATTENDED_SHADOW_SIGNAL_CONFIG_HASH,
        horizon=FormalHorizon.MINUTES_30,
        observed_at_utc=observed,
        valid_until_utc=observed + timedelta(minutes=30),
        decision=decision,
        probability_up=Decimal("0.61"),
    )


def _preflight(**overrides: object) -> V4GmoPreflightSnapshot:
    values: dict[str, object] = {
        "boot_reconciled": True,
        "process_lock_held": True,
        "data_fresh": True,
        "clock_synchronized": True,
        "notification_path_ready": True,
        "broker_snapshot_fresh": True,
    }
    values.update(overrides)
    return V4GmoPreflightSnapshot(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> controller.V4UnattendedShadowSnapshot:
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
    return controller.V4UnattendedShadowSnapshot(**values)  # type: ignore[arg-type]


def _report(
    tmp_path: Path,
    *,
    signal: FormalSignal | None = None,
    snapshot: controller.V4UnattendedShadowSnapshot | None = None,
    store: controller.V4UnattendedShadowStore | None = None,
) -> controller.V4ShadowControllerReport:
    resolved_store = store or controller.V4UnattendedShadowStore(
        _shadow_path(tmp_path, "shadow.sqlite3")
    )
    return controller.run_v4_unattended_shadow_cycle_once(
        signal=signal or _signal(),
        policy=_policy(),
        snapshot=snapshot or _snapshot(),
        store=resolved_store,
        lock_path=_shadow_path(tmp_path, "shadow.lock"),
        now_utc=_now(),
    )


def _blocked_report(tmp_path: Path) -> controller.V4ShadowControllerReport:
    return _report(tmp_path, snapshot=_snapshot(market_open=False))


def _would_enter_report(tmp_path: Path) -> controller.V4ShadowControllerReport:
    return _report(tmp_path)


def _stay_report(tmp_path: Path) -> controller.V4ShadowControllerReport:
    return _report(tmp_path, signal=_signal(decision=SignalDecision.STAY))


def _halted_report(tmp_path: Path) -> controller.V4ShadowControllerReport:
    store = controller.V4UnattendedShadowStore(_shadow_path(tmp_path, "shadow.sqlite3"))
    store.latch_halt(reason="OPERATOR_KILL")
    return _report(tmp_path, store=store)


def test_routine_blocked_cycle_is_not_notify_worthy(tmp_path: Path) -> None:
    report = _blocked_report(tmp_path)
    event = subject.decide_shadow_notification_event(
        report=report, previous_status=None
    )
    assert event is None


def test_stay_cycle_is_not_notify_worthy(tmp_path: Path) -> None:
    report = _stay_report(tmp_path)
    event = subject.decide_shadow_notification_event(
        report=report, previous_status=None
    )
    assert event is None


def test_first_actionable_observation_is_notify_worthy(tmp_path: Path) -> None:
    report = _would_enter_report(tmp_path)
    event = subject.decide_shadow_notification_event(
        report=report,
        previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
    )
    assert event is binding.H11V4NotificationEvent.SHADOW_ACTIONABLE_OBSERVED
    assert event not in binding.CRITICAL_EVENTS


def test_repeated_actionable_status_is_deduped(tmp_path: Path) -> None:
    report = _would_enter_report(tmp_path)
    event = subject.decide_shadow_notification_event(
        report=report,
        previous_status=controller.V4ShadowDecisionStatus.SHADOW_WOULD_ENTER_NON_AUTHORIZING,
    )
    assert event is None


def test_first_halt_is_notify_worthy_and_critical(tmp_path: Path) -> None:
    report = _halted_report(tmp_path)
    event = subject.decide_shadow_notification_event(
        report=report,
        previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
    )
    assert event is binding.H11V4NotificationEvent.SHADOW_HALT_ENGAGED
    assert event in binding.CRITICAL_EVENTS


def test_repeated_halt_every_subsequent_cycle_is_deduped(tmp_path: Path) -> None:
    # This is the scenario that matters most: a sticky HALT with no clear/reset
    # path means every cycle after the first will keep reporting SHADOW_HALTED.
    # Without dedup this would notify forever.
    store = controller.V4UnattendedShadowStore(_shadow_path(tmp_path, "shadow.sqlite3"))
    store.latch_halt(reason="OPERATOR_KILL")
    first = _report(tmp_path, store=store)
    second = _report(
        tmp_path,
        store=store,
        signal=_signal(decision=SignalDecision.SELL),
    )
    assert first.status is controller.V4ShadowDecisionStatus.SHADOW_HALTED
    assert second.status is controller.V4ShadowDecisionStatus.SHADOW_HALTED
    first_event = subject.decide_shadow_notification_event(
        report=first, previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE
    )
    second_event = subject.decide_shadow_notification_event(
        report=second, previous_status=first.status
    )
    assert first_event is binding.H11V4NotificationEvent.SHADOW_HALT_ENGAGED
    assert second_event is None


def test_first_ever_cycle_with_no_previous_status_still_notifies_when_worthy(
    tmp_path: Path,
) -> None:
    # A pre-latched HALT observed on the very first cycle (previous_status=None)
    # must still notify -- "no previous status" is itself a transition.
    report = _halted_report(tmp_path)
    event = subject.decide_shadow_notification_event(report=report, previous_status=None)
    assert event is binding.H11V4NotificationEvent.SHADOW_HALT_ENGAGED


def test_duplicate_signal_refused_status_is_not_notify_worthy(tmp_path: Path) -> None:
    store = controller.V4UnattendedShadowStore(_shadow_path(tmp_path, "shadow.sqlite3"))
    signal = _signal()
    first = _report(tmp_path, store=store, signal=signal)
    second = _report(tmp_path, store=store, signal=signal)
    assert second.status is controller.V4ShadowDecisionStatus.SHADOW_DUPLICATE_SIGNAL_REFUSED
    event = subject.decide_shadow_notification_event(
        report=second, previous_status=first.status
    )
    assert event is None


def test_decision_rejects_duck_typed_report(tmp_path: Path) -> None:
    from types import SimpleNamespace

    with pytest.raises(
        subject.V4UnattendedShadowNotificationError, match="SHADOW_NOTIFICATION_REPORT_INVALID"
    ):
        subject.decide_shadow_notification_event(
            report=SimpleNamespace(status=controller.V4ShadowDecisionStatus.SHADOW_HALTED),  # type: ignore[arg-type]
            previous_status=None,
        )


def test_decision_rejects_duck_typed_previous_status(tmp_path: Path) -> None:
    report = _blocked_report(tmp_path)
    with pytest.raises(
        subject.V4UnattendedShadowNotificationError,
        match="SHADOW_NOTIFICATION_PREVIOUS_STATUS_INVALID",
    ):
        subject.decide_shadow_notification_event(
            report=report, previous_status="SHADOW_BLOCKED_SAFE"  # type: ignore[arg-type]
        )


def test_notify_shadow_cycle_once_skips_routine_cycles_without_touching_notifier(
    tmp_path: Path,
) -> None:
    fake_pushover = binding.H11V4FakePushoverTransport()
    fake_email = binding.H11V4FakeEmailTransport()
    notifier = binding.H11V4DisabledDualRouteNotifier(primary=fake_pushover, secondary=fake_email)
    report = _blocked_report(tmp_path)
    result = subject.notify_shadow_cycle_once(
        report=report, previous_status=None, notifier=notifier
    )
    assert result is None
    assert fake_pushover.calls == []
    assert fake_email.calls == []


def test_notify_shadow_cycle_once_sends_exactly_once_for_a_notify_worthy_transition(
    tmp_path: Path,
) -> None:
    fake_pushover = binding.H11V4FakePushoverTransport()
    fake_email = binding.H11V4FakeEmailTransport()
    notifier = binding.H11V4DisabledDualRouteNotifier(primary=fake_pushover, secondary=fake_email)
    report = _halted_report(tmp_path)
    result = subject.notify_shadow_cycle_once(
        report=report,
        previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
        notifier=notifier,
    )
    assert result is not None
    assert bool(result) is False
    assert fake_pushover.calls == [binding.H11V4NotificationEvent.SHADOW_HALT_ENGAGED]
    assert fake_email.calls == [binding.H11V4NotificationEvent.SHADOW_HALT_ENGAGED]
    assert result.primary_ready is True
    assert result.secondary_ready is True


def test_notify_shadow_cycle_once_sends_the_non_critical_actionable_event(
    tmp_path: Path,
) -> None:
    # The critical (HALT) path is covered above; this exercises the
    # non-critical SHADOW_ACTIONABLE_OBSERVED path through the full
    # notify_once composition, not just the pure decision function.
    fake_pushover = binding.H11V4FakePushoverTransport()
    fake_email = binding.H11V4FakeEmailTransport()
    notifier = binding.H11V4DisabledDualRouteNotifier(primary=fake_pushover, secondary=fake_email)
    report = _would_enter_report(tmp_path)
    result = subject.notify_shadow_cycle_once(
        report=report,
        previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
        notifier=notifier,
    )
    assert result is not None
    assert fake_pushover.calls == [binding.H11V4NotificationEvent.SHADOW_ACTIONABLE_OBSERVED]
    assert fake_email.calls == [binding.H11V4NotificationEvent.SHADOW_ACTIONABLE_OBSERVED]
    assert result.primary_ready is True
    assert result.secondary_ready is True
    assert result.halt_required is False


def test_notify_shadow_cycle_once_rejects_a_non_wrapper_notifier(tmp_path: Path) -> None:
    report = _halted_report(tmp_path)
    with pytest.raises(
        subject.V4UnattendedShadowNotificationError,
        match="SHADOW_NOTIFICATION_NOTIFIER_CONTRACT_INVALID",
    ):
        subject.notify_shadow_cycle_once(
            report=report,
            previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
            notifier=object(),  # type: ignore[arg-type]
        )


def test_notify_shadow_cycle_once_with_default_refusing_notifier_raises_on_send(
    tmp_path: Path,
) -> None:
    # The default H11V4DisabledDualRouteNotifier() uses Refusing transports --
    # confirms this module inherits that structural incapacity rather than
    # silently swallowing it.
    notifier = binding.H11V4DisabledDualRouteNotifier()
    report = _halted_report(tmp_path)
    with pytest.raises(
        binding.H11V4NotificationError, match="PUSHOVER_TRANSPORT_DISABLED_NO_POST"
    ):
        subject.notify_shadow_cycle_once(
            report=report,
            previous_status=controller.V4ShadowDecisionStatus.SHADOW_BLOCKED_SAFE,
            notifier=notifier,
        )


def test_module_has_no_real_transport_or_credential_code_tokens() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "smtplib",
        "subprocess",
        "keyring",
        "os.environ",
        "os.getenv",
        "load_dotenv",
        "find-generic-password",
    ):
        assert forbidden not in source, forbidden


def test_module_reachable_app_imports_avoid_real_transport_and_write_modules() -> None:
    reachable = _reachable_app_modules(
        root_module="app.services.h11_v4_unattended_shadow_notification",
        app_root=Path(subject.__file__).parents[1],
    )
    forbidden_fragments = (
        "actual",
        "canary",
        "readonly_preflight",
        "post_canary",
        "coordinator",
        "hard_guard",
        "launchd",
        "private_api",
        "h11_manual",
    )
    for module_name in reachable:
        for fragment in forbidden_fragments:
            assert fragment not in module_name, module_name


def _reachable_app_modules(*, root_module: str, app_root: Path) -> set[str]:
    pending = [root_module]
    visited: set[str] = set()
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        module_path = _app_module_path(module_name=module_name, app_root=app_root)
        if module_path is None:
            continue
        visited.add(module_name)
        parts = module_name.split(".")
        pending.extend(".".join(parts[:length]) for length in range(1, len(parts)))
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                "app."
            ):
                pending.append(node.module)
            elif isinstance(node, ast.Import):
                pending.extend(
                    alias.name
                    for alias in node.names
                    if alias.name == "app" or alias.name.startswith("app.")
                )
    return visited


def _app_module_path(*, module_name: str, app_root: Path) -> Path | None:
    relative = module_name.split(".")[1:]
    if not relative:
        return None
    base = app_root.joinpath(*relative)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None
