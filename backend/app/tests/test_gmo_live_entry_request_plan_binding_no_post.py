"""No-POST tests for the entry request plan current-turn binding.

These tests pin that the binding is default-deny and fail-closed, that the
operator signal maps mechanically (never by AI inference) to the order kind
safe label, that only the dedicated ENTRY plan is bindable, that raw
body/ID/price/size/PnL/credential exposure requests are refused, that no
result is ever truthy or a POST permission, and that the safe previews carry
labels and safe booleans only.
"""

from __future__ import annotations

import pathlib
from dataclasses import asdict

import pytest

from app.private_api.order_builders import (
    GMO_FX_ENTRY_ORDER_PATH,
    REQUEST_KIND_ENTRY,
    build_gmo_fx_official_settlement_request_plan,
)
from app.services.gmo_live_entry_request_plan_binding import (
    OPERATOR_SIGNAL_TO_ORDER_KIND_SAFE_LABEL,
    EntryRequestPlanBindingInput,
    GmoEntryRequestPlanBindingError,
    GmoEntryRequestPlanStatus,
    bind_entry_request_plan_current_turn,
    build_actual_entry_gate_sanitized_preview,
    build_bound_entry_request_plan,
    build_entry_request_plan_safe_preview,
    validate_entry_only_request_plan,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_entry_request_plan_binding.py"
)


def _bindable_input(**overrides: object) -> EntryRequestPlanBindingInput:
    base = EntryRequestPlanBindingInput(
        operator_signal_type_safe_label="ENTRY_BUY",
        current_turn_binding_confirmed=True,
        approved_symbol_source_present=True,
        approved_size_source_present=True,
        approved_execution_type_source_present=True,
    )
    kwargs = asdict(base)
    kwargs.update(overrides)
    return EntryRequestPlanBindingInput(**kwargs)  # type: ignore[arg-type]


class TestDefaultDeny:
    def test_default_input_is_not_bound_and_falsey(self) -> None:
        result = bind_entry_request_plan_current_turn(EntryRequestPlanBindingInput())
        assert result.status is (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST
        )
        assert result.order_kind_safe_label == ""
        assert result.request_plan_current_turn_binding is False
        assert result.actual_entry_POST_allowed is False
        assert result.blocked_reasons
        assert not result

    def test_bound_safe_result_is_still_falsey_and_not_a_permission(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        assert result.status is (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_BOUND_SAFE
        )
        assert result.actual_entry_POST_allowed is False
        assert not result


class TestMechanicalMapping:
    def test_entry_buy_maps_to_entry_open_buy(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        assert result.order_kind_safe_label == "ENTRY_OPEN_BUY"
        assert result.request_plan_is_entry_only is True
        assert result.request_plan_current_turn_binding is True

    def test_entry_sell_maps_to_entry_open_sell(self) -> None:
        result = bind_entry_request_plan_current_turn(
            _bindable_input(operator_signal_type_safe_label="ENTRY_SELL")
        )
        assert result.order_kind_safe_label == "ENTRY_OPEN_SELL"

    @pytest.mark.parametrize("label", ["HOLD", "", "UNKNOWN", "entry_buy"])
    def test_non_executable_signal_is_not_bound(self, label: str) -> None:
        result = bind_entry_request_plan_current_turn(
            _bindable_input(operator_signal_type_safe_label=label)
        )
        assert result.status is (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST
        )
        assert (
            "OPERATOR_SIGNAL_NOT_EXECUTABLE_FOR_ENTRY_PLAN" in result.blocked_reasons
        )
        assert result.order_kind_safe_label == ""

    def test_mapping_has_no_hold_and_no_ai_default(self) -> None:
        assert "HOLD" not in OPERATOR_SIGNAL_TO_ORDER_KIND_SAFE_LABEL
        assert set(OPERATOR_SIGNAL_TO_ORDER_KIND_SAFE_LABEL) == {
            "ENTRY_BUY",
            "ENTRY_SELL",
        }


class TestNotBoundBlockers:
    @pytest.mark.parametrize(
        ("override", "expected_reason"),
        [
            (
                {"approved_symbol_source_present": False},
                "APPROVED_SYMBOL_SOURCE_MISSING",
            ),
            (
                {"approved_size_source_present": False},
                "APPROVED_SIZE_SOURCE_MISSING",
            ),
            (
                {"approved_execution_type_source_present": False},
                "APPROVED_EXECUTION_TYPE_SOURCE_MISSING",
            ),
            ({"ai_inference_required": True}, "AI_INFERENCE_REQUIRED_BLOCKED"),
        ],
    )
    def test_missing_source_or_ai_inference_blocks(
        self, override: dict, expected_reason: str
    ) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input(**override))
        assert result.status is (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_NOT_BOUND_NO_POST
        )
        assert expected_reason in result.blocked_reasons
        assert result.request_plan_current_turn_binding is False

    def test_unconfirmed_current_turn_needs_fresh_actual_gate(self) -> None:
        result = bind_entry_request_plan_current_turn(
            _bindable_input(current_turn_binding_confirmed=False)
        )
        assert result.status is (
            GmoEntryRequestPlanStatus
            .ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_FRESH_ACTUAL_GATE
        )
        assert "CURRENT_TURN_BINDING_NOT_CONFIRMED" in result.blocked_reasons
        assert result.request_plan_current_turn_binding is False


class TestUnsafeToUse:
    @pytest.mark.parametrize(
        ("override", "expected_reason"),
        [
            (
                {"raw_body_exposure_requested": True},
                "RAW_BODY_EXPOSURE_REQUESTED_BLOCKED",
            ),
            ({"ids_exposure_requested": True}, "IDS_EXPOSURE_REQUESTED_BLOCKED"),
            (
                {"price_size_pnl_exposure_requested": True},
                "PRICE_SIZE_PNL_EXPOSURE_REQUESTED_BLOCKED",
            ),
            (
                {"credential_exposure_requested": True},
                "CREDENTIAL_EXPOSURE_REQUESTED_BLOCKED",
            ),
            (
                {"settlement_plan_requested": True},
                "SETTLEMENT_PLAN_REQUESTED_BLOCKED",
            ),
            ({"close_plan_requested": True}, "CLOSE_PLAN_REQUESTED_BLOCKED"),
            ({"generic_plan_requested": True}, "GENERIC_PLAN_REQUESTED_BLOCKED"),
        ],
    )
    def test_exposure_or_non_entry_plan_is_unsafe(
        self, override: dict, expected_reason: str
    ) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input(**override))
        assert result.status is (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_UNSAFE_TO_USE
        )
        assert expected_reason in result.blocked_reasons
        assert result.request_plan_is_entry_only is False
        assert result.order_kind_safe_label == ""
        assert result.request_plan_current_turn_binding is False

    def test_result_exposure_flags_stay_false(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        assert result.request_plan_raw_body_exposed is False
        assert result.request_plan_ids_exposed is False
        assert result.request_plan_price_size_pnl_exposed is False
        assert result.request_plan_credentials_exposed is False


class TestBoundPlanBuilder:
    def test_bound_safe_builds_entry_only_plan(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        plan = build_bound_entry_request_plan(
            binding_result=result,
            approved_symbol="USD_JPY",
            approved_size="1",
        )
        assert plan.request_kind == REQUEST_KIND_ENTRY
        assert plan.method == "POST"
        assert plan.path == GMO_FX_ENTRY_ORDER_PATH
        validate_entry_only_request_plan(plan)  # does not raise

    def test_not_bound_result_refuses_to_build(self) -> None:
        result = bind_entry_request_plan_current_turn(EntryRequestPlanBindingInput())
        with pytest.raises(GmoEntryRequestPlanBindingError):
            build_bound_entry_request_plan(
                binding_result=result,
                approved_symbol="USD_JPY",
                approved_size="1",
            )

    def test_needs_fresh_actual_gate_result_refuses_to_build(self) -> None:
        result = bind_entry_request_plan_current_turn(
            _bindable_input(current_turn_binding_confirmed=False)
        )
        with pytest.raises(GmoEntryRequestPlanBindingError):
            build_bound_entry_request_plan(
                binding_result=result,
                approved_symbol="USD_JPY",
                approved_size="1",
            )

    def test_settlement_plan_fails_entry_only_validation(self) -> None:
        settlement_plan = build_gmo_fx_official_settlement_request_plan(
            symbol="USD_JPY", side="SELL", size="1"
        )
        with pytest.raises(GmoEntryRequestPlanBindingError):
            validate_entry_only_request_plan(settlement_plan)


class TestSafePreviews:
    def test_binding_preview_carries_labels_and_safe_booleans_only(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        preview = build_entry_request_plan_safe_preview(result)
        assert preview.request_plan_status_safe_label == (
            "ENTRY_REQUEST_PLAN_BOUND_SAFE"
        )
        assert preview.order_kind_safe_label == "ENTRY_OPEN_BUY"
        assert preview.request_plan_is_entry_only is True
        assert preview.request_plan_current_turn_binding is True
        assert preview.request_plan_raw_body_exposed is False
        assert preview.request_plan_ids_exposed is False
        assert preview.request_plan_price_size_pnl_exposed is False
        assert preview.request_plan_credentials_exposed is False
        assert not preview

    def test_previews_contain_no_symbol_size_or_body_values(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        build_bound_entry_request_plan(
            binding_result=result,
            approved_symbol="USD_JPY",
            approved_size="1",
        )
        preview = build_entry_request_plan_safe_preview(result)
        rendered = repr(preview) + repr(result)
        assert "USD_JPY" not in rendered
        assert "body_json" not in rendered
        assert "symbol" not in repr(preview)

    def test_combined_gate_preview_is_safe_labels_only(self) -> None:
        result = bind_entry_request_plan_current_turn(_bindable_input())
        gate_preview = build_actual_entry_gate_sanitized_preview(
            operator_signal_type_safe_label="ENTRY_BUY",
            binding_preview=build_entry_request_plan_safe_preview(result),
            market_status_safe_label="MARKET_OPEN_SAFE",
            ticker_freshness_safe_label="TICKER_FRESH_SAFE",
            spread_status_safe_label="SPREAD_WITHIN_LIMIT_SAFE",
            runtime_position_safe_status="NO_POSITION",
            active_pending_safe_status="CLEAR",
            credential_presence_safe_boolean=True,
            permit_status_safe_label="PERMIT_UNUSED_SAFE",
            hard_guard_status_safe_label="HARD_GUARD_DEFAULT_DENY_PRESENT",
            sender_injection_ready_safe_label="SENDER_INJECTION_READY",
        )
        assert gate_preview.order_kind_safe_label == "ENTRY_OPEN_BUY"
        assert gate_preview.request_plan_status_safe_label == (
            "ENTRY_REQUEST_PLAN_BOUND_SAFE"
        )
        assert gate_preview.entry_post_max_count == 1
        assert gate_preview.retry is False
        assert gate_preview.repost is False
        assert gate_preview.second_post is False
        assert gate_preview.settlement_post is False
        assert gate_preview.generic_close is False
        assert gate_preview.raw_id_value_exposure is False
        assert gate_preview.credential_value_exposed is False
        assert not gate_preview
        rendered = repr(gate_preview)
        assert "USD_JPY" not in rendered
        assert "api_key" not in rendered


class TestSourceScan:
    def test_module_has_no_settlement_close_or_generic_route(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "closeOrder" not in text
        assert "settlePosition" not in text
        assert "live_order_once" not in text
        assert "app.live_verification" not in text
        assert "OFFICIAL_SETTLEMENT" not in text

    def test_module_does_not_read_env_or_network_client(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "os.environ" not in text
        assert "getenv" not in text
        assert "load_dotenv" not in text
        assert "httpx" not in text
        assert "requests" not in text

    def test_module_has_no_allow_literals_or_raw_response_field(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
        assert "actual_entry_POST_allowed=True" not in text
        assert "actual_settlement_POST_allowed=True" not in text
        assert "allow_real_broker_post=True" not in text
        assert "allow_live_http_post=True" not in text
        assert "retry_allowed=True" not in text
        assert "repost_allowed=True" not in text
        assert "second_post_allowed=True" not in text
        raw_text = MODULE_PATH.read_text(encoding="utf-8")
        assert "raw_response" not in raw_text
        assert "EXPOSATION" not in raw_text
