from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.h11_auto.persistence import H11AutoProcessLock
from app.h11_auto.runtime_safety import DeadManStore
from app.h11_auto.v4_gmo_generation import v4_gmo_dead_man_policy
from app.services import h11_v4_unattended_operational_readiness_no_post as subject
from app.services.h11_v4_unattended_controller_snapshot_no_post import (
    assemble_offline_controller_snapshot_no_post,
)
from app.services.h11_v4_unattended_integrated_controller_no_post import (
    evaluate_integrated_controller,
)
from app.services.h11_v4_unattended_live_heartbeat_chain import (
    V4HeartbeatChainPolicy,
    V4HeartbeatChainStore,
)
from app.tests.h11_auto.test_v4_unattended_controller_snapshot_no_post import (
    _sources,
)

_REVIEWED = "sha256:" + ("a" * 64)
_GENERATION = "sha256:" + ("b" * 64)


def _stores(tmp_path: Path, now: datetime):
    dead_man = DeadManStore(
        tmp_path / "dead-man.json",
        policy=v4_gmo_dead_man_policy(),
    )
    dead_man.heartbeat(heartbeat_utc=now)
    heartbeat = V4HeartbeatChainStore(
        tmp_path / "heartbeat-chain.json",
        policy=V4HeartbeatChainPolicy(
            policy_label="TEST_CHAIN",
            maximum_gap_seconds=60,
            minimum_continuous_seconds=300,
        ),
    )
    for offset in range(-300, 1, 60):
        heartbeat.beat(now_utc=now + timedelta(seconds=offset))
    return dead_man, heartbeat


def test_observation_uses_existing_gates_without_external_action(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    dead_man, heartbeat = _stores(tmp_path, now)
    evidence = subject.observe_operational_readiness_no_post(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        process_lock=H11AutoProcessLock(tmp_path / "process.lock"),
        dead_man_store=dead_man,
        heartbeat_chain_store=heartbeat,
        now_utc=now,
    )
    assert evidence.process_lock_clear is False
    assert evidence.dead_man_clear is False
    assert evidence.heartbeat_chain_clear is False
    assert evidence.notification_ready is False
    assert evidence.credential_read is False
    assert evidence.private_api_read is False
    assert evidence.notification_send_count == 0
    assert evidence.broker_write is False
    assert evidence.broker_post_count == 0
    assert evidence.live_action_authorized is False
    assert bool(evidence) is False


def test_held_process_lock_is_observed_without_releasing_owner(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    dead_man, heartbeat = _stores(tmp_path, now)
    owner = H11AutoProcessLock(tmp_path / "process.lock")
    assert owner.acquire() is True
    try:
        evidence = subject.observe_operational_readiness_no_post(
            reviewed_files_digest=_REVIEWED,
            generation_digest=_GENERATION,
            process_lock=H11AutoProcessLock(tmp_path / "process.lock"),
            dead_man_store=dead_man,
            heartbeat_chain_store=heartbeat,
            now_utc=now,
        )
        assert evidence.process_lock_clear is False
        assert owner.held is True
    finally:
        owner.release()


def test_store_and_controller_bind_exact_operational_evidence(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    sources = _sources()
    evidence = subject.build_operational_readiness_evidence_no_post(
        reviewed_files_digest=sources.reviewed_files_digest,
        generation_digest=sources.generation.digest,
        observed_at_utc=now,
        process_lock_clear=False,
        dead_man_clear=False,
        heartbeat_chain_clear=False,
        notification_ready=False,
    )
    path = tmp_path / "operational-readiness.json"
    store = subject.V4OperationalReadinessStoreNoPost(path)
    store.save(evidence)
    loaded = store.load(
        expected_reviewed_files_digest=sources.reviewed_files_digest,
        expected_generation_digest=sources.generation.digest,
        now_utc=now,
    )
    snapshot = assemble_offline_controller_snapshot_no_post(
        sources=replace(sources, operational_readiness_evidence=loaded),
        now_utc=now,
    )
    assert snapshot.process_lock_clear is False
    assert snapshot.dead_man_clear is False
    assert snapshot.heartbeat_chain_clear is False
    assert snapshot.notification_ready is False
    assert snapshot.operational_readiness_evidence_digest == evidence.artifact_digest
    decision = evaluate_integrated_controller(snapshot)
    assert decision.actual_integration_implemented is False
    assert decision.permit_issued is False
    assert decision.broker_post_authorized is False
    assert decision.broker_write is False
    assert decision.actual_post_count == 0


def test_expired_or_cross_generation_evidence_is_rejected() -> None:
    now = datetime.now(UTC)
    evidence = subject.build_operational_readiness_evidence_no_post(
        reviewed_files_digest=_REVIEWED,
        generation_digest=_GENERATION,
        observed_at_utc=now - timedelta(seconds=61),
        process_lock_clear=False,
        dead_man_clear=False,
        heartbeat_chain_clear=False,
        notification_ready=False,
    )
    with pytest.raises(
        subject.V4OperationalReadinessNoPostError,
        match="NOT_FRESH",
    ):
        subject.validate_operational_readiness_evidence_no_post(
            evidence,
            expected_reviewed_files_digest=_REVIEWED,
            expected_generation_digest=_GENERATION,
            now_utc=now,
        )
    with pytest.raises(
        subject.V4OperationalReadinessNoPostError,
        match="EVIDENCE_INVALID",
    ):
        subject.validate_operational_readiness_evidence_no_post(
            replace(evidence, generation_digest="sha256:" + ("c" * 64)),
            expected_reviewed_files_digest=_REVIEWED,
            expected_generation_digest=_GENERATION,
            now_utc=now - timedelta(seconds=30),
        )


def test_module_has_no_secret_network_notification_or_broker_action() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "Keychain",
        "security find-generic-password",
        ".send_once(",
        '\"POST\"',
        ".post(",
        "closeOrder",
        "cancelOrders",
        "changeOrder",
        "assert_real_broker_post_allowed",
        "permit_issued",
        "allow=True",
    ):
        assert forbidden not in source
