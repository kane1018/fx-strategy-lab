from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.live_verification.live_order_real_official_settlement_actual_transport_no_post_controlled import (  # noqa: E501
    build_official_settlement_actual_transport_no_post_controlled,
)
from app.live_verification.live_order_real_official_settlement_side_provenance_gate_no_post_controlled import (  # noqa: E501
    APPROVED_SAFE_ARTIFACT_KIND,
    RESULT_SETTLEMENT_SIDE_PROVENANCE_CONFIRMED,
    OfficialSettlementSideProvenanceInput,
    OfficialSettlementSideProvenanceStatus,
    as_safe_dict,
    build_official_settlement_side_provenance_gate_no_post_controlled,
    render_official_settlement_side_provenance_gate_no_post_markdown,
)

FORBIDDEN_MARKERS = {
    "raw_request",
    "raw_response",
    "broker_api_response",
    "credential_value",
    "signature_value",
    "headers_value",
    "positionId",
    "tradeId",
    "orderId",
    "accountId",
}


def test_side_provenance_ready_from_fresh_entry_safe_artifact_no_post() -> None:
    result = build_official_settlement_side_provenance_gate_no_post_controlled()

    assert result.status is OfficialSettlementSideProvenanceStatus.READY_NO_POST
    assert result.sanitized_result_category == RESULT_SETTLEMENT_SIDE_PROVENANCE_CONFIRMED
    assert result.blocked_reasons == ()
    assert result.settlement_side_provenance_gate_confirmed is True
    assert result.settlement_side_source_safe_artifact_available is True
    assert result.settlement_side_source_safe_artifact_kind == APPROVED_SAFE_ARTIFACT_KIND
    assert result.settlement_side_source_is_default_value is False
    assert result.settlement_side_source_is_operator_input is False
    assert result.settlement_side_source_is_raw_broker_value is False
    assert result.settlement_side_source_is_position_specific_identifier is False
    assert result.settlement_side_source_is_generic_opposite_order is False
    assert result.fresh_entry_safe_side_artifact_found is True
    assert (
        result
        .settlement_side_derived_from_fresh_entry_safe_artifact_or_approved_safe_position_artifact
    )
    assert result.settlement_side_matches_official_settlement_side_semantics is True
    assert result.settlement_side_safe_artifact_propagated_to_official_settlement_preview
    assert result.settlement_side_safe_artifact_propagated_to_actual_transport_plan
    assert result.settlement_side_safe_artifact_propagated_to_execution_gate
    assert result.settlement_side_provenance_mechanically_confirmed is True
    assert result.execution_gate_can_verify_settlement_side_provenance_before_post is True
    assert result.next_execution_gate_has_no_known_side_provenance_blocker is True
    assert result.side_provenance_artifact is not None
    assert result.side_provenance_artifact.derived_from_fresh_entry_safe_artifact is True
    assert result.side_provenance_artifact.codex_inferred_side is False
    assert result.this_step_actual_settlement_post_executed is False
    assert result.official_settlement_post_count == 0
    assert result.real_http_post_executed is False
    assert result.broker_write_executed is False
    assert result.real_network_client_invocation_count == 0


def test_side_provenance_allows_approved_safe_position_artifact_alternative() -> None:
    result = build_official_settlement_side_provenance_gate_no_post_controlled(
        OfficialSettlementSideProvenanceInput(
            fresh_entry_safe_side_artifact_found=False,
            approved_safe_position_side_artifact_found=True,
            approved_safe_position_side_label="BUY",
        ),
    )

    assert result.status is OfficialSettlementSideProvenanceStatus.READY_NO_POST
    assert result.fresh_entry_safe_side_artifact_found is False
    assert result.approved_safe_position_side_artifact_found is True
    assert result.settlement_side_provenance_mechanically_confirmed is True
    assert result.side_provenance_artifact is not None
    assert result.side_provenance_artifact.derived_from_approved_safe_position_artifact is True


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        (
            "fresh_entry_safe_side_artifact_found",
            False,
            "settlement_side_source_safe_artifact_missing",
        ),
        (
            "approved_safe_position_side_artifact_required",
            True,
            "approved_safe_position_side_artifact_missing",
        ),
        (
            "settlement_side_source_is_default_value",
            True,
            "settlement_side_source_is_default_value=true",
        ),
        (
            "settlement_side_source_is_operator_input",
            True,
            "settlement_side_source_is_operator_input=true",
        ),
        (
            "settlement_side_source_is_raw_broker_value",
            True,
            "settlement_side_source_is_raw_broker_value=true",
        ),
        (
            "settlement_side_source_is_position_specific_identifier",
            True,
            "settlement_side_source_is_position_specific_identifier=true",
        ),
        (
            "settlement_side_source_is_generic_opposite_order",
            True,
            "settlement_side_source_is_generic_opposite_order=true",
        ),
        (
            "settlement_side_safe_artifact_propagated_to_actual_transport_plan",
            False,
            "settlement_side_safe_artifact_propagated_to_actual_transport_plan=false",
        ),
        (
            "settlement_side_safe_artifact_propagated_to_execution_gate",
            False,
            "settlement_side_safe_artifact_propagated_to_execution_gate=false",
        ),
        (
            "generic_order_executor_used_for_settlement",
            True,
            "generic_order_executor_used_for_settlement=true",
        ),
        ("live_order_once_used_for_settlement", True, "live_order_once_used_for_settlement=true"),
        (
            "one_shot_generic_order_path_used_for_settlement",
            True,
            "one_shot_generic_order_path_used_for_settlement=true",
        ),
        ("position_specific_path_used", True, "position_specific_path_used=true"),
        ("retry_allowed", True, "retry_allowed=true"),
        ("repost_allowed", True, "repost_allowed=true"),
        ("second_settlement_allowed", True, "second_settlement_allowed=true"),
        ("entry_post_executed", True, "entry_post_executed=true"),
        ("generic_close_post_executed", True, "generic_close_post_executed=true"),
        ("ledger_update", True, "ledger_update=true"),
        ("receipt_handoff", True, "receipt_handoff=true"),
        (
            "raw_id_value_credential_header_exposure",
            True,
            "raw_id_value_credential_header_exposure=true",
        ),
    ],
)
def test_side_provenance_fail_closed(field: str, value: object, reason: str) -> None:
    snapshot = OfficialSettlementSideProvenanceInput(**{field: value})

    result = build_official_settlement_side_provenance_gate_no_post_controlled(snapshot)

    assert result.status is OfficialSettlementSideProvenanceStatus.BLOCKED_NO_POST
    assert result.settlement_side_provenance_gate_confirmed is False
    assert result.settlement_side_provenance_mechanically_confirmed is False
    assert result.execution_gate_can_verify_settlement_side_provenance_before_post is False
    assert result.next_execution_gate_has_no_known_side_provenance_blocker is False
    assert result.side_provenance_artifact is None
    assert result.this_step_actual_settlement_post_executed is False
    assert result.official_settlement_post_count == 0
    assert reason in result.blocked_reasons


def test_side_provenance_blocks_side_mismatch_between_safe_artifacts() -> None:
    result = build_official_settlement_side_provenance_gate_no_post_controlled(
        OfficialSettlementSideProvenanceInput(
            fresh_entry_safe_side_artifact_found=True,
            approved_safe_position_side_artifact_found=True,
            approved_safe_position_side_label="SELL",
        ),
    )

    assert result.status is OfficialSettlementSideProvenanceStatus.BLOCKED_NO_POST
    assert "settlement_side_safe_artifact_mismatch" in result.blocked_reasons
    assert result.side_provenance_artifact is None


def test_fresh_entry_summary_must_be_accepted_once_without_exposure() -> None:
    base = OfficialSettlementSideProvenanceInput()
    bad_summary = replace(
        base.fresh_entry_summary,
        fresh_entry_post_execution_count=2,
        fresh_entry_retry_attempted=True,
        raw_request_exposed=True,
    )

    result = build_official_settlement_side_provenance_gate_no_post_controlled(
        replace(base, fresh_entry_summary=bad_summary),
    )

    assert result.status is OfficialSettlementSideProvenanceStatus.BLOCKED_NO_POST
    assert "fresh_entry_post_count_not_one" in result.blocked_reasons
    assert "fresh_entry_retry_attempted=true" in result.blocked_reasons
    assert "raw_request_exposed=true" in result.blocked_reasons


def test_side_provenance_propagates_to_actual_transport_plan() -> None:
    provenance = build_official_settlement_side_provenance_gate_no_post_controlled()
    transport = build_official_settlement_actual_transport_no_post_controlled()

    assert provenance.side_provenance_artifact is not None
    assert transport.actual_transport_plan is not None
    assert transport.settlement_side_provenance_gate_confirmed is True
    assert transport.settlement_side_source_safe_artifact_available is True
    assert transport.settlement_side_source_is_default_value is False
    assert transport.settlement_side_source_is_operator_input is False
    assert transport.settlement_side_source_is_raw_broker_value is False
    assert transport.settlement_side_source_is_generic_opposite_order is False
    assert transport.settlement_side_safe_artifact_propagated_to_actual_transport_plan
    assert transport.settlement_side_safe_artifact_propagated_to_execution_gate
    assert transport.settlement_side_provenance_mechanically_confirmed is True
    assert (
        transport.actual_transport_plan.settlement_side_safe_label
        == provenance.side_provenance_artifact.settlement_side_safe_label
    )
    assert (
        transport.actual_transport_plan.settlement_side_source_safe_label
        == provenance.side_provenance_artifact.settlement_side_source_safe_label
    )
    assert transport.execution_gate_can_call_actual_transport_after_confirmation is True
    assert transport.next_execution_gate_has_no_known_code_blocker is True
    assert transport.fake_http_transport_used is True
    assert transport.fake_http_transport_call_count == 1
    assert transport.real_http_client_call_count == 0
    assert transport.actual_transport_real_http_post_executed is False
    assert transport.actual_transport_broker_write_executed is False
    assert transport.settlement_post_count == 0


def test_side_provenance_render_and_safe_dict_do_not_expose_forbidden_values() -> None:
    result = build_official_settlement_side_provenance_gate_no_post_controlled()
    rendered = render_official_settlement_side_provenance_gate_no_post_markdown(result)
    safe_dict_text = repr(as_safe_dict(result))
    result_dict_text = repr(asdict(result))

    for marker in FORBIDDEN_MARKERS:
        assert marker not in rendered
        assert marker not in safe_dict_text
    assert "side_provenance_artifact" not in safe_dict_text
    assert "positionId" not in result_dict_text
    assert "tradeId" not in result_dict_text
