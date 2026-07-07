"""No-POST tests for the official settlement execution boundary.

Synthetic values only. No network, no credentials, no `.env`.
"""

from __future__ import annotations

import inspect

import pytest

from app.services import gmo_live_official_settlement_execution_boundary as module
from app.services.gmo_live_official_settlement_execution_boundary import (
    REQUIRED_SETTLEMENT_EXACT_CONFIRMATION,
    REQUIRED_SETTLEMENT_READINESS,
    REQUIRED_SETTLEMENT_UNDERSTANDS_RISK,
    FakeOfficialSettlementOneShotSender,
    GmoOfficialSettlementExecutionBoundaryError,
    GmoOfficialSettlementPermitScopeError,
    GmoOfficialSettlementPostPermitStatus,
    OfficialSettlementOperatorCurrentTurnInput,
    RefusingOfficialSettlementOneShotSender,
    SettlementPostSafeOutcome,
    assert_settlement_only_permit_scope,
    build_gmo_official_settlement_post_permit,
    build_official_settlement_execution_activation,
    consume_gmo_official_settlement_post_permit,
    send_official_settlement_post_once,
    verify_official_settlement_operator_input,
)
from app.services.gmo_live_official_settlement_preflight import (
    SealedOfficialSettlementValueSource,
    derive_official_settlement_side_from_prior_entry,
)

SYNTHETIC_SIZE = "137"  # synthetic sentinel used only in tests


def _valid_operator_input() -> OfficialSettlementOperatorCurrentTurnInput:
    return OfficialSettlementOperatorCurrentTurnInput(
        prior_entry_signal_safe_label="ENTRY_BUY",
        exact_confirmation=REQUIRED_SETTLEMENT_EXACT_CONFIRMATION,
        readiness=REQUIRED_SETTLEMENT_READINESS,
        understands_risk=REQUIRED_SETTLEMENT_UNDERSTANDS_RISK,
    )


def _usable_permit():
    return build_gmo_official_settlement_post_permit(
        operator_current_turn_exact_confirmation_present=True,
        operator_readiness_present=True,
        settlement_side_provenance_ready=True,
    )


_ALL_GATES = dict(
    settlement_preflight_ready=True,
    fresh_runtime_one_position_gate_ready=True,
    active_pending_clear_confirmed=True,
    one_use_settlement_permit_usable=True,
    hard_guard_controlled_supply_default_deny_present=True,
    sanitized_preview_ready=True,
    credential_presence_safe_boolean=True,
    settlement_size_source_present_not_exposed=True,
    official_settlement_route_ready=True,
    market_open_safe_label_confirmed=True,
    ticker_fresh_safe_label_confirmed=True,
    spread_within_limit_safe_label_confirmed=True,
)


def _granted_activation():
    return build_official_settlement_execution_activation(
        operator_input=_valid_operator_input(), **_ALL_GATES
    )


def _settlement_plan():
    source = SealedOfficialSettlementValueSource(
        operator_supplied_symbol_value="USD_JPY",
        operator_supplied_size_value=SYNTHETIC_SIZE,
    )
    return source.build_bound_official_settlement_request_plan_internal(
        side_provenance=derive_official_settlement_side_from_prior_entry(
            "ENTRY_BUY"
        )
    )


def _entry_like_plan():
    from app.private_api.order_builders import build_gmo_fx_entry_request_plan

    return build_gmo_fx_entry_request_plan(
        symbol="USD_JPY", side="BUY", size=SYNTHETIC_SIZE
    )


class TestOperatorInputVerification:
    def test_valid_input_verifies_and_derives_sell(self) -> None:
        ok, provenance, reason = verify_official_settlement_operator_input(
            _valid_operator_input()
        )
        assert ok
        assert reason == "OPERATOR_INPUT_VERIFIED"
        assert provenance.settlement_side_safe_label == "SETTLEMENT_SELL"

    @pytest.mark.parametrize(
        ("field", "reason"),
        [
            ("exact_confirmation", "OPERATOR_EXACT_CONFIRMATION_MISMATCH"),
            ("readiness", "OPERATOR_READINESS_MISMATCH"),
            ("understands_risk", "OPERATOR_UNDERSTANDS_RISK_MISMATCH"),
        ],
    )
    def test_each_mismatch_is_denied(self, field: str, reason: str) -> None:
        kwargs = {
            "prior_entry_signal_safe_label": "ENTRY_BUY",
            "exact_confirmation": REQUIRED_SETTLEMENT_EXACT_CONFIRMATION,
            "readiness": REQUIRED_SETTLEMENT_READINESS,
            "understands_risk": REQUIRED_SETTLEMENT_UNDERSTANDS_RISK,
        }
        kwargs[field] = "TYPO_VALUE"
        ok, _, got_reason = verify_official_settlement_operator_input(
            OfficialSettlementOperatorCurrentTurnInput(**kwargs)
        )
        assert not ok
        assert got_reason == reason

    @pytest.mark.parametrize("signal", ["HOLD", "", "UNKNOWN"])
    def test_non_derivable_prior_signal_is_denied(self, signal: str) -> None:
        operator_input = OfficialSettlementOperatorCurrentTurnInput(
            prior_entry_signal_safe_label=signal,
            exact_confirmation=REQUIRED_SETTLEMENT_EXACT_CONFIRMATION,
            readiness=REQUIRED_SETTLEMENT_READINESS,
            understands_risk=REQUIRED_SETTLEMENT_UNDERSTANDS_RISK,
        )
        ok, _, reason = verify_official_settlement_operator_input(operator_input)
        assert not ok
        assert reason == "SETTLEMENT_SIDE_NOT_DERIVABLE"

    def test_entry_confirmation_is_not_reusable_for_settlement(self) -> None:
        operator_input = OfficialSettlementOperatorCurrentTurnInput(
            prior_entry_signal_safe_label="ENTRY_BUY",
            exact_confirmation=(
                "CONFIRM_ONE_ENTRY_POST_MAX_NO_RETRY_NO_REPOST_NO_SETTLEMENT"
            ),
            readiness=REQUIRED_SETTLEMENT_READINESS,
            understands_risk=REQUIRED_SETTLEMENT_UNDERSTANDS_RISK,
        )
        ok, _, reason = verify_official_settlement_operator_input(operator_input)
        assert not ok
        assert reason == "OPERATOR_EXACT_CONFIRMATION_MISMATCH"


class TestSettlementPermit:
    def test_granted_permit_is_usable_once_and_never_truthy(self) -> None:
        permit = _usable_permit()
        assert permit.usable_for_one_settlement_post
        assert permit.hard_guard_allow_resolved is False
        assert not permit

    @pytest.mark.parametrize(
        ("kwargs", "status"),
        [
            (
                {"operator_current_turn_exact_confirmation_present": False},
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_MISSING_CURRENT_TURN_CONFIRMATION,
            ),
            (
                {"operator_readiness_present": False},
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_MISSING_OPERATOR_READINESS,
            ),
            (
                {"settlement_side_provenance_ready": False},
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_SIDE_PROVENANCE_NOT_READY,
            ),
            (
                {"retry_or_repost_context": True},
                GmoOfficialSettlementPostPermitStatus
                .PERMIT_DENIED_RETRY_OR_REPOST_CONTEXT,
            ),
        ],
    )
    def test_each_missing_signal_denies(self, kwargs, status) -> None:
        base = dict(
            operator_current_turn_exact_confirmation_present=True,
            operator_readiness_present=True,
            settlement_side_provenance_ready=True,
        )
        base.update(kwargs)
        permit = build_gmo_official_settlement_post_permit(**base)
        assert not permit.usable_for_one_settlement_post
        assert permit.status is status

    def test_consumed_permit_cannot_authorize_again(self) -> None:
        consumed = consume_gmo_official_settlement_post_permit(_usable_permit())
        assert consumed.consumed
        assert not consumed.usable_for_one_settlement_post

    @pytest.mark.parametrize(
        "scope",
        ["ENTRY", "ENTRY_ONLY", "GENERIC", "GENERIC_CLOSE", "CANCEL", "CHANGE"],
    )
    def test_forbidden_scopes_raise(self, scope: str) -> None:
        with pytest.raises(GmoOfficialSettlementPermitScopeError):
            assert_settlement_only_permit_scope(scope)

    def test_unknown_scope_raises(self) -> None:
        with pytest.raises(GmoOfficialSettlementPermitScopeError):
            assert_settlement_only_permit_scope("SOMETHING_ELSE")

    def test_settlement_scope_passes(self) -> None:
        assert_settlement_only_permit_scope("SETTLEMENT_ONLY")


class TestActivation:
    def test_all_gates_grant_one_use_settlement_only_activation(self) -> None:
        activation = _granted_activation()
        assert activation.granted
        assert activation.settlement_side_safe_label == "SETTLEMENT_SELL"
        assert activation.settlement_only
        assert activation.one_use
        assert activation.entry_allowed is False
        assert activation.generic_close_allowed is False
        assert activation.position_specific_allowed is False
        assert activation.retry_allowed is False
        assert activation.repost_allowed is False
        assert activation.second_post_allowed is False
        assert not activation

    def test_activation_repr_is_sanitized(self) -> None:
        activation = _granted_activation()
        assert "sanitized" in repr(activation)
        assert SYNTHETIC_SIZE not in repr(activation)

    @pytest.mark.parametrize("gate", sorted(_ALL_GATES))
    def test_each_missing_gate_denies(self, gate: str) -> None:
        gates = dict(_ALL_GATES)
        gates[gate] = False
        activation = build_official_settlement_execution_activation(
            operator_input=_valid_operator_input(), **gates
        )
        assert not activation.granted
        assert activation.grants_hard_guard_allow is False
        assert activation.denied_reason

    def test_operator_mismatch_denies_before_gates(self) -> None:
        operator_input = OfficialSettlementOperatorCurrentTurnInput(
            prior_entry_signal_safe_label="ENTRY_BUY",
            exact_confirmation="WRONG",
            readiness=REQUIRED_SETTLEMENT_READINESS,
            understands_risk=REQUIRED_SETTLEMENT_UNDERSTANDS_RISK,
        )
        activation = build_official_settlement_execution_activation(
            operator_input=operator_input, **_ALL_GATES
        )
        assert not activation.granted


class TestSingleCallSite:
    def test_granted_activation_sends_exactly_once(self) -> None:
        sender = FakeOfficialSettlementOneShotSender(
            preset_outcome=SettlementPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
        )
        result = send_official_settlement_post_once(
            activation=_granted_activation(),
            request_plan=_settlement_plan(),
            sender=sender,
        )
        assert sender.send_call_count == 1
        assert result.settlement_post_attempted
        assert result.settlement_post_attempt_count == 1
        assert result.outcome_category is (
            SettlementPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
        )
        assert result.next_recommended_step == (
            "POST_SETTLEMENT_READ_ONLY_NO_POSITION_CONFIRMATION_NO_POST"
        )

    @pytest.mark.parametrize(
        "outcome",
        [
            SettlementPostSafeOutcome.RESULT_REJECTED_SANITIZED,
            SettlementPostSafeOutcome.RESULT_UNKNOWN_SANITIZED,
            SettlementPostSafeOutcome.RESULT_TIMEOUT_SANITIZED,
            SettlementPostSafeOutcome.RESULT_NETWORK_ERROR_SANITIZED,
            SettlementPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED,
        ],
    )
    def test_any_non_accepted_outcome_never_resends(self, outcome) -> None:
        sender = FakeOfficialSettlementOneShotSender(preset_outcome=outcome)
        result = send_official_settlement_post_once(
            activation=_granted_activation(),
            request_plan=_settlement_plan(),
            sender=sender,
        )
        assert sender.send_call_count == 1
        assert result.retry_performed is False
        assert result.repost_performed is False
        assert result.second_post_performed is False
        assert result.next_recommended_step == (
            "REJECTED_OR_UNKNOWN_SAFE_REVIEW_NO_REPOST"
        )

    def test_ungranted_activation_blocks_before_post(self) -> None:
        activation = build_official_settlement_execution_activation(
            operator_input=_valid_operator_input(),
            **{**_ALL_GATES, "settlement_preflight_ready": False},
        )
        sender = FakeOfficialSettlementOneShotSender()
        result = send_official_settlement_post_once(
            activation=activation,
            request_plan=_settlement_plan(),
            sender=sender,
        )
        assert sender.send_call_count == 0
        assert result.settlement_post_attempted is False
        assert result.outcome_category is (
            SettlementPostSafeOutcome.RESULT_BLOCKED_BEFORE_POST_SANITIZED
        )

    def test_entry_plan_is_blocked_before_post(self) -> None:
        sender = FakeOfficialSettlementOneShotSender()
        result = send_official_settlement_post_once(
            activation=_granted_activation(),
            request_plan=_entry_like_plan(),
            sender=sender,
        )
        assert sender.send_call_count == 0
        assert result.outcome_category is (
            SettlementPostSafeOutcome.RESULT_BLOCKED_BEFORE_POST_SANITIZED
        )
        assert "REQUEST_PLAN_NOT_OFFICIAL_SETTLEMENT_ONLY" in (
            result.next_recommended_step
        )

    def test_result_never_exposes_and_never_truthy(self) -> None:
        result = send_official_settlement_post_once(
            activation=_granted_activation(),
            request_plan=_settlement_plan(),
            sender=FakeOfficialSettlementOneShotSender(),
        )
        assert result.entry_post_performed is False
        assert result.generic_close_performed is False
        assert result.position_specific_settlement_performed is False
        assert result.raw_response_exposed is False
        assert result.raw_ids_exposed is False
        assert result.raw_price_or_size_values_exposed is False
        assert result.raw_profit_loss_values_exposed is False
        assert result.credential_value_exposed is False
        assert not result

    def test_fake_sender_refuses_second_call(self) -> None:
        sender = FakeOfficialSettlementOneShotSender()
        sender.send_settlement_once_sanitized(
            method="POST", path="/private/v1/closeOrder", body_json="{}"
        )
        with pytest.raises(GmoOfficialSettlementExecutionBoundaryError):
            sender.send_settlement_once_sanitized(
                method="POST", path="/private/v1/closeOrder", body_json="{}"
            )

    def test_refusing_sender_proves_default_state_cannot_send(self) -> None:
        with pytest.raises(GmoOfficialSettlementExecutionBoundaryError):
            RefusingOfficialSettlementOneShotSender().send_settlement_once_sanitized(
                method="POST", path="/private/v1/closeOrder", body_json="{}"
            )


class TestModuleIsolation:
    def test_module_has_no_real_post_capability_surface(self) -> None:
        source = inspect.getsource(module)
        assert "httpx" not in source
        assert "live_order_once" not in source
        assert "live_verification" not in source
        assert "os.environ" not in source
        assert "getenv" not in source
        assert "requests" not in source
        assert "build_auth_headers" not in source
