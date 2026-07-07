"""Official settlement preflight (no-POST, fail-closed).

This module assembles the no-POST preflight for a FUTURE actual official
settlement step. It never performs a POST, never reads the network or the
process environment, and never exposes a raw value.

Hard rules enforced by construction:

- Only the dedicated official size-based settlement route
  (``POST /private/v1/closeOrder`` via
  ``app.private_api.order_builders``) is reviewable here. A generic
  opposite entry order used as a close has no surface in this module.
- Position-specific settlement (raw position ID handling) stays blocked:
  ``position_specific_identifier_safe_handling_ready`` is false
  project-wide, and this module carries that as a fixed blocked label.
- The settlement side is derived MECHANICALLY from the prior entry signal
  safe label (ENTRY_BUY -> SETTLEMENT_SELL, ENTRY_SELL -> SETTLEMENT_BUY).
  The AI never decides, infers, or defaults a settlement direction; HOLD
  and unknown labels are never derivable.
- The settlement size comes only from the operator-managed sealed local
  value file channel (same file as the approved entry internal value
  source). The sealed holder never returns, prints, or logs its values;
  validation errors never echo them. The single internal consumer hands
  the values straight to the audited settlement-only plan builder for the
  injected actual sender of a FUTURE step.
- Never a POST permission: ``actual_settlement_POST_allowed`` is hardcoded
  false everywhere, every result is never truthy, and the current-turn
  actual settlement confirmation has no field here so it cannot be banked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.private_api.order_builders import (
    GMO_FX_ENTRY_ORDER_PATH,
    GMO_FX_OFFICIAL_SETTLEMENT_METHOD,
    GMO_FX_OFFICIAL_SETTLEMENT_PATH,
    REQUEST_KIND_ENTRY,
    REQUEST_KIND_OFFICIAL_SETTLEMENT,
    GmoFxPrivateRequestPlan,
    build_gmo_fx_official_settlement_request_plan,
)
from app.services.gmo_live_approved_entry_internal_value_source import (
    OPERATOR_LOCAL_VALUE_FILE_NAME,
)
from app.services.gmo_live_approved_entry_order_profile import (
    APPROVED_ENTRY_EXECUTION_TYPE_SAFE_LABEL,
    APPROVED_ENTRY_SIZE_PROFILE_SAFE_LABEL,
    APPROVED_ENTRY_SYMBOL_SAFE_LABEL,
)

_SANITIZED_SOURCE_REPR = "SealedOfficialSettlementValueSource(<sanitized>)"

OFFICIAL_SETTLEMENT_ROUTE_SAFE_LABEL = "OFFICIAL_SIZE_BASED_CLOSE_ORDER"
GENERIC_CLOSE_FORBIDDEN_STATUS = "GENERIC_CLOSE_FORBIDDEN"
POSITION_SPECIFIC_PATH_BLOCKED_STATUS = (
    "POSITION_SPECIFIC_PATH_BLOCKED_SAFE_IDENTIFIER_HANDLING_NOT_READY"
)

# The operator supplies settlement values through the same gitignored local
# file channel as the approved entry internal value source.
OPERATOR_LOCAL_SETTLEMENT_VALUE_FILE_NAME = OPERATOR_LOCAL_VALUE_FILE_NAME
_LOCAL_FILE_REQUIRED_KEYS = frozenset({"symbol", "size"})


class GmoOfficialSettlementPreflightError(RuntimeError):
    """Raised for fail-closed violations. Never echoes a supplied value."""


class GmoOfficialSettlementSideSafeLabel(str, Enum):
    SETTLEMENT_SELL = "SETTLEMENT_SELL"
    SETTLEMENT_BUY = "SETTLEMENT_BUY"


# HOLD and unknown labels are intentionally absent: they are never derivable
# into a settlement side, and the AI never supplies a missing direction.
PRIOR_ENTRY_SIGNAL_TO_SETTLEMENT_SIDE: dict[
    str, GmoOfficialSettlementSideSafeLabel
] = {
    "ENTRY_BUY": GmoOfficialSettlementSideSafeLabel.SETTLEMENT_SELL,
    "ENTRY_SELL": GmoOfficialSettlementSideSafeLabel.SETTLEMENT_BUY,
}

_SETTLEMENT_SIDE_TO_BUILDER_SIDE: dict[GmoOfficialSettlementSideSafeLabel, str] = {
    GmoOfficialSettlementSideSafeLabel.SETTLEMENT_SELL: "SELL",
    GmoOfficialSettlementSideSafeLabel.SETTLEMENT_BUY: "BUY",
}


class GmoSettlementSideProvenanceStatus(str, Enum):
    SETTLEMENT_SIDE_PROVENANCE_READY_MECHANICAL = (
        "SETTLEMENT_SIDE_PROVENANCE_READY_MECHANICAL"
    )
    SETTLEMENT_SIDE_PROVENANCE_BLOCKED_NOT_DERIVABLE = (
        "SETTLEMENT_SIDE_PROVENANCE_BLOCKED_NOT_DERIVABLE"
    )


@dataclass(frozen=True)
class OfficialSettlementSideProvenance:
    """Mechanical side derivation record. Safe labels only, never truthy."""

    status: GmoSettlementSideProvenanceStatus
    prior_entry_signal_safe_label: str
    settlement_side_safe_label: str

    def __bool__(self) -> bool:
        return False

    @property
    def ready(self) -> bool:
        return self.status is (
            GmoSettlementSideProvenanceStatus
            .SETTLEMENT_SIDE_PROVENANCE_READY_MECHANICAL
        )


def derive_official_settlement_side_from_prior_entry(
    prior_entry_signal_safe_label: str,
) -> OfficialSettlementSideProvenance:
    """Map the prior entry signal to the settlement side mechanically."""

    side = PRIOR_ENTRY_SIGNAL_TO_SETTLEMENT_SIDE.get(prior_entry_signal_safe_label)
    if side is None:
        return OfficialSettlementSideProvenance(
            status=(
                GmoSettlementSideProvenanceStatus
                .SETTLEMENT_SIDE_PROVENANCE_BLOCKED_NOT_DERIVABLE
            ),
            prior_entry_signal_safe_label=prior_entry_signal_safe_label,
            settlement_side_safe_label="",
        )
    return OfficialSettlementSideProvenance(
        status=(
            GmoSettlementSideProvenanceStatus
            .SETTLEMENT_SIDE_PROVENANCE_READY_MECHANICAL
        ),
        prior_entry_signal_safe_label=prior_entry_signal_safe_label,
        settlement_side_safe_label=side.value,
    )


class GmoSettlementSizeSourceStatus(str, Enum):
    SETTLEMENT_SIZE_SOURCE_PRESENT_NOT_EXPOSED = (
        "SETTLEMENT_SIZE_SOURCE_PRESENT_NOT_EXPOSED"
    )
    SETTLEMENT_SIZE_SOURCE_MISSING_BLOCK_ACTUAL_SETTLEMENT_GATE = (
        "SETTLEMENT_SIZE_SOURCE_MISSING_BLOCK_ACTUAL_SETTLEMENT_GATE"
    )
    SETTLEMENT_SIZE_SOURCE_UNSAFE = "SETTLEMENT_SIZE_SOURCE_UNSAFE"


def validate_official_settlement_only_request_plan(
    plan: GmoFxPrivateRequestPlan,
) -> None:
    """Raise unless the plan is exactly the dedicated official settlement plan.

    The raised error never contains the plan body or any value from it.
    """

    if plan.request_kind != REQUEST_KIND_OFFICIAL_SETTLEMENT:
        raise GmoOfficialSettlementPreflightError(
            "request plan is not the dedicated official settlement plan"
        )
    if plan.method != GMO_FX_OFFICIAL_SETTLEMENT_METHOD:
        raise GmoOfficialSettlementPreflightError(
            "request plan method is not the official settlement method"
        )
    if plan.path != GMO_FX_OFFICIAL_SETTLEMENT_PATH:
        raise GmoOfficialSettlementPreflightError(
            "request plan path is not the official settlement path"
        )
    if plan.path == GMO_FX_ENTRY_ORDER_PATH:
        raise GmoOfficialSettlementPreflightError(
            "entry order path can never be used as a settlement route"
        )


def _validate_operator_supplied_size_shape(size_value: str) -> None:
    """Validate the size shape without ever echoing the value."""

    if not isinstance(size_value, str) or not size_value:
        raise GmoOfficialSettlementPreflightError(
            "operator-supplied size value must be a non-empty string"
        )
    try:
        numeric = float(size_value)
    except ValueError as error:
        raise GmoOfficialSettlementPreflightError(
            "operator-supplied size value must be a numeric string"
        ) from error
    if numeric <= 0:
        raise GmoOfficialSettlementPreflightError(
            "operator-supplied size value must be positive"
        )


class SealedOfficialSettlementValueSource:
    """Sealed operator-supplied settlement value holder. Never exposes values.

    Mirrors ``SealedApprovedEntryInternalValueSource`` but its single internal
    consumer builds only the dedicated OFFICIAL_SETTLEMENT plan; it has no
    entry, generic, or position-specific surface.
    """

    __slots__ = ("_symbol_value", "_size_value", "_configured")

    def __init__(
        self,
        *,
        operator_supplied_symbol_value: str | None = None,
        operator_supplied_size_value: str | None = None,
    ) -> None:
        supplied = (
            operator_supplied_symbol_value is not None
            or operator_supplied_size_value is not None
        )
        if not supplied:
            self._symbol_value = None
            self._size_value = None
            self._configured = False
            return
        if (
            operator_supplied_symbol_value is None
            or operator_supplied_size_value is None
        ):
            raise GmoOfficialSettlementPreflightError(
                "operator must supply both symbol and size values together"
            )
        if operator_supplied_symbol_value != APPROVED_ENTRY_SYMBOL_SAFE_LABEL:
            raise GmoOfficialSettlementPreflightError(
                "operator-supplied symbol does not match the approved symbol "
                "safe label"
            )
        _validate_operator_supplied_size_shape(operator_supplied_size_value)
        self._symbol_value = operator_supplied_symbol_value
        self._size_value = operator_supplied_size_value
        self._configured = True

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return _SANITIZED_SOURCE_REPR

    def __str__(self) -> str:
        return _SANITIZED_SOURCE_REPR

    def present_safe_boolean(self) -> bool:
        """Presence only. Never a value."""

        return self._configured

    @property
    def status(self) -> GmoSettlementSizeSourceStatus:
        if self._configured:
            return (
                GmoSettlementSizeSourceStatus
                .SETTLEMENT_SIZE_SOURCE_PRESENT_NOT_EXPOSED
            )
        return (
            GmoSettlementSizeSourceStatus
            .SETTLEMENT_SIZE_SOURCE_MISSING_BLOCK_ACTUAL_SETTLEMENT_GATE
        )

    def build_bound_official_settlement_request_plan_internal(
        self,
        *,
        side_provenance: OfficialSettlementSideProvenance,
    ) -> GmoFxPrivateRequestPlan:
        """Build the internal settlement-only plan for a FUTURE injected sender.

        Internal use only: the returned plan is handed to the actual
        settlement sender of a separate, explicitly gated step and is never
        reported, previewed, or logged. Raises fail-closed when the source is
        not configured or the side provenance is not ready; errors never
        contain the sealed values.
        """

        if (
            not self._configured
            or self._symbol_value is None
            or self._size_value is None
        ):
            raise GmoOfficialSettlementPreflightError(
                "settlement value source is not configured: the actual "
                "settlement gate must block"
            )
        if not side_provenance.ready:
            raise GmoOfficialSettlementPreflightError(
                "settlement side provenance is not ready: the side is never "
                "inferred by the AI"
            )
        side_label = GmoOfficialSettlementSideSafeLabel(
            side_provenance.settlement_side_safe_label
        )
        plan = build_gmo_fx_official_settlement_request_plan(
            symbol=self._symbol_value,
            side=_SETTLEMENT_SIDE_TO_BUILDER_SIDE[side_label],
            size=self._size_value,
        )
        validate_official_settlement_only_request_plan(plan)
        return plan


def build_sealed_official_settlement_value_source_not_configured() -> (
    SealedOfficialSettlementValueSource
):
    """Default fail-closed source: not configured, blocks the settlement gate."""

    return SealedOfficialSettlementValueSource()


def load_sealed_official_settlement_value_source_from_operator_local_file(
    file_path: str | Path,
) -> SealedOfficialSettlementValueSource:
    """Load the operator-managed local value file and seal its values.

    Same fail-closed, non-echoing contract as the approved entry loader: a
    missing file returns the NOT CONFIGURED source; malformed content raises
    a sanitized error that never echoes the file contents; parsed values go
    straight into the sealed holder and are never returned, printed, or
    logged by this function.
    """

    path = Path(file_path)
    if not path.exists():
        return SealedOfficialSettlementValueSource()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GmoOfficialSettlementPreflightError(
            "operator local value file could not be read or parsed; its "
            "contents are never echoed"
        ) from error
    if not isinstance(payload, dict) or set(payload) != _LOCAL_FILE_REQUIRED_KEYS:
        raise GmoOfficialSettlementPreflightError(
            "operator local value file must be a JSON object with exactly "
            "the keys symbol and size"
        )
    symbol_value = payload["symbol"]
    size_value = payload["size"]
    if not isinstance(symbol_value, str) or not isinstance(size_value, str):
        raise GmoOfficialSettlementPreflightError(
            "operator local value file values must be JSON strings"
        )
    return SealedOfficialSettlementValueSource(
        operator_supplied_symbol_value=symbol_value,
        operator_supplied_size_value=size_value,
    )


class GmoOfficialSettlementRouteStatus(str, Enum):
    OFFICIAL_SETTLEMENT_ROUTE_READY_DEDICATED_CLOSE_ORDER = (
        "OFFICIAL_SETTLEMENT_ROUTE_READY_DEDICATED_CLOSE_ORDER"
    )
    OFFICIAL_SETTLEMENT_ROUTE_BLOCKED = "OFFICIAL_SETTLEMENT_ROUTE_BLOCKED"


def review_official_settlement_route() -> GmoOfficialSettlementRouteStatus:
    """Structurally review the dedicated settlement route (no network).

    Ready only when the audited builder targets the dedicated closeOrder
    path with a settlement-specific request kind distinct from entry.
    """

    dedicated = (
        GMO_FX_OFFICIAL_SETTLEMENT_METHOD == "POST"
        and GMO_FX_OFFICIAL_SETTLEMENT_PATH == "/private/v1/closeOrder"
        and GMO_FX_OFFICIAL_SETTLEMENT_PATH != GMO_FX_ENTRY_ORDER_PATH
        and REQUEST_KIND_OFFICIAL_SETTLEMENT != REQUEST_KIND_ENTRY
    )
    if dedicated:
        return (
            GmoOfficialSettlementRouteStatus
            .OFFICIAL_SETTLEMENT_ROUTE_READY_DEDICATED_CLOSE_ORDER
        )
    return GmoOfficialSettlementRouteStatus.OFFICIAL_SETTLEMENT_ROUTE_BLOCKED


class GmoOfficialSettlementPreflightStatus(str, Enum):
    OFFICIAL_SETTLEMENT_PREFLIGHT_READY_NO_POST = (
        "OFFICIAL_SETTLEMENT_PREFLIGHT_READY_NO_POST"
    )
    OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST = (
        "OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST"
    )


@dataclass(frozen=True)
class GmoOfficialSettlementPreflightInput:
    """Default-deny input for THIS preflight turn only. Nothing is banked."""

    one_position_open_count_one_confirmed: bool = False
    active_pending_clear_count_zero_confirmed: bool = False
    runtime_read_confirmed_safe: bool = False
    credential_presence_safe_boolean_confirmed: bool = False

    # violations (any true blocks hard)
    generic_close_requested: bool = False
    position_specific_settlement_requested: bool = False
    entry_post_requested: bool = False
    retry_requested: bool = False
    repost_requested: bool = False
    second_post_requested: bool = False
    raw_response_exposure_requested: bool = False
    ids_exposure_requested: bool = False
    price_size_pnl_exposure_requested: bool = False
    credential_exposure_requested: bool = False


_VIOLATION_REASONS: tuple[tuple[str, str], ...] = (
    ("generic_close_requested", "GENERIC_CLOSE_REQUESTED_BLOCKED"),
    (
        "position_specific_settlement_requested",
        "POSITION_SPECIFIC_SETTLEMENT_REQUESTED_BLOCKED",
    ),
    ("entry_post_requested", "ENTRY_POST_IN_SETTLEMENT_STEP_BLOCKED"),
    ("retry_requested", "RETRY_REQUESTED_BLOCKED"),
    ("repost_requested", "REPOST_REQUESTED_BLOCKED"),
    ("second_post_requested", "SECOND_POST_REQUESTED_BLOCKED"),
    ("raw_response_exposure_requested", "RAW_RESPONSE_EXPOSURE_BLOCKED"),
    ("ids_exposure_requested", "IDS_EXPOSURE_BLOCKED"),
    ("price_size_pnl_exposure_requested", "PRICE_SIZE_PNL_EXPOSURE_BLOCKED"),
    ("credential_exposure_requested", "CREDENTIAL_EXPOSURE_BLOCKED"),
)

_RUNTIME_REASONS: tuple[tuple[str, str], ...] = (
    (
        "one_position_open_count_one_confirmed",
        "ONE_POSITION_OPEN_COUNT_ONE_NOT_CONFIRMED",
    ),
    (
        "active_pending_clear_count_zero_confirmed",
        "ACTIVE_PENDING_CLEAR_NOT_CONFIRMED",
    ),
    ("runtime_read_confirmed_safe", "RUNTIME_READ_NOT_CONFIRMED_SAFE"),
    (
        "credential_presence_safe_boolean_confirmed",
        "CREDENTIAL_PRESENCE_NOT_CONFIRMED",
    ),
)


@dataclass(frozen=True)
class GmoOfficialSettlementPreflightPackage:
    """Safe-label-only preflight package. Never truthy, never a permission."""

    status: GmoOfficialSettlementPreflightStatus
    blocked_reasons: tuple[str, ...]
    official_settlement_route_status: str
    settlement_side_provenance_status: str
    settlement_size_source_status: str
    one_position_only_status: str
    active_pending_clear_status: str
    generic_close_forbidden_status: str = GENERIC_CLOSE_FORBIDDEN_STATUS
    position_specific_path_status: str = POSITION_SPECIFIC_PATH_BLOCKED_STATUS
    settlement_post_max_count: int = 1
    actual_settlement_POST_allowed: bool = False
    actual_entry_POST_allowed: bool = False
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_post_allowed: bool = False
    generic_close_allowed: bool = False
    position_specific_settlement_allowed: bool = False
    current_turn_settlement_confirmation_bankable: bool = False

    def __bool__(self) -> bool:
        return False


def build_gmo_official_settlement_preflight_package(
    *,
    preflight_input: GmoOfficialSettlementPreflightInput,
    route_status: GmoOfficialSettlementRouteStatus,
    side_provenance: OfficialSettlementSideProvenance,
    size_source_status: GmoSettlementSizeSourceStatus,
) -> GmoOfficialSettlementPreflightPackage:
    """Classify settlement preflight readiness; never grant a POST permission."""

    blockers: list[str] = []
    for field_name, reason in _VIOLATION_REASONS:
        if getattr(preflight_input, field_name):
            blockers.append(reason)
    for field_name, reason in _RUNTIME_REASONS:
        if not getattr(preflight_input, field_name):
            blockers.append(reason)
    if route_status is not (
        GmoOfficialSettlementRouteStatus
        .OFFICIAL_SETTLEMENT_ROUTE_READY_DEDICATED_CLOSE_ORDER
    ):
        blockers.append("OFFICIAL_SETTLEMENT_ROUTE_NOT_READY")
    if not side_provenance.ready:
        blockers.append("SETTLEMENT_SIDE_PROVENANCE_NOT_READY")
    if size_source_status is not (
        GmoSettlementSizeSourceStatus.SETTLEMENT_SIZE_SOURCE_PRESENT_NOT_EXPOSED
    ):
        blockers.append(size_source_status.value)

    ready = not blockers
    return GmoOfficialSettlementPreflightPackage(
        status=(
            GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_READY_NO_POST
            if ready
            else GmoOfficialSettlementPreflightStatus
            .OFFICIAL_SETTLEMENT_PREFLIGHT_BLOCKED_NO_POST
        ),
        blocked_reasons=tuple(blockers),
        official_settlement_route_status=route_status.value,
        settlement_side_provenance_status=side_provenance.status.value,
        settlement_size_source_status=size_source_status.value,
        one_position_only_status=(
            "ONE_POSITION_OPEN_COUNT_ONE_CONFIRMED"
            if preflight_input.one_position_open_count_one_confirmed
            else "ONE_POSITION_OPEN_COUNT_ONE_NOT_CONFIRMED"
        ),
        active_pending_clear_status=(
            "ACTIVE_PENDING_CLEAR_CONFIRMED"
            if preflight_input.active_pending_clear_count_zero_confirmed
            else "ACTIVE_PENDING_NOT_CLEAR"
        ),
    )


@dataclass(frozen=True)
class GmoOfficialSettlementSanitizedPreview:
    """Safe preview of the future settlement order. Never raw/ID/value.

    There is structurally no field that can carry a raw numeric size, a
    price, a P/L, an ID, a credential, a signature, or a header value.
    """

    settlement_route_safe_label: str
    settlement_side_safe_label: str
    symbol_safe_label: str
    size_profile_safe_label: str
    execution_type_safe_label: str
    settlement_post_max_count: int = 1
    retry: bool = False
    repost: bool = False
    second_post: bool = False
    entry_post: bool = False
    generic_close: bool = False
    position_specific_settlement: bool = False
    raw_id_value_exposure: bool = False
    credential_value_exposed: bool = False

    def __bool__(self) -> bool:
        return False


def build_official_settlement_sanitized_preview(
    *,
    side_provenance: OfficialSettlementSideProvenance,
) -> GmoOfficialSettlementSanitizedPreview:
    """Build the safe preview from mechanical labels only.

    Raises fail-closed when the side provenance is not ready, so a preview
    can never show an AI-invented direction.
    """

    if not side_provenance.ready:
        raise GmoOfficialSettlementPreflightError(
            "sanitized settlement preview requires ready side provenance"
        )
    return GmoOfficialSettlementSanitizedPreview(
        settlement_route_safe_label=OFFICIAL_SETTLEMENT_ROUTE_SAFE_LABEL,
        settlement_side_safe_label=side_provenance.settlement_side_safe_label,
        symbol_safe_label=APPROVED_ENTRY_SYMBOL_SAFE_LABEL,
        size_profile_safe_label=APPROVED_ENTRY_SIZE_PROFILE_SAFE_LABEL,
        execution_type_safe_label=APPROVED_ENTRY_EXECUTION_TYPE_SAFE_LABEL,
    )
