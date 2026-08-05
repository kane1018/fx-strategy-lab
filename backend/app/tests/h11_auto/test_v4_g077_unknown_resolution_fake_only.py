"""Fake-only acceptance tests for the G077 unknown-resolution read-back (v1.1)."""

from __future__ import annotations

import fcntl
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.h11_v4_g077_runtime import (
    ACTION_CONFIRMED,
    G077_GENERATION_LABEL,
    G077_MAX_RESOLUTIONS_PER_GENERATION,
    G077_MIN_READ_INTERVAL_SECONDS,
    G077_PERSISTENT_HALT_FILE,
    G077_PROCESS_LOCK_FILE,
    G077_RESOLUTION_BUDGET_FILE,
    G077_RESOLUTION_COMPLETION_BUDGET_SECONDS,
    G077_RESOLUTION_EVIDENCE_SUFFIX,
    G077_RESOLUTION_START_WINDOW_SECONDS,
    G077_RESOLUTION_STARTED_SUFFIX,
    NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION,
    TERMINAL_FOR_GENERATION,
    G077Error,
    G077FakeOnlyCallable,
    G077ReadBackSource,
    G077ResolutionState,
    G077SanitizedRead,
    G077WriteActionKind,
    g077_resolution_status,
    load_g077_resolution_evidence,
    run_g077_unknown_resolution_once,
)
from h11_v4_g077_reviewed_digest import (
    G077_REVIEWED_FILES,
    compute_g077_generation_digest,
    compute_g077_reviewed_files_digest,
)

REPOSITORY = Path(__file__).resolve().parents[4]
GEN = "sha256:" + "a" * 64
REVIEWED = "sha256:" + "b" * 64
SCOPE = "sha256:" + "c" * 64
SCOPE_B = "sha256:" + "d" * 64
SCOPE_C = "sha256:" + "e" * 64
SCOPE_D = "sha256:" + "f" * 64
NOW = datetime(2026, 8, 5, 1, 0, 0, tzinfo=UTC)


def _read(
    *,
    source: G077ReadBackSource,
    known: bool = True,
    count: int = 0,
    account_flat: bool = False,
    ownership_exact: bool = False,
    quantity_matches: bool = False,
    protection_confirmed: bool = False,
    active_orders_zero: bool = False,
    matched_execution_seen: bool = False,
) -> G077SanitizedRead:
    return G077SanitizedRead(
        source=source,
        known=known,
        count=count,
        account_flat=account_flat,
        ownership_exact=ownership_exact,
        quantity_matches=quantity_matches,
        protection_confirmed=protection_confirmed,
        active_orders_zero=active_orders_zero,
        matched_execution_seen=matched_execution_seen,
    )


def _client(
    *,
    executions: G077SanitizedRead | None = None,
    positions: G077SanitizedRead | None = None,
    orders: G077SanitizedRead | None = None,
    calls: dict[str, int] | None = None,
) -> G077FakeOnlyCallable:
    configured = {
        G077ReadBackSource.LATEST_EXECUTIONS: (
            executions
            if executions is not None
            else _read(source=G077ReadBackSource.LATEST_EXECUTIONS, known=True)
        ),
        G077ReadBackSource.OPEN_POSITIONS: (
            positions
            if positions is not None
            else _read(
                source=G077ReadBackSource.OPEN_POSITIONS,
                known=True,
                account_flat=True,
            )
        ),
        G077ReadBackSource.ACTIVE_ORDERS: (
            orders
            if orders is not None
            else _read(
                source=G077ReadBackSource.ACTIVE_ORDERS,
                known=True,
                active_orders_zero=True,
            )
        ),
    }
    seen: dict[str, int] = calls if calls is not None else {}

    def read_back(source: object, now_utc: object) -> G077SanitizedRead:
        assert now_utc is NOW
        if not isinstance(source, G077ReadBackSource):
            raise AssertionError("unexpected source")
        seen[source.value] = seen.get(source.value, 0) + 1
        if seen[source.value] > 1:
            raise AssertionError(f"source read twice: {source.value}")
        return configured[source]

    return G077FakeOnlyCallable(read_back)


class _Clock:
    """Deterministic monotonic clock + recorded sleeps."""

    def __init__(self, *, now: float = 1000.0, jump_after: int | None = None) -> None:
        self.now = now
        self.sleeps: list[float] = []
        self._calls = 0
        self._jump_after = jump_after

    def monotonic(self) -> float:
        self._calls += 1
        if self._jump_after is not None and self._calls > self._jump_after:
            return self.now + G077_RESOLUTION_COMPLETION_BUDGET_SECONDS + 10.0
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _run(
    tmp_path: Path,
    client: G077FakeOnlyCallable,
    *,
    action_kind: G077WriteActionKind = G077WriteActionKind.MARKET_ENTRY,
    scope: str = SCOPE,
    observed: datetime | None = None,
    now: datetime = NOW,
    clock: _Clock | None = None,
) -> str:
    kwargs: dict[str, object] = {}
    if clock is not None:
        kwargs["monotonic"] = clock.monotonic
        kwargs["sleep"] = clock.sleep
    return run_g077_unknown_resolution_once(
        state_root=tmp_path,
        generation_digest=GEN,
        reviewed_files_digest=REVIEWED,
        action_scope_digest=scope,
        action_kind=action_kind,
        read_back_client=client,
        unknown_observed_at_utc=observed if observed is not None else now,
        now_utc=now,
        **kwargs,
    )


def _evidence(tmp_path: Path, *, scope: str = SCOPE) -> dict[str, object]:
    return load_g077_resolution_evidence(state_root=tmp_path, action_scope_digest=scope)


def _executed_entry_client() -> G077FakeOnlyCallable:
    return _client(
        executions=_read(
            source=G077ReadBackSource.LATEST_EXECUTIONS,
            known=True,
            count=1,
            matched_execution_seen=True,
        ),
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            count=1,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=True,
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            count=1,
            active_orders_zero=False,
        ),
    )


def test_confirmed_executed(tmp_path):
    client = _executed_entry_client()
    assert _run(tmp_path, client) == G077ResolutionState.CONFIRMED_EXECUTED.value
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    evidence = _evidence(tmp_path)
    assert evidence["status"] == G077ResolutionState.CONFIRMED_EXECUTED.value
    assert evidence["resolution_policy"] == ACTION_CONFIRMED
    assert evidence["actual_post_authorized"] is False
    assert evidence["broker_post_authorized"] is False
    assert evidence["retry_attempted"] is False
    assert (
        tmp_path / f"g077-resolution.{SCOPE[7:]}{G077_RESOLUTION_STARTED_SUFFIX}"
    ).is_file()


def test_confirmed_not_executed_next_cycle(tmp_path):
    client = _client()  # default: flat + zero orders + no match
    assert _run(tmp_path, client) == G077ResolutionState.CONFIRMED_NOT_EXECUTED.value
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    evidence = _evidence(tmp_path)
    assert evidence["resolution_policy"] == NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION


def test_partial_fill_is_terminal_halt(tmp_path):
    client = _client(
        executions=_read(
            source=G077ReadBackSource.LATEST_EXECUTIONS,
            known=True,
            count=1,
            matched_execution_seen=True,
        ),
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            count=1,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=False,  # size differs -> partial fill
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            count=1,
            active_orders_zero=False,
        ),
    )
    assert _run(tmp_path, client) == G077ResolutionState.CONFIRMED_PARTIAL_FILL.value
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_PARTIAL_FILL_TERMINAL"
    evidence = _evidence(tmp_path)
    assert evidence["resolution_policy"] == TERMINAL_FOR_GENERATION
    assert evidence["partial_fill"] is True


def test_first_read_failure_is_unresolved_halt_and_stops_reading(tmp_path):
    calls: dict[str, int] = {}
    client = _client(
        executions=_read(source=G077ReadBackSource.LATEST_EXECUTIONS, known=False),
        calls=calls,
    )
    assert _run(tmp_path, client) == G077ResolutionState.UNRESOLVED.value
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_READ_BACK_UNKNOWN"
    assert set(calls) == {G077ReadBackSource.LATEST_EXECUTIONS.value}
    evidence = _evidence(tmp_path)
    assert evidence["reads_completed"] == 1


def test_ambiguous_observation_is_unresolved_halt(tmp_path):
    # A matched execution with a flat account and zero active orders is
    # ambiguous for an entry: either it was closed again immediately or the
    # execution belongs to a different cycle -> UNRESOLVED (fail-closed).
    client = _client(
        executions=_read(
            source=G077ReadBackSource.LATEST_EXECUTIONS,
            known=True,
            matched_execution_seen=True,
        ),
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            account_flat=True,
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=True,
        ),
    )
    assert _run(tmp_path, client) == G077ResolutionState.UNRESOLVED.value
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_RESOLUTION_AMBIGUOUS"


def test_scope_marker_blocks_retry(tmp_path):
    client = _executed_entry_client()
    assert _run(tmp_path, client) == G077ResolutionState.CONFIRMED_EXECUTED.value
    with pytest.raises(G077Error, match="G077_RESOLUTION_ALREADY_STARTED_NO_RETRY"):
        _run(tmp_path, client)


def test_different_scope_allowed_within_budget(tmp_path):
    assert _run(tmp_path, _executed_entry_client(), scope=SCOPE) == (
        G077ResolutionState.CONFIRMED_EXECUTED.value
    )
    assert _run(
        tmp_path,
        _client(),  # flat + zero orders -> exit confirmed executed
        action_kind=G077WriteActionKind.POSITION_SPECIFIC_EXIT,
        scope=SCOPE_B,
    ) == G077ResolutionState.CONFIRMED_EXECUTED.value
    budget = json.loads(
        (tmp_path / G077_RESOLUTION_BUDGET_FILE).read_text(encoding="utf-8")
    )
    assert budget["resolutions_used"] == 2
    assert budget["resolutions_limit"] == G077_MAX_RESOLUTIONS_PER_GENERATION


def test_budget_exceeded_after_three_scopes(tmp_path):
    for scope in (SCOPE, SCOPE_B, SCOPE_C):
        assert _run(tmp_path, _executed_entry_client(), scope=scope) == (
            G077ResolutionState.CONFIRMED_EXECUTED.value
        )
    with pytest.raises(G077Error, match="G077_RESOLUTION_BUDGET_EXCEEDED"):
        _run(tmp_path, _executed_entry_client(), scope=SCOPE_D)


def test_start_window_exceeded_rejected_before_marker(tmp_path):
    client = _executed_entry_client()
    observed = NOW - timedelta(
        seconds=int(G077_RESOLUTION_START_WINDOW_SECONDS) + 1
    )
    with pytest.raises(G077Error, match="G077_RESOLUTION_START_WINDOW_EXCEEDED"):
        _run(tmp_path, client, observed=observed)
    assert not list(tmp_path.glob(f"g077-resolution.*{G077_RESOLUTION_STARTED_SUFFIX}"))
    assert not list(tmp_path.glob(f"g077-resolution.*{G077_RESOLUTION_EVIDENCE_SUFFIX}"))
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()


def test_completion_timeout_is_unresolved_halt(tmp_path):
    clock = _Clock(jump_after=1)  # first monotonic()=start, second jumps > 60s
    client = _executed_entry_client()
    assert _run(tmp_path, client, clock=clock) == G077ResolutionState.UNRESOLVED.value
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_RESOLUTION_TIMEOUT"
    evidence = _evidence(tmp_path)
    assert evidence["timed_out"] is True


def test_read_pacing_enforces_min_interval(tmp_path):
    clock = _Clock()
    client = _client()
    _run(tmp_path, client, clock=clock)
    assert clock.sleeps and all(
        value >= G077_MIN_READ_INTERVAL_SECONDS - 1e-9 for value in clock.sleeps
    )
    assert sum(clock.sleeps) >= G077_MIN_READ_INTERVAL_SECONDS * 2


def test_process_lock_held_rejected(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    lock_path = tmp_path / G077_PROCESS_LOCK_FILE
    holder = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(G077Error, match="G077_PROCESS_LOCK_HELD"):
            _run(tmp_path, _executed_entry_client())
    finally:
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()


def test_non_fake_read_back_client_rejected(tmp_path):
    def read_back(source: object, now_utc: object) -> object:
        raise AssertionError("must not be called")

    with pytest.raises(G077Error, match="G077_FAKE_ONLY_READ_BACK_REQUIRED"):
        _run(tmp_path, read_back)  # type: ignore[arg-type]


def test_each_source_read_at_most_once(tmp_path):
    # The _client helper raises AssertionError if any source is read twice, so
    # a successful run proves each source was read exactly once.
    assert _run(tmp_path, _executed_entry_client(), scope=SCOPE_B) == (
        G077ResolutionState.CONFIRMED_EXECUTED.value
    )
    budget = json.loads(
        (tmp_path / G077_RESOLUTION_BUDGET_FILE).read_text(encoding="utf-8")
    )
    assert budget["resolutions_used"] == 1


def test_evidence_artifact_digest_and_binding(tmp_path):
    _run(tmp_path, _executed_entry_client())
    evidence = _evidence(tmp_path)
    assert evidence["schema"] == "H11_V4_G077_RESOLUTION_EVIDENCE_V1"
    assert evidence["generation_label"] == G077_GENERATION_LABEL
    assert evidence["generation_digest"] == GEN
    assert evidence["reviewed_files_digest"] == REVIEWED
    assert evidence["action_scope_digest"] == SCOPE
    base = {key: value for key, value in evidence.items() if key != "artifact_digest"}
    import hashlib

    expected = "sha256:" + hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert evidence["artifact_digest"] == expected


def test_read_back_contract_violation_is_halt_and_rejected(tmp_path):
    def bad_client(source: object, now_utc: object) -> object:
        return {"not": "a sanitized read"}

    with pytest.raises(G077Error, match="G077_READ_BACK_CONTRACT_INVALID"):
        _run(tmp_path, G077FakeOnlyCallable(bad_client))
    assert (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_RESOLUTION_INTERNAL_FAILURE"


def test_sanitized_read_is_never_truthy():
    read = _read(source=G077ReadBackSource.LATEST_EXECUTIONS, known=True, count=5)
    assert bool(read) is False


def test_exit_kind_semantics(tmp_path):
    # exit executed: flat + zero orders
    executed = _client(
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS, known=True, account_flat=True
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=True,
        ),
    )
    assert _run(
        tmp_path, executed, action_kind=G077WriteActionKind.POSITION_SPECIFIC_EXIT
    ) == G077ResolutionState.CONFIRMED_EXECUTED.value
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    # exit not executed: position still owned exactly -> next cycle fresh
    still_owned = _client(
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=True,
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=False,
        ),
    )
    assert _run(
        tmp_path,
        still_owned,
        action_kind=G077WriteActionKind.POSITION_SPECIFIC_EXIT,
        scope=SCOPE_B,
    ) == G077ResolutionState.CONFIRMED_NOT_EXECUTED.value
    evidence = _evidence(tmp_path, scope=SCOPE_B)
    assert evidence["resolution_policy"] == NEXT_SCHEDULED_CYCLE_FRESH_OBSERVATION
    # exit semantics only distinguish flat vs owned: a size-mismatched owned
    # position is still CONFIRMED_NOT_EXECUTED (next cycle), not ambiguous.
    size_mismatch = _client(
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=False,
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=False,
        ),
    )
    assert _run(
        tmp_path,
        size_mismatch,
        action_kind=G077WriteActionKind.POSITION_SPECIFIC_EXIT,
        scope=SCOPE_C,
    ) == G077ResolutionState.CONFIRMED_NOT_EXECUTED.value
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    # The exit test uses exactly three of the three-resolution budget; a
    # fourth scope would raise G077_RESOLUTION_BUDGET_EXCEEDED (covered by
    # test_budget_exceeded_after_three_scopes).


def test_oco_kind_semantics(tmp_path):
    protected = _client(
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=True,
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=False,
        ),
    )
    assert _run(
        tmp_path, protected, action_kind=G077WriteActionKind.EXACT_SIZE_OCO_PROTECTION
    ) == G077ResolutionState.CONFIRMED_EXECUTED.value
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    # OCO not executed while flat -> protection moot -> next cycle
    flat = _client(
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS, known=True, account_flat=True
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=True,
        ),
    )
    assert _run(
        tmp_path,
        flat,
        action_kind=G077WriteActionKind.EXACT_SIZE_OCO_PROTECTION,
        scope=SCOPE_B,
    ) == G077ResolutionState.CONFIRMED_NOT_EXECUTED.value
    # OCO protection gap: owned but unprotected -> UNRESOLVED halt
    gap = _client(
        positions=_read(
            source=G077ReadBackSource.OPEN_POSITIONS,
            known=True,
            account_flat=False,
            ownership_exact=True,
            quantity_matches=True,
            protection_confirmed=False,
        ),
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=False,
        ),
    )
    assert _run(
        tmp_path,
        gap,
        action_kind=G077WriteActionKind.EXACT_SIZE_OCO_PROTECTION,
        scope=SCOPE_C,
    ) == G077ResolutionState.UNRESOLVED.value
    assert (tmp_path / G077_PERSISTENT_HALT_FILE).exists()


def test_cancel_kind_semantics(tmp_path):
    cancelled = _client(
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=True,
        )
    )
    assert _run(
        tmp_path, cancelled, action_kind=G077WriteActionKind.CANCEL_UNFILLED_REMAINDER
    ) == G077ResolutionState.CONFIRMED_EXECUTED.value
    assert not (tmp_path / G077_PERSISTENT_HALT_FILE).exists()
    pending = _client(
        orders=_read(
            source=G077ReadBackSource.ACTIVE_ORDERS,
            known=True,
            active_orders_zero=False,
            count=1,
        )
    )
    assert _run(
        tmp_path,
        pending,
        action_kind=G077WriteActionKind.CANCEL_UNFILLED_REMAINDER,
        scope=SCOPE_B,
    ) == G077ResolutionState.CONFIRMED_NOT_EXECUTED.value
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_RESOLUTION_TERMINAL"
    assert _evidence(tmp_path, scope=SCOPE_B)["resolution_policy"] == TERMINAL_FOR_GENERATION


def test_initial_activation_kind_is_terminal(tmp_path):
    client = _executed_entry_client()
    assert _run(
        tmp_path, client, action_kind=G077WriteActionKind.INITIAL_ACTIVATION
    ) == G077ResolutionState.UNRESOLVED.value
    halt = json.loads(
        (tmp_path / G077_PERSISTENT_HALT_FILE).read_text(encoding="utf-8")
    )
    assert halt["reason"] == "G077_RESOLUTION_AMBIGUOUS"


def test_status_projection_without_evidence(tmp_path):
    status = g077_resolution_status(state_root=tmp_path)
    assert status["resolution_state"] == G077ResolutionState.NOT_REQUIRED.value
    assert status["evidence_present"] is False
    assert status["resolutions_used"] == 0
    assert status["actual_post_authorized"] is False
    assert status["broker_post_authorized"] is False


def test_status_projection_with_evidence(tmp_path):
    _run(tmp_path, _executed_entry_client())
    status = g077_resolution_status(state_root=tmp_path)
    assert status["resolution_state"] == G077ResolutionState.CONFIRMED_EXECUTED.value
    assert status["evidence_present"] is True
    assert status["resolutions_used"] == 1
    assert status["resolutions"][0]["scope_token"] == SCOPE[7:]
    assert status["resolutions"][0]["status"] == G077ResolutionState.CONFIRMED_EXECUTED.value


def test_status_projection_with_invalid_evidence(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / f"g077-resolution.{'f' * 64}{G077_RESOLUTION_EVIDENCE_SUFFIX}").write_text(
        '{"schema":"wrong","status":"CONFIRMED_EXECUTED"}', encoding="utf-8"
    )
    status = g077_resolution_status(state_root=tmp_path)
    assert status["resolution_state"] == G077ResolutionState.UNRESOLVED.value
    assert status["resolutions"][0]["evidence_invalid"] is True


def test_module_source_scan_no_external_paths():
    module = (
        REPOSITORY / "backend/app/services/h11_v4_g077_runtime.py"
    ).read_text(encoding="utf-8")
    for token in (
        "import httpx",
        "httpx.",
        "find-generic-password",
        "smtplib",
        "subprocess",
        "import requests",
        "Pushover",
    ):
        assert token not in module


def test_reviewed_digest_self_consistent():
    reviewed = compute_g077_reviewed_files_digest(repository=REPOSITORY)
    assert reviewed.startswith("sha256:")
    artifact_path = REPOSITORY / "docs/templates/h11_v4_g077_frozen_generation.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["reviewed_files_digest"] == reviewed  # frozen binding value
    # Binding fields are nulled during hashing: changing them keeps the digest.
    original = artifact_path.read_text(encoding="utf-8")
    artifact["reviewed_files_digest"] = "sha256:" + "f" * 64
    artifact["implementation_digest"] = "sha256:" + "e" * 64
    try:
        artifact_path.write_text(
            json.dumps(artifact, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        assert compute_g077_reviewed_files_digest(repository=REPOSITORY) == reviewed
    finally:
        artifact_path.write_text(original, encoding="utf-8")
    # Every reviewed file exists and is a regular file.
    for relative in G077_REVIEWED_FILES:
        path = REPOSITORY / relative
        assert path.is_file() and not path.is_symlink()


def test_generation_digest_ignores_binding_fields():
    first = compute_g077_generation_digest(repository=REPOSITORY)
    assert first.startswith("sha256:")
    artifact_path = REPOSITORY / "docs/templates/h11_v4_g077_frozen_generation.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["generation_label"] == G077_GENERATION_LABEL
    original = artifact_path.read_text(encoding="utf-8")
    artifact["runtime_commissioning_evidence_digest"] = "sha256:" + "f" * 64
    artifact["successor_halt_release_digest"] = "sha256:" + "e" * 64
    artifact["unknown_resolution_contract_digest"] = "sha256:" + "d" * 64
    try:
        artifact_path.write_text(
            json.dumps(artifact, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        assert compute_g077_generation_digest(repository=REPOSITORY) == first
    finally:
        artifact_path.write_text(original, encoding="utf-8")
