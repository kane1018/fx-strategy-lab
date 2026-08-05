"""Fake-only acceptance tests for the G078 read-back resolution wiring.

The wiring connects an UNKNOWN write outcome to the one-use G078 read-back
resolution step and enforces the C1 remainder contract: any refused or failed
resolution while an UNKNOWN exists is terminal (persistent halt), except when
a valid evidence file already records the outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.h11_v4_g078_runtime import (
    ACTION_CONFIRMED,
    NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION,
    TERMINAL_FOR_GENERATION,
    G078FakeOnlyCallable,
    G078ReadBackSource,
    G078ResolutionState,
    G078SanitizedRead,
    G078WriteActionKind,
    engage_g078_halt,
)
from app.services.h11_v4_g078_unknown_resolution_wiring import (
    G078_WIRING_HALT_REASON,
    G078WiringError,
    G078WiringOutcome,
    wire_unknown_write_outcome_resolution_once,
)

GEN = "sha256:" + "a" * 64
REVIEWED = "sha256:" + "b" * 64
SCOPE = "sha256:" + "c" * 64
SCOPE_B = "sha256:" + "d" * 64
NOW = datetime(2026, 8, 5, 1, 0, 0, tzinfo=UTC)

HALT_FILE = "g078-persistent-halt.json"


def _read(
    *,
    source: G078ReadBackSource,
    known: bool = True,
    account_flat: bool = False,
    ownership_exact: bool = False,
    quantity_matches: bool = False,
    active_orders_zero: bool = False,
    matched_execution_seen: bool = False,
) -> G078SanitizedRead:
    return G078SanitizedRead(
        source=source,
        known=known,
        count=0,
        account_flat=account_flat,
        ownership_exact=ownership_exact,
        quantity_matches=quantity_matches,
        protection_confirmed=False,
        active_orders_zero=active_orders_zero,
        matched_execution_seen=matched_execution_seen,
    )


def _client(
    *,
    executions: G078SanitizedRead | None = None,
    positions: G078SanitizedRead | None = None,
    orders: G078SanitizedRead | None = None,
    calls: dict[str, int] | None = None,
) -> G078FakeOnlyCallable:
    configured = {
        G078ReadBackSource.LATEST_EXECUTIONS: (
            executions
            if executions is not None
            else _read(source=G078ReadBackSource.LATEST_EXECUTIONS)
        ),
        G078ReadBackSource.OPEN_POSITIONS: (
            positions
            if positions is not None
            else _read(source=G078ReadBackSource.OPEN_POSITIONS, account_flat=True)
        ),
        G078ReadBackSource.ACTIVE_ORDERS: (
            orders
            if orders is not None
            else _read(source=G078ReadBackSource.ACTIVE_ORDERS, active_orders_zero=True)
        ),
    }
    seen: dict[str, int] = calls if calls is not None else {}

    def read_back(source: object, now_utc: object) -> G078SanitizedRead:
        assert now_utc is NOW
        if not isinstance(source, G078ReadBackSource):
            raise AssertionError("unexpected source")
        seen[source.value] = seen.get(source.value, 0) + 1
        if seen[source.value] > 1:
            raise AssertionError(f"source read twice: {source.value}")
        return configured[source]

    return G078FakeOnlyCallable(read_back)


def _executed_entry_client() -> G078FakeOnlyCallable:
    return _client(
        executions=_read(
            source=G078ReadBackSource.LATEST_EXECUTIONS, matched_execution_seen=True
        ),
        positions=_read(
            source=G078ReadBackSource.OPEN_POSITIONS,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=True,
        ),
        orders=_read(
            source=G078ReadBackSource.ACTIVE_ORDERS, active_orders_zero=True
        ),
    )


def _not_executed_client() -> G078FakeOnlyCallable:
    # Still-owned position for an exit: the exit did not execute.
    return _client(
        executions=_read(source=G078ReadBackSource.LATEST_EXECUTIONS),
        positions=_read(
            source=G078ReadBackSource.OPEN_POSITIONS,
            account_flat=False,
            ownership_exact=True,
        ),
        orders=_read(
            source=G078ReadBackSource.ACTIVE_ORDERS, active_orders_zero=True
        ),
    )


def _ambiguous_client() -> G078FakeOnlyCallable:
    return _client(
        executions=_read(
            source=G078ReadBackSource.LATEST_EXECUTIONS, matched_execution_seen=True
        ),
        positions=_read(source=G078ReadBackSource.OPEN_POSITIONS, account_flat=True),
        orders=_read(
            source=G078ReadBackSource.ACTIVE_ORDERS, active_orders_zero=True
        ),
    )


def _raising_client() -> G078FakeOnlyCallable:
    def read_back(source: object, now_utc: object) -> G078SanitizedRead:
        raise RuntimeError("boom")

    return G078FakeOnlyCallable(read_back)


def _wire(
    tmp_path: Path,
    client: G078FakeOnlyCallable,
    *,
    scope: str = SCOPE,
    action_kind: G078WriteActionKind = G078WriteActionKind.MARKET_ENTRY,
    observed: datetime | None = None,
    observed_monotonic: float | None = None,
) -> G078WiringOutcome:
    return wire_unknown_write_outcome_resolution_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        action_scope_digest=scope,
        action_kind=action_kind,
        read_back_client=client,
        unknown_observed_at_utc=observed if observed is not None else NOW,
        now_utc=NOW,
        unknown_observed_monotonic=observed_monotonic,
    )


def _halt_reason(tmp_path: Path) -> str | None:
    path = tmp_path / HALT_FILE
    if not path.is_file():
        return None
    import json

    return str(json.loads(path.read_text(encoding="utf-8"))["reason"])


def test_wiring_confirmed_executed(tmp_path):
    outcome = _wire(tmp_path, _executed_entry_client())
    assert outcome.resolution_state == G078ResolutionState.CONFIRMED_EXECUTED.value
    assert outcome.resolution_policy == ACTION_CONFIRMED
    assert outcome.halt_engaged is False
    assert outcome.halt_reason is None
    assert outcome.action_kind == G078WriteActionKind.MARKET_ENTRY.value


def test_wiring_confirmed_not_executed(tmp_path):
    outcome = _wire(
        tmp_path,
        _not_executed_client(),
        action_kind=G078WriteActionKind.POSITION_SPECIFIC_EXIT,
    )
    assert outcome.resolution_state == G078ResolutionState.CONFIRMED_NOT_EXECUTED.value
    assert outcome.resolution_policy == NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION
    assert outcome.halt_engaged is False


def test_wiring_unresolved_latches_halt(tmp_path):
    outcome = _wire(tmp_path, _ambiguous_client())
    assert outcome.resolution_state == G078ResolutionState.UNRESOLVED.value
    assert outcome.resolution_policy == TERMINAL_FOR_GENERATION
    assert outcome.halt_engaged is True
    assert outcome.halt_reason == "G078_RESOLUTION_AMBIGUOUS"


def test_wiring_start_window_exceeded_preserves_module_halt(tmp_path):
    observed = NOW - timedelta(seconds=16)
    with pytest.raises(G078WiringError, match=G078_WIRING_HALT_REASON):
        _wire(tmp_path, _executed_entry_client(), observed=observed)
    # The module's specific reason must NOT be clobbered by the wiring layer.
    assert _halt_reason(tmp_path) == "G078_RESOLUTION_START_WINDOW_EXCEEDED"


def test_wiring_refused_resolution_latches_halt(tmp_path):
    # A started marker with no evidence: the resolution step refuses
    # (already-started, no retry) and the wiring treats the UNKNOWN as
    # terminal (C1 remainder).
    marker = tmp_path / f"g078-resolution.{SCOPE[7:]}.started.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"status": "STARTED"}', encoding="utf-8")
    with pytest.raises(G078WiringError, match=G078_WIRING_HALT_REASON):
        _wire(tmp_path, _executed_entry_client())
    assert _halt_reason(tmp_path) == G078_WIRING_HALT_REASON


def test_wiring_already_resolved_returns_recorded_outcome(tmp_path):
    first = _wire(tmp_path, _executed_entry_client())
    assert first.resolution_state == G078ResolutionState.CONFIRMED_EXECUTED.value
    # Re-invocation for the same scope: the recorded evidence governs.
    second = _wire(tmp_path, _executed_entry_client())
    assert second.resolution_state == G078ResolutionState.CONFIRMED_EXECUTED.value
    assert second.resolution_policy == ACTION_CONFIRMED
    assert second.halt_engaged is False


def test_wiring_unexpected_client_exception_latches_halt(tmp_path):
    # A non-G078 exception inside the resolution step is not caught by the
    # resolution module; the wiring must still leave a terminal record.
    with pytest.raises(G078WiringError, match=G078_WIRING_HALT_REASON):
        _wire(tmp_path, _raising_client())
    assert _halt_reason(tmp_path) == G078_WIRING_HALT_REASON


def test_wiring_non_fake_client_rejected(tmp_path):
    with pytest.raises(G078WiringError, match="G078_WIRING_FAKE_ONLY_READ_BACK_REQUIRED"):
        wire_unknown_write_outcome_resolution_once(
            state_root=tmp_path,
            generation_digest=GEN,
            reviewed_files_digest=REVIEWED,
            action_scope_digest=SCOPE,
            action_kind=G078WriteActionKind.MARKET_ENTRY,
            read_back_client=lambda s, n: _read(source=G078ReadBackSource.OPEN_POSITIONS),
            unknown_observed_at_utc=NOW,
            now_utc=NOW,
        )
    assert _halt_reason(tmp_path) is None


def test_wiring_bad_digest_rejected(tmp_path):
    with pytest.raises(G078WiringError, match="G078_WIRING_GENERATION_DIGEST_INVALID"):
        wire_unknown_write_outcome_resolution_once(
            state_root=tmp_path,
            generation_digest="not-a-digest",
            reviewed_files_digest=REVIEWED,
            action_scope_digest=SCOPE,
            action_kind=G078WriteActionKind.MARKET_ENTRY,
            read_back_client=_executed_entry_client(),
            unknown_observed_at_utc=NOW,
            now_utc=NOW,
        )
    assert _halt_reason(tmp_path) is None


def test_wiring_outcome_never_truthy(tmp_path):
    outcome = _wire(tmp_path, _executed_entry_client())
    assert bool(outcome) is False
    assert outcome.actual_post_authorized is False
    assert outcome.broker_post_authorized is False
    assert outcome.entry_authorized is False


def test_wiring_does_not_clear_existing_halt(tmp_path):
    engage_g078_halt(state_root=tmp_path, reason="PRE_EXISTING_HALT")
    with pytest.raises(G078WiringError, match=G078_WIRING_HALT_REASON):
        _wire(tmp_path, _raising_client())
    assert _halt_reason(tmp_path) == "PRE_EXISTING_HALT"


def test_wiring_module_source_scan_no_external_paths():
    source = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "h11_v4_g078_unknown_resolution_wiring.py"
    )
    content = source.read_text(encoding="utf-8")
    for token in (
        "import httpx",
        "httpx.",
        "find-generic-password",
        "smtplib",
        "subprocess",
        "import requests",
        "Pushover",
        "os.environ",
        "launchd",
        "/private/v1",
        "/public/v1",
    ):
        assert token not in content, token


def test_wiring_imports_resolution_step_directly():
    # The wiring must delegate to the one-use resolution step (no re-implemented
    # classification) and never construct its own allow values.
    source = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "h11_v4_g078_unknown_resolution_wiring.py"
    )
    content = source.read_text(encoding="utf-8")
    assert "run_g078_unknown_resolution_once(" in content
    assert "actual_post_authorized=True" not in content
    assert "broker_post_authorized=True" not in content
    assert "entry_authorized=True" not in content
