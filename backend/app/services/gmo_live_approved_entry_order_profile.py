"""Approved entry order profile (safe labels only, no-POST, fail-closed).

This module is the repo-internal source for the operator-approved actual
entry order profile, expressed EXCLUSIVELY as safe labels:

- approved_symbol_safe_label:         USD_JPY
- approved_size_profile_safe_label:   GMO_MINIMUM_ALLOWED_SIZE
- approved_execution_type_safe_label: MARKET

Hard rules enforced by construction:

- The profile is a safe-label source, never an actual POST permission.
  ``actual_entry_POST_allowed`` is hardcoded false and ``__bool__`` is always
  false, so the profile cannot become an allow-bridge.
- There is structurally no field that can carry a raw numeric size, a price,
  a P/L, an ID, a credential, a signature, or a header value. The size is
  represented ONLY by the ``GMO_MINIMUM_ALLOWED_SIZE`` safe label.
- The safe-label profile and the internal raw value source are separate
  concerns. The internal raw numeric values an actual sender would need are
  NOT present in this repository yet, and the AI must never infer them, so
  ``internal_raw_value_source_status`` reports
  ``INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE`` and every actual
  gate must block on it until a reviewed internal value source exists.
- The profile is entry-only: settlement / close / generic / retry / repost /
  second-POST are all hardcoded false.
- An actual gate must re-read this profile fresh in its own turn; the
  profile never substitutes the operator's current-turn entry input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

APPROVED_ENTRY_SYMBOL_SAFE_LABEL = "USD_JPY"
APPROVED_ENTRY_SIZE_PROFILE_SAFE_LABEL = "GMO_MINIMUM_ALLOWED_SIZE"
APPROVED_ENTRY_EXECUTION_TYPE_SAFE_LABEL = "MARKET"
APPROVED_ENTRY_PROFILE_SOURCE_SAFE_LABEL = (
    "REPO_APPROVED_ENTRY_ORDER_PROFILE_MODULE_SAFE_LABELS_ONLY"
)


class GmoApprovedEntryOrderProfileStatus(str, Enum):
    APPROVED_ENTRY_ORDER_PROFILE_SAFE_LABELS_READY = (
        "APPROVED_ENTRY_ORDER_PROFILE_SAFE_LABELS_READY"
    )
    APPROVED_ENTRY_ORDER_PROFILE_NOT_CONFIGURED = (
        "APPROVED_ENTRY_ORDER_PROFILE_NOT_CONFIGURED"
    )


class GmoApprovedEntryInternalRawValueSourceStatus(str, Enum):
    """Status of the internal raw value source an actual sender would need.

    The safe-label profile never carries raw values; a real send additionally
    needs a reviewed internal source for the actual numeric values. While
    that source is absent, every actual gate blocks
    (``APPROVED_SIZE_RUNTIME_VALUE_SOURCE_MISSING``).
    """

    INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED = (
        "INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED"
    )
    INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE = (
        "INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE"
    )
    INTERNAL_RAW_VALUE_SOURCE_UNSAFE = "INTERNAL_RAW_VALUE_SOURCE_UNSAFE"
    INTERNAL_RAW_VALUE_SOURCE_REVIEW_INCOMPLETE = (
        "INTERNAL_RAW_VALUE_SOURCE_REVIEW_INCOMPLETE"
    )


@dataclass(frozen=True)
class ApprovedEntryOrderProfile:
    """Safe-label-only approved entry order profile. Never truthy."""

    profile_status: GmoApprovedEntryOrderProfileStatus
    approved_symbol_safe_label: str
    approved_size_profile_safe_label: str
    approved_execution_type_safe_label: str
    profile_source_safe_label: str
    internal_raw_value_source_status: GmoApprovedEntryInternalRawValueSourceStatus
    entry_only: bool = True
    actual_entry_POST_allowed: bool = False
    actual_post_permission_implied: bool = False
    settlement_allowed: bool = False
    close_allowed: bool = False
    generic_allowed: bool = False
    retry_allowed: bool = False
    repost_allowed: bool = False
    second_post_allowed: bool = False
    raw_value_exposed: bool = False
    credentials_exposed: bool = False

    def __bool__(self) -> bool:
        return False

    @property
    def safe_labels_ready(self) -> bool:
        return self.profile_status is (
            GmoApprovedEntryOrderProfileStatus
            .APPROVED_ENTRY_ORDER_PROFILE_SAFE_LABELS_READY
        )

    @property
    def internal_raw_value_source_present(self) -> bool:
        return self.internal_raw_value_source_status is (
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_PRESENT_NOT_EXPOSED
        )


def build_approved_entry_order_profile() -> ApprovedEntryOrderProfile:
    """Build the current repo-approved safe-label profile.

    The internal raw value source is reported as MISSING because no reviewed
    internal numeric source exists in the repository yet; the actual gate
    must block on this until such a source is added in an explicitly
    reviewed step. This function never invents or embeds a numeric value.
    """

    return ApprovedEntryOrderProfile(
        profile_status=(
            GmoApprovedEntryOrderProfileStatus
            .APPROVED_ENTRY_ORDER_PROFILE_SAFE_LABELS_READY
        ),
        approved_symbol_safe_label=APPROVED_ENTRY_SYMBOL_SAFE_LABEL,
        approved_size_profile_safe_label=APPROVED_ENTRY_SIZE_PROFILE_SAFE_LABEL,
        approved_execution_type_safe_label=(
            APPROVED_ENTRY_EXECUTION_TYPE_SAFE_LABEL
        ),
        profile_source_safe_label=APPROVED_ENTRY_PROFILE_SOURCE_SAFE_LABEL,
        internal_raw_value_source_status=(
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_MISSING_BLOCK_ACTUAL_GATE
        ),
    )


def build_approved_entry_order_profile_not_configured() -> ApprovedEntryOrderProfile:
    """Default fail-closed profile used when no approved source is wired."""

    return ApprovedEntryOrderProfile(
        profile_status=(
            GmoApprovedEntryOrderProfileStatus
            .APPROVED_ENTRY_ORDER_PROFILE_NOT_CONFIGURED
        ),
        approved_symbol_safe_label="",
        approved_size_profile_safe_label="",
        approved_execution_type_safe_label="",
        profile_source_safe_label="",
        internal_raw_value_source_status=(
            GmoApprovedEntryInternalRawValueSourceStatus
            .INTERNAL_RAW_VALUE_SOURCE_REVIEW_INCOMPLETE
        ),
    )
