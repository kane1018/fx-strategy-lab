"""H-11 v3 Private WebSocket and external notification design (fake-only).

The protocols model the token-provider, reconnecting WebSocket client, and
external notifier injection points.  Only fake implementations are supplied.
They exchange safe states rather than token values, event payloads, IDs, or
account data, and they cannot perform network or credential operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class H11V3NotificationBindingError(RuntimeError):
    """Fail-closed error containing safe labels only."""


class H11V3PrivateWsTokenStatus(str, Enum):
    AVAILABLE_SYNTHETIC = "AVAILABLE_SYNTHETIC"
    UNAVAILABLE = "UNAVAILABLE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class H11V3PrivateWsConnectionStatus(str, Enum):
    CONNECTED_SYNTHETIC = "CONNECTED_SYNTHETIC"
    DISCONNECTED = "DISCONNECTED"
    UNKNOWN = "UNKNOWN"


class H11V3PrivateEventCategory(str, Enum):
    ENTRY = "ENTRY"
    SETTLEMENT = "SETTLEMENT"
    UNKNOWN = "UNKNOWN"


class H11V3ExternalNotificationCategory(str, Enum):
    HEARTBEAT = "HEARTBEAT"
    DEAD_MAN_HALTED = "DEAD_MAN_HALTED"
    ENTRY_OBSERVED = "ENTRY_OBSERVED"
    SETTLEMENT_OBSERVED = "SETTLEMENT_OBSERVED"
    UNKNOWN_EVENT_HALTED = "UNKNOWN_EVENT_HALTED"


class H11V3PrivateWsTokenProvider(Protocol):
    fake_only: bool

    def acquire_status(self) -> H11V3PrivateWsTokenStatus: ...


class H11V3PrivateWsClient(Protocol):
    fake_only: bool

    def connect(
        self, token_status: H11V3PrivateWsTokenStatus
    ) -> H11V3PrivateWsConnectionStatus: ...


class H11V3ExternalNotifier(Protocol):
    fake_only: bool
    external_send: bool

    def notify(self, category: H11V3ExternalNotificationCategory) -> bool: ...


@dataclass
class H11V3FakePrivateWsTokenProvider:
    status: H11V3PrivateWsTokenStatus = (
        H11V3PrivateWsTokenStatus.AVAILABLE_SYNTHETIC
    )
    fake_only: bool = field(default=True, init=False)
    acquire_count: int = field(default=0, init=False)
    actual_private_api_call_count: int = field(default=0, init=False)
    credential_read: bool = field(default=False, init=False)

    def acquire_status(self) -> H11V3PrivateWsTokenStatus:
        self.acquire_count += 1
        return self.status

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3FakePrivateWsClient:
    connection_sequence: tuple[H11V3PrivateWsConnectionStatus, ...] = (
        H11V3PrivateWsConnectionStatus.CONNECTED_SYNTHETIC,
    )
    fake_only: bool = field(default=True, init=False)
    connect_attempt_count: int = field(default=0, init=False)
    actual_connection_count: int = field(default=0, init=False)

    def connect(
        self, token_status: H11V3PrivateWsTokenStatus
    ) -> H11V3PrivateWsConnectionStatus:
        self.connect_attempt_count += 1
        if token_status is not H11V3PrivateWsTokenStatus.AVAILABLE_SYNTHETIC:
            return H11V3PrivateWsConnectionStatus.UNKNOWN
        index = min(
            self.connect_attempt_count - 1,
            max(0, len(self.connection_sequence) - 1),
        )
        if not self.connection_sequence:
            return H11V3PrivateWsConnectionStatus.UNKNOWN
        return self.connection_sequence[index]

    def __bool__(self) -> bool:
        return False


@dataclass
class H11V3FakeExternalNotifier:
    fail_categories: tuple[H11V3ExternalNotificationCategory, ...] = ()
    fake_only: bool = field(default=True, init=False)
    external_send: bool = field(default=False, init=False)
    categories: list[H11V3ExternalNotificationCategory] = field(
        default_factory=list, init=False
    )

    def notify(self, category: H11V3ExternalNotificationCategory) -> bool:
        if category in self.fail_categories:
            return False
        self.categories.append(category)
        return True

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class H11V3NotificationBindingResult:
    connection_ready: bool
    halt_required: bool
    reason_safe_label: str
    token_status: H11V3PrivateWsTokenStatus
    connect_attempt_count: int
    notification_categories: tuple[H11V3ExternalNotificationCategory, ...]
    notification_failure: bool
    actual_private_api_call_count: int = 0
    actual_ws_connection_count: int = 0
    external_send: bool = False
    credential_read: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        return False


def run_h11_v3_fake_notification_binding_no_post(
    *,
    token_provider: H11V3PrivateWsTokenProvider,
    ws_client: H11V3PrivateWsClient,
    notifier: H11V3ExternalNotifier,
    private_events: tuple[H11V3PrivateEventCategory, ...] = (),
    maximum_connect_attempts: int,
) -> H11V3NotificationBindingResult:
    """Exercise token/reconnect/notification policy using fake bindings only."""

    if maximum_connect_attempts <= 0:
        raise H11V3NotificationBindingError(
            "maximum connect attempts must be positive"
        )
    _require_fake_binding(token_provider, "token provider")
    _require_fake_binding(ws_client, "WebSocket client")
    _require_fake_binding(notifier, "external notifier")
    if notifier.external_send:
        raise H11V3NotificationBindingError("external send must remain disabled")

    token_status = token_provider.acquire_status()
    if token_status is not H11V3PrivateWsTokenStatus.AVAILABLE_SYNTHETIC:
        notified = notifier.notify(H11V3ExternalNotificationCategory.DEAD_MAN_HALTED)
        return _result(
            token_status=token_status,
            ws_client=ws_client,
            notifier=notifier,
            connection_ready=False,
            halt_required=True,
            reason="PRIVATE_WS_TOKEN_UNAVAILABLE_HALT",
            notification_failure=not notified,
        )

    connection_status = H11V3PrivateWsConnectionStatus.UNKNOWN
    for _ in range(maximum_connect_attempts):
        connection_status = ws_client.connect(token_status)
        if connection_status is H11V3PrivateWsConnectionStatus.CONNECTED_SYNTHETIC:
            break
    if connection_status is not H11V3PrivateWsConnectionStatus.CONNECTED_SYNTHETIC:
        notified = notifier.notify(H11V3ExternalNotificationCategory.DEAD_MAN_HALTED)
        return _result(
            token_status=token_status,
            ws_client=ws_client,
            notifier=notifier,
            connection_ready=False,
            halt_required=True,
            reason="PRIVATE_WS_RECONNECT_EXHAUSTED_HALT",
            notification_failure=not notified,
        )

    heartbeat_ok = notifier.notify(H11V3ExternalNotificationCategory.HEARTBEAT)
    if not heartbeat_ok:
        return _result(
            token_status=token_status,
            ws_client=ws_client,
            notifier=notifier,
            connection_ready=True,
            halt_required=True,
            reason="HEARTBEAT_NOTIFICATION_FAILED_HALT",
            notification_failure=True,
        )

    for event in private_events:
        category = _map_private_event(event)
        notified = notifier.notify(category)
        if event is H11V3PrivateEventCategory.UNKNOWN or not notified:
            reason = (
                "UNKNOWN_PRIVATE_EVENT_HALT"
                if event is H11V3PrivateEventCategory.UNKNOWN
                else "EXTERNAL_NOTIFICATION_FAILED_HALT"
            )
            return _result(
                token_status=token_status,
                ws_client=ws_client,
                notifier=notifier,
                connection_ready=True,
                halt_required=True,
                reason=reason,
                notification_failure=not notified,
            )

    return _result(
        token_status=token_status,
        ws_client=ws_client,
        notifier=notifier,
        connection_ready=True,
        halt_required=False,
        reason="FAKE_NOTIFICATION_PATH_HEALTHY",
        notification_failure=False,
    )


def _require_fake_binding(binding: object, label: str) -> None:
    if getattr(binding, "fake_only", False) is not True:
        raise H11V3NotificationBindingError(f"{label} must be fake-only")


def _map_private_event(
    event: H11V3PrivateEventCategory,
) -> H11V3ExternalNotificationCategory:
    mapping = {
        H11V3PrivateEventCategory.ENTRY: (
            H11V3ExternalNotificationCategory.ENTRY_OBSERVED
        ),
        H11V3PrivateEventCategory.SETTLEMENT: (
            H11V3ExternalNotificationCategory.SETTLEMENT_OBSERVED
        ),
        H11V3PrivateEventCategory.UNKNOWN: (
            H11V3ExternalNotificationCategory.UNKNOWN_EVENT_HALTED
        ),
    }
    return mapping[event]


def _result(
    *,
    token_status: H11V3PrivateWsTokenStatus,
    ws_client: H11V3PrivateWsClient,
    notifier: H11V3ExternalNotifier,
    connection_ready: bool,
    halt_required: bool,
    reason: str,
    notification_failure: bool,
) -> H11V3NotificationBindingResult:
    return H11V3NotificationBindingResult(
        connection_ready=connection_ready,
        halt_required=halt_required,
        reason_safe_label=reason,
        token_status=token_status,
        connect_attempt_count=getattr(ws_client, "connect_attempt_count", 0),
        notification_categories=tuple(getattr(notifier, "categories", ())),
        notification_failure=notification_failure,
    )
