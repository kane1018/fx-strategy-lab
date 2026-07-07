"""No-POST tests for the official settlement preflight boundary.

Synthetic values only. No network, no credentials, no `.env`.
"""

from __future__ import annotations

import inspect

import pytest

from app.private_api.order_builders import (
    GMO_FX_OFFICIAL_SETTLEMENT_METHOD,
    GMO_FX_OFFICIAL_SETTLEMENT_PATH,
    REQUEST_KIND_OFFICIAL_SETTLEMENT,
    build_gmo_fx_entry_request_plan,
)
from app.services import gmo_live_official_settlement_preflight as module
from app.services.gmo_live_official_settlement_preflight import (
    GENERIC_CLOSE_FORBIDDEN_STATUS,
    POSITION_SPECIFIC_PATH_BLOCKED_STATUS,
    GmoOfficialSettlementPreflightError,
    GmoOfficialSettlementPreflightInput,
    GmoOfficialSettlementPreflightStatus,
    GmoOfficialSettlementRouteStatus,
    GmoSettlementSideProvenanceStatus,
    GmoSettlementSizeSourceStatus,
    SealedOfficialSettlementValueSource,
    build_gmo_official_settlement_preflight_package,
    build_official_settlement_sanitized_preview,
    build_sealed_official_settlement_value_source_not_configured,
    derive_official_settlement_side_from_prior_entry,
    load_sealed_official_settlement_value_source_from_operator_local_file,
    review_official_settlement_route,
    validate_official_settlement_only_request_plan,
)

SYNTHETIC_SYMBOL = "USD_JPY"
SYNTHETIC_SIZE = "137"  # synthetic sentinel used only in tests


def _configured_source() -> SealedOfficialSettlementValueSource:
    return SealedOfficialSettlementValueSource(
        operator_supplied_symbol_value=SYNTHETIC_SYMBOL,
        operator_supplied_size_value=SYNTHETIC_SIZE,
    )


def _ready_provenance():
    return derive_official_settlement_side_from_prior_entry("ENTRY_BUY")


def _all_safe_input() -> GmoOfficialSettlementPreflightInput:
    return GmoOfficialSettlementPreflightInput(
        one_position_open_count_one_confirmed=True,
        active_pending_clear_count_zero_confirmed=True,
        runtime_read_confirmed_safe=True,
        credential_presence_safe_boolean_confirmed=True,
    )


class TestSideProvenance:
    def test_entry_buy_maps_to_settlement_sell(self) -> None:
        provenance = derive_official_settlement_side_from_prior_entry("ENTRY_BUY")
        assert provenance.ready
        assert provenance.settlement_side_safe_label == "SETTLEMENT_SELL"

    def test_entry_sell_maps_to_settlement_buy(self) -> None:
        provenance = derive_official_settlement_side_from_prior_entry("ENTRY_SELL")
        assert provenance.ready
        assert provenance.settlement_side_safe_label == "SETTLEMENT_BUY"

    @pytest.mark.parametrize("label", ["HOLD", "", "UNKNOWN", "ENTRY_OPEN_BUY"])
    def test_non_executable_labels_are_never_derivable(self, label: str) -> None:
        provenance = derive_official_settlement_side_from_prior_entry(label)
        assert not provenance.ready
        assert provenance.settlement_side_safe_label == ""
        assert provenance.status is (
            GmoSettlementSideProvenanceStatus
            .SETTLEMENT_SIDE_PROVENANCE_BLOCKED_NOT_DERIVABLE
        )

    def test_provenance_is_never_truthy(self) -> None:
        assert not _ready_provenance()


class TestSealedValueSource:
    def test_default_source_is_not_configured_and_blocks(self) -> None:
        source = build_sealed_official_settlement_value_source_not_configured()
        assert source.present_safe_boolean() is False
        assert source.status is (
            GmoSettlementSizeSourceStatus
            .SETTLEMENT_SIZE_SOURCE_MISSING_BLOCK_ACTUAL_SETTLEMENT_GATE
        )
        with pytest.raises(GmoOfficialSettlementPreflightError):
            source.build_bound_official_settlement_request_plan_internal(
                side_provenance=_ready_provenance()
            )

    def test_configured_source_is_present_not_exposed(self) -> None:
        source = _configured_source()
        assert source.present_safe_boolean() is True
        assert source.status is (
            GmoSettlementSizeSourceStatus.SETTLEMENT_SIZE_SOURCE_PRESENT_NOT_EXPOSED
        )

    def test_source_is_sealed_never_truthy_and_repr_sanitized(self) -> None:
        source = _configured_source()
        assert not source
        assert SYNTHETIC_SIZE not in repr(source)
        assert SYNTHETIC_SIZE not in str(source)
        assert not hasattr(source, "__dict__")

    def test_symbol_mismatch_is_rejected_without_echo(self) -> None:
        with pytest.raises(GmoOfficialSettlementPreflightError) as excinfo:
            SealedOfficialSettlementValueSource(
                operator_supplied_symbol_value="EUR_JPY",
                operator_supplied_size_value=SYNTHETIC_SIZE,
            )
        assert "EUR_JPY" not in str(excinfo.value)
        assert SYNTHETIC_SIZE not in str(excinfo.value)

    @pytest.mark.parametrize("bad_size", ["", "abc", "-1", "0"])
    def test_bad_size_shape_is_rejected_without_echo(self, bad_size: str) -> None:
        with pytest.raises(GmoOfficialSettlementPreflightError) as excinfo:
            SealedOfficialSettlementValueSource(
                operator_supplied_symbol_value=SYNTHETIC_SYMBOL,
                operator_supplied_size_value=bad_size,
            )
        if bad_size:
            assert bad_size not in str(excinfo.value)

    def test_partial_supply_is_rejected(self) -> None:
        with pytest.raises(GmoOfficialSettlementPreflightError):
            SealedOfficialSettlementValueSource(
                operator_supplied_symbol_value=SYNTHETIC_SYMBOL
            )


class TestLocalFileLoader:
    def test_missing_file_returns_not_configured_source(self, tmp_path) -> None:
        source = load_sealed_official_settlement_value_source_from_operator_local_file(
            tmp_path / "missing.local.json"
        )
        assert source.present_safe_boolean() is False

    def test_valid_file_seals_values(self, tmp_path) -> None:
        path = tmp_path / "value.local.json"
        path.write_text(
            f'{{"symbol": "{SYNTHETIC_SYMBOL}", "size": "{SYNTHETIC_SIZE}"}}',
            encoding="utf-8",
        )
        source = load_sealed_official_settlement_value_source_from_operator_local_file(
            path
        )
        assert source.present_safe_boolean() is True
        assert SYNTHETIC_SIZE not in repr(source)

    @pytest.mark.parametrize(
        "content",
        [
            "not json",
            '{"symbol": "USD_JPY"}',
            '{"symbol": "USD_JPY", "size": "137", "extra": 1}',
            '{"symbol": "USD_JPY", "size": 137}',
        ],
    )
    def test_malformed_file_raises_without_echo(self, tmp_path, content) -> None:
        path = tmp_path / "value.local.json"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(GmoOfficialSettlementPreflightError) as excinfo:
            load_sealed_official_settlement_value_source_from_operator_local_file(
                path
            )
        assert SYNTHETIC_SIZE not in str(excinfo.value)


class TestInternalPlanBuild:
    def test_internal_plan_is_settlement_only(self) -> None:
        plan = _configured_source().build_bound_official_settlement_request_plan_internal(
            side_provenance=_ready_provenance()
        )
        assert plan.request_kind == REQUEST_KIND_OFFICIAL_SETTLEMENT
        assert plan.method == GMO_FX_OFFICIAL_SETTLEMENT_METHOD
        assert plan.path == GMO_FX_OFFICIAL_SETTLEMENT_PATH
        validate_official_settlement_only_request_plan(plan)

    def test_prior_entry_buy_builds_sell_settlement(self) -> None:
        plan = _configured_source().build_bound_official_settlement_request_plan_internal(
            side_provenance=_ready_provenance()
        )
        assert '"side":"SELL"' in plan.body_json

    def test_blocked_provenance_raises_without_echo(self) -> None:
        blocked = derive_official_settlement_side_from_prior_entry("HOLD")
        with pytest.raises(GmoOfficialSettlementPreflightError) as excinfo:
            _configured_source().build_bound_official_settlement_request_plan_internal(
                side_provenance=blocked
            )
        assert SYNTHETIC_SIZE not in str(excinfo.value)

    def test_entry_plan_is_rejected_by_validator(self) -> None:
        entry_plan = build_gmo_fx_entry_request_plan(
            symbol=SYNTHETIC_SYMBOL, side="BUY", size=SYNTHETIC_SIZE
        )
        with pytest.raises(GmoOfficialSettlementPreflightError):
            validate_official_settlement_only_request_plan(entry_plan)


class TestRouteReview:
    def test_dedicated_route_is_ready(self) -> None:
        assert review_official_settlement_route() is (
            GmoOfficialSettlementRouteStatus
            .OFFICIAL_SETTLEMENT_ROUTE_READY_DEDICATED_CLOSE_ORDER
        )


class TestPreflightPackage:
    def _ready_package(self):
        return build_gmo_official_settlement_preflight_package(
            preflight_input=_all_safe_input(),
            route_status=review_official_settlement_route(),
            side_provenance=_ready_provenance(),
            size_source_status=_configured_source().status,
        )

    def test_all_safe_input_is_ready(self) -> None:
        package = self._ready_package()
        assert package.status is (
            GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_READY_NO_POST
        )
        assert package.blocked_reasons == ()

    def test_ready_is_never_a_post_permission(self) -> None:
        package = self._ready_package()
        assert package.actual_settlement_POST_allowed is False
        assert package.actual_entry_POST_allowed is False
        assert package.retry_allowed is False
        assert package.repost_allowed is False
        assert package.second_post_allowed is False
        assert package.generic_close_allowed is False
        assert package.position_specific_settlement_allowed is False
        assert package.current_turn_settlement_confirmation_bankable is False
        assert package.settlement_post_max_count == 1
        assert not package

    def test_fixed_forbidden_statuses(self) -> None:
        package = self._ready_package()
        assert package.generic_close_forbidden_status == (
            GENERIC_CLOSE_FORBIDDEN_STATUS
        )
        assert package.position_specific_path_status == (
            POSITION_SPECIFIC_PATH_BLOCKED_STATUS
        )

    @pytest.mark.parametrize(
        "missing_field",
        [
            "one_position_open_count_one_confirmed",
            "active_pending_clear_count_zero_confirmed",
            "runtime_read_confirmed_safe",
            "credential_presence_safe_boolean_confirmed",
        ],
    )
    def test_each_missing_runtime_gate_blocks(self, missing_field: str) -> None:
        kwargs = {
            "one_position_open_count_one_confirmed": True,
            "active_pending_clear_count_zero_confirmed": True,
            "runtime_read_confirmed_safe": True,
            "credential_presence_safe_boolean_confirmed": True,
        }
        kwargs[missing_field] = False
        package = build_gmo_official_settlement_preflight_package(
            preflight_input=GmoOfficialSettlementPreflightInput(**kwargs),
            route_status=review_official_settlement_route(),
            side_provenance=_ready_provenance(),
            size_source_status=_configured_source().status,
        )
        assert package.status is (
            GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST
        )

    @pytest.mark.parametrize(
        "violation_field",
        [
            "generic_close_requested",
            "position_specific_settlement_requested",
            "entry_post_requested",
            "retry_requested",
            "repost_requested",
            "second_post_requested",
            "raw_response_exposure_requested",
            "ids_exposure_requested",
            "price_size_pnl_exposure_requested",
            "credential_exposure_requested",
        ],
    )
    def test_each_violation_blocks(self, violation_field: str) -> None:
        preflight_input = GmoOfficialSettlementPreflightInput(
            one_position_open_count_one_confirmed=True,
            active_pending_clear_count_zero_confirmed=True,
            runtime_read_confirmed_safe=True,
            credential_presence_safe_boolean_confirmed=True,
            **{violation_field: True},
        )
        package = build_gmo_official_settlement_preflight_package(
            preflight_input=preflight_input,
            route_status=review_official_settlement_route(),
            side_provenance=_ready_provenance(),
            size_source_status=_configured_source().status,
        )
        assert package.status is (
            GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST
        )

    def test_missing_size_source_blocks(self) -> None:
        package = build_gmo_official_settlement_preflight_package(
            preflight_input=_all_safe_input(),
            route_status=review_official_settlement_route(),
            side_provenance=_ready_provenance(),
            size_source_status=(
                build_sealed_official_settlement_value_source_not_configured().status
            ),
        )
        assert package.status is (
            GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST
        )
        assert (
            "SETTLEMENT_SIZE_SOURCE_MISSING_BLOCK_ACTUAL_SETTLEMENT_GATE"
            in package.blocked_reasons
        )

    def test_blocked_provenance_blocks(self) -> None:
        package = build_gmo_official_settlement_preflight_package(
            preflight_input=_all_safe_input(),
            route_status=review_official_settlement_route(),
            side_provenance=derive_official_settlement_side_from_prior_entry("HOLD"),
            size_source_status=_configured_source().status,
        )
        assert package.status is (
            GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST
        )
        assert "SETTLEMENT_SIDE_PROVENANCE_NOT_READY" in package.blocked_reasons


class TestSanitizedPreview:
    def test_preview_uses_safe_labels_only(self) -> None:
        preview = build_official_settlement_sanitized_preview(
            side_provenance=_ready_provenance()
        )
        assert preview.settlement_route_safe_label == (
            "OFFICIAL_SIZE_BASED_CLOSE_ORDER"
        )
        assert preview.settlement_side_safe_label == "SETTLEMENT_SELL"
        assert preview.symbol_safe_label == "USD_JPY"
        assert preview.size_profile_safe_label == "GMO_MINIMUM_ALLOWED_SIZE"
        assert preview.execution_type_safe_label == "MARKET"
        assert preview.settlement_post_max_count == 1
        assert preview.retry is False
        assert preview.repost is False
        assert preview.second_post is False
        assert preview.entry_post is False
        assert preview.generic_close is False
        assert preview.position_specific_settlement is False
        assert not preview

    def test_preview_requires_ready_provenance(self) -> None:
        blocked = derive_official_settlement_side_from_prior_entry("HOLD")
        with pytest.raises(GmoOfficialSettlementPreflightError):
            build_official_settlement_sanitized_preview(side_provenance=blocked)


class TestModuleIsolation:
    def test_module_has_no_real_post_capability_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "build_auth_headers" not in source
