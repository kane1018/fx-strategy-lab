"""Pure mocked read-only precheck core for Phase 3C-1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from app.live_verification.errors import LiveVerificationPrecheckError

LIVE_VERIFICATION_MODE = "live_verification"
SUPPORTED_SYMBOL = "USD_JPY"
SUPPORTED_UNITS = 100


class PrecheckFailureReason(str, Enum):
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_UNITS = "unsupported_units"
    UNSUPPORTED_MODE = "unsupported_mode"
    ACCOUNT_ASSETS_FAILED = "account_assets_failed"
    OPEN_POSITIONS_FAILED = "open_positions_failed"
    ACTIVE_ORDERS_FAILED = "active_orders_failed"
    HAS_OPEN_POSITIONS = "has_open_positions"
    HAS_ACTIVE_ORDERS = "has_active_orders"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    HEADERS_SAVED = "headers_saved"
    CREDENTIALS_PRINTED = "credentials_printed"
    RETRY_ATTEMPTED = "retry_attempted"


@dataclass(frozen=True)
class ReadonlyPrecheckResult:
    readonly_precheck_id: str
    verification_run_id: str
    symbol: str
    expected_units: int
    mode: str
    account_assets_ok: bool
    open_positions_ok: bool
    active_orders_ok: bool
    has_open_positions: bool
    has_active_orders: bool
    raw_response_saved: bool
    headers_saved: bool
    credentials_printed: bool
    retry_attempted: bool
    readonly_precheck_passed: bool
    fail_reasons: tuple[PrecheckFailureReason, ...]

    def __post_init__(self) -> None:
        _require_non_empty("readonly_precheck_id", self.readonly_precheck_id)
        _require_non_empty("verification_run_id", self.verification_run_id)
        if self.readonly_precheck_id != make_readonly_precheck_id(
            verification_run_id=self.verification_run_id,
            symbol=self.symbol,
            expected_units=self.expected_units,
            mode=self.mode,
        ):
            raise LiveVerificationPrecheckError("readonly_precheck_id mismatch")
        bool_fields = (
            self.account_assets_ok,
            self.open_positions_ok,
            self.active_orders_ok,
            self.has_open_positions,
            self.has_active_orders,
            self.raw_response_saved,
            self.headers_saved,
            self.credentials_printed,
            self.retry_attempted,
            self.readonly_precheck_passed,
        )
        if any(type(value) is not bool for value in bool_fields):
            raise LiveVerificationPrecheckError("precheck flags must be bool")
        if any(not isinstance(reason, PrecheckFailureReason) for reason in self.fail_reasons):
            raise LiveVerificationPrecheckError("fail_reasons must contain precheck reasons")
        if self.readonly_precheck_passed and self.fail_reasons:
            raise LiveVerificationPrecheckError("passed precheck cannot contain fail reasons")
        if not self.readonly_precheck_passed and not self.fail_reasons:
            raise LiveVerificationPrecheckError("failed precheck requires fail reasons")


def evaluate_readonly_precheck(
    *,
    symbol: str,
    verification_run_id: str,
    expected_units: int,
    account_assets_ok: bool,
    open_positions_ok: bool,
    active_orders_ok: bool,
    has_open_positions: bool,
    has_active_orders: bool,
    raw_response_saved: bool,
    headers_saved: bool,
    credentials_printed: bool,
    mode: str = LIVE_VERIFICATION_MODE,
    retry_attempted: bool = False,
) -> ReadonlyPrecheckResult:
    """Evaluate sanitized mocked read-only precheck flags without any external I/O."""
    _require_non_empty("verification_run_id", verification_run_id)
    bool_fields = {
        "account_assets_ok": account_assets_ok,
        "open_positions_ok": open_positions_ok,
        "active_orders_ok": active_orders_ok,
        "has_open_positions": has_open_positions,
        "has_active_orders": has_active_orders,
        "raw_response_saved": raw_response_saved,
        "headers_saved": headers_saved,
        "credentials_printed": credentials_printed,
        "retry_attempted": retry_attempted,
    }
    for name, value in bool_fields.items():
        if type(value) is not bool:
            raise LiveVerificationPrecheckError(f"{name} must be bool")

    fail_reasons: list[PrecheckFailureReason] = []
    if symbol != SUPPORTED_SYMBOL:
        fail_reasons.append(PrecheckFailureReason.UNSUPPORTED_SYMBOL)
    if expected_units != SUPPORTED_UNITS:
        fail_reasons.append(PrecheckFailureReason.UNSUPPORTED_UNITS)
    if mode != LIVE_VERIFICATION_MODE:
        fail_reasons.append(PrecheckFailureReason.UNSUPPORTED_MODE)
    if not account_assets_ok:
        fail_reasons.append(PrecheckFailureReason.ACCOUNT_ASSETS_FAILED)
    if not open_positions_ok:
        fail_reasons.append(PrecheckFailureReason.OPEN_POSITIONS_FAILED)
    if not active_orders_ok:
        fail_reasons.append(PrecheckFailureReason.ACTIVE_ORDERS_FAILED)
    if has_open_positions:
        fail_reasons.append(PrecheckFailureReason.HAS_OPEN_POSITIONS)
    if has_active_orders:
        fail_reasons.append(PrecheckFailureReason.HAS_ACTIVE_ORDERS)
    if raw_response_saved:
        fail_reasons.append(PrecheckFailureReason.RAW_RESPONSE_SAVED)
    if headers_saved:
        fail_reasons.append(PrecheckFailureReason.HEADERS_SAVED)
    if credentials_printed:
        fail_reasons.append(PrecheckFailureReason.CREDENTIALS_PRINTED)
    if retry_attempted:
        fail_reasons.append(PrecheckFailureReason.RETRY_ATTEMPTED)

    return ReadonlyPrecheckResult(
        readonly_precheck_id=make_readonly_precheck_id(
            verification_run_id=verification_run_id,
            symbol=symbol,
            expected_units=expected_units,
            mode=mode,
        ),
        verification_run_id=verification_run_id,
        symbol=symbol,
        expected_units=expected_units,
        mode=mode,
        account_assets_ok=account_assets_ok,
        open_positions_ok=open_positions_ok,
        active_orders_ok=active_orders_ok,
        has_open_positions=has_open_positions,
        has_active_orders=has_active_orders,
        raw_response_saved=raw_response_saved,
        headers_saved=headers_saved,
        credentials_printed=credentials_printed,
        retry_attempted=retry_attempted,
        readonly_precheck_passed=not fail_reasons,
        fail_reasons=tuple(fail_reasons),
    )


def make_readonly_precheck_id(
    *,
    verification_run_id: str,
    symbol: str,
    expected_units: int,
    mode: str,
) -> str:
    _require_non_empty("verification_run_id", verification_run_id)
    digest = _short_hash({
        "expected_units": expected_units,
        "mode": mode,
        "symbol": symbol,
        "verification_run_id": verification_run_id,
    })
    return f"precheck_{verification_run_id}_{digest}"


def _short_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _require_non_empty(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise LiveVerificationPrecheckError(f"{field_name} is required")
