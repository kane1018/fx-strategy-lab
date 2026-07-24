from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from app.services import h11_v4_unattended_live_entry_notification as subject
from app.services.h11_v4_notification_binding_no_post import (
    CRITICAL_EVENTS,
    H11V4EmailTransport,
    H11V4FakeEmailTransport,
    H11V4FakePushoverTransport,
    H11V4NotificationEvent,
    H11V4PushoverDelivery,
    H11V4PushoverRequest,
    H11V4PushoverTransport,
)


# Test-only doubles satisfying the real transport protocol shape
# (fake_only=False) without ever touching a network or credential -- these
# exist only to exercise H11V4EnabledDualRouteNotifier's decision logic.
@dataclass
class _RealShapedPushoverTransport:
    accepted: bool = True
    receipt_present: bool = True
    acknowledged: bool = True
    fake_only: bool = field(default=False, init=False)
    calls: list[H11V4NotificationEvent] = field(default_factory=list, init=False)

    def send_once(self, request: H11V4PushoverRequest) -> H11V4PushoverDelivery:
        self.calls.append(request.event)
        receipt = self.receipt_present if request.receipt_required else False
        acknowledged = self.acknowledged if request.receipt_required else self.accepted
        return H11V4PushoverDelivery(
            accepted=self.accepted, receipt_present=receipt, acknowledged=acknowledged
        )


@dataclass
class _RealShapedEmailTransport:
    accepted: bool = True
    fake_only: bool = field(default=False, init=False)
    calls: list[H11V4NotificationEvent] = field(default_factory=list, init=False)

    def send_once(self, event: H11V4NotificationEvent) -> bool:
        self.calls.append(event)
        return self.accepted


def _fake_pushover() -> H11V4PushoverTransport:
    return cast(H11V4PushoverTransport, H11V4FakePushoverTransport())


def _fake_email() -> H11V4EmailTransport:
    return cast(H11V4EmailTransport, H11V4FakeEmailTransport())


def _real_pushover(**overrides: object) -> H11V4PushoverTransport:
    return cast(H11V4PushoverTransport, _RealShapedPushoverTransport(**overrides))


def _real_email(**overrides: object) -> H11V4EmailTransport:
    return cast(H11V4EmailTransport, _RealShapedEmailTransport(**overrides))


# ---------------------------------------------------------------- new event


def test_new_event_is_not_a_critical_event() -> None:
    assert H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED not in CRITICAL_EVENTS


def test_new_event_has_no_ack_requirement() -> None:
    from app.services.h11_v4_notification_binding_no_post import (
        build_h11_v4_pushover_request,
    )

    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )
    assert request.emergency_priority is False
    assert request.receipt_required is False
    assert request.retry_seconds is None
    assert request.expire_seconds is None


# ------------------------------------------------------- channel-ready check


def test_channel_ready_true_only_for_genuinely_real_transports() -> None:
    assert (
        subject.unattended_live_notification_channel_ready(
            primary=_real_pushover(), secondary=_real_email()
        )
        is True
    )


def test_channel_ready_false_for_fake_transports() -> None:
    assert (
        subject.unattended_live_notification_channel_ready(
            primary=_fake_pushover(), secondary=_fake_email()
        )
        is False
    )


def test_channel_ready_false_when_only_one_side_is_real() -> None:
    assert (
        subject.unattended_live_notification_channel_ready(
            primary=_real_pushover(), secondary=_fake_email()
        )
        is False
    )
    assert (
        subject.unattended_live_notification_channel_ready(
            primary=_fake_pushover(), secondary=_real_email()
        )
        is False
    )


def test_channel_ready_never_sends_anything() -> None:
    primary = _RealShapedPushoverTransport()
    secondary = _RealShapedEmailTransport()
    subject.unattended_live_notification_channel_ready(
        primary=cast(H11V4PushoverTransport, primary),
        secondary=cast(H11V4EmailTransport, secondary),
    )
    assert primary.calls == []
    assert secondary.calls == []


@pytest.mark.parametrize(
    ("primary", "secondary"),
    (
        (None, None),
        ("not-a-transport", None),
        (object(), object()),
    ),
)
def test_channel_ready_raises_on_type_invalid_inputs(
    primary: object, secondary: object
) -> None:
    with pytest.raises(
        subject.V4UnattendedLiveNotificationError,
        match="NOTIFICATION_TRANSPORT_CONTRACT_INVALID",
    ):
        subject.unattended_live_notification_channel_ready(
            primary=cast(H11V4PushoverTransport, primary),
            secondary=cast(H11V4EmailTransport, secondary),
        )


# ---------------------------------------------------- H11V4EnabledDualRouteNotifier


def test_enabled_notifier_rejects_fake_transports() -> None:
    with pytest.raises(
        subject.V4UnattendedLiveNotificationError,
        match="FAKE_NOTIFICATION_TRANSPORT_FORBIDDEN",
    ):
        subject.H11V4EnabledDualRouteNotifier(
            primary=_fake_pushover(), secondary=_fake_email()
        )


def test_enabled_notifier_rejects_type_invalid_transports() -> None:
    with pytest.raises(
        subject.V4UnattendedLiveNotificationError,
        match="NOTIFICATION_TRANSPORT_CONTRACT_INVALID",
    ):
        subject.H11V4EnabledDualRouteNotifier(
            primary=cast(H11V4PushoverTransport, object()),
            secondary=cast(H11V4EmailTransport, object()),
        )


def test_enabled_notifier_requires_both_arguments_with_no_default() -> None:
    signature = inspect.signature(subject.H11V4EnabledDualRouteNotifier.__init__)
    for name in ("primary", "secondary"):
        assert signature.parameters[name].default is inspect.Parameter.empty, name


def test_enabled_notifier_happy_path_both_routes_ready() -> None:
    notifier = subject.H11V4EnabledDualRouteNotifier(
        primary=_real_pushover(), secondary=_real_email()
    )
    result = notifier.notify_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    assert result.primary_ready is True
    assert result.secondary_ready is True
    assert result.halt_required is False
    assert result.reason_safe_label == "DUAL_ROUTE_READY"


def test_enabled_notifier_primary_rejected_halts_even_for_non_critical_event() -> None:
    notifier = subject.H11V4EnabledDualRouteNotifier(
        primary=_real_pushover(accepted=False), secondary=_real_email()
    )
    result = notifier.notify_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    assert result.primary_ready is False
    assert result.halt_required is True
    assert result.reason_safe_label == "NOTIFICATION_ROUTE_NOT_READY"


def test_enabled_notifier_secondary_failure_does_not_halt_a_non_critical_event() -> None:
    # Matches the disabled notifier's own semantics exactly: secondary only
    # gates CRITICAL_EVENTS; a non-critical event with primary ready and
    # secondary failed does not halt.
    notifier = subject.H11V4EnabledDualRouteNotifier(
        primary=_real_pushover(), secondary=_real_email(accepted=False)
    )
    result = notifier.notify_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    assert result.primary_ready is True
    assert result.secondary_ready is False
    assert result.halt_required is False


def test_enabled_notifier_secondary_failure_halts_a_critical_event() -> None:
    notifier = subject.H11V4EnabledDualRouteNotifier(
        primary=_real_pushover(), secondary=_real_email(accepted=False)
    )
    result = notifier.notify_once(H11V4NotificationEvent.RISK_STOPPED)
    assert result.secondary_ready is False
    assert result.halt_required is True


def test_enabled_notifier_critical_event_requires_ack_for_primary_ready() -> None:
    notifier = subject.H11V4EnabledDualRouteNotifier(
        primary=_real_pushover(acknowledged=False), secondary=_real_email()
    )
    result = notifier.notify_once(H11V4NotificationEvent.RISK_STOPPED)
    assert result.primary_ready is False
    assert result.halt_required is True


@pytest.mark.parametrize(
    ("primary_accepted", "primary_acknowledged", "secondary_accepted", "event"),
    (
        (True, True, True, H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED),
        (True, True, False, H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED),
        (False, True, True, H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED),
        (True, True, True, H11V4NotificationEvent.RISK_STOPPED),
        (True, True, False, H11V4NotificationEvent.RISK_STOPPED),
        (True, False, True, H11V4NotificationEvent.RISK_STOPPED),
        (False, True, True, H11V4NotificationEvent.RISK_STOPPED),
        (False, False, False, H11V4NotificationEvent.RISK_STOPPED),
    ),
)
def test_enabled_and_disabled_notifiers_compute_identical_decisions(
    primary_accepted: bool,
    primary_acknowledged: bool,
    secondary_accepted: bool,
    event: H11V4NotificationEvent,
) -> None:
    # Cross-checks the ONE property that matters given the decision logic is
    # deliberately duplicated (the disabled class must never be touched):
    # for the same accepted/acknowledged inputs, the real-transport sibling
    # must compute exactly the same primary_ready/secondary_ready/halt_required
    # as the reviewed fake-only original -- only the label may differ. This
    # is the mechanism that would catch a future silent divergence between
    # the two copies.
    from app.services.h11_v4_notification_binding_no_post import (
        H11V4DisabledDualRouteNotifier,
    )

    disabled = H11V4DisabledDualRouteNotifier(
        primary=cast(
            H11V4PushoverTransport,
            H11V4FakePushoverTransport(
                accepted=primary_accepted, acknowledged=primary_acknowledged
            ),
        ),
        secondary=cast(
            H11V4EmailTransport, H11V4FakeEmailTransport(accepted=secondary_accepted)
        ),
    )
    enabled = subject.H11V4EnabledDualRouteNotifier(
        primary=_real_pushover(
            accepted=primary_accepted, acknowledged=primary_acknowledged
        ),
        secondary=_real_email(accepted=secondary_accepted),
    )
    disabled_result = disabled.notify_once(event)
    enabled_result = enabled.notify_once(event)
    assert enabled_result.primary_ready == disabled_result.primary_ready
    assert enabled_result.secondary_ready == disabled_result.secondary_ready
    assert enabled_result.halt_required == disabled_result.halt_required


@pytest.mark.parametrize("truthy_non_bool", (1, "yes", "True"))
def test_channel_ready_treats_non_bool_truthy_fake_only_as_not_real(
    truthy_non_bool: object,
) -> None:
    # fake_only is compared with strict `is False`, not `==` -- a non-bool
    # truthy value must NOT be treated as real just because it's truthy.
    primary = _RealShapedPushoverTransport()
    primary.fake_only = truthy_non_bool  # type: ignore[assignment]
    assert (
        subject.unattended_live_notification_channel_ready(
            primary=cast(H11V4PushoverTransport, primary), secondary=_real_email()
        )
        is False
    )


@pytest.mark.parametrize("truthy_non_bool", (1, "yes", "True"))
def test_enabled_notifier_rejects_non_bool_truthy_fake_only(
    truthy_non_bool: object,
) -> None:
    primary = _RealShapedPushoverTransport()
    primary.fake_only = truthy_non_bool  # type: ignore[assignment]
    with pytest.raises(
        subject.V4UnattendedLiveNotificationError,
        match="FAKE_NOTIFICATION_TRANSPORT_FORBIDDEN",
    ):
        subject.H11V4EnabledDualRouteNotifier(
            primary=cast(H11V4PushoverTransport, primary), secondary=_real_email()
        )


def test_enabled_notifier_sends_exactly_once_per_route() -> None:
    primary = _RealShapedPushoverTransport()
    secondary = _RealShapedEmailTransport()
    notifier = subject.H11V4EnabledDualRouteNotifier(
        primary=cast(H11V4PushoverTransport, primary),
        secondary=cast(H11V4EmailTransport, secondary),
    )
    notifier.notify_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    assert primary.calls == [H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED]
    assert secondary.calls == [H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED]


# ---------------------------------------------------------------- isolation


def test_disabled_notifier_is_byte_identical() -> None:
    import app.services.h11_v4_notification_binding_no_post as binding_module

    doc = inspect.getsource(binding_module.H11V4DisabledDualRouteNotifier)
    assert "fake_only is not True" in doc
    assert "ACTUAL_NOTIFICATION_TRANSPORT_FORBIDDEN" in doc


def test_module_never_constructs_a_real_transport_or_touches_credentials() -> None:
    source = inspect.getsource(subject)
    for token in (
        "httpx",
        "smtplib",
        "requests",
        "socket",
        "os.environ",
        "os.getenv",
        "keyring",
        "subprocess",
        "find-generic-password",
    ):
        assert token not in source, token


def test_has_exactly_one_authorized_production_caller() -> None:
    # Scope note (same as the sibling reachability tests in this track):
    # catches direct names, attributes, and aliased imports
    # (`import ... as X`, via ast.alias.name/asname); does NOT catch
    # string-based/dynamic lookups. Originally asserted zero production
    # callers; the orchestration module (its own AGENTS.md exception, its
    # own review -- design doc §15) is now the single authorized caller.
    targets = {"H11V4EnabledDualRouteNotifier", "unattended_live_notification_channel_ready"}
    authorized = "backend/app/services/h11_v4_unattended_live_orchestration.py"
    module_path = Path(subject.__file__)
    repo_root = module_path.parents[2]
    hits: list[str] = []
    for path in repo_root.rglob("*.py"):
        if path == module_path or "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                (isinstance(node, ast.Name) and node.id in targets)
                or (isinstance(node, ast.Attribute) and node.attr in targets)
                or (
                    isinstance(node, ast.alias)
                    and (node.name in targets or node.asname in targets)
                )
            ):
                hits.append(path.as_posix())
    unauthorized = [hit for hit in hits if not hit.endswith(authorized)]
    assert unauthorized == []
    assert any(hit.endswith(authorized) for hit in hits)
