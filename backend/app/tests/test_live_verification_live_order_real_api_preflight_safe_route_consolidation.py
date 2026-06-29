from __future__ import annotations

import ast
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from app.live_verification.live_order_candidate import LIVE_ORDER_CANDIDATE_SIZE
from app.live_verification.live_order_real_api_preflight_execution import (
    STEP6E_MAX_SPREAD_JPY,
    STEP6E_MAX_TICKER_AGE_SECONDS,
    STEP6E_MIN_TICKER_AGE_SECONDS,
)
from app.live_verification.live_order_real_api_preflight_safe_route_consolidation import (
    LiveOrderRealApiPreflightConsolidationDataPolicy,
    LiveOrderRealApiPreflightLocalStaticSanitizedInput,
    LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput,
    LiveOrderRealApiPreflightPublicMarketSanitizedInput,
    LiveOrderRealApiPreflightSafeRouteConsolidationStatus,
    build_live_order_real_api_preflight_safe_route_consolidation,
    render_live_order_real_api_preflight_safe_route_consolidation_markdown,
    sanitize_live_order_real_api_preflight_ticker,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_OPEN_STATE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import CREATED_AT

Status = LiveOrderRealApiPreflightSafeRouteConsolidationStatus
_DEFAULT_PRIVATE = object()
_DEFAULT_PUBLIC = object()
_DEFAULT_LOCAL = object()


def _private(
    **overrides: object,
) -> LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput:
    values = {
        "source_route_name": "private_readonly_connection_script_sanitized",
        "source_route_verified_no_post": True,
        "source_route_verified_no_order_endpoint": True,
        "source_route_verified_no_live_order_once": True,
        "source_route_verified_no_raw_output": True,
        "source_route_verified_sanitized_output_only": True,
        "account_asset_status": "asset_status_sanitized_ok",
        "account_asset_check_passed": True,
        "open_positions_count": 0,
        "open_positions_check_passed": True,
        "active_orders_count": 0,
        "active_orders_check_passed": True,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightPrivateReadOnlySanitizedInput(**values)


def _public(
    **overrides: object,
) -> LiveOrderRealApiPreflightPublicMarketSanitizedInput:
    values = {
        "source_route_name": "public_market_adapter_sanitized",
        "source_route_verified_no_post": True,
        "source_route_verified_no_order_endpoint": True,
        "source_route_verified_no_live_order_once": True,
        "source_route_verified_no_raw_output": True,
        "source_route_verified_sanitized_output_only": True,
        "market_session_state": MARKET_HOURS_OPEN_STATE,
        "market_window_allowed": True,
        "broker_maintenance_active": False,
        "holiday_or_special_close": False,
        "market_hours_unknown": False,
        "ticker_symbol": SUPPORTED_SYMBOL,
        "ticker_bid": 150.001,
        "ticker_ask": 150.006,
        "ticker_spread_jpy": STEP6E_MAX_SPREAD_JPY,
        "ticker_age_seconds": STEP6E_MAX_TICKER_AGE_SECONDS,
        "ticker_check_passed": True,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightPublicMarketSanitizedInput(**values)


def _local(
    **overrides: object,
) -> LiveOrderRealApiPreflightLocalStaticSanitizedInput:
    values = {
        "source_route_name": "local_static_preflight_checks_sanitized",
        "source_route_verified_no_post": True,
        "source_route_verified_no_order_endpoint": True,
        "source_route_verified_no_live_order_once": True,
        "source_route_verified_no_raw_output": True,
        "source_route_verified_sanitized_output_only": True,
        "instrument_symbol": SUPPORTED_SYMBOL,
        "instrument_min_open_order_size": LIVE_ORDER_CANDIDATE_SIZE,
        "instrument_size_step": 1,
        "instrument_rule_check_passed": True,
        "permission_scope_check_passed": True,
        "ip_account_binding_check_passed": True,
        "previous_result_unknown_check_passed": True,
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightLocalStaticSanitizedInput(**values)


def _consolidation(
    *,
    private_input: object = _DEFAULT_PRIVATE,
    public_input: object = _DEFAULT_PUBLIC,
    local_input: object = _DEFAULT_LOCAL,
    data_policy: LiveOrderRealApiPreflightConsolidationDataPolicy | None = None,
):
    actual_private = _private() if private_input is _DEFAULT_PRIVATE else private_input
    actual_public = _public() if public_input is _DEFAULT_PUBLIC else public_input
    actual_local = _local() if local_input is _DEFAULT_LOCAL else local_input
    return build_live_order_real_api_preflight_safe_route_consolidation(
        private_readonly_input=actual_private,
        public_market_input=actual_public,
        local_static_input=actual_local,
        created_at=CREATED_AT,
        data_policy=data_policy,
    )


def test_complete_sanitized_inputs_consolidate_for_step6e_r2_no_api_no_post() -> None:
    result = _consolidation()
    consolidated = result.consolidated_result

    assert (
        consolidated.consolidation_status
        is Status.SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST
    )
    assert consolidated.consolidation_ready is True
    assert consolidated.eligible_for_step6e_r2_retry is True
    assert consolidated.allowed_for_live is False
    assert consolidated.read_only_api_called_this_step is False
    assert consolidated.public_api_called_this_step is False
    assert consolidated.private_api_called_this_step is False
    assert consolidated.broker_called_this_step is False
    assert consolidated.order_endpoint_called_this_step is False
    assert consolidated.live_order_once_called_this_step is False
    assert consolidated.post_executed_this_step is False
    assert consolidated.raw_response_saved is False
    assert consolidated.raw_response_displayed is False
    assert consolidated.blocked_reasons == ()


def test_missing_private_input_blocks_missing_input() -> None:
    result = _consolidation(private_input=None)

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT
    assert result.eligible_for_step6e_r2_retry is False
    assert "missing_private_readonly_input" in result.blocked_reasons


def test_missing_public_input_blocks_missing_input() -> None:
    result = _consolidation(public_input=None)

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT
    assert "missing_public_market_input" in result.blocked_reasons


def test_missing_local_static_input_blocks_missing_input() -> None:
    result = _consolidation(local_input=None)

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT
    assert "missing_local_static_input" in result.blocked_reasons


def test_route_no_post_false_blocks_unsafe_route() -> None:
    result = _consolidation(
        private_input=_private(source_route_verified_no_post=False),
    )

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE
    assert "private_readonly:source_route_verified_no_post_not_verified" in result.blocked_reasons


def test_route_no_order_endpoint_false_blocks_unsafe_route() -> None:
    result = _consolidation(
        public_input=_public(source_route_verified_no_order_endpoint=False),
    )

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE
    assert (
        "public_market:source_route_verified_no_order_endpoint_not_verified"
        in result.blocked_reasons
    )


def test_route_no_live_order_once_false_blocks_unsafe_route() -> None:
    result = _consolidation(
        local_input=_local(source_route_verified_no_live_order_once=False),
    )

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE
    assert (
        "local_static:source_route_verified_no_live_order_once_not_verified"
        in result.blocked_reasons
    )


def test_route_no_raw_output_false_blocks_unsafe_route() -> None:
    result = _consolidation(
        public_input=_public(source_route_verified_no_raw_output=False),
    )

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE
    assert (
        "public_market:source_route_verified_no_raw_output_not_verified"
        in result.blocked_reasons
    )


def test_route_sanitized_output_only_false_blocks_unsafe_route() -> None:
    result = _consolidation(
        private_input=_private(source_route_verified_sanitized_output_only=False),
    )

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE
    assert (
        "private_readonly:source_route_verified_sanitized_output_only_not_verified"
        in result.blocked_reasons
    )


def test_missing_required_field_blocks_incomplete_fields() -> None:
    result = _consolidation(local_input=_local(instrument_symbol=None))

    assert result.consolidation_status is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_INCOMPLETE_FIELDS
    assert "missing_instrument_symbol" in result.blocked_reasons


def test_market_closed_blocks_preflight_not_passing() -> None:
    result = _consolidation(public_input=_public(market_session_state="CLOSE"))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "market_session_not_open" in result.blocked_reasons


def test_maintenance_active_blocks_preflight_not_passing() -> None:
    result = _consolidation(public_input=_public(broker_maintenance_active=True))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "broker_maintenance_active" in result.blocked_reasons


def test_market_unknown_blocks_preflight_not_passing() -> None:
    result = _consolidation(public_input=_public(market_hours_unknown=True))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "market_hours_unknown" in result.blocked_reasons


def test_open_positions_nonzero_blocks_preflight_not_passing() -> None:
    result = _consolidation(private_input=_private(open_positions_count=1))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "open_positions_not_zero" in result.blocked_reasons


def test_active_orders_nonzero_blocks_preflight_not_passing() -> None:
    result = _consolidation(private_input=_private(active_orders_count=1))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "active_orders_not_zero" in result.blocked_reasons


def test_ticker_spread_too_wide_blocks_preflight_not_passing() -> None:
    result = _consolidation(
        public_input=_public(ticker_spread_jpy=STEP6E_MAX_SPREAD_JPY + 0.001),
    )

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "ticker_spread_too_wide" in result.blocked_reasons


def test_ticker_age_too_old_blocks_preflight_not_passing() -> None:
    result = _consolidation(
        public_input=_public(ticker_age_seconds=STEP6E_MAX_TICKER_AGE_SECONDS + 1),
    )

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "ticker_age_stale" in result.blocked_reasons


def test_ticker_age_future_skew_beyond_limit_blocks_preflight_not_passing() -> None:
    result = _consolidation(
        public_input=_public(ticker_age_seconds=STEP6E_MIN_TICKER_AGE_SECONDS - 1),
    )

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "ticker_age_stale" in result.blocked_reasons


def test_ticker_age_future_skew_within_limit_can_consolidate() -> None:
    result = _consolidation(
        public_input=_public(ticker_age_seconds=STEP6E_MIN_TICKER_AGE_SECONDS),
    )

    assert (
        result.consolidation_status
        is Status.SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST
    )
    assert result.consolidation_ready is True


def test_ticker_sanitizer_uses_actual_gmo_public_time_field_without_timestamp() -> None:
    ticker = SimpleNamespace(
        symbol=SUPPORTED_SYMBOL,
        bid=150.001,
        ask=150.006,
        time=CREATED_AT.isoformat(),
    )

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT + timedelta(seconds=1),
    )

    assert not hasattr(ticker, "timestamp")
    assert sanitized.ticker_time_field == "time"
    assert sanitized.ticker_age_seconds == 1.0
    assert sanitized.ticker_spread_jpy is not None
    assert round(sanitized.ticker_spread_jpy, 3) == 0.005
    assert sanitized.ticker_check_passed is True
    assert sanitized.blocked_reasons == ()


def test_ticker_sanitizer_supports_timestamp_field_when_present() -> None:
    ticker = {
        "symbol": SUPPORTED_SYMBOL,
        "bid": 150.001,
        "ask": 150.006,
        "timestamp": CREATED_AT.isoformat(),
    }

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT + timedelta(seconds=1),
    )

    assert sanitized.ticker_time_field == "timestamp"
    assert sanitized.ticker_age_seconds == 1.0
    assert sanitized.ticker_check_passed is True


def test_ticker_sanitizer_missing_time_fails_closed_without_exception() -> None:
    ticker = SimpleNamespace(symbol=SUPPORTED_SYMBOL, bid=150.001, ask=150.006)

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT,
    )

    assert sanitized.ticker_age_seconds is None
    assert sanitized.ticker_check_passed is False
    assert sanitized.blocked_reasons == ("ticker_time_missing",)


def test_ticker_sanitizer_future_timestamp_within_clock_skew_passes() -> None:
    ticker = SimpleNamespace(
        symbol=SUPPORTED_SYMBOL,
        bid=150.001,
        ask=150.006,
        time=(CREATED_AT + timedelta(seconds=5)).isoformat(),
    )

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT,
    )

    assert sanitized.ticker_age_seconds == STEP6E_MIN_TICKER_AGE_SECONDS
    assert sanitized.ticker_check_passed is True


def test_ticker_sanitizer_future_timestamp_beyond_clock_skew_fails_closed() -> None:
    ticker = SimpleNamespace(
        symbol=SUPPORTED_SYMBOL,
        bid=150.001,
        ask=150.006,
        time=(CREATED_AT + timedelta(seconds=6)).isoformat(),
    )

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT,
    )

    assert sanitized.ticker_age_seconds == STEP6E_MIN_TICKER_AGE_SECONDS - 1
    assert sanitized.ticker_check_passed is False
    assert "ticker_age_future_skew" in sanitized.blocked_reasons


def test_ticker_sanitizer_stale_timestamp_fails_closed() -> None:
    ticker = SimpleNamespace(
        symbol=SUPPORTED_SYMBOL,
        bid=150.001,
        ask=150.006,
        time=(
            CREATED_AT - timedelta(seconds=STEP6E_MAX_TICKER_AGE_SECONDS + 1)
        ).isoformat(),
    )

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT,
    )

    assert sanitized.ticker_age_seconds == STEP6E_MAX_TICKER_AGE_SECONDS + 1
    assert sanitized.ticker_check_passed is False
    assert "ticker_age_stale" in sanitized.blocked_reasons


def test_ticker_sanitizer_spread_too_wide_fails_closed() -> None:
    ticker = SimpleNamespace(
        symbol=SUPPORTED_SYMBOL,
        bid=150.001,
        ask=150.012,
        time=CREATED_AT.isoformat(),
    )

    sanitized = sanitize_live_order_real_api_preflight_ticker(
        ticker,
        observed_at=CREATED_AT,
    )

    assert sanitized.ticker_spread_jpy > STEP6E_MAX_SPREAD_JPY
    assert sanitized.ticker_check_passed is False
    assert "ticker_spread_too_wide" in sanitized.blocked_reasons


def test_ticker_sanitizer_serialization_does_not_hold_raw_secret_or_real_id_values() -> None:
    sanitized = sanitize_live_order_real_api_preflight_ticker(
        SimpleNamespace(
            symbol=SUPPORTED_SYMBOL,
            bid=150.001,
            ask=150.006,
            time=CREATED_AT.isoformat(),
        ),
        observed_at=CREATED_AT,
    )
    serialized = str(asdict(sanitized))
    represented = repr(sanitized)

    assert sanitized.raw_response_saved is False
    assert sanitized.raw_response_displayed is False
    assert sanitized.headers_displayed is False
    assert sanitized.signature_displayed is False
    assert sanitized.credentials_displayed is False
    for forbidden_value in (
        "raw-response-value",
        "header-value",
        "signature-value",
        "credential-value",
        "real-order-id-value",
    ):
        assert forbidden_value not in serialized
        assert forbidden_value not in represented


def test_permission_scope_failed_blocks_preflight_not_passing() -> None:
    result = _consolidation(local_input=_local(permission_scope_check_passed=False))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "permission_scope_check_failed" in result.blocked_reasons


def test_ip_account_binding_failed_blocks_preflight_not_passing() -> None:
    result = _consolidation(local_input=_local(ip_account_binding_check_passed=False))

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "ip_account_binding_check_failed" in result.blocked_reasons


def test_previous_result_unknown_failed_blocks_preflight_not_passing() -> None:
    result = _consolidation(
        local_input=_local(previous_result_unknown_check_passed=False),
    )

    assert (
        result.consolidation_status
        is Status.BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING
    )
    assert "previous_result_unknown_check_failed" in result.blocked_reasons


def test_data_policy_forbids_raw_headers_signatures_credentials_and_ids() -> None:
    policy = _consolidation().consolidation.data_policy

    assert policy.raw_request_display_allowed is False
    assert policy.raw_request_save_allowed is False
    assert policy.raw_response_display_allowed is False
    assert policy.raw_response_save_allowed is False
    assert policy.headers_display_allowed is False
    assert policy.headers_save_allowed is False
    assert policy.signature_display_allowed is False
    assert policy.signature_save_allowed is False
    assert policy.credentials_display_allowed is False
    assert policy.credentials_save_allowed is False
    assert policy.real_order_ids_display_allowed is False
    assert policy.real_execution_ids_display_allowed is False
    assert policy.real_position_ids_display_allowed is False
    assert policy.client_order_ids_display_allowed is False
    assert policy.sanitized_fields_only is True
    assert policy.api_execution_allowed_this_step is False
    assert policy.post_allowed_this_step is False
    assert policy.order_endpoint_allowed_this_step is False
    assert policy.live_order_once_allowed_this_step is False


def test_markdown_renderer_includes_no_api_no_post_warnings() -> None:
    markdown = render_live_order_real_api_preflight_safe_route_consolidation_markdown(
        _consolidation().consolidation,
    )

    assert "This Step 6E-SC safe route consolidation is no API / no POST." in markdown
    assert "This consolidation model does not call read-only API." in markdown
    assert "This consolidation model does not call public API." in markdown
    assert "This consolidation model does not call Private API." in markdown
    assert "This consolidation model does not call broker." in markdown
    assert "This consolidation model does not call live_order_once." in markdown
    assert "This consolidation model does not execute HTTP POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert "credential-value" not in markdown
    assert "raw-response-value" not in markdown
    assert "real-order-id-value" not in markdown


def test_serialization_repr_and_asdict_do_not_include_sensitive_actual_values() -> None:
    consolidation = _consolidation().consolidation
    serialized = str(asdict(consolidation))
    represented = repr(consolidation)

    for forbidden_value in (
        "credential-value",
        "raw-response-value",
        "real-order-id-value",
        "header-value",
        "signature-value",
    ):
        assert forbidden_value not in serialized
        assert forbidden_value not in represented


def test_new_module_has_no_http_private_broker_live_order_once_dependencies() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_api_preflight_safe_route_consolidation.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http.client",
        "socket",
        "subprocess",
        "dotenv",
        "app." + "brokers",
        "app." + "private_api",
        "app.live_verification.live_order_once",
    }
    blocked_names = {
        "Order" + "Request",
        "get" + "env",
        "ENABLE_" + "LIVE_TRADING",
        "GMO_FX_API_" + "KEY",
        "GMO_FX_API_" + "SECRET",
        "post_live_order_with_httpx",
        "execute_one_shot_live_order",
        "prepare_one_shot_live_order",
        "pbcopy",
    }
    blocked_call_names = {
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "prepare_one_shot_live_order",
        "pbcopy",
        "read_text",
        "write_text",
    }
    blocked_attrs = {"en" + "viron", "get" + "env"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not any(
                    alias.name == blocked or alias.name.startswith(f"{blocked}.")
                    for blocked in blocked_modules
                )
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not any(
                module == blocked or module.startswith(f"{blocked}.")
                for blocked in blocked_modules
            )
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names
        if isinstance(node, ast.Attribute):
            assert node.attr not in blocked_attrs
        if isinstance(node, ast.Call):
            call_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            assert call_name not in blocked_call_names
