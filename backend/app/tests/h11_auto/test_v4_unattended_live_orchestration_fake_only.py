from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import httpx
import pytest

from app.h11_auto import v4_gmo_canary_activation as activation_module
from app.h11_auto.runtime_safety import (
    DeadManPolicy,
    DeadManStore,
    PhaseBRiskPolicy,
    PhaseBRiskStore,
)
from app.services import h11_v4_unattended_live_orchestration as subject
from app.services.h11_v4_gmo_actual_transport import V4GmoSealedCredentialPair
from app.services.h11_v4_gmo_g013_canary import V4GmoG013PreparedSession
from app.services.h11_v4_unattended_live_authorization import (
    V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainPolicy,
    V4HeartbeatChainStore,
)

_NOW = datetime(2026, 7, 24, 1, 0, tzinfo=UTC)
_GENERATION = "sha256:" + "b" * 64


def _intent() -> activation_module.V4GmoCanaryIntent:
    return activation_module.V4GmoCanaryIntent(
        generation_digest=_GENERATION,
        cycle_ref="c" * 64,
        side="BUY",
        exact_order_sheet_digest="sha256:" + "d" * 64,
    )


def _fake_session() -> SimpleNamespace:
    return SimpleNamespace(intent=_intent())


def _fake_credential_pair() -> V4GmoSealedCredentialPair:
    return cast(
        V4GmoSealedCredentialPair,
        SimpleNamespace(api_key=object(), api_secret=object()),
    )


def _authorization_artifact(state_root: Path) -> None:
    path = (
        state_root
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "daily-authorization.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": V4_UNATTENDED_LIVE_AUTHORIZATION_SCHEMA,
                "generation_digest": _GENERATION,
                "trading_day_jst": "2026-07-24",
                "maximum_entries": 1,
                "operator_authorized": True,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _risk_policy() -> PhaseBRiskPolicy:
    return PhaseBRiskPolicy(
        policy_label="H11_AUTO_INITIAL_MINIMUM_LIVE_V1",
        per_trade_loss_bound_jpy=5_000,
        daily_loss_limit_jpy=10_000,
        monthly_loss_limit_jpy=50_000,
        maximum_consecutive_losses=5,
    )


def _healthy_stores(
    tmp_path: Path,
) -> tuple[PhaseBRiskStore, DeadManStore, V4HeartbeatChainStore]:
    risk_store = PhaseBRiskStore(tmp_path / "risk.json", policy=_risk_policy())
    risk_store.save(risk_store.load())
    dead_man = DeadManStore(
        tmp_path / "dead-man.json",
        policy=DeadManPolicy(
            policy_label="H11_AUTO_DEAD_MAN_15_60_V1",
            maximum_heartbeat_age_seconds=60,
        ),
    )
    dead_man.heartbeat(heartbeat_utc=_NOW - timedelta(seconds=5))
    chain = V4HeartbeatChainStore(
        tmp_path / "chain.json",
        policy=V4HeartbeatChainPolicy(
            policy_label="H11_V4_UNATTENDED_CHAIN_TEST_V1",
            maximum_gap_seconds=60,
            minimum_continuous_seconds=300,
        ),
    )
    for offset in range(0, 331, 30):
        chain.beat(now_utc=_NOW - timedelta(seconds=330 - offset))
    return risk_store, dead_man, chain


def _run(
    tmp_path: Path,
    *,
    credential_pair: object | None = "DEFAULT",
    client: object | None = "DEFAULT",
    entry_gate_blocked_reasons: tuple[str, ...] = (),
    stores: tuple[PhaseBRiskStore, DeadManStore, V4HeartbeatChainStore] | None = None,
    session: object | None = None,
) -> object:
    risk_store, dead_man, chain = stores if stores is not None else _healthy_stores(tmp_path)
    _authorization_artifact(tmp_path)
    return subject.run_unattended_live_entry_cycle_once(
        session=cast(V4GmoG013PreparedSession, session or _fake_session()),
        state_root=tmp_path,
        risk_store=risk_store,
        risk_policy=_risk_policy(),
        dead_man_store=dead_man,
        heartbeat_chain_store=chain,
        notification_ready=True,
        entry_gate_blocked_reasons=entry_gate_blocked_reasons,
        credential_pair=cast(
            V4GmoSealedCredentialPair,
            _fake_credential_pair() if credential_pair == "DEFAULT" else credential_pair,
        ),
        client=cast(httpx.Client, object() if client == "DEFAULT" else client),
        now_utc=_NOW,
    )


def test_signature_requires_credential_pair_and_client_with_no_default() -> None:
    signature = inspect.signature(subject.run_unattended_live_entry_cycle_once)
    for name in ("credential_pair", "client"):
        assert signature.parameters[name].default is inspect.Parameter.empty, name


@pytest.mark.parametrize(
    ("credential_pair", "client"),
    ((None, "DEFAULT"), ("DEFAULT", None), (None, None)),
)
def test_explicit_none_credential_or_client_is_rejected_before_any_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    credential_pair: object | None,
    client: object | None,
) -> None:
    constructor = MagicMock()
    driver = MagicMock()
    monkeypatch.setattr(subject, "confirm_v4_unattended_authorization_once", constructor)
    monkeypatch.setattr(
        subject, "run_g013_actual_canary_after_unattended_authorization", driver
    )
    with pytest.raises(
        subject.V4UnattendedLiveOrchestrationError,
        match="UNATTENDED_ORCHESTRATION_CREDENTIAL_OR_CLIENT_REQUIRED",
    ):
        _run(tmp_path, credential_pair=credential_pair, client=client)
    constructor.assert_not_called()
    driver.assert_not_called()


def test_happy_path_runs_real_proof_constructor_then_hands_proofs_to_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The REAL proof constructor runs against real tmp-path stores (only the
    # driver is faked): the six conditions genuinely evaluate, the daily
    # authorization is genuinely consumed, and real proof objects reach the
    # driver together with the caller-supplied credential/client, unchanged.
    driver_calls: list[dict[str, object]] = []

    def _fake_driver(**kwargs: object) -> str:
        driver_calls.append(kwargs)
        return "CANARY_RESULT"

    monkeypatch.setattr(
        subject, "run_g013_actual_canary_after_unattended_authorization", _fake_driver
    )
    session = _fake_session()
    credential_pair = _fake_credential_pair()
    client = object()
    result = _run(tmp_path, session=session, credential_pair=credential_pair, client=client)
    assert result == "CANARY_RESULT"
    assert len(driver_calls) == 1
    call = driver_calls[0]
    assert isinstance(
        call["resume_proof"], activation_module.V4MajorIncidentResumeProof
    )
    assert isinstance(
        call["confirmation_proof"], activation_module.V4CurrentTurnConfirmationProof
    )
    # Identity, not equality: the exact caller-supplied objects reach the
    # driver -- nothing reconstructed, swapped, or defaulted in between.
    assert call["session"] is session
    assert call["credential_pair"] is credential_pair
    assert call["client"] is client
    marker = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "unattended-authorization-consumed-2026-07-24.json"
    )
    assert marker.is_file()


def test_blocked_condition_raises_and_driver_is_never_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = MagicMock()
    monkeypatch.setattr(
        subject, "run_g013_actual_canary_after_unattended_authorization", driver
    )
    with pytest.raises(
        activation_module.V4GmoCanaryActivationError,
        match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR",
    ):
        _run(tmp_path, entry_gate_blocked_reasons=("SPREAD_LIMIT_EXCEEDED",))
    driver.assert_not_called()
    marker = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "unattended-authorization-consumed-2026-07-24.json"
    )
    assert not marker.exists()


def test_second_call_same_day_is_refused_before_the_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = MagicMock(return_value="CANARY_RESULT")
    monkeypatch.setattr(
        subject, "run_g013_actual_canary_after_unattended_authorization", driver
    )
    # Shared stores across both calls -- this is what a genuine same-day retry
    # looks like (same on-disk state re-read), not two fresh setups.
    stores = _healthy_stores(tmp_path)
    _run(tmp_path, stores=stores)
    assert driver.call_count == 1
    with pytest.raises(
        activation_module.V4GmoCanaryActivationError,
        match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR",
    ):
        _run(tmp_path, stores=stores)
    assert driver.call_count == 1


def test_driver_failure_after_consumption_propagates_and_burns_the_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pins the module's single most consequential documented behavior
    # (§10.3/§11.6 accepted cost): a driver failure AFTER the authorization
    # was consumed (a) propagates unwrapped -- never caught, swallowed, or
    # retried by this module; (b) leaves the day's consumption marker on
    # disk; (c) a same-day retry is refused at the gate without the driver
    # ever being called again.
    class _DriverBoundaryError(RuntimeError):
        pass

    driver = MagicMock(side_effect=_DriverBoundaryError("BROKER_REJECTED"))
    monkeypatch.setattr(
        subject, "run_g013_actual_canary_after_unattended_authorization", driver
    )
    stores = _healthy_stores(tmp_path)
    with pytest.raises(_DriverBoundaryError, match="BROKER_REJECTED"):
        _run(tmp_path, stores=stores)
    assert driver.call_count == 1
    marker = (
        tmp_path
        / "h11_v4_unattended_live"
        / f"generation-{'b' * 64}"
        / "unattended-authorization-consumed-2026-07-24.json"
    )
    assert marker.is_file()
    with pytest.raises(
        activation_module.V4GmoCanaryActivationError,
        match="V4_CANARY_UNATTENDED_GATE_NOT_CLEAR",
    ):
        _run(tmp_path, stores=stores)
    assert driver.call_count == 1


def test_module_source_contains_no_exception_handlers_at_all() -> None:
    # Structural pin for the no-swallow property: a future "helpful"
    # try/except-and-retry edit must fail this test, not just code review.
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8"))
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert handlers == []


def test_own_source_never_references_bypass_or_credential_construction_names() -> None:
    # Discharges design doc §10.3's bypass-prevention obligation structurally:
    # the orchestration module's own AST contains no reference to the
    # phrase-based confirmation functions, the runtime binder, the permit
    # issuer, or real credential/transport constructors. Docstring prose does
    # not count; Name/Attribute/alias nodes do.
    forbidden = {
        "confirm_v4_major_incident_resume_exact",
        "confirm_v4_current_turn_exact",
        "bind_v4_gmo_actual_runtime",
        "issue_v4_gmo_actual_activation_permit",
        "consume_v4_gmo_actual_activation_permit",
        "V4GmoKeychainCredentialPair",
        "V4GmoHttpxPrivateTransport",
        # The driver's private helper skips its session consume/refresh and
        # credential guard, and accepts None/None -- calling it directly would
        # reach real-Keychain-on-None. Must never be referenced here.
        "_run_g013_actual_canary_from_refreshed_session",
    }
    tree = ast.parse(Path(subject.__file__).read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden:
            hits.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in forbidden:
            hits.append(node.attr)
        elif isinstance(node, ast.alias) and (
            node.name in forbidden or node.asname in forbidden
        ):
            hits.append(node.name)
    assert hits == []


def test_no_production_callers_outside_this_test_file() -> None:
    # Same scope note as the sibling G013 test: catches direct names and
    # aliased imports; cannot catch string-based/dynamic lookups.
    target = "run_unattended_live_entry_cycle_once"
    module_path = Path(subject.__file__)
    repo_root = module_path.parents[2]
    hits: list[str] = []
    for path in repo_root.rglob("*.py"):
        if path == module_path or "/tests/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                (isinstance(node, ast.Name) and node.id == target)
                or (isinstance(node, ast.Attribute) and node.attr == target)
                or (
                    isinstance(node, ast.alias)
                    and (node.name == target or node.asname == target)
                )
            ):
                hits.append(str(path))
    assert hits == []


def test_module_contains_no_dangerous_tokens() -> None:
    source = inspect.getsource(subject)
    for token in (
        "os.environ",
        "os.getenv",
        "keyring",
        "find-generic-password",
        "load_dotenv",
        "subprocess",
        "launchd",
    ):
        assert token not in source, token
