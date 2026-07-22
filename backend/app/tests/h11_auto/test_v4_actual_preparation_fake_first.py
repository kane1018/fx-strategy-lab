from __future__ import annotations

import inspect
import json
import smtplib
import subprocess
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.h11_auto import v4_actual_host_kill_rehearsal as host_rehearsal_module
from app.h11_auto import v4_actual_preparation_guard as guard_module
from app.h11_auto.v4_actual_host_kill_rehearsal import (
    V4ActualHostKillRehearsalError,
    run_actual_host_kill_rehearsal,
    run_readonly_network_time_preparation,
)
from app.h11_auto.v4_actual_preparation_guard import (
    EMAIL_DELIVERY_CONFIRMATION,
    EXCLUSIVITY_CONFIRMATION,
    V4ActualPreparationGuardError,
    V4ExternalPreparationGate,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    V4PreparationOperationPermit,
    _completion_digest,
    check_v4_keychain_access_internal_only,
    check_v4_keychain_presence_only,
    confirm_account_exclusivity_exact,
    confirm_email_delivery_exact,
    load_completed_preparation_evidence,
    load_external_preparation_gate,
    require_operation_permit,
)
from app.services import h11_v4_gmo_readonly_preflight as readonly_module
from app.services import h11_v4_notification_actual_preparation as notification_actual_module
from app.services.h11_v4_gmo_public_preflight import (
    V4GmoFinitePublicPreflight,
    V4GmoPublicPreflightError,
)
from app.services.h11_v4_gmo_readonly_preflight import (
    V4GmoFiniteReadOnlyPreflight,
    V4GmoReadOnlyPreflightError,
    V4GmoReadOnlySealedSecret,
)
from app.services.h11_v4_notification_actual_preparation import (
    H11V4ActualNotificationError,
    H11V4NotificationCredentialBundle,
    _SealedNotificationSecret,
    run_actual_pushover_rehearsal_once,
    run_actual_smtp_rehearsal_once,
)
from scripts import (
    h11_auto_v4_actual_host_kill_rehearsal as host_rehearsal_script,
)


@dataclass(frozen=True)
class FakeGmoCredentials:
    def unseal_for_internal_request_only(
        self,
    ) -> tuple[V4GmoReadOnlySealedSecret, V4GmoReadOnlySealedSecret]:
        return V4GmoReadOnlySealedSecret(
            "synthetic-key"
        ), V4GmoReadOnlySealedSecret("synthetic-secret")


class FakeTime:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakeSmtp:
    def __init__(self) -> None:
        self.tls = False
        self.logged_in = False
        self.sent = 0

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *args: object) -> None:
        del args

    def ehlo(self) -> tuple[int, bytes]:
        return 250, b"synthetic ok"

    def starttls(self, *, context: object) -> None:
        assert context is not None
        self.tls = True

    def login(self, user: str, password: str) -> None:
        assert user == "synthetic@example.invalid"
        assert password
        self.logged_in = True

    def send_message(self, message: object) -> None:
        assert message is not None
        self.sent += 1


class ForgedOperationPermit:
    def consume_for(self, operation: V4PreparationOperation) -> None:
        del operation


@pytest.fixture
def external_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> V4ExternalPreparationGate:
    digest = "sha256:" + "a" * 64
    artifact = {
        "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
        "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
        "broker_post_authorized": False,
        "activation_permit_issued": False,
        "reviewed_files_digest": digest,
        "generation_manifest_digest": "sha256:" + "b" * 64,
        "focused_tests_passed": True,
        "related_tests_passed": True,
        "ruff_passed": True,
        "diff_check_passed": True,
        "danger_scan_passed": True,
        "architecture_review_clear": True,
        "safety_review_clear": True,
        "operations_review_clear": True,
    }
    artifact_path = tmp_path / guard_module.PREPARATION_ARTIFACT
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    monkeypatch.setattr(
        guard_module,
        "reviewed_files_digest",
        lambda *, repository: digest,
    )
    monkeypatch.setattr(
        guard_module,
        "load_v4_gmo_frozen_generation",
        lambda *, repository, implementation_digest: type(
            "SyntheticGeneration", (), {"digest": "sha256:" + "b" * 64}
        )(),
    )
    monkeypatch.setattr(
        guard_module,
        "require_clean_main",
        lambda *, repository: object(),
    )
    return load_external_preparation_gate(repository=tmp_path)


def _permit_for(
    *,
    external_gate: V4ExternalPreparationGate,
    target: V4PreparationOperation,
) -> tuple[V4PreparationAttemptLedger, V4PreparationOperationPermit]:
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    for operation in V4PreparationOperation:
        permit = ledger.begin(operation)
        if operation is target:
            return ledger, permit
        _test_only_complete(ledger, permit, operation)
    raise AssertionError("target preparation operation was not found")


def _test_only_complete(
    ledger: V4PreparationAttemptLedger,
    permit: V4PreparationOperationPermit,
    operation: V4PreparationOperation,
) -> None:
    """Create synthetic predecessor proof only inside fake-first tests."""

    reports: dict[V4PreparationOperation, dict[str, object]] = {
        V4PreparationOperation.PRESENCE: {
            "total_required": 6,
            "present_count": 6,
            "all_present": True,
            "values_read": False,
        },
        V4PreparationOperation.KEYCHAIN_ACCESS: {
            "total_required": 6,
            "accessible_count": 6,
            "all_accessible": True,
            "credential_value_exposed": False,
        },
        V4PreparationOperation.PUSHOVER: {
            "pushover_application_send_count": 1,
            "pushover_accepted": True,
            "pushover_acknowledged": True,
            "broker_post_count": 0,
        },
        V4PreparationOperation.SMTP: {
            "email_send_count": 1,
            "email_smtp_accepted": True,
            "broker_post_count": 0,
        },
        V4PreparationOperation.EMAIL_CONFIRMATION: {
            "exact_match": True,
            "broker_post_authorized": False,
            "activation_permit_issued": False,
        },
        V4PreparationOperation.NETWORK_TIME: {
            "status": "PASSED_NETWORK_TIME_READ_ONLY_NO_BROKER_POST",
            "network_time_enabled": True,
            "administrator_prompt_used": True,
            "settings_changed": False,
            "broker_get_count": 0,
            "broker_post_count": 0,
        },
        V4PreparationOperation.HOST_KILL: {
            "status": "PASSED_TEST_ONLY",
            "disposable_coordinator_process_killed": True,
            "coordinator_pending_marker_restart_halt_observed": True,
            "persistent_kill_latched": True,
            "entry_blocked_after_reload": True,
            "broker_post_count": 0,
        },
        V4PreparationOperation.EXCLUSIVITY_CONFIRMATION: {
            "exact_match": True,
            "broker_post_authorized": False,
            "activation_permit_issued": False,
        },
        V4PreparationOperation.PUBLIC_GET: {
            "public_get_count": 2,
            "market_open": True,
            "ticker_symbol_match": True,
            "ticker_status_open": True,
            "quote_fresh": True,
            "spread_within_limit": True,
            "quote_age_seconds": 1.0,
            "spread_pips": "0.5",
            "raw_response_retained": False,
            "identifier_exposed": False,
            "broker_post_count": 0,
            "broker_write_performed": False,
        },
        V4PreparationOperation.PRIVATE_GET: {
            "broker_get_count": 3,
            "account_wide_snapshot_clear": True,
            "account_flat": True,
            "account_active_orders_zero": True,
            "cadence_offsets_seconds": (0.0, 0.25, 0.5),
            "broker_post_count": 0,
            "broker_write_performed": False,
        },
        V4PreparationOperation.MONITOR_LAUNCHAGENT: {
            "installed": True,
            "bootstrapped": True,
            "restarted": True,
            "service_running": True,
            "heartbeat_fresh": True,
            "heartbeat_generation_digest_match": True,
            "heartbeat_waiting_for_canonical_runtime": True,
            "heartbeat_broker_read": False,
            "heartbeat_broker_write": False,
            "actual_post_count": 0,
            "raw_output_retained": False,
            "previous_service_present": False,
            "previous_service_booted_out": False,
        },
    }
    require_operation_permit(
        permit,
        expected_operation=operation,
        claim=True,
    )
    # Test-only fixture construction. Production code has no generic report
    # attestation entrypoint; local code/filesystem tampering is outside the
    # clean-commit reviewed-digest runtime boundary.
    permit._completion_report = reports[operation]
    permit._completion_digest = _completion_digest(
        operation=operation,
        safe_report=reports[operation],
        reviewed_files_digest=permit._reviewed_files_digest,
        generation_digest=permit._generation_digest,
    )
    ledger.complete(operation, operation_permit=permit)


def test_public_preflight_uses_official_all_symbol_schema_and_is_one_use(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUBLIC_GET,
    )
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        assert request.method == "GET"
        assert request.url.query == b""
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        assert request.url.path == "/public/v1/ticker"
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "EUR_JPY",
                        "ask": "170.010",
                        "bid": "170.000",
                        "timestamp": "2026-07-17T00:00:00Z",
                        "status": "OPEN",
                    },
                    {
                        "symbol": "USD_JPY",
                        "ask": "160.005",
                        "bid": "160.000",
                        "timestamp": "2026-07-17T00:00:00Z",
                        "status": "OPEN",
                    },
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    preflight = V4GmoFinitePublicPreflight(
        external_gate=external_gate,
        operation_permit=permit,
        client=client,
        wall_clock=lambda: datetime(2026, 7, 17, 0, 0, 1, tzinfo=UTC),
    )
    report = preflight.run_once()
    assert report.public_get_count == 2
    assert report.market_open is True
    assert report.quote_fresh is True
    assert report.spread_within_limit is True
    assert report.spread_pips == "0.5"
    assert report.raw_response_retained is False
    assert requested_paths == ["/public/v1/status", "/public/v1/ticker"]
    ledger.complete(V4PreparationOperation.PUBLIC_GET, operation_permit=permit)
    with pytest.raises(V4GmoPublicPreflightError, match="SECOND_RUN"):
        preflight.run_once()
    client.close()


def test_public_preflight_fails_closed_when_usd_jpy_is_missing(
    external_gate: V4ExternalPreparationGate,
) -> None:
    _, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUBLIC_GET,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        return httpx.Response(200, json={"status": 0, "data": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(V4GmoPublicPreflightError, match="SYMBOL_INVALID"):
        V4GmoFinitePublicPreflight(
            external_gate=external_gate,
            operation_permit=permit,
            client=client,
            wall_clock=lambda: datetime(2026, 7, 17, tzinfo=UTC),
        ).run_once()
    client.close()


def test_public_preflight_does_not_pass_spread_above_g013_limit(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUBLIC_GET,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": "160.021",
                        "bid": "160.000",
                        "timestamp": "2026-07-17T00:00:00Z",
                        "status": "OPEN",
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report = V4GmoFinitePublicPreflight(
        external_gate=external_gate,
        operation_permit=permit,
        client=client,
        wall_clock=lambda: datetime(2026, 7, 17, 0, 0, 1, tzinfo=UTC),
    ).run_once()
    assert report.status == "BLOCKED_PUBLIC_STATUS_TICKER_NOT_CLEAR"
    assert report.spread_within_limit is False
    with pytest.raises(V4ActualPreparationGuardError):
        ledger.complete(V4PreparationOperation.PUBLIC_GET, operation_permit=permit)
    client.close()


def test_completed_preparation_evidence_requires_all_steps_and_is_one_use(
    external_gate: V4ExternalPreparationGate,
) -> None:
    generation_digest = "sha256:" + "b" * 64
    with pytest.raises(V4ActualPreparationGuardError, match="NOT_COMPLETE"):
        load_completed_preparation_evidence(
            external_gate=external_gate,
            generation_digest=generation_digest,
        )

    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    for operation in V4PreparationOperation:
        permit = ledger.begin(operation)
        _test_only_complete(ledger, permit, operation)

    evidence = load_completed_preparation_evidence(
        external_gate=external_gate,
        generation_digest=generation_digest,
    )
    second_preloaded = load_completed_preparation_evidence(
        external_gate=external_gate,
        generation_digest=generation_digest,
    )
    evidence.consume_for_generation(generation_digest)
    with pytest.raises(V4ActualPreparationGuardError, match="EVIDENCE_INVALID"):
        evidence.consume_for_generation(generation_digest)
    with pytest.raises(V4ActualPreparationGuardError, match="EVIDENCE_INVALID"):
        second_preloaded.consume_for_generation(generation_digest)
    with pytest.raises(V4ActualPreparationGuardError, match="EVIDENCE_INVALID"):
        load_completed_preparation_evidence(
            external_gate=external_gate,
            generation_digest=generation_digest,
        )


def test_marker_only_cannot_complete_any_preparation_operation(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    permit = ledger.begin(V4PreparationOperation.PRESENCE)
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        ledger.complete(
            V4PreparationOperation.PRESENCE,
            operation_permit=permit,
        )
    assert not hasattr(permit, "consume_for")


def test_presence_only_check_never_requests_keychain_value(
    monkeypatch: pytest.MonkeyPatch,
    external_gate: V4ExternalPreparationGate,
) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="discarded", stderr="discarded")

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PRESENCE,
    )
    report = check_v4_keychain_presence_only(
        operation_permit=operation_permit,
        runner=runner,
    )
    assert report.all_present is True
    assert report.present_count == 6
    assert report.values_read is False
    assert all("-w" not in command and "-g" not in command for command in commands)


def test_keychain_access_check_reads_internal_values_with_long_prompt_window(
    monkeypatch: pytest.MonkeyPatch,
    external_gate: V4ExternalPreparationGate,
) -> None:
    calls: list[tuple[list[str], float]] = []

    def runner(
        command: list[str], timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, timeout_seconds))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="synthetic-secret-never-reported\n",
            stderr="",
        )

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.KEYCHAIN_ACCESS,
    )
    report = check_v4_keychain_access_internal_only(
        operation_permit=operation_permit,
        runner=runner,
        clock=iter((0.0, 0.0, 10.0, 20.0, 30.0, 40.0, 50.0)).__next__,
    )

    assert report.total_required == 6
    assert report.accessible_count == 6
    assert report.all_accessible is True
    assert report.values_read_internal is True
    assert report.credential_value_exposed is False
    assert "synthetic-secret-never-reported" not in repr(report)
    assert len(calls) == 6
    assert [timeout for _, timeout in calls] == [300.0, 290.0, 280.0, 270.0, 260.0, 250.0]
    assert all("-w" in command and "-g" not in command for command, _ in calls)


def test_keychain_timeout_does_not_retain_partial_secret_in_exception_chain(
    monkeypatch: pytest.MonkeyPatch,
    external_gate: V4ExternalPreparationGate,
) -> None:
    partial_secret = "synthetic-partial-secret-never-retained"

    def runner(
        command: list[str], timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command,
            timeout_seconds,
            output=partial_secret,
            stderr=partial_secret,
        )

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.KEYCHAIN_ACCESS,
    )

    with pytest.raises(V4ActualPreparationGuardError) as captured:
        check_v4_keychain_access_internal_only(
            operation_permit=operation_permit,
            runner=runner,
            clock=iter((0.0, 0.0)).__next__,
        )

    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert partial_secret not in repr(captured.value)


def test_keychain_access_uses_one_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
    external_gate: V4ExternalPreparationGate,
) -> None:
    calls = 0

    def runner(
        command: list[str], timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, 0, stdout="synthetic\n", stderr="")

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.KEYCHAIN_ACCESS,
    )

    with pytest.raises(
        V4ActualPreparationGuardError,
        match="PREPARATION_KEYCHAIN_ACCESS_FAILED",
    ):
        check_v4_keychain_access_internal_only(
            operation_permit=operation_permit,
            runner=runner,
            timeout_seconds=30.0,
            clock=iter((0.0, 0.0, 31.0)).__next__,
        )

    assert calls == 1


def test_new_digest_generation_preserves_legacy_no_retry_markers(
    tmp_path: Path,
    external_gate: V4ExternalPreparationGate,
) -> None:
    legacy_root = tmp_path / guard_module.PREPARATION_STATE_RELATIVE
    legacy_root.mkdir(parents=True, exist_ok=True)
    legacy_marker = legacy_root / "10_notification.started.json"
    legacy_marker.write_text("legacy marker retained\n", encoding="utf-8")

    ledger = V4PreparationAttemptLedger(external_gate=external_gate)

    assert ledger.state_root.parent == legacy_root
    assert ledger.state_root.name == f"generation-{'a' * 64}-{'b' * 64}"
    assert legacy_marker.read_text(encoding="utf-8") == "legacy marker retained\n"


def test_actual_keychain_readers_allow_interactive_prompt_time() -> None:
    access_rehearsal_default = inspect.signature(
        check_v4_keychain_access_internal_only
    ).parameters["timeout_seconds"].default
    notification_default = inspect.signature(
        notification_actual_module.read_notification_keychain_secret
    ).parameters["timeout_seconds"].default
    private_get_default = inspect.signature(
        readonly_module.read_v4_gmo_readonly_keychain_secret
    ).parameters["timeout_seconds"].default
    assert access_rehearsal_default == 300.0
    assert notification_default == 120.0
    assert private_get_default == 120.0


def test_actual_external_functions_reject_unreviewed_direct_calls(tmp_path: Path) -> None:
    with pytest.raises(V4ActualPreparationGuardError, match="EXTERNAL_GATE_INVALID"):
        V4GmoFiniteReadOnlyPreflight(
            external_gate=object(),  # type: ignore[arg-type]
            operation_permit=object(),  # type: ignore[arg-type]
        )


def test_actual_external_functions_reject_forged_operation_permit(
    external_gate: V4ExternalPreparationGate,
) -> None:
    forged = ForgedOperationPermit()
    commands: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        check_v4_keychain_presence_only(
            operation_permit=forged,  # type: ignore[arg-type]
            runner=runner,
        )
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        run_actual_pushover_rehearsal_once(
            external_gate=external_gate,
            operation_permit=forged,  # type: ignore[arg-type]
        )
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        run_actual_smtp_rehearsal_once(
            external_gate=external_gate,
            operation_permit=forged,  # type: ignore[arg-type]
        )
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        run_actual_host_kill_rehearsal(
            external_gate=external_gate,
            operation_permit=forged,  # type: ignore[arg-type]
            cycle_day_jst="2026-07-16",
        )
    preflight = V4GmoFiniteReadOnlyPreflight(
        external_gate=external_gate,
        operation_permit=forged,  # type: ignore[arg-type]
    )
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        preflight.run_once()
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        confirm_email_delivery_exact(
            phrase=EMAIL_DELIVERY_CONFIRMATION,
            operation_permit=forged,  # type: ignore[arg-type]
        )
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        confirm_account_exclusivity_exact(
            phrase=EXCLUSIVITY_CONFIRMATION,
            operation_permit=forged,  # type: ignore[arg-type]
        )
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    ledger.begin(V4PreparationOperation.PRESENCE)
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        ledger.complete(
            V4PreparationOperation.PRESENCE,
            operation_permit=forged,  # type: ignore[arg-type]
        )
    assert commands == []


def test_external_preparation_paths_do_not_accept_arbitrary_state_roots() -> None:
    assert "state_root" not in inspect.signature(
        V4PreparationAttemptLedger
    ).parameters
    assert "state_dir" not in inspect.signature(
        run_actual_host_kill_rehearsal
    ).parameters
    with pytest.raises(V4ActualPreparationGuardError, match="EXTERNAL_GATE_INVALID"):
        run_actual_pushover_rehearsal_once(
            external_gate=object(),  # type: ignore[arg-type]
            operation_permit=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(V4ActualPreparationGuardError, match="EXTERNAL_GATE_INVALID"):
        run_actual_smtp_rehearsal_once(
            external_gate=object(),  # type: ignore[arg-type]
            operation_permit=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(V4ActualPreparationGuardError, match="EXTERNAL_GATE_INVALID"):
        run_actual_host_kill_rehearsal(
            external_gate=object(),  # type: ignore[arg-type]
            operation_permit=object(),  # type: ignore[arg-type]
            cycle_day_jst="2026-07-16",
        )


def test_review_artifact_digest_mismatch_blocks_external_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_path = tmp_path / guard_module.PREPARATION_ARTIFACT
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "schema": "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1",
                "status": "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST",
                "broker_post_authorized": False,
                "activation_permit_issued": False,
                "reviewed_files_digest": "sha256:" + "a" * 64,
                "focused_tests_passed": True,
                "related_tests_passed": True,
                "ruff_passed": True,
                "diff_check_passed": True,
                "danger_scan_passed": True,
                "architecture_review_clear": True,
                "safety_review_clear": True,
                "operations_review_clear": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        guard_module,
        "reviewed_files_digest",
        lambda *, repository: "sha256:" + "b" * 64,
    )
    monkeypatch.setattr(
        guard_module,
        "require_clean_main",
        lambda *, repository: object(),
    )
    with pytest.raises(V4ActualPreparationGuardError, match="DIGEST_MISMATCH"):
        load_external_preparation_gate(repository=tmp_path)


def test_actual_pushover_rehearsal_uses_one_send_and_ack_poll(
    external_gate: V4ExternalPreparationGate,
) -> None:
    reads: list[tuple[str, str]] = []

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        reads.append((service, account))
        values = {
            "pushover-api-token": "synthetic-token",
            "pushover-user-key": "synthetic-user",
        }
        return _SealedNotificationSecret(values[account])

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json={"status": 1, "receipt": "synthetic-receipt"})
        return httpx.Response(200, json={"status": 1, "acknowledged": 1, "expired": 0})

    fake_time = FakeTime()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUSHOVER,
    )
    report = run_actual_pushover_rehearsal_once(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credentials=H11V4NotificationCredentialBundle(reader=reader),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        acknowledgement_timeout_seconds=15,
        receipt_poll_interval_seconds=5,
        monotonic_factory=fake_time.monotonic,
        sleep=fake_time.sleep,
    )
    assert len(reads) == 2
    assert calls == [
        ("POST", "/1/messages.json"),
        ("GET", "/1/receipts/synthetic-receipt.json"),
    ]
    assert report.pushover_application_send_count == 1
    assert report.pushover_acknowledged is True
    assert report.external_notification_send_count == 1
    assert report.broker_post_count == 0


def test_actual_smtp_rehearsal_uses_one_send_and_two_credentials(
    external_gate: V4ExternalPreparationGate,
) -> None:
    reads: list[tuple[str, str]] = []

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        reads.append((service, account))
        values = {
            "smtp-username": "synthetic@example.invalid",
            "smtp-app-password": "synthetic-app-password",
        }
        return _SealedNotificationSecret(values[account])

    smtp = FakeSmtp()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.SMTP,
    )
    report = run_actual_smtp_rehearsal_once(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credentials=H11V4NotificationCredentialBundle(reader=reader),
        smtp_factory=lambda host, port, timeout: smtp,
    )

    assert len(reads) == 2
    assert report.email_send_count == 1
    assert report.email_smtp_accepted is True
    assert report.email_delivery_operator_confirmed is False
    assert report.external_notification_send_count == 1
    assert report.broker_post_count == 0
    assert smtp.tls is True and smtp.logged_in is True and smtp.sent == 1


def test_smtp_tls_uses_certifi_ca_bundle(
    external_gate: V4ExternalPreparationGate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "smtp-username": "synthetic@example.invalid",
        "smtp-app-password": "synthetic-app-password",
    }
    captured: dict[str, object] = {}

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    def fake_create_default_context(*, cafile: str) -> object:
        captured["cafile"] = cafile
        return object()

    monkeypatch.setattr(
        notification_actual_module.certifi,
        "where",
        lambda: "/synthetic/certifi-ca.pem",
    )
    monkeypatch.setattr(
        notification_actual_module.ssl,
        "create_default_context",
        fake_create_default_context,
    )
    smtp = FakeSmtp()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.SMTP,
    )
    report = run_actual_smtp_rehearsal_once(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credentials=H11V4NotificationCredentialBundle(reader=reader),
        smtp_factory=lambda host, port, timeout: smtp,
    )

    assert captured == {"cafile": "/synthetic/certifi-ca.pem"}
    assert smtp.tls is True
    assert report.email_smtp_accepted is True


def test_pushover_default_ack_window_is_fifteen_minutes() -> None:
    signature = inspect.signature(run_actual_pushover_rehearsal_once)
    assert signature.parameters["acknowledgement_timeout_seconds"].default == 900.0
    assert signature.parameters["receipt_poll_interval_seconds"].default == 10.0


def test_notification_routes_are_structurally_separate() -> None:
    pushover_signature = inspect.signature(run_actual_pushover_rehearsal_once)
    smtp_signature = inspect.signature(run_actual_smtp_rehearsal_once)
    assert "smtp_factory" not in pushover_signature.parameters
    assert "http_client" not in smtp_signature.parameters
    assert "sleep" not in smtp_signature.parameters


def test_pushover_ack_poll_does_not_cross_total_deadline(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "pushover-api-token": "synthetic-token",
        "pushover-user-key": "synthetic-user",
    }

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    get_times: list[float] = []
    fake_time = FakeTime()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"status": 1, "receipt": "synthetic-receipt"},
            )
        get_times.append(fake_time.value)
        return httpx.Response(
            200,
            json={"status": 1, "acknowledged": 0, "expired": 0},
        )

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUSHOVER,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="PUSHOVER_ACK_NOT_CONFIRMED_NO_RETRY",
    ):
        run_actual_pushover_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            acknowledgement_timeout_seconds=15,
            receipt_poll_interval_seconds=10,
            monotonic_factory=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
    assert get_times == [10.0]
    assert fake_time.value == 15.0


def test_pushover_receipt_not_found_is_pending_within_ack_window(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "pushover-api-token": "synthetic-token",
        "pushover-user-key": "synthetic-user",
    }
    fake_time = FakeTime()
    receipt_get_count = 0

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal receipt_get_count
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"status": 1, "receipt": "synthetic-receipt"},
            )
        receipt_get_count += 1
        if receipt_get_count == 1:
            return httpx.Response(404, json={"status": 0})
        return httpx.Response(
            200,
            json={"status": 1, "acknowledged": 1, "expired": 0},
        )

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUSHOVER,
    )
    report = run_actual_pushover_rehearsal_once(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credentials=H11V4NotificationCredentialBundle(reader=reader),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        acknowledgement_timeout_seconds=15,
        receipt_poll_interval_seconds=5,
        monotonic_factory=fake_time.monotonic,
        sleep=fake_time.sleep,
    )
    assert receipt_get_count == 2
    assert report.pushover_application_send_count == 1
    assert report.pushover_acknowledged is True
    assert report.broker_post_count == 0


def test_pushover_receipt_non_404_failure_stops_without_second_get(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "pushover-api-token": "synthetic-token",
        "pushover-user-key": "synthetic-user",
    }
    receipt_get_count = 0
    fake_time = FakeTime()

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal receipt_get_count
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"status": 1, "receipt": "synthetic-receipt"},
            )
        receipt_get_count += 1
        return httpx.Response(400, json={"status": 0})

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUSHOVER,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="PUSHOVER_RECEIPT_REJECTED_NO_RETRY",
    ):
        run_actual_pushover_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            acknowledgement_timeout_seconds=15,
            receipt_poll_interval_seconds=5,
            monotonic_factory=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
    assert receipt_get_count == 1


def test_pushover_ack_returned_after_deadline_is_not_accepted(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "pushover-api-token": "synthetic-token",
        "pushover-user-key": "synthetic-user",
    }
    fake_time = FakeTime()

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                200,
                json={"status": 1, "receipt": "synthetic-receipt"},
            )
        fake_time.value = 16.0
        return httpx.Response(
            200,
            json={"status": 1, "acknowledged": 1, "expired": 0},
        )

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUSHOVER,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="PUSHOVER_ACK_NOT_CONFIRMED_NO_RETRY",
    ):
        run_actual_pushover_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            acknowledgement_timeout_seconds=15,
            receipt_poll_interval_seconds=10,
            monotonic_factory=fake_time.monotonic,
            sleep=fake_time.sleep,
        )
    assert fake_time.value == 16.0


def test_private_get_preflight_is_three_gets_spaced_and_single_use(
    external_gate: V4ExternalPreparationGate,
) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, dict(request.url.params)))
        rows = [] if request.url.path != "/private/v1/latestExecutions" else [{"x": 1}]
        return httpx.Response(200, json={"status": 0, "data": {"list": rows}})

    fake_time = FakeTime()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PRIVATE_GET,
    )
    preflight = V4GmoFiniteReadOnlyPreflight(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credential_pair=FakeGmoCredentials(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        monotonic_factory=fake_time.monotonic,
        sleep=fake_time.sleep,
    )
    report = preflight.run_once()
    assert calls == [
        (
            "GET",
            "/private/v1/latestExecutions",
            {"symbol": "USD_JPY", "count": "100"},
        ),
        ("GET", "/private/v1/openPositions", {"count": "100"}),
        ("GET", "/private/v1/activeOrders", {"count": "100"}),
    ]
    assert report.cadence_offsets_seconds == (0.0, 0.25, 0.5)
    assert report.account_flat is True
    assert report.account_active_orders_zero is True
    assert report.account_wide_snapshot_clear is True
    assert report.canary_preflight_clear is False
    assert report.broker_post_count == 0
    with pytest.raises(V4GmoReadOnlyPreflightError, match="SECOND_RUN_FORBIDDEN"):
        preflight.run_once()


@pytest.mark.parametrize(
    "occupied_path",
    ("/private/v1/openPositions", "/private/v1/activeOrders"),
)
def test_private_get_preflight_account_wide_nonzero_fails_closed(
    external_gate: V4ExternalPreparationGate,
    occupied_path: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        rows = [{"redacted": True}] if request.url.path == occupied_path else []
        return httpx.Response(200, json={"status": 0, "data": {"list": rows}})

    fake_time = FakeTime()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PRIVATE_GET,
    )
    report = V4GmoFiniteReadOnlyPreflight(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credential_pair=FakeGmoCredentials(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        monotonic_factory=fake_time.monotonic,
        sleep=fake_time.sleep,
    ).run_once()
    assert report.account_wide_snapshot_clear is False
    assert report.canary_preflight_clear is False
    assert report.broker_post_count == 0


def test_readonly_preflight_source_has_no_broker_post_route() -> None:
    source = inspect.getsource(readonly_module)
    for marker in (
        'method="POST"',
        '"/private/v1/order"',
        '"/private/v1/cancelOrders"',
        '"/private/v1/closeOrder"',
        "assert_real_broker_post_allowed",
        "V4GmoActualActivationPermit",
    ):
        assert marker not in source
    assert "h11_v4_gmo_actual_transport" not in source


def test_operation_attesters_are_confined_to_their_fixed_steps() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    allowed_by_marker = {
        "_attest_presence_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py"
        },
        "_attest_keychain_access_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py"
        },
        "_attest_email_confirmation_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py"
        },
        "_attest_exclusivity_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py"
        },
        "_attest_pushover_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py",
            "app/services/h11_v4_notification_actual_preparation.py",
        },
        "_attest_smtp_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py",
            "app/services/h11_v4_notification_actual_preparation.py",
        },
        "_attest_host_kill_success_" + "internal": {
            "app/h11_auto/v4_actual_host_kill_rehearsal.py",
            "app/h11_auto/v4_actual_preparation_guard.py",
        },
        "_attest_private_get_success_" + "internal": {
            "app/h11_auto/v4_actual_preparation_guard.py",
            "app/services/h11_v4_gmo_readonly_preflight.py",
        },
    }
    for marker, allowed in allowed_by_marker.items():
        references = {
            path.relative_to(backend_root).as_posix()
            for path in backend_root.rglob("*.py")
            if marker in path.read_text(encoding="utf-8")
        }
        assert references == allowed
    for marker in (
        "_bind_fixed_operation_" + "attestation",
        "_attest_operation_" + "success",
        "_OPERATION_ATTESTATION_" + "ISSUERS",
    ):
        references = {
            path.relative_to(backend_root).as_posix()
            for path in backend_root.rglob("*.py")
            if marker in path.read_text(encoding="utf-8")
        }
        assert references == {"app/h11_auto/v4_actual_preparation_guard.py"}


def test_private_get_inter_request_cadence_uses_actual_request_start_time(
    external_gate: V4ExternalPreparationGate,
) -> None:
    fake_time = FakeTime()
    request_starts: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_starts.append(fake_time.value)
        if len(request_starts) == 1:
            fake_time.value += 1.0
        return httpx.Response(200, json={"status": 0, "data": {"list": []}})

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PRIVATE_GET,
    )
    report = V4GmoFiniteReadOnlyPreflight(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credential_pair=FakeGmoCredentials(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        monotonic_factory=fake_time.monotonic,
        sleep=fake_time.sleep,
    ).run_once()
    assert request_starts == [0.0, 1.0, 1.25]
    assert report.cadence_offsets_seconds == (0.0, 1.0, 1.25)


def test_private_get_cadence_fails_closed_when_sleep_does_not_advance_clock(
    external_gate: V4ExternalPreparationGate,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": 0, "data": {"list": []}})

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PRIVATE_GET,
    )
    with pytest.raises(V4GmoReadOnlyPreflightError, match="CADENCE_NOT_REACHED"):
        V4GmoFiniteReadOnlyPreflight(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credential_pair=FakeGmoCredentials(),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            monotonic_factory=lambda: 0.0,
            sleep=lambda _seconds: None,
        ).run_once()
    assert calls == ["/private/v1/latestExecutions"]


def test_pushover_failure_does_not_attempt_smtp_and_does_not_leak(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "pushover-api-token": "secret-token-marker",
        "pushover-user-key": "secret-user-marker",
    }

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic network failure", request=request)

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUSHOVER,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="PUSHOVER_NETWORK_FAILED_NO_RETRY",
    ) as exc_info:
        run_actual_pushover_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    rendered = "".join(
        traceback.format_exception(
            exc_info.type,
            exc_info.value,
            exc_info.tb,
        )
    )
    for marker in values.values():
        assert marker not in rendered


def test_smtp_auth_failure_is_safely_classified_without_secret(
    external_gate: V4ExternalPreparationGate,
) -> None:
    secret_marker = "smtp-secret-never-rendered"

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        value = "synthetic@example.invalid" if account == "smtp-username" else secret_marker
        return _SealedNotificationSecret(value)

    class AuthFailingSmtp(FakeSmtp):
        def login(self, user: str, password: str) -> None:
            del user, password
            raise smtplib.SMTPAuthenticationError(535, b"provider detail hidden")

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.SMTP,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="SMTP_AUTH_FAILED_NO_RETRY",
    ) as exc_info:
        run_actual_smtp_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            smtp_factory=lambda host, port, timeout: AuthFailingSmtp(),
        )
    rendered = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert secret_marker not in rendered
    assert "provider detail hidden" not in rendered


def test_smtp_recipient_failure_is_safely_classified(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "smtp-username": "synthetic@example.invalid",
        "smtp-app-password": "synthetic-password",
    }

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    class RecipientFailingSmtp(FakeSmtp):
        def send_message(self, message: object) -> dict[str, tuple[int, bytes]]:
            del message
            return {"opaque": (550, b"hidden")}

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.SMTP,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="SMTP_RECIPIENT_FAILED_NO_RETRY",
    ):
        run_actual_smtp_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            smtp_factory=lambda host, port, timeout: RecipientFailingSmtp(),
        )


def test_smtp_ehlo_non_250_is_safely_classified(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "smtp-username": "synthetic@example.invalid",
        "smtp-app-password": "synthetic-password",
    }

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    class EhloFailingSmtp(FakeSmtp):
        def ehlo(self) -> tuple[int, bytes]:
            return 550, b"hidden"

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.SMTP,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="SMTP_EHLO_FAILED_NO_RETRY",
    ):
        run_actual_smtp_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            smtp_factory=lambda host, port, timeout: EhloFailingSmtp(),
        )


def test_smtp_recipient_exception_is_safely_classified(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "smtp-username": "synthetic@example.invalid",
        "smtp-app-password": "synthetic-password",
    }

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    class RecipientExceptionSmtp(FakeSmtp):
        def send_message(self, message: object) -> None:
            del message
            raise smtplib.SMTPRecipientsRefused(
                {"opaque@example.invalid": (550, b"hidden")}
            )

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.SMTP,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="SMTP_RECIPIENT_FAILED_NO_RETRY",
    ):
        run_actual_smtp_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            smtp_factory=lambda host, port, timeout: RecipientExceptionSmtp(),
        )


def test_persistent_preparation_ledger_enforces_order_and_no_retry(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    with pytest.raises(V4ActualPreparationGuardError, match="PREVIOUS_NOT_CLEAR"):
        ledger.begin(V4PreparationOperation.PUSHOVER)
    presence_permit = ledger.begin(V4PreparationOperation.PRESENCE)
    with pytest.raises(V4ActualPreparationGuardError, match="ALREADY_ATTEMPTED"):
        V4PreparationAttemptLedger(external_gate=external_gate).begin(
            V4PreparationOperation.PRESENCE,
        )
    _test_only_complete(
        ledger, presence_permit, V4PreparationOperation.PRESENCE
    )
    with pytest.raises(V4ActualPreparationGuardError, match="PREVIOUS_NOT_CLEAR"):
        ledger.begin(V4PreparationOperation.PUSHOVER)
    access_permit = ledger.begin(V4PreparationOperation.KEYCHAIN_ACCESS)
    _test_only_complete(
        ledger, access_permit, V4PreparationOperation.KEYCHAIN_ACCESS
    )
    pushover_permit = ledger.begin(V4PreparationOperation.PUSHOVER)
    _test_only_complete(
        ledger, pushover_permit, V4PreparationOperation.PUSHOVER
    )
    ledger.begin(V4PreparationOperation.SMTP)


def test_preparation_ledger_rejects_predecessor_from_other_review_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    permit = ledger.begin(V4PreparationOperation.PRESENCE)
    _test_only_complete(ledger, permit, V4PreparationOperation.PRESENCE)

    artifact_path = tmp_path / guard_module.PREPARATION_ARTIFACT
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    digest_b = "sha256:" + "b" * 64
    artifact["reviewed_files_digest"] = digest_b
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    monkeypatch.setattr(
        guard_module,
        "reviewed_files_digest",
        lambda *, repository: digest_b,
    )
    gate_b = load_external_preparation_gate(repository=tmp_path)
    with pytest.raises(V4ActualPreparationGuardError, match="PREVIOUS_NOT_CLEAR"):
        V4PreparationAttemptLedger(external_gate=gate_b).begin(
            V4PreparationOperation.PUSHOVER
        )


def test_exact_operator_confirmations_do_not_authorize_broker_post(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger, email_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.EMAIL_CONFIRMATION,
    )
    email = confirm_email_delivery_exact(
        phrase=EMAIL_DELIVERY_CONFIRMATION,
        operation_permit=email_permit,
    )
    ledger.complete(
        V4PreparationOperation.EMAIL_CONFIRMATION,
        operation_permit=email_permit,
    )
    network_time_permit = ledger.begin(V4PreparationOperation.NETWORK_TIME)
    _test_only_complete(
        ledger,
        network_time_permit,
        V4PreparationOperation.NETWORK_TIME,
    )
    host_permit = ledger.begin(V4PreparationOperation.HOST_KILL)
    _test_only_complete(
        ledger, host_permit, V4PreparationOperation.HOST_KILL
    )
    exclusivity_permit = ledger.begin(
        V4PreparationOperation.EXCLUSIVITY_CONFIRMATION
    )
    exclusive = confirm_account_exclusivity_exact(
        phrase=EXCLUSIVITY_CONFIRMATION,
        operation_permit=exclusivity_permit,
    )
    assert email.exact_match is True
    assert exclusive.exact_match is True
    assert email.broker_post_authorized is False
    assert exclusive.activation_permit_issued is False


def test_current_host_kill_rehearsal_kills_only_disposable_child_and_latches(
    external_gate: V4ExternalPreparationGate,
) -> None:
    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command == ["pmset", "-g", "batt"]:
            return subprocess.CompletedProcess(command, 0, stdout="Now drawing from 'AC Power'\n")
        if command[0] == "/usr/bin/sntp":
            return subprocess.CompletedProcess(command, 0, stdout="+0.125 +/- 0.010\n")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="Network Time: On\n",
        )

    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.HOST_KILL,
    )
    report = run_actual_host_kill_rehearsal(
        external_gate=external_gate,
        operation_permit=operation_permit,
        cycle_day_jst="2026-07-16",
        command_runner=runner,
    )
    assert report.disposable_process_sigkill_observed is True
    assert report.persistent_kill_latched is True
    assert report.entry_blocked_after_reload is True
    assert report.clock_probe_succeeded is True
    assert report.absolute_clock_skew_seconds == 0.125
    assert report.clock_skew_within_five_seconds is True
    assert report.network_time_admin_fallback_used is False
    assert report.actual_runtime_process_killed is False
    assert report.disposable_coordinator_process_killed is True
    assert report.coordinator_pending_marker_restart_halt_observed is True
    assert report.broker_post_count == 0


def test_host_rehearsal_on_battery_stops_before_admin_clock_or_kill(
    external_gate: V4ExternalPreparationGate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command == ["pmset", "-g", "batt"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="Now drawing from 'Battery Power'\n",
            )
        raise AssertionError("no probe may run after AC precondition fails")

    def admin_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        del command
        raise AssertionError("admin fallback must not run on battery")

    monkeypatch.setattr(host_rehearsal_module.platform, "system", lambda: "Darwin")
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.HOST_KILL,
    )
    report = run_actual_host_kill_rehearsal(
        external_gate=external_gate,
        operation_permit=operation_permit,
        cycle_day_jst="2026-07-16",
        command_runner=runner,
        admin_command_runner=admin_runner,
    )

    assert report.status == "BLOCKED_CURRENT_HOST_AC_POWER_NOT_CLEAR"
    assert report.external_power_connected is False
    assert report.network_time_admin_fallback_used is False
    assert report.disposable_process_started is False
    assert report.actual_runtime_process_killed is False
    assert calls == [["pmset", "-g", "batt"]]


def test_network_time_state_uses_fixed_admin_readonly_fallback() -> None:
    direct_calls: list[list[str]] = []
    admin_calls: list[list[str]] = []

    def direct_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        direct_calls.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="")

    def admin_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        admin_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Network Time: On\n")

    state, fallback_used = host_rehearsal_module._network_time_state(
        direct_runner,
        admin_runner,
    )

    assert state is True
    assert fallback_used is True
    assert direct_calls == [["/usr/sbin/systemsetup", "-getusingnetworktime"]]
    assert admin_calls == [
        [
            "/usr/bin/osascript",
            "-e",
            'do shell script "/usr/sbin/systemsetup -getusingnetworktime" '
            "with administrator privileges",
        ]
    ]


def test_network_time_preparation_is_separate_generation_bound_operation(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.NETWORK_TIME,
    )
    calls: list[list[str]] = []

    def admin_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "Network Time: On\n", "")

    report = run_readonly_network_time_preparation(
        external_gate=external_gate,
        operation_permit=permit,
        admin_command_runner=admin_runner,
    )

    assert report.status == "PASSED_NETWORK_TIME_READ_ONLY_NO_BROKER_POST"
    assert report.network_time_enabled is True
    assert report.settings_changed is False
    assert report.broker_post_count == 0
    assert calls == [list(host_rehearsal_module._ADMIN_NETWORK_TIME_COMMAND)]
    ledger.complete(V4PreparationOperation.NETWORK_TIME, operation_permit=permit)


def test_network_time_preparation_off_cannot_complete(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.NETWORK_TIME,
    )
    report = run_readonly_network_time_preparation(
        external_gate=external_gate,
        operation_permit=permit,
        admin_command_runner=lambda command: subprocess.CompletedProcess(
            command, 0, "Network Time: Off\n", ""
        ),
    )

    assert report.status == "BLOCKED_NETWORK_TIME_READ_ONLY_NOT_CLEAR"
    with pytest.raises(V4ActualPreparationGuardError, match="PERMIT_INVALID"):
        ledger.complete(V4PreparationOperation.NETWORK_TIME, operation_permit=permit)


def test_host_script_uses_only_prechecked_network_time_result() -> None:
    result = host_rehearsal_script._prechecked_network_time_result(
        list(host_rehearsal_module._ADMIN_NETWORK_TIME_COMMAND)
    )
    assert result.returncode == 0
    assert result.stdout == "Network Time: On\n"
    with pytest.raises(V4ActualHostKillRehearsalError, match="FORBIDDEN"):
        host_rehearsal_script._prechecked_network_time_result(
            ["/usr/sbin/systemsetup", "-setusingnetworktime", "on"]
        )


def test_network_time_state_falls_back_when_unprivileged_probe_exits_zero_with_error() -> None:
    admin_calls: list[list[str]] = []

    def direct_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="You need administrator access to run this tool... exiting!\n",
        )

    def admin_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        admin_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Network Time: On\n")

    state, fallback_used = host_rehearsal_module._network_time_state(
        direct_runner,
        admin_runner,
    )

    assert state is True
    assert fallback_used is True
    assert admin_calls == [list(host_rehearsal_module._ADMIN_NETWORK_TIME_COMMAND)]


@pytest.mark.parametrize("misleading_output", ("permission\n", "cutoff\n"))
def test_network_time_state_does_not_accept_error_suffixes(
    misleading_output: str,
) -> None:
    admin_calls: list[list[str]] = []

    def direct_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=misleading_output)

    def admin_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        admin_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Network Time: Off\n")

    state, fallback_used = host_rehearsal_module._network_time_state(
        direct_runner,
        admin_runner,
    )

    assert state is False
    assert fallback_used is True
    assert admin_calls == [list(host_rehearsal_module._ADMIN_NETWORK_TIME_COMMAND)]


def test_network_time_state_skips_admin_when_direct_probe_is_clear() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Network Time: On\n")

    def forbidden_admin_runner(
        command: list[str],
    ) -> subprocess.CompletedProcess[str]:
        del command
        raise AssertionError("admin fallback must not run")

    state, fallback_used = host_rehearsal_module._network_time_state(
        runner,
        forbidden_admin_runner,
    )

    assert state is True
    assert fallback_used is False
    assert calls == [["/usr/sbin/systemsetup", "-getusingnetworktime"]]


def test_host_command_runners_use_separate_finite_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[tuple[str, ...], float]] = []

    def fake_run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert check is False
        observed.append((tuple(command), timeout))
        return subprocess.CompletedProcess(command, 0, stdout="Network Time: On\n")

    monkeypatch.setattr(host_rehearsal_module.subprocess, "run", fake_run)
    host_rehearsal_module._run_readonly_host_command(["pmset", "-g", "batt"])
    host_rehearsal_module._run_readonly_host_command(
        list(host_rehearsal_module._SNTP_CLOCK_COMMAND)
    )
    host_rehearsal_module._run_readonly_admin_host_command(
        list(host_rehearsal_module._ADMIN_NETWORK_TIME_COMMAND)
    )

    assert observed == [
        (("pmset", "-g", "batt"), 5.0),
        (host_rehearsal_module._SNTP_CLOCK_COMMAND, 15.0),
        (host_rehearsal_module._ADMIN_NETWORK_TIME_COMMAND, 120.0),
    ]


@pytest.mark.parametrize(
    ("argv", "expected_exit_code"),
    ((["--help"], 0), (["--unknown"], 2), (["--"], 2)),
)
def test_host_rehearsal_cli_meta_arguments_never_start_preparation(
    argv: list[str],
    expected_exit_code: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_calls: list[str] = []

    def forbidden_clean_main(**_kwargs: object) -> None:
        preparation_calls.append("clean-main")

    monkeypatch.setattr(
        host_rehearsal_script,
        "require_clean_main",
        forbidden_clean_main,
    )

    with pytest.raises(SystemExit) as raised:
        host_rehearsal_script.main(argv)

    assert raised.value.code == expected_exit_code
    assert preparation_calls == []


def test_admin_host_runner_rejects_every_nonfixed_command() -> None:
    with pytest.raises(
        V4ActualHostKillRehearsalError,
        match="ADMIN_HOST_COMMAND_FORBIDDEN",
    ):
        host_rehearsal_module._run_readonly_admin_host_command(
            ["/usr/sbin/systemsetup", "-setusingnetworktime", "on"]
        )


def test_preparation_ledger_rejects_symlink_fixed_state_before_resolve(
    tmp_path: Path,
    external_gate: V4ExternalPreparationGate,
) -> None:
    state_root = external_gate.state_root_for_internal_preparation_only()
    state_root.parent.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "target"
    target.mkdir()
    state_root.symlink_to(target, target_is_directory=True)
    with pytest.raises(
        V4ActualPreparationGuardError, match="STATE_SYMLINK_FORBIDDEN"
    ):
        V4PreparationAttemptLedger(external_gate=external_gate)


def _one_usd_jpy_ticker_handler(timestamp: str) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/public/v1/status":
            return httpx.Response(200, json={"status": 0, "data": {"status": "OPEN"}})
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": [
                    {
                        "symbol": "USD_JPY",
                        "ask": "160.005",
                        "bid": "160.000",
                        "timestamp": timestamp,
                        "status": "OPEN",
                    }
                ],
            },
        )

    return handler


def test_public_preflight_tolerates_behind_clock_within_op30_skew(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUBLIC_GET,
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            _one_usd_jpy_ticker_handler("2026-07-17T00:00:02Z")
        )
    )
    # Local clock is 2s BEHIND the quote timestamp (age = -2s): a clock-skew
    # artifact within op30's +/-5s tolerance, not a stale quote.
    report = V4GmoFinitePublicPreflight(
        external_gate=external_gate,
        operation_permit=permit,
        client=client,
        wall_clock=lambda: datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC),
    ).run_once()
    assert report.quote_age_seconds == -2.0
    assert report.quote_fresh is True
    assert report.status == "PASSED_PUBLIC_STATUS_TICKER_SANITIZED_NO_BROKER_POST"
    ledger.complete(V4PreparationOperation.PUBLIC_GET, operation_permit=permit)
    client.close()


def test_public_preflight_still_rejects_quote_beyond_clock_skew_window(
    external_gate: V4ExternalPreparationGate,
) -> None:
    _, permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.PUBLIC_GET,
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            _one_usd_jpy_ticker_handler("2026-07-17T00:00:07Z")
        )
    )
    # age = -7s exceeds the +/-5s window -> not fresh -> blocked (gross clock
    # error, which op30 would also fail). The staleness upper bound is unchanged.
    report = V4GmoFinitePublicPreflight(
        external_gate=external_gate,
        operation_permit=permit,
        client=client,
        wall_clock=lambda: datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC),
    ).run_once()
    assert report.quote_age_seconds == -7.0
    assert report.quote_fresh is False
    assert report.status == "BLOCKED_PUBLIC_STATUS_TICKER_NOT_CLEAR"
    client.close()
