"""Operator-supplied sealed internal value source for the actual entry order.

This module closes the ``INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE``
blocker structurally: it provides the fail-closed, operator-supplied holder
for the internal raw values (symbol / size) an actual entry sender needs,
WITHOUT the repository, the AI, or any report ever containing those values.

Hard rules enforced by construction:

- The repository ships NO raw numeric size. The values are supplied by the
  operator only, at the actual gate turn (or via an operator-managed local
  config passed in by the gate runner). The AI never infers, defaults, or
  displays them.
- The holder is sealed: ``__slots__`` only, sanitized ``__repr__``/``__str__``,
  never truthy, no dict/model dump surface, and no method that returns the
  raw values to a caller. The single internal consumer is
  ``build_bound_entry_request_plan_internal``, which hands the values
  directly to the audited entry-only request plan builder; the resulting
  plan goes only to the injected actual sender and is never reported.
- Entry-only: the holder builds only the dedicated ENTRY request plan (the
  builder validates kind/method/path); it has no settlement, close, or
  generic surface.
- Fail-closed: the default state is NOT CONFIGURED and reports
  ``INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE``. A configured
  holder validates that the operator-supplied symbol equals the approved
  symbol safe label and that the size is a positive numeric string;
  validation errors never echo the supplied values.
- This module is never a POST permission. Presence of values does not allow
  a POST; every other actual-gate requirement (fresh current-turn operator
  input, fresh runtime read, permit, hard guard, activation) still applies.
"""

from __future__ import annotations

from app.private_api.order_builders import GmoFxPrivateRequestPlan
from app.services.gmo_live_approved_entry_order_profile import (
    APPROVED_ENTRY_SYMBOL_SAFE_LABEL,
    GmoApprovedEntryInternalRawValueSourceStatus,
)
from app.services.gmo_live_entry_request_plan_binding import (
    EntryRequestPlanBindingResult,
    build_bound_entry_request_plan,
)

_SANITIZED_REPR = "SealedApprovedEntryInternalValueSource(<sanitized>)"


class GmoApprovedEntryInternalValueSourceError(RuntimeError):
    """Raised for fail-closed violations. Never echoes a supplied value."""


def _validate_operator_supplied_size_shape(size_value: str) -> None:
    """Validate the size shape without ever echoing the value."""

    if not isinstance(size_value, str) or not size_value:
        raise GmoApprovedEntryInternalValueSourceError(
            "operator-supplied size value must be a non-empty string"
        )
    try:
        numeric = float(size_value)
    except ValueError as error:
        raise GmoApprovedEntryInternalValueSourceError(
            "operator-supplied size value must be a numeric string"
        ) from error
    if numeric <= 0:
        raise GmoApprovedEntryInternalValueSourceError(
            "operator-supplied size value must be positive"
        )


class SealedApprovedEntryInternalValueSource:
    """Sealed operator-supplied internal value holder. Never exposes values."""

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
            raise GmoApprovedEntryInternalValueSourceError(
                "operator must supply both symbol and size values together"
            )
        if operator_supplied_symbol_value != APPROVED_ENTRY_SYMBOL_SAFE_LABEL:
            raise GmoApprovedEntryInternalValueSourceError(
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
        return _SANITIZED_REPR

    def __str__(self) -> str:
        return _SANITIZED_REPR

    def present_safe_boolean(self) -> bool:
        """Presence only. Never a value."""

        return self._configured

    @property
    def status(self) -> GmoApprovedEntryInternalRawValueSourceStatus:
        if self._configured:
            return (
                GmoApprovedEntryInternalRawValueSourceStatus
                .INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED
            )
        return (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE
        )

    def build_bound_entry_request_plan_internal(
        self,
        *,
        binding_result: EntryRequestPlanBindingResult,
    ) -> GmoFxPrivateRequestPlan:
        """Build the internal entry-only plan for the injected actual sender.

        Internal use only: the returned plan is handed to the actual sender
        and never reported, previewed, or logged. Raises fail-closed when the
        source is not configured or the binding is not BOUND_SAFE; errors
        never contain the sealed values.
        """

        if (
            not self._configured
            or self._symbol_value is None
            or self._size_value is None
        ):
            raise GmoApprovedEntryInternalValueSourceError(
                "internal value source is not configured: the actual gate "
                "must block (no raw value exists to build a plan from)"
            )
        return build_bound_entry_request_plan(
            binding_result=binding_result,
            approved_symbol=self._symbol_value,
            approved_size=self._size_value,
        )


def build_approved_entry_internal_value_source_not_configured() -> (
    SealedApprovedEntryInternalValueSource
):
    """Default fail-closed source: not configured, blocks the actual gate."""

    return SealedApprovedEntryInternalValueSource()
