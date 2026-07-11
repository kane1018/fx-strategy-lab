"""Fake-only tests for the H-11 v3 sender injection boundary."""

from __future__ import annotations

import inspect

import pytest

from app.private_api.order_builders import (
    build_gmo_fx_entry_request_plan,
    build_gmo_fx_ifdoco_request_plan,
    summarize_gmo_fx_private_request_plan,
)
from app.services.h11_v3_actual_transport_binding_no_post import (
    H11V3DisabledTransportBinding,
    H11V3FakeHttpxClient,
    H11V3FakeIfdocoSender,
    H11V3FakeSealedCredential,
    H11V3SenderOutcome,
    H11V3TransportBindingError,
)


def _ifdoco_summary():  # type: ignore[no-untyped-def]
    return summarize_gmo_fx_private_request_plan(
        build_gmo_fx_ifdoco_request_plan(
            symbol="USD_JPY",
            first_side="BUY",
            first_size="10000",
            first_price="150.1",
            second_size="10000",
            second_limit_price="151.0",
            second_stop_price="149.0",
            client_order_id="SYNTHETIC123",
        )
    )


def test_default_binding_refuses_and_permission_is_not_constructible() -> None:
    binding = H11V3DisabledTransportBinding()
    assert binding.actual_post_allowed is False
    assert binding.actual_transport_bound is False
    assert binding.activation_token_constructible is False
    assert "actual_post_allowed" not in inspect.signature(
        H11V3DisabledTransportBinding
    ).parameters
    with pytest.raises(H11V3TransportBindingError, match="refuses"):
        binding.execute_fake_review(_ifdoco_summary())


def test_fake_credential_and_fake_httpx_client_execute_synthetic_once() -> None:
    credential = H11V3FakeSealedCredential()
    client = H11V3FakeHttpxClient()
    sender = H11V3FakeIfdocoSender(client=client, credential=credential)
    binding = H11V3DisabledTransportBinding(sender=sender)

    result = binding.execute_fake_review(_ifdoco_summary())

    assert result.outcome is H11V3SenderOutcome.ACCEPTED_SYNTHETIC
    assert result.fake_request_count == 1
    assert result.actual_post_count == 0
    assert result.broker_write is False
    assert result.credential_read is False
    assert client.network_enabled is False
    assert client.actual_post_count == 0
    assert credential.credential_read is False
    assert binding.actual_post_allowed is False


def test_fake_unknown_result_remains_no_post_and_safe() -> None:
    client = H11V3FakeHttpxClient(outcome=H11V3SenderOutcome.UNKNOWN_SYNTHETIC)
    binding = H11V3DisabledTransportBinding(
        sender=H11V3FakeIfdocoSender(
            client=client,
            credential=H11V3FakeSealedCredential(),
        )
    )
    result = binding.execute_fake_review(_ifdoco_summary())
    assert result.outcome is H11V3SenderOutcome.UNKNOWN_SYNTHETIC
    assert result.actual_post_count == 0


def test_non_fake_sender_is_rejected_at_injection_point() -> None:
    class UnsafeSender:
        fake_only = False

        def send_ifdoco_once_sanitized(self, plan_summary):  # type: ignore[no-untyped-def]
            raise AssertionError(plan_summary)

    with pytest.raises(H11V3TransportBindingError, match="non-fake"):
        H11V3DisabledTransportBinding(sender=UnsafeSender())


def test_non_ifdoco_plan_is_rejected_before_fake_client_call() -> None:
    client = H11V3FakeHttpxClient()
    binding = H11V3DisabledTransportBinding(
        sender=H11V3FakeIfdocoSender(
            client=client,
            credential=H11V3FakeSealedCredential(),
        )
    )
    entry_summary = summarize_gmo_fx_private_request_plan(
        build_gmo_fx_entry_request_plan(symbol="USD_JPY", side="BUY", size="10000")
    )
    with pytest.raises(H11V3TransportBindingError, match="IFDOCO"):
        binding.execute_fake_review(entry_summary)
    assert client.fake_request_count == 0
    assert client.actual_post_count == 0


def test_module_has_no_real_network_credential_or_allow_imports() -> None:
    import app.services.h11_v3_actual_transport_binding_no_post as module

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
