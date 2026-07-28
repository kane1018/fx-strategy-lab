"""Generation-bound Public-only shadow evidence, with no broker capability."""

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
    CURRENT_COMMISSIONING_SCHEMA,
    CURRENT_SHADOW_EVIDENCE_SCHEMA,
    V4CommissioningArtifact,
    V4PredecessorCanaryCompletionArtifact,
    V4ShadowEvidenceArtifact,
    build_commissioning_artifact,
    build_shadow_evidence_artifact,
    evaluate_commissioning,
)
from app.shadow.gmo_public import Candle, GmoPublicMarketDataClient

CURRENT_SHADOW_LEDGER_SCHEMA = "H11_V4_CURRENT_GENERATION_SHADOW_LEDGER_NO_POST_V1"
CURRENT_SHADOW_MAXIMUM_SLOTS = 20
CURRENT_SHADOW_PUBLICATION_DELAY_SECONDS = 10
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class V4CurrentGenerationShadowError(RuntimeError):
    """Fixed safe error that never includes provider content."""


class V4CurrentGenerationShadowStatus(str, Enum):
    RECORDED = "CURRENT_GENERATION_SHADOW_SLOT_RECORDED_NO_POST"
    ALREADY_OBSERVED = "CURRENT_GENERATION_SHADOW_SLOT_ALREADY_OBSERVED_NO_POST"
    CAP_REACHED = "CURRENT_GENERATION_SHADOW_SLOT_CAP_REACHED_NO_POST"
    LOCK_HELD = "CURRENT_GENERATION_SHADOW_LOCK_HELD_NO_POST"
    FAILED_SAFE = "CURRENT_GENERATION_SHADOW_FAILED_SAFE"
    CORRECTIVE_GENERATION_REQUIRED = (
        "CURRENT_GENERATION_SHADOW_PERSISTENT_HALT_CORRECTIVE_GENERATION_REQUIRED"
    )


@dataclass(frozen=True)
class V4CurrentGenerationCompletedSlot:
    slot_start_utc: datetime
    source_digest: str


@dataclass(frozen=True)
class _RecordedSlot:
    slot_start_utc: str
    source_digest: str


@dataclass(frozen=True)
class _Ledger:
    schema: str
    reviewed_files_digest: str
    generation_digest: str
    recorded_slots: tuple[_RecordedSlot, ...]
    abnormal_status_count: int
    ledger_digest: str

    def evidence(self) -> V4ShadowEvidenceArtifact:
        return build_shadow_evidence_artifact(
            schema=CURRENT_SHADOW_EVIDENCE_SCHEMA,
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
class V4CurrentGenerationShadowResult:
    status: V4CurrentGenerationShadowStatus
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
            "broker_write": False,
            "broker_post_count": 0,
            "credential_read": False,
            "private_api_read": False,
            "raw_response_retained": False,
            "authorization_granted": False,
            "activation_permit_issued": False,
        }

    def __bool__(self) -> bool:
        return False


def fetch_latest_completed_public_m1_slot(
    *, now_utc: datetime, client: GmoPublicMarketDataClient
) -> V4CurrentGenerationCompletedSlot:
    if now_utc.tzinfo is None:
        raise V4CurrentGenerationShadowError("CURRENT_SHADOW_TIMEZONE_REQUIRED")
    try:
        candles = client.fetch_candles(
            "USD_JPY",
            "M1",
            limit=200,
            price_type="BID",
            date=now_utc.astimezone(UTC).strftime("%Y%m%d"),
        )
    except Exception as error:
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_PUBLIC_SOURCE_UNAVAILABLE"
        ) from error
    cutoff = now_utc.astimezone(UTC) - timedelta(
        seconds=CURRENT_SHADOW_PUBLICATION_DELAY_SECONDS
    )
    completed: list[tuple[datetime, Candle]] = []
    for candle in candles:
        try:
            start = datetime.fromisoformat(candle.time.replace("Z", "+00:00"))
        except (TypeError, ValueError) as error:
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_PUBLIC_SOURCE_INVALID"
            ) from error
        if start.tzinfo is None:
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_PUBLIC_SOURCE_INVALID"
            )
        start = start.astimezone(UTC)
        if start + timedelta(minutes=1) <= cutoff:
            completed.append((start, candle))
    if not completed:
        raise V4CurrentGenerationShadowError("CURRENT_SHADOW_COMPLETED_SLOT_UNAVAILABLE")
    start, candle = completed[-1]
    return V4CurrentGenerationCompletedSlot(
        slot_start_utc=start,
        source_digest=_digest(
            {
                "schema": CURRENT_SHADOW_LEDGER_SCHEMA,
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


class V4CurrentGenerationShadowStore:
    """Atomic local ledger that stores only opaque slot digests."""

    def __init__(
        self,
        *,
        path: Path,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> None:
        self._path = path.resolve()
        self._reviewed = reviewed_files_digest
        self._generation = generation_digest
        if not _SHA256.fullmatch(reviewed_files_digest) or not _SHA256.fullmatch(
            generation_digest
        ):
            raise V4CurrentGenerationShadowError("CURRENT_SHADOW_BINDING_INVALID")

    def observe_once(
        self,
        *,
        fetch_completed_slot: Callable[[], V4CurrentGenerationCompletedSlot],
    ) -> V4CurrentGenerationShadowResult:
        with self._exclusive_lock() as acquired:
            if not acquired:
                return _result(
                    V4CurrentGenerationShadowStatus.LOCK_HELD,
                    self._load_or_empty(),
                    0,
                )
            ledger = self._load_or_empty()
            if ledger.abnormal_status_count > 0 or self._terminal_halt_exists():
                return _result(
                    V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED,
                    ledger,
                    0,
                )
            if len(ledger.recorded_slots) >= CURRENT_SHADOW_MAXIMUM_SLOTS:
                return _result(
                    V4CurrentGenerationShadowStatus.CAP_REACHED, ledger, 0
                )
            try:
                slot = fetch_completed_slot()
            except Exception:
                return self._record_abnormal(ledger)
            if not _valid_slot(slot):
                return self._record_abnormal(ledger)
            key = slot.slot_start_utc.astimezone(UTC).isoformat()
            if any(recorded.slot_start_utc == key for recorded in ledger.recorded_slots):
                return _result(
                    V4CurrentGenerationShadowStatus.ALREADY_OBSERVED, ledger, 1
                )
            updated = _ledger(
                self._reviewed,
                self._generation,
                (*ledger.recorded_slots, _RecordedSlot(key, slot.source_digest)),
                ledger.abnormal_status_count,
            )
            self._write(updated)
            return _result(V4CurrentGenerationShadowStatus.RECORDED, updated, 1)

    def load_evidence(self) -> V4ShadowEvidenceArtifact:
        return self._load_or_empty().evidence()

    @contextmanager
    def _exclusive_lock(self):
        import fcntl

        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._path.with_suffix(".lock")
        if lock.exists() and lock.is_symlink():
            raise V4CurrentGenerationShadowError("CURRENT_SHADOW_LEDGER_UNAVAILABLE")
        with lock.open("a+", encoding="utf-8") as handle:
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
        self, ledger: _Ledger
    ) -> V4CurrentGenerationShadowResult:
        _create_once(
            self._terminal_halt_path(),
            {
                "schema": "H11_V4_CURRENT_SHADOW_TERMINAL_HALT_V1",
                "reviewed_files_digest": self._reviewed,
                "generation_digest": self._generation,
            },
        )
        updated = _ledger(
            self._reviewed,
            self._generation,
            ledger.recorded_slots,
            ledger.abnormal_status_count + 1,
        )
        try:
            self._write(updated)
        except V4CurrentGenerationShadowError:
            return _result(
                V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED,
                ledger,
                1,
            )
        return _result(
            V4CurrentGenerationShadowStatus.CORRECTIVE_GENERATION_REQUIRED,
            updated,
            1,
        )

    def _terminal_halt_path(self) -> Path:
        return self._path.with_name("shadow-terminal-halt.json")

    def _terminal_halt_exists(self) -> bool:
        path = self._terminal_halt_path()
        if not path.exists():
            if path.is_symlink():
                raise V4CurrentGenerationShadowError(
                    "CURRENT_SHADOW_TERMINAL_HALT_INVALID"
                )
            return False
        if not path.is_file() or path.is_symlink():
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_TERMINAL_HALT_INVALID"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_TERMINAL_HALT_INVALID"
            ) from error
        if payload != {
            "schema": "H11_V4_CURRENT_SHADOW_TERMINAL_HALT_V1",
            "reviewed_files_digest": self._reviewed,
            "generation_digest": self._generation,
        }:
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_TERMINAL_HALT_INVALID"
            )
        return True

    def _load_or_empty(self) -> _Ledger:
        if not self._path.exists():
            return _ledger(self._reviewed, self._generation, (), 0)
        if not self._path.is_file() or self._path.is_symlink():
            raise V4CurrentGenerationShadowError("CURRENT_SHADOW_LEDGER_UNAVAILABLE")
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            slots = tuple(_RecordedSlot(**slot) for slot in payload.pop("recorded_slots"))
            ledger = _Ledger(recorded_slots=slots, **payload)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_LEDGER_INVALID"
            ) from error
        expected = _ledger(
            ledger.reviewed_files_digest,
            ledger.generation_digest,
            ledger.recorded_slots,
            ledger.abnormal_status_count,
        )
        if (
            ledger != expected
            or ledger.reviewed_files_digest != self._reviewed
            or ledger.generation_digest != self._generation
        ):
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_LEDGER_BINDING_MISMATCH"
            )
        return ledger

    def _write(self, ledger: _Ledger) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(asdict(ledger), sort_keys=True, separators=(",", ":"))
        descriptor, temporary = tempfile.mkstemp(
            prefix=".current-shadow-",
            dir=str(self._path.parent),
            text=True,
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
            raise V4CurrentGenerationShadowError(
                "CURRENT_SHADOW_LEDGER_WRITE_FAILED"
            ) from error


def build_current_generation_commissioning_artifact(
    *,
    generation_label: str,
    reviewed_files_digest: str,
    generation_digest: str,
    shadow: V4ShadowEvidenceArtifact,
    predecessor: V4PredecessorCanaryCompletionArtifact,
    architecture_review_clear: bool,
    safety_review_clear: bool,
    operations_review_clear: bool,
    review_evidence_digest: str,
) -> V4CommissioningArtifact:
    return build_commissioning_artifact(
        schema=CURRENT_COMMISSIONING_SCHEMA,
        generation_label=generation_label,
        prior_canary_generation_label=predecessor.prior_canary_generation_label,
        prior_canary_generation_digest=predecessor.prior_canary_generation_digest,
        prior_canary_reconciliation_artifact_digest=(
            predecessor.reconciliation_passed_marker_digest
        ),
        prior_canary_handoff_digest=predecessor.artifact_digest,
        commissioning_entry_disabled=True,
        reviewed_files_digest=reviewed_files_digest,
        generation_digest=generation_digest,
        shadow_evidence_digest=shadow.artifact_digest,
        shadow_reviewed_files_digest=shadow.reviewed_files_digest,
        shadow_generation_digest=shadow.generation_digest,
        shadow_scheduler_cycles_clear=len(shadow.completed_slot_digests),
        prior_canary_cycle_complete=(
            predecessor.commissioning_eligible is False
            and predecessor.entry_fill_recorded
            and predecessor.protection_confirmed
        ),
        prior_canary_flat_reconciled=(
            predecessor.reconciliation_result_known and predecessor.account_flat
        ),
        account_wide_active_orders_zero_evidence=predecessor.active_orders_zero,
        restart_safe_exit_contract_clear=False,
        notification_contract_clear=False,
        architecture_review_clear=architecture_review_clear,
        safety_review_clear=safety_review_clear,
        operations_review_clear=operations_review_clear,
        review_evidence_digest=review_evidence_digest,
    )


def write_canonical_shadow_artifacts(
    *,
    repository: Path,
    directory: Path,
    shadow: V4ShadowEvidenceArtifact,
    commissioning: V4CommissioningArtifact,
    predecessor: V4PredecessorCanaryCompletionArtifact,
) -> None:
    load_current_review_evidence(
        repository=repository,
        reviewed_files_digest=commissioning.reviewed_files_digest,
        generation_digest=commissioning.generation_digest,
        generation_label=commissioning.generation_label,
        expected_digest=commissioning.review_evidence_digest,
    )
    if (
        evaluate_commissioning(commissioning, shadow, predecessor).status.value
        != "SHADOW_COMMISSIONED_NO_POST"
    ):
        raise V4CurrentGenerationShadowError("CURRENT_SHADOW_COMMISSION_NOT_ELIGIBLE")
    directory.mkdir(parents=True, exist_ok=True)
    started = directory / "commissioning-seal.started.json"
    passed = directory / "commissioning-seal.passed.json"
    if started.exists() or passed.exists():
        raise V4CurrentGenerationShadowError("CURRENT_SHADOW_COMMISSION_ALREADY_SEALED")
    _create_once(
        started,
        {
            "schema": "H11_V4_CURRENT_SHADOW_SEAL_V1",
            "generation_digest": commissioning.generation_digest,
            "reviewed_files_digest": commissioning.reviewed_files_digest,
        },
    )
    try:
        for name, artifact in (
            ("shadow-evidence.json", shadow),
            ("commissioning.json", commissioning),
        ):
            path = directory / name
            if path.is_symlink():
                raise V4CurrentGenerationShadowError(
                    "CURRENT_SHADOW_ARTIFACT_UNAVAILABLE"
                )
            _atomic_json(path, asdict(artifact))
        _create_once(
            passed,
            {
                "schema": "H11_V4_CURRENT_SHADOW_SEAL_V1",
                "generation_digest": commissioning.generation_digest,
                "reviewed_files_digest": commissioning.reviewed_files_digest,
                "shadow_evidence_digest": shadow.artifact_digest,
                "commissioning_digest": commissioning.artifact_digest,
            },
        )
    except Exception as error:
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_COMMISSION_PERSISTENT_HALT_"
            "CORRECTIVE_GENERATION_REQUIRED"
        ) from error


def load_sealed_current_shadow_artifacts(
    *, directory: Path
) -> tuple[V4ShadowEvidenceArtifact, V4CommissioningArtifact]:
    from app.services.h11_v4_unattended_commissioning_no_post import (
        load_commissioning_artifact,
        load_shadow_evidence_artifact,
    )

    passed = directory / "commissioning-seal.passed.json"
    try:
        marker = json.loads(passed.read_text(encoding="utf-8"))
        shadow = load_shadow_evidence_artifact(directory / "shadow-evidence.json")
        commissioning = load_commissioning_artifact(directory / "commissioning.json")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4CurrentGenerationShadowError("CURRENT_SHADOW_SEAL_UNAVAILABLE") from error
    if (
        marker != {
            "schema": "H11_V4_CURRENT_SHADOW_SEAL_V1",
            "generation_digest": commissioning.generation_digest,
            "reviewed_files_digest": commissioning.reviewed_files_digest,
            "shadow_evidence_digest": shadow.artifact_digest,
            "commissioning_digest": commissioning.artifact_digest,
        }
    ):
        raise V4CurrentGenerationShadowError("CURRENT_SHADOW_SEAL_INVALID")
    return shadow, commissioning


def load_current_review_evidence(
    *,
    repository: Path,
    reviewed_files_digest: str,
    generation_digest: str,
    generation_label: str,
    expected_digest: str | None = None,
) -> dict[str, bool | str]:
    path = repository / "docs/templates/h11_v4_actual_preparation_evidence.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_REVIEW_EVIDENCE_INVALID"
        ) from error
    if not isinstance(payload, dict):
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_REVIEW_EVIDENCE_INVALID"
        )
    expected_evidence = {
        "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
        "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "generation_manifest_digest": generation_digest,
        "generation_label": generation_label,
        "actual_post_authorized": False,
        "broker_post_authorized": False,
        "activation_permit_issued": False,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
        "danger_scan_passed": True,
        "diff_check_passed": True,
        "focused_tests_passed": True,
        "related_tests_passed": True,
        "ruff_passed": True,
    }
    digest = _digest(payload)
    if (
        any(payload.get(key) != value for key, value in expected_evidence.items())
        or (expected_digest is not None and digest != expected_digest)
    ):
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_REVIEW_EVIDENCE_INVALID"
        )
    try:
        attestation = json.loads(
            (
                repository
                / "docs/templates/h11_v4_independent_review_attestation.json"
            ).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_REVIEW_EVIDENCE_INVALID"
        ) from error
    if (
        not isinstance(attestation, dict)
        or attestation.get("schema")
        != "H11_V4_INDEPENDENT_REVIEW_ATTESTATION_V1"
        or attestation.get("reviewed_files_digest") != reviewed_files_digest
        or attestation.get("generation_digest") != generation_digest
        or attestation.get("generation_label") != generation_label
        or attestation.get("architecture_status") != "CLEAR"
        or attestation.get("safety_status") != "CLEAR"
        or attestation.get("operations_status") != "CLEAR"
        or attestation.get("artifact_digest") != _digest(
            {
                key: value
                for key, value in attestation.items()
                if key != "artifact_digest"
            }
        )
        or payload.get("independent_review_attestation_digest")
        != attestation.get("artifact_digest")
    ):
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_REVIEW_EVIDENCE_INVALID"
        )
    return {
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
        "review_evidence_digest": digest,
    }


def _ledger(
    reviewed: str,
    generation: str,
    slots: tuple[_RecordedSlot, ...],
    abnormal: int,
) -> _Ledger:
    payload = {
        "schema": CURRENT_SHADOW_LEDGER_SCHEMA,
        "reviewed_files_digest": reviewed,
        "generation_digest": generation,
        "recorded_slots": [asdict(slot) for slot in slots],
        "abnormal_status_count": abnormal,
    }
    return _Ledger(
        schema=CURRENT_SHADOW_LEDGER_SCHEMA,
        reviewed_files_digest=reviewed,
        generation_digest=generation,
        recorded_slots=slots,
        abnormal_status_count=abnormal,
        ledger_digest=_digest(payload),
    )


def _valid_slot(slot: V4CurrentGenerationCompletedSlot) -> bool:
    return slot.slot_start_utc.tzinfo is not None and bool(
        _SHA256.fullmatch(slot.source_digest)
    )


def _result(
    status: V4CurrentGenerationShadowStatus,
    ledger: _Ledger,
    public_get_count: int,
) -> V4CurrentGenerationShadowResult:
    return V4CurrentGenerationShadowResult(
        status,
        len(ledger.recorded_slots),
        public_get_count,
    )


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    descriptor, temporary = tempfile.mkstemp(
        prefix=".current-shadow-artifact-",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as error:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_ARTIFACT_WRITE_FAILED"
        ) from error


def _create_once(path: Path, payload: dict[str, object]) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as error:
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_SEAL_MARKER_UNAVAILABLE"
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        raise V4CurrentGenerationShadowError(
            "CURRENT_SHADOW_SEAL_MARKER_UNAVAILABLE"
        ) from error


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
