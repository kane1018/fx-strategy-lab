"""P0-e: behavior tests for the unattended control API (no POST, fakes only).

Restored per the completion-plan handoff (P0-e was assigned to the
orchestrator, not the external implementer, so these tests are authored
independently of the implementation).  Every test drives the same entry
points the operator's UI uses; none depends on deleted generations.

The load-bearing behaviors pinned here:

1. ``unattended_auto_mode_requested`` fails CLOSED: if the current contract
   cannot be loaded, manual private GET stays blocked (True).
2. Manual private GET is blocked while armed, while a position is open, and
   while halted -- and unblocked only when disarmed with a quiet runtime.
3. ``turn_off`` (the stop lever) works even while an unresolved halt exists:
   halting the system must never lock the operator out of DISARM.
4. ``turn_off`` still refuses stale digests (409) -- stopping is always
   available but never on the wrong generation contract.
5. The CSRF/origin gate refuses foreign origins and mismatched tokens.
6. ``get_control_status`` degrades to 409, never to an unhandled error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.h11_manual import unattended_control_api as control
from app.services.h11_v4_unattended_live_arm_state import V4ArmDesiredState

_G075_LABEL = "H11_AUTO_30M_20260802_G075"


class _FakeGeneration:
    generation_label = _G075_LABEL
    digest = "sha256:" + "c" * 64


class _FakeContract:
    generation = _FakeGeneration()
    reviewed_files_digest = "sha256:" + "d" * 64


class _FakeArmCheck:
    def __init__(self, armed: bool) -> None:
        self.armed = armed


class _FakeArmStore:
    """Records set_desired_state calls; check() reports a fixed armed flag."""

    def __init__(self, *, armed: bool) -> None:
        self._armed = armed
        self.set_calls: list[dict[str, object]] = []

    def check(self, **_: object) -> _FakeArmCheck:
        return _FakeArmCheck(self._armed)

    def set_desired_state(self, **kwargs: object) -> None:
        self.set_calls.append(kwargs)


class _CsrfOkRequest:
    headers = {
        "origin": "http://127.0.0.1:8765",
        "x-h11-v4-control-csrf": "synthetic-token",
    }
    cookies = {"h11_v4_control_csrf": "synthetic-token"}


def _orphaned_halt(repository: Path) -> Path:
    root = (
        repository
        / "backend/market_data/h11_v4_gmo_actual_runtime"
        / ("generation-" + "9" * 64)
    )
    root.mkdir(parents=True)
    halt = root / "g074-persistent-halt.json"
    halt.write_text('{"reason": "TEST_ORPHANED_HALT"}', encoding="utf-8")
    return halt


# --- 1. fail-closed -----------------------------------------------------


def test_auto_mode_fails_closed_when_contract_cannot_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _broken_contract() -> object:
        raise OSError("contract unreadable")

    monkeypatch.setattr(control, "_load_current_contract", _broken_contract)
    assert control.unattended_auto_mode_requested() is True


# --- 2. blocked/unblocked matrix ---------------------------------------


@pytest.mark.parametrize(
    ("armed", "runtime_state", "expected"),
    [
        (True, "IDLE", True),
        (False, "POSITION_OPEN", True),
        (False, "HALTED", True),
        (False, "IDLE", False),
    ],
)
def test_auto_mode_matrix(
    monkeypatch: pytest.MonkeyPatch,
    armed: bool,
    runtime_state: str,
    expected: bool,
) -> None:
    monkeypatch.setattr(control, "_load_current_contract", lambda: _FakeContract())
    monkeypatch.setattr(
        control, "_arm_store", lambda contract: _FakeArmStore(armed=armed)
    )
    monkeypatch.setattr(
        control, "_runtime_projection", lambda contract: (runtime_state, None)
    )
    assert control.unattended_auto_mode_requested() is expected


# --- 3./4. the stop lever ----------------------------------------------


def test_turn_off_works_even_while_an_unresolved_halt_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DISARM must stay available under a halt: the same condition that makes
    turn_on refuse (Phase A) must never lock the operator out of stopping."""

    _orphaned_halt(tmp_path)
    store = _FakeArmStore(armed=True)
    monkeypatch.setattr(control, "REPOSITORY", tmp_path)
    monkeypatch.setattr(control, "require_clean_main", lambda *, repository: object())
    monkeypatch.setattr(control, "_load_current_contract", lambda: _FakeContract())
    monkeypatch.setattr(control, "_arm_store", lambda contract: store)
    monkeypatch.setattr(control, "_safe_status", lambda contract: {"ok": True})
    monkeypatch.setattr(control, "_require_local_csrf", lambda request: None)

    body = control.ArmChangeRequest(
        expected_revision=0,
        expected_generation_digest=_FakeContract.generation.digest,
        expected_reviewed_files_digest=_FakeContract.reviewed_files_digest,
    )
    result = control.turn_off(request_body=body, request=_CsrfOkRequest())
    assert result == {"ok": True}
    assert len(store.set_calls) == 1
    assert store.set_calls[0]["desired_state"] is V4ArmDesiredState.DISARMED


def test_turn_off_refuses_stale_generation_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeArmStore(armed=True)
    monkeypatch.setattr(control, "require_clean_main", lambda *, repository: object())
    monkeypatch.setattr(control, "_load_current_contract", lambda: _FakeContract())
    monkeypatch.setattr(control, "_arm_store", lambda contract: store)
    monkeypatch.setattr(control, "_require_local_csrf", lambda request: None)

    body = control.ArmChangeRequest(
        expected_revision=0,
        expected_generation_digest="sha256:" + "e" * 64,
        expected_reviewed_files_digest=_FakeContract.reviewed_files_digest,
    )
    with pytest.raises(HTTPException) as excinfo:
        control.turn_off(request_body=body, request=_CsrfOkRequest())
    assert excinfo.value.status_code == 409
    assert "ARM_STATE_GENERATION_MISMATCH" in str(excinfo.value.detail)
    assert store.set_calls == []


# --- 5. CSRF/origin gate ------------------------------------------------


def test_csrf_refuses_foreign_origin() -> None:
    class _ForeignRequest:
        headers = {
            "origin": "https://evil.example",
            "x-h11-v4-control-csrf": "synthetic-token",
        }
        cookies = {"h11_v4_control_csrf": "synthetic-token"}

    with pytest.raises(HTTPException) as excinfo:
        control._require_local_csrf(_ForeignRequest())
    assert excinfo.value.status_code == 403
    assert "ORIGIN_REFUSED" in str(excinfo.value.detail)


def test_csrf_refuses_token_mismatch() -> None:
    class _MismatchRequest:
        headers = {
            "origin": "http://127.0.0.1:8765",
            "x-h11-v4-control-csrf": "token-a",
        }
        cookies = {"h11_v4_control_csrf": "token-b"}

    with pytest.raises(HTTPException) as excinfo:
        control._require_local_csrf(_MismatchRequest())
    assert excinfo.value.status_code == 403
    assert "CSRF_REFUSED" in str(excinfo.value.detail)


# --- 6. status degrades safely -----------------------------------------


def test_control_status_degrades_to_409_when_contract_cannot_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _broken_contract() -> object:
        raise OSError("contract unreadable")

    monkeypatch.setattr(control, "_load_current_contract", _broken_contract)
    with pytest.raises(HTTPException) as excinfo:
        control.get_control_status()
    assert excinfo.value.status_code == 409
    assert "UNATTENDED_CONTROL_CURRENT_CONTRACT_NOT_CLEAR" in str(
        excinfo.value.detail
    )
