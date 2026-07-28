from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from app.services import h11_v4_predecessor_completion_evidence_v2_fake_only as subject


def _result(**overrides: bool | int) -> subject.V4FakeOnlyReconciliationResult:
    values: dict[str, bool | int] = {
        "fake_only": True,
        "result_known": True,
        "subject_entry_observed": True,
        "account_flat": True,
        "active_orders_zero": True,
        "broker_read_count": 3,
        "broker_write_attempt_count": 0,
        "raw_response_retained": False,
        "identifier_exposed": False,
    }
    values.update(overrides)
    return subject.V4FakeOnlyReconciliationResult(**values)


def test_fake_only_v2_pair_is_cross_bound_and_non_commissioning(tmp_path: Path) -> None:
    target = "sha256:" + "b" * 64
    root = tmp_path / ("generation-" + "b" * 64)
    evidence = subject.produce_fake_only_v2_evidence(
        runtime_root=root,
        origin_generation_digest="sha256:" + "a" * 64,
        target_generation_digest=target,
        result=_result(),
    )
    started = json.loads((root / "predecessor-completion-v2-fake.started.json").read_text())
    passed = json.loads((root / "predecessor-completion-v2-fake.passed.json").read_text())
    assert started["target_generation_digest"] == target
    assert passed["target_generation_digest"] == target
    assert passed["started_marker_digest"] == evidence.started_marker_digest
    assert passed["synthetic_evidence"] is True
    assert evidence.commissioning_eligible is False
    assert bool(evidence) is False
    assert evidence.broker_write is False
    assert evidence.actual_post_count == 0


@pytest.mark.parametrize(
    "overrides",
    ({"fake_only": False}, {"account_flat": False}, {"broker_write_attempt_count": 1}),
)
def test_non_synthetic_or_nonclear_input_cannot_create_markers(
    tmp_path: Path, overrides: dict[str, bool | int]
) -> None:
    with pytest.raises(subject.V4PredecessorCompletionV2FakeOnlyError, match="REJECTED"):
        subject.produce_fake_only_v2_evidence(
            runtime_root=tmp_path / ("generation-" + "b" * 64),
            origin_generation_digest="sha256:" + "a" * 64,
            target_generation_digest="sha256:" + "b" * 64,
            result=_result(**overrides),
        )
    assert not list(tmp_path.iterdir())


def test_wrong_runtime_target_or_reuse_fails_closed(tmp_path: Path) -> None:
    target = "sha256:" + "b" * 64
    with pytest.raises(subject.V4PredecessorCompletionV2FakeOnlyError, match="REJECTED"):
        subject.produce_fake_only_v2_evidence(
            runtime_root=tmp_path / ("generation-" + "c" * 64),
            origin_generation_digest="sha256:" + "a" * 64,
            target_generation_digest=target,
            result=_result(),
        )
    root = tmp_path / ("generation-" + "b" * 64)
    subject.produce_fake_only_v2_evidence(
        runtime_root=root,
        origin_generation_digest="sha256:" + "a" * 64,
        target_generation_digest=target,
        result=_result(),
    )
    with pytest.raises(subject.V4PredecessorCompletionV2FakeOnlyError, match="UNAVAILABLE"):
        subject.produce_fake_only_v2_evidence(
            runtime_root=root,
            origin_generation_digest="sha256:" + "a" * 64,
            target_generation_digest=target,
            result=_result(),
        )


def test_fake_only_producer_has_no_live_dependencies() -> None:
    source = inspect.getsource(subject)
    for forbidden in (
        "httpx",
        "Keychain",
        "transport",
        "closeOrder",
        "cancelOrders",
        "notification",
        "V4Gmo",
    ):
        assert forbidden not in source
