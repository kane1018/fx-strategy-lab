"""Finite actual notification rehearsal for H-11 v4 activation preparation.

This module may send exactly one Pushover message and exactly one email.  It
cannot call a broker endpoint and never returns provider identifiers, account
names, credential values, or raw responses.  The fake-only runtime notifier
remains unchanged and does not import this module.
"""

from __future__ import annotations

import json
import platform
import smtplib
import ssl
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from typing import Any, Protocol

import httpx

from app.h11_auto.v4_actual_preparation_guard import (
    V4ExternalPreparationGate,
    V4PreparationOperation,
    V4PreparationOperationPermit,
    require_external_preparation_gate,
    require_operation_permit,
)
from app.services.h11_v4_notification_binding_no_post import (
    H11V4NotificationEvent,
    build_h11_v4_pushover_request,
)

NOTIFICATION_KEYCHAIN_SERVICE = "fx-strategy-lab-h11-v4-notify"
PUSHOVER_TOKEN_ACCOUNT = "pushover-api-token"
PUSHOVER_USER_ACCOUNT = "pushover-user-key"
SMTP_USERNAME_ACCOUNT = "smtp-username"
SMTP_PASSWORD_ACCOUNT = "smtp-app-password"
PUSHOVER_MESSAGE_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_RECEIPT_URL_PREFIX = "https://api.pushover.net/1/receipts/"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

_SAFE_TITLE = "FX Strategy Lab H-11 v4"
_SAFE_MESSAGE = (
    "Activation preparation notification test. No broker order was sent. "
    "Please acknowledge this Pushover alert."
)
_SAFE_EMAIL_BODY = (
    "H-11 v4 activation preparation email path test completed. "
    "No broker order was sent."
)


class H11V4ActualNotificationError(RuntimeError):
    """Fixed safe failure; provider or credential content is never included."""


@dataclass(frozen=True, repr=False)
class _SealedNotificationSecret:
    _value: str

    def reveal_internal_only(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "_SealedNotificationSecret(***)"

    def __str__(self) -> str:
        return "***"

    def __bool__(self) -> bool:
        return False


SecretReader = Callable[[str, str], _SealedNotificationSecret]


def read_notification_keychain_secret(
    service: str,
    account: str,
    *,
    timeout_seconds: float = 5.0,
) -> _SealedNotificationSecret:
    if platform.system() != "Darwin":
        raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_PLATFORM_UNSUPPORTED")
    if service != NOTIFICATION_KEYCHAIN_SERVICE or account not in {
        PUSHOVER_TOKEN_ACCOUNT,
        PUSHOVER_USER_ACCOUNT,
        SMTP_USERNAME_ACCOUNT,
        SMTP_PASSWORD_ACCOUNT,
    }:
        raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_ITEM_NOT_ALLOWED")
    if timeout_seconds <= 0:
        raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_TIMEOUT_INVALID")
    try:
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_READ_FAILED") from None
    if completed.returncode != 0:
        raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_ITEM_UNAVAILABLE")
    value = completed.stdout.rstrip("\n")
    if not value:
        raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_ITEM_EMPTY")
    return _SealedNotificationSecret(value)


@dataclass(frozen=True, repr=False)
class H11V4NotificationCredentialBundle:
    reader: SecretReader = read_notification_keychain_secret

    def load_internal_only(
        self,
    ) -> tuple[
        _SealedNotificationSecret,
        _SealedNotificationSecret,
        _SealedNotificationSecret,
        _SealedNotificationSecret,
    ]:
        try:
            values = tuple(
                self.reader(NOTIFICATION_KEYCHAIN_SERVICE, account)
                for account in (
                    PUSHOVER_TOKEN_ACCOUNT,
                    PUSHOVER_USER_ACCOUNT,
                    SMTP_USERNAME_ACCOUNT,
                    SMTP_PASSWORD_ACCOUNT,
                )
            )
        except H11V4ActualNotificationError:
            raise
        except Exception:  # noqa: BLE001
            raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_READ_FAILED") from None
        if len(values) != 4 or any(
            not isinstance(value, _SealedNotificationSecret) for value in values
        ):
            raise H11V4ActualNotificationError("NOTIFICATION_KEYCHAIN_CONTRACT_INVALID")
        return values  # type: ignore[return-value]

    def __repr__(self) -> str:
        return "H11V4NotificationCredentialBundle(***)"

    def __bool__(self) -> bool:
        return False


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


@dataclass(frozen=True)
class H11V4ActualNotificationReport:
    status: str
    keychain_items_present: bool
    credential_read_count: int
    pushover_application_send_count: int
    pushover_accepted: bool
    pushover_receipt_present: bool
    pushover_acknowledged: bool
    pushover_receipt_poll_count: int
    email_send_count: int
    email_smtp_accepted: bool
    email_delivery_operator_confirmed: bool
    destination_is_smtp_username: bool
    external_notification_send_count: int
    broker_get_count: int = 0
    broker_post_count: int = 0
    provider_identifier_exposed: bool = False
    credential_exposed: bool = False
    raw_response_retained: bool = False
    activation_permit_issued: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


def run_actual_notification_rehearsal_once(
    *,
    external_gate: V4ExternalPreparationGate,
    operation_permit: V4PreparationOperationPermit,
    credentials: H11V4NotificationCredentialBundle | None = None,
    http_client: httpx.Client | None = None,
    smtp_factory: SmtpFactory = _default_smtp_factory,
    acknowledgement_timeout_seconds: float = 180.0,
    receipt_poll_interval_seconds: float = 5.0,
    monotonic_factory: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> H11V4ActualNotificationReport:
    """Send one emergency push and one email, then poll push acknowledgement."""

    require_external_preparation_gate(external_gate)
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.NOTIFICATION,
        consume=True,
    )
    if acknowledgement_timeout_seconds <= 0 or receipt_poll_interval_seconds < 5.0:
        raise H11V4ActualNotificationError("NOTIFICATION_REHEARSAL_TIMING_INVALID")
    bundle = (
        credentials
        if credentials is not None
        else H11V4NotificationCredentialBundle()
    )
    token, user, smtp_username, smtp_password = bundle.load_internal_only()
    token_value = token.reveal_internal_only()
    user_value = user.reveal_internal_only()
    smtp_user_value = smtp_username.reveal_internal_only()
    smtp_password_value = smtp_password.reveal_internal_only()
    client = http_client or httpx.Client(timeout=10.0)
    owns_client = http_client is None
    push_sent = 0
    email_sent = 0
    poll_count = 0
    push_accepted = False
    receipt_present = False
    acknowledged = False
    email_smtp_accepted = False
    push_failure: str | None = None
    email_failure: str | None = None
    try:
        request = build_h11_v4_pushover_request(
            H11V4NotificationEvent.ACTIVATION_PREPARATION_TEST
        )
        payload = {
            "token": token_value,
            "user": user_value,
            "title": _SAFE_TITLE,
            "message": _SAFE_MESSAGE,
            "priority": "2",
            "retry": str(request.retry_seconds),
            "expire": str(request.expire_seconds),
        }
        push_sent = 1
        try:
            response = client.post(PUSHOVER_MESSAGE_URL, data=payload)
        except httpx.HTTPError:
            push_failure = "PUSHOVER_NETWORK_FAILED_NO_RETRY"
            receipt = None
        else:
            try:
                push_payload = _json_mapping(
                    response, "PUSHOVER_SEND_RESPONSE_INVALID"
                )
                receipt = push_payload.get("receipt")
                if response.status_code != 200 or push_payload.get("status") != 1:
                    raise H11V4ActualNotificationError(
                        "PUSHOVER_SEND_REJECTED_NO_RETRY"
                    )
                push_accepted = True
                if not isinstance(receipt, str) or not receipt:
                    raise H11V4ActualNotificationError("PUSHOVER_RECEIPT_MISSING")
                receipt_present = True
            except H11V4ActualNotificationError as error:
                push_failure = str(error)
                receipt = None

        # The secondary route is attempted independently even if Pushover fails.
        message = EmailMessage()
        message["Subject"] = _SAFE_TITLE
        message["From"] = smtp_user_value
        message["To"] = smtp_user_value
        message.set_content(_SAFE_EMAIL_BODY)
        email_sent = 1
        try:
            with smtp_factory(SMTP_HOST, SMTP_PORT, 10.0) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(smtp_user_value, smtp_password_value)
                refused_recipients = smtp.send_message(message)
                if refused_recipients:
                    raise H11V4ActualNotificationError(
                        "EMAIL_SMTP_RECIPIENT_REJECTED_NO_RETRY"
                    )
            email_smtp_accepted = True
        except (OSError, smtplib.SMTPException, H11V4ActualNotificationError):
            email_failure = "EMAIL_SEND_FAILED_NO_RETRY"

        if receipt is not None:
            started = monotonic_factory()
            try:
                while monotonic_factory() - started < acknowledgement_timeout_seconds:
                    sleep(receipt_poll_interval_seconds)
                    poll_count += 1
                    try:
                        receipt_response = client.get(
                            f"{PUSHOVER_RECEIPT_URL_PREFIX}{receipt}.json",
                            params={"token": token_value},
                        )
                    except httpx.HTTPError:
                        raise H11V4ActualNotificationError(
                            "PUSHOVER_RECEIPT_NETWORK_FAILED_NO_RETRY"
                        ) from None
                    receipt_payload = _json_mapping(
                        receipt_response, "PUSHOVER_RECEIPT_RESPONSE_INVALID"
                    )
                    if (
                        receipt_response.status_code != 200
                        or receipt_payload.get("status") != 1
                    ):
                        raise H11V4ActualNotificationError(
                            "PUSHOVER_RECEIPT_REJECTED"
                        )
                    if receipt_payload.get("acknowledged") == 1:
                        acknowledged = True
                        break
                    if receipt_payload.get("expired") == 1:
                        break
                if not acknowledged:
                    raise H11V4ActualNotificationError(
                        "PUSHOVER_ACK_NOT_CONFIRMED"
                    )
            except H11V4ActualNotificationError as error:
                push_failure = str(error)

        if push_failure is not None or email_failure is not None:
            raise H11V4ActualNotificationError(
                "NOTIFICATION_REHEARSAL_FAILED_NO_RETRY"
            ) from None
        return H11V4ActualNotificationReport(
            status=(
                "PASSED_PROVIDER_ACCEPTANCE_AWAITING_EMAIL_OPERATOR_CONFIRMATION_"
                "NO_BROKER_POST"
            ),
            keychain_items_present=True,
            credential_read_count=4,
            pushover_application_send_count=push_sent,
            pushover_accepted=push_accepted,
            pushover_receipt_present=receipt_present,
            pushover_acknowledged=acknowledged,
            pushover_receipt_poll_count=poll_count,
            email_send_count=email_sent,
            email_smtp_accepted=email_smtp_accepted,
            email_delivery_operator_confirmed=False,
            destination_is_smtp_username=True,
            external_notification_send_count=2,
        )
    finally:
        if owns_client:
            client.close()


def _json_mapping(response: httpx.Response, error_label: str) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        raise H11V4ActualNotificationError(error_label) from None
    if not isinstance(payload, Mapping):
        raise H11V4ActualNotificationError(error_label)
    return payload
