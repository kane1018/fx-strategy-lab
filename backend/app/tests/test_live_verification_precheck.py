from __future__ import annotations

import pytest

from app.live_verification.errors import LiveVerificationPrecheckError
from app.live_verification.precheck import (
    PrecheckFailureReason,
    evaluate_readonly_precheck,
)


def _valid_kwargs() -> dict[str, object]:
    return {
        "symbol": "USD_JPY",
        "verification_run_id": "run_1",
        "expected_units": 100,
        "account_assets_ok": True,
        "open_positions_ok": True,
        "active_orders_ok": True,
        "has_open_positions": False,
        "has_active_orders": False,
        "raw_response_saved": False,
        "headers_saved": False,
        "credentials_printed": False,
    }


def _precheck(**overrides: object):
    kwargs = _valid_kwargs()
    kwargs.update(overrides)
    return evaluate_readonly_precheck(**kwargs)


def test_precheck_passes_only_for_sanitized_readonly_success_flags() -> None:
    result = _precheck()

    assert result.readonly_precheck_id.startswith("precheck_run_1_")
    assert result.verification_run_id == "run_1"
    assert result.symbol == "USD_JPY"
    assert result.expected_units == 100
    assert result.mode == "live_verification"
    assert result.account_assets_ok is True
    assert result.open_positions_ok is True
    assert result.active_orders_ok is True
    assert result.has_open_positions is False
    assert result.has_active_orders is False
    assert result.raw_response_saved is False
    assert result.headers_saved is False
    assert result.credentials_printed is False
    assert result.retry_attempted is False
    assert result.readonly_precheck_passed is True
    assert result.fail_reasons == ()


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("symbol", "EUR_USD", PrecheckFailureReason.UNSUPPORTED_SYMBOL),
        ("expected_units", 101, PrecheckFailureReason.UNSUPPORTED_UNITS),
        ("mode", "shadow", PrecheckFailureReason.UNSUPPORTED_MODE),
        ("account_assets_ok", False, PrecheckFailureReason.ACCOUNT_ASSETS_FAILED),
        ("open_positions_ok", False, PrecheckFailureReason.OPEN_POSITIONS_FAILED),
        ("active_orders_ok", False, PrecheckFailureReason.ACTIVE_ORDERS_FAILED),
        ("has_open_positions", True, PrecheckFailureReason.HAS_OPEN_POSITIONS),
        ("has_active_orders", True, PrecheckFailureReason.HAS_ACTIVE_ORDERS),
        ("raw_response_saved", True, PrecheckFailureReason.RAW_RESPONSE_SAVED),
        ("headers_saved", True, PrecheckFailureReason.HEADERS_SAVED),
        ("credentials_printed", True, PrecheckFailureReason.CREDENTIALS_PRINTED),
        ("retry_attempted", True, PrecheckFailureReason.RETRY_ATTEMPTED),
    ],
)
def test_precheck_fail_closed_reasons(
    field: str,
    value: object,
    reason: PrecheckFailureReason,
) -> None:
    result = _precheck(**{field: value})

    assert result.readonly_precheck_passed is False
    assert reason in result.fail_reasons


def test_precheck_collects_multiple_fail_reasons() -> None:
    result = _precheck(
        account_assets_ok=False,
        has_open_positions=True,
        credentials_printed=True,
    )

    assert result.readonly_precheck_passed is False
    assert result.fail_reasons == (
        PrecheckFailureReason.ACCOUNT_ASSETS_FAILED,
        PrecheckFailureReason.HAS_OPEN_POSITIONS,
        PrecheckFailureReason.CREDENTIALS_PRINTED,
    )


def test_precheck_requires_verification_run_id() -> None:
    with pytest.raises(LiveVerificationPrecheckError):
        _precheck(verification_run_id="")


def test_precheck_requires_bool_flags() -> None:
    with pytest.raises(LiveVerificationPrecheckError):
        _precheck(account_assets_ok="yes")
