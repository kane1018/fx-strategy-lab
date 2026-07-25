from __future__ import annotations

import ast
import inspect
import itertools
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from zoneinfo import ZoneInfo

import pytest

from app.h11_auto.runtime_safety import (
    AutoRiskStopState,
    DeadManPolicy,
    DeadManResult,
    DeadManStore,
    PhaseBRiskGateResult,
    PhaseBRiskPolicy,
    PhaseBRiskState,
    engage_risk_kill,
    evaluate_risk_before_entry,
    record_closed_result,
)
from app.services import h11_v4_unattended_live_authorization as authorization_module
from app.services import h11_v4_unattended_live_heartbeat_chain as chain_module
from app.services import h11_v4_unattended_live_permit_decision as decision_module

_JST = ZoneInfo("Asia/Tokyo")
_NOW = datetime(2026, 7, 24, 1, 0, tzinfo=UTC)
_TODAY_JST = _NOW.astimezone(_JST).date().isoformat()
_GENERATION = "sha256:" + "a" * 64


def _chain_policy() -> chain_module.V4HeartbeatChainPolicy:
    return chain_module.V4HeartbeatChainPolicy(
        policy_label="H11_V4_UNATTENDED_CHAIN_TEST_V1",
        maximum_gap_seconds=60,
        minimum_continuous_seconds=300,
    )


def _risk_policy() -> PhaseBRiskPolicy:
    return PhaseBRiskPolicy(
        policy_label="H11_AUTO_INITIAL_MINIMUM_LIVE_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
    )


_CHAIN_SEQUENCE = itertools.count()


def _healthy_chain(tmp_path: Path) -> chain_module.V4HeartbeatChainStore:
    # A unique file per call: re-beating an existing chain with older timestamps
    # is (correctly) refused as HEARTBEAT_CHAIN_TIME_BACKWARDS.
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / f"chain-{next(_CHAIN_SEQUENCE)}.json", policy=_chain_policy()
    )
    for offset in range(0, 331, 30):
        store.beat(now_utc=_NOW - timedelta(seconds=330 - offset))
    return store


def _artifact(tmp_path: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "schema": authorization_module.V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
        "generation_digest": _GENERATION,
        "trading_day_jst": _TODAY_JST,
        "maximum_entries": 1,
        "operator_authorized": True,
    }
    payload.update(overrides)
    path = tmp_path / "daily-authorization.json"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _check(
    tmp_path: Path, **overrides: object
) -> authorization_module.V4UnattendedLiveAuthorizationCheck:
    return authorization_module.check_operator_daily_authorization(
        artifact_path=_artifact(tmp_path, **overrides),
        expected_generation_digest=_GENERATION,
        now_utc=_NOW,
    )


# ---------------------------------------------------------------- heartbeat chain


def test_chain_policy_is_validated() -> None:
    with pytest.raises(chain_module.V4UnattendedLiveHeartbeatError):
        chain_module.V4HeartbeatChainPolicy(
            policy_label=" ", maximum_gap_seconds=60, minimum_continuous_seconds=300
        )
    with pytest.raises(chain_module.V4UnattendedLiveHeartbeatError):
        chain_module.V4HeartbeatChainPolicy(
            policy_label="X", maximum_gap_seconds=0, minimum_continuous_seconds=300
        )
    with pytest.raises(
        chain_module.V4UnattendedLiveHeartbeatError,
        match="HEARTBEAT_CHAIN_POLICY_INCONSISTENT",
    ):
        chain_module.V4HeartbeatChainPolicy(
            policy_label="X", maximum_gap_seconds=300, minimum_continuous_seconds=300
        )


def test_fresh_chain_is_not_yet_continuously_healthy(tmp_path: Path) -> None:
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=_chain_policy()
    )
    store.beat(now_utc=_NOW)
    assessment = store.assess(now_utc=_NOW + timedelta(seconds=10))
    assert assessment.continuously_healthy is False
    assert assessment.reason_safe_label == "HEARTBEAT_CHAIN_CONTINUITY_INSUFFICIENT"
    assert bool(assessment) is False


def test_sustained_beats_become_continuously_healthy(tmp_path: Path) -> None:
    store = _healthy_chain(tmp_path)
    assessment = store.assess(now_utc=_NOW + timedelta(seconds=10))
    assert assessment.continuously_healthy is True
    assert assessment.continuous_seconds is not None
    assert assessment.continuous_seconds >= 300


def test_gap_resets_the_chain_continuity(tmp_path: Path) -> None:
    store = _healthy_chain(tmp_path)
    # A 400-second silence exceeds the 60-second maximum gap: continuity restarts.
    late = _NOW + timedelta(seconds=400)
    store.beat(now_utc=late)
    assessment = store.assess(now_utc=late + timedelta(seconds=10))
    assert assessment.continuously_healthy is False
    assert assessment.reason_safe_label == "HEARTBEAT_CHAIN_CONTINUITY_INSUFFICIENT"


def test_stale_missing_future_and_corrupt_chain_fail_closed(tmp_path: Path) -> None:
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=_chain_policy()
    )
    assert store.assess(now_utc=_NOW).reason_safe_label == "HEARTBEAT_CHAIN_MISSING"
    store.beat(now_utc=_NOW)
    stale = store.assess(now_utc=_NOW + timedelta(seconds=120))
    assert stale.reason_safe_label == "HEARTBEAT_CHAIN_STALE"
    future = store.assess(now_utc=_NOW - timedelta(seconds=30))
    assert future.reason_safe_label == "HEARTBEAT_CHAIN_FROM_FUTURE"
    (tmp_path / "chain.json").write_text("not-json", encoding="utf-8")
    corrupt = store.assess(now_utc=_NOW)
    assert corrupt.reason_safe_label == "HEARTBEAT_CHAIN_STATE_INVALID"


def test_gap_exactly_at_maximum_keeps_the_chain(tmp_path: Path) -> None:
    # Inclusive boundary: a gap of exactly maximum_gap_seconds keeps continuity
    # (and an age of exactly maximum_gap_seconds is not stale). Load-bearing
    # semantics pinned so a refactor cannot silently flip <= to <.
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=_chain_policy()
    )
    start = _NOW - timedelta(seconds=360)
    store.beat(now_utc=start)
    store.beat(now_utc=start + timedelta(seconds=60))  # exactly the maximum gap
    for offset in range(120, 361, 30):
        store.beat(now_utc=start + timedelta(seconds=offset))
    assessment = store.assess(now_utc=_NOW + timedelta(seconds=60))
    assert assessment.continuously_healthy is True


def test_continuity_exactly_at_minimum_is_healthy(tmp_path: Path) -> None:
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=_chain_policy()
    )
    start = _NOW - timedelta(seconds=300)
    for offset in range(0, 301, 30):
        store.beat(now_utc=start + timedelta(seconds=offset))
    # continuous == exactly minimum_continuous_seconds (300)
    assessment = store.assess(now_utc=_NOW)
    assert assessment.continuously_healthy is True
    just_before = store.assess(now_utc=_NOW - timedelta(seconds=1))
    assert just_before.continuously_healthy is False


def test_backwards_beat_is_refused(tmp_path: Path) -> None:
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=_chain_policy()
    )
    store.beat(now_utc=_NOW)
    with pytest.raises(
        chain_module.V4UnattendedLiveHeartbeatError, match="HEARTBEAT_CHAIN_TIME_BACKWARDS"
    ):
        store.beat(now_utc=_NOW - timedelta(seconds=1))


def test_chain_written_under_a_different_policy_is_refused(tmp_path: Path) -> None:
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=_chain_policy()
    )
    store.beat(now_utc=_NOW)
    other_policy = chain_module.V4HeartbeatChainPolicy(
        policy_label="H11_V4_UNATTENDED_CHAIN_OTHER_V1",
        maximum_gap_seconds=60,
        minimum_continuous_seconds=300,
    )
    other = chain_module.V4HeartbeatChainStore(
        tmp_path / "chain.json", policy=other_policy
    )
    assert other.assess(now_utc=_NOW).reason_safe_label == "HEARTBEAT_CHAIN_STATE_INVALID"


def test_chain_store_has_no_clear_or_reset_api() -> None:
    store_attributes = dir(chain_module.V4HeartbeatChainStore)
    assert "clear" not in store_attributes
    assert "reset" not in store_attributes


# ---------------------------------------------------------------- authorization


def test_valid_operator_artifact_authorizes_today(tmp_path: Path) -> None:
    check = _check(tmp_path)
    assert check.authorized is True
    assert check.blocked_reasons == ()
    assert check.trading_day_jst == _TODAY_JST
    assert check.consumption_available is True
    assert check.permit_issued is False
    assert bool(check) is False


@pytest.mark.parametrize(
    ("overrides", "reason"),
    (
        ({"schema": "OTHER"}, "AUTHORIZATION_SCHEMA_INVALID"),
        (
            {"generation_digest": "sha256:" + "b" * 64},
            "AUTHORIZATION_GENERATION_MISMATCH",
        ),
        ({"trading_day_jst": "2020-01-01"}, "AUTHORIZATION_DAY_MISMATCH"),
        ({"maximum_entries": 2}, "AUTHORIZATION_ENTRY_CAP_INVALID"),
        ({"operator_authorized": False}, "AUTHORIZATION_NOT_GRANTED_BY_OPERATOR"),
    ),
)
def test_each_artifact_defect_blocks(
    tmp_path: Path, overrides: dict[str, object], reason: str
) -> None:
    check = _check(tmp_path, **overrides)
    assert check.authorized is False
    assert reason in check.blocked_reasons


def test_missing_and_malformed_artifacts_block(tmp_path: Path) -> None:
    missing = authorization_module.check_operator_daily_authorization(
        artifact_path=tmp_path / "absent.json",
        expected_generation_digest=_GENERATION,
        now_utc=_NOW,
    )
    assert "AUTHORIZATION_ARTIFACT_MISSING" in missing.blocked_reasons
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    malformed = authorization_module.check_operator_daily_authorization(
        artifact_path=bad, expected_generation_digest=_GENERATION, now_utc=_NOW
    )
    assert "AUTHORIZATION_ARTIFACT_MALFORMED" in malformed.blocked_reasons


def test_consumption_is_one_use_and_visible_to_later_checks(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    authorization_module.consume_operator_daily_authorization_once(
        artifact_path=artifact, expected_generation_digest=_GENERATION, now_utc=_NOW
    )
    with pytest.raises(
        authorization_module.V4UnattendedLiveAuthorizationError,
        match="AUTHORIZATION_ALREADY_CONSUMED",
    ):
        authorization_module.consume_operator_daily_authorization_once(
            artifact_path=artifact, expected_generation_digest=_GENERATION, now_utc=_NOW
        )
    after = authorization_module.check_operator_daily_authorization(
        artifact_path=artifact, expected_generation_digest=_GENERATION, now_utc=_NOW
    )
    assert after.authorized is False
    assert "AUTHORIZATION_ALREADY_CONSUMED" in after.blocked_reasons
    assert after.consumption_available is False


def test_consumption_refuses_an_unclear_authorization_without_writing(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, operator_authorized=False)
    with pytest.raises(
        authorization_module.V4UnattendedLiveAuthorizationError,
        match="AUTHORIZATION_NOT_CLEAR_FOR_CONSUMPTION",
    ):
        authorization_module.consume_operator_daily_authorization_once(
            artifact_path=artifact, expected_generation_digest=_GENERATION, now_utc=_NOW
        )
    markers = list(tmp_path.glob("unattended-authorization-consumed-*.json"))
    assert markers == []


def test_symlinked_artifact_is_refused(tmp_path: Path) -> None:
    real = _artifact(tmp_path)
    link = tmp_path / "link.json"
    link.symlink_to(real)
    check = authorization_module.check_operator_daily_authorization(
        artifact_path=link, expected_generation_digest=_GENERATION, now_utc=_NOW
    )
    assert "AUTHORIZATION_ARTIFACT_SYMLINK_REFUSED" in check.blocked_reasons


def test_module_ships_no_artifact_creation_or_extension_api() -> None:
    # Operator-write-only by construction: the module must not offer any way
    # for the automation to mint, extend, or re-issue an authorization.
    source = inspect.getsource(authorization_module)
    for forbidden in (
        "def create_",
        "def issue_",
        "def extend_",
        "def write_artifact",
        "def renew_",
    ):
        assert forbidden not in source, forbidden
    public_functions = [
        name
        for name, value in vars(authorization_module).items()
        if callable(value)
        and not name.startswith("_")
        and not isinstance(value, type)
        and getattr(value, "__module__", None) == authorization_module.__name__
    ]
    assert sorted(public_functions) == [
        "check_operator_daily_authorization",
        "consume_operator_daily_authorization_once",
    ]


def test_invalid_generation_digest_argument_is_refused(tmp_path: Path) -> None:
    for bad in ("not-a-digest", 12345, None, b"sha256:aa"):
        with pytest.raises(
            authorization_module.V4UnattendedLiveAuthorizationError,
            match="AUTHORIZATION_GENERATION_DIGEST_INVALID",
        ):
            authorization_module.check_operator_daily_authorization(
                artifact_path=_artifact(tmp_path),
                expected_generation_digest=cast(str, bad),
                now_utc=_NOW,
            )


def test_consumption_marker_carries_a_distinct_schema(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    authorization_module.consume_operator_daily_authorization_once(
        artifact_path=artifact, expected_generation_digest=_GENERATION, now_utc=_NOW
    )
    marker = tmp_path / f"unattended-authorization-consumed-{_TODAY_JST}.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        authorization_module.V4_UNATTENDED_LIVE_CONSUMPTION_SCHEMA
    )
    assert payload["schema"] != (
        authorization_module.V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA
    )
    # A marker can never itself pass the artifact check.
    as_artifact = authorization_module.check_operator_daily_authorization(
        artifact_path=marker, expected_generation_digest=_GENERATION, now_utc=_NOW
    )
    assert as_artifact.authorized is False


# ---------------------------------------------------------------- permit decision


def _alive_dead_man(tmp_path: Path) -> DeadManResult:
    policy = DeadManPolicy(
        policy_label="H11_AUTO_DEAD_MAN_15_60_V1", maximum_heartbeat_age_seconds=60
    )
    store = DeadManStore(tmp_path / "dead-man.json", policy=policy)
    store.heartbeat(heartbeat_utc=_NOW - timedelta(seconds=5))
    return store.evaluate(now_utc=_NOW)


def _decide(
    tmp_path: Path,
    **overrides: object,
) -> decision_module.V4UnattendedPermitDecision:
    risk_policy = _risk_policy()
    state = PhaseBRiskState(policy_digest=risk_policy.digest)
    values: dict[str, object] = {
        "authorization": _check(tmp_path),
        "risk_gate": evaluate_risk_before_entry(
            state=state, policy=risk_policy, cycle_day_jst=_TODAY_JST
        ),
        "dead_man": _alive_dead_man(tmp_path),
        "heartbeat_chain": _healthy_chain(tmp_path).assess(
            now_utc=_NOW + timedelta(seconds=10)
        ),
        "notification_ready": True,
        "entry_gate_blocked_reasons": (),
        "now_utc": _NOW,
    }
    values.update(overrides)
    return decision_module.decide_unattended_permit_issuance(**values)  # type: ignore[arg-type]


def test_all_six_conditions_clear_allows_without_issuing_anything(
    tmp_path: Path,
) -> None:
    decision = _decide(tmp_path)
    assert decision.allowed is True
    assert decision.blocked_reasons == ()
    assert decision.trading_day_jst == _TODAY_JST
    assert decision.permit_issued is False
    assert decision.broker_post_authorized is False
    assert decision.live_ready is False
    assert bool(decision) is False
    assert decision.to_safe_dict()["permit_issued"] is False


def test_operator_kill_blocks_through_the_reused_risk_gate(tmp_path: Path) -> None:
    risk_policy = _risk_policy()
    state = PhaseBRiskState(policy_digest=risk_policy.digest)
    engage_risk_kill(state=state, cycle_day_jst=_TODAY_JST)
    decision = _decide(
        tmp_path,
        risk_gate=evaluate_risk_before_entry(
            state=state, policy=risk_policy, cycle_day_jst=_TODAY_JST
        ),
    )
    assert decision.allowed is False
    assert "PERSISTENT_RISK_STOPPED" in decision.blocked_reasons


def test_per_trade_discipline_violation_blocks_through_the_reused_ledger(
    tmp_path: Path,
) -> None:
    risk_policy = _risk_policy()
    state = PhaseBRiskState(policy_digest=risk_policy.digest)
    # A realized loss beyond the frozen 5,000-yen per-trade bound engages the
    # latch-only KILL in the reused runtime_safety machinery.
    record_closed_result(
        state=state,
        policy=risk_policy,
        cycle_day_jst=_TODAY_JST,
        pnl_jpy_internal=-6_000,
    )
    decision = _decide(
        tmp_path,
        risk_gate=evaluate_risk_before_entry(
            state=state, policy=risk_policy, cycle_day_jst=_TODAY_JST
        ),
    )
    assert decision.allowed is False
    assert "PERSISTENT_RISK_STOPPED" in decision.blocked_reasons


def test_unclear_authorization_blocks(tmp_path: Path) -> None:
    decision = _decide(
        tmp_path, authorization=_check(tmp_path, operator_authorized=False)
    )
    assert decision.allowed is False
    assert "OPERATOR_DAILY_AUTHORIZATION_NOT_CLEAR" in decision.blocked_reasons
    assert "AUTHORIZATION_NOT_GRANTED_BY_OPERATOR" in decision.blocked_reasons


def test_stale_dead_man_blocks(tmp_path: Path) -> None:
    policy = DeadManPolicy(
        policy_label="H11_AUTO_DEAD_MAN_15_60_V1", maximum_heartbeat_age_seconds=60
    )
    store = DeadManStore(tmp_path / "dead-man.json", policy=policy)
    store.heartbeat(heartbeat_utc=_NOW - timedelta(seconds=300))
    decision = _decide(tmp_path, dead_man=store.evaluate(now_utc=_NOW))
    assert decision.allowed is False
    assert "DEAD_MAN_NOT_ALIVE" in decision.blocked_reasons
    assert "DEAD_MAN_HEARTBEAT_STALE" in decision.blocked_reasons


def test_insufficient_heartbeat_continuity_blocks(tmp_path: Path) -> None:
    store = chain_module.V4HeartbeatChainStore(
        tmp_path / "young-chain.json", policy=_chain_policy()
    )
    store.beat(now_utc=_NOW)
    decision = _decide(
        tmp_path, heartbeat_chain=store.assess(now_utc=_NOW + timedelta(seconds=10))
    )
    assert decision.allowed is False
    assert "HEARTBEAT_CHAIN_CONTINUITY_INSUFFICIENT" in decision.blocked_reasons


def test_notification_not_ready_blocks(tmp_path: Path) -> None:
    decision = _decide(tmp_path, notification_ready=False)
    assert decision.allowed is False
    assert "NOTIFICATION_PATH_NOT_READY" in decision.blocked_reasons


def test_entry_gate_reasons_pass_through_and_block(tmp_path: Path) -> None:
    decision = _decide(
        tmp_path, entry_gate_blocked_reasons=("SPREAD_LIMIT_EXCEEDED",)
    )
    assert decision.allowed is False
    assert "SPREAD_LIMIT_EXCEEDED" in decision.blocked_reasons


def test_stale_day_authorization_object_is_refused(tmp_path: Path) -> None:
    check = _check(tmp_path)
    tomorrow = _NOW + timedelta(days=1)
    decision = _decide(tmp_path, authorization=check, now_utc=tomorrow)
    assert decision.allowed is False
    assert "OPERATOR_AUTHORIZATION_DAY_STALE" in decision.blocked_reasons


def test_blocked_risk_gate_with_empty_reasons_still_blocks(tmp_path: Path) -> None:
    # Safety-review VETO regression (2026-07-24): PhaseBRiskGateResult carries
    # no internal consistency invariant, so allowed=False with an empty
    # reasons tuple is constructible. That combination must still block via
    # the unconditional sentinel -- it previously failed OPEN.


    forged = PhaseBRiskGateResult(
        allowed=False,
        stop_state=AutoRiskStopState.KILLED,
        blocked_reasons=(),
    )
    decision = _decide(tmp_path, risk_gate=forged)
    assert decision.allowed is False
    assert "PERSISTENT_RISK_GATE_NOT_CLEAR" in decision.blocked_reasons
    assert "PERSISTENT_RISK_STOP_STATE_NOT_ACTIVE" in decision.blocked_reasons


def test_latched_stop_state_blocks_even_with_inconsistent_allowed_true(
    tmp_path: Path,
) -> None:


    forged = PhaseBRiskGateResult(
        allowed=True,
        stop_state=AutoRiskStopState.KILLED,
        blocked_reasons=(),
    )
    decision = _decide(tmp_path, risk_gate=forged)
    assert decision.allowed is False
    assert "PERSISTENT_RISK_STOP_STATE_NOT_ACTIVE" in decision.blocked_reasons


def test_dead_man_halt_required_blocks_even_with_inconsistent_alive_true(
    tmp_path: Path,
) -> None:
    forged = DeadManResult(
        alive=True,
        halt_required=True,
        reason_safe_label="DEAD_MAN_ALIVE",
        heartbeat_age_seconds=1.0,
    )
    decision = _decide(tmp_path, dead_man=forged)
    assert decision.allowed is False
    assert "DEAD_MAN_HALT_REQUIRED" in decision.blocked_reasons


def test_multiple_simultaneous_failures_are_deduped_and_all_reported(
    tmp_path: Path,
) -> None:
    decision = _decide(
        tmp_path,
        authorization=_check(tmp_path, operator_authorized=False),
        notification_ready=False,
        entry_gate_blocked_reasons=(
            "SPREAD_LIMIT_EXCEEDED",
            "NOTIFICATION_PATH_NOT_READY",  # duplicate across sources
        ),
    )
    assert decision.allowed is False
    assert "OPERATOR_DAILY_AUTHORIZATION_NOT_CLEAR" in decision.blocked_reasons
    assert "SPREAD_LIMIT_EXCEEDED" in decision.blocked_reasons
    # Deduped: the notification reason appears exactly once even though two
    # sources contributed it.
    assert decision.blocked_reasons.count("NOTIFICATION_PATH_NOT_READY") == 1


def test_decision_rejects_duck_typed_inputs(tmp_path: Path) -> None:
    for field in (
        "authorization",
        "risk_gate",
        "dead_man",
        "heartbeat_chain",
        "notification_ready",
        "entry_gate_blocked_reasons",
    ):
        with pytest.raises(
            decision_module.V4UnattendedLivePermitDecisionError,
            match="PERMIT_DECISION_INPUT_INVALID",
        ):
            _decide(tmp_path, **{field: cast(object, SimpleNamespace())})


def test_decision_rejects_unsafe_entry_gate_reason(tmp_path: Path) -> None:
    with pytest.raises(
        decision_module.V4UnattendedLivePermitDecisionError,
        match="PERMIT_DECISION_REASON_INVALID",
    ):
        _decide(tmp_path, entry_gate_blocked_reasons=("lower case bad",))


def test_decision_object_cannot_claim_live_activity(tmp_path: Path) -> None:
    decision = _decide(tmp_path)
    with pytest.raises(
        decision_module.V4UnattendedLivePermitDecisionError,
        match="PERMIT_DECISION_CANNOT_CLAIM_LIVE_ACTIVITY",
    ):
        replace(decision, permit_issued=True)
    with pytest.raises(
        decision_module.V4UnattendedLivePermitDecisionError,
        match="PERMIT_DECISION_CANNOT_CLAIM_LIVE_ACTIVITY",
    ):
        replace(decision, broker_post_authorized=True)
    with pytest.raises(
        decision_module.V4UnattendedLivePermitDecisionError,
        match="PERMIT_DECISION_INCONSISTENT",
    ):
        replace(decision, allowed=False)


# ---------------------------------------------------------------- isolation


def test_modules_have_no_transport_or_credential_code_tokens() -> None:
    for module in (chain_module, authorization_module, decision_module):
        source = inspect.getsource(module)
        # Code-identifier tokens only; the decision module's docstring
        # legitimately NAMES the future permit function while explaining that
        # calling it is deliberately impossible from this layer, so that prose
        # reference is excluded. The import-graph test below is authoritative.
        for forbidden in (
            "httpx",
            "smtplib",
            "subprocess",
            "keyring",
            "os.environ",
            "os.getenv",
            "load_dotenv",
            "find-generic-password",
            "v4_gmo_canary_activation",
            "assert_real_broker_post_allowed",
        ):
            assert forbidden not in source, (module.__name__, forbidden)


def test_modules_reachable_app_imports_avoid_actual_and_transport_modules() -> None:
    for module in (chain_module, authorization_module, decision_module):
        reachable = _reachable_app_modules(
            root_module=module.__name__,
            app_root=Path(module.__file__).parents[1],
        )
        for fragment in (
            "actual",
            "canary",
            "coordinator",
            "transport",
            "hard_guard",
            "launchd",
            "private_api",
            "h11_manual",
            "readonly_preflight",
            "post_canary",
        ):
            for module_name in reachable:
                assert fragment not in module_name, (module.__name__, module_name)


def _reachable_app_modules(*, root_module: str, app_root: Path) -> set[str]:
    pending = [root_module]
    visited: set[str] = set()
    while pending:
        module_name = pending.pop()
        if module_name in visited:
            continue
        module_path = _app_module_path(module_name=module_name, app_root=app_root)
        if module_path is None:
            continue
        visited.add(module_name)
        parts = module_name.split(".")
        pending.extend(".".join(parts[:length]) for length in range(1, len(parts)))
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(
                "app."
            ):
                pending.append(node.module)
            elif isinstance(node, ast.Import):
                pending.extend(
                    alias.name
                    for alias in node.names
                    if alias.name == "app" or alias.name.startswith("app.")
                )
    return visited


def _app_module_path(*, module_name: str, app_root: Path) -> Path | None:
    relative = module_name.split(".")[1:]
    if not relative:
        return None
    base = app_root.joinpath(*relative)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None
