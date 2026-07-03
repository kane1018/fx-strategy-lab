from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification import (
    live_order_real_gmo_official_settlement_route_review_controlled as review,
)

RAW_RESPONSE_SENTINEL = "RAW_RESPONSE_SHOULD_NOT_SURFACE"
POSITION_ID_SENTINEL = "POSITION_ID_SHOULD_NOT_SURFACE"
ACCOUNT_ID_SENTINEL = "ACCOUNT_ID_SHOULD_NOT_SURFACE"
ORDER_ID_SENTINEL = "ORDER_ID_SHOULD_NOT_SURFACE"
TRANSACTION_ID_SENTINEL = "TRANSACTION_ID_SHOULD_NOT_SURFACE"
CREDENTIAL_VALUE_SENTINEL = "CREDENTIAL_VALUE_SHOULD_NOT_SURFACE"
SIGNATURE_VALUE_SENTINEL = "SIGNATURE_VALUE_SHOULD_NOT_SURFACE"
HEADERS_VALUE_SENTINEL = "HEADERS_VALUE_SHOULD_NOT_SURFACE"

_FORBIDDEN_SENTINELS = (
    RAW_RESPONSE_SENTINEL,
    POSITION_ID_SENTINEL,
    ACCOUNT_ID_SENTINEL,
    ORDER_ID_SENTINEL,
    TRANSACTION_ID_SENTINEL,
    CREDENTIAL_VALUE_SENTINEL,
    SIGNATURE_VALUE_SENTINEL,
    HEADERS_VALUE_SENTINEL,
)


def _confirmed_input(
    **overrides: object,
) -> review.GmoOfficialSettlementRouteReviewInput:
    values = {
        "official_manual_accessed": True,
        "official_rules_accessed": True,
        "official_api_docs_accessed": True,
        "manual_settlement_flow_found": True,
        "manual_position_summary_settlement_button_found": True,
        "manual_position_list_settlement_button_found": True,
        "manual_buy_sell_not_netted_confirmed": True,
        "manual_generic_opposite_order_as_settlement_supported": False,
        "rules_api_new_order_min_confirmed": True,
        "rules_settlement_quantity_no_lower_limit_confirmed": True,
        "rules_hedging_possible_confirmed": True,
        "rules_trading_time_recorded": True,
        "rules_order_reception_time_recorded": True,
        "repo_official_api_docs_found": True,
        "repo_settlement_endpoint_found": True,
        "repo_settlement_parameter_found": True,
        "repo_settlement_requires_position_identifier": False,
        "official_settlement_size_without_position_identifier_confirmed": True,
        "repo_settlement_safe_identifier_handling_ready": False,
        "repo_generic_order_endpoint_only": False,
        "repo_generic_order_is_not_settlement": True,
        "generic_opposite_order_as_close_forbidden": True,
        "generic_close_primitive_revoked": True,
    }
    values.update(overrides)
    return review.GmoOfficialSettlementRouteReviewInput(**values)


def test_official_manual_urls_and_trading_rules_url_are_recorded() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(),
    )

    assert review.GMO_OFFICIAL_MANUAL_URL.endswith("kawasefx-trading-manual.pdf")
    assert review.GMO_OFFICIAL_TRADING_RULES_URL.endswith("/fx/#rule")
    assert review.GMO_OFFICIAL_API_DOCS_URL.endswith("/fxdocs/")
    assert result.official_manual_url_recorded is True
    assert result.official_trading_rules_url_recorded is True
    assert result.official_api_docs_url_recorded is True


def test_official_settlement_route_confirmed_path_is_no_post_only() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(),
    )
    rendered = review.render_gmo_official_settlement_route_review_markdown(result)
    payload = repr(asdict(result))

    assert result.case is review.GmoOfficialSettlementRouteReviewCase.CASE_1
    assert (
        result.review_status
        is review.GmoOfficialSettlementRouteReviewStatus.CONFIRMED_NO_POST
    )
    assert result.gmo_official_settlement_route_review_ready is True
    assert result.official_manual_accessed is True
    assert result.official_rules_accessed is True
    assert result.official_api_docs_accessed is True
    assert result.manual_settlement_flow_found is True
    assert result.manual_position_summary_settlement_button_found is True
    assert result.manual_position_list_settlement_button_found is True
    assert result.manual_buy_sell_not_netted_confirmed is True
    assert result.manual_generic_opposite_order_as_settlement_supported is False
    assert result.official_manual_supports_generic_opposite_order_as_settlement is False
    assert result.rules_api_new_order_min_confirmed is True
    assert result.rules_settlement_quantity_no_lower_limit_confirmed is True
    assert result.rules_hedging_possible_confirmed is True
    assert result.rules_trading_time_recorded is True
    assert result.rules_order_reception_time_recorded is True
    assert result.repo_official_api_docs_found is True
    assert result.repo_settlement_endpoint_found is True
    assert result.repo_settlement_parameter_found is True
    assert result.repo_settlement_requires_position_identifier is False
    assert result.repo_generic_order_endpoint_only is False
    assert result.repo_generic_order_is_not_settlement is True
    assert result.generic_opposite_order_as_close_forbidden is True
    assert result.generic_close_primitive_revoked is True
    assert result.official_settlement_route_confirmed is True
    assert result.actual_close_post_allowed_now is False
    assert result.future_actual_close_post_requires_dedicated_settlement_gate is True
    assert result.future_actual_close_post_requires_no_raw_id_value_exposure is True
    assert result.level5_minimal_cycle_completed is False
    assert result.level5_full_auto_cycle_completed is False
    assert result.fresh_cycle_allowed is False
    assert result.actual_entry_post is False
    assert result.actual_close_post is False
    assert result.retry_repost is False
    assert result.ledger_update is False
    assert result.receipt_handoff is False
    assert "official_settlement_route_confirmed: true" in rendered
    assert "actual_close_post_allowed_now: false" in rendered
    for forbidden in _FORBIDDEN_SENTINELS:
        assert forbidden not in payload
        assert forbidden not in rendered


def test_repo_generic_order_only_keeps_official_settlement_route_not_confirmed() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(
            official_api_docs_accessed=False,
            repo_official_api_docs_found=False,
            repo_settlement_endpoint_found=False,
            repo_settlement_parameter_found=False,
            repo_settlement_requires_position_identifier=None,
            official_settlement_size_without_position_identifier_confirmed=False,
            repo_generic_order_endpoint_only=True,
        ),
    )

    assert result.case is review.GmoOfficialSettlementRouteReviewCase.CASE_2
    assert result.review_status is review.GmoOfficialSettlementRouteReviewStatus.NOT_CONFIRMED
    assert result.official_settlement_route_confirmed is False
    assert result.actual_close_post_allowed_now is False
    assert result.repo_generic_order_endpoint_only is True
    assert result.repo_generic_order_is_not_settlement is True
    assert result.generic_opposite_order_as_close_forbidden is True
    assert result.generic_close_primitive_revoked is True


def test_settlement_route_requiring_unsafe_identifier_handling_blocks() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(
            repo_settlement_requires_position_identifier=True,
            official_settlement_size_without_position_identifier_confirmed=False,
            repo_settlement_safe_identifier_handling_ready=False,
        ),
    )

    assert result.case is review.GmoOfficialSettlementRouteReviewCase.CASE_3
    assert (
        result.review_status
        is review.GmoOfficialSettlementRouteReviewStatus
        .UNSAFE_IDENTIFIER_HANDLING_BLOCKED
    )
    assert result.official_settlement_route_confirmed is False
    assert result.actual_close_post_allowed_now is False
    assert result.repo_settlement_requires_position_identifier is True
    assert result.repo_settlement_safe_identifier_handling_ready is False
    assert "settlement_identifier_safe_handling_not_ready" in result.blocked_reasons


def test_unsafe_attempts_are_blocked_and_not_reflected_as_executed() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(
            actual_entry_post_attempted_this_step=True,
            actual_close_post_attempted_this_step=True,
            retry_attempted_this_step=True,
            raw_response_exposure_attempted_this_step=True,
            position_id_exposure_attempted_this_step=True,
            credential_value_exposure_attempted_this_step=True,
        ),
    )

    assert result.case is review.GmoOfficialSettlementRouteReviewCase.CASE_4
    assert (
        result.review_status
        is review.GmoOfficialSettlementRouteReviewStatus.UNSAFE_EXPOSURE_BLOCKED
    )
    assert result.actual_entry_post is False
    assert result.actual_close_post is False
    assert result.retry_repost is False
    assert result.raw_response_exposed is False
    assert result.position_id_exposed is False
    assert result.credential_value_exposed is False
    assert "actual_entry_post_attempted" in result.blocked_reasons
    assert "actual_close_post_attempted" in result.blocked_reasons
    assert "retry_attempted" in result.blocked_reasons
    assert "raw_id_value_exposure_attempted" in result.blocked_reasons


def test_generic_close_primitive_must_remain_revoked() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(generic_close_primitive_revoked=False),
    )

    assert result.case is review.GmoOfficialSettlementRouteReviewCase.CASE_4
    assert result.official_settlement_route_confirmed is False
    assert result.actual_close_post_allowed_now is False
    assert "generic_close_primitive_not_revoked" in result.blocked_reasons


def test_manual_buy_sell_not_netted_keeps_hedged_positions_not_flat() -> None:
    result = review.build_gmo_official_settlement_route_review_controlled(
        _confirmed_input(),
    )

    assert result.manual_buy_sell_not_netted_confirmed is True
    assert result.repo_generic_order_is_not_settlement is True
    assert result.generic_opposite_order_as_close_forbidden is True
    assert result.current_position_state == "NO_POSITION_AFTER_MANUAL_FLATTEN"


def test_gmo_official_settlement_route_review_module_has_no_execution_imports() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "live_verification"
        / "live_order_real_gmo_official_settlement_route_review_controlled.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    blocked_modules = {
        "app.brokers",
        "app.private_api",
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "socket",
        "subprocess",
        "dotenv",
        "os",
    }
    blocked_names = {
        "live_order_once",
        "execute_one_shot_live_order",
        "post_live_order_with_httpx",
        "getenv",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in blocked_modules
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in blocked_modules
        if isinstance(node, ast.Name):
            assert node.id not in blocked_names

