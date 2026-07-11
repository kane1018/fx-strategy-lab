"""No-POST tests for the disabled H-11 v3 actual boundary."""

from __future__ import annotations

import inspect

import pytest

from app.private_api.order_builders import (
    build_gmo_fx_entry_request_plan,
    build_gmo_fx_ifdoco_request_plan,
    summarize_gmo_fx_private_request_plan,
)
from app.services.h11_v3_disabled_actual_boundary import (
    H11V3ActualActivation,
    H11V3ActualBoundaryReviewInput,
    H11V3DisabledActualBoundaryError,
    H11V3DisabledIfdocoTransport,
    review_h11_v3_disabled_actual_boundary,
)
from app.services.h11_v3_ifdoco_profile import H11_V3_CONFIG_HASH


def _ifdoco_summary():  # type: ignore[no-untyped-def]
    plan = build_gmo_fx_ifdoco_request_plan(
        symbol="USD_JPY",
        first_side="BUY",
        first_size="10000",
        first_price="150.1",
        second_size="10000",
        second_limit_price="151.0",
        second_stop_price="149.0",
        client_order_id="SYNTHETIC123",
    )
    return summarize_gmo_fx_private_request_plan(plan)


def test_activation_is_unconstructible_and_transport_cannot_send() -> None:
    with pytest.raises(H11V3DisabledActualBoundaryError):
        H11V3ActualActivation()
    transport = H11V3DisabledIfdocoTransport(plan_summary=_ifdoco_summary())
    assert not transport
    with pytest.raises(H11V3DisabledActualBoundaryError, match="no actual activation"):
        transport.send_ifdoco_once_sanitized()


def test_review_identifies_current_external_blockers() -> None:
    review = review_h11_v3_disabled_actual_boundary(
        H11V3ActualBoundaryReviewInput(
            plan_summary=_ifdoco_summary(),
            expected_config_hash=H11_V3_CONFIG_HASH,
            persistent_lock_ready=True,
            intent_first_ready=True,
            risk_stop_ready=True,
            boot_reconcile_ready=True,
            notification_dead_man_ready=True,
            server_side_oco_spec_ready=True,
            broker_native_expiry_confirmed=False,
            partial_fill_policy_ready=False,
            sealed_credential_boundary_reviewed=False,
        )
    )
    assert review.structural_review_ready is False
    assert review.blocked_reasons == (
        "BROKER_NATIVE_EXPIRY_NOT_CONFIRMED",
        "PARTIAL_FILL_POLICY_NOT_READY",
        "SEALED_CREDENTIAL_BOUNDARY_NOT_REVIEWED",
    )
    assert review.actual_transport_bound is False
    assert review.sender_bound is False
    assert review.hard_guard_allow_resolved is False
    assert review.allow_bridge_present is False
    assert review.actual_post_allowed is False
    assert review.actual_post_count == 0


def test_all_no_post_review_inputs_can_be_structurally_clear_without_permission() -> None:
    review = review_h11_v3_disabled_actual_boundary(
        H11V3ActualBoundaryReviewInput(
            plan_summary=_ifdoco_summary(),
            expected_config_hash=H11_V3_CONFIG_HASH,
            persistent_lock_ready=True,
            intent_first_ready=True,
            risk_stop_ready=True,
            boot_reconcile_ready=True,
            notification_dead_man_ready=True,
            server_side_oco_spec_ready=True,
            broker_native_expiry_confirmed=True,
            partial_fill_policy_ready=True,
            sealed_credential_boundary_reviewed=True,
        )
    )
    assert review.structural_review_ready is True
    assert review.blocked_reasons == ()
    assert review.actual_post_allowed is False


def test_non_ifdoco_plan_is_rejected() -> None:
    entry_summary = summarize_gmo_fx_private_request_plan(
        build_gmo_fx_entry_request_plan(symbol="USD_JPY", side="BUY", size="10000")
    )
    review = review_h11_v3_disabled_actual_boundary(
        H11V3ActualBoundaryReviewInput(
            plan_summary=entry_summary,
            expected_config_hash=H11_V3_CONFIG_HASH,
        )
    )
    assert "IFDOCO_PROTECTED_ENTRY_KIND_REQUIRED" in review.blocked_reasons
    assert "IFDOCO_ROUTE_REQUIRED" in review.blocked_reasons


def test_disabled_boundary_has_no_external_or_allow_capability() -> None:
    import app.services.h11_v3_disabled_actual_boundary as module

    source = inspect.getsource(module)
    for marker in (
        "httpx",
        "requests",
        "os.environ",
        "getenv",
        "load_dotenv",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "allow=True",
    ):
        assert marker not in source
