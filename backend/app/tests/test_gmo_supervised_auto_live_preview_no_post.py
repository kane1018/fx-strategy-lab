"""No-POST tests for the supervised auto live preview package."""

from __future__ import annotations

import inspect
from dataclasses import fields

from app.services import gmo_supervised_auto_live_preview as module
from app.services.gmo_paper_auto_cycle_runner import AutoPreviewSignal
from app.services.gmo_supervised_auto_live_preview import (
    REQUIRED_FUTURE_GATES,
    REQUIRED_FUTURE_OPERATOR_INPUT_NAMES,
    WHY_PREVIEW_IS_NOT_PERMISSION,
    GmoAutoTrendSafeLabel,
    GmoSupervisedAutoLivePreviewPackage,
    SupervisedAutoPreviewSafeInput,
    build_gmo_supervised_auto_live_preview,
    derive_auto_preview_signal,
)


def _all_green(trend: GmoAutoTrendSafeLabel) -> SupervisedAutoPreviewSafeInput:
    return SupervisedAutoPreviewSafeInput(
        trend_safe_label=trend,
        position_flat_safe=True,
        market_open_safe=True,
        ticker_fresh_safe=True,
        spread_within_limit_safe=True,
        active_pending_clear_safe=True,
    )


class TestSignalDerivation:
    def test_uptrend_derives_buy_preview(self) -> None:
        signal = derive_auto_preview_signal(
            _all_green(GmoAutoTrendSafeLabel.UPTREND)
        )
        assert signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY

    def test_downtrend_derives_sell_preview(self) -> None:
        signal = derive_auto_preview_signal(
            _all_green(GmoAutoTrendSafeLabel.DOWNTREND)
        )
        assert signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_SELL

    def test_flat_derives_hold_preview(self) -> None:
        signal = derive_auto_preview_signal(_all_green(GmoAutoTrendSafeLabel.FLAT))
        assert signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_HOLD

    def test_unknown_trend_is_blocked(self) -> None:
        signal = derive_auto_preview_signal(
            _all_green(GmoAutoTrendSafeLabel.UNKNOWN)
        )
        assert signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED

    def test_default_input_is_blocked_fail_closed(self) -> None:
        signal = derive_auto_preview_signal(SupervisedAutoPreviewSafeInput())
        assert signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED

    def test_open_position_never_yields_entry_preview(self) -> None:
        preview_input = SupervisedAutoPreviewSafeInput(
            trend_safe_label=GmoAutoTrendSafeLabel.UPTREND,
            position_flat_safe=False,
            market_open_safe=True,
            ticker_fresh_safe=True,
            spread_within_limit_safe=True,
            active_pending_clear_safe=True,
        )
        signal = derive_auto_preview_signal(preview_input)
        assert signal is AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED


class TestPreviewPackage:
    def test_buy_preview_is_not_operator_entry_buy(self) -> None:
        package = build_gmo_supervised_auto_live_preview(
            _all_green(GmoAutoTrendSafeLabel.UPTREND)
        )
        assert package.auto_preview_signal is (
            AutoPreviewSignal.AUTO_PREVIEW_SIGNAL_BUY
        )
        assert package.auto_preview_signal.value != "ENTRY_BUY"
        assert package.auto_preview_signal_is_operator_signal is False
        assert package.proposed_action_safe_label == "AUTO_PREVIEW_ENTRY_OPEN_BUY"

    def test_sell_preview_is_not_operator_entry_sell(self) -> None:
        package = build_gmo_supervised_auto_live_preview(
            _all_green(GmoAutoTrendSafeLabel.DOWNTREND)
        )
        assert package.auto_preview_signal.value != "ENTRY_SELL"
        assert package.auto_preview_signal_is_operator_signal is False

    def test_buy_preview_requires_future_operator_gate(self) -> None:
        package = build_gmo_supervised_auto_live_preview(
            _all_green(GmoAutoTrendSafeLabel.UPTREND)
        )
        assert package.proposal_would_require_live_gate is True
        assert package.required_future_gates == REQUIRED_FUTURE_GATES
        assert (
            package.required_future_operator_input_names
            == REQUIRED_FUTURE_OPERATOR_INPUT_NAMES
        )
        assert (
            "OPERATOR_CURRENT_TURN_EXACT_CONFIRMATION_NOT_BANKED"
            in package.required_future_gates
        )
        assert package.why_not_permission == WHY_PREVIEW_IS_NOT_PERMISSION

    def test_hold_preview_proposes_no_order(self) -> None:
        package = build_gmo_supervised_auto_live_preview(
            _all_green(GmoAutoTrendSafeLabel.FLAT)
        )
        assert package.proposed_action_safe_label == "AUTO_PREVIEW_NO_ORDER"
        assert package.proposal_would_require_live_gate is False
        assert package.required_future_gates == ()

    def test_blocked_preview_proposes_no_order(self) -> None:
        package = build_gmo_supervised_auto_live_preview(
            SupervisedAutoPreviewSafeInput()
        )
        assert package.proposed_action_safe_label == (
            "AUTO_PREVIEW_BLOCKED_NO_ORDER"
        )
        assert package.proposal_would_require_live_gate is False

    def test_package_is_never_a_permission_and_never_truthy(self) -> None:
        package = build_gmo_supervised_auto_live_preview(
            _all_green(GmoAutoTrendSafeLabel.UPTREND)
        )
        assert package.actual_entry_POST_allowed is False
        assert package.actual_settlement_POST_allowed is False
        assert package.operator_confirmation_generated is False
        assert package.operator_confirmation_banked is False
        assert package.broker_write_performed is False
        assert package.real_http_performed is False
        assert package.runtime_private_get_performed is False
        assert package.credential_value_read is False
        assert package.env_read_performed is False
        assert package.raw_id_value_exposure is False
        assert package.local_sealed_value_file_read is False
        assert package.real_sender_injected is False
        assert package.hard_guard_allow_resolved is False
        assert not package

    def test_package_has_no_field_for_confirmation_values(self) -> None:
        field_names = {f.name for f in fields(GmoSupervisedAutoLivePreviewPackage)}
        assert "operator_current_turn_exact_confirmation" not in field_names
        assert "operator_signal_type" not in field_names
        # Requirements carry input NAMES only, not values.
        assert (
            "operator_current_turn_exact_confirmation"
            in REQUIRED_FUTURE_OPERATOR_INPUT_NAMES
        )


class TestModuleIsolation:
    def test_module_has_no_real_broker_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "build_auth_headers" not in source
        assert "/private/v1" not in source
