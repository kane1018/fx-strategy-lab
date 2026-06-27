"""Step 6C dry-run approval artifact validation.

This module validates a Step 6B approval artifact against a provided command
snapshot. It does not display copyable approval text, issue a gate, call APIs,
read ledgers, or authorize live execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import (
    APPROVAL_GATE_TTL_SECONDS,
)
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
)
from app.live_verification.live_order_real_approval_artifact_generation import (
    REQUIRED_STEP6B_APPROVAL_ACK_TOKENS,
    LiveOrderRealApprovalArtifact,
    LiveOrderRealApprovalArtifactGenerationStatus,
)
from app.live_verification.live_order_real_approval_enablement_dry_run_plan import (
    MARKET_HOURS_MAX_AGE_SECONDS,
    MARKET_HOURS_OPEN_STATE,
    MARKET_HOURS_SOURCE,
    MARKET_HOURS_TIMEZONE,
)
from app.live_verification.live_order_real_approval_gate_enablement_state import (
    FRESH_PREFLIGHT_MAX_AGE_SECONDS,
    FRESH_PREFLIGHT_READY_STATUS,
    FRESH_PREFLIGHT_SOURCE,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

ArtifactStatus = LiveOrderRealApprovalArtifactGenerationStatus

LIVE_ORDER_REAL_APPROVAL_ARTIFACT_VALIDATION_ID_PREFIX = "LORAAV6C-"
STEP6C_REQUEST_SCOPE_LABEL = (
    "approval_artifact_validation_only_no_api_no_post_no_copyable_display"
)
APPROVAL_COMMAND_DISPLAY_MODE_STEP6C = "redacted_only_in_step6c"
DEFAULT_STEP6C_SOURCE_ARTIFACT_MAX_AGE_SECONDS = 300
DEFAULT_STEP6C_VALIDATION_RECEIVED_MAX_AGE_SECONDS = 300

DEFAULT_FUTURE_STEP6D_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6D",
    "Step 6D remains no POST unless separately scoped",
    "Step 6D is for API preflight planning or read-only/preflight boundary only",
    "validated artifact must still be fresh",
    "market-hours snapshot must be rerun",
    "fresh pre-approval preflight must be rerun",
    "no open positions and no active orders must be reconfirmed",
    "allowed_for_live remains false unless a later controlled step explicitly changes it",
    "one-shot POST remains Step 6E or later",
)

DEFAULT_FUTURE_STEP6D_BLOCKERS = (
    "no explicit Step 6D request",
    "validation missing or blocked",
    "validation stale",
    "approval artifact expired",
    "same session cannot be confirmed",
    "market/preflight state stale or unknown",
    "any API/broker/live_order_once called unexpectedly",
    "any secret/raw/real ID exposure risk",
    "any need for retry/loop/add/change/cancel/close",
)


class LiveOrderRealApprovalArtifactValidationStatus(str, Enum):
    APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST = (
        "APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST"
    )
    BLOCKED_STEP6C_VALIDATION_REQUEST = "BLOCKED_STEP6C_VALIDATION_REQUEST"
    BLOCKED_STEP6C_PROVIDED_COMMAND = "BLOCKED_STEP6C_PROVIDED_COMMAND"
    BLOCKED_STEP6C_VALIDATION_SAFETY_SNAPSHOT = (
        "BLOCKED_STEP6C_VALIDATION_SAFETY_SNAPSHOT"
    )
    BLOCKED_STEP6C_SOURCE_ARTIFACT = "BLOCKED_STEP6C_SOURCE_ARTIFACT"
    BLOCKED_STEP6C_UNSAFE_MISMATCH = "BLOCKED_STEP6C_UNSAFE_MISMATCH"


ValidationStatus = LiveOrderRealApprovalArtifactValidationStatus


class LiveOrderRealApprovalArtifactValidationBlockReason(str, Enum):
    MISSING_SOURCE_ARTIFACT = "missing_source_artifact"
    SOURCE_ARTIFACT_NOT_READY = "source_artifact_not_ready"
    SOURCE_ARTIFACT_NOT_ELIGIBLE = "source_artifact_not_eligible"
    SOURCE_ARTIFACT_ALLOWS_LIVE = "source_artifact_allows_live"
    SOURCE_GATE_NOT_ENABLED = "source_gate_not_enabled"
    SOURCE_GATE_ALREADY_ISSUED = "source_gate_already_issued"
    SOURCE_APPROVAL_ID_NOT_GENERATED = "source_approval_id_not_generated"
    SOURCE_APPROVAL_COMMAND_NOT_GENERATED = "source_approval_command_not_generated"
    SOURCE_APPROVAL_COMMAND_COPYABLE = "source_approval_command_copyable"
    SOURCE_APPROVAL_COMMAND_DISPLAYED = "source_approval_command_displayed"
    SOURCE_APPROVAL_COMMAND_PERSISTED = "source_approval_command_persisted"
    SOURCE_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD = (
        "source_approval_command_copied_to_clipboard"
    )
    SOURCE_APPROVAL_COMMAND_EXECUTABLE = "source_approval_command_executable"
    SOURCE_POST_ALLOWED_THIS_STEP = "source_post_allowed_this_step"
    SOURCE_POST_ALREADY_EXECUTED = "source_post_already_executed"
    LIVE_ORDER_ONCE_ALREADY_CALLED = "live_order_once_already_called"
    PRIVATE_API_ALREADY_CALLED = "private_api_already_called"
    BROKER_ALREADY_CALLED = "broker_already_called"
    READ_ONLY_API_ALREADY_CALLED = "read_only_api_already_called"
    PUBLIC_API_ALREADY_CALLED = "public_api_already_called"
    RETRY_ALLOWED = "retry_allowed"
    LOOP_ALLOWED = "loop_allowed"
    ADD_ORDER_ALLOWED = "add_order_allowed"
    CHANGE_ORDER_ALLOWED = "change_order_allowed"
    CANCEL_ORDER_ALLOWED = "cancel_order_allowed"
    CLOSE_ORDER_ALLOWED = "close_order_allowed"
    UNSUPPORTED_SYMBOL = "unsupported_symbol"
    UNSUPPORTED_SIDE = "unsupported_side"
    UNSUPPORTED_SIZE = "unsupported_size"
    UNSUPPORTED_EXECUTION_TYPE = "unsupported_execution_type"
    MISSING_VALIDATION_REQUEST_SNAPSHOT = "missing_validation_request_snapshot"
    EXPLICIT_STEP6C_REQUEST_MISSING = "explicit_step6c_request_missing"
    OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED = (
        "operator_real_money_risk_not_acknowledged"
    )
    OPERATOR_NO_API_NOT_ACKNOWLEDGED = "operator_no_api_not_acknowledged"
    OPERATOR_NO_POST_NOT_ACKNOWLEDGED = "operator_no_post_not_acknowledged"
    OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED = (
        "operator_no_live_order_once_not_acknowledged"
    )
    OPERATOR_VALIDATION_ONLY_NOT_ACKNOWLEDGED = (
        "operator_validation_only_not_acknowledged"
    )
    OPERATOR_NO_COPYABLE_COMMAND_NOT_ACKNOWLEDGED = (
        "operator_no_copyable_command_not_acknowledged"
    )
    OPERATOR_STEP6D_PREFLIGHT_NOT_ACKNOWLEDGED = (
        "operator_step6d_preflight_not_acknowledged"
    )
    OPERATOR_STEP6E_POST_NOT_ACKNOWLEDGED = "operator_step6e_post_not_acknowledged"
    OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED = (
        "operator_unknown_means_stop_not_acknowledged"
    )
    INVALID_REQUEST_SCOPE_LABEL = "invalid_request_scope_label"
    MISSING_PROVIDED_COMMAND = "missing_provided_command"
    PROVIDED_COMMAND_EMPTY = "provided_command_empty"
    PROVIDED_COMMAND_NEWLINE = "provided_command_newline"
    PROVIDED_COMMAND_NOT_ONE_LINE = "provided_command_not_one_line"
    PROVIDED_COMMAND_EXTRA_TOKENS = "provided_command_extra_tokens"
    PROVIDED_COMMAND_MISSING_ACK_TOKENS = "provided_command_missing_ack_tokens"
    APPROVAL_ID_MISMATCH = "approval_id_mismatch"
    SYMBOL_MISMATCH = "symbol_mismatch"
    SIDE_MISMATCH = "side_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    EXECUTION_TYPE_MISMATCH = "execution_type_mismatch"
    TTL_SECONDS_MISMATCH = "ttl_seconds_mismatch"
    SAME_SESSION_MISMATCH = "same_session_mismatch"
    SHA256_MISMATCH = "sha256_mismatch"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    EXACT_MATCH_MISMATCH = "exact_match_mismatch"
    MISSING_VALIDATION_SAFETY_SNAPSHOT = "missing_validation_safety_snapshot"
    SOURCE_ARTIFACT_STALE = "source_artifact_stale"
    VALIDATION_RECEIVED_STALE = "validation_received_stale"
    SAFETY_GATE_NOT_ENABLED = "safety_gate_not_enabled"
    SAFETY_ALLOWS_LIVE = "safety_allows_live"
    SAFETY_GATE_ALREADY_ISSUED = "safety_gate_already_issued"
    SAFETY_APPROVAL_ID_NOT_GENERATED = "safety_approval_id_not_generated"
    SAFETY_APPROVAL_COMMAND_NOT_GENERATED = "safety_approval_command_not_generated"
    SAFETY_APPROVAL_COMMAND_COPYABLE = "safety_approval_command_copyable"
    SAFETY_APPROVAL_COMMAND_DISPLAYED = "safety_approval_command_displayed"
    SAFETY_APPROVAL_COMMAND_PERSISTED = "safety_approval_command_persisted"
    SAFETY_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD = (
        "safety_approval_command_copied_to_clipboard"
    )
    SAFETY_APPROVAL_COMMAND_EXECUTABLE = "safety_approval_command_executable"
    SAFETY_REAL_APPROVAL_ARTIFACTS_AVAILABLE = (
        "safety_real_approval_artifacts_available"
    )
    INVALID_TIMEZONE = "invalid_timezone"
    INVALID_MARKET_HOURS_SOURCE = "invalid_market_hours_source"
    MARKET_SESSION_NOT_OPEN = "market_session_not_open"
    WEEKEND_JST = "weekend_jst"
    MARKET_WINDOW_NOT_ALLOWED = "market_window_not_allowed"
    BROKER_MAINTENANCE_ACTIVE = "broker_maintenance_active"
    HOLIDAY_OR_SPECIAL_CLOSE = "holiday_or_special_close"
    HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN = "holiday_or_special_close_unknown"
    MARKET_HOURS_UNKNOWN = "market_hours_unknown"
    MARKET_HOURS_SNAPSHOT_STALE = "market_hours_snapshot_stale"
    INVALID_FRESH_PREFLIGHT_SOURCE = "invalid_fresh_preflight_source"
    FRESH_PREFLIGHT_NOT_READY = "fresh_preflight_not_ready"
    FRESH_PREFLIGHT_NOT_PASSED = "fresh_preflight_not_passed"
    FRESH_PREFLIGHT_UNKNOWN = "fresh_preflight_unknown"
    FRESH_PREFLIGHT_STALE = "fresh_preflight_stale"
    OPEN_POSITION_EXISTS = "open_position_exists"
    ACTIVE_ORDER_EXISTS = "active_order_exists"
    RESULT_UNKNOWN = "result_unknown"
    RAW_RESPONSE_SAVED = "raw_response_saved"
    RAW_RESPONSE_DISPLAYED = "raw_response_displayed"
    SECRET_SCAN_NOT_PASSED = "secret_scan_not_passed"
    MISSING_FUTURE_STEP6D_HANDOFF_CONDITIONS = (
        "missing_future_step6d_handoff_conditions"
    )
    MISSING_FUTURE_STEP6D_BLOCKERS = "missing_future_step6d_blockers"


BlockReason = LiveOrderRealApprovalArtifactValidationBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactValidationRequestSnapshot:
    request_id: str
    created_at: datetime
    explicit_step6c_user_instruction_received: bool
    operator_understands_real_money_risk: bool
    operator_understands_no_api_in_step6c: bool
    operator_understands_no_post_in_step6c: bool
    operator_understands_no_live_order_once_in_step6c: bool
    operator_understands_validation_only: bool
    operator_understands_approval_command_not_copyable_in_step6c: bool
    operator_understands_step6d_required_for_api_preflight: bool
    operator_understands_step6e_or_later_required_for_post: bool
    operator_understands_unknown_means_stop: bool
    request_scope_label: str

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _ensure_aware(self.created_at)
        _require_non_empty("request_scope_label", self.request_scope_label)
        for field_name in (
            "explicit_step6c_user_instruction_received",
            "operator_understands_real_money_risk",
            "operator_understands_no_api_in_step6c",
            "operator_understands_no_post_in_step6c",
            "operator_understands_no_live_order_once_in_step6c",
            "operator_understands_validation_only",
            "operator_understands_approval_command_not_copyable_in_step6c",
            "operator_understands_step6d_required_for_api_preflight",
            "operator_understands_step6e_or_later_required_for_post",
            "operator_understands_unknown_means_stop",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApprovalProvidedCommandSnapshot:
    provided_command_present: bool
    provided_command: str
    provided_command_sha256: str
    provided_command_fingerprint: str
    provided_command_redacted: str
    provided_command_one_line: bool
    provided_command_contains_newline: bool
    provided_command_has_extra_tokens: bool
    provided_command_missing_ack_tokens: bool
    provided_command_extra_token_names: tuple[str, ...]
    provided_command_missing_ack_token_names: tuple[str, ...]
    provided_command_same_session_label: str
    provided_command_approval_id: str
    provided_command_symbol: str
    provided_command_side: str
    provided_command_size: int
    provided_command_execution_type: str
    provided_command_ttl_seconds: int
    provided_command_created_at: datetime
    provided_command_received_at: datetime

    def __post_init__(self) -> None:
        if type(self.provided_command_present) is not bool:
            raise LiveVerificationValidationError("provided_command_present must be bool")
        for label, value in (
            ("provided_command", self.provided_command),
            ("provided_command_sha256", self.provided_command_sha256),
            ("provided_command_fingerprint", self.provided_command_fingerprint),
            ("provided_command_redacted", self.provided_command_redacted),
            ("provided_command_same_session_label", self.provided_command_same_session_label),
            ("provided_command_approval_id", self.provided_command_approval_id),
            ("provided_command_symbol", self.provided_command_symbol),
            ("provided_command_side", self.provided_command_side),
            ("provided_command_execution_type", self.provided_command_execution_type),
        ):
            if not isinstance(value, str):
                raise LiveVerificationValidationError(f"{label} must be str")
        for field_name in (
            "provided_command_one_line",
            "provided_command_contains_newline",
            "provided_command_has_extra_tokens",
            "provided_command_missing_ack_tokens",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        for field_name in ("provided_command_size", "provided_command_ttl_seconds"):
            if type(getattr(self, field_name)) is not int:
                raise LiveVerificationValidationError(f"{field_name} must be int")
        _ensure_aware(self.provided_command_created_at)
        _ensure_aware(self.provided_command_received_at)


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactValidationSafetySnapshot:
    safety_snapshot_id: str
    created_at: datetime
    source_artifact_age_seconds: float
    source_artifact_max_age_seconds: float
    validation_received_age_seconds: float
    validation_received_max_age_seconds: float
    approval_gate_enabled: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_persisted: bool
    approval_command_copied_to_clipboard: bool
    approval_command_executable: bool
    real_approval_artifacts_available: bool
    timezone: str
    market_hours_source: str
    market_session_state: str
    is_weekend_jst: bool
    market_window_allowed: bool
    broker_maintenance_active: bool
    holiday_or_special_close: bool
    holiday_or_special_close_unknown: bool
    market_hours_unknown: bool
    market_hours_snapshot_age_seconds: float
    market_hours_snapshot_max_age_seconds: float
    fresh_pre_approval_preflight_source: str
    fresh_pre_approval_preflight_status: str
    fresh_pre_approval_preflight_passed: bool
    fresh_pre_approval_preflight_unknown: bool
    fresh_pre_approval_preflight_age_seconds: float
    fresh_pre_approval_preflight_max_age_seconds: float
    open_positions_count: int
    active_orders_count: int
    result_unknown: bool
    raw_response_saved: bool
    raw_response_displayed: bool
    secret_scan_passed: bool

    def __post_init__(self) -> None:
        _require_non_empty("safety_snapshot_id", self.safety_snapshot_id)
        _ensure_aware(self.created_at)
        for label, value in (
            ("timezone", self.timezone),
            ("market_hours_source", self.market_hours_source),
            ("market_session_state", self.market_session_state),
            (
                "fresh_pre_approval_preflight_source",
                self.fresh_pre_approval_preflight_source,
            ),
            (
                "fresh_pre_approval_preflight_status",
                self.fresh_pre_approval_preflight_status,
            ),
        ):
            _require_non_empty(label, value)
        for field_name in (
            "source_artifact_age_seconds",
            "source_artifact_max_age_seconds",
            "validation_received_age_seconds",
            "validation_received_max_age_seconds",
            "market_hours_snapshot_age_seconds",
            "market_hours_snapshot_max_age_seconds",
            "fresh_pre_approval_preflight_age_seconds",
            "fresh_pre_approval_preflight_max_age_seconds",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise LiveVerificationValidationError(f"{field_name} must be number")
        for field_name in (
            "approval_gate_enabled",
            "allowed_for_live",
            "approval_gate_issued",
            "approval_id_generated",
            "approval_command_generated",
            "approval_command_copyable",
            "approval_command_displayed",
            "approval_command_persisted",
            "approval_command_copied_to_clipboard",
            "approval_command_executable",
            "real_approval_artifacts_available",
            "is_weekend_jst",
            "market_window_allowed",
            "broker_maintenance_active",
            "holiday_or_special_close",
            "holiday_or_special_close_unknown",
            "market_hours_unknown",
            "fresh_pre_approval_preflight_passed",
            "fresh_pre_approval_preflight_unknown",
            "result_unknown",
            "raw_response_saved",
            "raw_response_displayed",
            "secret_scan_passed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")
        for field_name in ("open_positions_count", "active_orders_count"):
            if type(getattr(self, field_name)) is not int:
                raise LiveVerificationValidationError(f"{field_name} must be int")


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactValidationCheckResult:
    name: str
    passed: bool
    reason: str
    sanitized_value: str
    expected: str

    def __post_init__(self) -> None:
        _require_non_empty("check name", self.name)
        if type(self.passed) is not bool:
            raise LiveVerificationValidationError("check passed must be bool")
        _require_non_empty("check reason", self.reason)
        _require_non_empty("check sanitized_value", self.sanitized_value)
        _require_non_empty("check expected", self.expected)


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactValidationSection:
    section_id: str
    title: str
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty("section_id", self.section_id)
        _require_non_empty("section title", self.title)
        if not self.lines:
            raise LiveVerificationValidationError("section requires lines")
        for line in self.lines:
            _require_non_empty("section line", line)


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactValidation:
    validation_id: str
    created_at: datetime
    source_artifact_id: str
    source_enablement_state_id: str
    source_plan_id: str
    criteria_id: str
    symbol: str
    side: str
    size: int
    execution_type: str
    source_type: str
    strategy_name: str
    validation_status: LiveOrderRealApprovalArtifactValidationStatus
    validation_ready: bool
    approval_artifact_validated: bool
    eligible_for_step6d_api_preflight_planning: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_issued: bool
    approval_id_generated: bool
    approval_id_validated: bool
    approval_command_generated: bool
    approval_command_validated: bool
    approval_command_exact_match_validated: bool
    approval_command_sha256_validated: bool
    approval_command_fingerprint_validated: bool
    approval_command_ttl_validated: bool
    approval_command_same_session_validated: bool
    approval_command_one_line_validated: bool
    approval_command_ack_tokens_validated: bool
    approval_command_no_extra_tokens_validated: bool
    approval_command_no_newline_validated: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_display_mode: str
    approval_command_persisted: bool
    approval_command_copied_to_clipboard: bool
    approval_command_executable: bool
    dry_run_only: bool
    requires_human_approval: bool
    explicit_user_confirmation_required: bool
    ttl_seconds: int
    expires_at: datetime
    same_session_required: bool
    same_session_label: str
    required_ack_tokens: tuple[str, ...]
    post_allowed_this_step: bool
    post_attempt_limit: int
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool
    retry_allowed: bool
    loop_allowed: bool
    add_order_allowed: bool
    change_order_allowed: bool
    cancel_order_allowed: bool
    close_order_allowed: bool
    validation_request_snapshot: LiveOrderRealApprovalArtifactValidationRequestSnapshot
    provided_command_snapshot: LiveOrderRealApprovalProvidedCommandSnapshot
    validation_safety_snapshot: LiveOrderRealApprovalArtifactValidationSafetySnapshot
    future_step6d_handoff_conditions: tuple[str, ...]
    future_step6d_blockers: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalArtifactValidationCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalArtifactValidationSection, ...]

    def __post_init__(self) -> None:
        _validate_validation(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactValidationBuildResult:
    validation: LiveOrderRealApprovalArtifactValidation
    validation_id: str
    validation_status: LiveOrderRealApprovalArtifactValidationStatus
    validation_ready: bool
    approval_artifact_validated: bool
    approval_command_exact_match_validated: bool
    approval_command_ttl_validated: bool
    approval_command_same_session_validated: bool
    eligible_for_step6d_api_preflight_planning: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_persisted: bool
    approval_command_copied_to_clipboard: bool
    approval_command_executable: bool
    post_allowed_this_step: bool
    post_executed: bool
    live_order_once_called: bool
    private_api_called: bool
    broker_called: bool
    read_only_api_called: bool
    public_api_called: bool
    blocked_reasons: tuple[str, ...]
    recommended_next_step: str

    def __post_init__(self) -> None:
        if self.validation.validation_id != self.validation_id:
            raise LiveVerificationValidationError("validation_id mismatch")
        if self.validation.validation_status is not self.validation_status:
            raise LiveVerificationValidationError("validation_status mismatch")
        if self.validation.validation_ready is not self.validation_ready:
            raise LiveVerificationValidationError("validation_ready mismatch")
        if self.allowed_for_live is not False:
            raise LiveVerificationValidationError("allowed_for_live must be False")
        for field_name in (
            "approval_gate_issued",
            "approval_command_copyable",
            "approval_command_displayed",
            "approval_command_persisted",
            "approval_command_copied_to_clipboard",
            "approval_command_executable",
            "post_allowed_this_step",
            "post_executed",
            "live_order_once_called",
            "private_api_called",
            "broker_called",
            "read_only_api_called",
            "public_api_called",
        ):
            if getattr(self, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
        if self.validation.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.validation.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_provided_command_snapshot(
    *,
    provided_command: str | None,
    provided_command_created_at: datetime,
    provided_command_received_at: datetime,
) -> LiveOrderRealApprovalProvidedCommandSnapshot:
    """Build a sanitized command snapshot while preserving text only internally."""
    created = _ensure_aware(provided_command_created_at)
    received = _ensure_aware(provided_command_received_at)
    command = "" if provided_command is None else provided_command
    present = provided_command is not None
    parsed = _parse_provided_command(command)
    sha256 = hashlib.sha256(command.encode()).hexdigest() if command else "missing"
    fingerprint = (
        fingerprint_live_order_real_approval_provided_command(command)
        if command
        else "missing"
    )
    missing_ack_tokens = tuple(
        token.split("=", 1)[0]
        for token in REQUIRED_STEP6B_APPROVAL_ACK_TOKENS
        if token not in parsed.tokens
    )
    expected_token_names = {
        "APPROVE_FX_STEP6B_ARTIFACT",
        "approval_id",
        "symbol",
        "side",
        "size",
        "executionType",
        "ttl_seconds",
        "same_session",
        *(token.split("=", 1)[0] for token in REQUIRED_STEP6B_APPROVAL_ACK_TOKENS),
    }
    extra_names = tuple(
        name
        for name in parsed.token_names
        if name not in expected_token_names
    )
    has_extra = bool(extra_names) or len(parsed.tokens) > len(expected_token_names)
    return LiveOrderRealApprovalProvidedCommandSnapshot(
        provided_command_present=present,
        provided_command=command,
        provided_command_sha256=sha256,
        provided_command_fingerprint=fingerprint,
        provided_command_redacted=redact_live_order_real_approval_provided_command(
            command,
            command_fingerprint=fingerprint,
            ack_count=len(REQUIRED_STEP6B_APPROVAL_ACK_TOKENS)
            - len(missing_ack_tokens),
        ),
        provided_command_one_line=_is_one_line(command),
        provided_command_contains_newline="\n" in command or "\r" in command,
        provided_command_has_extra_tokens=has_extra,
        provided_command_missing_ack_tokens=bool(missing_ack_tokens),
        provided_command_extra_token_names=extra_names,
        provided_command_missing_ack_token_names=missing_ack_tokens,
        provided_command_same_session_label=parsed.fields.get("same_session", "missing"),
        provided_command_approval_id=parsed.fields.get("approval_id", "missing"),
        provided_command_symbol=parsed.fields.get("symbol", "missing"),
        provided_command_side=parsed.fields.get("side", "missing"),
        provided_command_size=_int_text(parsed.fields.get("size", "0")),
        provided_command_execution_type=parsed.fields.get("executionType", "missing"),
        provided_command_ttl_seconds=_int_text(parsed.fields.get("ttl_seconds", "0")),
        provided_command_created_at=created,
        provided_command_received_at=received,
    )


def build_live_order_real_approval_artifact_validation(
    *,
    source_artifact: LiveOrderRealApprovalArtifact | None,
    validation_request_snapshot: (
        LiveOrderRealApprovalArtifactValidationRequestSnapshot | None
    ),
    provided_command_snapshot: LiveOrderRealApprovalProvidedCommandSnapshot | None,
    validation_safety_snapshot: (
        LiveOrderRealApprovalArtifactValidationSafetySnapshot | None
    ),
    created_at: datetime | None = None,
    future_step6d_handoff_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_FUTURE_STEP6D_HANDOFF_CONDITIONS,
    future_step6d_blockers: tuple[str, ...] = DEFAULT_FUTURE_STEP6D_BLOCKERS,
) -> LiveOrderRealApprovalArtifactValidationBuildResult:
    """Validate a Step 6B artifact without API, POST, or copyable command output."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    source_reasons = _source_artifact_blocked_reasons(source_artifact)
    request_reasons = _request_blocked_reasons(validation_request_snapshot)
    command_reasons = _provided_command_blocked_reasons(
        artifact=source_artifact,
        snapshot=provided_command_snapshot,
    )
    safety_reasons = _safety_blocked_reasons(validation_safety_snapshot)
    condition_reasons = _condition_blocked_reasons(
        future_step6d_handoff_conditions=future_step6d_handoff_conditions,
        future_step6d_blockers=future_step6d_blockers,
    )

    source_missing_or_not_ready = _source_artifact_is_missing_or_not_ready(
        source_artifact,
        source_reasons,
    )
    if source_missing_or_not_ready:
        status = ValidationStatus.BLOCKED_STEP6C_SOURCE_ARTIFACT
        recommended_next_step = "fix_step6b_artifact_blockers_no_api_no_post"
        summary = "blocked Step 6C validation by source Step 6B artifact"
    elif request_reasons:
        status = ValidationStatus.BLOCKED_STEP6C_VALIDATION_REQUEST
        recommended_next_step = (
            "provide_explicit_step6c_request_and_acknowledgements_no_api_no_post"
        )
        summary = "blocked Step 6C validation by request acknowledgements"
    elif command_reasons:
        status = ValidationStatus.BLOCKED_STEP6C_PROVIDED_COMMAND
        recommended_next_step = (
            "provide_exact_one_line_approval_command_for_validation_no_api_no_post"
        )
        summary = "blocked Step 6C validation by provided command mismatch"
    elif safety_reasons:
        status = ValidationStatus.BLOCKED_STEP6C_VALIDATION_SAFETY_SNAPSHOT
        recommended_next_step = (
            "rerun_sanitized_validation_safety_snapshot_no_api_no_post"
        )
        summary = "blocked Step 6C validation by sanitized safety snapshot"
    elif source_reasons or condition_reasons:
        status = ValidationStatus.BLOCKED_STEP6C_UNSAFE_MISMATCH
        recommended_next_step = "fix_step6c_unsafe_mismatch_no_api_no_post"
        summary = "blocked Step 6C validation by unsafe mismatch"
    else:
        status = ValidationStatus.APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST
        recommended_next_step = (
            "stop_and_wait_for_explicit_step6d_api_preflight_planning_request_no_post"
        )
        summary = (
            "Step 6C validated the Step 6B approval artifact internally for future "
            "Step 6D planning only; live POST remains unavailable"
        )

    blocked_reasons = _merge_reasons(
        source_reasons,
        request_reasons,
        command_reasons,
        safety_reasons,
        condition_reasons,
    )
    ready = status is ValidationStatus.APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST
    safe_request = _request_or_empty(validation_request_snapshot, created)
    safe_command = _provided_command_or_empty(provided_command_snapshot, created)
    safe_safety = _safety_or_empty(validation_safety_snapshot, created)
    artifact = source_artifact
    check_results = _build_check_results(
        source_artifact=artifact,
        request_snapshot=validation_request_snapshot,
        provided_command_snapshot=provided_command_snapshot,
        validation_safety_snapshot=validation_safety_snapshot,
        future_step6d_handoff_conditions=future_step6d_handoff_conditions,
        future_step6d_blockers=future_step6d_blockers,
    )
    validation_id = make_live_order_real_approval_artifact_validation_id(
        source_artifact_id=_text_from(artifact, "artifact_id"),
        request_id=safe_request.request_id,
        safety_snapshot_id=safe_safety.safety_snapshot_id,
        provided_command_sha256=safe_command.provided_command_sha256,
        created_at=created,
        validation_status=status,
        blocked_reasons=blocked_reasons,
    )
    validation = LiveOrderRealApprovalArtifactValidation(
        validation_id=validation_id,
        created_at=created,
        source_artifact_id=_text_from(artifact, "artifact_id"),
        source_enablement_state_id=_text_from(artifact, "source_enablement_state_id"),
        source_plan_id=_text_from(artifact, "source_plan_id"),
        criteria_id=_text_from(artifact, "criteria_id"),
        symbol=_text_from(artifact, "symbol"),
        side=_text_from(artifact, "side"),
        size=_int_from(artifact, "size"),
        execution_type=_text_from(artifact, "execution_type"),
        source_type=_text_from(artifact, "source_type"),
        strategy_name=_text_from(artifact, "strategy_name"),
        validation_status=status,
        validation_ready=ready,
        approval_artifact_validated=ready,
        eligible_for_step6d_api_preflight_planning=ready,
        allowed_for_live=False,
        approval_gate_enabled=ready,
        approval_gate_issued=False,
        approval_id_generated=ready,
        approval_id_validated=ready,
        approval_command_generated=ready,
        approval_command_validated=ready,
        approval_command_exact_match_validated=ready,
        approval_command_sha256_validated=ready,
        approval_command_fingerprint_validated=ready,
        approval_command_ttl_validated=ready,
        approval_command_same_session_validated=ready,
        approval_command_one_line_validated=ready,
        approval_command_ack_tokens_validated=ready,
        approval_command_no_extra_tokens_validated=ready,
        approval_command_no_newline_validated=ready,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_display_mode=APPROVAL_COMMAND_DISPLAY_MODE_STEP6C,
        approval_command_persisted=False,
        approval_command_copied_to_clipboard=False,
        approval_command_executable=False,
        dry_run_only=True,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
        expires_at=_expires_at_or_created(artifact, created),
        same_session_required=True,
        same_session_label=_text_from(artifact, "same_session_label"),
        required_ack_tokens=REQUIRED_STEP6B_APPROVAL_ACK_TOKENS,
        post_allowed_this_step=False,
        post_attempt_limit=1,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        retry_allowed=False,
        loop_allowed=False,
        add_order_allowed=False,
        change_order_allowed=False,
        cancel_order_allowed=False,
        close_order_allowed=False,
        validation_request_snapshot=safe_request,
        provided_command_snapshot=safe_command,
        validation_safety_snapshot=safe_safety,
        future_step6d_handoff_conditions=future_step6d_handoff_conditions,
        future_step6d_blockers=future_step6d_blockers,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_step6d_handoff_conditions=future_step6d_handoff_conditions,
            future_step6d_blockers=future_step6d_blockers,
        ),
    )
    return LiveOrderRealApprovalArtifactValidationBuildResult(
        validation=validation,
        validation_id=validation.validation_id,
        validation_status=validation.validation_status,
        validation_ready=validation.validation_ready,
        approval_artifact_validated=validation.approval_artifact_validated,
        approval_command_exact_match_validated=(
            validation.approval_command_exact_match_validated
        ),
        approval_command_ttl_validated=validation.approval_command_ttl_validated,
        approval_command_same_session_validated=(
            validation.approval_command_same_session_validated
        ),
        eligible_for_step6d_api_preflight_planning=(
            validation.eligible_for_step6d_api_preflight_planning
        ),
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_persisted=False,
        approval_command_copied_to_clipboard=False,
        approval_command_executable=False,
        post_allowed_this_step=False,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        blocked_reasons=validation.blocked_reasons,
        recommended_next_step=validation.recommended_next_step,
    )


def render_live_order_real_approval_artifact_validation_markdown(
    validation: LiveOrderRealApprovalArtifactValidation,
) -> str:
    """Render a sanitized Step 6C validation without full command text."""
    blocked_text = ", ".join(validation.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in validation.required_ack_tokens)
    handoff_lines = "\n".join(
        f"- {item}" for item in validation.future_step6d_handoff_conditions
    )
    blocker_lines = "\n".join(f"- {item}" for item in validation.future_step6d_blockers)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in validation.check_results
    )
    command = validation.provided_command_snapshot
    safety = validation.validation_safety_snapshot
    return "\n".join(
        (
            "# Step 6C Real Approval Artifact Validation",
            "",
            "This Step 6C approval artifact validation is dry-run only.",
            "This Step 6C validation does not authorize live POST.",
            "This Step 6C validation keeps allowed_for_live=false.",
            "This Step 6C validation does not issue a real approval gate.",
            (
                "This Step 6C renderer does not display the full generated "
                "approval command."
            ),
            (
                "This Step 6C renderer does not display the full provided "
                "approval command."
            ),
            "This Step 6C renderer does not provide copyable approval text.",
            "This Step 6C validation does not call read-only API.",
            "This Step 6C validation does not call public API.",
            "This Step 6C validation does not call Private API.",
            "This Step 6C validation does not call live_order_once.",
            "This Step 6C validation does not execute HTTP POST.",
            "",
            f"validation_id: {validation.validation_id}",
            f"source_artifact_id: {validation.source_artifact_id}",
            f"source_enablement_state_id: {validation.source_enablement_state_id}",
            f"source_plan_id: {validation.source_plan_id}",
            f"criteria_id: {validation.criteria_id}",
            f"source_type: {validation.source_type}",
            f"strategy_name: {validation.strategy_name}",
            f"symbol: {validation.symbol}",
            f"side: {validation.side}",
            f"size: {validation.size}",
            f"executionType: {validation.execution_type}",
            f"validation_status: {validation.validation_status.value}",
            f"validation_ready: {validation.validation_ready}",
            f"approval_artifact_validated: {validation.approval_artifact_validated}",
            (
                "eligible_for_step6d_api_preflight_planning: "
                f"{validation.eligible_for_step6d_api_preflight_planning}"
            ),
            f"approval_gate_enabled: {validation.approval_gate_enabled}",
            f"allowed_for_live: {validation.allowed_for_live}",
            f"approval_gate_issued: {validation.approval_gate_issued}",
            f"approval_id_generated: {validation.approval_id_generated}",
            f"approval_id_validated: {validation.approval_id_validated}",
            f"approval_command_generated: {validation.approval_command_generated}",
            f"approval_command_validated: {validation.approval_command_validated}",
            (
                "approval_command_exact_match_validated: "
                f"{validation.approval_command_exact_match_validated}"
            ),
            (
                "approval_command_sha256_validated: "
                f"{validation.approval_command_sha256_validated}"
            ),
            (
                "approval_command_fingerprint_validated: "
                f"{validation.approval_command_fingerprint_validated}"
            ),
            f"approval_command_ttl_validated: {validation.approval_command_ttl_validated}",
            (
                "approval_command_same_session_validated: "
                f"{validation.approval_command_same_session_validated}"
            ),
            (
                "approval_command_one_line_validated: "
                f"{validation.approval_command_one_line_validated}"
            ),
            (
                "approval_command_ack_tokens_validated: "
                f"{validation.approval_command_ack_tokens_validated}"
            ),
            (
                "approval_command_no_extra_tokens_validated: "
                f"{validation.approval_command_no_extra_tokens_validated}"
            ),
            (
                "approval_command_no_newline_validated: "
                f"{validation.approval_command_no_newline_validated}"
            ),
            f"approval_command_copyable: {validation.approval_command_copyable}",
            f"approval_command_displayed: {validation.approval_command_displayed}",
            f"approval_command_display_mode: {validation.approval_command_display_mode}",
            f"approval_command_persisted: {validation.approval_command_persisted}",
            (
                "approval_command_copied_to_clipboard: "
                f"{validation.approval_command_copied_to_clipboard}"
            ),
            f"approval_command_executable: {validation.approval_command_executable}",
            f"provided_command_sha256: {command.provided_command_sha256}",
            f"provided_command_fingerprint: {command.provided_command_fingerprint}",
            f"provided_command_redacted: {command.provided_command_redacted}",
            f"ttl_seconds: {validation.ttl_seconds}",
            f"expires_at: {validation.expires_at.isoformat()}",
            f"same_session_required: {validation.same_session_required}",
            f"same_session_label: {validation.same_session_label}",
            f"post_allowed_this_step: {validation.post_allowed_this_step}",
            f"post_attempt_limit: {validation.post_attempt_limit}",
            f"post_executed: {validation.post_executed}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {validation.recommended_next_step}",
            "",
            "## Sanitized Safety Summary",
            f"- source_artifact_age_seconds: {safety.source_artifact_age_seconds}",
            f"- validation_received_age_seconds: {safety.validation_received_age_seconds}",
            f"- timezone: {safety.timezone}",
            f"- market_hours_source: {safety.market_hours_source}",
            f"- market_session_state: {safety.market_session_state}",
            f"- is_weekend_jst: {safety.is_weekend_jst}",
            f"- market_window_allowed: {safety.market_window_allowed}",
            f"- broker_maintenance_active: {safety.broker_maintenance_active}",
            f"- market_hours_unknown: {safety.market_hours_unknown}",
            (
                "- fresh_pre_approval_preflight_source: "
                f"{safety.fresh_pre_approval_preflight_source}"
            ),
            (
                "- fresh_pre_approval_preflight_status: "
                f"{safety.fresh_pre_approval_preflight_status}"
            ),
            (
                "- fresh_pre_approval_preflight_passed: "
                f"{safety.fresh_pre_approval_preflight_passed}"
            ),
            f"- open_positions_count: {safety.open_positions_count}",
            f"- active_orders_count: {safety.active_orders_count}",
            f"- result_unknown: {safety.result_unknown}",
            f"- raw_response_saved: {safety.raw_response_saved}",
            f"- raw_response_displayed: {safety.raw_response_displayed}",
            f"- secret_scan_passed: {safety.secret_scan_passed}",
            "",
            "## Required ACK Tokens",
            ack_lines,
            "",
            "## Future Step 6D Handoff Conditions",
            handoff_lines,
            "",
            "## Future Step 6D Blockers",
            blocker_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_artifact_validation_id(
    *,
    source_artifact_id: str,
    request_id: str,
    safety_snapshot_id: str,
    provided_command_sha256: str,
    created_at: datetime,
    validation_status: LiveOrderRealApprovalArtifactValidationStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "provided_command_sha256": provided_command_sha256,
        "request_id": request_id,
        "safety_snapshot_id": safety_snapshot_id,
        "source_artifact_id": source_artifact_id,
        "validation_status": validation_status.value,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_ARTIFACT_VALIDATION_ID_PREFIX}{digest}"


def redact_live_order_real_approval_provided_command(
    command: str,
    *,
    command_fingerprint: str,
    ack_count: int,
) -> str:
    _require_non_empty("command_fingerprint", command_fingerprint)
    if not command:
        return "APPROVE_FX_STEP6B_ARTIFACT <missing>"
    return (
        "APPROVE_FX_STEP6B_ARTIFACT "
        f"approval_id=<redacted:{command_fingerprint}> "
        "symbol=<sanitized> side=<sanitized> size=<sanitized> "
        "executionType=<sanitized> ttl_seconds=<sanitized> "
        "same_session=<redacted> "
        f"ack_count={ack_count}"
    )


def fingerprint_live_order_real_approval_provided_command(command: str) -> str:
    _require_non_empty("command", command)
    return hashlib.sha256(command.encode()).hexdigest()[:16].upper()


def _source_artifact_blocked_reasons(
    artifact: LiveOrderRealApprovalArtifact | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(artifact, LiveOrderRealApprovalArtifact):
        _add_reason(reasons, BlockReason.MISSING_SOURCE_ARTIFACT)
        return tuple(reasons)
    if (
        artifact.artifact_status
        is not ArtifactStatus.APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST
        or artifact.artifact_ready is not True
    ):
        _add_reason(reasons, BlockReason.SOURCE_ARTIFACT_NOT_READY)
    if artifact.eligible_for_step6c_validation is not True:
        _add_reason(reasons, BlockReason.SOURCE_ARTIFACT_NOT_ELIGIBLE)
    if artifact.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SOURCE_ARTIFACT_ALLOWS_LIVE)
    if artifact.approval_gate_enabled is not True:
        _add_reason(reasons, BlockReason.SOURCE_GATE_NOT_ENABLED)
    for flag, reason in (
        (artifact.approval_gate_issued, BlockReason.SOURCE_GATE_ALREADY_ISSUED),
        (
            artifact.approval_id_generated is not True,
            BlockReason.SOURCE_APPROVAL_ID_NOT_GENERATED,
        ),
        (
            artifact.approval_command_generated is not True,
            BlockReason.SOURCE_APPROVAL_COMMAND_NOT_GENERATED,
        ),
        (artifact.approval_command_copyable, BlockReason.SOURCE_APPROVAL_COMMAND_COPYABLE),
        (artifact.approval_command_displayed, BlockReason.SOURCE_APPROVAL_COMMAND_DISPLAYED),
        (artifact.approval_command_persisted, BlockReason.SOURCE_APPROVAL_COMMAND_PERSISTED),
        (
            artifact.approval_command_copied_to_clipboard,
            BlockReason.SOURCE_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD,
        ),
        (
            artifact.approval_command_executable,
            BlockReason.SOURCE_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (artifact.post_allowed_this_step, BlockReason.SOURCE_POST_ALLOWED_THIS_STEP),
        (artifact.post_executed, BlockReason.SOURCE_POST_ALREADY_EXECUTED),
        (artifact.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        (artifact.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
        (artifact.broker_called, BlockReason.BROKER_ALREADY_CALLED),
        (artifact.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        (artifact.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
        (artifact.retry_allowed, BlockReason.RETRY_ALLOWED),
        (artifact.loop_allowed, BlockReason.LOOP_ALLOWED),
        (artifact.add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (artifact.change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (artifact.cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (artifact.close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if artifact.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if artifact.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if artifact.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if artifact.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _request_blocked_reasons(
    snapshot: LiveOrderRealApprovalArtifactValidationRequestSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalArtifactValidationRequestSnapshot):
        _add_reason(reasons, BlockReason.MISSING_VALIDATION_REQUEST_SNAPSHOT)
        return tuple(reasons)
    for field_name, reason in (
        (
            "explicit_step6c_user_instruction_received",
            BlockReason.EXPLICIT_STEP6C_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_api_in_step6c",
            BlockReason.OPERATOR_NO_API_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6c",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_live_order_once_in_step6c",
            BlockReason.OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_validation_only",
            BlockReason.OPERATOR_VALIDATION_ONLY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_approval_command_not_copyable_in_step6c",
            BlockReason.OPERATOR_NO_COPYABLE_COMMAND_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6d_required_for_api_preflight",
            BlockReason.OPERATOR_STEP6D_PREFLIGHT_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6e_or_later_required_for_post",
            BlockReason.OPERATOR_STEP6E_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_unknown_means_stop",
            BlockReason.OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED,
        ),
    ):
        if getattr(snapshot, field_name) is not True:
            _add_reason(reasons, reason)
    if snapshot.request_scope_label != STEP6C_REQUEST_SCOPE_LABEL:
        _add_reason(reasons, BlockReason.INVALID_REQUEST_SCOPE_LABEL)
    return tuple(reasons)


def _provided_command_blocked_reasons(
    *,
    artifact: LiveOrderRealApprovalArtifact | None,
    snapshot: LiveOrderRealApprovalProvidedCommandSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalProvidedCommandSnapshot):
        _add_reason(reasons, BlockReason.MISSING_PROVIDED_COMMAND)
        return tuple(reasons)
    if snapshot.provided_command_present is not True:
        _add_reason(reasons, BlockReason.MISSING_PROVIDED_COMMAND)
    if snapshot.provided_command == "":
        _add_reason(reasons, BlockReason.PROVIDED_COMMAND_EMPTY)
    if snapshot.provided_command_contains_newline is True:
        _add_reason(reasons, BlockReason.PROVIDED_COMMAND_NEWLINE)
    if snapshot.provided_command_one_line is not True:
        _add_reason(reasons, BlockReason.PROVIDED_COMMAND_NOT_ONE_LINE)
    if snapshot.provided_command_has_extra_tokens is True:
        _add_reason(reasons, BlockReason.PROVIDED_COMMAND_EXTRA_TOKENS)
    if snapshot.provided_command_missing_ack_tokens is True:
        _add_reason(reasons, BlockReason.PROVIDED_COMMAND_MISSING_ACK_TOKENS)
    if not isinstance(artifact, LiveOrderRealApprovalArtifact):
        return tuple(reasons)
    if snapshot.provided_command_approval_id != artifact.approval_id:
        _add_reason(reasons, BlockReason.APPROVAL_ID_MISMATCH)
    if snapshot.provided_command_symbol != artifact.symbol:
        _add_reason(reasons, BlockReason.SYMBOL_MISMATCH)
    if snapshot.provided_command_side != artifact.side:
        _add_reason(reasons, BlockReason.SIDE_MISMATCH)
    if snapshot.provided_command_size != artifact.size:
        _add_reason(reasons, BlockReason.SIZE_MISMATCH)
    if snapshot.provided_command_execution_type != artifact.execution_type:
        _add_reason(reasons, BlockReason.EXECUTION_TYPE_MISMATCH)
    if snapshot.provided_command_ttl_seconds != artifact.ttl_seconds:
        _add_reason(reasons, BlockReason.TTL_SECONDS_MISMATCH)
    if snapshot.provided_command_same_session_label != artifact.same_session_label:
        _add_reason(reasons, BlockReason.SAME_SESSION_MISMATCH)
    if snapshot.provided_command_sha256 != artifact.approval_command_sha256:
        _add_reason(reasons, BlockReason.SHA256_MISMATCH)
    if snapshot.provided_command_fingerprint != artifact.approval_command_fingerprint:
        _add_reason(reasons, BlockReason.FINGERPRINT_MISMATCH)
    if snapshot.provided_command != artifact.approval_command:
        _add_reason(reasons, BlockReason.EXACT_MATCH_MISMATCH)
    return tuple(reasons)


def _safety_blocked_reasons(
    snapshot: LiveOrderRealApprovalArtifactValidationSafetySnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalArtifactValidationSafetySnapshot):
        _add_reason(reasons, BlockReason.MISSING_VALIDATION_SAFETY_SNAPSHOT)
        return tuple(reasons)
    if snapshot.source_artifact_age_seconds > snapshot.source_artifact_max_age_seconds:
        _add_reason(reasons, BlockReason.SOURCE_ARTIFACT_STALE)
    if (
        snapshot.validation_received_age_seconds
        > snapshot.validation_received_max_age_seconds
    ):
        _add_reason(reasons, BlockReason.VALIDATION_RECEIVED_STALE)
    if snapshot.approval_gate_enabled is not True:
        _add_reason(reasons, BlockReason.SAFETY_GATE_NOT_ENABLED)
    if snapshot.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SAFETY_ALLOWS_LIVE)
    for flag, reason in (
        (snapshot.approval_gate_issued, BlockReason.SAFETY_GATE_ALREADY_ISSUED),
        (
            snapshot.approval_id_generated is not True,
            BlockReason.SAFETY_APPROVAL_ID_NOT_GENERATED,
        ),
        (
            snapshot.approval_command_generated is not True,
            BlockReason.SAFETY_APPROVAL_COMMAND_NOT_GENERATED,
        ),
        (
            snapshot.approval_command_copyable,
            BlockReason.SAFETY_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            snapshot.approval_command_displayed,
            BlockReason.SAFETY_APPROVAL_COMMAND_DISPLAYED,
        ),
        (
            snapshot.approval_command_persisted,
            BlockReason.SAFETY_APPROVAL_COMMAND_PERSISTED,
        ),
        (
            snapshot.approval_command_copied_to_clipboard,
            BlockReason.SAFETY_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD,
        ),
        (
            snapshot.approval_command_executable,
            BlockReason.SAFETY_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            snapshot.real_approval_artifacts_available,
            BlockReason.SAFETY_REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if snapshot.timezone != MARKET_HOURS_TIMEZONE:
        _add_reason(reasons, BlockReason.INVALID_TIMEZONE)
    if snapshot.market_hours_source != MARKET_HOURS_SOURCE:
        _add_reason(reasons, BlockReason.INVALID_MARKET_HOURS_SOURCE)
    if snapshot.market_session_state != MARKET_HOURS_OPEN_STATE:
        _add_reason(reasons, BlockReason.MARKET_SESSION_NOT_OPEN)
    if snapshot.is_weekend_jst is not False:
        _add_reason(reasons, BlockReason.WEEKEND_JST)
    if snapshot.market_window_allowed is not True:
        _add_reason(reasons, BlockReason.MARKET_WINDOW_NOT_ALLOWED)
    if snapshot.broker_maintenance_active is not False:
        _add_reason(reasons, BlockReason.BROKER_MAINTENANCE_ACTIVE)
    if snapshot.holiday_or_special_close is not False:
        _add_reason(reasons, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE)
    if snapshot.holiday_or_special_close_unknown is not False:
        _add_reason(reasons, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE_UNKNOWN)
    if snapshot.market_hours_unknown is not False:
        _add_reason(reasons, BlockReason.MARKET_HOURS_UNKNOWN)
    if (
        snapshot.market_hours_snapshot_age_seconds
        > snapshot.market_hours_snapshot_max_age_seconds
    ):
        _add_reason(reasons, BlockReason.MARKET_HOURS_SNAPSHOT_STALE)
    if snapshot.fresh_pre_approval_preflight_source != FRESH_PREFLIGHT_SOURCE:
        _add_reason(reasons, BlockReason.INVALID_FRESH_PREFLIGHT_SOURCE)
    if snapshot.fresh_pre_approval_preflight_status != FRESH_PREFLIGHT_READY_STATUS:
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_NOT_READY)
    if snapshot.fresh_pre_approval_preflight_passed is not True:
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_NOT_PASSED)
    if snapshot.fresh_pre_approval_preflight_unknown is not False:
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_UNKNOWN)
    if (
        snapshot.fresh_pre_approval_preflight_age_seconds
        > snapshot.fresh_pre_approval_preflight_max_age_seconds
    ):
        _add_reason(reasons, BlockReason.FRESH_PREFLIGHT_STALE)
    if snapshot.open_positions_count != 0:
        _add_reason(reasons, BlockReason.OPEN_POSITION_EXISTS)
    if snapshot.active_orders_count != 0:
        _add_reason(reasons, BlockReason.ACTIVE_ORDER_EXISTS)
    if snapshot.result_unknown is not False:
        _add_reason(reasons, BlockReason.RESULT_UNKNOWN)
    if snapshot.raw_response_saved is not False:
        _add_reason(reasons, BlockReason.RAW_RESPONSE_SAVED)
    if snapshot.raw_response_displayed is not False:
        _add_reason(reasons, BlockReason.RAW_RESPONSE_DISPLAYED)
    if snapshot.secret_scan_passed is not True:
        _add_reason(reasons, BlockReason.SECRET_SCAN_NOT_PASSED)
    return tuple(reasons)


def _condition_blocked_reasons(
    *,
    future_step6d_handoff_conditions: tuple[str, ...],
    future_step6d_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not future_step6d_handoff_conditions:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6D_HANDOFF_CONDITIONS)
    if not future_step6d_blockers:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6D_BLOCKERS)
    return tuple(reasons)


def _build_check_results(
    *,
    source_artifact: LiveOrderRealApprovalArtifact | None,
    request_snapshot: LiveOrderRealApprovalArtifactValidationRequestSnapshot | None,
    provided_command_snapshot: LiveOrderRealApprovalProvidedCommandSnapshot | None,
    validation_safety_snapshot: LiveOrderRealApprovalArtifactValidationSafetySnapshot | None,
    future_step6d_handoff_conditions: tuple[str, ...],
    future_step6d_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalArtifactValidationCheckResult, ...]:
    source_ready = not _source_artifact_blocked_reasons(source_artifact)
    request_ready = not _request_blocked_reasons(request_snapshot)
    command_ready = not _provided_command_blocked_reasons(
        artifact=source_artifact,
        snapshot=provided_command_snapshot,
    )
    safety_ready = not _safety_blocked_reasons(validation_safety_snapshot)
    artifact = source_artifact
    command = provided_command_snapshot
    no_api_called = isinstance(artifact, LiveOrderRealApprovalArtifact) and all(
        getattr(artifact, field_name) is False
        for field_name in (
            "live_order_once_called",
            "private_api_called",
            "broker_called",
            "read_only_api_called",
            "public_api_called",
        )
    )
    exact_match = (
        isinstance(artifact, LiveOrderRealApprovalArtifact)
        and isinstance(command, LiveOrderRealApprovalProvidedCommandSnapshot)
        and command.provided_command == artifact.approval_command
    )
    command_present = (
        isinstance(command, LiveOrderRealApprovalProvidedCommandSnapshot)
        and command.provided_command_present
    )
    command_one_line = (
        isinstance(command, LiveOrderRealApprovalProvidedCommandSnapshot)
        and command.provided_command_one_line
    )
    command_no_newline = (
        isinstance(command, LiveOrderRealApprovalProvidedCommandSnapshot)
        and not command.provided_command_contains_newline
    )
    command_no_extra_tokens = (
        isinstance(command, LiveOrderRealApprovalProvidedCommandSnapshot)
        and not command.provided_command_has_extra_tokens
    )
    command_ack_tokens_complete = (
        isinstance(command, LiveOrderRealApprovalProvidedCommandSnapshot)
        and not command.provided_command_missing_ack_tokens
    )
    artifact_allows_no_live = (
        isinstance(artifact, LiveOrderRealApprovalArtifact)
        and artifact.allowed_for_live is False
    )
    artifact_gate_not_issued = (
        isinstance(artifact, LiveOrderRealApprovalArtifact)
        and artifact.approval_gate_issued is False
    )
    artifact_post_not_executed = (
        isinstance(artifact, LiveOrderRealApprovalArtifact)
        and artifact.post_executed is False
    )
    return (
        _check(
            "source_artifact_ready",
            source_ready,
            "source Step 6B artifact ready",
            _bool_text(source_ready),
            "true",
        ),
        _check(
            "explicit_step6c_request_received",
            request_ready,
            "explicit Step 6C request is required",
            _bool_text(request_ready),
            "true",
        ),
        _check(
            "operator_acknowledgements_complete",
            request_ready,
            "operator acknowledgements are required",
            _bool_text(request_ready),
            "true",
        ),
        _check(
            "provided_command_present",
            command_present,
            "provided command must be present internally",
            _bool_text(command_present),
            "true",
        ),
        _check(
            "provided_command_exact_match",
            exact_match,
            "provided command must exactly match generated command",
            _bool_text(exact_match),
            "true",
        ),
        _check(
            "approval_id_validated",
            command_ready and command_present,
            "approval_id must match source artifact",
            _bool_text(command_ready and command_present),
            "true",
        ),
        _check(
            "approval_command_sha256_validated",
            command_ready,
            "sha256 must match source artifact",
            _bool_text(command_ready),
            "true",
        ),
        _check(
            "approval_command_fingerprint_validated",
            command_ready,
            "fingerprint must match source artifact",
            _bool_text(command_ready),
            "true",
        ),
        _check(
            "approval_command_one_line",
            command_one_line,
            "provided command must be one-line",
            _bool_text(command_one_line),
            "true",
        ),
        _check(
            "approval_command_no_newline",
            command_no_newline,
            "provided command must not contain newline",
            _bool_text(command_no_newline),
            "true",
        ),
        _check(
            "approval_command_no_extra_tokens",
            command_no_extra_tokens,
            "provided command must not contain extra tokens",
            _bool_text(command_no_extra_tokens),
            "true",
        ),
        _check(
            "approval_command_ack_tokens_complete",
            command_ack_tokens_complete,
            "all ACK tokens must be present",
            _bool_text(command_ack_tokens_complete),
            "true",
        ),
        _check(
            "approval_command_ttl_validated",
            safety_ready and command_ready,
            "TTL and received age must be fresh",
            _bool_text(safety_ready and command_ready),
            "true",
        ),
        _check(
            "approval_command_same_session_validated",
            command_ready,
            "same session label must match",
            _bool_text(command_ready),
            "true",
        ),
        _check(
            "allowed_for_live_false",
            artifact_allows_no_live,
            "allowed_for_live must remain false",
            _bool_text(artifact_allows_no_live),
            "true",
        ),
        _check(
            "approval_gate_not_issued",
            artifact_gate_not_issued,
            "Step 6C must not issue gate",
            _bool_text(artifact_gate_not_issued),
            "true",
        ),
        _check(
            "approval_command_not_displayed",
            True,
            "Step 6C renderer must not display full command",
            "false",
            "false",
        ),
        _check(
            "approval_command_not_copyable",
            True,
            "Step 6C must not create copyable approval text",
            "false",
            "false",
        ),
        _check(
            "approval_command_not_persisted",
            True,
            "Step 6C must not persist approval command text",
            "false",
            "false",
        ),
        _check(
            "approval_command_not_copied_to_clipboard",
            True,
            "Step 6C must not copy approval command to clipboard",
            "false",
            "false",
        ),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_called,
            "Step 6C must not call API, broker, or live_order_once",
            _bool_text(no_api_called),
            "true",
        ),
        _check(
            "post_not_allowed_this_step",
            True,
            "Step 6C never allows HTTP POST",
            "false",
            "false",
        ),
        _check(
            "post_not_executed",
            artifact_post_not_executed,
            "Step 6C must not execute HTTP POST",
            _bool_text(artifact_post_not_executed),
            "true",
        ),
        _check(
            "future_step6d_handoff_conditions_present",
            bool(future_step6d_handoff_conditions),
            "future Step 6D handoff conditions must be present",
            _bool_text(bool(future_step6d_handoff_conditions)),
            "true",
        ),
        _check(
            "future_step6d_blockers_present",
            bool(future_step6d_blockers),
            "future Step 6D blockers must be present",
            _bool_text(bool(future_step6d_blockers)),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalArtifactValidationCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_step6d_handoff_conditions: tuple[str, ...],
    future_step6d_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalArtifactValidationSection, ...]:
    return (
        LiveOrderRealApprovalArtifactValidationSection(
            section_id="step6c_scope",
            title="Step 6C Scope",
            lines=(
                "approval artifact validation only",
                "allowed_for_live remains false",
                (
                    "full generated/provided approval commands are not rendered, "
                    "copied, persisted, or executable"
                ),
                "no API, broker, live_order_once, ledger, or HTTP POST is performed",
            ),
        ),
        LiveOrderRealApprovalArtifactValidationSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked_reasons or ("none",),
        ),
        LiveOrderRealApprovalArtifactValidationSection(
            section_id="check_results",
            title="Check Results",
            lines=tuple(
                f"{check.name}: passed={check.passed}, expected={check.expected}"
                for check in check_results
            ),
        ),
        LiveOrderRealApprovalArtifactValidationSection(
            section_id="future_step6d_handoff",
            title="Future Step 6D Handoff",
            lines=future_step6d_handoff_conditions or ("missing",),
        ),
        LiveOrderRealApprovalArtifactValidationSection(
            section_id="future_step6d_blockers",
            title="Future Step 6D Blockers",
            lines=future_step6d_blockers or ("missing",),
        ),
        LiveOrderRealApprovalArtifactValidationSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_validation(validation: LiveOrderRealApprovalArtifactValidation) -> None:
    _require_non_empty("validation_id", validation.validation_id)
    if not validation.validation_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_ARTIFACT_VALIDATION_ID_PREFIX,
    ):
        raise LiveVerificationValidationError("invalid validation_id prefix")
    _ensure_aware(validation.created_at)
    _ensure_aware(validation.expires_at)
    for label, value in (
        ("source_artifact_id", validation.source_artifact_id),
        ("source_enablement_state_id", validation.source_enablement_state_id),
        ("source_plan_id", validation.source_plan_id),
        ("criteria_id", validation.criteria_id),
        ("symbol", validation.symbol),
        ("side", validation.side),
        ("execution_type", validation.execution_type),
        ("source_type", validation.source_type),
        ("strategy_name", validation.strategy_name),
        ("approval_command_display_mode", validation.approval_command_display_mode),
        ("same_session_label", validation.same_session_label),
        ("summary", validation.summary),
        ("recommended_next_step", validation.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if validation.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    for field_name in (
        "approval_gate_issued",
        "approval_command_copyable",
        "approval_command_displayed",
        "approval_command_persisted",
        "approval_command_copied_to_clipboard",
        "approval_command_executable",
        "post_allowed_this_step",
        "post_executed",
        "live_order_once_called",
        "private_api_called",
        "broker_called",
        "read_only_api_called",
        "public_api_called",
        "retry_allowed",
        "loop_allowed",
        "add_order_allowed",
        "change_order_allowed",
        "cancel_order_allowed",
        "close_order_allowed",
    ):
        if getattr(validation, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    for field_name in (
        "dry_run_only",
        "requires_human_approval",
        "explicit_user_confirmation_required",
        "same_session_required",
    ):
        if getattr(validation, field_name) is not True:
            raise LiveVerificationValidationError(f"{field_name} must be True")
    if validation.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if validation.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if set(REQUIRED_STEP6B_APPROVAL_ACK_TOKENS) != set(validation.required_ack_tokens):
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if validation.validation_ready:
        if (
            validation.validation_status
            is not ValidationStatus.APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST
        ):
            raise LiveVerificationValidationError("ready validation has invalid status")
        for field_name in (
            "approval_artifact_validated",
            "eligible_for_step6d_api_preflight_planning",
            "approval_gate_enabled",
            "approval_id_generated",
            "approval_id_validated",
            "approval_command_generated",
            "approval_command_validated",
            "approval_command_exact_match_validated",
            "approval_command_sha256_validated",
            "approval_command_fingerprint_validated",
            "approval_command_ttl_validated",
            "approval_command_same_session_validated",
            "approval_command_one_line_validated",
            "approval_command_ack_tokens_validated",
            "approval_command_no_extra_tokens_validated",
            "approval_command_no_newline_validated",
        ):
            if getattr(validation, field_name) is not True:
                raise LiveVerificationValidationError(f"{field_name} must be True")
        if validation.symbol != SUPPORTED_SYMBOL:
            raise LiveVerificationValidationError("unsupported symbol")
        if validation.side not in {
            LiveOrderCandidateSide.BUY.value,
            LiveOrderCandidateSide.SELL.value,
        }:
            raise LiveVerificationValidationError("unsupported side")
        if validation.size != LIVE_ORDER_CANDIDATE_SIZE:
            raise LiveVerificationValidationError("unsupported size")
        if validation.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
            raise LiveVerificationValidationError("unsupported execution_type")
    else:
        for field_name in (
            "approval_artifact_validated",
            "eligible_for_step6d_api_preflight_planning",
            "approval_gate_enabled",
            "approval_id_generated",
            "approval_id_validated",
            "approval_command_generated",
            "approval_command_validated",
            "approval_command_exact_match_validated",
            "approval_command_sha256_validated",
            "approval_command_fingerprint_validated",
            "approval_command_ttl_validated",
            "approval_command_same_session_validated",
            "approval_command_one_line_validated",
            "approval_command_ack_tokens_validated",
            "approval_command_no_extra_tokens_validated",
            "approval_command_no_newline_validated",
        ):
            if getattr(validation, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
    if not validation.check_results:
        raise LiveVerificationValidationError("check_results required")
    if not validation.sections:
        raise LiveVerificationValidationError("sections required")


def _source_artifact_is_missing_or_not_ready(
    artifact: LiveOrderRealApprovalArtifact | None,
    reasons: tuple[str, ...],
) -> bool:
    if not isinstance(artifact, LiveOrderRealApprovalArtifact):
        return True
    source_blocking = {
        BlockReason.SOURCE_ARTIFACT_NOT_READY.value,
        BlockReason.SOURCE_ARTIFACT_NOT_ELIGIBLE.value,
        BlockReason.MISSING_SOURCE_ARTIFACT.value,
    }
    return bool(set(reasons) & source_blocking)


def _request_or_empty(
    snapshot: LiveOrderRealApprovalArtifactValidationRequestSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalArtifactValidationRequestSnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalArtifactValidationRequestSnapshot):
        return snapshot
    return LiveOrderRealApprovalArtifactValidationRequestSnapshot(
        request_id="missing",
        created_at=created_at,
        explicit_step6c_user_instruction_received=False,
        operator_understands_real_money_risk=False,
        operator_understands_no_api_in_step6c=False,
        operator_understands_no_post_in_step6c=False,
        operator_understands_no_live_order_once_in_step6c=False,
        operator_understands_validation_only=False,
        operator_understands_approval_command_not_copyable_in_step6c=False,
        operator_understands_step6d_required_for_api_preflight=False,
        operator_understands_step6e_or_later_required_for_post=False,
        operator_understands_unknown_means_stop=False,
        request_scope_label="missing",
    )


def _provided_command_or_empty(
    snapshot: LiveOrderRealApprovalProvidedCommandSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalProvidedCommandSnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalProvidedCommandSnapshot):
        return snapshot
    return build_live_order_real_approval_provided_command_snapshot(
        provided_command=None,
        provided_command_created_at=created_at,
        provided_command_received_at=created_at,
    )


def _safety_or_empty(
    snapshot: LiveOrderRealApprovalArtifactValidationSafetySnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalArtifactValidationSafetySnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalArtifactValidationSafetySnapshot):
        return snapshot
    return LiveOrderRealApprovalArtifactValidationSafetySnapshot(
        safety_snapshot_id="missing",
        created_at=created_at,
        source_artifact_age_seconds=999999,
        source_artifact_max_age_seconds=DEFAULT_STEP6C_SOURCE_ARTIFACT_MAX_AGE_SECONDS,
        validation_received_age_seconds=999999,
        validation_received_max_age_seconds=(
            DEFAULT_STEP6C_VALIDATION_RECEIVED_MAX_AGE_SECONDS
        ),
        approval_gate_enabled=False,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated=False,
        approval_command_generated=False,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_persisted=False,
        approval_command_copied_to_clipboard=False,
        approval_command_executable=False,
        real_approval_artifacts_available=True,
        timezone=MARKET_HOURS_TIMEZONE,
        market_hours_source=MARKET_HOURS_SOURCE,
        market_session_state="missing",
        is_weekend_jst=True,
        market_window_allowed=False,
        broker_maintenance_active=True,
        holiday_or_special_close=True,
        holiday_or_special_close_unknown=True,
        market_hours_unknown=True,
        market_hours_snapshot_age_seconds=999999,
        market_hours_snapshot_max_age_seconds=MARKET_HOURS_MAX_AGE_SECONDS,
        fresh_pre_approval_preflight_source=FRESH_PREFLIGHT_SOURCE,
        fresh_pre_approval_preflight_status="missing",
        fresh_pre_approval_preflight_passed=False,
        fresh_pre_approval_preflight_unknown=True,
        fresh_pre_approval_preflight_age_seconds=999999,
        fresh_pre_approval_preflight_max_age_seconds=FRESH_PREFLIGHT_MAX_AGE_SECONDS,
        open_positions_count=999999,
        active_orders_count=999999,
        result_unknown=True,
        raw_response_saved=True,
        raw_response_displayed=True,
        secret_scan_passed=False,
    )


@dataclass(frozen=True)
class _ParsedProvidedCommand:
    tokens: tuple[str, ...]
    token_names: tuple[str, ...]
    fields: dict[str, str]


def _parse_provided_command(command: str) -> _ParsedProvidedCommand:
    tokens = tuple(command.split(" ")) if command else ()
    fields: dict[str, str] = {}
    token_names: list[str] = []
    for token in tokens:
        if token == "APPROVE_FX_STEP6B_ARTIFACT":
            token_names.append(token)
            continue
        if "=" in token:
            key, value = token.split("=", 1)
            token_names.append(key)
            fields.setdefault(key, value)
        elif token:
            token_names.append(token)
    return _ParsedProvidedCommand(
        tokens=tokens,
        token_names=tuple(token_names),
        fields=fields,
    )


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalArtifactValidationCheckResult:
    return LiveOrderRealApprovalArtifactValidationCheckResult(
        name=name,
        passed=passed,
        reason=reason,
        sanitized_value=sanitized_value,
        expected=expected,
    )


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return tuple(merged)


def _add_reason(
    reasons: list[str],
    reason: LiveOrderRealApprovalArtifactValidationBlockReason,
) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


def _expires_at_or_created(
    artifact: LiveOrderRealApprovalArtifact | None,
    created_at: datetime,
) -> datetime:
    value = getattr(artifact, "expires_at", created_at)
    return value if isinstance(value, datetime) else created_at


def _is_one_line(value: str) -> bool:
    return value != "" and "\n" not in value and "\r" not in value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _text_from(obj: object, field_name: str) -> str:
    value = getattr(obj, field_name, None)
    if isinstance(value, str) and value:
        return value
    return "missing"


def _int_from(obj: object, field_name: str) -> int:
    value = getattr(obj, field_name, None)
    return value if type(value) is int else 0


def _int_text(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{label} must be non-empty")


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime value is required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value
