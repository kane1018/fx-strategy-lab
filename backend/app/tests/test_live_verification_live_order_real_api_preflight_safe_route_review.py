from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

from app.live_verification.live_order_real_api_preflight_safe_route_review import (
    REQUIRED_STEP6E_R_COVERAGE_FIELDS,
    LiveOrderRealApiPreflightRouteCandidate,
    LiveOrderRealApiPreflightRouteDataPolicy,
    LiveOrderRealApiPreflightSafeRouteReviewStatus,
    build_live_order_real_api_preflight_safe_route_review,
    default_live_order_real_api_preflight_route_candidates,
    render_live_order_real_api_preflight_safe_route_review_markdown,
)
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import CREATED_AT

Status = LiveOrderRealApiPreflightSafeRouteReviewStatus


def _candidate(**overrides: object) -> LiveOrderRealApiPreflightRouteCandidate:
    coverage_fields = overrides.pop("coverage_fields", REQUIRED_STEP6E_R_COVERAGE_FIELDS)
    values = {
        "route_name": "complete_static_safe_route",
        "route_file_path": "backend/app/live_verification/static_safe_route.py",
        "route_type": "offline_static_test_route",
        "route_scope": "sanitized Step 6E-R coverage",
        "uses_http_get": True,
        "uses_http_post": False,
        "uses_order_endpoint": False,
        "uses_live_order_once": False,
        "uses_speed_order": False,
        "uses_close_order": False,
        "uses_cancel_order": False,
        "uses_change_order": False,
        "uses_private_api": False,
        "uses_public_api": False,
        "uses_broker_order_path": False,
        "displays_raw_request": False,
        "saves_raw_request": False,
        "displays_raw_response": False,
        "saves_raw_response": False,
        "displays_headers": False,
        "saves_headers": False,
        "displays_signature": False,
        "saves_signature": False,
        "displays_credentials": False,
        "requires_env_display": False,
        "requires_env_file_display": False,
        "returns_sanitized_fields_only": True,
        "coverage_fields": tuple(coverage_fields),
        "missing_fields": tuple(
            field
            for field in REQUIRED_STEP6E_R_COVERAGE_FIELDS
            if field not in tuple(coverage_fields)
        ),
        "review_notes": ("offline static test candidate",),
    }
    values.update(overrides)
    return LiveOrderRealApiPreflightRouteCandidate(**values)


def _review(
    *,
    route_candidates: tuple[LiveOrderRealApiPreflightRouteCandidate, ...] | None = None,
    safe_route_consolidation_feasible: bool = True,
    data_policy: LiveOrderRealApiPreflightRouteDataPolicy | None = None,
):
    return build_live_order_real_api_preflight_safe_route_review(
        route_candidates=route_candidates or (_candidate(),),
        source_step6e_retry_head="78588c6",
        created_at=CREATED_AT,
        data_policy=data_policy,
        safe_route_consolidation_feasible=safe_route_consolidation_feasible,
    )


def test_complete_existing_route_coverage_is_ready_for_step6e_r2_retry() -> None:
    result = _review()
    review = result.review

    assert review.review_status is Status.READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE
    assert review.review_ready is True
    assert review.eligible_for_step6e_r2_retry is True
    assert review.eligible_for_safe_route_consolidation_implementation is False
    assert review.allowed_for_live is False
    assert review.api_executed_this_step is False
    assert review.read_only_api_called_this_step is False
    assert review.public_api_called_this_step is False
    assert review.private_api_called_this_step is False
    assert review.broker_called_this_step is False
    assert review.order_endpoint_called_this_step is False
    assert review.live_order_once_called_this_step is False
    assert review.post_executed_this_step is False
    assert review.route_gaps == ()
    assert result.allowed_for_live is False


def test_partial_safe_route_coverage_is_ready_for_consolidation_implementation() -> None:
    result = _review(
        route_candidates=default_live_order_real_api_preflight_route_candidates(),
    )
    review = result.review

    assert (
        review.review_status
        is Status.READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION
    )
    assert review.review_ready is True
    assert review.eligible_for_step6e_r2_retry is False
    assert review.eligible_for_safe_route_consolidation_implementation is True
    assert "instrument_min_open_order_size" in {
        gap.field_name for gap in review.route_gaps
    }
    assert (
        review.recommended_next_step
        == "implement_step6e_safe_route_consolidation_no_api_no_post"
    )


def test_missing_critical_fields_without_feasible_consolidation_blocks_incomplete() -> None:
    result = _review(
        route_candidates=(_candidate(coverage_fields=("market_session_state",)),),
        safe_route_consolidation_feasible=False,
    )

    assert result.review_status is Status.BLOCKED_STEP6E_SAFE_ROUTE_INCOMPLETE
    assert result.review_ready is False
    assert result.eligible_for_step6e_r2_retry is False
    assert result.eligible_for_safe_route_consolidation_implementation is False
    assert "missing_required_fields_without_feasible_consolidation" in result.blocked_reasons


def test_post_required_blocks_unsafe() -> None:
    result = _review(route_candidates=(_candidate(uses_http_post=True),))

    assert result.review_status is Status.BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE
    assert "complete_static_safe_route:uses_http_post" in result.blocked_reasons


def test_order_endpoint_required_blocks_unsafe() -> None:
    result = _review(route_candidates=(_candidate(uses_order_endpoint=True),))

    assert result.review_status is Status.BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE
    assert "complete_static_safe_route:uses_order_endpoint" in result.blocked_reasons


def test_live_order_once_required_blocks_unsafe() -> None:
    result = _review(route_candidates=(_candidate(uses_live_order_once=True),))

    assert result.review_status is Status.BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE
    assert "complete_static_safe_route:uses_live_order_once" in result.blocked_reasons


def test_raw_response_display_required_blocks_unsafe() -> None:
    result = _review(route_candidates=(_candidate(displays_raw_response=True),))

    assert result.review_status is Status.BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE
    assert "complete_static_safe_route:displays_raw_response" in result.blocked_reasons


def test_credentials_display_required_blocks_unsafe() -> None:
    result = _review(route_candidates=(_candidate(displays_credentials=True),))

    assert result.review_status is Status.BLOCKED_STEP6E_SAFE_ROUTE_UNSAFE
    assert "complete_static_safe_route:displays_credentials" in result.blocked_reasons


def test_required_coverage_fields_are_all_represented_in_matrix() -> None:
    result = _review(
        route_candidates=default_live_order_real_api_preflight_route_candidates(),
    )

    assert {item.field_name for item in result.review.coverage_items} == set(
        REQUIRED_STEP6E_R_COVERAGE_FIELDS,
    )


def test_missing_fields_are_preserved_as_route_gaps() -> None:
    result = _review(route_candidates=(_candidate(coverage_fields=("ticker_symbol",)),))

    missing = {gap.field_name for gap in result.review.route_gaps}
    assert "market_session_state" in missing
    assert "ticker_symbol" not in missing
    assert all(gap.requires_future_implementation for gap in result.review.route_gaps)


def test_data_policy_forbids_raw_headers_signatures_credentials_and_ids() -> None:
    policy = _review().review.data_policy

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
    assert policy.git_commit_real_api_results is False


def test_review_flags_always_remain_offline_no_api_no_post() -> None:
    review = _review().review

    assert review.allowed_for_live is False
    assert review.api_executed_this_step is False
    assert review.read_only_api_called_this_step is False
    assert review.public_api_called_this_step is False
    assert review.private_api_called_this_step is False
    assert review.broker_called_this_step is False
    assert review.order_endpoint_called_this_step is False
    assert review.live_order_once_called_this_step is False
    assert review.post_executed_this_step is False


def test_markdown_renderer_includes_static_no_api_no_post_warnings() -> None:
    markdown = render_live_order_real_api_preflight_safe_route_review_markdown(
        _review(
            route_candidates=default_live_order_real_api_preflight_route_candidates(),
        ).review,
    )

    assert "This Step 6E-RR safe route review is offline/static only." in markdown
    assert "This review does not call read-only API." in markdown
    assert "This review does not call public API." in markdown
    assert "This review does not call Private API." in markdown
    assert "This review does not call broker." in markdown
    assert "This review does not call live_order_once." in markdown
    assert "This review does not execute HTTP POST." in markdown
    assert "allowed_for_live=false." in markdown
    assert "remaining-real-id-value" not in markdown
    assert "credential-value" not in markdown


def test_serialization_repr_and_asdict_do_not_include_sensitive_actual_values() -> None:
    review = _review().review
    serialized = str(asdict(review))
    represented = repr(review)

    for forbidden_value in (
        "credential-value",
        "raw-payload-value",
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
        / "live_order_real_api_preflight_safe_route_review.py"
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
