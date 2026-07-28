"""G020 Public-only shadow evidence producer with no broker capability."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

from app.services.h11_v4_unattended_commissioning_no_post import (
    G020_SHADOW_EVIDENCE_SCHEMA,
    V4ShadowEvidenceArtifact,
    build_shadow_evidence_artifact,
)
from app.shadow.gmo_public import Candle, GmoPublicMarketDataClient

G020_SHADOW_LEDGER_SCHEMA = "H11_V4_G020_SHADOW_LEDGER_NO_POST_V1"
G020_SHADOW_MAXIMUM_SLOTS = 20
G020_SHADOW_PUBLICATION_DELAY_SECONDS = 10
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class V4G020ShadowObserverError(RuntimeError):
    """Fixed safe observer failure; provider content is never exposed."""


class V4G020ShadowObservationStatus(str, Enum):
    RECORDED = "G020_SHADOW_SLOT_RECORDED_NO_POST"
    ALREADY_OBSERVED = "G020_SHADOW_SLOT_ALREADY_OBSERVED_NO_POST"
    CAP_REACHED = "G020_SHADOW_SLOT_CAP_REACHED_NO_POST"
    LOCK_HELD = "G020_SHADOW_OBSERVER_LOCK_HELD_NO_POST"
    FAILED_SAFE = "G020_SHADOW_OBSERVER_FAILED_SAFE"


@dataclass(frozen=True)
class V4G020CompletedPublicSlot:
    slot_start_utc: datetime
    source_digest: str


@dataclass(frozen=True)
class V4G020RecordedShadowSlot:
    slot_start_utc: str
    source_digest: str


@dataclass(frozen=True)
class V4G020ShadowLedger:
    schema: str
    reviewed_files_digest: str
    generation_digest: str
    recorded_slots: tuple[V4G020RecordedShadowSlot, ...]
    abnormal_status_count: int
    ledger_digest: str

    def evidence(self) -> V4ShadowEvidenceArtifact:
        return build_shadow_evidence_artifact(
            schema=G020_SHADOW_EVIDENCE_SCHEMA,
            reviewed_files_digest=self.reviewed_files_digest,
            generation_digest=self.generation_digest,
            completed_slot_digests=tuple(
                slot.source_digest for slot in self.recorded_slots
            ),
            abnormal_status_count=self.abnormal_status_count,
            broker_write=False,
            actual_post_count=0,
        )


@dataclass(frozen=True)
class V4G020ShadowObservationResult:
    status: V4G020ShadowObservationStatus
    completed_slot_count: int
    public_get_count: int
    broker_write: bool = False
    broker_post_count: int = 0
    credential_read: bool = False
    private_api_read: bool = False
    raw_response_retained: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "completed_slot_count": self.completed_slot_count,
            "public_get_count": self.public_get_count,
            "broker_write": self.broker_write,
            "broker_post_count": self.broker_post_count,
            "credential_read": self.credential_read,
            "private_api_read": self.private_api_read,
            "raw_response_retained": self.raw_response_retained,
            "authorization_granted": False,
            "activation_permit_issued": False,
        }

    def __bool__(self) -> bool:
        return False


def fetch_latest_completed_public_m1_slot(
    *, now_utc: datetime, client: GmoPublicMarketDataClient
) -> V4G020CompletedPublicSlot:
    """Fetch one Public M1 response and immediately reduce it to a digest."""

    if now_utc.tzinfo is None:
        raise V4G020ShadowObserverError("G020_SHADOW_TIMEZONE_REQUIRED")
    try:
        candles = client.fetch_candles(
            "USD_JPY",
            "M1",
            limit=200,
            price_type="BID",
            date=now_utc.astimezone(UTC).strftime("%Y%m%d"),
        )
    except Exception as error:
        raise V4G020ShadowObserverError(
            "G020_SHADOW_PUBLIC_SOURCE_UNAVAILABLE"
        ) from error
    cutoff = now_utc.astimezone(UTC) - timedelta(
        seconds=G020_SHADOW_PUBLICATION_DELAY_SECONDS
    )
    completed: list[tuple[datetime, Candle]] = []
    for candle in candles:
        try:
            start = datetime.fromisoformat(candle.time.replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise V4G020ShadowObserverError(
                "G020_SHADOW_PUBLIC_SOURCE_INVALID"
            ) from error
        if start.tzinfo is None:
            raise V4G020ShadowObserverError("G020_SHADOW_PUBLIC_SOURCE_INVALID")
        start = start.astimezone(UTC)
        if start + timedelta(minutes=1) <= cutoff:
            completed.append((start, candle))
    if not completed:
        raise V4G020ShadowObserverError("G020_SHADOW_COMPLETED_SLOT_UNAVAILABLE")
    start, candle = completed[-1]
    return V4G020CompletedPublicSlot(
        slot_start_utc=start,
        source_digest=_digest(
            {
                "schema": G020_SHADOW_LEDGER_SCHEMA,
                "symbol": "USD_JPY",
                "price_type": "BID",
                "slot_start_utc": start.isoformat(),
                "open": repr(candle.open),
                "high": repr(candle.high),
                "low": repr(candle.low),
                "close": repr(candle.close),
            }
        ),
    )


class V4G020ShadowEvidenceStore:
    """Atomic local ledger; it never stores raw market values or authority."""

    def __init__(
        self,
        *,
        path: Path,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> None:
        self._path = path.resolve()
        self._reviewed_files_digest = reviewed_files_digest
        self._generation_digest = generation_digest
        if not _SHA256.fullmatch(reviewed_files_digest) or not _SHA256.fullmatch(
            generation_digest
        ):
            raise V4G020ShadowObserverError("G020_SHADOW_BINDING_INVALID")

    def observe_once(
        self,
        *,
        fetch_completed_slot: Callable[[], V4G020CompletedPublicSlot],
    ) -> V4G020ShadowObservationResult:
        with self._exclusive_lock() as acquired:
            if not acquired:
                return _result(
                    V4G020ShadowObservationStatus.LOCK_HELD,
                    self._load_or_empty(),
                    0,
                )
            return self._observe_once_locked(fetch_completed_slot=fetch_completed_slot)

    def _observe_once_locked(
        self,
        *,
        fetch_completed_slot: Callable[[], V4G020CompletedPublicSlot],
    ) -> V4G020ShadowObservationResult:
        ledger = self._load_or_empty()
        if len(ledger.recorded_slots) >= G020_SHADOW_MAXIMUM_SLOTS:
            return _result(V4G020ShadowObservationStatus.CAP_REACHED, ledger, 0)
        try:
            completed = fetch_completed_slot()
        except Exception:
            return self._record_abnormal(ledger, public_get_count=1)
        if not _valid_completed_slot(completed):
            return self._record_abnormal(ledger, public_get_count=1)
        slot_key = completed.slot_start_utc.astimezone(UTC).isoformat()
        if any(slot.slot_start_utc == slot_key for slot in ledger.recorded_slots):
            return _result(V4G020ShadowObservationStatus.ALREADY_OBSERVED, ledger, 1)
        updated = _ledger(
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
            recorded_slots=(
                *ledger.recorded_slots,
                V4G020RecordedShadowSlot(slot_key, completed.source_digest),
            ),
            abnormal_status_count=ledger.abnormal_status_count,
        )
        self._write(updated)
        return _result(V4G020ShadowObservationStatus.RECORDED, updated, 1)

    @contextmanager
    def _exclusive_lock(self):
        import fcntl

        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(".lock")
        if lock_path.exists() and lock_path.is_symlink():
            raise V4G020ShadowObserverError("G020_SHADOW_LEDGER_UNAVAILABLE")
        with lock_path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _record_abnormal(
        self,
        ledger: V4G020ShadowLedger,
        *,
        public_get_count: int,
    ) -> V4G020ShadowObservationResult:
        updated = _ledger(
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
            recorded_slots=ledger.recorded_slots,
            abnormal_status_count=ledger.abnormal_status_count + 1,
        )
        self._write(updated)
        return _result(V4G020ShadowObservationStatus.FAILED_SAFE, updated, public_get_count)

    def load_evidence(self) -> V4ShadowEvidenceArtifact:
        return self._load_or_empty().evidence()

    def _load_or_empty(self) -> V4G020ShadowLedger:
        if not self._path.exists():
            return _ledger(
                reviewed_files_digest=self._reviewed_files_digest,
                generation_digest=self._generation_digest,
                recorded_slots=(),
                abnormal_status_count=0,
            )
        if not self._path.is_file() or self._path.is_symlink():
            raise V4G020ShadowObserverError("G020_SHADOW_LEDGER_UNAVAILABLE")
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            slots = tuple(
                V4G020RecordedShadowSlot(**slot)
                for slot in payload.pop("recorded_slots")
            )
            ledger = V4G020ShadowLedger(recorded_slots=slots, **payload)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise V4G020ShadowObserverError("G020_SHADOW_LEDGER_INVALID") from error
        expected = _ledger(
            reviewed_files_digest=ledger.reviewed_files_digest,
            generation_digest=ledger.generation_digest,
            recorded_slots=ledger.recorded_slots,
            abnormal_status_count=ledger.abnormal_status_count,
        )
        if (
            ledger != expected
            or ledger.reviewed_files_digest != self._reviewed_files_digest
            or ledger.generation_digest != self._generation_digest
        ):
            raise V4G020ShadowObserverError("G020_SHADOW_LEDGER_BINDING_MISMATCH")
        return ledger

    def _write(self, ledger: V4G020ShadowLedger) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists() and self._path.is_symlink():
            raise V4G020ShadowObserverError("G020_SHADOW_LEDGER_UNAVAILABLE")
        encoded = json.dumps(asdict(ledger), sort_keys=True, separators=(",", ":"))
        descriptor, temporary = tempfile.mkstemp(
            prefix=".g020-shadow-", dir=str(self._path.parent), text=True
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except OSError as error:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise V4G020ShadowObserverError("G020_SHADOW_LEDGER_WRITE_FAILED") from error


def _ledger(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    recorded_slots: tuple[V4G020RecordedShadowSlot, ...],
    abnormal_status_count: int,
) -> V4G020ShadowLedger:
    payload = {
        "schema": G020_SHADOW_LEDGER_SCHEMA,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "recorded_slots": [asdict(slot) for slot in recorded_slots],
        "abnormal_status_count": abnormal_status_count,
    }
    return V4G020ShadowLedger(
        ledger_digest=_digest(payload),
        schema=G020_SHADOW_LEDGER_SCHEMA,
        reviewed_files_digest=reviewed_files_digest,
        generation_digest=generation_digest,
        recorded_slots=recorded_slots,
        abnormal_status_count=abnormal_status_count,
    )


def _valid_completed_slot(slot: V4G020CompletedPublicSlot) -> bool:
    return (
        slot.slot_start_utc.tzinfo is not None
        and bool(_SHA256.fullmatch(slot.source_digest))
    )


def _result(
    status: V4G020ShadowObservationStatus,
    ledger: V4G020ShadowLedger,
    public_get_count: int,
) -> V4G020ShadowObservationResult:
    return V4G020ShadowObservationResult(
        status=status,
        completed_slot_count=len(ledger.recorded_slots),
        public_get_count=public_get_count,
    )


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
