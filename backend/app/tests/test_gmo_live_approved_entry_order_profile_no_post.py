"""No-POST tests for the approved entry order profile safe-label source.

These tests pin that the profile is a safe-label-only source: it carries the
approved symbol / size-profile / executionType safe labels, never a raw
numeric size, price, P/L, ID, credential, signature, or header, is never
truthy, never grants or implies an actual POST permission, and reports the
internal raw value source as missing so every actual gate blocks until a
reviewed internal source exists.
"""

from __future__ import annotations

import pathlib
from dataclasses import fields

from app.services.gmo_live_approved_entry_order_profile import (
    APPROVED_ENTRY_EXECUTION_TYPE_SAFE_LABEL,
    APPROVED_ENTRY_SIZE_PROFILE_SAFE_LABEL,
    APPROVED_ENTRY_SYMBOL_SAFE_LABEL,
    ApprovedEntryOrderProfile,
    GmoApprovedEntryInternalRawValueSourceStatus,
    GmoApprovedEntryOrderProfileStatus,
    build_approved_entry_order_profile,
    build_approved_entry_order_profile_not_configured,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_approved_entry_order_profile.py"
)


class TestSafeLabels:
    def test_ready_profile_carries_expected_safe_labels(self) -> None:
        profile = build_approved_entry_order_profile()
        assert profile.profile_status is (
            GmoApprovedEntryOrderProfileStatus
            .APPROVED_ENTRY_ORDER_PROFILE_SAFE_LABELS_READY
        )
        assert profile.approved_symbol_safe_label == "USD_JPY"
        assert profile.approved_size_profile_safe_label == (
            "GMO_MINIMUM_ALLOWED_SIZE"
        )
        assert profile.approved_execution_type_safe_label == "MARKET"
        assert profile.safe_labels_ready is True
        assert APPROVED_ENTRY_SYMBOL_SAFE_LABEL == "USD_JPY"
        assert APPROVED_ENTRY_SIZE_PROFILE_SAFE_LABEL == "GMO_MINIMUM_ALLOWED_SIZE"
        assert APPROVED_ENTRY_EXECUTION_TYPE_SAFE_LABEL == "MARKET"

    def test_internal_raw_value_source_is_missing_and_blocks_actual_gate(
        self,
    ) -> None:
        profile = build_approved_entry_order_profile()
        assert profile.internal_raw_value_source_status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE
        )
        assert profile.internal_raw_value_source_present is False

    def test_configured_internal_source_presence_flows_into_profile(self) -> None:
        class _PresentSource:
            def present_safe_boolean(self) -> bool:
                return True

        profile = build_approved_entry_order_profile(
            internal_value_source=_PresentSource()
        )
        assert profile.internal_raw_value_source_status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED
        )
        assert profile.internal_raw_value_source_present is True
        # Presence never becomes a POST permission.
        assert profile.actual_entry_POST_allowed is False
        assert not profile

    def test_not_configured_profile_is_fail_closed(self) -> None:
        profile = build_approved_entry_order_profile_not_configured()
        assert profile.profile_status is (
            GmoApprovedEntryOrderProfileStatus
            .APPROVED_ENTRY_ORDER_PROFILE_NOT_CONFIGURED
        )
        assert profile.safe_labels_ready is False
        assert profile.internal_raw_value_source_present is False
        assert profile.approved_symbol_safe_label == ""
        assert profile.approved_size_profile_safe_label == ""


class TestNeverAPermission:
    def test_profile_is_not_an_executable_permission(self) -> None:
        for profile in (
            build_approved_entry_order_profile(),
            build_approved_entry_order_profile_not_configured(),
        ):
            assert profile.actual_entry_POST_allowed is False
            assert profile.actual_post_permission_implied is False
            assert profile.entry_only is True
            assert profile.settlement_allowed is False
            assert profile.close_allowed is False
            assert profile.generic_allowed is False
            assert profile.retry_allowed is False
            assert profile.repost_allowed is False
            assert profile.second_post_allowed is False
            assert profile.raw_value_exposed is False
            assert profile.credentials_exposed is False
            assert not profile  # __bool__ misuse blocked

    def test_profile_source_safe_label_present_when_ready(self) -> None:
        profile = build_approved_entry_order_profile()
        assert profile.profile_source_safe_label == (
            "REPO_APPROVED_ENTRY_ORDER_PROFILE_MODULE_SAFE_LABELS_ONLY"
        )


class TestNoRawValueSurface:
    def test_profile_type_has_no_numeric_or_raw_value_field(self) -> None:
        for field in fields(ApprovedEntryOrderProfile):
            assert field.type not in ("int", "float")
            for token in ("price", "pnl", "profit", "loss", "_id"):
                assert token not in field.name
        names = {field.name for field in fields(ApprovedEntryOrderProfile)}
        assert "size" not in names  # only the safe-label field exists
        assert "approved_size_profile_safe_label" in names

    def test_profile_repr_contains_no_numeric_size(self) -> None:
        rendered = repr(build_approved_entry_order_profile())
        assert "GMO_MINIMUM_ALLOWED_SIZE" in rendered  # safe label only
        assert not any(char.isdigit() for char in rendered)


class TestSourceScan:
    def test_module_has_no_settlement_close_or_generic_route(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "closeOrder" not in text
        assert "settlePosition" not in text
        assert "live_order_once" not in text
        assert "app.live_verification" not in text

    def test_module_does_not_read_env_or_network_client(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "os.environ" not in text
        assert "getenv" not in text
        assert "load_dotenv" not in text
        assert "httpx" not in text
        assert "urllib" not in text

    def test_module_has_no_allow_literals_or_raw_numeric_size(self) -> None:
        squeezed = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
        assert "actual_entry_POST_allowed=True" not in squeezed
        assert "actual_settlement_POST_allowed=True" not in squeezed
        assert "allow_real_broker_post=True" not in squeezed
        assert "allow_live_http_post=True" not in squeezed
        assert "retry_allowed=True" not in squeezed
        assert "repost_allowed=True" not in squeezed
        assert "second_post_allowed=True" not in squeezed
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "raw_response" not in text
        # No literal digits anywhere: the module cannot embed a raw numeric
        # size, price, or P/L value.
        assert not any(char.isdigit() for char in text)
