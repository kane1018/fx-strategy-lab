"""Fail-closed local guards for finite H-11 v4 activation preparation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path


class V4ActualPreparationGuardError(RuntimeError):
    """Fixed safe preparation guard failure."""


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]

PREPARATION_ARTIFACT = Path(
    "docs/templates/h11_v4_actual_preparation_evidence.json"
)
PREPARATION_STATE_RELATIVE = Path(
    "backend/market_data/h11_v4_actual_preparation"
)
_REVIEWED_FILES = (
    "AGENTS.md",
    "backend/app/h11_auto/v4_actual_preparation_guard.py",
    "backend/app/h11_auto/v4_actual_host_kill_rehearsal.py",
    "backend/app/h11_auto/v4_gmo_engine.py",
    "backend/app/h11_auto/runtime_safety.py",
    "backend/app/private_api/auth.py",
    "backend/app/services/h11_v4_gmo_actual_adapter.py",
    "backend/app/services/h11_v4_gmo_actual_transport.py",
    "backend/app/services/h11_v4_notification_binding_no_post.py",
    "backend/app/services/h11_v4_notification_actual_preparation.py",
    "backend/app/services/h11_v4_gmo_readonly_preflight.py",
    "backend/scripts/h11_auto_v4_actual_preparation_presence.py",
    "backend/scripts/h11_auto_v4_actual_notification_rehearsal.py",
    "backend/scripts/h11_auto_v4_actual_host_kill_rehearsal.py",
    "backend/scripts/h11_auto_v4_email_delivery_confirm.py",
    "backend/scripts/h11_auto_v4_exclusivity_confirm.py",
    "backend/scripts/h11_auto_v4_private_get_preflight.py",
    "backend/app/tests/h11_auto/test_v4_actual_preparation_fake_first.py",
    "backend/app/tests/h11_auto/test_v4_gmo_actual_adapter_fake_only.py",
    "backend/app/tests/h11_auto/test_v4_gmo_relaxed_no_post.py",
    "backend/app/tests/h11_auto/test_v4_notification_binding_fake_only.py",
    "backend/app/tests/test_h11_stage1_paper_wiring_no_post.py",
    "backend/app/tests/test_h11_v3_runtime_safety_no_post.py",
    "docs/H11_V4_ACTUAL_ACTIVATION_PREPARATION_REPORT_20260716.md",
    "docs/H11_AUTO_OPERATOR_DECISION_SHEET_NO_POST_20260715.md",
    "docs/H11_V4_MAJOR_INCIDENT_RESUME_DECLARATION_DRAFT_NO_POST_20260715.md",
)
_GATE_TOKEN = object()
_PERMIT_TOKEN = object()
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


class V4PreparationOperation(str, Enum):
    PRESENCE = "00_presence"
    NOTIFICATION = "10_notification"
    EMAIL_CONFIRMATION = "20_email_confirmation"
    HOST_KILL = "30_host_kill"
    EXCLUSIVITY_CONFIRMATION = "40_exclusivity_confirmation"
    PRIVATE_GET = "50_private_get"


_PREVIOUS_OPERATION = {
    V4PreparationOperation.PRESENCE: None,
    V4PreparationOperation.NOTIFICATION: V4PreparationOperation.PRESENCE,
    V4PreparationOperation.EMAIL_CONFIRMATION: V4PreparationOperation.NOTIFICATION,
    V4PreparationOperation.HOST_KILL: V4PreparationOperation.EMAIL_CONFIRMATION,
    V4PreparationOperation.EXCLUSIVITY_CONFIRMATION: V4PreparationOperation.HOST_KILL,
    V4PreparationOperation.PRIVATE_GET: V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
}


class V4PreparationOperationPermit:
    """Single-process companion to the already-persisted attempt marker."""

    __slots__ = ("_token", "_operation", "_consumed")

    def __init__(
        self,
        *,
        token: object,
        operation: V4PreparationOperation,
    ) -> None:
        if token is not _PERMIT_TOKEN:
            raise V4ActualPreparationGuardError("PREPARATION_OPERATION_PERMIT_INVALID")
        self._token = token
        self._operation = operation
        self._consumed = False

    def consume_for(self, operation: V4PreparationOperation) -> None:
        if (
            self._token is not _PERMIT_TOKEN
            or self._operation is not operation
            or self._consumed
        ):
            raise V4ActualPreparationGuardError(
                "PREPARATION_OPERATION_PERMIT_INVALID"
            )
        self._consumed = True

    def assert_consumed_for(self, operation: V4PreparationOperation) -> None:
        if (
            self._token is not _PERMIT_TOKEN
            or self._operation is not operation
            or not self._consumed
        ):
            raise V4ActualPreparationGuardError(
                "PREPARATION_OPERATION_PERMIT_NOT_CONSUMED"
            )

    def __repr__(self) -> str:
        return "V4PreparationOperationPermit(<redacted>)"

    def __bool__(self) -> bool:
        return False


def require_operation_permit(
    permit: object,
    *,
    expected_operation: V4PreparationOperation,
    consume: bool = False,
    require_consumed: bool = False,
) -> V4PreparationOperationPermit:
    """Accept only an opaque permit minted by the fixed preparation ledger."""

    if consume and require_consumed:
        raise V4ActualPreparationGuardError("PREPARATION_OPERATION_PERMIT_INVALID")
    if (
        type(permit) is not V4PreparationOperationPermit
        or getattr(permit, "_token", None) is not _PERMIT_TOKEN
        or getattr(permit, "_operation", None) is not expected_operation
        or not isinstance(getattr(permit, "_consumed", None), bool)
        or (require_consumed and not permit._consumed)
        or (not require_consumed and permit._consumed)
    ):
        raise V4ActualPreparationGuardError("PREPARATION_OPERATION_PERMIT_INVALID")
    if consume:
        V4PreparationOperationPermit.consume_for(permit, expected_operation)
    return permit


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
            require_consumed=True,
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
    ) -> None:
        payload = json.dumps(
            {
                "operation": operation.value,
                "status": status,
                "reviewed_files_digest": self._reviewed_files_digest,
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
        return (
            isinstance(payload, dict)
            and payload.get("operation") == operation.value
            and payload.get("status") == expected_status
            and payload.get("reviewed_files_digest") == self._reviewed_files_digest
        )


def preparation_state_root(*, repository: Path) -> Path:
    return repository.resolve() / PREPARATION_STATE_RELATIVE


def confirm_email_delivery_exact(
    *, phrase: str, operation_permit: V4PreparationOperationPermit
) -> V4OperatorConfirmationReport:
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.EMAIL_CONFIRMATION,
        consume=True,
    )
    if phrase != EMAIL_DELIVERY_CONFIRMATION:
        raise V4ActualPreparationGuardError("EMAIL_DELIVERY_CONFIRMATION_MISMATCH")
    return V4OperatorConfirmationReport(
        confirmation_kind="EMAIL_DELIVERY_OPERATOR_CONFIRMATION",
        exact_match=True,
    )


def confirm_account_exclusivity_exact(
    *, phrase: str, operation_permit: V4PreparationOperationPermit
) -> V4OperatorConfirmationReport:
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
        consume=True,
    )
    if phrase != EXCLUSIVITY_CONFIRMATION:
        raise V4ActualPreparationGuardError("ACCOUNT_EXCLUSIVITY_CONFIRMATION_MISMATCH")
    return V4OperatorConfirmationReport(
        confirmation_kind="ACCOUNT_EXCLUSIVITY_OPERATOR_CONFIRMATION",
        exact_match=True,
    )


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
    return V4ExternalPreparationGate(
        token=_GATE_TOKEN,
        reviewed_files_digest=actual_digest,
        state_root=preparation_state_root(repository=repository),
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
        consume=True,
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
    return V4KeychainPresenceReport(
        total_required=len(items),
        present_count=present,
        all_present=present == len(items),
    )
