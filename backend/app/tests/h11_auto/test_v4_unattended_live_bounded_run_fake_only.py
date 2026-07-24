from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import httpx
import pytest

from app.h11_auto import v4_gmo_canary_activation as activation_module
from app.services import h11_v4_gmo_g013_canary as canary_module
from app.services import h11_v4_unattended_live_orchestration as orchestration_module
from app.services.h11_v4_gmo_actual_transport import V4GmoSealedCredentialPair
from app.services.h11_v4_gmo_g013_canary import V4GmoG013PreparedSession

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "h11_auto_v4_unattended_live_bounded_run.py"
)


def _load_subject():
    spec = importlib.util.spec_from_file_location("_bounded_run_subject", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec: dataclass's __future__-annotations resolution
    # looks the module up in sys.modules by __module__ name during class
    # creation, and fails with an unhelpful AttributeError if it isn't there.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


subject = _load_subject()


def _fake_session() -> SimpleNamespace:
    return SimpleNamespace(intent=object())


def _kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "session": cast(V4GmoG013PreparedSession, _fake_session()),
        "risk_store": object(),
        "risk_policy": object(),
        "dead_man_store": object(),
        "heartbeat_chain_store": object(),
        "notification_ready": True,
        "entry_gate_reason_provider": lambda _now: (),
        "credential_pair": cast(V4GmoSealedCredentialPair, object()),
        "client": cast(httpx.Client, object()),
    }
    values.update(overrides)
    return values


def test_main_signature_requires_every_dependency_with_no_default() -> None:
    signature = inspect.signature(subject.main)
    for name in (
        "session",
        "risk_store",
        "risk_policy",
        "dead_man_store",
        "heartbeat_chain_store",
        "notification_ready",
        "entry_gate_reason_provider",
        "credential_pair",
        "client",
    ):
        assert signature.parameters[name].default is inspect.Parameter.empty, name


def test_max_cycles_out_of_range_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        subject.main(["--max-cycles", "0"], **_kwargs())
    with pytest.raises(SystemExit):
        subject.main(["--max-cycles", "10000"], **_kwargs())


def test_interval_seconds_out_of_range_errors() -> None:
    with pytest.raises(SystemExit):
        subject.main(["--max-cycles", "1", "--interval-seconds", "-1"], **_kwargs())
    with pytest.raises(SystemExit):
        subject.main(
            ["--max-cycles", "1", "--interval-seconds", "999999"], **_kwargs()
        )


def test_max_cycles_and_interval_seconds_exact_boundary_values_are_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pins the exact boundary, not just "some valid value" -- an off-by-one
    # in `1 <= args.max_cycles <= _MAXIMUM_CYCLES` (e.g. changed to `<`)
    # would only be caught by exercising the boundary itself.
    call_count = 0

    def _raise_gate_not_clear(**_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        raise activation_module.V4GmoCanaryActivationError(
            "V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
        )

    monkeypatch.setattr(
        orchestration_module,
        "run_unattended_live_entry_cycle_once",
        _raise_gate_not_clear,
    )
    monkeypatch.setattr(subject.time, "sleep", lambda _seconds: None)
    exit_code = subject.main(
        ["--max-cycles", str(subject._MAXIMUM_CYCLES), "--interval-seconds", "3600"],
        **_kwargs(),
    )
    assert exit_code == 0
    assert call_count == subject._MAXIMUM_CYCLES


def test_max_cycles_one_above_maximum_is_rejected() -> None:
    with pytest.raises(SystemExit):
        subject.main(
            ["--max-cycles", str(subject._MAXIMUM_CYCLES + 1)], **_kwargs()
        )


def test_interval_seconds_one_above_maximum_is_rejected() -> None:
    with pytest.raises(SystemExit):
        subject.main(
            [
                "--max-cycles",
                "1",
                "--interval-seconds",
                str(subject._MAXIMUM_INTERVAL_SECONDS + 1),
            ],
            **_kwargs(),
        )


def test_non_numeric_argv_is_rejected_by_argparse_itself(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Distinct code path from the explicit parser.error(...) range checks:
    # argparse's own type= coercion failure, exiting with status 2 before
    # this file's own range-check code ever runs.
    with pytest.raises(SystemExit) as excinfo:
        subject.main(["--max-cycles", "not-a-number"], **_kwargs())
    assert excinfo.value.code == 2
    assert "invalid int value" in capsys.readouterr().err


def test_integrity_drift_labels_propagate_and_abort_the_loop_instead_of_retrying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # These two labels mean the reviewed implementation digest or the frozen
    # generation changed underneath an already-running session -- a
    # tamper/drift signal, not a routine gate-timing wait. Must never be
    # folded into ordinary "not yet, try again" retries.
    for label in (
        "G013_IMPLEMENTATION_CHANGED_BEFORE_PERMIT",
        "G013_GENERATION_CHANGED_BEFORE_PERMIT",
    ):
        call_count = 0

        def _raise(label: str = label, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise canary_module.V4GmoG013CanaryError(label)

        monkeypatch.setattr(
            orchestration_module, "run_unattended_live_entry_cycle_once", _raise
        )
        with pytest.raises(canary_module.V4GmoG013CanaryError, match=label):
            subject.main(["--max-cycles", "5", "--interval-seconds", "0"], **_kwargs())
        assert call_count == 1, label


def test_provider_is_called_exactly_once_per_cycle_with_that_cycles_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls: list[object] = []
    cycle_clocks: list[object] = []

    def _provider(now: object) -> tuple[str, ...]:
        provider_calls.append(now)
        return ("ENTRY_GATE_MARKET_NOT_OPEN",)

    def _record_cycle(**kwargs: object) -> None:
        cycle_clocks.append(kwargs["now_utc"])
        raise activation_module.V4GmoCanaryActivationError(
            "V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
        )

    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", _record_cycle
    )
    subject.main(
        ["--max-cycles", "3", "--interval-seconds", "0"],
        **_kwargs(entry_gate_reason_provider=_provider),
    )
    assert len(provider_calls) == 3
    # The provider and the orchestration call receive the SAME clock value
    # within each cycle -- the same-cycle property §9.2 item 4 requires.
    assert provider_calls == cycle_clocks


def test_provider_result_reaches_the_orchestration_call_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reasons = ("ENTRY_GATE_SPREAD_LIMIT_EXCEEDED", "ENTRY_GATE_QUOTE_NOT_FRESH")
    seen: list[object] = []

    def _capture(**kwargs: object) -> None:
        seen.append(kwargs["entry_gate_blocked_reasons"])
        raise activation_module.V4GmoCanaryActivationError(
            "V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
        )

    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", _capture
    )
    subject.main(
        ["--max-cycles", "1", "--interval-seconds", "0"],
        **_kwargs(entry_gate_reason_provider=lambda _now: reasons),
    )
    assert seen == [reasons]


def test_provider_returning_non_tuple_aborts_the_run_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration = MagicMock()
    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", orchestration
    )
    with pytest.raises(
        subject.V4UnattendedLiveRunnerError,
        match="UNATTENDED_RUNNER_ENTRY_GATE_PROVIDER_INVALID",
    ):
        subject.main(
            ["--max-cycles", "5", "--interval-seconds", "0"],
            **_kwargs(entry_gate_reason_provider=lambda _now: ["a", "list"]),
        )
    orchestration.assert_not_called()


@pytest.mark.parametrize(
    "bad_result",
    (
        ("ENTRY_GATE_QUOTE_NOT_FRESH", None),
        (1, 2),
        (b"ENTRY_GATE_QUOTE_INVALID",),
    ),
)
def test_provider_tuple_with_non_string_elements_also_aborts_before_orchestration(
    monkeypatch: pytest.MonkeyPatch, bad_result: tuple[object, ...]
) -> None:
    # The container check alone would let a tuple of non-strings slip through
    # to the decision layer's own validation, whose DECISION_INVALID raise is
    # in the caught not-yet list -- silently burning the cycle budget on a
    # programming error. Element types must be checked here, before anything
    # downstream runs.
    orchestration = MagicMock()
    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", orchestration
    )
    with pytest.raises(
        subject.V4UnattendedLiveRunnerError,
        match="UNATTENDED_RUNNER_ENTRY_GATE_PROVIDER_INVALID",
    ):
        subject.main(
            ["--max-cycles", "5", "--interval-seconds", "0"],
            **_kwargs(entry_gate_reason_provider=lambda _now: bad_result),
        )
    orchestration.assert_not_called()


def test_decision_invalid_label_aborts_instead_of_being_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A charset-invalid (but str-typed) label passes the runner's element
    # check and is rejected by the decision layer as
    # V4_CANARY_UNATTENDED_DECISION_INVALID -- always a programming error,
    # never a market condition, so it must abort the run, not burn cycles.
    call_count = 0

    def _raise_decision_invalid(**_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        raise activation_module.V4GmoCanaryActivationError(
            "V4_CANARY_UNATTENDED_DECISION_INVALID"
        )

    monkeypatch.setattr(
        orchestration_module,
        "run_unattended_live_entry_cycle_once",
        _raise_decision_invalid,
    )
    with pytest.raises(
        activation_module.V4GmoCanaryActivationError,
        match="V4_CANARY_UNATTENDED_DECISION_INVALID",
    ):
        subject.main(
            ["--max-cycles", "5", "--interval-seconds", "0"],
            **_kwargs(entry_gate_reason_provider=lambda _now: ("bad-charset!",)),
        )
    assert call_count == 1


def test_provider_raising_aborts_the_run_rather_than_being_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    def _raising_provider(_now: object) -> tuple[str, ...]:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("provider fetch blew up")

    orchestration = MagicMock()
    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", orchestration
    )
    with pytest.raises(RuntimeError, match="provider fetch blew up"):
        subject.main(
            ["--max-cycles", "5", "--interval-seconds", "0"],
            **_kwargs(entry_gate_reason_provider=_raising_provider),
        )
    assert call_count == 1
    orchestration.assert_not_called()


def test_runner_error_type_is_not_in_the_caught_not_yet_list() -> None:
    assert subject.V4UnattendedLiveRunnerError not in subject._EXPECTED_NOT_YET_ERRORS
    assert not any(
        issubclass(subject.V4UnattendedLiveRunnerError, caught)
        for caught in subject._EXPECTED_NOT_YET_ERRORS
    )


def test_expected_not_yet_errors_are_caught_and_loop_continues(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    call_count = 0

    def _raise_gate_not_clear(**_kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        raise activation_module.V4GmoCanaryActivationError(
            "V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
        )

    monkeypatch.setattr(
        orchestration_module,
        "run_unattended_live_entry_cycle_once",
        _raise_gate_not_clear,
    )
    exit_code = subject.main(
        ["--max-cycles", "3", "--interval-seconds", "0"], **_kwargs()
    )
    assert exit_code == 0
    assert call_count == 3
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == 3
    for line in lines:
        assert "UNATTENDED_LIVE_CYCLE_NOT_YET" in line


@pytest.mark.parametrize(
    "error",
    (
        orchestration_module.V4UnattendedLiveOrchestrationError(
            "UNATTENDED_ORCHESTRATION_CREDENTIAL_OR_CLIENT_REQUIRED"
        ),
        canary_module.V4GmoG013CanaryError("G013_REVALIDATION_BLOCKED"),
    ),
)
def test_other_known_safe_label_error_types_are_also_caught(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def _raise(**_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", _raise
    )
    exit_code = subject.main(
        ["--max-cycles", "1", "--interval-seconds", "0"], **_kwargs()
    )
    assert exit_code == 0


def test_unexpected_exception_types_are_not_caught_and_abort_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(**_kwargs: object) -> None:
        raise RuntimeError("something genuinely unexpected")

    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", _raise
    )
    with pytest.raises(RuntimeError, match="something genuinely unexpected"):
        subject.main(["--max-cycles", "3", "--interval-seconds", "0"], **_kwargs())


def test_successful_cycle_stops_the_loop_early(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    call_count = 0

    def _succeed(**_kwargs: object):
        nonlocal call_count
        call_count += 1
        return canary_module.V4GmoG013CanaryResult(
            status="ENTRY_NOT_ACCEPTED_HALT",
            entry_post_attempt_count=1,
            cancel_post_attempt_count=0,
            protection_post_attempt_count=0,
            exact_protection_confirmed=False,
            flat_reconciled=False,
            persistent_halt=False,
        )

    monkeypatch.setattr(
        orchestration_module, "run_unattended_live_entry_cycle_once", _succeed
    )
    exit_code = subject.main(
        ["--max-cycles", "5", "--interval-seconds", "0"], **_kwargs()
    )
    assert exit_code == 0
    assert call_count == 1
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == 1
    assert "ENTRY_NOT_ACCEPTED_HALT" in lines[0]


def test_interval_sleep_is_skipped_after_the_final_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(subject.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    def _raise_gate_not_clear(**_kwargs: object) -> None:
        raise activation_module.V4GmoCanaryActivationError(
            "V4_CANARY_UNATTENDED_GATE_NOT_CLEAR"
        )

    monkeypatch.setattr(
        orchestration_module,
        "run_unattended_live_entry_cycle_once",
        _raise_gate_not_clear,
    )
    subject.main(["--max-cycles", "3", "--interval-seconds", "7"], **_kwargs())
    assert sleep_calls == [7.0, 7.0]


def test_running_the_file_directly_never_reaches_main_or_constructs_anything() -> None:
    import os

    backend_root = _SCRIPT_PATH.parents[1]
    env = {**os.environ, "PYTHONPATH": str(backend_root)}
    completed = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=backend_root,
        env=env,
    )
    assert completed.returncode != 0
    assert "cannot be run directly" in completed.stderr
    assert "credential_pair" in completed.stderr


def test_dunder_main_block_never_calls_main_with_any_arguments() -> None:
    # Structural check, independent of the subprocess test above: the
    # __main__ block's own AST must never contain a call to main(...).
    tree = ast.parse(_SCRIPT_PATH.read_text(encoding="utf-8"))
    module_body = tree.body
    dunder_main = next(
        node
        for node in module_body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )
    for node in ast.walk(dunder_main):
        if isinstance(node, ast.Call):
            assert not (isinstance(node.func, ast.Name) and node.func.id == "main")


def test_never_references_real_credential_or_transport_constructors() -> None:
    forbidden = {"V4GmoKeychainCredentialPair", "V4GmoHttpxPrivateTransport"}
    tree = ast.parse(_SCRIPT_PATH.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in forbidden:
            hits.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in forbidden:
            hits.append(node.attr)
        elif isinstance(node, ast.alias) and (
            node.name in forbidden or node.asname in forbidden
        ):
            hits.append(node.name)
    assert hits == []


def test_module_contains_no_dangerous_tokens() -> None:
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    for token in (
        "os.environ",
        "os.getenv",
        "keyring",
        "find-generic-password",
        "load_dotenv",
        "launchd",
        "cron",
        "LaunchAgent",
    ):
        assert token not in source, token
