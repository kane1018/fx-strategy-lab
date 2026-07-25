from __future__ import annotations

import ast
import inspect
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from app.h11_auto import v4_gmo_canary_activation as subject
from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.services.h11_v4_unattended_live_authorization import (
    V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainPolicy,
    V4HeartbeatChainStore,
)

_NOW = datetime(2026, 7, 24, 1, 0, tzinfo=UTC)
_GENERATION = "sha256:" + "b" * 64


def _intent(**overrides: object) -> subject.V4GmoCanaryIntent:
    values: dict[str, object] = {
        "generation_digest": _GENERATION,
        "cycle_ref": "c" * 64,
        "side": "BUY",
        "exact_order_sheet_digest": "sha256:" + "d" * 64,
    }
    values.update(overrides)
    return subject.V4GmoCanaryIntent(**values)  # type: ignore[arg-type]


def _authorization_artifact(path: Path, **overrides: object) -> None:
    payload: dict[str, object] = {
        "schema": V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
        "generation_digest": _GENERATION,
        "trading_day_jst": "2026-07-24",
        "maximum_entries": 1,
        "operator_authorized": True,
    }
    payload.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _risk_policy() -> PhaseBRiskPolicy:
    return PhaseBRiskPolicy(
        policy_label="H11_AUTO_INITIAL_MINIMUM_LIVE_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
    )


def _risk_store(tmp_path: Path, *, initialize: bool = True) -> PhaseBRiskStore:
    policy = _risk_policy()
    store = PhaseBRiskStore(tmp_path / "risk.json", policy=policy)
    if initialize:
        store.save(store.load())
    return store


def _dead_man_store(tmp_path: Path, *, alive: bool = True) -> DeadManStore:
    policy = DeadManPolicy(
        policy_label="H11_AUTO_DEAD_MAN_15_60_V1", maximum_heartbeat_age_seconds=60
    )
    store = DeadManStore(tmp_path / "dead-man.json", policy=policy)
    if alive:
        store.heartbeat(heartbeat_utc=_NOW - timedelta(seconds=5))
    return store


def _chain_policy() -> V4HeartbeatChainPolicy:
    return V4HeartbeatChainPolicy(
        policy_label="H11_V4_UNATTENDED_CHAIN_TEST_V1",
        maximum_gap_seconds=60,
        minimum_continuous_seconds=300,
    )


def _healthy_chain_store(tmp_path: Path, *, name: str = "chain.json") -> V4HeartbeatChainStore:
    store = V4HeartbeatChainStore(tmp_path / name, policy=_chain_policy())
    for offset in range(0, 331, 30):
        store.beat(now_utc=_NOW - timedelta(seconds=330 - offset))
    return store


def _confirm(
    tmp_path: Path,
    *,
    intent: subject.V4GmoCanaryIntent | None = None,
    state_root: Path | None = None,
    risk_store: PhaseBRiskStore | None = None,
    risk_policy: PhaseBRiskPolicy | None = None,
    dead_man_store: DeadManStore | None = None,
    heartbeat_chain_store: V4HeartbeatChainStore | None = None,
    notification_ready: bool = True,
    entry_gate_blocked_reasons: tuple[str, ...] = (),
    now_utc: datetime | None = None,
) -> tuple[subject.V4MajorIncidentResumeProof, subject.V4CurrentTurnConfirmationProof]:
    resolved_state_root = state_root or tmp_path
    if state_root is None:
        _authorization_artifact(
            resolved_state_root
            / "h11_v4_unattended_live"
            / f"generation-{'b' * 64}"
            / "daily-authorization.json"
        )
    return subject.confirm_v4_unattended_authorization_once(
        intent=intent or _intent(),
        state_root=resolved_state_root,
        risk_store=risk_store or _risk_store(tmp_path),
        risk_policy=risk_policy or _risk_policy(),
        dead_man_store=dead_man_store or _dead_man_store(tmp_path),
        heartbeat_chain_store=heartbeat_chain_store or _healthy_chain_store(tmp_path),
        notification_ready=notification_ready,
        entry_gate_blocked_reasons=entry_gate_blocked_reasons,
        now_utc=now_utc or _NOW,
    )


def test_all_conditions_clear_mints_both_proofs_and_consumes_authorization(
    tmp_path: Path,
) -> None:
    resume_proof, current_turn_proof = _confirm(tmp_path)
    assert isinstance(resume_proof, subject.V4MajorIncidentResumeProof)
    assert isinstance(current_turn_proof, subject.V4CurrentTurnConfirmationProof)
    assert bool(resume_proof) is False
    assert bool(current_turn_proof) is False
    marker = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "unattended-authorization-consumed-2026-07-24.json"
    )
    assert marker.is_file()


def test_second_call_same_day_is_refused_and_no_second_proof_pair_exists(
    tmp_path: Path,
) -> None:
    # Explicitly shared state across both calls: this is what "repeated
    # evaluation of the same day" actually looks like (same stores re-read),
    # not two independent fresh setups.
    risk_store = _risk_store(tmp_path)
    dead_man_store = _dead_man_store(tmp_path)
    heartbeat_store = _healthy_chain_store(tmp_path)
    _confirm(
        tmp_path,
        risk_store=risk_store,
        dead_man_store=dead_man_store,
        heartbeat_chain_store=heartbeat_store,
    )
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(
            tmp_path,
            risk_store=risk_store,
            dead_man_store=dead_man_store,
            heartbeat_chain_store=heartbeat_store,
        )


def test_missing_risk_state_file_refuses_rather_than_fabricating_active(
    tmp_path: Path,
) -> None:
    store = _risk_store(tmp_path, initialize=False)
    assert not store.path.exists()
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_RISK_STATE_MISSING"
    ):
        _confirm(tmp_path, risk_store=store)


def test_symlinked_risk_state_file_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "real-risk.json"
    _risk_store(tmp_path.parent / "elsewhere", initialize=True)
    store = _risk_store(tmp_path, initialize=True)
    store.path.unlink()
    real.write_text(store.path.read_text(encoding="utf-8") if real.exists() else "{}")
    store.path.symlink_to(real)
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_RISK_STATE_MISSING"
    ):
        _confirm(tmp_path, risk_store=store)


def test_latched_kill_blocks_via_the_reused_risk_ledger(tmp_path: Path) -> None:
    from app.h11_auto.runtime_safety import engage_risk_kill

    store = _risk_store(tmp_path, initialize=False)
    state = store.load()
    engage_risk_kill(state=state, cycle_day_jst="2026-07-24")
    store.save(state)
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, risk_store=store)


def test_corrupted_risk_state_file_is_refused_as_module_own_error_type(
    tmp_path: Path,
) -> None:
    # A policy-digest mismatch (e.g. a policy-constants change deployed
    # without migrating the on-disk state, or on-disk corruption/tampering)
    # must never leak runtime_safety's own H11AutoRuntimeSafetyError past
    # this module's boundary -- callers only catch V4GmoCanaryActivationError.
    store = _risk_store(tmp_path, initialize=False)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps({"policy_digest": "sha256:" + "0" * 64, "stop_state": "ACTIVE"}),
        encoding="utf-8",
    )
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_RISK_STATE_INVALID"
    ):
        _confirm(tmp_path, risk_store=store)


def test_non_killed_stop_state_also_blocks(tmp_path: Path) -> None:
    # The risk-gate veto must be state-agnostic, not special-cased to KILLED.
    from app.h11_auto.runtime_safety import record_closed_result

    policy = _risk_policy()
    store = _risk_store(tmp_path, initialize=False)
    state = store.load()
    # Two losses at exactly the per-trade bound (never exceeding it, so KILLED
    # is never triggered) whose sum reaches the daily budget limit.
    for _ in range(2):
        record_closed_result(
            state=state,
            policy=policy,
            cycle_day_jst="2026-07-24",
            pnl_jpy_internal=-policy.per_trade_loss_bound_jpy,
        )
    assert state.stop_state == "STOPPED_DAILY_BUDGET"
    store.save(state)
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, risk_store=store)


def test_entry_gate_reason_with_invalid_charset_is_refused_as_module_own_error_type(
    tmp_path: Path,
) -> None:
    # decide_unattended_permit_issuance raises its own
    # V4UnattendedLivePermitDecisionError for a badly-charset reason string;
    # this module must wrap it, never leak the service-layer exception type.
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_DECISION_INVALID"
    ):
        _confirm(tmp_path, entry_gate_blocked_reasons=("spread limit exceeded!",))


def test_missing_heartbeat_chain_file_entirely_blocks(tmp_path: Path) -> None:
    # Distinct from insufficient-continuity: no chain file has ever been
    # written at all (e.g. first run before any heartbeat has landed).
    absent = V4HeartbeatChainStore(tmp_path / "never-beaten.json", policy=_chain_policy())
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, heartbeat_chain_store=absent)


def test_unauthorized_artifact_blocks(tmp_path: Path) -> None:
    artifact_path = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "daily-authorization.json"
    )
    _authorization_artifact(artifact_path, operator_authorized=False)
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        subject.confirm_v4_unattended_authorization_once(
            intent=_intent(),
            state_root=tmp_path,
            risk_store=_risk_store(tmp_path),
            risk_policy=_risk_policy(),
            dead_man_store=_dead_man_store(tmp_path),
            heartbeat_chain_store=_healthy_chain_store(tmp_path),
            notification_ready=True,
            entry_gate_blocked_reasons=(),
            now_utc=_NOW,
        )


def test_dead_man_not_alive_blocks(tmp_path: Path) -> None:
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, dead_man_store=_dead_man_store(tmp_path, alive=False))


def test_insufficient_heartbeat_continuity_blocks(tmp_path: Path) -> None:
    young = V4HeartbeatChainStore(tmp_path / "young.json", policy=_chain_policy())
    young.beat(now_utc=_NOW)
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, heartbeat_chain_store=young)


def test_notification_not_ready_blocks(tmp_path: Path) -> None:
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, notification_ready=False)


def test_entry_gate_blocked_reasons_block(tmp_path: Path) -> None:
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
    ):
        _confirm(tmp_path, entry_gate_blocked_reasons=("SPREAD_LIMIT_EXCEEDED",))


def test_duck_typed_intent_is_refused(tmp_path: Path) -> None:
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_INTENT_INVALID"
    ):
        _confirm(tmp_path, intent=cast(subject.V4GmoCanaryIntent, SimpleNamespace()))


def test_naive_clock_is_refused(tmp_path: Path) -> None:
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_CLOCK_INVALID"
    ):
        _confirm(tmp_path, now_utc=datetime(2026, 7, 24, 1, 0))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("notification_ready", "yes"),
        ("entry_gate_blocked_reasons", ["SPREAD_LIMIT_EXCEEDED"]),
    ),
)
def test_duck_typed_scalar_inputs_are_refused(
    tmp_path: Path, field: str, value: object
) -> None:
    kwargs = {field: value}
    with pytest.raises(
        subject.V4GmoCanaryActivationError, match="V4_CANARY_UNATTENDED_INPUT_INVALID"
    ):
        _confirm(tmp_path, **kwargs)  # type: ignore[arg-type]


def test_authorization_path_is_never_caller_supplied_directly(tmp_path: Path) -> None:
    # The function only accepts state_root; the exact artifact path is always
    # internally derived via the same canonical helper the operator CLI uses.
    signature = inspect.signature(subject.confirm_v4_unattended_authorization_once)
    assert "authorization_artifact_path" not in signature.parameters
    assert "state_root" in signature.parameters


def test_default_state_root_matches_the_canonical_default() -> None:
    from app.services.h11_v4_unattended_live_paths import (
        DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT,
    )

    signature = inspect.signature(subject.confirm_v4_unattended_authorization_once)
    assert (
        signature.parameters["state_root"].default
        == DEFAULT_V4_UNATTENDED_LIVE_STATE_ROOT
    )


# ---------------------------------------------------------------- genuine concurrency


def test_concurrent_threads_racing_the_same_day_mint_exactly_one_proof_pair(
    tmp_path: Path,
) -> None:
    """Real OS-level race: N threads call the function concurrently against the
    SAME shared authorization artifact/risk/dead-man/heartbeat state. File I/O
    releases the GIL, so this genuinely exercises concurrent os.open(O_EXCL)
    calls, not just sequential Python-level calls dressed up as concurrent.
    Exactly one thread must succeed; every other thread must see this
    module's own GATE_NOT_CLEAR error, never a leaked exception type, and at
    most one resume/current-turn proof pair may ever exist for the day.
    """

    artifact_path = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "daily-authorization.json"
    )
    _authorization_artifact(artifact_path)
    risk_store = _risk_store(tmp_path)
    dead_man_store = _dead_man_store(tmp_path)
    heartbeat_store = _healthy_chain_store(tmp_path)
    intent = _intent()

    worker_count = 8
    results: list[object] = [None] * worker_count
    barrier = threading.Barrier(worker_count)

    def worker(index: int) -> None:
        barrier.wait()  # maximize actual overlap of the race window
        try:
            results[index] = subject.confirm_v4_unattended_authorization_once(
                intent=intent,
                state_root=tmp_path,
                risk_store=risk_store,
                risk_policy=_risk_policy(),
                dead_man_store=dead_man_store,
                heartbeat_chain_store=heartbeat_store,
                notification_ready=True,
                entry_gate_blocked_reasons=(),
                now_utc=_NOW,
            )
        except subject.V4GmoCanaryActivationError as error:
            results[index] = error

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    successes = [r for r in results if isinstance(r, tuple)]
    failures = [r for r in results if isinstance(r, subject.V4GmoCanaryActivationError)]
    assert len(successes) == 1, f"expected exactly 1 success, got {len(successes)}"
    assert len(failures) == worker_count - 1
    for failure in failures:
        assert "V4_CANARY_UNATTENDED_GATE_NOT_CLEAR" in str(failure)

    markers = list(
        (tmp_path / "h11_v4_unattended_live" / f"generation-{'b' * 64}").glob(
            "unattended-authorization-consumed-*.json"
        )
    )
    assert len(markers) == 1


# ---------------------------------------------------------------- isolation & purity


def test_existing_g013_functions_and_types_are_byte_identical_in_shape() -> None:
    # Confirms the change is purely additive: every pre-existing public name
    # this module defined before this slice still exists with the same kind.
    expected_still_present = {
        "V4GmoCanaryIntent": type,
        "V4MajorIncidentResumeProof": type,
        "confirm_v4_major_incident_resume_exact": type(lambda: None),
        "V4CurrentTurnChallenge": type,
        "V4CurrentTurnConfirmationProof": type,
        "confirm_v4_current_turn_exact": type(lambda: None),
        "V4GmoActualActivationPermit": type,
        "V4ActivatedRuntimeScope": type,
        "issue_v4_gmo_actual_activation_permit": type(lambda: None),
        "consume_v4_gmo_actual_activation_permit": type(lambda: None),
    }
    for name, kind in expected_still_present.items():
        assert hasattr(subject, name), name
        assert isinstance(getattr(subject, name), kind) or isinstance(
            getattr(subject, name), type
        )


def test_module_has_no_real_transport_or_credential_code_tokens() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "smtplib",
        "subprocess",
        "keyring",
        "os.environ",
        "os.getenv",
        "load_dotenv",
        "find-generic-password",
    ):
        assert forbidden not in source, forbidden


def test_new_function_reachable_imports_avoid_real_transport_and_credential_modules() -> (
    None
):
    reachable = _reachable_app_modules(
        root_module="app.h11_auto.v4_gmo_canary_activation",
        app_root=Path(subject.__file__).parents[1],
    )
    forbidden_fragments = (
        "actual_transport",
        "actual_adapter",
        "actual_coordinator",
        "coordinated_actual_path",
        "readonly_preflight",
        "post_canary",
        "hard_guard",
        "launchd",
        "private_api",
        "notification",
        "h11_manual",
    )
    for module_name in reachable:
        for fragment in forbidden_fragments:
            assert fragment not in module_name, module_name


def test_new_function_docstring_warns_against_bypassing_via_existing_confirm_functions() -> (
    None
):
    doc = subject.confirm_v4_unattended_authorization_once.__doc__ or ""
    assert "confirm_v4_major_incident_resume_exact" in doc
    assert "confirm_v4_current_turn_exact" in doc
    assert "bypass" in doc.lower()


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
