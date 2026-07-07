"""No-POST tests for the actual entry execution boundary.

These tests pin that the boundary is fail-closed and non-executing in this
phase: the activation is granted only with every gate satisfied, is
entry-only and single-use, the single reviewed call site refuses without a
granted activation / an entry-only plan / a passing hard guard, sends at most
once with no retry path, rejects settlement/close/generic plans, exposes no
raw/ID/value/credential, and the default sender refuses to send. Only fake
senders are used; there is no network and no credential access.
"""

from __future__ import annotations

import pathlib

import pytest

from app.private_api.order_builders import (
    build_gmo_fx_entry_request_plan,
    build_gmo_fx_official_settlement_request_plan,
)
from app.services.gmo_live_actual_entry_execution_boundary import (
    REQUIRED_ENTRY_EXACT_CONFIRMATION,
    REQUIRED_ENTRY_READINESS,
    REQUIRED_ENTRY_UNDERSTANDS_RISK,
    ActualEntryExecutionBoundaryError,
    ActualEntryOperatorCurrentTurnInput,
    EntryPostSafeOutcome,
    FakeActualEntryOneShotSender,
    RefusingActualEntryOneShotSender,
    build_actual_entry_execution_activation,
    send_actual_entry_post_once,
    verify_actual_entry_operator_input,
)

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "services"
    / "gmo_live_actual_entry_execution_boundary.py"
)


def _operator_input(**overrides: str) -> ActualEntryOperatorCurrentTurnInput:
    base = dict(
        signal_type_safe_label="ENTRY_BUY",
        exact_confirmation=REQUIRED_ENTRY_EXACT_CONFIRMATION,
        readiness=REQUIRED_ENTRY_READINESS,
        understands_risk=REQUIRED_ENTRY_UNDERSTANDS_RISK,
    )
    base.update(overrides)
    return ActualEntryOperatorCurrentTurnInput(**base)  # type: ignore[arg-type]


def _granted_activation(**overrides: object):
    kwargs: dict[str, object] = dict(
        operator_input=_operator_input(),
        final_preflight_ready=True,
        fresh_runtime_gate_ready=True,
        written_signoff_recorded=True,
        paper_evidence_confirmed=True,
        anomaly_evidence_confirmed=True,
        one_use_entry_permit_usable=True,
        hard_guard_controlled_supply_default_deny_present=True,
        sanitized_preview_ready=True,
        credential_presence_safe_boolean=True,
    )
    kwargs.update(overrides)
    return build_actual_entry_execution_activation(**kwargs)  # type: ignore[arg-type]


def _entry_plan():
    return build_gmo_fx_entry_request_plan(symbol="USD_JPY", side="BUY", size="1")


class TestOperatorInputVerification:
    def test_exact_match_buy_verifies_to_open_buy(self) -> None:
        ok, action, reason = verify_actual_entry_operator_input(_operator_input())
        assert ok is True
        assert action == "ENTRY_OPEN_BUY"
        assert reason == "OPERATOR_INPUT_VERIFIED"

    def test_exact_match_sell_verifies_to_open_sell(self) -> None:
        ok, action, _ = verify_actual_entry_operator_input(
            _operator_input(signal_type_safe_label="ENTRY_SELL")
        )
        assert ok is True
        assert action == "ENTRY_OPEN_SELL"

    def test_hold_is_never_executable(self) -> None:
        ok, action, reason = verify_actual_entry_operator_input(
            _operator_input(signal_type_safe_label="HOLD")
        )
        assert ok is False
        assert action == ""
        assert reason == "OPERATOR_SIGNAL_NOT_EXECUTABLE"

    @pytest.mark.parametrize(
        ("field", "reason"),
        [
            ("exact_confirmation", "OPERATOR_EXACT_CONFIRMATION_MISMATCH"),
            ("readiness", "OPERATOR_READINESS_MISMATCH"),
            ("understands_risk", "OPERATOR_UNDERSTANDS_RISK_MISMATCH"),
        ],
    )
    def test_any_mismatch_fails(self, field: str, reason: str) -> None:
        ok, _, got_reason = verify_actual_entry_operator_input(
            _operator_input(**{field: "WRONG_VALUE"})
        )
        assert ok is False
        assert got_reason == reason


class TestActivationFactory:
    def test_all_gates_satisfied_grants_one_use_entry_only(self) -> None:
        activation = _granted_activation()
        assert activation.granted is True
        assert activation.order_action_safe_label == "ENTRY_OPEN_BUY"
        assert activation.entry_only is True
        assert activation.one_use is True
        assert activation.settlement_allowed is False
        assert activation.close_allowed is False
        assert activation.generic_order_allowed is False
        assert activation.retry_allowed is False
        assert activation.repost_allowed is False
        assert activation.second_post_allowed is False
        assert activation.grants_hard_guard_allow is True
        assert not activation  # never truthy

    @pytest.mark.parametrize(
        ("override", "reason"),
        [
            ({"final_preflight_ready": False}, "FINAL_PREFLIGHT_NOT_READY"),
            ({"fresh_runtime_gate_ready": False}, "FRESH_RUNTIME_GATE_NOT_READY"),
            ({"written_signoff_recorded": False}, "WRITTEN_SIGNOFF_NOT_RECORDED"),
            ({"paper_evidence_confirmed": False}, "PAPER_EVIDENCE_NOT_CONFIRMED"),
            ({"anomaly_evidence_confirmed": False}, "ANOMALY_EVIDENCE_NOT_CONFIRMED"),
            ({"one_use_entry_permit_usable": False}, "ENTRY_PERMIT_NOT_USABLE"),
            (
                {"hard_guard_controlled_supply_default_deny_present": False},
                "HARD_GUARD_CONTROLLED_SUPPLY_MISSING",
            ),
            ({"sanitized_preview_ready": False}, "SANITIZED_PREVIEW_NOT_READY"),
            (
                {"credential_presence_safe_boolean": False},
                "CREDENTIAL_PRESENCE_NOT_CONFIRMED",
            ),
        ],
    )
    def test_any_missing_gate_denies(self, override: dict, reason: str) -> None:
        activation = _granted_activation(**override)
        assert activation.granted is False
        assert activation.denied_reason == reason
        assert activation.grants_hard_guard_allow is False
        assert activation.order_action_safe_label == ""

    def test_operator_mismatch_denies(self) -> None:
        activation = _granted_activation(
            operator_input=_operator_input(exact_confirmation="WRONG")
        )
        assert activation.granted is False
        assert activation.denied_reason == "OPERATOR_EXACT_CONFIRMATION_MISMATCH"

    def test_repr_and_str_are_sanitized(self) -> None:
        activation = _granted_activation()
        assert repr(activation) == "ActualEntryExecutionActivation(<sanitized>)"
        assert str(activation) == "ActualEntryExecutionActivation(<sanitized>)"
        assert "ENTRY_OPEN_BUY" not in repr(activation)


class TestDefaultSenderCannotSend:
    def test_refusing_sender_raises(self) -> None:
        with pytest.raises(ActualEntryExecutionBoundaryError):
            RefusingActualEntryOneShotSender().send_entry_once_sanitized(
                method="POST", path="/private/v1/order", body_json="{}"
            )

    def test_granted_activation_with_refusing_sender_raises_no_post(self) -> None:
        with pytest.raises(ActualEntryExecutionBoundaryError):
            send_actual_entry_post_once(
                activation=_granted_activation(),
                request_plan=_entry_plan(),
                sender=RefusingActualEntryOneShotSender(),
            )


class TestSingleReviewedCallSite:
    def test_denied_activation_blocks_before_post(self) -> None:
        result = send_actual_entry_post_once(
            activation=_granted_activation(final_preflight_ready=False),
            request_plan=_entry_plan(),
            sender=FakeActualEntryOneShotSender(),
        )
        assert result.post_attempted is False
        assert result.post_attempt_count == 0
        assert result.outcome_category is (
            EntryPostSafeOutcome.RESULT_BLOCKED_BEFORE_POST_SANITIZED
        )
        assert not result

    def test_settlement_plan_is_rejected(self) -> None:
        settlement_plan = build_gmo_fx_official_settlement_request_plan(
            symbol="USD_JPY", side="SELL", size="1"
        )
        sender = FakeActualEntryOneShotSender(
            preset_outcome=EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
        )
        result = send_actual_entry_post_once(
            activation=_granted_activation(),
            request_plan=settlement_plan,
            sender=sender,
        )
        assert result.post_attempted is False
        assert result.outcome_category is (
            EntryPostSafeOutcome.RESULT_BLOCKED_BEFORE_POST_SANITIZED
        )
        assert sender.send_call_count == 0  # sender never invoked

    @pytest.mark.parametrize(
        ("outcome", "expected_next"),
        [
            (
                EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED,
                "POST_ENTRY_READ_ONLY_POSITION_CONFIRMATION_NO_POST",
            ),
            (
                EntryPostSafeOutcome.RESULT_REJECTED_SANITIZED,
                "REJECTED_OR_UNKNOWN_SAFE_REVIEW_NO_REPOST",
            ),
            (
                EntryPostSafeOutcome.RESULT_TIMEOUT_SANITIZED,
                "REJECTED_OR_UNKNOWN_SAFE_REVIEW_NO_REPOST",
            ),
            (
                EntryPostSafeOutcome.RESULT_SERVER_ERROR_SANITIZED,
                "REJECTED_OR_UNKNOWN_SAFE_REVIEW_NO_REPOST",
            ),
        ],
    )
    def test_single_send_maps_outcome_and_never_resends(
        self, outcome: EntryPostSafeOutcome, expected_next: str
    ) -> None:
        sender = FakeActualEntryOneShotSender(preset_outcome=outcome)
        result = send_actual_entry_post_once(
            activation=_granted_activation(),
            request_plan=_entry_plan(),
            sender=sender,
        )
        assert result.post_attempted is True
        assert result.post_attempt_count == 1
        assert result.outcome_category is outcome
        assert result.retry_performed is False
        assert result.repost_performed is False
        assert result.second_post_performed is False
        assert result.settlement_post_performed is False
        assert result.generic_close_performed is False
        assert result.next_recommended_step == expected_next
        assert sender.send_call_count == 1  # exactly one attempt

    def test_result_exposes_no_raw_id_value_or_credential(self) -> None:
        sender = FakeActualEntryOneShotSender(
            preset_outcome=EntryPostSafeOutcome.RESULT_ACCEPTED_SANITIZED
        )
        result = send_actual_entry_post_once(
            activation=_granted_activation(),
            request_plan=_entry_plan(),
            sender=sender,
        )
        assert result.raw_response_exposed is False
        assert result.raw_ids_exposed is False
        assert result.raw_price_or_size_values_exposed is False
        assert result.credential_value_exposed is False


class TestSourceScan:
    def test_module_does_not_import_live_verification_or_live_order_once(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "app.live_verification" not in text
        assert "live_order_once" not in text

    def test_module_has_no_settlement_or_close_route(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "closeOrder" not in text
        assert "settlePosition" not in text

    def test_module_does_not_read_env_or_network_client(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        assert "os.environ" not in text
        assert "getenv" not in text
        assert "load_dotenv" not in text
        assert "httpx" not in text
        assert "requests" not in text

    def test_module_has_no_persistent_allow_literals(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8").replace(" ", "")
        assert "allow_real_broker_post=True" not in text
        assert "allow_live_http_post=True" not in text
        assert "actual_entry_POST_allowed=True" not in text
        assert "grants_hard_guard_allow=True" not in text
        # allow is derived from the granted flag at the single call site.
        assert "assert_real_broker_post_allowed(allow=activation.grants_hard_guard_allow)" in text
