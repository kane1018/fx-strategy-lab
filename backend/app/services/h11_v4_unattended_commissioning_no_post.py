"""Strict generation-bound commissioning artifacts with no live connection."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

COMMISSIONING_SCHEMA = "H11_V4_G019_COMMISSIONING_NO_POST_V1"
SHADOW_EVIDENCE_SCHEMA = "H11_V4_G019_SHADOW_EVIDENCE_NO_POST_V1"
EXPECTED_GENERATION_LABEL = "H11_AUTO_30M_20260728_G019"
EXPECTED_PRIOR_CANARY_GENERATION_LABEL = "H11_AUTO_30M_20260727_G018"
SHADOW_EVIDENCE_PRODUCER_IMPLEMENTED = False
_ZERO_DIGEST = "sha256:" + ("0" * 64)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class V4CommissioningStatus(str, Enum):
    READY_FOR_SEPARATE_LIVE_REVIEW = "READY_FOR_SEPARATE_LIVE_REVIEW"
    NOT_READY = "NOT_READY"


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
) -> V4ShadowEvidenceArtifact:
    payload = {
        "schema": SHADOW_EVIDENCE_SCHEMA,
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
    **fields: str | bool | int,
) -> V4CommissioningArtifact:
    """Build a canonical artifact; callers cannot supply their own digest."""

    payload = {"schema": COMMISSIONING_SCHEMA, **fields}
    return V4CommissioningArtifact(
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


def evaluate_commissioning(
    artifact: V4CommissioningArtifact,
    shadow: V4ShadowEvidenceArtifact,
) -> V4CommissioningDecision:
    """Require complete exact evidence but grant no live authority."""

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
        SHADOW_EVIDENCE_PRODUCER_IMPLEMENTED
        and _commissioning_artifact_is_canonical(artifact)
        and _shadow_artifact_is_canonical(shadow)
        and all(type(value) is bool for value in boolean_fields)
        and type(artifact.shadow_scheduler_cycles_clear) is int
        and type(shadow.abnormal_status_count) is int
        and type(shadow.actual_post_count) is int
        and artifact.schema == COMMISSIONING_SCHEMA
        and shadow.schema == SHADOW_EVIDENCE_SCHEMA
        and artifact.generation_label == EXPECTED_GENERATION_LABEL
        and artifact.prior_canary_generation_label
        == EXPECTED_PRIOR_CANARY_GENERATION_LABEL
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


def _shadow_artifact_is_canonical(
    artifact: V4ShadowEvidenceArtifact,
) -> bool:
    return artifact.artifact_digest == _artifact_digest(
        _payload_without_artifact_digest(artifact)
    )


def _payload_without_artifact_digest(
    artifact: V4CommissioningArtifact | V4ShadowEvidenceArtifact,
) -> dict[str, object]:
    payload = asdict(artifact)
    payload.pop("artifact_digest")
    return payload


def _artifact_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
