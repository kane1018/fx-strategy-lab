"""No-POST tests for the fail-closed production entry boundary.

These tests pin that the four code-blocker resolutions are fail-closed: the
disabled production entry transport can never send in this phase, the sealed
secret box never exposes what it holds, the hard-guard controlled supply
structurally cannot carry a resolved allow, and the runtime safe-read
connection adapter is a pure mapping with fail-closed UNKNOWN degradation.
Only synthetic placeholder tokens are used; no network, env, or credential
value is touched.
"""

from __future__ import annotations

import pathlib

import pytest

from app.private_api.order_builders import (
    build_gmo_fx_entry_request_plan,
    build_gmo_fx_official_settlement_request_plan,
    summarize_gmo_fx_private_request_plan,
)
from app.services.gmo_live_entry_post_permit import build_gmo_entry_post_permit
from app.services.gmo_live_entry_transport import (
    GmoEntryPostSanitizedPreview,
    GmoEntryPostStateMachineStatus,
    simulate_gmo_entry_post_once_fake_only,
)
from app.services.gmo_live_production_entry_boundary import (
    DisabledProductionEntryTransport,
    GmoProductionEntryBoundaryError,
    HardGuardAllowControlledSupply,
    ProductionEntryTransportActivation,
    SealedSecretBox,
    build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary,
    build_hard_guard_allow_controlled_supply_default_deny,
)
from app.services.gmo_live_runtime_safe_read import (
    GmoRuntimeActivePendingSafeStatus,
    GmoRuntimeMarketSafeStatus,
    GmoRuntimePositionSafeStatus,
    GmoRuntimeSpreadSafeStatus,
    GmoRuntimeTickerFreshnessSafeStatus,
    evaluate_gmo_runtime_safe_read_gate,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_production_entry_boundary.py"
)

_FAKE_TOKEN = "SYNTHETIC_PLACEHOLDER_SEALED_TOKEN_NOT_A_REAL_CREDENTIAL"


def _sanitized_preview() -> GmoEntryPostSanitizedPreview:
    return GmoEntryPostSanitizedPreview(
        operator_signal_safe_label="ENTRY_SIGNAL_SAFE_LABEL_PLACEHOLDER",
        order_side_safe_label="SIDE_SAFE_LABEL_PLACEHOLDER",
        symbol_safe_label="USD_JPY",
        execution_type_safe_label="MARKET",
        runtime_position_safe_status="NO_POSITION",
        position_count_safe=0,
        active_pending_safe_status="CLEAR",
        credential_presence_safe_boolean=True,
    )


def _entry_transport(
    *,
    plan_kind: str = "entry",
    activation: ProductionEntryTransportActivation | None = None,
) -> DisabledProductionEntryTransport:
    if plan_kind == "entry":
        plan = build_gmo_fx_entry_request_plan(
            symbol="USD_JPY", side="BUY", size="1"
        )
    else:
        plan = build_gmo_fx_official_settlement_request_plan(
            symbol="USD_JPY", side="SELL", size="1"
        )
    permit = build_gmo_entry_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=True,
        operator_signal_is_entry_buy_or_sell=True,
    )
    return DisabledProductionEntryTransport(
        plan_safe_summary=summarize_gmo_fx_private_request_plan(plan),
        sanitized_preview=_sanitized_preview(),
        sealed_credential=SealedSecretBox(_FAKE_TOKEN),
        permit=permit,
        hard_guard_supply=build_hard_guard_allow_controlled_supply_default_deny(),
        activation=activation,
    )


class TestSealedSecretBox:
    def test_repr_and_str_never_contain_the_token(self) -> None:
        box = SealedSecretBox(_FAKE_TOKEN)
        assert _FAKE_TOKEN not in repr(box)
        assert _FAKE_TOKEN not in str(box)
        assert "sealed" in repr(box)

    def test_presence_safe_boolean_only(self) -> None:
        assert SealedSecretBox(_FAKE_TOKEN).presence_safe_boolean() is True
        assert SealedSecretBox(None).presence_safe_boolean() is False
        assert SealedSecretBox("").presence_safe_boolean() is False

    def test_unseal_always_raises_in_no_post_phase(self) -> None:
        with pytest.raises(GmoProductionEntryBoundaryError):
            SealedSecretBox(_FAKE_TOKEN).unseal_inside_actual_execution_boundary()

    def test_box_is_falsey_and_has_no_value_accessors(self) -> None:
        box = SealedSecretBox(_FAKE_TOKEN)
        assert not box
        public_names = [name for name in dir(box) if not name.startswith("_")]
        assert sorted(public_names) == [
            "presence_safe_boolean",
            "unseal_inside_actual_execution_boundary",
        ]


class TestHardGuardAllowControlledSupply:
    def test_default_is_deny_and_falsey(self) -> None:
        supply = build_hard_guard_allow_controlled_supply_default_deny()
        assert supply.resolved_allow is False
        assert supply.allow_bridge_present is False
        assert supply.supply_source_safe_label == "DEFAULT_DENY_NO_POST_STEP"
        assert not supply

    def test_truthy_resolved_allow_is_unconstructible(self) -> None:
        with pytest.raises(GmoProductionEntryBoundaryError):
            HardGuardAllowControlledSupply(resolved_allow=True)

    def test_allow_bridge_marker_is_unconstructible(self) -> None:
        with pytest.raises(GmoProductionEntryBoundaryError):
            HardGuardAllowControlledSupply(allow_bridge_present=True)


class TestProductionEntryTransportActivation:
    def test_activation_is_unconstructible_in_no_post_phase(self) -> None:
        with pytest.raises(GmoProductionEntryBoundaryError):
            ProductionEntryTransportActivation()


class TestDisabledProductionEntryTransport:
    def test_send_raises_without_activation(self) -> None:
        transport = _entry_transport()
        with pytest.raises(GmoProductionEntryBoundaryError, match="disabled"):
            transport.send_entry_order_sanitized()

    def test_settlement_plan_is_rejected_before_anything_else(self) -> None:
        transport = _entry_transport(plan_kind="settlement")
        with pytest.raises(GmoProductionEntryBoundaryError, match="entry-only"):
            transport.send_entry_order_sanitized()

    def test_fake_only_state_machine_refuses_this_real_transport(self) -> None:
        transport = _entry_transport()
        result = simulate_gmo_entry_post_once_fake_only(
            transport=transport,  # type: ignore[arg-type]
            permit_usable_for_one_entry_post=True,
        )
        assert result.status is (
            GmoEntryPostStateMachineStatus
            .ENTRY_POST_BLOCKED_REAL_TRANSPORT_FORBIDDEN_IN_NO_POST
        )
        assert result.fake_post_count == 0
        assert result.real_post_count == 0

    def test_transport_is_falsey_and_marked_real(self) -> None:
        transport = _entry_transport()
        assert not transport
        assert transport.is_real_transport is True


class TestRuntimeSafeReadConnectionAdapter:
    def test_successful_clear_summary_maps_to_safe_snapshot(self) -> None:
        snapshot = (
            build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary(
                connection_result="success",
                open_positions_count=0,
                active_orders_count=0,
                fresh=True,
                market_open=True,
                ticker_fresh=True,
                spread_within_limit=True,
            )
        )
        assert snapshot.performed is True
        assert snapshot.fresh is True
        assert snapshot.position_status is GmoRuntimePositionSafeStatus.NO_POSITION
        assert snapshot.position_count_safe == 0
        assert (
            snapshot.active_pending_status is GmoRuntimeActivePendingSafeStatus.CLEAR
        )
        assert snapshot.active_order_count_safe == 0
        assert evaluate_gmo_runtime_safe_read_gate(snapshot).ready is True

    def test_failure_summary_degrades_to_not_performed(self) -> None:
        snapshot = (
            build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary(
                connection_result="failure",
                open_positions_count=0,
                active_orders_count=0,
                fresh=True,
            )
        )
        assert snapshot.performed is False
        assert snapshot.fresh is False
        assert evaluate_gmo_runtime_safe_read_gate(snapshot).ready is False

    def test_stale_result_is_blocked_by_the_gate(self) -> None:
        snapshot = (
            build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary(
                connection_result="success",
                open_positions_count=0,
                active_orders_count=0,
                fresh=False,
                market_open=True,
                ticker_fresh=True,
                spread_within_limit=True,
            )
        )
        gate = evaluate_gmo_runtime_safe_read_gate(snapshot)
        assert gate.ready is False
        assert "RUNTIME_SAFE_READ_STALE" in gate.blocked_reasons

    @pytest.mark.parametrize(
        ("positions", "orders", "expected_position", "expected_active"),
        [
            (
                1,
                0,
                GmoRuntimePositionSafeStatus.ONE_POSITION_OPEN,
                GmoRuntimeActivePendingSafeStatus.CLEAR,
            ),
            (
                2,
                0,
                GmoRuntimePositionSafeStatus.MULTIPLE_POSITIONS,
                GmoRuntimeActivePendingSafeStatus.CLEAR,
            ),
            (
                0,
                1,
                GmoRuntimePositionSafeStatus.NO_POSITION,
                GmoRuntimeActivePendingSafeStatus.CONFLICT,
            ),
            (
                None,
                None,
                GmoRuntimePositionSafeStatus.UNKNOWN,
                GmoRuntimeActivePendingSafeStatus.UNKNOWN,
            ),
            (
                -1,
                -1,
                GmoRuntimePositionSafeStatus.UNKNOWN,
                GmoRuntimeActivePendingSafeStatus.UNKNOWN,
            ),
        ],
    )
    def test_nonzero_and_unknown_counts_block(
        self,
        positions: int | None,
        orders: int | None,
        expected_position: GmoRuntimePositionSafeStatus,
        expected_active: GmoRuntimeActivePendingSafeStatus,
    ) -> None:
        snapshot = (
            build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary(
                connection_result="success",
                open_positions_count=positions,
                active_orders_count=orders,
                fresh=True,
                market_open=True,
                ticker_fresh=True,
                spread_within_limit=True,
            )
        )
        assert snapshot.position_status is expected_position
        assert snapshot.active_pending_status is expected_active
        assert evaluate_gmo_runtime_safe_read_gate(snapshot).ready is False

    def test_missing_market_safe_booleans_degrade_to_unknown_and_block(self) -> None:
        snapshot = (
            build_gmo_runtime_safe_read_snapshot_from_sanitized_connection_summary(
                connection_result="success",
                open_positions_count=0,
                active_orders_count=0,
                fresh=True,
            )
        )
        assert snapshot.market_status is GmoRuntimeMarketSafeStatus.UNKNOWN
        assert (
            snapshot.ticker_status is GmoRuntimeTickerFreshnessSafeStatus.UNKNOWN
        )
        assert snapshot.spread_status is GmoRuntimeSpreadSafeStatus.UNKNOWN
        assert evaluate_gmo_runtime_safe_read_gate(snapshot).ready is False


def test_module_does_not_import_live_verification_or_live_order_once() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "app.live_verification" not in text
    assert "live_order_once" not in text


def test_module_does_not_read_env_or_network_client() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in text
    assert "getenv" not in text
    assert "load_dotenv" not in text
    assert "httpx" not in text
    assert "requests" not in text


def test_module_has_no_dangerous_allow_literals(  # source scan
) -> None:
    text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
    assert "allow=True" not in text
    assert "allow_real_broker_post=True" not in text
    assert "allow_live_http_post=True" not in text
    assert "actual_entry_POST_allowed=True" not in text
    assert "resolved_allow=True" not in text
    assert "resolved_allow:bool=False" in text
