"""Runtime-shaped H-11 v4 notification transports for Pushover and SMTP.

``credentials``/``client``/``smtp_factory`` are all required, no-default
constructor parameters -- matching this track's standing convention that
anything credential-adjacent (``credential_pair``/``client`` in the bounded
runner CLI, real transports in
``h11_v4_unattended_live_entry_notification.py``) is fail-closed at
construction time, never zero-arg-constructible. This is deliberate:
``H11V4ActualPushoverTransport()``/``H11V4ActualEmailTransport()`` with no
arguments must not silently produce a live, ``fake_only is False`` object.

Ack-wait design (independent review, 2026-07-25): the daily preparation
rehearsal (``h11_v4_notification_actual_preparation.py``) blocks up to 15
minutes polling a critical Pushover alert's acknowledgement receipt, because
that flow is a deliberate, human-run, once-a-day check. This transport is
called from the real trading path instead, where blocking for minutes on
every notification would stall (or worse, ambiguously extend) an entry-cycle
attempt -- so ``H11V4ActualPushoverTransport`` bounds the ack-wait to a much
shorter default (10s) and exposes it as a constructor parameter rather than
hardcoding the rehearsal's 900s.
"""

from __future__ import annotations

import smtplib
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any, Protocol

import certifi
import httpx

from app.services.h11_v4_notification_actual_preparation import (
    PUSHOVER_MESSAGE_URL,
    PUSHOVER_RECEIPT_URL_PREFIX,
    SMTP_HOST,
    SMTP_PORT,
    H11V4NotificationCredentialBundle,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4NotificationEvent,
    H11V4PushoverDelivery,
    H11V4PushoverRequest,
)

_SAFE_TITLE = "FX Strategy Lab H-11 v4"
_SAFE_MESSAGE = "Unattended live execution notification test. No broker order was sent."
_SAFE_EMAIL_BODY = "H-11 v4 unattended live execution notification test."
_PUSHOVER_HTTP_TIMEOUT_SECONDS = 10.0


class H11V4ActualNotificationTransportError(RuntimeError):
    """Fixed safe failure label; provider/credential content is never included.

    Every raise site in this module uses ``from None`` (never ``from
    <original error>``): chaining the original exception would preserve it
    as ``__cause__``, and a full traceback render (an uncaught-exception
    handler, ``logging.exception``, a LaunchAgent's captured stderr) would
    then reproduce the provider's raw response text or an SMTP server's raw
    rejection message verbatim -- exactly the exposure this class exists to
    prevent. Independent review caught an earlier draft chaining with
    ``from error`` at several sites; fixed.
    """


class _SmtpClient(Protocol):
    def __enter__(self) -> _SmtpClient: ...

    def __exit__(self, *args: object) -> None: ...

    def ehlo(self) -> Any: ...

    def starttls(self, *, context: ssl.SSLContext) -> Any: ...

    def login(self, user: str, password: str) -> Any: ...

    def send_message(self, message: EmailMessage) -> Any: ...


SmtpFactory = Callable[[str, int, float], _SmtpClient]


def _default_smtp_factory(host: str, port: int, timeout: float) -> _SmtpClient:
    return smtplib.SMTP(host, port, timeout=timeout)


def _json_mapping(response: httpx.Response, error_label: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        raise H11V4ActualNotificationTransportError(error_label) from None
    if not isinstance(payload, dict):
        raise H11V4ActualNotificationTransportError(error_label)
    return payload


@dataclass(frozen=True)
class H11V4ActualPushoverTransport:
    """Runtime sender for Pushover emergency and non-emergency alerts.

    ``credentials``/``client`` are required with no default -- see module
    docstring. ``client`` is caller-owned: this class never closes it (the
    caller constructed it, the caller is responsible for its lifecycle),
    unlike the daily rehearsal's self-constructed, self-closed client.
    """

    credentials: H11V4NotificationCredentialBundle
    client: httpx.Client
    fake_only: bool = field(default=False, init=False)
    acknowledgement_timeout_seconds: float = 10.0
    receipt_poll_interval_seconds: float = 5.0
    monotonic_factory: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    def _read_credentials(self) -> tuple[str, str]:
        try:
            token, user = self.credentials.load_pushover_internal_only()
        except Exception:
            raise H11V4ActualNotificationTransportError(
                "NOTIFICATION_CREDENTIAL_ACCESS_FAILED"
            ) from None
        token_value = token.reveal_internal_only()
        user_value = user.reveal_internal_only()
        if not token_value or not user_value:
            raise H11V4ActualNotificationTransportError(
                "NOTIFICATION_CREDENTIAL_ACCESS_FAILED"
            )
        return token_value, user_value

    def _poll_critical_ack(
        self,
        *,
        token: str,
        receipt: str,
        timeout_seconds: float,
    ) -> bool:
        """Poll receipt acknowledgement for a bounded short interval.

        Only ever GETs the receipt endpoint -- never re-POSTs to the send
        endpoint, so a slow/never-acknowledged critical alert cannot result
        in a second message being sent. ``monotonic_factory``/``sleep`` are
        injectable (unlike a first draft that hardcoded ``time.monotonic``/
        ``time.sleep`` directly, which independent review flagged as leaving
        the acknowledged-mid-poll and expired-mid-poll branches with no
        deterministic test coverage) so tests can simulate both outcomes
        without a real wall-clock wait.
        """

        if timeout_seconds <= 0:
            return False
        if self.receipt_poll_interval_seconds <= 0:
            raise H11V4ActualNotificationTransportError(
                "PUSHOVER_ACK_POLLING_INVALID"
            )
        deadline = self.monotonic_factory() + timeout_seconds
        while True:
            remaining = deadline - self.monotonic_factory()
            if remaining <= 0:
                return False
            sleep_for = min(self.receipt_poll_interval_seconds, remaining)
            if sleep_for > 0:
                self.sleep(sleep_for)
            if self.monotonic_factory() >= deadline:
                return False
            try:
                response = self.client.get(
                    f"{PUSHOVER_RECEIPT_URL_PREFIX}{receipt}.json",
                    params={"token": token},
                    timeout=min(
                        _PUSHOVER_HTTP_TIMEOUT_SECONDS,
                        max(0.0, deadline - self.monotonic_factory()),
                    ),
                )
            except httpx.HTTPError:
                raise H11V4ActualNotificationTransportError(
                    "PUSHOVER_RECEIPT_NETWORK_FAILED_NO_RETRY"
                ) from None
            if response.status_code == 404:
                continue
            payload = _json_mapping(response, "PUSHOVER_RECEIPT_RESPONSE_INVALID")
            if response.status_code != 200 or payload.get("status") != 1:
                raise H11V4ActualNotificationTransportError(
                    "PUSHOVER_RECEIPT_REJECTED_NO_RETRY"
                )
            if payload.get("acknowledged") == 1:
                return True
            if payload.get("expired") == 1:
                return False

    def send_once(self, request: H11V4PushoverRequest) -> H11V4PushoverDelivery:
        token_value, user_value = self._read_credentials()
        payload: dict[str, str] = {
            "token": token_value,
            "user": user_value,
            "title": _SAFE_TITLE,
            "message": _SAFE_MESSAGE,
            "priority": "2" if request.emergency_priority else "0",
        }
        if request.retry_seconds is not None:
            payload["retry"] = str(request.retry_seconds)
        if request.expire_seconds is not None:
            payload["expire"] = str(request.expire_seconds)

        try:
            response = self.client.post(
                PUSHOVER_MESSAGE_URL,
                data=payload,
                timeout=_PUSHOVER_HTTP_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError:
            raise H11V4ActualNotificationTransportError(
                "PUSHOVER_NETWORK_FAILED_NO_RETRY"
            ) from None
        push_payload = _json_mapping(response, "PUSHOVER_SEND_RESPONSE_INVALID")
        if response.status_code != 200 or push_payload.get("status") != 1:
            raise H11V4ActualNotificationTransportError(
                "PUSHOVER_SEND_REJECTED_NO_RETRY"
            )
        receipt_raw = push_payload.get("receipt")
        if request.receipt_required:
            if not isinstance(receipt_raw, str) or not receipt_raw:
                raise H11V4ActualNotificationTransportError("PUSHOVER_RECEIPT_MISSING")
            acknowledged = self._poll_critical_ack(
                token=token_value,
                receipt=receipt_raw,
                timeout_seconds=self.acknowledgement_timeout_seconds,
            )
        else:
            acknowledged = True
        return H11V4PushoverDelivery(
            accepted=True,
            receipt_present=request.receipt_required and bool(receipt_raw),
            acknowledged=acknowledged,
            external_send_performed=True,
        )

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V4ActualEmailTransport:
    """Runtime sender for SMTP notifications.

    ``credentials`` is required with no default -- see module docstring.
    """

    credentials: H11V4NotificationCredentialBundle
    fake_only: bool = field(default=False, init=False)
    smtp_factory: SmtpFactory = _default_smtp_factory
    connect_timeout_seconds: float = 10.0

    def _read_credentials(self) -> tuple[str, str]:
        try:
            smtp_username, smtp_password = self.credentials.load_smtp_internal_only()
        except Exception:
            raise H11V4ActualNotificationTransportError(
                "NOTIFICATION_CREDENTIAL_ACCESS_FAILED"
            ) from None
        user_value = smtp_username.reveal_internal_only()
        password_value = smtp_password.reveal_internal_only()
        if not user_value or not password_value:
            raise H11V4ActualNotificationTransportError(
                "NOTIFICATION_CREDENTIAL_ACCESS_FAILED"
            )
        return user_value, password_value

    def _smtp_call_or_safe_error(self, call: Callable[[], Any], label: str) -> Any:
        try:
            return call()
        except (OSError, smtplib.SMTPException):
            raise H11V4ActualNotificationTransportError(label) from None

    @staticmethod
    def _smtp_response_accepted(code_response: object) -> bool:
        return (
            isinstance(code_response, tuple)
            and len(code_response) > 0
            and code_response[0] == 250
        )

    def send_once(self, event: H11V4NotificationEvent) -> bool:
        del event
        smtp_username, smtp_password = self._read_credentials()
        message = EmailMessage()
        message["Subject"] = _SAFE_TITLE
        message["From"] = smtp_username
        message["To"] = smtp_username
        message.set_content(_SAFE_EMAIL_BODY)

        client = self._smtp_call_or_safe_error(
            lambda: self.smtp_factory(SMTP_HOST, SMTP_PORT, self.connect_timeout_seconds),
            "SMTP_CONNECT_FAILED_NO_RETRY",
        )
        session: _SmtpClient | None = None
        send_failed = False
        try:
            session = self._smtp_call_or_safe_error(
                client.__enter__,
                "SMTP_CONNECT_FAILED_NO_RETRY",
            )
            result = self._smtp_call_or_safe_error(
                session.ehlo,
                "SMTP_EHLO_FAILED_NO_RETRY",
            )
            if not self._smtp_response_accepted(result):
                raise H11V4ActualNotificationTransportError("SMTP_EHLO_FAILED_NO_RETRY")
            self._smtp_call_or_safe_error(
                lambda: session.starttls(
                    context=ssl.create_default_context(cafile=certifi.where())
                ),
                "SMTP_TLS_FAILED_NO_RETRY",
            )
            result = self._smtp_call_or_safe_error(
                session.ehlo,
                "SMTP_EHLO_FAILED_NO_RETRY",
            )
            if not self._smtp_response_accepted(result):
                raise H11V4ActualNotificationTransportError("SMTP_EHLO_FAILED_NO_RETRY")
            self._smtp_call_or_safe_error(
                lambda: session.login(smtp_username, smtp_password),
                "SMTP_AUTH_FAILED_NO_RETRY",
            )
            refused = self._smtp_call_or_safe_error(
                lambda: session.send_message(message),
                "SMTP_SEND_FAILED_NO_RETRY",
            )
            if isinstance(refused, dict) and refused:
                raise H11V4ActualNotificationTransportError(
                    "SMTP_RECIPIENT_FAILED_NO_RETRY"
                )
            return True
        except Exception:
            send_failed = True
            raise
        finally:
            if session is not None:
                try:
                    client.__exit__(None, None, None)
                except (OSError, smtplib.SMTPException):
                    if not send_failed:
                        raise H11V4ActualNotificationTransportError(
                            "SMTP_SESSION_CLOSE_FAILED_NO_RETRY"
                        ) from None

    def __bool__(self) -> bool:
        return False
