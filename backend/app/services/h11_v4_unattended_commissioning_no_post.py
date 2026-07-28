"""Strict generation-bound commissioning artifacts with no live connection."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

COMMISSIONING_SCHEMA = "H11_V4_G019_COMMISSIONING_NO_POST_V1"
SHADOW_EVIDENCE_SCHEMA = "H11_V4_G019_SHADOW_EVIDENCE_NO_POST_V1"
G020_COMMISSIONING_SCHEMA = "H11_V4_G020_COMMISSIONING_NO_POST_V1"
G020_SHADOW_EVIDENCE_SCHEMA = "H11_V4_G020_SHADOW_EVIDENCE_NO_POST_V1"
G020_PREDECESSOR_CANARY_COMPLETION_SCHEMA = (
    "H11_V4_G020_PREDECESSOR_CANARY_COMPLETION_NO_POST_V1"
)
_ZERO_DIGEST = "sha256:" + ("0" * 64)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_G018_GENERATION_LABEL = "H11_AUTO_30M_20260727_G018"
_G018_GENERATION_DIGEST = (
    "sha256:9a01ea35afe97b164562a3ad0255af854d9cd19da05d67662190785dec727ceb"
)
_RESTART_SAFE_EXIT_ACTUAL_IMPLEMENTED = False
_G020_LEGACY_PREDECESSOR_COMMISSIONING_SUPPORTED = False


@dataclass(frozen=True)
class _CommissioningContract:
    generation_label: str
    prior_canary_generation_label: str
    shadow_evidence_producer_implemented: bool


_COMMISSIONING_CONTRACTS = {
    (COMMISSIONING_SCHEMA, SHADOW_EVIDENCE_SCHEMA): _CommissioningContract(
        generation_label="H11_AUTO_30M_20260728_G019",
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        shadow_evidence_producer_implemented=False,
    ),
    (G020_COMMISSIONING_SCHEMA, G020_SHADOW_EVIDENCE_SCHEMA): _CommissioningContract(
        generation_label="H11_AUTO_30M_20260728_G020",
        prior_canary_generation_label="H11_AUTO_30M_20260727_G018",
        shadow_evidence_producer_implemented=True,
    ),
}


class V4CommissioningStatus(str, Enum):
    READY_FOR_SEPARATE_LIVE_REVIEW = "READY_FOR_SEPARATE_LIVE_REVIEW"
    NOT_READY = "NOT_READY"


class V4PredecessorCanaryCompletionError(ValueError):
    """Fixed safe failure for invalid local predecessor completion evidence."""


@dataclass(frozen=True)
class V4ShadowEvidenceArtifact:
    schema: str
    artifact_digest: str
    reviewed_files_digest: str
    generation_digest: str
    completed_slot_digests: tuple[str, ...]
    abnormal_status_count: int
    broker_write: bool
    actual_post_count: int


@dataclass(frozen=True)
class V4CommissioningArtifact:
    schema: str
    artifact_digest: str
    generation_label: str
    prior_canary_generation_label: str
    prior_canary_generation_digest: str
    prior_canary_reconciliation_artifact_digest: str
    prior_canary_handoff_digest: str
    commissioning_entry_disabled: bool
    reviewed_files_digest: str
    generation_digest: str
    shadow_evidence_digest: str
    shadow_reviewed_files_digest: str
    shadow_generation_digest: str
    shadow_scheduler_cycles_clear: int
    prior_canary_cycle_complete: bool
    prior_canary_flat_reconciled: bool
    account_wide_active_orders_zero_evidence: bool
    restart_safe_exit_contract_clear: bool
    notification_contract_clear: bool
    architecture_review_clear: bool
    safety_review_clear: bool
    operations_review_clear: bool


@dataclass(frozen=True)
class V4PredecessorCanaryCompletionArtifact:
    """Sanitized, canonical G018 completion proof for no-POST commissioning."""

    schema: str
    artifact_digest: str
    prior_canary_generation_label: str
    prior_canary_generation_digest: str
    coordinator_ledger_digest: str
    coordinator_cycle_count: int
    market_entry_attempt_count: int
    exact_size_oco_protection_attempt_count: int
    entry_fill_recorded: bool
    protection_plan_recorded: bool
    protection_confirmed: bool
    reconciliation_runtime_generation_digest: str
    reconciliation_started_marker_digest: str
    reconciliation_passed_marker_digest: str
    reconciliation_origin_generation_digest: str
    reconciliation_status: str
    commissioning_eligible: bool
    reconciliation_result_known: bool
    subject_entry_observed: bool
    account_flat: bool
    active_orders_zero: bool
    broker_read_count: int
    broker_write_attempt_count: int
    raw_response_retained: bool
    identifier_exposed: bool


@dataclass(frozen=True)
class V4CommissioningDecision:
    status: V4CommissioningStatus
    separate_live_review_required: bool
    persistent_arm_change_allowed: bool
    broker_post_authorized: bool = False
    broker_write: bool = False
    actual_post_count: int = 0

    def __bool__(self) -> bool:
        """A commissioning result is evidence, never a transport allow value."""

        return False


def build_shadow_evidence_artifact(
    *,
    reviewed_files_digest: str,
    generation_digest: str,
    completed_slot_digests: tuple[str, ...],
    abnormal_status_count: int,
    broker_write: bool,
    actual_post_count: int,
    schema: str = SHADOW_EVIDENCE_SCHEMA,
) -> V4ShadowEvidenceArtifact:
    payload = {
        "schema": schema,
        "reviewed_files_digest": reviewed_files_digest,
        "generation_digest": generation_digest,
        "completed_slot_digests": completed_slot_digests,
        "abnormal_status_count": abnormal_status_count,
        "broker_write": broker_write,
        "actual_post_count": actual_post_count,
    }
    return V4ShadowEvidenceArtifact(
        artifact_digest=_artifact_digest(payload),
        **payload,
    )


def build_commissioning_artifact(
    *,
    schema: str = COMMISSIONING_SCHEMA,
    **fields: str | bool | int,
) -> V4CommissioningArtifact:
    """Build a canonical artifact; callers cannot supply their own digest."""

    payload = {"schema": schema, **fields}
    return V4CommissioningArtifact(
        artifact_digest=_artifact_digest(payload),
        **payload,
    )


def build_predecessor_canary_completion_artifact(
    **fields: str | bool | int,
) -> V4PredecessorCanaryCompletionArtifact:
    """Build canonical predecessor evidence; caller cannot supply its digest."""

    payload = {"schema": G020_PREDECESSOR_CANARY_COMPLETION_SCHEMA, **fields}
    return V4PredecessorCanaryCompletionArtifact(
        artifact_digest=_artifact_digest(payload),
        **payload,
    )


def load_shadow_evidence_artifact(path: Path) -> V4ShadowEvidenceArtifact:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        slot_digests = payload.get("completed_slot_digests")
        if not isinstance(slot_digests, list):
            raise TypeError
        payload["completed_slot_digests"] = tuple(slot_digests)
        artifact = V4ShadowEvidenceArtifact(**payload)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("V4_SHADOW_EVIDENCE_ARTIFACT_INVALID") from error
    if not _shadow_artifact_is_canonical(artifact):
        raise ValueError("V4_SHADOW_EVIDENCE_ARTIFACT_DIGEST_MISMATCH")
    return artifact


def load_commissioning_artifact(path: Path) -> V4CommissioningArtifact:
    """Load an exact-schema artifact without accepting extra fields."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = V4CommissioningArtifact(**payload)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise ValueError("V4_COMMISSIONING_ARTIFACT_INVALID") from error
    if not _commissioning_artifact_is_canonical(artifact):
        raise ValueError("V4_COMMISSIONING_ARTIFACT_DIGEST_MISMATCH")
    return artifact


def load_predecessor_canary_completion_artifact(
    path: Path,
) -> V4PredecessorCanaryCompletionArtifact:
    """Load exact, canonical, sanitized predecessor completion evidence."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifact = V4PredecessorCanaryCompletionArtifact(**payload)
    except (OSError, json.JSONDecodeError, TypeError) as error:
        raise V4PredecessorCanaryCompletionError(
            "V4_PREDECESSOR_COMPLETION_ARTIFACT_INVALID"
        ) from error
    if not _predecessor_completion_is_valid(artifact):
        raise V4PredecessorCanaryCompletionError(
            "V4_PREDECESSOR_COMPLETION_ARTIFACT_INVALID"
        )
    return artifact


def bind_g018_predecessor_canary_completion(
    *, repository: Path
) -> V4PredecessorCanaryCompletionArtifact:
    """Bind one G018 local ledger and one matching reconciliation pair.

    This reads local durable files only. It never opens a credential, sends a
    request, or returns an identifier, price, payload, or raw broker response.
    """

    runtime_root = repository.resolve() / "backend/market_data/h11_v4_gmo_actual_runtime"
    origin_root = runtime_root / f"generation-{_G018_GENERATION_DIGEST.removeprefix('sha256:')}"
    ledger = origin_root / "coordinator.sqlite3"
    if not ledger.is_file() or ledger.is_symlink():
        raise V4PredecessorCanaryCompletionError("V4_PREDECESSOR_LEDGER_INVALID")
    ledger_summary = _read_g018_ledger_summary(ledger)
    candidate = _find_g018_reconciliation_pair(runtime_root)
    return build_predecessor_canary_completion_artifact(
        prior_canary_generation_label=_G018_GENERATION_LABEL,
        prior_canary_generation_digest=_G018_GENERATION_DIGEST,
        coordinator_ledger_digest=_file_digest(ledger),
        **ledger_summary,
        **candidate,
        commissioning_eligible=False,
    )


def evaluate_commissioning(
    artifact: V4CommissioningArtifact,
    shadow: V4ShadowEvidenceArtifact,
    predecessor: V4PredecessorCanaryCompletionArtifact | None = None,
) -> V4CommissioningDecision:
    """Require complete exact evidence but grant no live authority."""

    contract = _COMMISSIONING_CONTRACTS.get((artifact.schema, shadow.schema))
    boolean_fields = (
        artifact.commissioning_entry_disabled,
        artifact.prior_canary_cycle_complete,
        artifact.prior_canary_flat_reconciled,
        artifact.account_wide_active_orders_zero_evidence,
        artifact.restart_safe_exit_contract_clear,
        artifact.notification_contract_clear,
        artifact.architecture_review_clear,
        artifact.safety_review_clear,
        artifact.operations_review_clear,
        shadow.broker_write,
    )
    slot_digests = shadow.completed_slot_digests
    ready = (
        contract is not None
        and contract.shadow_evidence_producer_implemented
        and _commissioning_artifact_is_canonical(artifact)
        and _shadow_artifact_is_canonical(shadow)
        and all(type(value) is bool for value in boolean_fields)
        and type(artifact.shadow_scheduler_cycles_clear) is int
        and type(shadow.abnormal_status_count) is int
        and type(shadow.actual_post_count) is int
        and artifact.generation_label == contract.generation_label
        and artifact.prior_canary_generation_label
        == contract.prior_canary_generation_label
        and bool(_SHA256.fullmatch(artifact.prior_canary_generation_digest))
        and bool(
            _SHA256.fullmatch(
                artifact.prior_canary_reconciliation_artifact_digest
            )
        )
        and bool(_SHA256.fullmatch(artifact.prior_canary_handoff_digest))
        and artifact.prior_canary_generation_digest != _ZERO_DIGEST
        and artifact.prior_canary_reconciliation_artifact_digest
        != _ZERO_DIGEST
        and artifact.prior_canary_handoff_digest != _ZERO_DIGEST
        and _commissioning_binds_historical_predecessor(artifact, predecessor)
        and _G020_LEGACY_PREDECESSOR_COMMISSIONING_SUPPORTED is True
        and artifact.commissioning_entry_disabled is True
        and bool(_SHA256.fullmatch(artifact.reviewed_files_digest))
        and bool(_SHA256.fullmatch(artifact.generation_digest))
        and artifact.shadow_evidence_digest == shadow.artifact_digest
        and artifact.shadow_reviewed_files_digest
        == artifact.reviewed_files_digest
        == shadow.reviewed_files_digest
        and artifact.shadow_generation_digest
        == artifact.generation_digest
        == shadow.generation_digest
        and artifact.shadow_scheduler_cycles_clear == len(slot_digests)
        and len(slot_digests) >= 20
        and len(set(slot_digests)) == len(slot_digests)
        and all(_SHA256.fullmatch(value) for value in slot_digests)
        and shadow.abnormal_status_count == 0
        and shadow.broker_write is False
        and shadow.actual_post_count == 0
        and artifact.prior_canary_cycle_complete is True
        and artifact.prior_canary_flat_reconciled is True
        and artifact.account_wide_active_orders_zero_evidence is True
        and artifact.restart_safe_exit_contract_clear is True
        and _RESTART_SAFE_EXIT_ACTUAL_IMPLEMENTED is True
        and artifact.notification_contract_clear is True
        and artifact.architecture_review_clear is True
        and artifact.safety_review_clear is True
        and artifact.operations_review_clear is True
    )
    return V4CommissioningDecision(
        status=(
            V4CommissioningStatus.READY_FOR_SEPARATE_LIVE_REVIEW
            if ready
            else V4CommissioningStatus.NOT_READY
        ),
        separate_live_review_required=True,
        persistent_arm_change_allowed=False,
    )


def _commissioning_artifact_is_canonical(
    artifact: V4CommissioningArtifact,
) -> bool:
    return artifact.artifact_digest == _artifact_digest(
        _payload_without_artifact_digest(artifact)
    )


def _predecessor_completion_is_valid(
    artifact: V4PredecessorCanaryCompletionArtifact,
) -> bool:
    return (
        artifact.schema == G020_PREDECESSOR_CANARY_COMPLETION_SCHEMA
        and artifact.artifact_digest == _artifact_digest(_payload_without_artifact_digest(artifact))
        and artifact.prior_canary_generation_label == _G018_GENERATION_LABEL
        and artifact.prior_canary_generation_digest == _G018_GENERATION_DIGEST
        and all(
            _SHA256.fullmatch(value)
            for value in (
                artifact.coordinator_ledger_digest,
                artifact.reconciliation_runtime_generation_digest,
                artifact.reconciliation_started_marker_digest,
                artifact.reconciliation_passed_marker_digest,
                artifact.reconciliation_origin_generation_digest,
            )
        )
        and artifact.coordinator_cycle_count == 1
        and artifact.market_entry_attempt_count == 1
        and artifact.exact_size_oco_protection_attempt_count == 1
        and artifact.entry_fill_recorded is True
        and artifact.protection_plan_recorded is True
        and artifact.protection_confirmed is True
        and artifact.reconciliation_origin_generation_digest == _G018_GENERATION_DIGEST
        and artifact.reconciliation_status == "G013_POST_CANARY_FLAT_CONFIRMED"
        and artifact.commissioning_eligible is False
        and artifact.reconciliation_result_known is True
        and artifact.subject_entry_observed is True
        and artifact.account_flat is True
        and artifact.active_orders_zero is True
        and artifact.broker_read_count == 3
        and artifact.broker_write_attempt_count == 0
        and artifact.raw_response_retained is False
        and artifact.identifier_exposed is False
    )


def _commissioning_binds_historical_predecessor(
    artifact: V4CommissioningArtifact,
    predecessor: V4PredecessorCanaryCompletionArtifact | None,
) -> bool:
    return (
        predecessor is not None
        and _predecessor_completion_is_valid(predecessor)
        and predecessor.commissioning_eligible is False
        and artifact.prior_canary_generation_label
        == predecessor.prior_canary_generation_label
        and artifact.prior_canary_generation_digest
        == predecessor.prior_canary_generation_digest
        and artifact.prior_canary_reconciliation_artifact_digest
        == predecessor.reconciliation_passed_marker_digest
        and artifact.prior_canary_handoff_digest == predecessor.artifact_digest
        and artifact.prior_canary_cycle_complete is True
        and artifact.prior_canary_flat_reconciled is predecessor.account_flat
        and artifact.account_wide_active_orders_zero_evidence
        is predecessor.active_orders_zero
    )


def _shadow_artifact_is_canonical(
    artifact: V4ShadowEvidenceArtifact,
) -> bool:
    return artifact.artifact_digest == _artifact_digest(
        _payload_without_artifact_digest(artifact)
    )


def _payload_without_artifact_digest(
    artifact: (
        V4CommissioningArtifact
        | V4ShadowEvidenceArtifact
        | V4PredecessorCanaryCompletionArtifact
    ),
) -> dict[str, object]:
    payload = asdict(artifact)
    payload.pop("artifact_digest")
    return payload


def _read_g018_ledger_summary(ledger: Path) -> dict[str, int | bool]:
    try:
        connection = sqlite3.connect(
            ledger.resolve().as_uri() + "?mode=ro", uri=True
        )
    except sqlite3.Error as error:
        raise V4PredecessorCanaryCompletionError(
            "V4_PREDECESSOR_LEDGER_INVALID"
        ) from error
    try:
        cycle = connection.execute(
            """
            SELECT COUNT(*),
                   SUM(entry_average_fill_price IS NOT NULL),
                   SUM(protection_plan_digest IS NOT NULL),
                   SUM(protection_confirmed_at_utc IS NOT NULL)
            FROM cycles
            """
        ).fetchone()
        attempts = connection.execute(
            """
            SELECT SUM(action = 'MARKET_ENTRY'),
                   SUM(action = 'EXACT_SIZE_OCO_PROTECTION')
            FROM attempts
            """
        ).fetchone()
    except sqlite3.Error as error:
        raise V4PredecessorCanaryCompletionError(
            "V4_PREDECESSOR_LEDGER_INVALID"
        ) from error
    finally:
        connection.close()
    if cycle is None or attempts is None:
        raise V4PredecessorCanaryCompletionError("V4_PREDECESSOR_LEDGER_INVALID")
    return {
        "coordinator_cycle_count": _required_int(cycle[0]),
        "entry_fill_recorded": _required_int(cycle[1]) == 1,
        "protection_plan_recorded": _required_int(cycle[2]) == 1,
        "protection_confirmed": _required_int(cycle[3]) == 1,
        "market_entry_attempt_count": _required_int(attempts[0]),
        "exact_size_oco_protection_attempt_count": _required_int(attempts[1]),
    }


def _find_g018_reconciliation_pair(runtime_root: Path) -> dict[str, str | bool | int]:
    candidates: list[dict[str, str | bool | int]] = []
    for started in runtime_root.glob("generation-*/post-canary-reconciliation.started.json"):
        passed = started.with_name("post-canary-reconciliation.passed.json")
        if (
            started.is_symlink()
            or passed.is_symlink()
            or not started.is_file()
            or not passed.is_file()
        ):
            continue
        try:
            started_payload = json.loads(started.read_text(encoding="utf-8"))
            passed_payload = json.loads(passed.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            started_payload.get("schema")
            != "H11_V4_G013_POST_CANARY_RECONCILIATION_V1"
            or started_payload.get("origin_generation_digest")
            != _G018_GENERATION_DIGEST
            or started_payload.get("target_generation_digest")
            != "sha256:" + started.parent.name.removeprefix("generation-")
            or started_payload.get("broker_write_attempt_count") != 0
            or passed_payload.get("schema")
            != "H11_V4_G013_POST_CANARY_RECONCILIATION_V1"
            or passed_payload.get("origin_generation_digest")
            != _G018_GENERATION_DIGEST
            or passed_payload.get("started_marker_digest") != _file_digest(started)
            or passed_payload.get("target_generation_digest")
            != "sha256:" + started.parent.name.removeprefix("generation-")
            or passed_payload.get("status") != "G013_POST_CANARY_FLAT_CONFIRMED"
            or passed_payload.get("result_known") is not True
            or passed_payload.get("subject_entry_observed") is not True
            or passed_payload.get("account_flat") is not True
            or passed_payload.get("active_orders_zero") is not True
            or passed_payload.get("broker_read_count") != 3
            or passed_payload.get("broker_write_attempt_count") != 0
            or passed_payload.get("raw_response_retained") is not False
            or passed_payload.get("identifier_exposed") is not False
        ):
            continue
        runtime_digest = "sha256:" + started.parent.name.removeprefix("generation-")
        if not _SHA256.fullmatch(runtime_digest):
            continue
        candidates.append(
            {
                "reconciliation_runtime_generation_digest": runtime_digest,
                "reconciliation_started_marker_digest": _file_digest(started),
                "reconciliation_passed_marker_digest": _file_digest(passed),
                "reconciliation_origin_generation_digest": _G018_GENERATION_DIGEST,
                "reconciliation_status": "G013_POST_CANARY_FLAT_CONFIRMED",
                "reconciliation_result_known": True,
                "subject_entry_observed": True,
                "account_flat": True,
                "active_orders_zero": True,
                "broker_read_count": 3,
                "broker_write_attempt_count": 0,
                "raw_response_retained": False,
                "identifier_exposed": False,
            }
        )
    if len(candidates) != 1:
        raise V4PredecessorCanaryCompletionError(
            "V4_PREDECESSOR_RECONCILIATION_UNBOUND_OR_AMBIGUOUS"
        )
    return candidates[0]


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _required_int(value: object) -> int:
    if type(value) is not int:
        raise V4PredecessorCanaryCompletionError("V4_PREDECESSOR_LEDGER_INVALID")
    return value


def _artifact_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
