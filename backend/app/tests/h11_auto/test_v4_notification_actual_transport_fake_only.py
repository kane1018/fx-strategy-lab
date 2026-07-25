from __future__ import annotations

import smtplib
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import parse_qs

import httpx
import pytest

from app.services import h11_v4_notification_actual_preparation as preparation_module
from app.services import h11_v4_unattended_live_entry_notification as entry_notification
from app.services.h11_v4_notification_actual_preparation import (
    H11V4NotificationCredentialBundle,
)
from app.services.h11_v4_notification_actual_transport import (
    H11V4ActualEmailTransport,
    H11V4ActualNotificationTransportError,
    H11V4ActualPushoverTransport,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4EmailTransport,
    H11V4NotificationEvent,
    H11V4PushoverTransport,
    build_h11_v4_pushover_request,
)


def _credential_bundle(
    *,
    pushover_token: str,
    pushover_user: str,
    smtp_username: str,
    smtp_password: str,
) -> H11V4NotificationCredentialBundle:
    def reader(
        _service: str, account: str
    ) -> preparation_module._SealedNotificationSecret:
        values = {
            "pushover-api-token": pushover_token,
            "pushover-user-key": pushover_user,
            "smtp-username": smtp_username,
            "smtp-app-password": smtp_password,
        }
        return preparation_module._SealedNotificationSecret(values[account])

    return H11V4NotificationCredentialBundle(reader=reader)


@dataclass
class _FakeSmtp:
    ehlo_result: tuple[int, str] = (250, "OK")
    tls_error: BaseException | None = None
    login_error: BaseException | None = None
    send_error: BaseException | None = None

    enter_called: bool = False
    starttls_called: bool = False
    login_called: bool = False
    send_called: bool = False

    def __enter__(self) -> _FakeSmtp:
        self.enter_called = True
        return self

    def __exit__(self, *args: object) -> None:  # noqa: ARG002
        return None

    def ehlo(self) -> tuple[int, str]:
        return self.ehlo_result

    def starttls(self, *, context: object) -> object:  # noqa: ARG002
        self.starttls_called = True
        if self.tls_error is not None:
            raise self.tls_error
        return object()

    def login(self, _user: str, _password: str) -> object:
        self.login_called = True
        if self.login_error is not None:
            raise self.login_error
        return object()

    def send_message(self, _message: object) -> dict[str, object] | None:
        self.send_called = True
        if self.send_error is not None:
            raise self.send_error
        return {}


@dataclass
class _FakeClock:
    """Deterministic monotonic()/sleep() pair -- no real wall-clock wait."""

    current: float = 0.0
    sleep_calls: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.current += seconds


def _pushover_transport(
    *,
    credentials: H11V4NotificationCredentialBundle,
    handler: Callable[[httpx.Request], httpx.Response],
    client: httpx.Client | None = None,
    clock: _FakeClock | None = None,
) -> H11V4ActualPushoverTransport:
    clock = clock or _FakeClock()
    return H11V4ActualPushoverTransport(
        credentials=credentials,
        client=client
        or httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=10.0,
        ),
        monotonic_factory=clock.monotonic,
        sleep=clock.sleep,
    )


def _email_transport(
    *,
    credentials: H11V4NotificationCredentialBundle,
    smtp: _FakeSmtp,
) -> H11V4ActualEmailTransport:
    return H11V4ActualEmailTransport(
        credentials=credentials,
        smtp_factory=lambda _host, _port, _timeout: smtp,
    )


def test_actual_transports_expose_false_fake_only_and_protocol_shape() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    pushover = H11V4ActualPushoverTransport(
        credentials=credentials,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={"status": 1, "receipt": "synthetic-receipt"},
                )
            )
        ),
    )
    email = H11V4ActualEmailTransport(
        credentials=credentials,
        smtp_factory=lambda _host, _port, _timeout: _FakeSmtp(),
    )

    assert pushover.fake_only is False
    assert email.fake_only is False
    assert isinstance(pushover, H11V4PushoverTransport)
    assert isinstance(email, H11V4EmailTransport)


def test_transports_require_credentials_and_client_no_default() -> None:
    # Independent review (2026-07-25) flagged an earlier draft as
    # zero-arg-constructible (credentials/client had defaults), breaking
    # this track's standing "no defaults for anything credential-adjacent"
    # convention. Confirms the fix: omitting either required argument fails
    # at construction time (fail-closed), not silently at first use.
    with pytest.raises(TypeError):
        H11V4ActualPushoverTransport()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        H11V4ActualEmailTransport()  # type: ignore[call-arg]


def test_channel_ready_and_notifier_happy_path_for_noncritical_event() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(
            200,
            json={"status": 1, "receipt": "synthetic-receipt"},
        )

    pushover = _pushover_transport(credentials=credentials, handler=handler)
    email = _email_transport(credentials=credentials, smtp=_FakeSmtp())

    assert entry_notification.unattended_live_notification_channel_ready(
        primary=pushover,
        secondary=email,
    )
    notifier = entry_notification.H11V4EnabledDualRouteNotifier(
        primary=pushover,
        secondary=email,
    )
    result = notifier.notify_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    assert result.halt_required is False
    assert result.primary_ready is True
    assert result.secondary_ready is True
    assert result.reason_safe_label == "DUAL_ROUTE_READY"
    assert calls == ["POST"]


def test_pushover_status_not_accepted_maps_to_fixed_label() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    transport = _pushover_transport(
        credentials=credentials,
        handler=lambda _request: httpx.Response(200, json={"status": 0}),
    )
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="PUSHOVER_SEND_REJECTED_NO_RETRY",
    ):
        transport.send_once(request)


def test_pushover_http_500_maps_to_fixed_label() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    # A non-200 status with a valid JSON body (Pushover's real error shape)
    # -- distinct from malformed-body failures, covered separately below.
    transport = _pushover_transport(
        credentials=credentials,
        handler=lambda _request: httpx.Response(
            500, json={"status": 0, "errors": ["internal error"]}
        ),
    )
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="PUSHOVER_SEND_REJECTED_NO_RETRY",
    ):
        transport.send_once(request)


def test_pushover_malformed_json_maps_to_fixed_label() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    transport = _pushover_transport(
        credentials=credentials,
        handler=lambda _request: httpx.Response(200, text="not json"),
    )
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="PUSHOVER_SEND_RESPONSE_INVALID",
    ):
        transport.send_once(request)


def test_pushover_network_error_maps_to_fixed_label() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    transport = _pushover_transport(credentials=credentials, handler=handler)
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="PUSHOVER_NETWORK_FAILED_NO_RETRY",
    ):
        transport.send_once(request)


def test_pushover_credential_bundle_raising_maps_to_fixed_label() -> None:
    def reader(
        _service: str, _account: str
    ) -> preparation_module._SealedNotificationSecret:
        raise preparation_module.H11V4ActualNotificationError(
            "NOTIFICATION_KEYCHAIN_ITEM_UNAVAILABLE"
        )

    credentials = H11V4NotificationCredentialBundle(reader=reader)
    transport = _pushover_transport(
        credentials=credentials,
        handler=lambda _request: (_ for _ in ()).throw(
            AssertionError("must not reach network without credentials")
        ),
    )
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="NOTIFICATION_CREDENTIAL_ACCESS_FAILED",
    ):
        transport.send_once(request)


def test_pushover_ack_acknowledged_mid_poll_never_sleeps_real_time() -> None:
    clock = _FakeClock()
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    poll_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if request.method == "POST":
            return httpx.Response(200, json={"status": 1, "receipt": "r"})
        poll_count += 1
        return httpx.Response(200, json={"status": 1, "acknowledged": 1})

    transport = _pushover_transport(credentials=credentials, handler=handler, clock=clock)
    request = build_h11_v4_pushover_request(H11V4NotificationEvent.PROTECTION_MISSING)

    delivery = transport.send_once(request)
    assert delivery.acknowledged is True
    assert poll_count == 1
    assert clock.sleep_calls  # slept via the fake clock, not real time


def test_pushover_ack_expired_mid_poll_returns_not_acknowledged() -> None:
    clock = _FakeClock()
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"status": 1, "receipt": "r"})
        return httpx.Response(200, json={"status": 1, "expired": 1})

    transport = _pushover_transport(credentials=credentials, handler=handler, clock=clock)
    request = build_h11_v4_pushover_request(H11V4NotificationEvent.PROTECTION_MISSING)

    delivery = transport.send_once(request)
    assert delivery.acknowledged is False
    assert delivery.accepted is True


def test_pushover_ack_timeout_exhausted_returns_not_acknowledged() -> None:
    clock = _FakeClock()
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"status": 1, "receipt": "r"})
        return httpx.Response(200, json={"status": 1})

    transport = _pushover_transport(credentials=credentials, handler=handler, clock=clock)
    request = build_h11_v4_pushover_request(H11V4NotificationEvent.PROTECTION_MISSING)

    delivery = transport.send_once(request)
    assert delivery.acknowledged is False
    # Bounded by the fake clock's advancing time, not a real 10s sleep.
    assert clock.current >= transport.acknowledgement_timeout_seconds


def test_smtp_auth_failure_maps_to_fixed_label() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    smtp = _FakeSmtp(
        login_error=smtplib.SMTPAuthenticationError(535, b"bad creds"),
    )
    transport = _email_transport(credentials=credentials, smtp=smtp)

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="SMTP_AUTH_FAILED_NO_RETRY",
    ):
        transport.send_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)


def test_smtp_send_failure_maps_to_fixed_label() -> None:
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    smtp = _FakeSmtp(send_error=smtplib.SMTPException("send failed"))
    transport = _email_transport(credentials=credentials, smtp=smtp)

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="SMTP_SEND_FAILED_NO_RETRY",
    ):
        transport.send_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)


def test_smtp_ehlo_rejection_without_exception_maps_to_fixed_label() -> None:
    # ehlo() can return a non-250 code WITHOUT raising -- a distinct path
    # from the exception-raising failures the other tests cover.
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    smtp = _FakeSmtp(ehlo_result=(421, "service not available"))
    transport = _email_transport(credentials=credentials, smtp=smtp)

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="SMTP_EHLO_FAILED_NO_RETRY",
    ):
        transport.send_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)


def test_smtp_credential_bundle_raising_maps_to_fixed_label() -> None:
    def reader(
        _service: str, _account: str
    ) -> preparation_module._SealedNotificationSecret:
        raise preparation_module.H11V4ActualNotificationError(
            "NOTIFICATION_KEYCHAIN_ITEM_UNAVAILABLE"
        )

    credentials = H11V4NotificationCredentialBundle(reader=reader)
    smtp = _FakeSmtp()
    transport = _email_transport(credentials=credentials, smtp=smtp)

    with pytest.raises(
        H11V4ActualNotificationTransportError,
        match="NOTIFICATION_CREDENTIAL_ACCESS_FAILED",
    ):
        transport.send_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)
    assert smtp.login_called is False


def test_smtp_transport_errors_do_not_leak_credentials() -> None:
    secret_password = "smtp-password-very-sensitive"
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="secret-smtp-username",
        smtp_password=secret_password,
    )
    smtp = _FakeSmtp(
        login_error=smtplib.SMTPAuthenticationError(535, b"bad creds"),
    )
    transport = _email_transport(credentials=credentials, smtp=smtp)

    with pytest.raises(H11V4ActualNotificationTransportError) as captured:
        transport.send_once(H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED)

    assert secret_password not in str(captured.value)
    assert secret_password not in repr(captured.value)
    assert captured.value.__cause__ is None  # `from None`: no chained cause to leak


def test_pushover_transport_errors_do_not_leak_credentials() -> None:
    secret_token = "synthetic-token-very-sensitive"
    credentials = _credential_bundle(
        pushover_token=secret_token,
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    transport = _pushover_transport(
        credentials=credentials,
        handler=lambda _request: httpx.Response(200, json={"status": 0}),
    )
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.UNATTENDED_LIVE_ENTRY_ATTEMPTED
    )

    with pytest.raises(H11V4ActualNotificationTransportError) as captured:
        transport.send_once(request)

    assert secret_token not in str(captured.value)
    assert secret_token not in repr(captured.value)
    assert captured.value.__cause__ is None


def test_critical_pushover_request_sets_emergency_retry_and_expire_fields() -> None:
    clock = _FakeClock()
    credentials = _credential_bundle(
        pushover_token="synthetic-token",
        pushover_user="synthetic-user",
        smtp_username="smtp-user",
        smtp_password="smtp-password",
    )
    captured: dict[str, list[str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            payload = parse_qs(request.content.decode("utf-8"))
            captured.update(payload)
            return httpx.Response(
                200, json={"status": 1, "receipt": "synthetic-receipt"}
            )
        return httpx.Response(200, json={"status": 1, "acknowledged": 1})

    transport = _pushover_transport(credentials=credentials, handler=handler, clock=clock)
    request = build_h11_v4_pushover_request(
        H11V4NotificationEvent.PROTECTION_MISSING
    )

    delivery = transport.send_once(request)
    assert request.emergency_priority is True
    assert request.receipt_required is True
    assert request.retry_seconds == 60
    assert request.expire_seconds == 3600
    assert captured["priority"] == ["2"]
    assert captured["retry"] == ["60"]
    assert captured["expire"] == ["3600"]
    assert delivery.external_send_performed is True
