"""Fake-only acceptance tests for the G079 runtime resolution wiring.

G079 wires the G078 read-back resolution into the write action UNKNOWN path:
an UNKNOWN that resolves to CONFIRMED_EXECUTED continues the runtime, an
UNKNOWN that resolves to CONFIRMED_NOT_EXECUTED is non-terminal (next
scheduled cycle), and anything else halts.  All transports are fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.services.h11_v4_g026_private_get_keychain import (
    V4G026PrivateGetKeychainCredentialPair,
)
from app.services.h11_v4_g078_private_get_producer import (
    build_g078_read_back_producer,
)
from app.services.h11_v4_g078_runtime import G078FakeOnlyCallable
from app.services.h11_v4_g079_runtime import (
    G079_PERSISTENT_HALT_FILE,
    G079Action,
    G079ActionNotExecutedError,
    G079ActionOutcome,
    G079ActionScope,
    G079EffectiveState,
    G079EntryDispatcher,
    G079EntryState,
    G079Error,
    G079ExitDispatcher,
    G079FakeOnlyCallable,
    G079FakeOnlyPort,
    G079FrozenStrategyEvaluator,
    G079OneShotActionDispatcher,
    G079ReconciliationEvidence,
    G079ReconciliationState,
    G079ResidentSupervisor,
    G079SanitizedSnapshot,
    G079StrategyObservation,
)
from app.services.h11_v4_unattended_shadow_private_preflight import (
    V4UnattendedShadowSealedSecret,
)

GEN = "sha256:" + "a" * 64
REVIEWED = "sha256:" + "b" * 64
RELEASE = "sha256:" + "c" * 64
STRATEGY = "sha256:" + "d" * 64
SCOPE = "sha256:" + "e" * 64
NOW = datetime(2026, 8, 5, 1, 0, 0, tzinfo=UTC)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self.responses = responses

    def get(
        self, url: str, *, headers: dict | None = None, timeout: float | None = None
    ) -> _FakeResponse:
        del headers, timeout
        if url not in self.responses:
            raise AssertionError(f"unexpected url: {url}")
        return self.responses[url]


def _fake_credential_pair() -> V4G026PrivateGetKeychainCredentialPair:
    def reader(service: str, account: str) -> V4UnattendedShadowSealedSecret:
        assert service == "fx-strategy-lab-h11-v4-actual"
        return V4UnattendedShadowSealedSecret("fake-value")

    return V4G026PrivateGetKeychainCredentialPair(reader=reader)


def _read_back_client(*, executed: bool, ambiguous: bool = False) -> G078FakeOnlyCallable:
    if ambiguous:
        responses = {
            "https://api.coin.z.com/private/v1/latestExecutions": _FakeResponse(
                {"data": [{"size": "1000"}]}
            ),
            "https://api.coin.z.com/private/v1/openPositions": _FakeResponse({"data": []}),
            "https://api.coin.z.com/private/v1/activeOrders": _FakeResponse({"data": []}),
        }
    elif executed:
        responses = {
            "https://api.coin.z.com/private/v1/latestExecutions": _FakeResponse(
                {"data": [{"size": "1000"}]}
            ),
            "https://api.coin.z.com/private/v1/openPositions": _FakeResponse(
                {"data": [{"symbol": "USD_JPY", "size": "1000", "ocoOrderId": "1"}]}
            ),
            "https://api.coin.z.com/private/v1/activeOrders": _FakeResponse({"data": []}),
        }
    else:
        responses = {
            "https://api.coin.z.com/private/v1/latestExecutions": _FakeResponse({"data": []}),
            "https://api.coin.z.com/private/v1/openPositions": _FakeResponse({"data": []}),
            "https://api.coin.z.com/private/v1/activeOrders": _FakeResponse({"data": []}),
        }
    return build_g078_read_back_producer(
        credential_pair=_fake_credential_pair(),
        client=_FakeClient(responses),
        generation_digest=GEN,
        action_scope_digest=SCOPE,
        now_factory=lambda: NOW,
    )


@dataclass
class _FakeActionPort(G079FakeOnlyPort):
    outcome: G079ActionOutcome = G079ActionOutcome.UNKNOWN

    def attempt_once(self, scope: G079ActionScope) -> G079ActionOutcome:
        del scope
        return self.outcome


def _dispatcher(tmp_path: Path, *, read_back: G078FakeOnlyCallable) -> G079OneShotActionDispatcher:
    return G079OneShotActionDispatcher.bound(
        state_root=tmp_path,
        port=_FakeActionPort(outcome=G079ActionOutcome.UNKNOWN),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        release_capability_digest=RELEASE,
        strategy_artifact_digest=STRATEGY,
        resolution_read_back_client=read_back,
    )


def _attempt(
    d: G079OneShotActionDispatcher, action: G079Action = G079Action.ENTRY
) -> G079ActionOutcome:
    return d.attempt_once(
        cycle_id="cycle-1",
        action=action,
        side="SELL",
        quantity=1_000,
        reconciliation_artifact_digest="sha256:" + "f" * 64,
        now_utc=NOW,
    )


def _halt_exists(tmp_path: Path) -> bool:
    return (tmp_path / G079_PERSISTENT_HALT_FILE).is_file()


def test_unknown_entry_resolution_confirmed_executed_continues(tmp_path):
    outcome = _attempt(_dispatcher(tmp_path, read_back=_read_back_client(executed=True)))
    assert outcome is G079ActionOutcome.ACCEPTED
    assert not _halt_exists(tmp_path)


def test_unknown_entry_resolution_not_executed_is_non_terminal(tmp_path):
    with pytest.raises(G079ActionNotExecutedError, match="G079_ACTION_NOT_EXECUTED_NO_RETRY"):
        _attempt(_dispatcher(tmp_path, read_back=_read_back_client(executed=False)))
    assert not _halt_exists(tmp_path)


def test_unknown_entry_resolution_unresolved_halts(tmp_path):
    with pytest.raises(G079Error, match="G079_ACTION_RESULT_UNKNOWN_NO_RETRY"):
        _attempt(_dispatcher(tmp_path, read_back=_read_back_client(executed=False, ambiguous=True)))
    assert _halt_exists(tmp_path)


def test_unknown_protection_resolution_confirmed_returns_protected(tmp_path):
    outcome = _attempt(
        _dispatcher(tmp_path, read_back=_read_back_client(executed=True)),
        action=G079Action.PROTECTION,
    )
    assert outcome is G079ActionOutcome.PROTECTED
    assert not _halt_exists(tmp_path)


def test_dispatcher_requires_fake_resolution_client(tmp_path):
    with pytest.raises(G079Error, match="G079_FAKE_ONLY_RESOLUTION_READ_BACK_REQUIRED"):
        G079OneShotActionDispatcher.bound(
            state_root=tmp_path,
            port=_FakeActionPort(outcome=G079ActionOutcome.UNKNOWN),
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            release_capability_digest=RELEASE,
            strategy_artifact_digest=STRATEGY,
            resolution_read_back_client=lambda s, n: None,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Supervisor-level non-halting NOT_EXECUTED handling
# ---------------------------------------------------------------------------


@dataclass
class _FakeStrategySource(G079FakeOnlyPort):
    def observe(self, *, now_utc: datetime) -> G079StrategyObservation:
        del now_utc
        return G079StrategyObservation(
            strategy_artifact_digest=STRATEGY,
            strategy_version="SHORT_V1",
            symbol="USD_JPY",
            quantity=1_000,
            side="SELL",
            horizon="30m",
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            signal_actionable=True,
            risk_clear=True,
            market_open=True,
            spread_clear=True,
            quote_fresh=True,
            signal_fresh=True,
            limits_clear=True,
            position_flat=True,
            active_orders_zero=True,
        )


def _fresh_flat_evidence(cycle_id: str) -> G079ReconciliationEvidence:
    return G079ReconciliationEvidence(
        generation_label="H11_AUTO_30M_20260805_G079",
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id=cycle_id,
        observed_at_utc=NOW.isoformat(),
        state=G079ReconciliationState.FRESH_FLAT,
        latest_execution_count=0,
        open_position_count=0,
        active_order_count=0,
        position_side=None,
        position_open=False,
        account_flat=True,
        active_orders_zero=True,
        ownership_exact=False,
        quantity_matches=False,
        protection_confirmed=False,
        broker_get_count=0,
        private_api_read_count=0,
        credential_read_count=0,
        broker_write=False,
        broker_post_count=0,
        pending_transport=False,
        artifact_digest="sha256:" + "0" * 64,
    )


def _enable_release_capability(tmp_path: Path) -> None:
    """Write the four commissioning evidence files required by _capability_valid."""
    import hashlib
    import json

    def h(payload: dict) -> str:
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    operation: dict[str, object] = {
        "schema": "H11_V4_G079_OPERATION_60_RESULT_V1",
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260805_G079",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "broker_write": False,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
        "notification_attempt_count": 0,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
    }
    operation["artifact_digest"] = h({k: v for k, v in operation.items() if k != "artifact_digest"})
    (tmp_path / "g079-operation-60.result.json").write_text(
        json.dumps(operation), encoding="utf-8"
    )
    outcome: dict[str, object] = {
        "status": "PASSED",
        "generation_label": "H11_AUTO_30M_20260805_G079",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "broker_post_count": 0,
        "private_api_read_count": 0,
        "credential_read_count": 0,
        "arm_mutation_count": 0,
    }
    outcome["artifact_digest"] = h({k: v for k, v in outcome.items() if k != "artifact_digest"})
    (tmp_path / "g079-initial-activation.outcome.json").write_text(
        json.dumps(outcome), encoding="utf-8"
    )
    capability: dict[str, object] = {
        "schema": "H11_V4_G079_SWITCH_CONTROL_CAPABILITY_V1",
        "status": "ENABLED",
        "generation_label": "H11_AUTO_30M_20260805_G079",
        "generation_digest": GEN,
        "reviewed_files_digest": REVIEWED,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "daily_authorization_required": False,
        "per_trade_confirmation_required": False,
    }
    capability["artifact_digest"] = h(
        {k: v for k, v in capability.items() if k != "artifact_digest"}
    )
    (tmp_path / "g079-switch-control-capability.json").write_text(
        json.dumps(capability), encoding="utf-8"
    )
    (tmp_path / "g079-release-capability.json").write_text(
        json.dumps(capability), encoding="utf-8"
    )


def _supervisor(tmp_path: Path, *, read_back: G078FakeOnlyCallable) -> G079ResidentSupervisor:
    from app.services.h11_v4_g079_runtime import run_g079_reconciliation_cycle_once

    _enable_release_capability(tmp_path)

    dispatcher = _dispatcher(tmp_path, read_back=read_back)
    entry = G079EntryDispatcher(actions=dispatcher)
    exit_dispatch = G079ExitDispatcher(actions=dispatcher)

    @dataclass
    class _FakeReconciler(G079FakeOnlyPort):
        def reconcile_once(
            self, *, cycle_id: str, now_utc: datetime
        ) -> G079SanitizedSnapshot:
            del cycle_id, now_utc
            return G079SanitizedSnapshot(
                latest_execution_count=0,
                open_position_count=0,
                active_order_count=0,
                broker_get_count=0,
                private_api_read_count=0,
                credential_read_count=0,
                pending_transport=False,
            )

    run_g079_reconciliation_cycle_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        cycle_id="pre-cycle",
        reconciler=_FakeReconciler(),
        now_utc=NOW,
    )

    def reconcile(cycle_id: str, now_utc: datetime) -> G079ReconciliationEvidence:
        del now_utc
        return _fresh_flat_evidence(cycle_id)

    evaluator = G079FrozenStrategyEvaluator(
        source=_FakeStrategySource(),
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        strategy_artifact_digest=STRATEGY,
    )
    return G079ResidentSupervisor(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        reconciliation_runner=G079FakeOnlyCallable(reconcile),
        strategy_evaluator=evaluator,
        entry_dispatcher=entry,
        exit_dispatcher=exit_dispatch,
    )


def test_supervisor_entry_not_executed_is_non_halting(tmp_path):
    supervisor = _supervisor(tmp_path, read_back=_read_back_client(executed=False))
    status = supervisor.tick(now_utc=NOW, arm_on=True)
    assert status["effective_state"] != G079EffectiveState.HALTED.value
    assert status["entry_state"] == G079EntryState.DISABLED.value
    assert status["safe_reason_label"] == "G079_ACTION_NOT_EXECUTED_NEXT_CYCLE"
    assert not _halt_exists(tmp_path)
