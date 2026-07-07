"""No-POST tests for the sealed operator-supplied internal value source.

These tests pin that the source is fail-closed by default (missing blocks
the actual gate), that operator-supplied values are sealed (never exposed
via repr/str/dict or any accessor), that validation rejects unsafe values
without echoing them, that the full profile -> binding -> internal plan
chain works without any raw value crossing a reporting boundary, and that
the module has no settlement/close/generic/env/network surface. All values
used here are synthetic test values, never real approved sizes.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.private_api.order_builders import (
    GMO_FX_ENTRY_ORDER_PATH,
    REQUEST_KIND_ENTRY,
)
from app.services.gmo_live_approved_entry_internal_value_source import (
    OPERATOR_LOCAL_VALUE_FILE_NAME,
    GmoApprovedEntryInternalValueSourceError,
    SealedApprovedEntryInternalValueSource,
    build_approved_entry_internal_value_source_not_configured,
    load_sealed_approved_entry_internal_value_source_from_operator_local_file,
)
from app.services.gmo_live_approved_entry_order_profile import (
    GmoApprovedEntryInternalRawValueSourceStatus,
    build_approved_entry_order_profile,
)
from app.services.gmo_live_entry_request_plan_binding import (
    GmoEntryRequestPlanBindingError,
    GmoEntryRequestPlanStatus,
    bind_entry_request_plan_current_turn,
    binding_input_from_approved_profile,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_approved_entry_internal_value_source.py"
)

# Synthetic test-only values; NOT the real approved size.
_TEST_SYMBOL = "USD_JPY"
_TEST_SIZE = "42"


def _configured_source() -> SealedApprovedEntryInternalValueSource:
    return SealedApprovedEntryInternalValueSource(
        operator_supplied_symbol_value=_TEST_SYMBOL,
        operator_supplied_size_value=_TEST_SIZE,
    )


class TestFailClosedDefault:
    def test_not_configured_source_is_missing_and_blocks(self) -> None:
        source = build_approved_entry_internal_value_source_not_configured()
        assert source.present_safe_boolean() is False
        assert source.status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE
        )
        assert not source

    def test_not_configured_source_refuses_to_build_a_plan(self) -> None:
        source = build_approved_entry_internal_value_source_not_configured()
        binding_input = binding_input_from_approved_profile(
            profile=build_approved_entry_order_profile(),
            operator_signal_type_safe_label="ENTRY_BUY",
            current_turn_binding_confirmed=True,
        )
        result = bind_entry_request_plan_current_turn(binding_input)
        with pytest.raises(GmoApprovedEntryInternalValueSourceError):
            source.build_bound_entry_request_plan_internal(binding_result=result)

    def test_missing_source_keeps_profile_and_binding_blocked(self) -> None:
        source = build_approved_entry_internal_value_source_not_configured()
        profile = build_approved_entry_order_profile(internal_value_source=source)
        assert profile.internal_raw_value_source_present is False
        binding_input = binding_input_from_approved_profile(
            profile=profile,
            operator_signal_type_safe_label="ENTRY_BUY",
            current_turn_binding_confirmed=True,
        )
        result = bind_entry_request_plan_current_turn(binding_input)
        assert result.status is (
            GmoEntryRequestPlanStatus
            .ENTRY_REQUEST_PLAN_PRESENT_BUT_NEEDS_INTERNAL_VALUE_SOURCE
        )


class TestValidation:
    def test_symbol_mismatch_is_rejected_without_echoing_values(self) -> None:
        with pytest.raises(GmoApprovedEntryInternalValueSourceError) as excinfo:
            SealedApprovedEntryInternalValueSource(
                operator_supplied_symbol_value="EUR_JPY",
                operator_supplied_size_value=_TEST_SIZE,
            )
        assert "EUR_JPY" not in str(excinfo.value)
        assert _TEST_SIZE not in str(excinfo.value)

    @pytest.mark.parametrize("bad_size", ["", "abc", "-1", "0"])
    def test_unsafe_size_is_rejected_without_echoing_value(
        self, bad_size: str
    ) -> None:
        with pytest.raises(GmoApprovedEntryInternalValueSourceError) as excinfo:
            SealedApprovedEntryInternalValueSource(
                operator_supplied_symbol_value=_TEST_SYMBOL,
                operator_supplied_size_value=bad_size,
            )
        if bad_size:
            assert bad_size not in str(excinfo.value)

    def test_partial_supply_is_rejected(self) -> None:
        with pytest.raises(GmoApprovedEntryInternalValueSourceError):
            SealedApprovedEntryInternalValueSource(
                operator_supplied_symbol_value=_TEST_SYMBOL
            )
        with pytest.raises(GmoApprovedEntryInternalValueSourceError):
            SealedApprovedEntryInternalValueSource(
                operator_supplied_size_value=_TEST_SIZE
            )


class TestSealedNonExposure:
    def test_repr_and_str_are_sanitized(self) -> None:
        source = _configured_source()
        for rendered in (repr(source), str(source)):
            assert rendered == (
                "SealedApprovedEntryInternalValueSource(<sanitized>)"
            )
            assert _TEST_SIZE not in rendered
            assert _TEST_SYMBOL not in rendered

    def test_source_has_no_dict_surface_and_is_never_truthy(self) -> None:
        source = _configured_source()
        assert not hasattr(source, "__dict__")
        assert not source

    def test_no_public_accessor_returns_the_values(self) -> None:
        source = _configured_source()
        public_methods = [
            name
            for name in dir(source)
            if not name.startswith("_") and callable(getattr(source, name))
        ]
        assert set(public_methods) == {
            "present_safe_boolean",
            "build_bound_entry_request_plan_internal",
        }
        assert source.present_safe_boolean() is True


class TestFullChainInternalOnly:
    def test_configured_source_completes_binding_and_builds_entry_plan(
        self,
    ) -> None:
        source = _configured_source()
        profile = build_approved_entry_order_profile(internal_value_source=source)
        assert profile.internal_raw_value_source_present is True
        assert profile.internal_raw_value_source_status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED
        )
        binding_input = binding_input_from_approved_profile(
            profile=profile,
            operator_signal_type_safe_label="ENTRY_BUY",
            current_turn_binding_confirmed=True,
        )
        result = bind_entry_request_plan_current_turn(binding_input)
        assert result.status is (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_BOUND_SAFE
        )
        assert result.order_kind_safe_label == "ENTRY_OPEN_BUY"
        assert result.actual_entry_POST_allowed is False

        plan = source.build_bound_entry_request_plan_internal(
            binding_result=result
        )
        assert plan.request_kind == REQUEST_KIND_ENTRY
        assert plan.path == GMO_FX_ENTRY_ORDER_PATH
        # The sealed values flow ONLY into the internal plan body (which goes
        # to the injected sender and is never reported); they never appear in
        # the binding result or the source's own rendering.
        assert _TEST_SIZE in plan.body_json
        assert _TEST_SIZE not in repr(result)
        assert _TEST_SIZE not in repr(source)

    def test_unbound_result_refuses_internal_plan_build(self) -> None:
        source = _configured_source()
        binding_input = binding_input_from_approved_profile(
            profile=build_approved_entry_order_profile(),
            operator_signal_type_safe_label="ENTRY_BUY",
            current_turn_binding_confirmed=True,
        )
        result = bind_entry_request_plan_current_turn(binding_input)
        assert result.status is not (
            GmoEntryRequestPlanStatus.ENTRY_REQUEST_PLAN_BOUND_SAFE
        )
        with pytest.raises(GmoEntryRequestPlanBindingError):
            source.build_bound_entry_request_plan_internal(binding_result=result)


class TestOperatorLocalFileChannel:
    def test_missing_file_returns_not_configured_source(self, tmp_path) -> None:
        source = (
            load_sealed_approved_entry_internal_value_source_from_operator_local_file(
                tmp_path / OPERATOR_LOCAL_VALUE_FILE_NAME
            )
        )
        assert source.present_safe_boolean() is False
        assert source.status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE
        )

    def test_valid_local_file_seals_values_without_exposure(self, tmp_path) -> None:
        value_file = tmp_path / OPERATOR_LOCAL_VALUE_FILE_NAME
        value_file.write_text(
            f'{{"symbol": "{_TEST_SYMBOL}", "size": "{_TEST_SIZE}"}}',
            encoding="utf-8",
        )
        source = (
            load_sealed_approved_entry_internal_value_source_from_operator_local_file(
                value_file
            )
        )
        assert source.present_safe_boolean() is True
        assert source.status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED
        )
        assert _TEST_SIZE not in repr(source)
        assert not source

    def test_malformed_json_raises_without_echoing_contents(self, tmp_path) -> None:
        value_file = tmp_path / OPERATOR_LOCAL_VALUE_FILE_NAME
        value_file.write_text('{"symbol": "USD_JPY", "size": ', encoding="utf-8")
        with pytest.raises(GmoApprovedEntryInternalValueSourceError) as excinfo:
            load_sealed_approved_entry_internal_value_source_from_operator_local_file(
                value_file
            )
        assert "USD_JPY" not in str(excinfo.value)

    @pytest.mark.parametrize(
        "content",
        [
            "[]",
            '{"symbol": "USD_JPY"}',
            '{"symbol": "USD_JPY", "size": "9", "extra": "x"}',
            '{"symbol": "USD_JPY", "size": 9}',
        ],
    )
    def test_wrong_shape_raises_without_echoing_contents(
        self, tmp_path, content: str
    ) -> None:
        value_file = tmp_path / OPERATOR_LOCAL_VALUE_FILE_NAME
        value_file.write_text(content, encoding="utf-8")
        with pytest.raises(GmoApprovedEntryInternalValueSourceError) as excinfo:
            load_sealed_approved_entry_internal_value_source_from_operator_local_file(
                value_file
            )
        assert "9" not in str(excinfo.value)

    def test_local_file_with_wrong_symbol_is_rejected(self, tmp_path) -> None:
        value_file = tmp_path / OPERATOR_LOCAL_VALUE_FILE_NAME
        value_file.write_text(
            f'{{"symbol": "EUR_JPY", "size": "{_TEST_SIZE}"}}', encoding="utf-8"
        )
        with pytest.raises(GmoApprovedEntryInternalValueSourceError) as excinfo:
            load_sealed_approved_entry_internal_value_source_from_operator_local_file(
                value_file
            )
        assert "EUR_JPY" not in str(excinfo.value)

    def test_local_value_file_name_is_gitignored(self) -> None:
        gitignore = (
            pathlib.Path(__file__).resolve().parents[3] / ".gitignore"
        ).read_text(encoding="utf-8")
        assert OPERATOR_LOCAL_VALUE_FILE_NAME in gitignore


class TestSourceScan:
    def test_module_has_no_settlement_close_generic_or_env_surface(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "closeOrder" not in text
        assert "settlePosition" not in text
        assert "live_order_once" not in text
        assert "app.live_verification" not in text
        assert "os.environ" not in text
        assert "getenv" not in text
        assert "load_dotenv" not in text
        assert "httpx" not in text
        assert "urllib" not in text

    def test_module_embeds_no_raw_numeric_size(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        # No multi-digit literal anywhere: the repository cannot ship a raw
        # size value inside this module.
        assert re.search(r"\d\d", text) is None

    def test_module_has_no_allow_literals_or_raw_response(self) -> None:
        squeezed = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
        assert "actual_entry_POST_allowed=True" not in squeezed
        assert "allow_real_broker_post=True" not in squeezed
        assert "allow_live_http_post=True" not in squeezed
        assert "retry_allowed=True" not in squeezed
        assert "repost_allowed=True" not in squeezed
        assert "second_post_allowed=True" not in squeezed
        assert "raw_response" not in MODULE_PATH.read_text(encoding="utf-8")
