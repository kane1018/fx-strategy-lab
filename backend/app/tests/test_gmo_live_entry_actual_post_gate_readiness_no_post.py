"""No-POST integration tests: entry actual-post gate readiness aggregation.

Critical: even when every fake boundary is satisfied, the aggregated summary
must never authorize a real POST.
"""

from __future__ import annotations

import pathlib

from app.services.gmo_live_entry_actual_post_gate_readiness import (
    GmoEntryActualPostReadinessStatus,
    build_gmo_entry_actual_post_gate_readiness_summary,
)
from app.services.gmo_live_entry_post_permit import build_gmo_entry_post_permit
from app.services.gmo_live_entry_transport import (
    FakeEntryTransport,
    ProductionEntryTransportNotImplemented,
)
from app.services.gmo_live_runtime_safe_read import (
    FakeRuntimeSafeReadClient,
    GmoRuntimeActivePendingSafeStatus,
    GmoRuntimeMarketSafeStatus,
    GmoRuntimePositionSafeStatus,
    GmoRuntimeSafeReadSnapshot,
    GmoRuntimeSpreadSafeStatus,
    GmoRuntimeTickerFreshnessSafeStatus,
    evaluate_gmo_runtime_safe_read_gate,
)
from app.services.gmo_live_sealed_credential_provider import (
    FakeSealedCredentialProvider,
    build_gmo_sealed_credential_presence,
    build_gmo_sealed_credential_presence_not_configured,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_entry_actual_post_gate_readiness.py"
)


def _clear_runtime_gate():
    snapshot = GmoRuntimeSafeReadSnapshot(
        performed=True,
        fresh=True,
        position_status=GmoRuntimePositionSafeStatus.NO_POSITION,
        position_count_safe=0,
        active_pending_status=GmoRuntimeActivePendingSafeStatus.CLEAR,
        active_order_count_safe=0,
        market_status=GmoRuntimeMarketSafeStatus.OPEN,
        ticker_status=GmoRuntimeTickerFreshnessSafeStatus.FRESH,
        spread_status=GmoRuntimeSpreadSafeStatus.WITHIN_LIMIT,
    )
    return evaluate_gmo_runtime_safe_read_gate(
        FakeRuntimeSafeReadClient(snapshot=snapshot).read_safe_snapshot()
    )


def _granted_permit():
    return build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=True,
        operator_signal_is_entry_buy_or_sell=True,
    )


def _ready_credential():
    return build_gmo_sealed_credential_presence(
        provider=FakeSealedCredentialProvider(present=True),
        current_turn_actual_use_authorization_present=True,
    )


def test_default_boundaries_block_and_never_allow_actual_post() -> None:
    summary = build_gmo_entry_actual_post_gate_readiness_summary(
        credential_presence=build_gmo_sealed_credential_presence_not_configured(),
        permit=build_gmo_entry_post_permit(
            operator_current_turn_exact_confirmation_present=False,
            operator_readiness_present=False,
            operator_signal_is_entry_buy_or_sell=False,
        ),
        runtime_gate=evaluate_gmo_runtime_safe_read_gate(GmoRuntimeSafeReadSnapshot()),
        entry_transport=FakeEntryTransport(),
    )
    assert summary.no_post_foundation_ready is False
    assert summary.actual_entry_POST_allowed is False
    assert (
        summary.status
        is GmoEntryActualPostReadinessStatus.BLOCKED_BY_CREDENTIAL_BOUNDARY
    )
    assert bool(summary) is False


def test_all_fake_boundaries_ready_still_never_allows_actual_post() -> None:
    summary = build_gmo_entry_actual_post_gate_readiness_summary(
        credential_presence=_ready_credential(),
        permit=_granted_permit(),
        runtime_gate=_clear_runtime_gate(),
        entry_transport=FakeEntryTransport(),
    )
    assert summary.no_post_foundation_ready is True
    # The single most important assertion of this whole step:
    assert summary.actual_entry_POST_allowed is False
    assert summary.entry_post_execution_gate_is_separate_step is True
    assert summary.production_real_transport_implemented is False
    assert (
        "PRODUCTION_REAL_ENTRY_TRANSPORT_NOT_IMPLEMENTED"
        in summary.blocked_reasons
    )
    assert (
        summary.status
        is GmoEntryActualPostReadinessStatus
        .NO_POST_FOUNDATION_READY_STILL_NOT_ACTUAL_POST_ALLOWED
    )
    assert summary.ai_trade_decision_performed is False
    assert summary.operator_confirmation_substituted is False
    assert bool(summary) is False


def test_real_transport_is_never_treated_as_available() -> None:
    summary = build_gmo_entry_actual_post_gate_readiness_summary(
        credential_presence=_ready_credential(),
        permit=_granted_permit(),
        runtime_gate=_clear_runtime_gate(),
        entry_transport=ProductionEntryTransportNotImplemented(),
    )
    assert summary.entry_transport_available_fake_only is False
    assert summary.no_post_foundation_ready is False
    assert summary.actual_entry_POST_allowed is False
    assert (
        summary.status is GmoEntryActualPostReadinessStatus.BLOCKED_BY_TRANSPORT
    )


def test_credential_present_but_not_actual_use_ready_blocks() -> None:
    summary = build_gmo_entry_actual_post_gate_readiness_summary(
        credential_presence=build_gmo_sealed_credential_presence(
            provider=FakeSealedCredentialProvider(present=True),
        ),
        permit=_granted_permit(),
        runtime_gate=_clear_runtime_gate(),
        entry_transport=FakeEntryTransport(),
    )
    assert summary.credential_present_safe_boolean is True
    assert summary.credential_actual_use_ready is False
    assert summary.no_post_foundation_ready is False
    assert summary.actual_entry_POST_allowed is False
    assert (
        summary.status
        is GmoEntryActualPostReadinessStatus.BLOCKED_BY_CREDENTIAL_BOUNDARY
    )


def test_module_hardcodes_actual_post_allowed_false() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "actual_entry_POST_allowed:bool=False" in text
    assert "actual_entry_POST_allowed=False" in text
    assert "actual_entry_POST_allowed=True" not in text
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text


def test_module_does_not_read_env_or_network() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "httpx" not in text
    assert "app.live_verification" not in text
    assert "live_order_once" not in text
