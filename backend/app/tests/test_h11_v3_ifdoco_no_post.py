"""Focused no-POST tests for H-11 v3 IFDOCO and persistent fake lifecycle."""

from __future__ import annotations

import inspect
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.private_api.order_builders import (
    GMO_FX_IFDOCO_ORDER_PATH,
    REQUEST_KIND_IFDOCO_PROTECTED_ENTRY,
    GmoFxOrderBuilderError,
    build_gmo_fx_ifdoco_request_plan,
)
from app.services.h11_v3_ifdoco_profile import (
    H11_V3_CAPABILITY_CONTRACT_HASH,
    H11_V3_CONFIG_HASH,
    H11V3AutomaticPlanStatus,
    H11V3Direction,
    H11V3IfdocoCandidate,
    H11V3ProfileError,
    _calculate_capability_contract_hash,
    _calculate_config_hash,
    build_h11_v3_automatic_plan_no_post,
    build_h11_v3_candidate,
    build_h11_v3_ifdoco_plan_no_post,
    build_h11_v3_safe_preview,
)
from app.services.h11_v3_observed_live_state import (
    H11V3FakeCycleInput,
    H11V3FakeOutcome,
    H11V3FakeSafetyGate,
    H11V3ObservedPersistentState,
    H11V3ObservedState,
    H11V3ObservedStateError,
    H11V3ObservedStateStore,
    run_h11_v3_fake_cycle_no_post,
)


def test_v3_config_hash_is_frozen_to_canonical_spec() -> None:
    assert H11_V3_CONFIG_HASH == _calculate_config_hash()
    assert H11_V3_CAPABILITY_CONTRACT_HASH == _calculate_capability_contract_hash()
    preview = build_h11_v3_safe_preview()
    assert preview.config_hash_matches is True
    assert preview.capability_contract_hash_matches is True
    assert preview.server_side_oco_required is True
    assert preview.actual_post_allowed is False
    assert preview.actual_post_count == 0


@pytest.mark.parametrize("direction", [H11V3Direction.BUY, H11V3Direction.SELL])
def test_candidate_brackets_entry_and_builds_ifdoco(direction: H11V3Direction) -> None:
    candidate = build_h11_v3_candidate(
        direction=direction,
        reference_close=Decimal("150.000"),
        atr_24=Decimal("0.200"),
        price_increment=Decimal("0.001"),
    )
    if direction is H11V3Direction.BUY:
        assert candidate.stop_loss_price < candidate.entry_stop_price
        assert candidate.entry_stop_price < candidate.take_profit_price
    else:
        assert candidate.take_profit_price < candidate.entry_stop_price
        assert candidate.entry_stop_price < candidate.stop_loss_price
    plan = build_h11_v3_ifdoco_plan_no_post(
        candidate=candidate,
        symbol="USD_JPY",
        client_order_id="SYNTHETIC123",
    )
    body = json.loads(plan.body_json)
    assert plan.request_kind == REQUEST_KIND_IFDOCO_PROTECTED_ENTRY
    assert plan.path == GMO_FX_IFDOCO_ORDER_PATH == "/private/v1/ifoOrder"
    assert body["firstExecutionType"] == "STOP"
    assert body["firstSize"] == body["secondSize"] == "10000"
    assert body["clientOrderId"] == "SYNTHETIC123"


def test_ifdoco_builder_rejects_unprotected_or_mutable_shapes() -> None:
    with pytest.raises(GmoFxOrderBuilderError, match="must match"):
        build_gmo_fx_ifdoco_request_plan(
            symbol="USD_JPY",
            first_side="BUY",
            first_size="10000",
            first_price="150.1",
            second_size="1",
            second_limit_price="151.0",
            second_stop_price="149.0",
        )
    with pytest.raises(GmoFxOrderBuilderError, match="must be STOP"):
        build_gmo_fx_ifdoco_request_plan(
            symbol="USD_JPY",
            first_side="BUY",
            first_size="10000",
            first_price="150.1",
            second_size="10000",
            second_limit_price="151.0",
            second_stop_price="149.0",
            first_execution_type="LIMIT",
        )
    with pytest.raises(GmoFxOrderBuilderError, match="bracket"):
        build_gmo_fx_ifdoco_request_plan(
            symbol="USD_JPY",
            first_side="BUY",
            first_size="10000",
            first_price="150.1",
            second_size="10000",
            second_limit_price="149.0",
            second_stop_price="151.0",
        )


def test_automatic_preview_signal_maps_to_protected_plan_no_post() -> None:
    decision = build_h11_v3_automatic_plan_no_post(
        preview_signal_safe_label="AUTO_PREVIEW_SIGNAL_BUY",
        expected_config_hash=H11_V3_CONFIG_HASH,
        reference_close=Decimal("150.000"),
        atr_24=Decimal("0.200"),
        price_increment=Decimal("0.001"),
        symbol="USD_JPY",
        client_order_id="SYNTHETIC123",
    )
    assert decision.status is H11V3AutomaticPlanStatus.READY_NO_POST
    assert decision.plan is not None
    assert decision.actual_post_allowed is False
    assert decision.actual_post_count == 0
    assert "SYNTHETIC123" not in repr(decision)


@pytest.mark.parametrize(
    "signal",
    ["AUTO_PREVIEW_SIGNAL_HOLD", "AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED", ""],
)
def test_automatic_non_entry_signal_is_blocked(signal: str) -> None:
    decision = build_h11_v3_automatic_plan_no_post(
        preview_signal_safe_label=signal,
        expected_config_hash=H11_V3_CONFIG_HASH,
        reference_close=Decimal("150.000"),
        atr_24=Decimal("0.200"),
        price_increment=Decimal("0.001"),
        symbol="USD_JPY",
    )
    assert decision.status is H11V3AutomaticPlanStatus.BLOCKED_NO_SIGNAL
    assert decision.plan is None


def test_automatic_config_mismatch_blocks_before_plan_construction() -> None:
    decision = build_h11_v3_automatic_plan_no_post(
        preview_signal_safe_label="AUTO_PREVIEW_SIGNAL_BUY",
        expected_config_hash="sha256:wrong",
        reference_close=Decimal("150.000"),
        atr_24=Decimal("0.200"),
        price_increment=Decimal("0.001"),
        symbol="USD_JPY",
    )
    assert decision.status is H11V3AutomaticPlanStatus.BLOCKED_CONFIG_MISMATCH
    assert decision.plan is None


def test_profile_rejects_nonpositive_inputs_and_size_drift() -> None:
    with pytest.raises(H11V3ProfileError):
        build_h11_v3_candidate(
            direction=H11V3Direction.BUY,
            reference_close=Decimal("150"),
            atr_24=Decimal("0"),
            price_increment=Decimal("0.001"),
        )
    candidate = H11V3IfdocoCandidate(
        direction=H11V3Direction.BUY,
        entry_stop_price=Decimal("150.1"),
        take_profit_price=Decimal("151"),
        stop_loss_price=Decimal("149"),
        size_units=1,
    )
    with pytest.raises(H11V3ProfileError, match="frozen"):
        build_h11_v3_ifdoco_plan_no_post(candidate=candidate, symbol="USD_JPY")


def test_profile_rejects_symbol_and_tick_capability_drift() -> None:
    with pytest.raises(H11V3ProfileError, match="price increment"):
        build_h11_v3_candidate(
            direction=H11V3Direction.BUY,
            reference_close=Decimal("150"),
            atr_24=Decimal("0.2"),
            price_increment=Decimal("0.01"),
        )
    candidate = build_h11_v3_candidate(
        direction=H11V3Direction.BUY,
        reference_close=Decimal("150"),
        atr_24=Decimal("0.2"),
        price_increment=Decimal("0.001"),
    )
    with pytest.raises(H11V3ProfileError, match="symbol"):
        build_h11_v3_ifdoco_plan_no_post(candidate=candidate, symbol="EUR_JPY")


def _store(tmp_path: Path) -> H11V3ObservedStateStore:
    return H11V3ObservedStateStore(tmp_path / "state.json")


def _open_gate() -> H11V3FakeSafetyGate:
    return H11V3FakeSafetyGate(
        boot_reconciled=True,
        budget_remaining=True,
        kill_off=True,
        dead_man_alive=True,
        notification_ready=True,
        broker_native_expiry_confirmed=True,
        sealed_credential_boundary_reviewed=True,
    )


def test_fake_ifdoco_and_broker_oco_cycle_reconciles_flat(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = run_h11_v3_fake_cycle_no_post(
        store=store,
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
            broker_oco_settled=True,
            flat_reconciled=True,
        ),
    )
    assert result.final_state is H11V3ObservedState.FLAT_RECONCILED
    assert result.entry_attempt_count == 1
    assert result.settlement_attempt_count == 0
    assert result.actual_post is False
    state_payload = json.loads((tmp_path / "state.json").read_text())
    assert state_payload["reconciled_flat_cycle_count"] == 1
    assert state_payload["actual_post_count"] == 0


def test_fake_timeout_halts_and_never_retries(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = run_h11_v3_fake_cycle_no_post(
        store=store,
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.TIMEOUT_SANITIZED,
            protection_reconciled=False,
            position_protected=False,
        ),
    )
    second = run_h11_v3_fake_cycle_no_post(
        store=store,
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
        ),
    )
    assert first.final_state is H11V3ObservedState.HALTED
    assert second.final_state is H11V3ObservedState.HALTED
    assert second.entry_attempt_count == 1
    assert "TIMEOUT" in second.halt_reason_safe_label


def test_unprotected_acceptance_halts(tmp_path: Path) -> None:
    result = run_h11_v3_fake_cycle_no_post(
        store=_store(tmp_path),
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=False,
            position_protected=True,
        ),
    )
    assert result.final_state is H11V3ObservedState.HALTED
    assert result.halt_reason_safe_label == "SERVER_SIDE_PROTECTION_NOT_RECONCILED"


def test_settlement_unknown_halts_after_one_attempt(tmp_path: Path) -> None:
    result = run_h11_v3_fake_cycle_no_post(
        store=_store(tmp_path),
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
            settlement_outcome=H11V3FakeOutcome.UNKNOWN_SANITIZED,
        ),
    )
    assert result.final_state is H11V3ObservedState.HALTED
    assert result.entry_attempt_count == 1
    assert result.settlement_attempt_count == 1


def test_default_closed_safety_gate_blocks_before_attempt(tmp_path: Path) -> None:
    result = run_h11_v3_fake_cycle_no_post(
        store=_store(tmp_path),
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=H11V3FakeSafetyGate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
        ),
    )
    assert result.final_state is H11V3ObservedState.HALTED
    assert result.entry_attempt_count == 0
    assert result.halt_reason_safe_label == "BOOT_RECONCILIATION_REQUIRED"


def test_second_entry_same_day_is_blocked(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = run_h11_v3_fake_cycle_no_post(
        store=store,
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
            broker_oco_settled=True,
            flat_reconciled=True,
        ),
    )
    second = run_h11_v3_fake_cycle_no_post(
        store=store,
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
        ),
    )
    assert first.final_state is H11V3ObservedState.FLAT_RECONCILED
    assert second.final_state is H11V3ObservedState.HALTED
    assert second.entry_attempt_count == 0
    assert second.halt_reason_safe_label == "MAX_ENTRIES_PER_DAY_BLOCKED"


def test_restart_from_durable_entry_attempt_halts_without_resend(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    persisted = H11V3ObservedPersistentState(
        state=H11V3ObservedState.ENTRY_ATTEMPT_STARTED.value,
        entry_attempt_count=1,
        last_entry_day_jst="2026-07-13",
    )
    state_path.write_text(json.dumps(persisted.__dict__))
    result = run_h11_v3_fake_cycle_no_post(
        store=_store(tmp_path),
        cycle_input=H11V3FakeCycleInput(
            cycle_day_jst="2026-07-13",
            safety_gate=_open_gate(),
            entry_outcome=H11V3FakeOutcome.ACCEPTED_SANITIZED,
            protection_reconciled=True,
            position_protected=True,
        ),
    )
    assert result.final_state is H11V3ObservedState.HALTED
    assert result.entry_attempt_count == 1
    assert result.halt_reason_safe_label == "RESTART_RECONCILIATION_REQUIRED"


def test_concurrent_lock_is_blocked(tmp_path: Path) -> None:
    first = _store(tmp_path)
    second = _store(tmp_path)
    with first:
        with pytest.raises(H11V3ObservedStateError, match="concurrent"):
            second.__enter__()


def test_persisted_config_mismatch_is_blocked(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    payload = H11V3ObservedPersistentState().__dict__.copy()
    payload["config_hash"] = "sha256:wrong"
    state_path.write_text(json.dumps(payload))
    with _store(tmp_path) as store:
        with pytest.raises(H11V3ObservedStateError, match="config hash"):
            store.load()


def test_new_modules_have_no_network_env_or_sender_binding() -> None:
    import app.services.h11_v3_ifdoco_profile as profile
    import app.services.h11_v3_observed_live_state as state

    source = inspect.getsource(profile) + inspect.getsource(state)
    forbidden = (
        "httpx",
        "requests",
        "os.environ",
        "getenv",
        "load_dotenv",
        "build_auth_headers",
        "assert_real_broker_post_allowed",
        "allow=True",
    )
    for marker in forbidden:
        assert marker not in source
