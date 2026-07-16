from __future__ import annotations

import inspect
import json
import subprocess
import traceback
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from app.h11_auto import v4_actual_preparation_guard as guard_module
from app.h11_auto.v4_actual_host_kill_rehearsal import (
    run_actual_host_kill_rehearsal,
)
from app.h11_auto.v4_actual_preparation_guard import (
    EMAIL_DELIVERY_CONFIRMATION,
    EXCLUSIVITY_CONFIRMATION,
    V4ActualPreparationGuardError,
    V4ExternalPreparationGate,
    V4PreparationAttemptLedger,
    V4PreparationOperation,
    V4PreparationOperationPermit,
    check_v4_keychain_access_internal_only,
    check_v4_keychain_presence_only,
    confirm_account_exclusivity_exact,
    confirm_email_delivery_exact,
    load_external_preparation_gate,
)
from app.services import h11_v4_gmo_readonly_preflight as readonly_module
from app.services import h11_v4_notification_actual_preparation as notification_actual_module
from app.services.h11_v4_gmo_readonly_preflight import (
    V4GmoFiniteReadOnlyPreflight,
    V4GmoReadOnlyPreflightError,
    V4GmoReadOnlySealedSecret,
)
from app.services.h11_v4_notification_actual_preparation import (
    H11V4ActualNotificationError,
    H11V4NotificationCredentialBundle,
    _SealedNotificationSecret,
    run_actual_notification_rehearsal_once,
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

    def ehlo(self) -> None:
        return None

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
        permit.consume_for(operation)
        ledger.complete(operation, operation_permit=permit)
    raise AssertionError("target preparation operation was not found")


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
    assert [timeout for _, timeout in calls] == [120.0, 110.0, 100.0, 90.0, 80.0, 70.0]
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
    assert ledger.state_root.name == f"generation-{'a' * 64}"
    assert legacy_marker.read_text(encoding="utf-8") == "legacy marker retained\n"


def test_actual_keychain_readers_allow_interactive_prompt_time() -> None:
    notification_default = inspect.signature(
        notification_actual_module.read_notification_keychain_secret
    ).parameters["timeout_seconds"].default
    private_get_default = inspect.signature(
        readonly_module.read_v4_gmo_readonly_keychain_secret
    ).parameters["timeout_seconds"].default
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
        run_actual_notification_rehearsal_once(
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
        run_actual_notification_rehearsal_once(
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


def test_actual_notification_rehearsal_uses_one_send_per_route_and_ack_poll(
    external_gate: V4ExternalPreparationGate,
) -> None:
    reads: list[tuple[str, str]] = []

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        reads.append((service, account))
        values = {
            "pushover-api-token": "synthetic-token",
            "pushover-user-key": "synthetic-user",
            "smtp-username": "synthetic@example.invalid",
            "smtp-app-password": "synthetic-app-password",
        }
        return _SealedNotificationSecret(values[account])

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json={"status": 1, "receipt": "synthetic-receipt"})
        return httpx.Response(200, json={"status": 1, "acknowledged": 1, "expired": 0})

    smtp = FakeSmtp()
    fake_time = FakeTime()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.NOTIFICATION,
    )
    report = run_actual_notification_rehearsal_once(
        external_gate=external_gate,
        operation_permit=operation_permit,
        credentials=H11V4NotificationCredentialBundle(reader=reader),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        smtp_factory=lambda host, port, timeout: smtp,
        acknowledgement_timeout_seconds=15,
        receipt_poll_interval_seconds=5,
        monotonic_factory=fake_time.monotonic,
        sleep=fake_time.sleep,
    )
    assert len(reads) == 4
    assert calls == [
        ("POST", "/1/messages.json"),
        ("GET", "/1/receipts/synthetic-receipt.json"),
    ]
    assert report.pushover_application_send_count == 1
    assert report.pushover_acknowledged is True
    assert report.email_send_count == 1
    assert report.email_smtp_accepted is True
    assert report.email_delivery_operator_confirmed is False
    assert report.external_notification_send_count == 2
    assert report.broker_post_count == 0
    assert smtp.tls is True and smtp.logged_in is True and smtp.sent == 1


def test_private_get_preflight_is_three_gets_spaced_and_single_use(
    external_gate: V4ExternalPreparationGate,
) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
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
        ("GET", "/private/v1/latestExecutions"),
        ("GET", "/private/v1/openPositions"),
        ("GET", "/private/v1/activeOrders"),
    ]
    assert report.cadence_offsets_seconds == (0.0, 0.25, 0.5)
    assert report.usd_jpy_flat is True
    assert report.usd_jpy_active_orders_zero is True
    assert report.limited_usd_jpy_snapshot_clear is True
    assert report.account_wide_exclusivity_proven is False
    assert report.canary_preflight_clear is False
    assert report.broker_post_count == 0
    with pytest.raises(V4GmoReadOnlyPreflightError, match="SECOND_RUN_FORBIDDEN"):
        preflight.run_once()


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


def test_notification_secondary_email_is_attempted_after_pushover_failure(
    external_gate: V4ExternalPreparationGate,
) -> None:
    values = {
        "pushover-api-token": "secret-token-marker",
        "pushover-user-key": "secret-user-marker",
        "smtp-username": "synthetic@example.invalid",
        "smtp-app-password": "secret-password-marker",
    }

    def reader(service: str, account: str) -> _SealedNotificationSecret:
        del service
        return _SealedNotificationSecret(values[account])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic network failure", request=request)

    smtp = FakeSmtp()
    _, operation_permit = _permit_for(
        external_gate=external_gate,
        target=V4PreparationOperation.NOTIFICATION,
    )
    with pytest.raises(
        H11V4ActualNotificationError,
        match="NOTIFICATION_REHEARSAL_FAILED_NO_RETRY",
    ) as exc_info:
        run_actual_notification_rehearsal_once(
            external_gate=external_gate,
            operation_permit=operation_permit,
            credentials=H11V4NotificationCredentialBundle(reader=reader),
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            smtp_factory=lambda host, port, timeout: smtp,
        )
    rendered = "".join(
        traceback.format_exception(
            exc_info.type,
            exc_info.value,
            exc_info.tb,
        )
    )
    assert smtp.sent == 1
    for marker in values.values():
        assert marker not in rendered


def test_persistent_preparation_ledger_enforces_order_and_no_retry(
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    with pytest.raises(V4ActualPreparationGuardError, match="PREVIOUS_NOT_CLEAR"):
        ledger.begin(V4PreparationOperation.NOTIFICATION)
    presence_permit = ledger.begin(V4PreparationOperation.PRESENCE)
    with pytest.raises(V4ActualPreparationGuardError, match="ALREADY_ATTEMPTED"):
        V4PreparationAttemptLedger(external_gate=external_gate).begin(
            V4PreparationOperation.PRESENCE,
        )
    presence_permit.consume_for(V4PreparationOperation.PRESENCE)
    ledger.complete(
        V4PreparationOperation.PRESENCE,
        operation_permit=presence_permit,
    )
    with pytest.raises(V4ActualPreparationGuardError, match="PREVIOUS_NOT_CLEAR"):
        ledger.begin(V4PreparationOperation.NOTIFICATION)
    access_permit = ledger.begin(V4PreparationOperation.KEYCHAIN_ACCESS)
    access_permit.consume_for(V4PreparationOperation.KEYCHAIN_ACCESS)
    ledger.complete(
        V4PreparationOperation.KEYCHAIN_ACCESS,
        operation_permit=access_permit,
    )
    ledger.begin(V4PreparationOperation.NOTIFICATION)


def test_preparation_ledger_rejects_predecessor_from_other_review_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    external_gate: V4ExternalPreparationGate,
) -> None:
    ledger = V4PreparationAttemptLedger(external_gate=external_gate)
    permit = ledger.begin(V4PreparationOperation.PRESENCE)
    permit.consume_for(V4PreparationOperation.PRESENCE)
    ledger.complete(
        V4PreparationOperation.PRESENCE,
        operation_permit=permit,
    )

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
            V4PreparationOperation.NOTIFICATION
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
    host_permit = ledger.begin(V4PreparationOperation.HOST_KILL)
    host_permit.consume_for(V4PreparationOperation.HOST_KILL)
    ledger.complete(
        V4PreparationOperation.HOST_KILL,
        operation_permit=host_permit,
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
    assert report.actual_runtime_process_killed is False
    assert report.broker_post_count == 0


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
