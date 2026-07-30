"""Fail-closed local guards for finite H-11 v4 activation preparation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from enum import Enum, StrEnum
from pathlib import Path

from app.h11_auto.persistence import H11AutoPersistenceError, H11AutoProcessLock
from app.h11_auto.runtime_safety import PhaseBRiskStore
from app.h11_auto.v4_gmo_contracts import v4_gmo_trading_day_jst
from app.h11_auto.v4_gmo_generation import (
    load_v4_gmo_frozen_generation,
    v4_gmo_risk_policy,
)
from app.h11_auto.v4_gmo_runtime_paths import v4_gmo_runtime_state_root
from h11_v4_reviewed_digest import (
    V4ReviewedDigestError,
    compute_reviewed_files_digest,
)


class V4PreparationFailureCode(StrEnum):
    OPERATION_PERMIT_INVALID = "PREPARATION_OPERATION_PERMIT_INVALID"
    STATE_SYMLINK_FORBIDDEN = "PREPARATION_STATE_SYMLINK_FORBIDDEN"
    ATTEMPT_LOCK_INVALID = "PREPARATION_ATTEMPT_LOCK_INVALID"
    OPERATION_IN_PROGRESS = "PREPARATION_OPERATION_IN_PROGRESS"
    SEQUENCE_PREVIOUS_NOT_CLEAR = "PREPARATION_SEQUENCE_PREVIOUS_NOT_CLEAR"
    OPERATION_ALREADY_ATTEMPTED = "PREPARATION_OPERATION_ALREADY_ATTEMPTED"
    GENERATION_TERMINAL_UNRESOLVED = (
        "PREPARATION_GENERATION_TERMINAL_UNRESOLVED"
    )
    ATTEMPT_NOT_PERSISTED = "PREPARATION_ATTEMPT_NOT_PERSISTED"
    ATTEMPT_STATE_INVALID = "PREPARATION_ATTEMPT_STATE_INVALID"
    PASS_ALREADY_EXISTS = "PREPARATION_PASS_ALREADY_EXISTS"
    PASS_NOT_PERSISTED = "PREPARATION_PASS_NOT_PERSISTED"


class V4ActualPreparationGuardError(RuntimeError):
    """Fixed safe preparation guard failure with optional typed code."""

    def __init__(self, code: V4PreparationFailureCode | str) -> None:
        self.code = code if isinstance(code, V4PreparationFailureCode) else None
        super().__init__(code.value if self.code is not None else code)


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
KeychainValueRunner = Callable[[list[str], float], subprocess.CompletedProcess[str]]
MonotonicClock = Callable[[], float]

PREPARATION_ARTIFACT = Path(
    "docs/templates/h11_v4_actual_preparation_evidence.json"
)
PREPARATION_STATE_RELATIVE = Path(
    "backend/market_data/h11_v4_actual_preparation"
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
        "_trading_day_jst",
        "_consumed",
    )

    def __init__(
        self,
        *,
        token: object,
        generation_digest: str,
        state_root: Path,
        trading_day_jst: str,
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
            or not _valid_trading_day_jst(trading_day_jst)
        ):
            raise V4ActualPreparationGuardError(
                "PREPARATION_COMPLETED_EVIDENCE_INVALID"
            )
        self._token = token
        self._generation_digest = generation_digest
        self._state_root = state_root
        self._trading_day_jst = trading_day_jst
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
        marker = (
            self._state_root
            / f"generation_consumed.{self._trading_day_jst}.json"
        )
        payload = json.dumps(
            {
                "generation_digest": self._generation_digest,
                "trading_day_jst": self._trading_day_jst,
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


class V4RuntimeOnlyPreparationCarryForwardEvidence:
    """Falsey evidence usable only as a fresh operation-60 predecessor."""

    __slots__ = (
        "_token",
        "source_reviewed_files_digest",
        "source_generation_digest",
        "target_reviewed_files_digest",
        "target_generation_digest",
        "trading_day_jst",
        "completed_operations",
        "broker_post_authorized",
        "activation_permit_issued",
    )

    def __init__(
        self,
        *,
        token: object,
        source_reviewed_files_digest: str,
        source_generation_digest: str,
        target_reviewed_files_digest: str,
        target_generation_digest: str,
        trading_day_jst: str,
        completed_operations: tuple[str, ...],
    ) -> None:
        if token is not _RUNTIME_CARRY_FORWARD_TOKEN:
            raise V4ActualPreparationGuardError(
                "G040_RUNTIME_CARRY_FORWARD_INVALID"
            )
        self._token = token
        self.source_reviewed_files_digest = source_reviewed_files_digest
        self.source_generation_digest = source_generation_digest
        self.target_reviewed_files_digest = target_reviewed_files_digest
        self.target_generation_digest = target_generation_digest
        self.trading_day_jst = trading_day_jst
        self.completed_operations = completed_operations
        self.broker_post_authorized = False
        self.activation_permit_issued = False

    def __bool__(self) -> bool:
        return False


class V4G052FlatOnlyCarryForwardEvidence:
    """Falsey G051 flat proof usable only as G052 operation-60 predecessor."""

    __slots__ = (
        "_token",
        "source_reviewed_files_digest",
        "source_generation_digest",
        "target_reviewed_files_digest",
        "target_generation_digest",
        "trading_day_jst",
        "flat_cycle_count",
        "unresolved_cycle_count",
        "transport_action_pending",
        "source_halt_remains_latched",
        "broker_post_authorized",
        "activation_permit_issued",
    )

    def __init__(
        self,
        *,
        token: object,
        source_reviewed_files_digest: str,
        source_generation_digest: str,
        target_reviewed_files_digest: str,
        target_generation_digest: str,
        trading_day_jst: str,
        flat_cycle_count: int,
        unresolved_cycle_count: int,
        transport_action_pending: bool,
        source_halt_remains_latched: bool,
    ) -> None:
        if token is not _G052_FLAT_CARRY_FORWARD_TOKEN:
            raise V4ActualPreparationGuardError(
                "G052_FLAT_CARRY_FORWARD_INVALID"
            )
        self._token = token
        self.source_reviewed_files_digest = source_reviewed_files_digest
        self.source_generation_digest = source_generation_digest
        self.target_reviewed_files_digest = target_reviewed_files_digest
        self.target_generation_digest = target_generation_digest
        self.trading_day_jst = trading_day_jst
        self.flat_cycle_count = flat_cycle_count
        self.unresolved_cycle_count = unresolved_cycle_count
        self.transport_action_pending = transport_action_pending
        self.source_halt_remains_latched = source_halt_remains_latched
        self.broker_post_authorized = False
        self.activation_permit_issued = False

    def __bool__(self) -> bool:
        return False


class V4G053FlatOnlyCarryForwardEvidence:
    """Falsey G052 incident-flat proof usable only by G053 operation 60."""

    __slots__ = (
        "_token",
        "source_reviewed_files_digest",
        "source_generation_digest",
        "target_reviewed_files_digest",
        "target_generation_digest",
        "trading_day_jst",
        "account_flat",
        "active_orders_zero",
        "source_unresolved_cycle_count",
        "source_market_attempt_count",
        "source_entries_today",
        "source_halt_remains_latched",
        "broker_post_authorized",
        "activation_permit_issued",
    )

    def __init__(
        self,
        *,
        token: object,
        source_reviewed_files_digest: str,
        source_generation_digest: str,
        target_reviewed_files_digest: str,
        target_generation_digest: str,
        trading_day_jst: str,
        account_flat: bool,
        active_orders_zero: bool,
        source_unresolved_cycle_count: int,
        source_market_attempt_count: int,
        source_entries_today: int,
        source_halt_remains_latched: bool,
    ) -> None:
        if token is not _G053_FLAT_CARRY_FORWARD_TOKEN:
            raise V4ActualPreparationGuardError(
                "G053_FLAT_CARRY_FORWARD_INVALID"
            )
        self._token = token
        self.source_reviewed_files_digest = source_reviewed_files_digest
        self.source_generation_digest = source_generation_digest
        self.target_reviewed_files_digest = target_reviewed_files_digest
        self.target_generation_digest = target_generation_digest
        self.trading_day_jst = trading_day_jst
        self.account_flat = account_flat
        self.active_orders_zero = active_orders_zero
        self.source_unresolved_cycle_count = source_unresolved_cycle_count
        self.source_market_attempt_count = source_market_attempt_count
        self.source_entries_today = source_entries_today
        self.source_halt_remains_latched = source_halt_remains_latched
        self.broker_post_authorized = False
        self.activation_permit_issued = False

    def __bool__(self) -> bool:
        return False


class V4PreparationOperation(str, Enum):
    PRESENCE = "00_presence"
    KEYCHAIN_ACCESS = "05_keychain_access"
    PUSHOVER = "10_pushover"
    SMTP = "15_smtp"
    EMAIL_CONFIRMATION = "20_email_confirmation"
    NETWORK_TIME = "25_network_time"
    HOST_KILL = "30_host_kill"
    EXCLUSIVITY_CONFIRMATION = "40_exclusivity_confirmation"
    PUBLIC_GET = "45_public_get"
    PRIVATE_GET = "50_private_get"
    MONITOR_LAUNCHAGENT = "60_monitor_launchagent"


_PREVIOUS_OPERATION = {
    V4PreparationOperation.PRESENCE: None,
    V4PreparationOperation.KEYCHAIN_ACCESS: V4PreparationOperation.PRESENCE,
    V4PreparationOperation.PUSHOVER: V4PreparationOperation.KEYCHAIN_ACCESS,
    V4PreparationOperation.SMTP: V4PreparationOperation.PUSHOVER,
    V4PreparationOperation.EMAIL_CONFIRMATION: V4PreparationOperation.SMTP,
    V4PreparationOperation.NETWORK_TIME: V4PreparationOperation.EMAIL_CONFIRMATION,
    V4PreparationOperation.HOST_KILL: V4PreparationOperation.NETWORK_TIME,
    V4PreparationOperation.EXCLUSIVITY_CONFIRMATION: V4PreparationOperation.HOST_KILL,
    V4PreparationOperation.PUBLIC_GET: V4PreparationOperation.EXCLUSIVITY_CONFIRMATION,
    V4PreparationOperation.PRIVATE_GET: V4PreparationOperation.PUBLIC_GET,
    V4PreparationOperation.MONITOR_LAUNCHAGENT: V4PreparationOperation.PRIVATE_GET,
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
        "_attempt_token",
    )

    def __init__(
        self,
        *,
        token: object,
        operation: V4PreparationOperation,
        reviewed_files_digest: str,
        generation_digest: str,
        attempt_token: str,
    ) -> None:
        if token is not _PERMIT_TOKEN:
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.OPERATION_PERMIT_INVALID
            )
        self._token = token
        self._operation = operation
        self._claimed = False
        self._completion_digest: str | None = None
        self._completion_report: dict[str, object] | None = None
        self._reviewed_files_digest = reviewed_files_digest
        self._generation_digest = generation_digest
        # Binds this permit to the specific begin() call that minted it, so a
        # stale permit from a since-retried attempt can never complete() a
        # step that a later begin() has superseded.
        self._attempt_token = attempt_token

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
        raise V4ActualPreparationGuardError(
            V4PreparationFailureCode.OPERATION_PERMIT_INVALID
        )
    if (
        type(permit) is not V4PreparationOperationPermit
        or getattr(permit, "_token", None) is not _PERMIT_TOKEN
        or getattr(permit, "_operation", None) is not expected_operation
        or not isinstance(getattr(permit, "_claimed", None), bool)
        or (require_completed and not _valid_completion_digest(permit._completion_digest))
        or (not require_completed and permit._completion_digest is not None)
    ):
        raise V4ActualPreparationGuardError(
            V4PreparationFailureCode.OPERATION_PERMIT_INVALID
        )
    if claim:
        if permit._claimed:
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.OPERATION_PERMIT_INVALID
            )
        permit._claimed = True
    return permit


def _valid_trading_day_jst(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


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


def _attest_network_time_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.NETWORK_TIME, safe_report=safe_report
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


def _attest_public_get_success_internal(
    permit: V4PreparationOperationPermit, safe_report: dict[str, object]
) -> None:
    _attest_operation_success(
        permit, operation=V4PreparationOperation.PUBLIC_GET, safe_report=safe_report
    )


def _attest_monitor_launchagent_success_internal(
    permit: V4PreparationOperationPermit,
    safe_report: dict[str, object],
    *,
    expected_runtime_initialized: bool,
) -> None:
    waiting = (
        safe_report.get("heartbeat_waiting_for_canonical_runtime") is True
    )
    runtime_initialized = (
        safe_report.get("heartbeat_runtime_initialized") is True
    )
    if (
        not isinstance(expected_runtime_initialized, bool)
        or waiting == runtime_initialized
        or runtime_initialized is not expected_runtime_initialized
    ):
        raise V4ActualPreparationGuardError(
            "PREPARATION_MONITOR_HEARTBEAT_SHAPE_MISMATCH"
        )
    _attest_operation_success(
        permit,
        operation=V4PreparationOperation.MONITOR_LAUNCHAGENT,
        safe_report=safe_report,
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
    if operation is V4PreparationOperation.NETWORK_TIME:
        return (
            report.get("status") == "PASSED_NETWORK_TIME_READ_ONLY_NO_BROKER_POST"
            and report.get("network_time_enabled") is True
            and report.get("administrator_prompt_used") is True
            and report.get("settings_changed") is False
            and report.get("broker_get_count") == 0
            and report.get("broker_post_count") == 0
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
    if operation is V4PreparationOperation.PUBLIC_GET:
        return (
            report.get("public_get_count") == 2
            and report.get("market_open") is True
            and report.get("ticker_symbol_match") is True
            and report.get("ticker_status_open") is True
            and report.get("quote_fresh") is True
            and report.get("spread_within_limit") is True
            and report.get("raw_response_retained") is False
            and report.get("identifier_exposed") is False
            and report.get("broker_post_count") == 0
            and report.get("broker_write_performed") is False
        )
    if operation is V4PreparationOperation.PRIVATE_GET:
        offsets = report.get("cadence_offsets_seconds")
        return (
            report.get("broker_get_count") == 3
            and report.get("account_wide_snapshot_clear") is True
            and report.get("account_flat") is True
            and report.get("account_active_orders_zero") is True
            and isinstance(offsets, tuple | list)
            and len(offsets) == 3
            and all(isinstance(value, int | float) for value in offsets)
            and float(offsets[1]) - float(offsets[0]) + 1e-9 >= 0.25
            and float(offsets[2]) - float(offsets[1]) + 1e-9 >= 0.25
            and report.get("broker_post_count") == 0
            and report.get("broker_write_performed") is False
        )
    if operation is V4PreparationOperation.MONITOR_LAUNCHAGENT:
        return (
            report.get("installed") is True
            and report.get("bootstrapped") is True
            and report.get("restarted") is True
            and report.get("service_running") is True
            and report.get("heartbeat_fresh") is True
            and report.get("heartbeat_generation_digest_match") is True
            and (
                report.get("heartbeat_waiting_for_canonical_runtime") is True
            )
            != (report.get("heartbeat_runtime_initialized") is True)
            and report.get("heartbeat_broker_read") is False
            and report.get("heartbeat_broker_write") is False
            and report.get("actual_post_count") == 0
            and report.get("raw_output_retained") is False
            and (
                report.get("previous_service_present") is False
                or report.get("previous_service_booted_out") is True
            )
        )
    return False


class V4PreparationAttemptLedger:
    """Persistent sequence with generation-terminal unresolved attempts.

    Any ``started`` marker without its matching ``passed`` marker is terminal
    for the generation, including across later trading days. A completed
    operation remains daily-scoped, so a fresh daily sequence may run under
    the same generation only when every prior attempt reached ``PASSED``.
    ``begin()`` holds one exclusive generation-wide process lock across every
    operation and trading day, serializing validation, scan, and marker creation.
    """

    def __init__(
        self,
        *,
        external_gate: V4ExternalPreparationGate,
        now_utc: datetime | None = None,
    ) -> None:
        self._locks: dict[V4PreparationOperation, H11AutoProcessLock] = {}
        require_external_preparation_gate(external_gate)
        self._external_gate = external_gate
        unresolved = external_gate.state_root_for_internal_preparation_only()
        path_candidates = (
            unresolved,
            unresolved.parent,
            unresolved.parent.parent,
            unresolved.parent.parent.parent,
        )
        if any(candidate.is_symlink() for candidate in path_candidates):
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.STATE_SYMLINK_FORBIDDEN
            )
        self.state_root = unresolved.resolve()
        self._reviewed_files_digest = (
            external_gate.reviewed_digest_for_internal_preparation_only()
        )
        self._generation_digest = "sha256:" + self.state_root.name.rsplit("-", 1)[-1]
        self.state_root.mkdir(parents=True, exist_ok=True)
        # Trading-day scope: the same reviewed generation can be prepared fresh on
        # every JST day (no code change/new generation required) instead of the
        # 00-60 sequence being usable exactly once for this generation's lifetime.
        # Every marker this ledger writes or reads is keyed by this day.
        self._trading_day_jst = v4_gmo_trading_day_jst(now_utc or datetime.now(UTC))

    def begin(
        self,
        operation: V4PreparationOperation,
    ) -> V4PreparationOperationPermit:
        return self._begin(operation=operation, runtime_predecessor_clear=False)

    def begin_g040_runtime_only_monitor(
        self,
        *,
        repository: Path,
        generation_digest: str,
    ) -> V4PreparationOperationPermit:
        evidence = load_g040_runtime_only_carry_forward_evidence(
            repository=repository,
            external_gate=self._external_gate,
            generation_digest=generation_digest,
        )
        if not _runtime_carry_forward_matches_target(
            evidence=evidence,
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
            trading_day_jst=self._trading_day_jst,
        ):
            raise V4ActualPreparationGuardError(
                "G040_RUNTIME_CARRY_FORWARD_INVALID"
            )
        return self._begin(
            operation=V4PreparationOperation.MONITOR_LAUNCHAGENT,
            runtime_predecessor_clear=True,
        )

    def begin_g052_flat_only_monitor(
        self,
        *,
        repository: Path,
        generation_digest: str,
    ) -> V4PreparationOperationPermit:
        evidence = load_g052_flat_only_carry_forward_evidence(
            repository=repository,
            external_gate=self._external_gate,
            generation_digest=generation_digest,
        )
        if not _g052_flat_carry_forward_matches_target(
            evidence=evidence,
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
            trading_day_jst=self._trading_day_jst,
        ):
            raise V4ActualPreparationGuardError(
                "G052_FLAT_CARRY_FORWARD_INVALID"
            )
        return self._begin(
            operation=V4PreparationOperation.MONITOR_LAUNCHAGENT,
            runtime_predecessor_clear=True,
        )

    def begin_g053_flat_only_monitor(
        self,
        *,
        repository: Path,
        generation_digest: str,
    ) -> V4PreparationOperationPermit:
        evidence = load_g053_flat_only_carry_forward_evidence(
            repository=repository,
            external_gate=self._external_gate,
            generation_digest=generation_digest,
        )
        if not _g053_flat_carry_forward_matches_target(
            evidence=evidence,
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
            trading_day_jst=self._trading_day_jst,
        ):
            raise V4ActualPreparationGuardError(
                "G053_FLAT_CARRY_FORWARD_INVALID"
            )
        return self._begin(
            operation=V4PreparationOperation.MONITOR_LAUNCHAGENT,
            runtime_predecessor_clear=True,
        )

    def _begin(
        self,
        *,
        operation: V4PreparationOperation,
        runtime_predecessor_clear: bool,
    ) -> V4PreparationOperationPermit:
        # One generation-level lock serializes predecessor validation, the
        # generation-wide unresolved scan, and durable started-marker creation.
        # Daily marker names remain useful evidence, but never form a lock scope.
        lock = self._locks.setdefault(
            operation, H11AutoProcessLock(self._lock_path(operation))
        )
        try:
            acquired = lock.acquire()
        except H11AutoPersistenceError as error:
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.ATTEMPT_LOCK_INVALID
            ) from error
        if not acquired:
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.OPERATION_IN_PROGRESS
            )
        previous = _PREVIOUS_OPERATION[operation]
        previous_is_current = previous is None or self._marker_matches_review(
            self._marker(previous, "passed"),
            operation=previous,
            expected_status="PASSED",
        )
        previous_is_runtime_carry_forward = (
            operation is V4PreparationOperation.MONITOR_LAUNCHAGENT
            and previous is V4PreparationOperation.PRIVATE_GET
            and runtime_predecessor_clear is True
        )
        if not (previous_is_current or previous_is_runtime_carry_forward):
            lock.release()
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.SEQUENCE_PREVIOUS_NOT_CLEAR
            )
        started = self._marker(operation, "started")
        passed = self._marker(operation, "passed")
        if passed.exists():
            lock.release()
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.OPERATION_ALREADY_ATTEMPTED
            )
        if started.is_symlink():
            lock.release()
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.STATE_SYMLINK_FORBIDDEN
            )
        if self._has_unresolved_attempt():
            lock.release()
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.GENERATION_TERMINAL_UNRESOLVED
            )
        attempt_token = uuid.uuid4().hex
        try:
            self._write_marker(
                started,
                operation=operation,
                status="ATTEMPT_STARTED",
                generation_digest=self._generation_digest,
                attempt_token=attempt_token,
            )
        except FileExistsError as error:
            lock.release()
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.ATTEMPT_NOT_PERSISTED
            ) from error
        except OSError as error:
            lock.release()
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.ATTEMPT_NOT_PERSISTED
            ) from error
        return V4PreparationOperationPermit(
            token=_PERMIT_TOKEN,
            operation=operation,
            reviewed_files_digest=self._reviewed_files_digest,
            generation_digest=self._generation_digest,
            attempt_token=attempt_token,
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
            expected_status="ATTEMPT_STARTED",
            expected_attempt_token=operation_permit._attempt_token,
        ) or passed.exists():
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.ATTEMPT_STATE_INVALID
            )
        try:
            self._write_marker(
                passed,
                operation=operation,
                status="PASSED",
                completion_digest=operation_permit._completion_digest,
                completion_report=operation_permit._completion_report,
                generation_digest=self._generation_digest,
                attempt_token=operation_permit._attempt_token,
            )
        except FileExistsError as error:
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.PASS_ALREADY_EXISTS
            ) from error
        except OSError as error:
            raise V4ActualPreparationGuardError(
                V4PreparationFailureCode.PASS_NOT_PERSISTED
            ) from error
        finally:
            lock = self._locks.get(operation)
            if lock is not None and lock.held:
                lock.release()

    def _lock_path(self, operation: V4PreparationOperation) -> Path:
        del operation
        return self.state_root / "preparation-generation.lock"

    def _marker(self, operation: V4PreparationOperation, suffix: str) -> Path:
        return (
            self.state_root
            / f"{operation.value}.{self._trading_day_jst}.{suffix}.json"
        )

    def _has_unresolved_attempt(self) -> bool:
        for operation in V4PreparationOperation:
            pattern = f"{operation.value}.*.started.json"
            prefix = f"{operation.value}."
            suffix = ".started.json"
            for started in self.state_root.glob(pattern):
                if started.is_symlink() or not started.is_file():
                    return True
                try:
                    payload = json.loads(started.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return True
                attempt_token = payload.get("attempt_token")
                if not isinstance(attempt_token, str) or not attempt_token:
                    return True
                if not self._marker_matches_review(
                    started,
                    operation=operation,
                    expected_status="ATTEMPT_STARTED",
                    expected_attempt_token=attempt_token,
                ):
                    return True
                trading_day = started.name.removeprefix(prefix).removesuffix(suffix)
                passed = (
                    self.state_root
                    / f"{operation.value}.{trading_day}.passed.json"
                )
                if not self._marker_matches_review(
                    passed,
                    operation=operation,
                    expected_status="PASSED",
                    expected_attempt_token=attempt_token,
                ):
                    return True
        return False

    def _write_marker(
        self,
        path: Path,
        *,
        operation: V4PreparationOperation,
        status: str,
        completion_digest: str | None = None,
        completion_report: dict[str, object] | None = None,
        generation_digest: str,
        attempt_token: str | None = None,
    ) -> None:
        payload = json.dumps(
            {
                "operation": operation.value,
                "status": status,
                "reviewed_files_digest": self._reviewed_files_digest,
                "completion_digest": completion_digest,
                "completion_report": completion_report,
                "generation_digest": generation_digest,
                "attempt_token": attempt_token,
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
        expected_attempt_token: str | None = None,
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
            and (
                expected_attempt_token is None
                or payload.get("attempt_token") == expected_attempt_token
            )
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
    now_utc: datetime | None = None,
) -> V4CompletedPreparationEvidence:
    """Mint no-POST readiness evidence only after today's fixed steps passed."""

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
    ledger = V4PreparationAttemptLedger(external_gate=external_gate, now_utc=now_utc)
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
    consumed_marker = (
        ledger.state_root / f"generation_consumed.{ledger._trading_day_jst}.json"
    )
    if consumed_marker.exists() or consumed_marker.is_symlink():
        raise V4ActualPreparationGuardError(
            "PREPARATION_COMPLETED_EVIDENCE_INVALID"
        )
    return V4CompletedPreparationEvidence(
        token=_COMPLETED_EVIDENCE_TOKEN,
        generation_digest=generation_digest,
        state_root=ledger.state_root,
        trading_day_jst=ledger._trading_day_jst,
    )


def load_completed_post_canary_preparation_evidence(
    *,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4CompletedPreparationEvidence:
    """Require fresh operations 00-50 for the entry-disabled reconciliation lane."""

    require_external_preparation_gate(external_gate)
    normalized = generation_digest.removeprefix("sha256:")
    if (
        not generation_digest.startswith("sha256:")
        or len(normalized) != 64
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise V4ActualPreparationGuardError(
            "POST_CANARY_PREPARATION_COMPLETED_EVIDENCE_INVALID"
        )
    ledger = V4PreparationAttemptLedger(external_gate=external_gate, now_utc=now_utc)
    if not ledger.state_root.name.endswith(f"-{normalized}"):
        raise V4ActualPreparationGuardError(
            "POST_CANARY_PREPARATION_GENERATION_MISMATCH"
        )
    required_operations = tuple(
        operation
        for operation in V4PreparationOperation
        if operation is not V4PreparationOperation.MONITOR_LAUNCHAGENT
    )
    for operation in required_operations:
        if not ledger._marker_matches_review(
            ledger._marker(operation, "passed"),
            operation=operation,
            expected_status="PASSED",
        ):
            raise V4ActualPreparationGuardError(
                "POST_CANARY_PREPARATION_SEQUENCE_NOT_COMPLETE"
            )
    consumed_marker = (
        ledger.state_root / f"generation_consumed.{ledger._trading_day_jst}.json"
    )
    if consumed_marker.exists() or consumed_marker.is_symlink():
        raise V4ActualPreparationGuardError(
            "POST_CANARY_PREPARATION_COMPLETED_EVIDENCE_INVALID"
        )
    return V4CompletedPreparationEvidence(
        token=_COMPLETED_EVIDENCE_TOKEN,
        generation_digest=generation_digest,
        state_root=ledger.state_root,
        trading_day_jst=ledger._trading_day_jst,
    )


def preparation_state_root(
    *,
    repository: Path,
    reviewed_files_digest: str,
    generation_manifest_digest: str,
) -> Path:
    """Bind every trading day's attempt set to source and generation digests."""

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


_G040_SOURCE_REVIEWED_FILES_DIGEST = (
    "sha256:16ecc53785ddc050952e1604b4c2ce1755b4bba7d74b8c46c579df16034c5007"
)
_G040_SOURCE_GENERATION_DIGEST = (
    "sha256:ff541122f94ba929edb5338918af2504f3edfe4401c8bde9bcf4cd56da1f5891"
)
_G040_SOURCE_TRADING_DAY_JST = "2026-07-29"
_RUNTIME_CARRY_FORWARD_TOKEN = object()
_G052_FLAT_CARRY_FORWARD_TOKEN = object()
_G053_FLAT_CARRY_FORWARD_TOKEN = object()
_G052_TARGET_GENERATION_LABEL = "H11_AUTO_30M_20260730_G052"
_G053_TARGET_GENERATION_LABEL = "H11_AUTO_30M_20260730_G053"
_G051_FLAT_SOURCE_REVIEWED_FILES_DIGEST = (
    "sha256:53d0dd07c663bfd528d0fece449b274e1dca631e03b43c8ead9fafa2d0f239ae"
)
_G051_FLAT_SOURCE_GENERATION_DIGEST = (
    "sha256:640556dd46a5066b8d7223f76d5196c22e4c65449c7d2371e526662049b9bf1c"
)
_G051_FLAT_SOURCE_TRADING_DAY_JST = "2026-07-30"
_G052_FLAT_SOURCE_REVIEWED_FILES_DIGEST = (
    "sha256:a0736d9f06cb912ef262c8321068de9564df8fb1b7f0dd6b0e01ef527ee9d4d3"
)
_G052_FLAT_SOURCE_GENERATION_DIGEST = (
    "sha256:4da28f2e6c49b7fd18fcdf466af9afbf4d875fc6273eaa22d7f2c0352bc8de13"
)
_RUNTIME_ONLY_TARGET_GENERATION_LABELS = {
    "H11_AUTO_30M_20260729_G040",
    "H11_AUTO_30M_20260729_G041",
    "H11_AUTO_30M_20260730_G047",
    "H11_AUTO_30M_20260730_G048",
    "H11_AUTO_30M_20260730_G049",
    "H11_AUTO_30M_20260730_G050",
    "H11_AUTO_30M_20260730_G051",
    "H11_AUTO_30M_20260730_G054",
}
_G040_RUNTIME_CARRIED_OPERATIONS = tuple(
    operation
    for operation in V4PreparationOperation
    if operation is not V4PreparationOperation.MONITOR_LAUNCHAGENT
)


def _source_marker_payload(
    *,
    path: Path,
    operation: V4PreparationOperation,
    expected_status: str,
    expected_attempt_token: str | None = None,
) -> dict[str, object]:
    current = path
    while True:
        if current.is_symlink():
            raise V4ActualPreparationGuardError(
                "G040_RUNTIME_SOURCE_EVIDENCE_INVALID"
            )
        if current.parent == current:
            break
        current = current.parent
    if not path.is_file():
        raise V4ActualPreparationGuardError(
            "G040_RUNTIME_SOURCE_EVIDENCE_MISSING"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise V4ActualPreparationGuardError(
            "G040_RUNTIME_SOURCE_EVIDENCE_INVALID"
        ) from error
    if (
        not isinstance(payload, dict)
        or payload.get("operation") != operation.value
        or payload.get("status") != expected_status
        or payload.get("reviewed_files_digest")
        != _G040_SOURCE_REVIEWED_FILES_DIGEST
        or payload.get("generation_digest") != _G040_SOURCE_GENERATION_DIGEST
        or (
            expected_attempt_token is not None
            and payload.get("attempt_token") != expected_attempt_token
        )
    ):
        raise V4ActualPreparationGuardError(
            "G040_RUNTIME_SOURCE_EVIDENCE_INVALID"
        )
    return payload


def load_g040_runtime_only_carry_forward_evidence(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4RuntimeOnlyPreparationCarryForwardEvidence:
    """Validate G039 00-50 from its recorded day without reusing operation 60."""

    require_external_preparation_gate(external_gate)
    target_ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=now_utc,
    )
    target_generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
    )
    if (
        target_generation.generation_label
        not in _RUNTIME_ONLY_TARGET_GENERATION_LABELS
        or target_generation.digest != generation_digest
        or not target_ledger.state_root.name.endswith(
            generation_digest.removeprefix("sha256:")
        )
    ):
        raise V4ActualPreparationGuardError("G040_RUNTIME_TARGET_MISMATCH")
    source_root = preparation_state_root(
        repository=repository,
        reviewed_files_digest=_G040_SOURCE_REVIEWED_FILES_DIGEST,
        generation_manifest_digest=_G040_SOURCE_GENERATION_DIGEST,
    )
    completed: list[str] = []
    for operation in _G040_RUNTIME_CARRIED_OPERATIONS:
        started = _source_marker_payload(
            path=source_root
            / f"{operation.value}.{_G040_SOURCE_TRADING_DAY_JST}.started.json",
            operation=operation,
            expected_status="ATTEMPT_STARTED",
        )
        attempt_token = started.get("attempt_token")
        if (
            not isinstance(attempt_token, str)
            or len(attempt_token) != 32
            or any(
                character not in "0123456789abcdef"
                for character in attempt_token
            )
        ):
            raise V4ActualPreparationGuardError(
                "G040_RUNTIME_SOURCE_EVIDENCE_INVALID"
            )
        passed = _source_marker_payload(
            path=source_root
            / f"{operation.value}.{_G040_SOURCE_TRADING_DAY_JST}.passed.json",
            operation=operation,
            expected_status="PASSED",
            expected_attempt_token=attempt_token,
        )
        report = passed.get("completion_report")
        if (
            not isinstance(report, dict)
            or not _operation_report_is_clear(operation, report)
            or passed.get("completion_digest")
            != _completion_digest(
                operation=operation,
                safe_report=report,
                reviewed_files_digest=_G040_SOURCE_REVIEWED_FILES_DIGEST,
                generation_digest=_G040_SOURCE_GENERATION_DIGEST,
            )
        ):
            raise V4ActualPreparationGuardError(
                "G040_RUNTIME_SOURCE_EVIDENCE_INVALID"
            )
        completed.append(operation.value)
    return V4RuntimeOnlyPreparationCarryForwardEvidence(
        token=_RUNTIME_CARRY_FORWARD_TOKEN,
        source_reviewed_files_digest=_G040_SOURCE_REVIEWED_FILES_DIGEST,
        source_generation_digest=_G040_SOURCE_GENERATION_DIGEST,
        target_reviewed_files_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
        target_generation_digest=generation_digest,
        trading_day_jst=target_ledger._trading_day_jst,
        completed_operations=tuple(completed),
    )


def _runtime_carry_forward_matches_target(
    *,
    evidence: V4RuntimeOnlyPreparationCarryForwardEvidence,
    reviewed_files_digest: str,
    generation_digest: str,
    trading_day_jst: str,
) -> bool:
    return (
        getattr(evidence, "_token", None) is _RUNTIME_CARRY_FORWARD_TOKEN
        and evidence.source_reviewed_files_digest
        == _G040_SOURCE_REVIEWED_FILES_DIGEST
        and evidence.source_generation_digest == _G040_SOURCE_GENERATION_DIGEST
        and evidence.target_reviewed_files_digest == reviewed_files_digest
        and evidence.target_generation_digest == generation_digest
        and evidence.trading_day_jst == trading_day_jst
        and evidence.completed_operations
        == tuple(
            operation.value for operation in _G040_RUNTIME_CARRIED_OPERATIONS
        )
        and evidence.broker_post_authorized is False
        and evidence.activation_permit_issued is False
        and bool(evidence) is False
    )


def _reject_g052_source_symlinks(path: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise V4ActualPreparationGuardError(
                "G052_FLAT_SOURCE_EVIDENCE_INVALID"
            )
        if current.parent == current:
            return
        current = current.parent


def load_g052_flat_only_carry_forward_evidence(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4G052FlatOnlyCarryForwardEvidence:
    """Validate only G051's completed flat lifecycle for G052 operation 60."""

    require_external_preparation_gate(external_gate)
    target_ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=now_utc,
    )
    target_generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
    )
    if (
        target_generation.generation_label != _G052_TARGET_GENERATION_LABEL
        or target_generation.digest != generation_digest
        or not target_ledger.state_root.name.endswith(
            generation_digest.removeprefix("sha256:")
        )
    ):
        raise V4ActualPreparationGuardError("G052_FLAT_TARGET_MISMATCH")

    source_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=_G051_FLAT_SOURCE_GENERATION_DIGEST,
    )
    completed_path = (
        source_root
        / "exit-sequence-dispatch-completed."
        f"{_G051_FLAT_SOURCE_TRADING_DAY_JST}.json"
    )
    database = source_root / "coordinator.sqlite3"
    for path in (source_root, completed_path, database):
        _reject_g052_source_symlinks(path)
    if not completed_path.is_file() or not database.is_file():
        raise V4ActualPreparationGuardError(
            "G052_FLAT_SOURCE_EVIDENCE_MISSING"
        )
    try:
        completed = json.loads(completed_path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(str(completed["observed_at_utc"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4ActualPreparationGuardError(
            "G052_FLAT_SOURCE_EVIDENCE_INVALID"
        ) from error
    if (
        set(completed)
        != {"generation_digest", "observed_at_utc", "status"}
        or completed.get("generation_digest")
        != _G051_FLAT_SOURCE_GENERATION_DIGEST
        or completed.get("status") != "EXIT_DISPATCH_COMPLETED_FLAT_RECONCILED"
        or observed.tzinfo is None
    ):
        raise V4ActualPreparationGuardError(
            "G052_FLAT_SOURCE_EVIDENCE_INVALID"
        )

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{database.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        generation_row = connection.execute(
            "SELECT value FROM metadata WHERE key='generation_digest'"
        ).fetchone()
        halt_row = connection.execute(
            "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
        ).fetchone()
        pending_row = connection.execute(
            "SELECT value FROM metadata WHERE key='pending_transport_resolution'"
        ).fetchone()
        cycle_row = connection.execute(
            "SELECT COUNT(*) cycle_count,"
            "SUM(CASE WHEN realized_pnl_jpy IS NOT NULL THEN 1 ELSE 0 END) "
            "flat_count,"
            "SUM(CASE WHEN realized_pnl_jpy IS NULL THEN 1 ELSE 0 END) "
            "unresolved_count FROM cycles"
        ).fetchone()
        attempt_rows = connection.execute(
            "SELECT action,COUNT(*) count FROM attempts "
            "GROUP BY action ORDER BY action"
        ).fetchall()
    except sqlite3.Error as error:
        raise V4ActualPreparationGuardError(
            "G052_FLAT_SOURCE_EVIDENCE_INVALID"
        ) from error
    finally:
        if connection is not None:
            connection.close()
    try:
        pending = json.loads(pending_row["value"])
    except (TypeError, KeyError, json.JSONDecodeError) as error:
        raise V4ActualPreparationGuardError(
            "G052_FLAT_SOURCE_EVIDENCE_INVALID"
        ) from error
    expected_attempts = {
        "CANCEL_EXACT_PROTECTION_FOR_TIME_EXIT": 1,
        "EXACT_SIZE_OCO_PROTECTION": 1,
        "MARKET_ENTRY": 1,
        "POSITION_SPECIFIC_TIME_EXIT": 1,
    }
    actual_attempts = {
        str(row["action"]): int(row["count"]) for row in attempt_rows
    }
    if (
        generation_row is None
        or generation_row["value"] != _G051_FLAT_SOURCE_GENERATION_DIGEST
        or halt_row is None
        or halt_row["value"] != "true"
        or pending_row is None
        or pending.get("generation_digest")
        != _G051_FLAT_SOURCE_GENERATION_DIGEST
        or pending.get("classification") != "FLAT_OR_REJECTED"
        or pending.get("previous_action") != "POSITION_SPECIFIC_TIME_EXIT"
        or cycle_row is None
        or int(cycle_row["cycle_count"]) != 1
        or int(cycle_row["flat_count"] or 0) != 1
        or int(cycle_row["unresolved_count"] or 0) != 0
        or actual_attempts != expected_attempts
    ):
        raise V4ActualPreparationGuardError(
            "G052_FLAT_SOURCE_EVIDENCE_INVALID"
        )
    return V4G052FlatOnlyCarryForwardEvidence(
        token=_G052_FLAT_CARRY_FORWARD_TOKEN,
        source_reviewed_files_digest=(
            _G051_FLAT_SOURCE_REVIEWED_FILES_DIGEST
        ),
        source_generation_digest=_G051_FLAT_SOURCE_GENERATION_DIGEST,
        target_reviewed_files_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
        target_generation_digest=generation_digest,
        trading_day_jst=target_ledger._trading_day_jst,
        flat_cycle_count=1,
        unresolved_cycle_count=0,
        transport_action_pending=False,
        source_halt_remains_latched=True,
    )


def _g052_flat_carry_forward_matches_target(
    *,
    evidence: V4G052FlatOnlyCarryForwardEvidence,
    reviewed_files_digest: str,
    generation_digest: str,
    trading_day_jst: str,
) -> bool:
    return (
        getattr(evidence, "_token", None) is _G052_FLAT_CARRY_FORWARD_TOKEN
        and evidence.source_reviewed_files_digest
        == _G051_FLAT_SOURCE_REVIEWED_FILES_DIGEST
        and evidence.source_generation_digest
        == _G051_FLAT_SOURCE_GENERATION_DIGEST
        and evidence.target_reviewed_files_digest == reviewed_files_digest
        and evidence.target_generation_digest == generation_digest
        and evidence.trading_day_jst == trading_day_jst
        and evidence.flat_cycle_count == 1
        and evidence.unresolved_cycle_count == 0
        and evidence.transport_action_pending is False
        and evidence.source_halt_remains_latched is True
        and evidence.broker_post_authorized is False
        and evidence.activation_permit_issued is False
        and bool(evidence) is False
    )


def _reject_g053_source_symlinks(path: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise V4ActualPreparationGuardError(
                "G053_FLAT_SOURCE_EVIDENCE_INVALID"
            )
        if current.parent == current:
            return
        current = current.parent


def load_g053_flat_only_carry_forward_evidence(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4G053FlatOnlyCarryForwardEvidence:
    """Validate G052's one-use account-flat result without clearing its HALT."""

    require_external_preparation_gate(external_gate)
    target_ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=now_utc,
    )
    target_generation = load_v4_gmo_frozen_generation(
        repository=repository,
        implementation_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
    )
    if (
        target_generation.generation_label != _G053_TARGET_GENERATION_LABEL
        or target_generation.digest != generation_digest
        or not target_ledger.state_root.name.endswith(
            generation_digest.removeprefix("sha256:")
        )
    ):
        raise V4ActualPreparationGuardError("G053_FLAT_TARGET_MISMATCH")

    source_root = v4_gmo_runtime_state_root(
        repository=repository,
        generation_digest=_G052_FLAT_SOURCE_GENERATION_DIGEST,
    )
    started_path = (
        source_root / "g052-emergency-readonly-reconciliation.started.json"
    )
    result_path = (
        source_root / "g052-emergency-readonly-reconciliation.result.json"
    )
    database = source_root / "coordinator.sqlite3"
    risk_path = source_root / "risk.json"
    for path in (source_root, started_path, result_path, database, risk_path):
        _reject_g053_source_symlinks(path)
    if (
        not started_path.is_file()
        or not result_path.is_file()
        or not database.is_file()
        or not risk_path.is_file()
    ):
        raise V4ActualPreparationGuardError(
            "G053_FLAT_SOURCE_EVIDENCE_MISSING"
        )
    try:
        started = json.loads(started_path.read_text(encoding="utf-8"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        started_at = datetime.fromisoformat(str(started["started_at_utc"]))
        started_stat = started_path.stat()
        result_stat = result_path.stat()
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise V4ActualPreparationGuardError(
            "G053_FLAT_SOURCE_EVIDENCE_INVALID"
        ) from error
    if (
        set(started)
        != {
            "generation_digest",
            "reviewed_files_digest",
            "started_at_utc",
            "status",
        }
        or set(result)
        != {
            "account_flat",
            "active_orders_count",
            "active_orders_zero",
            "broker_get_count",
            "broker_post_count",
            "broker_write",
            "identifier_exposed",
            "latest_executions_count",
            "open_positions_count",
            "raw_response_retained",
            "status",
        }
        or started_at.tzinfo is None
        or started_stat.st_uid != os.getuid()
        or result_stat.st_uid != os.getuid()
        or started_stat.st_nlink != 1
        or result_stat.st_nlink != 1
        or started_stat.st_mode & 0o777 != 0o600
        or result_stat.st_mode & 0o777 != 0o600
        or result_stat.st_mtime_ns < started_stat.st_mtime_ns
        or result_stat.st_mtime_ns - started_stat.st_mtime_ns
        > 300 * 1_000_000_000
        or abs(
            started_stat.st_mtime
            - started_at.astimezone(UTC).timestamp()
        )
        > 10
        or started.get("status") != "STARTED_NO_RETRY"
        or started.get("generation_digest")
        != _G052_FLAT_SOURCE_GENERATION_DIGEST
        or started.get("reviewed_files_digest")
        != _G052_FLAT_SOURCE_REVIEWED_FILES_DIGEST
        or result.get("status") != "G052_EMERGENCY_RECONCILIATION_KNOWN"
        or result.get("broker_get_count") != 3
        or result.get("open_positions_count") != 0
        or result.get("active_orders_count") != 0
        or result.get("account_flat") is not True
        or result.get("active_orders_zero") is not True
        or result.get("broker_write") is not False
        or result.get("broker_post_count") != 0
        or result.get("raw_response_retained") is not False
        or result.get("identifier_exposed") is not False
        or type(result.get("latest_executions_count")) is not int
        or result["latest_executions_count"] < 0
    ):
        raise V4ActualPreparationGuardError(
            "G053_FLAT_SOURCE_EVIDENCE_INVALID"
        )

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{database.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        generation_row = connection.execute(
            "SELECT value FROM metadata WHERE key='generation_digest'"
        ).fetchone()
        halt_row = connection.execute(
            "SELECT value FROM metadata WHERE key='unknown_halt_latched'"
        ).fetchone()
        pending_row = connection.execute(
            "SELECT 1 FROM metadata WHERE key='pending_transport_attempt'"
        ).fetchone()
        cycle_row = connection.execute(
            "SELECT COUNT(*) cycle_count,"
            "SUM(CASE WHEN realized_pnl_jpy IS NULL THEN 1 ELSE 0 END) "
            "unresolved_count FROM cycles"
        ).fetchone()
        attempt_rows = connection.execute(
            "SELECT action,COUNT(*) count FROM attempts "
            "GROUP BY action ORDER BY action"
        ).fetchall()
    except sqlite3.Error as error:
        raise V4ActualPreparationGuardError(
            "G053_FLAT_SOURCE_EVIDENCE_INVALID"
        ) from error
    finally:
        if connection is not None:
            connection.close()
    actual_attempts = {
        str(row["action"]): int(row["count"]) for row in attempt_rows
    }
    try:
        source_risk_state = PhaseBRiskStore(
            risk_path,
            policy=v4_gmo_risk_policy(),
        ).load()
    except Exception as error:
        raise V4ActualPreparationGuardError(
            "G053_FLAT_SOURCE_EVIDENCE_INVALID"
        ) from error
    if (
        generation_row is None
        or generation_row["value"] != _G052_FLAT_SOURCE_GENERATION_DIGEST
        or halt_row is None
        or halt_row["value"] != "true"
        or pending_row is not None
        or cycle_row is None
        or int(cycle_row["cycle_count"]) != 1
        or int(cycle_row["unresolved_count"] or 0) != 1
        or actual_attempts != {"MARKET_ENTRY": 1}
        or source_risk_state.current_day_jst
        != target_ledger._trading_day_jst
        or source_risk_state.entries_today != 2
    ):
        raise V4ActualPreparationGuardError(
            "G053_FLAT_SOURCE_EVIDENCE_INVALID"
        )
    return V4G053FlatOnlyCarryForwardEvidence(
        token=_G053_FLAT_CARRY_FORWARD_TOKEN,
        source_reviewed_files_digest=_G052_FLAT_SOURCE_REVIEWED_FILES_DIGEST,
        source_generation_digest=_G052_FLAT_SOURCE_GENERATION_DIGEST,
        target_reviewed_files_digest=(
            external_gate.reviewed_digest_for_internal_preparation_only()
        ),
        target_generation_digest=generation_digest,
        trading_day_jst=target_ledger._trading_day_jst,
        account_flat=True,
        active_orders_zero=True,
        source_unresolved_cycle_count=1,
        source_market_attempt_count=1,
        source_entries_today=2,
        source_halt_remains_latched=True,
    )


def _g053_flat_carry_forward_matches_target(
    *,
    evidence: V4G053FlatOnlyCarryForwardEvidence,
    reviewed_files_digest: str,
    generation_digest: str,
    trading_day_jst: str,
) -> bool:
    return (
        getattr(evidence, "_token", None) is _G053_FLAT_CARRY_FORWARD_TOKEN
        and evidence.source_reviewed_files_digest
        == _G052_FLAT_SOURCE_REVIEWED_FILES_DIGEST
        and evidence.source_generation_digest
        == _G052_FLAT_SOURCE_GENERATION_DIGEST
        and evidence.target_reviewed_files_digest == reviewed_files_digest
        and evidence.target_generation_digest == generation_digest
        and evidence.trading_day_jst == trading_day_jst
        and evidence.account_flat is True
        and evidence.active_orders_zero is True
        and evidence.source_unresolved_cycle_count == 1
        and evidence.source_market_attempt_count == 1
        and evidence.source_entries_today == 2
        and evidence.source_halt_remains_latched is True
        and evidence.broker_post_authorized is False
        and evidence.activation_permit_issued is False
        and bool(evidence) is False
    )


def require_g040_runtime_only_monitor_completion(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4RuntimeOnlyPreparationCarryForwardEvidence:
    evidence = load_g040_runtime_only_carry_forward_evidence(
        repository=repository,
        external_gate=external_gate,
        generation_digest=generation_digest,
        now_utc=now_utc,
    )
    ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=now_utc,
    )
    operation = V4PreparationOperation.MONITOR_LAUNCHAGENT
    if not ledger._marker_matches_review(
        ledger._marker(operation, "passed"),
        operation=operation,
        expected_status="PASSED",
    ):
        raise V4ActualPreparationGuardError(
            "G040_RUNTIME_MONITOR_NOT_COMPLETE"
        )
    return evidence


def require_g052_flat_only_monitor_completion(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4G052FlatOnlyCarryForwardEvidence:
    evidence = load_g052_flat_only_carry_forward_evidence(
        repository=repository,
        external_gate=external_gate,
        generation_digest=generation_digest,
        now_utc=now_utc,
    )
    ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=now_utc,
    )
    operation = V4PreparationOperation.MONITOR_LAUNCHAGENT
    if not ledger._marker_matches_review(
        ledger._marker(operation, "passed"),
        operation=operation,
        expected_status="PASSED",
    ):
        raise V4ActualPreparationGuardError(
            "G052_FLAT_ONLY_MONITOR_NOT_COMPLETE"
        )
    return evidence


def require_g053_flat_only_monitor_completion(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    now_utc: datetime | None = None,
) -> V4G053FlatOnlyCarryForwardEvidence:
    evidence = load_g053_flat_only_carry_forward_evidence(
        repository=repository,
        external_gate=external_gate,
        generation_digest=generation_digest,
        now_utc=now_utc,
    )
    ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=now_utc,
    )
    operation = V4PreparationOperation.MONITOR_LAUNCHAGENT
    if not ledger._marker_matches_review(
        ledger._marker(operation, "passed"),
        operation=operation,
        expected_status="PASSED",
    ):
        raise V4ActualPreparationGuardError(
            "G053_FLAT_ONLY_MONITOR_NOT_COMPLETE"
        )
    return evidence


def load_generation_completed_preparation_evidence(
    *,
    repository: Path,
    external_gate: V4ExternalPreparationGate,
    generation_digest: str,
    generation_label: str,
    now_utc: datetime | None = None,
) -> V4CompletedPreparationEvidence:
    """Mint exact one-use evidence from the generation's reviewed preparation lane."""

    current = (now_utc or datetime.now(UTC)).astimezone(UTC)
    if generation_label == _G052_TARGET_GENERATION_LABEL:
        require_g052_flat_only_monitor_completion(
            repository=repository,
            external_gate=external_gate,
            generation_digest=generation_digest,
            now_utc=current,
        )
    elif generation_label == _G053_TARGET_GENERATION_LABEL:
        require_g053_flat_only_monitor_completion(
            repository=repository,
            external_gate=external_gate,
            generation_digest=generation_digest,
            now_utc=current,
        )
    elif generation_label not in _RUNTIME_ONLY_TARGET_GENERATION_LABELS:
        return load_completed_preparation_evidence(
            external_gate=external_gate,
            generation_digest=generation_digest,
            now_utc=current,
        )
    else:
        require_g040_runtime_only_monitor_completion(
            repository=repository,
            external_gate=external_gate,
            generation_digest=generation_digest,
            now_utc=current,
        )
    ledger = V4PreparationAttemptLedger(
        external_gate=external_gate,
        now_utc=current,
    )
    normalized = generation_digest.removeprefix("sha256:")
    if not ledger.state_root.name.endswith(f"-{normalized}"):
        raise V4ActualPreparationGuardError(
            "PREPARATION_COMPLETED_GENERATION_MISMATCH"
        )
    consumed_marker = (
        ledger.state_root / f"generation_consumed.{ledger._trading_day_jst}.json"
    )
    if consumed_marker.exists() or consumed_marker.is_symlink():
        raise V4ActualPreparationGuardError(
            "PREPARATION_COMPLETED_EVIDENCE_INVALID"
        )
    return V4CompletedPreparationEvidence(
        token=_COMPLETED_EVIDENCE_TOKEN,
        generation_digest=generation_digest,
        state_root=ledger.state_root,
        trading_day_jst=ledger._trading_day_jst,
    )


def confirm_email_delivery_exact(
    *, phrase: str, operation_permit: V4PreparationOperationPermit
) -> V4OperatorConfirmationReport:
    validate_email_delivery_confirmation_exact(phrase=phrase)
    require_operation_permit(
        operation_permit,
        expected_operation=V4PreparationOperation.EMAIL_CONFIRMATION,
        claim=True,
    )
    report = V4OperatorConfirmationReport(
        confirmation_kind="EMAIL_DELIVERY_OPERATOR_CONFIRMATION",
        exact_match=True,
    )
    _attest_email_confirmation_success_internal(
        operation_permit, report.to_safe_dict()
    )
    return report


def validate_email_delivery_confirmation_exact(*, phrase: str) -> None:
    """Reject a public fixed-phrase mismatch before any ledger attempt begins."""

    if phrase != EMAIL_DELIVERY_CONFIRMATION:
        raise V4ActualPreparationGuardError("EMAIL_DELIVERY_CONFIRMATION_MISMATCH")


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
    try:
        return compute_reviewed_files_digest(repository=repository)
    except V4ReviewedDigestError as error:
        raise V4ActualPreparationGuardError(
            "PREPARATION_REVIEWED_FILE_INVALID"
        ) from error


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
