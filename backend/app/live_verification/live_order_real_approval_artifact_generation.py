"""Step 6B dry-run approval artifact generation.

This module may generate an internal approval artifact for a future validation
step. It does not display copyable approval text, issue a gate, call APIs, or
authorize live execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from app.live_verification.errors import LiveVerificationValidationError
from app.live_verification.live_order_approval_gate_design import APPROVAL_GATE_TTL_SECONDS
from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
    LiveOrderCandidateSide,
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
    LiveOrderRealApprovalGateEnablementState,
    LiveOrderRealApprovalGateEnablementStateStatus,
)
from app.live_verification.precheck import SUPPORTED_SYMBOL

SourceStatus = LiveOrderRealApprovalGateEnablementStateStatus

LIVE_ORDER_REAL_APPROVAL_ARTIFACT_ID_PREFIX = "LORAA6B-"
LIVE_ORDER_REAL_APPROVAL_ID_PREFIX = "LORAID6B-"
STEP6B_REQUEST_SCOPE_LABEL = (
    "approval_artifact_generation_only_no_api_no_post_no_copyable_display"
)
APPROVAL_COMMAND_TEMPLATE_VERSION = "step6b_artifact_v1"
APPROVAL_COMMAND_DISPLAY_MODE = "redacted_only_in_step6b"
SOURCE_ENABLEMENT_STATE_MAX_AGE_SECONDS = 300
NOT_GENERATED = "not_generated"

REQUIRED_STEP6B_APPROVAL_ACK_TOKENS = (
    "ACK_RISK=YES",
    "ACK_NO_POST_IN_STEP6B=YES",
    "ACK_NO_API_IN_STEP6B=YES",
    "ACK_NO_LIVE_ORDER_ONCE=YES",
    "ACK_NO_RETRY=YES",
    "ACK_NO_LOOP=YES",
    "ACK_NO_ADD=YES",
    "ACK_NO_CHANGE=YES",
    "ACK_NO_CANCEL=YES",
    "ACK_NO_CLOSE=YES",
    "ACK_UNKNOWN_MEANS_STOP=YES",
)

DEFAULT_FUTURE_STEP6C_HANDOFF_CONDITIONS = (
    "user explicitly requests Step 6C",
    "Step 6C remains no API and no POST unless separately scoped",
    "Step 6C validates approval artifact exact match",
    "Step 6C may compare user-provided command with generated command",
    "Step 6C must enforce TTL 300 seconds",
    "Step 6C must enforce same session",
    "Step 6C must enforce one-line command",
    "Step 6C must reject newline / extra token / missing ACK token",
    "Step 6C must keep allowed_for_live=false",
    "Step 6D or later required for real API preflight",
    "Step 6E or later required for any POST",
)

DEFAULT_FUTURE_STEP6C_BLOCKERS = (
    "no explicit Step 6C request",
    "artifact missing or blocked",
    "approval command expired",
    "same session cannot be confirmed",
    "command fingerprint mismatch",
    "approval command contains newline",
    "approval command contains extra token",
    "ACK tokens incomplete",
    "any API/broker/live_order_once called unexpectedly",
    "any secret/raw/real ID exposure risk",
    "any need for retry/loop/add/change/cancel/close",
)


class LiveOrderRealApprovalArtifactGenerationStatus(str, Enum):
    APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST = (
        "APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST"
    )
    BLOCKED_STEP6B_ARTIFACT_REQUEST = "BLOCKED_STEP6B_ARTIFACT_REQUEST"
    BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT = (
        "BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT"
    )
    BLOCKED_STEP6B_SOURCE_ENABLEMENT_STATE = "BLOCKED_STEP6B_SOURCE_ENABLEMENT_STATE"
    BLOCKED_STEP6B_UNSAFE_MISMATCH = "BLOCKED_STEP6B_UNSAFE_MISMATCH"


ArtifactStatus = LiveOrderRealApprovalArtifactGenerationStatus


class LiveOrderRealApprovalArtifactGenerationBlockReason(str, Enum):
    MISSING_SOURCE_ENABLEMENT_STATE = "missing_source_enablement_state"
    SOURCE_ENABLEMENT_STATE_NOT_READY = "source_enablement_state_not_ready"
    SOURCE_ENABLEMENT_STATE_NOT_ELIGIBLE = "source_enablement_state_not_eligible"
    SOURCE_GATE_NOT_ENABLED = "source_gate_not_enabled"
    SOURCE_ALLOWS_LIVE = "source_allows_live"
    SOURCE_NOT_DRY_RUN = "source_not_dry_run"
    SOURCE_GATE_ALREADY_ISSUED = "source_gate_already_issued"
    SOURCE_APPROVAL_ID_ALREADY_GENERATED = "source_approval_id_already_generated"
    SOURCE_APPROVAL_COMMAND_ALREADY_GENERATED = (
        "source_approval_command_already_generated"
    )
    SOURCE_APPROVAL_COMMAND_COPYABLE = "source_approval_command_copyable"
    SOURCE_APPROVAL_COMMAND_EXECUTABLE = "source_approval_command_executable"
    SOURCE_USABLE_APPROVAL_ARTIFACTS_GENERATED = (
        "source_usable_approval_artifacts_generated"
    )
    SOURCE_REAL_APPROVAL_ARTIFACTS_AVAILABLE = (
        "source_real_approval_artifacts_available"
    )
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
    MISSING_ARTIFACT_REQUEST_SNAPSHOT = "missing_artifact_request_snapshot"
    EXPLICIT_STEP6B_REQUEST_MISSING = "explicit_step6b_request_missing"
    OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED = (
        "operator_real_money_risk_not_acknowledged"
    )
    OPERATOR_NO_API_NOT_ACKNOWLEDGED = "operator_no_api_not_acknowledged"
    OPERATOR_NO_POST_NOT_ACKNOWLEDGED = "operator_no_post_not_acknowledged"
    OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED = (
        "operator_no_live_order_once_not_acknowledged"
    )
    OPERATOR_ARTIFACT_GENERATION_ONLY_NOT_ACKNOWLEDGED = (
        "operator_artifact_generation_only_not_acknowledged"
    )
    OPERATOR_NO_COPYABLE_COMMAND_NOT_ACKNOWLEDGED = (
        "operator_no_copyable_command_not_acknowledged"
    )
    OPERATOR_STEP6C_VALIDATION_NOT_ACKNOWLEDGED = (
        "operator_step6c_validation_not_acknowledged"
    )
    OPERATOR_STEP6D_PREFLIGHT_NOT_ACKNOWLEDGED = (
        "operator_step6d_preflight_not_acknowledged"
    )
    OPERATOR_STEP6E_POST_NOT_ACKNOWLEDGED = "operator_step6e_post_not_acknowledged"
    OPERATOR_UNKNOWN_MEANS_STOP_NOT_ACKNOWLEDGED = (
        "operator_unknown_means_stop_not_acknowledged"
    )
    INVALID_REQUEST_SCOPE_LABEL = "invalid_request_scope_label"
    MISSING_ARTIFACT_SAFETY_SNAPSHOT = "missing_artifact_safety_snapshot"
    SOURCE_ENABLEMENT_STATE_STALE = "source_enablement_state_stale"
    SAFETY_GATE_NOT_ENABLED = "safety_gate_not_enabled"
    SAFETY_ALLOWS_LIVE = "safety_allows_live"
    SAFETY_GATE_ALREADY_ISSUED = "safety_gate_already_issued"
    PRIOR_APPROVAL_ID_ALREADY_GENERATED = "prior_approval_id_already_generated"
    PRIOR_APPROVAL_COMMAND_ALREADY_GENERATED = (
        "prior_approval_command_already_generated"
    )
    PRIOR_APPROVAL_COMMAND_COPYABLE = "prior_approval_command_copyable"
    PRIOR_APPROVAL_COMMAND_EXECUTABLE = "prior_approval_command_executable"
    PRIOR_USABLE_APPROVAL_ARTIFACTS_GENERATED = (
        "prior_usable_approval_artifacts_generated"
    )
    PRIOR_REAL_APPROVAL_ARTIFACTS_AVAILABLE = (
        "prior_real_approval_artifacts_available"
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
    APPROVAL_COMMAND_NOT_ONE_LINE = "approval_command_not_one_line"
    APPROVAL_COMMAND_MISSING_ACK_TOKEN = "approval_command_missing_ack_token"
    APPROVAL_COMMAND_MISSING_ID = "approval_command_missing_id"
    APPROVAL_COMMAND_SHA256_MISSING = "approval_command_sha256_missing"
    APPROVAL_COMMAND_FINGERPRINT_MISSING = "approval_command_fingerprint_missing"
    APPROVAL_COMMAND_REDACTION_MISSING = "approval_command_redaction_missing"
    MISSING_FUTURE_STEP6C_HANDOFF_CONDITIONS = (
        "missing_future_step6c_handoff_conditions"
    )
    MISSING_FUTURE_STEP6C_BLOCKERS = "missing_future_step6c_blockers"


BlockReason = LiveOrderRealApprovalArtifactGenerationBlockReason


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactGenerationRequestSnapshot:
    request_id: str
    created_at: datetime
    explicit_step6b_user_instruction_received: bool
    operator_understands_real_money_risk: bool
    operator_understands_no_api_in_step6b: bool
    operator_understands_no_post_in_step6b: bool
    operator_understands_no_live_order_once_in_step6b: bool
    operator_understands_approval_artifact_generation_only: bool
    operator_understands_approval_command_not_copyable_in_step6b: bool
    operator_understands_step6c_required_for_validation: bool
    operator_understands_step6d_or_later_required_for_api_preflight: bool
    operator_understands_step6e_or_later_required_for_post: bool
    operator_understands_unknown_means_stop: bool
    request_scope_label: str

    def __post_init__(self) -> None:
        _require_non_empty("request_id", self.request_id)
        _ensure_aware(self.created_at)
        _require_non_empty("request_scope_label", self.request_scope_label)
        for field_name in (
            "explicit_step6b_user_instruction_received",
            "operator_understands_real_money_risk",
            "operator_understands_no_api_in_step6b",
            "operator_understands_no_post_in_step6b",
            "operator_understands_no_live_order_once_in_step6b",
            "operator_understands_approval_artifact_generation_only",
            "operator_understands_approval_command_not_copyable_in_step6b",
            "operator_understands_step6c_required_for_validation",
            "operator_understands_step6d_or_later_required_for_api_preflight",
            "operator_understands_step6e_or_later_required_for_post",
            "operator_understands_unknown_means_stop",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise LiveVerificationValidationError(f"{field_name} must be bool")


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactGenerationSafetySnapshot:
    safety_snapshot_id: str
    created_at: datetime
    source_enablement_state_age_seconds: float
    source_enablement_state_max_age_seconds: float
    approval_gate_enabled: bool
    allowed_for_live: bool
    approval_gate_issued: bool
    approval_id_generated_before_step6b: bool
    approval_command_generated_before_step6b: bool
    approval_command_copyable_before_step6b: bool
    approval_command_executable_before_step6b: bool
    usable_approval_artifacts_generated_before_step6b: bool
    real_approval_artifacts_available_before_step6b: bool
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
            "approval_gate_enabled",
            "allowed_for_live",
            "approval_gate_issued",
            "approval_id_generated_before_step6b",
            "approval_command_generated_before_step6b",
            "approval_command_copyable_before_step6b",
            "approval_command_executable_before_step6b",
            "usable_approval_artifacts_generated_before_step6b",
            "real_approval_artifacts_available_before_step6b",
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
        for field_name in (
            "source_enablement_state_age_seconds",
            "source_enablement_state_max_age_seconds",
            "market_hours_snapshot_age_seconds",
            "market_hours_snapshot_max_age_seconds",
            "fresh_pre_approval_preflight_age_seconds",
            "fresh_pre_approval_preflight_max_age_seconds",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise LiveVerificationValidationError(f"{field_name} must be number")
        for field_name in ("open_positions_count", "active_orders_count"):
            if type(getattr(self, field_name)) is not int:
                raise LiveVerificationValidationError(f"{field_name} must be int")


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactGenerationCheckResult:
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
class LiveOrderRealApprovalArtifactGenerationSection:
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
class LiveOrderRealApprovalArtifact:
    artifact_id: str
    created_at: datetime
    source_enablement_state_id: str
    source_plan_id: str
    criteria_id: str
    symbol: str
    side: str
    size: int
    execution_type: str
    source_type: str
    strategy_name: str
    artifact_status: LiveOrderRealApprovalArtifactGenerationStatus
    artifact_ready: bool
    eligible_for_step6c_validation: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_issued: bool
    approval_artifact_generated: bool
    approval_id_generated: bool
    approval_id: str
    approval_id_redacted: str
    approval_id_fingerprint: str
    approval_id_display_allowed: bool
    approval_command_generated: bool
    approval_command: str
    approval_command_sha256: str
    approval_command_fingerprint: str
    approval_command_redacted: str
    approval_command_template_version: str
    approval_command_one_line: bool
    approval_command_exact_match_required: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_display_mode: str
    approval_command_persisted: bool
    approval_command_copied_to_clipboard: bool
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
    approval_validation_deferred_to_step6c: bool
    api_preflight_deferred_to_step6d_or_later: bool
    post_deferred_to_step6e_or_later: bool
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
    artifact_generation_request_snapshot: (
        LiveOrderRealApprovalArtifactGenerationRequestSnapshot
    )
    artifact_generation_safety_snapshot: LiveOrderRealApprovalArtifactGenerationSafetySnapshot
    future_step6c_handoff_conditions: tuple[str, ...]
    future_step6c_blockers: tuple[str, ...]
    check_results: tuple[LiveOrderRealApprovalArtifactGenerationCheckResult, ...]
    blocked_reasons: tuple[str, ...]
    summary: str
    recommended_next_step: str
    sections: tuple[LiveOrderRealApprovalArtifactGenerationSection, ...]

    def __post_init__(self) -> None:
        _validate_artifact(self)


@dataclass(frozen=True)
class LiveOrderRealApprovalArtifactGenerationBuildResult:
    artifact: LiveOrderRealApprovalArtifact
    artifact_id: str
    artifact_status: LiveOrderRealApprovalArtifactGenerationStatus
    artifact_ready: bool
    eligible_for_step6c_validation: bool
    allowed_for_live: bool
    approval_gate_enabled: bool
    approval_gate_issued: bool
    approval_artifact_generated: bool
    approval_id_generated: bool
    approval_command_generated: bool
    approval_command_copyable: bool
    approval_command_displayed: bool
    approval_command_persisted: bool
    approval_command_copied_to_clipboard: bool
    approval_command_executable: bool
    usable_approval_artifacts_generated: bool
    real_approval_artifacts_available: bool
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
        if self.artifact.artifact_id != self.artifact_id:
            raise LiveVerificationValidationError("artifact_id mismatch")
        if self.artifact.artifact_status is not self.artifact_status:
            raise LiveVerificationValidationError("artifact_status mismatch")
        if self.artifact.artifact_ready is not self.artifact_ready:
            raise LiveVerificationValidationError("artifact_ready mismatch")
        if self.artifact.allowed_for_live is not False or self.allowed_for_live is not False:
            raise LiveVerificationValidationError("allowed_for_live must be False")
        for field_name in (
            "approval_gate_issued",
            "approval_command_copyable",
            "approval_command_displayed",
            "approval_command_persisted",
            "approval_command_copied_to_clipboard",
            "approval_command_executable",
            "real_approval_artifacts_available",
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
        if self.artifact.blocked_reasons != self.blocked_reasons:
            raise LiveVerificationValidationError("blocked_reasons mismatch")
        if self.artifact.recommended_next_step != self.recommended_next_step:
            raise LiveVerificationValidationError("recommended_next_step mismatch")


def build_live_order_real_approval_artifact(
    *,
    source_enablement_state: LiveOrderRealApprovalGateEnablementState | None,
    artifact_generation_request_snapshot: (
        LiveOrderRealApprovalArtifactGenerationRequestSnapshot | None
    ),
    artifact_generation_safety_snapshot: (
        LiveOrderRealApprovalArtifactGenerationSafetySnapshot | None
    ),
    created_at: datetime | None = None,
    same_session_label: str = "step6b_same_session",
    future_step6c_handoff_conditions: tuple[
        str,
        ...,
    ] = DEFAULT_FUTURE_STEP6C_HANDOFF_CONDITIONS,
    future_step6c_blockers: tuple[str, ...] = DEFAULT_FUTURE_STEP6C_BLOCKERS,
) -> LiveOrderRealApprovalArtifactGenerationBuildResult:
    """Build a Step 6B approval artifact without displaying or executing it."""
    created = _ensure_aware(created_at or datetime.now(UTC))
    _require_non_empty("same_session_label", same_session_label)
    source_reasons = _source_state_blocked_reasons(source_enablement_state)
    request_reasons = _request_blocked_reasons(artifact_generation_request_snapshot)
    safety_reasons = _safety_blocked_reasons(artifact_generation_safety_snapshot)
    condition_reasons = _condition_blocked_reasons(
        future_step6c_handoff_conditions=future_step6c_handoff_conditions,
        future_step6c_blockers=future_step6c_blockers,
    )
    ready_source = not source_reasons
    ready_request = not request_reasons
    ready_safety = not safety_reasons
    generated = ready_source and ready_request and ready_safety and not condition_reasons
    if _source_state_is_blocked(source_enablement_state, source_reasons):
        status = ArtifactStatus.BLOCKED_STEP6B_SOURCE_ENABLEMENT_STATE
        recommended_next_step = "fix_step6a_enablement_state_blockers_no_api_no_post"
        summary = "blocked Step 6B artifact by source Step 6A enablement state"
    elif request_reasons:
        status = ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_REQUEST
        recommended_next_step = (
            "provide_explicit_step6b_request_and_acknowledgements_no_api_no_post"
        )
        summary = "blocked Step 6B artifact by request acknowledgements"
    elif safety_reasons:
        status = ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT
        recommended_next_step = (
            "rerun_sanitized_artifact_generation_safety_snapshot_no_api_no_post"
        )
        summary = "blocked Step 6B artifact by sanitized safety snapshot"
    elif source_reasons or condition_reasons:
        status = ArtifactStatus.BLOCKED_STEP6B_UNSAFE_MISMATCH
        recommended_next_step = "fix_step6b_unsafe_mismatch_no_api_no_post"
        summary = "blocked Step 6B artifact by unsafe mismatch"
    else:
        status = ArtifactStatus.APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST
        recommended_next_step = (
            "stop_and_wait_for_explicit_step6c_approval_artifact_validation_request_no_api_no_post"
        )
        summary = (
            "Step 6B generated an internal approval artifact for future Step 6C "
            "validation only; live POST remains unavailable"
        )
    blocked_reasons = _merge_reasons(
        source_reasons,
        _source_state_existing_reasons(source_enablement_state),
        request_reasons,
        safety_reasons,
        condition_reasons,
    )
    safe_request = _request_or_empty(artifact_generation_request_snapshot, created)
    safe_safety = _safety_or_empty(artifact_generation_safety_snapshot, created)
    source_id = _text_from(source_enablement_state, "enablement_state_id")
    approval_id = (
        make_live_order_real_approval_id(
            source_enablement_state_id=source_id,
            symbol=_text_from(source_enablement_state, "symbol"),
            side=_text_from(source_enablement_state, "side"),
            size=_int_from(source_enablement_state, "size"),
            execution_type=_text_from(source_enablement_state, "execution_type"),
            same_session_label=same_session_label,
            created_at=created,
        )
        if generated
        else NOT_GENERATED
    )
    approval_command = (
        make_live_order_real_approval_command(
            approval_id=approval_id,
            symbol=_text_from(source_enablement_state, "symbol"),
            side=_text_from(source_enablement_state, "side"),
            size=_int_from(source_enablement_state, "size"),
            execution_type=_text_from(source_enablement_state, "execution_type"),
            ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
            same_session_label=same_session_label,
            required_ack_tokens=REQUIRED_STEP6B_APPROVAL_ACK_TOKENS,
        )
        if generated
        else NOT_GENERATED
    )
    approval_command_sha256 = (
        hashlib.sha256(approval_command.encode()).hexdigest() if generated else NOT_GENERATED
    )
    approval_command_fingerprint = (
        fingerprint_live_order_real_approval_command(approval_command)
        if generated
        else NOT_GENERATED
    )
    approval_id_fingerprint = (
        hashlib.sha256(approval_id.encode()).hexdigest()[:16].upper()
        if generated
        else NOT_GENERATED
    )
    approval_id_redacted = (
        f"{LIVE_ORDER_REAL_APPROVAL_ID_PREFIX}<redacted:{approval_id_fingerprint}>"
        if generated
        else NOT_GENERATED
    )
    approval_command_redacted = (
        redact_live_order_real_approval_command(
            approval_command,
            approval_id_fingerprint=approval_id_fingerprint,
            ack_count=len(REQUIRED_STEP6B_APPROVAL_ACK_TOKENS),
        )
        if generated
        else NOT_GENERATED
    )
    command_reasons = _command_blocked_reasons(
        approval_id=approval_id,
        approval_command=approval_command,
        approval_command_sha256=approval_command_sha256,
        approval_command_fingerprint=approval_command_fingerprint,
        approval_command_redacted=approval_command_redacted,
        command_generated=generated,
    )
    if command_reasons:
        status = ArtifactStatus.BLOCKED_STEP6B_UNSAFE_MISMATCH
        generated = False
        recommended_next_step = "fix_step6b_approval_artifact_shape_no_api_no_post"
        summary = "blocked Step 6B artifact by approval artifact shape"
    blocked_reasons = _merge_reasons(blocked_reasons, command_reasons)
    check_results = _build_check_results(
        source_enablement_state=source_enablement_state,
        request_snapshot=artifact_generation_request_snapshot,
        safety_snapshot=artifact_generation_safety_snapshot,
        future_step6c_handoff_conditions=future_step6c_handoff_conditions,
        future_step6c_blockers=future_step6c_blockers,
        approval_id_generated=generated,
        approval_command_generated=generated,
        approval_command=approval_command,
        approval_command_sha256=approval_command_sha256,
        approval_command_fingerprint=approval_command_fingerprint,
        approval_command_redacted=approval_command_redacted,
    )
    artifact_id = make_live_order_real_approval_artifact_id(
        source_enablement_state_id=source_id,
        request_id=safe_request.request_id,
        safety_snapshot_id=safe_safety.safety_snapshot_id,
        created_at=created,
        artifact_status=status,
        blocked_reasons=blocked_reasons,
    )
    artifact = LiveOrderRealApprovalArtifact(
        artifact_id=artifact_id,
        created_at=created,
        source_enablement_state_id=source_id,
        source_plan_id=_text_from(source_enablement_state, "source_plan_id"),
        criteria_id=_text_from(source_enablement_state, "criteria_id"),
        symbol=_text_from(source_enablement_state, "symbol"),
        side=_text_from(source_enablement_state, "side"),
        size=_int_from(source_enablement_state, "size"),
        execution_type=_text_from(source_enablement_state, "execution_type"),
        source_type=_text_from(source_enablement_state, "source_type"),
        strategy_name=_text_from(source_enablement_state, "strategy_name"),
        artifact_status=status,
        artifact_ready=generated,
        eligible_for_step6c_validation=generated,
        allowed_for_live=False,
        approval_gate_enabled=generated,
        approval_gate_issued=False,
        approval_artifact_generated=generated,
        approval_id_generated=generated,
        approval_id=approval_id,
        approval_id_redacted=approval_id_redacted,
        approval_id_fingerprint=approval_id_fingerprint,
        approval_id_display_allowed=False,
        approval_command_generated=generated,
        approval_command=approval_command,
        approval_command_sha256=approval_command_sha256,
        approval_command_fingerprint=approval_command_fingerprint,
        approval_command_redacted=approval_command_redacted,
        approval_command_template_version=APPROVAL_COMMAND_TEMPLATE_VERSION,
        approval_command_one_line=_is_one_line(approval_command) if generated else False,
        approval_command_exact_match_required=True,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_display_mode=APPROVAL_COMMAND_DISPLAY_MODE,
        approval_command_persisted=False,
        approval_command_copied_to_clipboard=False,
        approval_command_executable=False,
        usable_approval_artifacts_generated=generated,
        real_approval_artifacts_available=False,
        approval_validation_deferred_to_step6c=True,
        api_preflight_deferred_to_step6d_or_later=True,
        post_deferred_to_step6e_or_later=True,
        dry_run_only=True,
        requires_human_approval=True,
        explicit_user_confirmation_required=True,
        ttl_seconds=APPROVAL_GATE_TTL_SECONDS,
        expires_at=created + timedelta(seconds=APPROVAL_GATE_TTL_SECONDS),
        same_session_required=True,
        same_session_label=same_session_label,
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
        artifact_generation_request_snapshot=safe_request,
        artifact_generation_safety_snapshot=safe_safety,
        future_step6c_handoff_conditions=future_step6c_handoff_conditions,
        future_step6c_blockers=future_step6c_blockers,
        check_results=check_results,
        blocked_reasons=blocked_reasons,
        summary=summary,
        recommended_next_step=recommended_next_step,
        sections=_build_sections(
            check_results=check_results,
            blocked_reasons=blocked_reasons,
            recommended_next_step=recommended_next_step,
            future_step6c_handoff_conditions=future_step6c_handoff_conditions,
            future_step6c_blockers=future_step6c_blockers,
        ),
    )
    return LiveOrderRealApprovalArtifactGenerationBuildResult(
        artifact=artifact,
        artifact_id=artifact.artifact_id,
        artifact_status=artifact.artifact_status,
        artifact_ready=artifact.artifact_ready,
        eligible_for_step6c_validation=artifact.eligible_for_step6c_validation,
        allowed_for_live=False,
        approval_gate_enabled=artifact.approval_gate_enabled,
        approval_gate_issued=False,
        approval_artifact_generated=artifact.approval_artifact_generated,
        approval_id_generated=artifact.approval_id_generated,
        approval_command_generated=artifact.approval_command_generated,
        approval_command_copyable=False,
        approval_command_displayed=False,
        approval_command_persisted=False,
        approval_command_copied_to_clipboard=False,
        approval_command_executable=False,
        usable_approval_artifacts_generated=artifact.usable_approval_artifacts_generated,
        real_approval_artifacts_available=False,
        post_allowed_this_step=False,
        post_executed=False,
        live_order_once_called=False,
        private_api_called=False,
        broker_called=False,
        read_only_api_called=False,
        public_api_called=False,
        blocked_reasons=artifact.blocked_reasons,
        recommended_next_step=artifact.recommended_next_step,
    )


def render_live_order_real_approval_artifact_markdown(
    artifact: LiveOrderRealApprovalArtifact,
) -> str:
    """Render a sanitized Step 6B artifact without full approval command text."""
    blocked_text = ", ".join(artifact.blocked_reasons) or "none"
    ack_lines = "\n".join(f"- {token}" for token in artifact.required_ack_tokens)
    handoff_lines = "\n".join(
        f"- {item}" for item in artifact.future_step6c_handoff_conditions
    )
    blocker_lines = "\n".join(f"- {item}" for item in artifact.future_step6c_blockers)
    check_lines = "\n".join(
        (
            f"- {check.name}: passed={check.passed}, value={check.sanitized_value}, "
            f"expected={check.expected}"
        )
        for check in artifact.check_results
    )
    safety = artifact.artifact_generation_safety_snapshot
    return "\n".join(
        (
            "# Step 6B Real Approval Artifact Generation",
            "",
            "This Step 6B approval artifact generation is dry-run only.",
            "This Step 6B artifact does not authorize live POST.",
            "This Step 6B artifact keeps allowed_for_live=false.",
            "This Step 6B artifact does not issue a real approval gate.",
            (
                "This Step 6B artifact may generate an internal approval_id and "
                "approval_command for future Step 6C validation only."
            ),
            "This Step 6B renderer does not display the full approval command.",
            "This Step 6B renderer does not provide copyable approval text.",
            "This Step 6B artifact does not call read-only API.",
            "This Step 6B artifact does not call public API.",
            "This Step 6B artifact does not call Private API.",
            "This Step 6B artifact does not call live_order_once.",
            "This Step 6B artifact does not execute HTTP POST.",
            "",
            f"artifact_id: {artifact.artifact_id}",
            f"source_enablement_state_id: {artifact.source_enablement_state_id}",
            f"source_plan_id: {artifact.source_plan_id}",
            f"criteria_id: {artifact.criteria_id}",
            f"source_type: {artifact.source_type}",
            f"strategy_name: {artifact.strategy_name}",
            f"symbol: {artifact.symbol}",
            f"side: {artifact.side}",
            f"size: {artifact.size}",
            f"executionType: {artifact.execution_type}",
            f"artifact_status: {artifact.artifact_status.value}",
            f"artifact_ready: {artifact.artifact_ready}",
            f"eligible_for_step6c_validation: {artifact.eligible_for_step6c_validation}",
            f"approval_gate_enabled: {artifact.approval_gate_enabled}",
            f"allowed_for_live: {artifact.allowed_for_live}",
            f"approval_gate_issued: {artifact.approval_gate_issued}",
            f"approval_id_generated: {artifact.approval_id_generated}",
            f"approval_id_redacted: {artifact.approval_id_redacted}",
            f"approval_id_fingerprint: {artifact.approval_id_fingerprint}",
            f"approval_id_display_allowed: {artifact.approval_id_display_allowed}",
            f"approval_command_generated: {artifact.approval_command_generated}",
            f"approval_command_sha256: {artifact.approval_command_sha256}",
            f"approval_command_fingerprint: {artifact.approval_command_fingerprint}",
            f"approval_command_redacted: {artifact.approval_command_redacted}",
            (
                "approval_command_template_version: "
                f"{artifact.approval_command_template_version}"
            ),
            f"approval_command_one_line: {artifact.approval_command_one_line}",
            (
                "approval_command_exact_match_required: "
                f"{artifact.approval_command_exact_match_required}"
            ),
            f"approval_command_copyable: {artifact.approval_command_copyable}",
            f"approval_command_displayed: {artifact.approval_command_displayed}",
            f"approval_command_display_mode: {artifact.approval_command_display_mode}",
            f"approval_command_persisted: {artifact.approval_command_persisted}",
            (
                "approval_command_copied_to_clipboard: "
                f"{artifact.approval_command_copied_to_clipboard}"
            ),
            f"approval_command_executable: {artifact.approval_command_executable}",
            f"usable_approval_artifacts_generated: {artifact.usable_approval_artifacts_generated}",
            f"real_approval_artifacts_available: {artifact.real_approval_artifacts_available}",
            f"ttl_seconds: {artifact.ttl_seconds}",
            f"expires_at: {artifact.expires_at.isoformat()}",
            f"same_session_required: {artifact.same_session_required}",
            f"same_session_label: {artifact.same_session_label}",
            f"post_allowed_this_step: {artifact.post_allowed_this_step}",
            f"post_attempt_limit: {artifact.post_attempt_limit}",
            f"post_executed: {artifact.post_executed}",
            f"blocked_reasons: {blocked_text}",
            f"recommended_next_step: {artifact.recommended_next_step}",
            "",
            "## Sanitized Safety Summary",
            (
                "- source_enablement_state_age_seconds: "
                f"{safety.source_enablement_state_age_seconds}"
            ),
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
            "## Future Step 6C Handoff Conditions",
            handoff_lines,
            "",
            "## Future Step 6C Blockers",
            blocker_lines,
            "",
            "## Check Results",
            check_lines,
        ),
    )


def make_live_order_real_approval_artifact_id(
    *,
    source_enablement_state_id: str,
    request_id: str,
    safety_snapshot_id: str,
    created_at: datetime,
    artifact_status: LiveOrderRealApprovalArtifactGenerationStatus,
    blocked_reasons: tuple[str, ...],
) -> str:
    id_material = {
        "artifact_status": artifact_status.value,
        "blocked_reasons": list(blocked_reasons),
        "created_at": _ensure_aware(created_at).isoformat(),
        "request_id": request_id,
        "safety_snapshot_id": safety_snapshot_id,
        "source_enablement_state_id": source_enablement_state_id,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:12].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_ARTIFACT_ID_PREFIX}{digest}"


def make_live_order_real_approval_id(
    *,
    source_enablement_state_id: str,
    symbol: str,
    side: str,
    size: int,
    execution_type: str,
    same_session_label: str,
    created_at: datetime,
) -> str:
    id_material = {
        "created_at": _ensure_aware(created_at).isoformat(),
        "execution_type": execution_type,
        "same_session_label": same_session_label,
        "side": side,
        "size": size,
        "source_enablement_state_id": source_enablement_state_id,
        "symbol": symbol,
    }
    digest = hashlib.sha256(
        json.dumps(id_material, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()[:16].upper()
    return f"{LIVE_ORDER_REAL_APPROVAL_ID_PREFIX}{digest}"


def make_live_order_real_approval_command(
    *,
    approval_id: str,
    symbol: str,
    side: str,
    size: int,
    execution_type: str,
    ttl_seconds: int,
    same_session_label: str,
    required_ack_tokens: tuple[str, ...] = REQUIRED_STEP6B_APPROVAL_ACK_TOKENS,
) -> str:
    _require_non_empty("approval_id", approval_id)
    _require_non_empty("symbol", symbol)
    _require_non_empty("side", side)
    _require_non_empty("execution_type", execution_type)
    _require_non_empty("same_session_label", same_session_label)
    tokens = (
        "APPROVE_FX_STEP6B_ARTIFACT",
        f"approval_id={approval_id}",
        f"symbol={symbol}",
        f"side={side}",
        f"size={size}",
        f"executionType={execution_type}",
        f"ttl_seconds={ttl_seconds}",
        f"same_session={same_session_label}",
        *required_ack_tokens,
    )
    command = " ".join(tokens)
    if not _is_one_line(command):
        raise LiveVerificationValidationError("approval command must be one-line")
    return command


def redact_live_order_real_approval_command(
    command: str,
    *,
    approval_id_fingerprint: str,
    ack_count: int,
) -> str:
    """Return a non-copyable representation that never includes the full command."""
    _require_non_empty("command", command)
    _require_non_empty("approval_id_fingerprint", approval_id_fingerprint)
    return (
        "APPROVE_FX_STEP6B_ARTIFACT "
        f"approval_id=<redacted:{approval_id_fingerprint}> "
        "symbol=<sanitized> side=<sanitized> size=<sanitized> "
        "executionType=<sanitized> ttl_seconds=300 same_session=<redacted> "
        f"ack_count={ack_count}"
    )


def fingerprint_live_order_real_approval_command(command: str) -> str:
    _require_non_empty("command", command)
    return hashlib.sha256(command.encode()).hexdigest()[:16].upper()


def _source_state_blocked_reasons(
    state: LiveOrderRealApprovalGateEnablementState | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(state, LiveOrderRealApprovalGateEnablementState):
        _add_reason(reasons, BlockReason.MISSING_SOURCE_ENABLEMENT_STATE)
        return tuple(reasons)
    if (
        state.enablement_status is not SourceStatus.REAL_APPROVAL_GATE_ENABLED_NO_ARTIFACTS
        or state.enablement_state_ready is not True
    ):
        _add_reason(reasons, BlockReason.SOURCE_ENABLEMENT_STATE_NOT_READY)
    if state.eligible_for_future_step6b_approval_artifact_generation is not True:
        _add_reason(reasons, BlockReason.SOURCE_ENABLEMENT_STATE_NOT_ELIGIBLE)
    if state.approval_gate_enabled is not True:
        _add_reason(reasons, BlockReason.SOURCE_GATE_NOT_ENABLED)
    if state.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SOURCE_ALLOWS_LIVE)
    if state.dry_run_only is not True:
        _add_reason(reasons, BlockReason.SOURCE_NOT_DRY_RUN)
    for flag, reason in (
        (state.approval_gate_issued, BlockReason.SOURCE_GATE_ALREADY_ISSUED),
        (
            state.approval_id_generated,
            BlockReason.SOURCE_APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            state.approval_command_generated,
            BlockReason.SOURCE_APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (state.approval_command_copyable, BlockReason.SOURCE_APPROVAL_COMMAND_COPYABLE),
        (
            state.approval_command_executable,
            BlockReason.SOURCE_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            state.usable_approval_artifacts_generated,
            BlockReason.SOURCE_USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            state.real_approval_artifacts_available,
            BlockReason.SOURCE_REAL_APPROVAL_ARTIFACTS_AVAILABLE,
        ),
        (state.post_allowed_this_step, BlockReason.SOURCE_POST_ALLOWED_THIS_STEP),
        (state.post_executed, BlockReason.SOURCE_POST_ALREADY_EXECUTED),
        (state.live_order_once_called, BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED),
        (state.private_api_called, BlockReason.PRIVATE_API_ALREADY_CALLED),
        (state.broker_called, BlockReason.BROKER_ALREADY_CALLED),
        (state.read_only_api_called, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        (state.public_api_called, BlockReason.PUBLIC_API_ALREADY_CALLED),
        (state.retry_allowed, BlockReason.RETRY_ALLOWED),
        (state.loop_allowed, BlockReason.LOOP_ALLOWED),
        (state.add_order_allowed, BlockReason.ADD_ORDER_ALLOWED),
        (state.change_order_allowed, BlockReason.CHANGE_ORDER_ALLOWED),
        (state.cancel_order_allowed, BlockReason.CANCEL_ORDER_ALLOWED),
        (state.close_order_allowed, BlockReason.CLOSE_ORDER_ALLOWED),
    ):
        if flag is not False:
            _add_reason(reasons, reason)
    if state.symbol != SUPPORTED_SYMBOL:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SYMBOL)
    if state.side not in {LiveOrderCandidateSide.BUY.value, LiveOrderCandidateSide.SELL.value}:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIDE)
    if state.size != LIVE_ORDER_CANDIDATE_SIZE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_SIZE)
    if state.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
        _add_reason(reasons, BlockReason.UNSUPPORTED_EXECUTION_TYPE)
    return tuple(reasons)


def _source_state_existing_reasons(
    state: LiveOrderRealApprovalGateEnablementState | None,
) -> tuple[str, ...]:
    if not isinstance(state, LiveOrderRealApprovalGateEnablementState):
        return ()
    return tuple(state.blocked_reasons)


def _request_blocked_reasons(
    snapshot: LiveOrderRealApprovalArtifactGenerationRequestSnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalArtifactGenerationRequestSnapshot):
        _add_reason(reasons, BlockReason.MISSING_ARTIFACT_REQUEST_SNAPSHOT)
        return tuple(reasons)
    for field_name, reason in (
        (
            "explicit_step6b_user_instruction_received",
            BlockReason.EXPLICIT_STEP6B_REQUEST_MISSING,
        ),
        (
            "operator_understands_real_money_risk",
            BlockReason.OPERATOR_REAL_MONEY_RISK_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_api_in_step6b",
            BlockReason.OPERATOR_NO_API_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_post_in_step6b",
            BlockReason.OPERATOR_NO_POST_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_no_live_order_once_in_step6b",
            BlockReason.OPERATOR_NO_LIVE_ORDER_ONCE_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_approval_artifact_generation_only",
            BlockReason.OPERATOR_ARTIFACT_GENERATION_ONLY_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_approval_command_not_copyable_in_step6b",
            BlockReason.OPERATOR_NO_COPYABLE_COMMAND_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6c_required_for_validation",
            BlockReason.OPERATOR_STEP6C_VALIDATION_NOT_ACKNOWLEDGED,
        ),
        (
            "operator_understands_step6d_or_later_required_for_api_preflight",
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
    if snapshot.request_scope_label != STEP6B_REQUEST_SCOPE_LABEL:
        _add_reason(reasons, BlockReason.INVALID_REQUEST_SCOPE_LABEL)
    return tuple(reasons)


def _safety_blocked_reasons(
    snapshot: LiveOrderRealApprovalArtifactGenerationSafetySnapshot | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not isinstance(snapshot, LiveOrderRealApprovalArtifactGenerationSafetySnapshot):
        _add_reason(reasons, BlockReason.MISSING_ARTIFACT_SAFETY_SNAPSHOT)
        return tuple(reasons)
    if (
        snapshot.source_enablement_state_age_seconds
        > snapshot.source_enablement_state_max_age_seconds
    ):
        _add_reason(reasons, BlockReason.SOURCE_ENABLEMENT_STATE_STALE)
    if snapshot.approval_gate_enabled is not True:
        _add_reason(reasons, BlockReason.SAFETY_GATE_NOT_ENABLED)
    if snapshot.allowed_for_live is not False:
        _add_reason(reasons, BlockReason.SAFETY_ALLOWS_LIVE)
    for flag, reason in (
        (snapshot.approval_gate_issued, BlockReason.SAFETY_GATE_ALREADY_ISSUED),
        (
            snapshot.approval_id_generated_before_step6b,
            BlockReason.PRIOR_APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            snapshot.approval_command_generated_before_step6b,
            BlockReason.PRIOR_APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            snapshot.approval_command_copyable_before_step6b,
            BlockReason.PRIOR_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            snapshot.approval_command_executable_before_step6b,
            BlockReason.PRIOR_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            snapshot.usable_approval_artifacts_generated_before_step6b,
            BlockReason.PRIOR_USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            snapshot.real_approval_artifacts_available_before_step6b,
            BlockReason.PRIOR_REAL_APPROVAL_ARTIFACTS_AVAILABLE,
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
    future_step6c_handoff_conditions: tuple[str, ...],
    future_step6c_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not future_step6c_handoff_conditions:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6C_HANDOFF_CONDITIONS)
    if not future_step6c_blockers:
        _add_reason(reasons, BlockReason.MISSING_FUTURE_STEP6C_BLOCKERS)
    return tuple(reasons)


def _command_blocked_reasons(
    *,
    approval_id: str,
    approval_command: str,
    approval_command_sha256: str,
    approval_command_fingerprint: str,
    approval_command_redacted: str,
    command_generated: bool,
) -> tuple[str, ...]:
    if not command_generated:
        return ()
    reasons: list[str] = []
    if approval_id not in approval_command:
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_MISSING_ID)
    if not _is_one_line(approval_command):
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_NOT_ONE_LINE)
    for token in REQUIRED_STEP6B_APPROVAL_ACK_TOKENS:
        if token not in approval_command:
            _add_reason(reasons, BlockReason.APPROVAL_COMMAND_MISSING_ACK_TOKEN)
    if len(approval_command_sha256) != 64:
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_SHA256_MISSING)
    if not approval_command_fingerprint or approval_command_fingerprint == NOT_GENERATED:
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_FINGERPRINT_MISSING)
    if not approval_command_redacted or approval_command_redacted == approval_command:
        _add_reason(reasons, BlockReason.APPROVAL_COMMAND_REDACTION_MISSING)
    return tuple(reasons)


def _build_check_results(
    *,
    source_enablement_state: LiveOrderRealApprovalGateEnablementState | None,
    request_snapshot: LiveOrderRealApprovalArtifactGenerationRequestSnapshot | None,
    safety_snapshot: LiveOrderRealApprovalArtifactGenerationSafetySnapshot | None,
    future_step6c_handoff_conditions: tuple[str, ...],
    future_step6c_blockers: tuple[str, ...],
    approval_id_generated: bool,
    approval_command_generated: bool,
    approval_command: str,
    approval_command_sha256: str,
    approval_command_fingerprint: str,
    approval_command_redacted: str,
) -> tuple[LiveOrderRealApprovalArtifactGenerationCheckResult, ...]:
    source_ready = not _source_state_blocked_reasons(source_enablement_state)
    request_ready = not _request_blocked_reasons(request_snapshot)
    safety_ready = not _safety_blocked_reasons(safety_snapshot)
    state = source_enablement_state
    safety = safety_snapshot
    no_api_called = isinstance(state, LiveOrderRealApprovalGateEnablementState) and all(
        getattr(state, field_name) is False
        for field_name in (
            "live_order_once_called",
            "private_api_called",
            "broker_called",
            "read_only_api_called",
            "public_api_called",
        )
    )
    return (
        _check(
            "source_enablement_state_ready",
            source_ready,
            "source Step 6A state must be ready",
            _bool_text(source_ready),
            "true",
        ),
        _check(
            "approval_gate_enabled_true_from_step6a",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.approval_gate_enabled is True,
            "approval_gate_enabled must be true from Step 6A only",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.approval_gate_enabled is True,
            ),
            "true",
        ),
        _check(
            "allowed_for_live_false",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.allowed_for_live is False,
            "allowed_for_live must remain false",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.allowed_for_live is False,
            ),
            "true",
        ),
        _check(
            "approval_gate_not_issued",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.approval_gate_issued is False,
            "Step 6B must not issue a real approval gate",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.approval_gate_issued is False,
            ),
            "true",
        ),
        _check(
            "no_prior_approval_id",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.approval_id_generated is False,
            "source must not already contain approval id",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.approval_id_generated is False,
            ),
            "true",
        ),
        _check(
            "no_prior_approval_command",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.approval_command_generated is False,
            "source must not already contain approval command",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.approval_command_generated is False,
            ),
            "true",
        ),
        _check(
            "no_prior_copyable_command",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.approval_command_copyable is False,
            "source must not contain copyable approval text",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.approval_command_copyable is False,
            ),
            "true",
        ),
        _check(
            "request_snapshot_ready",
            request_ready,
            "explicit Step 6B request and acknowledgements are required",
            _bool_text(request_ready),
            "true",
        ),
        _check(
            "safety_snapshot_fresh",
            safety_ready,
            "sanitized Step 6B safety snapshot must be safe and fresh",
            _bool_text(safety_ready),
            "true",
        ),
        _check(
            "market_hours_source_sanitized_only",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.market_hours_source == MARKET_HOURS_SOURCE,
            "market-hours source must be sanitized snapshot only",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.market_hours_source == MARKET_HOURS_SOURCE,
            ),
            "true",
        ),
        _check(
            "fresh_preflight_source_sanitized_only",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.fresh_pre_approval_preflight_source == FRESH_PREFLIGHT_SOURCE,
            "fresh preflight source must be sanitized snapshot only",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.fresh_pre_approval_preflight_source
                == FRESH_PREFLIGHT_SOURCE
            ),
            "true",
        ),
        _check(
            "no_open_positions",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.open_positions_count == 0,
            "open positions must be zero",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.open_positions_count == 0,
            ),
            "true",
        ),
        _check(
            "no_active_orders",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.active_orders_count == 0,
            "active orders must be zero",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.active_orders_count == 0,
            ),
            "true",
        ),
        _check(
            "no_result_unknown",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.result_unknown is False,
            "result_unknown must be false",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.result_unknown is False,
            ),
            "true",
        ),
        _check(
            "raw_response_not_saved_or_displayed",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.raw_response_saved is False
            and safety.raw_response_displayed is False,
            "raw response must not be saved or displayed",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.raw_response_saved is False
                and safety.raw_response_displayed is False
            ),
            "true",
        ),
        _check(
            "secret_scan_passed",
            isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
            and safety.secret_scan_passed is True,
            "secret scan must pass",
            _bool_text(
                isinstance(safety, LiveOrderRealApprovalArtifactGenerationSafetySnapshot)
                and safety.secret_scan_passed is True,
            ),
            "true",
        ),
        _check(
            "approval_id_generated",
            approval_id_generated,
            "Step 6B may generate an internal approval id",
            _bool_text(approval_id_generated),
            "true only in ready Step 6B artifact",
        ),
        _check(
            "approval_command_generated",
            approval_command_generated,
            "Step 6B may generate an internal approval command",
            _bool_text(approval_command_generated),
            "true only in ready Step 6B artifact",
        ),
        _check(
            "approval_command_one_line",
            approval_command_generated and _is_one_line(approval_command),
            "approval command must be one-line for future exact-match validation",
            _bool_text(approval_command_generated and _is_one_line(approval_command)),
            "true",
        ),
        _check(
            "approval_command_sha256_generated",
            approval_command_generated and len(approval_command_sha256) == 64,
            "approval command sha256 must be generated",
            _bool_text(approval_command_generated and len(approval_command_sha256) == 64),
            "true",
        ),
        _check(
            "approval_command_fingerprint_generated",
            approval_command_generated
            and approval_command_fingerprint not in {"", NOT_GENERATED},
            "approval command fingerprint must be generated",
            _bool_text(
                approval_command_generated
                and approval_command_fingerprint not in {"", NOT_GENERATED},
            ),
            "true",
        ),
        _check(
            "approval_command_redacted",
            approval_command_generated
            and approval_command_redacted not in {"", NOT_GENERATED}
            and approval_command_redacted != approval_command,
            "approval command redaction must be generated without full command",
            _bool_text(
                approval_command_generated
                and approval_command_redacted not in {"", NOT_GENERATED}
                and approval_command_redacted != approval_command,
            ),
            "true",
        ),
        _check(
            "approval_command_not_displayed",
            True,
            "Step 6B renderer must not display the full approval command",
            "false",
            "false",
        ),
        _check(
            "approval_command_not_copyable",
            True,
            "Step 6B must not create copyable approval text",
            "false",
            "false",
        ),
        _check(
            "approval_command_not_persisted",
            True,
            "Step 6B must not persist approval command text",
            "false",
            "false",
        ),
        _check(
            "approval_command_not_copied_to_clipboard",
            True,
            "Step 6B must not copy approval command to clipboard",
            "false",
            "false",
        ),
        _check(
            "no_api_broker_live_order_once_called",
            no_api_called,
            "Step 6B must not call API, broker, or live_order_once",
            _bool_text(no_api_called),
            "true",
        ),
        _check(
            "post_not_allowed_this_step",
            True,
            "Step 6B never allows HTTP POST",
            "false",
            "false",
        ),
        _check(
            "post_not_executed",
            isinstance(state, LiveOrderRealApprovalGateEnablementState)
            and state.post_executed is False,
            "Step 6B must not execute HTTP POST",
            _bool_text(
                isinstance(state, LiveOrderRealApprovalGateEnablementState)
                and state.post_executed is False,
            ),
            "true",
        ),
        _check(
            "future_step6c_handoff_conditions_present",
            bool(future_step6c_handoff_conditions),
            "future Step 6C handoff conditions must be present",
            _bool_text(bool(future_step6c_handoff_conditions)),
            "true",
        ),
        _check(
            "future_step6c_blockers_present",
            bool(future_step6c_blockers),
            "future Step 6C blockers must be present",
            _bool_text(bool(future_step6c_blockers)),
            "true",
        ),
    )


def _build_sections(
    *,
    check_results: tuple[LiveOrderRealApprovalArtifactGenerationCheckResult, ...],
    blocked_reasons: tuple[str, ...],
    recommended_next_step: str,
    future_step6c_handoff_conditions: tuple[str, ...],
    future_step6c_blockers: tuple[str, ...],
) -> tuple[LiveOrderRealApprovalArtifactGenerationSection, ...]:
    return (
        LiveOrderRealApprovalArtifactGenerationSection(
            section_id="step6b_scope",
            title="Step 6B Scope",
            lines=(
                "internal approval artifact generation only",
                "allowed_for_live remains false",
                "full approval command is not rendered, copied, persisted, or executable",
                "no API, broker, live_order_once, ledger, or HTTP POST is performed",
            ),
        ),
        LiveOrderRealApprovalArtifactGenerationSection(
            section_id="blocked_reasons",
            title="Blocked Reasons",
            lines=blocked_reasons or ("none",),
        ),
        LiveOrderRealApprovalArtifactGenerationSection(
            section_id="check_results",
            title="Check Results",
            lines=tuple(
                f"{check.name}: passed={check.passed}, expected={check.expected}"
                for check in check_results
            ),
        ),
        LiveOrderRealApprovalArtifactGenerationSection(
            section_id="future_step6c_handoff",
            title="Future Step 6C Handoff",
            lines=future_step6c_handoff_conditions or ("missing",),
        ),
        LiveOrderRealApprovalArtifactGenerationSection(
            section_id="future_step6c_blockers",
            title="Future Step 6C Blockers",
            lines=future_step6c_blockers or ("missing",),
        ),
        LiveOrderRealApprovalArtifactGenerationSection(
            section_id="recommended_next_step",
            title="Recommended Next Step",
            lines=(recommended_next_step,),
        ),
    )


def _validate_artifact(artifact: LiveOrderRealApprovalArtifact) -> None:
    _require_non_empty("artifact_id", artifact.artifact_id)
    if not artifact.artifact_id.startswith(LIVE_ORDER_REAL_APPROVAL_ARTIFACT_ID_PREFIX):
        raise LiveVerificationValidationError("invalid artifact_id prefix")
    _ensure_aware(artifact.created_at)
    _ensure_aware(artifact.expires_at)
    for label, value in (
        ("source_enablement_state_id", artifact.source_enablement_state_id),
        ("source_plan_id", artifact.source_plan_id),
        ("criteria_id", artifact.criteria_id),
        ("symbol", artifact.symbol),
        ("side", artifact.side),
        ("execution_type", artifact.execution_type),
        ("source_type", artifact.source_type),
        ("strategy_name", artifact.strategy_name),
        ("approval_id", artifact.approval_id),
        ("approval_id_redacted", artifact.approval_id_redacted),
        ("approval_id_fingerprint", artifact.approval_id_fingerprint),
        ("approval_command", artifact.approval_command),
        ("approval_command_sha256", artifact.approval_command_sha256),
        ("approval_command_fingerprint", artifact.approval_command_fingerprint),
        ("approval_command_redacted", artifact.approval_command_redacted),
        ("approval_command_template_version", artifact.approval_command_template_version),
        ("approval_command_display_mode", artifact.approval_command_display_mode),
        ("same_session_label", artifact.same_session_label),
        ("summary", artifact.summary),
        ("recommended_next_step", artifact.recommended_next_step),
    ):
        _require_non_empty(label, value)
    if artifact.allowed_for_live is not False:
        raise LiveVerificationValidationError("allowed_for_live must be False")
    if artifact.approval_gate_issued is not False:
        raise LiveVerificationValidationError("approval_gate_issued must be False")
    for field_name in (
        "approval_id_display_allowed",
        "approval_command_copyable",
        "approval_command_displayed",
        "approval_command_persisted",
        "approval_command_copied_to_clipboard",
        "approval_command_executable",
        "real_approval_artifacts_available",
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
        if getattr(artifact, field_name) is not False:
            raise LiveVerificationValidationError(f"{field_name} must be False")
    for field_name in (
        "approval_validation_deferred_to_step6c",
        "api_preflight_deferred_to_step6d_or_later",
        "post_deferred_to_step6e_or_later",
        "dry_run_only",
        "requires_human_approval",
        "explicit_user_confirmation_required",
        "approval_command_exact_match_required",
        "same_session_required",
    ):
        if getattr(artifact, field_name) is not True:
            raise LiveVerificationValidationError(f"{field_name} must be True")
    if artifact.ttl_seconds != APPROVAL_GATE_TTL_SECONDS:
        raise LiveVerificationValidationError("ttl_seconds must be 300")
    if artifact.post_attempt_limit != 1:
        raise LiveVerificationValidationError("post_attempt_limit must be 1")
    if set(REQUIRED_STEP6B_APPROVAL_ACK_TOKENS) != set(artifact.required_ack_tokens):
        raise LiveVerificationValidationError("required_ack_tokens mismatch")
    if artifact.artifact_ready:
        if (
            artifact.artifact_status
            is not ArtifactStatus.APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST
        ):
            raise LiveVerificationValidationError("ready artifact has invalid status")
        if artifact.symbol != SUPPORTED_SYMBOL:
            raise LiveVerificationValidationError("unsupported symbol")
        if artifact.side not in {
            LiveOrderCandidateSide.BUY.value,
            LiveOrderCandidateSide.SELL.value,
        }:
            raise LiveVerificationValidationError("unsupported side")
        if artifact.size != LIVE_ORDER_CANDIDATE_SIZE:
            raise LiveVerificationValidationError("unsupported size")
        if artifact.execution_type != LIVE_ORDER_CANDIDATE_EXECUTION_TYPE:
            raise LiveVerificationValidationError("unsupported execution_type")
        for field_name in (
            "eligible_for_step6c_validation",
            "approval_gate_enabled",
            "approval_artifact_generated",
            "approval_id_generated",
            "approval_command_generated",
            "approval_command_one_line",
            "usable_approval_artifacts_generated",
        ):
            if getattr(artifact, field_name) is not True:
                raise LiveVerificationValidationError(f"{field_name} must be True")
        if not artifact.approval_id.startswith(LIVE_ORDER_REAL_APPROVAL_ID_PREFIX):
            raise LiveVerificationValidationError("invalid approval_id prefix")
        if artifact.approval_id not in artifact.approval_command:
            raise LiveVerificationValidationError("approval_id missing from command")
        if len(artifact.approval_command_sha256) != 64:
            raise LiveVerificationValidationError("approval_command_sha256 missing")
        if artifact.approval_command_redacted == artifact.approval_command:
            raise LiveVerificationValidationError("approval command must be redacted")
    else:
        for field_name in (
            "eligible_for_step6c_validation",
            "approval_gate_enabled",
            "approval_artifact_generated",
            "approval_id_generated",
            "approval_command_generated",
            "approval_command_one_line",
            "usable_approval_artifacts_generated",
        ):
            if getattr(artifact, field_name) is not False:
                raise LiveVerificationValidationError(f"{field_name} must be False")
    if not artifact.check_results:
        raise LiveVerificationValidationError("check_results required")
    if not artifact.sections:
        raise LiveVerificationValidationError("sections required")


def _source_state_is_blocked(
    state: LiveOrderRealApprovalGateEnablementState | None,
    reasons: tuple[str, ...],
) -> bool:
    if not isinstance(state, LiveOrderRealApprovalGateEnablementState):
        return True
    source_blocking = {
        BlockReason.SOURCE_ENABLEMENT_STATE_NOT_READY.value,
        BlockReason.SOURCE_ENABLEMENT_STATE_NOT_ELIGIBLE.value,
        BlockReason.MISSING_SOURCE_ENABLEMENT_STATE.value,
    }
    return bool(set(reasons) & source_blocking)


def _request_or_empty(
    snapshot: LiveOrderRealApprovalArtifactGenerationRequestSnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalArtifactGenerationRequestSnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalArtifactGenerationRequestSnapshot):
        return snapshot
    return LiveOrderRealApprovalArtifactGenerationRequestSnapshot(
        request_id="missing",
        created_at=created_at,
        explicit_step6b_user_instruction_received=False,
        operator_understands_real_money_risk=False,
        operator_understands_no_api_in_step6b=False,
        operator_understands_no_post_in_step6b=False,
        operator_understands_no_live_order_once_in_step6b=False,
        operator_understands_approval_artifact_generation_only=False,
        operator_understands_approval_command_not_copyable_in_step6b=False,
        operator_understands_step6c_required_for_validation=False,
        operator_understands_step6d_or_later_required_for_api_preflight=False,
        operator_understands_step6e_or_later_required_for_post=False,
        operator_understands_unknown_means_stop=False,
        request_scope_label="missing",
    )


def _safety_or_empty(
    snapshot: LiveOrderRealApprovalArtifactGenerationSafetySnapshot | None,
    created_at: datetime,
) -> LiveOrderRealApprovalArtifactGenerationSafetySnapshot:
    if isinstance(snapshot, LiveOrderRealApprovalArtifactGenerationSafetySnapshot):
        return snapshot
    return LiveOrderRealApprovalArtifactGenerationSafetySnapshot(
        safety_snapshot_id="missing",
        created_at=created_at,
        source_enablement_state_age_seconds=999999,
        source_enablement_state_max_age_seconds=SOURCE_ENABLEMENT_STATE_MAX_AGE_SECONDS,
        approval_gate_enabled=False,
        allowed_for_live=False,
        approval_gate_issued=False,
        approval_id_generated_before_step6b=False,
        approval_command_generated_before_step6b=False,
        approval_command_copyable_before_step6b=False,
        approval_command_executable_before_step6b=False,
        usable_approval_artifacts_generated_before_step6b=False,
        real_approval_artifacts_available_before_step6b=False,
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


def _check(
    name: str,
    passed: bool,
    reason: str,
    sanitized_value: str,
    expected: str,
) -> LiveOrderRealApprovalArtifactGenerationCheckResult:
    return LiveOrderRealApprovalArtifactGenerationCheckResult(
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
    reason: LiveOrderRealApprovalArtifactGenerationBlockReason,
) -> None:
    if reason.value not in reasons:
        reasons.append(reason.value)


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


def _require_non_empty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise LiveVerificationValidationError(f"{label} must be non-empty")


def _ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise LiveVerificationValidationError("datetime value is required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise LiveVerificationValidationError("datetime must be timezone-aware")
    return value
