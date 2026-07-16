"""Fail-closed local guards for finite H-11 v4 activation preparation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.h11_auto.v4_gmo_generation import load_v4_gmo_frozen_generation


class V4ActualPreparationGuardError(RuntimeError):
    """Fixed safe preparation guard failure."""


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
KeychainValueRunner = Callable[[list[str], float], subprocess.CompletedProcess[str]]
MonotonicClock = Callable[[], float]

PREPARATION_ARTIFACT = Path(
    "docs/templates/h11_v4_actual_preparation_evidence.json"
)
PREPARATION_STATE_RELATIVE = Path(
    "backend/market_data/h11_v4_actual_preparation"
)
_REVIEWED_FILES = (
    "AGENTS.md",
    "backend/requirements.txt",
    "backend/app/h11_auto/v4_actual_preparation_guard.py",
    "backend/app/h11_auto/v4_actual_host_kill_rehearsal.py",
    "backend/app/h11_auto/contracts.py",
    "backend/app/h11_auto/v4_activation_preparation.py",
    "backend/app/h11_auto/v4_gmo_actual_coordinator.py",
    "backend/app/h11_auto/v4_gmo_contracts.py",
    "backend/app/h11_auto/v4_gmo_engine.py",
    "backend/app/h11_auto/v4_gmo_generation.py",
    "backend/app/h11_auto/v4_gmo_persisted_authorization.py",
    "backend/app/h11_auto/v4_gmo_persistence.py",
    "backend/app/h11_auto/v4_gmo_protection.py",
    "backend/app/h11_auto/v4_gmo_runtime.py",
    "backend/app/h11_auto/runtime_safety.py",
    "backend/app/private_api/auth.py",
    "backend/app/security/real_broker_post_hard_guard.py",
    "backend/app/services/h11_v4_gmo_actual_adapter.py",
    "backend/app/services/h11_v4_gmo_coordinated_actual_path.py",
    "backend/app/services/h11_v4_gmo_public_market_status.py",
    "backend/app/services/h11_v4_gmo_actual_transport.py",
    "backend/app/services/h11_v4_notification_binding_no_post.py",
    "backend/app/services/h11_v4_notification_actual_preparation.py",
    "backend/app/services/h11_v4_gmo_readonly_preflight.py",
    "backend/scripts/h11_auto_v4_actual_preparation_presence.py",
    "backend/scripts/h11_auto_v4_keychain_access_rehearsal.py",
    "backend/scripts/h11_auto_v4_pushover_rehearsal.py",
    "backend/scripts/h11_auto_v4_smtp_rehearsal.py",
    "backend/scripts/h11_auto_v4_actual_host_kill_rehearsal.py",
    "backend/scripts/h11_auto_v4_coordinator_kill_probe.py",
    "backend/scripts/h11_auto_v4_email_delivery_confirm.py",
    "backend/scripts/h11_auto_v4_exclusivity_confirm.py",
    "backend/scripts/h11_auto_v4_private_get_preflight.py",
    "backend/app/tests/h11_auto/test_v4_actual_preparation_fake_first.py",
    "backend/app/tests/h11_auto/test_v4_gmo_actual_coordinator_precanary.py",
    "backend/app/tests/h11_auto/test_v4_gmo_actual_adapter_fake_only.py",
    "backend/app/tests/h11_auto/test_v4_gmo_relaxed_no_post.py",
    "backend/app/tests/h11_auto/test_v4_notification_binding_fake_only.py",
    "backend/app/tests/test_h11_stage1_paper_wiring_no_post.py",
    "backend/app/tests/test_h11_v3_runtime_safety_no_post.py",
    "docs/H11_V4_ACTUAL_ACTIVATION_PREPARATION_REPORT_20260716.md",
    "docs/H11_AUTO_OPERATOR_DECISION_SHEET_NO_POST_20260715.md",
    "docs/H11_V4_MAJOR_INCIDENT_RESUME_DECLARATION_DRAFT_NO_POST_20260715.md",
    "docs/H11_AUTO_FROZEN_GENERATION_MANIFEST_TEMPLATE_NO_POST_20260715.md",
    "docs/OPERATOR_V4_EDGE_IMPLEMENTATION_PROPOSAL_NO_POST_20260716.md",
)
_GATE_TOKEN = object()
_PERMIT_TOKEN = object()
_COMPLETED_EVIDENCE_TOKEN = object()
EMAIL_DELIVERY_CONFIRMATION = "I CONFIRM THE H11 V4 TEST EMAIL WAS RECEIVED"
EXCLUSIVITY_CONFIRMATION = (
    "I CONFIRM H11 V4 MANUAL UI AND ALL OTHER PRIVATE CLIENTS ARE STOPPED"
)


def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10.0,
        check=False,
    )


def _default_keychain_value_runner(
    command: list[str], timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


@dataclass(frozen=True)
class V4PreparationGitGate:
    working_tree_clean: bool
    head_matches_origin_main: bool
    branch_main: bool
    clear: bool

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4KeychainPresenceReport:
    total_required: int
    present_count: int
    all_present: bool
    values_read: bool = False
    credential_value_exposed: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4KeychainAccessReport:
    total_required: int
    accessible_count: int
    all_accessible: bool
    values_read_internal: bool = True
    credential_value_exposed: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


@dataclass(frozen=True)
class V4OperatorConfirmationReport:
    confirmation_kind: str
    exact_match: bool
    broker_post_authorized: bool = False
    activation_permit_issued: bool = False

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)

    def __bool__(self) -> bool:
        return False


class V4ExternalPreparationGate:
    """Opaque reviewed gate for external preparation only, never broker POST."""

    def __init__(
        self,
        *,
        token: object,
        reviewed_files_digest: str,
        state_root: Path,
    ) -> None:
        if (
            token is not _GATE_TOKEN
            or not reviewed_files_digest.startswith("sha256:")
            or not state_root.is_absolute()
        ):
            raise V4ActualPreparationGuardError("PREPARATION_EXTERNAL_GATE_INVALID")
        self._reviewed_files_digest = reviewed_files_digest
        self._token = token
        self._state_root = state_root

    def state_root_for_internal_preparation_only(self) -> Path:
        return self._state_root

    def reviewed_digest_for_internal_preparation_only(self) -> str:
        return self._reviewed_files_digest

    def __repr__(self) -> str:
        return "V4ExternalPreparationGate(scope=external-preparation-only)"

    def __bool__(self) -> bool:
        return False


def require_external_preparation_gate(
    gate: V4ExternalPreparationGate,
) -> V4ExternalPreparationGate:
    """Reject direct calls that did not pass the reviewed artifact loader."""

    if (
        not isinstance(gate, V4ExternalPreparationGate)
        or getattr(gate, "_token", None) is not _GATE_TOKEN
        or not getattr(gate, "_reviewed_files_digest", "").startswith("sha256:")
        or not getattr(gate, "_state_root", Path()).is_absolute()
    ):
        raise V4ActualPreparationGuardError("PREPARATION_EXTERNAL_GATE_INVALID")
    return gate


class V4CompletedPreparationEvidence:
    """One-use proof that the exact reviewed preparation sequence passed."""

    __slots__ = (
        "_token",
        "_generation_digest",
        "_state_root",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        generation_digest: str,
        state_root: Path,
    ) -> None:
        if (
            token is not _COMPLETED_EVIDENCE_TOKEN
            or not _valid_completion_digest(generation_digest)
            or not state_root.is_absolute()
            or state_root.is_symlink()
            or not state_root.is_dir()
            or not state_root.name.endswith(
                generation_digest.removeprefix("sha256:")
            )
        ):
            raise V4ActualPreparationGuardError(
                "PREPARATION_COMPLETED_EVIDENCE_INVALID"
            )
        self._token = token
        self._generation_digest = generation_digest
        self._state_root = state_root
        self._consumed = False

    def consume_for_generation(self, generation_digest: str) -> None:
        if (
            self._token is not _COMPLETED_EVIDENCE_TOKEN
            or self._consumed
            or self._generation_digest != generation_digest
        ):
            raise V4ActualPreparationGuardError(
                "PREPARATION_COMPLETED_EVIDENCE_INVALID"
            )
        marker = self._state_root / "generation_consumed.json"
        payload = json.dumps(
            {
                "generation_digest": self._generation_digest,
                "status": "CONSUMED_FOR_CANARY_PREFLIGHT",
            },
            sort_keys=True,
        )
        try:
            descriptor = os.open(
                marker,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            directory_descriptor = os.open(self._state_root, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except FileExistsError as error:
            raise V4ActualPreparationGuardError(
                "PREPARATION_COMPLETED_EVIDENCE_INVALID"
            ) from error
        except OSError as error:
            raise V4ActualPreparationGuardError(
                "PREPARATION_COMPLETED_EVIDENCE_NOT_PERSISTED"
            ) from error
        self._consumed = True

    def __repr__(self) -> str:
        return "V4CompletedPreparationEvidence(<redacted-one-use>)"

    def __bool__(self) -> bool:
        return False


class V4PreparationOperation(str, Enum):
    PRESENCE = "00_presence"
    KEYCHAIN_ACCESS = "05_keychain_access"
    PUSHOVER = "10_pushover"
    SMTP = "15_smtp"
    EMAIL_CONFIRMATION = "20_email_confirmation"
    HOST_KILL = "30_host_kill"
    EXCLUSIVITY_CONFIRMATION = "40_exclusivity_confirmation"
    PRIVATE_GET = "50_private_get"


_PREVIOUS_OPERATION = {
    V4PreparationOperation.PRESENCE: None,
    V4PreparationOperation.KEYCHAIN_ACCESS: V4PreparationOperation.PRESENCE,
    V4PreparationOperation.PUSHOVER: V4PreparationOperation.KEYCHAIN_ACCESS,
    V4PreparationOperation.SMTP: V4PreparationOperation.PUSHOVER,
    V4PreparationOperation.EMAIL_CONFIRMATION: V4PreparationOperation.SMTP,
    V4PreparationOperation.HOST_KILL: V4PreparationOperation.EMAIL_CONFIRMATION,
    V4PreparationOperation.EXCLUSIVITY_CONFIRMATION: V4PreparationOperation.HOST_KILL,
    V4PreparationOperation.PRIVATE_GET: V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
}


class V4PreparationOperationPermit:
    """Single-process companion to one persisted, externally performed step."""

    __slots__ = (
        "_token",
        "_operation",
        "_claimed",
        "_completion_digest",
        "_completion_report",
        "_reviewed_files_digest",
        "_generation_digest",
    )

    def __init__(
        self,
        *,
        token: object,
        operation: V4PreparationOperation,
        reviewed_files_digest: str,
        generation_digest: str,
    ) -> None:
        if token is not _PERMIT_TOKEN:
            raise V4ActualPreparationGuardError("PREPARATION_OPERATION_PERMIT_INVALID")
        self._token = token
        self._operation = operation
        self._claimed = False
        self._completion_digest: str | None = None
        self._completion_report: dict[str, object] | None = None
        self._reviewed_files_digest = reviewed_files_digest
        self._generation_digest = generation_digest

    def __repr__(self) -> str:
        return "V4PreparationOperationPermit(<redacted>)"

    def __bool__(self) -> bool:
        return False


def require_operation_permit(
    permit: object,
    *,
    expected_operation: V4PreparationOperation,
    claim: bool = False,
    require_completed: bool = False,
) -> V4PreparationOperationPermit:
    """Accept only an opaque permit minted by the fixed preparation ledger."""

    if claim and require_completed:
        raise V4ActualPreparationGuardError("PREPARATION_OPERATION_PERMIT_INVALID")
    if (
        type(permit) is not V4PreparationOperationPermit
        or getattr(permit, "_token", None) is not _PERMIT_TOKEN
        or getattr(permit, "_operation", None) is not expected_operation
        or not isinstance(getattr(permit, "_claimed", None), bool)
        or (require_completed and not _valid_completion_digest(permit._completion_digest))
        or (not require_completed and permit._completion_digest is not None)
    ):
        raise V4ActualPreparationGuardError("PREPARATION_OPERATION_PERMIT_INVALID")
    if claim:
        if permit._claimed:
            raise V4ActualPreparationGuardError(
                "PREPARATION_OPERATION_PERMIT_INVALID"
            )
        permit._claimed = True
    return permit


def _valid_completion_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _bind_fixed_operation_attestation(
    operation_permit: V4PreparationOperationPermit,
    *,
    operation: V4PreparationOperation,
    safe_report: dict[str, object],
    issuer_token: object,
) -> None:
    """Bind completion to a successful operation-specific sanitized report."""

    require_operation_permit(
        operation_permit,
        expected_operation=operation,
    )
    if (
        issuer_token is not _OPERATION_ATTESTATION_ISSUERS[operation]
        or not operation_permit._claimed
        or not _operation_report_is_clear(operation, safe_report)
    ):
        raise V4ActualPreparationGuardError(
            "PREPARATION_OPERATION_SUCCESS_PROOF_INVALID"
        )
    operation_permit._completion_report = json.loads(
        json.dumps(safe_report, sort_keys=True)
    )
    operation_permit._completion_digest = _completion_digest(
        operation=operation,
        safe_report=operation_permit._completion_report,
        reviewed_files_digest=operation_permit._reviewed_files_digest,
        generation_digest=operation_permit._generation_digest,
    )


_OPERATION_ATTESTATION_ISSUERS = {
    operation: object() for operation in V4PreparationOperation
}


def _attest_operation_success(
    operation_permit: V4PreparationOperationPermit,
    *,
    operation: V4PreparationOperation,
    safe_report: dict[str, object],
) -> None:
    """Operation-specific completion entrypoint used only by fixed step code."""

    _bind_fixed_operation_attestation(
        operation_permit,
        operation=operation,
        safe_report=safe_report,
        issuer_token=_OPERATION_ATTESTATION_ISSUERS[operation],
    )


def _attest_presence_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.PRESENCE, safe_report=safe_report
    )


def _attest_keychain_access_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit,
        operation=V4PreparationOperation.KEYCHAIN_ACCESS,
        safe_report=safe_report,
    )


def _attest_pushover_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.PUSHOVER, safe_report=safe_report
    )


def _attest_smtp_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.SMTP, safe_report=safe_report
    )


def _attest_email_confirmation_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit,
        operation=V4PreparationOperation.EMAIL_CONFIRMATION,
        safe_report=safe_report,
    )


def _attest_host_kill_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.HOST_KILL, safe_report=safe_report
    )


def _attest_exclusivity_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit,
        operation=V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
        safe_report=safe_report,
    )


def _attest_private_get_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.PRIVATE_GET, safe_report=safe_report
    )


def _completion_digest(
    *,
    operation: V4PreparationOperation,
    safe_report: dict[str, object],
    reviewed_files_digest: str,
    generation_digest: str,
) -> str:
    canonical = json.dumps(
        {
            "generation_digest": generation_digest,
            "operation": operation.value,
            "report": safe_report,
            "reviewed_files_digest": reviewed_files_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _operation_report_is_clear(
    operation: V4PreparationOperation,
    report: dict[str, object],
) -> bool:
    if operation is V4PreparationOperation.PRESENCE:
        return (
            report.get("total_required") == 6
            and report.get("present_count") == 6
            and report.get("all_present") is True
            and report.get("values_read") is False
        )
    if operation is V4PreparationOperation.KEYCHAIN_ACCESS:
        return (
            report.get("total_required") == 6
            and report.get("accessible_count") == 6
            and report.get("all_accessible") is True
            and report.get("credential_value_exposed") is False
        )
    if operation is V4PreparationOperation.PUSHOVER:
        return (
            report.get("pushover_application_send_count") == 1
            and report.get("pushover_accepted") is True
            and report.get("pushover_acknowledged") is True
            and report.get("broker_post_count") == 0
        )
    if operation is V4PreparationOperation.SMTP:
        return (
            report.get("email_send_count") == 1
            and report.get("email_smtp_accepted") is True
            and report.get("broker_post_count") == 0
        )
    if operation in {
        V4PreparationOperation.EMAIL_CONFIRMATION,
        V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
    }:
        return (
            report.get("exact_match") is True
            and report.get("broker_post_authorized") is False
            and report.get("activation_permit_issued") is False
        )
    if operation is V4PreparationOperation.HOST_KILL:
        return (
            str(report.get("status", "")).startswith("PASSED_")
            and report.get("disposable_coordinator_process_killed") is True
            and report.get("coordinator_pending_marker_restart_halt_observed") is True
            and report.get("persistent_kill_latched") is True
            and report.get("entry_blocked_after_reload") is True
            and report.get("broker_post_count") == 0
        )
    if operation is V4PreparationOperation.PRIVATE_GET:
        offsets = report.get("cadence_offsets_seconds")
        return (
            report.get("broker_get_count") == 3
            and report.get("limited_usd_jpy_snapshot_clear") is True
            and report.get("usd_jpy_flat") is True
            and report.get("usd_jpy_active_orders_zero") is True
            and isinstance(offsets, tuple | list)
            and len(offsets) == 3
            and all(isinstance(value, int | float) for value in offsets)
            and float(offsets[1]) - float(offsets[0]) + 1e-9 >= 0.25
            and float(offsets[2]) - float(offsets[1]) + 1e-9 >= 0.25
            and report.get("broker_post_count") == 0
            and report.get("broker_write_performed") is False
        )
    return False


class V4PreparationAttemptLedger:
    """Persistent no-reset sequence; attempt is written before external I/O."""

    def __init__(self, *, external_gate: V4ExternalPreparationGate) -> None:
        require_external_preparation_gate(external_gate)
        unresolved = external_gate.state_root_for_internal_preparation_only()
        path_candidates = (
            unresolved,
            unresolved.parent,
            unresolved.parent.parent,
            unresolved.parent.parent.parent,
        )
        if any(candidate.is_symlink() for candidate in path_candidates):
            raise V4ActualPreparationGuardError("PREPARATION_STATE_SYMLINK_FORBIDDEN")
        self.state_root = unresolved.resolve()
        self._reviewed_files_digest = (
            external_gate.reviewed_digest_for_internal_preparation_only()
        )
        self._generation_digest = "sha256:" + self.state_root.name.rsplit("-", 1)[-1]
        self.state_root.mkdir(parents=True, exist_ok=True)

    def begin(
        self,
        operation: V4PreparationOperation,
    ) -> V4PreparationOperationPermit:
        previous = _PREVIOUS_OPERATION[operation]
        if previous is not None and not self._marker_matches_review(
            self._marker(previous, "passed"),
            operation=previous,
            expected_status="PASSED",
        ):
            raise V4ActualPreparationGuardError("PREPARATION_SEQUENCE_PREVIOUS_NOT_CLEAR")
        started = self._marker(operation, "started")
        passed = self._marker(operation, "passed")
        if started.exists() or passed.exists():
            raise V4ActualPreparationGuardError("PREPARATION_OPERATION_ALREADY_ATTEMPTED")
        try:
            self._write_marker(
                started,
                operation=operation,
                status="ATTEMPT_STARTED_NO_RETRY",
                generation_digest=self._generation_digest,
            )
        except FileExistsError as error:
            raise V4ActualPreparationGuardError(
                "PREPARATION_OPERATION_ALREADY_ATTEMPTED"
            ) from error
        except OSError as error:
            raise V4ActualPreparationGuardError("PREPARATION_ATTEMPT_NOT_PERSISTED") from error
        return V4PreparationOperationPermit(
            token=_PERMIT_TOKEN,
            operation=operation,
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
        )

    def complete(
        self,
        operation: V4PreparationOperation,
        *,
        operation_permit: V4PreparationOperationPermit,
    ) -> None:
        require_operation_permit(
            operation_permit,
            expected_operation=operation,
            require_completed=True,
        )
        started = self._marker(operation, "started")
        passed = self._marker(operation, "passed")
        if not self._marker_matches_review(
            started,
            operation=operation,
            expected_status="ATTEMPT_STARTED_NO_RETRY",
        ) or passed.exists():
            raise V4ActualPreparationGuardError("PREPARATION_ATTEMPT_STATE_INVALID")
        try:
            self._write_marker(
                passed,
                operation=operation,
                status="PASSED",
                completion_digest=operation_permit._completion_digest,
                completion_report=operation_permit._completion_report,
                generation_digest=self._generation_digest,
            )
        except FileExistsError as error:
            raise V4ActualPreparationGuardError(
                "PREPARATION_PASS_ALREADY_EXISTS"
            ) from error
        except OSError as error:
            raise V4ActualPreparationGuardError("PREPARATION_PASS_NOT_PERSISTED") from error

    def _marker(self, operation: V4PreparationOperation, suffix: str) -> Path:
        return self.state_root / f"{operation.value}.{suffix}.json"

    def _write_marker(
        self,
        path: Path,
        *,
        operation: V4PreparationOperation,
        status: str,
        completion_digest: str | None = None,
        completion_report: dict[str, object] | None = None,
        generation_digest: str,
    ) -> None:
        payload = json.dumps(
            {
                "operation": operation.value,
                "status": status,
                "reviewed_files_digest": self._reviewed_files_digest,
                "completion_digest": completion_digest,
                "completion_report": completion_report,
                "generation_digest": generation_digest,
            },
            sort_keys=True,
        )
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _marker_matches_review(
        self,
        path: Path,
        *,
        operation: V4PreparationOperation,
        expected_status: str,
    ) -> bool:
        if path.is_symlink() or not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        base_matches = (
            isinstance(payload, dict)
            and payload.get("operation") == operation.value
            and payload.get("status") == expected_status
            and payload.get("reviewed_files_digest") == self._reviewed_files_digest
            and payload.get("generation_digest") == self._generation_digest
        )
        if not base_matches or expected_status != "PASSED":
            return base_matches
        report = payload.get("completion_report")
        if not isinstance(report, dict) or not _operation_report_is_clear(
            operation, report
        ):
            return False
        expected_digest = _completion_digest(
            operation=operation,
            safe_report=report,
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
        )
        return payload.get("completion_digest") == expected_digest


def load_completed_preparation_evidence(
    *,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
) -> V4CompletedPreparationEvidence:
    """Mint no-POST readiness evidence only after every fixed step passed."""

    require_external_preparation_gate(external_gate)
    normalized = generation_digest.removeprefix("sha256:")
    if (
        not generation_digest.startswith("sha256:")
        or len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise V4ActualPreparationGuardError(
            "PREPARATION_COMPLETED_EVIDENCE_INVALID"
        )
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    if not ledger.state_root.name.endswith(f"-{normalized}"):
        raise V4ActualPreparationGuardError(
            "PREPARATION_COMPLETED_GENERATION_MISMATCH"
        )
    for operation in V4PreparationOperation:
        if not ledger._marker_matches_review(
            ledger._marker(operation, "passed"),
            operation=operation,
            expected_status="PASSED",
        ):
            raise V4ActualPreparationGuardError(
                "PREPARATION_SEQUENCE_NOT_COMPLETE"
            )
    consumed_marker = ledger.state_root / "generation_consumed.json"
    if consumed_marker.exists() or consumed_marker.is_symlink():
        raise V4ActualPreparationGuardError(
            "PREPARATION_COMPLETED_EVIDENCE_INVALID"
        )
    return V4CompletedPreparationEvidence(
        token=_COMPLETED_EVIDENCE_TOKEN,
        generation_digest=generation_digest,
        state_root=ledger.state_root,
    )


def preparation_state_root(
    *,
    repository: Path,
    reviewed_files_digest: str,
    generation_manifest_digest: str,
) -> Path:
    """Bind every no-retry attempt set to source and generation digests."""

    prefix = "sha256:"
    digest = reviewed_files_digest.removeprefix(prefix)
    generation_digest = generation_manifest_digest.removeprefix(prefix)
    if any(
        (
            not value.startswith(prefix)
            or len(normalized) != 64
            or any(character not in "0123456789abcdef" for character in normalized)
        )
        for value, normalized in (
            (reviewed_files_digest, digest),
            (generation_manifest_digest, generation_digest),
        )
    ):
        raise V4ActualPreparationGuardError("PREPARATION_REVIEWED_DIGEST_INVALID")
    return (
        repository.resolve()
        / PREPARATION_STATE_RELATIVE
        / f"generation-{digest}-{generation_digest}"
    )


def confirm_email_delivery_exact(
    *, phrase: str, operation_permit: V4PreparationOperationPermit
) -> V4OperatorConfirmationReport:
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.EMAIL_CONFIRMATION,
        claim=True,
    )
    if phrase != EMAIL_DELIVERY_CONFIRMATION:
        raise V4ActualPreparationGuardError("EMAIL_DELIVERY_CONFIRMATION_MISMATCH")
    report = V4OperatorConfirmationReport(
        confirmation_kind="EMAIL_DELIVERY_OPERATOR_CONFIRMATION",
        exact_match=True,
    )
    _attest_email_confirmation_success_internal(
        operation_permit, report.to_safe_dict()
    )
    return report


def confirm_account_exclusivity_exact(
    *, phrase: str, operation_permit: V4PreparationOperationPermit
) -> V4OperatorConfirmationReport:
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
        claim=True,
    )
    if phrase != EXCLUSIVITY_CONFIRMATION:
        raise V4ActualPreparationGuardError("ACCOUNT_EXCLUSIVITY_CONFIRMATION_MISMATCH")
    report = V4OperatorConfirmationReport(
        confirmation_kind="ACCOUNT_EXCLUSIVITY_OPERATOR_CONFIRMATION",
        exact_match=True,
    )
    _attest_exclusivity_success_internal(operation_permit, report.to_safe_dict())
    return report


def reviewed_files_digest(*, repository: Path) -> str:
    digest = hashlib.sha256()
    root = repository.resolve()
    for relative in _REVIEWED_FILES:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise V4ActualPreparationGuardError("PREPARATION_REVIEWED_FILE_INVALID")
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def load_external_preparation_gate(*, repository: Path) -> V4ExternalPreparationGate:
    require_clean_main(repository=repository)
    artifact_path = repository.resolve() / PREPARATION_ARTIFACT
    if not artifact_path.is_file() or artifact_path.is_symlink():
        raise V4ActualPreparationGuardError("PREPARATION_REVIEW_ARTIFACT_MISSING")
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4ActualPreparationGuardError("PREPARATION_REVIEW_ARTIFACT_INVALID") from error
    expected_true = (
        "focused_tests_passed",
        "related_tests_passed",
        "ruff_passed",
        "diff_check_passed",
        "danger_scan_passed",
        "architecture_review_clear",
        "safety_review_clear",
        "operations_review_clear",
    )
    if (
        not isinstance(artifact, dict)
        or artifact.get("schema") != "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1"
        or artifact.get("status") != "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST"
        or artifact.get("broker_post_authorized") is not False
        or artifact.get("activation_permit_issued") is not False
        or any(artifact.get(field) is not True for field in expected_true)
    ):
        raise V4ActualPreparationGuardError("PREPARATION_REVIEW_ARTIFACT_NOT_CLEAR")
    actual_digest = reviewed_files_digest(repository=repository)
    if artifact.get("reviewed_files_digest") != actual_digest:
        raise V4ActualPreparationGuardError("PREPARATION_REVIEWED_FILES_DIGEST_MISMATCH")
    try:
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=actual_digest,
        )
    except ValueError as error:
        raise V4ActualPreparationGuardError(
            "PREPARATION_FROZEN_GENERATION_MISMATCH"
        ) from error
    if artifact.get("generation_manifest_digest") != generation.digest:
        raise V4ActualPreparationGuardError(
            "PREPARATION_FROZEN_GENERATION_MISMATCH"
        )
    return V4ExternalPreparationGate(
        token=_GATE_TOKEN,
        reviewed_files_digest=actual_digest,
        state_root=preparation_state_root(
            repository=repository,
            reviewed_files_digest=actual_digest,
            generation_manifest_digest=generation.digest,
        ),
    )


def inspect_clean_main(
    *, repository: Path, runner: CommandRunner = _default_runner
) -> V4PreparationGitGate:
    repository = repository.resolve()
    if not (repository / ".git").exists():
        raise V4ActualPreparationGuardError("PREPARATION_REPOSITORY_INVALID")

    def run_git(*args: str) -> subprocess.CompletedProcess[str]:
        try:
            result = runner(["git", "-C", str(repository), *args])
        except (OSError, subprocess.TimeoutExpired) as error:
            raise V4ActualPreparationGuardError("PREPARATION_GIT_CHECK_FAILED") from error
        if result.returncode != 0:
            raise V4ActualPreparationGuardError("PREPARATION_GIT_CHECK_FAILED")
        return result

    status = run_git("status", "--porcelain").stdout
    head = run_git("rev-parse", "HEAD").stdout.strip()
    origin = run_git("rev-parse", "origin/main").stdout.strip()
    branch = run_git("branch", "--show-current").stdout.strip()
    clean = status == ""
    matches = bool(head) and head == origin
    on_main = branch == "main"
    return V4PreparationGitGate(
        working_tree_clean=clean,
        head_matches_origin_main=matches,
        branch_main=on_main,
        clear=clean and matches and on_main,
    )


def require_clean_main(*, repository: Path) -> V4PreparationGitGate:
    gate = inspect_clean_main(repository=repository)
    if not gate.clear:
        raise V4ActualPreparationGuardError("PREPARATION_GIT_GATE_BLOCKED")
    return gate


def check_v4_keychain_presence_only(
    *,
    operation_permit: V4PreparationOperationPermit,
    runner: CommandRunner = _default_runner,
) -> V4KeychainPresenceReport:
    """Check exact item presence without asking Keychain to output values."""

    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.PRESENCE,
        claim=True,
    )
    if platform.system() != "Darwin":
        raise V4ActualPreparationGuardError("PREPARATION_KEYCHAIN_PLATFORM_UNSUPPORTED")
    items = (
        ("fx-strategy-lab-h11-v4-actual", "gmo-fx-api-key"),
        ("fx-strategy-lab-h11-v4-actual", "gmo-fx-api-secret"),
        ("fx-strategy-lab-h11-v4-notify", "pushover-api-token"),
        ("fx-strategy-lab-h11-v4-notify", "pushover-user-key"),
        ("fx-strategy-lab-h11-v4-notify", "smtp-username"),
        ("fx-strategy-lab-h11-v4-notify", "smtp-app-password"),
    )
    present = 0
    for service, account in items:
        try:
            completed = runner(
                ["security", "find-generic-password", "-s", service, "-a", account]
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise V4ActualPreparationGuardError("PREPARATION_KEYCHAIN_CHECK_FAILED") from error
        present += int(completed.returncode == 0)
    report = V4KeychainPresenceReport(
        total_required=len(items),
        present_count=present,
        all_present=present == len(items),
    )
    if report.all_present:
        _attest_presence_success_internal(operation_permit, report.to_safe_dict())
    return report


def check_v4_keychain_access_internal_only(
    *,
    operation_permit: V4PreparationOperationPermit,
    runner: KeychainValueRunner = _default_keychain_value_runner,
    timeout_seconds: float = 300.0,
    clock: MonotonicClock = time.monotonic,
) -> V4KeychainAccessReport:
    """Read and immediately discard six fixed values without exposing content."""

    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.KEYCHAIN_ACCESS,
        claim=True,
    )
    if platform.system() != "Darwin":
        raise V4ActualPreparationGuardError("PREPARATION_KEYCHAIN_PLATFORM_UNSUPPORTED")
    if timeout_seconds < 30.0 or timeout_seconds > 300.0:
        raise V4ActualPreparationGuardError("PREPARATION_KEYCHAIN_TIMEOUT_INVALID")
    items = (
        ("fx-strategy-lab-h11-v4-actual", "gmo-fx-api-key"),
        ("fx-strategy-lab-h11-v4-actual", "gmo-fx-api-secret"),
        ("fx-strategy-lab-h11-v4-notify", "pushover-api-token"),
        ("fx-strategy-lab-h11-v4-notify", "pushover-user-key"),
        ("fx-strategy-lab-h11-v4-notify", "smtp-username"),
        ("fx-strategy-lab-h11-v4-notify", "smtp-app-password"),
    )
    accessible = 0
    deadline = clock() + timeout_seconds
    for service, account in items:
        remaining_seconds = deadline - clock()
        if remaining_seconds <= 0:
            raise V4ActualPreparationGuardError(
                "PREPARATION_KEYCHAIN_ACCESS_FAILED"
            ) from None
        try:
            completed = runner(
                [
                    "security",
                    "find-generic-password",
                    "-s",
                    service,
                    "-a",
                    account,
                    "-w",
                ],
                remaining_seconds,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is None:
            # Raise outside the exception handler so a TimeoutExpired carrying
            # partial output is not retained as context or cause.
            raise V4ActualPreparationGuardError(
                "PREPARATION_KEYCHAIN_ACCESS_FAILED"
            ) from None
        # Never include stdout/stderr or the item name in a failure.  A
        # successful non-empty value is counted and immediately discarded.
        if completed.returncode != 0 or not completed.stdout.rstrip("\n"):
            raise V4ActualPreparationGuardError(
                "PREPARATION_KEYCHAIN_ACCESS_FAILED"
            )
        accessible += 1
        del completed
    report = V4KeychainAccessReport(
        total_required=len(items),
        accessible_count=accessible,
        all_accessible=accessible == len(items),
    )
    if report.all_accessible:
        _attest_keychain_access_success_internal(
            operation_permit, report.to_safe_dict()
        )
    return report
