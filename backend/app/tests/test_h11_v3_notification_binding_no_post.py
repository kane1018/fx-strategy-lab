"""Fake-only tests for H-11 v3 notification and Private WS design."""

from __future__ import annotations

import inspect

import pytest

from app.services.h11_v3_notification_binding_no_post import (
    H11V3ExternalNotificationCategory,
    H11V3FakeExternalNotifier,
    H11V3FakePrivateWsClient,
    H11V3FakePrivateWsTokenProvider,
    H11V3NotificationBindingError,
    H11V3PrivateEventCategory,
    H11V3PrivateWsConnectionStatus,
    H11V3PrivateWsTokenStatus,
    run_h11_v3_fake_notification_binding_no_post,
)


def test_heartbeat_entry_and_settlement_notifications_fire_on_fake_path() -> None:
    token_provider = H11V3FakePrivateWsTokenProvider()
    ws_client = H11V3FakePrivateWsClient()
    notifier = H11V3FakeExternalNotifier()

    result = run_h11_v3_fake_notification_binding_no_post(
        token_provider=token_provider,
        ws_client=ws_client,
        notifier=notifier,
        private_events=(
            H11V3PrivateEventCategory.ENTRY,
            H11V3PrivateEventCategory.SETTLEMENT,
        ),
        maximum_connect_attempts=2,
    )

    assert result.connection_ready is True
    assert result.halt_required is False
    assert result.notification_categories == (
        H11V3ExternalNotificationCategory.HEARTBEAT,
        H11V3ExternalNotificationCategory.ENTRY_OBSERVED,
        H11V3ExternalNotificationCategory.SETTLEMENT_OBSERVED,
    )
    assert result.actual_private_api_call_count == 0
    assert result.actual_ws_connection_count == 0
    assert result.external_send is False
    assert result.credential_read is False
    assert result.actual_post_count == 0


def test_fake_reconnect_succeeds_within_explicit_attempt_limit() -> None:
    ws_client = H11V3FakePrivateWsClient(
        connection_sequence=(
            H11V3PrivateWsConnectionStatus.DISCONNECTED,
            H11V3PrivateWsConnectionStatus.CONNECTED_SYNTHETIC,
        )
    )
    result = run_h11_v3_fake_notification_binding_no_post(
        token_provider=H11V3FakePrivateWsTokenProvider(),
        ws_client=ws_client,
        notifier=H11V3FakeExternalNotifier(),
        maximum_connect_attempts=2,
    )
    assert result.connection_ready is True
    assert result.connect_attempt_count == 2
    assert result.halt_required is False


def test_reconnect_exhaustion_fires_dead_man_and_halts() -> None:
    notifier = H11V3FakeExternalNotifier()
    result = run_h11_v3_fake_notification_binding_no_post(
        token_provider=H11V3FakePrivateWsTokenProvider(),
        ws_client=H11V3FakePrivateWsClient(
            connection_sequence=(H11V3PrivateWsConnectionStatus.DISCONNECTED,)
        ),
        notifier=notifier,
        maximum_connect_attempts=3,
    )
    assert result.connection_ready is False
    assert result.halt_required is True
    assert result.connect_attempt_count == 3
    assert result.reason_safe_label == "PRIVATE_WS_RECONNECT_EXHAUSTED_HALT"
    assert result.notification_categories == (
        H11V3ExternalNotificationCategory.DEAD_MAN_HALTED,
    )


@pytest.mark.parametrize(
    "token_status",
    [
        H11V3PrivateWsTokenStatus.UNAVAILABLE,
        H11V3PrivateWsTokenStatus.EXPIRED,
        H11V3PrivateWsTokenStatus.UNKNOWN,
    ],
)
def test_token_failure_halts_without_connecting(
    token_status: H11V3PrivateWsTokenStatus,
) -> None:
    ws_client = H11V3FakePrivateWsClient()
    result = run_h11_v3_fake_notification_binding_no_post(
        token_provider=H11V3FakePrivateWsTokenProvider(status=token_status),
        ws_client=ws_client,
        notifier=H11V3FakeExternalNotifier(),
        maximum_connect_attempts=2,
    )
    assert result.halt_required is True
    assert result.connect_attempt_count == 0
    assert result.actual_private_api_call_count == 0


def test_unknown_event_and_notifier_failure_are_fail_closed() -> None:
    unknown = run_h11_v3_fake_notification_binding_no_post(
        token_provider=H11V3FakePrivateWsTokenProvider(),
        ws_client=H11V3FakePrivateWsClient(),
        notifier=H11V3FakeExternalNotifier(),
        private_events=(H11V3PrivateEventCategory.UNKNOWN,),
        maximum_connect_attempts=1,
    )
    assert unknown.halt_required is True
    assert unknown.reason_safe_label == "UNKNOWN_PRIVATE_EVENT_HALT"

    failed = run_h11_v3_fake_notification_binding_no_post(
        token_provider=H11V3FakePrivateWsTokenProvider(),
        ws_client=H11V3FakePrivateWsClient(),
        notifier=H11V3FakeExternalNotifier(
            fail_categories=(H11V3ExternalNotificationCategory.ENTRY_OBSERVED,)
        ),
        private_events=(H11V3PrivateEventCategory.ENTRY,),
        maximum_connect_attempts=1,
    )
    assert failed.halt_required is True
    assert failed.notification_failure is True
    assert failed.reason_safe_label == "EXTERNAL_NOTIFICATION_FAILED_HALT"


def test_non_fake_binding_and_invalid_attempt_limit_are_rejected() -> None:
    class NonFakeProvider:
        fake_only = False

        def acquire_status(self):  # type: ignore[no-untyped-def]
            return H11V3PrivateWsTokenStatus.AVAILABLE_SYNTHETIC

    with pytest.raises(H11V3NotificationBindingError, match="positive"):
        run_h11_v3_fake_notification_binding_no_post(
            token_provider=H11V3FakePrivateWsTokenProvider(),
            ws_client=H11V3FakePrivateWsClient(),
            notifier=H11V3FakeExternalNotifier(),
            maximum_connect_attempts=0,
        )
    with pytest.raises(H11V3NotificationBindingError, match="fake-only"):
        run_h11_v3_fake_notification_binding_no_post(
            token_provider=NonFakeProvider(),
            ws_client=H11V3FakePrivateWsClient(),
            notifier=H11V3FakeExternalNotifier(),
            maximum_connect_attempts=1,
        )


def test_module_has_no_network_credential_or_environment_access() -> None:
    import app.services.h11_v3_notification_binding_no_post as module

    source = inspect.getsource(module)
    for marker in (
        "import httpx",
        "import requests",
        "os.environ",
        "getenv",
        "load_dotenv",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "allow=True",
    ):
        assert marker not in source
