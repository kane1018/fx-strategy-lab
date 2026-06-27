from __future__ import annotations

import ast
from dataclasses import asdict

import pytest

from app.live_verification.live_order_candidate import (
    LIVE_ORDER_CANDIDATE_EXECUTION_TYPE,
    LIVE_ORDER_CANDIDATE_SIZE,
)
from app.live_verification.live_order_real_approval_artifact_generation import (
    APPROVAL_COMMAND_DISPLAY_MODE,
    DEFAULT_FUTURE_STEP6C_BLOCKERS,
    DEFAULT_FUTURE_STEP6C_HANDOFF_CONDITIONS,
    LIVE_ORDER_REAL_APPROVAL_ARTIFACT_ID_PREFIX,
    LIVE_ORDER_REAL_APPROVAL_ID_PREFIX,
    REQUIRED_STEP6B_APPROVAL_ACK_TOKENS,
    SOURCE_ENABLEMENT_STATE_MAX_AGE_SECONDS,
    STEP6B_REQUEST_SCOPE_LABEL,
    LiveOrderRealApprovalArtifactGenerationBlockReason,
    LiveOrderRealApprovalArtifactGenerationRequestSnapshot,
    LiveOrderRealApprovalArtifactGenerationSafetySnapshot,
    LiveOrderRealApprovalArtifactGenerationStatus,
    build_live_order_real_approval_artifact,
    fingerprint_live_order_real_approval_command,
    make_live_order_real_approval_command,
    render_live_order_real_approval_artifact_markdown,
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
from app.tests.test_live_verification_live_order_real_approval_gate_enablement_state import (
    _state as _source_state,
)

ArtifactStatus = LiveOrderRealApprovalArtifactGenerationStatus
BlockReason = LiveOrderRealApprovalArtifactGenerationBlockReason
_DEFAULT_SOURCE = object()
_DEFAULT_REQUEST = object()
_DEFAULT_SAFETY = object()


def _request(
    **overrides: object,
) -> LiveOrderRealApprovalArtifactGenerationRequestSnapshot:
    values = {
        "request_id": "step6b_request_001",
        "created_at": CREATED_AT,
        "explicit_step6b_user_instruction_received": True,
        "operator_understands_real_money_risk": True,
        "operator_understands_no_api_in_step6b": True,
        "operator_understands_no_post_in_step6b": True,
        "operator_understands_no_live_order_once_in_step6b": True,
        "operator_understands_approval_artifact_generation_only": True,
        "operator_understands_approval_command_not_copyable_in_step6b": True,
        "operator_understands_step6c_required_for_validation": True,
        "operator_understands_step6d_or_later_required_for_api_preflight": True,
        "operator_understands_step6e_or_later_required_for_post": True,
        "operator_understands_unknown_means_stop": True,
        "request_scope_label": STEP6B_REQUEST_SCOPE_LABEL,
    }
    values.update(overrides)
    return LiveOrderRealApprovalArtifactGenerationRequestSnapshot(**values)


def _safety(
    **overrides: object,
) -> LiveOrderRealApprovalArtifactGenerationSafetySnapshot:
    values = {
        "safety_snapshot_id": "step6b_safety_snapshot_001",
        "created_at": CREATED_AT,
        "source_enablement_state_age_seconds": 0.5,
        "source_enablement_state_max_age_seconds": SOURCE_ENABLEMENT_STATE_MAX_AGE_SECONDS,
        "approval_gate_enabled": True,
        "allowed_for_live": False,
        "approval_gate_issued": False,
        "approval_id_generated_before_step6b": False,
        "approval_command_generated_before_step6b": False,
        "approval_command_copyable_before_step6b": False,
        "approval_command_executable_before_step6b": False,
        "usable_approval_artifacts_generated_before_step6b": False,
        "real_approval_artifacts_available_before_step6b": False,
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
    return LiveOrderRealApprovalArtifactGenerationSafetySnapshot(**values)


def _artifact(
    *,
    source=_DEFAULT_SOURCE,
    request=_DEFAULT_REQUEST,
    safety=_DEFAULT_SAFETY,
    **overrides: object,
):
    actual_source = _source_state().state if source is _DEFAULT_SOURCE else source
    actual_request = _request() if request is _DEFAULT_REQUEST else request
    actual_safety = _safety() if safety is _DEFAULT_SAFETY else safety
    return build_live_order_real_approval_artifact(
        source_enablement_state=actual_source,
        artifact_generation_request_snapshot=actual_request,
        artifact_generation_safety_snapshot=actual_safety,
        created_at=CREATED_AT,
        **overrides,
    )


def _assert_blocked(
    reason: LiveOrderRealApprovalArtifactGenerationBlockReason | str,
    *,
    expected_status: ArtifactStatus | None = None,
    **kwargs: object,
) -> None:
    result = _artifact(**kwargs)
    expected = reason.value if isinstance(reason, BlockReason) else reason

    assert result.artifact_ready is False
    assert result.eligible_for_step6c_validation is False
    assert result.allowed_for_live is False
    assert result.approval_gate_issued is False
    assert result.approval_id_generated is False
    assert result.approval_command_generated is False
    assert result.approval_command_copyable is False
    assert result.approval_command_displayed is False
    assert result.approval_command_persisted is False
    assert result.approval_command_copied_to_clipboard is False
    assert result.approval_command_executable is False
    assert result.usable_approval_artifacts_generated is False
    assert result.real_approval_artifacts_available is False
    assert result.post_allowed_this_step is False
    assert result.post_executed is False
    assert result.live_order_once_called is False
    assert result.private_api_called is False
    assert result.broker_called is False
    assert result.read_only_api_called is False
    assert result.public_api_called is False
    assert expected in result.blocked_reasons
    if expected_status is not None:
        assert result.artifact_status is expected_status


def test_ready_step6b_artifact_generates_internal_id_and_command_only() -> None:
    result = _artifact()
    artifact = result.artifact

    assert artifact.artifact_id.startswith(LIVE_ORDER_REAL_APPROVAL_ARTIFACT_ID_PREFIX)
    assert artifact.artifact_status is ArtifactStatus.APPROVAL_ARTIFACT_GENERATED_NO_API_NO_POST
    assert artifact.artifact_ready is True
    assert artifact.eligible_for_step6c_validation is True
    assert artifact.allowed_for_live is False
    assert artifact.approval_gate_enabled is True
    assert artifact.approval_gate_issued is False
    assert artifact.approval_artifact_generated is True
    assert artifact.approval_id_generated is True
    assert artifact.approval_id.startswith(LIVE_ORDER_REAL_APPROVAL_ID_PREFIX)
    assert artifact.approval_id_display_allowed is False
    assert artifact.approval_command_generated is True
    assert artifact.approval_command_copyable is False
    assert artifact.approval_command_displayed is False
    assert artifact.approval_command_display_mode == APPROVAL_COMMAND_DISPLAY_MODE
    assert artifact.approval_command_persisted is False
    assert artifact.approval_command_copied_to_clipboard is False
    assert artifact.approval_command_executable is False
    assert artifact.usable_approval_artifacts_generated is True
    assert artifact.real_approval_artifacts_available is False
    assert artifact.post_allowed_this_step is False
    assert artifact.post_attempt_limit == 1
    assert artifact.post_executed is False


def test_ready_artifact_command_shape_is_internal_one_line_and_fingerprinted() -> None:
    artifact = _artifact().artifact

    assert "\n" not in artifact.approval_command
    assert "\r" not in artifact.approval_command
    assert artifact.approval_command_one_line is True
    assert artifact.approval_id in artifact.approval_command
    assert "symbol=USD_JPY" in artifact.approval_command
    assert f"size={LIVE_ORDER_CANDIDATE_SIZE}" in artifact.approval_command
    assert f"executionType={LIVE_ORDER_CANDIDATE_EXECUTION_TYPE}" in (
        artifact.approval_command
    )
    for token in REQUIRED_STEP6B_APPROVAL_ACK_TOKENS:
        assert token in artifact.approval_command
    assert len(artifact.approval_command_sha256) == 64
    assert artifact.approval_command_fingerprint == (
        fingerprint_live_order_real_approval_command(artifact.approval_command)
    )
    assert artifact.approval_command_redacted != artifact.approval_command
    assert artifact.approval_id not in artifact.approval_command_redacted
    assert artifact.approval_id_fingerprint in artifact.approval_command_redacted


def test_ready_artifact_defers_validation_preflight_and_post() -> None:
    artifact = _artifact().artifact

    assert artifact.approval_validation_deferred_to_step6c is True
    assert artifact.api_preflight_deferred_to_step6d_or_later is True
    assert artifact.post_deferred_to_step6e_or_later is True
    assert artifact.dry_run_only is True
    assert artifact.requires_human_approval is True
    assert artifact.explicit_user_confirmation_required is True
    assert artifact.ttl_seconds == 300
    assert artifact.expires_at > artifact.created_at
    assert artifact.same_session_required is True
    assert artifact.retry_allowed is False
    assert artifact.loop_allowed is False
    assert artifact.add_order_allowed is False
    assert artifact.change_order_allowed is False
    assert artifact.cancel_order_allowed is False
    assert artifact.close_order_allowed is False


def test_markdown_renderer_never_outputs_full_command_or_copyable_text() -> None:
    artifact = _artifact().artifact
    markdown = render_live_order_real_approval_artifact_markdown(artifact)

    for required in (
        "This Step 6B approval artifact generation is dry-run only.",
        "This Step 6B artifact does not authorize live POST.",
        "This Step 6B artifact keeps allowed_for_live=false.",
        "This Step 6B artifact does not issue a real approval gate.",
        "This Step 6B artifact may generate an internal approval_id and approval_command",
        "This Step 6B renderer does not display the full approval command.",
        "This Step 6B renderer does not provide copyable approval text.",
        "This Step 6B artifact does not call read-only API.",
        "This Step 6B artifact does not call public API.",
        "This Step 6B artifact does not call Private API.",
        "This Step 6B artifact does not call live_order_once.",
        "This Step 6B artifact does not execute HTTP POST.",
        "approval_command_sha256:",
        "approval_command_fingerprint:",
        "approval_command_redacted:",
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


def test_missing_request_snapshot_blocks_request_status() -> None:
    _assert_blocked(
        BlockReason.MISSING_ARTIFACT_REQUEST_SNAPSHOT,
        request=None,
        expected_status=ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_REQUEST,
    )


@pytest.mark.parametrize(
    ("field_name", "reason"),
    (
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
    ),
)
def test_request_acknowledgement_blockers_fail_closed(
    field_name: str,
    reason: BlockReason,
) -> None:
    _assert_blocked(
        reason,
        request=_request(**{field_name: False}),
        expected_status=ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_REQUEST,
    )


def test_invalid_request_scope_blocks() -> None:
    _assert_blocked(
        BlockReason.INVALID_REQUEST_SCOPE_LABEL,
        request=_request(request_scope_label="copyable_approval_command"),
        expected_status=ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_REQUEST,
    )


def test_missing_or_blocked_source_state_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_SOURCE_ENABLEMENT_STATE,
        source=None,
        expected_status=ArtifactStatus.BLOCKED_STEP6B_SOURCE_ENABLEMENT_STATE,
    )
    blocked_state = _source_state(request=None).state
    _assert_blocked(
        BlockReason.SOURCE_ENABLEMENT_STATE_NOT_READY,
        source=blocked_state,
        expected_status=ArtifactStatus.BLOCKED_STEP6B_SOURCE_ENABLEMENT_STATE,
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        ({"allowed_for_live": True}, BlockReason.SOURCE_ALLOWS_LIVE),
        ({"approval_gate_enabled": False}, BlockReason.SOURCE_GATE_NOT_ENABLED),
        ({"approval_gate_issued": True}, BlockReason.SOURCE_GATE_ALREADY_ISSUED),
        (
            {"approval_id_generated": True},
            BlockReason.SOURCE_APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            {"approval_command_generated": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            {"approval_command_copyable": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_COPYABLE,
        ),
        (
            {"approval_command_executable": True},
            BlockReason.SOURCE_APPROVAL_COMMAND_EXECUTABLE,
        ),
        (
            {"usable_approval_artifacts_generated": True},
            BlockReason.SOURCE_USABLE_APPROVAL_ARTIFACTS_GENERATED,
        ),
        (
            {"real_approval_artifacts_available": True},
            BlockReason.SOURCE_REAL_APPROVAL_ARTIFACTS_AVAILABLE,
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
def test_source_state_unsafe_mismatches_block(
    override: dict[str, object],
    reason: BlockReason,
) -> None:
    source = _unchecked(_source_state().state, **override)
    _assert_blocked(
        reason,
        source=source,
        expected_status=ArtifactStatus.BLOCKED_STEP6B_UNSAFE_MISMATCH,
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    (
        (
            {"source_enablement_state_age_seconds": 301},
            BlockReason.SOURCE_ENABLEMENT_STATE_STALE,
        ),
        ({"approval_gate_enabled": False}, BlockReason.SAFETY_GATE_NOT_ENABLED),
        ({"allowed_for_live": True}, BlockReason.SAFETY_ALLOWS_LIVE),
        ({"approval_gate_issued": True}, BlockReason.SAFETY_GATE_ALREADY_ISSUED),
        (
            {"approval_id_generated_before_step6b": True},
            BlockReason.PRIOR_APPROVAL_ID_ALREADY_GENERATED,
        ),
        (
            {"approval_command_generated_before_step6b": True},
            BlockReason.PRIOR_APPROVAL_COMMAND_ALREADY_GENERATED,
        ),
        (
            {"approval_command_copyable_before_step6b": True},
            BlockReason.PRIOR_APPROVAL_COMMAND_COPYABLE,
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
        expected_status=ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT,
    )


def test_missing_safety_snapshot_blocks() -> None:
    _assert_blocked(
        BlockReason.MISSING_ARTIFACT_SAFETY_SNAPSHOT,
        safety=None,
        expected_status=ArtifactStatus.BLOCKED_STEP6B_ARTIFACT_SAFETY_SNAPSHOT,
    )


def test_future_step6c_lists_are_required_and_preserved() -> None:
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6C_HANDOFF_CONDITIONS,
        future_step6c_handoff_conditions=(),
        expected_status=ArtifactStatus.BLOCKED_STEP6B_UNSAFE_MISMATCH,
    )
    _assert_blocked(
        BlockReason.MISSING_FUTURE_STEP6C_BLOCKERS,
        future_step6c_blockers=(),
        expected_status=ArtifactStatus.BLOCKED_STEP6B_UNSAFE_MISMATCH,
    )

    artifact = _artifact().artifact
    assert artifact.future_step6c_handoff_conditions == (
        DEFAULT_FUTURE_STEP6C_HANDOFF_CONDITIONS
    )
    assert artifact.future_step6c_blockers == DEFAULT_FUTURE_STEP6C_BLOCKERS
    assert "Step 6C must enforce TTL 300 seconds" in (
        artifact.future_step6c_handoff_conditions
    )
    assert "approval command contains newline" in artifact.future_step6c_blockers


def test_check_results_cover_artifact_no_api_no_post_and_step6c_handoff() -> None:
    artifact = _artifact().artifact
    names = {check.name for check in artifact.check_results}

    assert {
        "source_enablement_state_ready",
        "approval_gate_enabled_true_from_step6a",
        "allowed_for_live_false",
        "approval_gate_not_issued",
        "no_prior_approval_id",
        "no_prior_approval_command",
        "no_prior_copyable_command",
        "request_snapshot_ready",
        "safety_snapshot_fresh",
        "market_hours_source_sanitized_only",
        "fresh_preflight_source_sanitized_only",
        "no_open_positions",
        "no_active_orders",
        "no_result_unknown",
        "raw_response_not_saved_or_displayed",
        "secret_scan_passed",
        "approval_id_generated",
        "approval_command_generated",
        "approval_command_one_line",
        "approval_command_sha256_generated",
        "approval_command_fingerprint_generated",
        "approval_command_redacted",
        "approval_command_not_displayed",
        "approval_command_not_copyable",
        "approval_command_not_persisted",
        "approval_command_not_copied_to_clipboard",
        "no_api_broker_live_order_once_called",
        "post_not_allowed_this_step",
        "post_not_executed",
        "future_step6c_handoff_conditions_present",
        "future_step6c_blockers_present",
    } <= names


def test_command_helper_is_one_line_and_requires_no_forbidden_inputs() -> None:
    command = make_live_order_real_approval_command(
        approval_id="LORAID6B-TESTONLY123456",
        symbol="USD_JPY",
        side="BUY",
        size=100,
        execution_type="MARKET",
        ttl_seconds=300,
        same_session_label="same_session_test",
    )

    assert "\n" not in command
    assert "LORAID6B-TESTONLY123456" in command
    for token in REQUIRED_STEP6B_APPROVAL_ACK_TOKENS:
        assert token in command


def test_serialization_and_repr_do_not_contain_secret_or_real_id_values() -> None:
    artifact = _artifact().artifact
    serialized = f"{asdict(artifact)} {artifact!r}"

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
    kwargs = {
        "source_enablement_state": _source_state().state,
        "artifact_generation_request_snapshot": _request(),
        "artifact_generation_safety_snapshot": _safety(),
        "created_at": CREATED_AT,
        forbidden_kwarg: "forbidden",
    }
    with pytest.raises(TypeError):
        build_live_order_real_approval_artifact(**kwargs)


def test_module_does_not_depend_on_api_order_runner_or_clipboard() -> None:
    import app.live_verification.live_order_real_approval_artifact_generation as module

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
