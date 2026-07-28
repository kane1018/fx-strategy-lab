import fcntl
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from app.services.h11_v4_g020_shadow_observer_no_post import (
    V4G020CompletedPublicSlot,
    V4G020ShadowEvidenceStore,
    V4G020ShadowObservationStatus,
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("ascii")).hexdigest()


def _slot(minute: int, value: str = "slot") -> V4G020CompletedPublicSlot:
    return V4G020CompletedPublicSlot(
        slot_start_utc=datetime(2026, 7, 28, 1, minute, tzinfo=UTC),
        source_digest=_digest(value),
    )


def _store(tmp_path: Path) -> V4G020ShadowEvidenceStore:
    return V4G020ShadowEvidenceStore(
        path=tmp_path / "shadow-ledger.json",
        reviewed_files_digest=_digest("reviewed"),
        generation_digest=_digest("generation"),
    )


def test_shadow_observer_records_only_digest_and_no_authority(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = store.observe_once(fetch_completed_slot=lambda: _slot(1))

    assert result.status is V4G020ShadowObservationStatus.RECORDED
    assert result.completed_slot_count == 1
    assert result.public_get_count == 1
    assert result.broker_write is False
    assert result.broker_post_count == 0
    assert result.credential_read is False
    assert result.private_api_read is False
    assert result.raw_response_retained is False
    assert bool(result) is False
    serialized = (tmp_path / "shadow-ledger.json").read_text()
    assert "price" not in serialized
    assert "direction" not in serialized
    assert "credential" not in serialized


def test_shadow_observer_refuses_duplicate_completed_slot_without_rewrite(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.observe_once(fetch_completed_slot=lambda: _slot(1, "first"))
    result = store.observe_once(fetch_completed_slot=lambda: _slot(1, "changed"))

    assert first.status is V4G020ShadowObservationStatus.RECORDED
    assert result.status is V4G020ShadowObservationStatus.ALREADY_OBSERVED
    assert result.completed_slot_count == 1
    assert len(store.load_evidence().completed_slot_digests) == 1


def test_shadow_observer_failure_does_not_create_evidence_slot(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = store.observe_once(
        fetch_completed_slot=lambda: (_ for _ in ()).throw(RuntimeError("network"))
    )

    assert result.status is V4G020ShadowObservationStatus.FAILED_SAFE
    assert result.completed_slot_count == 0
    evidence = store.load_evidence()
    assert evidence.completed_slot_digests == ()
    assert evidence.abnormal_status_count == 1


def test_shadow_observer_failure_keeps_later_evidence_abnormal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.observe_once(
        fetch_completed_slot=lambda: (_ for _ in ()).throw(RuntimeError("network"))
    )
    result = store.observe_once(fetch_completed_slot=lambda: _slot(2, "later"))

    assert result.status is V4G020ShadowObservationStatus.RECORDED
    evidence = store.load_evidence()
    assert len(evidence.completed_slot_digests) == 1
    assert evidence.abnormal_status_count == 1


def test_shadow_observer_stops_before_fetch_at_twenty_slots(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for minute in range(20):
        result = store.observe_once(
            fetch_completed_slot=lambda minute=minute: _slot(minute, str(minute))
        )
        assert result.status is V4G020ShadowObservationStatus.RECORDED

    called = False

    def unexpected_fetch() -> V4G020CompletedPublicSlot:
        nonlocal called
        called = True
        return _slot(21)

    result = store.observe_once(fetch_completed_slot=unexpected_fetch)

    assert result.status is V4G020ShadowObservationStatus.CAP_REACHED
    assert called is False


def test_shadow_observer_stops_before_fetch_when_lock_is_held(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lock_path = tmp_path / "shadow-ledger.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = store.observe_once(fetch_completed_slot=_unexpected_slot_called)

    assert result.status is V4G020ShadowObservationStatus.LOCK_HELD
    assert result.public_get_count == 0


def _unexpected_slot_called() -> V4G020CompletedPublicSlot:
    raise AssertionError("fetch must not run while lock is held")
