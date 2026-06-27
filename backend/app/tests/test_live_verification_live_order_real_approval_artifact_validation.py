from __future__ import annotations

import ast
from dataclasses import asdict

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_approval_artifact_validation import (
    APPROVAL_COMMAND_DISPLAY_MODE_STEP6C,
    DEFAULT_FUTURE_STEP6D_BLOCKERS,
    DEFAULT_FUTURE_STEP6D_HANDOFF_CONDITIONS,
    DEFAULT_STEP6C_SOURCE_ARTIFACT_MAX_AGE_SECONDS,
    DEFAULT_STEP6C_VALIDATION_RECEIVED_MAX_AGE_SECONDS,
    LIVE_ORDER_REAL_APPROVAL_ARTIFACT_VALIDATION_ID_PREFIX,
    STEP6C_REQUEST_SCOPE_LABEL,
    LiveOrderRealApprovalArtifactValidationBlockReason,
    LiveOrderRealApprovalArtifactValidationRequestSnapshot,
    LiveOrderRealApprovalArtifactValidationSafetySnapshot,
    LiveOrderRealApprovalArtifactValidationStatus,
    build_live_order_real_approval_artifact_validation,
    build_live_order_real_approval_provided_command_snapshot,
    fingerprint_live_order_real_approval_provided_command,
    render_live_order_real_approval_artifact_validation_markdown,
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
from app.tests.test_live_verification_live_order_e2e_dry_run_chain import (
    CREATED_AT,
    _unchecked,
)
from app.tests.test_live_verification_live_order_real_approval_artifact_generation import (
    _artifact as _source_artifact,
)

ValidationStatus = LiveOrderRealApprovalArtifactValidationStatus
BlockReason = LiveOrderRealApprovalArtifactValidationBlockReason
_DEFAULT_ARTIFACT = object()
_DEFAULT_REQUEST = object()
_DEFAULT_COMMAND = object()
_DEFAULT_SAFETY = object()


def _request(
    **overrides: object,
) -> LiveOrderRealApprovalArtifactValidationRequestSnapshot:
    values = {
        "request_id": "step6c_request_001",
        "created_at": CREATED_AT,
        "explicit_step6c_user_instruction_received": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_no_api_in_step6c": True,
        "operator_understands_no_post_in_step6c": True,
        "operator_understands_no_live_order_once_in_step6c": True,
        "operator_understands_validation_only": True,
        "operator_understands_approval_command_not_copyable_in_step6c": True,
        "operator_understands_step6d_required_for_api_preflight": True,
        "operator_understands_step6e_or_later_required_for_post": True,
        "operator_understands_unknown_means_stop": True,
        "request_scope_label": STEP6C_REQUEST_SCOPE_LABEL,
    }
    values.update(overrides)
    return LiveOrderRealApprovalArtifactValidationRequestSnapshot(**values)


def _command(command: str | None = _DEFAULT_COMMAND):
    source = _source_artifact().artifact
    actual_command = source.approval_command if command is _DEFAULT_COMMAND else command
    return build_live_order_real_approval_provided_command_snapshot(
        provided_command=actual_command,
        provided_command_created_at=CREATED_AT,
        provided_command_received_at=CREATED_AT,
    )


def _safety(
    **overrides: object,
) -> LiveOrderRealApprovalArtifactValidationSafetySnapshot:
    values = {
        "safety_snapshot_id": "step6c_safety_snapshot_001",
        "created_at": CREATED_AT,
        "source_artifact_age_seconds": 0.5,
        "source_artifact_max_age_seconds": DEFAULT_STEP6C_SOURCE_ARTIFACT_MAX_AGE_SECONDS,
        "validation_received_age_seconds": 0.5,
        "validation_received_max_age_seconds": (
            DEFAULT_STEP6C_VALIDATION_RECEIVED_MAX_AGE_SECONDS
        ),
        "approval_gate_enabled": True,
        "allowed_for_live": False,
        "approval_gate_issued": False,
        "approval_id_generated": True,
        "approval_command_generated": True,
        "approval_command_copyable": False,
        "approval_command_displayed": False,
        "approval_command_persisted": False,
        "approval_command_copied_to_clipboard": False,
        "approval_command_executable": False,
        "real_approval_artifacts_available": False,
        "timezone": MARKET_HOURS_TIMEZONE,
        "market_hours_source": MARKET_HOURS_SOURCE,
        "market_session_state": MARKET_HOURS_OPEN_STATE,
        "is_weekend_jst": False,
        "market_window_allowed": True,
        "broker_maintenance_active": False,
        "holiday_or_special_close": False,
        "holiday_or_special_close_unknown": False,
        "market_hours_unknown": False,
        "market_hours_snapshot_age_seconds": 0.5,
        "market_hours_snapshot_max_age_seconds": MARKET_HOURS_MAX_AGE_SECONDS,
        "fresh_pre_approval_preflight_source": FRESH_PREFLIGHT_SOURCE,
        "fresh_pre_approval_preflight_status": FRESH_PREFLIGHT_READY_STATUS,
        "fresh_pre_approval_preflight_passed": True,
        "fresh_pre_approval_preflight_unknown": False,
        "fresh_pre_approval_preflight_age_seconds": 0.5,
        "fresh_pre_approval_preflight_max_age_seconds": FRESH_PREFLIGHT_MAX_AGE_SECONDS,
        "open_positions_count": 0,
        "active_orders_count": 0,
        "result_unknown": False,
        "raw_response_saved": False,
        "raw_response_displayed": False,
        "secret_scan_passed": True,
    }
    values.update(overrides)
    return LiveOrderRealApprovalArtifactValidationSafetySnapshot(**values)


def _validation(
    *,
    artifact=_DEFAULT_ARTIFACT,
    request=_DEFAULT_REQUEST,
    command=_DEFAULT_COMMAND,
    safety=_DEFAULT_SAFETY,
    **overrides: object,
):
    actual_artifact = _source_artifact().artifact if artifact is _DEFAULT_ARTIFACT else artifact
    actual_request = _request() if request is _DEFAULT_REQUEST else request
    if command is _DEFAULT_COMMAND:
        actual_command = _command(actual_artifact.approval_command)
    else:
        actual_command = command
    actual_safety = _safety() if safety is _DEFAULT_SAFETY else safety
    return build_live_order_real_approval_artifact_validation(
        source_artifact=actual_artifact,
        validation_request_snapshot=actual_request,
        provided_command_snapshot=actual_command,
        validation_safety_snapshot=actual_safety,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalArtifactValidationBlockReason | str,
    *,
    expected_status: ValidationStatus | None = None,
    **kwargs: object,
) -> None:
    result = _validation(**kwargs)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert result.validation_ready is False
    assert result.approval_artifact_validated is False
    assert result.eligible_for_step6d_api_preflight_planning is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_command_copyable is False
    assert result.approval_command_displayed is False
    assert result.approval_command_persisted is False
    assert result.approval_command_copied_to_clipboard is False
    assert result.approval_command_executable is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert result.private_api_called is False
    assert result.broker_called is False
    assert result.read_only_api_called is False
    assert result.public_api_called is False
    assert expected in result.blocked_reasons
    if expected_status is not None:
        assert result.validation_status is expected_status


def test_ready_artifact_request_command_and_safety_validate_without_post() -> None:
    result = _validation()
    validation = result.validation

    assert validation.validation_id.startswith(
        LIVE_ORDER_REAL_APPROVAL_ARTIFACT_VALIDATION_ID_PREFIX,
    )
    assert validation.validation_status is (
        ValidationStatus.APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST
    )
    assert validation.validation_ready is True
    assert validation.approval_artifact_validated is True
    assert validation.approval_command_exact_match_validated is True
    assert validation.approval_command_sha256_validated is True
    assert validation.approval_command_fingerprint_validated is True
    assert validation.approval_command_ttl_validated is True
    assert validation.approval_command_same_session_validated is True
    assert validation.approval_command_one_line_validated is True
    assert validation.approval_command_ack_tokens_validated is True
    assert validation.eligible_for_step6d_api_preflight_planning is True
    assert validation.allowed_for_live is False
    assert validation.approval_gate_issued is False
    assert validation.approval_command_copyable is False
    assert validation.approval_command_displayed is False
    assert validation.approval_command_display_mode == APPROVAL_COMMAND_DISPLAY_MODE_STEP6C
    assert validation.approval_command_persisted is False
    assert validation.approval_command_copied_to_clipboard is False
    assert validation.approval_command_executable is False
    assert validation.post_allowed_this_step is False
    assert validation.post_attempt_limit == 1
    assert validation.post_executed is False
    assert validation.live_order_once_called is False
    assert validation.private_api_called is False
    assert validation.broker_called is False
    assert validation.read_only_api_called is False
    assert validation.public_api_called is False


def test_ready_provided_command_snapshot_uses_redaction_fingerprint_and_sha_only() -> None:
    artifact = _source_artifact().artifact
    command = _command(artifact.approval_command)

    assert command.provided_command == artifact.approval_command
    assert command.provided_command_sha256 == artifact.approval_command_sha256
    assert command.provided_command_fingerprint == (
        fingerprint_live_order_real_approval_provided_command(artifact.approval_command)
    )
    assert command.provided_command_redacted != command.provided_command
    assert artifact.approval_id not in command.provided_command_redacted
    assert command.provided_command_one_line is True
    assert command.provided_command_contains_newline is False
    assert command.provided_command_has_extra_tokens is False
    assert command.provided_command_missing_ack_tokens is False


def test_markdown_renderer_never_outputs_full_generated_or_provided_command() -> None:
    validation = _validation().validation
    artifact = _source_artifact().artifact
    markdown = render_live_order_real_approval_artifact_validation_markdown(validation)

    for required in (
        "This Step 6C approval artifact validation is dry-run only.",
        "This Step 6C validation does not authorize live POST.",
        "This Step 6C validation keeps allowed_for_live=false.",
        "This Step 6C validation does not issue a real approval gate.",
        "This Step 6C renderer does not display the full generated approval command.",
        "This Step 6C renderer does not display the full provided approval command.",
        "This Step 6C renderer does not provide copyable approval text.",
        "This Step 6C validation does not call read-only API.",
        "This Step 6C validation does not call public API.",
        "This Step 6C validation does not call Private API.",
        "This Step 6C validation does not call live_order_once.",
        "This Step 6C validation does not execute HTTP POST.",
        "provided_command_sha256:",
        "provided_command_fingerprint:",
        "provided_command_redacted:",
    ):
        assert required in markdown
    assert artifact.approval_command not in markdown
    assert artifact.approval_id not in markdown
    for forbidden in (
        "sk_live_",
        "api_key_value",
        "secret_value",
        "signature_value",
        "raw request body",
        "raw response body",
        "real_order_id_123",
        "clientOrderId",
        "STEP4_APPROVE ",
        "STEP4F-",
        "pbcopy",
        "curl ",
    ):
        assert forbidden not in markdown


def test_missing_provided_command_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_PROVIDED_COMMAND,
        command=None,
        expected_status=ValidationStatus.BLOCKED_STEP6C_PROVIDED_COMMAND,
    )


def test_empty_provided_command_blocks() -> None:
    _assert_blocked(
        BlockReason.PROVIDED_COMMAND_EMPTY,
        command=_command(""),
        expected_status=ValidationStatus.BLOCKED_STEP6C_PROVIDED_COMMAND,
    )


@pytest.mark.parametrize(
    ("mutate", "reason"),
    (
        (
            lambda command: command + "\n",
            BlockReason.PROVIDED_COMMAND_NEWLINE,
        ),
        (
            lambda command: command + " ACK_EXTRA=YES",
            BlockReason.PROVIDED_COMMAND_EXTRA_TOKENS,
        ),
        (
            lambda command: command.replace(" ACK_NO_LOOP=YES", ""),
            BlockReason.PROVIDED_COMMAND_MISSING_ACK_TOKENS,
        ),
        (
            lambda command: command.replace("approval_id=", "approval_id=BAD", 1),
            BlockReason.APPROVAL_ID_MISMATCH,
        ),
        (
            lambda command: command.replace("symbol=USD_JPY", "symbol=EUR_USD"),
            BlockReason.SYMBOL_MISMATCH,
        ),
        (
            lambda command: command.replace("side=BUY", "side=NO_TRADE"),
            BlockReason.SIDE_MISMATCH,
        ),
        (
            lambda command: command.replace(f"size={LIVE_ORDER_CANDIDATE_SIZE}", "size=200"),
            BlockReason.SIZE_MISMATCH,
        ),
        (
            lambda command: command.replace(
                f"executionType={LIVE_ORDER_CANDIDATE_EXECUTION_TYPE}",
                "executionType=LIMIT",
            ),
            BlockReason.EXECUTION_TYPE_MISMATCH,
        ),
        (
            lambda command: command.replace("ttl_seconds=300", "ttl_seconds=120"),
            BlockReason.TTL_SECONDS_MISMATCH,
        ),
        (
            lambda command: command.replace("same_session=", "same_session=other", 1),
            BlockReason.SAME_SESSION_MISMATCH,
        ),
    ),
)
def test_provided_command_shape_mismatches_block(
    mutate,
    reason: BlockReason,
) -> None:
    artifact = _source_artifact().artifact
    _assert_blocked(
        reason,
        command=_command(mutate(artifact.approval_command)),
        expected_status=ValidationStatus.BLOCKED_STEP6C_PROVIDED_COMMAND,
    )


def test_sha256_and_fingerprint_mismatch_blocks_even_if_snapshot_claims_wrong_values() -> None:
    artifact = _source_artifact().artifact
    command = _command(artifact.approval_command)
    tampered = _unchecked(
        command,
        provided_command_sha256="0" * 64,
        provided_command_fingerprint="BADFINGERPRINT",
    )

    result = _validation(command=tampered)

    assert result.validation_status is ValidationStatus.BLOCKED_STEP6C_PROVIDED_COMMAND
    assert BlockReason.SHA256_MISMATCH.value in result.blocked_reasons
    assert BlockReason.FINGERPRINT_MISMATCH.value in result.blocked_reasons


def test_missing_request_snapshot_blocks_request_status() -> None:
    _assert_blocked(
        BlockReason.MISSING_VALIDATION_REQUEST_SNAPSHOT,
        request=None,
        expected_status=ValidationStatus.BLOCKED_STEP6C_VALIDATION_REQUEST,
    )


@pytest.mark.parametrize(
    ("field_name", "reason"),
    (
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
    ),
)
def test_request_acknowledgement_blockers_fail_closed(
    field_name: str,
    reason: BlockReason,
) -> None:
    _assert_blocked(
        reason,
        request=_request(**{field_name: False}),
        expected_status=ValidationStatus.BLOCKED_STEP6C_VALIDATION_REQUEST,
    )


def test_invalid_request_scope_blocks() -> None:
    _assert_blocked(
        BlockReason.INVALID_REQUEST_SCOPE_LABEL,
        request=_request(request_scope_label="copyable_display"),
        expected_status=ValidationStatus.BLOCKED_STEP6C_VALIDATION_REQUEST,
    )


def test_missing_or_blocked_source_artifact_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_SOURCE_ARTIFACT,
        artifact=None,
        command=_command(None),
        expected_status=ValidationStatus.BLOCKED_STEP6C_SOURCE_ARTIFACT,
    )
    blocked_artifact = _source_artifact(request=None).artifact
    _assert_blocked(
        BlockReason.SOURCE_ARTIFACT_NOT_READY,
        artifact=blocked_artifact,
        command=_command(None),
        expected_status=ValidationStatus.BLOCKED_STEP6C_SOURCE_ARTIFACT,
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"allowed_for_live": True}, BlockReason.SOURCE_ARTIFACT_ALLOWS_LIVE),
        ({"approval_gate_enabled": False}, BlockReason.SOURCE_GATE_NOT_ENABLED),
        ({"approval_gate_issued": True}, BlockReason.SOURCE_GATE_ALREADY_ISSUED),
        (
            {"approval_id_generated": False},
            BlockReason.SOURCE_APPROVAL_ID_NOT_GENERATED,
        ),
        (
            {"approval_command_generated": False},
            BlockReason.SOURCE_APPROVAL_COMMAND_NOT_GENERATED,
        ),
        (
            {"approval_command_copyable": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            {"approval_command_displayed": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_DISPLAYED,
        ),
        (
            {"approval_command_persisted": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_PERSISTED,
        ),
        (
            {"approval_command_copied_to_clipboard": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_COPIED_TO_CLIPBOARD,
        ),
        (
            {"approval_command_executable": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_EXECUTABLE,
        ),
        ({"post_executed": True}, BlockReason.SOURCE_POST_ALREADY_EXECUTED),
        (
            {"live_order_once_called": True},
            BlockReason.LIVE_ORDER_ONCE_ALREADY_CALLED,
        ),
        ({"private_api_called": True}, BlockReason.PRIVATE_API_ALREADY_CALLED),
        ({"broker_called": True}, BlockReason.BROKER_ALREADY_CALLED),
        ({"read_only_api_called": True}, BlockReason.READ_ONLY_API_ALREADY_CALLED),
        ({"public_api_called": True}, BlockReason.PUBLIC_API_ALREADY_CALLED),
        ({"symbol": "EUR_USD"}, BlockReason.UNSUPPORTED_SYMBOL),
        ({"side": "NO_TRADE"}, BlockReason.UNSUPPORTED_SIDE),
        ({"size": 200}, BlockReason.UNSUPPORTED_SIZE),
        ({"execution_type": "LIMIT"}, BlockReason.UNSUPPORTED_EXECUTION_TYPE),
    ),
)
def test_source_artifact_unsafe_mismatches_block(
    override: dict[str, object],
    reason: BlockReason,
) -> None:
    artifact = _unchecked(_source_artifact().artifact, **override)
    command = _command(artifact.approval_command)
    _assert_blocked(reason, artifact=artifact, command=command)


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"source_artifact_age_seconds": 301},
            BlockReason.SOURCE_ARTIFACT_STALE,
        ),
        (
            {"validation_received_age_seconds": 301},
            BlockReason.VALIDATION_RECEIVED_STALE,
        ),
        ({"approval_gate_enabled": False}, BlockReason.SAFETY_GATE_NOT_ENABLED),
        ({"allowed_for_live": True}, BlockReason.SAFETY_ALLOWS_LIVE),
        ({"approval_gate_issued": True}, BlockReason.SAFETY_GATE_ALREADY_ISSUED),
        (
            {"approval_id_generated": False},
            BlockReason.SAFETY_APPROVAL_ID_NOT_GENERATED,
        ),
        (
            {"approval_command_generated": False},
            BlockReason.SAFETY_APPROVAL_COMMAND_NOT_GENERATED,
        ),
        (
            {"approval_command_copyable": True},
            BlockReason.SAFETY_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            {"approval_command_displayed": True},
            BlockReason.SAFETY_APPROVAL_COMMAND_DISPLAYED,
        ),
        ({"timezone": "UTC"}, BlockReason.INVALID_TIMEZONE),
        ({"market_hours_source": "real_api"}, BlockReason.INVALID_MARKET_HOURS_SOURCE),
        ({"market_session_state": "CLOSED"}, BlockReason.MARKET_SESSION_NOT_OPEN),
        ({"is_weekend_jst": True}, BlockReason.WEEKEND_JST),
        ({"market_window_allowed": False}, BlockReason.MARKET_WINDOW_NOT_ALLOWED),
        ({"broker_maintenance_active": True}, BlockReason.BROKER_MAINTENANCE_ACTIVE),
        ({"holiday_or_special_close": True}, BlockReason.HOLIDAY_OR_SPECIAL_CLOSE),
        ({"market_hours_unknown": True}, BlockReason.MARKET_HOURS_UNKNOWN),
        (
            {"market_hours_snapshot_age_seconds": 31},
            BlockReason.MARKET_HOURS_SNAPSHOT_STALE,
        ),
        (
            {"fresh_pre_approval_preflight_status": "BLOCKED"},
            BlockReason.FRESH_PREFLIGHT_NOT_READY,
        ),
        (
            {"fresh_pre_approval_preflight_passed": False},
            BlockReason.FRESH_PREFLIGHT_NOT_PASSED,
        ),
        (
            {"fresh_pre_approval_preflight_unknown": True},
            BlockReason.FRESH_PREFLIGHT_UNKNOWN,
        ),
        (
            {"fresh_pre_approval_preflight_age_seconds": 31},
            BlockReason.FRESH_PREFLIGHT_STALE,
        ),
        ({"open_positions_count": 1}, BlockReason.OPEN_POSITION_EXISTS),
        ({"active_orders_count": 1}, BlockReason.ACTIVE_ORDER_EXISTS),
        ({"result_unknown": True}, BlockReason.RESULT_UNKNOWN),
        ({"raw_response_saved": True}, BlockReason.RAW_RESPONSE_SAVED),
        ({"raw_response_displayed": True}, BlockReason.RAW_RESPONSE_DISPLAYED),
        ({"secret_scan_passed": False}, BlockReason.SECRET_SCAN_NOT_PASSED),
    ),
)
def test_safety_snapshot_blockers_fail_closed(
    override: dict[str, object],
    reason: BlockReason,
) -> None:
    _assert_blocked(
        reason,
        safety=_safety(**override),
        expected_status=ValidationStatus.BLOCKED_STEP6C_VALIDATION_SAFETY_SNAPSHOT,
    )


def test_missing_safety_snapshot_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_VALIDATION_SAFETY_SNAPSHOT,
        safety=None,
        expected_status=ValidationStatus.BLOCKED_STEP6C_VALIDATION_SAFETY_SNAPSHOT,
    )


def test_future_step6d_lists_are_required_and_preserved() -> None:
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6D_HANDOFF_CONDITIONS,
        future_step6d_handoff_conditions=(),
        expected_status=ValidationStatus.BLOCKED_STEP6C_UNSAFE_MISMATCH,
    )
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6D_BLOCKERS,
        future_step6d_blockers=(),
        expected_status=ValidationStatus.BLOCKED_STEP6C_UNSAFE_MISMATCH,
    )

    validation = _validation().validation
    assert validation.future_step6d_handoff_conditions == (
        DEFAULT_FUTURE_STEP6D_HANDOFF_CONDITIONS
    )
    assert validation.future_step6d_blockers == DEFAULT_FUTURE_STEP6D_BLOCKERS
    assert "user explicitly requests Step 6D" in (
        validation.future_step6d_handoff_conditions
    )
    assert "validation missing or blocked" in validation.future_step6d_blockers


def test_check_results_cover_validation_no_api_no_post_and_step6d_handoff() -> None:
    validation = _validation().validation
    names = {check.name for check in validation.check_results}

    assert {
        "source_artifact_ready",
        "explicit_step6c_request_received",
        "operator_acknowledgements_complete",
        "provided_command_present",
        "provided_command_exact_match",
        "approval_id_validated",
        "approval_command_sha256_validated",
        "approval_command_fingerprint_validated",
        "approval_command_one_line",
        "approval_command_no_newline",
        "approval_command_no_extra_tokens",
        "approval_command_ack_tokens_complete",
        "approval_command_ttl_validated",
        "approval_command_same_session_validated",
        "allowed_for_live_false",
        "approval_gate_not_issued",
        "approval_command_not_displayed",
        "approval_command_not_copyable",
        "approval_command_not_persisted",
        "approval_command_not_copied_to_clipboard",
        "no_api_broker_live_order_once_called",
        "post_not_allowed_this_step",
        "post_not_executed",
        "future_step6d_handoff_conditions_present",
        "future_step6d_blockers_present",
    } <= names


def test_serialization_and_repr_do_not_contain_secret_or_real_id_values() -> None:
    validation = _validation().validation
    serialized = f"{asdict(validation)} {validation!r}"

    for forbidden in (
        "sk_live_",
        "api_key_value",
        "secret_value",
        "signature_value",
        "raw request body",
        "raw response body",
        "real_order_id_123",
        "real_position_id_123",
        "clientOrderId",
        "STEP4_APPROVE ",
        "STEP4F-",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    "forbidden_kwarg",
    (
        "api_key",
        "secret",
        "signature",
        "headers",
        "raw_request",
        "raw_response",
        "clientOrderId",
        "positionId",
        "executionId",
        "copyable_command",
        "approval_text_file",
        "ledger_path",
        "pbcopy",
        "api_client",
        "broker_client",
    ),
)
def test_builder_does_not_accept_forbidden_inputs(forbidden_kwarg: str) -> None:
    artifact = _source_artifact().artifact
    kwargs = {
        "source_artifact": artifact,
        "validation_request_snapshot": _request(),
        "provided_command_snapshot": _command(artifact.approval_command),
        "validation_safety_snapshot": _safety(),
        "created_at": CREATED_AT,
        forbidden_kwarg: "forbidden",
    }
    with pytest.raises(TypeError):
        build_live_order_real_approval_artifact_validation(**kwargs)


def test_module_does_not_depend_on_api_order_runner_or_clipboard() -> None:
    import app.live_verification.live_order_real_approval_artifact_validation as module

    module_source = module.__loader__.get_source(module.__name__)
    assert module_source is not None
    tree = ast.parse(module_source)
    blocked_modules = (
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "http.client",
        "socket",
        "subprocess",
        "app.brokers",
        "app.private_api",
        "live_order_once",
    )
    blocked_call_names = {"pbcopy", "read_text", "write_text"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not any(
                    alias.name == blocked or alias.name.startswith(f"{blocked}.")
                    for blocked in blocked_modules
                )
                for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            assert not any(
                module_name == blocked or module_name.startswith(f"{blocked}.")
                for blocked in blocked_modules
            )
        if isinstance(node, ast.Call):
            func = node.func
            call_name = func.id if isinstance(func, ast.Name) else None
            if isinstance(func, ast.Attribute):
                call_name = func.attr
            assert call_name not in blocked_call_names
