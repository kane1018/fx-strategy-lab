"""Core E1 full-auto shadow tests: finite, offline, virtual-only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.shadow.e1.contracts import (
    E1ContractError,
    E1Policy,
    E1Stage,
    EngineLabel,
    EnginePhase,
    EntryIntent,
    FaultInjection,
    FrozenHypothesisRegistry,
    FrozenHypothesisSpec,
    GateAction,
    HypothesisLabel,
    MarketFrame,
    PositionSide,
    ShadowGateToken,
    VirtualPosition,
    build_hypothesis_decision,
    build_settlement_decision,
    canonical_timestamp,
    make_local_id,
    position_digest,
)
from app.shadow.e1.engine import (
    E1EngineError,
    E1ShadowFullAutoEngine,
)
from app.shadow.e1.persistence import (
    E1PersistenceError,
    JournalEventType,
    ShadowIntentJournal,
    VirtualVenueStateStore,
)
from app.shadow.e1.qualification import summarize_e1_journal

NOW = datetime(2026, 7, 10, 1, 0, tzinfo=UTC)


def _frame(now: datetime = NOW, *, bid: str = "150.000", ask: str = "150.004") -> MarketFrame:
    return MarketFrame.build(
        symbol="USD_JPY",
        evaluation_time=now,
        market_data_time=now,
        bid=bid,
        ask=ask,
    )


def _engine(
    tmp_path,
    *,
    run_id: str = "e1-test",
    policy: E1Policy | None = None,
    clock=None,
):
    active_policy = policy or E1Policy(cooldown_seconds=0)
    root = tmp_path / run_id
    journal = ShadowIntentJournal(
        root=root,
        path=root / "intent_journal.jsonl",
        run_id=run_id,
        config_hash=active_policy.config_hash,
    )
    venue = VirtualVenueStateStore(
        root=root,
        path=root / "virtual_venue_state.json",
        config_hash=active_policy.config_hash,
    )
    engine = E1ShadowFullAutoEngine(
        run_id=run_id,
        policy=active_policy,
        journal=journal,
        venue=venue,
        clock=clock or (lambda: NOW),
    )
    return engine, journal, venue, active_policy


def _ready_engine(tmp_path, *, run_id: str = "e1-test", policy: E1Policy | None = None):
    engine, journal, venue, active_policy = _engine(
        tmp_path, run_id=run_id, policy=policy
    )
    assert engine.boot_reconcile(now=NOW).value == "INITIAL_FLAT_CONFIRMED"
    engine.record_heartbeat(now=NOW)
    return engine, journal, venue, active_policy


def _buy(policy: E1Policy):
    return build_hypothesis_decision(
        HypothesisLabel.BUY_CANDIDATE,
        config_hash=policy.config_hash,
        reason_code="FIXTURE_BUY",
    )


def _sell(policy: E1Policy):
    return build_hypothesis_decision(
        HypothesisLabel.SELL_CANDIDATE,
        config_hash=policy.config_hash,
        reason_code="FIXTURE_SELL",
    )


def test_namespaces_are_exact_and_legacy_strings_are_rejected() -> None:
    assert {label.value for label in HypothesisLabel} == {
        "HYPOTHESIS_BUY_CANDIDATE",
        "HYPOTHESIS_SELL_CANDIDATE",
        "HYPOTHESIS_HOLD_CANDIDATE",
        "HYPOTHESIS_NO_ACTION",
    }
    assert {label.value for label in EngineLabel} == {
        "ENGINE_ENTRY_BUY_CANDIDATE",
        "ENGINE_ENTRY_SELL_CANDIDATE",
        "ENGINE_EXIT_CANDIDATE",
        "ENGINE_SETTLEMENT_CANDIDATE",
        "ENGINE_NO_ACTION",
    }
    with pytest.raises(E1ContractError):
        build_hypothesis_decision(  # type: ignore[arg-type]
            "ENTRY_BUY", config_hash=E1Policy().config_hash, reason_code="LEGACY"
        )


def test_no_action_is_terminal_and_issues_no_token(tmp_path) -> None:
    engine, journal, venue, policy = _ready_engine(tmp_path)
    decision = build_hypothesis_decision(
        HypothesisLabel.NO_ACTION,
        config_hash=policy.config_hash,
        reason_code="NO_ACTION_FIXTURE",
    )
    result = engine.process_decision(decision=decision, market=_frame())
    assert result.status == "ENGINE_NO_ACTION_TERMINAL"
    assert result.token_issued is False
    assert result.virtual_execution_attempted is False
    assert result.actual_post_count == 0
    assert venue.position is None
    assert not result
    assert journal.records[-1].event_type is JournalEventType.NO_ACTION_RECORDED


@pytest.mark.parametrize(
    ("decision_factory", "stop", "expected_side"),
    [
        (_buy, "149.000", PositionSide.LONG),
        (_sell, "151.000", PositionSide.SHORT),
    ],
)
def test_full_auto_virtual_entry_and_position_specific_settlement(
    tmp_path, decision_factory, stop, expected_side
) -> None:
    engine, journal, venue, policy = _ready_engine(tmp_path)
    entry = engine.process_decision(
        decision=decision_factory(policy),
        market=_frame(),
        protective_stop_price=stop,
    )
    assert entry.status == "VIRTUAL_EXECUTION_CONFIRMED"
    assert entry.phase is EnginePhase.POSITION_OPEN
    assert venue.position is not None
    assert venue.position.side is expected_side
    position_ref = venue.position.position_ref

    settlement = engine.process_decision(
        decision=build_settlement_decision(
            position_ref=position_ref,
            config_hash=policy.config_hash,
            reason_code="FIXTURE_POSITION_SPECIFIC_EXIT",
        ),
        market=_frame(NOW + timedelta(seconds=1)),
    )
    assert settlement.status == "VIRTUAL_EXECUTION_CONFIRMED"
    assert settlement.phase is EnginePhase.READY_FLAT
    assert venue.position is None
    summary = summarize_e1_journal(journal, policy=policy)
    assert summary.virtual_entry_effect_count == 1
    assert summary.virtual_settlement_effect_count == 1
    assert summary.durable_intent_count == 2
    assert summary.consumed_shadow_token_count == 2
    assert summary.virtual_execution_count == 2
    assert summary.cardinality_invariant_ok is True
    assert summary.actual_post_count == 0


def test_second_entry_scale_in_and_flip_are_blocked(tmp_path) -> None:
    engine, journal, venue, policy = _ready_engine(tmp_path)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    original = venue.position
    assert original is not None

    same_side = engine.process_decision(
        decision=_buy(policy),
        market=_frame(NOW + timedelta(seconds=1)),
        protective_stop_price="149.000",
    )
    opposite_side = engine.process_decision(
        decision=_sell(policy),
        market=_frame(NOW + timedelta(seconds=2)),
        protective_stop_price="151.000",
    )
    assert same_side.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert opposite_side.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert same_side.virtual_execution_attempted is False
    assert opposite_side.virtual_execution_attempted is False
    assert venue.position == original
    assert summarize_e1_journal(journal, policy=policy).virtual_entry_effect_count == 1


def test_wrong_position_reference_cannot_settle(tmp_path) -> None:
    engine, journal, venue, policy = _ready_engine(tmp_path)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    result = engine.process_decision(
        decision=build_settlement_decision(
            position_ref="vposition:wrong",
            config_hash=policy.config_hash,
            reason_code="WRONG_POSITION",
        ),
        market=_frame(NOW + timedelta(seconds=1)),
    )
    assert result.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert "POSITION_SPECIFIC_SETTLEMENT_MISMATCH" in result.reason_codes
    assert venue.position is not None
    assert (
        summarize_e1_journal(journal, policy=policy).virtual_settlement_effect_count
        == 0
    )


def test_protective_stop_is_mandatory_and_directional(tmp_path) -> None:
    engine, _journal, venue, policy = _ready_engine(tmp_path)
    missing = engine.process_decision(decision=_buy(policy), market=_frame())
    assert missing.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert missing.virtual_execution_attempted is False
    with pytest.raises(E1ContractError):
        engine.process_decision(
            decision=_buy(policy),
            market=_frame(NOW + timedelta(seconds=1)),
            protective_stop_price="151.000",
        )
    assert venue.position is None


def test_market_risk_gates_fail_closed_before_token(tmp_path) -> None:
    engine, _journal, venue, policy = _ready_engine(tmp_path)
    blocked = _frame(ask="150.020")
    result = engine.process_decision(
        decision=_buy(policy), market=blocked, protective_stop_price="149.000"
    )
    assert result.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert result.token_issued is False
    assert "SPREAD_LIMIT_EXCEEDED" in result.reason_codes
    assert venue.position is None


def test_prospective_stop_loss_is_checked_before_token_issue(tmp_path) -> None:
    policy = E1Policy(
        max_virtual_loss_per_trade=Decimal("0.5"),
        cooldown_seconds=0,
    )
    engine, _journal, venue, _ = _ready_engine(
        tmp_path, run_id="prospective-risk", policy=policy
    )
    result = engine.process_decision(
        decision=_buy(policy),
        market=_frame(),
        protective_stop_price="149.000",
    )
    assert result.status == "RISK_GATE_BLOCKED_NO_ACTION"
    assert "PER_TRADE_VIRTUAL_LOSS_CAP_EXCEEDED" in result.reason_codes
    assert result.token_issued is False
    assert venue.position is None


def test_hypothesis_registry_is_frozen_into_config_and_decision_identity(tmp_path) -> None:
    first_spec = FrozenHypothesisSpec(
        hypothesis_id="HYPOTHESIS_ALPHA",
        version="v1",
        rule_digest="a" * 64,
    )
    second_spec = FrozenHypothesisSpec(
        hypothesis_id="HYPOTHESIS_ALPHA",
        version="v2",
        rule_digest="b" * 64,
    )
    first_registry = FrozenHypothesisRegistry(specs=(first_spec,))
    second_registry = FrozenHypothesisRegistry(specs=(second_spec,))
    first_policy = E1Policy(hypothesis_registry=first_registry, cooldown_seconds=0)
    second_policy = E1Policy(hypothesis_registry=second_registry, cooldown_seconds=0)
    assert first_registry.registry_hash != second_registry.registry_hash
    assert first_policy.config_hash != second_policy.config_hash

    engine, _journal, venue, _ = _ready_engine(
        tmp_path, run_id="registry-valid", policy=first_policy
    )
    valid = build_hypothesis_decision(
        HypothesisLabel.BUY_CANDIDATE,
        config_hash=first_policy.config_hash,
        reason_code="REGISTERED_ALPHA",
        hypothesis_id="HYPOTHESIS_ALPHA",
        hypothesis_version="v1",
    )
    result = engine.process_decision(
        decision=valid, market=_frame(), protective_stop_price="149.000"
    )
    assert result.status == "VIRTUAL_EXECUTION_CONFIRMED"
    assert venue.position is not None

    blocked_engine, _blocked_journal, blocked_venue, _ = _ready_engine(
        tmp_path, run_id="registry-invalid", policy=first_policy
    )
    unregistered = build_hypothesis_decision(
        HypothesisLabel.BUY_CANDIDATE,
        config_hash=first_policy.config_hash,
        reason_code="UNREGISTERED_ALPHA",
        hypothesis_id="HYPOTHESIS_ALPHA",
        hypothesis_version="v2",
    )
    blocked = blocked_engine.process_decision(
        decision=unregistered,
        market=_frame(),
        protective_stop_price="149.000",
    )
    assert blocked.status == "KILL_HALTED_FLAT"
    assert blocked_engine.phase is EnginePhase.HALTED
    assert blocked_venue.position is None


def test_token_binds_canonical_intent_digest_and_blocks_payload_substitution(tmp_path) -> None:
    engine, journal, venue, policy = _ready_engine(
        tmp_path, run_id="intent-digest", policy=E1Policy(cooldown_seconds=0)
    )
    frame = _frame()
    valid_position = VirtualPosition(
        position_ref="vposition:digest",
        symbol="USD_JPY",
        side=PositionSide.LONG,
        units=policy.fixed_virtual_units,
        entry_price=frame.ask,
        protective_stop_price=Decimal("149"),
    )
    valid_intent = EntryIntent(
        intent_id="intent:digest",
        run_id="intent-digest",
        config_hash=policy.config_hash,
        created_at=frame.evaluation_time,
        position=valid_position,
    )
    token, reasons = engine._risk_gate.issue_entry_token(
        intent=valid_intent,
        market=frame,
        phase=EnginePhase.READY_FLAT,
    )
    assert token is not None and reasons == ()
    before = position_digest(None)
    planned = position_digest(valid_position)
    engine._authority.commit_intent(
        token=token,
        durable_append=lambda: journal.append(
            event_type=JournalEventType.INTENT_PREPARED,
            timestamp=frame.evaluation_time,
            status_label="DIGEST_BINDING_FIXTURE",
            expected_state_digest=before,
            position_count=0,
            action=GateAction.VIRTUAL_ENTRY,
            intent_id=valid_intent.intent_id,
            intent_digest=valid_intent.intent_digest,
            token_id=token.token_id,
            state_before_digest=before,
            planned_state_digest=planned,
        ),
    )
    journal.append(
        event_type=JournalEventType.VIRTUAL_EXECUTION_STARTED,
        timestamp=frame.evaluation_time,
        status_label="DIGEST_BINDING_EXECUTION_STARTED",
        expected_state_digest=before,
        position_count=0,
        action=GateAction.VIRTUAL_ENTRY,
        intent_id=valid_intent.intent_id,
        intent_digest=valid_intent.intent_digest,
        token_id=token.token_id,
        state_before_digest=before,
        planned_state_digest=planned,
    )
    replacement = EntryIntent(
        intent_id=valid_intent.intent_id,
        run_id=valid_intent.run_id,
        config_hash=valid_intent.config_hash,
        created_at=valid_intent.created_at,
        position=VirtualPosition(
            position_ref=valid_position.position_ref,
            symbol="USD_JPY",
            side=PositionSide.LONG,
            units=999,
            entry_price=valid_position.entry_price,
            protective_stop_price=valid_position.protective_stop_price,
        ),
    )
    assert replacement.intent_digest != valid_intent.intent_digest
    with pytest.raises(E1EngineError, match="binding mismatch"):
        engine._executor.execute_entry(
            token=token,
            intent=replacement,
            fault=FaultInjection(),
        )
    assert venue.position is None


def test_token_is_ttl_bound_single_use_and_not_replaceable_by_a_label(tmp_path) -> None:
    policy = E1Policy(cooldown_seconds=0)
    engine, journal, venue, _ = _ready_engine(tmp_path, run_id="token-used", policy=policy)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    prepared = next(
        record
        for record in journal.records
        if record.event_type is JournalEventType.INTENT_PREPARED
    )
    token = engine._authority._issued[prepared.token_id]
    append_was_called = False

    def append_duplicate() -> None:
        nonlocal append_was_called
        append_was_called = True

    with pytest.raises(E1EngineError, match="single-use"):
        engine._authority.commit_intent(
            token=token,
            durable_append=append_duplicate,
        )
    assert append_was_called is False
    assert sum(
        record.event_type is JournalEventType.INTENT_PREPARED
        and record.token_id == token.token_id
        for record in journal.records
    ) == 1
    with pytest.raises(E1EngineError, match="single-use"):
        engine._authority.begin_execution(
            token=token,
            action=GateAction.VIRTUAL_ENTRY,
            intent_id=prepared.intent_id,
            intent_digest=prepared.intent_digest,
        )
    with pytest.raises(E1EngineError, match="ShadowGateToken only"):
        engine._authority.commit_intent(  # type: ignore[arg-type]
            token=EngineLabel.ENTRY_BUY_CANDIDATE,
            durable_append=lambda: None,
        )

    class MutableClock:
        value = NOW

        def __call__(self):
            return self.value

    clock = MutableClock()
    expiring_engine, expiring_journal, _expiring_venue, expiring_policy = _ready_engine(
        tmp_path,
        run_id="token-expired",
        policy=E1Policy(cooldown_seconds=0),
    )
    expiring_engine._authority._clock = clock
    frame = _frame()
    position = VirtualPosition(
        position_ref="vposition:expiry",
        symbol="USD_JPY",
        side=PositionSide.LONG,
        units=1,
        entry_price=frame.ask,
        protective_stop_price=Decimal("149"),
    )
    intent = EntryIntent(
        intent_id="intent:expiry",
        run_id="token-expired",
        config_hash=expiring_policy.config_hash,
        created_at=frame.evaluation_time,
        position=position,
    )
    expired, reasons = expiring_engine._risk_gate.issue_entry_token(
        intent=intent,
        market=frame,
        phase=EnginePhase.READY_FLAT,
    )
    assert expired is not None and reasons == ()
    clock.value = NOW + timedelta(seconds=expiring_policy.token_ttl_seconds)
    with pytest.raises(E1EngineError, match="expired"):
        expiring_engine._authority.commit_intent(
            token=expired,
            durable_append=lambda: expiring_journal.append(
                event_type=JournalEventType.INTENT_PREPARED,
                timestamp=frame.evaluation_time,
                status_label="SHOULD_NOT_APPEND_EXPIRED_TOKEN",
                expected_state_digest=position_digest(None),
                position_count=0,
                action=GateAction.VIRTUAL_ENTRY,
                intent_id=intent.intent_id,
                intent_digest=intent.intent_digest,
                token_id=expired.token_id,
                state_before_digest=position_digest(None),
                planned_state_digest=position_digest(position),
            ),
        )
    assert all(record.intent_id != intent.intent_id for record in expiring_journal.records)
    assert venue.position is not None


def test_forged_token_is_rejected(tmp_path) -> None:
    engine, _journal, _venue, policy = _ready_engine(tmp_path, run_id="token-forged")
    forged = ShadowGateToken(
        token_id="shadowtoken:forged",
        run_id="token-test",
        intent_id="intent:forged",
        intent_digest="a" * 64,
        action=GateAction.VIRTUAL_ENTRY,
        stage=E1Stage.SHADOW,
        config_hash=policy.config_hash,
        issued_at=canonical_timestamp(NOW),
        expires_at=canonical_timestamp(NOW + timedelta(seconds=1)),
    )
    with pytest.raises(E1EngineError, match="not issued"):
        engine._authority.commit_intent(token=forged, durable_append=lambda: None)


def test_intent_is_fsynced_before_virtual_effect(tmp_path, monkeypatch) -> None:
    engine, journal, venue, policy = _ready_engine(tmp_path)
    original_open = venue._open_position

    def checked_open(position, *, executor_key):
        events = [record.event_type for record in journal.records]
        assert events[-2:] == [
            JournalEventType.INTENT_PREPARED,
            JournalEventType.VIRTUAL_EXECUTION_STARTED,
        ]
        original_open(position, executor_key=executor_key)

    monkeypatch.setattr(venue, "_open_position", checked_open)
    engine.process_decision(
        decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
    )
    assert venue.position is not None


def test_journal_failure_before_intent_means_zero_virtual_effect(tmp_path, monkeypatch) -> None:
    engine, journal, venue, policy = _ready_engine(tmp_path)
    original_append = journal.append

    def fail_intent(**kwargs):
        if kwargs["event_type"] is JournalEventType.INTENT_PREPARED:
            raise E1PersistenceError("injected local write failure")
        return original_append(**kwargs)

    monkeypatch.setattr(journal, "append", fail_intent)
    with pytest.raises(E1EngineError, match="before virtual execution"):
        engine.process_decision(
            decision=_buy(policy), market=_frame(), protective_stop_price="149.000"
        )
    assert engine.phase is EnginePhase.HALTED
    assert venue.position is None
    assert all(
        record.event_type is not JournalEventType.VIRTUAL_EXECUTION_STARTED
        for record in journal.records
    )


def test_policy_forbids_scale_flip_hedge_and_loss_escalation_flags() -> None:
    for name in (
        "allow_scale_in",
        "allow_position_flip",
        "allow_hedging",
        "allow_martingale",
        "allow_grid",
        "allow_nanpin",
        "allow_real_order",
        "allow_private_api",
        "allow_broker_call",
    ):
        with pytest.raises(E1ContractError):
            E1Policy(**{name: True})
    with pytest.raises(E1ContractError):
        E1Policy(max_positions=2)


def test_virtual_venue_mutation_requires_bound_executor_capability(tmp_path) -> None:
    policy = E1Policy()
    root = tmp_path / "venue"
    venue = VirtualVenueStateStore(
        root=root, path=root / "state.json", config_hash=policy.config_hash
    )
    position = VirtualPosition(
        position_ref=make_local_id("vposition", {"n": 1}),
        symbol="USD_JPY",
        side=PositionSide.LONG,
        units=1,
        entry_price=Decimal("150"),
        protective_stop_price=Decimal("149"),
    )
    with pytest.raises(E1PersistenceError, match="bound executor"):
        venue._open_position(position, executor_key=object())
    assert venue.position is None
    assert not hasattr(venue, "open_position")
    assert not hasattr(venue, "settle_position_specific")


def replace_position_ref(position: VirtualPosition, position_ref: str) -> VirtualPosition:
    return VirtualPosition(
        position_ref=position_ref,
        symbol=position.symbol,
        side=position.side,
        units=position.units,
        entry_price=position.entry_price,
        protective_stop_price=position.protective_stop_price,
    )


def test_executor_contract_intent_is_not_itself_a_capability(tmp_path) -> None:
    engine, _journal, _venue, policy = _ready_engine(tmp_path)
    position = VirtualPosition(
        position_ref="vposition:test",
        symbol="USD_JPY",
        side=PositionSide.LONG,
        units=1,
        entry_price=Decimal("150"),
        protective_stop_price=Decimal("149"),
    )
    intent = EntryIntent(
        intent_id="intent:test",
        run_id="e1-test",
        config_hash=policy.config_hash,
        created_at=canonical_timestamp(NOW),
        position=position,
    )
    with pytest.raises(E1EngineError, match="ShadowGateToken only"):
        engine._executor.execute_entry(  # type: ignore[arg-type]
            token=intent,
            intent=intent,
            fault=FaultInjection(),
        )
